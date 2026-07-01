#!/usr/bin/env node
/**
 * Full Integration Test for Explainability Reporter
 *
 * Tests:
 * 1. Direct API usage
 * 2. Wrapper API (weighted-voting-with-explain)
 * 3. Environment variable control
 * 4. Integration helper utilities
 * 5. CLI tool
 *
 * Run: node shared/test-explainability-full-integration.cjs
 *
 * Created: 2026-07-01
 * Issue: #266
 */

const fs = require('fs');
const { execSync } = require('child_process');

// ============================================================================
// MOCK DATA
// ============================================================================

function getMockVotingResult() {
  return {
    status: 'success',
    algorithm: 'weighted_voting',
    task_type: 'test',
    bft_enabled: false,
    winner: {
      answer: { result: 'test' },
      total_weight: 1.5,
      vote_count: 2,
      consensus_strength: 0.75,
      consensus_level: 'strong',
      votes: [
        {
          model: 'opus',
          weight: 1.0,
          confidence: 0.9,
          tier_weight: 1.0,
          capability_score: 0.9,
          normalized_confidence: 0.9,
          historical_accuracy: 0.8,
          calibration_penalty: 1.0,
        },
        {
          model: 'haiku',
          weight: 0.5,
          confidence: 0.7,
          tier_weight: 0.6,
          capability_score: 0.7,
          normalized_confidence: 0.7,
          historical_accuracy: 0.7,
          calibration_penalty: 1.0,
        },
      ],
    },
    all_groups: [
      {
        answer: { result: 'test' },
        total_weight: 1.5,
        vote_count: 2,
        percentage: 75.0,
      },
      {
        answer: { result: 'other' },
        total_weight: 0.5,
        vote_count: 1,
        percentage: 25.0,
      },
    ],
    metadata: {
      total_votes: 3,
      filtered_votes: 0,
      discarded_votes: 0,
    },
  };
}

// ============================================================================
// TEST SUITE
// ============================================================================

async function test1_DirectAPI() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 1: Direct API Usage');
  console.log('='.repeat(70));

  const { explain } = require('./explainability-reporter.cjs');
  const votingResult = getMockVotingResult();

  const result = await explain(votingResult, {
    format: 'both',
    outputPath: '/tmp/test-explainability-direct',
  });

  // Verify
  if (!result.report) throw new Error('No report generated');
  if (!result.json) throw new Error('No JSON output');
  if (!result.markdown) throw new Error('No Markdown output');
  if (!result.file_path) throw new Error('No file written');
  if (!fs.existsSync(result.file_path)) throw new Error('File not created');

  console.log('✓ Report generated');
  console.log('✓ JSON formatted (' + result.json.length + ' chars)');
  console.log('✓ Markdown formatted (' + result.markdown.length + ' chars)');
  console.log('✓ File written: ' + result.file_path);

  // Cleanup
  fs.unlinkSync(result.file_path);

  return { passed: true };
}

async function test2_WrapperAPI() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 2: Wrapper API (weighted-voting-with-explain)');
  console.log('='.repeat(70));

  const { runWeightedVotingWithExplain } = require('./weighted-voting-with-explain.cjs');

  // Mock votes
  const votes = [
    { model: 'opus', output: { answer: 'A' }, confidence: 0.9 },
    { model: 'haiku', output: { answer: 'A' }, confidence: 0.7 },
  ];

  const result = await runWeightedVotingWithExplain(votes, 'test', {
    explain: true,
    explainFormat: 'json',
  });

  // Verify
  if (!result.explainability) throw new Error('No explainability attached');
  if (!result.explainability.report) throw new Error('No report in explainability');
  if (!result.explainability.json) throw new Error('No JSON in explainability');

  console.log('✓ Wrapper executed successfully');
  console.log('✓ Explainability attached to result');
  console.log('✓ Report contains summary:', !!result.explainability.report.summary);

  return { passed: true };
}

async function test3_EnvironmentVariables() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 3: Environment Variable Control');
  console.log('='.repeat(70));

  const {
    isExplainabilityEnabled,
    getExplainFormat,
    getExplainOutputDir,
  } = require('./explainability-integration-helper.cjs');

  // Test 1: Default (disabled)
  delete process.env.CONSENSUS_EXPLAIN;
  if (isExplainabilityEnabled()) throw new Error('Should be disabled by default');
  console.log('✓ Disabled by default');

  // Test 2: Enable via env
  process.env.CONSENSUS_EXPLAIN = '1';
  if (!isExplainabilityEnabled()) throw new Error('Should be enabled via CONSENSUS_EXPLAIN=1');
  console.log('✓ Enabled via CONSENSUS_EXPLAIN=1');

  // Test 3: Format override
  process.env.CONSENSUS_EXPLAIN_FORMAT = 'markdown';
  if (getExplainFormat() !== 'markdown') throw new Error('Format override failed');
  console.log('✓ Format override works');

  // Test 4: Directory override
  process.env.CONSENSUS_EXPLAIN_DIR = '/custom/dir';
  if (getExplainOutputDir() !== '/custom/dir') throw new Error('Directory override failed');
  console.log('✓ Directory override works');

  // Cleanup
  delete process.env.CONSENSUS_EXPLAIN;
  delete process.env.CONSENSUS_EXPLAIN_FORMAT;
  delete process.env.CONSENSUS_EXPLAIN_DIR;

  return { passed: true };
}

async function test4_IntegrationHelpers() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 4: Integration Helper Utilities');
  console.log('='.repeat(70));

  const { withExplainability, addExplainOptions } = require('./explainability-integration-helper.cjs');
  const { runWeightedVoting } = require('./weighted-voting.cjs');

  // Mock voting function
  const votes = [
    { model: 'opus', output: { answer: 'A' }, confidence: 0.9 },
    { model: 'haiku', output: { answer: 'A' }, confidence: 0.7 },
  ];

  // Test withExplainability wrapper
  const result = await withExplainability(
    async () => await runWeightedVoting(votes, 'test', {}),
    { force: true, format: 'json' }
  );

  if (!result.explainability) throw new Error('withExplainability did not add explainability');
  console.log('✓ withExplainability() wrapper works');

  // Test addExplainOptions
  const options = addExplainOptions({ strategy: 'test' }, { explain: true, explainFormat: 'markdown' });
  if (!options.explain) throw new Error('addExplainOptions did not add explain flag');
  if (options.explainFormat !== 'markdown') throw new Error('addExplainOptions format mismatch');
  console.log('✓ addExplainOptions() utility works');

  return { passed: true };
}

async function test5_CLI() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 5: CLI Tool');
  console.log('='.repeat(70));

  try {
    // Test mock data (default format is markdown)
    const output = execSync(
      'node shared/explain-consensus-cli.cjs --mock --output /tmp/test-cli-report',
      { encoding: 'utf8', cwd: __dirname + '/..' }
    );

    if (!output.includes('SUMMARY STATISTICS')) throw new Error('CLI output missing summary');
    if (!fs.existsSync('/tmp/test-cli-report.md')) throw new Error('CLI did not write file');

    console.log('✓ CLI executed successfully');
    console.log('✓ Output contains summary statistics');
    console.log('✓ File written to /tmp/test-cli-report.md');

    // Cleanup
    fs.unlinkSync('/tmp/test-cli-report.md');

  } catch (err) {
    throw new Error('CLI test failed: ' + err.message);
  }

  return { passed: true };
}

// ============================================================================
// RUNNER
// ============================================================================

async function runAllTests() {
  const tests = [
    { name: 'Direct API', fn: test1_DirectAPI },
    { name: 'Wrapper API', fn: test2_WrapperAPI },
    { name: 'Environment Variables', fn: test3_EnvironmentVariables },
    { name: 'Integration Helpers', fn: test4_IntegrationHelpers },
    { name: 'CLI Tool', fn: test5_CLI },
  ];

  const results = [];

  console.log('\n' + '#'.repeat(70));
  console.log('# EXPLAINABILITY REPORTER - FULL INTEGRATION TEST');
  console.log('#'.repeat(70));

  for (const test of tests) {
    try {
      const result = await test.fn();
      results.push({ test: test.name, passed: result.passed, error: null });
    } catch (err) {
      results.push({ test: test.name, passed: false, error: err.message });
      console.error('\n✗ TEST FAILED:', test.name);
      console.error('  Error:', err.message);
    }
  }

  // Summary
  console.log('\n' + '='.repeat(70));
  console.log('TEST SUMMARY');
  console.log('='.repeat(70));

  const passed = results.filter(r => r.passed).length;
  const total = results.length;

  results.forEach(r => {
    const icon = r.passed ? '✓' : '✗';
    const status = r.passed ? 'PASS' : 'FAIL';
    console.log(`${icon} ${r.test}: ${status}`);
    if (r.error) {
      console.log(`  └─ ${r.error}`);
    }
  });

  console.log('='.repeat(70));
  console.log(`Results: ${passed}/${total} tests passed`);
  console.log('='.repeat(70));

  if (passed === total) {
    console.log('\n✅ ALL TESTS PASSED\n');
    process.exit(0);
  } else {
    console.log('\n❌ SOME TESTS FAILED\n');
    process.exit(1);
  }
}

if (require.main === module) {
  runAllTests();
}

module.exports = { runAllTests };
