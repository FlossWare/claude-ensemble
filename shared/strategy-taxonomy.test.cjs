'use strict';

const {
  StrategyTaxonomy,
  STRATEGY_DIMENSIONS,
  PROMPT_STRATEGIES,
  ORCHESTRATION_STRATEGIES,
  VERIFICATION_STRATEGIES,
  SEQUENCE_STRATEGIES,
  getDimensions,
  getStrategies,
  getStrategyMeta,
  getTotalStrategies,
  estimateCost,
  estimateLatency,
  filterStrategies,
} = require('./strategy-taxonomy.cjs');

let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) { passed++; }
  else { failed++; console.error(`FAIL: ${msg}`); }
}

console.log('=== Strategy Taxonomy Test Suite ===\n');

// ========== DIMENSION TESTS ==========
console.log('Testing dimensions...');
const dims = getDimensions();
assert(dims.length === 4, 'should have 4 dimensions');
assert(dims.includes('prompts'), 'should include prompts');
assert(dims.includes('orchestration'), 'should include orchestration');
assert(dims.includes('verification'), 'should include verification');
assert(dims.includes('sequences'), 'should include sequences');

// ========== STRATEGY COUNT TESTS ==========
console.log('Testing strategy counts...');
assert(getStrategies('prompts').length === 4, 'prompts has 4 strategies');
assert(getStrategies('orchestration').length === 4, 'orchestration has 4 strategies');
assert(getStrategies('verification').length === 3, 'verification has 3 strategies');
assert(getStrategies('sequences').length === 3, 'sequences has 3 strategies');

// Total
assert(getTotalStrategies() === 14, `total strategies should be 14, got ${getTotalStrategies()}`);

// ========== METADATA TESTS ==========
console.log('Testing metadata...');
const meta = getStrategyMeta('prompts', 'zero_shot');
assert(meta.cost_profile === 'low', 'zero_shot cost is low');
assert(meta.latency_profile === 'low', 'zero_shot latency is low');
assert(meta.dimension === 'prompts', 'meta includes dimension');
assert(meta.strategy === 'zero_shot', 'meta includes strategy name');
assert(typeof meta.description === 'string', 'meta has description');

// ========== ERROR HANDLING TESTS ==========
console.log('Testing error handling...');
try { getStrategies('nonexistent'); assert(false, 'should throw'); } catch (e) { passed++; }
try { getStrategyMeta('prompts', 'nonexistent'); assert(false, 'should throw'); } catch (e) { passed++; }

// ========== COST/LATENCY ESTIMATION TESTS ==========
console.log('Testing cost and latency estimation...');
const cheapCombo = { prompts: 'zero_shot', orchestration: 'single_model', verification: 'self_check', sequences: 'analyze_then_verify' };
const expensiveCombo = { prompts: 'tree_of_thought', orchestration: 'adversarial', verification: 'adversarial_refute', sequences: 'iterative_refine' };
assert(estimateCost(cheapCombo) < estimateCost(expensiveCombo), 'cheap combo costs less');
// Note: latency is based on max profile across dimensions, so high latency_profile in analyze_then_verify makes both combos equal
const cheapLatency = estimateLatency(cheapCombo);
const expensiveLatency = estimateLatency(expensiveCombo);
assert(cheapLatency <= expensiveLatency, 'cheap combo has lower or equal latency');

// ========== FILTERING TESTS ==========
console.log('Testing filtering...');
const lowCost = filterStrategies('prompts', { maxCost: 'low' });
assert(lowCost.includes('zero_shot'), 'zero_shot is low cost');
assert(!lowCost.includes('tree_of_thought'), 'tree_of_thought is not low cost');

const lowLatency = filterStrategies('orchestration', { maxLatency: 'low' });
assert(lowLatency.includes('single_model'), 'single_model is low latency');

// ========== METADATA VALIDATION TESTS ==========
console.log('Testing metadata completeness...');
for (const dim of dims) {
  for (const strat of getStrategies(dim)) {
    const m = getStrategyMeta(dim, strat);
    assert(m.description, `${dim}.${strat} has description`);
    assert(['low', 'medium', 'high'].includes(m.cost_profile), `${dim}.${strat} has valid cost_profile`);
    assert(['low', 'medium', 'high'].includes(m.latency_profile), `${dim}.${strat} has valid latency_profile`);
  }
}

// ========== STRATEGY TAXONOMY CLASS TESTS ==========
console.log('\nTesting StrategyTaxonomy class...');
const tax = new StrategyTaxonomy();

// Test getStrategy
const zeroShotStrat = tax.getStrategy('zero_shot');
assert(zeroShotStrat !== null, 'getStrategy returns zero_shot');
assert(zeroShotStrat.type === 'prompt', 'zero_shot is prompt type');

const consensusStrat = tax.getStrategy('consensus');
assert(consensusStrat !== null, 'getStrategy returns consensus');
assert(consensusStrat.type === 'orchestration', 'consensus is orchestration type');

// Test getDimension
const prompts = tax.getDimension('prompts');
assert(prompts !== null, 'getDimension returns prompts');
assert(Object.keys(prompts).length === 4, 'prompts dimension has 4 strategies');

// Test listStrategyIds
const promptIds = tax.listStrategyIds('prompts');
assert(promptIds.length === 4, 'listStrategyIds returns 4 prompt strategies');
assert(promptIds.includes('zero_shot'), 'includes zero_shot');
assert(promptIds.includes('few_shot'), 'includes few_shot');
assert(promptIds.includes('chain_of_thought'), 'includes chain_of_thought');
assert(promptIds.includes('tree_of_thought'), 'includes tree_of_thought');

// Test getRecommendation
const simpleRecommendation = tax.getRecommendation('simple_task');
assert(simpleRecommendation.prompt === 'zero_shot', 'simple task uses zero_shot');
assert(simpleRecommendation.orchestration === 'single_model', 'simple task uses single_model');

const complexRecommendation = tax.getRecommendation('complex_problem');
assert(complexRecommendation.prompt === 'chain_of_thought', 'complex task uses chain_of_thought');
assert(complexRecommendation.orchestration === 'consensus', 'complex task uses consensus');

const criticalRecommendation = tax.getRecommendation('critical_decision');
assert(criticalRecommendation.orchestration === 'adversarial', 'critical decision uses adversarial');
assert(criticalRecommendation.verification === 'adversarial_refute', 'critical decision uses adversarial_refute');

// Test calculateCost
const costResult = tax.calculateCost(simpleRecommendation);
assert(typeof costResult.base === 'number', 'calculateCost returns base cost');
assert(typeof costResult.estimated_tokens === 'number', 'calculateCost returns estimated_tokens');
assert(typeof costResult.estimated_cost_usd === 'number', 'calculateCost returns estimated_cost_usd');
assert(costResult.base === 1.2, 'simple task has base cost 1.2 (1.0 * 1.2 for self_check)');

const expensiveCost = tax.calculateCost(criticalRecommendation);
assert(expensiveCost.base > costResult.base, 'critical decision costs more than simple task');

// Test calculateLatency
const latencyResult = tax.calculateLatency(simpleRecommendation);
assert(typeof latencyResult.relative === 'number', 'calculateLatency returns relative');
assert(typeof latencyResult.estimated_ms === 'number', 'calculateLatency returns estimated_ms');

const criticalLatency = tax.calculateLatency(criticalRecommendation);
assert(criticalLatency.relative >= latencyResult.relative, 'critical decision has higher or equal latency');

// Test validateCombination
const validationResult = tax.validateCombination(simpleRecommendation);
assert(validationResult.valid === true, 'validation result has valid field');
assert(Array.isArray(validationResult.warnings), 'validation result has warnings array');

const invalidCombo = { prompt: 'zero_shot', orchestration: 'adversarial', verification: 'self_check', sequence: 'parallel_then_merge' };
const invalidValidation = tax.validateCombination(invalidCombo);
assert(invalidValidation.warnings.length > 0, 'invalid combo has warnings');

// Test toJSON
const json = tax.toJSON();
assert(json.prompts !== undefined, 'toJSON includes prompts');
assert(json.orchestration !== undefined, 'toJSON includes orchestration');
assert(json.verification !== undefined, 'toJSON includes verification');
assert(json.sequences !== undefined, 'toJSON includes sequences');
assert(json.all_strategies !== undefined, 'toJSON includes all_strategies');
assert(Object.keys(json.all_strategies).length === 14, 'all_strategies has 14 items');

// Test getStats
const stats = tax.getStats();
assert(stats.total_strategies === 14, 'stats shows 14 total strategies');
assert(stats.prompt_strategies === 4, 'stats shows 4 prompt strategies');
assert(stats.orchestration_strategies === 4, 'stats shows 4 orchestration strategies');
assert(stats.verification_strategies === 3, 'stats shows 3 verification strategies');
assert(stats.sequence_strategies === 3, 'stats shows 3 sequence strategies');

// ========== STRATEGY DETAILS TESTS ==========
console.log('\nTesting strategy details...');

// Test PROMPT_STRATEGIES
assert(PROMPT_STRATEGIES.zero_shot.id === 'zero_shot', 'zero_shot has id');
assert(Array.isArray(PROMPT_STRATEGIES.zero_shot.use_cases), 'zero_shot has use_cases');
assert(Array.isArray(PROMPT_STRATEGIES.zero_shot.pros), 'zero_shot has pros');
assert(Array.isArray(PROMPT_STRATEGIES.zero_shot.cons), 'zero_shot has cons');

// Test ORCHESTRATION_STRATEGIES
assert(ORCHESTRATION_STRATEGIES.consensus.cost_relative === 3.0, 'consensus has cost_relative');
assert(ORCHESTRATION_STRATEGIES.consensus.quality_relative === 0.88, 'consensus has quality_relative');

// Test VERIFICATION_STRATEGIES
assert(VERIFICATION_STRATEGIES.peer_review.effectiveness === 0.72, 'peer_review has effectiveness');
assert(VERIFICATION_STRATEGIES.peer_review.cost_multiplier === 1.5, 'peer_review has cost_multiplier');

// Test SEQUENCE_STRATEGIES
assert(SEQUENCE_STRATEGIES.iterative_refine.latency_factor === 3.5, 'iterative_refine has latency_factor');
assert(Array.isArray(SEQUENCE_STRATEGIES.iterative_refine.good_for), 'iterative_refine has good_for');

console.log(`\n=== Test Results ===`);
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);
console.log(`Total:  ${passed + failed}`);
process.exit(failed > 0 ? 1 : 0);
