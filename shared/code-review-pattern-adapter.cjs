/**
 * Code Review Pattern Extractor - JavaScript Adapter
 *
 * Provides JavaScript API to the Python code review pattern extractor.
 * Used by workflows to get model recommendations and predict issue likelihood.
 *
 * Usage:
 *   const { getTopReviewModels, predictIssues } = require('./shared/code-review-pattern-adapter.cjs');
 *
 *   const models = await getTopReviewModels(5);
 *   const prediction = await predictIssues({ files: 10, duration_ms: 5000 });
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const EXTRACTOR_SCRIPT = path.join(__dirname, '..', 'tools', 'code_review_pattern_extractor.py');
const MODEL_PATH = path.join(__dirname, '..', 'learning', 'code_review_pattern_extractor.pkl');

// Cache for model recommendations (refresh every 5 minutes)
const CACHE_TTL = 5 * 60 * 1000;
let modelCache = { data: null, timestamp: 0 };
let statsCache = { data: null, timestamp: 0 };

/**
 * Get top performing models for code review
 * @param {number} n - Number of top models to return (default: 5)
 * @returns {Promise<Array<{model: string, success_rate: string, avg_confidence: string, reviews: number}>>}
 */
async function getTopReviewModels(n = 5) {
  try {
    // Check cache
    const now = Date.now();
    if (modelCache.data && (now - modelCache.timestamp) < CACHE_TTL) {
      return modelCache.data.slice(0, n);
    }

    // Check if model exists
    if (!fs.existsSync(MODEL_PATH)) {
      console.warn('⚠️ Code review pattern model not found - train first with:');
      console.warn(`   python3 ${EXTRACTOR_SCRIPT} --window 90`);
      return getDefaultModels();
    }

    // Load model and get recommendations
    const cmd = `python3 -c "
import pickle
import json

with open('${MODEL_PATH}', 'rb') as f:
    model_data = pickle.load(f)

# Get top models
models = []
for model, stats in model_data['patterns']['model_performance'].items():
    if stats['reviews'] == 0:
        continue
    success_rate = stats['success'] / stats['reviews']
    score = success_rate * 0.7 + stats['avg_confidence'] * 0.3
    models.append({
        'model': model,
        'success_rate': f'{success_rate:.1%}',
        'avg_confidence': f'{stats['avg_confidence']:.2f}',
        'reviews': stats['reviews'],
        'score': score
    })

models.sort(key=lambda x: x['score'], reverse=True)
print(json.dumps(models[:${n}]))
"`;

    const output = execSync(cmd, { encoding: 'utf8', timeout: 30000 });
    return JSON.parse(output.trim());
  } catch (error) {
    console.warn(`⚠️ Failed to get top models: ${error.message}`);
    return getDefaultModels();
  }
}

/**
 * Predict likelihood of finding issues in a review task
 * @param {Object} taskFeatures - Task characteristics
 * @param {number} taskFeatures.duration_ms - Expected duration in milliseconds
 * @param {number} taskFeatures.input_tokens - Expected input tokens
 * @param {number} taskFeatures.output_tokens - Expected output tokens
 * @param {number} taskFeatures.files - Number of files to review
 * @param {number} taskFeatures.confidence - Model confidence (0-1)
 * @returns {Promise<{probability: number, message: string}>}
 */
async function predictIssues(taskFeatures) {
  try {
    // Check if model exists
    if (!fs.existsSync(MODEL_PATH)) {
      return {
        probability: 0.5,
        message: 'Model not trained - using default estimate'
      };
    }

    const features = {
      duration_ms: taskFeatures.duration_ms || 0,
      input_tokens: taskFeatures.input_tokens || 0,
      output_tokens: taskFeatures.output_tokens || 0,
      confidence: taskFeatures.confidence || 0.5,
      files_mentioned: taskFeatures.files || 0,
      categories: taskFeatures.categories || 0,
      severities: taskFeatures.severities || 0,
      outcome: taskFeatures.outcome || 'success',
      cost_usd: taskFeatures.cost_usd || 0
    };

    const cmd = `python3 -c "
import pickle
import numpy as np
import json

with open('${MODEL_PATH}', 'rb') as f:
    model_data = pickle.load(f)

features = ${JSON.stringify(Object.values(features))}
X = np.array([features])
X_scaled = model_data['scaler'].transform(X)

prob = model_data['issue_predictor'].predict_proba(X_scaled)[0][1]

if prob > 0.7:
    message = 'High likelihood of finding issues'
elif prob > 0.5:
    message = 'Moderate likelihood of finding issues'
else:
    message = 'Low likelihood of finding issues'

print(json.dumps({'probability': float(prob), 'message': message}))
"`;

    const output = execSync(cmd, { encoding: 'utf8', timeout: 30000 });
    return JSON.parse(output.trim());
  } catch (error) {
    console.warn(`⚠️ Failed to predict issues: ${error.message}`);
    return {
      probability: 0.5,
      message: 'Prediction failed - using default estimate'
    };
  }
}

/**
 * Get pattern statistics from trained model
 * @returns {Promise<Object>}
 */
async function getPatternStats() {
  try {
    // Check cache
    const now = Date.now();
    if (statsCache.data && (now - statsCache.timestamp) < CACHE_TTL) {
      return statsCache.data;
    }

    if (!fs.existsSync(MODEL_PATH)) {
      return getDefaultStats();
    }

    const cmd = `python3 -c "
import pickle
import json

with open('${MODEL_PATH}', 'rb') as f:
    model_data = pickle.load(f)

patterns = model_data['patterns']

# Convert Counter objects to dicts
stats = {
    'issue_categories': dict(patterns['issue_categories']),
    'severity_distribution': dict(patterns['severity_distribution']),
    'task_complexity': patterns['task_complexity'],
    'review_outcomes': dict(patterns['review_outcomes']),
    'trained_at': model_data['trained_at'],
    'version': model_data['version']
}

print(json.dumps(stats))
"`;

    const output = execSync(cmd, { encoding: 'utf8', timeout: 30000 });
    const stats = JSON.parse(output.trim());

    // Update cache
    statsCache = { data: stats, timestamp: now };

    return stats;
  } catch (error) {
    console.warn(`⚠️ Failed to get pattern stats: ${error.message}`);
    return getDefaultStats();
  }
}

/**
 * Retrain the model with latest workflow data
 * @param {number} windowDays - Number of days to analyze (default: 90)
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function retrainModel(windowDays = 90) {
  try {
    console.log(`🔄 Retraining code review pattern model (${windowDays} days)...`);

    const output = execSync(
      `python3 ${EXTRACTOR_SCRIPT} --window ${windowDays} --output ${MODEL_PATH}`,
      { encoding: 'utf8', timeout: 120000 }
    );

    console.log(output);

    return {
      success: true,
      message: 'Model retrained successfully'
    };
  } catch (error) {
    console.error(`❌ Model retraining failed: ${error.message}`);
    return {
      success: false,
      message: error.message
    };
  }
}

/**
 * Get recommended review strategy based on task characteristics
 * @param {Object} task - Task description
 * @param {number} task.files - Number of files to review
 * @param {string} task.type - Type of review ('bug', 'security', 'style', etc.)
 * @returns {Promise<Object>}
 */
async function getReviewStrategy(task) {
  const models = await getTopReviewModels(6);
  const prediction = await predictIssues({
    files: task.files || 0,
    duration_ms: (task.files || 0) * 1000, // Estimate 1s per file
  });

  // Strategy selection
  let strategy = 'base';
  let workers = models.slice(0, 3).map(m => m.model);
  let arbiter = models[0]?.model || 'opus';

  if (task.files > 50 || task.type === 'security') {
    strategy = 'maximum-coverage';
    workers = models.slice(0, 6).map(m => m.model);
  } else if (prediction.probability > 0.7) {
    strategy = 'quintuple-verification';
    workers = models.slice(0, 5).map(m => m.model);
  }

  return {
    strategy,
    workers,
    arbiter,
    prediction,
    top_models: models.slice(0, 3)
  };
}

/**
 * Default models when pattern extractor not available
 */
function getDefaultModels() {
  return [
    { model: 'opus', success_rate: '95.0%', avg_confidence: '0.90', reviews: 0 },
    { model: 'command-a-03-2025', success_rate: '85.0%', avg_confidence: '0.85', reviews: 0 },
    { model: 'sonnet', success_rate: '80.0%', avg_confidence: '0.80', reviews: 0 }
  ];
}

function getDefaultStats() {
  return {
    issue_categories: {},
    severity_distribution: {},
    task_complexity: { simple: 0, medium: 0, complex: 0 },
    review_outcomes: {},
    trained_at: 'never',
    version: '0.0.0'
  };
}

/**
 * Health check for pattern extractor system
 * @returns {Promise<{healthy: boolean, model_exists: boolean, trained_at: string}>}
 */
async function healthCheck() {
  const modelExists = fs.existsSync(MODEL_PATH);

  if (!modelExists) {
    return {
      healthy: false,
      model_exists: false,
      trained_at: 'never',
      message: 'Model not trained'
    };
  }

  try {
    const stats = await getPatternStats();

    return {
      healthy: true,
      model_exists: true,
      trained_at: stats.trained_at,
      version: stats.version,
      message: 'System healthy'
    };
  } catch (error) {
    return {
      healthy: false,
      model_exists: true,
      trained_at: 'unknown',
      message: `Health check failed: ${error.message}`
    };
  }
}

module.exports = {
  getTopReviewModels,
  predictIssues,
  getPatternStats,
  retrainModel,
  getReviewStrategy,
  healthCheck
};
