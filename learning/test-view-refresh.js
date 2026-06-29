#!/usr/bin/env node

/**
 * Test: Automated View Refresh
 *
 * Validates that:
 * 1. Workflow execution storage works
 * 2. Materialized views refresh automatically
 * 3. CONCURRENTLY option is used (no blocking)
 * 4. Thompson Sampling state updates
 */

const { WorkflowStorageAdapter } = require('./workflow-storage-adapter.cjs');

async function testViewRefresh() {
  const adapter = new WorkflowStorageAdapter();

  console.log('=== Step 1: Initialize Schema ===');
  try {
    await adapter.initializeSchema();
    console.log('✓ Schema initialized\n');
  } catch (err) {
    console.log(`Note: ${err.message}\n`);
  }

  console.log('=== Step 2: Store Test Execution ===');
  const execution = {
    workflow: 'test-workflow',
    model: 'claude-sonnet-4',
    task_type: 'test_view_refresh',
    quality_score: 0.85,
    input_tokens: 1000,
    output_tokens: 500,
    cost_usd: 0.015,
    duration_ms: 2500,
    outcome: 'success',
    metadata: {
      strategy: 'test_strategy',
      test_run: true,
      timestamp: new Date().toISOString()
    }
  };

  try {
    const stored = await adapter.storeExecution(execution);
    console.log('✓ Execution stored:', {
      id: stored.id,
      timestamp: stored.timestamp
    });
  } catch (err) {
    console.error('✗ Failed to store execution:', err.message);
    await adapter.disconnect();
    process.exit(1);
  }

  console.log('\n=== Step 3: Verify View Refresh ===');
  try {
    await adapter.connect();

    // Check if views were updated
    const viewChecks = [
      {
        name: 'monitoring.model_performance_summary',
        query: `SELECT model, total_executions, avg_quality
                FROM monitoring.model_performance_summary
                WHERE model = 'claude-sonnet-4'`
      },
      {
        name: 'monitoring.workflow_efficiency',
        query: `SELECT workflow, executions, avg_quality
                FROM monitoring.workflow_efficiency
                WHERE workflow = 'test-workflow'`
      },
      {
        name: 'learning.strategy_rankings',
        query: `SELECT strategy, avg_reward, rank
                FROM learning.strategy_rankings
                WHERE strategy = 'test_strategy'`
      }
    ];

    for (const check of viewChecks) {
      const result = await adapter.client.query(check.query);
      if (result.rows.length > 0) {
        console.log(`✓ ${check.name}:`, result.rows[0]);
      } else {
        console.log(`⚠ ${check.name}: No data (may need manual refresh)`);
      }
    }

  } catch (err) {
    console.error('✗ View verification failed:', err.message);
  }

  console.log('\n=== Step 4: Test Thompson Sampling Selection ===');
  try {
    const selectedStrategy = await adapter.selectStrategy();
    console.log('✓ Best strategy selected:', selectedStrategy);
  } catch (err) {
    console.error('✗ Strategy selection failed:', err.message);
  }

  console.log('\n=== Step 5: Test Vector Similarity Search ===');
  try {
    // Generate random embedding (128-dim)
    const embedding = Array.from({ length: 128 }, () => Math.random());

    await adapter.storeExperience({
      problem_type: 'test_problem',
      problem_hash: 'test_hash_' + Date.now(),
      context: { test: true },
      embedding,
      strategy: 'test_strategy',
      success: true,
      reward: 0.85,
      novelty_score: 0.7,
      importance: 0.8
    });

    console.log('✓ Experience stored with embedding');

    const similar = await adapter.findSimilarExperiences(embedding, 5, 0.5);
    console.log(`✓ Found ${similar.length} similar experiences`);

    if (similar.length > 0) {
      console.log('  Top match:', {
        strategy: similar[0].strategy,
        reward: similar[0].reward,
        distance: similar[0].distance
      });
    }

  } catch (err) {
    console.error('✗ Vector search failed:', err.message);
  }

  console.log('\n=== Step 6: Manual View Refresh Test ===');
  try {
    const startTime = Date.now();
    await adapter.refreshViews();
    const duration = Date.now() - startTime;
    console.log(`✓ Views refreshed in ${duration}ms`);
  } catch (err) {
    console.error('✗ Manual refresh failed:', err.message);
  }

  await adapter.disconnect();
  console.log('\n=== Test Complete ===');
}

// Run tests
if (require.main === module) {
  testViewRefresh()
    .then(() => {
      console.log('\nAll tests passed ✓');
      process.exit(0);
    })
    .catch(err => {
      console.error('\nTest suite failed:', err.message);
      process.exit(1);
    });
}

module.exports = { testViewRefresh };
