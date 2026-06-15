/**
 * Get Consensus Models from Orchestrator
 *
 * Helper function for workflows to query orchestrator for optimal model selection.
 * Auto-detects Red Hat proprietary context and adjusts model count accordingly.
 */

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || 'http://pi-02:8888';

/**
 * Get models for multi-AI consensus via orchestrator
 *
 * @param {Object} options
 * @param {string} options.taskType - Type of task (code-review, general, etc.)
 * @param {string} options.task - Description of the task
 * @param {number} options.count - Number of models to select
 * @returns {Promise<string[]>} Array of model names
 */
export async function getConsensusModels(options = {}) {
  const {
    taskType = 'general',
    task = '',
    count = null  // Auto-determine based on context
  } = options;

  // Auto-detect Red Hat proprietary context
  const cwd = process.cwd() || '';
  const isRedHat = cwd.includes('/redhat/') || cwd.includes('/rh/');

  // Red Hat: 3 models (compliance), Non-proprietary: 6 models (quality)
  const modelCount = count || (isRedHat ? 3 : 6);

  try {
    // Query orchestrator Thompson Sampling endpoint
    const response = await fetch(`${ORCHESTRATOR_URL}/route-thompson`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        taskType,
        task,
        count: modelCount,
        constraints: {
          diversity: true,
          onlyAnthropic: isRedHat,  // Red Hat compliance
          maxCost: isRedHat ? 0.10 : 0.30
        }
      }),
      signal: AbortSignal.timeout(5000)  // 5s timeout
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const routing = await response.json();

    if (routing.models && Array.isArray(routing.models) && routing.models.length > 0) {
      log(`[orchestrator] Selected ${routing.models.length} models: ${routing.models.join(', ')}`);
      return routing.models;
    }

    throw new Error('No models returned from orchestrator');
  } catch (error) {
    // Graceful fallback if orchestrator unavailable
    log(`[orchestrator] Unavailable (${error.message}), using defaults`);

    if (isRedHat) {
      // Red Hat fallback: 3 Anthropic models
      return ['opus', 'sonnet', 'haiku'];
    } else {
      // Non-proprietary fallback: 6 diverse models
      return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
    }
  }
}

/**
 * Record feedback to orchestrator after task completion
 *
 * @param {string} model - Model that executed the task
 * @param {Object} feedback - Task outcome
 * @param {boolean} feedback.success - Task succeeded
 * @param {number} feedback.quality - Quality score 0-1
 * @param {number} feedback.cost - Cost in USD
 * @param {number} feedback.duration - Duration in ms
 * @param {string} feedback.taskType - Type of task
 */
export async function recordFeedback(model, feedback) {
  try {
    await fetch(`${ORCHESTRATOR_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, ...feedback }),
      signal: AbortSignal.timeout(3000)
    });
  } catch (error) {
    // Silent failure - don't block workflow if feedback fails
    log(`[orchestrator] Feedback failed: ${error.message}`);
  }
}
