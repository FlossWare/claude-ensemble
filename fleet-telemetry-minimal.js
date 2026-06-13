/**
 * Fleet Telemetry - Minimal Integration
 *
 * Lightweight telemetry layer for workflow agent() calls.
 * Zero external dependencies (only fetch + JSON).
 * Silent fallback when dispatcher unavailable.
 */

const DISPATCHER_URL = process.env.FLEET_DISPATCHER_URL || 'http://pi-02:3004';

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
export function inferJobType(opts) {
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
 * Dispatch agent to fleet (register job with dispatcher)
 */
export async function dispatchAgent(model, promptPreview, options = {}) {
  const { jobType = 'agent', estimatedRam = 1.0, estimatedDuration = 60 } = options;

  try {
    const response = await fetch(\`\${DISPATCHER_URL}/dispatch\`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: promptPreview,
        job_type: jobType,
        estimated_ram: estimatedRam,
        estimated_duration: estimatedDuration,
      }),
    });

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch (e) {
    return null;
  }
}

/**
 * Record agent completion
 */
export async function completeAgent(jobId, server, success, duration, jobType, model, error = null) {
  try {
    await fetch(\`\${DISPATCHER_URL}/complete\`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: jobId,
        server,
        success,
        duration,
        job_type: jobType,
        model,
        error,
      }),
    });
  } catch (e) {
    // Silent failure - telemetry is best-effort
  }
}

/**
 * Wrap agent function with telemetry
 */
export async function telemetryWrap(agentFn, options = {}) {
  if (process.env.FLEET_DISPATCHER === 'false') {
    return agentFn();
  }

  const model = options.model || 'sonnet';
  const jobType = options.jobType || 'agent';
  const estimatedRam = options.estimatedRam || RAM_ESTIMATES[model] || 1.0;
  const estimatedDuration = options.estimatedDuration || DURATION_ESTIMATES[jobType] || 60;

  const dispatch = await dispatchAgent(model, '', {
    jobType,
    estimatedRam,
    estimatedDuration,
  });

  if (!dispatch) {
    return agentFn();
  }

  const startTime = Date.now();
  try {
    const result = await agentFn();
    const duration = (Date.now() - startTime) / 1000;

    completeAgent(
      dispatch.job_id,
      dispatch.server || dispatch.instance,
      true,
      duration,
      jobType,
      dispatch.model || model
    ).catch(() => {});

    return result;
  } catch (error) {
    const duration = (Date.now() - startTime) / 1000;

    completeAgent(
      dispatch.job_id,
      dispatch.server || dispatch.instance,
      false,
      duration,
      jobType,
      dispatch.model || model,
      error.message
    ).catch(() => {});

    throw error;
  }
}

export default {
  inferJobType,
  dispatchAgent,
  completeAgent,
  telemetryWrap,
};
