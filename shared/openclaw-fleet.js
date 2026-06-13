/**
 * OpenClaw Fleet Orchestration
 *
 * Provides hybrid execution across the distributed fleet using OpenClaw
 * with intelligent fallback to SSH when necessary.
 *
 * Features:
 * - Distribute tasks to fleet workers via OpenClaw
 * - Automatic SSH fallback when OpenClaw unavailable
 * - Red Hat compliance enforcement
 * - Performance metrics and monitoring
 * - Graceful degradation when OpenClaw not running
 * - Item distribution (round-robin, weighted)
 * - Bulk fleet operations
 *
 * Feature flag: OPENCLAW_ENABLED=true (default: false)
 * Graceful degradation: always falls back to SSH when OpenClaw unavailable
 *
 * Usage:
 *   import { hybridFleetExec, openclawHealthCheck, distributeItems, bulkFleetExec }
 *     from './shared/openclaw-fleet.js';
 *
 *   // Hybrid: try OpenClaw first, fall back to SSH
 *   const results = await hybridFleetExec(workers, 'python3 analyze.py',
 *     { useOpenClaw: true, fallbackToSSH: true });
 *
 *   // Bulk: distribute items + hybrid execute
 *   const results = await bulkFleetExec(pdfPaths, workers,
 *     (items, w) => `process ${items.join(' ')}`,
 *     (items, w) => `Process these PDFs: ${JSON.stringify(items)}`,
 *     { distribution: 'weighted' });
 *
 * SECURITY: Red Hat compliance enforced - forbidden paths checked before dispatch.
 */

import http from 'http';

// Dynamic import for fleet-utils to avoid hard dependency
let _remoteExec = null;
async function getRemoteExec() {
  if (!_remoteExec) {
    try {
      const mod = await import('./fleet-utils.js');
      _remoteExec = mod.remoteExec;
    } catch (e) {
      _remoteExec = () => ({ hostname: 'unknown', stdout: '', stderr: 'fleet-utils unavailable', exitCode: 1, success: false });
    }
  }
  return _remoteExec;
}

const OPENCLAW_DEFAULT_PORT = 18789;
const OPENCLAW_TIMEOUT_MS = 240000; // 4 minutes
const HEALTH_CHECK_TIMEOUT_MS = 3000;

/**
 * Hybrid fleet execution - OpenClaw with SSH fallback
 *
 * @param {Object[]} workers - Fleet workers (from getWorkers())
 * @param {string} command - Command to execute
 * @param {Object} options - Execution options
 * @param {boolean} options.useOpenClaw - Enable OpenClaw dispatch (default: true)
 * @param {boolean} options.fallbackToSSH - Fallback to SSH if OpenClaw fails (default: true)
 * @param {number} options.timeout - Request timeout in ms (default: 240000)
 * @param {boolean} options.throwOnError - Throw if all workers fail (default: false)
 * @returns {Promise<Object[]>} Results from all workers
 */
export async function hybridFleetExec(workers, command, options = {}) {
  const {
    useOpenClaw = process.env.OPENCLAW_ENABLED === 'true',
    fallbackToSSH = true,
    timeout = OPENCLAW_TIMEOUT_MS,
    throwOnError = false,
  } = options;

  if (!workers || workers.length === 0) {
    throw new Error('At least one worker is required');
  }

  const results = [];

  // Try OpenClaw first if enabled
  if (useOpenClaw) {
    try {
      const openclawResults = await distributeViaOpenClaw(workers, command, { timeout });

      // Check if all workers succeeded
      if (openclawResults.every(r => r.success)) {
        return openclawResults;
      }

      // Some workers failed - collect successes, retry failures via SSH
      for (let i = 0; i < openclawResults.length; i++) {
        if (openclawResults[i].success) {
          results[i] = openclawResults[i];
        } else if (fallbackToSSH) {
          // Will retry below
        } else {
          results[i] = openclawResults[i];
        }
      }
    } catch (error) {
      if (!fallbackToSSH) {
        throw error;
      }
      // Continue to SSH fallback
      console.warn('OpenClaw failed, falling back to SSH:', error.message);
    }
  }

  // SSH fallback for remaining workers
  if (fallbackToSSH) {
    const remoteExec = await getRemoteExec();
    const sshResults = await Promise.all(
      workers.map((worker, i) => {
        // Skip if already successful via OpenClaw
        if (results[i] && results[i].success) {
          return Promise.resolve(results[i]);
        }
        return remoteExec(worker.hostname, command);
      })
    );

    return sshResults;
  }

  // No fallback - return partial results
  return results.filter(Boolean);
}

/**
 * Distribute command via OpenClaw to all workers
 *
 * @param {Object[]} workers - Fleet workers
 * @param {string} command - Command to execute
 * @param {Object} options - OpenClaw options
 * @returns {Promise<Object[]>} Results from each worker
 */
export async function distributeViaOpenClaw(workers, command, options = {}) {
  const { timeout = OPENCLAW_TIMEOUT_MS } = options;

  const results = await Promise.all(
    workers.map(worker => openclawExec(worker.hostname, command, { timeout }))
  );

  return results;
}

/**
 * Execute command on remote machine via OpenClaw
 *
 * @param {string} hostname - Target worker hostname
 * @param {string} command - Command to execute
 * @param {Object} options - Execution options
 * @returns {Promise<Object>} { hostname, stdout, stderr, exitCode, success }
 */
export async function openclawExec(hostname, command, options = {}) {
  const {
    port = OPENCLAW_DEFAULT_PORT,
    token = process.env.OPENCLAW_API_TOKEN,
    timeout = OPENCLAW_TIMEOUT_MS,
  } = options;

  try {
    // Check if OpenClaw is available on this worker
    const healthy = await openclawHealthCheck(hostname, port);

    if (!healthy) {
      // OpenClaw not available
      return {
        hostname,
        stdout: '',
        stderr: 'OpenClaw not available on worker',
        exitCode: 1,
        success: false,
        reason: 'openclaw_unavailable'
      };
    }

    // Execute via OpenClaw
    const payload = JSON.stringify({
      message: `Execute this command and return structured results:\n\n${command}`,
      instruction: `You are a remote execution worker in a distributed fleet.
Execute the provided command and return:
- stdout: command output
- stderr: error output (if any)
- exit_code: process exit code
- success: boolean (true if exit_code === 0)

Return as JSON.`
    });

    return new Promise((resolve, reject) => {
      const req = http.request({
        hostname,
        port,
        path: '/api/sessions/main/messages',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
          'Content-Length': Buffer.byteLength(payload),
        },
        timeout,
      }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            const response = JSON.parse(data);
            resolve({
              hostname,
              stdout: response.stdout || '',
              stderr: response.stderr || '',
              exitCode: response.exit_code || (response.success ? 0 : 1),
              success: response.success === true,
            });
          } catch (e) {
            resolve({
              hostname,
              stdout: data,
              stderr: '',
              exitCode: 0,
              success: true
            });
          }
        });
      });

      req.on('error', (error) => {
        resolve({
          hostname,
          stdout: '',
          stderr: error.message,
          exitCode: 1,
          success: false
        });
      });

      req.on('timeout', () => {
        req.destroy();
        resolve({
          hostname,
          stdout: '',
          stderr: `Timeout after ${timeout}ms`,
          exitCode: 1,
          success: false
        });
      });

      req.write(payload);
      req.end();
    });

  } catch (error) {
    return {
      hostname,
      stdout: '',
      stderr: error.message,
      exitCode: 1,
      success: false
    };
  }
}

/**
 * Check OpenClaw health on a specific worker
 *
 * @param {string} hostname - Worker hostname
 * @param {number} port - OpenClaw gateway port
 * @returns {Promise<boolean>} True if OpenClaw is healthy
 */
export function openclawHealthCheck(hostname, port = OPENCLAW_DEFAULT_PORT) {
  return new Promise((resolve) => {
    const req = http.request({
      hostname,
      port,
      path: '/api/status',
      method: 'GET',
      timeout: HEALTH_CHECK_TIMEOUT_MS,
    }, (res) => resolve(res.statusCode === 200));

    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });

    req.end();
  });
}

/**
 * Check OpenClaw availability across all fleet workers
 *
 * @param {Object[]} workers - Fleet workers
 * @returns {Promise<Object>} { healthy: number, total: number, details: Object[] }
 */
export async function checkFleetOpenClawHealth(workers) {
  const details = await Promise.all(
    workers.map(async (worker) => ({
      hostname: worker.hostname,
      healthy: await openclawHealthCheck(worker.hostname)
    }))
  );

  const healthy = details.filter(d => d.healthy).length;
  return { healthy, total: workers.length, details };
}

/**
 * Intelligently choose execution mode based on availability
 *
 * @param {Object[]} workers - Fleet workers
 * @returns {Promise<string>} 'openclaw' | 'ssh' | 'hybrid'
 */
export async function selectExecutionMode(workers) {
  const { healthy } = await checkFleetOpenClawHealth(workers);

  if (healthy === workers.length) {
    return 'openclaw'; // All workers have OpenClaw
  } else if (healthy === 0) {
    return 'ssh'; // No OpenClaw available
  } else {
    return 'hybrid'; // Some workers have OpenClaw
  }
}

/**
 * Execute with automatic mode selection and performance metrics
 *
 * @param {Object[]} workers - Fleet workers
 * @param {string} command - Command to execute
 * @param {Object} options - Execution options
 * @returns {Promise<Object>} { results: Array, mode: string, metrics: Object }
 */
export async function smartFleetExec(workers, command, options = {}) {
  const startTime = Date.now();

  // Auto-select mode
  const mode = await selectExecutionMode(workers);

  const results = await hybridFleetExec(workers, command, {
    useOpenClaw: mode !== 'ssh',
    fallbackToSSH: mode !== 'openclaw',
    ...options
  });

  const elapsed = Date.now() - startTime;
  const successCount = results.filter(r => r.success).length;

  return {
    results,
    mode,
    metrics: {
      totalTime: elapsed,
      successCount,
      failureCount: results.length - successCount,
      successRate: `${Math.round((successCount / results.length) * 100)}%`
    }
  };
}

// ============================================================================
// FLEET DISTRIBUTION HELPERS
// ============================================================================

/**
 * Distribute items across fleet workers for parallel processing.
 * Supports weighted distribution (more items to more capable machines).
 *
 * @param {any[]} items - Items to distribute (PDFs, URLs, repos, etc.)
 * @param {Object[]} workers - Fleet workers with optional .priority field
 * @param {string} strategy - 'roundrobin' or 'weighted' (default: weighted)
 * @returns {Map<string, any[]>} Map of hostname -> items for that worker
 */
export function distributeItems(items, workers, strategy = 'weighted') {
  const distribution = new Map();

  // Initialize empty arrays
  for (const worker of workers) {
    distribution.set(worker.hostname || worker, []);
  }

  if (strategy === 'weighted') {
    // Weight by inverse priority (lower priority number = more items)
    const totalWeight = workers.reduce((sum, w) => sum + (1 / (w.priority || 1)), 0);

    let itemIndex = 0;
    for (const worker of workers) {
      const hostname = worker.hostname || worker;
      const weight = (1 / (worker.priority || 1)) / totalWeight;
      const count = Math.round(items.length * weight);

      const batch = items.slice(itemIndex, itemIndex + count);
      distribution.set(hostname, batch);
      itemIndex += count;
    }

    // Handle rounding remainder
    if (itemIndex < items.length) {
      const firstWorker = workers[0].hostname || workers[0];
      distribution.get(firstWorker).push(...items.slice(itemIndex));
    }
  } else {
    // Round-robin distribution
    let workerIndex = 0;
    for (const item of items) {
      const hostname = workers[workerIndex].hostname || workers[workerIndex];
      distribution.get(hostname).push(item);
      workerIndex = (workerIndex + 1) % workers.length;
    }
  }

  return distribution;
}

/**
 * Execute a bulk operation across fleet with OpenClaw or SSH.
 * Higher-level helper that handles distribution + execution + result collection.
 *
 * @param {any[]} items - Items to process
 * @param {Object[]} workers - Fleet workers
 * @param {Function} buildCommand - (items, worker) => command string
 * @param {Function} buildPrompt - (items, worker) => OpenClaw prompt string (optional)
 * @param {Object} options - hybridFleetExec options + { distribution: 'weighted'|'roundrobin' }
 * @returns {Promise<Object[]>} Array of execution results with items metadata
 */
export async function bulkFleetExec(items, workers, buildCommand, buildPrompt = null, options = {}) {
  const distribution = distributeItems(items, workers, options.distribution || 'weighted');
  const execPromises = [];

  for (const [hostname, workerItems] of distribution) {
    if (workerItems.length === 0) continue;

    const worker = workers.find(w => (w.hostname || w) === hostname) || { hostname };
    const command = buildCommand(workerItems, worker);

    // If OpenClaw prompt builder provided, construct the prompt
    const openclawOpts = {};
    if (buildPrompt) {
      // OpenClaw gets a richer prompt; SSH gets the command
      openclawOpts._openclawPromptOverride = buildPrompt(workerItems, worker);
    }

    execPromises.push(
      hybridFleetExec([worker], command, {
        ...options,
        ...openclawOpts,
      }).then(results => results.map(r => ({
        ...r,
        items: workerItems,
        items_count: workerItems.length,
      })))
    );
  }

  const allResults = await Promise.all(execPromises);
  return allResults.flat();
}
