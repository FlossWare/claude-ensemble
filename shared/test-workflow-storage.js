#!/usr/bin/env node
/**
 * Test Workflow Storage Adapter
 *
 * Validates database schema, embedding generation, and core methods.
 */

const { getWorkflowStorage } = require('./workflow-storage-adapter');

async function testWorkflowStorage() {
  console.log('Testing Workflow Storage Adapter...\n');

  const storage = getWorkflowStorage();

  try {
    // Test 1: Store workflow execution
    console.log('Test 1: Store workflow execution');
    const workflowId = `test-workflow-${Date.now()}`;
    const executionId = await storage.storeExecution({
      workflow_id: workflowId,
      workflow_name: 'deep-research',
      task_description: 'Research quantum computing advances in 2025',
      total_workers: 3,
      total_duration_ms: 45000,
      outcome: 'success',
      metadata: {
        test: true,
        phase_count: 3
      }
    });
    console.log(`✓ Stored workflow execution ID: ${executionId}\n`);

    // Test 2: Store worker results
    console.log('Test 2: Store worker results');
    const worker1Id = await storage.storeWorkerResult({
      workflow_execution_id: executionId,
      worker_id: 'worker-1',
      model: 'opus',
      task_assigned: 'Search for quantum computing research papers',
      result: 'Found 15 papers on quantum error correction and fault-tolerant quantum computing',
      confidence: 0.85,
      duration_ms: 12000,
      input_tokens: 500,
      output_tokens: 1200,
      cost_usd: 0.025,
      outcome: 'success',
      metadata: { sources: 15 }
    });
    console.log(`✓ Stored worker 1 result ID: ${worker1Id}`);

    const worker2Id = await storage.storeWorkerResult({
      workflow_execution_id: executionId,
      worker_id: 'worker-2',
      model: 'sonnet',
      task_assigned: 'Search for quantum computing industry applications',
      result: 'IBM and Google announced new quantum processors with 1000+ qubits',
      confidence: 0.90,
      duration_ms: 10000,
      input_tokens: 450,
      output_tokens: 1000,
      cost_usd: 0.015,
      outcome: 'success',
      metadata: { sources: 8 }
    });
    console.log(`✓ Stored worker 2 result ID: ${worker2Id}\n`);

    // Test 3: Store arbiter decision
    console.log('Test 3: Store arbiter decision');
    const arbiterId = await storage.storeArbiterDecision({
      workflow_execution_id: executionId,
      arbiter_model: 'opus',
      worker_result_ids: [worker1Id, worker2Id],
      decision: 'Quantum computing made significant progress in 2025 with error correction and larger processors',
      reasoning: 'Both workers found consistent evidence of progress in quantum computing',
      confidence: 0.88,
      duration_ms: 8000,
      input_tokens: 2700,
      output_tokens: 800,
      cost_usd: 0.020,
      metadata: { consensus_level: 'high' }
    });
    console.log(`✓ Stored arbiter decision ID: ${arbiterId}\n`);

    // Test 4: Store workflow phase
    console.log('Test 4: Store workflow phases');
    await storage.storePhase({
      workflow_execution_id: executionId,
      phase_name: 'search',
      phase_order: 1,
      duration_ms: 22000,
      outcome: 'success',
      metadata: { workers_spawned: 2 }
    });

    await storage.storePhase({
      workflow_execution_id: executionId,
      phase_name: 'verify',
      phase_order: 2,
      duration_ms: 15000,
      outcome: 'success',
      metadata: { claims_verified: 5 }
    });

    await storage.storePhase({
      workflow_execution_id: executionId,
      phase_name: 'synthesize',
      phase_order: 3,
      duration_ms: 8000,
      outcome: 'success',
      metadata: { final_arbiter: 'opus' }
    });
    console.log('✓ Stored 3 workflow phases\n');

    // Test 5: Store feedback
    console.log('Test 5: Store feedback');
    await storage.storeFeedback({
      workflow_execution_id: executionId,
      feedback_type: 'automated',
      quality_score: 0.87,
      feedback_text: 'High-quality synthesis with good source coverage',
      metadata: { evaluator: 'quality-checker' }
    });
    console.log('✓ Stored automated feedback\n');

    // Test 6: Store learnings
    console.log('Test 6: Store learnings');
    await storage.storeLearnings({
      workflow_execution_id: executionId,
      learning_type: 'pattern',
      description: 'Opus and Sonnet show high consensus on technical topics',
      actionable_insight: 'Use Opus+Sonnet combination for technical research tasks',
      importance: 0.75,
      metadata: { domain: 'quantum-computing' }
    });
    console.log('✓ Stored learning\n');

    // Test 7: Query similar workflows
    console.log('Test 7: Query similar workflows');
    const similar = await storage.findSimilarWorkflows(
      'Research advances in quantum computing',
      5
    );
    console.log(`✓ Found ${similar.length} similar workflow(s)`);
    if (similar.length > 0) {
      console.log(`  Most similar: ${similar[0].workflow_name} (distance: ${similar[0].distance})\n`);
    }

    // Test 8: Get complete workflow data
    console.log('Test 8: Get complete workflow data');
    const complete = await storage.getWorkflowComplete(workflowId);
    console.log(`✓ Retrieved complete workflow data:`);
    console.log(`  - Execution: ${complete.execution.workflow_name}`);
    console.log(`  - Workers: ${complete.workers.length}`);
    console.log(`  - Arbiters: ${complete.arbiters.length}`);
    console.log(`  - Phases: ${complete.phases.length}`);
    console.log(`  - Feedback: ${complete.feedback.length}`);
    console.log(`  - Learnings: ${complete.learnings.length}\n`);

    console.log('✅ All tests passed!');

  } catch (err) {
    console.error('❌ Test failed:', err);
    process.exit(1);
  } finally {
    await storage.close();
  }
}

testWorkflowStorage();
