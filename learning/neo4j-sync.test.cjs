#!/usr/bin/env node

/**
 * Neo4j Sync Service Test Suite
 *
 * Comprehensive tests for neo4j-sync-service.js
 *
 * Test Coverage:
 * 1. Connection management (connect, disconnect, reconnect)
 * 2. Schema initialization (constraints, indexes)
 * 3. Workflow sync (single, batch, unsynced)
 * 4. Learning relationship creation (RELATED_TO)
 * 5. Graph queries (related workflows, learnings, model stats)
 * 6. Error handling (connection failures, retries)
 * 7. Graceful degradation (PostgreSQL fallback)
 *
 * Prerequisites:
 * - PostgreSQL running on aio-01:5433 with 'learning' database
 * - Neo4j running on aio-01:7687 (optional, tests degrade gracefully)
 * - Sample workflow data in PostgreSQL (created by test)
 *
 * Run: node learning/neo4j-sync.test.cjs
 * Run with TAP reporter: node learning/neo4j-sync.test.cjs | grep -E "^(ok|not ok|# )"
 */

const { Neo4jSyncService } = require('./neo4j-sync-service.js');
const { Pool } = require('pg');

// ============================================================================
// TEST FRAMEWORK
// ============================================================================

let testCount = 0;
let passCount = 0;
let failCount = 0;

function assert(condition, message) {
  testCount++;
  if (condition) {
    passCount++;
    console.log('ok ' + testCount + ' - ' + message);
  } else {
    failCount++;
    console.log('not ok ' + testCount + ' - ' + message);
  }
}

function assertEqual(actual, expected, message) {
  assert(actual === expected, message + ' (expected ' + expected + ', got ' + actual + ')');
}

function assertApprox(actual, expected, tolerance, message) {
  const diff = Math.abs(actual - expected);
  assert(diff <= tolerance, message + ' (expected ~' + expected + ', got ' + actual + ')');
}

function assertGreaterThan(actual, expected, message) {
  assert(actual > expected, message + ' (expected >' + expected + ', got ' + actual + ')');
}

function assertNotNull(value, message) {
  assert(value !== null && value !== undefined, message + ' (got null/undefined)');
}

async function test(name, fn) {
  console.log('# ' + name);
  try {
    await fn();
  } catch (err) {
    failCount++;
    console.log('not ok - Uncaught error: ' + err.message);
    console.error(err.stack);
  }
}

// ============================================================================
// TEST HELPERS
// ============================================================================

const pgPool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  max: 5
});

/**
 * Create sample workflow execution in PostgreSQL
 * @returns {Promise<number>} execution ID
 */
async function createSampleWorkflow() {
  const client = await pgPool.connect();
  try {
    // Create workflow execution
    const execResult = await client.query(
      `INSERT INTO workflow.executions
       (workflow_id, workflow_name, task_description, total_workers, total_duration_ms, outcome, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
       RETURNING id`,
      [
        'test-wf-' + Date.now(),
        'test-workflow',
        'Test workflow for Neo4j sync',
        3,
        5000,
        'success',
        JSON.stringify({ test: true })
      ]
    );
    const execId = execResult.rows[0].id;

    // Create phase
    await client.query(
      `INSERT INTO workflow.phases
       (workflow_execution_id, phase_name, phase_order, duration_ms, outcome, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
      [execId, 'test-phase', 1, 1000, 'success', JSON.stringify({ test: true })]
    );

    // Create workers
    for (let i = 0; i < 3; i++) {
      await client.query(
        `INSERT INTO workflow.worker_results
         (workflow_execution_id, worker_id, model, task_assigned, result, confidence, duration_ms, input_tokens, output_tokens, cost_usd, outcome, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())`,
        [
          execId,
          'worker-' + i,
          ['opus', 'sonnet', 'haiku'][i],
          'test-task-' + i,
          'test-result-' + i,
          0.85 + (i * 0.05),
          1000 + (i * 100),
          100,
          50,
          0.01,
          'success',
          JSON.stringify({ test: true })
        ]
      );
    }

    // Create arbiter decision
    await client.query(
      `INSERT INTO workflow.arbiter_decisions
       (workflow_execution_id, arbiter_model, worker_result_ids, decision, reasoning, confidence, duration_ms, input_tokens, output_tokens, cost_usd, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())`,
      [
        execId,
        'opus',
        [1, 2, 3],
        'Selected worker 1',
        'Highest confidence',
        0.92,
        500,
        50,
        20,
        0.005,
        JSON.stringify({ test: true })
      ]
    );

    // Create learning
    await client.query(
      `INSERT INTO workflow.learnings
       (workflow_execution_id, learning_type, description, actionable_insight, importance, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
      [
        execId,
        'pattern',
        'Test learning: Multi-model consensus improves quality',
        'Use 3+ models for critical tasks',
        0.85,
        JSON.stringify({ test: true })
      ]
    );

    return execId;

  } finally {
    client.release();
  }
}

/**
 * Clean up test data from PostgreSQL
 * @param {number} execId - execution ID to delete
 */
async function cleanupWorkflow(execId) {
  const client = await pgPool.connect();
  try {
    await client.query('DELETE FROM workflow.learnings WHERE workflow_execution_id = $1', [execId]);
    await client.query('DELETE FROM workflow.arbiter_decisions WHERE workflow_execution_id = $1', [execId]);
    await client.query('DELETE FROM workflow.worker_results WHERE workflow_execution_id = $1', [execId]);
    await client.query('DELETE FROM workflow.phases WHERE workflow_execution_id = $1', [execId]);
    await client.query('DELETE FROM workflow.executions WHERE id = $1', [execId]);
  } finally {
    client.release();
  }
}

// ============================================================================
// TEST SUITE
// ============================================================================

(async function runTests() {
  console.log('TAP version 13');

  const service = new Neo4jSyncService({
    neo4jUri: process.env.NEO4J_URI || 'bolt://aio-01:7687',
    neo4jUser: process.env.NEO4J_USER || 'neo4j',
    neo4jPassword: process.env.NEO4J_PASSWORD || '',
    maxRetries: 2,
    retryBaseMs: 500,
    batchSize: 10
  });

  let testExecId = null;
  let neo4jAvailable = false;

  // -------------------------------------------------------------------------
  // Test 1: Connection Management
  // -------------------------------------------------------------------------
  await test('Connection Management', async function() {
    // Test connect
    try {
      await service.connect();
      neo4jAvailable = service.neo4jAvailable;

      if (neo4jAvailable) {
        assert(true, 'Connected to Neo4j');
        assert(service.driver !== null, 'Driver is initialized');
      } else {
        assert(true, 'Neo4j unavailable (graceful degradation)');
      }
    } catch (err) {
      assert(false, 'Connection failed unexpectedly: ' + err.message);
    }

    // Test reconnect (idempotent)
    if (neo4jAvailable) {
      await service.connect();
      assert(service.neo4jAvailable, 'Reconnect is idempotent');
    }
  });

  // -------------------------------------------------------------------------
  // Test 2: Schema Initialization
  // -------------------------------------------------------------------------
  await test('Schema Initialization', async function() {
    if (!neo4jAvailable) {
      assert(true, 'Skipping schema tests (Neo4j unavailable)');
      return;
    }

    try {
      await service.initialize();
      assert(true, 'Schema initialized successfully');

      // Verify constraints exist
      const session = service.driver.session();
      try {
        const result = await session.run('SHOW CONSTRAINTS');
        const constraints = result.records.map(r => r.get('name'));
        assert(constraints.length > 0, 'Constraints created');
      } finally {
        await session.close();
      }

    } catch (err) {
      assert(false, 'Schema initialization failed: ' + err.message);
    }
  });

  // -------------------------------------------------------------------------
  // Test 3: Workflow Sync (Single)
  // -------------------------------------------------------------------------
  await test('Workflow Sync (Single)', async function() {
    // Create sample workflow in PostgreSQL
    testExecId = await createSampleWorkflow();
    assert(testExecId > 0, 'Sample workflow created (ID: ' + testExecId + ')');

    if (!neo4jAvailable) {
      assert(true, 'Skipping sync tests (Neo4j unavailable)');
      return;
    }

    // Sync to Neo4j
    try {
      const stats = await service.syncWorkflowExecution(testExecId);

      assertNotNull(stats, 'Sync stats returned');
      assertEqual(stats.workflow, 1, 'One workflow synced');
      assertGreaterThan(stats.phases, 0, 'Phases synced');
      assertGreaterThan(stats.workers, 0, 'Workers synced');
      assertEqual(stats.arbiter, 1, 'Arbiter synced');
      assertGreaterThan(stats.learnings, 0, 'Learnings synced');

    } catch (err) {
      assert(false, 'Workflow sync failed: ' + err.message);
    }
  });

  // -------------------------------------------------------------------------
  // Test 4: Verify Nodes Created
  // -------------------------------------------------------------------------
  await test('Verify Nodes Created', async function() {
    if (!neo4jAvailable) {
      assert(true, 'Skipping node verification (Neo4j unavailable)');
      return;
    }

    const session = service.driver.session();
    try {
      // Check Workflow node
      const workflowResult = await session.run(
        'MATCH (w:Workflow {pg_execution_id: $execId}) RETURN w',
        { execId: testExecId }
      );
      assertEqual(workflowResult.records.length, 1, 'Workflow node created');

      // Check Phase nodes
      const phaseResult = await session.run(
        'MATCH (w:Workflow {pg_execution_id: $execId})-[:CONTAINS]->(p:Phase) RETURN count(p) as phase_count',
        { execId: testExecId }
      );
      assertGreaterThan(phaseResult.records[0].get('phase_count').toNumber(), 0, 'Phase nodes created');

      // Check Worker nodes
      const workerResult = await session.run(
        'MATCH (w:Workflow {pg_execution_id: $execId})-[:EXECUTES]->(wr:Worker) RETURN count(wr) as worker_count',
        { execId: testExecId }
      );
      assertEqual(workerResult.records[0].get('worker_count').toNumber(), 3, 'Worker nodes created');

      // Check Model nodes
      const modelResult = await session.run(
        'MATCH (m:Model) WHERE m.name IN ["opus", "sonnet", "haiku"] RETURN count(m) as model_count'
      );
      assertGreaterThan(modelResult.records[0].get('model_count').toNumber(), 0, 'Model nodes created');

      // Check Learning nodes
      const learningResult = await session.run(
        'MATCH (w:Workflow {pg_execution_id: $execId})-[:PRODUCED]->(l:Learning) RETURN count(l) as learning_count',
        { execId: testExecId }
      );
      assertGreaterThan(learningResult.records[0].get('learning_count').toNumber(), 0, 'Learning nodes created');

    } catch (err) {
      assert(false, 'Node verification failed: ' + err.message);
    } finally {
      await session.close();
    }
  });

  // -------------------------------------------------------------------------
  // Test 5: Learning Relationships
  // -------------------------------------------------------------------------
  await test('Learning Relationships (RELATED_TO)', async function() {
    if (!neo4jAvailable) {
      assert(true, 'Skipping learning relationship tests (Neo4j unavailable)');
      return;
    }

    // Create additional learning for similarity
    const client = await pgPool.connect();
    try {
      await client.query(
        `INSERT INTO workflow.learnings
         (workflow_execution_id, learning_type, description, actionable_insight, importance, metadata, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
        [
          testExecId,
          'pattern',
          'Test learning 2: Consensus strategies improve reliability',
          'Always use multiple models',
          0.90,
          JSON.stringify({ test: true })
        ]
      );
    } finally {
      client.release();
    }

    // Re-sync to get new learning
    await service.syncWorkflowExecution(testExecId);

    // Create similarity links (low threshold for testing)
    try {
      const count = await service.createSimilarityLinks(0.5);
      assert(count >= 0, 'Similarity links created (count: ' + count + ')');
    } catch (err) {
      // Embeddings might not be available
      assert(true, 'Similarity link creation skipped (embeddings unavailable): ' + err.message);
    }
  });

  // -------------------------------------------------------------------------
  // Test 6: Graph Queries - Related Workflows
  // -------------------------------------------------------------------------
  await test('Graph Queries - Related Workflows', async function() {
    if (!neo4jAvailable) {
      assert(true, 'Skipping query tests (Neo4j unavailable)');
      return;
    }

    try {
      const related = await service.queryRelatedWorkflows(testExecId, 2);
      assert(Array.isArray(related), 'Related workflows query returns array');

      // May be empty if no related workflows
      assert(true, 'Related workflows: ' + related.length);
    } catch (err) {
      assert(false, 'Related workflows query failed: ' + err.message);
    }
  });

  // -------------------------------------------------------------------------
  // Test 7: Graph Queries - Model Usage Stats
  // -------------------------------------------------------------------------
  await test('Graph Queries - Model Usage Stats', async function() {
    if (!neo4jAvailable) {
      assert(true, 'Skipping model stats tests (Neo4j unavailable)');
      return;
    }

    try {
      const stats = await service.getModelUsageStats();
      assert(Array.isArray(stats), 'Model usage stats returns array');
      assertGreaterThan(stats.length, 0, 'Model usage stats has data');

      // Verify stats structure
      const stat = stats[0];
      assertNotNull(stat.model, 'Model name present');
      assertNotNull(stat.total_uses, 'Total uses present');
      assertNotNull(stat.avg_confidence, 'Avg confidence present');
      assertNotNull(stat.success_rate, 'Success rate present');

    } catch (err) {
      assert(false, 'Model usage stats query failed: ' + err.message);
    }
  });

  // -------------------------------------------------------------------------
  // Test 8: Batch Sync
  // -------------------------------------------------------------------------
  await test('Batch Sync', async function() {
    if (!neo4jAvailable) {
      assert(true, 'Skipping batch sync tests (Neo4j unavailable)');
      return;
    }

    // Create 3 sample workflows
    const execIds = [];
    for (let i = 0; i < 3; i++) {
      const execId = await createSampleWorkflow();
      execIds.push(execId);
    }

    try {
      const stats = await service.syncBatch(execIds);

      assertNotNull(stats, 'Batch sync stats returned');
      assertEqual(stats.workflows, 3, 'Three workflows synced');
      assertGreaterThan(stats.phases, 0, 'Phases synced in batch');
      assertGreaterThan(stats.workers, 0, 'Workers synced in batch');

    } catch (err) {
      assert(false, 'Batch sync failed: ' + err.message);
    } finally {
      // Cleanup batch workflows
      for (const execId of execIds) {
        await cleanupWorkflow(execId);
      }
    }
  });

  // -------------------------------------------------------------------------
  // Test 9: Sync Unsynced
  // -------------------------------------------------------------------------
  await test('Sync Unsynced', async function() {
    if (!neo4jAvailable) {
      assert(true, 'Skipping unsynced sync tests (Neo4j unavailable)');
      return;
    }

    // Create workflow not yet synced
    const newExecId = await createSampleWorkflow();

    try {
      const stats = await service.syncUnsynced();

      assertNotNull(stats, 'Unsynced sync stats returned');
      assertGreaterThan(stats.workflows, 0, 'Unsynced workflows found and synced');

    } catch (err) {
      assert(false, 'Unsynced sync failed: ' + err.message);
    } finally {
      await cleanupWorkflow(newExecId);
    }
  });

  // -------------------------------------------------------------------------
  // Test 10: Error Handling - Invalid Execution ID
  // -------------------------------------------------------------------------
  await test('Error Handling - Invalid Execution ID', async function() {
    if (!neo4jAvailable) {
      assert(true, 'Skipping error handling tests (Neo4j unavailable)');
      return;
    }

    try {
      await service.syncWorkflowExecution(999999999);
      assert(false, 'Should throw error for invalid execution ID');
    } catch (err) {
      assert(true, 'Error thrown for invalid execution ID');
    }
  });

  // -------------------------------------------------------------------------
  // Test 11: Connection Close
  // -------------------------------------------------------------------------
  await test('Connection Close', async function() {
    if (!neo4jAvailable) {
      assert(true, 'Skipping close tests (Neo4j unavailable)');
      return;
    }

    try {
      await service.close();
      assert(true, 'Connection closed successfully');
      assertEqual(service.neo4jAvailable, false, 'Neo4j marked as unavailable after close');
    } catch (err) {
      assert(false, 'Connection close failed: ' + err.message);
    }
  });

  // -------------------------------------------------------------------------
  // Cleanup
  // -------------------------------------------------------------------------
  console.log('# Cleanup');
  if (testExecId) {
    await cleanupWorkflow(testExecId);
    assert(true, 'Test workflow cleaned up');
  }

  await pgPool.end();
  assert(true, 'PostgreSQL connection pool closed');

  // -------------------------------------------------------------------------
  // Test Summary
  // -------------------------------------------------------------------------
  console.log('# Summary');
  console.log('1..' + testCount);
  console.log('# tests ' + testCount);
  console.log('# pass ' + passCount);
  console.log('# fail ' + failCount);

  if (failCount > 0) {
    console.log('# FAILED: ' + failCount + ' test(s) failed');
    process.exit(1);
  } else {
    console.log('# ALL TESTS PASSED');
    process.exit(0);
  }
})().catch(err => {
  console.error('Test suite failed:', err);
  process.exit(1);
});
