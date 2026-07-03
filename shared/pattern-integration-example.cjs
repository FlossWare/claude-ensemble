/**
 * Pattern Integration Example
 *
 * Demonstrates how to integrate consensus-validated reasoning patterns
 * into multi-AI workflows.
 *
 * Usage:
 *   node shared/pattern-integration-example.cjs
 *
 * Created: 2026-07-03
 */

const { getConsensusPatterns } = require('./consensus-pattern-adapter.cjs');
const { enhanceWorkflowWithPatterns, getPatternSuggestions } = require('./pattern-enhanced-workflow.cjs');

// ============================================================================
// Example 1: Direct Pattern Retrieval
// ============================================================================

async function example1_directRetrieval() {
  console.log('\n=== Example 1: Direct Pattern Retrieval ===\n');

  const db = getConsensusPatterns();

  // Get pattern by category
  const debugPattern = await db.getPatternByCategory('debugging', 0.7);
  if (debugPattern) {
    console.log('Debugging Pattern:');
    console.log(`- Confidence: ${debugPattern.pattern_confidence}`);
    console.log(`- Models Used: ${debugPattern.models_used}`);
    console.log(`- Approach: ${debugPattern.successful_approach}`);
    console.log('');
  }

  // Get top patterns
  const topPatterns = await db.getTopPatterns(5, 0.8);
  console.log(`Found ${topPatterns.length} high-confidence patterns (≥80%):`);
  topPatterns.forEach(p => {
    console.log(`- ${p.problem_category}: ${Math.round(p.pattern_confidence * 100)}% (${p.models_used} models)`);
  });
  console.log('');

  // Get statistics
  const stats = await db.getStats();
  console.log('Pattern Database Statistics:');
  console.log(`- Total Patterns: ${stats.total_patterns}`);
  console.log(`- Unique Categories: ${stats.unique_categories}`);
  console.log(`- Average Confidence: ${stats.avg_confidence}`);
  console.log(`- Average Models Used: ${stats.avg_models_used}`);
  console.log('');
}

// ============================================================================
// Example 2: Auto-Detection and Task Augmentation
// ============================================================================

async function example2_taskAugmentation() {
  console.log('\n=== Example 2: Task Augmentation ===\n');

  const db = getConsensusPatterns();

  const taskDescription = `
Debug why the memory leak occurs in the connection pool.
The application crashes after ~1000 requests with OOM error.
  `.trim();

  // Detect categories
  const categories = db.detectCategories(taskDescription);
  console.log('Auto-detected categories:', categories.join(', '));
  console.log('');

  // Get relevant patterns
  const patterns = await db.getPatternsForTask(taskDescription, 0.7, 2);
  console.log(`Found ${patterns.length} relevant patterns:`);
  patterns.forEach(p => {
    console.log(`- ${p.problem_category}: ${Math.round(p.pattern_confidence * 100)}%`);
  });
  console.log('');

  // Augment task
  const augmentedTask = await db.augmentTaskWithPatterns(taskDescription, 0.7, 2);
  console.log('Original Task Length:', taskDescription.length, 'chars');
  console.log('Augmented Task Length:', augmentedTask.length, 'chars');
  console.log('');
  console.log('Augmented Task Preview:');
  console.log(augmentedTask.substring(0, 500) + '...\n');
}

// ============================================================================
// Example 3: Pattern Suggestions (Debugging Helper)
// ============================================================================

async function example3_patternSuggestions() {
  console.log('\n=== Example 3: Pattern Suggestions ===\n');

  const tasks = [
    'Optimize the database query that takes 30 seconds to execute',
    'Design a scalable microservices architecture for the payment system',
    'Refactor this complex nested loop into something more readable'
  ];

  for (const task of tasks) {
    console.log(`Task: "${task}"`);
    const suggestions = await getPatternSuggestions(task, { maxPatterns: 2 });

    if (suggestions.length > 0) {
      console.log(`Suggestions (${suggestions.length} patterns):`);
      suggestions.forEach((s, i) => {
        console.log(`  ${i + 1}. ${s.category} (${Math.round(s.confidence * 100)}%, ${s.models_used} models)`);
        console.log(`     Approach: ${s.approach.substring(0, 100)}...`);
      });
    } else {
      console.log('  No specific patterns found (will use top patterns)\n');
    }
    console.log('');
  }
}

// ============================================================================
// Example 4: Workflow Integration (Simulated)
// ============================================================================

async function example4_workflowIntegration() {
  console.log('\n=== Example 4: Workflow Integration (Simulated) ===\n');

  // Simulate a workflow function
  const myWorkflow = async ({ agent, parallel, patternStats }) => {
    console.log('Workflow started...\n');

    // Simulate agent calls (would normally call actual LLM)
    const mockAgent = async (task) => {
      console.log(`[Agent] Received task (${task.length} chars)`);
      return { output: 'mock result', taskLength: task.length };
    };

    const mockParallel = async (tasks) => {
      console.log(`[Parallel] Processing ${tasks.length} tasks`);
      return tasks.map((t, i) => ({ output: `mock result ${i}`, taskLength: typeof t === 'string' ? t.length : 0 }));
    };

    // Call agent (will be auto-enhanced)
    const result1 = await mockAgent('Debug the memory leak in connection pool');
    console.log(`  Result 1 task length: ${result1.taskLength} chars\n`);

    // Call parallel (will be auto-enhanced)
    const results2 = await mockParallel([
      'Optimize database query performance',
      'Design system architecture',
      'Refactor complex code'
    ]);
    console.log(`  Parallel results: ${results2.length} tasks processed\n`);

    // Access pattern stats
    console.log('Pattern Stats:');
    console.log(`- Patterns Applied: ${patternStats.patternsApplied}`);
    console.log(`- Categories: ${[...new Set(patternStats.categoriesDetected)].join(', ')}`);
    console.log('');

    return { success: true };
  };

  // Enhance workflow with pattern injection
  const enhancedWorkflow = enhanceWorkflowWithPatterns(myWorkflow, {
    enablePatterns: true,
    minConfidence: 0.7,
    maxPatterns: 2
  });

  // Execute enhanced workflow
  const context = {
    agent: async (task) => {
      console.log(`[Agent] Received task (${task.length} chars)`);
      return { output: 'mock result', taskLength: task.length };
    },
    parallel: async (tasks) => {
      console.log(`[Parallel] Processing ${tasks.length} tasks`);
      return tasks.map((t, i) => ({ output: `mock result ${i}`, taskLength: typeof t === 'string' ? t.length : 0 }));
    },
    phase: async (name, fn) => fn(),
    log: console.log
  };

  await enhancedWorkflow(context);
}

// ============================================================================
// Example 5: Pattern Formatting
// ============================================================================

async function example5_patternFormatting() {
  console.log('\n=== Example 5: Pattern Formatting ===\n');

  const db = getConsensusPatterns();

  // Get a sample pattern
  const pattern = await db.getPatternByCategory('optimization', 0.7);

  if (pattern) {
    const formatted = db.formatPatternContext(pattern);
    console.log('Formatted Pattern Context:');
    console.log(formatted);
    console.log('');
  }
}

// ============================================================================
// Example 6: Category Explorer
// ============================================================================

async function example6_categoryExplorer() {
  console.log('\n=== Example 6: Category Explorer ===\n');

  const db = getConsensusPatterns();

  const categories = await db.getCategories();
  console.log(`Available Pattern Categories (${categories.length} total):\n`);

  for (const category of categories) {
    const pattern = await db.getPatternByCategory(category, 0.0); // Get any pattern in category
    if (pattern) {
      console.log(`${category.padEnd(25)} - ${Math.round(pattern.pattern_confidence * 100)}% confidence, ${pattern.models_used} models`);
      console.log(`  "${pattern.successful_approach.substring(0, 80)}..."`);
      console.log('');
    }
  }
}

// ============================================================================
// Main Execution
// ============================================================================

async function main() {
  try {
    console.log('======================================');
    console.log('Consensus Pattern Integration Examples');
    console.log('======================================');

    await example1_directRetrieval();
    await example2_taskAugmentation();
    await example3_patternSuggestions();
    await example4_workflowIntegration();
    await example5_patternFormatting();
    await example6_categoryExplorer();

    console.log('======================================');
    console.log('All examples completed successfully!');
    console.log('======================================\n');

    process.exit(0);
  } catch (error) {
    console.error('Error running examples:', error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main();
}

module.exports = {
  example1_directRetrieval,
  example2_taskAugmentation,
  example3_patternSuggestions,
  example4_workflowIntegration,
  example5_patternFormatting,
  example6_categoryExplorer
};
