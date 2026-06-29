#!/usr/bin/env node

/**
 * Test script for execution_host and execution_hosts migration
 * Verifies:
 * 1. Column exists in worker_results (execution_host)
 * 2. Column exists in executions (execution_hosts array)
 * 3. Adapter populates execution_host in storeWorkerResult()
 * 4. Adapter populates execution_hosts in storeExecution()
 */

const { getWorkflowStorage } = require('./shared/workflow-storage-adapter.cjs');
const os = require('os');

async function testExecutionHostMigration() {
  const db = getWorkflowStorage();
  const testHostname = os.hostname();

  try {
    console.log('Testing execution_host migration...\n');

    // 1. Verify columns exist
    console.log('1. Verifying schema columns exist...');
    const checkWorkerResult = await db.pool.query(
      `SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'workflow' AND table_name = 'worker_results'
        AND column_name = 'execution_host'
      ) as column_exists`
    );

    if (!checkWorkerResult.rows[0].column_exists) {
      throw new Error('❌ execution_host column does not exist in worker_results');
    }
    console.log('✅ execution_host column exists in worker_results');

    const checkExecutions = await db.pool.query(
      `SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'workflow' AND table_name = 'executions'
        AND column_name = 'execution_hosts'
      ) as column_exists`
    );

    if (!checkExecutions.rows[0].column_exists) {
      throw new Error('❌ execution_hosts column does not exist in executions');
    }
    console.log('✅ execution_hosts column exists in executions\n');

    // 2. Test storeExecution with execution_hosts
    console.log('2. Testing storeExecution() with execution_hosts...');
    const workflowId = 'test-' + Date.now();
    const execId = await db.storeExecution({
      workflow_id: workflowId,
      workflow_name: 'test-workflow',
      task_description: 'Test execution_hosts migration',
      total_workers: 2,
      total_duration_ms: 1000,
      outcome: 'success',
      execution_hosts: ['server-01', 'server-02']
    });

    console.log(`✅ Stored workflow execution: ID ${execId}`);

    // Verify the data was stored correctly
    const execResult = await db.pool.query(
      `SELECT execution_hosts FROM workflow.executions WHERE id = $1`,
      [execId]
    );

    const storedHosts = execResult.rows[0].execution_hosts;
    if (!Array.isArray(storedHosts) || storedHosts.length === 0) {
      throw new Error('❌ execution_hosts not stored correctly');
    }
    console.log(`✅ execution_hosts stored correctly: ${JSON.stringify(storedHosts)}\n`);

    // 3. Test storeWorkerResult with execution_host
    console.log('3. Testing storeWorkerResult() with execution_host...');
    const workerId = await db.storeWorkerResult({
      workflow_execution_id: execId,
      worker_id: 'worker-1',
      model: 'opus',
      task_assigned: 'Test task',
      result: 'Test result',
      confidence: 0.95,
      duration_ms: 500,
      input_tokens: 100,
      output_tokens: 50,
      cost_usd: 0.01,
      outcome: 'success',
      execution_host: testHostname
    });

    console.log(`✅ Stored worker result: ID ${workerId}`);

    // Verify the data was stored correctly
    const workerResult = await db.pool.query(
      `SELECT execution_host FROM workflow.worker_results WHERE id = $1`,
      [workerId]
    );

    const storedHost = workerResult.rows[0].execution_host;
    if (storedHost !== testHostname) {
      throw new Error(`❌ execution_host not stored correctly: got ${storedHost}, expected ${testHostname}`);
    }
    console.log(`✅ execution_host stored correctly: ${storedHost}\n`);

    // 4. Test default hostname assignment
    console.log('4. Testing default os.hostname() assignment...');
    const workerId2 = await db.storeWorkerResult({
      workflow_execution_id: execId,
      worker_id: 'worker-2',
      model: 'sonnet',
      task_assigned: 'Test task 2',
      result: 'Test result 2',
      confidence: 0.92,
      duration_ms: 400,
      input_tokens: 80,
      output_tokens: 40,
      cost_usd: 0.008,
      outcome: 'success'
      // No execution_host specified - should default to os.hostname()
    });

    const workerResult2 = await db.pool.query(
      `SELECT execution_host FROM workflow.worker_results WHERE id = $1`,
      [workerId2]
    );

    const defaultHost = workerResult2.rows[0].execution_host;
    if (defaultHost !== testHostname) {
      throw new Error(`❌ Default execution_host not set correctly: got ${defaultHost}, expected ${testHostname}`);
    }
    console.log(`✅ Default execution_host set correctly: ${defaultHost}\n`);

    // 5. Test querying by execution_host
    console.log('5. Testing query by execution_host...');
    const queryResult = await db.pool.query(
      `SELECT COUNT(*) as count FROM workflow.worker_results WHERE execution_host = $1`,
      [testHostname]
    );

    const count = parseInt(queryResult.rows[0].count);
    if (count === 0) {
      throw new Error('❌ No worker results found with expected execution_host');
    }
    console.log(`✅ Query by execution_host successful: found ${count} worker results\n`);

    // 6. Test querying by execution_hosts array
    console.log('6. Testing query by execution_hosts array...');
    const arrayQueryResult = await db.pool.query(
      `SELECT COUNT(*) as count FROM workflow.executions WHERE 'server-01' = ANY(execution_hosts)`,
      []
    );

    const arrayCount = parseInt(arrayQueryResult.rows[0].count);
    if (arrayCount === 0) {
      throw new Error('❌ No executions found with expected execution_hosts');
    }
    console.log(`✅ Query by execution_hosts array successful: found ${arrayCount} execution(s)\n`);

    console.log('✅ All tests passed!\n');
    console.log('Summary:');
    console.log(`  - Workflow execution ID: ${execId}`);
    console.log(`  - Worker result ID: ${workerId}`);
    console.log(`  - Execution hosts: ${JSON.stringify(storedHosts)}`);
    console.log(`  - Worker execution host: ${storedHost}`);

    return true;

  } catch (err) {
    console.error('\n❌ Test failed:', err.message);
    return false;
  } finally {
    await db.close();
  }
}

// Run tests
testExecutionHostMigration().then(success => {
  process.exit(success ? 0 : 1);
});
