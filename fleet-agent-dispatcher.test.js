/**
 * Test harness for fleet-agent-dispatcher
 *
 * Validates job type detection, resource estimation, and error handling
 * Run with: node fleet-agent-dispatcher.test.js
 */

import { detectJobType, estimateResources, analyzeWorkflow } from './fleet-agent-dispatcher.js';

// Test runner
let passed = 0;
let failed = 0;

function assertEquals(actual, expected, testName) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) {
    console.log(`  ✅ ${testName}`);
    passed++;
  } else {
    console.log(`  ❌ ${testName}`);
    console.log(`     Expected: ${JSON.stringify(expected)}`);
    console.log(`     Got:      ${JSON.stringify(actual)}`);
    failed++;
  }
}

function assertRange(actual, min, max, testName) {
  if (actual >= min && actual <= max) {
    console.log(`  ✅ ${testName} (${actual})`);
    passed++;
  } else {
    console.log(`  ❌ ${testName}`);
    console.log(`     Expected range: ${min}-${max}`);
    console.log(`     Got: ${actual}`);
    failed++;
  }
}

// ============================================================================
// TEST SUITE 1: Job Type Detection (8 tests)
// ============================================================================

console.log('\n=== Job Type Detection ===\n');

// Test 1.1: ai-consensus detection (keyword: worker)
assertEquals(
  detectJobType('opus-weighted-worker', 'Return your perspective'),
  'ai-consensus',
  'Detects ai-consensus from "worker" keyword'
);

// Test 1.2: ai-consensus detection (keyword: consensus)
assertEquals(
  detectJobType('consensus-arbiter', 'Synthesize 3 perspectives'),
  'ai-consensus',
  'Detects ai-consensus from "consensus" keyword'
);

// Test 1.3: code-review detection (keyword: review)
assertEquals(
  detectJobType('code-review', 'Analyze code quality'),
  'code-review',
  'Detects code-review from "review" keyword'
);

// Test 1.4: code-review detection (prompt content)
assertEquals(
  detectJobType('Static Analysis', 'Code analysis of the function...'),
  'code-review',
  'Detects code-review from "code analysis" prompt'
);

// Test 1.5: code-execute detection
assertEquals(
  detectJobType('Run Tests', 'Execute: npm test && echo done'),
  'code-execute',
  'Detects code-execute from "npm test" in prompt'
);

// Test 1.6: data-extraction detection
assertEquals(
  detectJobType('Extract Issues', 'Fetch and parse the JSON response'),
  'data-extraction',
  'Detects data-extraction from extraction keywords'
);

// Test 1.7: ai-heavy detection
assertEquals(
  detectJobType('Generate Docs', 'Synthesize all findings into a report'),
  'ai-heavy',
  'Detects ai-heavy from generation keywords'
);

// Test 1.8: default fallback
assertEquals(
  detectJobType('Unknown Label', 'Do something generic'),
  'agent',
  'Falls back to "agent" for unknown patterns'
);

// ============================================================================
// TEST SUITE 2: Resource Estimation (12 tests)
// ============================================================================

console.log('\n=== Resource Estimation ===\n');

// Test 2.1: Minimal prompt (short, simple)
const est1 = estimateResources('Hi', 'sonnet', null, 'agent');
assertRange(est1.duration, 20, 40, 'Short prompt duration (20-40s)');
assertRange(est1.ram, 0.8, 1.2, 'Short prompt RAM (0.8-1.2GB)');

// Test 2.2: Medium prompt
const est2 = estimateResources('x'.repeat(1500), 'sonnet', null, 'agent');
assertRange(est2.duration, 35, 55, 'Medium prompt duration (35-55s)');
assertRange(est2.ram, 1.2, 1.5, 'Medium prompt RAM (1.2-1.5GB)');

// Test 2.3: Large prompt
const est3 = estimateResources('x'.repeat(5000), 'sonnet', null, 'agent');
assertRange(est3.duration, 50, 70, 'Large prompt duration (50-70s)');
assertRange(est3.ram, 1.4, 1.8, 'Large prompt RAM (1.4-1.8GB)');

// Test 2.4: Opus model (heavy)
const est4 = estimateResources('test', 'opus', null, 'agent');
assertRange(est4.duration, 35, 55, 'Opus duration (35-55s, +15s from model)');
assertRange(est4.ram, 1.3, 1.7, 'Opus RAM (1.3-1.7GB, +0.5GB from model)');

// Test 2.5: Haiku model (light)
const est5 = estimateResources('test', 'haiku', null, 'agent');
assertRange(est5.duration, 10, 30, 'Haiku duration (10-30s, -10s from model)');
assertRange(est5.ram, 0.5, 0.9, 'Haiku RAM (0.5-0.9GB, -0.3GB from model)');

// Test 2.5a: Sonnet model (baseline)
const est5a = estimateResources('test', 'sonnet', null, 'agent');
assertRange(est5a.duration, 25, 40, 'Sonnet duration (baseline)');
assertRange(est5a.ram, 0.9, 1.2, 'Sonnet RAM (baseline)');

// Test 2.5b: Fable model (baseline, no specific adjustment)
const est5b = estimateResources('test', 'fable', null, 'agent');
assertRange(est5b.duration, 25, 40, 'Fable duration (baseline, no model adjustment)');
assertRange(est5b.ram, 0.9, 1.2, 'Fable RAM (baseline, no model adjustment)');

// Test 2.5c: GPT-4o model (heavy, similar to opus)
const est5c = estimateResources('test', 'gpt-4o', null, 'agent');
assertRange(est5c.duration, 35, 55, 'GPT-4o duration (+15s from gpt-4 pattern)');
assertRange(est5c.ram, 1.3, 1.7, 'GPT-4o RAM (+0.5GB from gpt-4 pattern)');

// Test 2.5d: Gemini model (medium adjustment)
const est5d = estimateResources('test', 'gemini', null, 'agent');
assertRange(est5d.duration, 30, 45, 'Gemini duration (+5s from gemini pattern)');
assertRange(est5d.ram, 1.1, 1.4, 'Gemini RAM (+0.2GB from gemini pattern)');

// Test 2.6: Schema with 5 properties
const schema6 = { properties: { a: {}, b: {}, c: {}, d: {}, e: {} } };
const est6 = estimateResources('test', 'sonnet', schema6, 'agent');
assertRange(est6.duration, 30, 50, 'Small schema duration (+5s)');
assertRange(est6.ram, 1.1, 1.4, 'Small schema RAM (+0.2GB)');

// Test 2.7: Schema with 15 properties
const schema7 = { properties: Object.fromEntries(Array(15).fill(0).map((_, i) => [String.fromCharCode(97 + i), {}])) };
const est7 = estimateResources('test', 'sonnet', schema7, 'agent');
assertRange(est7.duration, 30, 50, 'Medium schema duration (+10s)');
assertRange(est7.ram, 1.2, 1.5, 'Medium schema RAM (+0.3GB)');

// Test 2.8: code-execute job type (+20s, +0.5GB)
const est8 = estimateResources('test', 'sonnet', null, 'code-execute');
assertRange(est8.duration, 40, 60, 'code-execute duration (+20s)');
assertRange(est8.ram, 1.3, 1.7, 'code-execute RAM (+0.5GB)');

// Test 2.9: data-extraction job type (-10s, -0.3GB)
const est9 = estimateResources('test', 'sonnet', null, 'data-extraction');
assertRange(est9.duration, 10, 30, 'data-extraction duration (-10s)');
assertRange(est9.ram, 0.5, 1.0, 'data-extraction RAM (-0.3GB)');

// Test 2.10: ai-heavy job type (+15s, +0.3GB)
const est10 = estimateResources('test', 'sonnet', null, 'ai-heavy');
assertRange(est10.duration, 35, 55, 'ai-heavy duration (+15s)');
assertRange(est10.ram, 1.1, 1.4, 'ai-heavy RAM (+0.3GB)');

// Test 2.11: Explicit duration/ram overrides
const est11 = estimateResources('x'.repeat(5000), 'opus', null, 'code-execute', 120, 2.5);
assertEquals(est11.duration, 120, 'Explicit duration override');
assertEquals(est11.ram, 2.5, 'Explicit RAM override');

// Test 2.12: Minimum values enforced
const est12 = estimateResources('', 'haiku', null, 'data-extraction');
assertRange(est12.duration, 10, 20, 'Duration minimum enforced (>=10s)');
assertRange(est12.ram, 0.5, 0.8, 'RAM minimum enforced (>=0.5GB)');

// ============================================================================
// TEST SUITE 3: Workflow Analysis (5 tests)
// ============================================================================

console.log('\n=== Workflow Analysis ===\n');

// Test 3.1: Simple workflow with 2 agent calls
const code1 = `
const r1 = await agent('prompt1');
const r2 = await agent('prompt2', {model: 'opus'});
`;
const analysis1 = analyzeWorkflow(code1);
assertEquals(analysis1.totalCalls, 2, 'Counts 2 agent() calls');
assertEquals(analysis1.modelOverride, 1, 'Detects 1 model override');

// Test 3.2: Workflow with schema
const code2 = `
const result = await agent('fetch data', {
  schema: {type: 'object', properties: {id: {}}}
});
`;
const analysis2 = analyzeWorkflow(code2);
assertEquals(analysis2.schemaUsage, 1, 'Detects schema usage');

// Test 3.3: Workflow with parallel
const code3 = `
await parallel([
  () => agent('a', {model: 'opus'}),
  () => agent('b', {model: 'sonnet'})
]);
`;
const analysis3 = analyzeWorkflow(code3);
assertEquals(analysis3.usesParallel, true, 'Detects parallel() usage');

// Test 3.4: Workflow with pipeline
const code4 = `
await pipeline(items, item =>
  agent(\`Process \${item}\`, {label: \`Item \${item}\`})
);
`;
const analysis4 = analyzeWorkflow(code4);
assertEquals(analysis4.usesPipeline, true, 'Detects pipeline() usage');
assertEquals(analysis4.labelUsage, 1, 'Detects label usage');

// Test 3.5: Complex workflow
const code5 = `
export const meta = {...};
const check = await agent('Check', {model: 'haiku', schema: S, label: 'L1'});
const results = await parallel(
  models.map(m => () => agent('Work', {model: m}))
);
const final = await agent('Summary', {schema: S2});
`;
const analysis5 = analyzeWorkflow(code5);
assertEquals(analysis5.totalCalls, 4, 'Counts all agent() calls correctly');
assertEquals(analysis5.usesParallel, true, 'Detects parallel in complex code');
assertEquals(analysis5.schemaUsage, 2, 'Counts 2 schema uses');

// ============================================================================
// SUMMARY
// ============================================================================

console.log('\n' + '='.repeat(60));
console.log(`Tests passed: ${passed}`);
console.log(`Tests failed: ${failed}`);
console.log(`Total tests:  ${passed + failed}`);
console.log('='.repeat(60) + '\n');

if (failed > 0) {
  process.exit(1);
}
