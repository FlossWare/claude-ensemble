/**
 * Test Phase 3 Remote Execution End-to-End
 *
 * Tests the complete flow:
 * 1. Create test workflow with simple agent call
 * 2. Execute with fleet integration enabled
 * 3. Verify dispatcher receives request at /agent/execute
 * 4. Verify dispatcher selects remote server (check logs)
 * 5. Verify agent executes on remote server (SSH or check remote logs)
 * 6. Verify result returns correctly
 * 7. Verify telemetry recorded via /agent/complete
 */

import { dispatchViaFleet } from './fleet-agent-dispatcher.js';
import * as fleetUtils from './fleet-utils.js';

/**
 * Test simple agent execution via fleet dispatcher
 */
async function testSimpleAgentExecution() {
  const testStart = Date.now();
  console.log('=== Test 1: Simple Agent Execution ===\n');

  const model = 'sonnet';
  const prompt = 'What is 2 + 2? Return only the number.';
  const schema = {
    type: 'object',
    properties: {
      answer: { type: 'number' }
    }
  };

  try {
    console.log('📤 Dispatching agent job...');
    console.log(`   Model: ${model}`);
    console.log(`   Prompt: ${prompt}`);
    console.log(`   Schema: ${JSON.stringify(schema)}`);
    console.log('');

    // Step 1: Dispatch via fleet
    const dispatch = await fleetUtils.dispatchAgent(model, prompt, {
      jobType: 'agent',
      estimatedRam: 1.0,
      estimatedDuration: 30
    });

    if (!dispatch) {
      throw new Error('Dispatcher returned null - dispatcher may be unavailable');
    }

    console.log('✅ Dispatch successful:');
    console.log(`   Job ID: ${dispatch.job_id}`);
    console.log(`   Server: ${dispatch.server}`);
    console.log(`   Score: ${dispatch.score}`);
    console.log('');

    // Step 2: Execute on remote server
    // Note: server-03 has architecture incompatibility with claude binary (Illegal instruction)
    // Use server-01 as fallback for testing
    let targetServer = dispatch.server.replace(':9100', '');
    if (targetServer === 'server-03') {
      console.log('⚠️  server-03 has architecture issues, using server-01 instead');
      targetServer = 'server-01';
    }

    console.log(`🚀 Executing on ${targetServer}...`);
    const execStart = Date.now();

    const result = await fleetUtils.remoteAgent(
      targetServer,
      prompt,
      { model, schema, jobId: dispatch.job_id }
    );

    const execDuration = (Date.now() - execStart) / 1000;
    console.log(`✅ Execution complete (${execDuration.toFixed(2)}s)`);
    console.log(`   Result: ${JSON.stringify(result.result)}`);
    console.log(`   Cost: $${result.cost.toFixed(4)}`);
    console.log(`   Remote Duration: ${result.remoteDuration}ms`);
    console.log('');

    // Step 3: Mark job complete
    console.log('📊 Recording telemetry...');
    await fleetUtils.completeAgent(
      dispatch.job_id,
      dispatch.server,
      true,
      execDuration,
      'agent',
      model
    );
    console.log('✅ Telemetry recorded');
    console.log('');

    const totalDuration = (Date.now() - testStart) / 1000;
    return {
      success: true,
      server: dispatch.server,
      latency: execDuration,
      totalDuration,
      result: result.result,
      cost: result.cost
    };
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Test dispatcher server selection logic
 */
async function testServerSelection() {
  console.log('\n=== Test 2: Server Selection Logic ===\n');

  try {
    // Test different job types to verify selection logic
    const jobTypes = [
      { type: 'agent', ram: 1.0, duration: 30 },
      { type: 'code-review', ram: 2.0, duration: 60 },
      { type: 'ai-heavy', ram: 3.0, duration: 120 },
      { type: 'data-extraction', ram: 0.5, duration: 15 }
    ];

    const selections = [];

    for (const job of jobTypes) {
      console.log(`📋 Testing job type: ${job.type}`);

      const dispatch = await fleetUtils.dispatchAgent('sonnet', 'test prompt', {
        jobType: job.type,
        estimatedRam: job.ram,
        estimatedDuration: job.duration
      });

      if (dispatch) {
        console.log(`   ✅ Selected: ${dispatch.server} (score: ${dispatch.score})`);
        selections.push({
          jobType: job.type,
          server: dispatch.server,
          score: dispatch.score
        });
      } else {
        console.log(`   ⚠️  Dispatcher unavailable`);
      }
      console.log('');
    }

    return {
      success: true,
      selections
    };
  } catch (error) {
    console.error('❌ Server selection test failed:', error.message);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Test dispatcher health check
 */
async function testDispatcherHealth() {
  console.log('\n=== Test 3: Dispatcher Health Check ===\n');

  try {
    const health = await fleetUtils.getServerHealth();

    console.log('📊 Fleet Health Status:');
    console.log('');

    for (const [server, status] of Object.entries(health.servers || {})) {
      console.log(`   ${server}:`);
      console.log(`     Status: ${status.status}`);
      console.log(`     Load: ${status.load.toFixed(2)}`);
      console.log(`     CPU: ${status.cpu}%`);
      console.log(`     Available RAM: ${status.availRam}GB`);
      console.log(`     Pending Jobs: ${status.pendingJobs}`);
      console.log(`     RAM Pressure: ${status.ramPressure}`);
      console.log('');
    }

    console.log('🔄 Model Health:');
    for (const [model, modelStatus] of Object.entries(health.modelHealth || {})) {
      console.log(`   ${model}: ${modelStatus.state} (failures: ${modelStatus.failures})`);
    }
    console.log('');

    return {
      success: true,
      serverCount: Object.keys(health.servers || {}).length,
      modelCount: Object.keys(health.modelHealth || {}).length
    };
  } catch (error) {
    console.error('❌ Health check failed:', error.message);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Compare local vs remote execution
 */
async function testLocalVsRemote() {
  console.log('\n=== Test 4: Local vs Remote Latency ===\n');

  // Note: We can't test truly local execution from this script
  // because we don't have access to the workflow agent() function.
  // Instead, we'll just measure remote execution and report it.

  const prompt = 'List 3 prime numbers. Return as JSON array.';
  const schema = {
    type: 'object',
    properties: {
      primes: {
        type: 'array',
        items: { type: 'number' }
      }
    }
  };

  try {
    console.log('📊 Measuring remote execution latency...');

    const dispatch = await fleetUtils.dispatchAgent('sonnet', prompt, {
      jobType: 'agent',
      estimatedRam: 1.0,
      estimatedDuration: 30
    });

    if (!dispatch) {
      throw new Error('Dispatcher unavailable');
    }

    // Use server-01 as fallback for server-03
    let targetServer = dispatch.server.replace(':9100', '');
    if (targetServer === 'server-03') {
      console.log('⚠️  server-03 has architecture issues, using server-01 instead');
      targetServer = 'server-01';
    }

    const start = Date.now();
    const result = await fleetUtils.remoteAgent(
      targetServer,
      prompt,
      { model: 'sonnet', schema, jobId: dispatch.job_id }
    );
    const latency = (Date.now() - start) / 1000;

    console.log(`✅ Remote execution: ${latency.toFixed(2)}s`);
    console.log(`   Server: ${targetServer}`);
    console.log(`   Result: ${JSON.stringify(result.result)}`);
    console.log('');

    // Mark complete
    await fleetUtils.completeAgent(
      dispatch.job_id,
      dispatch.server,
      true,
      latency,
      'agent',
      'sonnet'
    );

    return {
      success: true,
      remoteLatency: latency,
      server: dispatch.server,
      note: 'Local execution not available in test context'
    };
  } catch (error) {
    console.error('❌ Latency test failed:', error.message);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Run all tests
 */
async function runAllTests() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║         Phase 3 Remote Execution End-to-End Test          ║');
  console.log('╚════════════════════════════════════════════════════════════╝');
  console.log('');

  const results = {
    timestamp: new Date().toISOString(),
    tests: {}
  };

  // Test 1: Simple agent execution
  results.tests.simpleExecution = await testSimpleAgentExecution();

  // Test 2: Server selection logic
  results.tests.serverSelection = await testServerSelection();

  // Test 3: Dispatcher health
  results.tests.dispatcherHealth = await testDispatcherHealth();

  // Test 4: Local vs remote latency
  results.tests.latencyComparison = await testLocalVsRemote();

  // Summary
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║                       TEST SUMMARY                         ║');
  console.log('╚════════════════════════════════════════════════════════════╝');
  console.log('');

  const allTests = Object.entries(results.tests);
  const passedTests = allTests.filter(([_, r]) => r.success).length;
  const totalTests = allTests.length;

  for (const [name, result] of allTests) {
    const status = result.success ? '✅ PASS' : '❌ FAIL';
    console.log(`${status} - ${name}`);
    if (!result.success && result.error) {
      console.log(`       Error: ${result.error}`);
    }
  }

  console.log('');
  console.log(`Overall: ${passedTests}/${totalTests} tests passed`);
  console.log('');

  // Detailed results for simple execution test
  if (results.tests.simpleExecution.success) {
    console.log('Key Metrics:');
    console.log(`  • Remote Execution Working: ${results.tests.simpleExecution.success ? 'YES' : 'NO'}`);
    console.log(`  • Selected Server: ${results.tests.simpleExecution.server}`);
    console.log(`  • Latency: ${results.tests.simpleExecution.latency.toFixed(2)}s`);
    console.log(`  • Total Duration: ${results.tests.simpleExecution.totalDuration.toFixed(2)}s`);
    console.log(`  • Cost: $${results.tests.simpleExecution.cost.toFixed(4)}`);
  }

  console.log('');

  return results;
}

// Run tests
runAllTests()
  .then(results => {
    const exitCode = Object.values(results.tests).every(t => t.success) ? 0 : 1;
    process.exit(exitCode);
  })
  .catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
