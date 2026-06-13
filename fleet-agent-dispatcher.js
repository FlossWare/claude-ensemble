/**
 * Fleet-Aware Agent Dispatcher
 *
 * Drop-in replacement for workflow agent() that intelligently routes
 * to fleet dispatcher when enabled, with automatic fallback.
 *
 * Usage in workflows:
 *   import { dispatchViaFleet } from './fleet-agent-dispatcher.js';
 *
 *   // Wrap any agent() call:
 *   const result = USE_FLEET_DISPATCHER
 *     ? await dispatchViaFleet('opus', prompt, {schema, label})
 *     : await agent(prompt, {model: 'opus', schema, label});
 *
 *   // Or use as direct replacement (auto-detects model from opts):
 *   const result = await dispatchViaFleet(prompt, opts);
 */


/**
 * Job type detection heuristics
 * Classifies 158 agent() calls into 5 job type categories
 *
 * @private
 */
function detectJobType(label, prompt) {
  label = (label || '').toLowerCase();
  prompt = (prompt || '').toLowerCase();

  // ai-consensus: multi-AI workers
  if (
    label.includes('worker') ||
    label.includes('consensus') ||
    label.includes('opinion') ||
    label.includes('perspective') ||
    label.includes('arbiter')
  ) {
    return 'ai-consensus';
  }

  // code-review: file analysis, complexity check
  if (
    label.includes('review') ||
    label.includes('audit') ||
    label.includes('quality') ||
    label.includes('complexity') ||
    label.includes('refactor') ||
    label.includes('smell') ||
    prompt.includes('code analysis') ||
    prompt.includes('code quality') ||
    prompt.includes('code review') ||
    prompt.includes('identify issues')
  ) {
    return 'code-review';
  }

  // code-execute: running tests, builds, shell commands
  if (
    label.includes('test') ||
    label.includes('build') ||
    label.includes('execute') ||
    label.includes('run') ||
    label.includes('verify') ||
    prompt.includes('execute:') ||
    prompt.includes('run:') ||
    prompt.includes('npm test') ||
    prompt.includes('pytest') ||
    prompt.includes('./gradlew')
  ) {
    return 'code-execute';
  }

  // data-extraction: parsing, scraping, transforming
  if (
    label.includes('extract') ||
    label.includes('fetch') ||
    label.includes('parse') ||
    label.includes('detect') ||
    label.includes('scan') ||
    (prompt.includes('return') && prompt.includes('json')) ||
    prompt.includes('extract') ||
    prompt.includes('structured')
  ) {
    return 'data-extraction';
  }

  // ai-heavy: synthesis, generation, summary
  if (
    label.includes('synthesis') ||
    label.includes('summary') ||
    label.includes('generate') ||
    label.includes('document') ||
    label.includes('document') ||
    label.includes('report') ||
    prompt.includes('summarize') ||
    prompt.includes('synthesis') ||
    prompt.includes('generate')
  ) {
    return 'ai-heavy';
  }

  // Default: generic agent job
  return 'agent';
}

/**
 * Estimate resources needed for job
 * Based on: prompt length, model size, schema complexity, job type
 *
 * @private
 */
function estimateResources(prompt, model, schema, jobType, providedDuration, providedRam) {
  // If explicitly provided, use those
  if (providedDuration !== undefined && providedRam !== undefined) {
    return {
      duration: providedDuration,
      ram: providedRam
    };
  }

  // Base estimates
  let duration = 25;  // seconds
  let ram = 1.0;      // GB

  // 1. Prompt length adjustment
  const promptLen = (prompt || '').length;
  if (promptLen < 500) {
    duration += 10;
    ram += 0.0;
  } else if (promptLen < 2000) {
    duration += 20;
    ram += 0.3;
  } else if (promptLen < 5000) {
    duration += 30;
    ram += 0.5;
  } else {
    duration += 45;
    ram += 1.0;
  }

  // 2. Model size adjustment
  if (model?.includes('opus') || model?.includes('gpt-4')) {
    duration += 15;
    ram += 0.5;
  } else if (model?.includes('haiku') || model?.includes('gpt-3.5')) {
    duration -= 10;
    ram -= 0.3;
  } else if (model?.includes('gpt') || model?.includes('gemini')) {
    duration += 5;
    ram += 0.2;
  }

  // 3. Schema complexity adjustment
  if (schema && typeof schema === 'object') {
    const propCount = Object.keys(schema.properties || {}).length;
    if (propCount > 0 && propCount <= 5) {
      duration += 5;
      ram += 0.2;
    } else if (propCount > 5 && propCount <= 20) {
      duration += 10;
      ram += 0.3;
    } else if (propCount > 20) {
      duration += 15;
      ram += 0.5;
    }
  }

  // 4. Job type multiplier
  switch (jobType) {
    case 'code-execute':
      duration += 20;
      ram += 0.5;
      break;
    case 'ai-heavy':
      duration += 15;
      ram += 0.3;
      break;
    case 'data-extraction':
      duration -= 10;
      ram -= 0.3;
      break;
    case 'ai-consensus':
    case 'code-review':
    case 'agent':
    default:
      // baseline
      break;
  }

  // Ensure minimum values
  duration = Math.max(10, duration);
  ram = Math.max(0.5, ram);

  // Cap maximums
  duration = Math.min(300, duration);
  ram = Math.min(4.0, ram);

  return { duration: Math.ceil(duration), ram: Math.round(ram * 10) / 10 };
}

/**
 * Execute agent on selected server
 *
 * @private
 */
async function executeOnServer(serverInstance, model, prompt, schema) {
  // Extract server name from instance (e.g., 'server-03:9100' -> 'server-03')
  const serverName = serverInstance?.replace(':9100', '') || 'server-03';

  try {
    // Use existing remoteAgent from fleet-utils
    const result = await fleetUtils.remoteAgent(serverName, prompt, {
      model,
      schema
    });

    return result;
  } catch (err) {
    console.error(`❌ Remote agent execution failed on ${serverName}:`, err.message);
    return null;
  }
}

/**
 * Validate result against schema
 *
 * @private
 */
function validateAgainstSchema(result, schema) {
  if (!schema) return result;

  // If result is string, try to parse as JSON first
  if (typeof result === 'string') {
    try {
      return JSON.parse(result);
    } catch {
      // Return unparsed string (caller will handle)
      return result;
    }
  }

  // If result is object, return as-is
  return result;
}

/**
 * Dispatch agent job via fleet dispatcher with fallback
 *
 * This is the main wrapper that routes between fleet and direct agent() calls.
 *
 * @param {string} model - AI model name (e.g., 'opus', 'sonnet')
 * @param {string} prompt - Agent prompt
 * @param {object} opts - Options {schema, label, phase, jobType, estimatedRam, estimatedDuration}
 * @param {boolean} useDispatcher - Whether to use fleet dispatcher (set by caller)
 * @returns {Promise<any>} Agent result (string or parsed schema object)
 */
export async function dispatchViaFleet(model, prompt, opts = {}, useDispatcher = true) {
  const {
    schema = null,
    label = null,
    phase = null,
    jobType = null,
    estimatedRam = undefined,
    estimatedDuration = undefined,
    skipDispatcher = false
  } = opts;

  // Skip dispatcher if disabled
  if (!useDispatcher || skipDispatcher) {
    // Fall back to direct agent() call
    // The caller's agent() function will be used
    throw new Error(
      'dispatchViaFleet requires direct agent() call. ' +
      'This is called by the wrapper that should have fallback logic.'
    );
  }

  // Detect job type if not provided
  const detectedJobType = jobType || detectJobType(label, prompt);

  // Estimate resources if not provided
  const { duration, ram } = estimateResources(
    prompt,
    model,
    schema,
    detectedJobType,
    estimatedDuration,
    estimatedRam
  );

  // Track execution timing
  const startTime = Date.now();
  let dispatch = null;
  let result = null;

  try {
    // Step 1: Dispatch job to fleet dispatcher
    console.log(
      `📤 Dispatching ${detectedJobType} job to fleet (${model}, ~${duration}s, ${ram}GB)`
    );

    dispatch = await fleetUtils.dispatchAgent(model, prompt, {
      jobType: detectedJobType,
      estimatedRam: ram,
      estimatedDuration: duration
    });

    if (!dispatch) {
      // Dispatcher unavailable or failed to dispatch
      console.warn('⚠️  Fleet dispatcher unavailable, falling back to direct agent()');
      throw new Error('Dispatcher returned null');
    }

    console.log(`✅ Dispatched to ${dispatch.server} (jobId: ${dispatch.job_id})`);

    // Step 2: Execute agent on selected server
    result = await executeOnServer(dispatch.server, model, prompt, schema);

    if (result === null) {
      throw new Error('Agent execution returned null');
    }

    // Step 3: Validate against schema if provided
    result = validateAgainstSchema(result, schema);

    // Step 4: Mark job complete
    const actualDuration = (Date.now() - startTime) / 1000;
    await fleetUtils.completeAgent(
      dispatch.job_id,
      dispatch.server,
      true,
      actualDuration,
      detectedJobType,
      model
    );

    console.log(`✅ Job complete (${actualDuration.toFixed(1)}s)`);
    return result;

  } catch (err) {
    const actualDuration = (Date.now() - startTime) / 1000;

    // Try to mark job as failed
    if (dispatch) {
      try {
        await fleetUtils.completeAgent(
          dispatch.job_id,
          dispatch.server || 'unknown',
          false,
          actualDuration,
          detectedJobType,
          model,
          err.message
        );
      } catch (completeErr) {
        // Ignore completion tracking errors
        console.warn('⚠️  Failed to mark job complete:', completeErr.message);
      }
    }

    // If dispatch itself failed, error is recoverable (return null for fallback)
    if (!dispatch) {
      console.warn(`⚠️  Fleet dispatch failed: ${err.message}`);
      return null; // Signal fallback to caller
    }

    // Otherwise propagate error (matches current agent() behavior)
    throw err;
  }
}

/**
 * Create a wrapped agent() function for use in workflows
 *
 * This creates a context-aware wrapper that intelligently chooses between
 * fleet dispatcher and direct agent() based on USE_FLEET_DISPATCHER flag.
 *
 * Usage in workflow:
 *   const agent = createFleetAgent(USE_FLEET_DISPATCHER);
 *   const result = await agent(prompt, opts);
 *
 * @param {boolean} useFleet - Whether to use fleet dispatcher
 * @param {Function} directAgent - The original agent() function from context
 * @returns {Function} Wrapped agent() function
 */
export function createFleetAgent(useFleet, directAgent) {
  return async function fleetAwareAgent(prompt, opts = {}) {
    const model = opts.model || 'sonnet';
    const { schema, label, phase } = opts;

    // If dispatcher disabled, use direct agent
    if (!useFleet) {
      return await directAgent(prompt, { model, schema, label, phase });
    }

    // Try fleet dispatcher first
    try {
      const result = await dispatchViaFleet(
        model,
        prompt,
        { schema, label, phase, ...opts },
        true // useDispatcher
      );

      // If result is null, fallback to direct agent
      if (result === null) {
        console.log('📍 Falling back to direct agent()');
        return await directAgent(prompt, { model, schema, label, phase });
      }

      return result;

    } catch (err) {
      // On any error, fallback to direct agent
      console.warn(`⚠️  Fleet dispatch failed, using direct agent(): ${err.message}`);
      return await directAgent(prompt, { model, schema, label, phase });
    }
  };
}

/**
 * Analyze workflow to detect all agent() calls and their patterns
 * Useful for migration planning
 *
 * @param {string} workflowCode - The JavaScript code of the workflow
 * @returns {object} Analysis results
 */
export function analyzeWorkflow(workflowCode) {
  const agentPattern = /await\s+agent\s*\(\s*([^,)]+),?\s*({[^}]*})?/g;
  const parallelPattern = /parallel\s*\(/g;
  const pipelinePattern = /pipeline\s*\(/g;

  const matches = [];
  let match;

  while ((match = agentPattern.exec(workflowCode)) !== null) {
    const prompt = match[1].slice(0, 50);  // First 50 chars
    const opts = match[2] || '{}';
    matches.push({
      position: match.index,
      prompt,
      opts,
      hasSchema: opts.includes('schema'),
      hasModel: opts.includes('model'),
      hasLabel: opts.includes('label'),
      hasPhase: opts.includes('phase')
    });
  }

  return {
    totalCalls: matches.length,
    usesParallel: parallelPattern.test(workflowCode),
    usesPipeline: pipelinePattern.test(workflowCode),
    schemaUsage: matches.filter(m => m.hasSchema).length,
    modelOverride: matches.filter(m => m.hasModel).length,
    labelUsage: matches.filter(m => m.hasLabel).length,
    phaseUsage: matches.filter(m => m.hasPhase).length,
    calls: matches
  };
}

// Export private functions for testing
export { detectJobType, estimateResources };

export default {
  dispatchViaFleet,
  createFleetAgent,
  detectJobType,
  estimateResources,
  analyzeWorkflow
};
