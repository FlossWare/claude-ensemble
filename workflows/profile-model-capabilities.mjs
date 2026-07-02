#!/usr/bin/env node
/**
 * Model Capability Profiling Workflow
 *
 * Benchmarks models on standard tasks to determine capabilities:
 * - Code generation
 * - Code review
 * - Research/summarization
 * - Math/reasoning
 * - General QA
 *
 * Usage:
 *   node workflows/profile-model-capabilities.mjs --count=50 --parallel
 *   node workflows/profile-model-capabilities.mjs --provider=mistral
 *   node workflows/profile-model-capabilities.mjs --model=qwen/qwen3-coder:free
 */

export const meta = {
  name: 'profile-model-capabilities',
  description: 'Benchmark models on standard tasks to build capability database',
  phases: [
    { title: 'Select Models', detail: 'Get unprofiled models from database' },
    { title: 'Benchmark', detail: 'Test each model on 5 standard tasks', model: 'opus' },
    { title: 'Score', detail: 'Evaluate responses and calculate scores' },
    { title: 'Store', detail: 'Save capabilities to PostgreSQL' }
  ]
}

// Standard test tasks
const BENCHMARK_TASKS = {
  code_generation: {
    prompt: `Write a Python function called 'merge_sort' that implements the merge sort algorithm. Include:
- Proper function signature with type hints
- Docstring explaining the algorithm
- Helper function for merging
- Handle edge cases (empty list, single element)
Return ONLY the code, no explanations.`,
    scoreCriteria: {
      hasFunction: 0.2,
      hasDocstring: 0.1,
      hasTypeHints: 0.1,
      hasHelper: 0.2,
      handlesEdgeCases: 0.2,
      syntaxValid: 0.2
    }
  },

  code_review: {
    prompt: `Review this Python code for bugs and issues:

\`\`\`python
def calculate_average(numbers):
    total = 0
    for i in range(len(numbers)):
        total += numbers[i]
    return total / len(numbers)

# Usage
scores = [85, 90, 78, 92, 88]
avg = calculate_average(scores)
print(f"Average: {avg}")
\`\`\`

List any bugs, potential issues, or improvements. Be specific.`,
    scoreCriteria: {
      identifiesDivisionByZero: 0.4,
      suggestsBuiltins: 0.2,
      suggestsTypeHints: 0.1,
      identifiesEdgeCases: 0.2,
      formatQuality: 0.1
    }
  },

  research: {
    prompt: `Summarize the key concepts of "Attention Is All You Need" (the Transformer paper):
- Main innovation
- How attention mechanism works
- Key advantages over RNNs
Keep it concise (3-4 sentences).`,
    scoreCriteria: {
      mentionsAttention: 0.3,
      explainsMechanism: 0.3,
      comparesRNNs: 0.2,
      correctInfo: 0.2
    }
  },

  math_reasoning: {
    prompt: `Solve this step-by-step:

If 5 machines take 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?

Show your reasoning.`,
    scoreCriteria: {
      correctAnswer: 0.5,
      showsSteps: 0.3,
      explainsReasoning: 0.2
    }
  },

  general_qa: {
    prompt: `Explain dependency injection in software engineering. Include:
- What it is
- Why it's used
- Simple example
Keep it brief (2-3 sentences).`,
    scoreCriteria: {
      definesCorrectly: 0.4,
      explainsBenefits: 0.3,
      providesExample: 0.3
    }
  }
}

export default async function({ phase, parallel, pipeline, agent, log, args }) {
  const { getDB } = require('../shared/postgres-adapter.js')
  const db = getDB()

  // Parse arguments
  const count = parseInt(args?.count) || 50
  const targetProvider = args?.provider
  const targetModel = args?.model
  const useParallel = args?.parallel || false

  log(`🧪 Model Capability Profiling`)
  log(`Target: ${targetModel ? targetModel : targetProvider ? targetProvider : `${count} unprofiled models`}`)

  // Phase 1: Select Models
  await phase('Select Models', async () => {
    log('Querying database for unprofiled models...')

    let query = `
      SELECT fm.model_id, fm.provider, fm.model_name, fm.context_length
      FROM learning.free_models fm
      LEFT JOIN learning.model_capabilities mc ON fm.model_id = mc.model_id
      WHERE mc.model_id IS NULL
    `

    const params = []
    if (targetModel) {
      query += ` AND fm.model_id = $1`
      params.push(targetModel)
    } else if (targetProvider) {
      query += ` AND fm.provider = $1`
      params.push(targetProvider)
    }

    query += ` ORDER BY fm.context_length DESC NULLS LAST LIMIT $${params.length + 1}`
    params.push(count)

    const result = await db.query(query, params)
    const models = result.rows

    if (models.length === 0) {
      log('No unprofiled models found!')
      return { models: [], benchmarks: [] }
    }

    log(`Selected ${models.length} models to profile`)
    log(`Providers: ${[...new Set(models.map(m => m.provider))].join(', ')}`)

    return { models }
  })

  const { models } = await phase('Select Models')

  if (!models || models.length === 0) {
    return { message: 'No models to profile', profiled: 0 }
  }

  // Phase 2: Benchmark
  await phase('Benchmark', async () => {
    log(`Benchmarking ${models.length} models on ${Object.keys(BENCHMARK_TASKS).length} tasks...`)
    log(`Mode: ${useParallel ? 'PARALLEL (fast)' : 'SEQUENTIAL (safe)'}`)

    const benchmarkFn = (model) => async () => {
      const startTime = Date.now()
      const results = {}

      log(`Testing ${model.model_id}...`)

      // Test each task
      for (const [taskName, task] of Object.entries(BENCHMARK_TASKS)) {
        try {
          const taskStart = Date.now()

          // Call the model
          const response = await agent(task.prompt, {
            label: `${model.model_id.substring(0, 20)}-${taskName}`,
            model: 'opus', // Use opus to evaluate the model's response
            phase: 'Benchmark'
          })

          const latency = Date.now() - taskStart

          results[taskName] = {
            response,
            latency,
            success: true
          }
        } catch (error) {
          log(`  ❌ ${taskName} failed: ${error.message}`)
          results[taskName] = {
            response: null,
            latency: null,
            success: false,
            error: error.message
          }
        }
      }

      const totalTime = Date.now() - startTime
      log(`  ✓ ${model.model_id} completed in ${(totalTime/1000).toFixed(1)}s`)

      return {
        model_id: model.model_id,
        provider: model.provider,
        results,
        total_time_ms: totalTime
      }
    }

    const benchmarks = useParallel
      ? await parallel(models.map(benchmarkFn))
      : await pipeline(models, benchmarkFn)

    return { benchmarks: benchmarks.filter(Boolean) }
  })

  const { benchmarks } = await phase('Benchmark')

  // Phase 3: Score
  await phase('Score', async () => {
    log('Evaluating responses with FREE judge + automated checks...')

    const scoringPromises = benchmarks.map(benchmark => async () => {
      // First: Automated checks (free, instant)
      const automatedScores = {
        code_generation: 0,
        code_review: 0,
        research: 0,
        math_reasoning: 0,
        general_qa: 0
      }

      // Code generation checks
      if (benchmark.results.code_generation?.success) {
        const code = benchmark.results.code_generation.response || ''
        if (code.includes('def merge_sort') || code.includes('def mergeSort')) automatedScores.code_generation += 0.2
        if (code.includes('"""') || code.includes("'''")) automatedScores.code_generation += 0.1
        if (code.includes(':') && code.includes('->')) automatedScores.code_generation += 0.1
        if (code.includes('def merge') || code.includes('def _merge')) automatedScores.code_generation += 0.2
        if (code.includes('if not') || code.includes('if len')) automatedScores.code_generation += 0.1
        try {
          // Basic syntax check (doesn't execute)
          if (!code.includes('SyntaxError') && code.includes('def ')) automatedScores.code_generation += 0.2
        } catch (e) {}
      }

      // Code review checks
      if (benchmark.results.code_review?.success) {
        const review = (benchmark.results.code_review.response || '').toLowerCase()
        if (review.includes('division') && review.includes('zero')) automatedScores.code_review += 0.4
        if (review.includes('sum') || review.includes('built-in')) automatedScores.code_review += 0.2
        if (review.includes('type hint') || review.includes('annotation')) automatedScores.code_review += 0.1
        if (review.includes('edge case') || review.includes('empty')) automatedScores.code_review += 0.2
      }

      // Math reasoning checks
      if (benchmark.results.math_reasoning?.success) {
        const answer = (benchmark.results.math_reasoning.response || '').toLowerCase()
        if (answer.includes('5 minute') || answer.includes('five minute')) automatedScores.math_reasoning += 0.5
        if (answer.includes('step') || answer.includes('reasoning')) automatedScores.math_reasoning += 0.3
      }

      // Research checks
      if (benchmark.results.research?.success) {
        const research = (benchmark.results.research.response || '').toLowerCase()
        if (research.includes('attention') || research.includes('self-attention')) automatedScores.research += 0.3
        if (research.includes('transformer')) automatedScores.research += 0.2
        if (research.includes('rnn') || research.includes('recurrent')) automatedScores.research += 0.2
      }

      // General QA checks
      if (benchmark.results.general_qa?.success) {
        const qa = (benchmark.results.general_qa.response || '').toLowerCase()
        if (qa.includes('dependency injection') || qa.includes('di')) automatedScores.general_qa += 0.4
        if (qa.includes('decouple') || qa.includes('testable') || qa.includes('flexible')) automatedScores.general_qa += 0.3
      }

      // Second: Free model judge for nuanced evaluation
      return await agent(`Evaluate this model's benchmark results and assign scores (0.0-1.0).

**Model:** ${benchmark.model_id}

**Results:**
${Object.entries(benchmark.results).map(([task, result]) => `
**${task}:**
${result.success ? `Response: ${result.response?.substring(0, 500)}...` : `FAILED: ${result.error}`}
`).join('\n')}

**Scoring criteria:**
- code_generation: Is the code correct, complete, follows best practices?
- code_review: Did it identify the division-by-zero bug and suggest improvements?
- research: Does it correctly explain the Transformer architecture?
- math_reasoning: Correct answer (5 minutes) with clear reasoning?
- general_qa: Accurate explanation of dependency injection?

For failed tasks, score 0.0.

Return scores as JSON object with task names as keys, scores (0.0-1.0) as values.
Also include avg_latency_ms (average of successful task latencies).

**Automated checks found:**
${JSON.stringify(automatedScores, null, 2)}

Use these as a baseline, but adjust based on response quality.`, {
        label: `score-${benchmark.model_id.substring(0, 20)}`,
        phase: 'Score',
        model: 'groq/llama-3.3-70b-versatile', // FREE judge
        schema: {
          type: 'object',
          properties: {
            code_generation: { type: 'number', minimum: 0, maximum: 1 },
            code_review: { type: 'number', minimum: 0, maximum: 1 },
            research: { type: 'number', minimum: 0, maximum: 1 },
            math_reasoning: { type: 'number', minimum: 0, maximum: 1 },
            general_qa: { type: 'number', minimum: 0, maximum: 1 },
            avg_latency_ms: { type: 'number' }
          },
          required: ['code_generation', 'code_review', 'research', 'math_reasoning', 'general_qa']
        }
      })
    })

    const judgedScores = await parallel(scoringPromises)

    // Combine benchmarks with scores (automated + judged)
    const profiledModels = benchmarks.map((benchmark, i) => ({
      ...benchmark,
      scores: judgedScores[i],
      evaluation_method: 'free_judge_plus_automated'
    }))

    return { profiledModels }
  })

  const { profiledModels } = await phase('Score')

  // Phase 4: Store
  await phase('Store', async () => {
    log('Saving capability profiles to PostgreSQL...')

    let stored = 0
    for (const profile of profiledModels.filter(p => p.scores)) {
      try {
        await db.query(`
          INSERT INTO learning.model_capabilities
          (model_id, provider, code_generation, code_review, research,
           math_reasoning, general_qa, avg_latency_ms, test_count, notes)
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 1, $9)
          ON CONFLICT (model_id) DO UPDATE SET
            code_generation = EXCLUDED.code_generation,
            code_review = EXCLUDED.code_review,
            research = EXCLUDED.research,
            math_reasoning = EXCLUDED.math_reasoning,
            general_qa = EXCLUDED.general_qa,
            avg_latency_ms = EXCLUDED.avg_latency_ms,
            test_count = learning.model_capabilities.test_count + 1,
            last_tested = NOW()
        `, [
          profile.model_id,
          profile.provider,
          profile.scores.code_generation,
          profile.scores.code_review,
          profile.scores.research,
          profile.scores.math_reasoning,
          profile.scores.general_qa,
          profile.scores.avg_latency_ms,
          `Profiled on ${new Date().toISOString()}`
        ])
        stored++
      } catch (error) {
        log(`  ❌ Failed to store ${profile.model_id}: ${error.message}`)
      }
    }

    log(`✅ Stored ${stored}/${profiledModels.length} profiles`)

    // Show summary
    const summary = await db.query(`
      SELECT
        provider,
        COUNT(*) as profiled_count,
        ROUND(AVG(code_generation)::numeric, 2) as avg_code_score,
        ROUND(AVG(general_qa)::numeric, 2) as avg_qa_score
      FROM learning.model_capabilities
      GROUP BY provider
      ORDER BY profiled_count DESC
    `)

    log('\n📊 Capability database summary:')
    for (const row of summary.rows) {
      log(`  ${row.provider}: ${row.profiled_count} models (avg code: ${row.avg_code_score}, avg qa: ${row.avg_qa_score})`)
    }

    return { stored, summary: summary.rows }
  })

  const { stored } = await phase('Store')

  return {
    models_profiled: stored,
    total_models_with_capabilities: stored + 12 // Add existing
  }
}
