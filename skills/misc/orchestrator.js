/**
 * Model Selection Orchestrator
 *
 * Consults the learning database to select the best model(s) for a given task
 * based on historical performance, confidence scores, and success rates.
 *
 * AI-DISCOVERED PATTERNS:
 * - Automatically applies insights from learning/discoveries.json
 * - Filters models based on task context (cost, schema, complexity)
 * - Biases selection toward optimal models for specific scenarios
 * - Examples: avoid opus for cost-sensitive tasks, skip fable for JSON output
 *
 * Selection strategies:
 * - 'greedy' (default): Select models with highest historical performance
 * - 'thompson': Thompson Sampling for exploration/exploitation balance
 *
 * Usage:
 *   import { selectModel, selectWorkers, getModelMetrics } from './orchestrator.js';
 *
 *   // Get single best model (greedy)
 *   const model = await selectModel('code-review', { count: 1 });
 *   // => 'opus'
 *
 *   // Thompson Sampling (balances exploration/exploitation)
 *   const model = await selectModel('code-review', { strategy: 'thompson' });
 *   // => 'fable' (explores uncertain models too)
 *
 *   // With discovery context (filters/biases applied automatically)
 *   const model = await selectModel('api-generation', {
 *     strategy: 'thompson',
 *     requires_schema: true,
 *     cost_sensitivity: 'high'
 *   });
 *   // => 'sonnet' (fable filtered due to schema, opus filtered due to cost)
 *
 *   // Get multiple models ranked by performance
 *   const workers = await selectWorkers('multi-model-consensus', { count: 4 });
 *   // => ['opus', 'sonnet', 'haiku', 'fable']
 *
 *   // Get detailed metrics for a model
 *   const metrics = await getModelMetrics('opus', 'code-review');
 *   // => { avg_quality: 0.92, avg_confidence: 0.88, success_rate: 0.96, ... }
 */

import { getDb } from './shared/learning-logger.js';
import { hotImport } from './shared/hot-reload.js';

// Hot-reload thompson sampling for live updates
let thompson = null;
async function getThompson() {
  if (!thompson) {
    thompson = await hotImport('./learning/thompson-sampling.js');
  }
  return thompson;
}

// Hot-reload discovery application for live updates
let discoveries = null;
async function getDiscoveries() {
  if (!discoveries) {
    discoveries = await hotImport('./learning/apply-discoveries.js');
  }
  return discoveries;
}

// Hot-reload session manager for live updates
let sessionManager = null;
async function getSessionManager() {
  if (!sessionManager) {
    const module = await hotImport('./learning/session-manager.js');
    sessionManager = module.getSessionManager();
  }
  return sessionManager;
}

const DEFAULT_MODELS = ['opus', 'sonnet', 'haiku', 'fable', 'gpt-4o', 'gemini'];

// Track auto-registration state (one-time per session)
let autoRegistrationAttempted = false;

/**
 * Get metrics for a model on a specific task type
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type (code-review, multi-model-consensus, etc.)
 * @param {number} days - Look back N days (default: 30)
 * @returns {Promise<Object>} Metrics including success_rate, avg_quality, avg_confidence
 */
export async function getModelMetrics(model, taskType, days = 30) {
  const db = getDb();
  if (!db) return null;

  try {
    const query = `
      SELECT
        COUNT(*) as executions,
        SUM(CASE WHEN quality_score > 0.5 THEN 1 ELSE 0 END) as successes,
        AVG(quality_score) as avg_quality,
        AVG(confidence) as avg_confidence,
        AVG(duration_ms) as avg_duration,
        AVG(CAST(cost_usd as REAL)) as avg_cost,
        MAX(quality_score) as max_quality,
        MIN(quality_score) as min_quality
      FROM executions
      WHERE
        model = ?
        AND task_type = ?
        AND created_at > datetime('now', '-' || ? || ' days')
        AND created_at > datetime('now', '-90 days') /* Keep at least some history */
    `;

    const stmt = db.prepare(query);
    const metrics = stmt.get(model, taskType, days);

    if (!metrics || metrics.executions === 0) {
      return {
        model,
        task_type: taskType,
        executions: 0,
        success_rate: 0.5, // Default to neutral
        avg_quality: 0.5,
        avg_confidence: 0.5,
        avg_duration: 0,
        avg_cost: 0,
        available: false, // No data yet
      };
    }

    return {
      model,
      task_type: taskType,
      executions: metrics.executions,
      success_rate: metrics.successes / metrics.executions,
      avg_quality: metrics.avg_quality || 0.5,
      avg_confidence: metrics.avg_confidence || 0.5,
      avg_duration: metrics.avg_duration || 0,
      avg_cost: metrics.avg_cost || 0,
      max_quality: metrics.max_quality || 0,
      min_quality: metrics.min_quality || 0,
      available: true,
    };
  } catch (e) {
    console.warn(`Error querying model metrics: ${e.message}`);
    return null;
  }
}

/**
 * Calculate a score for model selection based on multiple factors
 *
 * @param {Object} metrics - Metrics from getModelMetrics
 * @param {Object} options - Scoring options
 * @returns {number} Score 0-100, higher is better
 */
function calculateScore(metrics, options = {}) {
  if (!metrics || !metrics.available) {
    return 50; // Default score for unknown models
  }

  const {
    qualityWeight = 0.4,      // 40% based on quality
    confidenceWeight = 0.3,   // 30% based on confidence
    successRateWeight = 0.2,  // 20% based on success rate
    costWeight = 0.1,         // 10% based on cost (lower is better)
  } = options;

  const successRate = metrics.success_rate || 0.5;
  const avgQuality = metrics.avg_quality || 0.5;
  const avgConfidence = metrics.avg_confidence || 0.5;

  // Cost scoring: penalize expensive models
  let costScore = 1.0;
  if (metrics.avg_cost > 0.01) {
    costScore = Math.max(0, 1 - metrics.avg_cost / 0.01);
  }

  const score =
    (avgQuality * qualityWeight +
     avgConfidence * confidenceWeight +
     successRate * successRateWeight +
     costScore * costWeight) * 100;

  return Math.round(score);
}

/**
 * Select the best model for a task type
 *
 * @param {string} taskType - Task type
 * @param {Object} options - Selection options
 * @param {number} options.count - Number of models to return (default: 1)
 * @param {number} options.days - Look back N days (default: 30)
 * @param {string[]} options.models - Models to consider (default: all)
 * @param {number} options.minExecutions - Minimum executions to consider (default: 3)
 * @param {string} options.strategy - Selection strategy: 'greedy' (default) or 'thompson'
 * @param {string} options.cost_sensitivity - Cost sensitivity: 'low', 'medium', 'high'
 * @param {boolean} options.requires_schema - Task requires structured output (JSON, schema)
 * @param {string} options.output_format - Output format: 'json', 'text', etc.
 * @param {boolean} options.budget_constraint - Task has budget constraints
 * @param {number} options.quality_threshold - Minimum quality threshold (0-1)
 * @param {string} options.complexity - Task complexity: 'low', 'medium', 'high'
 * @param {string} options.workflow - Workflow type: 'consensus', 'single', etc.
 * @returns {Promise<string|string[]>} Best model name, or array if count > 1
 */
export async function selectModel(taskType, options = {}) {
  // Auto-register session on first call
  if (!autoRegistrationAttempted && process.env.CLAUDE_CODE_SESSION_ID) {
    autoRegistrationAttempted = true;
    registerSession({
      sessionId: process.env.CLAUDE_CODE_SESSION_ID,
      pid: process.pid,
      capabilities: { task: taskType || 'auto-detected' },
    }).catch(err => {
      // Silent fail - don't break orchestrator if registration fails
    });
  }

  // Auto-heartbeat after registration
  if (process.env.CLAUDE_CODE_SESSION_ID) {
    heartbeat(process.env.CLAUDE_CODE_SESSION_ID).catch(() => {});
  }

  const {
    count = 1,
    days = 30,
    models = DEFAULT_MODELS,
    minExecutions = 3,
    strategy = 'greedy',
  } = options;

  try {
    // Apply discoveries BEFORE model selection
    const context = {
      task_type: taskType,
      cost_sensitivity: options.cost_sensitivity,
      requires_schema: options.requires_schema,
      output_format: options.output_format,
      budget_constraint: options.budget_constraint,
      quality_threshold: options.quality_threshold,
      complexity: options.complexity,
      workflow: options.workflow,
      worker_count: count,
    };

    const disc = await getDiscoveries();
    const config = await disc.applyDiscoveries(models, context);

    // Use filtered models and biases from discoveries
    const filteredModels = config.models;
    const biases = config.biases;

    // Thompson Sampling strategy
    if (strategy === 'thompson') {
      const ts = await getThompson();

      if (count === 1) {
        // Single model selection via Thompson Sampling
        // TODO: Apply biases to Thompson sampling (requires enhancement to thompson-sampling.js)
        const selected = ts.selectModel(filteredModels);
        return selected;
      } else {
        // Multiple models: sample repeatedly without replacement
        const selected = [];
        const remaining = [...filteredModels];
        for (let i = 0; i < count && remaining.length > 0; i++) {
          const model = ts.selectModel(remaining);
          selected.push(model);
          // Remove selected model from remaining pool
          const idx = remaining.indexOf(model);
          if (idx >= 0) remaining.splice(idx, 1);
        }
        return selected;
      }
    }

    // Greedy strategy (original behavior)
    // Fetch metrics for filtered models
    const allMetrics = await Promise.all(
      filteredModels.map(m => getModelMetrics(m, taskType, days))
    );

    // Score and sort by performance
    const scored = allMetrics
      .filter(m => m && m.executions >= minExecutions) // Only models with enough data
      .map(m => ({
        model: m.model,
        score: calculateScore(m, options),
        metrics: m,
      }))
      .sort((a, b) => b.score - a.score);

    // Fallback: if no models have enough executions, score all
    if (scored.length === 0) {
      const fallback = allMetrics
        .filter(m => m)
        .map(m => ({
          model: m.model,
          score: calculateScore(m, options),
          metrics: m,
        }))
        .sort((a, b) => b.score - a.score);

      return count === 1 ? fallback[0]?.model || 'sonnet' : fallback.slice(0, count).map(s => s.model);
    }

    // Return top N
    const top = scored.slice(0, count);
    return count === 1 ? top[0]?.model || 'sonnet' : top.map(s => s.model);
  } catch (e) {
    console.warn(`Error selecting model: ${e.message}`);
    return count === 1 ? 'sonnet' : ['opus', 'sonnet', 'haiku'];
  }
}

/**
 * Select multiple workers for consensus
 *
 * @param {string} taskType - Task type
 * @param {Object} options - Selection options (same as selectModel)
 * @returns {Promise<string[]>} Array of model names, best first
 */
export async function selectWorkers(taskType, options = {}) {
  // Auto-register session on first call
  if (!autoRegistrationAttempted && process.env.CLAUDE_CODE_SESSION_ID) {
    autoRegistrationAttempted = true;
    registerSession({
      sessionId: process.env.CLAUDE_CODE_SESSION_ID,
      pid: process.pid,
      capabilities: { task: taskType || 'auto-detected' },
    }).catch(err => {
      // Silent fail - don't break orchestrator if registration fails
    });
  }

  // Auto-heartbeat after registration
  if (process.env.CLAUDE_CODE_SESSION_ID) {
    heartbeat(process.env.CLAUDE_CODE_SESSION_ID).catch(() => {});
  }

  return selectModel(taskType, { ...options, count: options.count || 4 });
}

/**
 * Get performance comparison across models
 *
 * @param {string} taskType - Task type
 * @param {Object} options - Options (days, models)
 * @returns {Promise<Object[]>} Array of metrics sorted by score
 */
export async function compareModels(taskType, options = {}) {
  const {
    days = 30,
    models = DEFAULT_MODELS,
  } = options;

  try {
    const allMetrics = await Promise.all(
      models.map(m => getModelMetrics(m, taskType, days))
    );

    return allMetrics
      .filter(m => m)
      .map(m => ({
        ...m,
        score: calculateScore(m, options),
      }))
      .sort((a, b) => b.score - a.score);
  } catch (e) {
    console.warn(`Error comparing models: ${e.message}`);
    return [];
  }
}

/**
 * Get historical trend for a model
 *
 * @param {string} model - Model name
 * @param {string} taskType - Task type
 * @param {number} days - Look back N days
 * @returns {Promise<Object[]>} Array of daily metrics
 */
export async function getModelTrend(model, taskType, days = 30) {
  const db = getDb();
  if (!db) return [];

  try {
    const query = `
      SELECT
        DATE(created_at) as date,
        COUNT(*) as executions,
        AVG(quality_score) as avg_quality,
        AVG(confidence) as avg_confidence,
        SUM(CASE WHEN quality_score > 0.5 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
      FROM executions
      WHERE
        model = ?
        AND task_type = ?
        AND created_at > datetime('now', '-' || ? || ' days')
      GROUP BY DATE(created_at)
      ORDER BY date DESC
    `;

    const stmt = db.prepare(query);
    return stmt.all(model, taskType, days);
  } catch (e) {
    console.warn(`Error fetching trend data: ${e.message}`);
    return [];
  }
}

/**
 * Record a model selection result for Thompson Sampling learning.
 *
 * Call this after executing with a model selected via strategy='thompson'
 * to update the bandit state with the observed quality score.
 *
 * @param {string} model - Model that was used
 * @param {number} qualityScore - Quality score (0-1)
 * @param {object} options - Recording options
 * @param {string[]} options.appliedDiscoveries - IDs of discoveries that were applied
 * @param {object} options.context - Execution context
 * @returns {Object} Updated model state
 */
export async function recordResult(model, qualityScore, options = {}) {
  try {
    const ts = await getThompson();
    const result = ts.updateModel(model, qualityScore);

    // Record evidence for applied discoveries (async, don't wait)
    if (options.appliedDiscoveries && options.appliedDiscoveries.length > 0) {
      _recordDiscoveryEvidence(options.appliedDiscoveries, qualityScore, options.context).catch(err => {
        if (process.env.LEARNING_DEBUG) {
          console.error(`[orchestrator] Discovery evidence tracking failed: ${err.message}`);
        }
      });
    }

    return result;
  } catch (e) {
    console.warn(`Error recording result: ${e.message}`);
    return null;
  }
}

/**
 * Record evidence for discoveries (internal helper)
 */
async function _recordDiscoveryEvidence(discoveryIds, qualityScore, context) {
  try {
    const { default: updateMetadata } = await import('./learning/update-discovery-metadata.js');

    const outcome = {
      qualityScore,
      success: qualityScore >= 0.7,
      context,
    };

    for (const discoveryId of discoveryIds) {
      await updateMetadata.recordDiscoveryEvidence(discoveryId, outcome);
    }
  } catch (err) {
    // Ignore tracking errors
  }
}

/**
 * Get Thompson Sampling statistics for all models.
 *
 * @returns {Object[]} Array of model statistics
 */
export async function getThompsonStats() {
  try {
    const ts = await getThompson();
    return ts.getAllModelStats();
  } catch (e) {
    console.warn(`Error fetching Thompson stats: ${e.message}`);
    return [];
  }
}

// ============================================================================
// CROSS-SESSION COMMUNICATION
// ============================================================================

/**
 * Register this session with the orchestrator
 *
 * @param {Object} options - Session options
 * @param {string[]} options.capabilities - Model capabilities
 * @param {string} options.taskType - Current task type
 * @param {Object} options.metadata - Additional metadata
 * @returns {Promise<string>} Session ID
 */
export async function registerSession(options = {}) {
  try {
    const manager = await getSessionManager();
    return await manager.registerSession(options);
  } catch (err) {
    console.warn(`Error registering session: ${err.message}`);
    return null;
  }
}

/**
 * Send message to another session or broadcast
 *
 * @param {string} to - Target session ID or 'broadcast'
 * @param {Object} message - Message object
 * @param {string} message.type - Message type (discovery, insight, request, response, coordination)
 * @param {Object} message.data - Message data
 * @returns {Promise<string>} Message ID
 */
export async function sendMessage(to, message) {
  try {
    const manager = await getSessionManager();
    return await manager.sendMessage(to, message);
  } catch (err) {
    console.warn(`Error sending message: ${err.message}`);
    return null;
  }
}

/**
 * Broadcast message to all sessions
 *
 * @param {Object} message - Message object
 * @returns {Promise<string>} Message ID
 */
export async function broadcast(message) {
  try {
    const manager = await getSessionManager();
    return await manager.broadcast(message);
  } catch (err) {
    console.warn(`Error broadcasting message: ${err.message}`);
    return null;
  }
}

/**
 * Get messages for this session
 *
 * @returns {Promise<Object[]>} Array of messages
 */
export async function getMessages() {
  try {
    const manager = await getSessionManager();
    return await manager.getMessages();
  } catch (err) {
    console.warn(`Error getting messages: ${err.message}`);
    return [];
  }
}

/**
 * Update heartbeat for this session
 *
 * @returns {Promise<void>}
 */
export async function heartbeat() {
  try {
    const manager = await getSessionManager();
    await manager.heartbeat();
  } catch (err) {
    // Silent fail - heartbeat is best-effort
  }
}

/**
 * Get all active sessions
 *
 * @returns {Promise<Object[]>} Array of active sessions
 */
export async function getActiveSessions() {
  try {
    const manager = await getSessionManager();
    return await manager.getActiveSessions();
  } catch (err) {
    console.warn(`Error getting active sessions: ${err.message}`);
    return [];
  }
}

/**
 * Register message handler
 *
 * @param {string} type - Message type
 * @param {Function} handler - Handler function (async)
 */
export async function onMessage(type, handler) {
  try {
    const manager = await getSessionManager();
    manager.onMessage(type, handler);
  } catch (err) {
    console.warn(`Error registering message handler: ${err.message}`);
  }
}

/**
 * Initialize session manager (auto-start heartbeat + polling)
 *
 * @param {Object} options - Session options
 * @returns {Promise<string>} Session ID
 */
export async function initSession(options = {}) {
  try {
    const module = await hotImport('./learning/session-manager.js');
    const manager = await module.initSessionManager(options);
    sessionManager = manager; // Cache for hot-reload
    return manager.sessionId;
  } catch (err) {
    console.warn(`Error initializing session: ${err.message}`);
    return null;
  }
}

/**
 * Get session statistics
 *
 * @returns {Promise<Object>} Session stats
 */
export async function getSessionStats() {
  try {
    const manager = await getSessionManager();
    return await manager.getStats();
  } catch (err) {
    console.warn(`Error getting session stats: ${err.message}`);
    return null;
  }
}

export default {
  selectModel,
  selectWorkers,
  getModelMetrics,
  compareModels,
  getModelTrend,
  recordResult,
  getThompsonStats,
  // Cross-session communication
  registerSession,
  sendMessage,
  broadcast,
  getMessages,
  heartbeat,
  getActiveSessions,
  onMessage,
  initSession,
  getSessionStats,
};
