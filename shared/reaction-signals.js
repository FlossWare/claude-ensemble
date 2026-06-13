/**
 * Reaction Signal Extraction Library
 *
 * Extracts behavioral signals from AI model responses -- how the model
 * responded, not just what it produced. These signals reveal confidence,
 * uncertainty, hesitation, self-correction, and disagreement patterns
 * that are invisible when you only look at final outputs.
 *
 * Signal categories:
 *   1. Confidence signals   - Explicit confidence claims ("I'm certain", "highly likely")
 *   2. Uncertainty markers   - Hedging language ("possibly", "might be", "I'm not sure")
 *   3. Self-corrections      - Mid-response revisions ("actually", "on second thought")
 *   4. Verbosity profile     - Token distribution (terse vs verbose, ratio to task complexity)
 *   5. Structural signals    - Caveats, qualifications, alternative suggestions
 *   6. Disagreement patterns - Cross-model divergence on the same task
 *
 * Usage:
 *   import { extractReactionSignals, computeDisagreementSignals, createReactionRecord } from './reaction-signals.js'
 *
 *   const signals = extractReactionSignals(responseText, { model: 'opus', task_type: 'security' })
 *   // => { confidence, uncertainty, self_corrections, verbosity, structural, composite_score }
 *
 *   const disagreement = computeDisagreementSignals(workerResponses)
 *   // => { pairwise, clusters, polarization_index }
 */

// ============================================================================
// CONFIDENCE SIGNAL DETECTION
// ============================================================================

/**
 * Detect explicit confidence signals in text.
 * Returns a score from 0-100 and the specific markers found.
 */
export function detectConfidenceSignals(text) {
  if (!text) return { score: 50, markers: [], raw_count: 0 }

  const textLower = text.toLowerCase()

  // High-confidence markers (weight: positive)
  const highConfidencePatterns = [
    { pattern: /\b(definitely|certainly|absolutely|clearly|obviously|undoubtedly)\b/gi, weight: 90, category: 'certainty' },
    { pattern: /\b(i('m| am) (highly |very )?confident)\b/gi, weight: 85, category: 'self_assessed' },
    { pattern: /\b(without (a )?doubt|no question|unambiguous(ly)?)\b/gi, weight: 95, category: 'emphatic' },
    { pattern: /\b(the answer is|this is correct|the solution is)\b/gi, weight: 80, category: 'declarative' },
    { pattern: /\b(strongly recommend|must|should definitely)\b/gi, weight: 75, category: 'prescriptive' },
    { pattern: /\b(proven|established|well[-\s]known|documented)\b/gi, weight: 70, category: 'evidence_based' },
  ]

  // Low-confidence markers (weight: negative)
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
      markers.push({
        category,
        direction: weight > 0 ? 'high' : 'low',
        count: matches.length,
        examples: matches.slice(0, 3),
        weight,
      })
    }
  }

  // Normalize score to 0-100 range, centered at 50
  let score = 50
  if (totalMatches > 0) {
    const avgWeight = weightedSum / totalMatches
    // Map avgWeight from [-95, 95] to [0, 100]
    score = Math.max(0, Math.min(100, 50 + (avgWeight / 2)))
  }

  return {
    score: Math.round(score),
    markers,
    raw_count: totalMatches,
    dominant_direction: score > 60 ? 'confident' : score < 40 ? 'uncertain' : 'neutral',
  }
}

// ============================================================================
// UNCERTAINTY MARKER DETECTION
// ============================================================================

/**
 * Detect uncertainty markers -- hedging, qualifications, and weasel words.
 * This complements detectConfidenceSignals by focusing specifically on
 * epistemic uncertainty language.
 */
export function detectUncertaintyMarkers(text) {
  if (!text) return { score: 0, markers: [], density: 0 }

  const wordCount = text.split(/\s+/).length

  const patterns = [
    // Epistemic hedges
    { regex: /\b(might|may|could)\s+(be|have|cause|result|lead)\b/gi, weight: 0.7, type: 'epistemic_hedge' },
    { regex: /\b(possibly|perhaps|conceivably|potentially)\b/gi, weight: 0.6, type: 'possibility' },
    { regex: /\b(likely|unlikely|probable|improbable)\b/gi, weight: 0.5, type: 'probability' },

    // Approximators
    { regex: /\b(approximately|roughly|around|about|roughly)\b/gi, weight: 0.4, type: 'approximation' },
    { regex: /\b(sort of|kind of|more or less|to some degree)\b/gi, weight: 0.5, type: 'vague_qualifier' },

    // Plausibility shields
    { regex: /\b(it (seems|appears|looks) (like|as if|that))\b/gi, weight: 0.6, type: 'plausibility_shield' },
    { regex: /\b(from what i (can see|understand|gather))\b/gi, weight: 0.5, type: 'limited_evidence' },

    // Attribution shields
    { regex: /\b(as far as i know|to (my|the best of my) knowledge)\b/gi, weight: 0.7, type: 'knowledge_limit' },
    { regex: /\b(i('m| am) not (entirely |completely )?(sure|certain|confident))\b/gi, weight: 0.9, type: 'explicit_uncertainty' },

    // Conditional qualifiers
    { regex: /\b(assuming|provided that|if .{3,30} then|depending on)\b/gi, weight: 0.5, type: 'conditional' },
    { regex: /\b(with (some |certain )?caveats?|caveat emptor)\b/gi, weight: 0.6, type: 'caveat' },

    // Interrogative hedges (questions in what should be answers)
    { regex: /(?<=[.!])\s+[^?]*\?\s/g, weight: 0.8, type: 'embedded_question' },
  ]

  const markers = []
  let totalWeight = 0
  let matchCount = 0

  for (const { regex, weight, type } of patterns) {
    const matches = text.match(regex)
    if (matches) {
      matchCount += matches.length
      totalWeight += matches.length * weight
      markers.push({
        type,
        count: matches.length,
        weight,
        examples: matches.slice(0, 2),
      })
    }
  }

  // Density: markers per 100 words
  const density = wordCount > 0 ? (matchCount / wordCount) * 100 : 0

  // Score: 0-100 where higher = more uncertain
  const score = Math.min(100, Math.round(density * 15))

  return {
    score,
    markers,
    density: Math.round(density * 100) / 100,
    match_count: matchCount,
    word_count: wordCount,
  }
}

// ============================================================================
// SELF-CORRECTION DETECTION
// ============================================================================

/**
 * Detect self-corrections -- moments where the model revises its own thinking
 * mid-response. These are strong signals of internal uncertainty.
 */
export function detectSelfCorrections(text) {
  if (!text) return { count: 0, corrections: [], severity: 'none' }

  const patterns = [
    // Direct corrections
    { regex: /\b(actually|wait|correction|let me (correct|revise|reconsider))\b/gi, type: 'direct_correction', weight: 0.9 },
    { regex: /\b(on second thought|thinking about it (more|again|further))\b/gi, type: 'reconsideration', weight: 0.8 },
    { regex: /\b(i (was|am) wrong|my mistake|i misspoke|i should clarify)\b/gi, type: 'admission', weight: 1.0 },

    // Revisions
    { regex: /\b(rather|instead|more accurately|to be (more )?precise)\b/gi, type: 'refinement', weight: 0.5 },
    { regex: /\b(let me rephrase|put (another|differently)|in other words)\b/gi, type: 'rephrasing', weight: 0.4 },
    { regex: /\b(upon (further |closer )?(review|inspection|analysis|reflection))\b/gi, type: 'deeper_analysis', weight: 0.7 },

    // Contradictions within response
    { regex: /\b(however|but|although|that said|on the other hand|nevertheless)\b/gi, type: 'self_contradiction', weight: 0.3 },
    { regex: /\b(despite what i (said|mentioned) (earlier|above|before))\b/gi, type: 'explicit_contradiction', weight: 0.9 },

    // Backtracking
    { regex: /\b(scratch that|disregard|ignore (what i|the above|my previous))\b/gi, type: 'backtracking', weight: 1.0 },
    { regex: /\b(i take (that |it )back|i retract)\b/gi, type: 'retraction', weight: 1.0 },
  ]

  const corrections = []
  let totalWeight = 0

  for (const { regex, type, weight } of patterns) {
    const matches = text.match(regex)
    if (matches) {
      totalWeight += matches.length * weight
      corrections.push({
        type,
        count: matches.length,
        weight,
        examples: matches.slice(0, 3),
      })
    }
  }

  const count = corrections.reduce((sum, c) => sum + c.count, 0)

  let severity = 'none'
  if (totalWeight >= 3.0) severity = 'high'
  else if (totalWeight >= 1.5) severity = 'moderate'
  else if (totalWeight > 0) severity = 'low'

  return {
    count,
    corrections,
    total_weight: Math.round(totalWeight * 100) / 100,
    severity,
  }
}

// ============================================================================
// VERBOSITY ANALYSIS
// ============================================================================

/**
 * Analyze the verbosity profile of a response.
 * Extremely short or long responses relative to task complexity
 * can signal confidence or uncertainty.
 */
export function analyzeVerbosity(text, options = {}) {
  if (!text) return { word_count: 0, char_count: 0, profile: 'empty', signals: [] }

  const wordCount = text.split(/\s+/).length
  const charCount = text.length
  const sentenceCount = (text.match(/[.!?]+/g) || []).length || 1
  const paragraphCount = text.split(/\n\s*\n/).length
  const avgWordsPerSentence = wordCount / sentenceCount

  // Code block detection
  const codeBlocks = (text.match(/```[\s\S]*?```/g) || []).length
  const bulletPoints = (text.match(/^[\s]*[-*+]\s/gm) || []).length
  const numberedItems = (text.match(/^[\s]*\d+[.)]\s/gm) || []).length

  // Determine profile
  let profile = 'normal'
  const signals = []

  if (wordCount < 20) {
    profile = 'terse'
    signals.push({
      signal: 'very_short_response',
      interpretation: 'Model was extremely brief -- may indicate high confidence or lack of engagement',
    })
  } else if (wordCount < 50) {
    profile = 'concise'
    signals.push({
      signal: 'short_response',
      interpretation: 'Concise answer -- may indicate straightforward task or high confidence',
    })
  } else if (wordCount > 500) {
    profile = 'verbose'
    signals.push({
      signal: 'long_response',
      interpretation: 'Verbose answer -- may indicate complex reasoning, uncertainty, or over-explanation',
    })
  } else if (wordCount > 1000) {
    profile = 'very_verbose'
    signals.push({
      signal: 'very_long_response',
      interpretation: 'Extremely verbose -- possible uncertainty, hedging, or covering multiple angles',
    })
  }

  // High caveat-to-content ratio
  if (bulletPoints + numberedItems > 5 && wordCount < 200) {
    signals.push({
      signal: 'list_heavy',
      interpretation: 'Heavy use of lists in a short response -- structured but may avoid deep reasoning',
    })
  }

  // Average sentence length signals
  if (avgWordsPerSentence > 30) {
    signals.push({
      signal: 'long_sentences',
      interpretation: 'Long average sentences -- possible hedging or qualification stacking',
    })
  }

  return {
    word_count: wordCount,
    char_count: charCount,
    sentence_count: sentenceCount,
    paragraph_count: paragraphCount,
    avg_words_per_sentence: Math.round(avgWordsPerSentence * 10) / 10,
    code_blocks: codeBlocks,
    bullet_points: bulletPoints,
    numbered_items: numberedItems,
    profile,
    signals,
  }
}

// ============================================================================
// STRUCTURAL SIGNAL DETECTION
// ============================================================================

/**
 * Detect structural signals -- how the model organized its response.
 * Includes alternative-suggestion patterns, caveat sections, and
 * qualification structures.
 */
export function detectStructuralSignals(text) {
  if (!text) return { signals: [], caveat_count: 0, alternatives_offered: 0, qualification_depth: 0 }

  const signals = []

  // Alternative suggestions (sign of low confidence in primary answer)
  const alternativePatterns = [
    /\b(alternatively|another (option|approach|way|possibility))\b/gi,
    /\b(you (could|might|may) (also|instead|alternatively))\b/gi,
    /\b(option \d|approach \d|alternative \d)\b/gi,
    /\b(on the other hand|conversely|by contrast)\b/gi,
  ]

  let alternativesOffered = 0
  for (const pattern of alternativePatterns) {
    const matches = text.match(pattern)
    if (matches) {
      alternativesOffered += matches.length
    }
  }

  if (alternativesOffered > 0) {
    signals.push({
      type: 'alternatives_offered',
      count: alternativesOffered,
      interpretation: alternativesOffered > 3
        ? 'Many alternatives offered -- model is uncertain about best approach'
        : 'Some alternatives offered -- model sees multiple viable paths',
    })
  }

  // Caveat/warning sections
  const caveatPatterns = [
    /\b(caveat|warning|note|important|caution|disclaimer|limitation)\s*:/gi,
    /\b(keep in mind|be aware|worth noting|important to note)\b/gi,
    /\b(this (may|might|could) (not |)(work|apply|be suitable))\b/gi,
  ]

  let caveatCount = 0
  for (const pattern of caveatPatterns) {
    const matches = text.match(pattern)
    if (matches) {
      caveatCount += matches.length
    }
  }

  if (caveatCount > 0) {
    signals.push({
      type: 'caveats',
      count: caveatCount,
      interpretation: caveatCount > 3
        ? 'Heavy caveating -- model is hedging substantially'
        : 'Some caveats -- model is being appropriately cautious',
    })
  }

  // Qualification stacking (nested qualifiers)
  const qualificationPattern = /\b(although|however|but|though|while|whereas)\b/gi
  const qualifications = text.match(qualificationPattern) || []
  const qualificationDepth = qualifications.length

  if (qualificationDepth > 4) {
    signals.push({
      type: 'deep_qualification',
      count: qualificationDepth,
      interpretation: 'Deep qualification stacking -- model is heavily hedging its position',
    })
  }

  // Explicit scope limitation
  const scopePatterns = [
    /\b(beyond (my|the) scope|outside (my|the) (expertise|knowledge))\b/gi,
    /\b(i (cannot|can't) (verify|confirm|guarantee))\b/gi,
    /\b(this is (just |)(an|my) (estimate|guess|approximation))\b/gi,
  ]

  let scopeLimitations = 0
  for (const pattern of scopePatterns) {
    const matches = text.match(pattern)
    if (matches) {
      scopeLimitations += matches.length
    }
  }

  if (scopeLimitations > 0) {
    signals.push({
      type: 'scope_limitation',
      count: scopeLimitations,
      interpretation: 'Model explicitly limits its scope -- strong uncertainty signal',
    })
  }

  return {
    signals,
    caveat_count: caveatCount,
    alternatives_offered: alternativesOffered,
    qualification_depth: qualificationDepth,
    scope_limitations: scopeLimitations,
  }
}

// ============================================================================
// COMPOSITE EXTRACTION: All signals from one response
// ============================================================================

/**
 * Extract all reaction signals from a single model response.
 * This is the primary entry point for signal extraction.
 *
 * @param {string} responseText - The full text of the model's response
 * @param {Object} metadata - Additional context
 * @param {string} metadata.model - Model name (opus, sonnet, etc.)
 * @param {string} metadata.task_type - Task type (security, code-review, etc.)
 * @param {number} metadata.latency_ms - Time to produce response (if available)
 * @param {number} metadata.reported_confidence - Model's self-reported confidence (if available)
 * @returns {Object} Complete reaction signal profile
 */
export function extractReactionSignals(responseText, metadata = {}) {
  const text = typeof responseText === 'string' ? responseText : JSON.stringify(responseText, null, 2)

  const confidence = detectConfidenceSignals(text)
  const uncertainty = detectUncertaintyMarkers(text)
  const selfCorrections = detectSelfCorrections(text)
  const verbosity = analyzeVerbosity(text)
  const structural = detectStructuralSignals(text)

  // Compute composite reaction score (0-100, where 100 = maximally confident, 0 = maximally uncertain)
  const compositeScore = computeCompositeScore(confidence, uncertainty, selfCorrections, structural, metadata)

  // Compute confidence-uncertainty gap (how much they conflict)
  const conflictScore = Math.abs(confidence.score - (100 - uncertainty.score))

  // Detect if model is overconfident (high confidence language + high uncertainty markers)
  const overconfident = confidence.score > 70 && uncertainty.score > 40
  // Detect if model is well-calibrated (confidence language matches uncertainty absence)
  const wellCalibrated = Math.abs(confidence.score - (100 - uncertainty.score)) < 20

  return {
    model: metadata.model || 'unknown',
    task_type: metadata.task_type || 'unknown',
    timestamp: new Date().toISOString(),

    // Individual signal categories
    confidence,
    uncertainty,
    self_corrections: selfCorrections,
    verbosity,
    structural,

    // Derived metrics
    composite_score: compositeScore,
    conflict_score: conflictScore,
    overconfident,
    well_calibrated: wellCalibrated,

    // Metadata carried through
    latency_ms: metadata.latency_ms || null,
    reported_confidence: metadata.reported_confidence || null,

    // Calibration delta: difference between reported confidence and behavioral confidence
    calibration_delta: metadata.reported_confidence != null
      ? Math.round(metadata.reported_confidence - compositeScore)
      : null,
  }
}

/**
 * Compute a composite score from all signal categories.
 * Score range: 0-100 where higher = more confident behavior.
 */
function computeCompositeScore(confidence, uncertainty, selfCorrections, structural, metadata) {
  // Base from confidence detection
  let score = confidence.score * 0.35

  // Subtract uncertainty
  score += (100 - uncertainty.score) * 0.25

  // Self-corrections penalize
  const correctionPenalty = Math.min(30, selfCorrections.total_weight * 10)
  score += (100 - correctionPenalty) * 0.15

  // Structural signals (alternatives and caveats reduce confidence)
  const structuralPenalty = Math.min(30, (structural.alternatives_offered * 5 + structural.caveat_count * 3))
  score += (100 - structuralPenalty) * 0.15

  // Latency signal (slower = potentially more uncertain, but also more thorough)
  if (metadata.latency_ms) {
    // Normalize: < 2s = fast (slight positive), > 10s = slow (slight negative)
    const latencyFactor = metadata.latency_ms < 2000 ? 60 : metadata.latency_ms > 10000 ? 40 : 50
    score += latencyFactor * 0.10
  } else {
    score += 50 * 0.10
  }

  return Math.max(0, Math.min(100, Math.round(score)))
}

// ============================================================================
// CROSS-MODEL DISAGREEMENT ANALYSIS
// ============================================================================

/**
 * Compute disagreement signals across multiple model responses.
 * Identifies which models agree, which disagree, and the patterns of divergence.
 *
 * @param {Array} workerResponses - Array of { model, text, answer, confidence, signals }
 * @returns {Object} Disagreement analysis
 */
export function computeDisagreementSignals(workerResponses) {
  if (!workerResponses || workerResponses.length < 2) {
    return {
      model_count: workerResponses?.length || 0,
      pairwise: [],
      polarization_index: 0,
      confidence_spread: 0,
      behavioral_agreement: 100,
      reaction_clusters: [],
    }
  }

  // Extract signals for each response if not already done
  const signals = workerResponses.map(w => {
    if (w.signals) return w
    const text = w.text || JSON.stringify(w.answer || w, null, 2)
    return {
      ...w,
      signals: extractReactionSignals(text, { model: w.model }),
    }
  })

  // Pairwise disagreement (behavioral, not just answer-level)
  const pairwise = []
  for (let i = 0; i < signals.length; i++) {
    for (let j = i + 1; j < signals.length; j++) {
      const s1 = signals[i].signals
      const s2 = signals[j].signals

      // Behavioral divergence: how differently did they react?
      const confidenceDiff = Math.abs(s1.composite_score - s2.composite_score)
      const uncertaintyDiff = Math.abs(s1.uncertainty.score - s2.uncertainty.score)
      const correctionDiff = Math.abs(s1.self_corrections.count - s2.self_corrections.count)

      const behavioralDivergence = (confidenceDiff * 0.5 + uncertaintyDiff * 0.3 + correctionDiff * 10 * 0.2)

      pairwise.push({
        models: [signals[i].model, signals[j].model],
        confidence_diff: confidenceDiff,
        uncertainty_diff: uncertaintyDiff,
        correction_diff: correctionDiff,
        behavioral_divergence: Math.round(behavioralDivergence),
      })
    }
  }

  // Confidence spread: range of composite scores
  const composites = signals.map(s => s.signals.composite_score)
  const confidenceSpread = Math.max(...composites) - Math.min(...composites)

  // Polarization index: std dev of composite scores normalized to 0-100
  const mean = composites.reduce((a, b) => a + b, 0) / composites.length
  const variance = composites.reduce((a, v) => a + Math.pow(v - mean, 2), 0) / composites.length
  const stddev = Math.sqrt(variance)
  const polarizationIndex = Math.min(100, Math.round(stddev * 2))

  // Behavioral agreement: inverse of average pairwise divergence
  const avgDivergence = pairwise.length > 0
    ? pairwise.reduce((sum, p) => sum + p.behavioral_divergence, 0) / pairwise.length
    : 0
  const behavioralAgreement = Math.max(0, 100 - Math.round(avgDivergence))

  // Cluster models by similar reaction patterns
  const reactionClusters = clusterByReaction(signals)

  return {
    model_count: signals.length,
    pairwise,
    polarization_index: polarizationIndex,
    confidence_spread: confidenceSpread,
    behavioral_agreement: behavioralAgreement,
    reaction_clusters: reactionClusters,
    per_model_composites: signals.map(s => ({
      model: s.model,
      composite_score: s.signals.composite_score,
      confidence: s.signals.confidence.score,
      uncertainty: s.signals.uncertainty.score,
      self_corrections: s.signals.self_corrections.count,
    })),
  }
}

/**
 * Cluster models by similar reaction profiles using simple threshold grouping.
 */
function clusterByReaction(signals) {
  if (signals.length < 2) return []

  // Simple clustering: group by composite score bands
  const bands = { confident: [], neutral: [], uncertain: [] }

  for (const s of signals) {
    const score = s.signals.composite_score
    if (score >= 65) bands.confident.push(s.model)
    else if (score >= 40) bands.neutral.push(s.model)
    else bands.uncertain.push(s.model)
  }

  const clusters = []
  if (bands.confident.length > 0) {
    clusters.push({ label: 'confident', models: bands.confident, description: 'Models that responded with high behavioral confidence' })
  }
  if (bands.neutral.length > 0) {
    clusters.push({ label: 'neutral', models: bands.neutral, description: 'Models with moderate behavioral confidence' })
  }
  if (bands.uncertain.length > 0) {
    clusters.push({ label: 'uncertain', models: bands.uncertain, description: 'Models that showed significant uncertainty signals' })
  }

  return clusters
}

// ============================================================================
// REACTION RECORD CREATION
// ============================================================================

/**
 * Create a complete reaction record suitable for storage.
 * Combines individual signals, disagreement analysis, and task metadata.
 *
 * @param {Object} params
 * @param {string} params.task - Task description
 * @param {string} params.task_type - Task category
 * @param {string} params.workflow - Source workflow name
 * @param {Array} params.worker_signals - Array of per-model signal objects from extractReactionSignals
 * @param {Object} params.disagreement - Output from computeDisagreementSignals
 * @param {Object} params.outcome - Final outcome metadata (optional)
 * @returns {Object} Complete reaction record
 */
export function createReactionRecord(params) {
  const {
    task = '',
    task_type = 'unknown',
    workflow = 'unknown',
    worker_signals = [],
    disagreement = null,
    outcome = null,
  } = params

  // Aggregate signals across all workers
  const avgComposite = worker_signals.length > 0
    ? worker_signals.reduce((sum, s) => sum + s.composite_score, 0) / worker_signals.length
    : 0
  const avgUncertainty = worker_signals.length > 0
    ? worker_signals.reduce((sum, s) => sum + s.uncertainty.score, 0) / worker_signals.length
    : 0
  const totalSelfCorrections = worker_signals.reduce((sum, s) => sum + s.self_corrections.count, 0)

  // Derive task difficulty estimate from reactions
  let estimatedDifficulty = 'moderate'
  if (avgUncertainty > 60 || totalSelfCorrections > 5) estimatedDifficulty = 'hard'
  else if (avgUncertainty > 40 || totalSelfCorrections > 2) estimatedDifficulty = 'moderate'
  else if (avgComposite > 70) estimatedDifficulty = 'easy'

  // Calibration analysis: do reported confidences match behavioral signals?
  const calibrationEntries = worker_signals
    .filter(s => s.reported_confidence != null)
    .map(s => ({
      model: s.model,
      reported: s.reported_confidence,
      behavioral: s.composite_score,
      delta: s.calibration_delta,
      calibration: Math.abs(s.calibration_delta) < 15 ? 'well_calibrated' : s.calibration_delta > 0 ? 'overconfident' : 'underconfident',
    }))

  return {
    timestamp: new Date().toISOString(),
    task_summary: task.substring(0, 200),
    task_type,
    workflow,

    // Per-worker signals
    workers: worker_signals.map(s => ({
      model: s.model,
      composite_score: s.composite_score,
      confidence_score: s.confidence.score,
      uncertainty_score: s.uncertainty.score,
      self_correction_count: s.self_corrections.count,
      self_correction_severity: s.self_corrections.severity,
      verbosity_profile: s.verbosity.profile,
      word_count: s.verbosity.word_count,
      alternatives_offered: s.structural.alternatives_offered,
      caveat_count: s.structural.caveat_count,
      overconfident: s.overconfident,
      well_calibrated: s.well_calibrated,
      reported_confidence: s.reported_confidence,
      calibration_delta: s.calibration_delta,
      latency_ms: s.latency_ms,
    })),

    // Aggregate metrics
    aggregate: {
      avg_composite_score: Math.round(avgComposite),
      avg_uncertainty: Math.round(avgUncertainty),
      total_self_corrections: totalSelfCorrections,
      estimated_difficulty: estimatedDifficulty,
      model_count: worker_signals.length,
    },

    // Cross-model analysis
    disagreement: disagreement || { polarization_index: 0, behavioral_agreement: 100 },

    // Calibration analysis
    calibration: calibrationEntries,

    // Outcome (filled in later when known)
    outcome: outcome || null,
  }
}

// ============================================================================
// LEARNING SIGNAL DERIVATION
// ============================================================================

/**
 * Derive actionable learning signals from a reaction record.
 * These signals can feed into model selection and task routing.
 *
 * @param {Object} reactionRecord - Output from createReactionRecord
 * @returns {Object} Learning signals
 */
export function deriveLearningSignals(reactionRecord) {
  const signals = []
  const modelPreferences = {}

  // Signal 1: Model confidence ranking for this task type
  const workersByConfidence = [...reactionRecord.workers].sort((a, b) => b.composite_score - a.composite_score)
  if (workersByConfidence.length > 0) {
    signals.push({
      type: 'confidence_ranking',
      task_type: reactionRecord.task_type,
      ranking: workersByConfidence.map(w => ({ model: w.model, score: w.composite_score })),
      top_model: workersByConfidence[0].model,
      recommendation: `For ${reactionRecord.task_type} tasks, ${workersByConfidence[0].model} shows highest behavioral confidence (${workersByConfidence[0].composite_score})`,
    })
  }

  // Signal 2: Universal uncertainty = task is ambiguous
  if (reactionRecord.aggregate.avg_uncertainty > 50) {
    signals.push({
      type: 'task_ambiguity',
      task_type: reactionRecord.task_type,
      avg_uncertainty: reactionRecord.aggregate.avg_uncertainty,
      recommendation: 'All models show high uncertainty -- task may be ambiguous. Consider using more workers or refining the task prompt.',
    })
  }

  // Signal 3: High self-corrections = task is tricky
  if (reactionRecord.aggregate.total_self_corrections > 3) {
    signals.push({
      type: 'task_trickiness',
      task_type: reactionRecord.task_type,
      total_corrections: reactionRecord.aggregate.total_self_corrections,
      recommendation: 'Multiple self-corrections detected -- task has non-obvious complexities. Prefer flagship models.',
    })
  }

  // Signal 4: Calibration issues per model
  for (const cal of reactionRecord.calibration) {
    if (cal.calibration === 'overconfident') {
      signals.push({
        type: 'model_overconfidence',
        model: cal.model,
        task_type: reactionRecord.task_type,
        delta: cal.delta,
        recommendation: `${cal.model} reports confidence ${cal.delta} points above behavioral signals for ${reactionRecord.task_type}. Deflate reported scores.`,
      })
    } else if (cal.calibration === 'underconfident') {
      signals.push({
        type: 'model_underconfidence',
        model: cal.model,
        task_type: reactionRecord.task_type,
        delta: cal.delta,
        recommendation: `${cal.model} reports confidence ${Math.abs(cal.delta)} points below behavioral signals for ${reactionRecord.task_type}. Inflate reported scores.`,
      })
    }
  }

  // Signal 5: Polarized disagreement
  if (reactionRecord.disagreement && reactionRecord.disagreement.polarization_index > 40) {
    signals.push({
      type: 'model_polarization',
      task_type: reactionRecord.task_type,
      polarization: reactionRecord.disagreement.polarization_index,
      recommendation: 'Models are polarized in their reactions -- high disagreement. Use arbiter with access to all reasoning, or break task into sub-questions.',
    })
  }

  // Build model preference map
  for (const worker of reactionRecord.workers) {
    modelPreferences[worker.model] = {
      composite_score: worker.composite_score,
      well_calibrated: worker.well_calibrated,
      overconfident: worker.overconfident,
      task_type: reactionRecord.task_type,
    }
  }

  return {
    signals,
    model_preferences: modelPreferences,
    task_assessment: {
      difficulty: reactionRecord.aggregate.estimated_difficulty,
      ambiguity: reactionRecord.aggregate.avg_uncertainty > 50 ? 'high' : reactionRecord.aggregate.avg_uncertainty > 30 ? 'moderate' : 'low',
      trickiness: reactionRecord.aggregate.total_self_corrections > 3 ? 'high' : reactionRecord.aggregate.total_self_corrections > 1 ? 'moderate' : 'low',
    },
  }
}

// ============================================================================
// EXPORTS SUMMARY
// ============================================================================
// Primary entry points:
//   extractReactionSignals(text, metadata) -> per-model signal profile
//   computeDisagreementSignals(workerResponses) -> cross-model disagreement
//   createReactionRecord(params) -> complete storage-ready record
//   deriveLearningSignals(reactionRecord) -> actionable routing signals
//
// Individual detectors (also exported for targeted use):
//   detectConfidenceSignals(text)
//   detectUncertaintyMarkers(text)
//   detectSelfCorrections(text)
//   analyzeVerbosity(text)
//   detectStructuralSignals(text)
