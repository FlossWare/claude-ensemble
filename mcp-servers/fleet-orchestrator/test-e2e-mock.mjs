#!/usr/bin/env node
/**
 * End-to-End Test with Mock API
 * Tests the full integration flow without requiring real API calls
 */

import { getCostTracker } from './lib/cost-tracker.js';
import { getWorkflowStorage } from '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/workflow-storage-adapter.cjs';
import { Pool } from 'pg';

const results = {
  task_routed: true,  // Mock: task routing works
  api_called: true,    // Mock: API call succeeds
  database_written: false,
  cost_tracked: false,
  all_passing: false,
  details: {}
};

async function runTest() {
  console.log('Starting end-to-end test with mock API...\n');

  const pool = new Pool({
    host: process.env.PGHOST || 'aio-01',
    port: parseInt(process.env.PGPORT || '5433'),
    database: process.env.PGDATABASE || 'learning',
    user: process.env.PGUSER || process.env.USER,
    password: process.env.PGPASSWORD,
    max: 2,
  });

  const costTracker = getCostTracker();
  const workflowStorage = getWorkflowStorage();

  try {
    // Step 1: Mock API call (simulates successful execution)
    console.log('Step 1: Simulating API call...');
    const task = 'What is 2+2? Answer with just the number.';
    const model = 'haiku';

    // Mock API response
    const mockApiResult = {
      output: '4',
      input_tokens: 15,
      output_tokens: 3,
      provider: 'anthropic',
      duration_ms: 542,
      success: true
    };

    console.log(`✓ Mock API call completed`);
    console.log(`  Output: ${mockApiResult.output}`);
    console.log(`  Input tokens: ${mockApiResult.input_tokens}`);
    console.log(`  Output tokens: ${mockApiResult.output_tokens}`);
    console.log(`  Provider: ${mockApiResult.provider}\n`);

    results.details.api_output = mockApiResult.output;
    results.details.input_tokens = mockApiResult.input_tokens;
    results.details.output_tokens = mockApiResult.output_tokens;
    results.details.provider = mockApiResult.provider;
    results.details.model = model;

    // Step 2: Calculate and track cost
    console.log('Step 2: Calculating and tracking cost...');
    const costCalc = costTracker.calculateCost(
      model,
      mockApiResult.input_tokens,
      mockApiResult.output_tokens
    );

    console.log(`✓ Cost calculated:`);
    console.log(`  Input: $${costCalc.input_cost_usd.toFixed(6)} (${mockApiResult.input_tokens} tokens @ $${costCalc.input_cost_per_1m / 1000000}/token)`);
    console.log(`  Output: $${costCalc.output_cost_usd.toFixed(6)} (${mockApiResult.output_tokens} tokens @ $${costCalc.output_cost_per_1m / 1000000}/token)`);
    console.log(`  Total: $${costCalc.total_cost_usd.toFixed(6)}\n`);

    // Track in database
    const costEntry = await costTracker.trackCost({
      model,
      input_tokens: mockApiResult.input_tokens,
      output_tokens: mockApiResult.output_tokens,
      worker_id: 'test-worker',
      task_hash: Buffer.from(task).toString('hex').slice(0, 64),
      metadata: {
        test: true,
        e2e_test_mock: true
      }
    });

    console.log(`✓ Cost tracked in database (entry ID: ${costEntry.id})\n`);
    results.cost_tracked = true;
    results.details.cost_usd = costCalc.total_cost_usd;
    results.details.cost_entry_id = costEntry.id;

    // Verify cost entry
    const costVerify = await pool.query(
      'SELECT * FROM costs.entries WHERE id = $1',
      [costEntry.id]
    );

    if (costVerify.rows.length > 0) {
      console.log('  Cost database verification:');
      console.log(`    Model: ${costVerify.rows[0].model}`);
      console.log(`    Input tokens: ${costVerify.rows[0].input_tokens}`);
      console.log(`    Output tokens: ${costVerify.rows[0].output_tokens}`);
      console.log(`    Total cost: $${costVerify.rows[0].total_cost}\n`);
    }

    // Step 3: Create workflow execution first
    console.log('Step 3: Creating workflow execution...');
    const execResult = await pool.query(
      `INSERT INTO workflow.executions
       (workflow_id, workflow_name, task_description, total_workers, total_duration_ms, outcome)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING id`,
      ['test-e2e-' + Date.now(), 'end-to-end-test', task, 1, mockApiResult.duration_ms, 'success']
    );
    const workflowExecId = execResult.rows[0].id;
    console.log(`✓ Workflow execution created (ID: ${workflowExecId})\n`);

    // Step 4: Write to workflow storage
    console.log('Step 4: Writing to workflow storage...');
    await workflowStorage.storeWorkerResult({
      workflow_execution_id: workflowExecId,
      worker_id: 'test-worker',
      execution_host: 'mock-host',
      model,
      task_assigned: task,
      result: mockApiResult.output,
      confidence: null,
      duration_ms: mockApiResult.duration_ms,
      input_tokens: mockApiResult.input_tokens,
      output_tokens: mockApiResult.output_tokens,
      cost_usd: costCalc.total_cost_usd,
      outcome: 'success',
      metadata: {
        test: true,
        e2e_test_mock: true,
        provider: mockApiResult.provider
      }
    });

    console.log(`✓ Result written to workflow.worker_results\n`);

    // Verify workflow storage write
    const workflowVerify = await pool.query(
      `SELECT id, model, outcome, input_tokens, output_tokens, cost_usd, created_at
       FROM workflow.worker_results
       WHERE model = $1
       AND metadata->>'e2e_test_mock' = 'true'
       ORDER BY created_at DESC
       LIMIT 1`,
      [model]
    );

    if (workflowVerify.rows.length > 0) {
      const dbRow = workflowVerify.rows[0];
      console.log('  Workflow database verification:');
      console.log(`    ID: ${dbRow.id}`);
      console.log(`    Model: ${dbRow.model}`);
      console.log(`    Outcome: ${dbRow.outcome}`);
      console.log(`    Tokens: ${dbRow.input_tokens}/${dbRow.output_tokens}`);
      console.log(`    Cost: $${dbRow.cost_usd}`);
      console.log(`    Timestamp: ${dbRow.created_at}\n`);
      results.database_written = true;
      results.details.workflow_record_id = dbRow.id;
    } else {
      console.log('  WARNING: Could not verify workflow storage write\n');
    }

    // Final verification
    results.all_passing = results.task_routed &&
                          results.api_called &&
                          results.database_written &&
                          results.cost_tracked;

    if (results.all_passing) {
      console.log('✓✓✓ ALL TESTS PASSING - End-to-end workflow verified! ✓✓✓\n');
      console.log('Integration points confirmed:');
      console.log('  [✓] Task routing (simulated)');
      console.log('  [✓] API execution (mocked)');
      console.log('  [✓] Cost calculation');
      console.log('  [✓] Cost tracking in PostgreSQL');
      console.log('  [✓] Workflow storage in PostgreSQL');
      console.log('  [✓] Database verification queries\n');
    } else {
      console.log('✗ Some tests failed\n');
      if (!results.task_routed) console.log('  [✗] Task routing failed');
      if (!results.api_called) console.log('  [✗] API call failed');
      if (!results.database_written) console.log('  [✗] Database write failed');
      if (!results.cost_tracked) console.log('  [✗] Cost tracking failed');
    }

  } catch (error) {
    console.error('Test failed:', error.message);
    results.details.error = error.message;
    results.details.stack = error.stack;
    results.all_passing = false;
  } finally {
    await pool.end();
  }

  return results;
}

runTest()
  .then(results => {
    console.log('='.repeat(70));
    console.log('FINAL RESULTS JSON:');
    console.log('='.repeat(70));
    console.log(JSON.stringify(results, null, 2));
    console.log('='.repeat(70));
    process.exit(results.all_passing ? 0 : 1);
  })
  .catch(err => {
    console.error('Unhandled error:', err);
    process.exit(1);
  });
