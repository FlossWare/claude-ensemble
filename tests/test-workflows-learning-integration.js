#!/usr/bin/env node
/**
 * Test: Workflows Learning Integration
 *
 * Verifies:
 * 1. Database schema exists
 * 2. WorkflowsLearning class works correctly
 * 3. Reaction signals are persisted
 * 4. Queries return expected data
 * 5. Traceability via run_id works
 *
 * Usage:
 *   node test-workflows-learning-integration.js
 */

const { getWorkflowsLearning, getDB, OUTCOMES } = require('../../learning/postgres-adapter');
const { randomBytes } = require('crypto');

let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  ✓ ${message}`);
    testsPassed++;
  } else {
    console.error(`  ✗ ${message}`);
    testsFailed++;
  }
}

async function testDatabaseConnection() {
  console.log('\n=== Test 1: Database Connection ===\n');

  try {
    const db = getDB();
    const result = await db.query('SELECT 1 AS test');
    assert(result.length === 1 && result[0].test === 1, 'PostgreSQL connection works');
  } catch (error) {
    assert(false, `PostgreSQL connection failed: ${error.message}`);
  }
}

async function testSchemaExists() {
  console.log('\n=== Test 2: Workflows Schema Exists ===\n');

  try {
    const db = getDB();

    // Check if workflows schema exists
    const schemas = await db.query(
      "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'workflows'"
    );
    assert(schemas.length === 1, 'workflows schema exists');

    // Check if learnings table exists
    const tables = await db.query(
      "SELECT table_name FROM information_schema.tables WHERE table_schema = 'workflows' AND table_name = 'learnings'"
    );
    assert(tables.length === 1, 'workflows.learnings table exists');

    // Check if runs table exists
    const runsTables = await db.query(
      "SELECT table_name FROM information_schema.tables WHERE table_schema = 'workflows' AND table_name = 'runs'"
    );
    assert(runsTables.length === 1, 'workflows.runs table exists');

    // Check if views exist
    const views = await db.query(
      "SELECT table_name FROM information_schema.views WHERE table_schema = 'workflows'"
    );
    assert(views.length >= 3, `workflows views exist (found ${views.length})`);

  } catch (error) {
    assert(false, `Schema check failed: ${error.message}`);
  }
}

async function testRecordLearning() {
  console.log('\n=== Test 3: Record Learning ===\n');

  try {
    const workflowsLearning = getWorkflowsLearning();
    const run_id = `test_run_${Date.now()}_${randomBytes(4).toString('hex')}`;

    const reactionSignals = {
      avg_composite_score: 78,
      avg_uncertainty: 32,
      total_self_corrections: 2,
      estimated_difficulty: 'moderate',
      model_count: 3
    };

    const result = await workflowsLearning.recordLearning({
      run_id: run_id,
      workflow_name: 'test-workflow',
      learning_type: 'model_behavior',
      reaction_signals: reactionSignals,
      task_difficulty: 'moderate',
      task_type: 'test',
      task_summary: 'Test task summary',
      quality_score: 0.85,
      outcome: OUTCOMES.SUCCESS,
      model_count: 3,
      polarization_index: 25,
      behavioral_agreement: 85,
      duration_ms: 1500,
      cost_usd: 0.003,
      metadata: { test_field: 'test_value' }
    });

    assert(result.id > 0, `Learning recorded with ID: ${result.id}`);
    assert(result.created_at !== null, 'created_at timestamp is set');

    // Verify data was inserted
    const db = getDB();
    const rows = await db.query(
      'SELECT * FROM workflows.learnings WHERE run_id = $1',
      [run_id]
    );

    assert(rows.length === 1, 'Learning record inserted');
    assert(rows[0].workflow_name === 'test-workflow', 'workflow_name matches');
    assert(rows[0].learning_type === 'model_behavior', 'learning_type matches');
    assert(rows[0].task_difficulty === 'moderate', 'task_difficulty matches');
    assert(rows[0].model_count === 3, 'model_count matches');
    assert(rows[0].polarization_index === 25, 'polarization_index matches');
    assert(rows[0].behavioral_agreement === 85, 'behavioral_agreement matches');

    // Clean up
    await db.run('DELETE FROM workflows.learnings WHERE run_id = $1', [run_id]);

  } catch (error) {
    assert(false, `Record learning failed: ${error.message}`);
    console.error(error.stack);
  }
}

async function testQueryLearnings() {
  console.log('\n=== Test 4: Query Learnings ===\n');

  try {
    const workflowsLearning = getWorkflowsLearning();
    const db = getDB();
    const run_id = `test_query_${Date.now()}_${randomBytes(4).toString('hex')}`;

    // Insert test data
    await workflowsLearning.recordLearning({
      run_id: run_id,
      workflow_name: 'test-query-workflow',
      learning_type: 'model_behavior',
      reaction_signals: { test: true },
      task_difficulty: 'hard',
      task_type: 'query-test',
      task_summary: 'Query test',
      quality_score: 0.9,
      outcome: OUTCOMES.SUCCESS,
      model_count: 5
    });

    // Query by task_difficulty
    const hardTasks = await workflowsLearning.queryLearnings({
      task_difficulty: 'hard',
      limit: 10
    });

    assert(hardTasks.length > 0, `Found ${hardTasks.length} hard tasks`);
    assert(hardTasks.some(t => t.run_id === run_id), 'Query includes inserted record');

    // Query by workflow_name
    const workflowTasks = await workflowsLearning.queryLearnings({
      workflow_name: 'test-query-workflow',
      limit: 10
    });

    assert(workflowTasks.length > 0, `Found ${workflowTasks.length} workflow tasks`);
    assert(workflowTasks[0].workflow_name === 'test-query-workflow', 'Workflow name filter works');

    // Clean up
    await db.run('DELETE FROM workflows.learnings WHERE run_id = $1', [run_id]);

  } catch (error) {
    assert(false, `Query learnings failed: ${error.message}`);
    console.error(error.stack);
  }
}

async function testWorkflowRun() {
  console.log('\n=== Test 5: Workflow Run Metadata ===\n');

  try {
    const workflowsLearning = getWorkflowsLearning();
    const db = getDB();
    const run_id = `test_run_metadata_${Date.now()}_${randomBytes(4).toString('hex')}`;

    // Record run start
    await workflowsLearning.recordRun({
      run_id: run_id,
      workflow_name: 'test-metadata-workflow',
      status: 'running',
      input_args: { test: 'input' }
    });

    // Verify running status
    let row = await db.get('SELECT * FROM workflows.runs WHERE run_id = $1', [run_id]);
    assert(row !== null, 'Run metadata inserted');
    assert(row.status === 'running', 'Status is running');

    // Update to completed
    await workflowsLearning.recordRun({
      run_id: run_id,
      workflow_name: 'test-metadata-workflow',
      status: 'completed',
      output_result: { test: 'output' },
      duration_ms: 2500
    });

    // Verify completed status
    row = await db.get('SELECT * FROM workflows.runs WHERE run_id = $1', [run_id]);
    assert(row.status === 'completed', 'Status updated to completed');
    assert(row.duration_ms === 2500, 'Duration recorded');
    assert(row.completed_at !== null, 'completed_at timestamp set');

    // Clean up
    await db.run('DELETE FROM workflows.runs WHERE run_id = $1', [run_id]);

  } catch (error) {
    assert(false, `Workflow run metadata failed: ${error.message}`);
    console.error(error.stack);
  }
}

async function testTraceability() {
  console.log('\n=== Test 6: Traceability (run_id FK) ===\n');

  try {
    const workflowsLearning = getWorkflowsLearning();
    const db = getDB();
    const run_id = `test_trace_${Date.now()}_${randomBytes(4).toString('hex')}`;

    // Record run metadata
    await workflowsLearning.recordRun({
      run_id: run_id,
      workflow_name: 'test-trace-workflow',
      status: 'running'
    });

    // Record multiple learnings for same run
    await workflowsLearning.recordLearning({
      run_id: run_id,
      workflow_name: 'test-trace-workflow',
      learning_type: 'model_behavior',
      task_type: 'trace-test-1',
      task_summary: 'First learning',
      outcome: OUTCOMES.SUCCESS
    });

    await workflowsLearning.recordLearning({
      run_id: run_id,
      workflow_name: 'test-trace-workflow',
      learning_type: 'model_behavior',
      task_type: 'trace-test-2',
      task_summary: 'Second learning',
      outcome: OUTCOMES.SUCCESS
    });

    // Get all learnings for run_id
    const learnings = await workflowsLearning.getLearningsByRunId(run_id);

    assert(learnings.length === 2, `Found ${learnings.length} learnings for run_id`);
    assert(learnings[0].run_id === run_id, 'First learning has correct run_id');
    assert(learnings[1].run_id === run_id, 'Second learning has correct run_id');

    // Clean up
    await db.run('DELETE FROM workflows.learnings WHERE run_id = $1', [run_id]);
    await db.run('DELETE FROM workflows.runs WHERE run_id = $1', [run_id]);

  } catch (error) {
    assert(false, `Traceability test failed: ${error.message}`);
    console.error(error.stack);
  }
}

async function testViews() {
  console.log('\n=== Test 7: Pre-built Views ===\n');

  try {
    const db = getDB();

    // Test recent_model_behaviors view
    const recentBehaviors = await db.query(
      'SELECT * FROM workflows.recent_model_behaviors LIMIT 5'
    );
    assert(true, `recent_model_behaviors view accessible (${recentBehaviors.length} rows)`);

    // Test task_difficulty_stats view
    const difficultyStats = await db.query(
      'SELECT * FROM workflows.task_difficulty_stats LIMIT 5'
    );
    assert(true, `task_difficulty_stats view accessible (${difficultyStats.length} rows)`);

    // Test performance_summary view
    const performanceSummary = await db.query(
      'SELECT * FROM workflows.performance_summary LIMIT 5'
    );
    assert(true, `performance_summary view accessible (${performanceSummary.length} rows)`);

  } catch (error) {
    assert(false, `Views test failed: ${error.message}`);
    console.error(error.stack);
  }
}

async function main() {
  console.log('\n=================================================================');
  console.log('Workflows Learning Integration - Test Suite');
  console.log('=================================================================');

  try {
    await testDatabaseConnection();
    await testSchemaExists();
    await testRecordLearning();
    await testQueryLearnings();
    await testWorkflowRun();
    await testTraceability();
    await testViews();

    console.log('\n=================================================================');
    console.log('Test Results');
    console.log('=================================================================');
    console.log(`\n  Passed: ${testsPassed}`);
    console.log(`  Failed: ${testsFailed}`);
    console.log(`  Total:  ${testsPassed + testsFailed}`);
    console.log('\n=================================================================\n');

    if (testsFailed > 0) {
      process.exit(1);
    } else {
      console.log('All tests passed! ✓\n');
      process.exit(0);
    }

  } catch (error) {
    console.error('\nFATAL ERROR:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

// Run tests
if (require.main === module) {
  main();
}

module.exports = {
  testDatabaseConnection,
  testSchemaExists,
  testRecordLearning,
  testQueryLearnings,
  testWorkflowRun,
  testTraceability,
  testViews
};
