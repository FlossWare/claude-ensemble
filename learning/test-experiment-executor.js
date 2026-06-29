#!/usr/bin/env node

/**
 * Test script for experiment-executor.js PostgreSQL integration
 * Validates:
 * 1. SQLite removed
 * 2. PostgreSQL integrated
 * 3. Table names fixed (experiments.registry, experiments.runs)
 * 4. Input validation for experiment.type and experiment.opportunity
 * 5. Error handling throws instead of silently failing
 */

const { ExperimentExecutor } = require('./experiment-executor.js');

async function runTests() {
  const results = {
    sqlite_removed: false,
    postgres_integrated: false,
    table_names_fixed: false,
    tests_passing: false,
    issues: []
  };

  try {
    // Test 1: Verify SQLite is removed
    const source = require('fs').readFileSync('./experiment-executor.js', 'utf8');
    if (!source.includes('sqlite3')) {
      console.log('✓ Test 1: SQLite removed');
      results.sqlite_removed = true;
    } else {
      console.log('✗ Test 1: FAILED - SQLite still present');
      results.issues.push('SQLite import still present in code');
    }

    // Test 2: Verify PostgreSQL is integrated
    if (source.includes('postgres-adapter')) {
      console.log('✓ Test 2: PostgreSQL adapter imported');
      results.postgres_integrated = true;
    } else {
      console.log('✗ Test 2: FAILED - PostgreSQL adapter not imported');
      results.issues.push('PostgreSQL adapter not imported');
    }

    // Test 3: Verify table names are fixed
    if (source.includes('experiments.runs') && source.includes('experiments.registry')) {
      console.log('✓ Test 3: Table names fixed (experiments.registry, experiments.runs)');
      results.table_names_fixed = true;
    } else {
      console.log('✗ Test 3: FAILED - Incorrect table names');
      results.issues.push('Still using execution_log instead of experiments.runs');
    }

    // Test 4: Verify input validation
    const executor = new ExperimentExecutor();
    await executor.init();

    try {
      // Test missing experiment.type
      await executor.recordExperimentOutcome('test-id', {
        // missing type
        opportunity: 'test'
      }, {}, 0);
      console.log('✗ Test 4a: FAILED - Missing validation for experiment.type');
      results.issues.push('Missing validation for experiment.type');
    } catch (err) {
      if (err.message.includes('experiment.type is required')) {
        console.log('✓ Test 4a: Input validation for experiment.type works');
      } else {
        console.log('✗ Test 4a: FAILED - Wrong error for missing experiment.type:', err.message);
        results.issues.push('Wrong error message for missing experiment.type');
      }
    }

    try {
      // Test missing experiment.opportunity
      await executor.recordExperimentOutcome('test-id', {
        type: 'test',
        // missing opportunity
      }, {}, 0);
      console.log('✗ Test 4b: FAILED - Missing validation for experiment.opportunity');
      results.issues.push('Missing validation for experiment.opportunity');
    } catch (err) {
      if (err.message.includes('experiment.opportunity is required')) {
        console.log('✓ Test 4b: Input validation for experiment.opportunity works');
      } else {
        console.log('✗ Test 4b: FAILED - Wrong error for missing experiment.opportunity:', err.message);
        results.issues.push('Wrong error message for missing experiment.opportunity');
      }
    }

    // Test 5: Verify error handling throws
    try {
      await executor.recordExperimentFailure('test-id', {
        // missing type
        opportunity: 'test'
      }, 'test error');
      console.log('✗ Test 5: FAILED - recordExperimentFailure should throw on missing type');
      results.issues.push('recordExperimentFailure does not validate experiment.type');
    } catch (err) {
      if (err.message.includes('experiment.type is required')) {
        console.log('✓ Test 5: Error handling throws correctly');
      } else {
        console.log('✗ Test 5: FAILED - Wrong error:', err.message);
        results.issues.push('recordExperimentFailure has wrong error handling');
      }
    }

    await executor.close();

    // Overall test status
    results.tests_passing = results.sqlite_removed &&
                            results.postgres_integrated &&
                            results.table_names_fixed &&
                            results.issues.length === 0;

    console.log('\n' + '='.repeat(60));
    console.log('TEST RESULTS:');
    console.log('='.repeat(60));
    console.log('SQLite removed:', results.sqlite_removed ? '✓' : '✗');
    console.log('PostgreSQL integrated:', results.postgres_integrated ? '✓' : '✗');
    console.log('Table names fixed:', results.table_names_fixed ? '✓' : '✗');
    console.log('Tests passing:', results.tests_passing ? '✓' : '✗');
    if (results.issues.length > 0) {
      console.log('\nIssues:');
      results.issues.forEach(issue => console.log('  -', issue));
    }
    console.log('='.repeat(60));

    console.log('\nJSON Output:');
    console.log(JSON.stringify(results, null, 2));

    process.exit(results.tests_passing ? 0 : 1);

  } catch (error) {
    console.error('Test suite failed:', error.message);
    results.issues.push(`Test suite error: ${error.message}`);
    console.log(JSON.stringify(results, null, 2));
    process.exit(1);
  }
}

runTests().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
