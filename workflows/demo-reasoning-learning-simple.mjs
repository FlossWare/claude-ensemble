export const meta = {
  name: 'demo-reasoning-learning-simple',
  description: 'Simple inline demo: Learn reasoning pattern and apply it',
  phases: [
    { title: 'Learn from Consensus', detail: '6 models solve debugging task' },
    { title: 'Extract Pattern', detail: 'Find consensus reasoning steps' },
    { title: 'Test Pattern', detail: 'Apply to new task and compare' }
  ]
}

/**
 * SIMPLIFIED DEMO - ALL INLINE (no nested workflows)
 *
 * Shows the complete learning cycle in one workflow
 */

log('REASONING LEARNING DEMO (Simplified)')
log('=' .repeat(60))
log('')

// ============================================================================
// PHASE 1: LEARN FROM CONSENSUS
// ============================================================================

phase('Learn from Consensus')

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

Test: findMax([3, 7, 2, 9, 1])  // Expected: 9, Actual: undefined`

log('Learning from debugging task...')
log('Assigning to 6 diverse models in parallel...')
log('')

const workers = [
  'opus', 'sonnet', 'haiku',
  'gemini-2.0-flash-exp:free',
  'deepseek-r1-distill-llama-70b',
  'qwen/qwen-2.5-72b-instruct'
]

const workerResults = await parallel(
  workers.map((model, idx) => () =>
    agent(`Debug this code and explain your step-by-step reasoning.

${learningTask}

Return JSON:
{
  "solution": "your bug fix explanation",
  "reasoning_steps": ["step 1", "step 2", ...],
  "confidence": 0.0-1.0
}`, {
      label: `worker-${idx+1}:${model.substring(0, 15)}`,
      phase: 'Learn from Consensus',
      model: model,
      schema: {
        type: 'object',
        properties: {
          solution: { type: 'string' },
          reasoning_steps: { type: 'array', items: { type: 'string' } },
          confidence: { type: 'number' }
        },
        required: ['solution', 'reasoning_steps', 'confidence']
      }
    })
  )
)

const validResults = workerResults.filter(Boolean)
log(`✓ ${validResults.length}/${workers.length} workers completed`)
log('')

// ============================================================================
// PHASE 2: EXTRACT PATTERN
// ============================================================================

phase('Extract Pattern')

log('Extracting consensus reasoning pattern...')

const patternExtraction = await agent(`Extract consensus reasoning pattern from these model results.

${JSON.stringify(validResults.map((r, i) => ({
  model: workers[i],
  steps: r.reasoning_steps,
  confidence: r.confidence
})), null, 2)}

Find steps that appear in 4+ models (66% consensus).

Return JSON:
{
  "consensus_steps": ["step 1", "step 2", ...],
  "consensus_score": 0.0-1.0,
  "pattern_quality": "excellent"|"good"|"weak"
}`, {
  label: 'extract-consensus',
  phase: 'Extract Pattern',
  schema: {
    type: 'object',
    properties: {
      consensus_steps: { type: 'array', items: { type: 'string' } },
      consensus_score: { type: 'number' },
      pattern_quality: { type: 'string' }
    },
    required: ['consensus_steps', 'consensus_score']
  }
})

if (!patternExtraction.consensus_steps || patternExtraction.consensus_steps.length === 0) {
  log('❌ No consensus found')
  return { learned: false, reason: 'No consensus' }
}

log(`✓ Learned ${patternExtraction.consensus_steps.length}-step pattern`)
log(`  Consensus: ${(patternExtraction.consensus_score*100).toFixed(0)}%`)
log(`  Quality: ${patternExtraction.pattern_quality}`)
log('')
log('Reasoning Pattern:')
patternExtraction.consensus_steps.forEach((step, i) => {
  log(`  ${i+1}. ${step}`)
})
log('')

// ============================================================================
// PHASE 3: TEST PATTERN (WITH vs WITHOUT)
// ============================================================================

phase('Test Pattern')

const testTask = `Debug this Python function:

def find_average(numbers):
    total = 0
    for i in range(len(numbers)):
        total += numbers[i]
    return total / len(numbers)

Test: find_average([])  # Expected: 0, Actual: ZeroDivisionError`

log('Testing learned pattern on NEW debugging task...')
log('')

// Test WITH learned pattern
log('Executing WITH learned pattern...')

const withPatternPrompt = `Debug this code.

Follow this proven reasoning pattern (${(patternExtraction.consensus_score*100).toFixed(0)}% consensus):
${patternExtraction.consensus_steps.map((s, i) => `${i+1}. ${s}`).join('\n')}

${testTask}`

const withPattern = await agent(withPatternPrompt, {
  label: 'with-pattern',
  phase: 'Test Pattern'
})

log('✓ WITH pattern completed')
log('')

// Test WITHOUT learned pattern (baseline)
log('Executing WITHOUT pattern (baseline)...')

const withoutPattern = await agent(testTask, {
  label: 'without-pattern',
  phase: 'Test Pattern'
})

log('✓ WITHOUT pattern completed')
log('')

// Compare results
log('Comparing results...')

const comparison = await agent(`Compare debugging results WITH vs WITHOUT learned pattern.

WITH Pattern Result:
${withPattern}

WITHOUT Pattern Result (baseline):
${withoutPattern}

Score each on:
- Correctness (found the bug?)
- Explanation quality
- Completeness

Return JSON:
{
  "with_score": 0-100,
  "without_score": 0-100,
  "winner": "with_pattern"|"without_pattern"|"tie",
  "improvement_pct": number,
  "summary": "brief explanation"
}`, {
  label: 'compare',
  phase: 'Test Pattern',
  schema: {
    type: 'object',
    properties: {
      with_score: { type: 'number' },
      without_score: { type: 'number' },
      winner: { type: 'string' },
      improvement_pct: { type: 'number' },
      summary: { type: 'string' }
    },
    required: ['with_score', 'without_score', 'winner', 'summary']
  }
})

log('')
log('=' .repeat(60))
log('RESULTS')
log('=' .repeat(60))
log('')
log(`Pattern Learned:`)
log(`  Steps: ${patternExtraction.consensus_steps.length}`)
log(`  Consensus: ${(patternExtraction.consensus_score*100).toFixed(0)}%`)
log(`  Quality: ${patternExtraction.pattern_quality}`)
log('')
log(`Quality Comparison:`)
log(`  WITH pattern: ${comparison.with_score}/100`)
log(`  WITHOUT pattern: ${comparison.without_score}/100`)
log(`  Winner: ${comparison.winner}`)
if (comparison.improvement_pct) {
  log(`  Improvement: ${comparison.improvement_pct.toFixed(1)}%`)
}
log('')
log(`Summary: ${comparison.summary}`)
log('')

return {
  demo_completed: true,
  learned_pattern: {
    steps: patternExtraction.consensus_steps,
    consensus: patternExtraction.consensus_score,
    quality: patternExtraction.pattern_quality
  },
  quality_comparison: {
    with_pattern: comparison.with_score,
    without_pattern: comparison.without_score,
    winner: comparison.winner,
    improvement: comparison.improvement_pct
  },
  verdict: comparison.winner === 'with_pattern'
    ? `✅ LEARNED REASONING IMPROVED QUALITY BY ${comparison.improvement_pct?.toFixed(1)}%`
    : comparison.winner === 'tie'
    ? '⚠️ LEARNED REASONING MATCHED BASELINE'
    : '❌ BASELINE PERFORMED BETTER (pattern needs refinement)'
}
