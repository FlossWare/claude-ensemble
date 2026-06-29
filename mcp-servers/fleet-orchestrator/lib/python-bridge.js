/**
 * Python Bridge - Spawns Python to execute fleet-executor.py for worker tasks
 *
 * Bridges JavaScript MCP server to the Python fleet executor, which handles
 * SSH-based distributed execution across the fleet with provider-agnostic
 * API calls (OpenAI, Anthropic, Google, Groq, Cerebras).
 *
 * The Python executor is preferred because it:
 *   - Works on ALL architectures (x86_64, arm64, armhf)
 *   - Uses stdlib only (no pip dependencies on workers)
 *   - Handles API key sourcing from remote .bashrc
 */

import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Resolve the path to fleet-executor.py relative to this project's shared/ directory
 */
const FLEET_EXECUTOR_PATH = path.resolve(
  __dirname, '..', '..', '..', 'shared', 'fleet-executor.py'
);

/**
 * Execute a worker task by spawning Python and calling fleet-executor.py
 *
 * Sends a JSON payload to the Python process via stdin and reads the
 * JSON result from stdout. Stderr is captured for diagnostics.
 *
 * @param {Object} options - Execution options
 * @param {string} options.worker - Worker hostname (e.g., 'server-01', 'aio-01' for local)
 * @param {string} options.model - Model name (e.g., 'gpt-4o-mini', 'claude-sonnet-4.5')
 * @param {string} options.task - The prompt/task to execute
 * @param {number} [options.maxTokens=4096] - Maximum tokens in response
 * @param {number} [options.timeoutMs=30000] - Timeout in milliseconds
 * @param {string} [options.apiKey] - Optional API key (Python will source from env if omitted)
 * @param {string} [options.pythonPath='python3'] - Path to Python interpreter
 * @returns {Promise<Object>} Result with output, duration_ms, tokens, execution_host, provider
 * @throws {Error} If Python process fails, times out, or returns an error
 */
export async function executePythonWorker(options) {
  const {
    worker,
    model,
    task,
    maxTokens = 4096,
    timeoutMs = 30000,
    apiKey = null,
    pythonPath = 'python3'
  } = options;

  if (!worker) throw new Error('worker is required');
  if (!model) throw new Error('model is required');
  if (!task) throw new Error('task is required');

  const payload = JSON.stringify({
    worker,
    model,
    task,
    max_tokens: maxTokens,
    timeout_ms: timeoutMs,
    ...(apiKey ? { api_key: apiKey } : {})
  });

  // Python script that imports fleet-executor and calls execute_on_worker
  const pythonScript = `
import sys, json, os
sys.path.insert(0, ${JSON.stringify(path.dirname(FLEET_EXECUTOR_PATH))})
from fleet_executor import execute_on_worker

params = json.loads(sys.stdin.read())
try:
    result = execute_on_worker(
        worker=params['worker'],
        model=params['model'],
        task=params['task'],
        max_tokens=params.get('max_tokens', 4096),
        timeout_ms=params.get('timeout_ms', 30000),
        api_key=params.get('api_key')
    )
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({'error': str(e)[:500]}))
    sys.exit(1)
`;

  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    let stdout = '';
    let stderr = '';
    let settled = false;

    // Add buffer time beyond the worker timeout for Python startup + SSH overhead
    const processTimeout = timeoutMs + 15000;

    const proc = spawn(pythonPath, ['-c', pythonScript], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env }
    });

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        proc.kill('SIGKILL');
        reject(new Error(
          `Python worker timed out after ${processTimeout}ms ` +
          `(worker=${worker}, model=${model})`
        ));
      }
    }, processTimeout);

    proc.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    proc.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    proc.on('error', (err) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        reject(new Error(
          `Failed to spawn Python: ${err.message}. ` +
          `Ensure ${pythonPath} is available.`
        ));
      }
    });

    proc.on('close', (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);

      const durationMs = Date.now() - startTime;

      if (code !== 0) {
        const errMsg = stderr.trim() || stdout.trim() || `exit code ${code}`;
        reject(new Error(
          `Python worker failed (code=${code}, worker=${worker}, model=${model}): ` +
          errMsg.slice(0, 500)
        ));
        return;
      }

      // Parse JSON result from stdout
      const trimmed = stdout.trim();
      if (!trimmed) {
        reject(new Error(
          `Python worker returned empty output (worker=${worker}, model=${model})`
        ));
        return;
      }

      let result;
      try {
        result = JSON.parse(trimmed);
      } catch (parseErr) {
        reject(new Error(
          `Invalid JSON from Python worker: ${trimmed.slice(0, 200)}`
        ));
        return;
      }

      if (result.error) {
        reject(new Error(
          `Python worker error (worker=${worker}, model=${model}): ${result.error}`
        ));
        return;
      }

      resolve({
        ...result,
        bridge: 'python',
        bridge_overhead_ms: durationMs - (result.duration_ms || 0)
      });
    });

    // Send payload to stdin and close it
    proc.stdin.write(payload);
    proc.stdin.end();
  });
}

/**
 * Execute tasks in parallel across multiple workers via Python fleet executor
 *
 * @param {Object} options - Parallel execution options
 * @param {string[]} options.workers - List of worker hostnames
 * @param {string} options.model - Model to use on all workers
 * @param {string[]} options.tasks - Tasks (one per worker, or single task repeated)
 * @param {number} [options.maxTokens=4096] - Max tokens per response
 * @param {number} [options.timeoutMs=30000] - Timeout per worker
 * @returns {Promise<Object[]>} Array of results, one per worker (errors included inline)
 */
export async function executePythonWorkerParallel(options) {
  const {
    workers,
    model,
    tasks,
    maxTokens = 4096,
    timeoutMs = 30000
  } = options;

  if (!workers || !workers.length) throw new Error('workers array is required');
  if (!model) throw new Error('model is required');
  if (!tasks || !tasks.length) throw new Error('tasks array is required');

  const promises = workers.map((worker, i) => {
    const task = i < tasks.length ? tasks[i] : tasks[0];
    return executePythonWorker({ worker, model, task, maxTokens, timeoutMs })
      .catch(err => ({
        worker,
        model,
        error: err.message,
        bridge: 'python'
      }));
  });

  return Promise.all(promises);
}

/**
 * Check whether the Python executor is available and functional
 *
 * @param {string} [pythonPath='python3'] - Path to Python interpreter
 * @returns {Promise<Object>} Health check result with available, python_version, executor_path
 */
export async function checkPythonBridge(pythonPath = 'python3') {
  return new Promise((resolve) => {
    const proc = spawn(pythonPath, [
      '-c',
      `import sys, json, os; ` +
      `sys.path.insert(0, ${JSON.stringify(path.dirname(FLEET_EXECUTOR_PATH))}); ` +
      `ok = os.path.exists(${JSON.stringify(FLEET_EXECUTOR_PATH)}); ` +
      `print(json.dumps({` +
      `"available": ok, ` +
      `"python_version": sys.version.split()[0], ` +
      `"executor_path": ${JSON.stringify(FLEET_EXECUTOR_PATH)}` +
      `}))`
    ], { stdio: ['pipe', 'pipe', 'pipe'] });

    let stdout = '';
    proc.stdout.on('data', (chunk) => { stdout += chunk; });

    const timer = setTimeout(() => {
      proc.kill('SIGKILL');
      resolve({ available: false, error: 'health check timed out' });
    }, 5000);

    proc.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        resolve({ available: false, error: `python exited with code ${code}` });
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim()));
      } catch {
        resolve({ available: false, error: 'invalid health check output' });
      }
    });

    proc.on('error', (err) => {
      clearTimeout(timer);
      resolve({ available: false, error: err.message });
    });
  });
}
