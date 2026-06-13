/**
 * Fleet-Aware Agent Wrapper
 *
 * Factory that creates a fleet-aware wrapper around the original agent() function.
 * Phase 2: Telemetry only - registers jobs, executes locally, records completion.
 * Phase 3: Will add actual remote execution.
 *
 * Usage in workflows:
 *   import { createFleetAgent } from './fleet-agent-wrapper.js';
 *   const _originalAgent = agent;
 *   const agent = (process.env.FLEET_DISPATCHER !== 'false') ? createFleetAgent(_originalAgent) : _originalAgent;
 */


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
 * Create a fleet-aware agent wrapper
 *
 * @param {Function} originalAgent - The original workflow agent() function
 * @returns {Function} Wrapped agent function with fleet dispatcher integration
 */
export function createFleetAgent(originalAgent) {
  return async function wrappedAgent(prompt, opts = {}) {
    // Check if dispatcher is disabled
    if (process.env.FLEET_DISPATCHER === 'false') {
      return originalAgent(prompt, opts);
    }

    const model = opts.model || 'sonnet';
    const jobType = opts.jobType || inferJobType(opts);
    const estimatedRam = opts.estimatedRam || RAM_ESTIMATES[model] || 1.0;
    const estimatedDuration = opts.estimatedDuration || DURATION_ESTIMATES[jobType] || 60;

    // Strip wrapper-only opts before passing to originalAgent
    const agentOpts = { ...opts };
    delete agentOpts.jobType;
    delete agentOpts.estimatedRam;
    delete agentOpts.estimatedDuration;

    // Register with dispatcher (best-effort, silent fallback)
    let dispatch = null;
    try {
      dispatch = await fleetUtils.dispatchAgent(model, prompt.slice(0, 200), {
        jobType,
        estimatedRam,
        estimatedDuration,
      });
    } catch (e) {
      // Dispatcher unreachable - fall back to direct execution
      return originalAgent(prompt, agentOpts);
    }

    if (!dispatch) {
      // Dispatcher failed - fall back to direct execution
      return originalAgent(prompt, agentOpts);
    }

    // Execute locally (Phase 2: telemetry only, not remote execution)
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
  };
}

export default {
  createFleetAgent,
};
