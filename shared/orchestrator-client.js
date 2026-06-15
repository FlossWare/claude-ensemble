/**
 * Orchestrator Client
 *
 * Queries pi-02 orchestrator for model routing decisions
 */

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || 'http://pi-02:8888';

/**
 * Get 3 recommended models for multi-AI consensus
 *
 * @param {Object} options
 * @param {string} options.taskType - Type of task (code-review, general, reasoning, etc.)
 * @param {string} options.task - Description of the task
 * @param {number} options.maxCost - Max cost per model in USD
 * @param {boolean} options.preferLocal - Prefer local models (Red Hat compliance)
 * @returns {Promise<string[]>} Array of 3 model names
 */
export async function getConsensusModels(options = {}) {
  const {
    taskType = 'general',
    task = '',
    maxCost = 0.10,
    preferLocal = true
  } = options;

  try {
    // Query orchestrator for 3 diverse models
    const requests = [
      // Worker 1: Best for task type
      fetch(`${ORCHESTRATOR_URL}/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: taskType === 'code-review' ? 'opus' : 'general',
          task,
          taskType,
          constraints: { maxCost, preferLocal }
        })
      }),
      // Worker 2: Alternative perspective
      fetch(`${ORCHESTRATOR_URL}/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'sonnet',
          task,
          taskType,
          constraints: { maxCost, preferLocal }
        })
      }),
      // Worker 3: Fast/efficient model
      fetch(`${ORCHESTRATOR_URL}/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'haiku',
          task,
          taskType,
          constraints: { maxCost, preferLocal }
        })
      })
    ];

    const responses = await Promise.all(requests);
    const routings = await Promise.all(responses.map(r => r.json()));

    // Extract model names from routing responses
    const models = routings
      .filter(r => r.selectedModel && !r.error)
      .map(r => r.selectedModel);

    // Deduplicate if orchestrator returned same model multiple times
    const uniqueModels = [...new Set(models)];

    // If we got fewer than 3 unique models, fall back to defaults
    if (uniqueModels.length < 3) {
      console.warn(`[orchestrator-client] Only got ${uniqueModels.length} unique models, using defaults`);
      return ['opus', 'sonnet', 'haiku'].slice(0, 3 - uniqueModels.length).concat(uniqueModels);
    }

    return uniqueModels.slice(0, 3);
  } catch (error) {
    console.error(`[orchestrator-client] Failed to query orchestrator: ${error.message}`);
    // Fallback to hardcoded defaults
    return ['opus', 'sonnet', 'haiku'];
  }
}

/**
 * Get single best model for a task
 *
 * @param {Object} options
 * @param {string} options.taskType - Type of task
 * @param {string} options.task - Description of the task
 * @param {string} options.preferredModel - Preferred model or category
 * @param {number} options.maxCost - Max cost in USD
 * @param {boolean} options.preferLocal - Prefer local models
 * @returns {Promise<Object>} Routing decision with selectedModel, selectedHost, reasoning
 */
export async function routeTask(options = {}) {
  const {
    taskType = 'general',
    task = '',
    preferredModel = 'opus',
    maxCost = 0.10,
    preferLocal = true
  } = options;

  try {
    const response = await fetch(`${ORCHESTRATOR_URL}/route`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: preferredModel,
        task,
        taskType,
        constraints: { maxCost, preferLocal }
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`[orchestrator-client] Route failed: ${error.message}`);
    return {
      error: error.message,
      selectedModel: preferredModel,
      selectedHost: 'localhost',
      reasoning: 'Orchestrator unavailable, using fallback'
    };
  }
}

/**
 * Get fleet utilization stats
 *
 * @returns {Promise<Object>} Utilization by host
 */
export async function getUtilization() {
  try {
    const response = await fetch(`${ORCHESTRATOR_URL}/utilization`);
    return await response.json();
  } catch (error) {
    console.error(`[orchestrator-client] Utilization check failed: ${error.message}`);
    return { error: error.message };
  }
}

/**
 * Get available models
 *
 * @returns {Promise<Array>} List of available models
 */
export async function getModels() {
  try {
    const response = await fetch(`${ORCHESTRATOR_URL}/models`);
    const data = await response.json();
    return data.models || [];
  } catch (error) {
    console.error(`[orchestrator-client] Models list failed: ${error.message}`);
    return [];
  }
}

/**
 * Check orchestrator health
 *
 * @returns {Promise<Object>} Health status
 */
export async function checkHealth() {
  try {
    const response = await fetch(`${ORCHESTRATOR_URL}/health`);
    return await response.json();
  } catch (error) {
    return {
      status: 'unreachable',
      error: error.message
    };
  }
}
