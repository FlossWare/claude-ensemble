// Quick integration test for resource estimation learning

async function test() {
  console.log('Testing resource estimation integration...\n');

  // Test 1: Import learner
  console.log('1. Testing learner import...');
  const learner = require('../shared/resource-estimation-learner.cjs');
  console.log('   ✓ Learner imported\n');

  // Test 2: Check database connection
  console.log('2. Testing database connection...');
  const stats = await learner.getLearningStats();
  console.log(`   ✓ Database connected: ${stats.total_jobs} jobs tracked\n`);

  // Test 3: Record a test job
  console.log('3. Recording test job execution...');
  const result = await learner.learnFromExecution({
    prompt_length: 500,
    model: 'sonnet',
    schema_complexity: 3,
    job_type: 'agent',
    actual_duration: 25,
    actual_ram: 1.0,
    estimated_duration: 30,
    estimated_ram: 1.2
  });
  console.log(`   ✓ Job recorded: error=${(result.duration_error * 100).toFixed(1)}%\n`);

  // Test 4: Try to get estimate (will be null if <10 jobs)
  console.log('4. Testing estimate retrieval...');
  const estimate = await learner.getLearnedEstimate({
    prompt_length: 500,
    model: 'sonnet',
    schema_complexity: 3,
    job_type: 'agent'
  });
  if (estimate) {
    console.log(`   ✓ Learned estimate: ${estimate.duration}s, ${estimate.ram}GB\n`);
  } else {
    console.log('   ⚠ No learned estimate yet (need 10+ jobs for training)\n');
  }

  // Test 5: Test fleet dispatcher integration
  console.log('5. Testing fleet dispatcher integration...');
  const { estimateResources } = await import('../skills/misc/fleet-agent-dispatcher.js');
  const dispatcherEst = await estimateResources(
    'x'.repeat(500),
    'sonnet',
    { properties: { a: {}, b: {}, c: {} } },
    'agent'
  );
  console.log(`   ✓ Dispatcher estimate: ${dispatcherEst.duration}s, ${dispatcherEst.ram}GB (source: ${dispatcherEst.source})\n`);

  // Final stats
  const finalStats = await learner.getLearningStats();
  console.log('='.repeat(60));
  console.log('Final state:');
  console.log(`  Total jobs: ${finalStats.total_jobs}`);
  console.log(`  Retrains: ${finalStats.retrain_count}`);
  console.log(`  Jobs since retrain: ${finalStats.jobs_since_retrain}`);
  console.log('='.repeat(60));

  console.log('\n✅ All integration tests passed!\n');

  await learner.pool.end();
}

test().catch(err => {
  console.error('❌ Test failed:', err);
  process.exit(1);
});
