/**
 * Worker HTTP Client
 * Replaces SSH-based fleet-ssh-orchestrator.js
 * Communicates with worker-daemon.py on each worker node
 */

import http from 'http';

const WORKER_PORT = 8003;
const AUTH_TOKEN = process.env.WORKER_AUTH_TOKEN || 'change-me-in-production';

/**
 * Execute command on worker via HTTP
 *
 * @param {Object} options
 * @param {string} options.worker - Worker hostname
 * @param {string} options.command - Command to execute
 * @param {string[]} options.args - Command arguments
 * @param {number} options.timeoutMs - Execution timeout
 * @returns {Promise<Object>} {stdout, stderr, returncode, duration_ms}
 */
export async function executeOnWorker({ worker, command, args = [], timeoutMs = 30000 }) {
  const startTime = Date.now();

  return new Promise((resolve, reject) => {
    const requestData = JSON.stringify({
      command,
      args,
      timeout: Math.floor(timeoutMs / 1000)
    });

    const req = http.request({
      hostname: worker,
      port: WORKER_PORT,
      path: '/execute',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(requestData),
        'Authorization': `Bearer ${AUTH_TOKEN}`
      },
      timeout: timeoutMs
    }, (res) => {
      let data = '';

      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        const duration_ms = Date.now() - startTime;

        try {
          const result = JSON.parse(data);

          if (res.statusCode === 200) {
            resolve({
              output: result.stdout,
              stderr: result.stderr,
              exitCode: result.returncode,
              worker,
              duration_ms,
              success: result.success
            });
          } else {
            reject(new Error(result.error || `HTTP ${res.statusCode}`));
          }
        } catch (err) {
          reject(new Error(`Failed to parse response: ${err.message}`));
        }
      });
    });

    req.on('error', (err) => {
      reject(new Error(`Cannot connect to worker ${worker}:${WORKER_PORT}: ${err.message}`));
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error(`Worker ${worker} timed out after ${timeoutMs}ms`));
    });

    req.write(requestData);
    req.end();
  });
}

/**
 * Deploy file to worker via HTTP
 *
 * @param {Object} options
 * @param {string} options.worker - Worker hostname
 * @param {string} options.path - Target path (relative to worker home)
 * @param {string} options.content - File content
 * @param {number} options.mode - File permissions (octal)
 * @returns {Promise<Object>} {path, size, checksum}
 */
export async function deployToWorker({ worker, path, content, mode = 0o755 }) {
  return new Promise((resolve, reject) => {
    const requestData = JSON.stringify({
      path,
      content,
      encoding: 'utf8',
      mode
    });

    const req = http.request({
      hostname: worker,
      port: WORKER_PORT,
      path: '/deploy',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(requestData),
        'Authorization': `Bearer ${AUTH_TOKEN}`
      }
    }, (res) => {
      let data = '';

      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);

          if (res.statusCode === 200) {
            resolve(result);
          } else {
            reject(new Error(result.error || `HTTP ${res.statusCode}`));
          }
        } catch (err) {
          reject(new Error(`Failed to parse response: ${err.message}`));
        }
      });
    });

    req.on('error', (err) => {
      reject(new Error(`Cannot connect to worker ${worker}:${WORKER_PORT}: ${err.message}`));
    });

    req.write(requestData);
    req.end();
  });
}

/**
 * Check worker health
 *
 * @param {string} worker - Worker hostname
 * @returns {Promise<Object>} {status, hostname, worker_home}
 */
export async function checkWorkerHealth(worker) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: worker,
      port: WORKER_PORT,
      path: '/health',
      method: 'GET',
      timeout: 5000
    }, (res) => {
      let data = '';

      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          resolve(result);
        } catch (err) {
          reject(new Error(`Invalid health response: ${err.message}`));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error(`Health check timeout for ${worker}`));
    });

    req.end();
  });
}

/**
 * Execute on multiple workers in parallel
 *
 * @param {Object} options
 * @param {Array<{id: string, worker: string, command: string}>} options.tasks
 * @param {number} options.maxParallel - Max concurrent executions
 * @returns {Promise<Array>} Results
 */
export async function executeParallel({ tasks, maxParallel = 8 }) {
  const results = [];
  const queue = [...tasks];
  const inProgress = new Set();

  while (queue.length > 0 || inProgress.size > 0) {
    while (queue.length > 0 && inProgress.size < maxParallel) {
      const task = queue.shift();
      inProgress.add(task.id);

      executeOnWorker({
        worker: task.worker,
        command: task.command,
        args: task.args,
        timeoutMs: task.timeoutMs || 30000
      })
        .then(result => {
          results.push({ taskId: task.id, result, error: null });
        })
        .catch(error => {
          results.push({ taskId: task.id, result: null, error: error.message });
        })
        .finally(() => {
          inProgress.delete(task.id);
        });
    }

    if (inProgress.size >= maxParallel || queue.length === 0) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }

  return results;
}
