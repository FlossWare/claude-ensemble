export const meta = {
  name: 'test-adaptive-exploration',
  description: 'Compare fixed vs adaptive exploration strategies',
  phases: [
    { title: 'Fixed Exploration Test', detail: 'Test fixed 15% exploration (1000 iterations)' },
    { title: 'Adaptive Exploration Test', detail: 'Test adaptive exploration (1000 iterations)' },
    { title: 'Comparison Analysis', detail: 'Compare both strategies' }
  ]
}

// Phase 1: Fixed Exploration (baseline)
phase('Fixed Exploration Test')

log('Testing fixed 15% exploration (baseline)...')

const fixedTest = await agent(`Run 1000 iterations with FIXED 15% exploration.

Instructions:
1. Run test with fixed exploration rate:
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   python3 -c "
import sys
sys.path.insert(0, 'tools')
from auto_profiler import AutoProfiler

profiler = AutoProfiler(exploration_rate=0.15, adaptive=False)
iterations = 1000
exploration_count = 0
coverage_samples = []

for i in range(iterations):
    model, is_exploration = profiler.select_model_for_task('code_generation')
    if is_exploration:
        exploration_count += 1

    # Sample coverage every 100 iterations
    if (i + 1) % 100 == 0:
        stats = profiler.get_profiled_count()
        coverage = stats['profiled'] / stats['total'] * 100
        coverage_samples.append(coverage)

print(f'FIXED_EXPLORATIONS={exploration_count}')
print(f'FIXED_RATE={exploration_count/iterations*100:.1f}')
print(f'COVERAGE_SAMPLES={coverage_samples}')
"

2. Parse results and return structured data

Return JSON with:
- strategy: "fixed"
- iterations: 1000
- exploration_count: (number)
- exploration_rate: (percentage)
- coverage_progression: (array of coverage at each 100 iterations)`, {
  label: 'fixed-exploration',
  phase: 'Fixed Exploration Test',
  schema: {
    type: 'object',
    properties: {
      strategy: { type: 'string' },
      iterations: { type: 'number' },
      exploration_count: { type: 'number' },
      exploration_rate: { type: 'number' },
      coverage_progression: { type: 'array', items: { type: 'number' } }
    },
    required: ['strategy', 'iterations', 'exploration_count', 'exploration_rate']
  }
})

log(`✓ Fixed exploration: ${fixedTest.exploration_rate}% (${fixedTest.exploration_count}/1000)`)

// Phase 2: Adaptive Exploration
phase('Adaptive Exploration Test')

log('Testing adaptive exploration (30% → 15% → 5% based on coverage)...')

const adaptiveTest = await agent(`Run 1000 iterations with ADAPTIVE exploration.

Adaptive strategy:
- Coverage < 20%: 30% exploration
- Coverage 20-80%: 15% exploration
- Coverage > 80%: 5% exploration

Instructions:
1. Run test with adaptive exploration:
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   python3 -c "
import sys
sys.path.insert(0, 'tools')
from auto_profiler import AutoProfiler

profiler = AutoProfiler(exploration_rate=0.15, adaptive=True)
iterations = 1000
exploration_count = 0
coverage_samples = []
exploration_rate_samples = []

for i in range(iterations):
    # Get current exploration rate (will adapt)
    current_rate = profiler.exploration_rate

    model, is_exploration = profiler.select_model_for_task('code_generation')
    if is_exploration:
        exploration_count += 1

    # Sample every 100 iterations
    if (i + 1) % 100 == 0:
        stats = profiler.get_profiled_count()
        coverage = stats['profiled'] / stats['total'] * 100
        coverage_samples.append(coverage)
        exploration_rate_samples.append(current_rate * 100)

print(f'ADAPTIVE_EXPLORATIONS={exploration_count}')
print(f'ADAPTIVE_RATE={exploration_count/iterations*100:.1f}')
print(f'COVERAGE_SAMPLES={coverage_samples}')
print(f'RATE_SAMPLES={exploration_rate_samples}')
"

2. Parse results

Return JSON with:
- strategy: "adaptive"
- iterations: 1000
- exploration_count: (number)
- exploration_rate: (percentage - overall average)
- coverage_progression: (array)
- rate_progression: (array - how exploration rate changed)`, {
  label: 'adaptive-exploration',
  phase: 'Adaptive Exploration Test',
  schema: {
    type: 'object',
    properties: {
      strategy: { type: 'string' },
      iterations: { type: 'number' },
      exploration_count: { type: 'number' },
      exploration_rate: { type: 'number' },
      coverage_progression: { type: 'array', items: { type: 'number' } },
      rate_progression: { type: 'array', items: { type: 'number' } }
    },
    required: ['strategy', 'iterations', 'exploration_count', 'exploration_rate']
  }
})

log(`✓ Adaptive exploration: ${adaptiveTest.exploration_rate}% avg (${adaptiveTest.exploration_count}/1000)`)

// Phase 3: Compare strategies
phase('Comparison Analysis')

log('Analyzing fixed vs adaptive exploration strategies...')

const comparison = await agent(`Compare fixed vs adaptive exploration strategies.

Fixed Exploration Results:
${JSON.stringify(fixedTest, null, 2)}

Adaptive Exploration Results:
${JSON.stringify(adaptiveTest, null, 2)}

Current state: 37/252 models profiled (14.7% coverage)

Instructions:
1. Compare exploration efficiency:
   - Which strategy explores more early (when coverage is low)?
   - Which strategy finds better balance as coverage grows?
   - Which gets to full coverage faster?

2. Analyze coverage progression:
   - Does adaptive start faster (30% exploration when coverage < 20%)?
   - Does it reduce waste later (5% when coverage > 80%)?

3. Provide recommendation:
   - Which strategy is better for current state (14.7% coverage)?
   - What are the tradeoffs?
   - Should we switch to adaptive?

Return JSON with:
- winner: "fixed" | "adaptive" | "tie"
- fixed_efficiency: (number - score 0-100)
- adaptive_efficiency: (number - score 0-100)
- recommendation: "use_fixed" | "use_adaptive" | "depends_on_context"
- reasoning: (string - detailed explanation)
- optimal_for_current_state: "fixed" | "adaptive" (for 14.7% coverage)`, {
  label: 'compare-strategies',
  phase: 'Comparison Analysis',
  schema: {
    type: 'object',
    properties: {
      winner: { type: 'string', enum: ['fixed', 'adaptive', 'tie'] },
      fixed_efficiency: { type: 'number' },
      adaptive_efficiency: { type: 'number' },
      recommendation: { type: 'string', enum: ['use_fixed', 'use_adaptive', 'depends_on_context'] },
      reasoning: { type: 'string' },
      optimal_for_current_state: { type: 'string', enum: ['fixed', 'adaptive'] }
    },
    required: ['winner', 'recommendation', 'reasoning', 'optimal_for_current_state']
  }
})

log(`✓ Analysis complete: ${comparison.winner} wins`)
log(`  Recommendation: ${comparison.recommendation}`)

// Return comprehensive results
return {
  test_results: {
    fixed: fixedTest,
    adaptive: adaptiveTest
  },
  comparison: comparison,
  verdict: comparison.optimal_for_current_state === 'adaptive'
    ? `✅ ADAPTIVE EXPLORATION RECOMMENDED (better for ${fixedTest.coverage_progression?.[0] || '14.7'}% coverage)`
    : `✅ FIXED EXPLORATION ADEQUATE (${fixedTest.exploration_rate}% is sufficient)`,
  next_steps: comparison.recommendation === 'use_adaptive'
    ? 'Deploy adaptive exploration to production'
    : 'Keep current fixed exploration strategy'
}
