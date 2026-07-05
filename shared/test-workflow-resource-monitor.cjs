#!/usr/bin/env node
/**
 * Test script for workflow-resource-monitor.cjs
 *
 * Demonstrates:
 * - Starting resource monitoring
 * - Simulating workflow execution
 * - Stopping monitoring and retrieving stats
 * - Querying resource usage history
 * - Aggregated statistics
 *
 * Usage:
 *   node shared/test-workflow-resource-monitor.cjs
 */

const {
  startMonitoring,
  stopMonitoring,
  getResourceHistory,
  getResourceByExecutionId,
  getAggregatedStats,
  pool,
} = require('./workflow-resource-monitor.cjs');

/**
 * Simulate CPU-intensive work
 */
function simulateCPUWork(durationMs) {
  const start = Date.now();
  let count = 0;

  while (Date.now() - start < durationMs) {
    // Busy loop to simulate CPU work
    count += Math.sqrt(Math.random());
  }

  return count;
}

/**
 * Simulate memory-intensive work
 */
function simulateMemoryWork(sizeInMB) {
  const arrays = [];
  const chunkSize = 1024 * 1024; // 1MB chunks

  for (let i = 0; i < sizeInMB; i++) {
    // Allocate 1MB array
    arrays.push(new Array(chunkSize / 8).fill(Math.random()));
  }

  return arrays; // Keep in memory
}

/**
 * Sleep for specified milliseconds
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runTest() {
  console.log('================================================================================');
  console.log('WORKFLOW RESOURCE MONITOR TEST');
  console.log('================================================================================\n');

  // Test 1: Basic monitoring
  console.log('Test 1: Basic workflow monitoring (5 seconds)');
  console.log('Starting monitoring for workflow "test-wf-basic"...');

  const workflowId1 = 'test-wf-basic-' + Date.now();
  startMonitoring(workflowId1);

  // Simulate workflow execution
  console.log('Simulating workflow execution...');
  await sleep(1000);
  simulateCPUWork(500); // CPU-intensive work
  await sleep(1000);
  const memoryData = simulateMemoryWork(50); // Allocate 50MB
  await sleep(1000);
  simulateCPUWork(500);
  await sleep(1000);
  simulateCPUWork(500);
  await sleep(1000);

  console.log('Stopping monitoring...\n');
  const stats1 = await stopMonitoring(workflowId1);

  console.log('Resource usage statistics:');
  console.log(JSON.stringify(stats1, null, 2));
  console.log('');

  // Clean up memory
  memoryData.length = 0;

  // Test 2: Workflow with execution ID
  console.log('\n================================================================================');
  console.log('Test 2: Workflow with execution ID (3 seconds)');
  console.log('================================================================================\n');

  const workflowId2 = 'test-wf-with-exec-id-' + Date.now();
  const executionId = 12345;

  console.log(`Starting monitoring for workflow "${workflowId2}" (execution ID: ${executionId})...`);
  startMonitoring(workflowId2);

  // Simulate shorter workflow
  await sleep(1000);
  simulateCPUWork(300);
  await sleep(1000);
  simulateCPUWork(300);
  await sleep(1000);

  console.log('Stopping monitoring...\n');
  const stats2 = await stopMonitoring(workflowId2, { workflowExecutionId: executionId });

  console.log('Resource usage statistics:');
  console.log(JSON.stringify(stats2, null, 2));
  console.log('');

  // Test 3: Custom sample interval
  console.log('\n================================================================================');
  console.log('Test 3: Custom sample interval (500ms, 2 seconds total)');
  console.log('================================================================================\n');

  const workflowId3 = 'test-wf-custom-interval-' + Date.now();

  console.log('Starting monitoring with 500ms sample interval...');
  startMonitoring(workflowId3, { sampleIntervalMs: 500 });

  await sleep(500);
  simulateCPUWork(200);
  await sleep(500);
  simulateCPUWork(200);
  await sleep(500);
  simulateCPUWork(200);
  await sleep(500);

  console.log('Stopping monitoring...\n');
  const stats3 = await stopMonitoring(workflowId3);

  console.log('Resource usage statistics:');
  console.log(JSON.stringify(stats3, null, 2));
  console.log('');

  // Test 4: Query resource history
  console.log('\n================================================================================');
  console.log('Test 4: Query resource usage history');
  console.log('================================================================================\n');

  console.log(`Querying history for workflow "${workflowId1}"...`);
  const history = await getResourceHistory(workflowId1, { limit: 5 });

  console.log(`Found ${history.length} record(s):\n`);
  for (const record of history) {
    console.log(`  ID: ${record.id}`);
    console.log(`  Duration: ${record.duration_ms}ms`);
    console.log(`  Peak Memory: ${record.peak_memory_mb}MB`);
    console.log(`  Avg CPU: ${record.avg_cpu_percent}%`);
    console.log(`  Samples: ${record.sample_count}`);
    console.log('');
  }

  // Test 5: Query by execution ID
  console.log('\n================================================================================');
  console.log('Test 5: Query resource usage by execution ID');
  console.log('================================================================================\n');

  console.log(`Querying resource usage for execution ID ${executionId}...`);
  const execStats = await getResourceByExecutionId(executionId);

  if (execStats) {
    console.log('Found resource usage record:\n');
    console.log(JSON.stringify(execStats, null, 2));
    console.log('');
  } else {
    console.log('No record found.\n');
  }

  // Test 6: Aggregated statistics
  console.log('\n================================================================================');
  console.log('Test 6: Aggregated statistics (last 1000 workflows)');
  console.log('================================================================================\n');

  const aggStats = await getAggregatedStats();

  console.log('Aggregated statistics across all workflows:');
  console.log(`  Total workflows: ${aggStats.total_workflows}`);
  console.log(`  Avg duration: ${parseFloat(aggStats.avg_duration_ms).toFixed(0)}ms`);
  console.log(`  Max duration: ${aggStats.max_duration_ms}ms`);
  console.log(`  Min duration: ${aggStats.min_duration_ms}ms`);
  console.log(`  Avg peak memory: ${parseFloat(aggStats.avg_peak_memory_mb).toFixed(2)}MB`);
  console.log(`  Max peak memory: ${parseFloat(aggStats.max_peak_memory_mb).toFixed(2)}MB`);
  console.log(`  Avg CPU: ${parseFloat(aggStats.avg_cpu_percent).toFixed(2)}%`);
  console.log(`  Max CPU: ${parseFloat(aggStats.max_cpu_percent).toFixed(2)}%`);
  console.log('');

  // Test 7: Recent aggregated statistics (last 24 hours)
  console.log('\n================================================================================');
  console.log('Test 7: Recent aggregated statistics (last 24 hours)');
  console.log('================================================================================\n');

  const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  const recentStats = await getAggregatedStats({ since: yesterday });

  console.log('Aggregated statistics (last 24 hours):');
  console.log(`  Total workflows: ${recentStats.total_workflows}`);
  console.log(`  Avg duration: ${parseFloat(recentStats.avg_duration_ms || 0).toFixed(0)}ms`);
  console.log(`  Avg peak memory: ${parseFloat(recentStats.avg_peak_memory_mb || 0).toFixed(2)}MB`);
  console.log(`  Avg CPU: ${parseFloat(recentStats.avg_cpu_percent || 0).toFixed(2)}%`);
  console.log('');

  console.log('================================================================================');
  console.log('ALL TESTS COMPLETED SUCCESSFULLY ✓');
  console.log('================================================================================\n');

  // Clean up and exit
  await pool.end();
  process.exit(0);
}

// Run tests
runTest().catch((err) => {
  console.error('Test failed:', err);
  pool.end();
  process.exit(1);
});
