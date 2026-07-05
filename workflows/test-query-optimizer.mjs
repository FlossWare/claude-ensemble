#!/usr/bin/env node
/**
 * Test workflow for Query Optimizer integration
 *
 * Demonstrates:
 * - Optimizing queries before execution
 * - Recording execution metrics
 * - Analyzing slow queries
 * - Using Thompson Sampling to learn optimal strategies
 */

import { optimizeQuery, recordExecution, analyzeSlowQueries, optimizeAndExecute, getStats } from '../shared/query-optimizer-adapter.cjs';
import pkg from 'pg';
const { Client } = pkg;

async function testWorkflow() {
  console.log('=' .repeat(80));
  console.log('QUERY OPTIMIZER WORKFLOW TEST');
  console.log('=' .repeat(80));

  // Connect to PostgreSQL
  const client = new Client({
    host: 'aio-01',
    port: 5433,
    user: 'claude',
    database: 'learning'
  });

  await client.connect();

  // Test 1: Simple query with optimization
  console.log('\n1. SIMPLE QUERY WITH OPTIMIZATION');
  console.log('-'.repeat(80));

  const query1 = 'SELECT * FROM learning.experiences WHERE success = TRUE LIMIT 10';

  const plan1 = await optimizeQuery(query1, {
    estimated_rows: 10,
    table_size_mb: 50
  });

  console.log(`Predicted cost: ${plan1.predicted_cost_ms.toFixed(1)}ms`);
  console.log(`Strategy: ${plan1.recommended_strategy}`);

  const start1 = Date.now();
  const result1 = await client.query(query1);
  const duration1 = Date.now() - start1;

  console.log(`Actual cost: ${duration1}ms`);
  console.log(`Rows returned: ${result1.rows.length}`);

  // Record execution
  await recordExecution(query1, duration1, {
    plan_used: plan1.recommended_strategy,
    actual_rows: result1.rows.length
  });

  console.log('✓ Execution recorded');

  // Test 2: Complex JOIN query
  console.log('\n2. JOIN QUERY WITH OPTIMIZATION');
  console.log('-'.repeat(80));

  const query2 = `
    SELECT e.id, e.strategy, e.reward, sp.avg_reward
    FROM learning.experiences e
    JOIN learning.strategy_performance sp ON e.strategy = sp.strategy
    WHERE e.success = TRUE
    ORDER BY e.reward DESC
    LIMIT 10
  `;

  const plan2 = await optimizeQuery(query2, {
    estimated_rows: 100,
    table_size_mb: 50,
    index_count: 3
  });

  console.log(`Predicted cost: ${plan2.predicted_cost_ms.toFixed(1)}ms`);
  console.log(`Strategy: ${plan2.recommended_strategy}`);

  if (plan2.recommendations.length > 0) {
    console.log('Recommendations:');
    plan2.recommendations.forEach(rec => {
      console.log(`  [${rec.priority}] ${rec.message}`);
    });
  }

  const start2 = Date.now();
  const result2 = await client.query(query2);
  const duration2 = Date.now() - start2;

  console.log(`Actual cost: ${duration2}ms`);
  console.log(`Rows returned: ${result2.rows.length}`);

  await recordExecution(query2, duration2, {
    plan_used: plan2.recommended_strategy
  });

  // Test 3: Aggregation query
  console.log('\n3. AGGREGATION QUERY');
  console.log('-'.repeat(80));

  const query3 = `
    SELECT model, COUNT(*) as executions, AVG(duration_ms) as avg_duration
    FROM monitoring.execution_summary
    WHERE duration_ms > 0
    GROUP BY model
    ORDER BY avg_duration DESC
    LIMIT 10
  `;

  // Use the optimizeAndExecute helper
  const result3 = await optimizeAndExecute(
    query3,
    async () => await client.query(query3),
    {
      estimated_rows: 1000,
      table_size_mb: 200
    }
  );

  console.log(`Actual cost: ${result3.execution.durationMs}ms`);
  console.log(`Prediction accuracy: ${(result3.prediction_accuracy * 100).toFixed(1)}%`);
  console.log(`Rows returned: ${result3.execution.result.rows.length}`);

  // Analyze slow queries
  console.log('\n' + '='.repeat(80));
  console.log('SLOW QUERY ANALYSIS');
  console.log('='.repeat(80));

  const slow = await analyzeSlowQueries(5000, 30);

  console.log(`\nFound ${slow.length} slow queries (>5s):\n`);
  slow.slice(0, 5).forEach((sq, i) => {
    console.log(`${i + 1}. ${sq.workflow} / ${sq.task_type} / ${sq.model}`);
    console.log(`   Avg: ${(sq.avg_duration_ms / 1000).toFixed(1)}s, Runs: ${sq.executions}`);
    if (sq.suggestions.length > 0) {
      sq.suggestions.forEach(s => console.log(`   → ${s}`));
    }
  });

  // Get stats
  console.log('\n' + '='.repeat(80));
  console.log('OPTIMIZER STATISTICS');
  console.log('='.repeat(80));

  const stats = await getStats();

  console.log(`\nModel trained: ${stats.model_trained}`);
  console.log(`Cached queries: ${stats.cached_queries}`);
  console.log(`Execution history: ${stats.execution_history}`);

  console.log('\nStrategy Performance (Thompson Sampling):');
  Object.entries(stats.strategies)
    .sort((a, b) => b[1].confidence - a[1].confidence)
    .forEach(([strategy, perf]) => {
      console.log(`  ${strategy.padEnd(20)}: confidence=${perf.confidence.toFixed(3)} ` +
                  `(α=${perf.alpha.toFixed(1)}, β=${perf.beta.toFixed(1)})`);
    });

  console.log('\n' + '='.repeat(80));
  console.log('✓ Query optimizer test complete');
  console.log('=' .repeat(80));

  await client.end();
}

// Run test
testWorkflow().catch(console.error);
