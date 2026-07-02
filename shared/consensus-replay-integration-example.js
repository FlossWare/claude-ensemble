/**
 * Consensus Replay Integration Examples
 *
 * Shows how to use consensus-replay in your workflows and scripts.
 */

// Example 1: Using the CLI wrapper
// ----------------------------------
// The easiest way to replay workflows

/*
# List available workflows
bin/replay-consensus --list --limit 20

# Replay a specific workflow
bin/replay-consensus orchestrator-1782851258 --html-report /tmp/replay.html --store

# Replay latest successful workflow
bin/replay-consensus --latest --store

# Batch replay all workflows from last week
bin/replay-consensus --batch-recent --days 7 --store
*/

// Example 2: Programmatic API from workflow-completion-hook
// ----------------------------------------------------------
// Replay workflows from within your code

const { replayWorkflow, getReplayHistory } = require('./workflow-completion-hook');

async function example2() {
  // Replay a specific workflow
  const comparison = await replayWorkflow('orchestrator-1782851258', {
    sameModels: true,
    store: true
  });

  console.log('Verdict:', comparison.summary.verdict);
  console.log('Confidence Delta:', comparison.summary.avg_confidence_delta);

  // Get replay history for this workflow
  const history = await getReplayHistory('orchestrator-1782851258');
  console.log('Replay count:', history.length);
  console.log('Latest verdict:', history[0]?.verdict);
}

// Example 3: Direct ConsensusReplay class
// ----------------------------------------
// Full control over replay process

const { ConsensusReplay } = require('./consensus-replay.cjs');

async function example3() {
  const replay = new ConsensusReplay();

  try {
    // Fetch historical workflow
    const historical = await replay.fetchHistoricalWorkflow('orchestrator-1782851258');

    // Re-run with different models
    const newRun = await replay.rerunConsensus(historical, {
      overrideModels: ['opus', 'sonnet', 'haiku', 'cerebras-120b'] // Test different config
    });

    // Compare results
    const comparison = replay.compareResults(historical, newRun);

    // Generate HTML report
    replay.generateHTMLReport(comparison, '/tmp/custom-replay.html');

    // Store to database
    await replay.storeReplayResults(comparison);

    console.log('Replay complete:', comparison.summary.verdict);

  } finally {
    await replay.close();
  }
}

// Example 4: Automated nightly replay
// ------------------------------------
// Monitor model quality over time

async function example4_nightlyReplay() {
  const { ConsensusReplay } = require('./consensus-replay.cjs');
  const replay = new ConsensusReplay();

  try {
    // Get all successful workflows from last 7 days
    const result = await replay.pool.query(`
      SELECT workflow_id
      FROM workflow.executions
      WHERE created_at > NOW() - INTERVAL '7 days'
        AND outcome = 'success'
        AND total_workers > 0
      ORDER BY created_at DESC
      LIMIT 10
    `);

    for (const row of result.rows) {
      const workflowId = row.workflow_id;

      try {
        const historical = await replay.fetchHistoricalWorkflow(workflowId);
        const newRun = await replay.rerunConsensus(historical, { sameModels: true });
        const comparison = replay.compareResults(historical, newRun);

        // Store results
        await replay.storeReplayResults(comparison);

        console.log(`${workflowId}: ${comparison.summary.verdict}`);

      } catch (error) {
        console.error(`Failed to replay ${workflowId}:`, error.message);
      }
    }

  } finally {
    await replay.close();
  }
}

// Example 5: Integration with consensus-engine
// ---------------------------------------------
// Replay after model updates to measure improvements

const { multiModelReview } = require('./consensus-engine');

async function example5_testModelUpdate() {
  const testPrompt = 'Analyze this code for security vulnerabilities';
  const schema = {
    type: 'object',
    properties: {
      vulnerabilities: { type: 'array' },
      confidence: { type: 'number' }
    }
  };

  // Run current consensus
  const currentResult = await multiModelReview(testPrompt, schema, {
    workers: ['opus', 'sonnet', 'haiku', 'cerebras-120b'],
    strategy: 'rotating'
  });

  console.log('Current arbiter confidence:', currentResult.arbiter?.confidence);

  // Later, after model updates, replay historical workflows
  // to measure if quality improved
  const { replayWorkflow } = require('./workflow-completion-hook');

  // Replay recent consensus workflows
  const recentWorkflows = ['wf-001', 'wf-002', 'wf-003'];
  for (const wfId of recentWorkflows) {
    const comparison = await replayWorkflow(wfId, { store: true });
    console.log(`${wfId}: ${comparison.summary.verdict} (Δ${comparison.summary.avg_confidence_delta})`);
  }
}

// Example 6: Query replay trends
// -------------------------------
// Analyze model improvements over time

async function example6_trendAnalysis() {
  const { ConsensusReplay } = require('./consensus-replay.cjs');
  const replay = new ConsensusReplay();

  try {
    // Find workflows with significant improvement
    const improvements = await replay.pool.query(`
      SELECT
        original_workflow_id,
        avg_confidence_delta,
        arbiter_confidence_delta,
        verdict,
        replayed_at
      FROM workflow.replays
      WHERE verdict IN ('SIGNIFICANT_IMPROVEMENT', 'MODERATE_IMPROVEMENT')
      ORDER BY avg_confidence_delta DESC
      LIMIT 10
    `);

    console.log('Top Improvements:');
    for (const row of improvements.rows) {
      console.log(
        `${row.original_workflow_id}: +${row.avg_confidence_delta} (${row.verdict})`
      );
    }

    // Track quality trends over time
    const trends = await replay.pool.query(`
      SELECT
        DATE(replayed_at) as replay_date,
        AVG(avg_confidence_delta) as avg_improvement,
        COUNT(*) as total_replays
      FROM workflow.replays
      GROUP BY DATE(replayed_at)
      ORDER BY replay_date DESC
      LIMIT 30
    `);

    console.log('\nDaily Trends:');
    for (const row of trends.rows) {
      console.log(
        `${row.replay_date}: Avg Δ${row.avg_improvement?.toFixed(3) || '0.000'} (${row.total_replays} replays)`
      );
    }

  } finally {
    await replay.close();
  }
}

// Example 7: Automated cron job
// ------------------------------
// Add to crontab for nightly replays

/*
#!/bin/bash
# /home/sfloess/bin/nightly-consensus-replay.sh

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Replay all workflows from last 7 days
bin/replay-consensus --batch-recent --days 7 --store >> /tmp/nightly-replay.log 2>&1

# Generate summary report
psql -h aio-01 -p 5433 -U sfloess -d learning -c "
  SELECT verdict, COUNT(*) as count
  FROM workflow.replays
  WHERE replayed_at > NOW() - INTERVAL '1 day'
  GROUP BY verdict
  ORDER BY count DESC
" >> /tmp/nightly-replay.log 2>&1

# Crontab entry:
# 0 2 * * * /home/sfloess/bin/nightly-consensus-replay.sh
*/

module.exports = {
  example2,
  example3,
  example4_nightlyReplay,
  example5_testModelUpdate,
  example6_trendAnalysis
};
