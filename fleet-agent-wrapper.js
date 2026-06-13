/**
 * Fleet-Aware Agent Wrapper
 *
 * Factory that creates a fleet-aware wrapper around the original agent() function.
 * Phase 2: Telemetry only - registers jobs, executes locally, records completion.
 * Phase 3: Actual remote execution via SSH + claude -p on fleet servers.
 *
 * Phase 3 execution flow:
 *   1. Workflow calls agent() -> fleet-agent-wrapper intercepts
 *   2. POST /agent/execute to pi-02:3004 dispatcher -> returns {job_id, server, model, score}
 *   3. Wrapper executes SSH + claude -p on the assigned server (RemoteExecutor)
 *   4. Wrapper parses result from claude JSON envelope
 *   5. Wrapper POST /agent/complete to report outcome
 *   6. Returns result to workflow
 *
 * Failure cascade (5 levels):
 *   L1: Dispatcher unreachable -> fall back to local agent()
 *   L2: SSH connection fails -> retry on alternate server (one retry)
 *   L3: claude -p fails on remote -> fall back to local agent()
 *   L4: Result parsing fails -> return raw output
 *   L5: Timeout -> kill SSH, fall back to local agent()
 *
 * Toggle:
 *   FLEET_DISPATCHER=false       -> disable everything (no dispatcher contact)
 *   FLEET_REMOTE_EXECUTION=false -> Phase 2 (telemetry only, local execution) [default]
 *   FLEET_REMOTE_EXECUTION=true  -> Phase 3 (actual remote execution) [explicit opt-in required]
 *
 * Usage in workflows:
 *   import { createFleetAgent } from './fleet-agent-wrapper.js';
 *   const _originalAgent = agent;
 *   const _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
 */

import { RemoteExecutor } from './fleet-remote-executor.js';
import fs from 'fs';
import path from 'path';

// Resource estimation tables
const RAM_ESTIMATES = {
  'fable': 2.0,
  'opus': 2.0,
  'sonnet': 1.5,
  'haiku': 0.5,
  'gpt-4o': 1.5,
  'gemini': 1.5,
};

const DURATION_ESTIMATES = {
  'ai-heavy': 120,
  'ai-consensus': 90,
  'code-review': 60,
  'build-test': 180,
  'ai-light': 30,
  'data-extraction': 60,
  'agent': 60,
};

// Timeout multiplier: estimated duration * this = actual timeout
const TIMEOUT_MULTIPLIER = 3;
const MIN_TIMEOUT_MS = 60000;   // 60 seconds minimum
const MAX_TIMEOUT_MS = 600000;  // 10 minutes maximum

/**
 * Infer job type from agent options
 */
function inferJobType(opts) {
  const label = (opts.label || '').toLowerCase();
  const phase = (opts.phase || '').toLowerCase();
  const model = (opts.model || '').toLowerCase();

  // Check label patterns
  if (label.includes('arbiter') || label.includes('synthesis') || label.includes('consensus')) {
    return 'ai-consensus';
  }
  if (label.includes('extract') || label.includes('parse') || label.includes('detect')) {
    return 'data-extraction';
  }

  // Check phase patterns
  if (phase.includes('review') || phase.includes('verify') || phase.includes('audit')) {
    return 'code-review';
  }
  if (phase.includes('test')) {
    return 'build-test';
  }

  // Check model
  if (model === 'fable' || model === 'opus') {
    return 'ai-heavy';
  }
  if (model === 'haiku') {
    return 'ai-light';
  }

  // Check schema complexity
  if (opts.schema) {
    try {
      if (JSON.stringify(opts.schema).length > 500) {
        return 'ai-heavy';
      }
    } catch (e) {
      // If schema is not serializable (circular ref), assume it's complex
      return 'ai-heavy';
    }
  }

  return 'agent';
}

/**
 * Match model name against pattern (supports wildcards)
 * @param {string} modelName - Model name to check
 * @param {string} pattern - Pattern (e.g., "gpt-*", "ollama-*")
 * @returns {boolean} true if matches
 */
function matchesModelPattern(modelName, pattern) {
  if (pattern === '*') return true;
  if (!pattern.includes('*')) return modelName === pattern;

  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp('^' + escaped.replace(/\*/g, '.*') + '$');
  return regex.test(modelName);
}

/**
 * Check if model is allowed in current directory
 * @param {string} modelName - Model name to check
 * @returns {{allowed: boolean, reason?: string}} Compliance result
 */
function checkModelCompliance(modelName) {
  if (!modelName) return { allowed: true };

  try {
    const fleetConfigPath = path.join(process.env.HOME || '/home/sfloess', '.claude', 'fleet.json');
    if (!fs.existsSync(fleetConfigPath)) return { allowed: true };

    const config = JSON.parse(fs.readFileSync(fleetConfigPath, 'utf8'));
    const restrictions = config.compliance?.path_restrictions || [];

    let cwd;
    try {
      cwd = fs.realpathSync(process.cwd());
    } catch (e) {
      cwd = process.cwd();
    }

    // Find matching restrictions (longest path first = most specific)
    const matching = restrictions
      .filter(r => cwd.startsWith(r.path))
      .sort((a, b) => b.path.length - a.path.length);

    if (!matching.length) return { allowed: true };

    const restriction = matching[0];

    // Check denied models first
    if (restriction.denied_models) {
      for (const pattern of restriction.denied_models) {
        if (matchesModelPattern(modelName, pattern)) {
          return {
            allowed: false,
            reason: restriction.reason || `Model ${modelName} not allowed in ${restriction.path}`
          };
        }
      }
    }

    // Check allowed models if specified
    if (restriction.allowed_models) {
      for (const pattern of restriction.allowed_models) {
        if (matchesModelPattern(modelName, pattern)) {
          return { allowed: true };
        }
      }
      // Model not in allow list
      return {
        allowed: false,
        reason: restriction.reason || `Model ${modelName} not in allowed list for ${restriction.path}`
      };
    }

    // No denied, no allowed = allow by default
    return { allowed: true };
  } catch (e) {
    // If we can't read config, assume compliant
    return { allowed: true };
  }
}

/**
 * Check compliance - verify cwd is not under forbidden paths
 * @returns {boolean} true if compliant (safe to use fleet)
 */
function checkCompliance() {
  try {
    const fleetConfigPath = path.join(process.env.HOME || '/home/sfloess', '.claude', 'fleet.json');
    if (!fs.existsSync(fleetConfigPath)) return true;

    const config = JSON.parse(fs.readFileSync(fleetConfigPath, 'utf8'));
    const forbidden = config.compliance?.forbidden_paths || [];

    let cwd;
    try {
      cwd = fs.realpathSync(process.cwd());
    } catch (e) {
      cwd = process.cwd();
    }

    for (const fp of forbidden) {
      if (cwd.startsWith(fp)) {
        return false;
      }
    }
  } catch (e) {
    // If we can't read config, assume compliant
  }
  return true;
}

/**
 * Calculate timeout from estimated duration
 * @param {number} estimatedDurationSec - Estimated duration in seconds
 * @returns {number} Timeout in milliseconds
 */
function calculateTimeout(estimatedDurationSec) {
  const timeoutMs = estimatedDurationSec * 1000 * TIMEOUT_MULTIPLIER;
  return Math.min(MAX_TIMEOUT_MS, Math.max(MIN_TIMEOUT_MS, timeoutMs));
}

/**
 * Get alternate server from fleet topology when primary fails
 *
 * @param {string} failedServer - Server that failed
 * @returns {Promise<string|null>} Alternate server hostname, or null
 */
async function getAlternateServer(failedServer) {
  try {
    // Dynamic import to avoid circular dependencies
    const fleetUtils = await import('./fleet-utils.js');
    const topology = await fleetUtils.getFleetTopology();

    if (!topology || Object.keys(topology).length === 0) {
      return null;
    }

    // Filter out failed server, sort by available RAM descending
    const candidates = Object.entries(topology)
      .filter(([name]) => {
        // Extract hostname from potential instance format (server-01:9100 -> server-01)
        const normalizedFailed = failedServer.replace(':9100', '');
        const normalizedName = name.replace(':9100', '');
        return normalizedName !== normalizedFailed;
      })
      .filter(([, info]) => !info.apiOnly && !info.isOverloaded)
      .sort((a, b) => (b[1].availRam || 0) - (a[1].availRam || 0));

    return candidates.length > 0 ? candidates[0][0] : null;
  } catch (e) {
    return null;
  }
}

/**
 * Create a fleet-aware agent wrapper
 *
 * @param {Function} originalAgent - The original workflow agent() function
 * @returns {Function} Wrapped agent function with fleet dispatcher integration
 */
export function createFleetAgent(originalAgent) {
  // Check Phase 3 toggle
  // SAFETY: Remote execution is opt-in only. Must explicitly set FLEET_REMOTE_EXECUTION=true.
  const remoteExecutionEnabled = process.env.FLEET_REMOTE_EXECUTION === 'true';

  // Create RemoteExecutor instance (reused across all calls)
  let executor = null;
  if (remoteExecutionEnabled) {
    try {
      executor = new RemoteExecutor();
    } catch (e) {
      // If RemoteExecutor fails to initialize, fall back to Phase 2
      console.warn('RemoteExecutor initialization failed, using Phase 2 mode:', e.message);
    }
  }

  return async function wrappedAgent(prompt, opts = {}) {
    // Check if dispatcher is disabled entirely
    if (process.env.FLEET_DISPATCHER === 'false') {
      return originalAgent(prompt, opts);
    }

    // Compliance check - skip fleet for forbidden paths
    if (!checkCompliance()) {
      return originalAgent(prompt, opts);
    }

    const model = opts.model || 'sonnet';

    // Model compliance check - ensure model allowed in current directory
    const modelCheck = checkModelCompliance(model);
    if (!modelCheck.allowed) {
      throw new Error(`Model compliance violation: ${modelCheck.reason}`);
    }
    const jobType = opts.jobType || inferJobType(opts);
    const estimatedRam = opts.estimatedRam || RAM_ESTIMATES[model] || 1.0;
    const estimatedDuration = opts.estimatedDuration || DURATION_ESTIMATES[jobType] || 60;

    // Strip wrapper-only opts before passing to originalAgent
    const agentOpts = { ...opts };
    delete agentOpts.jobType;
    delete agentOpts.estimatedRam;
    delete agentOpts.estimatedDuration;

    // Dynamic import fleet-utils (avoids issues if module not available)
    let fleetUtils;
    try {
      fleetUtils = await import('./fleet-utils.js');
    } catch (e) {
      return originalAgent(prompt, agentOpts);
    }

    // Register with dispatcher (best-effort, silent fallback) -- Level 1
    let dispatch = null;
    try {
      dispatch = await fleetUtils.dispatchAgent(model, prompt.slice(0, 200), {
        jobType,
        estimatedRam,
        estimatedDuration,
      });
    } catch (e) {
      // Dispatcher unreachable - fall back to direct execution (L1)
      return originalAgent(prompt, agentOpts);
    }

    if (!dispatch) {
      // Dispatcher failed - fall back to direct execution (L1)
      return originalAgent(prompt, agentOpts);
    }

    // Phase 3: Remote execution
    if (remoteExecutionEnabled && executor) {
      return await remoteExecuteWithFallback(
        executor, dispatch, model, prompt, agentOpts, jobType,
        estimatedDuration, originalAgent, fleetUtils
      );
    }

    // Phase 2: Telemetry-only, local execution
    return await localExecuteWithTelemetry(
      dispatch, model, prompt, agentOpts, jobType, originalAgent, fleetUtils
    );
  };
}

/**
 * Phase 3: Execute remotely with full failure cascade
 * @private
 */
async function remoteExecuteWithFallback(
  executor, dispatch, model, prompt, agentOpts, jobType,
  estimatedDuration, originalAgent, fleetUtils
) {
  const server = (dispatch.server || dispatch.instance || '').replace(':9100', '');
  const timeoutMs = calculateTimeout(estimatedDuration);
  const startTime = Date.now();

  // Attempt 1: Execute on assigned server
  try {
    const result = await executor.execute(server, model, prompt, {
      jobId: dispatch.job_id,
      timeoutMs,
      schema: agentOpts.schema || null,
    });

    const duration = (Date.now() - startTime) / 1000;

    // Record successful remote completion
    fleetUtils.completeAgent(
      dispatch.job_id,
      dispatch.server || dispatch.instance,
      true,
      duration,
      jobType,
      dispatch.model || model,
      null
    ).catch(() => {});

    return result.result;

  } catch (primaryError) {
    const primaryDuration = (Date.now() - startTime) / 1000;

    // Level 2: SSH connection failure -> retry on alternate server
    if (primaryError.code === 'SSH_CONNECT_FAILED' || primaryError.code === 'EXECUTION_TIMEOUT') {
      // Report primary failure
      fleetUtils.completeAgent(
        dispatch.job_id,
        dispatch.server || dispatch.instance,
        false,
        primaryDuration,
        jobType,
        dispatch.model || model,
        primaryError.message
      ).catch(() => {});

      // Try alternate server (one retry)
      const alternateServer = await getAlternateServer(server);
      if (alternateServer) {
        try {
          const retryStart = Date.now();
          const result = await executor.execute(alternateServer, model, prompt, {
            jobId: `${dispatch.job_id}-retry`,
            timeoutMs,
            schema: agentOpts.schema || null,
          });

          const retryDuration = (Date.now() - retryStart) / 1000;

          // Record successful retry
          fleetUtils.completeAgent(
            dispatch.job_id,
            alternateServer,
            true,
            retryDuration,
            jobType,
            dispatch.model || model,
            null
          ).catch(() => {});

          return result.result;

        } catch (retryError) {
          // Retry also failed - fall through to local (L3)
          console.warn(`Fleet retry on ${alternateServer} also failed: ${retryError.message}`);
        }
      }
    }

    // Level 3/4/5: Fall back to local execution
    console.warn(`Fleet remote execution failed (${primaryError.code || 'UNKNOWN'}), falling back to local agent()`);

    // Record remote failure
    fleetUtils.completeAgent(
      dispatch.job_id,
      dispatch.server || dispatch.instance,
      false,
      primaryDuration,
      jobType,
      dispatch.model || model,
      primaryError.message
    ).catch(() => {});

    // Execute locally
    try {
      const localStart = Date.now();
      const result = await originalAgent(prompt, agentOpts);
      const localDuration = (Date.now() - localStart) / 1000;

      // Record local fallback completion
      fleetUtils.completeAgent(
        dispatch.job_id,
        'local-fallback',
        true,
        localDuration,
        jobType,
        model,
        null
      ).catch(() => {});

      return result;

    } catch (localError) {
      // Local also failed - propagate error
      throw localError;
    }
  }
}

/**
 * Phase 2: Local execution with telemetry recording
 * @private
 */
async function localExecuteWithTelemetry(
  dispatch, model, prompt, agentOpts, jobType, originalAgent, fleetUtils
) {
  const startTime = Date.now();
  try {
    const result = await originalAgent(prompt, agentOpts);
    const duration = (Date.now() - startTime) / 1000;

    // Record successful completion (fire-and-forget)
    fleetUtils.completeAgent(
      dispatch.job_id,
      dispatch.server || dispatch.instance,
      true,
      duration,
      jobType,
      dispatch.model || model
    ).catch(() => {
      // Silently ignore telemetry failures
    });

    return result;
  } catch (error) {
    const duration = (Date.now() - startTime) / 1000;

    // Record failed completion (fire-and-forget)
    fleetUtils.completeAgent(
      dispatch.job_id,
      dispatch.server || dispatch.instance,
      false,
      duration,
      jobType,
      dispatch.model || model,
      error.message
    ).catch(() => {
      // Silently ignore telemetry failures
    });

    // Re-throw original error - existing error handling continues to work
    throw error;
  }
}

export default {
  createFleetAgent,
};
