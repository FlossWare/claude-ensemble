#!/usr/bin/env node
/**
 * Example: How Active Learning Changes Decisions
 *
 * Demonstrates the system actively using its intelligence to make better
 * decisions over time.
 *
 * Run: node example-active-learning.js
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
} from './orchestrator-brain.js';

// ============================================================================
// EXAMPLE 1: Before vs After - Model Selection
// ============================================================================

async function example1_modelSelection() {
  console.log('=' .repeat(70));
  console.log('EXAMPLE 1: Model Selection - Thompson Sampling in Action');
  console.log('='.repeat(70));

  console.log('\n📊 Historical guidance for code-review:');
  const guidance = await consultLearnings('code-review', { days: 90 });

  if (guidance.available) {
    console.log(`  Sample size: ${guidance.sample_size} executions`);
    console.log(`  Success rate: ${(guidance.success_rate * 100).toFixed(1)}%`);
    console.log(`  Avg quality: ${guidance.avg_quality.toFixed(2)}`);
    console.log(`\n  Top 3 models:`);
    for (const model of guidance.best_models.slice(0, 3)) {
      console.log(`    ${model.model}: quality=${model.avg_quality.toFixed(2)} (${model.count} uses)`);
    }
    console.log(`\n  💡 Recommendation: ${guidance.recommendation}`);
  } else {
    console.log(`  No historical data - system will explore`);
  }

  console.log('\n🎲 Thompson Sampling - Balancing exploration/exploitation:');
  const selections = [];
  for (let i = 0; i < 10; i++) {
    const model = await selectModelIntelligently('code-review', {
      useThompson: true,
      count: 1,
    });
    selections.push(model);
  }

  const counts = {};
  for (const model of selections) {
    counts[model] = (counts[model] || 0) + 1;
  }

  console.log(`  Selections: ${selections.join(', ')}`);
  console.log(`  Distribution:`);
  for (const [model, count] of Object.entries(counts)) {
    const pct = (count / 10 * 100).toFixed(0);
    const bar = '█'.repeat(Math.round(pct / 5));
    console.log(`    ${model.padEnd(10)}: ${bar} ${pct}%`);
  }

  console.log('\n  ✨ Notice: System explores uncertain models while favoring proven ones');
}

// ============================================================================
// EXAMPLE 2: Knowledge Base Search
// ============================================================================

async function example2_knowledgeSearch() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 2: Knowledge Base Search - Finding Past Learnings');
  console.log('='.repeat(70));

  const queries = [
    'endpoint configuration',
    'async patterns',
    'security best practices',
  ];

  for (const query of queries) {
    console.log(`\n🔍 Query: "${query}"`);
    const results = await searchKnowledgeBases(query, {
      limit: 3,
      minConfidence: 0.5,
    });

    console.log(`  Found ${results.total_found} items:`);
    console.log(`    Disseminator KB: ${results.disseminator.length}`);
    console.log(`    Web synthesis: ${results.web_synthesis.length}`);

    if (results.disseminator.length > 0) {
      console.log(`\n  Top result from disseminator:`);
      const top = results.disseminator[0];
      console.log(`    "${top.title}"`);
      console.log(`    Confidence: ${(top.confidence * 100).toFixed(0)}%`);
      console.log(`    Relevance: ${(top.relevance * 100).toFixed(0)}%`);
    }
  }

  console.log('\n  ✨ Instead of re-discovering, we use past learnings!');
}

// ============================================================================
// EXAMPLE 3: Orchestrator Delegation
// ============================================================================

async function example3_orchestratorDelegation() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 3: Orchestrator Delegation - When to Coordinate');
  console.log('='.repeat(70));

  const tasks = [
    {
      name: 'Simple query',
      task: {
        type: 'simple-query',
        complexity: 0.2,
        multiDomain: false,
        modelCount: 1,
      },
    },
    {
      name: 'Code review',
      task: {
        type: 'code-review',
        complexity: 0.5,
        multiDomain: false,
        modelCount: 2,
      },
    },
    {
      name: 'Multi-domain security',
      task: {
        type: 'security-review',
        complexity: 0.85,
        multiDomain: true,
        modelCount: 6,
      },
    },
  ];

  for (const { name, task } of tasks) {
    console.log(`\n📋 Task: ${name}`);
    console.log(`  Complexity: ${task.complexity.toFixed(2)}`);
    console.log(`  Multi-domain: ${task.multiDomain}`);
    console.log(`  Models needed: ${task.modelCount}`);

    const decision = await shouldUseOrchestrator(task);
    console.log(`\n  🤖 Use orchestrator: ${decision.use_orchestrator}`);
    console.log(`  Confidence: ${(decision.confidence * 100).toFixed(0)}%`);

    if (decision.reasons.length > 0) {
      console.log(`  Reasons:`);
      for (const reason of decision.reasons) {
        console.log(`    - ${reason}`);
      }
    }
  }

  console.log('\n  ✨ System intelligently decides when to delegate!');
}

// ============================================================================
// EXAMPLE 4: Orchestrator Intelligence
// ============================================================================

async function example4_orchestratorIntelligence() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 4: Orchestrator Intelligence - Smart Coordination');
  console.log('='.repeat(70));

  const task = {
    type: 'multi-domain-review',
    description: 'Review security, performance, and architecture',
    subtasks: ['security-review', 'performance-review', 'architecture-review'],
    domains: ['security', 'performance', 'architecture'],
    quality_requirement: 0.9,
    time_pressure: 0.3,
  };

  console.log('\n📝 Task analysis:');
  const analysis = await analyzeTaskComplexity(task);

  console.log(`  Complexity: ${analysis.complexity_score.toFixed(2)} (${analysis.complexity_level})`);
  console.log(`  Estimated models: ${analysis.estimated_models}`);
  console.log(`  Estimated duration: ${(analysis.estimated_duration_ms / 1000).toFixed(1)}s`);
  console.log(`  Estimated cost: $${analysis.estimated_cost_usd.toFixed(4)}`);
  console.log(`  Recommended strategy: ${analysis.recommendation}`);

  console.log('\n🎯 Strategy selection:');
  const strategy = await selectAgentStrategy(task, analysis);

  console.log(`  Strategy: ${strategy.strategy}`);
  console.log(`  Workers: ${strategy.worker_models.join(', ')}`);
  console.log(`  Arbiter: ${strategy.arbiter_model}`);
  console.log(`  Confidence: ${(strategy.confidence * 100).toFixed(0)}%`);
  console.log(`  Reasoning: ${strategy.reasoning}`);

  console.log('\n  ✨ Orchestrator makes intelligent coordination decisions!');
}

// ============================================================================
// EXAMPLE 5: Learning Loop
// ============================================================================

async function example5_learningLoop() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 5: Learning Loop - System Gets Smarter');
  console.log('='.repeat(70));

  // Simulate several decisions with varying outcomes
  console.log('\n📚 Recording decisions:');

  const decisions = [
    {
      task_type: 'demo-task-1',
      model_used: 'opus',
      decision: 'Used single model approach',
      outcome: 'success',
      quality_score: 0.92,
    },
    {
      task_type: 'demo-task-1',
      model_used: 'sonnet',
      decision: 'Used single model approach',
      outcome: 'success',
      quality_score: 0.78,
    },
    {
      task_type: 'demo-task-1',
      model_used: 'haiku',
      decision: 'Used single model approach',
      outcome: 'failure',
      quality_score: 0.42,
    },
  ];

  for (const decision of decisions) {
    const result = await recordDecision(decision);
    console.log(`  ✓ ${decision.model_used}: quality=${decision.quality_score.toFixed(2)}`);
  }

  console.log('\n📊 Intelligence summary:');
  const summary = await getIntelligenceSummary();

  console.log(`\n  Thompson Sampling:`);
  console.log(`    Models tracked: ${summary.thompson_sampling.models_tracked}`);

  const topModels = summary.thompson_sampling.stats
    .sort((a, b) => b.success_rate - a.success_rate)
    .slice(0, 5);

  console.log(`\n    Top 5 models by success rate:`);
  for (const model of topModels) {
    console.log(`      ${model.model.padEnd(10)}: ${(model.success_rate * 100).toFixed(0)}% (${model.total} executions)`);
  }

  console.log(`\n  Decisions:`);
  console.log(`    Total: ${summary.decisions.total}`);
  console.log(`    Success rate: ${(summary.decisions.success_rate * 100).toFixed(1)}%`);
  console.log(`    Avg quality: ${summary.decisions.avg_quality.toFixed(2)}`);

  console.log(`\n  Learnings:`);
  console.log(`    Total: ${summary.learnings.total}`);
  console.log(`    Success patterns: ${summary.learnings.success_patterns}`);
  console.log(`    Failure patterns: ${summary.learnings.failure_patterns}`);

  if (summary.learnings.recent.length > 0) {
    console.log(`\n  Recent insights:`);
    for (const learning of summary.learnings.recent.slice(0, 3)) {
      console.log(`    - ${learning.insight}`);
    }
  }

  console.log('\n  ✨ System tracks and learns from every decision!');
}

// ============================================================================
// EXAMPLE 6: Before vs After Comparison
// ============================================================================

async function example6_beforeAfter() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 6: Before vs After - The Difference');
  console.log('='.repeat(70));

  console.log('\n❌ BEFORE (without active learning):');
  console.log('  - Claude picks models based on... vibes?');
  console.log('  - No memory of what worked before');
  console.log('  - Same mistakes repeated');
  console.log('  - Manual model selection');
  console.log('  - Orchestrator just passes messages');
  console.log('  - Knowledge scattered, not searchable');

  console.log('\n✅ AFTER (with active learning):');
  console.log('  - Claude consults historical performance data');
  console.log('  - Thompson Sampling balances explore/exploit');
  console.log('  - Knowledge bases searched automatically');
  console.log('  - Decisions recorded and learned from');
  console.log('  - Orchestrator makes intelligent coordination');
  console.log('  - System gets smarter over time');

  console.log('\n📈 Example improvement trajectory:');
  const decisionSummary = await getDecisionSummary({ limit: 100 });

  if (decisionSummary.total > 0) {
    console.log(`\n  Current performance:`);
    console.log(`    Total decisions: ${decisionSummary.total}`);
    console.log(`    Success rate: ${(decisionSummary.success_rate * 100).toFixed(1)}%`);
    console.log(`    Avg quality: ${decisionSummary.avg_quality.toFixed(2)}`);

    // Group by time to show improvement
    const recent = decisionSummary.decisions.slice(0, 20);
    const older = decisionSummary.decisions.slice(20, 40);

    if (older.length > 0) {
      const recentAvg = recent.reduce((sum, d) => sum + (d.quality_score || 0.5), 0) / recent.length;
      const olderAvg = older.reduce((sum, d) => sum + (d.quality_score || 0.5), 0) / older.length;
      const improvement = ((recentAvg - olderAvg) / olderAvg * 100).toFixed(1);

      console.log(`\n  Improvement over time:`);
      console.log(`    Older quality: ${olderAvg.toFixed(2)}`);
      console.log(`    Recent quality: ${recentAvg.toFixed(2)}`);
      console.log(`    Improvement: ${improvement > 0 ? '+' : ''}${improvement}%`);
    }
  }

  console.log('\n  ✨ The system actively uses its own intelligence!');
}

// ============================================================================
// RUN ALL EXAMPLES
// ============================================================================

async function runExamples() {
  console.log('\n🚀 Active Learning Integration - Examples\n');

  try {
    await example1_modelSelection();
    await example2_knowledgeSearch();
    await example3_orchestratorDelegation();
    await example4_orchestratorIntelligence();
    await example5_learningLoop();
    await example6_beforeAfter();

    console.log('\n' + '='.repeat(70));
    console.log('🎉 SYSTEM IS ACTIVELY USING ITS INTELLIGENCE!');
    console.log('='.repeat(70));
    console.log('\nKey takeaways:');
    console.log('  1. consultLearnings() guides decisions with historical data');
    console.log('  2. Thompson Sampling balances exploration and exploitation');
    console.log('  3. Knowledge bases prevent re-discovering past learnings');
    console.log('  4. Orchestrator delegation is intelligent, not hardcoded');
    console.log('  5. Every decision feeds the learning loop');
    console.log('  6. System gets demonstrably smarter over time');
    console.log('\n' + '='.repeat(70) + '\n');

  } catch (err) {
    console.error('\n❌ Error running examples:', err.message);
    if (process.env.DEBUG) {
      console.error(err.stack);
    }
    process.exit(1);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runExamples().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}

export default runExamples;
