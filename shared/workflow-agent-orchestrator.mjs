/**
 * Workflow Agent Orchestrator
 *
 * Intercepts agent() calls from workflows and distributes them across
 * 8 fleet workers via SSH using fleet_executor.py on each remote node.
 *
 * Architecture:
 * - 8 workers: server-01, server-02, server-03, laptop-01, pi-01, pi-02,
 *   desktop-ap, server-ap
 * - 1 orchestrator: aio-01 (infrastructure only, NOT a worker)
 * - Round-robin load balancing with per-worker active-task tracking
 * - SSH user: 'claude' on all workers
 * - Execution: fleet_executor.py (Python, stdlib-only, works on all architectures)
 *
 * Usage in workflows:
 *
 *   import { createOrchestrator } from '../shared/workflow-agent-orchestrator.mjs';
 *
 *   const orch = createOrchestrator();
 *
 *   // Single agent call (distributed to next available worker)
 *   const result = await orch.agent({ model: 'gpt-4o-mini', task: 'Summarize X' });
 *
 *   // Parallel agent calls (distributed across workers automatically)
 *   const results = await orch.parallel([
 *     { model: 'gpt-4o-mini', task: 'Analyze aspect A' },
 *     { model: 'gpt-4o-mini', task: 'Analyze aspect B' },
 *     { model: 'gpt-4o-mini', task: 'Analyze aspect C' },
 *   ]);
 *
 *   // Get worker stats
 *   const stats = orch.getStats();
 *
 * Created: 2026-06-29
 */

import { spawn } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Fleet topology: 8 API-only workers.  aio-01 is the orchestrator and is NOT
// a worker.  Matches shared/fleet-topology.js and lib/fleet-api-policy.json.
// ---------------------------------------------------------------------------

const WORKERS = [
  { hostname: 'server-01',  sshUser: 'claude', arch: 'x86_64',  cores: 8, tier: 'heavy'  },
  { hostname: 'server-02',  sshUser: 'claude', arch: 'x86_64',  cores: 8, tier: 'heavy'  },
  { hostname: 'server-03',  sshUser: 'claude', arch: 'x86_64',  cores: 8, tier: 'heavy'  },
  { hostname: 'laptop-01',  sshUser: 'claude', arch: 'x86_64',  cores: 8, tier: 'heavy'  },
  { hostname: 'pi-01',      sshUser: 'claude', arch: 'aarch64', cores: 4, tier: 'light'  },
  { hostname: 'pi-02',      sshUser: 'claude', arch: 'aarch64', cores: 4, tier: 'light'  },
  { hostname: 'desktop-ap', sshUser: 'claude', arch: 'x86_64',  cores: 4, tier: 'medium' },
  { hostname: 'server-ap',  sshUser: 'claude', arch: 'x86_64',  cores: 4, tier: 'medium' },
];

// Path to fleet_executor.py on remote workers (under claude user home)
const REMOTE_EXECUTOR_PATH =
  '/home/claude/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/fleet_executor.py';

// Path on local machine (for aio-01 / localhost)
const LOCAL_EXECUTOR_PATH = resolve(__dirname, 'fleet_executor.py');

// Hostname validation: alphanumeric, dots, hyphens only (RFC 952 / 1123)
const VALID_HOSTNAME_RE = /^[a-zA-Z0-9][a-zA-Z0-9._-]*$/;

// ---------------------------------------------------------------------------
// Worker state tracked per-orchestrator instance
// ---------------------------------------------------------------------------

/**
 * Per-worker runtime state used for load balancing.
 *
 * @typedef {Object} WorkerState
 * @property {number} activeTasks  - Number of currently in-flight tasks
 * @property {number} totalTasks   - Lifetime tasks dispatched
 * @property {number} failures     - Lifetime task failures
 * @property {number} totalLatency - Cumulative latency (ms) for averaging
 * @property {boolean} healthy     - False after N consecutive failures
 */

function makeWorkerState() {
  return {
    activeTasks: 0,
    totalTasks: 0,
    failures: 0,
    consecutiveFailures: 0,
    totalLatency: 0,
    healthy: true,
  };
}

// ---------------------------------------------------------------------------
// SSH + fleet_executor.py bridge
// ---------------------------------------------------------------------------

/**
 * Execute an agent task on a specific worker via SSH + fleet_executor.py.
 *
 * Communication protocol:
 * 1. JSON parameters are written to the Python process via stdin.
 * 2. The Python script calls the appropriate LLM API on the worker.
 * 3. JSON result is read from stdout.
 *
 * @param {Object} opts
 * @param {string} opts.worker     - Worker hostname
 * @param {string} opts.model      - LLM model name (e.g. 'gpt-4o-mini')
 * @param {string} opts.task       - Prompt / task text
 * @param {number} [opts.maxTokens=4096] - Max response tokens
 * @param {number} [opts.timeoutMs=60000] - Per-task timeout
 * @returns {Promise<Object>} Result with { output, input_tokens, output_tokens, duration_ms, execution_host, ... }
 */
function executeOnWorker({ worker, model, task, maxTokens = 4096, timeoutMs = 60000 }) {
  if (!VALID_HOSTNAME_RE.test(worker)) {
    return Promise.reject(new Error(`Invalid worker hostname: ${worker}`));
  }

  return new Promise((resolve, reject) => {
    const startTime = Date.now();

    // Build the JSON payload that fleet_executor.py's execute_on_worker() expects
    // when invoked as a library.  When the script is invoked standalone it reads
    // from stdin, but since we are driving it via the Python subprocess directly
    // we pass the payload to python-worker.py through fleet_executor.py's
    // execute_on_worker function.
    //
    // Instead of importing fleet_executor as a library (which would require the
    // caller to be Python), we build a small inline Python invocation that:
    //   - imports execute_on_worker from fleet_executor
    //   - calls it with the correct arguments
    //   - prints JSON to stdout
    //
    // The inline script is executed:
    //   - locally via `python3 -c ...` when worker is aio-01 / localhost
    //   - remotely via `ssh claude@<worker> python3 -c ...` otherwise

    const paramsJson = JSON.stringify({ worker, model, task, max_tokens: maxTokens, timeout_ms: timeoutMs });

    // The inline Python script reads JSON params from stdin (not interpolated
    // into the code string) to prevent command injection via task content.
    const executorDir = worker === 'aio-01' || worker === 'localhost' ? LOCAL_EXECUTOR_PATH : REMOTE_EXECUTOR_PATH;
    const inlinePython = [
      'import sys, os, json',
      `sys.path.insert(0, os.path.dirname(${JSON.stringify(executorDir)}))`,
      'from fleet_executor import execute_on_worker',
      'p = json.load(sys.stdin)',
      'r = execute_on_worker(worker="aio-01", model=p["model"], task=p["task"], max_tokens=p["max_tokens"], timeout_ms=p["timeout_ms"])',
      'print(json.dumps(r))',
    ].join('; ');

    let args;
    if (worker === 'aio-01' || worker === 'localhost') {
      args = ['python3', '-c', inlinePython];
    } else {
      // SSH to the worker, source .bashrc for API keys, run inline Python
      const remoteCmd = `source ~/.bashrc 2>/dev/null; python3 -c '${inlinePython.replace(/'/g, "'\\''")}'`;
      args = [
        'ssh',
        '-o', 'ConnectTimeout=5',
        '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=accept-new',
        `${WORKERS.find(w => w.hostname === worker)?.sshUser || 'claude'}@${worker}`,
        'bash', '-lc', JSON.stringify(remoteCmd),
      ];
    }

    const proc = spawn(args[0], args.slice(1), {
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: timeoutMs + 15000, // buffer for SSH overhead
    });

    // Pass params via stdin instead of embedding in the Python code string.
    // This prevents command injection through user-controlled task content.
    proc.stdin.write(paramsJson);
    proc.stdin.end();

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    proc.stderr.on('data', (chunk) => { stderr += chunk.toString(); });

    proc.on('error', (err) => {
      reject(new Error(`Failed to spawn process for worker ${worker}: ${err.message}`));
    });

    proc.on('close', (code) => {
      const durationMs = Date.now() - startTime;
      const trimmed = stdout.trim();

      if (!trimmed) {
        reject(new Error(
          `Worker ${worker} returned empty output (exit ${code}).\n` +
          `stderr: ${stderr.slice(0, 500)}`
        ));
        return;
      }

      let result;
      try {
        result = JSON.parse(trimmed);
      } catch (parseErr) {
        reject(new Error(
          `Worker ${worker} returned invalid JSON (exit ${code}).\n` +
          `stdout: ${trimmed.slice(0, 500)}\n` +
          `stderr: ${stderr.slice(0, 500)}`
        ));
        return;
      }

      if (result.error) {
        reject(new Error(`Worker ${worker} error: ${result.error}`));
        return;
      }

      resolve({
        ...result,
        execution_host: worker,
        actually_executed_on_worker: true,
        total_duration_ms: durationMs,
        ssh_overhead_ms: durationMs - (result.duration_ms || 0),
      });
    });
  });
}

// ---------------------------------------------------------------------------
// Load balancing strategies
// ---------------------------------------------------------------------------

/**
 * Round-robin: picks the next worker in cyclic order, skipping unhealthy.
 *
 * @param {Map<string, WorkerState>} state - Per-worker state map
 * @param {number} rrIndex - Current round-robin index (mutated externally)
 * @param {Object[]} workers - Available worker list
 * @returns {{ worker: Object, nextIndex: number }}
 */
function roundRobin(state, rrIndex, workers) {
  const len = workers.length;
  for (let attempt = 0; attempt < len; attempt++) {
    const idx = (rrIndex + attempt) % len;
    const w = workers[idx];
    const ws = state.get(w.hostname);
    if (ws && ws.healthy) {
      return { worker: w, nextIndex: (idx + 1) % len };
    }
  }
  // All unhealthy - reset health and try first worker
  for (const [, ws] of state) {
    ws.healthy = true;
    ws.consecutiveFailures = 0;
  }
  return { worker: workers[rrIndex % len], nextIndex: (rrIndex + 1) % len };
}

/**
 * Least-loaded: picks the healthy worker with the fewest active tasks.
 * Breaks ties using round-robin order for determinism.
 *
 * @param {Map<string, WorkerState>} state
 * @param {Object[]} workers
 * @returns {Object} Selected worker
 */
function leastLoaded(state, workers) {
  let best = null;
  let bestActive = Infinity;

  for (const w of workers) {
    const ws = state.get(w.hostname);
    if (!ws || !ws.healthy) continue;
    if (ws.activeTasks < bestActive) {
      bestActive = ws.activeTasks;
      best = w;
    }
  }

  if (!best) {
    // All unhealthy - reset and pick first
    for (const [, ws] of state) {
      ws.healthy = true;
      ws.consecutiveFailures = 0;
    }
    best = workers[0];
  }

  return best;
}

// ---------------------------------------------------------------------------
// Orchestrator factory
// ---------------------------------------------------------------------------

/** Maximum consecutive failures before a worker is marked unhealthy */
const MAX_CONSECUTIVE_FAILURES = 3;

/** Number of retry attempts for transient SSH/execution failures */
const RETRY_ATTEMPTS = 3;

/** Base delay for exponential backoff (ms) - doubles each retry */
const RETRY_BASE_DELAY_MS = 1000;

/**
 * Create a new orchestrator instance.
 *
 * @param {Object} [options]
 * @param {string} [options.strategy='least-loaded'] - 'round-robin' | 'least-loaded'
 * @param {string[]} [options.workers]  - Override worker hostnames (default: all 8)
 * @param {number} [options.maxTokens=4096] - Default max tokens
 * @param {number} [options.timeoutMs=60000] - Default timeout per task (ms)
 * @param {boolean} [options.verbose=false] - Log dispatch decisions to stderr
 * @returns {Object} Orchestrator with agent(), parallel(), getStats(), getWorkers()
 */
export function createOrchestrator(options = {}) {
  const {
    strategy = 'least-loaded',
    workers: workerHostnames,
    maxTokens: defaultMaxTokens = 4096,
    timeoutMs: defaultTimeoutMs = 60000,
    verbose = false,
  } = options;

  // Resolve the active worker list
  const activeWorkers = workerHostnames
    ? WORKERS.filter(w => workerHostnames.includes(w.hostname))
    : [...WORKERS];

  if (activeWorkers.length === 0) {
    throw new Error('No workers available. Check worker hostnames.');
  }

  // Initialize per-worker state
  const state = new Map();
  for (const w of activeWorkers) {
    state.set(w.hostname, makeWorkerState());
  }

  let rrIndex = 0; // round-robin cursor

  // ------------------------------------------------------------------
  // Internal: pick a worker using the configured strategy
  // ------------------------------------------------------------------
  function pickWorker() {
    if (strategy === 'round-robin') {
      const { worker, nextIndex } = roundRobin(state, rrIndex, activeWorkers);
      rrIndex = nextIndex;
      return worker;
    }
    return leastLoaded(state, activeWorkers);
  }

  // ------------------------------------------------------------------
  // Internal: wrap executeOnWorker with state tracking
  // ------------------------------------------------------------------
  async function dispatchToWorker(worker, { model, task, maxTokens, timeoutMs }) {
    const ws = state.get(worker.hostname);
    ws.activeTasks++;
    ws.totalTasks++;

    const startTime = Date.now();

    if (verbose) {
      process.stderr.write(
        `[orchestrator] dispatching to ${worker.hostname} ` +
        `(active=${ws.activeTasks}, total=${ws.totalTasks}, model=${model})\n`
      );
    }

    let lastError;

    for (let attempt = 0; attempt <= RETRY_ATTEMPTS; attempt++) {
      try {
        if (attempt > 0) {
          const delayMs = RETRY_BASE_DELAY_MS * Math.pow(2, attempt - 1);
          if (verbose) {
            process.stderr.write(
              `[orchestrator] retry ${attempt}/${RETRY_ATTEMPTS} for ${worker.hostname} ` +
              `after ${delayMs}ms backoff (error: ${lastError.message})\n`
            );
          }
          await new Promise(r => setTimeout(r, delayMs));
        }

        const result = await executeOnWorker({
          worker: worker.hostname,
          model,
          task,
          maxTokens,
          timeoutMs,
        });

        ws.activeTasks--;
        ws.consecutiveFailures = 0;
        ws.totalLatency += Date.now() - startTime;

        if (attempt > 0 && verbose) {
          process.stderr.write(
            `[orchestrator] ${worker.hostname} succeeded on retry ${attempt}\n`
          );
        }

        return result;
      } catch (err) {
        lastError = err;

        // Only retry on transient SSH/connection failures, not on
        // application-level errors (e.g. invalid model, bad prompt)
        const isTransient =
          err.message.includes('Failed to spawn') ||
          err.message.includes('empty output') ||
          err.message.includes('Connection refused') ||
          err.message.includes('Connection reset') ||
          err.message.includes('Connection timed out') ||
          err.message.includes('No route to host') ||
          err.message.includes('Host is unreachable') ||
          err.message.includes('ssh') ||
          err.message.includes('SSH') ||
          err.message.includes('timeout') ||
          err.message.includes('ETIMEDOUT') ||
          err.message.includes('ECONNREFUSED') ||
          err.message.includes('ECONNRESET') ||
          err.message.includes('EHOSTUNREACH');

        if (!isTransient) {
          // Non-transient error: fail immediately, do not retry
          if (verbose) {
            process.stderr.write(
              `[orchestrator] non-transient error on ${worker.hostname}, skipping retries: ${err.message}\n`
            );
          }
          break;
        }

        if (attempt === RETRY_ATTEMPTS) {
          // Exhausted all retries
          if (verbose) {
            process.stderr.write(
              `[orchestrator] ${worker.hostname} failed after ${RETRY_ATTEMPTS} retries: ${err.message}\n`
            );
          }
        }
      }
    }

    // All retries exhausted or non-transient error
    ws.activeTasks--;
    ws.failures++;
    ws.consecutiveFailures++;

    if (ws.consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
      ws.healthy = false;
      if (verbose) {
        process.stderr.write(
          `[orchestrator] marking ${worker.hostname} unhealthy ` +
          `after ${ws.consecutiveFailures} consecutive failures\n`
        );
      }
    }

    throw lastError;
  }

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  /**
   * Execute a single agent task on the next available worker.
   *
   * @param {Object} opts
   * @param {string} opts.model     - LLM model name
   * @param {string} opts.task      - Prompt / task text
   * @param {number} [opts.maxTokens] - Max response tokens
   * @param {number} [opts.timeoutMs] - Per-task timeout (ms)
   * @param {string} [opts.worker]  - Force a specific worker hostname
   * @returns {Promise<Object>} LLM result with execution metadata
   */
  async function agent({ model, task, maxTokens, timeoutMs, worker: forceWorker } = {}) {
    if (!model) throw new Error('agent() requires a model');
    if (!task) throw new Error('agent() requires a task');

    const tokens = maxTokens ?? defaultMaxTokens;
    const timeout = timeoutMs ?? defaultTimeoutMs;

    let worker;
    if (forceWorker) {
      worker = activeWorkers.find(w => w.hostname === forceWorker);
      if (!worker) {
        throw new Error(`Forced worker '${forceWorker}' not in active worker list`);
      }
    } else {
      worker = pickWorker();
    }

    return dispatchToWorker(worker, { model, task, maxTokens: tokens, timeoutMs: timeout });
  }

  /**
   * Execute multiple agent tasks in parallel, distributed across workers.
   *
   * Each task object requires { model, task } at minimum.
   * Tasks are spread across workers using the load balancing strategy.
   *
   * @param {Object[]} tasks - Array of { model, task, maxTokens?, timeoutMs?, worker? }
   * @returns {Promise<Object[]>} Array of results (one per task, same order)
   */
  async function parallel(tasks) {
    if (!Array.isArray(tasks) || tasks.length === 0) {
      return [];
    }

    const promises = tasks.map((t) => {
      // Each call to agent() picks a worker independently
      return agent({
        model: t.model,
        task: t.task,
        maxTokens: t.maxTokens,
        timeoutMs: t.timeoutMs,
        worker: t.worker,
      }).catch((err) => ({
        error: err.message,
        execution_host: t.worker || 'unknown',
        model: t.model,
      }));
    });

    return Promise.all(promises);
  }

  /**
   * Get per-worker statistics.
   *
   * @returns {Object} Map of hostname -> { totalTasks, failures, avgLatency, healthy, activeTasks }
   */
  function getStats() {
    const stats = {};
    for (const [hostname, ws] of state) {
      stats[hostname] = {
        totalTasks: ws.totalTasks,
        activeTasks: ws.activeTasks,
        failures: ws.failures,
        healthy: ws.healthy,
        avgLatencyMs: ws.totalTasks > ws.failures
          ? Math.round(ws.totalLatency / (ws.totalTasks - ws.failures))
          : 0,
      };
    }
    return stats;
  }

  /**
   * Get list of active worker hostnames.
   *
   * @returns {string[]}
   */
  function getActiveWorkers() {
    return activeWorkers.map(w => w.hostname);
  }

  /**
   * Reset a specific worker's health status (e.g., after manual fix).
   *
   * @param {string} hostname
   */
  function resetWorkerHealth(hostname) {
    const ws = state.get(hostname);
    if (ws) {
      ws.healthy = true;
      ws.consecutiveFailures = 0;
    }
  }

  return {
    agent,
    parallel,
    getStats,
    getActiveWorkers,
    resetWorkerHealth,
    /** Expose worker count for callers that need it */
    workerCount: activeWorkers.length,
  };
}

// ---------------------------------------------------------------------------
// Convenience: default singleton (created lazily)
// ---------------------------------------------------------------------------

let _defaultOrchestrator = null;

/**
 * Get or create the default orchestrator singleton.
 * Uses least-loaded strategy across all 8 workers.
 *
 * @param {Object} [options] - Same options as createOrchestrator
 * @returns {Object} Orchestrator instance
 */
export function getOrchestrator(options) {
  if (!_defaultOrchestrator) {
    _defaultOrchestrator = createOrchestrator(options);
  }
  return _defaultOrchestrator;
}

// ---------------------------------------------------------------------------
// Direct execution for testing
// ---------------------------------------------------------------------------

if (process.argv[1] && process.argv[1].endsWith('workflow-agent-orchestrator.mjs')) {
  (async () => {
    const orch = createOrchestrator({ verbose: true });

    console.log('Workflow Agent Orchestrator');
    console.log(`Workers: ${orch.getActiveWorkers().join(', ')}`);
    console.log(`Worker count: ${orch.workerCount}`);
    console.log(`Strategy: least-loaded`);
    console.log('');

    if (process.argv[2] === '--test') {
      console.log('Running single-worker test...');
      try {
        const result = await orch.agent({
          model: 'gpt-4o-mini',
          task: 'Reply with exactly: OK',
          maxTokens: 10,
          timeoutMs: 15000,
        });
        console.log('Result:', JSON.stringify(result, null, 2));
      } catch (err) {
        console.error('Test failed:', err.message);
      }

      console.log('\nWorker stats:', JSON.stringify(orch.getStats(), null, 2));
    } else {
      console.log('Usage: node workflow-agent-orchestrator.mjs --test');
      console.log('');
      console.log('In workflows:');
      console.log("  import { createOrchestrator } from '../shared/workflow-agent-orchestrator.mjs';");
      console.log('  const orch = createOrchestrator();');
      console.log("  const result = await orch.agent({ model: 'gpt-4o-mini', task: 'Hello' });");
    }
  })();
}
