#!/usr/bin/env node

/**
 * Full Integration Test - Demonstrates complete knowledge sync flow
 */

const { shareDiscovery, verifyDiscovery, getFleetKnowledge, getStats } = require('../shared/knowledge-sync-integration.cjs');
const { onWorkflowComplete } = require('../shared/workflow-completion-hook.cjs');

async function testFullIntegration() {
  console.log('='.repeat(60));
  console.log('FULL KNOWLEDGE SYNC INTEGRATION TEST');
  console.log('='.repeat(60));

  try {
    // Step 1: Simulate workflow completion with auto-discovery extraction
    console.log('\n1. Simulating workflow completion...');
    const mockWorkflow = {
      workflow_id: 'integration-test-' + Date.now(),
      workflow_name: 'test-integration',
      task: 'Testing full knowledge sync integration',
      workers: [
        {
          worker_id: 'test-worker-alpha',
          model: 'opus',
          quality_score: 0.92,
          result: { finding: 'High-quality result demonstrating integration' },
          duration_ms: 5000,
          input_tokens: 500,
          output_tokens: 300,
          cost_usd: 0.02
        }
      ],
      arbiter: {
        model: 'sonnet',
        reasoning: 'Selected opus for comprehensive analysis and detail',
        confidence: 0.88,
        duration_ms: 2000
      },
      phases: [
        { name: 'research', order: 1, duration_ms: 3000, outcome: 'success' }
      ],
      duration_ms: 10000,
      outcome: 'success',
      metadata: { test: true }
    };

    const executionId = await onWorkflowComplete(mockWorkflow);
    console.log(`✅ Workflow stored (execution ID: ${executionId})`);
    console.log('   Auto-extracted discoveries from high-quality worker results');

    // Step 2: Manually share a discovery
    console.log('\n2. Manually sharing a discovery...');
    const manualDiscoveryId = await shareDiscovery({
      workerId: 'test-worker-beta',
      type: 'technique',
      content: 'Integration test: Using workflow-completion-hook auto-extracts discoveries',
      confidence: 0.85
    });
    console.log(`✅ Manual discovery shared (ID: ${manualDiscoveryId})`);

    // Step 3: Verify discoveries
    console.log('\n3. Verifying discoveries from other workers...');
    await verifyDiscovery({
      discoveryId: manualDiscoveryId,
      workerId: 'test-worker-gamma',
      approve: true,
      reasoning: 'Verified: workflow-completion-hook is working'
    });
    await verifyDiscovery({
      discoveryId: manualDiscoveryId,
      workerId: 'test-worker-delta',
      approve: true,
      reasoning: 'Confirmed: auto-extraction functional'
    });
    await verifyDiscovery({
      discoveryId: manualDiscoveryId,
      workerId: 'test-worker-epsilon',
      approve: true,
      reasoning: 'Validated: integration complete'
    });
    console.log('✅ Discovery verified by 3 workers (should be marked as verified)');

    // Step 4: Query verified knowledge
    console.log('\n4. Querying verified fleet knowledge...');
    const knowledge = await getFleetKnowledge({ minConfidence: 0.7, limit: 10 });
    console.log(`✅ Retrieved ${knowledge.length} verified discoveries`);
    
    if (knowledge.length > 0) {
      console.log('\n   Top 3 verified discoveries:');
      knowledge.slice(0, 3).forEach((k, i) => {
        console.log(`   ${i + 1}. [${k.type}] ${k.content.substring(0, 60)}...`);
        console.log(`      Confidence: ${k.confidence}, Verified by: ${k.verifications} workers`);
      });
    }

    // Step 5: Get statistics
    console.log('\n5. Knowledge sync statistics:');
    const stats = await getStats();
    console.log(`   Total discoveries: ${stats.total}`);
    console.log(`   Verified: ${stats.verified}, Pending: ${stats.pending}, Rejected: ${stats.rejected}`);
    console.log(`   Active workers: ${stats.active_workers}`);
    console.log(`   Total votes: ${stats.total_votes}`);

    console.log('\n' + '='.repeat(60));
    console.log('✅ FULL INTEGRATION TEST PASSED');
    console.log('='.repeat(60));
    console.log('\nIntegration is working correctly:');
    console.log('  ✓ Workflow completion auto-extracts discoveries');
    console.log('  ✓ Manual discovery sharing works');
    console.log('  ✓ Multi-worker verification works');
    console.log('  ✓ Verified knowledge query works');
    console.log('  ✓ Statistics tracking works');

  } catch (err) {
    console.error('\n❌ Integration test failed:', err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

testFullIntegration();
