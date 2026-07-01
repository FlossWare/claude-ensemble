#!/usr/bin/env node

/**
 * Verify Knowledge Sync Integration
 *
 * Tests:
 *   1. knowledge_sync.py is callable from Node.js
 *   2. Discoveries can be shared and verified
 *   3. Fleet knowledge is retrievable
 *   4. workflow-completion-hook integration works
 *   5. Neo4j sync daemon can connect
 *
 * Usage:
 *   node scripts/verify-knowledge-sync.js
 */

const {
  shareDiscovery,
  verifyDiscovery,
  getFleetKnowledge,
  getPendingDiscoveries,
  getStats,
  extractWorkflowDiscoveries
} = require('../shared/knowledge-sync-integration.cjs');

const { KnowledgeSyncDaemon } = require('../services/knowledge-sync-daemon.cjs');

async function runTests() {
  console.log('='.repeat(60));
  console.log('KNOWLEDGE SYNC INTEGRATION VERIFICATION');
  console.log('='.repeat(60));

  let testsPassed = 0;
  let testsFailed = 0;

  // Test 1: Share discovery
  try {
    console.log('\n[Test 1] Sharing discovery via knowledge_sync.py...');
    const discoveryId = await shareDiscovery({
      workerId: 'test-worker-01',
      type: 'optimization',
      content: 'Integration test: HNSW index provides 2x faster similarity search than sequential scan',
      confidence: 0.9
    });

    console.log(`✅ PASS: Shared discovery (ID: ${discoveryId})`);
    testsPassed++;

    // Test 2: Verify discovery
    try {
      console.log('\n[Test 2] Verifying discovery from another worker...');
      const result = await verifyDiscovery({
        discoveryId,
        workerId: 'test-worker-02',
        approve: true,
        reasoning: 'Confirmed in integration testing'
      });

      console.log(`✅ PASS: Verified discovery (${result.verifications} verifications, ${result.rejections} rejections, status: ${result.status})`);
      testsPassed++;
    } catch (err) {
      console.error(`❌ FAIL: ${err.message}`);
      testsFailed++;
    }

    // Test 3: Get pending discoveries
    try {
      console.log('\n[Test 3] Fetching pending discoveries...');
      const pending = await getPendingDiscoveries({ limit: 5 });
      console.log(`✅ PASS: Retrieved ${pending.length} pending discoveries`);
      testsPassed++;
    } catch (err) {
      console.error(`❌ FAIL: ${err.message}`);
      testsFailed++;
    }

    // Test 4: Get fleet knowledge
    try {
      console.log('\n[Test 4] Fetching verified fleet knowledge...');
      const knowledge = await getFleetKnowledge({ minConfidence: 0.7, limit: 10 });
      console.log(`✅ PASS: Retrieved ${knowledge.length} verified knowledge entries`);

      if (knowledge.length > 0) {
        console.log(`   Sample: [${knowledge[0].type}] ${knowledge[0].content.substring(0, 60)}... (confidence: ${knowledge[0].confidence})`);
      }
      testsPassed++;
    } catch (err) {
      console.error(`❌ FAIL: ${err.message}`);
      testsFailed++;
    }

    // Test 5: Get statistics
    try {
      console.log('\n[Test 5] Fetching knowledge sync statistics...');
      const stats = await getStats();
      console.log(`✅ PASS: Stats retrieved`);
      console.log(`   Total discoveries: ${stats.total}`);
      console.log(`   Verified: ${stats.verified}, Pending: ${stats.pending}, Rejected: ${stats.rejected}`);
      console.log(`   Active workers: ${stats.active_workers}`);
      console.log(`   Total votes: ${stats.total_votes}`);
      testsPassed++;
    } catch (err) {
      console.error(`❌ FAIL: ${err.message}`);
      testsFailed++;
    }

  } catch (err) {
    console.error(`❌ FAIL: ${err.message}`);
    testsFailed++;
  }

  // Test 6: Extract discoveries from workflow data
  try {
    console.log('\n[Test 6] Extracting discoveries from workflow completion...');
    const mockWorkflowData = {
      workflow_id: 'test-workflow-001',
      workflow_name: 'test-deep-research',
      task: 'Test task description',
      workers: [
        {
          worker_id: 'test-worker-03',
          id: 'test-worker-03',
          model: 'opus',
          quality_score: 0.85,
          result: { finding: 'Test finding with high quality' }
        }
      ],
      arbiter: {
        model: 'sonnet',
        reasoning: 'Selected opus result for superior detail and accuracy',
        confidence: 0.82
      },
      outcome: 'success',
      duration_ms: 45000,
      metadata: {}
    };

    const discoveries = await extractWorkflowDiscoveries(mockWorkflowData);
    console.log(`✅ PASS: Extracted ${discoveries.length} discoveries from workflow data`);
    testsPassed++;
  } catch (err) {
    console.error(`❌ FAIL: ${err.message}`);
    testsFailed++;
  }

  // Test 7: Neo4j daemon connectivity
  try {
    console.log('\n[Test 7] Testing Neo4j sync daemon connectivity...');
    const daemon = new KnowledgeSyncDaemon();
    const status = await daemon.getStatus();

    console.log(`✅ PASS: Daemon status retrieved`);
    console.log(`   Database discoveries - Total: ${status.database.total}, Verified: ${status.database.verified}, Unsynced: ${status.database.unsynced}`);
    console.log(`   Neo4j available: ${status.neo4j.available}`);

    await daemon.disconnect();
    testsPassed++;
  } catch (err) {
    console.error(`❌ FAIL: ${err.message}`);
    testsFailed++;
  }

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('TEST SUMMARY');
  console.log('='.repeat(60));
  console.log(`✅ Passed: ${testsPassed}`);
  console.log(`❌ Failed: ${testsFailed}`);
  console.log(`Total: ${testsPassed + testsFailed}`);

  if (testsFailed === 0) {
    console.log('\n🎉 ALL TESTS PASSED - Knowledge sync integration is working!');
    console.log('\nNext steps:');
    console.log('1. Start knowledge sync daemon: node services/knowledge-sync-daemon.js');
    console.log('2. Check daemon status: node services/knowledge-sync-daemon.js --status');
    console.log('3. Run workflows to generate discoveries automatically');
    console.log('4. Query fleet knowledge: require("./shared/knowledge-sync-integration").getFleetKnowledge()');
  } else {
    console.log('\n⚠️  Some tests failed. Check error messages above.');
    process.exit(1);
  }
}

// Run tests
runTests().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
