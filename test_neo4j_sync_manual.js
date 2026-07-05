const { syncWorkflowToNeo4j } = require('./shared/neo4j-realtime-sync.js');

async function test() {
  const { Pool } = require('pg');
  const pool = new Pool({
    host: 'aio-01',
    port: 5433,
    database: 'learning',
    user: 'claude'
  });

  const result = await pool.query('SELECT id, workflow_name FROM workflow.executions ORDER BY created_at DESC LIMIT 1');
  const execution = result.rows[0];

  console.log(`\n=== Testing Neo4j Sync ===`);
  console.log(`Workflow ID: ${execution.id}`);
  console.log(`Workflow Name: ${execution.workflow_name}`);
  console.log();

  const success = await syncWorkflowToNeo4j(execution.id);

  console.log();
  console.log(success ? '✅ Sync successful!' : '❌ Sync failed');

  await pool.end();
  process.exit(success ? 0 : 1);
}

test().catch(err => {
  console.error('Test failed:', err.message);
  process.exit(1);
});
