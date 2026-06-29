// Test suite for ai-performance-monitor.js
// Run with: node ai-performance-monitor.test.js

import monitor from './ai-performance-monitor.js'

// Test helper
function assert(condition, message) {
  if (!condition) {
    console.error(`FAIL: ${message}`)
    process.exit(1)
  }
  console.log(`PASS: ${message}`)
}

async function runTests() {
  console.log('Starting ai-performance-monitor tests...\n')

  // Test 1: Reset data
  console.log('Test 1: Reset data')
  let result = await monitor({ action: 'reset' })
  assert(result.reset === true, 'Reset returns true')
  assert(result.new_session_id, 'New session ID generated')
  console.log()

  // Test 2: Track a single call
  console.log('Test 2: Track a single call')
  result = await monitor({
    action: 'track',
    model: 'opus',
    workflow_id: 'test-run-1',
    task_type: 'testing',
    latency_ms: 2500,
    input_tokens: 1500,
    output_tokens: 800,
    cost_usd: 0.0825,
    accuracy: 0.95,
    success: true,
  })
  assert(result.recorded === true, 'Call recorded')
  assert(result.total_records === 1, 'Total records = 1')
  console.log()

  // Test 3: Track multiple calls with variation
  console.log('Test 3: Track multiple calls')
  const testCalls = [
    { latency_ms: 2300, cost_usd: 0.075, accuracy: 0.92 },
    { latency_ms: 3100, cost_usd: 0.095, accuracy: 0.88 },
    { latency_ms: 2000, cost_usd: 0.068, accuracy: 0.97 },
    { latency_ms: 2800, cost_usd: 0.082, accuracy: 0.90 },
    { latency_ms: 2600, cost_usd: 0.078, accuracy: 0.94 },
  ]

  for (const call of testCalls) {
    await monitor({
      action: 'track',
      model: 'opus',
      workflow_id: 'test-run-1',
      task_type: 'testing',
      latency_ms: call.latency_ms,
      input_tokens: 1500,
      output_tokens: 800,
      cost_usd: call.cost_usd,
      accuracy: call.accuracy,
      success: true,
    })
  }

  result = await monitor({ action: 'getMetrics', model: 'opus' })
  assert(result.record_count === 6, 'Total 6 records tracked')
  assert(result.metrics.call_count === 6, 'Metrics show 6 calls')
  assert(result.metrics.success_rate === 100, 'Success rate is 100%')
  console.log()

  // Test 4: Verify latency metrics
  console.log('Test 4: Verify latency metrics')
  const metrics = result.metrics
  assert(metrics.latency.avg > 2000, 'Average latency > 2000ms')
  assert(metrics.latency.avg < 3000, 'Average latency < 3000ms')
  assert(metrics.latency.min < 2500, 'Min latency exists')
  assert(metrics.latency.max > 2500, 'Max latency exists')
  assert(metrics.latency.stddev > 0, 'Stddev computed')
  console.log(`  Latency: avg=${metrics.latency.avg.toFixed(0)}ms, p95=${metrics.latency.p95.toFixed(0)}ms`)
  console.log()

  // Test 5: Verify cost metrics
  console.log('Test 5: Verify cost metrics')
  assert(metrics.cost.total > 0.45, 'Total cost > $0.45')
  assert(metrics.cost.total < 0.55, 'Total cost < $0.55')
  assert(metrics.cost.avg > 0.070, 'Avg cost > $0.070')
  assert(metrics.cost.avg < 0.090, 'Avg cost < $0.090')
  console.log(`  Cost: total=$${metrics.cost.total.toFixed(4)}, avg=$${metrics.cost.avg.toFixed(4)}`)
  console.log()

  // Test 6: Verify accuracy metrics
  console.log('Test 6: Verify accuracy metrics')
  assert(metrics.accuracy.avg > 0.90, 'Avg accuracy > 0.90')
  assert(metrics.accuracy.avg < 0.95, 'Avg accuracy < 0.95')
  assert(metrics.accuracy.min > 0.87, 'Min accuracy > 0.87')
  assert(metrics.accuracy.max > 0.96, 'Max accuracy > 0.96')
  console.log(`  Accuracy: avg=${(metrics.accuracy.avg * 100).toFixed(1)}%, range=${(metrics.accuracy.min * 100).toFixed(1)}%-${(metrics.accuracy.max * 100).toFixed(1)}%`)
  console.log()

  // Test 7: Add anomalous data point
  console.log('Test 7: Add anomalous data point')
  await monitor({
    action: 'track',
    model: 'opus',
    workflow_id: 'test-run-1',
    task_type: 'testing',
    latency_ms: 15000, // Very high
    input_tokens: 1500,
    output_tokens: 800,
    cost_usd: 0.15, // Very high
    accuracy: 0.5, // Very low
    success: false, // Failed
  })

  result = await monitor({ action: 'detectAnomalies', model: 'opus' })
  assert(result.anomaly_count > 0, 'Anomalies detected')
  console.log(`  Found ${result.anomaly_count} anomalies`)
  if (result.anomalies.length > 0) {
    console.log(`  First anomaly: ${result.anomalies[0].metric} (${result.anomalies[0].severity})`)
  }
  console.log()

  // Test 8: Get trends
  console.log('Test 8: Analyze trends')
  result = await monitor({ action: 'getTrends', model: 'opus' })
  assert(result.trends && Array.isArray(result.trends), 'Trends returned')
  console.log(`  Found ${result.trends.length} trend(s)`)
  for (const trend of result.trends) {
    console.log(`    ${trend.metric}: ${trend.direction} (${trend.change_percent}%)`)
  }
  console.log()

  // Test 9: Test with multiple models
  console.log('Test 9: Test multiple models')
  await monitor({
    action: 'track',
    model: 'sonnet',
    workflow_id: 'test-run-2',
    task_type: 'testing',
    latency_ms: 1200,
    input_tokens: 1000,
    output_tokens: 500,
    cost_usd: 0.025,
    accuracy: 0.93,
    success: true,
  })

  await monitor({
    action: 'track',
    model: 'haiku',
    workflow_id: 'test-run-2',
    task_type: 'testing',
    latency_ms: 800,
    input_tokens: 500,
    output_tokens: 250,
    cost_usd: 0.0012,
    accuracy: 0.85,
    success: true,
  })

  result = await monitor({
    action: 'compareModels',
    models: ['opus', 'sonnet', 'haiku'],
  })
  assert(result.models_compared.length === 3, 'Three models compared')
  assert(Object.keys(result.comparison_table).length === 3, 'Three models in comparison table')
  assert(result.rankings.fastest, 'Rankings include fastest')
  assert(result.rankings.cheapest, 'Rankings include cheapest')
  console.log(`  Fastest: ${result.rankings.fastest[0]}`)
  console.log(`  Cheapest: ${result.rankings.cheapest[0]}`)
  console.log()

  // Test 10: Get dashboard
  console.log('Test 10: Generate dashboard')
  result = await monitor({ action: 'getDashboard', include_charts: true })
  assert(result.summary, 'Dashboard summary exists')
  assert(result.overall_metrics, 'Overall metrics exist')
  assert(result.system_health, 'System health exists')
  assert(result.charts, 'Charts included')
  console.log(`  Total records: ${result.summary.total_records}`)
  console.log(`  Unique models: ${result.summary.unique_models}`)
  console.log(`  System health: ${result.system_health.status}`)
  console.log()

  // Test 11: Generate comprehensive report
  console.log('Test 11: Generate comprehensive report')
  result = await monitor({
    action: 'generateReport',
    time_window_hours: 24,
  })
  assert(result.title, 'Report has title')
  assert(result.executive_summary, 'Report has executive summary')
  assert(result.detailed_metrics, 'Report has detailed metrics')
  assert(result.anomalies, 'Report has anomalies section')
  assert(result.trends, 'Report has trends section')
  assert(result.recommendations, 'Report has recommendations')
  assert(result.tables, 'Report has tables')
  console.log(`  Report: ${result.title}`)
  console.log(`  Analysis period: ${result.analysis_period.record_count} records`)
  console.log(`  Recommendations: ${result.recommendations.length}`)
  console.log()

  // Test 12: Test alert detection
  console.log('Test 12: Alert detection')
  result = await monitor({
    action: 'track',
    model: 'test-alerts',
    latency_ms: 10000, // Over 5000ms threshold
    cost_usd: 1.0, // Over 0.50 threshold
    accuracy: 0.5, // Under 0.70 threshold
    success: true,
  })
  assert(result.alerts && Array.isArray(result.alerts), 'Alerts returned')
  assert(result.alerts.length >= 2, 'Multiple alerts triggered')
  console.log(`  Alerts triggered: ${result.alerts.length}`)
  for (const alert of result.alerts) {
    console.log(`    - ${alert.type}: ${alert.message}`)
  }
  console.log()

  // Test 13: Time window filtering
  console.log('Test 13: Time window filtering')
  result = await monitor({
    action: 'getMetrics',
    model: 'opus',
    time_window_hours: 1, // Only last hour
  })
  // Should have fewer or equal records
  assert(typeof result.record_count === 'number', 'Record count returned')
  console.log(`  Records in last 1 hour: ${result.record_count}`)
  console.log()

  // Test 14: Unknown action error handling
  console.log('Test 14: Error handling')
  result = await monitor({ action: 'unknown-action' })
  assert(result.error, 'Error returned for unknown action')
  assert(result.available_actions, 'Available actions listed')
  console.log(`  Error message: ${result.error}`)
  console.log()

  console.log('All tests passed!')
}

// Run tests
runTests().catch((err) => {
  console.error('Test suite failed:', err)
  process.exit(1)
})
