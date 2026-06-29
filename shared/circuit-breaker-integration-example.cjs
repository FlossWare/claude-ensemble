/**
 * Circuit Breaker Integration Example
 *
 * Demonstrates integration with weighted voting and worker orchestration.
 * Shows how circuit breaker protects against failing models.
 *
 * Run: node circuit-breaker-integration-example.cjs
 *
 * Created: 2026-06-28
 */

const { runWeightedVoting } = require('./weighted-voting.cjs');
const { getCircuitBreaker, withCircuitBreaker, FailureType } = require('./circuit-breaker.cjs');

// ============================================================================
// EXAMPLE 1: Basic Integration with Weighted Voting
// ============================================================================

async function example1_WeightedVotingWithCircuitBreaker() {
  console.log('\n=== Example 1: Weighted Voting with Circuit Breaker ===\n');

  // Simulate worker votes
  const votes = [
    { model: 'opus', answer: 'A', confidence: 0.9 },
    { model: 'sonnet', answer: 'A', confidence: 0.85 },
    { model: 'haiku', answer: 'B', confidence: 0.7 },
    { model: 'fable', answer: 'A', confidence: 0.88 },
    { model: 'gpt-4o', answer: 'A', confidence: 0.92 }, // Will be filtered (open circuit)
    { model: 'gemini', answer: 'B', confidence: 0.75 },
  ];

  // Simulate that gpt-4o has been failing
  const circuitBreaker = getCircuitBreaker();
  await circuitBreaker.resetCircuit('gpt-4o'); // Clean slate
  await circuitBreaker.recordFailure('gpt-4o', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('gpt-4o', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('gpt-4o', FailureType.API_ERROR);

  console.log('Circuit state for gpt-4o:', (await circuitBreaker.getState('gpt-4o')).state);
  console.log('');

  // Run weighted voting (circuit breaker auto-filters gpt-4o)
  const result = await runWeightedVoting(votes, 'code_review', {
    minConfidence: 70,
  });

  console.log('Voting result:');
  console.log('  Winner:', result.voting_result.winner.answer);
  console.log('  Consensus:', result.voting_result.winner.consensus_level);
  console.log('  Vote count:', result.voting_result.winner.vote_count);

  if (result.voting_result.circuit_breaker_analysis) {
    console.log('\nCircuit Breaker Analysis:');
    console.log('  Unavailable models:', result.voting_result.circuit_breaker_analysis.unavailable_models);
    console.log('  Votes filtered:', result.voting_result.circuit_breaker_analysis.votes_filtered);
    console.log('  Votes remaining:', result.voting_result.circuit_breaker_analysis.votes_remaining);
  }
}

// ============================================================================
// EXAMPLE 2: Worker Orchestration with Circuit Breaker
// ============================================================================

async function example2_WorkerOrchestrationWithCircuitBreaker() {
  console.log('\n\n=== Example 2: Worker Orchestration with Circuit Breaker ===\n');

  const circuitBreaker = getCircuitBreaker();

  // Reset circuits for example
  await circuitBreaker.resetCircuit('worker-1');
  await circuitBreaker.resetCircuit('worker-2');
  await circuitBreaker.resetCircuit('worker-3');

  // Simulate worker-2 failures
  await circuitBreaker.recordFailure('worker-2', FailureType.TIMEOUT);
  await circuitBreaker.recordFailure('worker-2', FailureType.TIMEOUT);
  await circuitBreaker.recordFailure('worker-2', FailureType.TIMEOUT);

  console.log('Checking worker availability before spawning...\n');

  // Pre-flight check: filter available workers
  const allWorkers = ['worker-1', 'worker-2', 'worker-3'];
  const availableWorkers = await circuitBreaker.filterAvailableModels(allWorkers);

  console.log('Available workers:', availableWorkers);
  console.log('Unavailable workers:', allWorkers.filter(w => !availableWorkers.includes(w)));
  console.log('');

  // Spawn only available workers
  console.log('Spawning workers:', availableWorkers.join(', '));

  // Simulate worker execution with circuit breaker protection
  for (const worker of availableWorkers) {
    try {
      const result = await withCircuitBreaker(worker, async () => {
        // Simulate worker logic
        console.log(`  ${worker}: Executing task...`);
        return { success: true, data: `Result from ${worker}` };
      });

      console.log(`  ${worker}: ✓ Success`);
    } catch (err) {
      console.log(`  ${worker}: ✗ Failed - ${err.message}`);
    }
  }
}

// ============================================================================
// EXAMPLE 3: Monitoring and Recovery
// ============================================================================

async function example3_MonitoringAndRecovery() {
  console.log('\n\n=== Example 3: Monitoring and Recovery ===\n');

  const circuitBreaker = getCircuitBreaker();

  // Get statistics
  const stats = await circuitBreaker.getStatistics();

  console.log('Circuit Breaker Statistics:');
  console.log('  Total circuits:', stats.total);
  console.log('  By state:', JSON.stringify(stats.by_state, null, 2));
  console.log('');

  // Get open circuits
  const openCircuits = await circuitBreaker.getOpenCircuits();

  if (openCircuits.length > 0) {
    console.log(`Open Circuits (${openCircuits.length}):`);
    for (const circuit of openCircuits) {
      console.log(`  - ${circuit.model}:`);
      console.log(`      Failure count: ${circuit.failure_count}`);
      console.log(`      Last failure: ${circuit.last_failure_time}`);
      console.log(`      Metadata:`, JSON.stringify(circuit.metadata, null, 2));
    }
  } else {
    console.log('No open circuits ✓');
  }

  console.log('');

  // Manual recovery example
  if (openCircuits.length > 0) {
    const modelToRecover = openCircuits[0].model;
    console.log(`Manually recovering circuit: ${modelToRecover}`);
    await circuitBreaker.resetCircuit(modelToRecover);

    const state = await circuitBreaker.getState(modelToRecover);
    console.log(`  New state: ${state.state} ✓`);
  }
}

// ============================================================================
// EXAMPLE 4: Graceful Degradation Pattern
// ============================================================================

async function example4_GracefulDegradation() {
  console.log('\n\n=== Example 4: Graceful Degradation Pattern ===\n');

  const circuitBreaker = getCircuitBreaker();

  // Simulate primary model failure
  await circuitBreaker.resetCircuit('primary-model');
  await circuitBreaker.recordFailure('primary-model', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('primary-model', FailureType.API_ERROR);
  await circuitBreaker.recordFailure('primary-model', FailureType.API_ERROR);

  // Graceful degradation: try primary, fallback to secondary
  const modelFallbackChain = ['primary-model', 'secondary-model', 'tertiary-model'];

  console.log('Attempting models in fallback order:', modelFallbackChain.join(' → '));
  console.log('');

  for (const model of modelFallbackChain) {
    const status = await circuitBreaker.isAvailable(model);

    if (status.available) {
      console.log(`Using model: ${model} (state: ${status.state})`);

      try {
        const result = await withCircuitBreaker(model, async () => {
          // Simulate model call
          if (model === 'secondary-model') {
            return { success: true, data: `Result from ${model}` };
          }
          throw new Error('Model unavailable');
        });

        console.log('  Result:', result.data);
        console.log('  ✓ Success with fallback model\n');
        break;

      } catch (err) {
        console.log(`  ✗ ${model} failed: ${err.message}`);
        console.log('  Trying next model in chain...\n');
      }
    } else {
      console.log(`Skipping ${model}: circuit ${status.state} (${status.reason})`);
      if (status.retry_after_seconds) {
        console.log(`  Retry in ${status.retry_after_seconds}s\n`);
      }
    }
  }
}

// ============================================================================
// EXAMPLE 5: All Models Failed Scenario
// ============================================================================

async function example5_AllModelsFailed() {
  console.log('\n\n=== Example 5: All Models Failed (Error Handling) ===\n');

  // Simulate all models failing
  const votes = [
    { model: 'failed-1', answer: 'A', confidence: 0.9 },
    { model: 'failed-2', answer: 'B', confidence: 0.85 },
    { model: 'failed-3', answer: 'A', confidence: 0.88 },
  ];

  const circuitBreaker = getCircuitBreaker();

  // Open all circuits
  for (const model of ['failed-1', 'failed-2', 'failed-3']) {
    await circuitBreaker.resetCircuit(model);
    await circuitBreaker.recordFailure(model, FailureType.API_ERROR);
    await circuitBreaker.recordFailure(model, FailureType.API_ERROR);
    await circuitBreaker.recordFailure(model, FailureType.API_ERROR);
  }

  // Try weighted voting (should fail gracefully)
  const result = await runWeightedVoting(votes, 'general', {
    minConfidence: 70,
  });

  console.log('Voting result status:', result.voting_result.status);

  if (result.voting_result.status === 'error') {
    console.log('Error:', result.voting_result.error);
    console.log('Message:', result.voting_result.message);
    console.log('');
    console.log('Circuit breaker prevented wasted API calls ✓');

    if (result.voting_result.circuit_breaker_analysis) {
      console.log('\nUnavailable models:');
      result.voting_result.circuit_breaker_analysis.unavailable_models.forEach(m => {
        console.log(`  - ${m}`);
      });
    }
  }
}

// ============================================================================
// RUN EXAMPLES
// ============================================================================

async function runExamples() {
  console.log('='.repeat(70));
  console.log('Circuit Breaker Integration Examples');
  console.log('='.repeat(70));

  try {
    await example1_WeightedVotingWithCircuitBreaker();
    await example2_WorkerOrchestrationWithCircuitBreaker();
    await example3_MonitoringAndRecovery();
    await example4_GracefulDegradation();
    await example5_AllModelsFailed();

    console.log('\n' + '='.repeat(70));
    console.log('✓ All examples completed successfully');
    console.log('='.repeat(70) + '\n');

    // Clean up test circuits
    const circuitBreaker = getCircuitBreaker();
    await circuitBreaker.resetCircuit('gpt-4o');
    await circuitBreaker.resetCircuit('worker-1');
    await circuitBreaker.resetCircuit('worker-2');
    await circuitBreaker.resetCircuit('worker-3');
    await circuitBreaker.resetCircuit('primary-model');
    await circuitBreaker.resetCircuit('secondary-model');
    await circuitBreaker.resetCircuit('failed-1');
    await circuitBreaker.resetCircuit('failed-2');
    await circuitBreaker.resetCircuit('failed-3');

    console.log('Test circuits cleaned up\n');

    process.exit(0);

  } catch (err) {
    console.error('\n❌ Example failed:', err);
    console.error(err.stack);
    process.exit(1);
  }
}

runExamples();
