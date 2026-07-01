#!/usr/bin/env node

/**
 * Simple Knowledge Sync Test - Just tests knowledge_sync.py integration
 */

const { shareDiscovery, verifyDiscovery, getFleetKnowledge, getStats } = require('../shared/knowledge-sync-integration.cjs');

async function test() {
  console.log('Knowledge Sync Simple Integration Test\n');

  // Share discovery
  console.log('1. Sharing discovery...');
  const id = await shareDiscovery({
    workerId: 'simple-test-worker',
    type: 'integration',
    content: 'Simple integration test: knowledge_sync.py is wired correctly',
    confidence: 0.9
  });
  console.log(`✅ Shared discovery ID: ${id}\n`);

  // Verify it
  console.log('2. Verifying discovery...');
  for (let i = 1; i <= 3; i++) {
    await verifyDiscovery({
      discoveryId: id,
      workerId: `verifier-${i}`,
      approve: true,
      reasoning: `Verification ${i}/3`
    });
  }
  console.log('✅ Discovery verified by 3 workers\n');

  // Query knowledge
  console.log('3. Querying fleet knowledge...');
  const knowledge = await getFleetKnowledge({ minConfidence: 0.8, limit: 5 });
  console.log(`✅ Retrieved ${knowledge.length} verified discoveries\n`);

  // Stats
  console.log('4. Statistics:');
  const stats = await getStats();
  console.log(`   Total: ${stats.total}, Verified: ${stats.verified}, Pending: ${stats.pending}`);
  console.log(`   Active workers: ${stats.active_workers}\n`);

  console.log('✅ Knowledge sync integration working correctly!');
}

test().catch(err => {
  console.error('❌ Test failed:', err.message);
  process.exit(1);
});
