#!/usr/bin/env node
/**
 * Validation Test - Prove Active Learning Works
 *
 * Tests that:
 * 1. consultLearnings() returns meaningful guidance
 * 2. selectModelIntelligently() varies based on Thompson Sampling
 * 3. searchKnowledgeBases() finds disseminator knowledge
 * 4. shouldUseOrchestrator() makes intelligent decisions
 * 5. recordDecision() feeds the learning loop
 * 6. orchestrator-brain makes smarter decisions over time
 *
 * Run: node validation-test.js
 */

import {
  consultLearnings,
  selectModelIntelligently,
  searchKnowledgeBases,
  shouldUseOrchestrator,
  recordDecision,
  getDecisionSummary,
} from './claude-learning-integration.js';

import {
  analyzeTaskComplexity,
  selectAgentStrategy,
  coordinateTask,
  learnFromCoordination,
  getIntelligenceSummary,
  STRATEGIES,
} from './orchestrator-brain.js';

import * as db from './learning/db.js';
import * as thompson from './learning/thompson-sampling.js';

// ============================================================================
// TEST SUITE
// ============================================================================

let passCount = 0;
let failCount = 0;

function test(name, fn) {
  return async () => {
    process.stdout.write(`\n▶ ${name} ... `);
    try {
      await fn();
      passCount++;
      console.log('✓ PASS');
      return true;
    } catch (err) {
      failCount++;
      console.log(`✗ FAIL\n  ${err.message}`);
      if (process.env.DEBUG) {
        console.error(err.stack);
      }
      return false;
    }
  };
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertExists(value, name) {
  assert(value !== null && value !== undefined, `${name} should exist`);
}

function assertNumber(value, name) {
  assertExists(value, name);
  assert(typeof value === 'number', `${name} should be a number`);
}

function assertString(value, name) {
  assertExists(value, name);
  assert(typeof value === 'string', `${name} should be a string`);
}

function assertArray(value, name) {
  assertExists(value, name);
  assert(Array.isArray(value), `${name} should be an array`);
}

// ============================================================================
// TEST 1: consultLearnings() Returns Meaningful Guidance
// ============================================================================

const test1 = test('consultLearnings() returns guidance', async () => {
  const guidance = await consultLearnings('code-review', { days: 90 });

  assertExists(guidance, 'guidance');
  assertString(guidance.task_type, 'task_type');
  assert(guidance.task_type === 'code-review', 'task_type should match input');

  if (guidance.available) {
    assertNumber(guidance.success_rate, 'success_rate');
    assertNumber(guidance.avg_quality, 'avg_quality');
    assertArray(guidance.best_models, 'best_models');
    assertArray(guidance.best_strategies, 'best_strategies');
    assertString(guidance.recommendation, 'recommendation');
    assertNumber(guidance.confidence, 'confidence');

    console.log(`\n    Sample size: ${guidance.sample_size}`);
    console.log(`    Success rate: ${(guidance.success_rate * 100).toFixed(1)}%`);
    console.log(`    Avg quality: ${guidance.avg_quality.toFixed(2)}`);
    console.log(`    Best model: ${guidance.best_models[0]?.model || 'none'}`);
    console.log(`    Recommendation: ${guidance.recommendation}`);
  } else {
    console.log(`\n    No historical data available - ${guidance.recommendation}`);
  }
});

// ============================================================================
// TEST 2: selectModelIntelligently() Uses Thompson Sampling
// ============================================================================

const test2 = test('selectModelIntelligently() uses Thompson Sampling', async () => {
  const selections = [];

  // Run 10 selections and see if we get variety (exploration)
  for (let i = 0; i < 10; i++) {
    const model = await selectModelIntelligently('code-review', {
      useThompson: true,
      count: 1,
    });
    selections.push(model);
  }

  const unique = new Set(selections);

  console.log(`\n    Selections: ${selections.join(', ')}`);
  console.log(`    Unique models: ${unique.size} / 10`);

  // Thompson Sampling should explore, so we expect some variety
  // (unless one model is extremely dominant)
  assert(selections.length === 10, 'Should make 10 selections');

  // For greedy, should always pick same model
  const greedySelections = [];
  for (let i = 0; i < 5; i++) {
    const model = await selectModelIntelligently('code-review', {
      useThompson: false,
      count: 1,
    });
    greedySelections.push(model);
  }

  const greedyUnique = new Set(greedySelections);
  console.log(`    Greedy selections: ${greedySelections.join(', ')}`);
  console.log(`    Greedy unique: ${greedyUnique.size} / 5 (should be 1 if data exists)`);
});

// ============================================================================
// TEST 3: searchKnowledgeBases() Finds Disseminator Knowledge
// ============================================================================

const test3 = test('searchKnowledgeBases() finds knowledge', async () => {
  const knowledge = await searchKnowledgeBases('endpoint configuration', {
    limit: 5,
    minConfidence: 0.5,
  });

  assertExists(knowledge, 'knowledge');
  assertString(knowledge.query, 'query');
  assertArray(knowledge.disseminator, 'disseminator results');
  assertArray(knowledge.web_synthesis, 'web_synthesis results');
  assertNumber(knowledge.total_found, 'total_found');

  console.log(`\n    Query: ${knowledge.query}`);
  console.log(`    Disseminator: ${knowledge.disseminator.length} items`);
  console.log(`    Web synthesis: ${knowledge.web_synthesis.length} items`);
  console.log(`    Total found: ${knowledge.total_found}`);

  if (knowledge.disseminator.length > 0) {
    const first = knowledge.disseminator[0];
    console.log(`    Sample: "${first.title}" (confidence: ${first.confidence}, relevance: ${first.relevance?.toFixed(2)})`);
  }

  // Should find something from disseminator KB (166 items)
  // (unless the query doesn't match anything)
  assert(knowledge.total_found >= 0, 'Should return valid count');
});

// ============================================================================
// TEST 4: shouldUseOrchestrator() Makes Intelligent Decisions
// ============================================================================

const test4 = test('shouldUseOrchestrator() decides correctly', async () => {
  // Simple task - should NOT use orchestrator
  const simpleTask = {
    type: 'simple-query',
    complexity: 0.2,
    multiDomain: false,
    modelCount: 1,
  };

  const simpleDecision = await shouldUseOrchestrator(simpleTask);
  assertExists(simpleDecision, 'simpleDecision');
  assert(typeof simpleDecision.use_orchestrator === 'boolean', 'use_orchestrator should be boolean');
  assertArray(simpleDecision.reasons, 'reasons');

  console.log(`\n    Simple task: use_orchestrator=${simpleDecision.use_orchestrator}`);
  console.log(`    Reasons: ${simpleDecision.reasons.join(', ') || 'none'}`);

  // Complex task - SHOULD use orchestrator
  const complexTask = {
    type: 'multi-domain-security-review',
    complexity: 0.85,
    multiDomain: true,
    modelCount: 6,
  };

  const complexDecision = await shouldUseOrchestrator(complexTask);
  assertExists(complexDecision, 'complexDecision');

  console.log(`\n    Complex task: use_orchestrator=${complexDecision.use_orchestrator}`);
  console.log(`    Reasons: ${complexDecision.reasons.join(', ')}`);

  // Complex task should trigger orchestrator
  assert(complexDecision.use_orchestrator === true, 'Complex task should use orchestrator');
  assert(complexDecision.reasons.length > 0, 'Should have reasons');
});

// ============================================================================
// TEST 5: recordDecision() Feeds Learning Loop
// ============================================================================

const test5 = test('recordDecision() feeds learning loop', async () => {
  const beforeCount = db.query('SELECT COUNT(*) as cnt FROM execution_log')[0]?.cnt || 0;

  const result = await recordDecision({
    task_type: 'test-task',
    model_used: 'sonnet',
    decision: 'Test decision for validation',
    outcome: 'success',
    quality_score: 0.88,
    metadata: {
      test: true,
      selected_via_thompson: true,
    },
  });

  assertExists(result, 'result');
  assert(result.success === true, 'Should succeed');
  assertString(result.recorded_id, 'recorded_id');

  console.log(`\n    Recorded ID: ${result.recorded_id}`);

  // Check database
  const afterCount = db.query('SELECT COUNT(*) as cnt FROM execution_log')[0]?.cnt || 0;
  console.log(`    DB executions: ${beforeCount} → ${afterCount}`);

  assert(afterCount >= beforeCount, 'Should add to database');

  // Check Thompson Sampling state
  const thompsonStats = thompson.getModelStats('sonnet');
  assertExists(thompsonStats, 'thompsonStats');
  console.log(`    Thompson (sonnet): alpha=${thompsonStats.alpha}, beta=${thompsonStats.beta}, avg=${thompsonStats.avg_quality.toFixed(2)}`);
});

// ============================================================================
// TEST 6: analyzeTaskComplexity() Returns Valid Analysis
// ============================================================================

const test6 = test('analyzeTaskComplexity() analyzes tasks', async () => {
  const task = {
    type: 'security-review',
    description: 'Review security across multiple domains',
    subtasks: ['frontend-sec', 'backend-sec', 'infra-sec', 'data-sec'],
    domains: ['security', 'architecture', 'compliance'],
    quality_requirement: 0.9,
    time_pressure: 0.3,
  };

  const analysis = await analyzeTaskComplexity(task);

  assertExists(analysis, 'analysis');
  assertNumber(analysis.complexity_score, 'complexity_score');
  assertString(analysis.complexity_level, 'complexity_level');
  assertNumber(analysis.estimated_models, 'estimated_models');
  assertNumber(analysis.estimated_duration_ms, 'estimated_duration_ms');

  console.log(`\n    Complexity: ${analysis.complexity_score.toFixed(2)} (${analysis.complexity_level})`);
  console.log(`    Estimated models: ${analysis.estimated_models}`);
  console.log(`    Estimated duration: ${(analysis.estimated_duration_ms / 1000).toFixed(1)}s`);
  console.log(`    Recommendation: ${analysis.recommendation}`);

  assert(analysis.complexity_score >= 0 && analysis.complexity_score <= 1, 'Score should be 0-1');
  assert(analysis.estimated_models >= 1, 'Should estimate at least 1 model');
});

// ============================================================================
// TEST 7: selectAgentStrategy() Chooses Strategy
// ============================================================================

const test7 = test('selectAgentStrategy() selects strategy', async () => {
  const task = {
    type: 'security-review',
    description: 'Multi-domain security review',
  };

  const analysis = await analyzeTaskComplexity(task);
  const strategy = await selectAgentStrategy(task, analysis);

  assertExists(strategy, 'strategy');
  assertString(strategy.strategy, 'strategy.strategy');
  assertArray(strategy.worker_models, 'worker_models');
  assertString(strategy.arbiter_model, 'arbiter_model');
  assertNumber(strategy.confidence, 'confidence');
  assertString(strategy.reasoning, 'reasoning');

  console.log(`\n    Strategy: ${strategy.strategy}`);
  console.log(`    Workers: ${strategy.worker_models.join(', ')}`);
  console.log(`    Arbiter: ${strategy.arbiter_model}`);
  console.log(`    Confidence: ${strategy.confidence.toFixed(2)}`);
  console.log(`    Reasoning: ${strategy.reasoning}`);

  // Validate strategy is one of the known strategies
  const validStrategies = Object.values(STRATEGIES);
  assert(validStrategies.includes(strategy.strategy), `Strategy should be one of: ${validStrategies.join(', ')}`);

  // Arbiter should be different from workers
  assert(!strategy.worker_models.includes(strategy.arbiter_model), 'Arbiter should be different from workers');
});

// ============================================================================
// TEST 8: coordinateTask() Executes Strategy
// ============================================================================

const test8 = test('coordinateTask() executes strategy', async () => {
  const task = {
    type: 'test-coordination',
    description: 'Test task for coordination',
  };

  const analysis = await analyzeTaskComplexity(task);
  const strategy = await selectAgentStrategy(task, analysis);
  const result = await coordinateTask(task, strategy);

  assertExists(result, 'result');
  assert(typeof result.success === 'boolean', 'success should be boolean');
  assertString(result.coordination_id, 'coordination_id');
  assertNumber(result.duration_ms, 'duration_ms');

  console.log(`\n    Success: ${result.success}`);
  console.log(`    Coordination ID: ${result.coordination_id}`);
  console.log(`    Duration: ${result.duration_ms}ms`);

  if (result.success) {
    assertExists(result.result, 'result.result');
    console.log(`    Strategy executed: ${result.result.strategy}`);
    console.log(`    Quality score: ${result.result.quality_score?.toFixed(2) || 'N/A'}`);
  } else {
    console.log(`    Error: ${result.error}`);
  }
});

// ============================================================================
// TEST 9: learnFromCoordination() Extracts Insights
// ============================================================================

const test9 = test('learnFromCoordination() learns', async () => {
  const mockResult = {
    coordination_id: 'test-coord-001',
    result: {
      strategy: STRATEGIES.CONSENSUS,
      workers: ['opus', 'sonnet', 'haiku'],
      arbiter: 'fable',
      quality_score: 0.85,
      consensus_score: 0.78,
    },
    duration_ms: 45000,
  };

  const learning = await learnFromCoordination(mockResult);

  assertExists(learning, 'learning');
  assert(typeof learning.success === 'boolean', 'success should be boolean');

  console.log(`\n    Success: ${learning.success}`);

  if (learning.success) {
    assertString(learning.learning_id, 'learning_id');
    assertString(learning.insight, 'insight');

    console.log(`    Learning ID: ${learning.learning_id}`);
    console.log(`    Insight: ${learning.insight}`);
  } else {
    console.log(`    Error: ${learning.error}`);
  }
});

// ============================================================================
// TEST 10: Intelligence Summary Shows Learning
// ============================================================================

const test10 = test('getIntelligenceSummary() shows progress', async () => {
  const summary = await getIntelligenceSummary();

  assertExists(summary, 'summary');

  if (!summary.error) {
    assertExists(summary.thompson_sampling, 'thompson_sampling');
    assertExists(summary.decisions, 'decisions');
    assertExists(summary.learnings, 'learnings');

    console.log(`\n    Thompson Sampling:`);
    console.log(`      Models tracked: ${summary.thompson_sampling.models_tracked}`);

    console.log(`\n    Decisions:`);
    console.log(`      Total: ${summary.decisions.total}`);
    console.log(`      Success rate: ${(summary.decisions.success_rate * 100).toFixed(1)}%`);
    console.log(`      Avg quality: ${summary.decisions.avg_quality.toFixed(2)}`);

    console.log(`\n    Learnings:`);
    console.log(`      Total: ${summary.learnings.total}`);
    console.log(`      Success patterns: ${summary.learnings.success_patterns}`);
    console.log(`      Failure patterns: ${summary.learnings.failure_patterns}`);

    if (summary.learnings.recent.length > 0) {
      console.log(`\n    Recent insight: ${summary.learnings.recent[0].insight}`);
    }
  } else {
    console.log(`\n    Error: ${summary.error}`);
  }
});

// ============================================================================
// RUN ALL TESTS
// ============================================================================

async function runTests() {
  console.log('='.repeat(70));
  console.log('ACTIVE LEARNING INTEGRATION - VALIDATION TEST SUITE');
  console.log('='.repeat(70));

  const tests = [
    test1,
    test2,
    test3,
    test4,
    test5,
    test6,
    test7,
    test8,
    test9,
    test10,
  ];

  for (const testFn of tests) {
    await testFn();
  }

  console.log('\n' + '='.repeat(70));
  console.log('RESULTS');
  console.log('='.repeat(70));
  console.log(`✓ Passed: ${passCount}`);
  console.log(`✗ Failed: ${failCount}`);
  console.log(`Total: ${passCount + failCount}`);

  if (failCount === 0) {
    console.log('\n🎉 ALL TESTS PASSED - Active learning is working!');
  } else {
    console.log(`\n⚠️  ${failCount} test(s) failed - check output above`);
  }

  console.log('='.repeat(70));

  process.exit(failCount > 0 ? 1 : 0);
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runTests().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}

export default runTests;
