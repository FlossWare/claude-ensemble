#!/usr/bin/env node
/**
 * Model Regression Monitor - Automated weekly replay analysis
 *
 * Runs consensus-replay on representative workflows to detect
 * model performance changes over time using STATISTICAL TESTING.
 *
 * Usage:
 *   node tools/model_regression_monitor.js [--weeks 4] [--html /tmp/report.html] [--samples 5]
 *
 * What it does:
 * 1. Queries workflow.executions for high-quality consensus workflows
 * 2. Selects representative samples (by workflow type)
 * 3. Re-runs them with current model weights (5 samples per workflow)
 * 4. Performs statistical testing (Welch's t-test + bootstrap CI)
 * 5. Generates comparison report with p-values and effect sizes
 * 6. Stores results in workflow.replays table
 *
 * Statistical Testing:
 * - Uses experiment-manager.cjs integration via ConsensusReplay.generateStatisticalVerdict()
 * - Collects baseline confidences from previous replays (workflow.replays table)
 * - Collects treatment confidences from new runs (N=5 by default)
 * - Falls back to single comparison if <3 historical runs available
 *
 * Integration:
 * - Run via cron weekly: 0 2 * * 0 (Sundays at 2am)
 * - Alerts on DEGRADATION verdicts (p < 0.05, negative effect)
 * - Feeds into performance_dashboard.py
 */

const { ConsensusReplay } = require('../shared/consensus-replay.cjs');
const { Pool } = require('pg');
const path = require('path');
const fs = require('fs');

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || 'claude',
  password: process.env.PGPASSWORD,
});

/**
 * Select representative workflows for regression testing
 *
 * Strategy:
 * - One workflow per workflow_name (diversity)
 * - Only workflows with arbiter decisions (consensus workflows)
 * - Minimum quality threshold (exclude failures)
 * - Recency bias (last N weeks)
 */
async function selectRepresentativeWorkflows(weeks = 4, limit = 10) {
  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT DISTINCT ON (workflow_name)
        workflow_id,
        workflow_name,
        task_description,
        created_at,
        total_workers,
        outcome
      FROM workflow.executions
      WHERE
        created_at > NOW() - INTERVAL '${weeks} weeks'
        AND outcome = 'success'
        AND total_workers > 1
        AND EXISTS (
          SELECT 1 FROM workflow.arbiter_decisions
          WHERE workflow_execution_id = workflow.executions.id
        )
      ORDER BY workflow_name, created_at DESC
      LIMIT ${limit}
    `);

    return result.rows;
  } finally {
    client.release();
  }
}

/**
 * Run regression analysis on selected workflows
 */
async function runRegressionAnalysis(workflows, options = {}) {
  const { htmlReportDir = '/tmp/consensus-replay-reports', samples = 5 } = options;

  // Ensure report directory exists
  if (!fs.existsSync(htmlReportDir)) {
    fs.mkdirSync(htmlReportDir, { recursive: true });
  }

  const replay = new ConsensusReplay();
  const results = [];

  for (const workflow of workflows) {
    console.log(`\n=== Replaying: ${workflow.workflow_name} (${workflow.workflow_id}) ===`);
    console.log(`Task: ${workflow.task_description.substring(0, 100)}...`);

    try {
      // Fetch historical data
      const historical = await replay.fetchHistoricalWorkflow(workflow.workflow_id);
      if (!historical) {
        console.error(`  ⚠ Workflow not found: ${workflow.workflow_id}`);
        continue;
      }

      // Collect baseline confidence scores (from historical runs with same workflow_id)
      const baselineConfidences = await fetchHistoricalConfidences(workflow.workflow_id, samples);

      // If not enough historical runs, fall back to single comparison
      if (baselineConfidences.length < 3) {
        console.log(`  ⚠ Only ${baselineConfidences.length} historical runs - using single comparison`);

        // Re-run with current models (single run)
        console.log(`  Running with ${historical.workers.length} workers...`);
        const newRun = await replay.rerunConsensus(historical, { sameModels: true });

        // Compare results (legacy method)
        const comparison = replay.compareResults(historical, newRun);

        console.log(`  Verdict: ${comparison.summary.verdict}`);
        console.log(`  Confidence Δ: ${comparison.summary.arbiter_confidence_delta}`);
        console.log(`  Cost Δ: $${comparison.summary.total_cost_delta}`);

        // Store results
        const replayId = await replay.storeReplayResults(comparison);
        console.log(`  ✓ Stored as replay ID: ${replayId}`);

        // Generate HTML report
        const htmlPath = path.join(htmlReportDir, `${workflow.workflow_id}_${Date.now()}.html`);
        replay.generateHTMLReport(comparison, htmlPath);
        console.log(`  ✓ HTML report: ${htmlPath}`);

        results.push({
          workflow_id: workflow.workflow_id,
          workflow_name: workflow.workflow_name,
          verdict: comparison.summary.verdict,
          confidence_delta: parseFloat(comparison.summary.arbiter_confidence_delta),
          cost_delta: parseFloat(comparison.summary.total_cost_delta),
          html_report: htmlPath,
          replay_id: replayId,
          method: 'single_comparison'
        });

        continue;
      }

      // Collect treatment confidence scores (multiple new runs)
      console.log(`  Running ${samples} replays with ${historical.workers.length} workers...`);
      const treatmentConfidences = [];
      const newRuns = [];

      for (let i = 0; i < samples; i++) {
        const newRun = await replay.rerunConsensus(historical, { sameModels: true });
        newRuns.push(newRun);
        treatmentConfidences.push(newRun.arbiter.confidence);
        console.log(`    Run ${i + 1}/${samples}: confidence = ${newRun.arbiter.confidence.toFixed(3)}`);
      }

      // Statistical comparison using experiment-manager integration
      const statisticalResult = replay.generateStatisticalVerdict(
        baselineConfidences,
        treatmentConfidences,
        { alpha: 0.05, min_improvement_pct: 3 }
      );

      console.log(`  Verdict: ${statisticalResult.verdict}`);
      console.log(`  Baseline mean: ${statisticalResult.statistics.baseline_mean.toFixed(3)}`);
      console.log(`  Treatment mean: ${statisticalResult.statistics.treatment_mean.toFixed(3)}`);
      console.log(`  Improvement: ${statisticalResult.statistics.improvement_pct.toFixed(1)}%`);
      console.log(`  p-value: ${statisticalResult.statistics.p_value.toFixed(4)}`);
      console.log(`  Effect size: ${statisticalResult.statistics.effect_size.toFixed(3)}`);

      // Store results for each replay run
      const replayIds = [];
      for (let i = 0; i < newRuns.length; i++) {
        const comparison = replay.compareResults(historical, newRuns[i]);
        const replayId = await replay.storeReplayResults(comparison);
        replayIds.push(replayId);
      }
      console.log(`  ✓ Stored ${replayIds.length} replay runs`);

      // Generate HTML report (using first run as representative)
      const firstComparison = replay.compareResults(historical, newRuns[0]);
      const htmlPath = path.join(htmlReportDir, `${workflow.workflow_id}_${Date.now()}.html`);
      replay.generateHTMLReport(firstComparison, htmlPath);
      console.log(`  ✓ HTML report: ${htmlPath}`);

      // Calculate cost delta (sum across all runs)
      const totalCostDelta = newRuns.reduce((sum, run) => {
        return sum + (run.total_cost - historical.total_cost);
      }, 0);

      results.push({
        workflow_id: workflow.workflow_id,
        workflow_name: workflow.workflow_name,
        verdict: statisticalResult.verdict,
        confidence_delta: statisticalResult.statistics.improvement_pct / 100,
        cost_delta: totalCostDelta,
        html_report: htmlPath,
        replay_ids: replayIds,
        method: 'statistical',
        statistics: statisticalResult.statistics,
        sample_size: samples
      });

    } catch (error) {
      console.error(`  ✗ Failed to replay ${workflow.workflow_id}:`, error.message);
      results.push({
        workflow_id: workflow.workflow_id,
        workflow_name: workflow.workflow_name,
        verdict: 'ERROR',
        error: error.message
      });
    }
  }

  await replay.close();
  return results;
}

/**
 * Fetch historical confidence scores for a workflow
 *
 * Queries workflow.replays table for previous runs of the same workflow_id
 * to establish a baseline distribution.
 *
 * @param {string} workflowId - Original workflow ID
 * @param {number} limit - Maximum number of historical runs to fetch
 * @returns {Promise<number[]>} Array of confidence scores
 */
async function fetchHistoricalConfidences(workflowId, limit = 5) {
  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT arbiter_new_confidence
      FROM workflow.replays
      WHERE original_workflow_id = $1
        AND arbiter_new_confidence IS NOT NULL
      ORDER BY created_at DESC
      LIMIT $2
    `, [workflowId, limit]);

    return result.rows.map(row => parseFloat(row.arbiter_new_confidence));
  } finally {
    client.release();
  }
}

/**
 * Generate summary report
 */
function generateSummaryReport(results) {
  const verdictCounts = results.reduce((acc, r) => {
    acc[r.verdict] = (acc[r.verdict] || 0) + 1;
    return acc;
  }, {});

  const avgConfidenceDelta = results
    .filter(r => r.confidence_delta !== undefined)
    .reduce((sum, r) => sum + r.confidence_delta, 0) / results.length;

  const avgCostDelta = results
    .filter(r => r.cost_delta !== undefined)
    .reduce((sum, r) => sum + r.cost_delta, 0) / results.length;

  const statisticalCount = results.filter(r => r.method === 'statistical').length;
  const singleCount = results.filter(r => r.method === 'single_comparison').length;

  console.log('\n' + '='.repeat(60));
  console.log('REGRESSION ANALYSIS SUMMARY');
  console.log('='.repeat(60));
  console.log(`Total workflows analyzed: ${results.length}`);
  console.log(`Statistical testing: ${statisticalCount} workflows`);
  console.log(`Single comparison: ${singleCount} workflows (insufficient historical data)`);
  console.log(`\nVerdict breakdown:`);
  Object.entries(verdictCounts).forEach(([verdict, count]) => {
    console.log(`  ${verdict}: ${count}`);
  });
  console.log(`\nAverage confidence delta: ${avgConfidenceDelta.toFixed(3)}`);
  console.log(`Average cost delta: $${avgCostDelta.toFixed(4)}`);

  // Alert on degradations
  const degradations = results.filter(r => r.verdict === 'DEGRADATION');
  if (degradations.length > 0) {
    console.log('\n⚠ ALERT: Model degradation detected in:');
    degradations.forEach(d => {
      console.log(`  - ${d.workflow_name} (${d.workflow_id})`);
      if (d.method === 'statistical') {
        console.log(`    Improvement: ${d.statistics?.improvement_pct?.toFixed(1) || 'N/A'}%`);
        console.log(`    p-value: ${d.statistics?.p_value?.toFixed(4) || 'N/A'}`);
        console.log(`    Effect size: ${d.statistics?.effect_size?.toFixed(3) || 'N/A'}`);
      } else {
        console.log(`    Confidence Δ: ${d.confidence_delta?.toFixed(3) || 'N/A'}`);
      }
      console.log(`    Report: ${d.html_report || 'N/A'}`);
    });
  }

  // Highlight improvements
  const improvements = results.filter(r =>
    r.verdict === 'SIGNIFICANT_IMPROVEMENT' || r.verdict === 'MODERATE_IMPROVEMENT'
  );
  if (improvements.length > 0) {
    console.log('\n✓ Model improvements detected in:');
    improvements.forEach(i => {
      console.log(`  - ${i.workflow_name} (${i.workflow_id})`);
      if (i.method === 'statistical') {
        console.log(`    Improvement: ${i.statistics?.improvement_pct?.toFixed(1) || 'N/A'}%`);
        console.log(`    p-value: ${i.statistics?.p_value?.toFixed(4) || 'N/A'}`);
        console.log(`    Effect size: ${i.statistics?.effect_size?.toFixed(3) || 'N/A'}`);
      } else {
        console.log(`    Confidence Δ: ${i.confidence_delta?.toFixed(3) || 'N/A'}`);
      }
    });
  }

  console.log('='.repeat(60) + '\n');

  return {
    total: results.length,
    verdicts: verdictCounts,
    avg_confidence_delta: avgConfidenceDelta,
    avg_cost_delta: avgCostDelta,
    degradations,
    improvements,
    statistical_count: statisticalCount,
    single_count: singleCount
  };
}

/**
 * Main entry point
 */
async function main() {
  const args = process.argv.slice(2);

  // Parse arguments
  let weeks = 4;
  let htmlDir = '/tmp/consensus-replay-reports';
  let samples = 5;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--weeks' && args[i + 1]) {
      weeks = parseInt(args[i + 1]);
    }
    if (args[i] === '--html' && args[i + 1]) {
      htmlDir = args[i + 1];
    }
    if (args[i] === '--samples' && args[i + 1]) {
      samples = parseInt(args[i + 1]);
    }
  }

  console.log('Model Regression Monitor');
  console.log(`Analyzing workflows from the last ${weeks} weeks`);
  console.log(`Statistical testing: ${samples} samples per workflow\n`);

  try {
    // Select representative workflows
    const workflows = await selectRepresentativeWorkflows(weeks);
    console.log(`Selected ${workflows.length} representative workflows for analysis`);

    if (workflows.length === 0) {
      console.log('No workflows found matching criteria');
      await pool.end();
      return;
    }

    // Run regression analysis
    const results = await runRegressionAnalysis(workflows, {
      htmlReportDir: htmlDir,
      samples: samples
    });

    // Generate summary
    const summary = generateSummaryReport(results);

    // Exit with error code if degradations detected
    if (summary.degradations.length > 0) {
      process.exit(1);
    }

  } catch (error) {
    console.error('Regression analysis failed:', error);
    await pool.end();
    process.exit(1);
  }

  await pool.end();
}

// Run if invoked directly
if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = {
  selectRepresentativeWorkflows,
  runRegressionAnalysis,
  generateSummaryReport
};
