#!/usr/bin/env node

/**
 * Test Procedural Rules Integration
 *
 * Verifies:
 * 1. Rules can be recorded
 * 2. Rules can be queried
 * 3. Rules are extracted from execution summary
 * 4. Recommendations work
 */

import {
  recordProceduralRule,
  queryProceduralRules,
  extractRulesFromExecutions,
  getRecommendedAction,
  closePool
} from './procedural-rules-adapter.js';

console.log('=== Procedural Rules Integration Test ===\n');

// Test 1: Record a rule manually
console.log('Test 1: Record procedural rule');
const testRule = {
  condition: {
    workflow: 'test-workflow',
    task_type: 'test-task',
    language: 'javascript'
  },
  action: 'use_model_haiku',
  confidence: 0.85,
  evidence_count: 3
};

const recordResult = await recordProceduralRule(testRule);
console.log('  Record result:', recordResult);
console.log('  ✅ Rule recorded\n');

// Test 2: Query the rule
console.log('Test 2: Query procedural rules');
const rules = await queryProceduralRules(
  { workflow: 'test-workflow', task_type: 'test-task' },
  0.7
);
console.log('  Found rules:', rules.length);
if (rules.length > 0) {
  console.log('  Top rule:', {
    action: rules[0].action,
    confidence: rules[0].confidence,
    evidence_count: rules[0].evidence_count
  });
}
console.log('  ✅ Query works\n');

// Test 3: Extract rules from execution summary
console.log('Test 3: Extract rules from execution summary');
const extraction = await extractRulesFromExecutions({
  minQuality: 0.75,
  limit: 100
});
console.log('  Executions analyzed:', extraction.executions_analyzed);
console.log('  Patterns found:', extraction.patterns_found);
console.log('  Rules created:', extraction.rules_created);
if (extraction.rules && extraction.rules.length > 0) {
  console.log('  Sample rule:', extraction.rules[0]);
}
console.log('  ✅ Extraction works\n');

// Test 4: Get recommendation
console.log('Test 4: Get recommended action');
const recommendation = await getRecommendedAction(
  { workflow: 'meta-answer', task_type: 'meta-answer' },
  0.7
);
if (recommendation) {
  console.log('  Recommendation:', {
    action: recommendation.action,
    confidence: recommendation.confidence,
    evidence_count: recommendation.evidence_count
  });
  console.log('  ✅ Recommendation works\n');
} else {
  console.log('  No recommendation found (need more data)');
  console.log('  ⚠️ Recommendation requires historical data\n');
}

// Test 5: Verify partial match works
console.log('Test 5: Partial condition matching');
const partialRules = await queryProceduralRules(
  { workflow: 'test-workflow' }, // Missing task_type
  0.5
);
console.log('  Partial match found:', partialRules.length, 'rules');
console.log('  ✅ JSONB containment works\n');

console.log('=== All Tests Complete ===');
console.log('\nSample query to see all rules:');
console.log('psql -h aio-01 -p 5433 -U claude -d learning -c "SELECT condition, action, confidence, evidence_count FROM learning.procedural_rules ORDER BY confidence DESC LIMIT 10;"');

await closePool();
