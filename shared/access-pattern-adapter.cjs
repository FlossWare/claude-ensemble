/**
 * Access Pattern Analyzer - JavaScript Adapter
 *
 * Provides JavaScript interface to the Python-trained access pattern analyzer.
 * Used in workflows to predict best models, resource usage, and failure risks.
 *
 * Usage:
 *   const { predictBestModel, getResourceEstimate, getFailureRisk } = require('./shared/access-pattern-adapter.cjs');
 *
 *   // Predict best models for a task
 *   const models = await predictBestModel("Fix memory leak in cache", 3);
 *   console.log(`Best model: ${models[0].model} (score: ${models[0].score})`);
 *
 *   // Get resource estimates
 *   const resources = await getResourceEstimate("opus");
 *   console.log(`Expected: ${resources.duration_ms}ms, $${resources.cost_usd}`);
 *
 *   // Check failure risk
 *   const risk = await getFailureRisk("opus", "Fix critical bug");
 *   console.log(`Failure risk: ${(risk * 100).toFixed(1)}%`);
 */

const { execSync } = require('child_process');
const { existsSync } = require('fs');
const path = require('path');
const os = require('os');

const ANALYZER_SCRIPT = path.join(__dirname, '../tools/use_access_pattern_analyzer.py');
const MODEL_PATH = path.join(os.homedir(), '.claude/learning/access_pattern_analyzer.pkl');

/**
 * Check if analyzer is trained and available
 * @returns {boolean}
 */
function isAnalyzerAvailable() {
  return existsSync(MODEL_PATH);
}

/**
 * Run the Python analyzer script with given arguments
 * @param {string[]} args - Command line arguments
 * @returns {string} - Script output
 */
function runAnalyzer(args) {
  if (!isAnalyzerAvailable()) {
    throw new Error('Access pattern analyzer not trained. Run: python3 tools/access_pattern_analyzer_trainer.py');
  }

  const cmd = ['python3', ANALYZER_SCRIPT, ...args];
  const result = execSync(cmd.join(' '), {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024, // 10MB buffer
    cwd: path.join(__dirname, '..')
  });

  return result;
}

/**
 * Parse prediction output from the analyzer
 * @param {string} output - Raw output from analyzer
 * @returns {Array<{model: string, score: number, duration_ms: number, cost_usd: number, risk: number}>}
 */
function parsePredictionOutput(output) {
  const lines = output.split('\n');
  const predictions = [];

  let inData = false;
  for (const line of lines) {
    // Skip header lines
    if (line.includes('Model') && line.includes('Score')) {
      inData = true;
      continue;
    }

    if (line.includes('---')) {
      continue;
    }

    if (inData && line.trim()) {
      // Stop at Task Features section
      if (line.includes('Task Features:')) {
        break;
      }

      // Use regex to extract fields more reliably
      // Format: model_name   score   duration   cost   risk
      const match = line.match(/^(.+?)\s+([\d.]+)\s+([\d.]+)ms\s+\$\s*([\d.]+)\s+([\d.]+)%/);
      if (match) {
        const model = match[1].trim();
        const score = parseFloat(match[2]);
        const duration_ms = parseFloat(match[3]);
        const cost_usd = parseFloat(match[4]);
        const risk = parseFloat(match[5]) / 100;

        predictions.push({
          model,
          score,
          duration_ms,
          cost_usd,
          risk
        });
      }
    }
  }

  return predictions;
}

/**
 * Predict best models for a task
 * @param {string} taskDescription - Description of the task
 * @param {number} topK - Number of top models to return (default: 3)
 * @returns {Promise<Array<{model: string, score: number, duration_ms: number, cost_usd: number, risk: number}>>}
 */
async function predictBestModel(taskDescription, topK = 3) {
  try {
    const output = runAnalyzer([`"${taskDescription}"`, '--top-k', topK.toString()]);
    return parsePredictionOutput(output);
  } catch (error) {
    console.error('Error predicting best model:', error.message);
    return [];
  }
}

/**
 * Get resource usage estimates for a model
 * Note: This uses prediction output for a sample task
 * @param {string} model - Model name
 * @param {string} sampleTask - Sample task to estimate (default: "Implement new feature")
 * @returns {Promise<{duration_ms: number, input_tokens: number, output_tokens: number, cost_usd: number}>}
 */
async function getResourceEstimate(model, sampleTask = "Implement new feature") {
  try {
    const predictions = await predictBestModel(sampleTask, 20);
    const modelPrediction = predictions.find(p => p.model === model);

    if (modelPrediction) {
      return {
        duration_ms: modelPrediction.duration_ms,
        cost_usd: modelPrediction.cost_usd,
        // These aren't in the output, so use estimates
        input_tokens: Math.round(modelPrediction.duration_ms / 5), // Rough estimate
        output_tokens: Math.round(modelPrediction.duration_ms / 10)
      };
    }

    // Default estimates if model not found
    return {
      duration_ms: 5000,
      input_tokens: 1000,
      output_tokens: 500,
      cost_usd: 0.01
    };
  } catch (error) {
    console.error('Error getting resource estimate:', error.message);
    return {
      duration_ms: 5000,
      input_tokens: 1000,
      output_tokens: 500,
      cost_usd: 0.01
    };
  }
}

/**
 * Get failure risk for a model on a specific task
 * @param {string} model - Model name
 * @param {string} taskDescription - Task description
 * @returns {Promise<number>} - Failure probability (0.0 - 1.0)
 */
async function getFailureRisk(model, taskDescription) {
  try {
    const predictions = await predictBestModel(taskDescription, 20);
    const modelPrediction = predictions.find(p => p.model === model);

    if (modelPrediction) {
      return modelPrediction.risk;
    }

    // Default risk if model not found
    return 0.1;
  } catch (error) {
    console.error('Error getting failure risk:', error.message);
    return 0.1;
  }
}

/**
 * Get analyzer statistics
 * @returns {Promise<Object>} - Statistics object
 */
async function getAnalyzerStats() {
  try {
    const output = runAnalyzer(['--stats']);
    const stats = {};

    const lines = output.split('\n');
    for (const line of lines) {
      if (line.includes(':') && !line.includes('===') && !line.includes('---')) {
        const [key, value] = line.split(':').map(s => s.trim());
        stats[key] = value;
      }
    }

    return stats;
  } catch (error) {
    console.error('Error getting analyzer stats:', error.message);
    return {};
  }
}

/**
 * Train or retrain the analyzer
 * @param {number} windowDays - Training window in days (default: 30)
 * @returns {Promise<boolean>} - Success status
 */
async function trainAnalyzer(windowDays = 30) {
  try {
    const trainerScript = path.join(__dirname, '../tools/access_pattern_analyzer_trainer.py');
    execSync(`python3 ${trainerScript} --window ${windowDays}`, {
      encoding: 'utf8',
      stdio: 'inherit',
      cwd: path.join(__dirname, '..')
    });
    return true;
  } catch (error) {
    console.error('Error training analyzer:', error.message);
    return false;
  }
}

/**
 * Recommend model for a task (simplified interface)
 * Returns the single best model with all its details
 * @param {string} taskDescription - Task description
 * @returns {Promise<{model: string, score: number, duration_ms: number, cost_usd: number, risk: number} | null>}
 */
async function recommendModel(taskDescription) {
  const predictions = await predictBestModel(taskDescription, 1);
  return predictions.length > 0 ? predictions[0] : null;
}

module.exports = {
  isAnalyzerAvailable,
  predictBestModel,
  getResourceEstimate,
  getFailureRisk,
  getAnalyzerStats,
  trainAnalyzer,
  recommendModel
};
