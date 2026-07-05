#!/usr/bin/env node
/**
 * Measure current query performance for workflow-predictor.js
 *
 * Tests all major queries to identify bottlenecks
 */

import { Pool } from 'pg';

const pool = new Pool({
  host: 'aio-01',
  port: 5433,
  database: 'learning',
  user: process.env.USER || 'claude',
  password: process.env.PGPASSWORD,
});

async function measureQuery(name, queryFn) {
  const start = Date.now();
  try {
    const result = await queryFn();
    const duration = Date.now() - start;
    console.log(`✓ ${name}: ${duration}ms (${result.rows?.length || 0} rows)`);
    return { name, duration, rows: result.rows?.length || 0, success: true };
  } catch (err) {
    const duration = Date.now() - start;
    console.log(`✗ ${name}: ${duration}ms - ERROR: ${err.message}`);
    return { name, duration, error: err.message, success: false };
  }
}

async function main() {
  console.log('Measuring query performance...\n');

  const results = [];

  // Query 1: Historical token usage (predictCost)
  results.push(await measureQuery(
    'Historical token usage (predictCost)',
    () => pool.query(`
      SELECT AVG(wr.input_tokens) as avg_input, AVG(wr.output_tokens) as avg_output
      FROM workflow.worker_results wr
      JOIN workflow.executions we ON wr.workflow_execution_id = we.id
      WHERE we.outcome = 'success'
      AND we.created_at > NOW() - INTERVAL '30 days'
    `)
  ));

  // Query 2: Similar workflows (predictDuration)
  results.push(await measureQuery(
    'Similar workflows (predictDuration)',
    () => pool.query(`
      SELECT AVG(total_duration_ms) as avg_duration
      FROM workflow.executions
      WHERE outcome = 'success'
      AND total_workers = $1
      AND created_at > NOW() - INTERVAL '30 days'
      LIMIT 100
    `, [5])
  ));

  // Query 3: Historical quality (predictQuality)
  results.push(await measureQuery(
    'Historical quality (predictQuality)',
    () => pool.query(`
      SELECT AVG(confidence) as avg_quality
      FROM workflow.arbiter_decisions
      WHERE created_at > NOW() - INTERVAL '30 days'
    `)
  ));

  // Query 4: Success rate (predictSuccess)
  results.push(await measureQuery(
    'Success rate (predictSuccess)',
    () => pool.query(`
      SELECT
        COUNT(*) FILTER (WHERE outcome = 'success') * 1.0 / NULLIF(COUNT(*), 0) as success_rate
      FROM workflow.executions
      WHERE created_at > NOW() - INTERVAL '30 days'
    `)
  ));

  // Query 5: Circuit breakers (predictSuccess)
  results.push(await measureQuery(
    'Circuit breakers (predictSuccess)',
    () => pool.query(`
      SELECT COUNT(*) as open_breakers
      FROM monitoring.circuit_breaker_events
      WHERE event = 'open'
      AND created_at > NOW() - INTERVAL '5 minutes'
    `)
  ));

  // Query 6: Model performance (predictBestModel)
  results.push(await measureQuery(
    'Model performance (predictBestModel)',
    () => pool.query(`
      SELECT model, AVG(confidence) as avg_quality, COUNT(*) as uses
      FROM workflow.worker_results
      WHERE outcome = 'success'
      AND created_at > NOW() - INTERVAL '30 days'
      GROUP BY model
      ORDER BY avg_quality DESC, uses DESC
      LIMIT 1
    `)
  ));

  // Query 7: Memory usage prediction (SLOW - 8.1s reported)
  results.push(await measureQuery(
    'Memory usage prediction (mlPredictResourceUsage fallback)',
    () => pool.query(`
      SELECT
        AVG(input_tokens + output_tokens) as avg_tokens,
        COUNT(*) as sample_size
      FROM workflow.worker_results
      WHERE created_at > NOW() - INTERVAL '30 days'
      AND outcome = 'success'
    `)
  ));

  // Query 8: Bug prediction (SLOW - 7.0s reported)
  results.push(await measureQuery(
    'Bug prediction (mlPredictBugRisk fallback)',
    () => pool.query(`
      SELECT
        COUNT(*) FILTER (WHERE outcome = 'error') * 1.0 / NULLIF(COUNT(*), 0) as error_rate,
        AVG(CASE WHEN outcome = 'error' THEN 1 ELSE 0 END) as bug_prob
      FROM monitoring.execution_summary
      WHERE timestamp > NOW() - INTERVAL '30 days'
      AND task_type LIKE '%code%'
      LIMIT 1000
    `)
  ));

  // Query 9: Prediction accuracy stats (getPredictionStats)
  results.push(await measureQuery(
    'Prediction accuracy stats (getPredictionStats)',
    () => pool.query(`
      SELECT
        COUNT(*) as total_predictions,
        AVG(prediction_error_percent) as avg_prediction_error,
        AVG(ABS(predicted_cost_usd - actual_cost_usd) / NULLIF(predicted_cost_usd, 0) * 100) as avg_cost_error,
        AVG(ABS(predicted_duration_ms - actual_duration_ms) / NULLIF(predicted_duration_ms, 0) * 100) as avg_duration_error
      FROM monitoring.prediction_accuracy
      WHERE created_at > NOW() - INTERVAL '30 days'
    `)
  ));

  console.log('\n' + '='.repeat(80));
  console.log('SUMMARY');
  console.log('='.repeat(80));

  const successful = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);
  const total = successful.reduce((sum, r) => sum + r.duration, 0);
  const slow = successful.filter(r => r.duration > 1000);

  console.log(`Total queries: ${results.length}`);
  console.log(`Successful: ${successful.length}`);
  console.log(`Failed: ${failed.length}`);
  console.log(`Total time: ${total}ms (${(total / 1000).toFixed(1)}s)`);
  console.log(`Avg time: ${(total / successful.length).toFixed(0)}ms`);

  if (slow.length > 0) {
    console.log(`\nSLOW QUERIES (>1s):`);
    slow.forEach(r => {
      console.log(`  ${r.name}: ${r.duration}ms`);
    });
  }

  if (failed.length > 0) {
    console.log(`\nFAILED QUERIES:`);
    failed.forEach(r => {
      console.log(`  ${r.name}: ${r.error}`);
    });
  }

  await pool.end();
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
