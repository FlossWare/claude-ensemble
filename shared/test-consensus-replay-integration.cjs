#!/usr/bin/env node
/**
 * Test Consensus Replay Integration
 *
 * Verifies that consensus-replay.cjs can be imported and used
 * in various integration scenarios.
 */

const { ConsensusReplay } = require('./consensus-replay.cjs');

async function testDirectImport() {
  console.log('\n=== Test 1: Direct Import ===');
  const replay = new ConsensusReplay();
  console.log('✓ ConsensusReplay class imported successfully');

  // Test database connection
  try {
    const result = await replay.pool.query('SELECT NOW()');
    console.log('✓ Database connection working');
  } catch (error) {
    console.log('✗ Database connection failed:', error.message);
  }

  await replay.close();
}

async function testListWorkflows() {
  console.log('\n=== Test 2: List Recent Workflows ===');
  const replay = new ConsensusReplay();

  try {
    const result = await replay.pool.query(`
      SELECT workflow_id, workflow_name, outcome, total_workers, created_at
      FROM workflow.executions
      ORDER BY created_at DESC
      LIMIT 5
    `);

    console.log(`Found ${result.rows.length} recent workflows:`);
    for (const row of result.rows) {
      console.log(`  - ${row.workflow_id} (${row.workflow_name}, ${row.outcome}, ${row.total_workers} workers)`);
    }
  } catch (error) {
    console.log('✗ Failed to list workflows:', error.message);
  }

  await replay.close();
}

async function testFetchHistorical() {
  console.log('\n=== Test 3: Fetch Historical Workflow ===');
  const replay = new ConsensusReplay();

  try {
    // Get first workflow ID
    const result = await replay.pool.query(`
      SELECT workflow_id
      FROM workflow.executions
      WHERE total_workers > 0
      ORDER BY created_at DESC
      LIMIT 1
    `);

    if (result.rows.length === 0) {
      console.log('✗ No workflows found to test with');
      await replay.close();
      return;
    }

    const workflowId = result.rows[0].workflow_id;
    console.log(`Testing with workflow: ${workflowId}`);

    const historical = await replay.fetchHistoricalWorkflow(workflowId);

    if (historical) {
      console.log('✓ Historical workflow fetched successfully');
      console.log(`  Workers: ${historical.workers.length}`);
      console.log(`  Arbiters: ${historical.arbiters.length}`);
      console.log(`  Phases: ${historical.phases.length}`);
    } else {
      console.log('✗ Failed to fetch historical workflow');
    }
  } catch (error) {
    console.log('✗ Error fetching historical workflow:', error.message);
  }

  await replay.close();
}

async function testReplayTableExists() {
  console.log('\n=== Test 4: Replay Table Schema ===');
  const replay = new ConsensusReplay();

  try {
    // Check if replays table exists
    const result = await replay.pool.query(`
      SELECT column_name, data_type
      FROM information_schema.columns
      WHERE table_schema = 'workflow' AND table_name = 'replays'
      ORDER BY ordinal_position
    `);

    if (result.rows.length > 0) {
      console.log('✓ workflow.replays table exists');
      console.log('  Columns:');
      for (const row of result.rows) {
        console.log(`    - ${row.column_name} (${row.data_type})`);
      }
    } else {
      console.log('✗ workflow.replays table does not exist (will be auto-created on first use)');
    }
  } catch (error) {
    console.log('✗ Error checking replay table:', error.message);
  }

  await replay.close();
}

async function testCLIWrapper() {
  console.log('\n=== Test 5: CLI Wrapper Exists ===');
  const fs = require('fs');
  const path = require('path');
  const cliPath = path.join(__dirname, '..', 'bin', 'replay-consensus');

  if (fs.existsSync(cliPath)) {
    const stats = fs.statSync(cliPath);
    const isExecutable = (stats.mode & 0o111) !== 0;
    console.log('✓ CLI wrapper exists:', cliPath);
    console.log(`  Executable: ${isExecutable ? 'Yes' : 'No'}`);
  } else {
    console.log('✗ CLI wrapper not found:', cliPath);
  }
}

async function main() {
  console.log('Consensus Replay Integration Tests');
  console.log('===================================');

  await testDirectImport();
  await testListWorkflows();
  await testFetchHistorical();
  await testReplayTableExists();
  testCLIWrapper();

  console.log('\n=== All Tests Complete ===\n');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
