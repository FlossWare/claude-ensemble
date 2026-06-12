/**
 * Fleet Bulk Orchestration Framework
 *
 * Generic multi-session orchestration for bulk processing across fleet workers.
 * Used by all *-bulk skills (ai-pdf-deep-research-bulk, ai-web-learn-bulk, etc.)
 *
 * Pattern:
 *   1. Split input into N chunks (one per worker)
 *   2. Launch independent Claude Code session on each worker via SSH
 *   3. Each session runs a pre-built workflow with its chunk
 *   4. Collect results from each worker (files, JSON, or stdout)
 *   5. Merge results using skill-specific merge function
 *   6. Return unified output
 *
 * Key difference from code-test-fleet:
 *   - code-test-fleet: remoteExec() runs shell commands (test runners)
 *   - fleet-bulk-orchestration: remoteExec() launches Claude Code workflows
 *
 * Usage:
 *   import { bulkOrchestrate } from './fleet-bulk-orchestration.js';
 *
 *   const result = await bulkOrchestrate({
 *     skill: 'ai-pdf-deep-research',
 *     items: [...600 PDFs...],
 *     workerScript: 'workflows/ai-pdf-deep-research.js',
 *     mergeStrategy: (results) => concatenate_markdown(results),
 *     progressCallback: (w, done, total) => log(`${w}: ${done}/${total}`),
 *   });
 */

import { getWorkers, remoteExec } from './fleet-utils.js';
import {
  distributeItems,
  distributeItemsWeighted,
  nfsProjectPath,
  isOnNfs,
  workerTempDir,
  createFleetProgress,
} from './fleet-workflow-patterns.js';
import fs from 'fs';
import path from 'path';

// ============================================================================
// ORCHESTRATION ENGINE
// ============================================================================

/**
 * Main bulk orchestration function.
 *
 * @param {Object} config
 * @param {string} config.skill - Skill name (e.g., 'ai-pdf-deep-research')
 * @param {any[]} config.items - Items to process (PDFs, URLs, files, repos, topics)
 * @param {string} config.workerScript - Relative path to workflow script
 *   Example: 'workflows/ai-pdf-deep-research.js'
 *   Will be invoked as: claude --workflow ai-pdf-deep-research --args '<batch-json>'
 * @param {Function} config.mergeStrategy - (results[]) => mergedResult
 *   Called with array of per-worker results. Responsible for merging/concatenating.
 * @param {Function} [config.itemSerializer] - (items[]) => string
 *   Custom serializer for items (default: JSON.stringify)
 *   Useful for paths that need special escaping
 * @param {Function} [config.resultDeserializer] - (stdout) => object
 *   Custom deserializer for worker output (default: JSON.parse)
 *   Useful if workers output markdown or other formats
 * @param {Function} [config.progressCallback] - (hostname, completed, total) => void
 * @param {Function} [config.log] - Logging function (default: console.log)
 * @param {Object} [config.fleetOptions] - Options for getWorkers() filtering
 * @param {string} [config.distribution] - 'round-robin' or 'weighted' (default: 'round-robin')
 * @param {number} [config.minWorkers] - Minimum workers for fleet mode (default: 2)
 * @param {number} [config.timeout] - Per-worker timeout in ms (default: 600000 = 10 min)
 * @param {number} [config.maxRetries] - Retries per failed worker (default: 1)
 * @param {boolean} [config.dryRun] - Show distribution plan without executing (default: false)
 * @param {boolean} [config.useWeightedDistribution] - Distribute by worker memory (default: false)
 * @returns {Promise<Object>} {
 *   status: 'success'|'partial'|'failed',
 *   fleetUsed: boolean,
 *   workersUsed: number,
 *   itemsProcessed: number,
 *   totalItems: number,
 *   result: mergedResult,
 *   workerResults: { hostname: result },
 *   errors: [{ hostname, error }],
 * }
 */
export async function bulkOrchestrate(config) {
  const {
    skill,
    items,
    workerScript,
    mergeStrategy,
    itemSerializer = (items) => JSON.stringify(items),
    resultDeserializer = (stdout) => JSON.parse(stdout),
    progressCallback,
    log = console.log,
    fleetOptions = {},
    distribution = 'round-robin',
    minWorkers = 2,
    timeout = 600000,
    maxRetries = 1,
    dryRun = false,
    useWeightedDistribution = false,
  } = config;

  log('');
  log('='.repeat(70));
  log(`Bulk Orchestration: ${skill} (${items.length} items)`);
  log('='.repeat(70));
  log('');

  // ========================================================================
  // PHASE 1: Fleet Discovery
  // ========================================================================

  log('Phase 1: Fleet Discovery');

  let workers = [];
  try {
    workers = getWorkers(fleetOptions);
    if (workers.length >= minWorkers) {
      log(`Fleet available: ${workers.length} workers`);
      workers.forEach(w => log(`  - ${w.hostname} (${w.cpus}C/${w.memory_gb}GB)`));
    } else {
      log(`Insufficient workers (${workers.length}/${minWorkers}), running locally`);
      workers = [];
    }
  } catch (error) {
    log(`Fleet unavailable (${error.message}), running locally`);
  }

  // Check NFS visibility
  const projectDir = nfsProjectPath();
  if (workers.length > 0 && !isOnNfs(projectDir)) {
    log(`Project not on NFS, cannot use fleet`);
    workers = [];
  }

  log('');

  // ========================================================================
  // PHASE 2: Item Distribution
  // ========================================================================

  log('Phase 2: Item Distribution');

  let distribution_map;
  let useFleet = workers.length >= minWorkers;

  if (useFleet) {
    distribution_map = useWeightedDistribution
      ? distributeItemsWeighted(items, workers)
      : distributeItems(items, workers);

    log(`Distributing ${items.length} items across ${workers.length} workers (${distribution}):`);
    for (const [hostname, workerItems] of distribution_map.entries()) {
      log(`  ${hostname}: ${workerItems.length} items`);
      workerItems.slice(0, 2).forEach(item => {
        const itemStr = typeof item === 'string' ? item.slice(0, 60) : JSON.stringify(item).slice(0, 60);
        log(`    - ${itemStr}${itemStr.length >= 60 ? '...' : ''}`);
      });
      if (workerItems.length > 2) log(`    ... and ${workerItems.length - 2} more`);
    }
  } else {
    log('Fleet not available - running all items locally');
    distribution_map = new Map([['localhost', items]]);
  }

  log('');

  if (dryRun) {
    log('DRY RUN: No actual execution');
    return {
      status: 'dry_run',
      fleetUsed: useFleet,
      workersUsed: workers.length,
      distribution: Object.fromEntries(distribution_map),
      itemsProcessed: 0,
      totalItems: items.length,
      result: null,
      workerResults: {},
      errors: [],
    };
  }

  // ========================================================================
  // PHASE 3: Execute on Workers
  // ========================================================================

  log('Phase 3: Worker Execution');

  const workerResults = new Map();
  const errors = [];
  const progress = progressCallback
    ? createFleetProgress(items.length, workers.length, log)
    : null;

  const executeWorker = async (worker, workerItems, workerIndex) => {
    const hostname = worker.hostname === 'localhost' ? 'localhost' : worker.hostname;
    const itemsJson = itemSerializer(workerItems);

    if (hostname === 'localhost') {
      // Local execution
      log(`Executing locally (${workerItems.length} items)...`);
      try {
        const result = await agent(
          `Execute workflow with items:\n\n${itemsJson}`,
          {
            label: 'Local Execution',
            schema: {
              type: 'object',
              properties: {
                status: { type: 'string' },
                data: { type: 'object' },
              },
            }
          }
        );
        return result;
      } catch (error) {
        throw new Error(`Local execution failed: ${error.message}`);
      }
    } else {
      // Remote SSH execution
      log(`Starting on ${hostname} (${workerItems.length} items)...`);

      let lastError = null;
      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        if (attempt > 0) {
          log(`  Retrying ${hostname} (attempt ${attempt + 1}/${maxRetries + 1})...`);
        }

        try {
          // Build Claude Code command
          const workflowName = workerScript.replace(/^workflows\//, '').replace(/\.js$/, '');
          const argsJson = itemsJson.replace(/'/g, "'\\''");

          const command = `
            cd '${projectDir}' && \
            claude --workflow '${workflowName}' --args '${argsJson}' --json 2>&1
          `.trim();

          const result = remoteExec(hostname, command, { timeout });

          if (!result.success) {
            throw new Error(result.stderr || 'Unknown error');
          }

          // Parse result
          let parsed;
          try {
            parsed = resultDeserializer(result.stdout);
          } catch (parseError) {
            throw new Error(`Failed to parse worker output: ${parseError.message}`);
          }

          log(`  ${hostname}: execution complete (${workerItems.length} items)`);
          return parsed;

        } catch (error) {
          lastError = error;
          log(`  ${hostname} failed: ${error.message}`);
        }
      }

      throw lastError;
    }
  };

  // Execute all workers in parallel
  const execPromises = Array.from(distribution_map.entries()).map(
    async ([hostname, workerItems], idx) => {
      const worker = workers.find(w => w.hostname === hostname) || { hostname };

      try {
        const result = await executeWorker(worker, workerItems, idx);
        workerResults.set(hostname, result);

        if (progressCallback) {
          progressCallback(hostname, workerItems.length, items.length);
        }

        return { hostname, success: true, result };
      } catch (error) {
        errors.push({ hostname, error: error.message });
        log(`  ${hostname}: FAILED - ${error.message}`);
        return { hostname, success: false, error: error.message };
      }
    }
  );

  const outcomes = await Promise.all(execPromises);

  log('');

  // ========================================================================
  // PHASE 4: Result Merging
  // ========================================================================

  log('Phase 4: Result Merging');

  const successCount = outcomes.filter(o => o.success).length;
  log(`Workers successful: ${successCount}/${workers.length}`);

  if (successCount === 0) {
    log('No workers succeeded');
    return {
      status: 'failed',
      fleetUsed: useFleet,
      workersUsed: 0,
      itemsProcessed: 0,
      totalItems: items.length,
      result: null,
      workerResults: Object.fromEntries(workerResults),
      errors,
    };
  }

  try {
    const resultArray = Array.from(workerResults.values());
    const merged = mergeStrategy(resultArray);

    const itemsProcessed = outcomes
      .filter(o => o.success)
      .reduce((sum, o) => {
        const items = distribution_map.get(o.hostname) || [];
        return sum + items.length;
      }, 0);

    log('Merge complete');
    log('');
    log('='.repeat(70));
    log('BULK ORCHESTRATION COMPLETE');
    log('='.repeat(70));
    log(`Items processed: ${itemsProcessed}/${items.length}`);
    log(`Status: ${errors.length === 0 ? 'SUCCESS' : 'PARTIAL'}`);
    log('='.repeat(70));
    log('');

    return {
      status: errors.length === 0 ? 'success' : 'partial',
      fleetUsed: useFleet,
      workersUsed: successCount,
      itemsProcessed,
      totalItems: items.length,
      result: merged,
      workerResults: Object.fromEntries(workerResults),
      errors,
    };
  } catch (mergeError) {
    log(`Merge failed: ${mergeError.message}`);
    return {
      status: 'partial',
      fleetUsed: useFleet,
      workersUsed: successCount,
      itemsProcessed: outcomes.filter(o => o.success).length,
      totalItems: items.length,
      result: null,
      workerResults: Object.fromEntries(workerResults),
      errors: [...errors, { phase: 'merge', error: mergeError.message }],
    };
  }
}

// ============================================================================
// RESULT MERGING STRATEGIES
// ============================================================================

/**
 * Concatenate markdown results from multiple workers.
 * Used by ai-pdf-deep-research-bulk, deep-research-bulk.
 *
 * @param {Object[]} results - Array of worker results with 'markdown' field
 * @returns {string} Concatenated markdown
 */
export function mergeMarkdownResults(results) {
  return results
    .map(r => r.markdown || r.report || '')
    .filter(Boolean)
    .join('\n\n---\n\n');
}

/**
 * Merge JSON array results from multiple workers.
 * Used by ai-web-learn-bulk, code-security-bulk.
 *
 * @param {Object[]} results - Array of worker results with 'data' or 'findings' field
 * @param {string} [key] - Field name containing array (default: 'data')
 * @returns {any[]} Merged array
 */
export function mergeArrayResults(results, key = 'data') {
  return results.flatMap(r => r[key] || []);
}

/**
 * Merge and deduplicate findings by semantic key.
 * Used by code-review-bulk, code-security-bulk.
 *
 * @param {Object[]} results - Array of results with 'findings' array
 * @param {Function} keyFn - (finding) => string for deduplication
 * @returns {Object[]} Deduplicated findings
 */
export function mergeAndDedupFindings(results, keyFn) {
  const all = results.flatMap(r => r.findings || []);
  const seen = new Map();

  for (const finding of all) {
    const key = keyFn(finding);
    if (!seen.has(key)) {
      seen.set(key, finding);
    } else {
      // Keep version with higher severity/confidence
      const existing = seen.get(key);
      const compareSeverity = (a, b) => {
        const rank = { critical: 4, high: 3, medium: 2, low: 1 };
        return (rank[b.severity] || 0) - (rank[a.severity] || 0);
      };
      if (compareSeverity(finding, existing) > 0) {
        seen.set(key, finding);
      }
    }
  }

  return Array.from(seen.values());
}

/**
 * Merge ChromaDB embedding results from multiple workers.
 * Each worker outputs embeddings as JSON; controller inserts into single DB.
 *
 * @param {Object[]} results - Array of results with 'embeddings' array
 * @returns {Object} { embeddings: [...], total_chunks: number }
 */
export function mergeEmbeddingResults(results) {
  const embeddings = [];
  let totalChunks = 0;

  for (const result of results) {
    if (result.embeddings) {
      embeddings.push(...result.embeddings);
      totalChunks += (result.embeddings.length || 0);
    }
  }

  return { embeddings, total_chunks: totalChunks };
}

/**
 * Merge test results from multiple workers.
 *
 * @param {Object[]} results - Array of test result objects
 * @returns {Object} Merged test summary
 */
export function mergeTestResults(results) {
  const merged = {
    total: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    failures: [],
  };

  for (const result of results) {
    merged.total += result.total || 0;
    merged.passed += result.passed || 0;
    merged.failed += result.failed || 0;
    merged.skipped += result.skipped || 0;
    if (result.failures) {
      merged.failures.push(...result.failures);
    }
  }

  return merged;
}

// ============================================================================
// BATCH FILE UTILITIES
// ============================================================================

/**
 * Save batch items to a file on NFS (for worker pickup).
 * Used when items are large (e.g., 600 PDFs) and passing via JSON is inefficient.
 *
 * @param {string[]} items - Items to save (file paths, URLs, etc.)
 * @param {string} skillName - Skill name for temp file naming
 * @returns {string} Path to saved batch file
 */
export function saveBatchFile(items, skillName) {
  const batchDir = path.join(nfsProjectPath(), '.claude', 'bulk-batches');
  if (!fs.existsSync(batchDir)) {
    fs.mkdirSync(batchDir, { recursive: true });
  }

  const batchFile = path.join(batchDir, `${skillName}-${Date.now()}.txt`);
  fs.writeFileSync(batchFile, items.join('\n'));
  return batchFile;
}

/**
 * Load items from a batch file.
 *
 * @param {string} filePath - Path to batch file
 * @returns {string[]} Items from file
 */
export function loadBatchFile(filePath) {
  return fs.readFileSync(filePath, 'utf8').split('\n').filter(Boolean);
}
