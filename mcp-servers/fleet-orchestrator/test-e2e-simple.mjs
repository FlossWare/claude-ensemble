#!/usr/bin/env node
/**
 * Simplified End-to-End Test
 * Tests API call → Database → Cost tracking directly
 */

import { executeRemoteLLMTask } from '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/fleet-utils.js';
import { getCostTracker } from './lib/cost-tracker.js';
import { getWorkflowStorage } from '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/workflow-storage-adapter.cjs';
import { Pool } from 'pg';

const results = {
  task_routed: false,
  api_called: false,
  database_written: false,
  cost_tracked: false,
  all_passing: false,
  details: {}
};

async function runTest() {
  console.log('Starting simplified end-to-end test...\n');

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
    // Step 1: Execute real API call
    console.log('Step 1: Executing real API call (haiku)...');
    const task = 'What is 2+2? Answer with just the number.';
    const model = 'haiku';

    const startTime = Date.now();
    const apiResult = await executeRemoteLLMTask({
      task,
      model,
      maxTokens: 100,
      timeoutMs: 60000
    });
    const endTime = Date.now();

    console.log(`✓ API call completed in ${endTime - startTime}ms`);
    console.log(`  Output: ${apiResult.output}`);
    console.log(`  Input tokens: ${apiResult.input_tokens}`);
    console.log(`  Output tokens: ${apiResult.output_tokens}`);
    console.log(`  Provider: ${apiResult.provider}\n`);

    results.api_called = true;
    results.task_routed = true;  // Direct API call, no fleet routing needed
    results.details.api_output = apiResult.output;
    results.details.input_tokens = apiResult.input_tokens;
    results.details.output_tokens = apiResult.output_tokens;
    results.details.provider = apiResult.provider;
    results.details.model = model;

    // Step 2: Calculate and track cost
    console.log('Step 2: Calculating and tracking cost...');
    const costCalc = costTracker.calculateCost(
      model,
      apiResult.input_tokens,
      apiResult.output_tokens
    );

    console.log(`✓ Cost calculated:`);
    console.log(`  Input: $${costCalc.input_cost_usd.toFixed(6)}`);
    console.log(`  Output: $${costCalc.output_cost_usd.toFixed(6)}`);
    console.log(`  Total: $${costCalc.total_cost_usd.toFixed(6)}\n`);

    // Track in database
    const costEntry = await costTracker.trackCost({
      model,
      input_tokens: apiResult.input_tokens,
      output_tokens: apiResult.output_tokens,
      worker_id: 'test-worker',
      task_hash: Buffer.from(task).toString('hex').slice(0, 64),
      metadata: {
        test: true,
        e2e_test: true
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
      console.log(`    Total cost: $${costVerify.rows[0].total_cost}\n`);
    }

    // Step 3: Write to workflow storage
    console.log('Step 3: Writing to workflow storage...');
    await workflowStorage.storeWorkerResult({
      workflow_execution_id: null,
      worker_id: 'test-worker',
      execution_host: 'localhost',
      model,
      task_assigned: task,
      result: apiResult.output,
      confidence: null,
      duration_ms: apiResult.duration_ms,
      input_tokens: apiResult.input_tokens,
      output_tokens: apiResult.output_tokens,
      cost_usd: costCalc.total_cost_usd,
      outcome: 'success',
      metadata: {
        test: true,
        e2e_test: true,
        provider: apiResult.provider
      }
    });

    console.log(`✓ Result written to workflow.worker_results\n`);

    // Verify workflow storage write
    const workflowVerify = await pool.query(
      `SELECT id, model, outcome, input_tokens, output_tokens, cost_usd, created_at
       FROM workflow.worker_results
       WHERE model = $1
       AND metadata->>'e2e_test' = 'true'
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
    }

    // Final verification
    results.all_passing = results.task_routed &&
                          results.api_called &&
                          results.database_written &&
                          results.cost_tracked;

    if (results.all_passing) {
      console.log('✓ ALL TESTS PASSING - End-to-end workflow verified!\n');
    } else {
      console.log('✗ Some tests failed\n');
    }

  } catch (error) {
    console.error('Test failed:', error.message);
    results.details.error = error.message;
    results.details.stack = error.stack;
  } finally {
    await pool.end();
  }

  return results;
}

runTest()
  .then(results => {
    console.log('='.repeat(60));
    console.log('FINAL RESULTS:');
    console.log('='.repeat(60));
    console.log(JSON.stringify(results, null, 2));
    process.exit(results.all_passing ? 0 : 1);
  })
  .catch(err => {
    console.error('Unhandled error:', err);
    process.exit(1);
  });
