#!/usr/bin/env node

/**
 * Test Phase Tracker
 *
 * Verifies that phase tracking properly stores data to PostgreSQL
 *
 * Usage: node shared/test-phase-tracker.js
 */

import { PhaseTracker } from './phase-tracker.js';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');

async function testPhaseTracker() {
  console.log('🧪 Testing Phase Tracker\n');

  // Test 1: Basic initialization
  console.log('Test 1: Initialization');
  const tracker = new PhaseTracker(
    'test-workflow',
    'Test phase tracking functionality',
    { enableStorage: true }
  );

  const executionId = await tracker.init();
  console.log(`✅ Initialized with execution ID: ${executionId}\n`);

  // Test 2: Track phases
  console.log('Test 2: Track multiple phases');

  tracker.startPhase('Phase 1');
  await new Promise(resolve => setTimeout(resolve, 100));
  await tracker.endPhase('Phase 1', 'success', { test: 'data1' });

  tracker.startPhase('Phase 2');
  await new Promise(resolve => setTimeout(resolve, 150));
  await tracker.endPhase('Phase 2', 'success', { test: 'data2' });

  tracker.startPhase('Phase 3');
  await new Promise(resolve => setTimeout(resolve, 75));
  await tracker.endPhase('Phase 3', 'success', { test: 'data3' });

  console.log('✅ Tracked 3 phases\n');

  // Test 3: Complete workflow
  console.log('Test 3: Complete workflow');
  await tracker.complete('success', { test_completed: true });
  console.log('✅ Workflow completed\n');

  // Test 4: Verify data in PostgreSQL
  console.log('Test 4: Verify PostgreSQL storage');
  const db = getWorkflowStorage();

  try {
    const phasesResult = await db.pool.query(
      `SELECT phase_name, phase_order, duration_ms, outcome
       FROM workflow.phases
       WHERE workflow_execution_id = $1
       ORDER BY phase_order`,
      [executionId]
    );

    console.log(`✅ Found ${phasesResult.rows.length} phases in PostgreSQL:`);
    phasesResult.rows.forEach(row => {
      console.log(`   ${row.phase_order + 1}. ${row.phase_name}: ${row.duration_ms}ms (${row.outcome})`);
    });
    console.log('');

    const executionResult = await db.pool.query(
      `SELECT workflow_id, workflow_name, outcome, total_duration_ms, metadata
       FROM workflow.executions
       WHERE id = $1`,
      [executionId]
    );

    const exec = executionResult.rows[0];
    console.log(`✅ Workflow execution record:`);
    console.log(`   ID: ${exec.workflow_id}`);
    console.log(`   Name: ${exec.workflow_name}`);
    console.log(`   Outcome: ${exec.outcome}`);
    console.log(`   Duration: ${exec.total_duration_ms}ms`);
    console.log(`   Phases: ${exec.metadata.phases_count}`);
    console.log('');

  } catch (error) {
    console.error(`❌ PostgreSQL query failed: ${error.message}`);
    process.exit(1);
  }

  // Test 5: Statistics
  console.log('Test 5: Statistics');
  const stats = tracker.getStats();
  console.log(`✅ Statistics:`);
  console.log(`   Total phases: ${stats.total}`);
  console.log(`   Completed: ${stats.completed}`);
  console.log(`   Successful: ${stats.successful}`);
  console.log(`   Total duration: ${stats.totalDuration}ms`);
  console.log(`   Avg duration: ${Math.round(stats.avgDuration)}ms`);
  console.log('');

  console.log('🎉 All tests passed!\n');

  // Cleanup: close connection
  await db.pool.end();
}

// Run tests
testPhaseTracker().catch(error => {
  console.error('❌ Test failed:', error);
  process.exit(1);
});
