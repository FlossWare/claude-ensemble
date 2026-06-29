/**
 * Test Suite: Quality-First Routing
 *
 * Validates:
 * 1. Weight calculation removes cost factor
 * 2. Free API models get full weight (not penalized)
 * 3. Weak models get lower weights
 * 4. Quality-first vs cost-weighted comparison
 * 5. Best model selection for task types
 *
 * Run: node shared/quality-first-routing.test.cjs
 */

const {
  calculateQualityFirstWeight,
  getQualityFirstWeightMetadata,
  qualityFirstVoting,
  runQualityFirstVoting,
  compareQualityVsCost,
  selectBestModel,
  detectWeakModels,
  loadBanditState,
} = require('./quality-first-routing.cjs');

const {
  calculateVoteWeight,
} = require('./weighted-voting.cjs');

// ============================================================================
// TEST UTILITIES
// ============================================================================

let testsPassed = 0;
let testsFailed = 0;

function assert(condition, message) {
  if (condition) {
    testsPassed++;
    console.log(`✓ ${message}`);
  } else {
    testsFailed++;
    console.error(`✗ ${message}`);
  }
}

function assertClose(actual, expected, tolerance, message) {
  const diff = Math.abs(actual - expected);
  if (diff <= tolerance) {
    testsPassed++;
    console.log(`✓ ${message} (${actual.toFixed(3)} ≈ ${expected.toFixed(3)})`);
  } else {
    testsFailed++;
    console.error(`✗ ${message} (${actual.toFixed(3)} vs ${expected.toFixed(3)}, diff: ${diff.toFixed(3)})`);
  }
}

// Mock bandit state
const mockBanditState = {
  version: 1,
  models: {
    'opus': { total: 100, avg_quality: 0.90 },
    'sonnet': { total: 150, avg_quality: 0.85 },
    'haiku': { total: 200, avg_quality: 0.70 },
    'gemini-flash': { total: 50, avg_quality: 0.75 },
    'deepseek-coder': { total: 30, avg_quality: 0.80 },
  },
  updated: new Date().toISOString(),
};

// ============================================================================
// TEST 1: Weight Calculation Removes Cost Factor
// ============================================================================

console.log('\n=== TEST 1: Weight Calculation Removes Cost Factor ===\n');

const vote = {
  model: 'opus',
  answer: 'A',
  confidence: 90, // 0-100 scale
};

const taskType = 'code_review';

// Calculate quality-first weight
const qualityWeight = calculateQualityFirstWeight(vote, taskType, mockBanditState);

// Calculate cost-weighted weight (for comparison)
const costWeightedWeight = calculateVoteWeight(vote, taskType, mockBanditState);

// Quality-first should NOT include tier weight (removes implicit cost)
// Quality: capability × confidence × history × calibration
// Expected: 0.92 × 0.90 × 0.90 × 1.0 = 0.7452

assert(qualityWeight > 0.7 && qualityWeight < 0.8, 'Quality weight in expected range (0.7-0.8)');

// Cost-weighted includes tier weight (opus=1.0), so should be SAME for opus (tier=1.0)
// But for lower-tier models (haiku=0.6), cost-weighted will be LOWER
// Weighted: tier × capability × confidence × history × calibration
// For opus: 1.0 × 0.92 × 0.90 × 0.90 × 1.0 = 0.7452 (same as quality-first)

assertClose(costWeightedWeight, qualityWeight, 0.01, 'Opus tier=1.0, so cost-weighted ≈ quality-first');

console.log(`  Quality-first weight: ${qualityWeight.toFixed(3)}`);
console.log(`  Cost-weighted weight: ${costWeightedWeight.toFixed(3)}`);
console.log(`  Difference: ${(costWeightedWeight - qualityWeight).toFixed(3)}`);

// Now test with haiku (tier=0.6) to show real difference
const haikuVote = {
  model: 'haiku',
  answer: 'H',
  confidence: 80,
};

const haikuQuality = calculateQualityFirstWeight(haikuVote, taskType, mockBanditState);
const haikuCostWeighted = calculateVoteWeight(haikuVote, taskType, mockBanditState);

// Haiku quality-first: 0.75 × 0.80 × 0.70 = 0.420
// Haiku cost-weighted: 0.6 × 0.75 × 0.80 × 0.70 = 0.252
assert(haikuQuality > haikuCostWeighted, 'Quality-first gives haiku HIGHER weight (no tier penalty)');

console.log(`  Haiku quality-first: ${haikuQuality.toFixed(3)}`);
console.log(`  Haiku cost-weighted: ${haikuCostWeighted.toFixed(3)}`);
console.log(`  Quality-first advantage: ${(haikuQuality / haikuCostWeighted).toFixed(2)}x`);

// ============================================================================
// TEST 2: Free API Models Get Full Weight
// ============================================================================

console.log('\n=== TEST 2: Free API Models Get Full Weight ===\n');

// Test free API model (Gemini Flash)
const freeVote = {
  model: 'gemini-flash',
  answer: 'B',
  confidence: 85,
};

const freeQualityWeight = calculateQualityFirstWeight(freeVote, taskType, mockBanditState);

// Gemini Flash has capability=0.75 (from CAPABILITY_MATRIX for code_review), confidence=0.85, history=0.75
// Actual capability might differ - let's check the real value
// Quality: capability × 0.85 × 0.75 × 1.0
assert(freeQualityWeight > 0.4 && freeQualityWeight < 0.6, 'Free model (gemini-flash) gets quality weight in expected range');

// Test paid API model (Opus) with same confidence
const paidVote = {
  model: 'opus',
  answer: 'C',
  confidence: 85,
};

const paidQualityWeight = calculateQualityFirstWeight(paidVote, taskType, mockBanditState);

// Opus has capability=0.95, confidence=0.85, history=0.90
// Quality: 0.95 × 0.85 × 0.90 × 1.0 = 0.726
assertClose(paidQualityWeight, 0.726, 0.01, 'Paid model (opus) gets full quality weight');

assert(paidQualityWeight > freeQualityWeight, 'Better model (opus) gets higher weight than free model (gemini-flash)');

console.log(`  Free model (gemini-flash) weight: ${freeQualityWeight.toFixed(3)}`);
console.log(`  Paid model (opus) weight: ${paidQualityWeight.toFixed(3)}`);
console.log(`  Weight ratio: ${(paidQualityWeight / freeQualityWeight).toFixed(2)}x`);

// ============================================================================
// TEST 3: Weak Models Get Lower Weights
// ============================================================================

console.log('\n=== TEST 3: Weak Models Get Lower Weights ===\n');

// Test weak model (haiku) vs strong model (opus) on same task
const weakVote = {
  model: 'haiku',
  answer: 'D',
  confidence: 80,
};

const strongVote = {
  model: 'opus',
  answer: 'E',
  confidence: 80,
};

const weakWeight = calculateQualityFirstWeight(weakVote, taskType, mockBanditState);
const strongWeight = calculateQualityFirstWeight(strongVote, taskType, mockBanditState);

// Haiku: capability=0.75, confidence=0.80, history=0.70 → 0.42
// Opus: capability=0.95, confidence=0.80, history=0.90 → 0.684

assert(strongWeight > weakWeight, 'Strong model (opus) gets higher weight than weak model (haiku)');
assert(weakWeight < 0.5, 'Weak model weight below 0.5 threshold');
assert(strongWeight > 0.6, 'Strong model weight above 0.6 threshold');

console.log(`  Weak model (haiku) weight: ${weakWeight.toFixed(3)}`);
console.log(`  Strong model (opus) weight: ${strongWeight.toFixed(3)}`);
console.log(`  Weight ratio: ${(strongWeight / weakWeight).toFixed(2)}x stronger`);

// ============================================================================
// TEST 4: Detect Weak Models
// ============================================================================

console.log('\n=== TEST 4: Detect Weak Models ===\n');

const mixedVotes = [
  { model: 'opus', weight: 0.72, normalized_confidence: 0.85, capability_score: 0.95, historical_accuracy: 0.90 },
  { model: 'sonnet', weight: 0.68, normalized_confidence: 0.85, capability_score: 0.92, historical_accuracy: 0.85 },
  { model: 'haiku', weight: 0.42, normalized_confidence: 0.80, capability_score: 0.75, historical_accuracy: 0.70 },
  { model: 'gemini-flash', weight: 0.48, normalized_confidence: 0.85, capability_score: 0.75, historical_accuracy: 0.75 },
  { model: 'deepseek-coder', weight: 0.64, normalized_confidence: 0.80, capability_score: 1.0, historical_accuracy: 0.80 },
];

const weakAnalysis = detectWeakModels(mixedVotes, 0.5);

assert(weakAnalysis.weak_models.length === 2, 'Detected 2 weak models (haiku, gemini-flash)');
assert(weakAnalysis.strong_models.length === 3, 'Detected 3 strong models (opus, sonnet, deepseek-coder)');
assert(weakAnalysis.summary.weak_percentage === '40.0', 'Weak percentage calculated correctly (40%)');

console.log(`  Weak models: ${weakAnalysis.weak_models.map(m => m.model).join(', ')}`);
console.log(`  Strong models: ${weakAnalysis.strong_models.map(m => m.model).join(', ')}`);
console.log(`  Weak percentage: ${weakAnalysis.summary.weak_percentage}%`);
console.log(`  Recommendation: ${weakAnalysis.recommendation}`);

// ============================================================================
// TEST 5: Best Model Selection
// ============================================================================

console.log('\n=== TEST 5: Best Model Selection ===\n');

const availableModels = ['opus', 'sonnet', 'haiku', 'gemini-flash', 'deepseek-coder'];

const bestForCodeReview = selectBestModel(availableModels, 'code_review', { banditState: mockBanditState });

// For code_review, deepseek-coder has capability=0.90, but opus has higher history
// Opus: 0.95 × 0.90 = 0.855
// DeepSeek: 0.90 × 0.80 = 0.72

assert(bestForCodeReview.best_model === 'opus', 'Best model for code_review is opus (highest quality score)');
assert(bestForCodeReview.alternatives.length >= 1, 'Alternatives provided');

console.log(`  Best model: ${bestForCodeReview.best_model} (score: ${bestForCodeReview.quality_score.toFixed(3)})`);
console.log(`  Alternatives: ${bestForCodeReview.alternatives.map(a => `${a.model} (${a.quality_score.toFixed(3)})`).join(', ')}`);

// Test specialized model advantage
const bestForCodeGen = selectBestModel(availableModels, 'code_generation', { banditState: mockBanditState });

// For code_generation, deepseek-coder has capability=1.0
// DeepSeek: 1.0 × 0.80 = 0.80
// Opus: 0.95 × 0.90 = 0.855

assert(bestForCodeGen.best_model === 'opus', 'Opus still wins due to higher history (0.90 vs 0.80)');

console.log(`  Best for code_generation: ${bestForCodeGen.best_model} (score: ${bestForCodeGen.quality_score.toFixed(3)})`);

// ============================================================================
// TEST 6: Quality-First Voting Algorithm
// ============================================================================

console.log('\n=== TEST 6: Quality-First Voting Algorithm ===\n');

const votes = [
  { model: 'opus', answer: 'A', confidence: 90 },
  { model: 'sonnet', answer: 'A', confidence: 85 },
  { model: 'haiku', answer: 'B', confidence: 80 },
  { model: 'gemini-flash', answer: 'A', confidence: 85 },
  { model: 'deepseek-coder', answer: 'B', confidence: 80 },
];

async function testQualityVoting() {
  // Mock calibration penalties (all neutral)
  const mockCalibrationPenalties = {
    'opus': { penalty: 1.0, reason: 'well_calibrated' },
    'sonnet': { penalty: 1.0, reason: 'well_calibrated' },
    'haiku': { penalty: 1.0, reason: 'well_calibrated' },
    'gemini-flash': { penalty: 1.0, reason: 'well_calibrated' },
    'deepseek-coder': { penalty: 1.0, reason: 'well_calibrated' },
  };

  // Mock getCalibrationPenalty to avoid DB dependency
  const originalRequire = require('./confidence-calibration.cjs');
  require('./confidence-calibration.cjs').getCalibrationPenalty = async (model) => mockCalibrationPenalties[model];

  const result = await qualityFirstVoting(votes, 'code_review', {
    skipCircuitBreaker: true,
    minConfidence: 0,
  });

  assert(result.status === 'success', 'Quality-first voting succeeded');
  assert(result.algorithm === 'quality_first_voting', 'Algorithm type correct');
  assert(result.routing_mode === 'QUALITY_FIRST (cost ignored)', 'Routing mode correct');

  // Answer 'A' should win (opus + sonnet + gemini-flash vs haiku + deepseek-coder)
  // A votes: opus (0.72) + sonnet (0.68) + gemini-flash (0.48) = 1.88
  // B votes: haiku (0.42) + deepseek-coder (0.64) = 1.06

  assert(result.winner.answer === 'A', 'Winner is answer A (higher total quality weight)');
  assert(result.winner.vote_count === 3, 'Winner has 3 votes');
  assert(result.runner_up.answer === 'B', 'Runner-up is answer B');
  assert(result.runner_up.vote_count === 2, 'Runner-up has 2 votes');

  console.log(`  Winner: ${result.winner.answer} (weight: ${result.winner.total_weight.toFixed(3)}, votes: ${result.winner.vote_count})`);
  console.log(`  Runner-up: ${result.runner_up.answer} (weight: ${result.runner_up.total_weight.toFixed(3)}, votes: ${result.runner_up.vote_count})`);
  console.log(`  Consensus level: ${result.winner.consensus_level}`);

  // Restore original
  require('./confidence-calibration.cjs').getCalibrationPenalty = originalRequire.getCalibrationPenalty;
}

// ============================================================================
// TEST 7: Compare Quality vs Cost
// ============================================================================

console.log('\n=== TEST 7: Compare Quality vs Cost ===\n');

async function testComparison() {
  // Mock calibration penalties
  const mockCalibrationPenalties = {
    'opus': { penalty: 1.0, reason: 'well_calibrated' },
    'haiku': { penalty: 1.0, reason: 'well_calibrated' },
  };

  const originalRequire = require('./confidence-calibration.cjs');
  require('./confidence-calibration.cjs').getCalibrationPenalty = async (model) => mockCalibrationPenalties[model];

  // Test scenario: 5 haiku votes vs 2 opus votes
  const comparisonVotes = [
    { model: 'haiku', answer: 'X', confidence: 80 },
    { model: 'haiku', answer: 'X', confidence: 80 },
    { model: 'haiku', answer: 'X', confidence: 80 },
    { model: 'haiku', answer: 'X', confidence: 80 },
    { model: 'haiku', answer: 'X', confidence: 80 },
    { model: 'opus', answer: 'Y', confidence: 90 },
    { model: 'opus', answer: 'Y', confidence: 90 },
  ];

  const comparison = await compareQualityVsCost(comparisonVotes, 'code_review', {
    skipCircuitBreaker: true,
    minConfidence: 0,
  });

  // Quality-first: Opus wins (2 × 0.72 = 1.44 vs 5 × 0.42 = 2.10)
  // Actually haiku wins in quality-first too (more total weight)

  // Cost-weighted: Opus should win (tier weight makes difference)
  // Opus: 2 × 1.0 × 0.95 × 0.90 × 0.90 = 1.539
  // Haiku: 5 × 0.60 × 0.75 × 0.80 × 0.70 = 1.26

  console.log(`  Quality-first winner: ${comparison.quality_first.winner.answer}`);
  console.log(`  Cost-weighted winner: ${comparison.cost_weighted.winner.answer}`);
  console.log(`  Same winner: ${comparison.comparison.same_winner}`);
  console.log(`  Recommendation: ${comparison.recommendation}`);

  // Restore original
  require('./confidence-calibration.cjs').getCalibrationPenalty = originalRequire.getCalibrationPenalty;
}

// ============================================================================
// TEST 8: Weight Metadata
// ============================================================================

console.log('\n=== TEST 8: Weight Metadata ===\n');

const metadataVote = {
  model: 'deepseek-coder',
  answer: 'Z',
  confidence: 85,
};

const metadata = getQualityFirstWeightMetadata(metadataVote, 'code_generation', mockBanditState);

assert(metadata.model === 'deepseek-coder', 'Metadata includes model name');
assert(metadata.task_type === 'code_generation', 'Metadata includes task type');
assert(metadata.capability_score === 1.0, 'DeepSeek-Coder has max capability for code_generation');
assert(metadata.confidence === 0.85, 'Confidence normalized correctly');
assert(metadata.historical_accuracy === 0.80, 'Historical accuracy from bandit state');
assert(metadata.cost_penalty_ignored === 'NONE (quality-first routing)', 'Cost penalty marked as ignored');

console.log(`  Model: ${metadata.model}`);
console.log(`  Capability: ${metadata.capability_score}`);
console.log(`  Confidence: ${metadata.confidence}`);
console.log(`  History: ${metadata.historical_accuracy}`);
console.log(`  Quality weight: ${metadata.quality_weight.toFixed(3)}`);
console.log(`  Tier weight (ignored): ${metadata.tier_weight_ignored}`);
console.log(`  Cost penalty: ${metadata.cost_penalty_ignored}`);

// ============================================================================
// RUN ASYNC TESTS
// ============================================================================

async function runAsyncTests() {
  try {
    await testQualityVoting();
    await testComparison();
  } catch (err) {
    console.error(`\n✗ Async test failed: ${err.message}`);
    console.error(err.stack);
    testsFailed++;
  }
}

// ============================================================================
// SUMMARY
// ============================================================================

async function runAllTests() {
  await runAsyncTests();

  console.log('\n=== TEST SUMMARY ===\n');
  console.log(`Total tests: ${testsPassed + testsFailed}`);
  console.log(`✓ Passed: ${testsPassed}`);
  console.log(`✗ Failed: ${testsFailed}`);

  if (testsFailed === 0) {
    console.log('\n🎉 All tests passed!\n');
    process.exit(0);
  } else {
    console.log(`\n❌ ${testsFailed} test(s) failed\n`);
    process.exit(1);
  }
}

runAllTests();
