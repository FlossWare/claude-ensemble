/**
 * Fleet SSH Orchestrator
 *
 * Production-grade SSH-based fleet distribution with health checks, retries,
 * and comprehensive error handling. Executes Claude CLI commands on remote
 * workers via SSH for true distributed processing.
 *
 * Architecture:
 * - 8 API-only workers (server-01/02/03, laptop-01, pi-01/02, desktop-ap, server-ap)
 * - SSH user: 'claude' (from fleet-topology.js)
 * - Load balancing: Round-robin or capability-based
 * - Health monitoring: Pre-flight SSH checks before task assignment
 * - Failure handling: Automatic retries with exponential backoff
 * - Parallel execution: Up to 6 concurrent workers (configurable)
 *
 * Security:
 * - Hostname validation against allowlist (fleet-topology.js)
 * - Prompt content base64-encoded (shell-safe)
 * - BatchMode=yes prevents password prompt hangs
 * - StrictHostKeyChecking=accept-new prevents MITM
 * - ConnectTimeout=5s prevents indefinite hangs
 *
 * Created: 2026-06-29
 * @module fleet-ssh-orchestrator
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { FLEET_NODES } from './fleet-topology.js';
import { getFleetTopology } from './fleet-topology-dynamic.js';
import { createRequire } from 'module';
import { preValidate, recordValidationMetrics } from './pre-execution-validator.js';

const execAsync = promisify(exec);
const require = createRequire(import.meta.url);

// Import consensus tools (optional - only loaded if useConsensus=true)
let consensusTools = null;
function loadConsensusTools() {
  if (!consensusTools) {
    try {
      consensusTools = require('./consensus-tools.cjs');
    } catch (e) {
      console.warn('[fleet-ssh-orchestrator] consensus-tools.cjs not available:', e.message);
    }
  }
  return consensusTools;
}

// Use dynamic topology if available, fallback to static
let WORKERS;
try {
  WORKERS = await getFleetTopology();
  console.log(`[fleet-ssh-orchestrator] Loaded ${WORKERS.length} workers from registry`);
} catch (err) {
  console.warn('[fleet-ssh-orchestrator] Registry unavailable, using static topology');
  WORKERS = FLEET_NODES.filter(node => node.roles && node.roles.includes('worker'));
}

// Auto-storage integration
let workflowStorage = null;
try {
  // Path depends on where this is run from - try both locations
  let storageModule;
  try {
    storageModule = await import('/home/sfloess/.claude/learning/workflow-storage-adapter.js');
  } catch {
    storageModule = await import('../learning/workflow-storage-adapter.js');
  }
  const { getWorkflowStorage } = storageModule;
  workflowStorage = getWorkflowStorage();
} catch (err) {
  console.warn('[fleet-ssh-orchestrator] Workflow storage unavailable:', err.message);
}

// WORKERS already set from dynamic topology above

/**
 * Worker health status cache (TTL: 60s)
 * { hostname: { healthy: boolean, lastCheck: timestamp, error?: string } }
 */
const healthCache = new Map();
const HEALTH_CACHE_TTL_MS = 60000;

/**
 * Round-robin index for load balancing
 */
let roundRobinIndex = 0;

/**
 * Execute a Claude CLI command on a remote worker via SSH
 *
 * @param {Object} options - Execution options
 * @param {string} options.worker - Worker hostname (e.g., 'server-01', 'laptop-01')
 * @param {string} options.prompt - The prompt to pass to `claude -p`
 * @param {number} [options.timeoutMs=300000] - Command timeout (default: 5 min)
 * @param {number} [options.maxRetries=2] - Max retry attempts on failure
 * @param {boolean} [options.skipHealthCheck=false] - Skip pre-flight health check
 * @returns {Promise<Object>} { output: string, exitCode: number, worker: string, duration_ms: number }
 * @throws {Error} If SSH fails after all retries
 */
export async function executeOnWorker({
  worker,
  prompt,
  timeoutMs = 300000,
  maxRetries = 2,
  skipHealthCheck = false
}) {
  // Validation
  if (!worker || typeof worker !== 'string') {
    throw new Error('worker must be a non-empty string');
  }
  if (!prompt || typeof prompt !== 'string') {
    throw new Error('prompt must be a non-empty string');
  }

  // Validate worker against fleet topology
  const workerNode = WORKERS.find(w => w.hostname === worker);
  if (!workerNode) {
    throw new Error(
      `Unknown worker: ${worker}. Valid workers: ${WORKERS.map(w => w.hostname).join(', ')}`
    );
  }

  const sshUser = workerNode.ssh_user || 'claude';

  // Health check (unless skipped)
  if (!skipHealthCheck) {
    const healthy = await checkWorkerHealth(worker);
    if (!healthy) {
      const cached = healthCache.get(worker);
      throw new Error(
        `Worker ${worker} failed health check: ${cached?.error || 'unknown error'}`
      );
    }
  }

  // Execute with retries
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await _executeSSHCommand({
        worker,
        sshUser,
        prompt,
        timeoutMs
      });
    } catch (error) {
      lastError = error;

      // Mark worker as unhealthy in cache
      healthCache.set(worker, {
        healthy: false,
        lastCheck: Date.now(),
        error: error.message
      });

      // Don't retry on validation errors or timeout
      if (
        error.message.includes('Unknown worker') ||
        error.message.includes('Invalid prompt') ||
        error.message.includes('timed out')
      ) {
        throw error;
      }

      // Exponential backoff before retry
      if (attempt < maxRetries) {
        const backoffMs = Math.min(1000 * Math.pow(2, attempt), 10000);
        await new Promise(resolve => setTimeout(resolve, backoffMs));
      }
    }
  }

  throw new Error(
    `Failed to execute on worker ${worker} after ${maxRetries + 1} attempts. ` +
    `Last error: ${lastError.message}`
  );
}

/**
 * Internal: Execute SSH command to run `claude -p` on worker
 * @private
 */
async function _executeSSHCommand({ worker, sshUser, prompt, timeoutMs }) {
  // Base64-encode prompt for shell safety
  const promptBase64 = Buffer.from(prompt).toString('base64');

  // Remote command: decode prompt, call worker-client.sh (lightweight API client)
  // Workers use ~/worker-client.sh to make HTTP calls to aio-01:8000 proxy
  const remoteCmd = `~/worker-client.sh "$(echo ${promptBase64} | base64 -d)"`;

  // Build SSH command
  const sshCmd = [
    'ssh',
    '-o ConnectTimeout=5',
    '-o BatchMode=yes',
    '-o StrictHostKeyChecking=accept-new',
    `${sshUser}@${worker}`,
    `"${remoteCmd}"`  // Use double quotes to allow $() expansion
  ].join(' ');

  const startTime = Date.now();

  try {
    const { stdout, stderr } = await execAsync(sshCmd, {
      timeout: timeoutMs + 5000, // 5s buffer for SSH overhead
      maxBuffer: 50 * 1024 * 1024, // 50MB (large outputs)
      encoding: 'utf8'
    });

    const duration_ms = Date.now() - startTime;

    // Mark worker as healthy
    healthCache.set(worker, {
      healthy: true,
      lastCheck: Date.now()
    });

    const result = {
      output: stdout,
      stderr: stderr || '',
      exitCode: 0,
      worker,
      duration_ms,
      ssh_overhead_ms: Math.max(0, duration_ms - 100) // Estimate 100ms for worker script
    };

    // Auto-store to PostgreSQL
    if (workflowStorage) {
      try {
        await workflowStorage.storeWorkerResult({
          workflow_execution_id: null, // Set by caller if part of workflow
          worker_id: worker,
          model: 'unknown', // Caller should provide
          task_assigned: prompt.substring(0, 200),
          result: stdout,
          confidence: null,
          duration_ms,
          input_tokens: null,
          output_tokens: null,
          cost_usd: null,
          outcome: 'success'
        }).catch(err => console.warn('[fleet-ssh-orchestrator] Storage failed:', err.message));
      } catch (err) {
        // Non-fatal storage error
      }
    }

    return result;
  } catch (error) {
    const duration_ms = Date.now() - startTime;

    // Report failure to registry
    try {
      const http = await import('http');
      const failureData = JSON.stringify({
        hostname: worker,
        error_message: error.message,
        reported_by: 'orchestrator'
      });

      // Wrap HTTP request in Promise to properly await it
      await new Promise((resolve, reject) => {
        const req = http.request({
          hostname: 'aio-01',
          port: 8002,
          path: '/failure',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(failureData)
          },
          timeout: 5000
        }, (res) => {
          // Consume response to prevent memory leak
          res.on('data', () => {});
          res.on('end', () => {
            if (res.statusCode === 200) {
              resolve();
            } else {
              reject(new Error(`Registry returned ${res.statusCode}`));
            }
          });
        });

        req.on('error', reject);
        req.on('timeout', () => {
          req.destroy();
          reject(new Error('Registry timeout'));
        });

        req.write(failureData);
        req.end();
      });
    } catch (reportErr) {
      // Non-fatal if failure reporting fails
      console.warn(`[fleet-ssh-orchestrator] Failed to report worker failure: ${reportErr.message}`);
    }

    // Timeout
    if (error.killed) {
      throw new Error(
        `SSH command on worker ${worker} timed out after ${timeoutMs}ms. ` +
        `The worker may be overloaded or the task too complex.`
      );
    }

    // Connection refused (SSH not running or firewall)
    if (error.code === 255 || error.message?.includes('Connection refused')) {
      throw new Error(
        `Cannot SSH to worker ${worker}. ` +
        `Ensure SSH is running and accessible: ssh ${sshUser}@${worker} echo OK`
      );
    }

    // Command execution error (non-zero exit)
    if (error.code && error.code !== 255) {
      return {
        output: error.stdout || '',
        stderr: error.stderr || '',
        exitCode: error.code,
        worker,
        duration_ms,
        error: error.message
      };
    }

    throw new Error(
      `SSH execution failed on worker ${worker}: ${error.message} (duration: ${duration_ms}ms)`
    );
  }
}

/**
 * Check if a worker is healthy (can accept SSH connections)
 *
 * Uses cached health status if available and fresh (< 60s old).
 * Otherwise runs a quick SSH test command.
 *
 * @param {string} worker - Worker hostname
 * @returns {Promise<boolean>} true if healthy, false otherwise
 */
export async function checkWorkerHealth(worker) {
  // Check cache
  const cached = healthCache.get(worker);
  if (cached && (Date.now() - cached.lastCheck) < HEALTH_CACHE_TTL_MS) {
    return cached.healthy;
  }

  // Validate worker
  const workerNode = WORKERS.find(w => w.hostname === worker);
  if (!workerNode) {
    healthCache.set(worker, {
      healthy: false,
      lastCheck: Date.now(),
      error: 'Unknown worker'
    });
    return false;
  }

  const sshUser = workerNode.ssh_user || 'claude';

  try {
    // Quick health check: echo OK
    const sshCmd = [
      'ssh',
      '-o ConnectTimeout=5',
      '-o BatchMode=yes',
      '-o StrictHostKeyChecking=accept-new',
      `${sshUser}@${worker}`,
      'echo OK'
    ].join(' ');

    const { stdout } = await execAsync(sshCmd, {
      timeout: 10000,
      encoding: 'utf8'
    });

    const healthy = stdout.trim() === 'OK';
    healthCache.set(worker, {
      healthy,
      lastCheck: Date.now(),
      error: healthy ? undefined : 'Health check failed'
    });

    return healthy;
  } catch (error) {
    healthCache.set(worker, {
      healthy: false,
      lastCheck: Date.now(),
      error: error.message
    });
    return false;
  }
}

/**
 * Select next available worker using round-robin load balancing
 *
 * Optionally filters workers by capability (e.g., 'lightweight' for Pi nodes).
 * Automatically skips unhealthy workers if health checks are enabled.
 *
 * @param {Object} [options] - Selection options
 * @param {string[]} [options.requireRoles] - Required roles (e.g., ['lightweight'])
 * @param {string[]} [options.excludeWorkers] - Workers to exclude from selection
 * @param {boolean} [options.checkHealth=true] - Check worker health before selection
 * @returns {Promise<string|null>} Worker hostname or null if none available
 */
export async function selectWorker({
  requireRoles = [],
  excludeWorkers = [],
  checkHealth = true
} = {}) {
  // Filter workers by roles
  let candidates = WORKERS.filter(w => {
    if (excludeWorkers.includes(w.hostname)) return false;
    if (requireRoles.length === 0) return true;
    return requireRoles.every(role => w.roles && w.roles.includes(role));
  });

  if (candidates.length === 0) {
    return null;
  }

  // Check health if enabled
  if (checkHealth) {
    const healthChecks = await Promise.all(
      candidates.map(async (w) => ({
        worker: w.hostname,
        healthy: await checkWorkerHealth(w.hostname)
      }))
    );

    candidates = candidates.filter(w => {
      const check = healthChecks.find(h => h.worker === w.hostname);
      return check && check.healthy;
    });

    if (candidates.length === 0) {
      return null;
    }
  }

  // Round-robin selection
  const selected = candidates[roundRobinIndex % candidates.length];
  roundRobinIndex = (roundRobinIndex + 1) % candidates.length;

  return selected.hostname;
}

/**
 * Execute prompts on multiple workers in parallel
 *
 * Automatically distributes work across available healthy workers.
 * Handles failures by retrying on different workers.
 *
 * @param {Object} options - Execution options
 * @param {Array<{id: string, prompt: string}>} options.tasks - Tasks to execute
 * @param {number} [options.maxParallel=6] - Max concurrent executions
 * @param {number} [options.timeoutMs=300000] - Per-task timeout
 * @param {number} [options.maxRetries=2] - Max retry attempts per task
 * @param {string[]} [options.requireRoles] - Required worker roles
 * @param {boolean} [options.skipPreValidation=false] - Skip pre-execution validation
 * @param {Object} [options.tokenBudget] - Token budget tracker for validation
 * @returns {Promise<Array<{taskId: string, result: Object, error?: string}>>}
 */
export async function executeParallel({
  tasks,
  maxParallel = 6,
  timeoutMs = 300000,
  maxRetries = 2,
  requireRoles = [],
  skipPreValidation = false,
  tokenBudget = null,
  useConsensus = false,      // NEW: Enable multi-worker consensus
  consensusWorkers = 3       // NEW: Number of workers to query for consensus
}) {
  if (!Array.isArray(tasks) || tasks.length === 0) {
    throw new Error('tasks must be a non-empty array');
  }

  // Validate tasks
  for (const task of tasks) {
    if (!task.id || !task.prompt) {
      throw new Error('Each task must have {id, prompt}');
    }
  }

  // PRE-EXECUTION VALIDATION (ECC #193)
  if (!skipPreValidation) {
    try {
      const availableWorkers = await getAvailableWorkers({ requireRoles, onlyHealthy: false });
      const validationResult = await preValidate({
        tasks,
        maxParallel,
        availableWorkers,
        tokenBudget,
        healthCache
      });

      // Log warnings
      if (validationResult.warnings.length > 0) {
        console.warn('[fleet-ssh-orchestrator] Pre-validation warnings:');
        validationResult.warnings.forEach(w => console.warn(`  - ${w}`));
      }

      // Log recommendations
      if (validationResult.recommendations.length > 0) {
        console.log('[fleet-ssh-orchestrator] Pre-validation recommendations:');
        validationResult.recommendations.forEach(r => console.log(`  - ${r}`));
      }

      // Check for blockers
      if (!validationResult.passed) {
        console.error('[fleet-ssh-orchestrator] Pre-validation failed with blockers:');
        validationResult.blockers.forEach(b => console.error(`  - ${b}`));

        // Record validation metrics
        await recordValidationMetrics('full', false, true, false);

        throw new Error(
          `Pre-execution validation failed: ${validationResult.blockers.join('; ')}. ` +
          `Use skipPreValidation=true to override.`
        );
      }

      // Record successful validation
      await recordValidationMetrics('full', true, false, false);

    } catch (validationError) {
      // If validation itself fails (not blockers, but errors), fail-open with warning
      if (validationError.message.includes('Pre-execution validation failed')) {
        throw validationError; // Re-throw blocker errors
      }
      console.warn('[fleet-ssh-orchestrator] Validation error (fail-open):', validationError.message);
    }
  } else {
    // Record override usage
    await recordValidationMetrics('full', true, false, true).catch(() => {});
  }

  const results = [];
  const queue = [...tasks];
  const inProgress = new Set();

  // Worker assignment tracking (avoid overloading same worker)
  const workerAssignments = new Map();

  while (queue.length > 0 || inProgress.size > 0) {
    // Start new tasks up to maxParallel
    while (queue.length > 0 && inProgress.size < maxParallel) {
      const task = queue.shift();
      inProgress.add(task.id);

      // Select worker (exclude workers already at capacity)
      const busyWorkers = Array.from(workerAssignments.values())
        .filter(w => w.count >= 2) // Max 2 tasks per worker
        .map(w => w.hostname);

      const worker = await selectWorker({
        requireRoles,
        excludeWorkers: busyWorkers,
        checkHealth: true
      });

      if (!worker) {
        // No workers available, put task back in queue
        queue.unshift(task);
        inProgress.delete(task.id);
        await new Promise(resolve => setTimeout(resolve, 1000));
        continue;
      }

      // Track worker assignment
      if (!workerAssignments.has(worker)) {
        workerAssignments.set(worker, { hostname: worker, count: 0 });
      }
      workerAssignments.get(worker).count++;

      // Execute task
      executeOnWorker({
        worker,
        prompt: task.prompt,
        timeoutMs,
        maxRetries,
        skipHealthCheck: true // Already checked in selectWorker
      })
        .then(result => {
          results.push({
            taskId: task.id,
            result,
            error: result.error
          });
        })
        .catch(error => {
          results.push({
            taskId: task.id,
            result: null,
            error: error.message
          });
        })
        .finally(() => {
          inProgress.delete(task.id);

          // Release worker assignment
          const assignment = workerAssignments.get(worker);
          if (assignment) {
            assignment.count = Math.max(0, assignment.count - 1);
          }
        });
    }

    // Wait a bit before checking queue again
    if (inProgress.size >= maxParallel || queue.length === 0) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }

  // Apply consensus if requested
  if (useConsensus && consensusWorkers > 1) {
    const tools = loadConsensusTools();
    if (tools) {
      console.log(`[fleet-ssh-orchestrator] Applying ${consensusWorkers}-worker consensus to ${results.length} tasks`);

      // Group results by task (for future multi-worker per task)
      // For now, just mark that consensus is available
      // TODO: Implement actual consensus voting when same task sent to multiple workers
      results.forEach(r => {
        if (r.result) {
          r.result.consensus = { enabled: true, workers: 1, mode: 'single-worker' };
        }
      });
    }
  }

  return results;
}

/**
 * Get health status for all workers
 *
 * @returns {Promise<Array<{worker: string, healthy: boolean, lastCheck: number, error?: string}>>}
 */
export async function getFleetHealth() {
  const healthChecks = await Promise.all(
    WORKERS.map(async (w) => {
      const healthy = await checkWorkerHealth(w.hostname);
      const cached = healthCache.get(w.hostname);
      return {
        worker: w.hostname,
        healthy,
        lastCheck: cached?.lastCheck || 0,
        error: cached?.error,
        roles: w.roles,
        architecture: w.architecture,
        cpu_cores: w.cpu_cores,
        ram_gb: w.ram_gb
      };
    })
  );

  return healthChecks;
}

/**
 * Clear health cache (force fresh checks on next request)
 */
export function clearHealthCache() {
  healthCache.clear();
}

/**
 * Get list of available workers
 *
 * @param {Object} [options] - Filter options
 * @param {string[]} [options.requireRoles] - Required roles
 * @param {boolean} [options.onlyHealthy=false] - Only return healthy workers
 * @returns {Promise<string[]>} Worker hostnames
 */
export async function getAvailableWorkers({ requireRoles = [], onlyHealthy = false } = {}) {
  let workers = WORKERS.filter(w => {
    if (requireRoles.length === 0) return true;
    return requireRoles.every(role => w.roles && w.roles.includes(role));
  });

  if (onlyHealthy) {
    const healthChecks = await Promise.all(
      workers.map(async (w) => ({
        hostname: w.hostname,
        healthy: await checkWorkerHealth(w.hostname)
      }))
    );

    workers = workers.filter(w => {
      const check = healthChecks.find(h => h.hostname === w.hostname);
      return check && check.healthy;
    });
  }

  return workers.map(w => w.hostname);
}
