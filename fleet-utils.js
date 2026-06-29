/**
 * @deprecated This file is DEPRECATED. Use shared/fleet-orchestrator.js instead.
 *
 * Migration guide: docs/fleet-routing-consolidation.md
 *
 * Replace:
 *   import { selectWorker, remoteAgent } from './fleet-utils.js';
 * With:
 *   import { selectModel, executeOnModel, getWorkers, remoteExec } from './shared/fleet-orchestrator.js';
 *
 * This file will be removed in a future release.
 *
 * ---
 * Original description:
 * Fleet-Aware Workflow Utilities
 *
 * Helpers for distributing AI work across the entire fleet.
 * Use in workflows to automatically route work to the best server.
 */

// Emit deprecation warning on first import
console.warn(
  '[DEPRECATED] fleet-utils.js (root) is deprecated. ' +
  'Use shared/fleet-orchestrator.js instead. ' +
  'See docs/fleet-routing-consolidation.md for migration guide.'
);

import { execSync, exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs';
import path from 'path';

const execAsync = promisify(exec);

/**
 * Escape a string for safe use in a shell single-quoted context.
 * Wraps the value in single quotes, escaping any embedded single quotes
 * using the standard shell idiom: ' -> '\''
 *
 * @param {string} str - The string to escape
 * @returns {string} Shell-safe single-quoted string
 */
export function escapeShell(str) {
  if (typeof str !== 'string') {
    throw new TypeError(`escapeShell requires a string, got ${typeof str}`);
  }
  // Replace each ' with '\'' (end quote, escaped quote, start quote)
  // then wrap the whole thing in single quotes
  return "'" + str.replace(/'/g, "'\\''") + "'";
}

/**
 * Validate a server/hostname string to prevent SSH injection.
 * Only allows alphanumeric characters, hyphens, dots, and underscores.
 *
 * @param {string} server - Server hostname to validate
 * @returns {string} The validated server name
 * @throws {Error} If the server name contains invalid characters
 */
export function validateHostname(server) {
  if (typeof server !== 'string' || server.length === 0) {
    throw new Error('Server name must be a non-empty string');
  }
  if (!/^[a-zA-Z0-9._-]+$/.test(server)) {
    throw new Error(`Invalid server name: ${JSON.stringify(server)} — only alphanumeric, hyphens, dots, and underscores are allowed`);
  }
  if (server.length > 253) {
    throw new Error(`Server name too long (${server.length} chars, max 253)`);
  }
  return server;
}

// Port 3004: Fleet Dispatcher with Circuit Breaker (Prometheus-based discovery)
//   - API: /fleet/status, /agent/execute, /agent/complete
//   - Features: Circuit breaker, load balancing, historical learning
// Port 3003: Announce Dispatcher (different API, returns 'nodes' not 'servers')
// Port 3002: Legacy job queue (referenced in multi-ai-config.json)
const FLEET_DISPATCHER = 'http://pi-02:3004';

/**
 * Infer job type from agent options
 */
export function inferJobType(opts = {}) {
  const label = (opts.label || '').toLowerCase();
  const phase = (opts.phase || '').toLowerCase();
  const model = (opts.model || '').toLowerCase();

  if (label.includes('arbiter') || label.includes('synthesis') || label.includes('consensus')) {
    return 'ai-consensus';
  }
  if (label.includes('extract') || label.includes('parse') || label.includes('detect')) {
    return 'data-extraction';
  }
  if (phase.includes('review') || phase.includes('verify') || phase.includes('audit')) {
    return 'code-review';
  }
  if (phase.includes('test')) {
    return 'build-test';
  }
  if (model === 'fable' || model === 'opus') {
    return 'ai-heavy';
  }
  if (model === 'haiku') {
    return 'ai-light';
  }
  if (opts.schema) {
    try {
      if (JSON.stringify(opts.schema).length > 500) {
        return 'ai-heavy';
      }
    } catch (e) {
      return 'ai-heavy';
    }
  }
  return 'agent';
}

/**
 * Load fleet configuration with fallback paths
 */
export function loadFleetConfig() {
  const paths = [
    '/mnt/nas/multi-ai-config.json',
    path.join(process.env.HOME || '', '.claude/multi-ai-config.json'),
    path.join(process.env.HOME || '', 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/multi-ai-config.json'),
  ];

  for (const configPath of paths) {
    try {
      return JSON.parse(fs.readFileSync(configPath, 'utf8'));
    } catch (e) {
      // Try next path
      continue;
    }
  }

  throw new Error(
    'Fleet config not found. Tried:\n' +
    paths.map(p => `  - ${p}`).join('\n')
  );
}

/**
 * Get fleet topology from fleet dispatcher (Prometheus-discovered)
 */
export async function getFleetTopology() {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    try {
      const response = await fetch(`${FLEET_DISPATCHER}/fleet/status`, {
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      const data = await response.json();

      // Convert Prometheus data to server capabilities format
      const topology = {};
      for (const server of data.servers) {
        const name = server.instance.replace(':9100', '');
        topology[name] = {
          ram: server.total_ram_gb,
          availRam: server.avail_ram_gb,
          cpu: server.cores,
          arch: server.arch,
          load: server.load_1m,
          isHeavy: server.is_heavy,
          isFast: server.is_fast,
          isLight: server.is_light,
          isMedium: server.is_medium,
          apiOnly: server.api_only,
          ramPressure: server.ram_pressure,
          isOverloaded: server.is_overloaded
        };
      }
      return topology;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        console.warn('[fleet] getFleetTopology timeout after 30s, falling back to local config');
      } else {
        console.warn('[fleet] getFleetTopology failed:', error.message);
      }
      // Fallback to local config if dispatcher unavailable
      const config = loadFleetConfig();
      return config.serverCapabilities;
    }
  } catch (error) {
    console.error('[fleet] getFleetTopology error:', error.message);
    return {};
  }
}

/**
 * Select best worker for a job type
 * @param {string} jobType - 'code', 'heavy', 'fast', 'data', 'batch'
 * @returns {string} server name
 */
export function selectWorker(jobType) {
  const config = loadFleetConfig();

  // Map job types to server roles
  const roleMapping = {
    'code': ['code', 'medium'],
    'heavy': ['heavy', 'batch'],
    'fast': ['fast', 'preprocessing'],
    'data': ['data', 'heavy'],
    'batch': ['batch', 'heavy'],
    'pdf-small': ['passive'],  // aio-01 for small PDFs
    'pdf-medium': ['fast'],
    'pdf-large': ['code', 'medium'],
    'pdf-huge': ['heavy', 'batch']
  };

  const requiredRoles = roleMapping[jobType] || ['heavy'];

  // Find servers matching roles, sorted by priority
  const servers = Object.entries(config.serverCapabilities)
    .filter(([name, caps]) =>
      caps.roles.some(role => requiredRoles.includes(role))
    )
    .sort((a, b) => a[1].priority - b[1].priority)
    .map(([name]) => name);

  return servers[0] || 'server-03';  // Default to server-03 if no match
}

/**
 * Select best server for a specific AI model
 * @param {string} modelName - e.g., 'opus', 'sonnet', 'cerebras-120b'
 * @returns {string} server name
 */
export function selectServerForModel(modelName) {
  const config = loadFleetConfig();

  // Find server assigned to this model
  const worker = config.workers.models.find(w =>
    typeof w === 'object' ? w.name === modelName : w === modelName
  );

  if (worker && typeof worker === 'object' && worker.server) {
    return worker.server;
  }

  // Check serverCapabilities for model assignment
  for (const [serverName, caps] of Object.entries(config.serverCapabilities)) {
    if (caps.models && caps.models.includes(modelName)) {
      return serverName;
    }
  }

  // Default assignments based on model characteristics
  if (modelName.includes('fable') || modelName.includes('opus')) {
    return 'laptop-01';  // Heavy models
  } else if (modelName.includes('haiku') || modelName.includes('sonnet')) {
    return 'server-01';  // Fast models
  } else if (modelName.includes('gpt') || modelName.includes('qwen')) {
    return 'server-02';  // Code models
  } else {
    return 'server-03';  // Other heavy models
  }
}

/**
 * Execute agent on a specific server via SSH + claude -p
 *
 * Phase 3: Uses the battle-tested SSH + claude -p pattern from fleet-bulk-lib.sh.
 * Async execution (child_process.exec) preserves parallelism in parallel() thunks.
 *
 * @param {string} server - Server name (e.g., 'server-01')
 * @param {string} prompt - Agent prompt
 * @param {object} opts - Options {schema, model, label, phase, timeoutMs, jobId}
 * @returns {Promise<{result: any, cost: number, remoteDuration: number}>}
 */
export async function remoteAgent(server, prompt, opts = {}) {
  const {schema, model, timeoutMs = 180000, jobId} = opts;

  // Validate server hostname to prevent SSH injection
  validateHostname(server);

  const NFS_ROOT = process.env.NFS_ROOT || path.join(process.env.HOME || '/home/sfloess', 'Development');
  const VERTEX_PROJECT = process.env.ANTHROPIC_VERTEX_PROJECT_ID || 'itpc-gcp-uie-eng-claude';
  const VERTEX_ENABLED = process.env.CLAUDE_CODE_USE_VERTEX || '1';
  const GENAI_VERTEX = process.env.GOOGLE_GENAI_USE_VERTEXAI || 'True';

  // Environment variable exports — use escapeShell for all interpolated values
  const envExports = [
    `export ANTHROPIC_VERTEX_PROJECT_ID=${escapeShell(VERTEX_PROJECT)}`,
    `export CLAUDE_CODE_USE_VERTEX=${escapeShell(VERTEX_ENABLED)}`,
    `export GOOGLE_GENAI_USE_VERTEXAI=${escapeShell(GENAI_VERTEX)}`,
  ].join(' && ');

  // Claude flags (matches fleet-bulk-lib.sh lines 388-393)
  const claudeFlags = '--dangerously-skip-permissions --output-format json --max-turns 50 --no-session-persistence';

  // Determine prompt passing method
  const promptBytes = Buffer.byteLength(prompt, 'utf8');
  const effectiveJobId = jobId || `remote-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  let claudeCmd;
  let usedPromptFile = false;

  if (promptBytes >= 4096) {
    // Large prompt: write to NFS file, read on remote
    const promptFilePath = await promptToFile(effectiveJobId, prompt);
    claudeCmd = `claude -p ${claudeFlags} "$(cat ${escapeShell(promptFilePath)})"`;
    usedPromptFile = true;
  } else {
    // Small prompt: inline with escapeShell for proper quoting
    claudeCmd = `claude -p ${claudeFlags} ${escapeShell(prompt)}`;
  }

  // Full remote command — use escapeShell for NFS_ROOT path
  const remoteCmd = `${envExports} && cd ${escapeShell(NFS_ROOT)} && ${claudeCmd}`;
  // Escape for SSH double-quote wrapper
  const escapedRemoteCmd = remoteCmd
    .replace(/\\/g, '\\\\')
    .replace(/\$/g, '\\$')
    .replace(/`/g, '\\`')
    .replace(/"/g, '\\"')
    .replace(/!/g, '\\!');

  const sshCommand = `ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -- ${escapeShell(server)} "${escapedRemoteCmd}"`;

  try {
    const { stdout } = await execAsync(sshCommand, {
      encoding: 'utf8',
      maxBuffer: 50 * 1024 * 1024, // 50MB buffer
      timeout: timeoutMs + 5000,
    });

    // Parse claude JSON output envelope
    if (!stdout || stdout.trim().length === 0) {
      throw new Error('Empty output from remote agent');
    }

    // Filter out bash completion messages and other non-JSON lines
    const lines = stdout.split('\n').filter(line =>
      !line.includes('Universal AI bash completion') &&
      !line.includes('bash completion loaded') &&
      line.trim().length > 0
    );

    const cleanOutput = lines.join('\n').trim();
    if (!cleanOutput || cleanOutput.length === 0) {
      throw new Error('Empty output from remote agent after filtering');
    }

    const envelope = JSON.parse(cleanOutput);

    if (envelope.is_error === true) {
      throw new Error(`Remote agent error: ${envelope.result || 'Unknown error'}`);
    }

    const resultStr = envelope.result;
    if (resultStr === null || resultStr === undefined || resultStr === '') {
      throw new Error('Empty result from remote agent');
    }

    // Parse result based on schema expectation
    let result = resultStr;
    if (schema && typeof resultStr === 'string') {
      const trimmed = resultStr.trim();
      if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
          result = JSON.parse(trimmed);
        } catch (e) {
          // Return raw string if JSON parse fails - caller decides
          result = trimmed;
        }
      }
    }

    return {
      result,
      cost: envelope.cost_usd || 0,
      remoteDuration: envelope.duration_ms || 0,
    };
  } catch (error) {
    console.error(`Remote agent failed on ${server}:`, error.message);
    throw error;
  } finally {
    if (usedPromptFile) {
      await cleanupJobFiles(effectiveJobId).catch(() => {});
    }
  }
}

/**
 * Write prompt to NFS shared file for large prompt passing
 * @param {string} jobId - Job identifier
 * @param {string} prompt - Prompt text
 * @returns {Promise<string>} Path to prompt file
 */
export async function promptToFile(jobId, prompt) {
  const NFS_ROOT = process.env.NFS_ROOT || path.join(process.env.HOME || '/home/sfloess', 'Development');
  const promptsDir = path.join(NFS_ROOT, 'fleet-results', '.prompts');
  await fs.promises.mkdir(promptsDir, { recursive: true });
  const filePath = path.join(promptsDir, `${jobId}.txt`);
  await fs.promises.writeFile(filePath, prompt, 'utf8');
  return filePath;
}

/**
 * Read result from NFS shared file
 * @param {string} jobId - Job identifier
 * @returns {Promise<Object>} Parsed JSON result
 */
export async function readResultFile(jobId) {
  const NFS_ROOT = process.env.NFS_ROOT || path.join(process.env.HOME || '/home/sfloess', 'Development');
  const filePath = path.join(NFS_ROOT, 'fleet-results', '.results', `${jobId}.json`);
  const content = await fs.promises.readFile(filePath, 'utf8');
  return JSON.parse(content);
}

/**
 * Clean up temporary NFS files for a job
 * @param {string} jobId - Job identifier
 * @returns {Promise<void>}
 */
export async function cleanupJobFiles(jobId) {
  const NFS_ROOT = process.env.NFS_ROOT || path.join(process.env.HOME || '/home/sfloess', 'Development');
  const promptFile = path.join(NFS_ROOT, 'fleet-results', '.prompts', `${jobId}.txt`);
  const resultFile = path.join(NFS_ROOT, 'fleet-results', '.results', `${jobId}.json`);
  await Promise.all([
    fs.promises.unlink(promptFile).catch(() => {}),
    fs.promises.unlink(resultFile).catch(() => {}),
  ]);
}

/**
 * Distribute agent calls across fleet in parallel
 * @param {Array} prompts - Array of {prompt, opts} objects
 * @param {string} strategy - 'auto', 'balanced', 'code', 'heavy', 'fast'
 * @returns {Promise<Array>} Results from all agents
 */
export async function distributeAgents(prompts, strategy = 'auto') {
  const config = loadFleetConfig();

  // Determine server for each prompt
  const assignments = prompts.map((item, index) => {
    const {prompt, opts = {}} = item;

    let server;
    if (opts.server) {
      server = opts.server;  // Explicit server
    } else if (opts.model) {
      server = selectServerForModel(opts.model);  // Based on model
    } else if (strategy === 'balanced') {
      // Round-robin across active servers
      const servers = ['laptop-01', 'server-01', 'server-02', 'server-03'];
      server = servers[index % servers.length];
    } else if (strategy === 'code') {
      server = 'server-02';
    } else if (strategy === 'heavy') {
      server = index % 2 === 0 ? 'laptop-01' : 'server-03';
    } else if (strategy === 'fast') {
      server = 'server-01';
    } else {
      // Auto: distribute based on job type
      server = selectWorker(opts.jobType || 'heavy');
    }

    return {prompt, opts, server};
  });

  // Execute all in parallel
  const results = await Promise.all(
    assignments.map(({prompt, opts, server}) =>
      remoteAgent(server, prompt, opts)
    )
  );

  return results;
}

/**
 * Get server load/health and model status from fleet dispatcher
 */
export async function getServerHealth() {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    try {
      const response = await fetch(`${FLEET_DISPATCHER}/fleet/status`, {
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      const data = await response.json();

      const health = {};
      for (const server of data.servers) {
        const name = server.instance.replace(':9100', '');
        health[name] = {
          status: server.is_overloaded ? 'degraded' : 'up',
          load: server.load_1m,
          cpu: server.cpu_usage_pct,
          availRam: server.avail_ram_gb,
          pendingJobs: server.pending_jobs,
          ramPressure: server.ram_pressure
        };
      }

      return {
        servers: health,
        modelHealth: data.model_health
      };
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        console.warn('[fleet] getServerHealth timeout after 30s');
      } else {
        console.warn('[fleet] getServerHealth failed:', error.message);
      }
      return {servers: {}, modelHealth: {}};
    }
  } catch (error) {
    console.error('[fleet] getServerHealth error:', error.message);
    return {servers: {}, modelHealth: {}};
  }
}

/**
 * Dispatch agent via fleet dispatcher with circuit breaker
 * @param {string} model - AI model name (e.g., 'opus', 'sonnet', 'haiku')
 * @param {string} prompt - Agent prompt
 * @param {object} opts - Options {jobType, estimatedRam, estimatedDuration}
 * @returns {Promise<object>} {jobId, server, model, score, timestamp}
 */
export async function dispatchAgent(model, prompt, opts = {}) {
  const {jobType = 'agent', estimatedRam = 1.0, estimatedDuration = 60} = opts;

  try {
    const response = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        model,
        prompt,
        job_type: jobType,
        estimated_ram_gb: estimatedRam,
        estimated_duration: estimatedDuration
      })
    });

    if (!response.ok) {
      let errorMsg = `HTTP ${response.status}`;
      try {
        const error = await response.json();
        errorMsg = error.message || error.error || errorMsg;
      } catch {
        // Response is not JSON, try text
        try {
          const text = await response.text();
          errorMsg = text || errorMsg;
        } catch {
          // Keep HTTP status as error message
        }
      }
      throw new Error(errorMsg);
    }

    return await response.json();
  } catch (error) {
    console.error(`❌ Agent dispatch failed for ${model}:`, error.message);
    return null;
  }
}

/**
 * Complete agent job and record history
 * @param {string} jobId - Job ID from dispatchAgent
 * @param {string} instance - Server instance (e.g., 'server-03:9100')
 * @param {boolean} success - Whether job succeeded
 * @param {number} duration - Actual duration in seconds
 * @param {string} jobType - Job type
 * @param {string} model - Model used
 * @param {string} error - Error message if failed
 */
export async function completeAgent(jobId, instance, success, duration, jobType, model, error = null) {
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        job_id: jobId,
        instance,
        success,
        duration_seconds: duration,
        job_type: jobType,
        model,
        error
      })
    });

    return await response.json();
  } catch (err) {
    console.error(`❌ Failed to complete job ${jobId}:`, err.message);
    return {status: 'error'};
  }
}

/**
 * Get model health status (circuit breaker state)
 */
export async function getModelHealth() {
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/fleet/status`);
    const data = await response.json();
    return data.model_health || {};
  } catch (error) {
    console.warn('Could not fetch model health');
    return {};
  }
}

/**
 * Smart worker selection with load balancing
 * Queries pi-02 for current load and selects least-loaded server
 */
export async function selectWorkerWithLoadBalance(jobType) {
  const health = await getServerHealth();
  const baseServer = selectWorker(jobType);

  // If health data unavailable, use base selection
  if (!health || !health.servers || Object.keys(health.servers).length === 0) {
    return baseServer;
  }

  // Find least-loaded server matching job type
  const config = loadFleetConfig();
  const roleMapping = {
    'code': ['code', 'medium'],
    'heavy': ['heavy', 'batch'],
    'fast': ['fast', 'preprocessing']
  };

  const requiredRoles = roleMapping[jobType] || ['heavy'];

  const candidates = Object.entries(config.serverCapabilities)
    .filter(([name, caps]) =>
      caps.roles.some(role => requiredRoles.includes(role)) &&
      health.servers[name]?.status === 'up'
    )
    .map(([name]) => ({
      name,
      load: health.servers[name]?.load || 0
    }))
    .sort((a, b) => a.load - b.load);

  return candidates[0]?.name || baseServer;
}

export default {
  escapeShell,
  validateHostname,
  loadFleetConfig,
  getFleetTopology,
  selectWorker,
  selectServerForModel,
  remoteAgent,
  distributeAgents,
  getServerHealth,
  selectWorkerWithLoadBalance,
  dispatchAgent,
  completeAgent,
  getModelHealth,
  promptToFile,
  readResultFile,
  cleanupJobFiles
};
