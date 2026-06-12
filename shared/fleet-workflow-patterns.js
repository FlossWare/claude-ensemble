/**
 * Fleet Workflow Patterns - Reusable abstractions for fleet-distributed workflows
 *
 * Provides high-level patterns for distributing work across fleet workers
 * with graceful fallback, error handling, and result merging.
 *
 * Usage:
 *   import { distributeAndMerge, parallelPhases, gracefulFallback, distributeItems }
 *     from '../shared/fleet-workflow-patterns.js';
 *
 * IMPORTANT: These patterns wrap fleet-utils.js and fleet-integration.js.
 * They handle the full lifecycle: discovery -> distribution -> execution -> merge -> fallback.
 *
 * Error Handling Strategy:
 *   - 1 worker fails: continue with remaining 2, log warning
 *   - 2+ workers fail: abort fleet, retry entire workload locally
 *   - Retry failed workers once before fallback
 *   - All operations have timeouts (configurable, default 5 min)
 *
 * NFS Coordination:
 *   - Unique temp dirs per worker: /tmp/fleet-<skill>-<worker>-<timestamp>
 *   - No lock files needed (NFS read-only for source, workers write to local /tmp)
 *   - Results collected via SSH after completion
 */

import { getWorkers, getFleet, remoteExec, loadFleetConfig, validateCompliance }
  from './fleet-utils.js';

// ============================================================================
// ITEM DISTRIBUTION
// ============================================================================

/**
 * Distribute items across workers using round-robin assignment.
 *
 * @param {any[]} items - Items to distribute
 * @param {Object[]} workers - Fleet worker machines
 * @returns {Map<string, any[]>} Map of hostname -> items assigned
 */
export function distributeItems(items, workers) {
  const distribution = new Map();
  workers.forEach(w => distribution.set(w.hostname, []));

  items.forEach((item, idx) => {
    const worker = workers[idx % workers.length];
    distribution.get(worker.hostname).push(item);
  });

  return distribution;
}

/**
 * Distribute items across workers using weighted assignment (by memory).
 * Workers with more memory get proportionally more items.
 *
 * @param {any[]} items - Items to distribute
 * @param {Object[]} workers - Fleet worker machines (must have memory_gb)
 * @returns {Map<string, any[]>} Map of hostname -> items assigned
 */
export function distributeItemsWeighted(items, workers) {
  const totalMemory = workers.reduce((sum, w) => sum + (w.memory_gb || 8), 0);
  const distribution = new Map();
  workers.forEach(w => distribution.set(w.hostname, []));

  let assigned = 0;
  workers.forEach((worker, wIdx) => {
    const share = Math.round((worker.memory_gb || 8) / totalMemory * items.length);
    // Last worker gets remaining items to avoid off-by-one
    const count = (wIdx === workers.length - 1)
      ? items.length - assigned
      : Math.min(share, items.length - assigned);

    for (let i = 0; i < count; i++) {
      distribution.get(worker.hostname).push(items[assigned + i]);
    }
    assigned += count;
  });

  return distribution;
}

// ============================================================================
// DISTRIBUTE AND MERGE PATTERN
// ============================================================================

/**
 * Core pattern: Distribute items across fleet workers, execute, and merge results.
 *
 * This is the fundamental fleet pattern used by most skills:
 * 1. Check fleet availability
 * 2. Distribute items across available workers
 * 3. Execute workerFn on each worker (with retry)
 * 4. Collect results
 * 5. Merge using mergeFn
 * 6. If fleet fails, fall back to localFn
 *
 * @param {Object} config
 * @param {any[]} config.items - Items to distribute (files, URLs, scan types, etc.)
 * @param {Function} config.workerFn - (worker, items, workerIndex) => result
 *   Called for each worker with its assigned items. Must return a result object.
 *   The worker argument is { hostname, cpus, memory_gb, ... }.
 * @param {Function} config.mergeFn - (results[]) => mergedResult
 *   Called with array of successful worker results. Returns final merged result.
 * @param {Function} [config.localFn] - (items) => result
 *   Fallback function when fleet is unavailable. If not provided, workerFn is
 *   called with a synthetic local worker.
 * @param {Function} [config.log] - Logging function (default: console.log)
 * @param {Object} [config.fleetOptions] - Options for getWorkers()
 * @param {string} [config.distribution] - 'round-robin' (default) or 'weighted'
 * @param {number} [config.minWorkers] - Minimum workers needed (default: 1)
 * @param {number} [config.maxRetries] - Retries per failed worker (default: 1)
 * @param {number} [config.timeout] - Per-worker timeout in ms (default: 300000)
 * @param {boolean} [config.abortOnMajorityFailure] - Abort if >50% workers fail (default: true)
 * @returns {Object} { result, fleetUsed, workersUsed, workerResults, errors }
 */
export async function distributeAndMerge(config) {
  const {
    items,
    workerFn,
    mergeFn,
    localFn,
    log = console.log,
    fleetOptions = {},
    distribution = 'round-robin',
    minWorkers = 1,
    maxRetries = 1,
    timeout = 300000,
    abortOnMajorityFailure = true,
  } = config;

  // Step 1: Discover fleet
  let workers = [];
  try {
    workers = getWorkers(fleetOptions);
  } catch (error) {
    log(`Fleet unavailable (${error.message}), running locally`);
  }

  // Step 2: Check minimum workers
  if (workers.length < minWorkers) {
    log(`Insufficient workers (${workers.length}/${minWorkers}), running locally`);

    if (localFn) {
      const result = await localFn(items);
      return {
        result,
        fleetUsed: false,
        workersUsed: 0,
        workerResults: [],
        errors: [],
      };
    }

    // Fallback: run workerFn with synthetic local worker
    const localWorker = { hostname: 'localhost', cpus: 0, memory_gb: 0, role: 'local' };
    const result = await workerFn(localWorker, items, 0);
    const merged = await mergeFn([result]);
    return {
      result: merged,
      fleetUsed: false,
      workersUsed: 0,
      workerResults: [result],
      errors: [],
    };
  }

  // Step 3: Distribute items
  log(`Distributing ${items.length} items across ${workers.length} workers (${distribution})`);

  const itemMap = distribution === 'weighted'
    ? distributeItemsWeighted(items, workers)
    : distributeItems(items, workers);

  // Log distribution
  for (const [hostname, workerItems] of itemMap.entries()) {
    log(`  ${hostname}: ${workerItems.length} items`);
  }

  // Step 4: Execute on each worker (with retry)
  const workerResults = [];
  const errors = [];

  const execPromises = workers.map(async (worker, wIdx) => {
    const workerItems = itemMap.get(worker.hostname);
    if (!workerItems || workerItems.length === 0) return null;

    let lastError = null;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          log(`  Retrying ${worker.hostname} (attempt ${attempt + 1}/${maxRetries + 1})`);
        }
        const result = await Promise.race([
          Promise.resolve(workerFn(worker, workerItems, wIdx)),
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error(`Timeout after ${timeout}ms`)), timeout)
          ),
        ]);
        return { worker, result, success: true };
      } catch (error) {
        lastError = error;
        log(`  Worker ${worker.hostname} failed: ${error.message}`);
      }
    }

    return { worker, error: lastError, success: false };
  });

  const outcomes = await Promise.all(execPromises);

  for (const outcome of outcomes) {
    if (!outcome) continue;
    if (outcome.success) {
      workerResults.push(outcome.result);
    } else {
      errors.push({
        hostname: outcome.worker.hostname,
        error: outcome.error.message,
      });
    }
  }

  // Step 5: Check for majority failure
  const failureRate = errors.length / workers.length;
  if (abortOnMajorityFailure && failureRate > 0.5) {
    log(`Majority failure (${errors.length}/${workers.length}), falling back to local`);

    if (localFn) {
      const result = await localFn(items);
      return {
        result,
        fleetUsed: false,
        workersUsed: 0,
        workerResults: [],
        errors,
        fallbackReason: 'majority_failure',
      };
    }
  }

  if (workerResults.length === 0) {
    log('All workers failed, attempting local execution');
    if (localFn) {
      const result = await localFn(items);
      return {
        result,
        fleetUsed: false,
        workersUsed: 0,
        workerResults: [],
        errors,
        fallbackReason: 'all_failed',
      };
    }
    throw new Error('All fleet workers failed and no local fallback provided');
  }

  // Step 6: Merge results
  if (errors.length > 0) {
    log(`Partial success: ${workerResults.length}/${workers.length} workers completed`);
  }

  const merged = await mergeFn(workerResults);

  return {
    result: merged,
    fleetUsed: true,
    workersUsed: workerResults.length,
    workerResults,
    errors,
  };
}

// ============================================================================
// PARALLEL PHASES PATTERN
// ============================================================================

/**
 * Execute independent phases in parallel across fleet workers.
 * Each phase is assigned to a specific worker.
 *
 * Used by code-sdlc-fleet for phases 4-6 (security, docs, release notes).
 *
 * @param {Object} config
 * @param {Object[]} config.phases - Array of phase definitions
 * @param {string} config.phases[].name - Phase name
 * @param {Function} config.phases[].fn - (worker) => result
 * @param {string} [config.phases[].preferredWorker] - Preferred hostname
 * @param {Object[]} [config.workers] - Workers to use (auto-discovered if not provided)
 * @param {Function} [config.log] - Logging function
 * @param {number} [config.timeout] - Per-phase timeout in ms (default: 600000)
 * @returns {Object} { results: Map<phaseName, result>, errors: Map<phaseName, error> }
 */
export async function parallelPhases(config) {
  const {
    phases,
    workers: providedWorkers,
    log = console.log,
    timeout = 600000,
  } = config;

  let workers = providedWorkers;
  if (!workers) {
    try {
      workers = getWorkers();
    } catch (error) {
      workers = [];
    }
  }

  // Assign phases to workers (round-robin, respecting preferences)
  const assignments = new Map();
  const usedWorkers = new Set();

  // First pass: assign preferred workers
  for (const phase of phases) {
    if (phase.preferredWorker) {
      const worker = workers.find(w => w.hostname === phase.preferredWorker);
      if (worker && !usedWorkers.has(worker.hostname)) {
        assignments.set(phase.name, { phase, worker });
        usedWorkers.add(worker.hostname);
      }
    }
  }

  // Second pass: assign remaining phases to available workers
  const availableWorkers = workers.filter(w => !usedWorkers.has(w.hostname));
  let workerIdx = 0;

  for (const phase of phases) {
    if (!assignments.has(phase.name)) {
      if (workers.length === 0) {
        // No fleet available - all phases run locally
        assignments.set(phase.name, {
          phase,
          worker: { hostname: 'localhost', role: 'local' },
        });
      } else {
        // Round-robin from all workers (may reuse if more phases than workers)
        const worker = workers[workerIdx % workers.length];
        assignments.set(phase.name, { phase, worker });
        workerIdx++;
      }
    }
  }

  // Log assignments
  for (const [name, { worker }] of assignments.entries()) {
    log(`  Phase "${name}" -> ${worker.hostname}`);
  }

  // Execute all phases in parallel
  const results = new Map();
  const errors = new Map();

  const execPromises = Array.from(assignments.entries()).map(
    async ([name, { phase, worker }]) => {
      try {
        const result = await Promise.race([
          Promise.resolve(phase.fn(worker)),
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error(`Phase "${name}" timed out after ${timeout}ms`)), timeout)
          ),
        ]);
        return { name, result, success: true };
      } catch (error) {
        return { name, error, success: false };
      }
    }
  );

  const outcomes = await Promise.all(execPromises);

  for (const outcome of outcomes) {
    if (outcome.success) {
      results.set(outcome.name, outcome.result);
    } else {
      errors.set(outcome.name, outcome.error.message);
      log(`  Phase "${outcome.name}" failed: ${outcome.error.message}`);
    }
  }

  return { results, errors };
}

// ============================================================================
// GRACEFUL FALLBACK PATTERN
// ============================================================================

/**
 * Try fleet execution first, fall back to local if fleet is unavailable or fails.
 *
 * @param {Function} fleetFn - (workers) => result. Called with available workers.
 * @param {Function} localFn - () => result. Called as fallback.
 * @param {Object} [options]
 * @param {Function} [options.log] - Logging function
 * @param {Object} [options.fleetOptions] - Options for getWorkers()
 * @returns {Object} { result, fleetUsed, workers }
 */
export async function gracefulFallback(fleetFn, localFn, options = {}) {
  const { log = console.log, fleetOptions = {} } = options;

  let workers = [];
  try {
    workers = getWorkers(fleetOptions);
  } catch (error) {
    log(`Fleet discovery failed: ${error.message}`);
  }

  if (workers.length === 0) {
    log('No fleet workers available, running locally');
    const result = await localFn();
    return { result, fleetUsed: false, workers: [] };
  }

  try {
    log(`Fleet available: ${workers.length} workers (${workers.map(w => w.hostname).join(', ')})`);
    const result = await fleetFn(workers);
    return { result, fleetUsed: true, workers };
  } catch (error) {
    log(`Fleet execution failed (${error.message}), falling back to local`);
    const result = await localFn();
    return { result, fleetUsed: false, workers: [], fallbackReason: error.message };
  }
}

// ============================================================================
// REMOTE COMMAND HELPERS
// ============================================================================

/**
 * Execute a command on a remote worker and parse JSON output.
 *
 * @param {Object} worker - Worker machine { hostname }
 * @param {string} command - Command to execute (must output JSON)
 * @param {Object} [options] - remoteExec options
 * @returns {Object|null} Parsed JSON result, or null on failure
 */
export function remoteExecJson(worker, command, options = {}) {
  const result = remoteExec(worker.hostname, command, options);

  if (!result.success) {
    return null;
  }

  try {
    return JSON.parse(result.stdout);
  } catch (error) {
    return null;
  }
}

/**
 * Execute a command on a remote worker, writing items to a temp file first.
 * Useful for passing large lists of files/URLs to remote commands.
 *
 * @param {Object} worker - Worker machine { hostname }
 * @param {string[]} items - List of items (file paths, URLs, etc.)
 * @param {string} commandTemplate - Command template with {{ITEMS_FILE}} placeholder
 * @param {Object} [options] - remoteExec options
 * @returns {Object} remoteExec result
 */
export function remoteExecWithItems(worker, items, commandTemplate, options = {}) {
  const itemsList = items.join('\n');
  // Create temp file with items, execute command, clean up
  const fullCommand = `
    ITEMS_FILE=$(mktemp /tmp/fleet-items-XXXXXX)
    echo '${itemsList.replace(/'/g, "'\\''")}' > "$ITEMS_FILE"
    ${commandTemplate.replace(/\{\{ITEMS_FILE\}\}/g, '"$ITEMS_FILE"')}
    EXIT_CODE=$?
    rm -f "$ITEMS_FILE"
    exit $EXIT_CODE
  `.trim();

  return remoteExec(worker.hostname, fullCommand, options);
}

// ============================================================================
// RESULT MERGING HELPERS
// ============================================================================

/**
 * Merge arrays from multiple worker results.
 * Concatenates arrays from the same key across all results.
 *
 * @param {Object[]} results - Array of worker results
 * @param {string} arrayKey - Key containing the array to merge
 * @returns {any[]} Merged array
 */
export function mergeArrays(results, arrayKey) {
  return results.flatMap(r => r[arrayKey] || []);
}

/**
 * Merge and deduplicate findings by file:line:type.
 * Used by code-security-fleet to remove duplicate findings across workers.
 *
 * @param {Object[]} findings - Array of finding objects
 * @param {Function} [keyFn] - Custom key function. Default: f => `${f.file}:${f.line}:${f.type}`
 * @returns {Object[]} Deduplicated findings
 */
export function deduplicateFindings(findings, keyFn) {
  const defaultKeyFn = (f) => `${f.file || ''}:${f.line || ''}:${f.type || ''}`;
  const getKey = keyFn || defaultKeyFn;
  const seen = new Map();

  for (const finding of findings) {
    const key = getKey(finding);
    if (!seen.has(key)) {
      seen.set(key, finding);
    } else {
      // Keep the finding with higher severity or confidence
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
 * Merge test results from multiple workers into a unified report.
 *
 * @param {Object[]} results - Array of per-worker test results
 * @returns {Object} Unified test report { total, passed, failed, skipped, details }
 */
export function mergeTestResults(results) {
  const merged = {
    total: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    errors: 0,
    details: [],
    per_worker: [],
  };

  for (const result of results) {
    const workerReport = {
      hostname: result.hostname || 'unknown',
      total: result.total || 0,
      passed: result.passed || 0,
      failed: result.failed || 0,
      skipped: result.skipped || 0,
    };

    merged.total += workerReport.total;
    merged.passed += workerReport.passed;
    merged.failed += workerReport.failed;
    merged.skipped += workerReport.skipped;
    merged.per_worker.push(workerReport);

    if (result.details) {
      merged.details.push(...result.details);
    }
    if (result.failures) {
      merged.details.push(...result.failures.map(f => ({ ...f, status: 'fail' })));
    }
  }

  return merged;
}

// ============================================================================
// FLEET STATUS AND PROGRESS
// ============================================================================

/**
 * Get a human-readable fleet execution summary.
 *
 * @param {Object} outcome - Result from distributeAndMerge or parallelPhases
 * @returns {string} Summary string
 */
export function getFleetSummary(outcome) {
  if (!outcome.fleetUsed) {
    const reason = outcome.fallbackReason || 'fleet unavailable';
    return `Local execution (${reason})`;
  }

  const errorInfo = outcome.errors && outcome.errors.length > 0
    ? `, ${outcome.errors.length} errors`
    : '';

  return `Fleet execution: ${outcome.workersUsed} workers${errorInfo}`;
}

/**
 * Create a progress tracker for fleet operations.
 *
 * @param {number} totalItems - Total items being processed
 * @param {number} totalWorkers - Number of workers
 * @param {Function} log - Logging function
 * @returns {Object} { workerDone(hostname, count), summary() }
 */
export function createFleetProgress(totalItems, totalWorkers, log) {
  const workerProgress = new Map();
  let completedItems = 0;

  return {
    workerDone(hostname, count) {
      workerProgress.set(hostname, (workerProgress.get(hostname) || 0) + count);
      completedItems += count;
      const pct = Math.round((completedItems / totalItems) * 100);
      log(`  [${pct}%] ${hostname}: +${count} items (${completedItems}/${totalItems} total)`);
    },

    summary() {
      const lines = [];
      for (const [hostname, count] of workerProgress.entries()) {
        lines.push(`  ${hostname}: ${count} items`);
      }
      return lines.join('\n');
    },
  };
}

// ============================================================================
// NFS COORDINATION HELPERS
// ============================================================================

/**
 * Generate a unique temporary directory path for a worker.
 * Workers use local /tmp to avoid NFS write contention.
 *
 * @param {string} skillName - Name of the skill (e.g., 'code-test')
 * @param {string} hostname - Worker hostname
 * @returns {string} Unique temp dir path
 */
export function workerTempDir(skillName, hostname) {
  // Use process PID and a simple counter for uniqueness without Date()
  const unique = `${process.pid}-${Math.random().toString(36).slice(2, 8)}`;
  return `/tmp/fleet-${skillName}-${hostname}-${unique}`;
}

/**
 * Get the NFS project path that is visible to all workers.
 * Resolves to the same path on any fleet machine.
 *
 * @param {string} [projectDir] - Project directory (default: process.cwd())
 * @returns {string} NFS-visible project path
 */
export function nfsProjectPath(projectDir) {
  const dir = projectDir || process.cwd();
  // NFS root is /home/sfloess/Development (shared across all machines)
  // If the path is under this root, it's visible to all workers
  const nfsRoot = '/home/sfloess/Development';
  if (dir.startsWith(nfsRoot)) {
    return dir;
  }
  // Not under NFS - return as-is but warn
  return dir;
}

/**
 * Check if a path is on NFS (visible to all fleet workers).
 *
 * @param {string} dirPath - Directory path to check
 * @returns {boolean} True if path is on NFS
 */
export function isOnNfs(dirPath) {
  const nfsRoot = '/home/sfloess/Development';
  return dirPath.startsWith(nfsRoot);
}
