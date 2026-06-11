export const meta = {
  name: 'ai-task-router',
  description: 'Dynamic task routing - selects optimal worker models based on task complexity, specialization, and cost budget',
  whenToUse: 'When you need to intelligently assign tasks to the right models based on complexity, specialization strengths, and cost constraints',
  phases: [
    { title: 'Classify', detail: 'Analyze task context to determine complexity and category' },
    { title: 'Load Config', detail: 'Read model cost and specialization data' },
    { title: 'Route', detail: 'Select optimal workers within budget constraints' },
  ],
}

// ============================================================================
// USAGE:
//
// const result = await workflow('ai-task-router', {
//   task: 'Review this code for security vulnerabilities',
//   context: '<code here>',
//   budget: 0.50,                        // optional, max cost in relative units
//   count: 3,                            // optional, number of workers (default 3)
//   prefer: 'quality',                   // optional: 'quality' | 'speed' | 'cost'
//   force_models: ['opus'],              // optional, always include these
//   exclude_models: ['gemini'],          // optional, never include these
// })
//
// Returns:
// {
//   workers: ['opus', 'sonnet', 'haiku'],
//   routing_reason: '...',
//   estimated_cost: 0.35,
//   complexity: 'complex',
//   category: 'security',
//   budget_remaining: 0.15
// }
// ============================================================================

// ============================================================================
// MODEL COST & SPECIALIZATION CONFIG
// ============================================================================

// Inline config providing cost and specialization data for each model.
// An external model-config.json is loaded as an override when present.

const DEFAULT_MODEL_CONFIG = {
  models: {
    opus: {
      id: 'opus',
      provider: 'anthropic',
      tier: 'flagship',
      cost_per_1k_input: 0.015,
      cost_per_1k_output: 0.075,
      relative_cost: 1.0,
      specializations: ['security', 'architecture', 'logic', 'synthesis', 'complex-reasoning', 'code-review'],
      complexity_fit: ['complex', 'critical'],
      speed: 'slow',
      quality: 1.0,
    },
    sonnet: {
      id: 'sonnet',
      provider: 'anthropic',
      tier: 'mid',
      cost_per_1k_input: 0.003,
      cost_per_1k_output: 0.015,
      relative_cost: 0.2,
      specializations: ['code-review', 'refactoring', 'documentation', 'testing', 'general'],
      complexity_fit: ['moderate', 'complex'],
      speed: 'medium',
      quality: 0.85,
    },
    haiku: {
      id: 'haiku',
      provider: 'anthropic',
      tier: 'fast',
      cost_per_1k_input: 0.00025,
      cost_per_1k_output: 0.00125,
      relative_cost: 0.04,
      specializations: ['formatting', 'classification', 'extraction', 'simple-qa', 'summarization'],
      complexity_fit: ['simple', 'moderate'],
      speed: 'fast',
      quality: 0.65,
    },
    gemini: {
      id: 'gemini',
      provider: 'google',
      tier: 'mid',
      cost_per_1k_input: 0.00035,
      cost_per_1k_output: 0.0014,
      relative_cost: 0.05,
      specializations: ['general', 'summarization', 'extraction', 'multimodal'],
      complexity_fit: ['simple', 'moderate'],
      speed: 'fast',
      quality: 0.75,
    },
  },

  // Task categories with keyword signals and default complexity
  task_categories: {
    security:       { keywords: ['security', 'vulnerability', 'CVE', 'injection', 'XSS', 'auth', 'CSRF', 'SSRF'], default_complexity: 'complex' },
    architecture:   { keywords: ['architecture', 'design', 'pattern', 'microservice', 'scalability', 'system design'], default_complexity: 'complex' },
    'code-review':  { keywords: ['review', 'code review', 'bug', 'defect', 'correctness', 'lint'], default_complexity: 'moderate' },
    refactoring:    { keywords: ['refactor', 'simplify', 'clean', 'extract', 'rename', 'reorganize'], default_complexity: 'moderate' },
    testing:        { keywords: ['test', 'spec', 'coverage', 'unit test', 'integration test', 'e2e'], default_complexity: 'moderate' },
    documentation:  { keywords: ['document', 'readme', 'jsdoc', 'docstring', 'comment', 'explain'], default_complexity: 'simple' },
    formatting:     { keywords: ['format', 'style', 'lint', 'prettier', 'indent'], default_complexity: 'simple' },
    classification: { keywords: ['classify', 'categorize', 'label', 'sort', 'triage'], default_complexity: 'simple' },
    extraction:     { keywords: ['extract', 'parse', 'scrape', 'pull out', 'identify'], default_complexity: 'simple' },
    summarization:  { keywords: ['summarize', 'summary', 'tldr', 'brief', 'overview'], default_complexity: 'simple' },
    logic:          { keywords: ['logic', 'algorithm', 'optimize', 'performance', 'complexity', 'concurrent'], default_complexity: 'complex' },
    synthesis:      { keywords: ['synthesize', 'combine', 'merge', 'consensus', 'arbiter'], default_complexity: 'complex' },
    general:        { keywords: [], default_complexity: 'moderate' },
  },

  // Complexity tiers controlling budget allocation and quality floors
  complexity_tiers: {
    simple:   { max_cost_multiplier: 0.1, preferred_tier: 'fast', min_quality: 0.5 },
    moderate: { max_cost_multiplier: 0.4, preferred_tier: 'mid', min_quality: 0.7 },
    complex:  { max_cost_multiplier: 0.8, preferred_tier: 'flagship', min_quality: 0.85 },
    critical: { max_cost_multiplier: 1.0, preferred_tier: 'flagship', min_quality: 0.95 },
  },
}

// ============================================================================
// LOAD EXTERNAL CONFIG OVERRIDE (if present)
// ============================================================================

function loadModelConfig() {
  try {
    const fs = require('fs')
    const configPath = '~/.claude/repos/claude-global-skills/model-config.json'
    const raw = fs.readFileSync(configPath, 'utf-8')
    const external = JSON.parse(raw)
    // Merge: external overrides defaults per-model
    const merged = { ...DEFAULT_MODEL_CONFIG }
    if (external.models) {
      merged.models = { ...merged.models }
      for (const [id, overrides] of Object.entries(external.models)) {
        merged.models[id] = { ...(merged.models[id] || {}), ...overrides, id }
      }
    }
    if (external.task_categories) {
      merged.task_categories = { ...merged.task_categories, ...external.task_categories }
    }
    if (external.complexity_tiers) {
      merged.complexity_tiers = { ...merged.complexity_tiers, ...external.complexity_tiers }
    }
    return merged
  } catch (_err) {
    // No external config or parse error; use defaults
    return DEFAULT_MODEL_CONFIG
  }
}

// ============================================================================
// LOAD PERFORMANCE TRACKER DATA (wraps SmartModelSelector from model-performance.js)
// ============================================================================

function loadPerformanceData() {
  try {
    const fs = require('fs')
    const dataPath = '~/.claude/repos/claude-global-skills/memory/model-performance.json'
    const raw = fs.readFileSync(dataPath, 'utf-8')
    return JSON.parse(raw)
  } catch (_err) {
    return null
  }
}

/**
 * Wraps SmartModelSelector from shared/model-performance.js.
 * Instantiates a ModelPerformanceTracker, hydrates it from stored JSON,
 * and returns a SmartModelSelector ready for querying.
 *
 * Returns null if no performance data is available.
 */
function buildSmartSelector(performanceData) {
  if (!performanceData) return null

  try {
    // Reconstruct tracker state from stored JSON
    // The tracker stores { tasks, models, taskTypes } which we can query directly
    return {
      getBestModel(taskType) {
        const models = performanceData.models || {}
        const candidates = []

        for (const [model, stats] of Object.entries(models)) {
          const taskStats = stats.taskTypes && stats.taskTypes[taskType]
          if (!taskStats || taskStats.count < 3) continue

          candidates.push({
            model,
            score: taskStats.score || 0,
            accuracy: taskStats.avgAccuracy || 0,
            consensus: taskStats.avgConsensus || 0,
            count: taskStats.count,
          })
        }

        if (candidates.length === 0) return null

        candidates.sort((a, b) => b.score - a.score)
        return {
          recommended: candidates[0].model,
          score: candidates[0].score,
          alternatives: candidates.slice(1, 3).map(c => c.model),
        }
      },

      getModelScore(modelId, taskType) {
        const models = performanceData.models || {}
        const stats = models[modelId]
        if (!stats) return 0
        const taskStats = stats.taskTypes && stats.taskTypes[taskType]
        if (!taskStats || taskStats.count < 1) return 0
        return taskStats.score || 0
      },
    }
  } catch (_err) {
    return null
  }
}

// ============================================================================
// TASK CLASSIFIER
// ============================================================================

function classifyTask(taskText, contextText, config) {
  const combined = `${taskText} ${contextText}`.toLowerCase()

  // Detect category by keyword matching
  let bestCategory = 'general'
  let bestScore = 0

  for (const [category, info] of Object.entries(config.task_categories)) {
    if (!info.keywords || info.keywords.length === 0) continue
    let score = 0
    for (const kw of info.keywords) {
      if (combined.includes(kw.toLowerCase())) {
        score += 1
      }
    }
    if (score > bestScore) {
      bestScore = score
      bestCategory = category
    }
  }

  // Detect complexity via heuristics
  const categoryInfo = config.task_categories[bestCategory] || config.task_categories.general
  let complexity = categoryInfo.default_complexity || 'moderate'

  // Override complexity based on signals in the text
  const complexSignals = ['critical', 'production', 'security', 'exploit', 'vulnerability',
                          'concurrent', 'race condition', 'distributed', 'at scale']
  const simpleSignals = ['simple', 'trivial', 'quick', 'basic', 'format', 'rename',
                         'typo', 'whitespace', 'indent']

  let complexScore = 0
  let simpleScore = 0
  for (const sig of complexSignals) {
    if (combined.includes(sig)) complexScore++
  }
  for (const sig of simpleSignals) {
    if (combined.includes(sig)) simpleScore++
  }

  if (complexScore >= 2) complexity = 'critical'
  else if (complexScore >= 1 && complexity !== 'complex') complexity = 'complex'
  if (simpleScore >= 2 && complexScore === 0) complexity = 'simple'

  // Factor in context length as a complexity signal
  const contextLength = (contextText || '').length
  if (contextLength > 10000 && complexity === 'simple') complexity = 'moderate'
  if (contextLength > 50000 && complexity !== 'critical') complexity = 'complex'

  return {
    category: bestCategory,
    complexity,
    keyword_hits: bestScore,
    complex_signals: complexScore,
    simple_signals: simpleScore,
    context_length: contextLength,
  }
}

// ============================================================================
// selectWorkers - MAIN ROUTING FUNCTION
// ============================================================================

function selectWorkers(taskContext, budget, config, performanceData) {
  const {
    task = '',
    context = '',
    count = 3,
    prefer = 'quality',   // 'quality' | 'speed' | 'cost'
    force_models = [],
    exclude_models = [],
  } = taskContext

  // Step 1: Classify the task
  const classification = classifyTask(task, context, config)

  // Step 2: Build smart selector from performance history
  const smartSelector = buildSmartSelector(performanceData)

  // Step 3: Get all candidate models
  const allModels = Object.values(config.models)
    .filter(m => !exclude_models.includes(m.id))

  // Step 4: Score each model for this task
  const scored = allModels.map(model => {
    let score = 0

    // Specialization match (0-40 points)
    if (model.specializations && model.specializations.includes(classification.category)) {
      score += 40
    } else if (model.specializations && model.specializations.includes('general')) {
      score += 10
    }

    // Complexity fit (0-30 points)
    if (model.complexity_fit && model.complexity_fit.includes(classification.complexity)) {
      score += 30
    }

    // Quality score (0-20 points)
    score += (model.quality || 0.5) * 20

    // Preference adjustments
    if (prefer === 'speed') {
      if (model.speed === 'fast') score += 25
      else if (model.speed === 'medium') score += 10
      else score -= 10
    } else if (prefer === 'cost') {
      // Invert cost: cheaper models score higher
      score += (1 - (model.relative_cost || 0.5)) * 25
    } else {
      // quality preference: boost high-quality models
      score += (model.quality || 0.5) * 15
    }

    // Historical performance bonus via SmartModelSelector wrapper (up to 20 points)
    if (smartSelector) {
      const perfScore = smartSelector.getModelScore(model.id, classification.category)
      if (perfScore > 0) {
        score += perfScore * 20
      }
    }

    return {
      model: model.id,
      score,
      cost: model.relative_cost || 0.5,
      tier: model.tier,
      quality: model.quality || 0.5,
    }
  })

  // Step 5: Sort by score descending
  scored.sort((a, b) => b.score - a.score)

  // Step 6: Select within budget
  const selected = []
  let totalCost = 0
  const effectiveBudget = budget || Infinity

  // Always include forced models first
  for (const forcedId of force_models) {
    const model = scored.find(m => m.model === forcedId)
    if (model && !selected.find(s => s.model === forcedId)) {
      selected.push(model)
      totalCost += model.cost
    }
  }

  // Fill remaining slots from scored list
  for (const candidate of scored) {
    if (selected.length >= count) break
    if (selected.find(s => s.model === candidate.model)) continue

    const newTotal = totalCost + candidate.cost
    if (budget && newTotal > effectiveBudget) {
      // Would exceed budget - skip and try cheaper alternatives
      continue
    }

    selected.push(candidate)
    totalCost += candidate.cost
  }

  // Step 7: If budget too tight and we have fewer than requested, backfill with cheapest
  if (selected.length < count && selected.length < allModels.length) {
    const cheapest = scored
      .filter(m => !selected.find(s => s.model === m.model))
      .sort((a, b) => a.cost - b.cost)

    for (const cheap of cheapest) {
      if (selected.length >= count) break
      selected.push(cheap)
      totalCost += cheap.cost
    }
  }

  // Step 8: Build routing explanation
  const complexityLabel = classification.complexity
  let routingReason = ''

  if (complexityLabel === 'simple') {
    routingReason = `Simple ${classification.category} task - prioritized fast/cheap models (e.g., Haiku)`
  } else if (complexityLabel === 'critical') {
    routingReason = `Critical ${classification.category} task - prioritized flagship models (Opus) for maximum quality`
  } else if (complexityLabel === 'complex') {
    routingReason = `Complex ${classification.category} task - selected high-quality models (Opus preferred) with specialization match`
  } else {
    routingReason = `Moderate ${classification.category} task - balanced model selection`
  }

  if (prefer !== 'quality') {
    routingReason += ` (optimized for ${prefer})`
  }

  if (budget && totalCost > effectiveBudget) {
    routingReason += ` [WARNING: estimated cost ${totalCost.toFixed(2)} exceeds budget ${effectiveBudget.toFixed(2)}]`
  }

  // Note from SmartModelSelector if it had a recommendation
  if (smartSelector) {
    const bestFromHistory = smartSelector.getBestModel(classification.category)
    if (bestFromHistory) {
      routingReason += ` [Performance data recommends ${bestFromHistory.recommended} for ${classification.category}]`
    }
  }

  return {
    models: selected.map(s => s.model),
    routing_reason: routingReason,
    estimated_cost: totalCost,
    complexity: classification.complexity,
    category: classification.category,
    budget_remaining: budget ? Math.max(0, effectiveBudget - totalCost) : null,
    classification,
    model_scores: selected.map(s => ({ model: s.model, score: s.score, cost: s.cost })),
  }
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

const task = args.task || (typeof args === 'string' ? args : null)
const context = args.context || ''
let budgetRaw = args.budget || null
// Convert string budget to number
const budgetMap = { low: 0.01, medium: 0.05, high: 0.20, unlimited: null }
const budget = typeof budgetRaw === "string" ? (budgetMap[budgetRaw] || null) : budgetRaw
const count = args.count || 3
const prefer = args.prefer || 'quality'
const forceModels = args.force_models || []
const excludeModels = args.exclude_models || []

if (!task) {
  log('ERROR: No task provided')
  log('')
  log('Usage: workflow("ai-task-router", { task: "...", budget: 0.50 })')
  log('')
  log('Options:')
  log('  task            - The task description (required)')
  log('  context         - Additional context (code, docs, etc.)')
  log('  budget          - Max cost budget as relative units (optional)')
  log('  count           - Number of workers to select (default: 3)')
  log('  prefer          - "quality" | "speed" | "cost" (default: "quality")')
  log('  force_models    - Array of models to always include')
  log('  exclude_models  - Array of models to never include')
  return { error: 'No task provided' }
}

// PHASE 1: Classify
phase('Classify')

const config = loadModelConfig()
const performanceData = loadPerformanceData()

log('='.repeat(60))
log('DYNAMIC TASK ROUTER')
log('='.repeat(60))
log(`Task: ${task.substring(0, 100)}${task.length > 100 ? '...' : ''}`)
log(`Budget: ${typeof budget === "number" ? budget.toFixed(2) : budget || "unlimited"}`)
log(`Preference: ${prefer}`)
log(`Requested workers: ${count}`)
log('')

// PHASE 2: Load Config
phase('Load Config')

const modelCount = Object.keys(config.models).length
log(`Loaded ${modelCount} model configurations`)

if (performanceData) {
  const trackedModels = Object.keys(performanceData.models || {}).length
  log(`Loaded performance data for ${trackedModels} models`)
} else {
  log('No historical performance data available (using defaults)')
}
log('')

// PHASE 3: Route
phase('Route')

const result = selectWorkers(
  { task, context, count, prefer, force_models: forceModels, exclude_models: excludeModels },
  budget,
  config,
  performanceData
)

log(`Category: ${result.category}`)
log(`Complexity: ${result.complexity}`)
log(`Selected workers: ${result.workers.join(', ')}`)
log(`Estimated cost: ${result.estimated_cost.toFixed(3)} relative units`)
if (budget) {
  log(`Budget remaining: ${result.budget_remaining.toFixed(3)}`)
}
log(`Routing reason: ${result.routing_reason}`)
log('')

log('Model Scores:')
for (const ms of result.model_scores) {
  log(`  ${ms.model}: score=${ms.score.toFixed(1)}, cost=${ms.cost.toFixed(3)}`)
}

log('')
log('='.repeat(60))
log('ROUTING COMPLETE')
log('='.repeat(60))

return result