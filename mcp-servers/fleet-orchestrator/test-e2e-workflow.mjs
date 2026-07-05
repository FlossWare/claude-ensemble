#!/usr/bin/env node
/**
 * End-to-End Workflow Test
 *
 * Traces complete path:
 * 1. Submit task via fleet-execute
 * 2. Task routes to worker
 * 3. Real API call executes
 * 4. Result written to database
 * 5. Metrics tracked
 * 6. Cost calculated
 */

import { fleetExecute } from './tools/fleet-execute.js';
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
  console.log('Starting end-to-end workflow test...\n');

  // Setup database connection to verify writes
  const pool = new Pool({
    host: process.env.PGHOST || 'aio-01',
    port: parseInt(process.env.PGPORT || '5433'),
    database: process.env.PGDATABASE || 'learning',
    user: process.env.PGUSER || process.env.USER,
    password: process.env.PGPASSWORD,
    max: 2,
  });

  try {
    // Step 1: Submit task via fleet-execute
    console.log('Step 1: Submitting task via fleet-execute...');
    const testTask = 'What is 2+2? Answer with just the number.';

    const startTime = Date.now();
    const result = await fleetExecute({
      task: testTask,
      model: 'haiku',  // Cheapest model for testing
      worker: 'auto',
      timeout_ms: 60000,
      track_execution: true,
      track_costs: true
    });
    const endTime = Date.now();

    console.log(`✓ Task submitted and completed in ${endTime - startTime}ms\n`);
    results.details.execution_time_ms = endTime - startTime;
    results.details.task = testTask;

    // Step 2: Verify task routing
    console.log('Step 2: Verifying task routing...');
    if (result.worker && result.model) {
      console.log(`✓ Task routed to worker: ${result.worker}, model: ${result.model}\n`);
      results.task_routed = true;
      results.details.worker = result.worker;
      results.details.model = result.model;
    } else {
      console.log('✗ Task routing failed\n');
      results.details.routing_error = 'Missing worker or model assignment';
    }

    // Step 3: Verify API call executed
    console.log('Step 3: Verifying API call execution...');
    if (result.output && result.output.length > 0) {
      console.log(`✓ API call executed successfully`);
      console.log(`  Output: ${result.output.slice(0, 100)}`);
      console.log(`  Input tokens: ${result.input_tokens}`);
      console.log(`  Output tokens: ${result.output_tokens}`);
      console.log(`  Duration: ${result.duration_ms}ms\n`);
      results.api_called = true;
      results.details.api_output = result.output.slice(0, 200);
      results.details.input_tokens = result.input_tokens;
      results.details.output_tokens = result.output_tokens;
    } else {
      console.log('✗ API call did not return output\n');
      results.details.api_error = 'No output received';
    }

    // Step 4: Verify database write (workflow storage)
    console.log('Step 4: Verifying database write...');
    if (result.database_integrated === true) {
      console.log(`✓ Result written to workflow.worker_results table\n`);

      // Query to verify the write
      const verifyQuery = await pool.query(
        `SELECT id, model, outcome, input_tokens, output_tokens, cost_usd, created_at
         FROM workflow.worker_results
         WHERE model = $1
         AND metadata->>'fleet_execute' = 'true'
         ORDER BY created_at DESC
         LIMIT 1`,
        [result.model]
      );

      if (verifyQuery.rows.length > 0) {
        const dbRow = verifyQuery.rows[0];
        console.log('  Database verification:');
        console.log(`    ID: ${dbRow.id}`);
        console.log(`    Model: ${dbRow.model}`);
        console.log(`    Outcome: ${dbRow.outcome}`);
        console.log(`    Tokens: ${dbRow.input_tokens}/${dbRow.output_tokens}`);
        console.log(`    Cost: $${dbRow.cost_usd}`);
        console.log(`    Timestamp: ${dbRow.created_at}\n`);
        results.database_written = true;
        results.details.db_record_id = dbRow.id;
      }
    } else {
      console.log('✗ Database write failed or was not attempted\n');
      results.details.db_error = 'database_integrated flag is false';
    }

    // Step 5: Verify cost tracking
    console.log('Step 5: Verifying cost tracking...');
    if (result.cost_tracked === true && result.cost_usd > 0) {
      console.log(`✓ Cost tracked: $${result.cost_usd.toFixed(6)}`);
      console.log(`  Input cost: $${result.input_cost_usd?.toFixed(6) || 'N/A'}`);
      console.log(`  Output cost: $${result.output_cost_usd?.toFixed(6) || 'N/A'}`);
      console.log(`  Provider: ${result.provider}\n`);
      results.cost_tracked = true;
      results.details.cost_usd = result.cost_usd;
      results.details.provider = result.provider;

      // Verify cost entry in database
      if (result.cost_entry_id) {
        const costQuery = await pool.query(
          `SELECT * FROM costs.entries WHERE id = $1`,
          [result.cost_entry_id]
        );

        if (costQuery.rows.length > 0) {
          console.log('  Cost database verification:');
          console.log(`    Entry ID: ${result.cost_entry_id}`);
          console.log(`    Stored cost: $${costQuery.rows[0].total_cost}\n`);
        }
      }
    } else {
      console.log('✗ Cost tracking failed\n');
      results.details.cost_error = 'cost_tracked flag is false or cost_usd is 0';
    }

    // Step 6: Overall verification
    console.log('Step 6: Overall verification...');
    results.all_passing = results.task_routed &&
                          results.api_called &&
                          results.database_written &&
                          results.cost_tracked;

    if (results.all_passing) {
      console.log('✓ ALL TESTS PASSING - End-to-end workflow verified!\n');
    } else {
      console.log('✗ Some tests failed - see details above\n');
    }

  } catch (error) {
    console.error('Test failed with error:', error.message);
    results.details.error = error.message;
    results.details.stack = error.stack;
  } finally {
    await pool.end();
  }

  return results;
}

// Execute test
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
