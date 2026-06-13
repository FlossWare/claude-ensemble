export const meta = {
  name: 'ai-reaction-tracker',
  description: 'Track and learn from AI behavioral reactions during execution -- confidence signals, uncertainty markers, self-corrections, disagreement patterns, and verbosity profiles',
  whenToUse: 'When you need to capture HOW AI models respond (not just what they produce), analyze behavioral patterns across executions, or improve model selection based on reaction history',
  phases: [
    { title: 'Load', detail: 'Load reaction history and configuration' },
    { title: 'Execute', detail: 'Run the requested action (record, analyze, query, report, learn)' },
    { title: 'Persist', detail: 'Save updated reaction data to disk' },
  ],
}

// ============================================================================
// USAGE:
//
// --- Record reaction signals from a workflow execution ---
// const result = await workflow('ai-reaction-tracker', {
//   action: 'record',
//   task: 'Review this code for security vulnerabilities',
//   task_type: 'security',
//   workflow: 'ai-consensus-weighted',
//   responses: [
//     { model: 'opus', text: '...full response text...', confidence: 92, latency_ms: 3200 },
//     { model: 'sonnet', text: '...full response text...', confidence: 78, latency_ms: 1800 },
//     { model: 'haiku', text: '...full response text...', confidence: 65, latency_ms: 800 },
//   ],
// })
//
// --- Analyze signals from text without recording ---
// const result = await workflow('ai-reaction-tracker', {
//   action: 'analyze',
//   text: '...model response text...',
//   model: 'opus',
//   task_type: 'code-review',
// })
//
// --- Query reaction history for a model/task type ---
// const result = await workflow('ai-reaction-tracker', {
//   action: 'query',
//   model: 'opus',            // optional filter
//   task_type: 'security',    // optional filter
//   limit: 50,                // optional, default 100
// })
//
// --- Generate reaction report ---
// const result = await workflow('ai-reaction-tracker', {
//   action: 'report',
//   model: 'opus',            // optional filter
//   task_type: 'security',    // optional filter
// })
//
// --- Derive learning signals for model selection ---
// const result = await workflow('ai-reaction-tracker', {
//   action: 'learn',
//   task_type: 'security',    // optional: focus on task type
// })
//
// --- Update outcome for a previous reaction record ---
// const result = await workflow('ai-reaction-tracker', {
//   action: 'update-outcome',
//   record_id: 'reaction_2026-06-13T...',
//   outcome: { success: true, quality_score: 0.92 },
// })
//
// --- Reset all reaction data ---
// const result = await workflow('ai-reaction-tracker', { action: 'reset' })
// ============================================================================

// ============================================================================
// INLINE SIGNAL EXTRACTION (from shared/reaction-signals.js)
//
// These functions are inlined because workflows cannot reliably import from
// shared/ at runtime. The canonical source is shared/reaction-signals.js.
// ============================================================================

function detectConfidenceSignals(text) {
  if (!text) return { score: 50, markers: [], raw_count: 0 }

  const highConfidencePatterns = [
    { pattern: /\b(definitely|certainly|absolutely|clearly|obviously|undoubtedly)\b/gi, weight: 90, category: 'certainty' },
    { pattern: /\b(i('m| am) (highly |very )?confident)\b/gi, weight: 85, category: 'self_assessed' },
    { pattern: /\b(without (a )?doubt|no question|unambiguous(ly)?)\b/gi, weight: 95, category: 'emphatic' },
    { pattern: /\b(the answer is|this is correct|the solution is)\b/gi, weight: 80, category: 'declarative' },
    { pattern: /\b(strongly recommend|must|should definitely)\b/gi, weight: 75, category: 'prescriptive' },
    { pattern: /\b(proven|established|well[-\s]known|documented)\b/gi, weight: 70, category: 'evidence_based' },
  ]

  const lowConfidencePatterns = [
    { pattern: /\b(i('m| am) not sure|i('m| am) unsure|uncertain)\b/gi, weight: -80, category: 'self_doubt' },
    { pattern: /\b(might|may|could|possibly|perhaps|probably)\b/gi, weight: -40, category: 'hedging' },
    { pattern: /\b(i think|i believe|in my (opinion|view))\b/gi, weight: -30, category: 'subjective' },
    { pattern: /\b(it depends|hard to say|difficult to determine)\b/gi, weight: -60, category: 'contingent' },
    { pattern: /\b(not entirely|partially|somewhat|to some extent)\b/gi, weight: -45, category: 'qualified' },
    { pattern: /\b(unclear|ambiguous|open to interpretation)\b/gi, weight: -70, category: 'admission' },
  ]

  const markers = []
  let weightedSum = 0
  let totalMatches = 0

  for (const { pattern, weight, category } of [...highConfidencePatterns, ...lowConfidencePatterns]) {
    const matches = text.match(pattern)
    if (matches) {
      totalMatches += matches.length
      weightedSum += matches.length * weight
      markers.push({ category, direction: weight > 0 ? 'high' : 'low', count: matches.length, examples: matches.slice(0, 3), weight })
    }
  }

  let score = 50
  if (totalMatches > 0) {
    const avgWeight = weightedSum / totalMatches
    score = Math.max(0, Math.min(100, 50 + (avgWeight / 2)))
  }

  return { score: Math.round(score), markers, raw_count: totalMatches, dominant_direction: score > 60 ? 'confident' : score < 40 ? 'uncertain' : 'neutral' }
}

function detectUncertaintyMarkers(text) {
  if (!text) return { score: 0, markers: [], density: 0 }

  const wordCount = text.split(/\s+/).length
  const patterns = [
    { regex: /\b(might|may|could)\s+(be|have|cause|result|lead)\b/gi, weight: 0.7, type: 'epistemic_hedge' },
    { regex: /\b(possibly|perhaps|conceivably|potentially)\b/gi, weight: 0.6, type: 'possibility' },
    { regex: /\b(likely|unlikely|probable|improbable)\b/gi, weight: 0.5, type: 'probability' },
    { regex: /\b(approximately|roughly|around|about)\b/gi, weight: 0.4, type: 'approximation' },
    { regex: /\b(sort of|kind of|more or less|to some degree)\b/gi, weight: 0.5, type: 'vague_qualifier' },
    { regex: /\b(it (seems|appears|looks) (like|as if|that))\b/gi, weight: 0.6, type: 'plausibility_shield' },
    { regex: /\b(as far as i know|to (my|the best of my) knowledge)\b/gi, weight: 0.7, type: 'knowledge_limit' },
    { regex: /\b(i('m| am) not (entirely |completely )?(sure|certain|confident))\b/gi, weight: 0.9, type: 'explicit_uncertainty' },
    { regex: /\b(assuming|provided that|depending on)\b/gi, weight: 0.5, type: 'conditional' },
    { regex: /\b(with (some |certain )?caveats?)\b/gi, weight: 0.6, type: 'caveat' },
  ]

  const markers = []
  let matchCount = 0

  for (const { regex, weight, type } of patterns) {
    const matches = text.match(regex)
    if (matches) {
      matchCount += matches.length
      markers.push({ type, count: matches.length, weight, examples: matches.slice(0, 2) })
    }
  }

  const density = wordCount > 0 ? (matchCount / wordCount) * 100 : 0
  const score = Math.min(100, Math.round(density * 15))

  return { score, markers, density: Math.round(density * 100) / 100, match_count: matchCount, word_count: wordCount }
}

function detectSelfCorrections(text) {
  if (!text) return { count: 0, corrections: [], severity: 'none' }

  const patterns = [
    { regex: /\b(actually|wait|correction|let me (correct|revise|reconsider))\b/gi, type: 'direct_correction', weight: 0.9 },
    { regex: /\b(on second thought|thinking about it (more|again|further))\b/gi, type: 'reconsideration', weight: 0.8 },
    { regex: /\b(i (was|am) wrong|my mistake|i misspoke|i should clarify)\b/gi, type: 'admission', weight: 1.0 },
    { regex: /\b(rather|instead|more accurately|to be (more )?precise)\b/gi, type: 'refinement', weight: 0.5 },
    { regex: /\b(let me rephrase|put (another|differently)|in other words)\b/gi, type: 'rephrasing', weight: 0.4 },
    { regex: /\b(upon (further |closer )?(review|inspection|analysis|reflection))\b/gi, type: 'deeper_analysis', weight: 0.7 },
    { regex: /\b(however|but|although|that said|on the other hand|nevertheless)\b/gi, type: 'self_contradiction', weight: 0.3 },
    { regex: /\b(scratch that|disregard|ignore (what i|the above|my previous))\b/gi, type: 'backtracking', weight: 1.0 },
  ]

  const corrections = []
  let totalWeight = 0

  for (const { regex, type, weight } of patterns) {
    const matches = text.match(regex)
    if (matches) {
      totalWeight += matches.length * weight
      corrections.push({ type, count: matches.length, weight, examples: matches.slice(0, 3) })
    }
  }

  const count = corrections.reduce((sum, c) => sum + c.count, 0)
  let severity = 'none'
  if (totalWeight >= 3.0) severity = 'high'
  else if (totalWeight >= 1.5) severity = 'moderate'
  else if (totalWeight > 0) severity = 'low'

  return { count, corrections, total_weight: Math.round(totalWeight * 100) / 100, severity }
}

function analyzeVerbosity(text) {
  if (!text) return { word_count: 0, char_count: 0, profile: 'empty', signals: [] }

  const wordCount = text.split(/\s+/).length
  const charCount = text.length
  const sentenceCount = (text.match(/[.!?]+/g) || []).length || 1
  const avgWordsPerSentence = wordCount / sentenceCount

  const codeBlocks = (text.match(/```[\s\S]*?```/g) || []).length
  const bulletPoints = (text.match(/^[\s]*[-*+]\s/gm) || []).length

  let profile = 'normal'
  const signals = []

  if (wordCount < 20) {
    profile = 'terse'
    signals.push({ signal: 'very_short_response', interpretation: 'Model was extremely brief -- may indicate high confidence or lack of engagement' })
  } else if (wordCount < 50) {
    profile = 'concise'
  } else if (wordCount > 1000) {
    profile = 'very_verbose'
    signals.push({ signal: 'very_long_response', interpretation: 'Extremely verbose -- possible uncertainty, hedging, or covering multiple angles' })
  } else if (wordCount > 500) {
    profile = 'verbose'
    signals.push({ signal: 'long_response', interpretation: 'Verbose answer -- may indicate complex reasoning or uncertainty' })
  }

  if (avgWordsPerSentence > 30) {
    signals.push({ signal: 'long_sentences', interpretation: 'Long average sentences -- possible hedging or qualification stacking' })
  }

  return { word_count: wordCount, char_count: charCount, sentence_count: sentenceCount, avg_words_per_sentence: Math.round(avgWordsPerSentence * 10) / 10, code_blocks: codeBlocks, bullet_points: bulletPoints, profile, signals }
}

function detectStructuralSignals(text) {
  if (!text) return { signals: [], caveat_count: 0, alternatives_offered: 0, qualification_depth: 0 }

  const signals = []

  const alternativePatterns = [
    /\b(alternatively|another (option|approach|way|possibility))\b/gi,
    /\b(you (could|might|may) (also|instead|alternatively))\b/gi,
    /\b(option \d|approach \d|alternative \d)\b/gi,
  ]

  let alternativesOffered = 0
  for (const pattern of alternativePatterns) {
    const matches = text.match(pattern)
    if (matches) alternativesOffered += matches.length
  }

  if (alternativesOffered > 0) {
    signals.push({
      type: 'alternatives_offered', count: alternativesOffered,
      interpretation: alternativesOffered > 3 ? 'Many alternatives -- model uncertain about best approach' : 'Some alternatives -- multiple viable paths seen',
    })
  }

  const caveatPatterns = [
    /\b(caveat|warning|note|important|caution|disclaimer|limitation)\s*:/gi,
    /\b(keep in mind|be aware|worth noting|important to note)\b/gi,
  ]

  let caveatCount = 0
  for (const pattern of caveatPatterns) {
    const matches = text.match(pattern)
    if (matches) caveatCount += matches.length
  }

  if (caveatCount > 0) {
    signals.push({ type: 'caveats', count: caveatCount, interpretation: caveatCount > 3 ? 'Heavy caveating -- substantial hedging' : 'Some caveats -- appropriate caution' })
  }

  const qualifications = text.match(/\b(although|however|but|though|while|whereas)\b/gi) || []
  const qualificationDepth = qualifications.length

  if (qualificationDepth > 4) {
    signals.push({ type: 'deep_qualification', count: qualificationDepth, interpretation: 'Deep qualification stacking -- heavily hedging position' })
  }

  const scopePatterns = [
    /\b(beyond (my|the) scope|outside (my|the) (expertise|knowledge))\b/gi,
    /\b(i (cannot|can't) (verify|confirm|guarantee))\b/gi,
  ]

  let scopeLimitations = 0
  for (const pattern of scopePatterns) {
    const matches = text.match(pattern)
    if (matches) scopeLimitations += matches.length
  }

  return { signals, caveat_count: caveatCount, alternatives_offered: alternativesOffered, qualification_depth: qualificationDepth, scope_limitations: scopeLimitations }
}

function extractReactionSignals(responseText, metadata = {}) {
  const text = typeof responseText === 'string' ? responseText : JSON.stringify(responseText, null, 2)

  const confidence = detectConfidenceSignals(text)
  const uncertainty = detectUncertaintyMarkers(text)
  const selfCorrections = detectSelfCorrections(text)
  const verbosity = analyzeVerbosity(text)
  const structural = detectStructuralSignals(text)

  const compositeScore = computeCompositeScore(confidence, uncertainty, selfCorrections, structural, metadata)
  const conflictScore = Math.abs(confidence.score - (100 - uncertainty.score))
  const overconfident = confidence.score > 70 && uncertainty.score > 40
  const wellCalibrated = Math.abs(confidence.score - (100 - uncertainty.score)) < 20

  return {
    model: metadata.model || 'unknown',
    task_type: metadata.task_type || 'unknown',
    timestamp: new Date().toISOString(),
    confidence, uncertainty, self_corrections: selfCorrections, verbosity, structural,
    composite_score: compositeScore, conflict_score: conflictScore, overconfident, well_calibrated: wellCalibrated,
    latency_ms: metadata.latency_ms || null,
    reported_confidence: metadata.reported_confidence || null,
    calibration_delta: metadata.reported_confidence != null ? Math.round(metadata.reported_confidence - compositeScore) : null,
  }
}

function computeCompositeScore(confidence, uncertainty, selfCorrections, structural, metadata) {
  let score = confidence.score * 0.35
  score += (100 - uncertainty.score) * 0.25
  const correctionPenalty = Math.min(30, selfCorrections.total_weight * 10)
  score += (100 - correctionPenalty) * 0.15
  const structuralPenalty = Math.min(30, (structural.alternatives_offered * 5 + structural.caveat_count * 3))
  score += (100 - structuralPenalty) * 0.15
  if (metadata.latency_ms) {
    const latencyFactor = metadata.latency_ms < 2000 ? 60 : metadata.latency_ms > 10000 ? 40 : 50
    score += latencyFactor * 0.10
  } else {
    score += 50 * 0.10
  }
  return Math.max(0, Math.min(100, Math.round(score)))
}

function computeDisagreementSignals(workerResponses) {
  if (!workerResponses || workerResponses.length < 2) {
    return { model_count: workerResponses?.length || 0, pairwise: [], polarization_index: 0, confidence_spread: 0, behavioral_agreement: 100, reaction_clusters: [] }
  }

  const signals = workerResponses.map(w => {
    if (w.signals) return w
    const text = w.text || JSON.stringify(w.answer || w, null, 2)
    return { ...w, signals: extractReactionSignals(text, { model: w.model }) }
  })

  const pairwise = []
  for (let i = 0; i < signals.length; i++) {
    for (let j = i + 1; j < signals.length; j++) {
      const s1 = signals[i].signals
      const s2 = signals[j].signals
      const confidenceDiff = Math.abs(s1.composite_score - s2.composite_score)
      const uncertaintyDiff = Math.abs(s1.uncertainty.score - s2.uncertainty.score)
      const correctionDiff = Math.abs(s1.self_corrections.count - s2.self_corrections.count)
      const behavioralDivergence = (confidenceDiff * 0.5 + uncertaintyDiff * 0.3 + correctionDiff * 10 * 0.2)
      pairwise.push({ models: [signals[i].model, signals[j].model], confidence_diff: confidenceDiff, uncertainty_diff: uncertaintyDiff, behavioral_divergence: Math.round(behavioralDivergence) })
    }
  }

  const composites = signals.map(s => s.signals.composite_score)
  const confidenceSpread = Math.max(...composites) - Math.min(...composites)
  const mean = composites.reduce((a, b) => a + b, 0) / composites.length
  const variance = composites.reduce((a, v) => a + Math.pow(v - mean, 2), 0) / composites.length
  const polarizationIndex = Math.min(100, Math.round(Math.sqrt(variance) * 2))

  const avgDivergence = pairwise.length > 0 ? pairwise.reduce((sum, p) => sum + p.behavioral_divergence, 0) / pairwise.length : 0
  const behavioralAgreement = Math.max(0, 100 - Math.round(avgDivergence))

  // Cluster by reaction profile
  const bands = { confident: [], neutral: [], uncertain: [] }
  for (const s of signals) {
    const score = s.signals.composite_score
    if (score >= 65) bands.confident.push(s.model)
    else if (score >= 40) bands.neutral.push(s.model)
    else bands.uncertain.push(s.model)
  }
  const clusters = []
  if (bands.confident.length > 0) clusters.push({ label: 'confident', models: bands.confident })
  if (bands.neutral.length > 0) clusters.push({ label: 'neutral', models: bands.neutral })
  if (bands.uncertain.length > 0) clusters.push({ label: 'uncertain', models: bands.uncertain })

  return { model_count: signals.length, pairwise, polarization_index: polarizationIndex, confidence_spread: confidenceSpread, behavioral_agreement: behavioralAgreement, reaction_clusters: clusters, per_model: signals.map(s => ({ model: s.model, composite: s.signals.composite_score, confidence: s.signals.confidence.score, uncertainty: s.signals.uncertainty.score })) }
}

function createReactionRecord(params) {
  const { task = '', task_type = 'unknown', workflow = 'unknown', worker_signals = [], disagreement = null, outcome = null } = params

  const avgComposite = worker_signals.length > 0 ? worker_signals.reduce((sum, s) => sum + s.composite_score, 0) / worker_signals.length : 0
  const avgUncertainty = worker_signals.length > 0 ? worker_signals.reduce((sum, s) => sum + s.uncertainty.score, 0) / worker_signals.length : 0
  const totalSelfCorrections = worker_signals.reduce((sum, s) => sum + s.self_corrections.count, 0)

  let estimatedDifficulty = 'moderate'
  if (avgUncertainty > 60 || totalSelfCorrections > 5) estimatedDifficulty = 'hard'
  else if (avgUncertainty > 40 || totalSelfCorrections > 2) estimatedDifficulty = 'moderate'
  else if (avgComposite > 70) estimatedDifficulty = 'easy'

  const calibrationEntries = worker_signals.filter(s => s.reported_confidence != null).map(s => ({
    model: s.model, reported: s.reported_confidence, behavioral: s.composite_score,
    delta: s.calibration_delta, calibration: Math.abs(s.calibration_delta) < 15 ? 'well_calibrated' : s.calibration_delta > 0 ? 'overconfident' : 'underconfident',
  }))

  const recordId = `reaction_${new Date().toISOString()}_${Math.random().toString(36).substr(2, 9)}`

  return {
    id: recordId,
    timestamp: new Date().toISOString(),
    task_summary: task.substring(0, 200),
    task_type, workflow,
    workers: worker_signals.map(s => ({
      model: s.model, composite_score: s.composite_score, confidence_score: s.confidence.score,
      uncertainty_score: s.uncertainty.score, self_correction_count: s.self_corrections.count,
      self_correction_severity: s.self_corrections.severity, verbosity_profile: s.verbosity.profile,
      word_count: s.verbosity.word_count, alternatives_offered: s.structural.alternatives_offered,
      caveat_count: s.structural.caveat_count, overconfident: s.overconfident, well_calibrated: s.well_calibrated,
      reported_confidence: s.reported_confidence, calibration_delta: s.calibration_delta, latency_ms: s.latency_ms,
    })),
    aggregate: {
      avg_composite_score: Math.round(avgComposite), avg_uncertainty: Math.round(avgUncertainty),
      total_self_corrections: totalSelfCorrections, estimated_difficulty: estimatedDifficulty,
      model_count: worker_signals.length,
    },
    disagreement: disagreement || { polarization_index: 0, behavioral_agreement: 100 },
    calibration: calibrationEntries,
    outcome: outcome || null,
  }
}

function deriveLearningSignals(reactionRecord) {
  const signals = []
  const modelPreferences = {}

  const workersByConfidence = [...reactionRecord.workers].sort((a, b) => b.composite_score - a.composite_score)
  if (workersByConfidence.length > 0) {
    signals.push({
      type: 'confidence_ranking', task_type: reactionRecord.task_type,
      ranking: workersByConfidence.map(w => ({ model: w.model, score: w.composite_score })),
      top_model: workersByConfidence[0].model,
      recommendation: `For ${reactionRecord.task_type} tasks, ${workersByConfidence[0].model} shows highest behavioral confidence (${workersByConfidence[0].composite_score})`,
    })
  }

  if (reactionRecord.aggregate.avg_uncertainty > 50) {
    signals.push({
      type: 'task_ambiguity', task_type: reactionRecord.task_type,
      avg_uncertainty: reactionRecord.aggregate.avg_uncertainty,
      recommendation: 'All models show high uncertainty -- task may be ambiguous. Consider using more workers or refining the task prompt.',
    })
  }

  if (reactionRecord.aggregate.total_self_corrections > 3) {
    signals.push({
      type: 'task_trickiness', task_type: reactionRecord.task_type,
      total_corrections: reactionRecord.aggregate.total_self_corrections,
      recommendation: 'Multiple self-corrections detected -- task has non-obvious complexities. Prefer flagship models.',
    })
  }

  for (const cal of reactionRecord.calibration) {
    if (cal.calibration === 'overconfident') {
      signals.push({
        type: 'model_overconfidence', model: cal.model, task_type: reactionRecord.task_type,
        delta: cal.delta, recommendation: `${cal.model} reports confidence ${cal.delta} points above behavioral signals for ${reactionRecord.task_type}. Deflate reported scores.`,
      })
    } else if (cal.calibration === 'underconfident') {
      signals.push({
        type: 'model_underconfidence', model: cal.model, task_type: reactionRecord.task_type,
        delta: cal.delta, recommendation: `${cal.model} reports confidence ${Math.abs(cal.delta)} points below behavioral signals for ${reactionRecord.task_type}. Inflate reported scores.`,
      })
    }
  }

  if (reactionRecord.disagreement && reactionRecord.disagreement.polarization_index > 40) {
    signals.push({
      type: 'model_polarization', task_type: reactionRecord.task_type,
      polarization: reactionRecord.disagreement.polarization_index,
      recommendation: 'Models are polarized in their reactions -- high disagreement. Use arbiter with access to all reasoning, or break task into sub-questions.',
    })
  }

  for (const worker of reactionRecord.workers) {
    modelPreferences[worker.model] = {
      composite_score: worker.composite_score, well_calibrated: worker.well_calibrated,
      overconfident: worker.overconfident, task_type: reactionRecord.task_type,
    }
  }

  return {
    signals, model_preferences: modelPreferences,
    task_assessment: {
      difficulty: reactionRecord.aggregate.estimated_difficulty,
      ambiguity: reactionRecord.aggregate.avg_uncertainty > 50 ? 'high' : reactionRecord.aggregate.avg_uncertainty > 30 ? 'moderate' : 'low',
      trickiness: reactionRecord.aggregate.total_self_corrections > 3 ? 'high' : reactionRecord.aggregate.total_self_corrections > 1 ? 'moderate' : 'low',
    },
  }
}

// ============================================================================
// DATA STORE
// ============================================================================

const REACTION_DATA_PATH = `${process.env.HOME}/.claude/repos/claude-global-skills/memory/reaction-data.json`

function loadReactionData() {
  try {
    const fs = require('fs')
    const raw = fs.readFileSync(REACTION_DATA_PATH, 'utf-8')
    return JSON.parse(raw)
  } catch (_err) {
    return {
      version: '1.0',
      created: new Date().toISOString(),
      updated: new Date().toISOString(),
      records: [],
      model_profiles: {},
      task_type_profiles: {},
      learning_signals: [],
    }
  }
}

function saveReactionData(data) {
  try {
    const fs = require('fs')
    const path = require('path')
    const dir = path.dirname(REACTION_DATA_PATH)
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }
    data.updated = new Date().toISOString()
    fs.writeFileSync(REACTION_DATA_PATH, JSON.stringify(data, null, 2))
    return true
  } catch (err) {
    return false
  }
}

// ============================================================================
// PROFILE AGGREGATION
// ============================================================================

/**
 * Update per-model and per-task-type aggregate profiles from a new record.
 */
function updateProfiles(data, record) {
  // Update model profiles
  for (const worker of record.workers) {
    const model = worker.model
    if (!data.model_profiles[model]) {
      data.model_profiles[model] = {
        total_observations: 0,
        task_types: {},
        avg_composite_score: 0,
        avg_uncertainty: 0,
        avg_calibration_delta: 0,
        overconfidence_rate: 0,
        self_correction_rate: 0,
      }
    }

    const profile = data.model_profiles[model]
    profile.total_observations++

    // Running averages
    const n = profile.total_observations
    profile.avg_composite_score = updateRunningAverage(profile.avg_composite_score, worker.composite_score, n)
    profile.avg_uncertainty = updateRunningAverage(profile.avg_uncertainty, worker.uncertainty_score, n)
    if (worker.calibration_delta != null) {
      profile.avg_calibration_delta = updateRunningAverage(profile.avg_calibration_delta, worker.calibration_delta, n)
    }

    // Rates
    const overconfidentCount = (profile.overconfidence_rate * (n - 1)) + (worker.overconfident ? 1 : 0)
    profile.overconfidence_rate = overconfidentCount / n

    const correctionCount = (profile.self_correction_rate * (n - 1)) + (worker.self_correction_count > 0 ? 1 : 0)
    profile.self_correction_rate = correctionCount / n

    // Per-task-type within model
    const taskType = record.task_type
    if (!profile.task_types[taskType]) {
      profile.task_types[taskType] = {
        count: 0, avg_composite: 0, avg_uncertainty: 0, avg_calibration_delta: 0,
      }
    }
    const tp = profile.task_types[taskType]
    tp.count++
    tp.avg_composite = updateRunningAverage(tp.avg_composite, worker.composite_score, tp.count)
    tp.avg_uncertainty = updateRunningAverage(tp.avg_uncertainty, worker.uncertainty_score, tp.count)
    if (worker.calibration_delta != null) {
      tp.avg_calibration_delta = updateRunningAverage(tp.avg_calibration_delta, worker.calibration_delta, tp.count)
    }
  }

  // Update task type profiles
  const taskType = record.task_type
  if (!data.task_type_profiles[taskType]) {
    data.task_type_profiles[taskType] = {
      total_records: 0,
      avg_composite: 0,
      avg_uncertainty: 0,
      avg_self_corrections: 0,
      avg_polarization: 0,
      difficulty_distribution: { easy: 0, moderate: 0, hard: 0 },
      best_model: null,
      best_model_score: 0,
    }
  }

  const ttp = data.task_type_profiles[taskType]
  ttp.total_records++
  ttp.avg_composite = updateRunningAverage(ttp.avg_composite, record.aggregate.avg_composite_score, ttp.total_records)
  ttp.avg_uncertainty = updateRunningAverage(ttp.avg_uncertainty, record.aggregate.avg_uncertainty, ttp.total_records)
  ttp.avg_self_corrections = updateRunningAverage(ttp.avg_self_corrections, record.aggregate.total_self_corrections, ttp.total_records)
  if (record.disagreement) {
    ttp.avg_polarization = updateRunningAverage(ttp.avg_polarization, record.disagreement.polarization_index, ttp.total_records)
  }

  ttp.difficulty_distribution[record.aggregate.estimated_difficulty] = (ttp.difficulty_distribution[record.aggregate.estimated_difficulty] || 0) + 1

  // Update best model for this task type
  for (const worker of record.workers) {
    if (worker.composite_score > ttp.best_model_score) {
      ttp.best_model = worker.model
      ttp.best_model_score = worker.composite_score
    }
  }
}

function updateRunningAverage(currentAvg, newValue, count) {
  return (currentAvg * (count - 1) + newValue) / count
}

// ============================================================================
// ACTION HANDLERS
// ============================================================================

function handleRecord(data, actionArgs) {
  const responses = actionArgs.responses || []
  const task = actionArgs.task || ''
  const taskType = actionArgs.task_type || 'unknown'
  const workflowName = actionArgs.workflow || 'unknown'

  if (responses.length === 0) {
    return { error: 'No responses provided. Provide an array of { model, text, confidence?, latency_ms? }.' }
  }

  log(`Extracting reaction signals from ${responses.length} responses...`)

  // Extract signals from each response
  const workerSignals = responses.map(r => {
    const text = r.text || JSON.stringify(r.answer || r, null, 2)
    return extractReactionSignals(text, {
      model: r.model || 'unknown',
      task_type: taskType,
      latency_ms: r.latency_ms || null,
      reported_confidence: r.confidence || null,
    })
  })

  // Log per-model signals
  for (const sig of workerSignals) {
    log(`  ${sig.model}: composite=${sig.composite_score}, confidence=${sig.confidence.score}, uncertainty=${sig.uncertainty.score}, corrections=${sig.self_corrections.count}`)
    if (sig.calibration_delta != null) {
      log(`    calibration delta: ${sig.calibration_delta > 0 ? '+' : ''}${sig.calibration_delta} (${sig.calibration_delta > 15 ? 'OVERCONFIDENT' : sig.calibration_delta < -15 ? 'UNDERCONFIDENT' : 'well calibrated'})`)
    }
  }

  // Compute disagreement
  const disagreement = computeDisagreementSignals(
    responses.map((r, i) => ({ model: r.model, text: r.text, answer: r.answer, signals: workerSignals[i] }))
  )

  log(`  Disagreement: polarization=${disagreement.polarization_index}, behavioral_agreement=${disagreement.behavioral_agreement}%`)

  // Create record
  const record = createReactionRecord({
    task, task_type: taskType, workflow: workflowName,
    worker_signals: workerSignals, disagreement,
  })

  // Update profiles
  updateProfiles(data, record)

  // Store record (keep last 500 records)
  data.records.push(record)
  if (data.records.length > 500) {
    data.records = data.records.slice(-500)
  }

  // Derive and store learning signals
  const learning = deriveLearningSignals(record)
  data.learning_signals.push({
    timestamp: record.timestamp,
    task_type: taskType,
    signals: learning.signals,
    task_assessment: learning.task_assessment,
  })
  if (data.learning_signals.length > 200) {
    data.learning_signals = data.learning_signals.slice(-200)
  }

  log('')
  log(`Estimated task difficulty: ${record.aggregate.estimated_difficulty}`)
  log(`Learning signals derived: ${learning.signals.length}`)

  return {
    status: 'recorded',
    record_id: record.id,
    aggregate: record.aggregate,
    disagreement: {
      polarization_index: disagreement.polarization_index,
      behavioral_agreement: disagreement.behavioral_agreement,
    },
    calibration: record.calibration,
    learning_signals: learning.signals,
    task_assessment: learning.task_assessment,
  }
}

function handleAnalyze(actionArgs) {
  const text = actionArgs.text || ''
  const model = actionArgs.model || 'unknown'
  const taskType = actionArgs.task_type || 'unknown'
  const confidence = actionArgs.confidence || null
  const latencyMs = actionArgs.latency_ms || null

  if (!text) {
    return { error: 'No text provided for analysis.' }
  }

  log(`Analyzing reaction signals for ${model}...`)

  const signals = extractReactionSignals(text, {
    model, task_type: taskType,
    reported_confidence: confidence,
    latency_ms: latencyMs,
  })

  log(`  Composite score: ${signals.composite_score}`)
  log(`  Confidence: ${signals.confidence.score} (${signals.confidence.dominant_direction})`)
  log(`  Uncertainty: ${signals.uncertainty.score} (density: ${signals.uncertainty.density})`)
  log(`  Self-corrections: ${signals.self_corrections.count} (${signals.self_corrections.severity})`)
  log(`  Verbosity: ${signals.verbosity.profile} (${signals.verbosity.word_count} words)`)
  log(`  Alternatives offered: ${signals.structural.alternatives_offered}`)
  log(`  Caveats: ${signals.structural.caveat_count}`)

  if (signals.overconfident) {
    log(`  ** OVERCONFIDENT: high confidence language + high uncertainty markers`)
  }
  if (signals.well_calibrated) {
    log(`  Calibration: GOOD -- confidence language matches uncertainty absence`)
  }
  if (signals.calibration_delta != null) {
    log(`  Calibration delta: ${signals.calibration_delta > 0 ? '+' : ''}${signals.calibration_delta}`)
  }

  return {
    status: 'analyzed',
    signals,
  }
}

function handleQuery(data, actionArgs) {
  const model = actionArgs.model || null
  const taskType = actionArgs.task_type || null
  const limit = actionArgs.limit || 100

  let records = data.records

  if (model) {
    records = records.filter(r => r.workers.some(w => w.model === model))
  }
  if (taskType) {
    records = records.filter(r => r.task_type === taskType)
  }

  records = records.slice(-limit)

  log(`Found ${records.length} matching records`)

  // Compute query-level aggregates
  const allWorkers = records.flatMap(r => r.workers)
  const filteredWorkers = model ? allWorkers.filter(w => w.model === model) : allWorkers

  const avgComposite = filteredWorkers.length > 0
    ? filteredWorkers.reduce((sum, w) => sum + w.composite_score, 0) / filteredWorkers.length
    : 0
  const avgUncertainty = filteredWorkers.length > 0
    ? filteredWorkers.reduce((sum, w) => sum + w.uncertainty_score, 0) / filteredWorkers.length
    : 0

  return {
    status: 'queried',
    filters: { model, task_type: taskType, limit },
    record_count: records.length,
    aggregates: {
      avg_composite: Math.round(avgComposite),
      avg_uncertainty: Math.round(avgUncertainty),
      total_workers_analyzed: filteredWorkers.length,
    },
    records: records.map(r => ({
      id: r.id,
      timestamp: r.timestamp,
      task_type: r.task_type,
      workflow: r.workflow,
      aggregate: r.aggregate,
      workers: r.workers.map(w => ({ model: w.model, composite_score: w.composite_score, reported_confidence: w.reported_confidence, calibration_delta: w.calibration_delta })),
    })),
  }
}

function handleReport(data, actionArgs) {
  const model = actionArgs.model || null
  const taskType = actionArgs.task_type || null

  log('Generating reaction report...')
  log('')

  // Model profiles section
  const modelProfiles = model
    ? { [model]: data.model_profiles[model] }
    : data.model_profiles

  // Task type profiles section
  const taskProfiles = taskType
    ? { [taskType]: data.task_type_profiles[taskType] }
    : data.task_type_profiles

  // Summary stats
  log('='.repeat(70))
  log('AI REACTION REPORT')
  log('='.repeat(70))
  log(`Total records: ${data.records.length}`)
  log(`Models tracked: ${Object.keys(data.model_profiles).length}`)
  log(`Task types tracked: ${Object.keys(data.task_type_profiles).length}`)
  log(`Learning signals accumulated: ${data.learning_signals.length}`)
  log('')

  // Per-model section
  log('--- MODEL BEHAVIORAL PROFILES ---')
  for (const [modelName, profile] of Object.entries(modelProfiles)) {
    if (!profile) continue
    log(`  ${modelName.toUpperCase()}:`)
    log(`    Observations: ${profile.total_observations}`)
    log(`    Avg composite score: ${Math.round(profile.avg_composite_score)}`)
    log(`    Avg uncertainty: ${Math.round(profile.avg_uncertainty)}`)
    log(`    Overconfidence rate: ${(profile.overconfidence_rate * 100).toFixed(1)}%`)
    log(`    Self-correction rate: ${(profile.self_correction_rate * 100).toFixed(1)}%`)
    if (profile.avg_calibration_delta !== 0) {
      log(`    Avg calibration delta: ${profile.avg_calibration_delta > 0 ? '+' : ''}${Math.round(profile.avg_calibration_delta)}`)
    }
    if (Object.keys(profile.task_types).length > 0) {
      log(`    Per task type:`)
      for (const [tt, tstats] of Object.entries(profile.task_types)) {
        log(`      ${tt}: composite=${Math.round(tstats.avg_composite)}, uncertainty=${Math.round(tstats.avg_uncertainty)}, n=${tstats.count}`)
      }
    }
    log('')
  }

  // Per-task-type section
  log('--- TASK TYPE PROFILES ---')
  for (const [ttName, profile] of Object.entries(taskProfiles)) {
    if (!profile) continue
    log(`  ${ttName}:`)
    log(`    Records: ${profile.total_records}`)
    log(`    Avg composite: ${Math.round(profile.avg_composite)}`)
    log(`    Avg uncertainty: ${Math.round(profile.avg_uncertainty)}`)
    log(`    Avg polarization: ${Math.round(profile.avg_polarization)}`)
    log(`    Best model: ${profile.best_model || 'N/A'} (score: ${Math.round(profile.best_model_score)})`)
    log(`    Difficulty distribution: easy=${profile.difficulty_distribution.easy || 0}, moderate=${profile.difficulty_distribution.moderate || 0}, hard=${profile.difficulty_distribution.hard || 0}`)
    log('')
  }

  // Recent learning signals
  const recentSignals = data.learning_signals.slice(-10)
  if (recentSignals.length > 0) {
    log('--- RECENT LEARNING SIGNALS ---')
    for (const ls of recentSignals) {
      for (const sig of ls.signals) {
        log(`  [${sig.type}] ${sig.recommendation}`)
      }
    }
    log('')
  }

  log('='.repeat(70))

  return {
    status: 'reported',
    summary: {
      total_records: data.records.length,
      models_tracked: Object.keys(data.model_profiles).length,
      task_types_tracked: Object.keys(data.task_type_profiles).length,
      learning_signals_total: data.learning_signals.length,
    },
    model_profiles: modelProfiles,
    task_type_profiles: taskProfiles,
    recent_learning_signals: recentSignals,
  }
}

function handleLearn(data, actionArgs) {
  const taskType = actionArgs.task_type || null

  log('Deriving learning signals from reaction history...')
  log('')

  // Collect all learning signals
  let signals = data.learning_signals
  if (taskType) {
    signals = signals.filter(s => s.task_type === taskType)
  }

  if (signals.length === 0) {
    log('No learning signals available yet. Record some reactions first.')
    return { status: 'no_data', signals: [], recommendations: [] }
  }

  // Aggregate signal types
  const signalCounts = {}
  const modelRankings = {}
  const taskAssessments = {}

  for (const entry of signals) {
    for (const sig of entry.signals) {
      signalCounts[sig.type] = (signalCounts[sig.type] || 0) + 1

      if (sig.type === 'confidence_ranking' && sig.ranking) {
        for (const rank of sig.ranking) {
          if (!modelRankings[rank.model]) modelRankings[rank.model] = []
          modelRankings[rank.model].push(rank.score)
        }
      }
    }

    if (entry.task_assessment) {
      const key = `${entry.task_type}_${entry.task_assessment.difficulty}`
      taskAssessments[key] = (taskAssessments[key] || 0) + 1
    }
  }

  // Compute average rankings
  const modelAvgScores = {}
  for (const [model, scores] of Object.entries(modelRankings)) {
    modelAvgScores[model] = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
  }

  // Generate recommendations
  const recommendations = []

  // Best model per task type from profiles
  for (const [tt, profile] of Object.entries(data.task_type_profiles)) {
    if (taskType && tt !== taskType) continue
    if (profile.best_model && profile.total_records >= 3) {
      recommendations.push({
        type: 'model_selection',
        task_type: tt,
        recommendation: `Prefer ${profile.best_model} for ${tt} tasks (avg behavioral confidence: ${Math.round(profile.best_model_score)}, based on ${profile.total_records} observations)`,
      })
    }

    if (profile.avg_uncertainty > 50) {
      recommendations.push({
        type: 'task_refinement',
        task_type: tt,
        recommendation: `${tt} tasks have high average uncertainty (${Math.round(profile.avg_uncertainty)}%). Consider adding more context or breaking into sub-tasks.`,
      })
    }

    if (profile.avg_polarization > 40) {
      recommendations.push({
        type: 'worker_scaling',
        task_type: tt,
        recommendation: `${tt} tasks have high model polarization (${Math.round(profile.avg_polarization)}%). Use more workers for better consensus.`,
      })
    }
  }

  // Overconfident models
  for (const [model, profile] of Object.entries(data.model_profiles)) {
    if (profile.overconfidence_rate > 0.3 && profile.total_observations >= 5) {
      recommendations.push({
        type: 'calibration_warning',
        model,
        recommendation: `${model} shows overconfidence in ${(profile.overconfidence_rate * 100).toFixed(0)}% of responses. Deflate its reported confidence by ~${Math.round(Math.abs(profile.avg_calibration_delta))} points.`,
      })
    }
  }

  log('Signal type distribution:')
  for (const [type, count] of Object.entries(signalCounts)) {
    log(`  ${type}: ${count}`)
  }
  log('')

  log('Model average behavioral scores:')
  const sortedModels = Object.entries(modelAvgScores).sort((a, b) => b[1] - a[1])
  for (const [model, score] of sortedModels) {
    log(`  ${model}: ${score}`)
  }
  log('')

  log(`Recommendations (${recommendations.length}):`)
  for (const rec of recommendations) {
    log(`  [${rec.type}] ${rec.recommendation}`)
  }

  return {
    status: 'learned',
    signal_counts: signalCounts,
    model_avg_scores: modelAvgScores,
    task_assessments: taskAssessments,
    recommendations,
    observation_count: signals.length,
  }
}

function handleUpdateOutcome(data, actionArgs) {
  const recordId = actionArgs.record_id
  const outcome = actionArgs.outcome

  if (!recordId) return { error: 'record_id is required' }
  if (!outcome) return { error: 'outcome is required' }

  const record = data.records.find(r => r.id === recordId)
  if (!record) return { error: `Record not found: ${recordId}` }

  record.outcome = {
    ...outcome,
    updated_at: new Date().toISOString(),
  }

  log(`Updated outcome for ${recordId}`)
  return { status: 'updated', record_id: recordId, outcome: record.outcome }
}

function handleReset() {
  return {
    version: '1.0',
    created: new Date().toISOString(),
    updated: new Date().toISOString(),
    records: [],
    model_profiles: {},
    task_type_profiles: {},
    learning_signals: [],
  }
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

const action = args.action || (typeof args === 'string' ? args : 'report')

const validActions = ['record', 'analyze', 'query', 'report', 'learn', 'update-outcome', 'reset']
if (!validActions.includes(action)) {
  log('ERROR: Unknown action: ' + action)
  log('')
  log('Usage: workflow("ai-reaction-tracker", { action: "..." })')
  log('')
  log('Actions:')
  log('  record          - Record reaction signals from workflow responses')
  log('  analyze         - Analyze reaction signals from text (no persistence)')
  log('  query           - Query reaction history with filters')
  log('  report          - Generate comprehensive reaction report')
  log('  learn           - Derive learning signals for model selection')
  log('  update-outcome  - Update outcome for a previous record')
  log('  reset           - Reset all reaction data')
  return { error: 'Unknown action: ' + action }
}

// ---------------------------------------------------------------------------
// PHASE 1: Load
// ---------------------------------------------------------------------------
phase('Load')

log('='.repeat(60))
log('AI REACTION TRACKER')
log('='.repeat(60))
log(`Action: ${action}`)
log('')

let data = loadReactionData()
log(`Loaded ${data.records.length} existing reaction records`)
log(`Model profiles: ${Object.keys(data.model_profiles).length}`)
log(`Task type profiles: ${Object.keys(data.task_type_profiles).length}`)
log('')

// ---------------------------------------------------------------------------
// PHASE 2: Execute
// ---------------------------------------------------------------------------
phase('Execute')

let result

switch (action) {
  case 'record':
    result = handleRecord(data, args)
    break
  case 'analyze':
    result = handleAnalyze(args)
    break
  case 'query':
    result = handleQuery(data, args)
    break
  case 'report':
    result = handleReport(data, args)
    break
  case 'learn':
    result = handleLearn(data, args)
    break
  case 'update-outcome':
    result = handleUpdateOutcome(data, args)
    break
  case 'reset':
    data = handleReset()
    result = { status: 'reset', message: 'All reaction data cleared' }
    break
}

// ---------------------------------------------------------------------------
// PHASE 3: Persist
// ---------------------------------------------------------------------------
phase('Persist')

if (action !== 'analyze') {
  const saved = saveReactionData(data)
  if (saved) {
    log('Reaction data saved to: ' + REACTION_DATA_PATH)
  } else {
    log('WARNING: Failed to save reaction data')
  }
}

log('')
log('='.repeat(60))
log('REACTION TRACKING COMPLETE')
log('='.repeat(60))

return result
