export const meta = {
  name: 'ai-uncertainty-analysis',
  description: 'Uncertainty quantification: epistemic (model disagreement) vs aleatoric (task ambiguity)',
  whenToUse: 'When you need to quantify confidence, identify disagreement sources, and assess decision reliability',
  phases: [
    { title: 'Get Arbiter', detail: 'Determine next arbiter via rotation' },
    { title: 'Workers', detail: 'Parallel execution with hedging detection' },
    { title: 'Epistemic Analysis', detail: 'Compute inter-model variance and disagreement' },
    { title: 'Aleatoric Analysis', detail: 'Detect intra-model hedging and ambiguity' },
    { title: 'Synthesis', detail: 'Generate UncertaintyReport with recommendations' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// USAGE:
// const result = await workflow('ai-uncertainty-analysis', {
//   task: 'Classify this image as cat or dog',
//   context: imageData,
//   schema: { type: 'object', properties: { classification: { type: 'string' } } },
//   models: ['opus', 'sonnet', 'haiku'],
// })

// ============================================================================
// UNCERTAINTY REPORT DATA STRUCTURE
// ============================================================================

function createUncertaintyReport() {
  return {
    task_summary: '',
    timestamp: args?._timestamp || 'timestamp-at-runtime',

    epistemic: {
      type: 'inter_model_variance',
      description: 'Uncertainty due to model disagreement',
      model_count: 0,
      agreement_score: 0,           // 0-100: how much models agree
      variance_magnitude: 0,         // variance of model outputs
      disagreement_patterns: [],     // list of disagreement clusters
      consensus_strength: 'low',     // low, medium, high
      conflicting_models: [],        // pairs with max disagreement
    },

    aleatoric: {
      type: 'intra_model_hedging',
      description: 'Uncertainty due to task ambiguity and hedging',
      hedging_indicators: [],        // list of hedging patterns found
      total_hedging_score: 0,        // 0-100: avg hedging across models
      ambiguity_signals: [],         // specific ambiguity detections
      task_clarity: 'low',           // low, medium, high
      uncertain_terms: [],           // words/phrases indicating uncertainty
    },

    aggregate: {
      total_uncertainty: 0,          // combined epistemic + aleatoric (0-100)
      decision_reliability: 'low',   // low, medium, high
      recommendation: '',            // actionable guidance
      risk_level: 'high',            // high, medium, low
    },

    worker_details: {
      count: 0,
      responses: [],                 // full worker responses with confidence
      avg_confidence: 0,
      confidence_range: { min: 0, max: 0 },
    },

    model_specific: {},              // per-model analysis
  }
}

// ============================================================================
// HEDGING DETECTION: Find uncertainty signals in text
// ============================================================================

function detectHedgingPatterns(text, model_name) {
  if (!text) return { score: 0, indicators: [] }

  const text_lower = text.toLowerCase()

  // Hedging keywords and their weights
  const hedging_patterns = [
    { pattern: /\b(might|may|could|possibly|perhaps|probably)\b/gi, weight: 0.6, category: 'possibility' },
    { pattern: /\b(somewhat|relatively|fairly|rather|quite|somewhat)\b/gi, weight: 0.5, category: 'mitigation' },
    { pattern: /\b(seems|appears|suggests|indicates|tends to)\b/gi, weight: 0.7, category: 'observation' },
    { pattern: /\b(uncertain|ambiguous|unclear|unclear|difficult to determine)\b/gi, weight: 0.9, category: 'explicit_uncertainty' },
    { pattern: /\b(in my opinion|i think|it seems|arguably|debatable)\b/gi, weight: 0.8, category: 'opinion' },
    { pattern: /\b(depends on|depends|varies|can vary|contingent)\b/gi, weight: 0.8, category: 'contingency' },
    { pattern: /\b(with caveats|caveat|exception|unless|except)\b/gi, weight: 0.7, category: 'caveats' },
    { pattern: /\?\s*$|^\?/gm, weight: 0.9, category: 'interrogative' },
  ]

  let total_weight = 0
  let match_count = 0
  const found_indicators = []

  for (const { pattern, weight, category } of hedging_patterns) {
    const matches = text_lower.match(pattern)
    if (matches) {
      match_count += matches.length
      total_weight += matches.length * weight
      found_indicators.push({
        category,
        count: matches.length,
        examples: matches.slice(0, 3)
      })
    }
  }

  // Normalize hedging score (0-100)
  const hedging_score = Math.min(100, (match_count / Math.max(text.split(/\s+/).length / 10, 1)) * 100)

  return {
    score: Math.round(hedging_score),
    indicator_count: match_count,
    indicators: found_indicators,
  }
}

// ============================================================================
// EPISTEMIC UNCERTAINTY: Inter-model variance
// ============================================================================

function analyzeEpistemicUncertainty(worker_responses, schema) {
  const count = worker_responses.length

  if (count < 2) {
    return {
      model_count: count,
      agreement_score: 100,
      variance_magnitude: 0,
      disagreement_patterns: [],
      consensus_strength: 'perfect',
      conflicting_models: [],
    }
  }

  // Extract answer portions from responses
  const answers = worker_responses.map((w, i) => ({
    model: w.model || `worker_${i}`,
    answer: JSON.stringify(w.answer || w.result || w),
    confidence: w.confidence || 50,
  }))

  // Compute pairwise disagreement
  const disagreements = []
  for (let i = 0; i < answers.length; i++) {
    for (let j = i + 1; j < answers.length; j++) {
      const a1 = answers[i]
      const a2 = answers[j]

      // Simple string similarity (edit distance normalized)
      const similarity = computeStringSimilarity(a1.answer, a2.answer)
      const disagreement = 1 - similarity

      disagreements.push({
        model_1: a1.model,
        model_2: a2.model,
        disagreement: disagreement,
        confidence_diff: Math.abs(a1.confidence - a2.confidence),
      })
    }
  }

  // Compute statistics
  const avg_disagreement = disagreements.length > 0
    ? disagreements.reduce((sum, d) => sum + d.disagreement, 0) / disagreements.length
    : 0

  const agreement_score = Math.max(0, Math.min(100, Math.round((1 - avg_disagreement) * 100)))

  // Find maximum disagreement pairs (conflicting models)
  const sorted_disagreements = [...disagreements].sort((a, b) => b.disagreement - a.disagreement)
  const conflicting_models = sorted_disagreements.slice(0, 3).map(d => ({
    pair: [d.model_1, d.model_2],
    disagreement_level: Math.round(d.disagreement * 100),
    confidence_gap: d.confidence_diff,
  }))

  // Determine consensus strength
  let consensus_strength = 'high'
  if (agreement_score < 40) consensus_strength = 'low'
  else if (agreement_score < 70) consensus_strength = 'medium'

  // Identify disagreement clusters/patterns
  const disagreement_patterns = []
  if (agreement_score < 60) {
    disagreement_patterns.push({
      pattern: 'high_variance',
      description: 'Models produce significantly different answers',
      severity: agreement_score < 40 ? 'critical' : 'moderate',
    })
  }

  return {
    model_count: count,
    agreement_score,
    variance_magnitude: Math.round(avg_disagreement * 100),
    disagreement_patterns,
    consensus_strength,
    conflicting_models,
  }
}

// ============================================================================
// ALEATORIC UNCERTAINTY: Intra-model hedging
// ============================================================================

function analyzeAleatoryUncertainty(worker_responses) {
  const hedging_analyses = worker_responses.map((w, i) => ({
    model: w.model || `worker_${i}`,
    text: JSON.stringify(w, null, 2),
    confidence: w.confidence || 50,
  }))

  const all_hedging = []
  const all_uncertain_terms = new Set()

  for (const analysis of hedging_analyses) {
    const hedging = detectHedgingPatterns(analysis.text, analysis.model)
    all_hedging.push({
      model: analysis.model,
      score: hedging.score,
      indicators: hedging.indicators,
    })

    // Collect uncertain terms
    hedging.indicators.forEach(ind => {
      ind.examples?.forEach(term => all_uncertain_terms.add(term))
    })
  }

  const avg_hedging = all_hedging.length > 0
    ? all_hedging.reduce((sum, h) => sum + h.score, 0) / all_hedging.length
    : 0

  // Identify ambiguity signals
  const ambiguity_signals = []

  // High average hedging indicates task ambiguity
  if (avg_hedging > 60) {
    ambiguity_signals.push({
      signal: 'high_hedging_prevalence',
      description: 'Multiple models hedge their answers, indicating task ambiguity',
      confidence: avg_hedging,
    })
  }

  // Variance in hedging across models
  if (all_hedging.length > 1) {
    const hedging_scores = all_hedging.map(h => h.score)
    const max_hedging = Math.max(...hedging_scores)
    const min_hedging = Math.min(...hedging_scores)

    if (max_hedging - min_hedging > 40) {
      ambiguity_signals.push({
        signal: 'hedging_variance',
        description: 'Models have different levels of confidence/uncertainty',
        confidence: Math.round((max_hedging - min_hedging) / 100 * 100),
      })
    }
  }

  // Determine task clarity
  let task_clarity = 'high'
  if (avg_hedging > 60) task_clarity = 'low'
  else if (avg_hedging > 40) task_clarity = 'medium'

  return {
    hedging_indicators: all_hedging,
    total_hedging_score: Math.round(avg_hedging),
    ambiguity_signals,
    task_clarity,
    uncertain_terms: Array.from(all_uncertain_terms).slice(0, 10),
  }
}

// ============================================================================
// STRING SIMILARITY: Compute Levenshtein-based similarity
// ============================================================================

function computeStringSimilarity(s1, s2) {
  const longer = s1.length > s2.length ? s1 : s2
  const shorter = s1.length > s2.length ? s2 : s1

  if (longer.length === 0) return 1.0

  const editDistance = computeEditDistance(longer, shorter)
  return (longer.length - editDistance) / longer.length
}

function computeEditDistance(s1, s2) {
  const costs = []
  for (let i = 0; i <= s1.length; i++) {
    let lastValue = i
    for (let j = 0; j <= s2.length; j++) {
      if (i === 0) {
        costs[j] = j
      } else if (j > 0) {
        let newValue = costs[j - 1]
        if (s1.charAt(i - 1) !== s2.charAt(j - 1)) {
          newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1
        }
        costs[j - 1] = lastValue
        lastValue = newValue
      }
    }
    if (i > 0) costs[s2.length] = lastValue
  }
  return costs[s2.length]
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

const task = args.task || args
const context = args.context || ''
const budget = args.budget || 'medium'
const models = args.models || null
const schema = args.schema || {
  type: 'object',
  properties: {
    answer: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 100 }
  }
}

if (!task) {
  log('No task provided')
  log('Usage: workflow("ai-uncertainty-analysis", { task: "...", context: "...", schema: {...} })')
  return { error: 'No task provided' }
}

log('='.repeat(70))
log('UNCERTAINTY QUANTIFICATION ANALYSIS')
log('='.repeat(70))
log(`Task: ${task.substring(0, 100)}${task.length > 100 ? '...' : ''}`)
log('')

// PHASE 0: Get next arbiter from rotation
phase('Get Arbiter')

const arbiterChoice = await workflow('get-next-arbiter', { taskType: 'uncertainty_analysis' })
log(`Arbiter for this run: ${arbiterChoice.arbiter}`)

// PHASE 1: Workers execute in parallel
phase('Workers')

// Determine worker models
let workerModels = models
if (!workerModels) {
  const routerResult = await workflow('ai-task-router', { task, budget })
  if (routerResult.error) {
    log(`Task router error: ${routerResult.error}, falling back to default models`)
    workerModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
  } else {
    workerModels = routerResult.models || []
  }
}

log(`Workers executing (${workerModels.join(', ')})...`)

const workerPrompt = (model) => `[${model.toUpperCase()}] ${task}

${context ? `Context:\n${context}\n\n` : ''}

Provide your answer along with:
1. A confidence score (0-100) in your answer
2. Reasoning for your answer
3. Any caveats or uncertainties

Return structured data per schema.`

// Build worker tasks
const workerTasks = workerModels.map(model =>
  () => agent(workerPrompt(model), {
    label: `${model}-worker`,
    model: model,
    schema: {
      type: 'object',
      properties: {
        answer: schema.properties?.answer || { type: 'string' },
        confidence: { type: 'number', minimum: 0, maximum: 100 },
        reasoning: { type: 'string' },
        caveats: { type: 'array', items: { type: 'string' } }
      }
    }
  })
)

const workers = await parallel(workerTasks)

const validWorkers = workers.filter(Boolean)
log(`${validWorkers.length}/${workerTasks.length} workers completed`)

if (validWorkers.length === 0) {
  log('All workers failed')
  return { error: 'All workers failed', workers: [] }
}

// PHASE 2: Epistemic analysis
phase('Epistemic Analysis')

log('Computing inter-model variance and disagreement...')

const epistemicAnalysis = analyzeEpistemicUncertainty(validWorkers, schema)

log(`Agreement Score: ${epistemicAnalysis.agreement_score}%`)
log(`Consensus Strength: ${epistemicAnalysis.consensus_strength}`)
log(`Model Count: ${epistemicAnalysis.model_count}`)

if (epistemicAnalysis.conflicting_models.length > 0) {
  log('Top disagreement pairs:')
  epistemicAnalysis.conflicting_models.forEach((pair, i) => {
    log(`  ${i + 1}. ${pair.pair.join(' vs ')}: ${pair.disagreement_level}% disagreement`)
  })
}

// PHASE 3: Aleatoric analysis
phase('Aleatoric Analysis')

log('Detecting hedging patterns and task ambiguity...')

const aleatoryAnalysis = analyzeAleatoryUncertainty(validWorkers)

log(`Average Hedging Score: ${aleatoryAnalysis.total_hedging_score}%`)
log(`Task Clarity: ${aleatoryAnalysis.task_clarity}`)

if (aleatoryAnalysis.ambiguity_signals.length > 0) {
  log('Ambiguity signals detected:')
  aleatoryAnalysis.ambiguity_signals.forEach((signal, i) => {
    log(`  ${i + 1}. ${signal.signal}: ${signal.description}`)
  })
}

// PHASE 4: Synthesis with recommendations
phase('Synthesis')

log('Generating UncertaintyReport with recommendations...')

// Compute aggregate uncertainty
const total_uncertainty = (epistemicAnalysis.variance_magnitude + aleatoryAnalysis.total_hedging_score) / 2

// Determine decision reliability
let decision_reliability = 'high'
let risk_level = 'low'
let recommendation = ''

if (total_uncertainty > 70) {
  decision_reliability = 'low'
  risk_level = 'high'
  recommendation = 'High uncertainty detected. Consider: (1) Refining the task definition, (2) Gathering more context, (3) Running additional analysis with different models, (4) Breaking the task into smaller sub-questions.'
} else if (total_uncertainty > 50) {
  decision_reliability = 'medium'
  risk_level = 'medium'
  recommendation = 'Moderate uncertainty detected. Consider: (1) Reviewing model disagreements for insights, (2) Clarifying ambiguous aspects of the task, (3) Using the consensus as a best-estimate with appropriate caveats.'
} else {
  decision_reliability = 'high'
  risk_level = 'low'
  recommendation = 'Low uncertainty. Models are well-aligned and the task is clear. Proceed with confidence, documenting key assumptions.'
}

// Build the uncertainty report
const report = createUncertaintyReport()

report.task_summary = task.substring(0, 200)
report.timestamp = args?._timestamp || 'timestamp-at-runtime'

report.epistemic = epistemicAnalysis
report.aleatoric = aleatoryAnalysis

report.aggregate = {
  total_uncertainty: Math.round(total_uncertainty),
  decision_reliability,
  recommendation,
  risk_level,
}

report.worker_details = {
  count: validWorkers.length,
  responses: validWorkers.map(w => ({
    model: w.model,
    confidence: w.confidence || 50,
    reasoning: w.reasoning || '',
    caveats: w.caveats || [],
  })),
  avg_confidence: Math.round(
    validWorkers.reduce((sum, w) => sum + (w.confidence || 50), 0) / validWorkers.length
  ),
  confidence_range: {
    min: Math.min(...validWorkers.map(w => w.confidence || 50)),
    max: Math.max(...validWorkers.map(w => w.confidence || 50)),
  },
}

// Per-model analysis
report.model_specific = {}
for (const worker of validWorkers) {
  const hedging = detectHedgingPatterns(
    JSON.stringify(worker),
    worker.model
  )

  report.model_specific[worker.model] = {
    confidence: worker.confidence || 50,
    hedging_score: hedging.score,
    reasoning: worker.reasoning || '',
    caveats: worker.caveats || [],
  }
}

log('')
log('='.repeat(70))
log('UNCERTAINTY REPORT SUMMARY')
log('='.repeat(70))
log(`Total Uncertainty Score: ${report.aggregate.total_uncertainty}%`)
log(`Decision Reliability: ${report.aggregate.decision_reliability}`)
log(`Risk Level: ${report.aggregate.risk_level}`)
log('')
log(`Epistemic (Model Disagreement): ${report.epistemic.agreement_score}% agreement`)
log(`Aleatoric (Task Ambiguity): ${report.aleatoric.task_clarity}`)
log('')
log(`Recommendation: ${report.aggregate.recommendation}`)
log('')

// PHASE 5: Update arbiter state
phase('Update State')

await workflow('update-arbiter-state', { arbiter: arbiterChoice.arbiter, workflow_name: 'ai-uncertainty-analysis' })

return {
  status: 'success',
  uncertainty_report: report,
  workers: validWorkers,
  execution_id: `uncertainty_${args?._timestamp || 'exec'}_${Math.random().toString(36).substr(2, 9)}`,
}

}
