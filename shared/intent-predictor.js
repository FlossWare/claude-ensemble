/**
 * User Intent Predictor - JavaScript Integration
 *
 * Provides intent prediction for workflow routing and optimization.
 */

import { execSync } from 'child_process';
import { existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const PREDICTOR_SCRIPT = join(
  homedir(),
  'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/predict_intent.py'
);

const MODEL_PATH = join(homedir(), '.claude/learning/intent_predictor.pkl');

/**
 * Check if intent predictor model is available
 */
export function isIntentPredictorAvailable() {
  return existsSync(MODEL_PATH) && existsSync(PREDICTOR_SCRIPT);
}

/**
 * Predict user intent from text
 *
 * @param {string} text - User input text
 * @param {number} threshold - Confidence threshold (0-1), default 0.3
 * @returns {Object} - { primary_intent, intents: [{name, confidence}] }
 */
export function predictIntent(text, threshold = 0.3) {
  if (!isIntentPredictorAvailable()) {
    return {
      primary_intent: 'unknown',
      intents: [],
      error: 'Intent predictor model not found. Run train_intent_predictor.py first.',
    };
  }

  try {
    const result = execSync(
      `python3 "${PREDICTOR_SCRIPT}" "${text.replace(/"/g, '\\"')}" --threshold ${threshold} --json`,
      { encoding: 'utf-8', maxBuffer: 1024 * 1024 }
    );

    return JSON.parse(result);
  } catch (error) {
    return {
      primary_intent: 'unknown',
      intents: [],
      error: error.message,
    };
  }
}

/**
 * Get intent-specific routing recommendations
 *
 * @param {string} intent - Primary intent
 * @returns {Object} - Routing configuration
 */
export function getIntentRouting(intent) {
  const routingMap = {
    code_generation: {
      suggested_models: ['deepseek-coder-java:finetuned', 'sonnet', 'haiku'],
      worker_count: 2,
      quality_threshold: 0.7,
      verification_required: true,
    },
    code_review: {
      suggested_models: ['opus', 'sonnet', 'fable'],
      worker_count: 3,
      quality_threshold: 0.8,
      verification_required: true,
    },
    research: {
      suggested_models: ['opus', 'gemini', 'sonnet'],
      worker_count: 4,
      quality_threshold: 0.75,
      verification_required: false,
    },
    system_ops: {
      suggested_models: ['haiku', 'sonnet'],
      worker_count: 2,
      quality_threshold: 0.7,
      verification_required: true,
    },
    debugging: {
      suggested_models: ['sonnet', 'opus', 'haiku'],
      worker_count: 3,
      quality_threshold: 0.75,
      verification_required: true,
    },
    data_analysis: {
      suggested_models: ['sonnet', 'opus'],
      worker_count: 2,
      quality_threshold: 0.7,
      verification_required: false,
    },
    documentation: {
      suggested_models: ['sonnet', 'haiku'],
      worker_count: 2,
      quality_threshold: 0.65,
      verification_required: false,
    },
    workflow_automation: {
      suggested_models: ['sonnet', 'opus'],
      worker_count: 4,
      quality_threshold: 0.75,
      verification_required: true,
    },
    learning: {
      suggested_models: ['phi-4-mini-routing:finetuned', 'sonnet'],
      worker_count: 2,
      quality_threshold: 0.7,
      verification_required: false,
    },
  };

  return routingMap[intent] || {
    suggested_models: ['sonnet', 'haiku'],
    worker_count: 2,
    quality_threshold: 0.7,
    verification_required: false,
  };
}

/**
 * Predict intent and get routing configuration
 *
 * @param {string} text - User input text
 * @param {number} threshold - Confidence threshold
 * @returns {Object} - { intent, confidence, routing }
 */
export function predictAndRoute(text, threshold = 0.3) {
  const prediction = predictIntent(text, threshold);

  if (prediction.error) {
    return { error: prediction.error };
  }

  const routing = getIntentRouting(prediction.primary_intent);

  return {
    intent: prediction.primary_intent,
    confidence: prediction.intents[0]?.confidence || 0,
    all_intents: prediction.intents,
    routing,
  };
}

/**
 * Example usage in workflows
 */
export function exampleUsage() {
  const userInput = "Write a Python script to analyze log files";

  const result = predictAndRoute(userInput);

  console.log('User Intent Analysis:');
  console.log('  Primary Intent:', result.intent);
  console.log('  Confidence:', (result.confidence * 100).toFixed(1) + '%');
  console.log('  Routing Config:', result.routing);

  return result;
}

// Test if run directly
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('Intent Predictor Integration Test\n');

  if (!isIntentPredictorAvailable()) {
    console.error('ERROR: Intent predictor not available');
    console.error('Run: python3 tools/train_intent_predictor.py');
    process.exit(1);
  }

  const testCases = [
    "Write a Python script to parse JSON logs",
    "Debug this code that's throwing an error",
    "Research the latest Kubernetes best practices",
    "Deploy the application to production",
    "Train a classifier on this dataset",
    "Create a workflow to process files in parallel",
    "Review this code for security issues",
    "Analyze performance metrics in PostgreSQL",
  ];

  for (const text of testCases) {
    const result = predictAndRoute(text);
    console.log(`\nInput: ${text}`);
    console.log(`Intent: ${result.intent} (${(result.confidence * 100).toFixed(1)}%)`);
    console.log(`Models: ${result.routing.suggested_models.join(', ')}`);
    console.log(`Workers: ${result.routing.worker_count}`);
  }
}
