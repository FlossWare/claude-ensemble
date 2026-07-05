#!/usr/bin/env node
/**
 * Test Access Pattern Analyzer Integration
 *
 * Demonstrates how to use the access pattern analyzer in workflows
 */

import {
  isAnalyzerAvailable,
  predictBestModel,
  getResourceEstimate,
  getFailureRisk,
  recommendModel,
  getAnalyzerStats
} from '../shared/access-pattern-adapter.cjs';

async function main() {
  console.log('='.repeat(80));
  console.log('ACCESS PATTERN ANALYZER - Integration Test');
  console.log('='.repeat(80));

  // Check if analyzer is available
  console.log('\n1. Checking analyzer availability...');
  const available = isAnalyzerAvailable();
  console.log(`   Analyzer available: ${available ? '✓ Yes' : '✗ No'}`);

  if (!available) {
    console.log('\n   Run: python3 tools/access_pattern_analyzer_trainer.py');
    process.exit(1);
  }

  // Get statistics
  console.log('\n2. Getting analyzer statistics...');
  const stats = await getAnalyzerStats();
  console.log('   Statistics:');
  for (const [key, value] of Object.entries(stats)) {
    console.log(`     ${key}: ${value}`);
  }

  // Test predictions with various tasks
  console.log('\n3. Testing predictions...\n');

  const testTasks = [
    "FIX Issue #456: Memory leak in worker pool",
    "Implement JWT authentication for API",
    "REVIEW: Database migration schema changes",
    "Write comprehensive unit tests for auth module",
    "Debug segmentation fault in C++ service"
  ];

  for (const task of testTasks) {
    console.log(`\nTask: "${task}"`);
    console.log('-'.repeat(80));

    // Get top 3 recommendations
    const predictions = await predictBestModel(task, 3);

    if (predictions.length === 0) {
      console.log('  No predictions available');
      continue;
    }

    console.log(`  Top ${predictions.length} models:`);
    for (let i = 0; i < predictions.length; i++) {
      const p = predictions[i];
      console.log(`    ${i + 1}. ${p.model}`);
      console.log(`       Score: ${p.score.toFixed(3)}, ` +
                  `Duration: ${p.duration_ms.toFixed(0)}ms, ` +
                  `Cost: $${p.cost_usd.toFixed(4)}, ` +
                  `Risk: ${(p.risk * 100).toFixed(1)}%`);
    }
  }

  // Test quick recommendation
  console.log('\n4. Testing quick recommendation...\n');
  const quickTask = "Optimize database query performance";
  console.log(`Task: "${quickTask}"`);
  const recommendation = await recommendModel(quickTask);

  if (recommendation) {
    console.log(`  Recommended: ${recommendation.model}`);
    console.log(`  Score: ${recommendation.score.toFixed(3)}`);
    console.log(`  Expected: ${recommendation.duration_ms.toFixed(0)}ms, ` +
                `$${recommendation.cost_usd.toFixed(4)}`);
    console.log(`  Failure risk: ${(recommendation.risk * 100).toFixed(1)}%`);
  } else {
    console.log('  No recommendation available');
  }

  // Test resource estimates
  console.log('\n5. Testing resource estimates for specific models...\n');
  const testModels = ['opus', 'sonnet', 'haiku', 'gpt-4o'];

  for (const model of testModels) {
    const resources = await getResourceEstimate(model, "Implement new API endpoint");
    console.log(`  ${model}:`);
    console.log(`    Duration: ${resources.duration_ms}ms`);
    console.log(`    Tokens: ~${resources.input_tokens} in, ~${resources.output_tokens} out`);
    console.log(`    Cost: $${resources.cost_usd.toFixed(4)}`);
  }

  // Test failure risk analysis
  console.log('\n6. Testing failure risk analysis...\n');
  const riskTask = "Refactor legacy authentication system";

  console.log(`Task: "${riskTask}"`);
  for (const model of ['opus', 'sonnet', 'haiku']) {
    const risk = await getFailureRisk(model, riskTask);
    console.log(`  ${model}: ${(risk * 100).toFixed(1)}% failure risk`);
  }

  console.log('\n' + '='.repeat(80));
  console.log('✓ All tests complete!');
  console.log('='.repeat(80));
}

main().catch(error => {
  console.error('Error:', error);
  process.exit(1);
});
