export const meta = {
  name: 'test-ga-exploration-fleet',
  description: 'Run 1000-iteration GA exploration test distributed across 8 workers',
  phases: [
    { title: 'Parallel Exploration Test', detail: '8 workers × 125 iterations each = 1000 total' },
    { title: 'Aggregate Results', detail: 'Collect exploration statistics' }
  ]
}

// Phase 1: Distribute 1000 iterations across 8 workers (125 each)
phase('Parallel Exploration Test')

log('Running 1000-iteration GA exploration test across 8 fleet workers...')
log('Each worker runs 125 iterations independently, then we aggregate.')

const iterationsPerWorker = 125
const workerCount = 8
const totalIterations = iterationsPerWorker * workerCount

const explorationResults = await parallel(
  Array.from({ length: workerCount }, (_, idx) => () =>
    agent(`Run ${iterationsPerWorker} GA exploration iterations.

Worker ID: ${idx + 1}/${workerCount}
Iterations: ${iterationsPerWorker}

Instructions:
1. Run Python test:
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   python3 -c "
import sys
sys.path.insert(0, 'tools')
from auto_profiler import AutoProfiler

profiler = AutoProfiler(exploration_rate=0.15)
iterations = ${iterationsPerWorker}
exploration_count = 0
selected_models = []

for i in range(iterations):
    model, is_exploration = profiler.select_model_for_task('code_generation')
    selected_models.append(model)
    if is_exploration:
        exploration_count += 1

unique_models = len(set(selected_models))
exploration_rate = (exploration_count / iterations) * 100

print(f'ITERATIONS={iterations}')
print(f'EXPLORATIONS={exploration_count}')
print(f'UNIQUE_MODELS={unique_models}')
print(f'EXPLORATION_RATE={exploration_rate:.1f}')
"

2. Parse output and extract metrics

Return JSON with:
- worker_id: ${idx + 1}
- iterations: ${iterationsPerWorker}
- exploration_count: (number of explorations)
- unique_models: (number of unique models selected)
- exploration_rate: (percentage)`, {
      label: `worker-${idx + 1}`,
      phase: 'Parallel Exploration Test',
      schema: {
        type: 'object',
        properties: {
          worker_id: { type: 'number' },
          iterations: { type: 'number' },
          exploration_count: { type: 'number' },
          unique_models: { type: 'number' },
          exploration_rate: { type: 'number' }
        },
        required: ['worker_id', 'iterations', 'exploration_count', 'exploration_rate']
      }
    })
  )
)

const validResults = explorationResults.filter(Boolean)

log(`✓ ${validResults.length}/${workerCount} workers completed`)

// Phase 2: Aggregate results
phase('Aggregate Results')

const totalExplorations = validResults.reduce((sum, r) => sum + r.exploration_count, 0)
const totalUniqueModels = Math.max(...validResults.map(r => r.unique_models || 0))
const avgExplorationRate = totalExplorations / totalIterations * 100

log('Aggregating exploration statistics...')
log(`Total iterations: ${totalIterations} (${workerCount} workers × ${iterationsPerWorker})`)
log(`Total explorations: ${totalExplorations}`)
log(`Overall exploration rate: ${avgExplorationRate.toFixed(1)}%`)
log(`Expected: ~15% (150 explorations)`)

// Analyze results
const analysis = await agent(`Analyze GA exploration test results from ${workerCount} workers.

Total iterations: ${totalIterations}
Total explorations: ${totalExplorations}
Exploration rate: ${avgExplorationRate.toFixed(1)}%
Expected rate: 15%

Per-worker results:
${JSON.stringify(validResults, null, 2)}

Instructions:
1. Determine if exploration rate is in acceptable range (10-20%)
2. Check for consistency across workers
3. Identify any anomalies (workers with 0% or 100% exploration)
4. Provide verdict on GA exploration health

Return JSON with:
- verdict: "PASS" | "FAIL"
- exploration_healthy: boolean
- rate_within_range: boolean (10-20%)
- worker_consistency: boolean (all workers show similar rates)
- summary: string
- recommendation: string`, {
  label: 'analyze-exploration',
  phase: 'Aggregate Results',
  schema: {
    type: 'object',
    properties: {
      verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
      exploration_healthy: { type: 'boolean' },
      rate_within_range: { type: 'boolean' },
      worker_consistency: { type: 'boolean' },
      summary: { type: 'string' },
      recommendation: { type: 'string' }
    },
    required: ['verdict', 'exploration_healthy', 'summary']
  }
})

log(`✓ Analysis complete: ${analysis.verdict}`)

// Return results
return {
  test_config: {
    total_iterations: totalIterations,
    workers: workerCount,
    iterations_per_worker: iterationsPerWorker,
    expected_exploration_rate: 15.0
  },
  results: {
    total_explorations: totalExplorations,
    actual_exploration_rate: avgExplorationRate,
    rate_deviation: Math.abs(avgExplorationRate - 15.0),
    worker_results: validResults
  },
  analysis: analysis,
  verdict: analysis.verdict === 'PASS'
    ? `✅ GA EXPLORATION VERIFIED (${avgExplorationRate.toFixed(1)}% over ${totalIterations} iterations)`
    : `❌ EXPLORATION ISSUE (${avgExplorationRate.toFixed(1)}% vs expected 15%)`
}
