/**
 * Consensus Replay Tests
 *
 * Test scenarios:
 * 1. Fetch historical workflow (success + not found)
 * 2. Re-run with same models
 * 3. Re-run with override models
 * 4. Compare results (improvement, degradation, neutral)
 * 5. Store replay results
 * 6. Generate HTML report
 *
 * Created: 2026-06-28
 */

const { ConsensusReplay } = require('./consensus-replay.cjs');
const { Pool } = require('pg');
const fs = require('fs');
const path = require('path');

// Test database connection
const pool = new Pool({
  host: process.env.PGHOST || 'aio-01',
  port: parseInt(process.env.PGPORT || '5433'),
  database: process.env.PGDATABASE || 'learning',
  user: process.env.PGUSER || process.env.USER,
  password: process.env.PGPASSWORD,
});

/**
 * Test 1: Fetch Historical Workflow
 */
async function testFetchHistoricalWorkflow() {
  console.log('\n=== Test 1: Fetch Historical Workflow ===');
  const replay = new ConsensusReplay();

  try {
    // Get a real workflow ID from database
    const client = await pool.connect();
    const result = await client.query(
      `SELECT workflow_id FROM workflow.executions ORDER BY created_at DESC LIMIT 1`
    );
    client.release();

    if (result.rows.length === 0) {
      console.log('❌ No workflows in database, skipping test');
      return;
    }

    const workflowId = result.rows[0].workflow_id;
    console.log(`Testing with workflow: ${workflowId}`);

    const historical = await replay.fetchHistoricalWorkflow(workflowId);

    if (!historical) {
      console.log('❌ Failed to fetch historical workflow');
      return;
    }

    console.log('✅ Fetched historical workflow:');
    console.log(`   - Task: ${historical.execution.task_description.substring(0, 80)}...`);
    console.log(`   - Workers: ${historical.workers.length}`);
    console.log(`   - Arbiters: ${historical.arbiters.length}`);
    console.log(`   - Phases: ${historical.phases.length}`);

    // Test not found case
    const notFound = await replay.fetchHistoricalWorkflow('wf-nonexistent');
    if (notFound === null) {
      console.log('✅ Correctly returned null for non-existent workflow');
    } else {
      console.log('❌ Should return null for non-existent workflow');
    }

  } catch (error) {
    console.log('❌ Test failed:', error.message);
  }
}

/**
 * Test 2: Compare Results (Mock Data)
 */
async function testCompareResults() {
  console.log('\n=== Test 2: Compare Results ===');
  const replay = new ConsensusReplay();

  // Mock historical data
  const historical = {
    execution: {
      workflow_id: 'wf-test-123',
      task_description: 'Test task for replay',
      created_at: '2026-06-01T10:00:00Z'
    },
    workers: [
      { model: 'opus', confidence: 0.75, duration_ms: 5000, cost_usd: 0.05 },
      { model: 'sonnet', confidence: 0.80, duration_ms: 3000, cost_usd: 0.03 },
      { model: 'haiku', confidence: 0.70, duration_ms: 2000, cost_usd: 0.01 }
    ],
    arbiters: [
      { confidence: 0.82, duration_ms: 4000 }
    ],
    phases: []
  };

  // Mock new run data (improvement scenario)
  const newRunImproved = {
    workers: [
      { model: 'opus', confidence: 0.85, duration_ms: 4500, cost_usd: 0.04, created_at: new Date().toISOString() },
      { model: 'sonnet', confidence: 0.88, duration_ms: 2800, cost_usd: 0.03, created_at: new Date().toISOString() },
      { model: 'haiku', confidence: 0.78, duration_ms: 1800, cost_usd: 0.01, created_at: new Date().toISOString() }
    ],
    arbiter: {
      confidence: 0.90,
      duration_ms: 3500,
      created_at: new Date().toISOString()
    },
    metadata: {
      replayed_at: new Date().toISOString(),
      original_workflow_id: 'wf-test-123',
      models_used: ['opus', 'sonnet', 'haiku']
    }
  };

  const comparisonImproved = replay.compareResults(historical, newRunImproved);

  console.log('Test: Improvement Scenario');
  console.log(`   Verdict: ${comparisonImproved.summary.verdict}`);
  console.log(`   Avg Confidence Delta: ${comparisonImproved.summary.avg_confidence_delta}`);
  console.log(`   Arbiter Confidence Delta: ${comparisonImproved.summary.arbiter_confidence_delta}`);

  if (comparisonImproved.summary.verdict.includes('IMPROVEMENT')) {
    console.log('✅ Correctly detected improvement');
  } else {
    console.log('❌ Failed to detect improvement');
  }

  // Mock new run data (degradation scenario)
  const newRunDegraded = {
    workers: [
      { model: 'opus', confidence: 0.65, duration_ms: 6000, cost_usd: 0.06, created_at: new Date().toISOString() },
      { model: 'sonnet', confidence: 0.68, duration_ms: 4000, cost_usd: 0.04, created_at: new Date().toISOString() },
      { model: 'haiku', confidence: 0.60, duration_ms: 3000, cost_usd: 0.02, created_at: new Date().toISOString() }
    ],
    arbiter: {
      confidence: 0.70,
      duration_ms: 5000,
      created_at: new Date().toISOString()
    },
    metadata: {
      replayed_at: new Date().toISOString(),
      original_workflow_id: 'wf-test-123',
      models_used: ['opus', 'sonnet', 'haiku']
    }
  };

  const comparisonDegraded = replay.compareResults(historical, newRunDegraded);

  console.log('\nTest: Degradation Scenario');
  console.log(`   Verdict: ${comparisonDegraded.summary.verdict}`);
  console.log(`   Avg Confidence Delta: ${comparisonDegraded.summary.avg_confidence_delta}`);
  console.log(`   Arbiter Confidence Delta: ${comparisonDegraded.summary.arbiter_confidence_delta}`);

  if (comparisonDegraded.summary.verdict === 'DEGRADATION') {
    console.log('✅ Correctly detected degradation');
  } else {
    console.log('❌ Failed to detect degradation');
  }
}

/**
 * Test 3: Store Replay Results
 */
async function testStoreReplayResults() {
  console.log('\n=== Test 3: Store Replay Results ===');
  const replay = new ConsensusReplay();

  const mockComparison = {
    summary: {
      workflow_id: 'wf-test-store-' + Date.now(),
      task: 'Test storage task',
      replayed_at: new Date().toISOString(),
      original_created_at: new Date().toISOString(),
      avg_confidence_delta: '0.050',
      arbiter_confidence_delta: '0.080',
      total_cost_delta: '-0.0100',
      verdict: 'MODERATE_IMPROVEMENT'
    },
    workers: [],
    arbiter: {},
    details: {}
  };

  try {
    const replayId = await replay.storeReplayResults(mockComparison);
    console.log(`✅ Stored replay results with ID: ${replayId}`);

    // Verify storage
    const client = await pool.connect();
    const result = await client.query(
      `SELECT * FROM workflow.replays WHERE id = $1`,
      [replayId]
    );
    client.release();

    if (result.rows.length === 1) {
      console.log('✅ Successfully retrieved stored replay');
      console.log(`   Verdict: ${result.rows[0].verdict}`);
      console.log(`   Avg Confidence Delta: ${result.rows[0].avg_confidence_delta}`);
    } else {
      console.log('❌ Failed to retrieve stored replay');
    }

  } catch (error) {
    console.log('❌ Store test failed:', error.message);
  }
}

/**
 * Test 4: Generate HTML Report
 */
async function testGenerateHTMLReport() {
  console.log('\n=== Test 4: Generate HTML Report ===');
  const replay = new ConsensusReplay();

  const mockComparison = {
    summary: {
      workflow_id: 'wf-test-html',
      task: 'Test HTML report generation',
      replayed_at: new Date().toISOString(),
      original_created_at: new Date().toISOString(),
      avg_confidence_delta: '0.065',
      arbiter_confidence_delta: '0.120',
      total_cost_delta: '-0.0050',
      verdict: 'SIGNIFICANT_IMPROVEMENT'
    },
    workers: [
      {
        model: 'opus',
        old_confidence: 0.75,
        new_confidence: 0.85,
        confidence_delta: 0.10,
        old_duration_ms: 5000,
        new_duration_ms: 4500,
        speed_improvement: '10.0%',
        old_cost_usd: 0.05,
        new_cost_usd: 0.04,
        cost_delta: -0.01
      },
      {
        model: 'sonnet',
        old_confidence: 0.80,
        new_confidence: 0.88,
        confidence_delta: 0.08,
        old_duration_ms: 3000,
        new_duration_ms: 2800,
        speed_improvement: '6.7%',
        old_cost_usd: 0.03,
        new_cost_usd: 0.03,
        cost_delta: 0
      }
    ],
    arbiter: {
      old_confidence: 0.82,
      new_confidence: 0.94,
      confidence_delta: 0.12,
      old_duration_ms: 4000,
      new_duration_ms: 3500,
      speed_improvement: '12.5%'
    },
    details: {}
  };

  const reportPath = path.join('/tmp', `replay-report-${Date.now()}.html`);

  try {
    replay.generateHTMLReport(mockComparison, reportPath);

    if (fs.existsSync(reportPath)) {
      const content = fs.readFileSync(reportPath, 'utf8');
      console.log('✅ HTML report generated successfully');
      console.log(`   Path: ${reportPath}`);
      console.log(`   Size: ${content.length} bytes`);

      // Verify content contains key elements
      const hasTitle = content.includes('Consensus Replay Report');
      const hasVerdict = content.includes('SIGNIFICANT_IMPROVEMENT');
      const hasWorkerTable = content.includes('Worker Comparison');
      const hasArbiterTable = content.includes('Arbiter Comparison');

      if (hasTitle && hasVerdict && hasWorkerTable && hasArbiterTable) {
        console.log('✅ Report contains all expected sections');
      } else {
        console.log('❌ Report missing expected sections');
      }
    } else {
      console.log('❌ HTML report not created');
    }

  } catch (error) {
    console.log('❌ HTML report test failed:', error.message);
  }
}

/**
 * Test 5: Confidence Extraction
 */
async function testConfidenceExtraction() {
  console.log('\n=== Test 5: Confidence Extraction ===');
  const replay = new ConsensusReplay();

  const testCases = [
    { text: 'Result: foo bar\nConfidence: 0.85', expected: 0.85 },
    { text: 'I am 92% confident in this answer', expected: 0.92 },
    { text: 'No confidence mentioned', expected: 0.5 },
    { text: 'CONFIDENCE: 0.75 based on analysis', expected: 0.75 },
  ];

  let passed = 0;
  for (const tc of testCases) {
    const extracted = replay._extractConfidence(tc.text);
    if (Math.abs(extracted - tc.expected) < 0.01) {
      console.log(`✅ Correctly extracted ${tc.expected} from: "${tc.text.substring(0, 50)}..."`);
      passed++;
    } else {
      console.log(`❌ Expected ${tc.expected}, got ${extracted} from: "${tc.text.substring(0, 50)}..."`);
    }
  }

  console.log(`\nPassed: ${passed}/${testCases.length} tests`);
}

/**
 * Test 6: Verdict Generation
 */
async function testVerdictGeneration() {
  console.log('\n=== Test 6: Verdict Generation ===');
  const replay = new ConsensusReplay();

  const testCases = [
    { arbiterDelta: 0.15, avgDelta: 0.08, expected: 'SIGNIFICANT_IMPROVEMENT' },
    { arbiterDelta: 0.07, avgDelta: 0.04, expected: 'MODERATE_IMPROVEMENT' },
    { arbiterDelta: -0.12, avgDelta: -0.03, expected: 'DEGRADATION' },
    { arbiterDelta: 0.02, avgDelta: 0.01, expected: 'NO_SIGNIFICANT_CHANGE' },
  ];

  let passed = 0;
  for (const tc of testCases) {
    const verdict = replay._generateVerdict(tc.arbiterDelta, tc.avgDelta);
    if (verdict === tc.expected) {
      console.log(`✅ Correct verdict: ${verdict} (arbiter: ${tc.arbiterDelta}, avg: ${tc.avgDelta})`);
      passed++;
    } else {
      console.log(`❌ Expected ${tc.expected}, got ${verdict} (arbiter: ${tc.arbiterDelta}, avg: ${tc.avgDelta})`);
    }
  }

  console.log(`\nPassed: ${passed}/${testCases.length} tests`);
}

/**
 * Run all tests
 */
async function runAllTests() {
  console.log('=== Consensus Replay Test Suite ===');
  console.log('Testing against PostgreSQL database on aio-01:5433');

  try {
    await testFetchHistoricalWorkflow();
    await testCompareResults();
    await testStoreReplayResults();
    await testGenerateHTMLReport();
    await testConfidenceExtraction();
    await testVerdictGeneration();

    console.log('\n=== All Tests Complete ===');

  } catch (error) {
    console.error('\n=== Test Suite Failed ===');
    console.error(error);
  } finally {
    await pool.end();
  }
}

// Run tests
if (require.main === module) {
  runAllTests();
}

module.exports = {
  testFetchHistoricalWorkflow,
  testCompareResults,
  testStoreReplayResults,
  testGenerateHTMLReport,
  testConfidenceExtraction,
  testVerdictGeneration
};
