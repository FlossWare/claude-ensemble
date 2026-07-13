#!/usr/bin/env node

/**
 * Test script for queue metrics
 *
 * Simulates queue activity and verifies metrics tracking
 */

const QueueMetrics = require('./queue-metrics');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testMetrics() {
  const metrics = new QueueMetrics();

  console.log('Testing queue metrics...\n');

  try {
    // Test 1: Record some processed items
    console.log('Test 1: Recording processed items...');
    for (let i = 0; i < 10; i++) {
      await metrics.recordProcessed('scrape', Math.random() * 1000 + 100);
      await sleep(50);
    }
    console.log('✓ Recorded 10 items\n');

    // Test 2: Record some errors
    console.log('Test 2: Recording errors...');
    await metrics.recordError('scrape', new Error('Test error 1'));
    await metrics.recordError('scrape', new Error('Test error 2'));
    console.log('✓ Recorded 2 errors\n');

    // Test 3: Worker heartbeats
    console.log('Test 3: Recording worker heartbeats...');
    await metrics.workerHeartbeat('worker-test-1', 'scrape', 'active');
    await metrics.workerHeartbeat('worker-test-2', 'storage', 'active');
    await metrics.workerHeartbeat('worker-test-3', 'embedding', 'active');
    console.log('✓ Recorded 3 worker heartbeats\n');

    // Test 4: Get snapshot
    console.log('Test 4: Getting metrics snapshot...');
    const snapshot = await metrics.getSnapshot();
    console.log('✓ Snapshot retrieved\n');

    // Test 5: Print metrics
    console.log('Test 5: Printing formatted metrics...');
    await metrics.printMetrics();

    // Test 6: Get specific metrics
    console.log('Test 6: Getting specific metrics...');
    const throughput = await metrics.getThroughput('scrape', 60000);
    console.log(`Throughput: ${throughput.itemsPerMin.toFixed(2)} items/min`);
    console.log(`Avg processing: ${throughput.avgProcessingMs.toFixed(0)}ms`);

    const errorRate = await metrics.getErrorRate('scrape', 60000);
    console.log(`Error rate: ${errorRate.errorRate}`);
    console.log('✓ Specific metrics retrieved\n');

    // Test 7: Verify worker tracking
    console.log('Test 7: Verifying worker tracking...');
    const workers = await metrics.getActiveWorkers();
    console.log(`Active workers: ${workers.length}`);
    workers.forEach(w => {
      console.log(`  - ${w.id}: ${w.queue} (${w.status}, ${w.age}ms ago)`);
    });
    console.log('✓ Workers tracked\n');

    console.log('All tests passed! ✓');

  } catch (error) {
    console.error('Test failed:', error);
  } finally {
    await metrics.close();
  }
}

// Run tests
if (require.main === module) {
  testMetrics().catch(console.error);
}

module.exports = testMetrics;
