export const meta = {
  name: 'fleet-integration-tests',
  description: 'Run all 19 integration tests across fleet workers',
  phases: [
    { title: 'Parallel Test Execution', detail: '3 test suites across 3 workers' },
    { title: 'Aggregate Results', detail: 'Collect and analyze all test results' }
  ]
}

// Phase 1: Parallel Test Execution
phase('Parallel Test Execution')

log('Running 19 integration tests across 3 fleet workers...')

const testSuites = await parallel([
  // Worker 1: ML Systems Tests (10 tests)
  () => agent(`Run ML systems integration tests on fleet.

Test Suite: test_ml_systems.py (10 tests)
Location: tests/integration/test_ml_systems.py

Instructions:
1. Run test suite:
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   python3 tests/integration/test_ml_systems.py

2. Capture output (all test results)

3. Parse results:
   - Extract passed/failed counts
   - Extract any error messages
   - Get execution time

Tests covered:
- Thompson Sampling load/predict (2)
- Auto-Profiler coverage/selection (2)
- Novelty Detector load/predict (2)
- Complexity Estimator load/predict (2)
- Prompt Optimizer exists (1)
- CPU Fine-Tuning scripts (1)

Return JSON with:
- suite_name: "test_ml_systems.py"
- total_tests: 10
- passed: (number)
- failed: (number)
- execution_time_seconds: (number)
- test_results: (array of {name, status, error})
- output: (string - last 50 lines)`, {
    label: 'ml-systems-tests',
    phase: 'Parallel Test Execution',
    schema: {
      type: 'object',
      properties: {
        suite_name: { type: 'string' },
        total_tests: { type: 'number' },
        passed: { type: 'number' },
        failed: { type: 'number' },
        execution_time_seconds: { type: 'number' },
        test_results: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              status: { type: 'string', enum: ['PASS', 'FAIL'] },
              error: { type: 'string' }
            }
          }
        },
        output: { type: 'string' }
      },
      required: ['suite_name', 'total_tests', 'passed', 'failed']
    }
  }),

  // Worker 2: Smart Orchestrator Tests (5 tests)
  () => agent(`Run smart orchestrator integration tests on fleet.

Test Suite: test_smart_orchestrator.py (5 tests)
Location: tests/integration/test_smart_orchestrator.py

Instructions:
1. Run test suite:
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   python3 tests/integration/test_smart_orchestrator.py

2. Capture output

3. Parse results:
   - Extract passed/failed counts
   - Extract error messages if any
   - Get execution time

Tests covered:
- Thompson Sampling model selection (1)
- Auto-Profiler exploration (1)
- Fleet parallel execution (1)
- Orchestrator status (1)
- Context extraction (1)

Return JSON with same schema as ml-systems tests.`, {
    label: 'orchestrator-tests',
    phase: 'Parallel Test Execution',
    schema: {
      type: 'object',
      properties: {
        suite_name: { type: 'string' },
        total_tests: { type: 'number' },
        passed: { type: 'number' },
        failed: { type: 'number' },
        execution_time_seconds: { type: 'number' },
        test_results: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              status: { type: 'string', enum: ['PASS', 'FAIL'] },
              error: { type: 'string' }
            }
          }
        },
        output: { type: 'string' }
      },
      required: ['suite_name', 'total_tests', 'passed', 'failed']
    }
  }),

  // Worker 3: Performance Persistence Tests (4 tests)
  () => agent(`Run performance persistence integration tests on fleet.

Test Suite: test_smart_consensus_persistence.mjs (4 tests)
Location: tests/test_smart_consensus_persistence.mjs

Instructions:
1. Run test suite:
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   node tests/test_smart_consensus_persistence.mjs

2. Capture output

3. Parse results:
   - Extract passed/failed counts
   - Extract error messages
   - Get execution time

Tests covered:
- Load performance data from PostgreSQL (1)
- Create tracker with test data (1)
- Save performance data to PostgreSQL (1)
- Reload to verify persistence (1)

Return JSON with same schema.`, {
    label: 'persistence-tests',
    phase: 'Parallel Test Execution',
    schema: {
      type: 'object',
      properties: {
        suite_name: { type: 'string' },
        total_tests: { type: 'number' },
        passed: { type: 'number' },
        failed: { type: 'number' },
        execution_time_seconds: { type: 'number' },
        test_results: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              status: { type: 'string', enum: ['PASS', 'FAIL'] },
              error: { type: 'string' }
            }
          }
        },
        output: { type: 'string' }
      },
      required: ['suite_name', 'total_tests', 'passed', 'failed']
    }
  })
])

const [mlTests, orchestratorTests, persistenceTests] = testSuites.filter(Boolean)

log(`✓ Test execution complete:`)
log(`  ML Systems: ${mlTests.passed}/${mlTests.total_tests} passed`)
log(`  Orchestrator: ${orchestratorTests.passed}/${orchestratorTests.total_tests} passed`)
log(`  Persistence: ${persistenceTests.passed}/${persistenceTests.total_tests} passed`)

// Phase 2: Aggregate Results
phase('Aggregate Results')

const totalTests = mlTests.total_tests + orchestratorTests.total_tests + persistenceTests.total_tests
const totalPassed = mlTests.passed + orchestratorTests.passed + persistenceTests.passed
const totalFailed = mlTests.failed + orchestratorTests.failed + persistenceTests.failed
const totalTime = mlTests.execution_time_seconds + orchestratorTests.execution_time_seconds + persistenceTests.execution_time_seconds

log(`Aggregating results from ${testSuites.length} test suites...`)

const aggregateReport = await agent(`Analyze fleet integration test results and provide summary.

Test Results:
1. ML Systems (10 tests): ${mlTests.passed}/${mlTests.total_tests} passed
2. Smart Orchestrator (5 tests): ${orchestratorTests.passed}/${orchestratorTests.total_tests} passed
3. Performance Persistence (4 tests): ${persistenceTests.passed}/${persistenceTests.total_tests} passed

Total: ${totalPassed}/${totalTests} passed, ${totalFailed} failed
Execution time: ${totalTime}s

Full Results:
${JSON.stringify({ mlTests, orchestratorTests, persistenceTests }, null, 2)}

Instructions:
1. Analyze all test results
2. Identify any failing tests
3. Determine if failures are:
   - Test environment issues (workers don't have dependencies)
   - Actual bugs (code problems)
   - Infrastructure issues (PostgreSQL, fleet connectivity)

4. Provide assessment:
   - Overall pass rate
   - Critical failures (if any)
   - Non-critical failures (environment/infrastructure)
   - Recommendation (production-ready or needs fixes)

Return JSON with:
- overall_status: "ALL_PASS" | "SOME_FAIL" | "CRITICAL_FAIL"
- pass_rate: (number - percentage)
- critical_failures: (array of test names)
- environment_failures: (array of test names)
- recommendation: "PRODUCTION_READY" | "FIX_CRITICAL" | "FIX_ENVIRONMENT"
- summary: (string)`, {
  label: 'aggregate-report',
  phase: 'Aggregate Results',
  schema: {
    type: 'object',
    properties: {
      overall_status: { type: 'string', enum: ['ALL_PASS', 'SOME_FAIL', 'CRITICAL_FAIL'] },
      pass_rate: { type: 'number' },
      critical_failures: { type: 'array', items: { type: 'string' } },
      environment_failures: { type: 'array', items: { type: 'string' } },
      recommendation: { type: 'string', enum: ['PRODUCTION_READY', 'FIX_CRITICAL', 'FIX_ENVIRONMENT'] },
      summary: { type: 'string' }
    },
    required: ['overall_status', 'pass_rate', 'recommendation', 'summary']
  }
})

log(`✓ Analysis complete: ${aggregateReport.overall_status}`)
log(`  Recommendation: ${aggregateReport.recommendation}`)

// Return summary
return {
  test_summary: {
    total_tests: totalTests,
    passed: totalPassed,
    failed: totalFailed,
    pass_rate: (totalPassed / totalTests * 100).toFixed(1) + '%',
    execution_time_seconds: totalTime
  },
  suites: {
    ml_systems: mlTests,
    orchestrator: orchestratorTests,
    persistence: persistenceTests
  },
  analysis: aggregateReport,
  verdict: aggregateReport.overall_status === 'ALL_PASS'
    ? '✅ ALL 19 TESTS PASSED - FLEET VALIDATED'
    : aggregateReport.recommendation === 'FIX_ENVIRONMENT'
    ? '⚠️ TESTS PASSED - ENVIRONMENT ISSUES ONLY'
    : '❌ CRITICAL FAILURES - NEEDS FIXES'
}
