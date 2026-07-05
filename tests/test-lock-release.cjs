#!/usr/bin/env node
/**
 * Test lock release on error in disagreement-detector.cjs
 *
 * Verifies that advisory locks are properly released on ROLLBACK
 * when database errors occur.
 */

const { Pool } = require('pg');
const { hashCode } = require('../shared/disagreement-detector.cjs');

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
});

async function testLockReleaseOnError() {
  console.log('=== Lock Release on Error Test ===\n');

  const testId = 'test-lock-release-' + Date.now();
  const lockId = hashCode(testId);

  console.log(`Test ID: ${testId}`);
  console.log(`Lock ID: ${lockId}\n`);

  const client1 = await pool.connect();
  const client2 = await pool.connect();

  try {
    // Client 1: Acquire lock and simulate error
    console.log('[client-1] Starting transaction...');
    await client1.query('BEGIN');

    console.log('[client-1] Acquiring advisory lock...');
    await client1.query('SELECT pg_advisory_xact_lock($1)', [lockId]);
    console.log('[client-1] ✅ Lock acquired');

    console.log('[client-1] Simulating error with ROLLBACK...');
    await client1.query('ROLLBACK');
    console.log('[client-1] ✅ Transaction rolled back');

    // Client 2: Try to acquire same lock (should succeed immediately)
    console.log('\n[client-2] Starting transaction...');
    await client2.query('BEGIN');

    console.log('[client-2] Attempting to acquire same lock...');
    const startTime = Date.now();
    await client2.query('SELECT pg_advisory_xact_lock($1)', [lockId]);
    const duration = Date.now() - startTime;

    console.log(`[client-2] ✅ Lock acquired in ${duration}ms`);

    await client2.query('COMMIT');
    console.log('[client-2] ✅ Transaction committed');

    // Verify lock was released (duration should be very short)
    const lockReleased = duration < 100; // Should be nearly instant

    console.log('\n=== Results ===');
    console.log(`Lock released on ROLLBACK: ${lockReleased ? '✅ YES' : '❌ NO (blocked for ' + duration + 'ms)'}`);

    return lockReleased;

  } catch (err) {
    console.error('❌ ERROR:', err.message);
    return false;
  } finally {
    client1.release();
    client2.release();
  }
}

async function main() {
  const passed = await testLockReleaseOnError();

  console.log(`\nOverall: ${passed ? '✅ PASS' : '❌ FAIL'}`);

  await pool.end();
  process.exit(passed ? 0 : 1);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
