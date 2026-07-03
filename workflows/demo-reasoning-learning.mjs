export const meta = {
  name: 'demo-reasoning-learning',
  description: 'Demo: Learn and apply reasoning patterns (end-to-end)',
  phases: [
    { title: 'Learn Pattern', detail: 'Learn from debugging task consensus' },
    { title: 'Apply Pattern', detail: 'Use learned pattern on new task' },
    { title: 'Compare Results', detail: 'With vs without learned reasoning' }
  ]
}

/**
 * END-TO-END DEMO: How Reasoning Learning Works
 *
 * Step 1: Learn reasoning pattern from multi-model consensus
 * Step 2: Apply learned pattern to similar new task
 * Step 3: Compare quality with/without learned reasoning
 *
 * This demonstrates the full learning cycle in action!
 */

log('=' .repeat(60))
log('REASONING LEARNING DEMO')
log('=' .repeat(60))
log('')

// ============================================================================
// PHASE 1: LEARN PATTERN (from consensus)
// ============================================================================

phase('Learn Pattern')

log('Step 1: Learn reasoning pattern from debugging task...')
log('')

const learningTask = `Debug this JavaScript function:

function findMax(arr) {
  let max = arr[0];
  for (let i = 1; i <= arr.length; i++) {
    if (arr[i] > max) {
      max = arr[i];
    }
  }
  return max;
}

// Test case:
findMax([3, 7, 2, 9, 1])  // Expected: 9, Actual: undefined
`

// Run learning workflow inline (can't nest workflows, must use agents)
const learnResult = await agent(`Learn reasoning pattern from multi-model consensus.

Task to learn from:
${learningTask}

Task Type: debugging
Worker Count: 6
Min Consensus: 66%

Instructions:
1. Launch learning workflow:
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   claude workflow run workflows/learn-reasoning-consensus.mjs --args '{"task": "${learningTask.replace(/\n/g, '\\n').replace(/"/g, '\\"')}", "task_type": "debugging", "worker_count": 6, "min_consensus": 0.66}'

2. Wait for completion and parse results

Return JSON matching the learning workflow output schema:
{
  "learned": true/false,
  "pattern_id": (number),
  "pattern": {
    "task_type": "debugging",
    "reasoning_steps": [...],
    "consensus_score": 0.0-1.0,
    "quality": "excellent"|"good"|"weak"
  },
  "statistics": {...}
}`, {
  label: 'learn-pattern-orchestrator',
  phase: 'Learn Pattern'
})

log('')
log('Learning Results:')
log(`  Learned: ${learnResult.learned}`)
if (learnResult.learned) {
  log(`  Pattern ID: ${learnResult.pattern_id}`)
  log(`  Consensus: ${(learnResult.pattern.consensus_score*100).toFixed(0)}%`)
  log(`  Quality: ${learnResult.pattern.quality}`)
  log(`  Reasoning steps:`)
  learnResult.pattern.reasoning_steps.forEach((step, i) => {
    log(`    ${i+1}. ${step}`)
  })
}
log('')

if (!learnResult.learned) {
  return {
    demo_completed: false,
    reason: 'Failed to learn pattern from consensus',
    learn_result: learnResult
  }
}

// ============================================================================
// PHASE 2: APPLY PATTERN (to new similar task)
// ============================================================================

phase('Apply Pattern')

log('Step 2: Apply learned pattern to NEW debugging task...')
log('')

const newTask = `Debug this Python function:

def find_average(numbers):
    total = 0
    for i in range(len(numbers)):
        total += numbers[i]
    return total / len(numbers)

# Test case:
find_average([])  # Expected: 0, Actual: ZeroDivisionError
`

const applyResult = await workflow('execute-with-learned-reasoning', {
  task: newTask,
  task_type: 'debugging'
})

log('')
log('Application Results:')
log(`  Pattern used: ${applyResult.pattern_used}`)
if (applyResult.pattern_used) {
  log(`  Pattern ID: ${applyResult.pattern_id}`)
  log(`  Execution time: ${applyResult.execution_metrics.execution_time_ms}ms`)
  log(`  Quality score: ${applyResult.execution_metrics.quality_score}`)
}
log('')

// ============================================================================
// PHASE 3: COMPARE (with vs without learned reasoning)
// ============================================================================

phase('Compare Results')

log('Step 3: Compare quality WITH vs WITHOUT learned reasoning...')
log('')

// Execute same task WITHOUT pattern
log('Executing WITHOUT learned pattern (baseline)...')

const baselineResult = await agent(newTask, {
  label: 'baseline-no-pattern',
  phase: 'Compare Results'
})

// Compare results
const comparison = await agent(`Compare results from WITH vs WITHOUT learned reasoning.

Task: ${newTask}

Result WITH learned pattern:
${JSON.stringify(applyResult.result, null, 2)}

Result WITHOUT pattern (baseline):
${JSON.stringify(baselineResult, null, 2)}

Instructions:
Compare on:
1. Correctness - Did it find the bug?
2. Completeness - Did it explain the fix?
3. Quality - How thorough was the reasoning?
4. Efficiency - Time taken

Return JSON with:
{
  "with_pattern_score": 0-100,
  "without_pattern_score": 0-100,
  "winner": "with_pattern" | "without_pattern" | "tie",
  "improvement": (percentage),
  "reasoning": "detailed comparison"
}`, {
  label: 'compare-results',
  phase: 'Compare Results',
  schema: {
    type: 'object',
    properties: {
      with_pattern_score: { type: 'number' },
      without_pattern_score: { type: 'number' },
      winner: { type: 'string', enum: ['with_pattern', 'without_pattern', 'tie'] },
      improvement: { type: 'number' },
      reasoning: { type: 'string' }
    },
    required: ['with_pattern_score', 'without_pattern_score', 'winner', 'reasoning']
  }
})

log('')
log('Comparison Results:')
log(`  WITH pattern: ${comparison.with_pattern_score}/100`)
log(`  WITHOUT pattern: ${comparison.without_pattern_score}/100`)
log(`  Winner: ${comparison.winner}`)
if (comparison.improvement) {
  log(`  Improvement: ${comparison.improvement.toFixed(1)}%`)
}
log('')
log('Reasoning:')
log(comparison.reasoning)
log('')

// ============================================================================
// FINAL SUMMARY
// ============================================================================

log('=' .repeat(60))
log('DEMO SUMMARY')
log('=' .repeat(60))
log('')

const summary = {
  demo_completed: true,

  learning_phase: {
    task_type: 'debugging',
    learned: learnResult.learned,
    pattern_id: learnResult.pattern_id,
    consensus_score: learnResult.pattern?.consensus_score,
    reasoning_steps: learnResult.pattern?.reasoning_steps?.length
  },

  application_phase: {
    pattern_used: applyResult.pattern_used,
    execution_time_ms: applyResult.execution_metrics?.execution_time_ms,
    quality_score: applyResult.execution_metrics?.quality_score
  },

  comparison: {
    with_pattern: comparison.with_pattern_score,
    without_pattern: comparison.without_pattern_score,
    winner: comparison.winner,
    improvement_pct: comparison.improvement
  },

  verdict: comparison.winner === 'with_pattern'
    ? `✅ LEARNED REASONING IMPROVED QUALITY BY ${comparison.improvement.toFixed(1)}%`
    : comparison.winner === 'tie'
    ? '⚠️  LEARNED REASONING MATCHED BASELINE (no improvement)'
    : '❌ LEARNED REASONING UNDERPERFORMED BASELINE (needs tuning)'
}

log(`Learning: ${summary.learning_phase.learned ? 'SUCCESS' : 'FAILED'}`)
log(`  Pattern ID: ${summary.learning_phase.pattern_id}`)
log(`  Consensus: ${(summary.learning_phase.consensus_score*100).toFixed(0)}%`)
log(`  Steps learned: ${summary.learning_phase.reasoning_steps}`)
log('')
log(`Application: ${summary.application_phase.pattern_used ? 'SUCCESS' : 'FAILED'}`)
log(`  Execution time: ${summary.application_phase.execution_time_ms}ms`)
log(`  Quality: ${summary.application_phase.quality_score}`)
log('')
log(`Comparison: ${comparison.winner}`)
log(`  WITH pattern: ${comparison.with_pattern_score}/100`)
log(`  WITHOUT pattern: ${comparison.without_pattern_score}/100`)
if (comparison.improvement > 0) {
  log(`  Improvement: ${comparison.improvement.toFixed(1)}%`)
}
log('')

return summary
