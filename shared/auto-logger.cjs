/**
 * Auto Logger for Workflow Executions
 *
 * Automatically captures ALL workflow executions and logs to PostgreSQL.
 * Tracks: start/end time, success/failure, resource usage, cost, performance.
 *
 * Usage:
 *   const { wrapWorkflow } = require('./shared/auto-logger.js');
 *
 *   const myWorkflow = wrapWorkflow(async ({ agent, parallel }) => {
 *     // ... workflow logic ...
 *     return result;
 *   }, {
 *     workflow_name: 'deep-research',
 *     model: 'opus',
 *     task_type: 'research'
 *   });
 *
 *   const result = await myWorkflow({ agent, parallel });
 *
 * Features:
 * - Auto-captures start/end timestamps
 * - Tracks success/failure with error details
 * - Monitors resource usage (CPU, memory, tokens, cost)
 * - Logs to monitoring.execution_summary
 * - Returns original workflow result + execution metadata
 * - Graceful error handling (logs even if workflow fails)
 *
 * Created: 2026-07-04
 */

const { Pool } = require('pg');
const os = require('os');

// Reuse connection pool
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 10,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => {
  console.error('[auto-logger] PostgreSQL pool error:', err.message);
});

// Clean up on exit
process.on('exit', () => pool.end());
process.on('SIGINT', () => { pool.end(); process.exit(0); });
process.on('SIGTERM', () => { pool.end(); process.exit(0); });

/**
 * Resource Monitor
 * Tracks CPU, memory, and execution metrics during workflow execution
 */
class ResourceMonitor {
  constructor() {
    this.startTime = null;
    this.endTime = null;
    this.startCpuUsage = null;
    this.startMemUsage = null;
    this.peakMemory = 0;
    this.intervalHandle = null;
  }

  /**
   * Start monitoring resources
   */
  start() {
    this.startTime = Date.now();
    this.startCpuUsage = process.cpuUsage();
    this.startMemUsage = process.memoryUsage();
    this.peakMemory = this.startMemUsage.heapUsed;

    // Poll memory usage every 100ms to track peak
    this.intervalHandle = setInterval(() => {
      const current = process.memoryUsage().heapUsed;
      if (current > this.peakMemory) {
        this.peakMemory = current;
      }
    }, 100);
  }

  /**
   * Stop monitoring and return metrics
   * @returns {Object} Resource usage metrics
   */
  stop() {
    this.endTime = Date.now();

    if (this.intervalHandle) {
      clearInterval(this.intervalHandle);
      this.intervalHandle = null;
    }

    const endCpuUsage = process.cpuUsage(this.startCpuUsage);
    const endMemUsage = process.memoryUsage();

    const durationMs = this.endTime - this.startTime;

    // CPU usage in milliseconds converted to percentage
    // cpuUsage returns microseconds, convert to ms then to percentage of wall time
    const cpuPercent = ((endCpuUsage.user + endCpuUsage.system) / 1000) / durationMs * 100;

    return {
      duration_ms: durationMs,
      cpu_percent: Math.round(cpuPercent * 10) / 10,
      memory_used_mb: Math.round(this.peakMemory / 1024 / 1024 * 10) / 10,
      memory_delta_mb: Math.round((endMemUsage.heapUsed - this.startMemUsage.heapUsed) / 1024 / 1024 * 10) / 10,
      start_time: new Date(this.startTime).toISOString(),
      end_time: new Date(this.endTime).toISOString()
    };
  }

  /**
   * Stop monitoring and discard metrics (for error cases)
   */
  cancel() {
    if (this.intervalHandle) {
      clearInterval(this.intervalHandle);
      this.intervalHandle = null;
    }
  }
}

/**
 * Calculate cost based on token usage and model
 * Uses standard API pricing (as of 2026-07)
 *
 * @param {string} model - Model name
 * @param {number} inputTokens - Input tokens
 * @param {number} outputTokens - Output tokens
 * @returns {number} Cost in USD
 */
function calculateCost(model, inputTokens = 0, outputTokens = 0) {
  // Pricing per 1M tokens (input, output)
  const pricing = {
    'opus': [15.00, 75.00],
    'sonnet': [3.00, 15.00],
    'haiku': [0.25, 1.25],
    'fable': [0.50, 2.50],
    'gpt-4o': [5.00, 15.00],
    'gpt-4o-mini': [0.15, 0.60],
    'gemini-pro': [0.50, 1.50],
    'gemini-flash': [0.075, 0.30],
    'deepseek-coder': [0.14, 0.28],
    'qwen-coder': [0.09, 0.18]
  };

  const modelKey = model.toLowerCase().replace(/[^a-z0-9-]/g, '');
  const rates = pricing[modelKey] || [1.00, 3.00]; // Default fallback

  const inputCost = (inputTokens / 1_000_000) * rates[0];
  const outputCost = (outputTokens / 1_000_000) * rates[1];

  return Math.round((inputCost + outputCost) * 10000) / 10000; // Round to 4 decimals
}

/**
 * Log execution to PostgreSQL
 *
 * @param {Object} logData - Execution log data
 * @returns {Promise<number>} Record ID
 */
async function logExecution(logData) {
  const {
    model,
    workflow,
    task_type,
    quality_score = null,
    input_tokens = 0,
    output_tokens = 0,
    cost_usd = null,
    duration_ms,
    outcome,
    metadata = {}
  } = logData;

  const client = await pool.connect();
  try {
    const result = await client.query(
      `INSERT INTO monitoring.execution_summary
       (timestamp, model, workflow, task_type, quality_score, input_tokens,
        output_tokens, cost_usd, duration_ms, outcome, metadata)
       VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
       RETURNING id`,
      [
        model,
        workflow,
        task_type,
        quality_score,
        Math.floor(input_tokens),
        Math.floor(output_tokens),
        cost_usd,
        Math.floor(duration_ms),
        outcome,
        JSON.stringify(metadata)
      ]
    );

    return result.rows[0].id;
  } finally {
    client.release();
  }
}

/**
 * Extract token counts from workflow result
 * Supports multiple result formats
 *
 * @param {any} result - Workflow result
 * @returns {Object} { input_tokens, output_tokens }
 */
function extractTokenCounts(result) {
  let inputTokens = 0;
  let outputTokens = 0;

  if (!result) {
    return { input_tokens: 0, output_tokens: 0 };
  }

  // Direct token properties
  if (result.input_tokens) inputTokens += result.input_tokens;
  if (result.output_tokens) outputTokens += result.output_tokens;

  // Usage object (OpenAI style)
  if (result.usage) {
    inputTokens += result.usage.prompt_tokens || result.usage.input_tokens || 0;
    outputTokens += result.usage.completion_tokens || result.usage.output_tokens || 0;
  }

  // Array of results (parallel workers)
  if (Array.isArray(result)) {
    for (const item of result) {
      const tokens = extractTokenCounts(item);
      inputTokens += tokens.input_tokens;
      outputTokens += tokens.output_tokens;
    }
  }

  // Nested results object
  if (result.results && typeof result.results === 'object') {
    const tokens = extractTokenCounts(result.results);
    inputTokens += tokens.input_tokens;
    outputTokens += tokens.output_tokens;
  }

  return { input_tokens: inputTokens, output_tokens: outputTokens };
}

/**
 * Wrap a workflow function to auto-log execution
 *
 * @param {Function} workflowFn - Async workflow function to wrap
 * @param {Object} metadata - Workflow metadata
 * @param {string} metadata.workflow_name - Workflow name (e.g., 'deep-research')
 * @param {string} metadata.model - Primary model used (e.g., 'opus')
 * @param {string} metadata.task_type - Task type (e.g., 'research', 'code_generation')
 * @param {Object} metadata.additional - Additional metadata to log
 * @returns {Function} Wrapped workflow function
 *
 * Example:
 *   const wrappedWorkflow = wrapWorkflow(async ({ agent }) => {
 *     return await agent('research', 'Find firmware bugs');
 *   }, {
 *     workflow_name: 'firmware-analysis',
 *     model: 'opus',
 *     task_type: 'security_audit'
 *   });
 *
 *   const { result, execution } = await wrappedWorkflow({ agent });
 *   console.log('Execution ID:', execution.id);
 *   console.log('Duration:', execution.duration_ms, 'ms');
 */
function wrapWorkflow(workflowFn, metadata = {}) {
  const {
    workflow_name = 'unnamed-workflow',
    model = 'unknown',
    task_type = 'general',
    additional = {}
  } = metadata;

  return async function wrappedWorkflowExecution(...args) {
    const monitor = new ResourceMonitor();
    monitor.start();

    let outcome = 'success';
    let result = null;
    let error = null;
    let inputTokens = 0;
    let outputTokens = 0;

    try {
      // Execute workflow
      result = await workflowFn(...args);

      // Extract token counts from result
      const tokens = extractTokenCounts(result);
      inputTokens = tokens.input_tokens;
      outputTokens = tokens.output_tokens;

    } catch (err) {
      outcome = 'error';
      error = err;
      console.error(`[auto-logger] Workflow '${workflow_name}' failed:`, err.message);
    } finally {
      // Always log, even on failure
      const resourceMetrics = monitor.stop();
      const costUsd = calculateCost(model, inputTokens, outputTokens);

      const logData = {
        model,
        workflow: workflow_name,
        task_type,
        quality_score: outcome === 'success' ? 1.0 : 0.0,
        input_tokens: inputTokens,
        output_tokens: outputTokens,
        cost_usd: costUsd,
        duration_ms: resourceMetrics.duration_ms,
        outcome,
        metadata: {
          ...additional,
          resource_metrics: resourceMetrics,
          error: error ? {
            message: error.message,
            stack: error.stack?.split('\n').slice(0, 5).join('\n') // First 5 lines
          } : null,
          hostname: os.hostname(),
          node_version: process.version,
          platform: process.platform
        }
      };

      try {
        const executionId = await logExecution(logData);

        // Return result + execution metadata
        const executionMeta = {
          id: executionId,
          workflow_name,
          model,
          outcome,
          duration_ms: resourceMetrics.duration_ms,
          cost_usd: costUsd,
          input_tokens: inputTokens,
          output_tokens: outputTokens,
          resource_metrics: resourceMetrics
        };

        if (error) {
          // Re-throw error after logging
          throw error;
        }

        return {
          result,
          execution: executionMeta
        };

      } catch (logErr) {
        console.error('[auto-logger] Failed to log execution:', logErr.message);

        // Still return result even if logging failed
        if (error) {
          throw error;
        }

        return {
          result,
          execution: {
            workflow_name,
            model,
            outcome,
            error: logErr.message
          }
        };
      }
    }
  };
}

/**
 * Simple wrapper for quick logging (without resource monitoring)
 * Use when you just need basic execution tracking
 *
 * @param {string} workflowName - Workflow name
 * @param {string} model - Model used
 * @param {Function} fn - Function to execute
 * @returns {Promise<any>} Function result
 *
 * Example:
 *   const result = await quickLog('test-workflow', 'opus', async () => {
 *     return await doSomething();
 *   });
 */
async function quickLog(workflowName, model, fn) {
  const wrapped = wrapWorkflow(fn, {
    workflow_name: workflowName,
    model,
    task_type: 'general'
  });

  const { result } = await wrapped();
  return result;
}

/**
 * Manual logging (for cases where you can't wrap the function)
 *
 * @param {Object} data - Log data (same as logExecution)
 * @returns {Promise<number>} Record ID
 *
 * Example:
 *   const id = await manualLog({
 *     model: 'opus',
 *     workflow: 'custom-task',
 *     task_type: 'research',
 *     duration_ms: 5000,
 *     outcome: 'success',
 *     input_tokens: 1000,
 *     output_tokens: 500
 *   });
 */
async function manualLog(data) {
  const cost = data.cost_usd || calculateCost(
    data.model,
    data.input_tokens || 0,
    data.output_tokens || 0
  );

  return await logExecution({
    ...data,
    cost_usd: cost
  });
}

/**
 * Get execution statistics for a workflow
 *
 * @param {string} workflowName - Workflow name
 * @param {number} limit - Max records to analyze (default: 100)
 * @returns {Promise<Object>} Statistics
 *
 * Example:
 *   const stats = await getWorkflowStats('deep-research');
 *   console.log('Success rate:', stats.success_rate);
 *   console.log('Avg duration:', stats.avg_duration_ms);
 */
async function getWorkflowStats(workflowName, limit = 100) {
  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT
         COUNT(*) as total_executions,
         SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
         AVG(duration_ms) as avg_duration_ms,
         AVG(cost_usd) as avg_cost_usd,
         SUM(input_tokens) as total_input_tokens,
         SUM(output_tokens) as total_output_tokens,
         MIN(duration_ms) as min_duration_ms,
         MAX(duration_ms) as max_duration_ms
       FROM monitoring.execution_summary
       WHERE workflow = $1
       LIMIT $2`,
      [workflowName, limit]
    );

    const row = result.rows[0];
    const total = parseInt(row.total_executions);
    const successes = parseInt(row.successes);

    return {
      total_executions: total,
      success_rate: total > 0 ? Math.round((successes / total) * 1000) / 10 : 0,
      avg_duration_ms: Math.round(parseFloat(row.avg_duration_ms) || 0),
      avg_cost_usd: Math.round((parseFloat(row.avg_cost_usd) || 0) * 10000) / 10000,
      total_input_tokens: parseInt(row.total_input_tokens) || 0,
      total_output_tokens: parseInt(row.total_output_tokens) || 0,
      min_duration_ms: parseInt(row.min_duration_ms) || 0,
      max_duration_ms: parseInt(row.max_duration_ms) || 0
    };
  } finally {
    client.release();
  }
}

module.exports = {
  wrapWorkflow,
  quickLog,
  manualLog,
  getWorkflowStats,
  calculateCost,
  extractTokenCounts,
  ResourceMonitor,
  pool
};
