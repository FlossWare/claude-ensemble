#!/usr/bin/env node
/**
 * Pattern Integration Validation Test
 *
 * Quick smoke test to verify consensus pattern deployment.
 *
 * Usage:
 *   node shared/test-pattern-integration.cjs
 *
 * Created: 2026-07-03
 */

const { getConsensusPatterns } = require('./consensus-pattern-adapter.cjs');

async function runTests() {
  console.log('Pattern Integration Validation\n');
  console.log('=================================\n');

  const db = getConsensusPatterns();
  let passed = 0;
  let failed = 0;

  // Test 1: Database connection
  try {
    const stats = await db.getStats();
    console.log('✓ Test 1: Database connection OK');
    console.log(`  - Total patterns: ${stats.total_patterns}`);
    console.log(`  - Average confidence: ${stats.avg_confidence}`);
    passed++;
  } catch (err) {
    console.log('✗ Test 1: Database connection FAILED');
    console.log(`  Error: ${err.message}`);
    failed++;
    return; // Can't continue without DB
  }

  // Test 2: Category retrieval
  try {
    const pattern = await db.getPatternByCategory('debugging', 0.7);
    if (pattern) {
      console.log('\n✓ Test 2: Category retrieval OK');
      console.log(`  - Found debugging pattern: ${pattern.problem_description.substring(0, 50)}...`);
      console.log(`  - Confidence: ${pattern.pattern_confidence}`);
      console.log(`  - Models used: ${pattern.models_used}`);
      passed++;
    } else {
      console.log('\n✗ Test 2: Category retrieval FAILED (no pattern found)');
      failed++;
    }
  } catch (err) {
    console.log('\n✗ Test 2: Category retrieval FAILED');
    console.log(`  Error: ${err.message}`);
    failed++;
  }

  // Test 3: Auto-detection
  try {
    const categories = db.detectCategories('Debug why the application crashes with OOM error');
    if (categories.length > 0) {
      console.log('\n✓ Test 3: Auto-detection OK');
      console.log(`  - Detected categories: ${categories.join(', ')}`);
      passed++;
    } else {
      console.log('\n✗ Test 3: Auto-detection FAILED (no categories detected)');
      failed++;
    }
  } catch (err) {
    console.log('\n✗ Test 3: Auto-detection FAILED');
    console.log(`  Error: ${err.message}`);
    failed++;
  }

  // Test 4: Task augmentation
  try {
    const task = 'Optimize database query performance';
    const augmented = await db.augmentTaskWithPatterns(task, 0.7, 2);
    if (augmented.length > task.length) {
      console.log('\n✓ Test 4: Task augmentation OK');
      console.log(`  - Original length: ${task.length} chars`);
      console.log(`  - Augmented length: ${augmented.length} chars`);
      console.log(`  - Enhancement: +${augmented.length - task.length} chars`);
      passed++;
    } else {
      console.log('\n✗ Test 4: Task augmentation FAILED (no enhancement)');
      console.log(`  - Original length: ${task.length} chars`);
      console.log(`  - Augmented length: ${augmented.length} chars`);
      failed++;
    }
  } catch (err) {
    console.log('\n✗ Test 4: Task augmentation FAILED');
    console.log(`  Error: ${err.message}`);
    failed++;
  }

  // Test 5: Pattern retrieval for task
  try {
    const task = 'Refactor complex nested loops to improve code readability';
    const patterns = await db.getPatternsForTask(task, 0.7, 3);
    console.log('\n✓ Test 5: Pattern retrieval for task OK');
    console.log(`  - Found ${patterns.length} patterns`);
    if (patterns.length > 0) {
      patterns.forEach((p, i) => {
        console.log(`    ${i + 1}. ${p.problem_category} (${Math.round(p.pattern_confidence * 100)}%)`);
      });
    }
    passed++;
  } catch (err) {
    console.log('\n✗ Test 5: Pattern retrieval for task FAILED');
    console.log(`  Error: ${err.message}`);
    failed++;
  }

  // Test 6: Top patterns
  try {
    const topPatterns = await db.getTopPatterns(5, 0.8);
    console.log('\n✓ Test 6: Top patterns retrieval OK');
    console.log(`  - Found ${topPatterns.length} high-confidence patterns (≥80%)`);
    topPatterns.forEach((p, i) => {
      console.log(`    ${i + 1}. ${p.problem_category}: ${Math.round(p.pattern_confidence * 100)}%`);
    });
    passed++;
  } catch (err) {
    console.log('\n✗ Test 6: Top patterns retrieval FAILED');
    console.log(`  Error: ${err.message}`);
    failed++;
  }

  // Test 7: Pattern formatting
  try {
    const pattern = await db.getPatternByCategory('optimization', 0.7);
    if (pattern) {
      const formatted = db.formatPatternContext(pattern);
      if (formatted.includes('Proven Approach') && formatted.includes('Reasoning Steps')) {
        console.log('\n✓ Test 7: Pattern formatting OK');
        console.log(`  - Formatted length: ${formatted.length} chars`);
        console.log(`  - Contains sections: Proven Approach, Reasoning Steps, Avoid Errors`);
        passed++;
      } else {
        console.log('\n✗ Test 7: Pattern formatting FAILED (missing sections)');
        failed++;
      }
    } else {
      console.log('\n✗ Test 7: Pattern formatting FAILED (no pattern found)');
      failed++;
    }
  } catch (err) {
    console.log('\n✗ Test 7: Pattern formatting FAILED');
    console.log(`  Error: ${err.message}`);
    failed++;
  }

  // Test 8: Category list
  try {
    const categories = await db.getCategories();
    console.log('\n✓ Test 8: Category list retrieval OK');
    console.log(`  - Available categories: ${categories.length}`);
    console.log(`  - Sample: ${categories.slice(0, 5).join(', ')}...`);
    passed++;
  } catch (err) {
    console.log('\n✗ Test 8: Category list retrieval FAILED');
    console.log(`  Error: ${err.message}`);
    failed++;
  }

  // Summary
  console.log('\n=================================');
  console.log('Test Results\n');
  console.log(`Passed: ${passed}/8`);
  console.log(`Failed: ${failed}/8`);
  console.log('=================================\n');

  if (failed === 0) {
    console.log('✓ All tests passed! Pattern integration is ready.\n');
    process.exit(0);
  } else {
    console.log('✗ Some tests failed. Check errors above.\n');
    process.exit(1);
  }
}

// Run tests
runTests().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
