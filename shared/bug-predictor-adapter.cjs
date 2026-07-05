/**
 * Bug Predictor Adapter - JavaScript wrapper for Python bug predictor
 *
 * Provides easy integration with workflow orchestration scripts.
 * Uses the trained Random Forest model to predict bug likelihood.
 *
 * @module bug-predictor-adapter
 */

const { execSync } = require('child_process');
const { resolve } = require('path');
const { existsSync } = require('fs');

/**
 * Predict bug likelihood for a task
 *
 * @param {Object} options - Prediction options
 * @param {string} options.task - Task description
 * @param {string} [options.model] - Model to use (opus, sonnet, haiku, etc.)
 * @param {string} [options.workflow] - Workflow name
 * @param {string} [options.taskType] - Task type (security, refactor, test)
 * @returns {Promise<Object>} Prediction result
 *
 * @example
 * const { predictBugLikelihood } = require('./shared/bug-predictor-adapter');
 *
 * const result = await predictBugLikelihood({
 *   task: "Implement OAuth2 authentication",
 *   model: "haiku",
 *   workflow: "code"
 * });
 *
 * if (result.risk_category === 'CRITICAL') {
 *   // Use multi-model consensus
 *   await multiModelConsensus(task);
 * }
 */
async function predictBugLikelihood({ task, model, workflow, taskType }) {
  const scriptPath = resolve(__dirname, '../tools/use_bug_predictor.py');
  const modelPath = resolve(process.env.HOME, '.claude/learning/bug_predictor.pkl');

  // Check if model exists
  if (!existsSync(modelPath)) {
    throw new Error(
      `Bug predictor model not found at ${modelPath}. ` +
      `Run: python3 tools/bug_predictor.py to train the model.`
    );
  }

  // Build command
  let cmd = `python3 "${scriptPath}" "${task.replace(/"/g, '\\"')}" --json`;
  if (model) cmd += ` --model "${model}"`;
  if (workflow) cmd += ` --workflow "${workflow}"`;
  if (taskType) cmd += ` --task-type "${taskType}"`;

  try {
    const output = execSync(cmd, { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 });

    // Find JSON in output (skip loading message)
    const jsonMatch = output.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('No JSON output from bug predictor');
    }

    return JSON.parse(jsonMatch[0]);
  } catch (error) {
    console.error('Bug predictor failed:', error.message);

    // Return neutral prediction on error
    return {
      bug_probability: 0.5,
      risk_category: 'MEDIUM',
      prediction: 'UNKNOWN',
      top_risk_factors: [],
      features: {},
      error: error.message
    };
  }
}

/**
 * Get recommended model based on bug risk
 *
 * @param {number} bugProbability - Bug probability (0.0-1.0)
 * @returns {string} Recommended model (opus, sonnet, haiku)
 *
 * @example
 * const model = getRecommendedModel(result.bug_probability);
 * // Returns 'opus' for high risk, 'haiku' for low risk
 */
function getRecommendedModel(bugProbability) {
  if (bugProbability > 0.7) {
    return 'opus';  // Critical risk - use most capable model
  } else if (bugProbability > 0.4) {
    return 'sonnet';  // Medium/high risk - balanced model
  } else {
    return 'haiku';  // Low risk - fast and cheap
  }
}

/**
 * Check if multi-model consensus is recommended
 *
 * @param {number} bugProbability - Bug probability (0.0-1.0)
 * @returns {boolean} True if consensus recommended
 *
 * @example
 * if (shouldUseConsensus(result.bug_probability)) {
 *   await multiModelConsensus(task);
 * }
 */
function shouldUseConsensus(bugProbability) {
  return bugProbability > 0.6;
}

/**
 * Get task routing strategy based on bug prediction
 *
 * @param {Object} prediction - Prediction result from predictBugLikelihood
 * @returns {Object} Routing strategy
 *
 * @example
 * const strategy = getRoutingStrategy(result);
 * console.log(strategy);
 * // {
 * //   model: 'opus',
 * //   useConsensus: true,
 * //   requireReview: true,
 * //   requireTests: true,
 * //   estimatedCost: 0.50
 * // }
 */
function getRoutingStrategy(prediction) {
  const { bug_probability, risk_category } = prediction;

  const costs = {
    opus: 0.50,
    sonnet: 0.15,
    haiku: 0.04,
  };

  let strategy = {
    model: getRecommendedModel(bug_probability),
    useConsensus: shouldUseConsensus(bug_probability),
    requireReview: bug_probability > 0.4,
    requireTests: bug_probability > 0.5,
    riskCategory: risk_category,
    bugProbability: bug_probability,
  };

  // Estimate cost
  if (strategy.useConsensus) {
    // Consensus uses 3 models (typically opus, sonnet, haiku)
    strategy.estimatedCost = costs.opus + costs.sonnet + costs.haiku;
    strategy.modelCount = 3;
  } else {
    strategy.estimatedCost = costs[strategy.model];
    strategy.modelCount = 1;
  }

  return strategy;
}

/**
 * Format prediction for display
 *
 * @param {Object} prediction - Prediction result
 * @returns {string} Formatted summary
 */
function formatPrediction(prediction) {
  const { bug_probability, risk_category, top_risk_factors } = prediction;

  let output = `Bug Likelihood: ${(bug_probability * 100).toFixed(1)}% (${risk_category})\n`;

  if (top_risk_factors && top_risk_factors.length > 0) {
    output += `Top risks: ${top_risk_factors.slice(0, 3).map(f => f.feature).join(', ')}`;
  }

  return output;
}

/**
 * Example workflow integration
 */
async function exampleWorkflow() {
  const task = "Implement distributed transaction coordinator with rollback";

  // Predict bug likelihood
  const prediction = await predictBugLikelihood({
    task,
    model: 'haiku',
    workflow: 'code'
  });

  console.log('Prediction:', formatPrediction(prediction));

  // Get routing strategy
  const strategy = getRoutingStrategy(prediction);
  console.log('\nRouting Strategy:', strategy);

  // Route based on risk
  if (strategy.useConsensus) {
    console.log('→ Using multi-model consensus (high risk)');
    // await multiModelConsensus(task);
  } else if (strategy.requireReview) {
    console.log(`→ Using ${strategy.model} + code review`);
    // const output = await agent(task, { model: strategy.model });
    // await codeReview(output);
  } else {
    console.log(`→ Using ${strategy.model} (low risk)`);
    // await agent(task, { model: strategy.model });
  }

  console.log(`\nEstimated cost: $${strategy.estimatedCost.toFixed(2)}`);
}

// Export functions
module.exports = {
  predictBugLikelihood,
  getRecommendedModel,
  shouldUseConsensus,
  getRoutingStrategy,
  formatPrediction,
  exampleWorkflow,
};

// Run example if called directly
if (require.main === module) {
  exampleWorkflow().catch(console.error);
}
