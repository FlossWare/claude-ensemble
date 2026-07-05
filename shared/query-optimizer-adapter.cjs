#!/usr/bin/env node
/**
 * JavaScript adapter for Query Optimizer
 *
 * Provides easy integration for workflow scripts to:
 * - Optimize database queries
 * - Record execution metrics
 * - Analyze slow queries
 * - Get query recommendations
 *
 * Usage:
 *   const { optimizeQuery, recordExecution } = require('./shared/query-optimizer-adapter.cjs');
 *
 *   const plan = await optimizeQuery('SELECT ...', { estimated_rows: 1000 });
 *   await recordExecution('SELECT ...', 450, { plan_used: 'index_scan' });
 */

const { execSync } = require('child_process');
const path = require('path');

const PYTHON_CMD = 'python3';
const OPTIMIZER_SCRIPT = path.join(__dirname, '..', 'tools', 'query_optimizer.py');

/**
 * Optimize a database query
 *
 * @param {string} query - SQL query to optimize
 * @param {Object} context - Query context (optional)
 * @param {number} context.estimated_rows - Expected result size
 * @param {number} context.table_size_mb - Table size in MB
 * @param {number} context.index_count - Number of available indexes
 * @param {number} context.cpu_cores - Available CPU cores
 * @returns {Promise<Object>} Optimization result
 */
async function optimizeQuery(query, context = {}) {
  const { writeFileSync } = require('fs');
  const { tmpdir } = require('os');
  const tmpScript = path.join(tmpdir(), `optimize_${Date.now()}.py`);

  const script = `import sys
import io
from contextlib import redirect_stdout
sys.path.insert(0, '${path.dirname(OPTIMIZER_SCRIPT)}')
from query_optimizer import QueryOptimizer
import json

f = io.StringIO()
with redirect_stdout(f):
    optimizer = QueryOptimizer()
    result = optimizer.optimize(${JSON.stringify(query)}, ${JSON.stringify(context)})

print(json.dumps(result))
`;

  try {
    writeFileSync(tmpScript, script);
    const output = execSync(`${PYTHON_CMD} ${tmpScript} 2>/dev/null`, {
      encoding: 'utf-8',
      maxBuffer: 10 * 1024 * 1024
    });

    require('fs').unlinkSync(tmpScript);
    const lines = output.trim().split('\n');
    return JSON.parse(lines[lines.length - 1]);
  } catch (error) {
    console.error('Query optimization failed:', error.message);
    // Return fallback result
    return {
      query_fingerprint: 'error',
      predicted_cost_ms: 1000,
      recommended_strategy: 'seq_scan',
      recommendations: [],
      error: error.message
    };
  }
}

/**
 * Record query execution for learning
 *
 * @param {string} query - SQL query that was executed
 * @param {number} actualCostMs - Actual execution time in milliseconds
 * @param {Object} context - Execution context (optional)
 * @param {string} context.plan_used - Query plan that was used
 * @returns {Promise<void>}
 */
async function recordExecution(query, actualCostMs, context = {}) {
  const { writeFileSync } = require('fs');
  const { tmpdir } = require('os');
  const tmpScript = path.join(tmpdir(), `record_${Date.now()}.py`);

  const script = `import sys
sys.path.insert(0, '${path.dirname(OPTIMIZER_SCRIPT)}')
from query_optimizer import QueryOptimizer

optimizer = QueryOptimizer()
optimizer.record_execution(
  ${JSON.stringify(query)},
  ${actualCostMs},
  ${JSON.stringify(context)},
  ${JSON.stringify(context.plan_used || null)}
)
print('OK')
`;

  try {
    writeFileSync(tmpScript, script);
    execSync(`${PYTHON_CMD} ${tmpScript}`, {
      encoding: 'utf-8'
    });
    require('fs').unlinkSync(tmpScript);
  } catch (error) {
    console.error('Failed to record execution:', error.message);
  }
}

/**
 * Analyze slow queries
 *
 * @param {number} thresholdMs - Threshold for slow queries (default: 1000ms)
 * @param {number} windowDays - Analysis window in days (default: 7)
 * @returns {Promise<Array>} List of slow queries with suggestions
 */
async function analyzeSlowQueries(thresholdMs = 1000, windowDays = 7) {
  const { writeFileSync } = require('fs');
  const { tmpdir } = require('os');
  const tmpScript = path.join(tmpdir(), `slow_${Date.now()}.py`);

  const script = `import sys
import io
from contextlib import redirect_stdout
sys.path.insert(0, '${path.dirname(OPTIMIZER_SCRIPT)}')
from query_optimizer import QueryOptimizer
import json

f = io.StringIO()
with redirect_stdout(f):
    optimizer = QueryOptimizer()
    slow = optimizer.analyze_slow_queries(threshold_ms=${thresholdMs}, window_days=${windowDays})

print(json.dumps(slow))
`;

  try {
    writeFileSync(tmpScript, script);
    const output = execSync(`${PYTHON_CMD} ${tmpScript} 2>/dev/null`, {
      encoding: 'utf-8',
      maxBuffer: 10 * 1024 * 1024
    });

    require('fs').unlinkSync(tmpScript);
    const lines = output.trim().split('\n');
    return JSON.parse(lines[lines.length - 1]);
  } catch (error) {
    console.error('Slow query analysis failed:', error.message);
    return [];
  }
}

/**
 * Train the query optimizer model
 *
 * @returns {Promise<boolean>} True if training succeeded
 */
async function trainOptimizer() {
  try {
    execSync(`${PYTHON_CMD} ${OPTIMIZER_SCRIPT} --train`, {
      encoding: 'utf-8',
      stdio: 'inherit'
    });
    return true;
  } catch (error) {
    console.error('Training failed:', error.message);
    return false;
  }
}

/**
 * Get optimizer statistics
 *
 * @returns {Promise<Object>} Optimizer stats
 */
async function getStats() {
  const { writeFileSync } = require('fs');
  const { tmpdir } = require('os');
  const tmpScript = path.join(tmpdir(), `stats_${Date.now()}.py`);

  const script = `import sys
import os
os.environ['PYTHONWARNINGS'] = 'ignore'
sys.path.insert(0, '${path.dirname(OPTIMIZER_SCRIPT)}')
from query_optimizer import QueryOptimizer
import json

# Suppress print statements during initialization
import io
from contextlib import redirect_stdout

f = io.StringIO()
with redirect_stdout(f):
    optimizer = QueryOptimizer()
    stats = optimizer.get_stats()

print(json.dumps(stats))
`;

  try {
    writeFileSync(tmpScript, script);
    const output = execSync(`${PYTHON_CMD} ${tmpScript} 2>/dev/null`, {
      encoding: 'utf-8',
      maxBuffer: 10 * 1024 * 1024
    });

    require('fs').unlinkSync(tmpScript);

    // Extract just the JSON from output
    const lines = output.trim().split('\n');
    const jsonLine = lines[lines.length - 1];
    return JSON.parse(jsonLine);
  } catch (error) {
    console.error('Failed to get stats:', error.message);
    return {
      cached_queries: 0,
      execution_history: 0,
      model_trained: false,
      strategies: {}
    };
  }
}

/**
 * Measure query execution time and record
 *
 * @param {Function} queryFn - Async function that executes the query
 * @param {string} query - SQL query string
 * @param {Object} context - Query context
 * @returns {Promise<Object>} Query result and metrics
 */
async function measureAndRecord(queryFn, query, context = {}) {
  const start = Date.now();

  try {
    const result = await queryFn();
    const durationMs = Date.now() - start;

    // Record execution
    await recordExecution(query, durationMs, context);

    return {
      result,
      durationMs,
      success: true
    };
  } catch (error) {
    const durationMs = Date.now() - start;

    // Record failed execution
    await recordExecution(query, durationMs, {
      ...context,
      error: error.message
    });

    return {
      result: null,
      durationMs,
      success: false,
      error: error.message
    };
  }
}

/**
 * Optimize and execute query with automatic measurement
 *
 * @param {string} query - SQL query
 * @param {Function} queryFn - Async function that executes the query
 * @param {Object} context - Query context
 * @returns {Promise<Object>} Result with optimization plan and metrics
 */
async function optimizeAndExecute(query, queryFn, context = {}) {
  // Get optimization plan
  const plan = await optimizeQuery(query, context);

  console.log(`Query predicted cost: ${plan.predicted_cost_ms.toFixed(1)}ms`);
  console.log(`Recommended strategy: ${plan.recommended_strategy}`);

  if (plan.recommendations.length > 0) {
    console.log('Recommendations:');
    plan.recommendations.forEach(rec => {
      console.log(`  [${rec.priority}] ${rec.message}`);
    });
  }

  // Execute and measure
  const execution = await measureAndRecord(queryFn, query, {
    ...context,
    plan_used: plan.recommended_strategy
  });

  // Compare prediction vs actual
  const accuracy = Math.abs(plan.predicted_cost_ms - execution.durationMs) / execution.durationMs;

  return {
    plan,
    execution,
    prediction_accuracy: 1 - Math.min(accuracy, 1)
  };
}

module.exports = {
  optimizeQuery,
  recordExecution,
  analyzeSlowQueries,
  trainOptimizer,
  getStats,
  measureAndRecord,
  optimizeAndExecute
};

// CLI mode
if (require.main === module) {
  const command = process.argv[2];

  (async () => {
    switch (command) {
      case 'train':
        console.log('Training query optimizer...');
        const success = await trainOptimizer();
        process.exit(success ? 0 : 1);
        break;

      case 'stats':
        const stats = await getStats();
        console.log('Query Optimizer Statistics:');
        console.log(JSON.stringify(stats, null, 2));
        break;

      case 'slow':
        const threshold = parseFloat(process.argv[3]) || 1000;
        const slow = await analyzeSlowQueries(threshold);
        console.log(`Slow queries (>${threshold}ms):`);
        console.log(JSON.stringify(slow, null, 2));
        break;

      default:
        console.log('Usage:');
        console.log('  node query-optimizer-adapter.cjs train');
        console.log('  node query-optimizer-adapter.cjs stats');
        console.log('  node query-optimizer-adapter.cjs slow [threshold_ms]');
        process.exit(1);
    }
  })();
}
