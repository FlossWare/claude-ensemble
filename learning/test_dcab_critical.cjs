const { Pool } = require('pg');

async function testPoolConnect() {
  const pool = new Pool({
    host: 'localhost',
    database: 'learning',
    user: process.env.USER,
    max: 10
  });

  const client = await pool.connect();
  console.log('Client type:', typeof client);
  console.log('Has query:', typeof client.query === 'function');
  console.log('Has release:', typeof client.release === 'function');
  
  // Test transaction
  await client.query('BEGIN');
  const result = await client.query('SELECT 1 as test');
  console.log('Query result type:', Array.isArray(result) ? 'Array' : typeof result);
  console.log('Has .rows:', result.rows !== undefined);
  console.log('Result structure:', JSON.stringify(result, null, 2));
  await client.query('ROLLBACK');
  
  client.release();
  await pool.end();
}

testPoolConnect().catch(console.error);
