/**
 * Fleet-Aware Workflow Utilities
 *
 * Helpers for distributing AI work across the entire fleet.
 * Use in workflows to automatically route work to the best server.
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

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
    const response = await fetch(`${FLEET_DISPATCHER}/fleet/status`);
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
    // Fallback to local config if dispatcher unavailable
    const config = loadFleetConfig();
    return config.serverCapabilities;
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
 * Execute agent on a specific server
 * @param {string} server - Server name
 * @param {string} prompt - Agent prompt
 * @param {object} opts - Options {schema, model, label, phase}
 * @returns {Promise<any>} Agent result
 */
export async function remoteAgent(server, prompt, opts = {}) {
  const {schema, model, label, phase} = opts;

  // Build command to run on remote server
  const schemaArg = schema ? `--schema='${JSON.stringify(schema)}'` : '';
  const modelArg = model ? `--model=${model}` : '';
  const labelArg = label ? `--label="${label}"` : '';
  const phaseArg = phase ? `--phase="${phase}"` : '';

  const command = `ssh ${server} "cd ~/fleet-coordinator && ./run-agent.sh ${modelArg} ${schemaArg} ${labelArg} ${phaseArg} '${prompt.replace(/'/g, "'\\''")}'"`;

  try {
    const result = execSync(command, {encoding: 'utf8', maxBuffer: 10 * 1024 * 1024});

    if (schema) {
      return JSON.parse(result);
    }
    return result.trim();
  } catch (error) {
    console.error(`❌ Remote agent failed on ${server}:`, error.message);
    return null;
  }
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
    const response = await fetch(`${FLEET_DISPATCHER}/fleet/status`);
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
    console.warn('Could not fetch server health from fleet dispatcher');
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
  getModelHealth
};
