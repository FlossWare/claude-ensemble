#!/usr/bin/env node
/**
 * Consensus Replay Demonstration
 *
 * Shows end-to-end usage:
 * 1. Find recent successful workflows
 * 2. Replay with current models
 * 3. Compare results
 * 4. Generate HTML report
 * 5. Store to database
 *
 * Usage: node consensus-replay-demo.cjs [--limit N]
 *
 * Created: 2026-06-28
 */

const { ConsensusReplay } = require('./consensus-replay.cjs');
const { Pool } = require('pg');
const path = require('path');
const fs = require('fs');

// PostgreSQL connection pool
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
});

/**
 * Find recent successful workflows for replay
 *
 * @param {number} limit - Max workflows to fetch
 * @returns {Promise<Array>} Workflow IDs
 */
async function findRecentWorkflows(limit = 5) {
  const client = await pool.connect();
  try {
    const result = await client.query(
      `SELECT workflow_id, task_description, created_at
       FROM workflow.executions
       WHERE outcome = 'success'
       AND total_workers > 0
       ORDER BY created_at DESC
       LIMIT $1`,
      [limit]
    );

    return result.rows;
  } finally {
    client.release();
  }
}

/**
 * Replay a single workflow and generate report
 *
 * @param {string} workflowId - Workflow ID to replay
 * @param {ConsensusReplay} replay - Replay instance
 * @param {string} reportDir - Report output directory
 * @returns {Promise<Object|null>} Comparison result or null if failed
 */
async function replaySingleWorkflow(workflowId, replay, reportDir) {
  console.log(`\n${'='.repeat(80)}`);
  console.log(`Replaying: ${workflowId}`);
  console.log('='.repeat(80));

  try {
    // Fetch historical workflow
    const historical = await replay.fetchHistoricalWorkflow(workflowId);

    if (!historical) {
      console.log('❌ Workflow not found');
      return null;
    }

    console.log(`\n📋 Original Workflow:`);
    console.log(`   Created: ${historical.execution.created_at}`);
    console.log(`   Task: ${historical.execution.task_description.substring(0, 100)}...`);
    console.log(`   Workers: ${historical.workers.length}`);
    console.log(`   Arbiters: ${historical.arbiters.length}`);

    if (historical.workers.length === 0) {
      console.log('⏭️  Skipping (no workers to replay)');
      return null;
    }

    // Show original results
    console.log(`\n📊 Original Results:`);
    historical.workers.forEach((w, i) => {
      console.log(`   Worker ${i + 1} (${w.model}): confidence=${w.confidence.toFixed(3)}, duration=${w.duration_ms}ms`);
    });
    if (historical.arbiters.length > 0) {
      console.log(`   Arbiter: confidence=${historical.arbiters[0].confidence.toFixed(3)}`);
    }

    // Re-run with current models (mock execution for demo)
    console.log(`\n🔄 Re-running with current models...`);

    // For demo purposes, simulate improvement
    const newRun = simulateReplay(historical);

    // Compare results
    const comparison = replay.compareResults(historical, newRun);

    console.log(`\n📈 Comparison Results:`);
    console.log(`   Verdict: ${comparison.summary.verdict}`);
    console.log(`   Avg Confidence Delta: ${comparison.summary.avg_confidence_delta}`);
    console.log(`   Arbiter Confidence Delta: ${comparison.summary.arbiter_confidence_delta}`);
    console.log(`   Total Cost Delta: $${comparison.summary.total_cost_delta}`);

    // Generate HTML report
    const reportPath = path.join(reportDir, `${workflowId}.html`);
    replay.generateHTMLReport(comparison, reportPath);
    console.log(`\n📄 HTML report: ${reportPath}`);

    // Store to database
    const replayId = await replay.storeReplayResults(comparison);
    console.log(`💾 Stored to database (ID: ${replayId})`);

    return comparison;

  } catch (error) {
    console.error(`❌ Replay failed: ${error.message}`);
    return null;
  }
}

/**
 * Simulate replay execution (for demo purposes)
 * In production, this would call _executeWorkersParallel
 *
 * @param {Object} historical - Historical workflow data
 * @returns {Object} Simulated new execution
 */
function simulateReplay(historical) {
  // Simulate slight improvement (5-10% confidence boost, 10-20% speed improvement)
  const workers = historical.workers.map(w => ({
    worker_id: w.worker_id,
    model: w.model,
    task_assigned: w.task_assigned,
    result: w.result,
    confidence: Math.min(0.99, w.confidence + (Math.random() * 0.1 + 0.05)),
    duration_ms: Math.floor(w.duration_ms * (0.8 + Math.random() * 0.1)),
    input_tokens: w.input_tokens,
    output_tokens: w.output_tokens,
    cost_usd: w.cost_usd * 0.95, // Simulate 5% cost reduction
    outcome: 'success',
    created_at: new Date().toISOString()
  }));

  const arbiter = historical.arbiters.length > 0 ? {
    arbiter_model: historical.arbiters[0].arbiter_model,
    decision: historical.arbiters[0].decision,
    confidence: Math.min(0.99, historical.arbiters[0].confidence + (Math.random() * 0.15 + 0.05)),
    duration_ms: Math.floor(historical.arbiters[0].duration_ms * 0.85),
    input_tokens: historical.arbiters[0].input_tokens,
    output_tokens: historical.arbiters[0].output_tokens,
    cost_usd: historical.arbiters[0].cost_usd * 0.95,
    created_at: new Date().toISOString()
  } : {
    arbiter_model: 'opus',
    decision: 'Simulated decision',
    confidence: 0.85,
    duration_ms: 3000,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    created_at: new Date().toISOString()
  };

  return {
    workers,
    arbiter,
    metadata: {
      replayed_at: new Date().toISOString(),
      original_workflow_id: historical.execution.workflow_id,
      models_used: workers.map(w => w.model),
      simulated: true // Mark as simulated for demo
    }
  };
}

/**
 * Generate summary statistics across all replays
 *
 * @param {Array} comparisons - Array of comparison results
 */
function generateSummaryStats(comparisons) {
  console.log(`\n${'='.repeat(80)}`);
  console.log('SUMMARY STATISTICS');
  console.log('='.repeat(80));

  const validComparisons = comparisons.filter(c => c !== null);

  if (validComparisons.length === 0) {
    console.log('No valid comparisons to summarize');
    return;
  }

  // Count verdicts
  const verdictCounts = validComparisons.reduce((acc, c) => {
    acc[c.summary.verdict] = (acc[c.summary.verdict] || 0) + 1;
    return acc;
  }, {});

  console.log(`\n📊 Verdicts:`);
  Object.entries(verdictCounts).forEach(([verdict, count]) => {
    const pct = (count / validComparisons.length * 100).toFixed(1);
    console.log(`   ${verdict}: ${count} (${pct}%)`);
  });

  // Average metrics
  const avgConfidenceDelta = validComparisons.reduce(
    (sum, c) => sum + parseFloat(c.summary.avg_confidence_delta), 0
  ) / validComparisons.length;

  const avgArbiterDelta = validComparisons.reduce(
    (sum, c) => sum + parseFloat(c.summary.arbiter_confidence_delta), 0
  ) / validComparisons.length;

  const totalCostDelta = validComparisons.reduce(
    (sum, c) => sum + parseFloat(c.summary.total_cost_delta), 0
  );

  console.log(`\n📈 Averages:`);
  console.log(`   Avg Confidence Delta: ${avgConfidenceDelta.toFixed(4)}`);
  console.log(`   Arbiter Confidence Delta: ${avgArbiterDelta.toFixed(4)}`);
  console.log(`   Total Cost Delta: $${totalCostDelta.toFixed(4)}`);

  // Overall verdict
  if (avgConfidenceDelta > 0.05 && avgArbiterDelta > 0.05) {
    console.log(`\n✅ Overall: SIGNIFICANT IMPROVEMENT across replays`);
  } else if (avgConfidenceDelta > 0.03) {
    console.log(`\n✅ Overall: MODERATE IMPROVEMENT across replays`);
  } else if (avgConfidenceDelta < -0.05) {
    console.log(`\n⚠️  Overall: DEGRADATION detected across replays`);
  } else {
    console.log(`\n➡️  Overall: NO SIGNIFICANT CHANGE`);
  }
}

/**
 * Main demonstration
 */
async function main() {
  const args = process.argv.slice(2);
  const limitIdx = args.indexOf('--limit');
  const limit = limitIdx >= 0 ? parseInt(args[limitIdx + 1]) : 3;

  console.log('='.repeat(80));
  console.log('CONSENSUS REPLAY DEMONSTRATION');
  console.log('='.repeat(80));
  console.log(`\nReplaying up to ${limit} recent workflows...`);

  const replay = new ConsensusReplay();
  const reportDir = '/tmp/consensus-replay-reports';

  // Create report directory
  if (!fs.existsSync(reportDir)) {
    fs.mkdirSync(reportDir, { recursive: true });
  }

  try {
    // Find recent workflows
    console.log(`\n🔍 Finding recent successful workflows...`);
    const workflows = await findRecentWorkflows(limit);

    if (workflows.length === 0) {
      console.log('No workflows found to replay');
      return;
    }

    console.log(`\nFound ${workflows.length} workflows:`);
    workflows.forEach((w, i) => {
      console.log(`   ${i + 1}. ${w.workflow_id} - ${w.task_description.substring(0, 60)}...`);
    });

    // Replay each workflow
    const comparisons = [];
    for (const workflow of workflows) {
      const comparison = await replaySingleWorkflow(workflow.workflow_id, replay, reportDir);
      if (comparison) {
        comparisons.push(comparison);
      }
    }

    // Generate summary
    generateSummaryStats(comparisons);

    console.log(`\n📁 All reports saved to: ${reportDir}`);
    console.log(`\n✅ Demo complete!`);

  } catch (error) {
    console.error('\n❌ Demo failed:', error);
  } finally {
    await replay.close();
    await pool.end();
  }
}

// Run demo
if (require.main === module) {
  main().catch(console.error);
}

module.exports = { replaySingleWorkflow, simulateReplay };
