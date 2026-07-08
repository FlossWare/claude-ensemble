/**
 * Model Usage Tracker - REST API Client
 *
 * Logs every model selection to centralized API (aio-01:5000)
 * NO direct database access - all workers call the API
 *
 * Logs:
 * - Which model was selected
 * - Why it was selected (task type, filter reason)
 * - When it was used
 * - What rules were applied
 *
 * Storage: REST API → PostgreSQL monitoring.model_usage table
 */

const fs = require('fs');
const path = require('path');
const http = require('http');

// API endpoint
const API_HOST = process.env.ORCHESTRATOR_API_HOST || 'aio-01';
const API_PORT = process.env.ORCHESTRATOR_API_PORT || 5000;
const API_BASE = `http://${API_HOST}:${API_PORT}/api`;

// Local fallback if API unavailable
const LOCAL_LOG = path.join(process.env.HOME, '.claude', 'learning', 'model-usage-log.jsonl');

/**
 * Make HTTP request to API
 */
function apiRequest(method, path, data = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: API_HOST,
      port: API_PORT,
      path: `/api${path}`,
      method: method,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 5000,
    };

    const req = http.request(options, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(body));
          } catch (parseError) {
            resolve({ success: true });
          }
        } else {
          reject(new Error(`API error: ${res.statusCode} ${body}`));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('API request timeout'));
    });

    if (data) {
      req.write(JSON.stringify(data));
    }
    req.end();
  });
}

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
  const record = {
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

  // Try API first
  try {
    await apiRequest('POST', '/model-usage', record);
    return { success: true, storage: 'api' };
  } catch (apiError) {
    // Fallback to local JSONL file
    const logLine = JSON.stringify({ timestamp: new Date().toISOString(), ...record }) + '\n';
    fs.appendFileSync(LOCAL_LOG, logLine);
    return { success: true, storage: 'local_file', error: apiError.message };
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
    const params = new URLSearchParams({ hours, limit });
    if (taskType) params.append('task_type', taskType);

    const result = await apiRequest('GET', `/model-usage/recent?${params}`);
    return result.usage || [];
  } catch (apiError) {
    // Fallback to local file
    if (!fs.existsSync(LOCAL_LOG)) return [];

    const content = fs.readFileSync(LOCAL_LOG, 'utf8');
    const lines = content.trim().split('\n').filter(Boolean);
    const records = lines.map(line => JSON.parse(line));

    const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000);
    let filtered = records.filter(r => new Date(r.timestamp) > cutoff);

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
  try {
    return await apiRequest('GET', `/model-usage/stats?hours=${hours}`);
  } catch (apiError) {
    // Fallback to local computation
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
      stats.by_model[record.model] = (stats.by_model[record.model] || 0) + 1;
      const taskType = record.task_type || 'general';
      stats.by_task_type[taskType] = (stats.by_task_type[taskType] || 0) + 1;
      if (record.anthropic_only) stats.anthropic_only_count++;
      if (record.whitelist?.length > 0 || record.blacklist?.length > 0) stats.filtered_count++;
    }

    stats.model_distribution = {};
    for (const [model, count] of Object.entries(stats.by_model)) {
      stats.model_distribution[model] = {
        count,
        percentage: ((count / stats.total) * 100).toFixed(1) + '%',
      };
    }

    return stats;
  }
}

/**
 * Check for Red Hat compliance violations
 * @param {number} hours - Look back N hours
 * @returns {Array<Object>} - Violations (should be empty!)
 */
async function checkRedHatCompliance(hours = 24) {
  try {
    const result = await apiRequest('GET', `/model-usage/compliance?hours=${hours}`);
    return result.violations || [];
  } catch (apiError) {
    // Fallback to local check
    const usage = await getRecentUsage({ hours, limit: 10000 });

    const violations = usage.filter(record => {
      const isRedHatTask = record.task_type?.startsWith('redhat_');
      if (!isRedHatTask) return false;

      const anthropicModels = ['opus', 'sonnet', 'haiku', 'fable', 'claude'];
      const isAnthropicModel = anthropicModels.some(name =>
        record.model?.toLowerCase().includes(name)
      );

      return !isAnthropicModel;
    });

    return violations;
  }
}

module.exports = {
  logModelUsage,
  getRecentUsage,
  getUsageStats,
  checkRedHatCompliance,
};
