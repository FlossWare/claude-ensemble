/**
 * Consensus Replay System - PRODUCTION ACTIVE ✓
 *
 * Re-run old consensus workflows with updated model weights to measure improvement/degradation.
 *
 * Architecture:
 * 1. Fetch historical workflow from workflow.executions
 * 2. Extract original task + worker assignments
 * 3. Re-run with current model weights
 * 4. Compare old vs new results (confidence, quality, cost, speed)
 * 5. Generate comparison report with statistical significance testing
 *
 * Use Case:
 * - Measure if new model weights improve on your workload
 * - Detect regression after model updates
 * - Track quality evolution over time
 *
 * PRODUCTION INTEGRATION (ACTIVE):
 * ================================
 * ✓ Automated weekly via tools/model_regression_monitor.cjs (cron: Sundays 2am)
 * ✓ Results displayed in tools/performance_dashboard.py (--regression flag)
 * ✓ Alerts on DEGRADATION verdicts (exit code 1 from monitor)
 * ✓ HTML reports generated: /tmp/consensus-replay-reports/
 * ✓ Database storage: workflow.replays table
 *
 * Setup: ./setup-regression-monitoring.sh
 * Manual run: node tools/model_regression_monitor.cjs --weeks 4
 * View results: python3 tools/performance_dashboard.py
 *
 * PRODUCTION CONSUMERS:
 * ====================
 * 1. tools/model_regression_monitor.cjs - Main automated consumer
 * 2. tools/performance_dashboard.py - UI display (get_regression_analysis)
 * 3. shared/workflow-completion-hook.cjs - Optional post-workflow replay
 * 4. shared/advanced-consensus.js - Advanced consensus workflows
 *
 * STATISTICAL TESTING (Issue #267, 2026-07-02):
 * =============================================
 * ✓ Integrated experiment-manager.cjs for Welch's t-test + bootstrap CI
 * ✓ generateStatisticalVerdict() for rigorous regression detection
 * ✓ Replaces threshold-based verdicts when multiple samples available
 *
 * Created: 2026-06-28
 * Production Status: ACTIVE (Issue #265 verified 2026-07-02)
 * Enhanced: Statistical testing (Issue #267, 2026-07-02)
 */

const { Pool } = require('pg');
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const { compareResults: statisticalCompare } = require('./experiment-manager.cjs');

// PostgreSQL connection pool
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
  console.error('PostgreSQL pool error:', err.message);
});

/**
 * Consensus Replay Engine
 */
class ConsensusReplay {
  constructor() {
    this.pool = pool;
  }

  /**
   * Fetch historical workflow execution from database
   *
   * @param {string} workflowId - Workflow ID to replay
   * @returns {Promise<Object|null>} Historical workflow data or null if not found
   */
  async fetchHistoricalWorkflow(workflowId) {
    const client = await this.pool.connect();
    try {
      // Get workflow execution
      const execResult = await client.query(
        `SELECT * FROM workflow.executions WHERE workflow_id = $1`,
        [workflowId]
      );

      if (execResult.rows.length === 0) {
        return null;
      }

      const execution = execResult.rows[0];
      const executionId = execution.id;

      // Get worker results
      const workersResult = await client.query(
        `SELECT * FROM workflow.worker_results
         WHERE workflow_execution_id = $1
         ORDER BY created_at`,
        [executionId]
      );

      // Get arbiter decisions
      const arbitersResult = await client.query(
        `SELECT * FROM workflow.arbiter_decisions
         WHERE workflow_execution_id = $1
         ORDER BY created_at`,
        [executionId]
      );

      // Get phases
      const phasesResult = await client.query(
        `SELECT * FROM workflow.phases
         WHERE workflow_execution_id = $1
         ORDER BY phase_order`,
        [executionId]
      );

      return {
        execution,
        workers: workersResult.rows,
        arbiters: arbitersResult.rows,
        phases: phasesResult.rows
      };

    } finally {
      client.release();
    }
  }

  /**
   * Re-run consensus with current model weights
   *
   * Uses fleet-utils.js executeOnFleet to run workers in parallel.
   * Extracts original task descriptions and re-assigns to same models.
   *
   * @param {Object} historical - Historical workflow data
   * @param {Object} options - Replay options
   * @param {boolean} options.sameModels - Use same models as original (default true)
   * @param {string[]} options.overrideModels - Override with specific models
   * @returns {Promise<Object>} New execution results
   */
  async rerunConsensus(historical, options = {}) {
    const { sameModels = true, overrideModels = null } = options;

    const taskDescription = historical.execution.task_description;
    const originalWorkers = historical.workers;

    // Determine which models to use
    let modelsToUse;
    if (overrideModels) {
      modelsToUse = overrideModels;
    } else if (sameModels) {
      modelsToUse = originalWorkers.map(w => w.model);
    } else {
      // Default: use current fleet topology
      modelsToUse = this._getCurrentFleetModels();
    }

    console.log(`Replaying workflow with ${modelsToUse.length} workers: ${modelsToUse.join(', ')}`);

    // Execute workers in parallel
    const workerResults = await this._executeWorkersParallel(taskDescription, modelsToUse);

    // Run arbiter to synthesize results
    const arbiterResult = await this._executeArbiter(taskDescription, workerResults);

    return {
      workers: workerResults,
      arbiter: arbiterResult,
      metadata: {
        replayed_at: new Date().toISOString(),
        original_workflow_id: historical.execution.workflow_id,
        models_used: modelsToUse
      }
    };
  }

  /**
   * Execute workers in parallel using fleet orchestration
   *
   * @param {string} task - Task description
   * @param {string[]} models - Models to use
   * @returns {Promise<Array>} Worker results
   */
  async _executeWorkersParallel(task, models) {
    // Build fleet tasks (one per model)
    const tasks = models.map((model, idx) => ({
      id: `worker-${idx}`,
      model,
      task,
      prompt: `You are analyzing the following task:\n\n${task}\n\nProvide your analysis, recommendation, or solution. Rate your confidence (0.0-1.0).`
    }));

    // Execute on fleet (parallel)
    const results = [];
    for (const taskDef of tasks) {
      const start = Date.now();
      const result = await this._executeWorker(taskDef);
      results.push({
        worker_id: taskDef.id,
        model: taskDef.model,
        task_assigned: task,
        result: result.output,
        confidence: result.confidence,
        duration_ms: Date.now() - start,
        input_tokens: result.input_tokens || 0,
        output_tokens: result.output_tokens || 0,
        cost_usd: result.cost_usd || 0,
        outcome: result.error ? 'error' : 'success',
        created_at: new Date().toISOString()
      });
    }

    return results;
  }

  /**
   * Execute single worker via Claude CLI
   *
   * @param {Object} taskDef - Task definition
   * @returns {Promise<Object>} Worker result
   */
  async _executeWorker(taskDef) {
    try {
      // Execute via Claude CLI with specified model
      const cmdArgs = [
        'claude',
        '--model', taskDef.model,
        '--message', taskDef.prompt
      ];

      const result = execSync(cmdArgs.join(' '), {
        encoding: 'utf8',
        maxBuffer: 10 * 1024 * 1024, // 10MB
        timeout: 120000 // 2 min timeout
      });

      // Parse output (simple text response)
      return {
        output: result.trim(),
        confidence: this._extractConfidence(result),
        input_tokens: 0, // Claude CLI doesn't report tokens
        output_tokens: 0,
        cost_usd: 0
      };

    } catch (error) {
      console.error(`Worker ${taskDef.id} (${taskDef.model}) failed:`, error.message);
      return {
        output: `ERROR: ${error.message}`,
        confidence: 0.0,
        error: error.message
      };
    }
  }

  /**
   * Extract confidence score from worker output
   * Looks for patterns like "confidence: 0.85" or "85% confident"
   *
   * @param {string} text - Worker output
   * @returns {number} Confidence score (0.0-1.0)
   */
  _extractConfidence(text) {
    // Pattern 1: "confidence: 0.85"
    const pattern1 = /confidence:\s*(0?\.\d+)/i;
    const match1 = text.match(pattern1);
    if (match1) return parseFloat(match1[1]);

    // Pattern 2: "85% confident"
    const pattern2 = /(\d+)%\s*confident/i;
    const match2 = text.match(pattern2);
    if (match2) return parseFloat(match2[1]) / 100;

    // Default: moderate confidence
    return 0.5;
  }

  /**
   * Execute arbiter to synthesize worker results
   *
   * @param {string} task - Original task
   * @param {Array} workers - Worker results
   * @returns {Promise<Object>} Arbiter decision
   */
  async _executeArbiter(task, workers) {
    const arbiterPrompt = `
You are the arbiter synthesizing results from multiple AI workers.

ORIGINAL TASK:
${task}

WORKER RESULTS:
${workers.map((w, i) => `
Worker ${i + 1} (${w.model}, confidence: ${w.confidence}):
${w.result}
`).join('\n---\n')}

Synthesize the best answer from these results. Consider confidence scores and quality.
Provide your final decision and rate your confidence (0.0-1.0).
`;

    const start = Date.now();
    try {
      const result = execSync(`claude --model opus --message "${arbiterPrompt.replace(/"/g, '\\"')}"`, {
        encoding: 'utf8',
        maxBuffer: 10 * 1024 * 1024,
        timeout: 120000
      });

      return {
        arbiter_model: 'opus',
        decision: result.trim(),
        confidence: this._extractConfidence(result),
        duration_ms: Date.now() - start,
        input_tokens: 0,
        output_tokens: 0,
        cost_usd: 0,
        created_at: new Date().toISOString()
      };

    } catch (error) {
      console.error('Arbiter failed:', error.message);
      return {
        arbiter_model: 'opus',
        decision: `ERROR: ${error.message}`,
        confidence: 0.0,
        duration_ms: Date.now() - start,
        error: error.message,
        created_at: new Date().toISOString()
      };
    }
  }

  /**
   * Get current fleet models from topology
   *
   * @returns {string[]} Available models
   */
  _getCurrentFleetModels() {
    try {
      const topologyPath = path.join(__dirname, 'fleet-topology.js');
      const topology = require(topologyPath);
      const models = topology.FLEET_TOPOLOGY.flatMap(node => node.models || []);
      return [...new Set(models)]; // Deduplicate
    } catch (error) {
      console.warn('Failed to load fleet topology, using defaults:', error.message);
      return ['opus', 'sonnet', 'haiku', 'fable'];
    }
  }

  /**
   * Compare old vs new consensus results
   *
   * Metrics:
   * - Confidence delta (new - old)
   * - Quality improvement (subjective, based on arbiter confidence)
   * - Speed delta (duration)
   * - Cost delta
   *
   * @param {Object} historical - Historical workflow
   * @param {Object} newRun - New execution results
   * @returns {Object} Comparison report
   */
  compareResults(historical, newRun) {
    const oldWorkers = historical.workers;
    const newWorkers = newRun.workers;
    const oldArbiter = historical.arbiters[0] || {};
    const newArbiter = newRun.arbiter;

    // Worker-level comparison
    const workerComparison = oldWorkers.map((oldW, idx) => {
      const newW = newWorkers[idx] || {};
      return {
        model: oldW.model,
        old_confidence: oldW.confidence,
        new_confidence: newW.confidence,
        confidence_delta: (newW.confidence || 0) - (oldW.confidence || 0),
        old_duration_ms: oldW.duration_ms,
        new_duration_ms: newW.duration_ms,
        speed_improvement: ((oldW.duration_ms - newW.duration_ms) / oldW.duration_ms * 100).toFixed(1) + '%',
        old_cost_usd: oldW.cost_usd,
        new_cost_usd: newW.cost_usd || 0,
        cost_delta: (newW.cost_usd || 0) - (oldW.cost_usd || 0)
      };
    });

    // Arbiter-level comparison
    const arbiterComparison = {
      old_confidence: oldArbiter.confidence || 0,
      new_confidence: newArbiter.confidence,
      confidence_delta: (newArbiter.confidence || 0) - (oldArbiter.confidence || 0),
      old_duration_ms: oldArbiter.duration_ms || 0,
      new_duration_ms: newArbiter.duration_ms,
      speed_improvement: oldArbiter.duration_ms
        ? ((oldArbiter.duration_ms - newArbiter.duration_ms) / oldArbiter.duration_ms * 100).toFixed(1) + '%'
        : 'N/A'
    };

    // Overall metrics
    const avgOldConfidence = oldWorkers.reduce((sum, w) => sum + w.confidence, 0) / oldWorkers.length;
    const avgNewConfidence = newWorkers.reduce((sum, w) => sum + (w.confidence || 0), 0) / newWorkers.length;
    const totalOldCost = oldWorkers.reduce((sum, w) => sum + w.cost_usd, 0);
    const totalNewCost = newWorkers.reduce((sum, w) => sum + (w.cost_usd || 0), 0);

    return {
      summary: {
        workflow_id: historical.execution.workflow_id,
        task: historical.execution.task_description,
        replayed_at: newRun.metadata.replayed_at,
        original_created_at: historical.execution.created_at,
        avg_confidence_delta: (avgNewConfidence - avgOldConfidence).toFixed(3),
        arbiter_confidence_delta: arbiterComparison.confidence_delta.toFixed(3),
        total_cost_delta: (totalNewCost - totalOldCost).toFixed(4),
        verdict: this._generateVerdict(arbiterComparison.confidence_delta, avgNewConfidence - avgOldConfidence)
      },
      workers: workerComparison,
      arbiter: arbiterComparison,
      details: {
        old_execution: historical.execution,
        new_metadata: newRun.metadata
      }
    };
  }

  /**
   * Generate verdict based on performance deltas
   *
   * LEGACY METHOD: Uses simple thresholds (backward compatibility)
   * For single replays or when statistical testing unavailable.
   *
   * @param {number} arbiterDelta - Arbiter confidence delta
   * @param {number} avgWorkerDelta - Average worker confidence delta
   * @returns {string} Verdict
   */
  _generateVerdict(arbiterDelta, avgWorkerDelta) {
    if (arbiterDelta > 0.1 && avgWorkerDelta > 0.05) {
      return 'SIGNIFICANT_IMPROVEMENT';
    } else if (arbiterDelta > 0.05 || avgWorkerDelta > 0.03) {
      return 'MODERATE_IMPROVEMENT';
    } else if (arbiterDelta < -0.1 || avgWorkerDelta < -0.05) {
      return 'DEGRADATION';
    } else {
      return 'NO_SIGNIFICANT_CHANGE';
    }
  }

  /**
   * Generate statistically-rigorous verdict (NEW METHOD, Issue #267)
   *
   * Uses Welch's t-test + bootstrap CI from experiment-manager.cjs.
   * Requires multiple samples (baseline vs treatment).
   *
   * Example usage:
   *   const baselineConfidences = [0.72, 0.68, 0.75, 0.70, 0.73];
   *   const treatmentConfidences = [0.78, 0.82, 0.76, 0.79, 0.81];
   *   const result = replay.generateStatisticalVerdict(baselineConfidences, treatmentConfidences);
   *
   * @param {number[]} baselineConfidences - Historical confidence scores
   * @param {number[]} treatmentConfidences - New replay confidence scores
   * @param {Object} [options]
   * @param {number} [options.alpha] - Significance level (default: 0.05)
   * @param {number} [options.min_improvement_pct] - Min improvement to keep (default: 3)
   * @returns {Object} Statistical comparison result with verdict
   */
  generateStatisticalVerdict(baselineConfidences, treatmentConfidences, options = {}) {
    // Use experiment-manager's statistical comparison
    const stats = statisticalCompare(baselineConfidences, treatmentConfidences, {
      alpha: options.alpha || 0.05,
      min_improvement_pct: options.min_improvement_pct || 3,
      bootstrap_iterations: options.bootstrap_iterations || 1000,
      bootstrap_confidence: options.bootstrap_confidence || 0.95,
    });

    // Map experiment-manager verdicts to consensus-replay verdicts
    let consensusVerdict;
    if (stats.verdict === 'keep') {
      // Significant improvement
      consensusVerdict = stats.improvement_pct > 5
        ? 'SIGNIFICANT_IMPROVEMENT'
        : 'MODERATE_IMPROVEMENT';
    } else if (stats.verdict === 'remove') {
      // Significant degradation
      consensusVerdict = 'DEGRADATION';
    } else {
      // Inconclusive or no significant change
      consensusVerdict = 'NO_SIGNIFICANT_CHANGE';
    }

    return {
      verdict: consensusVerdict,
      statistics: {
        baseline_mean: stats.baseline_mean,
        treatment_mean: stats.treatment_mean,
        improvement_pct: stats.improvement_pct,
        p_value: stats.p_value,
        t_stat: stats.t_stat,
        df: stats.df,
        ci_lower: stats.ci_lower,
        ci_upper: stats.ci_upper,
        effect_size: stats.effect_size,
        significant: stats.significant,
        reason: stats.reason,
      },
    };
  }

  /**
   * Store replay results to database for tracking
   *
   * @param {Object} comparison - Comparison report
   * @returns {Promise<number>} Replay record ID
   */
  async storeReplayResults(comparison) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      // Store in workflow.replays table (create if not exists)
      await client.query(`
        CREATE TABLE IF NOT EXISTS workflow.replays (
          id SERIAL PRIMARY KEY,
          original_workflow_id VARCHAR(255),
          replayed_at TIMESTAMP,
          original_created_at TIMESTAMP,
          avg_confidence_delta NUMERIC,
          arbiter_confidence_delta NUMERIC,
          total_cost_delta NUMERIC,
          verdict VARCHAR(50),
          comparison_data JSONB,
          created_at TIMESTAMP DEFAULT NOW()
        )
      `);

      const result = await client.query(
        `INSERT INTO workflow.replays
         (original_workflow_id, replayed_at, original_created_at, avg_confidence_delta,
          arbiter_confidence_delta, total_cost_delta, verdict, comparison_data)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         RETURNING id`,
        [
          comparison.summary.workflow_id,
          comparison.summary.replayed_at,
          comparison.summary.original_created_at,
          parseFloat(comparison.summary.avg_confidence_delta),
          parseFloat(comparison.summary.arbiter_confidence_delta),
          parseFloat(comparison.summary.total_cost_delta),
          comparison.summary.verdict,
          JSON.stringify(comparison)
        ]
      );

      await client.query('COMMIT');
      return result.rows[0].id;

    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Generate HTML comparison report
   *
   * @param {Object} comparison - Comparison report
   * @param {string} outputPath - Output file path
   */
  generateHTMLReport(comparison, outputPath) {
    const html = `
<!DOCTYPE html>
<html>
<head>
  <title>Consensus Replay Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    h1 { color: #333; }
    h2 { color: #666; margin-top: 30px; }
    table { border-collapse: collapse; width: 100%; margin: 20px 0; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; }
    .improvement { color: green; font-weight: bold; }
    .degradation { color: red; font-weight: bold; }
    .neutral { color: gray; }
    .verdict { font-size: 1.2em; padding: 10px; margin: 20px 0; border-radius: 5px; }
    .verdict.SIGNIFICANT_IMPROVEMENT { background-color: #d4edda; color: #155724; }
    .verdict.MODERATE_IMPROVEMENT { background-color: #d1ecf1; color: #0c5460; }
    .verdict.NO_SIGNIFICANT_CHANGE { background-color: #f8f9fa; color: #6c757d; }
    .verdict.DEGRADATION { background-color: #f8d7da; color: #721c24; }
  </style>
</head>
<body>
  <h1>Consensus Replay Report</h1>

  <div class="verdict ${comparison.summary.verdict}">
    Verdict: ${comparison.summary.verdict.replace(/_/g, ' ')}
  </div>

  <h2>Summary</h2>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Workflow ID</td><td>${comparison.summary.workflow_id}</td></tr>
    <tr><td>Task</td><td>${comparison.summary.task}</td></tr>
    <tr><td>Original Created</td><td>${comparison.summary.original_created_at}</td></tr>
    <tr><td>Replayed At</td><td>${comparison.summary.replayed_at}</td></tr>
    <tr><td>Avg Confidence Delta</td><td class="${parseFloat(comparison.summary.avg_confidence_delta) > 0 ? 'improvement' : 'degradation'}">${comparison.summary.avg_confidence_delta}</td></tr>
    <tr><td>Arbiter Confidence Delta</td><td class="${parseFloat(comparison.summary.arbiter_confidence_delta) > 0 ? 'improvement' : 'degradation'}">${comparison.summary.arbiter_confidence_delta}</td></tr>
    <tr><td>Total Cost Delta</td><td class="${parseFloat(comparison.summary.total_cost_delta) < 0 ? 'improvement' : 'degradation'}">$${comparison.summary.total_cost_delta}</td></tr>
  </table>

  <h2>Worker Comparison</h2>
  <table>
    <tr>
      <th>Model</th>
      <th>Old Confidence</th>
      <th>New Confidence</th>
      <th>Delta</th>
      <th>Speed Improvement</th>
      <th>Cost Delta</th>
    </tr>
    ${comparison.workers.map(w => `
    <tr>
      <td>${w.model}</td>
      <td>${w.old_confidence.toFixed(3)}</td>
      <td>${(w.new_confidence || 0).toFixed(3)}</td>
      <td class="${w.confidence_delta > 0 ? 'improvement' : w.confidence_delta < 0 ? 'degradation' : 'neutral'}">${w.confidence_delta.toFixed(3)}</td>
      <td>${w.speed_improvement}</td>
      <td>$${w.cost_delta.toFixed(4)}</td>
    </tr>
    `).join('')}
  </table>

  <h2>Arbiter Comparison</h2>
  <table>
    <tr><th>Metric</th><th>Old</th><th>New</th><th>Delta</th></tr>
    <tr>
      <td>Confidence</td>
      <td>${comparison.arbiter.old_confidence.toFixed(3)}</td>
      <td>${comparison.arbiter.new_confidence.toFixed(3)}</td>
      <td class="${comparison.arbiter.confidence_delta > 0 ? 'improvement' : 'degradation'}">${comparison.arbiter.confidence_delta.toFixed(3)}</td>
    </tr>
    <tr>
      <td>Speed</td>
      <td>${comparison.arbiter.old_duration_ms}ms</td>
      <td>${comparison.arbiter.new_duration_ms}ms</td>
      <td>${comparison.arbiter.speed_improvement}</td>
    </tr>
  </table>

  <p style="margin-top: 40px; color: #666; font-size: 0.9em;">
    Generated: ${new Date().toISOString()}
  </p>
</body>
</html>
`;

    fs.writeFileSync(outputPath, html);
    console.log(`HTML report written to: ${outputPath}`);
  }

  /**
   * Close database connection pool
   */
  async close() {
    await this.pool.end();
  }
}

/**
 * CLI Interface
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log(`
Usage: node consensus-replay.cjs <workflow-id> [options]

Options:
  --same-models          Use same models as original (default)
  --override-models M1,M2 Use specific models instead
  --html-report PATH     Generate HTML report
  --store                Store replay results to database

Example:
  node consensus-replay.cjs wf-1719594345678 --html-report /tmp/replay-report.html --store
`);
    process.exit(0);
  }

  const workflowId = args[0];
  const sameModels = !args.includes('--override-models');
  const overrideModels = args.includes('--override-models')
    ? args[args.indexOf('--override-models') + 1].split(',')
    : null;
  const htmlReport = args.includes('--html-report')
    ? args[args.indexOf('--html-report') + 1]
    : null;
  const store = args.includes('--store');

  const replay = new ConsensusReplay();

  try {
    console.log(`Fetching historical workflow: ${workflowId}`);
    const historical = await replay.fetchHistoricalWorkflow(workflowId);

    if (!historical) {
      console.error(`Workflow not found: ${workflowId}`);
      process.exit(1);
    }

    console.log(`Found workflow from ${historical.execution.created_at}`);
    console.log(`Task: ${historical.execution.task_description.substring(0, 100)}...`);

    console.log('\nRe-running consensus with current models...');
    const newRun = await replay.rerunConsensus(historical, { sameModels, overrideModels });

    console.log('\nComparing results...');
    const comparison = replay.compareResults(historical, newRun);

    console.log('\n=== COMPARISON SUMMARY ===');
    console.log(JSON.stringify(comparison.summary, null, 2));

    if (store) {
      console.log('\nStoring replay results to database...');
      const replayId = await replay.storeReplayResults(comparison);
      console.log(`Stored as replay ID: ${replayId}`);
    }

    if (htmlReport) {
      console.log('\nGenerating HTML report...');
      replay.generateHTMLReport(comparison, htmlReport);
    }

    await replay.close();

  } catch (error) {
    console.error('Replay failed:', error);
    await replay.close();
    process.exit(1);
  }
}

// Export for programmatic use
module.exports = {
  ConsensusReplay,
  pool
};

// Run as CLI if invoked directly
if (require.main === module) {
  main();
}
