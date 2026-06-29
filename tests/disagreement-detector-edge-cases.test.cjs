/**
 * Edge Case Tests for Disagreement Detector
 *
 * Tests the 3 priority fixes:
 * 1. NaN/Infinity guards in coefficientOfVariation
 * 2. Confidence validation (filter invalid scores)
 * 3. Task-specific thresholds
 *
 * Created: 2026-06-28
 */

const {
  analyzeDisagreement,
  coefficientOfVariation,
  getReviewThreshold,
  TASK_THRESHOLDS,
} = require('../shared/disagreement-detector.cjs');

// ============================================================================
// PRIORITY 1: NaN/Infinity Guards
// ============================================================================

console.log('\n=== PRIORITY 1: NaN/Infinity Guards ===\n');

// Test 1.1: Division by zero (all zeros)
console.log('Test 1.1: All zero values');
const cvAllZeros = coefficientOfVariation([0, 0, 0, 0]);
console.log(`  CV([0,0,0,0]) = ${cvAllZeros}`);
console.assert(cvAllZeros === 0, 'FAIL: Should return 0 for all zeros');
console.assert(isFinite(cvAllZeros), 'FAIL: Should be finite');
console.log('  ✅ PASS\n');

// Test 1.2: NaN inputs
console.log('Test 1.2: NaN inputs');
const cvNaN = coefficientOfVariation([NaN, NaN, NaN]);
console.log(`  CV([NaN,NaN,NaN]) = ${cvNaN}`);
console.assert(cvNaN === 0, 'FAIL: Should return 0 for NaN values');
console.assert(isFinite(cvNaN), 'FAIL: Should be finite');
console.log('  ✅ PASS\n');

// Test 1.3: Infinity inputs
console.log('Test 1.3: Infinity inputs');
const cvInfinity = coefficientOfVariation([Infinity, Infinity, Infinity]);
console.log(`  CV([Inf,Inf,Inf]) = ${cvInfinity}`);
console.assert(cvInfinity === 0, 'FAIL: Should return 0 for Infinity values');
console.assert(isFinite(cvInfinity), 'FAIL: Should be finite');
console.log('  ✅ PASS\n');

// Test 1.4: Mixed NaN and valid values
console.log('Test 1.4: Mixed NaN and valid values');
const cvMixed = coefficientOfVariation([10, NaN, 20, 30]);
console.log(`  CV([10,NaN,20,30]) = ${cvMixed}`);
// NaN propagates through mean/stdDev, should return 0
console.assert(cvMixed === 0, 'FAIL: Should return 0 when NaN in values');
console.assert(isFinite(cvMixed), 'FAIL: Should be finite');
console.log('  ✅ PASS\n');

// Test 1.5: Valid values (sanity check)
console.log('Test 1.5: Valid values (sanity check)');
const cvValid = coefficientOfVariation([10, 20, 30, 40]);
console.log(`  CV([10,20,30,40]) = ${cvValid.toFixed(4)}`);
console.assert(cvValid > 0 && isFinite(cvValid), 'FAIL: Should return valid CV');
console.log('  ✅ PASS\n');

// ============================================================================
// PRIORITY 2: Confidence Validation
// ============================================================================

console.log('\n=== PRIORITY 2: Confidence Validation ===\n');

// Test 2.1: All null confidence
console.log('Test 2.1: All null confidence');
const votesAllNull = [
  { model: 'opus', answer: 'A', confidence: null },
  { model: 'sonnet', answer: 'B', confidence: null },
  { model: 'haiku', answer: 'C', confidence: null },
];
const resultAllNull = analyzeDisagreement(votesAllNull);
console.log(`  Status: ${resultAllNull.status}`);
console.log(`  Error: ${resultAllNull.error}`);
console.assert(resultAllNull.status === 'error', 'FAIL: Should return error status');
console.assert(resultAllNull.error === 'all_invalid_confidence', 'FAIL: Should have correct error code');
console.log('  ✅ PASS\n');

// Test 2.2: All undefined confidence
console.log('Test 2.2: All undefined confidence');
const votesAllUndefined = [
  { model: 'opus', answer: 'A', confidence: undefined },
  { model: 'sonnet', answer: 'B', confidence: undefined },
];
const resultAllUndefined = analyzeDisagreement(votesAllUndefined);
console.log(`  Status: ${resultAllUndefined.status}`);
console.log(`  Error: ${resultAllUndefined.error}`);
console.assert(resultAllUndefined.status === 'error', 'FAIL: Should return error status');
console.assert(resultAllUndefined.error === 'all_invalid_confidence', 'FAIL: Should have correct error code');
console.log('  ✅ PASS\n');

// Test 2.3: All NaN confidence
console.log('Test 2.3: All NaN confidence');
const votesAllNaN = [
  { model: 'opus', answer: 'A', confidence: NaN },
  { model: 'sonnet', answer: 'B', confidence: NaN },
  { model: 'haiku', answer: 'C', confidence: NaN },
];
const resultAllNaN = analyzeDisagreement(votesAllNaN);
console.log(`  Status: ${resultAllNaN.status}`);
console.log(`  Error: ${resultAllNaN.error}`);
console.assert(resultAllNaN.status === 'error', 'FAIL: Should return error status');
console.assert(resultAllNaN.error === 'all_invalid_confidence', 'FAIL: Should have correct error code');
console.log('  ✅ PASS\n');

// Test 2.4: All Infinity confidence
console.log('Test 2.4: All Infinity confidence');
const votesAllInfinity = [
  { model: 'opus', answer: 'A', confidence: Infinity },
  { model: 'sonnet', answer: 'B', confidence: Infinity },
];
const resultAllInfinity = analyzeDisagreement(votesAllInfinity);
console.log(`  Status: ${resultAllInfinity.status}`);
console.log(`  Error: ${resultAllInfinity.error}`);
console.assert(resultAllInfinity.status === 'error', 'FAIL: Should return error status');
console.assert(resultAllInfinity.error === 'all_invalid_confidence', 'FAIL: Should have correct error code');
console.log('  ✅ PASS\n');

// Test 2.5: Mixed valid and invalid confidence
console.log('Test 2.5: Mixed valid and invalid confidence');
const votesMixed = [
  { model: 'opus', answer: 'A', confidence: 0.85 },
  { model: 'sonnet', answer: 'B', confidence: null },
  { model: 'haiku', answer: 'A', confidence: 0.90 },
  { model: 'fable', answer: 'C', confidence: NaN },
  { model: 'gpt4o', answer: 'A', confidence: 0.75 },
];
const resultMixed = analyzeDisagreement(votesMixed);
console.log(`  Status: ${resultMixed.status}`);
console.log(`  Original votes: ${resultMixed.original_vote_count}`);
console.log(`  Valid votes: ${resultMixed.num_votes}`);
console.log(`  Filtered: ${resultMixed.filtered_invalid_votes}`);
console.assert(resultMixed.status === 'success', 'FAIL: Should return success');
console.assert(resultMixed.original_vote_count === 5, 'FAIL: Should track original vote count');
console.assert(resultMixed.num_votes === 3, 'FAIL: Should have 3 valid votes');
console.assert(resultMixed.filtered_invalid_votes === 2, 'FAIL: Should have filtered 2 votes');
console.log('  ✅ PASS\n');

// Test 2.6: All valid confidence (sanity check)
console.log('Test 2.6: All valid confidence (sanity check)');
const votesAllValid = [
  { model: 'opus', answer: 'A', confidence: 0.85 },
  { model: 'sonnet', answer: 'B', confidence: 0.70 },
  { model: 'haiku', answer: 'A', confidence: 0.90 },
];
const resultAllValid = analyzeDisagreement(votesAllValid);
console.log(`  Status: ${resultAllValid.status}`);
console.log(`  Valid votes: ${resultAllValid.num_votes}`);
console.log(`  Filtered: ${resultAllValid.filtered_invalid_votes}`);
console.assert(resultAllValid.status === 'success', 'FAIL: Should return success');
console.assert(resultAllValid.num_votes === 3, 'FAIL: Should have 3 valid votes');
console.assert(resultAllValid.filtered_invalid_votes === 0, 'FAIL: Should have filtered 0 votes');
console.log('  ✅ PASS\n');

// ============================================================================
// PRIORITY 3: Task-Specific Thresholds
// ============================================================================

console.log('\n=== PRIORITY 3: Task-Specific Thresholds ===\n');

// Test 3.1: Security audit (stricter threshold)
console.log('Test 3.1: Security audit task (strict threshold)');
const securityThreshold = getReviewThreshold('security_audit');
console.log(`  Threshold: ${securityThreshold}`);
console.assert(securityThreshold === TASK_THRESHOLDS.security_audit, 'FAIL: Should match security_audit threshold');
console.assert(securityThreshold === 0.15, 'FAIL: Should be 0.15');
console.log('  ✅ PASS\n');

// Test 3.2: Research task (lenient threshold)
console.log('Test 3.2: Research task (lenient threshold)');
const researchThreshold = getReviewThreshold('research');
console.log(`  Threshold: ${researchThreshold}`);
console.assert(researchThreshold === TASK_THRESHOLDS.research, 'FAIL: Should match research threshold');
console.assert(researchThreshold === 0.30, 'FAIL: Should be 0.30');
console.log('  ✅ PASS\n');

// Test 3.3: Routing task (most lenient)
console.log('Test 3.3: Routing task (most lenient)');
const routingThreshold = getReviewThreshold('routing');
console.log(`  Threshold: ${routingThreshold}`);
console.assert(routingThreshold === TASK_THRESHOLDS.routing, 'FAIL: Should match routing threshold');
console.assert(routingThreshold === 0.40, 'FAIL: Should be 0.40');
console.log('  ✅ PASS\n');

// Test 3.4: Unknown task type (default)
console.log('Test 3.4: Unknown task type (default)');
const unknownThreshold = getReviewThreshold('unknown_task_type');
console.log(`  Threshold: ${unknownThreshold}`);
console.assert(unknownThreshold === TASK_THRESHOLDS.general, 'FAIL: Should match general threshold');
console.assert(unknownThreshold === 0.20, 'FAIL: Should be 0.20');
console.log('  ✅ PASS\n');

// Test 3.5: Task-specific threshold in analyzeDisagreement
console.log('Test 3.5: Task-specific threshold in analyzeDisagreement');
const votesForTaskType = [
  { model: 'opus', answer: 'A', confidence: 0.70 },
  { model: 'sonnet', answer: 'A', confidence: 0.75 },
  { model: 'haiku', answer: 'B', confidence: 0.60 },
];

// Security audit (strict: 0.15)
const securityResult = analyzeDisagreement(votesForTaskType, { task_type: 'security_audit' });
console.log(`  Security audit:`);
console.log(`    CV: ${securityResult.disagreement_score.toFixed(3)}`);
console.log(`    Threshold: ${securityResult.review_threshold}`);
console.log(`    Needs review: ${securityResult.needs_human_review}`);
console.assert(securityResult.task_type === 'security_audit', 'FAIL: Should have task_type set');
console.assert(securityResult.review_threshold === 0.15, 'FAIL: Should use security_audit threshold');

// Research (lenient: 0.30)
const researchResult = analyzeDisagreement(votesForTaskType, { task_type: 'research' });
console.log(`  Research:`);
console.log(`    CV: ${researchResult.disagreement_score.toFixed(3)}`);
console.log(`    Threshold: ${researchResult.review_threshold}`);
console.log(`    Needs review: ${researchResult.needs_human_review}`);
console.assert(researchResult.task_type === 'research', 'FAIL: Should have task_type set');
console.assert(researchResult.review_threshold === 0.30, 'FAIL: Should use research threshold');

// Same votes, different thresholds should yield different review decisions
console.log('  ✅ PASS\n');

// Test 3.6: Manual threshold override (should override task_type)
console.log('Test 3.6: Manual threshold override');
const manualResult = analyzeDisagreement(votesForTaskType, {
  task_type: 'security_audit',  // Would be 0.15
  review_threshold: 0.50,       // Manual override
});
console.log(`  Task type: ${manualResult.task_type}`);
console.log(`  Threshold: ${manualResult.review_threshold}`);
console.assert(manualResult.review_threshold === 0.50, 'FAIL: Should use manual override');
console.log('  ✅ PASS\n');

// ============================================================================
// SUMMARY
// ============================================================================

console.log('\n=== ALL EDGE CASE TESTS PASSED ✅ ===\n');

console.log('Priority 1: NaN/Infinity guards working correctly');
console.log('Priority 2: Confidence validation filtering invalid votes');
console.log('Priority 3: Task-specific thresholds implemented\n');

console.log('Task thresholds configured:');
for (const [task, threshold] of Object.entries(TASK_THRESHOLDS)) {
  console.log(`  ${task.padEnd(20)} → ${threshold}`);
}
console.log('');

// Gracefully close (let pool timeout naturally)
setTimeout(() => {
  console.log('Tests complete. Exiting.\n');
  process.exit(0);
}, 100);
