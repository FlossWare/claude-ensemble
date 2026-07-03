export const meta = {
  name: 'test-ga-comprehensive',
  description: 'Comprehensive GA testing (5 tests including 300-iteration exploration)',
  phases: [
    { title: 'Run GA Tests', detail: 'All GA functionality with 300-iteration exploration' }
  ]
}

phase('Run GA Tests')

log('Running comprehensive GA integration tests (5 tests total)...')

const gaTests = await agent(`Run comprehensive GA integration tests on fleet.

Test Suite: test_ga_comprehensive.py (5 tests)
Location: tests/integration/test_ga_comprehensive.py

Tests:
1. Auto-Profiler Exploration - 300 iterations (verify 15% exploration rate)
2. GA Elitism - Issue #205 (verify elite models preserved)
3. GA Fitness Caching - Issue #206 (verify cached fitness)
4. Task-Specific Selection (verify different models for different tasks)
5. Coverage Evolution (verify model coverage growing)

Instructions:
1. Run test suite:
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   python3 tests/integration/test_ga_comprehensive.py

2. Capture full output

3. Parse results:
   - Extract pass/fail for each of 5 tests
   - Extract diversity rate from Test 1 (300 iterations)
   - Extract model coverage from Test 5
   - Get execution time

Expected behavior:
- Test 1: Diversity rate >= 5% (confirms exploration working)
- Test 2: Elitism enabled
- Test 3: Fitness cached
- Test 4: Multiple models selected for different tasks
- Test 5: Coverage >= 10 models

Return JSON with:
- total_tests: 5
- passed: (number)
- failed: (number)
- test_results: [
    {name, status: "PASS"|"FAIL", details}
  ]
- exploration_diversity_rate: (number from Test 1)
- model_coverage: (number from Test 5)
- execution_time_seconds: (number)
- summary: (string)`, {
  label: 'ga-comprehensive-tests',
  phase: 'Run GA Tests',
  schema: {
    type: 'object',
    properties: {
      total_tests: { type: 'number' },
      passed: { type: 'number' },
      failed: { type: 'number' },
      test_results: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            status: { type: 'string', enum: ['PASS', 'FAIL'] },
            details: { type: 'string' }
          }
        }
      },
      exploration_diversity_rate: { type: 'number' },
      model_coverage: { type: 'number' },
      execution_time_seconds: { type: 'number' },
      summary: { type: 'string' }
    },
    required: ['total_tests', 'passed', 'failed', 'test_results', 'summary']
  }
})

log(`✓ GA tests complete: ${gaTests.passed}/${gaTests.total_tests} passed`)

if (gaTests.exploration_diversity_rate) {
  log(`✓ Exploration diversity: ${gaTests.exploration_diversity_rate.toFixed(1)}%`)
}

if (gaTests.model_coverage) {
  log(`✓ Model coverage: ${gaTests.model_coverage} models`)
}

// Determine verdict
const allPassed = gaTests.passed === gaTests.total_tests
const explorationWorking = gaTests.exploration_diversity_rate >= 5.0

return {
  ga_test_results: gaTests,
  verdict: allPassed && explorationWorking
    ? '✅ ALL GA TESTS PASSED - EXPLORATION VERIFIED'
    : allPassed && !explorationWorking
    ? '⚠️ TESTS PASSED BUT LOW EXPLORATION'
    : `❌ ${gaTests.failed} TEST(S) FAILED`,
  recommendations: allPassed && explorationWorking
    ? 'GA system is production-ready. Issues #205 and #206 verified fixed.'
    : !explorationWorking
    ? 'Investigate exploration rate. May need epsilon adjustment.'
    : 'Fix failing tests before production deployment.'
}
