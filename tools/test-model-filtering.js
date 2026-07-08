#!/usr/bin/env node
/**
 * Test Model Filtering Rules
 *
 * Verifies that:
 * 1. Red Hat tasks ONLY use Anthropic models
 * 2. Task-specific rules are applied correctly
 * 3. Whitelist/blacklist filtering works
 */

import { applyRules, getRulesForTask, requiresAnthropicOnly } from '../shared/task-model-rules.cjs';
import { isAnthropicModel, filterAnthropicOnly } from '../shared/anthropic-models.cjs';

// Mock model pool (mix of Anthropic and third-party)
const ALL_MODELS = [
  'claude-opus-4.8',
  'claude-sonnet-4.5',
  'claude-haiku-4.5',
  'claude-fable-5',
  'gpt-4o',
  'gpt-4o-mini',
  'gemini-pro',
  'gemini-flash',
  'deepseek-coder',
  'qwen-coder',
];

console.log('========================================');
console.log('MODEL FILTERING TEST SUITE');
console.log('========================================\n');

// ============================================================
// TEST 1: Red Hat Code Review (MUST be Anthropic only)
// ============================================================
console.log('TEST 1: Red Hat Code Review');
console.log('─────────────────────────────');

const redhatTaskType = 'redhat_code_review';
const redhatFiltered = applyRules(ALL_MODELS, redhatTaskType);
const redhatRules = getRulesForTask(redhatTaskType);

console.log(`Task: ${redhatTaskType}`);
console.log(`Anthropic-only: ${redhatRules.anthropic_only}`);
console.log(`Whitelist: ${redhatRules.whitelist?.join(', ') || 'none'}`);
console.log(`Blacklist: ${redhatRules.blacklist?.join(', ') || 'none'}`);
console.log(`Reason: ${redhatRules.reason}`);
console.log(`\nAll models (${ALL_MODELS.length}): ${ALL_MODELS.join(', ')}`);
console.log(`Filtered (${redhatFiltered.length}): ${redhatFiltered.join(', ')}`);

// Verify ONLY Anthropic models
const allAnthropicOnly = redhatFiltered.every(isAnthropicModel);
const hasOpusOrSonnet = redhatFiltered.some(m => m.includes('opus') || m.includes('sonnet'));
const noHaikuOrFable = !redhatFiltered.some(m => m.includes('haiku') || m.includes('fable'));

console.log(`\n✓ All Anthropic? ${allAnthropicOnly ? 'YES ✓' : 'NO ✗'}`);
console.log(`✓ Has Opus/Sonnet? ${hasOpusOrSonnet ? 'YES ✓' : 'NO ✗'}`);
console.log(`✓ No Haiku/Fable? ${noHaikuOrFable ? 'YES ✓' : 'NO ✗'}`);

const test1Pass = allAnthropicOnly && hasOpusOrSonnet && noHaikuOrFable;
console.log(`\n>>> TEST 1: ${test1Pass ? 'PASS ✓' : 'FAIL ✗'}\n`);

// ============================================================
// TEST 2: General Code Review (Allow coding specialists)
// ============================================================
console.log('TEST 2: General Code Review');
console.log('─────────────────────────────');

const codeReviewTaskType = 'code_review';
const codeReviewFiltered = applyRules(ALL_MODELS, codeReviewTaskType);
const codeReviewRules = getRulesForTask(codeReviewTaskType);

console.log(`Task: ${codeReviewTaskType}`);
console.log(`Anthropic-only: ${codeReviewRules.anthropic_only || false}`);
console.log(`Whitelist: ${codeReviewRules.whitelist?.join(', ') || 'none'}`);
console.log(`Blacklist: ${codeReviewRules.blacklist?.join(', ') || 'none'}`);
console.log(`Reason: ${codeReviewRules.reason}`);
console.log(`\nFiltered (${codeReviewFiltered.length}): ${codeReviewFiltered.join(', ')}`);

// Verify includes Anthropic + coding specialists, excludes small models
const hasCodingSpecialists = codeReviewFiltered.some(m => m.includes('deepseek') || m.includes('qwen'));
const noSmallModels = !codeReviewFiltered.some(m => m.includes('haiku') || m.includes('fable') || m.includes('gpt-3.5'));

console.log(`\n✓ Has coding specialists? ${hasCodingSpecialists ? 'YES ✓' : 'NO ✗'}`);
console.log(`✓ No small models? ${noSmallModels ? 'YES ✓' : 'NO ✗'}`);

const test2Pass = hasCodingSpecialists && noSmallModels;
console.log(`\n>>> TEST 2: ${test2Pass ? 'PASS ✓' : 'FAIL ✗'}\n`);

// ============================================================
// TEST 3: Documentation (Cheap models OK, no Opus)
// ============================================================
console.log('TEST 3: Documentation');
console.log('─────────────────────────────');

const docsTaskType = 'documentation';
const docsFiltered = applyRules(ALL_MODELS, docsTaskType);
const docsRules = getRulesForTask(docsTaskType);

console.log(`Task: ${docsTaskType}`);
console.log(`Blacklist: ${docsRules.blacklist?.join(', ') || 'none'}`);
console.log(`Reason: ${docsRules.reason}`);
console.log(`\nFiltered (${docsFiltered.length}): ${docsFiltered.join(', ')}`);

// Verify no Opus (too expensive)
const noOpus = !docsFiltered.some(m => m.includes('opus'));

console.log(`\n✓ No Opus? ${noOpus ? 'YES ✓' : 'NO ✗'}`);

const test3Pass = noOpus;
console.log(`\n>>> TEST 3: ${test3Pass ? 'PASS ✓' : 'FAIL ✗'}\n`);

// ============================================================
// TEST 4: Anthropic Model Detection
// ============================================================
console.log('TEST 4: Anthropic Model Detection');
console.log('─────────────────────────────');

const anthropicTests = [
  { model: 'claude-opus-4.8', expected: true },
  { model: 'claude-sonnet-4.5', expected: true },
  { model: 'opus', expected: true },
  { model: 'sonnet', expected: true },
  { model: 'gpt-4o', expected: false },
  { model: 'deepseek-coder', expected: false },
];

let anthropicTestPass = true;
for (const { model, expected } of anthropicTests) {
  const actual = isAnthropicModel(model);
  const pass = actual === expected;
  console.log(`${model}: ${actual ? 'Anthropic' : 'Third-party'} ${pass ? '✓' : '✗'}`);
  if (!pass) anthropicTestPass = false;
}

console.log(`\n>>> TEST 4: ${anthropicTestPass ? 'PASS ✓' : 'FAIL ✗'}\n`);

// ============================================================
// SUMMARY
// ============================================================
console.log('========================================');
console.log('TEST SUMMARY');
console.log('========================================');

const allPass = test1Pass && test2Pass && test3Pass && anthropicTestPass;

console.log(`Test 1 (Red Hat compliance): ${test1Pass ? 'PASS ✓' : 'FAIL ✗'}`);
console.log(`Test 2 (General code review): ${test2Pass ? 'PASS ✓' : 'FAIL ✗'}`);
console.log(`Test 3 (Documentation): ${test3Pass ? 'PASS ✓' : 'FAIL ✗'}`);
console.log(`Test 4 (Anthropic detection): ${anthropicTestPass ? 'PASS ✓' : 'FAIL ✗'}`);
console.log(`\nOVERALL: ${allPass ? 'ALL TESTS PASS ✓' : 'SOME TESTS FAILED ✗'}`);

process.exit(allPass ? 0 : 1);
