/**
 * Model Usage Tracker
 *
 * Logs every model selection with:
 * - Which model was selected
 * - Why it was selected (task type, filter reason)
 * - When it was used
 * - What rules were applied
 *
 * Storage: PostgreSQL monitoring.model_usage table
 */

const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');

// Local fallback if PostgreSQL unavailable
const LOCAL_LOG = path.join(process.env.HOME, '.claude', 'learning', 'model-usage-log.jsonl');

// Singleton connection pool
const pool = new Pool({
  host: 'aio-01',
  port: 5433,
  user: 'claude',
  password: process.env.PGPASSWORD || 'claude',  // fallback for dev
  database: 'learning',
  max: 10,  // connection pool size
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
  statement_timeout: 5000,
});

/**
 * Log model selection
 * @param {Object} usage - Usage details
 * @param {string} usage.model - Model selected (e.g., 'opus', 'deepseek-coder')
 * @param {string} usage.taskType - Task type (e.g., 'redhat_code_review')
 * @param {string} usage.filterReason - Why this model was chosen
 * @param {Array<string>} usage.pool - All models in rotation pool
 * @param {string} usage.poolSource - How pool was determined
 * @param {Object} usage.rulesApplied - Filtering rules that were applied
 * @param {string} usage.workflow - Which workflow invoked the selection
 * @param {string} usage.context - Additional context
 */
async function logModelUsage(usage) {
  const timestamp = new Date().toISOString();

  const record = {
    timestamp,
    model: usage.model,
    task_type: usage.taskType || 'general',
    filter_reason: usage.filterReason || 'No specific rules',
    pool: usage.pool || [],
    pool_source: usage.poolSource || 'unknown',
    rules_applied: usage.rulesApplied || {},
    workflow: usage.workflow || 'unknown',
    context: usage.context || '',
    anthropic_only: usage.rulesApplied?.anthropic_only || false,
    whitelist: usage.rulesApplied?.whitelist || [],
    blacklist: usage.rulesApplied?.blacklist || [],
  };

  // Try PostgreSQL first
  try {
    await pool.query(`
      INSERT INTO monitoring.model_usage (
        timestamp, model, task_type, filter_reason, pool,
        pool_source, rules_applied, workflow, context,
        anthropic_only, whitelist, blacklist
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
    `, [
      timestamp,
      record.model,
      record.task_type,
      record.filter_reason,
      JSON.stringify(record.pool),
      record.pool_source,
      JSON.stringify(record.rules_applied),
      record.workflow,
      record.context,
      record.anthropic_only,
      JSON.stringify(record.whitelist),
      JSON.stringify(record.blacklist),
    ]);

    return { success: true, storage: 'postgresql' };

  } catch (pgError) {
    // Fallback to local JSONL file
    const logLine = JSON.stringify(record) + '\n';
    fs.appendFileSync(LOCAL_LOG, logLine);
    return { success: true, storage: 'local_file', error: pgError.message };
  }
}

/**
 * Get recent model usage
 * @param {Object} options
 * @param {number} options.limit - Number of records to return
 * @param {string} options.taskType - Filter by task type
 * @param {number} options.hours - Look back N hours
 * @returns {Array<Object>} - Usage records
 */
async function getRecentUsage(options = {}) {
  const limit = options.limit || 100;
  const taskType = options.taskType || null;
  const hours = options.hours || 24;

  try {
    const params = [];
    let query = `
      SELECT * FROM monitoring.model_usage
      WHERE timestamp > NOW() - INTERVAL $1 hours
    `;
    params.push(hours);

    if (taskType) {
      params.push(taskType);
      query += ` AND task_type = $${params.length}`;
    }

    params.push(limit);
    query += ` ORDER BY timestamp DESC LIMIT $${params.length}`;

    const result = await pool.query(query, params);

    return result.rows;

  } catch (pgError) {
    // Fallback to local file
    if (!fs.existsSync(LOCAL_LOG)) return [];

    const content = fs.readFileSync(LOCAL_LOG, 'utf8');
    const lines = content.trim().split('\n').filter(Boolean);
    const records = lines.map(line => JSON.parse(line));

    // Filter by time
    const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000);
    let filtered = records.filter(r => new Date(r.timestamp) > cutoff);

    // Filter by task type
    if (taskType) {
      filtered = filtered.filter(r => r.task_type === taskType);
    }

    return filtered.slice(-limit).reverse();
  }
}

/**
 * Get model usage statistics
 * @param {number} hours - Look back N hours
 * @returns {Object} - Statistics
 */
async function getUsageStats(hours = 24) {
  const usage = await getRecentUsage({ hours, limit: 10000 });

  const stats = {
    total: usage.length,
    by_model: {},
    by_task_type: {},
    anthropic_only_count: 0,
    filtered_count: 0,
    period_hours: hours,
    timestamp: new Date().toISOString(),
  };

  for (const record of usage) {
    // Count by model
    stats.by_model[record.model] = (stats.by_model[record.model] || 0) + 1;

    // Count by task type
    const taskType = record.task_type || 'general';
    stats.by_task_type[taskType] = (stats.by_task_type[taskType] || 0) + 1;

    // Count Anthropic-only enforcement
    if (record.anthropic_only) {
      stats.anthropic_only_count++;
    }

    // Count filtered selections
    if (record.whitelist?.length > 0 || record.blacklist?.length > 0) {
      stats.filtered_count++;
    }
  }

  // Calculate percentages
  stats.model_distribution = {};
  for (const [model, count] of Object.entries(stats.by_model)) {
    stats.model_distribution[model] = {
      count,
      percentage: ((count / stats.total) * 100).toFixed(1) + '%',
    };
  }

  return stats;
}

/**
 * Check for Red Hat compliance violations
 * @param {number} hours - Look back N hours
 * @returns {Array<Object>} - Violations (should be empty!)
 */
async function checkRedHatCompliance(hours = 24) {
  const usage = await getRecentUsage({ hours, limit: 10000 });

  const violations = usage.filter(record => {
    // Check if task is Red Hat work
    const isRedHatTask = record.task_type?.startsWith('redhat_');
    if (!isRedHatTask) return false;

    // Check if Anthropic model was used
    const anthropicModels = ['opus', 'sonnet', 'haiku', 'fable', 'claude'];
    const isAnthropicModel = anthropicModels.some(name =>
      record.model?.toLowerCase().includes(name)
    );

    // VIOLATION: Red Hat task used non-Anthropic model!
    return !isAnthropicModel;
  });

  return violations;
}

module.exports = {
  logModelUsage,
  getRecentUsage,
  getUsageStats,
  checkRedHatCompliance,
};
