/**
 * Online Learning Integration for Workflow System
 *
 * Bridges JavaScript workflows with Python online learning system.
 * Provides real-time model selection and feedback updates.
 *
 * Usage:
 *   const { OnlineLearningClient } = require('./shared/online-learning-integration.js');
 *
 *   const learner = new OnlineLearningClient();
 *
 *   // Select best model for task
 *   const model = await learner.selectModel(taskDescription, metadata);
 *
 *   // Update based on outcome
 *   await learner.update(model, taskDescription, reward, outcome);
 */

import { exec, spawn } from 'child_process';
import { promisify } from 'util';
import fs from 'fs/promises';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PYTHON_SCRIPT = path.join(__dirname, 'online_learning_system.py');
const STATE_FILE = path.join(os.homedir(), '.claude', 'learning', 'online_learning_state.json');

class OnlineLearningClient {
  constructor(options = {}) {
    this.pythonPath = options.pythonPath || 'python3';
    this.timeout = options.timeout || 10000;
    this.cacheTimeout = options.cacheTimeout || 60000; // Cache for 1 minute
    this.stateCache = null;
    this.lastCacheTime = 0;
  }

  /**
   * Execute Python online learning script
   */
  async _executePython(method, args = []) {
    // Write args to temp file to avoid shell escaping issues
    const tmpFile = path.join(os.tmpdir(), `online-learning-${Date.now()}.json`);

    await fs.writeFile(tmpFile, JSON.stringify({ method, args }));

    const command = `${this.pythonPath} -c "
import sys
import json
import os
sys.path.insert(0, '${path.dirname(PYTHON_SCRIPT)}')
from online_learning_system import OnlineLearningOrchestrator

# Load args from temp file
with open('${tmpFile}', 'r') as f:
    data = json.load(f)
method = data['method']
args = data['args']

# Clean up temp file
os.remove('${tmpFile}')

# Load orchestrator
orchestrator = OnlineLearningOrchestrator.load('${STATE_FILE}')

# Execute method
if method == 'select_model':
    task_description = args[0]
    metadata = args[1] if len(args) > 1 else {}
    explore = args[2] if len(args) > 2 else True
    result = orchestrator.select_model(task_description, metadata, explore)
    print(json.dumps({'model': result}))

elif method == 'update':
    model = args[0]
    task_description = args[1]
    reward = args[2]
    metadata = args[3] if len(args) > 3 else {}
    loss = orchestrator.update(model, task_description, reward, metadata)
    orchestrator.save('${STATE_FILE}')
    print(json.dumps({'loss': float(loss)}))

elif method == 'get_statistics':
    stats = orchestrator.get_statistics()
    print(json.dumps(stats))

elif method == 'get_rankings':
    rankings = orchestrator.get_model_rankings()
    result = [{'model': model, 'score': float(score)} for model, score in rankings]
    print(json.dumps(result))

else:
    print(json.dumps({'error': f'Unknown method: {method}'}))
"`;

    try {
      const { stdout, stderr } = await execAsync(command, {
        timeout: this.timeout,
        maxBuffer: 10 * 1024 * 1024
      });

      if (stderr && stderr.length > 0) {
        console.warn('[OnlineLearning] Python stderr:', stderr.substring(0, 200));
      }

      // Find JSON output (last line usually)
      const lines = stdout.trim().split('\n');
      const jsonLine = lines[lines.length - 1];

      return JSON.parse(jsonLine);
    } catch (error) {
      console.error('[OnlineLearning] Python execution failed:', error.message);
      throw new Error(`Online learning failed: ${error.message}`);
    }
  }

  /**
   * Select best model for task using online learning
   *
   * @param {string} taskDescription - Task description text
   * @param {Object} metadata - Additional metadata (workflow, priority, etc.)
   * @param {boolean} explore - Whether to explore (true) or exploit (false)
   * @returns {Promise<string>} Selected model name
   */
  async selectModel(taskDescription, metadata = {}, explore = true) {
    try {
      const result = await this._executePython('select_model', [
        taskDescription,
        metadata,
        explore
      ]);

      return result.model;
    } catch (error) {
      console.error('[OnlineLearning] Model selection failed:', error.message);

      // Fallback to default model
      return 'sonnet';
    }
  }

  /**
   * Update online learning models based on observed reward
   *
   * @param {string} model - Model that was used
   * @param {string} taskDescription - Task description
   * @param {number} reward - Observed reward (0.0 to 1.0)
   * @param {Object} metadata - Additional metadata
   * @returns {Promise<number>} Training loss
   */
  async update(model, taskDescription, reward, metadata = {}) {
    try {
      const result = await this._executePython('update', [
        model,
        taskDescription,
        reward,
        metadata
      ]);

      return result.loss;
    } catch (error) {
      console.error('[OnlineLearning] Update failed:', error.message);
      return 0.0;
    }
  }

  /**
   * Get learning statistics
   *
   * @returns {Promise<Object>} Statistics object
   */
  async getStatistics() {
    try {
      return await this._executePython('get_statistics', []);
    } catch (error) {
      console.error('[OnlineLearning] Get statistics failed:', error.message);
      return {
        total_updates: 0,
        num_models: 0,
        best_model: 'unknown'
      };
    }
  }

  /**
   * Get model rankings by predicted reward
   *
   * @returns {Promise<Array>} Array of {model, score} objects
   */
  async getModelRankings() {
    try {
      return await this._executePython('get_rankings', []);
    } catch (error) {
      console.error('[OnlineLearning] Get rankings failed:', error.message);
      return [];
    }
  }

  /**
   * Load state from disk (fast, no Python execution)
   *
   * @returns {Promise<Object>} State object or null
   */
  async loadState() {
    const now = Date.now();

    // Return cached state if fresh
    if (this.stateCache && (now - this.lastCacheTime < this.cacheTimeout)) {
      return this.stateCache;
    }

    try {
      const data = await fs.readFile(STATE_FILE, 'utf8');
      this.stateCache = JSON.parse(data);
      this.lastCacheTime = now;
      return this.stateCache;
    } catch (error) {
      // State file doesn't exist yet
      return null;
    }
  }

  /**
   * Calculate reward from workflow outcome
   *
   * Converts workflow outcome data into reward signal (0.0 to 1.0)
   *
   * @param {Object} outcome - Workflow outcome data
   * @param {string} outcome.outcome - 'success', 'failed', or 'error'
   * @param {number} outcome.quality_score - Quality score (0.0 to 1.0)
   * @param {number} outcome.duration_ms - Duration in milliseconds
   * @param {Object} outcome.metadata - Additional metadata
   * @returns {number} Reward (0.0 to 1.0)
   */
  calculateReward(outcome) {
    let reward = 0.0;

    // Base reward from outcome
    if (outcome.outcome === 'success') {
      reward = 0.7; // Base success reward
    } else if (outcome.outcome === 'failed') {
      reward = 0.3; // Partial credit for trying
    } else if (outcome.outcome === 'error') {
      reward = 0.1; // Small reward for error (model at least tried)
    }

    // Adjust by quality score if available
    if (typeof outcome.quality_score === 'number') {
      reward = reward * 0.5 + outcome.quality_score * 0.5;
    }

    // Penalty for excessive duration (if timeout specified)
    if (outcome.timeout_ms && outcome.duration_ms) {
      const timeRatio = outcome.duration_ms / outcome.timeout_ms;
      if (timeRatio > 0.9) {
        reward *= 0.9; // 10% penalty for near-timeout
      }
    }

    // Bonus for high confidence
    if (outcome.metadata?.confidence && outcome.metadata.confidence > 0.8) {
      reward = Math.min(1.0, reward * 1.1);
    }

    return Math.max(0.0, Math.min(1.0, reward));
  }
}

/**
 * Workflow integration helper
 *
 * Wraps a workflow execution with online learning feedback
 */
class OnlineLearningWorkflow {
  constructor(learner = null) {
    this.learner = learner || new OnlineLearningClient();
    this.executionLog = [];
  }

  /**
   * Select worker models using online learning
   *
   * @param {string} taskDescription - Task description
   * @param {number} numWorkers - Number of workers to select
   * @param {Object} metadata - Task metadata
   * @returns {Promise<Array<string>>} Array of selected model names
   */
  async selectWorkers(taskDescription, numWorkers = 3, metadata = {}) {
    const workers = [];

    // Select diverse workers (mix exploration + exploitation)
    for (let i = 0; i < numWorkers; i++) {
      const explore = i < Math.floor(numWorkers * 0.4); // 40% exploration
      const model = await this.learner.selectModel(taskDescription, metadata, explore);

      // Avoid duplicates
      if (!workers.includes(model)) {
        workers.push(model);
      } else {
        // Try again with exploration
        const alternativeModel = await this.learner.selectModel(taskDescription, metadata, true);
        if (!workers.includes(alternativeModel)) {
          workers.push(alternativeModel);
        }
      }
    }

    return workers;
  }

  /**
   * Update online learning from worker results
   *
   * @param {string} taskDescription - Task description
   * @param {Array<Object>} workerResults - Worker results
   * @param {Object} arbiterDecision - Arbiter decision
   * @returns {Promise<void>}
   */
  async updateFromWorkers(taskDescription, workerResults, arbiterDecision) {
    for (const result of workerResults) {
      // Calculate reward
      const reward = this.learner.calculateReward({
        outcome: result.outcome || 'success',
        quality_score: result.quality_score || result.confidence || 0.7,
        duration_ms: result.duration_ms,
        metadata: {
          was_selected: result.model === arbiterDecision?.selected_model,
          confidence: result.confidence
        }
      });

      // Bonus if arbiter selected this model
      const finalReward = result.model === arbiterDecision?.selected_model
        ? Math.min(1.0, reward * 1.2)
        : reward;

      // Update online learner
      await this.learner.update(
        result.model,
        taskDescription,
        finalReward,
        {
          workflow: result.workflow,
          phase: result.phase,
          was_selected: result.model === arbiterDecision?.selected_model
        }
      );

      // Log
      this.executionLog.push({
        timestamp: new Date().toISOString(),
        model: result.model,
        task: taskDescription.substring(0, 100),
        reward: finalReward,
        was_selected: result.model === arbiterDecision?.selected_model
      });
    }
  }

  /**
   * Get execution log
   */
  getExecutionLog() {
    return this.executionLog;
  }

  /**
   * Get learning statistics
   */
  async getStatistics() {
    return await this.learner.getStatistics();
  }
}

export {
  OnlineLearningClient,
  OnlineLearningWorkflow
};
