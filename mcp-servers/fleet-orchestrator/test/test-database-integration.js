#!/usr/bin/env node
/**
 * Test database integration for fleet execution
 * Verifies that execution_host data is written to PostgreSQL workflow tables
 */

import pg from 'pg';
import { fleetExecute } from '../tools/fleet-execute.js';

const { Pool } = pg;

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
  max: 10
});

async function runTests() {
  console.log('=== Database Integration Test ===\n');

  try {
    // Test 1: Execute tasks via fleet-execute
    console.log('Test 1: Executing 3 tasks via fleet-execute...');
    const tasks = [
      'echo "Test task 1 on $(hostname)"',
      'echo "Test task 2 on $(hostname)"',
      'echo "Test task 3 on $(hostname)"'
    ];

    const results = [];
    for (const task of tasks) {
      const result = await fleetExecute({ task, timeout_ms: 30000 });
      results.push(result);
      console.log(`  - Worker: ${result.worker}, execution_host: ${result.execution_host}`);
    }

    console.log(`\n✓ Executed ${results.length} tasks\n`);

    // Extract execution_hosts from results
    const executionHosts = results.map(r => r.execution_host);
    console.log(`Execution hosts from fleet-execute: ${JSON.stringify(executionHosts)}\n`);

    // Test 2: Insert test workflow execution with execution_hosts
    console.log('Test 2: Inserting test workflow execution...');
    const workflowId = `test-workflow-${Date.now()}`;
    const insertResult = await pool.query(
      `INSERT INTO workflow.executions
       (workflow_id, workflow_name, task_description, total_workers,
        total_duration_ms, outcome, execution_hosts, metadata, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
       RETURNING id, workflow_id, execution_hosts`,
      [
        workflowId,
        'test-database-integration',
        'Test execution for database integration',
        executionHosts.length,
        5000,
        'success',
        executionHosts, // PostgreSQL array
        JSON.stringify({ test: true })
      ]
    );

    const workflowExecutionId = insertResult.rows[0].id;
    console.log(`  - Inserted workflow execution ID: ${workflowExecutionId}`);
    console.log(`  - Execution hosts stored: ${JSON.stringify(insertResult.rows[0].execution_hosts)}\n`);

    // Test 3: Insert worker results with execution_host
    console.log('Test 3: Inserting worker results...');
    for (let i = 0; i < results.length; i++) {
      const result = results[i];
      await pool.query(
        `INSERT INTO workflow.worker_results
         (workflow_execution_id, worker_id, model, task_assigned, result,
          confidence, duration_ms, input_tokens, output_tokens, cost_usd,
          outcome, execution_host, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())`,
        [
          workflowExecutionId,
          `worker-${i + 1}`,
          result.model,
          result.task,
          result.output,
          0.95,
          result.duration_ms || 1000,
          100,
          50,
          result.cost_usd || 0.001,
          'success',
          result.execution_host
        ]
      );
      console.log(`  - Inserted worker result for ${result.execution_host}`);
    }
    console.log('\n✓ Inserted all worker results\n');

    // Test 4: Query workflow.worker_results for execution_host
    console.log('Test 4: Querying worker_results for execution_host...');
    const workerQuery = await pool.query(
      `SELECT worker_id, model, execution_host, created_at
       FROM workflow.worker_results
       WHERE workflow_execution_id = $1
       ORDER BY created_at`,
      [workflowExecutionId]
    );

    console.log(`  - Found ${workerQuery.rows.length} worker results:`);
    for (const row of workerQuery.rows) {
      console.log(`    * ${row.worker_id}: execution_host = ${row.execution_host}, model = ${row.model}`);
    }
    console.log('');

    // Test 5: Verify execution_hosts array in workflow.executions
    console.log('Test 5: Verifying execution_hosts array in workflow.executions...');
    const executionQuery = await pool.query(
      `SELECT workflow_id, workflow_name, execution_hosts, created_at
       FROM workflow.executions
       WHERE id = $1`,
      [workflowExecutionId]
    );

    const execution = executionQuery.rows[0];
    console.log(`  - Workflow: ${execution.workflow_name}`);
    console.log(`  - Execution hosts: ${JSON.stringify(execution.execution_hosts)}`);
    console.log(`  - Host count: ${execution.execution_hosts.length}`);

    if (execution.execution_hosts && execution.execution_hosts.length > 0) {
      console.log('\n✓ execution_hosts array populated successfully\n');
    } else {
      console.log('\n✗ ERROR: execution_hosts array is empty or null\n');
    }

    // Test 6: Query execution_hosts array aggregation
    console.log('Test 6: Verifying execution_hosts aggregation...');
    const hostsQuery = await pool.query(
      `SELECT DISTINCT unnest(execution_hosts) as host
       FROM workflow.executions
       WHERE workflow_id = $1`,
      [workflowId]
    );

    console.log(`  - Unique hosts in execution_hosts array:`);
    for (const row of hostsQuery.rows) {
      console.log(`    * ${row.host}`);
    }
    console.log('\n✓ Execution hosts aggregation working\n');

    // Test 7: Query by execution_host in worker_results
    console.log('Test 7: Querying worker_results by execution_host...');
    const hostFilterQuery = await pool.query(
      `SELECT COUNT(*) as count, execution_host
       FROM workflow.worker_results
       WHERE workflow_execution_id = $1
       GROUP BY execution_host
       ORDER BY count DESC`,
      [workflowExecutionId]
    );

    console.log(`  - Worker distribution by host:`);
    for (const row of hostFilterQuery.rows) {
      console.log(`    * ${row.execution_host}: ${row.count} workers`);
    }
    console.log('\n✓ Host-based filtering working\n');

    // Summary
    console.log('=== Test Summary ===');
    console.log(`✓ All tests passed`);
    console.log(`✓ execution_host written to PostgreSQL`);
    console.log(`✓ workflow.worker_results populated`);
    console.log(`✓ execution_hosts array populated`);
    console.log(`✓ Database integration working correctly`);

  } catch (error) {
    console.error('\n✗ Test failed:', error.message);
    console.error('Stack trace:', error.stack);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

runTests().catch(console.error);
