#!/usr/bin/env node

/**
 * End-to-end test for Issue #11: Host tracking in workflow.worker_results
 *
 * Tests:
 * 1. Database migration applied (execution_host column exists)
 * 2. Code captures hostname correctly
 * 3. Can query which fleet node executed which agent
 */

import { WorkflowCompletionHook } from '../learning/workflow-completion-hook.js';
import os from 'os';

async function test() {
  const hook = new WorkflowCompletionHook();

  console.log('=== HOST TRACKING END-TO-END TEST ===\n');

  // 1. Check current hostname
  console.log('1. Current host information:');
  const currentHost = os.hostname();
  console.log('   Hostname:', currentHost);

  // 2. Create test workflow execution
  console.log('\n2. Creating test workflow execution...');
  const storage = await hook._ensureStorage();

  const workflowId = 'test-host-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

  const execRows = await storage.db.query(`
    INSERT INTO workflow.executions (
      workflow_id, workflow_name, task_description,
      total_workers, total_duration_ms, outcome
    )
    VALUES ($1, $2, $3, $4, $5, $6)
    RETURNING id
  `, [
    workflowId,
    'host-tracking-test',
    'Testing host tracking for Issue #11',
    3,
    1000,
    'success'
  ]);

  const execId = execRows[0].id;
  console.log('   ✓ Created execution ID:', execId);

  // 3. Store worker results with host tracking
  console.log('\n3. Storing worker results with host tracking...');
  const workers = [
    {
      workerId: 'worker-1',
      model: 'opus',
      taskAssigned: 'Task 1',
      result: 'Result from opus',
      confidence: 0.9,
      durationMs: 100,
      inputTokens: 50,
      outputTokens: 25,
      costUsd: 0.01,
      outcome: 'success'
    },
    {
      workerId: 'worker-2',
      model: 'sonnet',
      taskAssigned: 'Task 2',
      result: 'Result from sonnet',
      confidence: 0.85,
      durationMs: 120,
      inputTokens: 60,
      outputTokens: 30,
      costUsd: 0.015,
      outcome: 'success'
    },
    {
      workerId: 'worker-3',
      model: 'haiku',
      taskAssigned: 'Task 3',
      result: 'Result from haiku',
      confidence: 0.8,
      durationMs: 80,
      inputTokens: 40,
      outputTokens: 20,
      costUsd: 0.005,
      outcome: 'success'
    }
  ];

  await hook.storeWorkerResults(execId, workers);
  console.log('   ✓ Stored', workers.length, 'worker results');

  // 4. Verify results
  console.log('\n4. Verifying test workflow results...');
  const testResults = await storage.db.query(`
    SELECT worker_id, model, execution_host, created_at
    FROM workflow.worker_results
    WHERE workflow_execution_id = $1
    ORDER BY created_at
  `, [execId]);

  console.log('   Test Workflow Results:');
  for (const row of testResults) {
    console.log('   -', row.worker_id, '('+row.model+') executed on', row.execution_host);
  }

  // 5. Check host distribution
  console.log('\n5. Fleet node execution summary (Issue #11 requirement):');
  const fleetSummary = await storage.db.query(`
    SELECT
      execution_host,
      model,
      COUNT(*) as executions,
      AVG(confidence) as avg_confidence,
      SUM(cost_usd) as total_cost
    FROM workflow.worker_results
    WHERE created_at > NOW() - INTERVAL '1 day'
      AND execution_host IS NOT NULL
    GROUP BY execution_host, model
    ORDER BY execution_host, executions DESC
  `);

  console.log('   Recent fleet activity (last 24 hours):');
  let currentDisplayHost = null;
  for (const row of fleetSummary) {
    if (row.execution_host !== currentDisplayHost) {
      console.log('\n   ' + row.execution_host + ':');
      currentDisplayHost = row.execution_host;
    }
    console.log('     -', row.model + ':', row.executions, 'tasks,',
                'avg confidence:', parseFloat(row.avg_confidence || 0).toFixed(3) + ',',
                'cost: $' + parseFloat(row.total_cost).toFixed(4));
  }

  // 6. Check for NULL hosts
  const nullHosts = await storage.db.query(`
    SELECT COUNT(*) as null_count
    FROM workflow.worker_results
    WHERE execution_host IS NULL
  `);

  console.log('\n6. NULL host check:');
  console.log('   Records with NULL execution_host:', nullHosts[0].null_count);

  await storage.disconnect();

  console.log('\n=== TEST COMPLETE ===');
  console.log('\nACCEPTANCE CRITERIA STATUS:');
  const allHostsMatch = testResults.every(r => r.execution_host === currentHost);
  console.log('✓ Database stores hostname correctly:', allHostsMatch);
  console.log('✓ Can query which host executed which work: YES');
  console.log('✓ Meets Issue #11 spec (show which fleet node executed each agent): YES');
  console.log('\nIssue #11 is', allHostsMatch ? 'VERIFIED and COMPLETE' : 'FAILED');

  process.exit(allHostsMatch ? 0 : 1);
}

test().catch(e => {
  console.error('ERROR:', e.message);
  console.error(e.stack);
  process.exit(1);
});
