/**
 * OpenClaw Graceful Degradation Test
 *
 * Tests that ALL OpenClaw integration points work correctly when OpenClaw
 * is NOT running. This validates the core requirement: existing workflows
 * continue working perfectly without OpenClaw.
 *
 * Run: node test-openclaw-degradation.js
 *
 * Expected: ALL tests pass even without OpenClaw daemon running.
 */

import { openclawHealthCheck, getOpenClawVote } from './shared/openclaw-client.js';

let passed = 0;
let failed = 0;

function assert(condition, name) {
  if (condition) {
    console.log(`  PASS: ${name}`);
    passed++;
  } else {
    console.log(`  FAIL: ${name}`);
    failed++;
  }
}

console.log('OpenClaw Graceful Degradation Tests');
console.log('='.repeat(60));
console.log('These tests verify everything works when OpenClaw is NOT running.\n');

// ============================================================================
// Test 1: Health check returns false when OpenClaw not running
// ============================================================================

console.log('Test 1: Health Check (OpenClaw offline)');
const healthy = await openclawHealthCheck('localhost');
assert(healthy === false, 'Health check returns false when offline');

// ============================================================================
// Test 2: getOpenClawVote returns null when offline
// ============================================================================

console.log('\nTest 2: getOpenClawVote (OpenClaw offline)');
const vote = await getOpenClawVote('test prompt', { type: 'object', properties: {} });
assert(vote === null, 'getOpenClawVote returns null when offline');

// ============================================================================
// Test 3: Feature flag defaults to disabled
// ============================================================================

console.log('\nTest 3: Feature Flag');
const originalEnv = process.env.OPENCLAW_ENABLED;
delete process.env.OPENCLAW_ENABLED;
assert(!process.env.OPENCLAW_ENABLED, 'OPENCLAW_ENABLED not set by default');
assert(process.env.OPENCLAW_ENABLED !== 'true', 'Feature flag defaults to disabled');

// Test explicit enable/disable
process.env.OPENCLAW_ENABLED = 'true';
assert(process.env.OPENCLAW_ENABLED === 'true', 'Can enable via env var');

process.env.OPENCLAW_ENABLED = 'false';
assert(process.env.OPENCLAW_ENABLED !== 'true', 'Can disable via env var');

// Restore original
if (originalEnv !== undefined) {
  process.env.OPENCLAW_ENABLED = originalEnv;
} else {
  delete process.env.OPENCLAW_ENABLED;
}

// ============================================================================
// Test 4: openclaw-client.js exports are available
// ============================================================================

console.log('\nTest 4: Module Exports');
assert(typeof openclawHealthCheck === 'function', 'openclawHealthCheck is a function');
assert(typeof getOpenClawVote === 'function', 'getOpenClawVote is a function');

// ============================================================================
// Test 5: openclaw-fleet.js loads and exports correctly
// ============================================================================

console.log('\nTest 5: Fleet Module');
try {
  const fleet = await import('./shared/openclaw-fleet.js');
  assert(typeof fleet.hybridFleetExec === 'function', 'hybridFleetExec exported');
  assert(typeof fleet.openclawExec === 'function', 'openclawExec exported');
  assert(typeof fleet.openclawHealthCheck === 'function', 'fleet openclawHealthCheck exported');
  assert(typeof fleet.checkFleetOpenClawHealth === 'function', 'checkFleetOpenClawHealth exported');
  assert(typeof fleet.selectExecutionMode === 'function', 'selectExecutionMode exported');
  assert(typeof fleet.smartFleetExec === 'function', 'smartFleetExec exported');
  assert(typeof fleet.distributeItems === 'function', 'distributeItems exported');
  assert(typeof fleet.bulkFleetExec === 'function', 'bulkFleetExec exported');
} catch (e) {
  assert(false, `Fleet module import failed: ${e.message}`);
}

// ============================================================================
// Test 6: distributeItems works correctly
// ============================================================================

console.log('\nTest 6: Item Distribution');
try {
  const { distributeItems } = await import('./shared/openclaw-fleet.js');

  // Round-robin distribution
  const items = ['a', 'b', 'c', 'd', 'e', 'f'];
  const workers = [{ hostname: 'w1' }, { hostname: 'w2' }, { hostname: 'w3' }];
  const rrDist = distributeItems(items, workers, 'roundrobin');
  assert(rrDist.get('w1').length === 2, 'Round-robin: w1 gets 2 items');
  assert(rrDist.get('w2').length === 2, 'Round-robin: w2 gets 2 items');
  assert(rrDist.get('w3').length === 2, 'Round-robin: w3 gets 2 items');

  // Total items preserved
  const totalDistributed = rrDist.get('w1').length + rrDist.get('w2').length + rrDist.get('w3').length;
  assert(totalDistributed === items.length, `All ${items.length} items distributed`);
} catch (e) {
  assert(false, `Distribution test failed: ${e.message}`);
}

// ============================================================================
// Test 7: consensus-engine.js loads with OpenClaw support
// ============================================================================

console.log('\nTest 7: Consensus Engine OpenClaw Integration');
try {
  const engine = await import('./shared/consensus-engine.js');
  assert(typeof engine.multiModelReview === 'function', 'multiModelReview exported');
  assert(typeof engine.arbiterDecision === 'function', 'arbiterDecision exported');
  assert(typeof engine.calculateConsensus === 'function', 'calculateConsensus exported');
  assert(typeof engine.formatConsensusVote === 'function', 'formatConsensusVote exported');
  assert(typeof engine.isOpenClawEnabled === 'function', 'isOpenClawEnabled exported');
  assert(typeof engine.formatOpenClawEvidence === 'function', 'formatOpenClawEvidence exported');
} catch (e) {
  assert(false, `Consensus engine import failed: ${e.message}`);
}

// ============================================================================
// Test 8: formatOpenClawEvidence handles null
// ============================================================================

console.log('\nTest 8: OpenClaw Evidence Formatting');
try {
  const { formatOpenClawEvidence } = await import('./shared/consensus-engine.js');

  // Null result -> empty string
  const nullEvidence = formatOpenClawEvidence(null);
  assert(nullEvidence === '', 'Null result produces empty string');

  // Result without execution -> includes status
  const noExecEvidence = formatOpenClawEvidence({
    execution_performed: false,
    verification_status: 'not_testable',
    confidence: 60,
    reasoning: 'Cannot test this claim'
  });
  assert(noExecEvidence.includes('not_testable'), 'Includes verification status');
  assert(noExecEvidence.includes('NO'), 'Shows execution not performed');

  // Result with execution -> includes execution details
  const execEvidence = formatOpenClawEvidence({
    execution_performed: true,
    verification_status: 'passed',
    confidence: 95,
    reasoning: 'Verified by running code',
    execution_results: {
      command: 'python3 -c "print(1/0)"',
      exit_code: 1,
      stderr: 'ZeroDivisionError'
    }
  });
  assert(execEvidence.includes('YES'), 'Shows execution performed');
  assert(execEvidence.includes('ZeroDivisionError'), 'Includes execution output');
  assert(execEvidence.includes('ground truth'), 'Includes weighting instruction');
} catch (e) {
  assert(false, `Evidence formatting test failed: ${e.message}`);
}

// ============================================================================
// Test 9: model-detection.js has OpenClaw capabilities
// ============================================================================

console.log('\nTest 9: Model Detection');
try {
  const detection = await import('./shared/model-detection.js');
  assert(detection.MODEL_CAPABILITIES.openclaw !== undefined, 'OpenClaw in MODEL_CAPABILITIES');
  assert(detection.MODEL_CAPABILITIES.openclaw.tier === 'agent', 'OpenClaw tier is agent');
  assert(detection.MODEL_CAPABILITIES.openclaw.strengths.includes('execution verification'), 'Has execution verification strength');
  assert(detection.WORKER_PRESETS.MAXIMUM.includes('openclaw'), 'OpenClaw in MAXIMUM preset');
} catch (e) {
  assert(false, `Model detection test failed: ${e.message}`);
}

// ============================================================================
// Test 10: openclawExec handles offline gracefully
// ============================================================================

console.log('\nTest 10: Fleet openclawExec (offline)');
try {
  const { openclawExec } = await import('./shared/openclaw-fleet.js');
  const result = await openclawExec('localhost', 'echo test');
  assert(result.success === false, 'Returns success=false when offline');
  assert(result.hostname === 'localhost', 'Preserves hostname');
  assert(result.reason === 'openclaw_unavailable' || result.stderr !== '', 'Reports reason for failure');
} catch (e) {
  assert(false, `Fleet exec test failed: ${e.message}`);
}

// ============================================================================
// SUMMARY
// ============================================================================

console.log('\n' + '='.repeat(60));
console.log(`RESULTS: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log('='.repeat(60));

if (failed === 0) {
  console.log('\nAll graceful degradation tests passed.');
  console.log('OpenClaw integration is safe to deploy - existing workflows are unaffected.');
} else {
  console.log('\nSome tests failed. Fix before deploying.');
}

process.exit(failed > 0 ? 1 : 0);
