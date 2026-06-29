#!/usr/bin/env node

/**
 * Generate Sample Analytics Data
 *
 * Creates synthetic workflow execution data for testing analytics views
 * when no real workflow data exists yet.
 *
 * Usage: node workflows/generate-sample-data.js [count]
 */

const { WorkflowStorageAdapter } = require('../.claude/learning/workflow-storage-adapter.cjs');

const SAMPLE_COUNT = parseInt(process.argv[2]) || 50;

const MODELS = [
  'claude-opus-4',
  'claude-sonnet-4',
  'claude-haiku-4',
  'gpt-4o',
  'gemini-1.5-pro',
  'deepseek-coder-v2'
];

const WORKFLOWS = [
  'deep-research',
  'ai-pdf-deep-research',
  'ai-consensus',
  'ai-consensus-debate',
  'code-review'
];

const TASK_TYPES = [
  'research_synthesis',
  'claim_verification',
  'source_analysis',
  'consensus_building',
  'adversarial_review'
];

const STRATEGIES = [
  'parallel_search',
  'sequential_fetch',
  'adversarial_verify',
  'weighted_consensus',
  'thompson_sampling'
];

// Helper: Random number in range
function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

// Helper: Random float in range
function randomFloat(min, max) {
  return Math.random() * (max - min) + min;
}

// Helper: Random choice from array
function randomChoice(arr) {
  return arr[randomInt(0, arr.length - 1)];
}

// Helper: Random timestamp in last N days
function randomTimestamp(daysAgo) {
  const now = Date.now();
  const offset = randomInt(0, daysAgo * 24 * 60 * 60 * 1000);
  return new Date(now - offset);
}

// Generate realistic execution metadata
function generateMetadata(workflow, taskType, outcome) {
  const metadata = {
    session_id: `${workflow}_${Date.now()}_${randomInt(100000, 999999)}`,
    strategy: randomChoice(STRATEGIES)
  };

  if (workflow === 'deep-research') {
    const totalClaims = randomInt(20, 100);
    const verifiedClaims = outcome === 'success'
      ? randomInt(Math.floor(totalClaims * 0.6), totalClaims)
      : randomInt(0, Math.floor(totalClaims * 0.4));

    metadata.angles_count = 5;
    metadata.sources_count = randomInt(8, 15);
    metadata.claims_total = totalClaims;
    metadata.claims_verified = verifiedClaims;
    metadata.phases_completed = outcome === 'success' ? 5 : randomInt(1, 4);

    // Phase durations (ms)
    if (outcome === 'success') {
      metadata.phase_scope_duration_ms = randomInt(2000, 5000);
      metadata.phase_search_duration_ms = randomInt(10000, 20000);
      metadata.phase_fetch_duration_ms = randomInt(15000, 30000);
      metadata.phase_verify_duration_ms = randomInt(30000, 60000);
      metadata.phase_synthesize_duration_ms = randomInt(10000, 20000);
    }
  } else if (workflow === 'ai-pdf-deep-research') {
    metadata.pdf_pages = randomInt(10, 50);
    metadata.claims_total = randomInt(15, 40);
    metadata.claims_verified = outcome === 'success'
      ? randomInt(10, metadata.claims_total)
      : randomInt(0, 10);
  } else if (workflow.includes('consensus')) {
    metadata.voter_count = randomInt(3, 6);
    metadata.confidence_threshold = 0.7;
    metadata.iterations = randomInt(1, 3);
  }

  if (outcome === 'failure') {
    const phases = ['scope', 'search', 'fetch', 'verify', 'synthesize'];
    metadata.phase_failed = randomChoice(phases);
    metadata.error = `${metadata.phase_failed} phase timeout`;
  }

  return metadata;
}

// Generate model-specific quality characteristics
function getModelQuality(model, taskType) {
  const characteristics = {
    'claude-opus-4': { base: 0.85, variance: 0.08, costMultiplier: 3.0 },
    'claude-sonnet-4': { base: 0.78, variance: 0.10, costMultiplier: 1.0 },
    'claude-haiku-4': { base: 0.65, variance: 0.12, costMultiplier: 0.2 },
    'gpt-4o': { base: 0.82, variance: 0.09, costMultiplier: 2.5 },
    'gemini-1.5-pro': { base: 0.76, variance: 0.11, costMultiplier: 1.2 },
    'deepseek-coder-v2': { base: 0.70, variance: 0.15, costMultiplier: 0.5 }
  };

  const char = characteristics[model] || { base: 0.70, variance: 0.15, costMultiplier: 1.0 };

  // Task-specific modifiers
  let modifier = 0;
  if (taskType === 'research_synthesis' && model === 'claude-opus-4') modifier = 0.05;
  if (taskType === 'claim_verification' && model === 'gpt-4o') modifier = 0.03;
  if (taskType === 'code_review' && model === 'deepseek-coder-v2') modifier = 0.08;

  const quality = Math.max(0.3, Math.min(0.98,
    char.base + modifier + randomFloat(-char.variance, char.variance)
  ));

  return {
    quality,
    costMultiplier: char.costMultiplier
  };
}

// Generate single execution record
function generateExecution(timestampDaysAgo = 30) {
  const model = randomChoice(MODELS);
  const workflow = randomChoice(WORKFLOWS);
  const taskType = randomChoice(TASK_TYPES);

  // 85% success rate overall
  const outcome = Math.random() < 0.85 ? 'success' : 'failure';

  const { quality, costMultiplier } = getModelQuality(model, taskType);
  const qualityScore = outcome === 'success' ? quality : randomFloat(0.1, 0.4);

  // Token counts (realistic ranges)
  const inputTokens = randomInt(5000, 30000);
  const outputTokens = randomInt(1000, 8000);

  // Cost calculation (simplified)
  // Opus: $15/1M input, $75/1M output
  // Sonnet: $3/1M input, $15/1M output
  // Haiku: $0.25/1M input, $1.25/1M output
  const baseCost = (inputTokens * 3 + outputTokens * 15) / 1_000_000;
  const costUsd = baseCost * costMultiplier;

  // Duration (ms) - varies by model and task complexity
  const baseDuration = randomInt(20000, 120000);
  const durationMs = outcome === 'success' ? baseDuration : randomInt(5000, baseDuration / 2);

  const metadata = generateMetadata(workflow, taskType, outcome);

  return {
    workflow,
    model,
    task_type: taskType,
    quality_score: qualityScore,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    cost_usd: costUsd,
    duration_ms: durationMs,
    outcome,
    metadata,
    timestamp: randomTimestamp(timestampDaysAgo)
  };
}

// Main execution
(async () => {
  console.log('========================================');
  console.log('Sample Analytics Data Generator');
  console.log('========================================');
  console.log('');
  console.log(`Generating ${SAMPLE_COUNT} sample execution records...`);
  console.log('');

  const storage = new WorkflowStorageAdapter();

  try {
    await storage.connect();

    const executions = [];
    for (let i = 0; i < SAMPLE_COUNT; i++) {
      executions.push(generateExecution());
    }

    // Sort by timestamp (oldest first) for realistic data
    executions.sort((a, b) => a.timestamp - b.timestamp);

    console.log('Inserting records...');
    let successCount = 0;
    let failCount = 0;

    for (const exec of executions) {
      try {
        // Manual insert (don't trigger view refresh for each record)
        await storage.client.query(`
          INSERT INTO monitoring.execution_summary (
            model, workflow, task_type, quality_score,
            input_tokens, output_tokens, cost_usd,
            duration_ms, outcome, metadata, timestamp
          )
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        `, [
          exec.model,
          exec.workflow,
          exec.task_type,
          exec.quality_score,
          exec.input_tokens,
          exec.output_tokens,
          exec.cost_usd,
          exec.duration_ms,
          exec.outcome,
          JSON.stringify(exec.metadata),
          exec.timestamp
        ]);

        successCount++;
        if (successCount % 10 === 0) {
          process.stdout.write(`  Progress: ${successCount}/${SAMPLE_COUNT}\r`);
        }
      } catch (err) {
        failCount++;
        console.error(`\nFailed to insert record: ${err.message}`);
      }
    }

    console.log(`\n  ✓ Inserted ${successCount} records successfully`);
    if (failCount > 0) {
      console.log(`  ✗ Failed to insert ${failCount} records`);
    }

    // Refresh materialized views
    console.log('');
    console.log('Refreshing materialized views...');
    await storage.refreshViews();

    console.log('');
    console.log('========================================');
    console.log('Data Generation Complete!');
    console.log('========================================');
    console.log('');

    // Show summary statistics
    const summary = await storage.client.query(`
      SELECT
        COUNT(*) as total_executions,
        COUNT(DISTINCT workflow) as workflows,
        COUNT(DISTINCT model) as models,
        COUNT(DISTINCT task_type) as task_types,
        ROUND(AVG(quality_score)::numeric, 3) as avg_quality,
        ROUND(SUM(cost_usd)::numeric, 4) as total_cost,
        SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
      FROM monitoring.execution_summary
    `);

    const stats = summary.rows[0];
    console.log('Database Summary:');
    console.log(`  Total Executions: ${stats.total_executions}`);
    console.log(`  Workflows: ${stats.workflows}`);
    console.log(`  Models: ${stats.models}`);
    console.log(`  Task Types: ${stats.task_types}`);
    console.log(`  Avg Quality: ${stats.avg_quality}`);
    console.log(`  Total Cost: $${stats.total_cost}`);
    console.log(`  Success Rate: ${(stats.success_rate * 100).toFixed(1)}%`);
    console.log('');

    console.log('Next steps:');
    console.log('  1. View analytics: psql -h laptop-01 -U sfloess -d learning');
    console.log('  2. Test queries: bash workflows/test-analytics.sh');
    console.log('  3. Import Grafana dashboard: workflows/grafana-dashboard.json');
    console.log('');

    await storage.disconnect();
    process.exit(0);

  } catch (err) {
    console.error('\nError:', err.message);
    await storage.disconnect();
    process.exit(1);
  }
})();
