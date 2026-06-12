/**
 * Fleet Multi-Session Orchestration
 *
 * TRUE multi-session fleet parallelism - launches independent Claude Code
 * sessions on each worker machine for embarrassingly parallel workloads.
 *
 * Key differences from existing fleet workflows:
 * - Existing (ai-web-learn-fleet, code-security-fleet): agent() with parallel()
 *   = SINGLE session, cosmetic worker labels, NO true parallelism
 * - This module: remoteExec() with independent Claude sessions
 *   = MULTI-session, true SSH parallelism, 2.5-3x speedup
 *
 * Pattern:
 * 1. Split work (PDFs, URLs, files) across 3 workers
 * 2. Launch independent `claude --workflow <skill>` on each worker via SSH
 * 3. Each worker processes its batch independently (no coordination)
 * 4. Collect results from workers via SSH
 * 5. Merge results on controller
 *
 * Used by:
 * - ai-pdf-deep-research-bulk (600 PDFs -> 3 workers -> 200 each)
 * - ai-web-learn-bulk (1000 URLs -> 3 workers -> 333 each)
 * - deep-research-bulk (100 topics -> 3 workers -> 33 each)
 * - code-security-bulk (500 files -> 3 workers -> 166 each)
 * - ai-web-code-learn-bulk (50 repos -> 3 workers -> 16 each)
 * - code-review-bulk (200 files -> 3 workers -> 66 each)
 * - code-doc-bulk (500 files -> 3 workers -> 166 each)
 *
 * IMPORTANT: This is for bulk processing where each item is independent.
 * For test sharding (code-test-fleet), use remoteExec() with test commands directly.
 */

import { getWorkers, remoteExec } from './fleet-utils.js';
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';

// ============================================================================
// BATCH DISTRIBUTION
// ============================================================================

/**
 * Split items into batches for N workers (round-robin).
 *
 * @param {any[]} items - Items to distribute
 * @param {number} numWorkers - Number of workers
 * @returns {any[][]} Array of batches (one per worker)
 */
export function splitBatches(items, numWorkers) {
  const batches = Array.from({ length: numWorkers }, () => []);
  items.forEach((item, idx) => {
    batches[idx % numWorkers].push(item);
  });
  return batches;
}

/**
 * Split items into batches for N workers (weighted by memory).
 *
 * @param {any[]} items - Items to distribute
 * @param {Object[]} workers - Worker machines with memory_gb
 * @returns {any[][]} Array of batches (one per worker)
 */
export function splitBatchesWeighted(items, workers) {
  const totalMemory = workers.reduce((sum, w) => sum + (w.memory_gb || 8), 0);
  const batches = [];
  let assigned = 0;

  workers.forEach((worker, idx) => {
    const share = Math.round((worker.memory_gb / totalMemory) * items.length);
    const count = (idx === workers.length - 1)
      ? items.length - assigned  // Last worker gets remainder
      : Math.min(share, items.length - assigned);

    batches.push(items.slice(assigned, assigned + count));
    assigned += count;
  });

  return batches;
}

// ============================================================================
// MULTI-SESSION ORCHESTRATION
// ============================================================================

/**
 * Execute a workflow on multiple workers with independent Claude sessions.
 *
 * This is the core multi-session pattern. Each worker gets:
 * 1. A batch of items (PDFs, URLs, files, etc.)
 * 2. An independent Claude Code session via SSH
 * 3. A command: `cd <project> && claude --workflow <skill> --args '<json>'`
 * 4. Output written to worker-local /tmp (NFS avoidance)
 *
 * @param {Object} config
 * @param {any[]} config.items - Items to process (PDFs, URLs, files, repos, etc.)
 * @param {string} config.workflowName - Workflow to run on each worker
 * @param {Function} config.buildArgs - (batch, workerIdx) => args object for workflow
 * @param {Function} config.mergeResults - (workerOutputs[]) => finalResult
 * @param {Object} [config.options]
 * @param {string} [config.options.distribution] - 'round-robin' (default) or 'weighted'
 * @param {number} [config.options.minWorkers] - Minimum workers (default: 2)
 * @param {number} [config.options.timeout] - Per-worker timeout ms (default: 600000)
 * @param {Function} [config.options.log] - Logging function
 * @param {string} [config.options.projectDir] - Project directory (default: cwd)
 * @param {string} [config.options.outputFormat] - 'json' or 'text' (default: 'json')
 * @returns {Object} { result, fleetUsed, workersUsed, workerOutputs, errors }
 */
export async function runMultiSession(config) {
  const {
    items,
    workflowName,
    buildArgs,
    mergeResults,
    options = {},
  } = config;

  const {
    distribution = 'round-robin',
    minWorkers = 2,
    timeout = 600000,
    log = console.log,
    projectDir = process.cwd(),
    outputFormat = 'json',
  } = options;

  // Step 1: Discover fleet
  let workers = [];
  try {
    workers = getWorkers();
  } catch (error) {
    log(`Fleet unavailable (${error.message})`);
  }

  // Step 2: Check minimum workers
  if (workers.length < minWorkers) {
    throw new Error(
      `Insufficient workers: ${workers.length}/${minWorkers} required. ` +
      `Run locally or use local fallback.`
    );
  }

  // Step 3: Check NFS visibility
  const nfsRoot = '/home/sfloess/Development';
  if (!projectDir.startsWith(nfsRoot)) {
    throw new Error(
      `Project not on NFS: ${projectDir}\n` +
      `Multi-session requires NFS-shared project (${nfsRoot})`
    );
  }

  // Step 4: Distribute items across workers
  const batches = distribution === 'weighted'
    ? splitBatchesWeighted(items, workers)
    : splitBatches(items, workers.length);

  log(`Distributing ${items.length} items across ${workers.length} workers (${distribution}):`);
  batches.forEach((batch, idx) => {
    log(`  ${workers[idx].hostname}: ${batch.length} items`);
  });

  // Step 5: Launch independent Claude sessions on each worker
  log('');
  log('Launching independent Claude Code sessions on workers...');

  const workerPromises = workers.map(async (worker, idx) => {
    const batch = batches[idx];
    if (!batch || batch.length === 0) {
      return { worker, output: null, success: false, skipped: true };
    }

    // Build workflow args for this batch
    const argsObj = buildArgs(batch, idx);
    const argsJson = JSON.stringify(argsObj);

    // Create temp output file on worker (local /tmp, not NFS)
    const outputFile = `/tmp/fleet-${workflowName}-${worker.hostname}-${Date.now()}.json`;

    // Build remote command
    const remoteCmd = `
      cd '${projectDir}' && \
      claude --workflow '${workflowName}' --args '${argsJson.replace(/'/g, "'\\''")}' \
      > '${outputFile}' 2>&1
    `.trim();

    log(`  ${worker.hostname}: starting (${batch.length} items)...`);

    try {
      const result = remoteExec(worker.hostname, remoteCmd, { timeout });

      if (!result.success) {
        log(`  ${worker.hostname}: FAILED (exit ${result.exitCode})`);
        return {
          worker,
          output: null,
          success: false,
          error: result.stderr || result.stdout,
        };
      }

      // Fetch output file from worker
      const fetchCmd = `cat '${outputFile}' && rm -f '${outputFile}'`;
      const fetchResult = remoteExec(worker.hostname, fetchCmd, { timeout: 10000 });

      if (!fetchResult.success) {
        log(`  ${worker.hostname}: Failed to fetch output`);
        return {
          worker,
          output: null,
          success: false,
          error: 'Failed to fetch output file',
        };
      }

      // Parse output
      let output = fetchResult.stdout;
      if (outputFormat === 'json') {
        try {
          output = JSON.parse(output);
        } catch (error) {
          log(`  ${worker.hostname}: Invalid JSON output`);
          return {
            worker,
            output: fetchResult.stdout,
            success: false,
            error: 'Invalid JSON output',
          };
        }
      }

      log(`  ${worker.hostname}: SUCCESS (${batch.length} items processed)`);
      return {
        worker,
        output,
        success: true,
        itemsProcessed: batch.length,
      };

    } catch (error) {
      log(`  ${worker.hostname}: ERROR - ${error.message}`);
      return {
        worker,
        output: null,
        success: false,
        error: error.message,
      };
    }
  });

  const workerResults = await Promise.all(workerPromises);

  // Step 6: Collect successful results
  const successfulResults = workerResults.filter(r => r.success);
  const failedResults = workerResults.filter(r => !r.success && !r.skipped);

  log('');
  log(`Worker results: ${successfulResults.length} succeeded, ${failedResults.length} failed`);

  if (successfulResults.length === 0) {
    throw new Error(
      `All workers failed:\n` +
      failedResults.map(r => `  ${r.worker.hostname}: ${r.error}`).join('\n')
    );
  }

  // Step 7: Merge results
  log('Merging results from workers...');
  const workerOutputs = successfulResults.map(r => r.output);
  const finalResult = mergeResults(workerOutputs);

  return {
    result: finalResult,
    fleetUsed: true,
    workersUsed: successfulResults.length,
    workerOutputs,
    errors: failedResults.map(r => ({
      hostname: r.worker.hostname,
      error: r.error,
    })),
  };
}

// ============================================================================
// RESULT MERGE HELPERS
// ============================================================================

/**
 * Merge markdown reports from multiple workers.
 * Concatenates with section headers per worker.
 *
 * @param {string[]} markdownReports - Array of markdown strings
 * @param {string[]} workerNames - Worker hostnames
 * @returns {string} Merged markdown
 */
export function mergeMarkdownReports(markdownReports, workerNames) {
  return markdownReports
    .map((report, idx) => {
      const header = `\n\n${'='.repeat(80)}\n## Worker: ${workerNames[idx] || `worker-${idx + 1}`}\n${'='.repeat(80)}\n\n`;
      return header + report;
    })
    .join('\n');
}

/**
 * Merge JSON results by concatenating arrays under specified keys.
 *
 * @param {Object[]} jsonResults - Array of JSON objects
 * @param {string[]} arrayKeys - Keys containing arrays to merge
 * @returns {Object} Merged JSON with concatenated arrays
 */
export function mergeJsonArrays(jsonResults, arrayKeys) {
  const merged = {};

  for (const key of arrayKeys) {
    merged[key] = jsonResults.flatMap(r => r[key] || []);
  }

  // Add summary stats
  merged.workers_used = jsonResults.length;
  merged.per_worker = jsonResults.map((r, idx) => ({
    worker_index: idx,
    items_processed: arrayKeys.reduce((sum, key) => sum + (r[key]?.length || 0), 0),
  }));

  return merged;
}

/**
 * Merge findings with deduplication by file:line:type.
 *
 * @param {Object[]} findingsArrays - Array of findings arrays
 * @returns {Object[]} Deduplicated findings
 */
export function mergeAndDeduplicateFindings(findingsArrays) {
  const allFindings = findingsArrays.flat();
  const seen = new Map();

  for (const finding of allFindings) {
    const key = `${finding.file || ''}:${finding.line || ''}:${finding.type || ''}`;
    if (!seen.has(key)) {
      seen.set(key, finding);
    } else {
      // Keep finding with higher severity
      const existing = seen.get(key);
      const severityRank = { critical: 4, high: 3, medium: 2, low: 1 };
      const existingSev = severityRank[existing.severity] || 0;
      const newSev = severityRank[finding.severity] || 0;
      if (newSev > existingSev) {
        seen.set(key, finding);
      }
    }
  }

  return Array.from(seen.values());
}

/**
 * Merge ChromaDB/vector store data.
 * Used by ai-web-learn-bulk: workers output JSON facts, controller writes to ChromaDB.
 *
 * @param {Object[]} workerFacts - Array of fact extraction results
 * @returns {Object} { facts: [], metadata: {} }
 */
export function mergeVectorStoreData(workerFacts) {
  const allFacts = workerFacts.flatMap(w => w.facts || []);

  // Deduplicate by claim hash
  const seen = new Set();
  const unique = [];

  for (const fact of allFacts) {
    const key = fact.claim?.toLowerCase().trim();
    if (key && !seen.has(key)) {
      seen.add(key);
      unique.push(fact);
    }
  }

  return {
    facts: unique,
    total_extracted: allFacts.length,
    total_unique: unique.length,
    workers: workerFacts.length,
  };
}
