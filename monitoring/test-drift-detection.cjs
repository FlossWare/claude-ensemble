#!/usr/bin/env node
/**
 * Test script for drift detection fixes
 *
 * Tests:
 * 1. Schema uses quality metrics (avg_quality, stddev_quality)
 * 2. Alert deduplication (same drift doesn't create duplicate alerts)
 * 3. Minimum sample size is 20
 *
 * Usage:
 *   node monitoring/test-drift-detection.cjs
 */

const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
});

async function testSchemaColumns() {
  console.log('\n=== Test 1: Schema uses quality metrics ===');

  const client = await pool.connect();
  try {
    // Check materialized view columns
    const result = await client.query(`
      SELECT column_name
      FROM information_schema.columns
      WHERE table_schema = 'monitoring'
        AND table_name = 'model_drift'
        AND column_name IN ('avg_quality', 'stddev_quality', 'avg_confidence', 'stddev_confidence')
      ORDER BY column_name
    `);

    const columns = result.rows.map(r => r.column_name);
    console.log('Found columns:', columns);

    if (columns.includes('avg_quality') && columns.includes('stddev_quality')) {
      console.log('✅ PASS: Using quality metrics (avg_quality, stddev_quality)');
      return true;
    } else if (columns.includes('avg_confidence') && columns.includes('stddev_confidence')) {
      console.log('⚠️  FAIL: Still using old confidence columns (need to run migrate-model-drift-view.sql)');
      return false;
    } else {
      console.log('❌ FAIL: Unknown column state:', columns);
      return false;
    }
  } finally {
    client.release();
  }
}

async function testDeduplication() {
  console.log('\n=== Test 2: Alert deduplication ===');

  const client = await pool.connect();
  try {
    // Check for deduplication columns
    const colResult = await client.query(`
      SELECT column_name
      FROM information_schema.columns
      WHERE table_schema = 'monitoring'
        AND table_name = 'drift_alerts'
        AND column_name IN ('times_alerted', 'last_alerted')
      ORDER BY column_name
    `);

    const columns = colResult.rows.map(r => r.column_name);
    console.log('Deduplication columns:', columns);

    if (!columns.includes('times_alerted') || !columns.includes('last_alerted')) {
      console.log('⚠️  FAIL: Missing deduplication columns (need to run migrate-drift-alerts.sql)');
      return false;
    }

    // Check for unique index
    const idxResult = await client.query(`
      SELECT indexname
      FROM pg_indexes
      WHERE schemaname = 'monitoring'
        AND tablename = 'drift_alerts'
        AND indexname = 'idx_drift_alerts_unique_daily'
    `);

    if (idxResult.rows.length > 0) {
      console.log('✅ PASS: Deduplication columns and index exist');
      return true;
    } else {
      console.log('⚠️  FAIL: Missing unique daily index (need to run migrate-drift-alerts.sql)');
      return false;
    }
  } finally {
    client.release();
  }
}

async function testMinSamples() {
  console.log('\n=== Test 3: Minimum sample size ===');

  const client = await pool.connect();
  try {
    // Check function source for default min_samples value
    const result = await client.query(`
      SELECT prosrc
      FROM pg_proc p
      JOIN pg_namespace n ON p.pronamespace = n.oid
      WHERE n.nspname = 'monitoring'
        AND p.proname = 'detect_model_drift'
    `);

    if (result.rows.length === 0) {
      console.log('❌ FAIL: detect_model_drift function not found');
      return false;
    }

    const source = result.rows[0].prosrc;

    // Check if default is 20 (not 5)
    if (source.includes('min_samples INTEGER DEFAULT 20')) {
      console.log('✅ PASS: Minimum samples raised to 20');
      return true;
    } else if (source.includes('min_samples INTEGER DEFAULT 5')) {
      console.log('⚠️  FAIL: Still using old minimum of 5 (need to redeploy schema-drift-detection.sql)');
      return false;
    } else {
      console.log('⚠️  WARNING: Could not determine min_samples default');
      console.log('Function signature:', source.substring(0, 200));
      return false;
    }
  } finally {
    client.release();
  }
}

async function testDriftDetectorConfig() {
  console.log('\n=== Test 4: drift-detector.cjs configuration ===');

  const fs = require('fs');
  const path = require('path');

  const driftDetectorPath = path.join(__dirname, 'drift-detector.cjs');
  const content = fs.readFileSync(driftDetectorPath, 'utf-8');

  // Check for minSamples = 20
  if (content.includes('minSamples = 20')) {
    console.log('✅ PASS: drift-detector.cjs uses minSamples = 20');
    return true;
  } else if (content.includes('minSamples = 5')) {
    console.log('❌ FAIL: drift-detector.cjs still uses minSamples = 5');
    return false;
  } else {
    console.log('⚠️  WARNING: Could not determine minSamples in drift-detector.cjs');
    return false;
  }
}

async function runAllTests() {
  console.log('Testing drift detection fixes...');
  console.log('===============================================');

  const results = {
    schemaColumns: await testSchemaColumns(),
    deduplication: await testDeduplication(),
    minSamples: await testMinSamples(),
    driftDetectorConfig: await testDriftDetectorConfig(),
  };

  console.log('\n===============================================');
  console.log('Test Summary:');
  console.log('===============================================');
  console.log(`Schema columns (quality):  ${results.schemaColumns ? '✅ PASS' : '⚠️  FAIL'}`);
  console.log(`Alert deduplication:       ${results.deduplication ? '✅ PASS' : '⚠️  FAIL'}`);
  console.log(`Min samples (SQL):         ${results.minSamples ? '✅ PASS' : '⚠️  FAIL'}`);
  console.log(`Min samples (JS):          ${results.driftDetectorConfig ? '✅ PASS' : '⚠️  FAIL'}`);

  const allPassed = Object.values(results).every(r => r);

  if (allPassed) {
    console.log('\n✅ All tests passed!');
  } else {
    console.log('\n⚠️  Some tests failed. Migration steps needed:');
    if (!results.deduplication) {
      console.log('   1. Run: psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/migrate-drift-alerts.sql');
    }
    if (!results.schemaColumns) {
      console.log('   2. Run: psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/migrate-model-drift-view.sql');
    }
    if (!results.minSamples) {
      console.log('   3. Run: psql -h aio-01 -p 5433 -U postgres -d learning -f monitoring/schema-drift-detection.sql');
    }
  }

  await pool.end();
  process.exit(allPassed ? 0 : 1);
}

runAllTests().catch(err => {
  console.error('Test error:', err);
  process.exit(1);
});
