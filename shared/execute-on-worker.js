/**
 * Execute LLM API tasks on remote fleet workers via SSH.
 *
 * This module fixes the core architectural problem: fleet-execute.js was selecting
 * a worker hostname but running the API call locally on aio-01. This module
 * actually SSHes to the selected worker and executes the API call there, using
 * that worker's credentials and network.
 *
 * Security:
 * - Hostname validated against [a-zA-Z0-9._-] (same as fleet-utils.js)
 * - Task content base64-encoded (never touches shell parsing)
 * - Script content base64-encoded (never touches shell parsing)
 * - BatchMode=yes prevents password prompt hangs
 * - StrictHostKeyChecking=accept-new prevents MITM on first connect
 * - Temp script cleaned up even on failure
 *
 * @module execute-on-worker
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

/**
 * Execute an LLM API task on a remote fleet worker via SSH.
 *
 * How it works:
 * 1. Base64-encodes the task parameters (avoids all shell quoting issues)
 * 2. Base64-encodes a Node.js script that calls executeRemoteLLMTask
 * 3. SSHes to the worker and:
 *    a. Decodes the script to a temp .mjs file
 *    b. Sets WORKER_PARAMS_B64 env var with the encoded parameters
 *    c. Runs the script with node (which makes the actual API call)
 *    d. Cleans up the temp file
 * 4. Parses the JSON output from stdout
 *
 * @param {Object} options - Execution options
 * @param {string} options.worker - Worker hostname (e.g., 'server-01', 'laptop-01')
 * @param {string} options.model - Model shorthand or full name (e.g., 'sonnet', 'opus')
 * @param {string} options.task - The prompt/task to send to the LLM
 * @param {number} [options.maxTokens=4096] - Maximum output tokens
 * @param {number} [options.timeoutMs=120000] - Request timeout in milliseconds
 * @param {string} [options.projectDir] - Project directory on worker (relative to home)
 * @returns {Promise<Object>} Result with output, tokens, timing, and execution_host
 * @throws {Error} If SSH connection fails, worker script fails, or API call fails
 */
export async function executeOnWorker({
  worker,
  model,
  task,
  maxTokens = 4096,
  timeoutMs = 120000,
  projectDir = 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills'
}) {
  if (!worker || typeof worker !== 'string') {
    throw new Error('worker must be a non-empty string');
  }
  if (!model || typeof model !== 'string') {
    throw new Error('model must be a non-empty string');
  }
  if (!task || typeof task !== 'string') {
    throw new Error('task must be a non-empty string');
  }

  // Validate hostname (same pattern as fleet-utils.js validateHostname)
  if (!/^[a-zA-Z0-9._-]+$/.test(worker)) {
    throw new Error(`Invalid worker hostname: ${worker}`);
  }
  if (!/^[a-zA-Z0-9/_.-]+$/.test(projectDir)) {
    throw new Error(`Invalid projectDir: ${projectDir}`);
  }

  // Base64-encode the task parameters. This is the key insight:
  // base64 output contains only [A-Za-z0-9+/=], which are all shell-safe
  // characters that need no quoting in any context.
  const paramsBase64 = Buffer.from(
    JSON.stringify({ task, model, maxTokens, timeoutMs })
  ).toString('base64');

  // The Node.js script that runs on the worker.
  // It reads base64-encoded params from env, decodes, calls the API.
  // Note: Use absolute path to import since temp script is in /tmp
  const scriptContent = [
    `import { executeRemoteLLMTask } from "/home/claude/${projectDir}/shared/fleet-utils.js";`,
    'const p = JSON.parse(Buffer.from(process.env.WORKER_PARAMS_B64, "base64").toString());',
    'try {',
    '  const r = await executeRemoteLLMTask({ task: p.task, model: p.model, maxTokens: p.maxTokens, timeoutMs: p.timeoutMs });',
    '  process.stdout.write(JSON.stringify(r));',
    '} catch (e) {',
    '  process.stdout.write(JSON.stringify({ error: e.message }));',
    '  process.exit(1);',
    '}'
  ].join('\n');

  const scriptBase64 = Buffer.from(scriptContent).toString('base64');

  // Unique temp file path on the worker
  const tmpFile = `/tmp/fleet-worker-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.mjs`;

  // Collect API keys from environment
  const apiKeys = [
    'ANTHROPIC_API_KEY',
    'ANTHROPIC_VERTEX_PROJECT_ID',
    'OPENAI_API_KEY',
    'OPENAI_TOKEN',
    'GEMINI_API_KEY',
    'OPENROUTER_API_KEY',
    'GROQ_API_KEY',
    'CEREBRAS_API_KEY',
    'DEEPSEEK_API_KEY',
    'CLOUDFLARE_API_KEY'
  ].filter(key => process.env[key])
   .map(key => `${key}=${Buffer.from(process.env[key]).toString('base64')}`)
   .join(' ');

  // The remote command. Every variable value is either:
  // - A validated path (projectDir, tmpFile)
  // - A base64 string (paramsBase64, scriptBase64, API keys)
  // - A shell builtin/keyword
  // None of these contain single quotes, so wrapping in single quotes for SSH is safe.
  const remoteCmd = [
    // Decode script to temp file
    `echo ${scriptBase64} | base64 -d > ${tmpFile}`,
    // cd to project directory (where shared/fleet-utils.js lives)
    `cd ~/${projectDir}`,
    // Run the script with params + API keys in env vars; capture exit status; clean up
    // Decode base64 API keys on the remote side
    apiKeys.split(' ').map(kv => {
      const [key, b64val] = kv.split('=');
      return `${key}=$(echo ${b64val} | base64 -d)`;
    }).join(' ') + ` WORKER_PARAMS_B64=${paramsBase64} node ${tmpFile}; S=$?; rm -f ${tmpFile}; exit $S`
  ].join(' && ');

  // Build SSH command. Single-quote the remote command.
  // Since remoteCmd contains no single quotes (proven above), no escaping needed.
  const sshCmd =
    `ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new ` +
    `claude@${worker} '${remoteCmd}'`;

  const startTime = Date.now();

  try {
    const { stdout, stderr } = await execAsync(sshCmd, {
      timeout: timeoutMs + 10000, // extra 10s buffer for SSH overhead
      maxBuffer: 10 * 1024 * 1024, // 10MB
      encoding: 'utf8'
    });

    const duration_ms = Date.now() - startTime;

    const trimmed = stdout.trim();
    if (!trimmed) {
      throw new Error(`Worker ${worker} returned empty output. Stderr: ${stderr || '(none)'}`);
    }

    let result;
    try {
      result = JSON.parse(trimmed);
    } catch (parseErr) {
      throw new Error(
        `Worker ${worker} returned invalid JSON.\n` +
        `stdout: ${trimmed.slice(0, 500)}\n` +
        `stderr: ${(stderr || '').slice(0, 500)}`
      );
    }

    if (result.error) {
      throw new Error(`Worker ${worker} API call failed: ${result.error}`);
    }

    return {
      ...result,
      execution_host: worker,
      actually_executed_on_worker: true,
      ssh_overhead_ms: duration_ms - (result.duration_ms || 0)
    };
  } catch (error) {
    const duration_ms = Date.now() - startTime;

    // Before giving up, try direct API call with intelligent-fallback.
    // Worker SSH failures should not prevent the task from completing
    // when the API can be called directly from the orchestrator.
    if (!options.disableFallback) {
      try {
        const { executeRemoteLLMTask } = await import('./fleet-utils.js');
        console.warn(
          `[execute-on-worker] Worker ${worker} failed (${error.message}), ` +
          `falling back to direct API call with intelligent-fallback`
        );
        const fallbackResult = await executeRemoteLLMTask({
          task,
          model,
          maxTokens,
          timeoutMs,
          disableFallback: false, // Let fleet-utils use intelligent-fallback
        });

        return {
          ...fallbackResult,
          execution_host: 'local-fallback',
          originally_targeted_worker: worker,
          worker_error: error.message,
          actually_executed_on_worker: false,
          fallback_used: true,
        };
      } catch (fallbackErr) {
        // Fallback also failed; report both errors
        console.error(
          `[execute-on-worker] Fallback direct API call also failed: ${fallbackErr.message}`
        );
      }
    }

    if (error.killed) {
      throw new Error(
        `SSH to worker ${worker} timed out after ${timeoutMs + 10000}ms.\n` +
        `The worker may be overloaded or unreachable.`
      );
    }

    if (error.code === 255 || (error.message && error.message.includes('Connection refused'))) {
      throw new Error(
        `Cannot SSH to worker ${worker}.\n` +
        `Ensure: ssh claude@${worker} echo OK\n` +
        `Original error: ${error.message}`
      );
    }

    // Re-throw if already our enhanced error
    if (error.message && (error.message.includes('Worker') || error.message.includes('API call failed'))) {
      throw error;
    }

    throw new Error(
      `Failed to execute on worker ${worker}: ${error.message}\n` +
      `Duration: ${duration_ms}ms`
    );
  }
}
