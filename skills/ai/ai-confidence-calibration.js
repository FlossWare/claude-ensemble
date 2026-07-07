import fs from 'fs';
import path from 'path';

export const meta = {
  name: 'ai-confidence-calibration',
  description: 'Confidence calibration tracker - records (model, reported_confidence, actual_outcome), applies Platt scaling or isotonic regression, provides calibrated confidence scores',
  whenToUse: 'When you need to correct raw model confidence scores using historical calibration data, or record new calibration observations',
  phases: [
    { title: 'Load', detail: 'Load calibration data and autoresolve-learning.json history' },
    { title: 'Execute', detail: 'Run the requested action (record, calibrate, report, fit)' },
    { title: 'Persist', detail: 'Save updated calibration data to disk' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// ============================================================================
// USAGE:
//
// --- Record an observation ---
// const result = await workflow('ai-confidence-calibration', {
//   action: 'record',
//   model: 'opus',
//   reported_confidence: 85,
//   actual_outcome: true,          // true = correct, false = incorrect
//   task_type: 'code-review',      // optional
//   workflow_id: 'run-1234',       // optional
// })
//
// --- Get calibrated confidence ---
// const result = await workflow('ai-confidence-calibration', {
//   action: 'calibrate',
//   model: 'opus',
//   raw_confidence: 90,
// })
// // result.calibrated_confidence => 78.3  (deflated from overconfident model)
//
// --- Get calibration report ---
// const result = await workflow('ai-confidence-calibration', { action: 'report' })
//
// --- Refit calibration models from all data ---
// const result = await workflow('ai-confidence-calibration', { action: 'fit' })
//
// --- Import data from autoresolve-learning.json ---
// const result = await workflow('ai-confidence-calibration', { action: 'import' })
//
// ============================================================================

// ============================================================================
// CALIBRATION DATA STORE PATH
// ============================================================================

const CALIBRATION_DATA_PATH = `${process.env.HOME}/.claude/repos/claude-global-skills/memory/confidence-calibration.json`
const AUTORESOLVE_LEARNING_PATH = `${process.env.HOME}/.claude/autoresolve-learning.json`

// ============================================================================
// CalibrationTracker CLASS
// ============================================================================

class CalibrationTracker {
  constructor() {
    // observations: array of { model, reported_confidence, actual_outcome, task_type, workflow_id, timestamp }
    this.observations = []
    // Per-model calibration parameters
    // platt: { a, b } for logistic P(correct) = 1 / (1 + exp(a * confidence + b))
    // isotonic: sorted array of { threshold, calibrated } breakpoints
    this.models = {}
    this.meta = {
      created: args?._timestamp || 'timestamp-at-runtime',
      last_updated: args?._timestamp || 'timestamp-at-runtime',
      total_observations: 0,
      last_fit: null,
    }
  }

  // --------------------------------------------------------------------------
  // Record a new observation: (model, reported_confidence, actual_outcome)
  // --------------------------------------------------------------------------
  record(model, reportedConfidence, actualOutcome, taskType, workflowId) {
    const observation = {
      model: normalizeModelName(model),
      reported_confidence: clampConfidence(reportedConfidence),
      actual_outcome: actualOutcome === true || actualOutcome === 1 || actualOutcome === 'success',
      task_type: taskType || 'unknown',
      workflow_id: workflowId || null,
      timestamp: args?._timestamp || 'timestamp-at-runtime',
    }
    this.observations.push(observation)
    this.meta.total_observations = this.observations.length
    this.meta.last_updated = args?._timestamp || 'timestamp-at-runtime'
    return observation
  }

  // --------------------------------------------------------------------------
  // Get calibrated confidence for a given model and raw score
  // --------------------------------------------------------------------------
  getCalibratedConfidence(model, rawConfidence) {
    const normalizedModel = normalizeModelName(model)
    const modelData = this.models[normalizedModel]

    if (!modelData || !modelData.method) {
      // No calibration data available; return raw with a warning
      return {
        calibrated_confidence: rawConfidence,
        raw_confidence: rawConfidence,
        model: normalizedModel,
        method: 'none',
        warning: 'No calibration data available for this model; returning raw confidence',
        observations_count: 0,
      }
    }

    let calibrated
    if (modelData.method === 'platt') {
      calibrated = plattTransform(rawConfidence / 100, modelData.platt_params.a, modelData.platt_params.b) * 100
    } else if (modelData.method === 'isotonic') {
      calibrated = isotonicTransform(rawConfidence / 100, modelData.isotonic_breakpoints) * 100
    } else {
      calibrated = rawConfidence
    }

    calibrated = Math.max(0, Math.min(100, calibrated))

    return {
      calibrated_confidence: Math.round(calibrated * 100) / 100,
      raw_confidence: rawConfidence,
      model: normalizedModel,
      method: modelData.method,
      adjustment: Math.round((calibrated - rawConfidence) * 100) / 100,
      observations_count: modelData.observations_count || 0,
      last_fit: modelData.last_fit || null,
    }
  }

  // --------------------------------------------------------------------------
  // Fit calibration models from recorded observations
  // --------------------------------------------------------------------------
  fitAll() {
    const results = {}
    const modelGroups = groupBy(this.observations, 'model')

    for (const [model, observations] of Object.entries(modelGroups)) {
      results[model] = this.fitModel(model, observations)
    }

    this.meta.last_fit = args?._timestamp || 'timestamp-at-runtime'
    this.meta.last_updated = args?._timestamp || 'timestamp-at-runtime'
    return results
  }

  fitModel(model, observations) {
    if (!observations || observations.length < 5) {
      this.models[model] = {
        method: null,
        observations_count: observations ? observations.length : 0,
        warning: 'Insufficient observations (minimum 5 required)',
        last_fit: args?._timestamp || 'timestamp-at-runtime',
      }
      return this.models[model]
    }

    // Extract parallel arrays: reported confidence (0-1) and outcome (0 or 1)
    const confidences = observations.map(o => o.reported_confidence / 100)
    const outcomes = observations.map(o => o.actual_outcome ? 1 : 0)

    // Try Platt scaling first
    const plattParams = fitPlattScaling(confidences, outcomes)

    // Try isotonic regression
    const isotonicBreakpoints = fitIsotonicRegression(confidences, outcomes)

    // Evaluate both via log-loss on the training data
    const plattLoss = computeLogLoss(confidences, outcomes, (c) => plattTransform(c, plattParams.a, plattParams.b))
    const isotonicLoss = computeLogLoss(confidences, outcomes, (c) => isotonicTransform(c, isotonicBreakpoints))

    // Pick the method with lower log-loss; prefer Platt for small samples due to
    // isotonic's tendency to overfit with few data points
    let method, params
    if (observations.length < 20 || plattLoss <= isotonicLoss) {
      method = 'platt'
      params = {
        method: 'platt',
        platt_params: plattParams,
        platt_log_loss: plattLoss,
        isotonic_log_loss: isotonicLoss,
        observations_count: observations.length,
        last_fit: args?._timestamp || 'timestamp-at-runtime',
      }
    } else {
      method = 'isotonic'
      params = {
        method: 'isotonic',
        isotonic_breakpoints: isotonicBreakpoints,
        platt_log_loss: plattLoss,
        isotonic_log_loss: isotonicLoss,
        observations_count: observations.length,
        last_fit: args?._timestamp || 'timestamp-at-runtime',
      }
    }

    // Compute calibration statistics
    params.calibration_stats = computeCalibrationStats(confidences, outcomes)

    this.models[model] = params
    return params
  }

  // --------------------------------------------------------------------------
  // Generate a calibration report across all models
  // --------------------------------------------------------------------------
  generateReport() {
    const modelGroups = groupBy(this.observations, 'model')
    const modelReports = {}

    for (const [model, observations] of Object.entries(modelGroups)) {
      const confidences = observations.map(o => o.reported_confidence / 100)
      const outcomes = observations.map(o => o.actual_outcome ? 1 : 0)

      const stats = computeCalibrationStats(confidences, outcomes)
      const modelParams = this.models[model] || {}

      modelReports[model] = {
        observations_count: observations.length,
        calibration_method: modelParams.method || 'none',
        ...stats,
        // Show example calibration at standard confidence levels
        calibration_examples: [25, 50, 75, 90, 95].map(raw => {
          const result = this.getCalibratedConfidence(model, raw)
          return {
            raw: raw,
            calibrated: result.calibrated_confidence,
            adjustment: result.adjustment,
          }
        }),
      }
    }

    return {
      total_observations: this.observations.length,
      models_tracked: Object.keys(modelGroups).length,
      last_fit: this.meta.last_fit,
      last_updated: this.meta.last_updated,
      model_reports: modelReports,
    }
  }

  // --------------------------------------------------------------------------
  // Import observations from autoresolve-learning.json
  // --------------------------------------------------------------------------
  importFromAutoresolveLearning(data) {
    if (!data || !data.feedback) return { imported: 0, skipped: 0 }

    let imported = 0
    let skipped = 0

    for (const entry of data.feedback) {
      // Determine if we can extract a confidence and outcome
      const model = entry.model_name
      if (!model) { skipped++; continue }

      // Use arbiter_score as reported confidence (it's 0-1 scale)
      const reportedConfidence = entry.arbiter_score != null
        ? entry.arbiter_score * 100
        : (entry.confidence != null ? entry.confidence : null)

      if (reportedConfidence == null) { skipped++; continue }

      // Determine actual outcome from acceptance_rate, outcome field, or pr_merged
      let actualOutcome
      if (entry.outcome === 'success') {
        actualOutcome = true
      } else if (entry.outcome === 'failure' || entry.outcome === 'failed') {
        actualOutcome = false
      } else if (entry.acceptance_rate != null) {
        // If acceptance_rate >= 0.7, treat as correct
        actualOutcome = entry.acceptance_rate >= 0.7
      } else if (entry.pr_merged != null) {
        actualOutcome = entry.pr_merged === true
      } else {
        // Default: if was_selected, treat as success
        actualOutcome = entry.was_selected === true
      }

      // Check for duplicate (same model, same timestamp)
      const timestamp = entry.timestamp
      const isDuplicate = this.observations.some(o =>
        o.model === normalizeModelName(model) &&
        o.timestamp === timestamp
      )

      if (isDuplicate) { skipped++; continue }

      this.observations.push({
        model: normalizeModelName(model),
        reported_confidence: clampConfidence(reportedConfidence),
        actual_outcome: actualOutcome,
        task_type: entry.issue_type || entry.workflow_type || 'unknown',
        workflow_id: entry.workflow_type || null,
        timestamp: timestamp || args?._timestamp || 'timestamp-at-runtime',
        source: 'autoresolve-learning',
      })

      imported++
    }

    // Also import from model_stats confidence_calibration buckets
    if (data.model_stats) {
      for (const [model, stats] of Object.entries(data.model_stats)) {
        if (!stats.confidence_calibration) continue

        for (const [bucket, bucketData] of Object.entries(stats.confidence_calibration)) {
          if (bucketData.total === 0) continue

          // Map bucket names to representative confidence values
          const bucketConfidence = { HIGH: 90, MEDIUM: 60, LOW: 30 }
          const conf = bucketConfidence[bucket]
          if (!conf) continue

          // Generate synthetic observations from bucket aggregates
          for (let i = 0; i < bucketData.correct; i++) {
            this.observations.push({
              model: normalizeModelName(model),
              reported_confidence: conf,
              actual_outcome: true,
              task_type: 'aggregated',
              workflow_id: null,
              timestamp: stats.timestamp || data.meta?.last_updated || args?._timestamp || 'timestamp-at-runtime',
              source: 'autoresolve-calibration-bucket',
            })
            imported++
          }

          const incorrect = bucketData.total - bucketData.correct
          for (let i = 0; i < incorrect; i++) {
            this.observations.push({
              model: normalizeModelName(model),
              reported_confidence: conf,
              actual_outcome: false,
              task_type: 'aggregated',
              workflow_id: null,
              timestamp: stats.timestamp || data.meta?.last_updated || args?._timestamp || 'timestamp-at-runtime',
              source: 'autoresolve-calibration-bucket',
            })
            imported++
          }
        }
      }
    }

    this.meta.total_observations = this.observations.length
    this.meta.last_updated = args?._timestamp || 'timestamp-at-runtime'

    return { imported, skipped }
  }

  // --------------------------------------------------------------------------
  // Serialize / deserialize
  // --------------------------------------------------------------------------
  toJSON() {
    return {
      observations: this.observations,
      models: this.models,
      meta: this.meta,
    }
  }

  static fromJSON(data) {
    const tracker = new CalibrationTracker()
    tracker.observations = data.observations || []
    tracker.models = data.models || {}
    tracker.meta = data.meta || tracker.meta
    tracker.meta.total_observations = tracker.observations.length
    return tracker
  }
}

// ============================================================================
// PLATT SCALING
//
// Platt scaling fits a logistic regression: P(correct | confidence) = sigmoid(a*c + b)
// where c is the raw confidence (0-1).
// Parameters a, b are found by minimizing log-loss via gradient descent.
// ============================================================================

function sigmoid(x) {
  if (x > 500) return 1
  if (x < -500) return 0
  return 1 / (1 + Math.exp(-x))
}

function plattTransform(confidence, a, b) {
  // P(correct) = sigmoid(a * confidence + b)
  return sigmoid(a * confidence + b)
}

function fitPlattScaling(confidences, outcomes, maxIter, learningRate) {
  maxIter = maxIter || 200
  learningRate = learningRate || 0.01

  const n = confidences.length
  if (n === 0) return { a: 1, b: 0 }

  // Initialize: a = 1, b = 0 (identity-ish mapping)
  let a = 1.0
  let b = 0.0

  // Gradient descent on log-loss
  for (let iter = 0; iter < maxIter; iter++) {
    let gradA = 0
    let gradB = 0

    for (let i = 0; i < n; i++) {
      const c = confidences[i]
      const y = outcomes[i]
      const p = sigmoid(a * c + b)

      // Gradient of binary cross-entropy: d/da = (p - y) * c, d/db = (p - y)
      const diff = p - y
      gradA += diff * c
      gradB += diff
    }

    gradA /= n
    gradB /= n

    // L2 regularization to prevent extreme parameters
    const lambda = 0.001
    gradA += lambda * a
    gradB += lambda * b

    a -= learningRate * gradA
    b -= learningRate * gradB

    // Clamp to prevent numerical explosion
    a = Math.max(-20, Math.min(20, a))
    b = Math.max(-20, Math.min(20, b))
  }

  return { a: Math.round(a * 10000) / 10000, b: Math.round(b * 10000) / 10000 }
}

// ============================================================================
// ISOTONIC REGRESSION
//
// Pool Adjacent Violators Algorithm (PAVA):
// Sort observations by reported confidence, then merge adjacent bins that
// violate the monotonicity constraint (calibrated should be non-decreasing).
// ============================================================================

function fitIsotonicRegression(confidences, outcomes) {
  const n = confidences.length
  if (n === 0) return []

  // Pair and sort by confidence
  const pairs = confidences.map((c, i) => ({ confidence: c, outcome: outcomes[i] }))
  pairs.sort((a, b) => a.confidence - b.confidence)

  // Bin into groups with same confidence (or very close)
  const bins = []
  let currentBin = { confidence: pairs[0].confidence, sum: pairs[0].outcome, count: 1 }

  for (let i = 1; i < pairs.length; i++) {
    // Group confidences within 0.02 of each other
    if (Math.abs(pairs[i].confidence - currentBin.confidence) < 0.02) {
      currentBin.sum += pairs[i].outcome
      currentBin.count++
    } else {
      bins.push(currentBin)
      currentBin = { confidence: pairs[i].confidence, sum: pairs[i].outcome, count: 1 }
    }
  }
  bins.push(currentBin)

  // Pool Adjacent Violators
  const pooled = bins.map(b => ({
    confidence: b.confidence,
    value: b.sum / b.count,
    weight: b.count,
  }))

  let changed = true
  while (changed) {
    changed = false
    for (let i = 0; i < pooled.length - 1; i++) {
      if (pooled[i].value > pooled[i + 1].value) {
        // Merge: weighted average
        const totalWeight = pooled[i].weight + pooled[i + 1].weight
        const mergedValue = (pooled[i].value * pooled[i].weight + pooled[i + 1].value * pooled[i + 1].weight) / totalWeight
        const mergedConfidence = (pooled[i].confidence * pooled[i].weight + pooled[i + 1].confidence * pooled[i + 1].weight) / totalWeight

        pooled[i] = {
          confidence: mergedConfidence,
          value: mergedValue,
          weight: totalWeight,
        }
        pooled.splice(i + 1, 1)
        changed = true
        break
      }
    }
  }

  // Convert to breakpoints
  return pooled.map(p => ({
    threshold: Math.round(p.confidence * 10000) / 10000,
    calibrated: Math.round(p.value * 10000) / 10000,
    weight: p.weight,
  }))
}

function isotonicTransform(confidence, breakpoints) {
  if (!breakpoints || breakpoints.length === 0) return confidence

  // If below the first breakpoint, return first calibrated value
  if (confidence <= breakpoints[0].threshold) {
    return breakpoints[0].calibrated
  }

  // If above the last breakpoint, return last calibrated value
  if (confidence >= breakpoints[breakpoints.length - 1].threshold) {
    return breakpoints[breakpoints.length - 1].calibrated
  }

  // Linear interpolation between nearest breakpoints
  for (let i = 0; i < breakpoints.length - 1; i++) {
    if (confidence >= breakpoints[i].threshold && confidence <= breakpoints[i + 1].threshold) {
      const t = (confidence - breakpoints[i].threshold) / (breakpoints[i + 1].threshold - breakpoints[i].threshold)
      return breakpoints[i].calibrated + t * (breakpoints[i + 1].calibrated - breakpoints[i].calibrated)
    }
  }

  return confidence
}

// ============================================================================
// CALIBRATION STATISTICS
// ============================================================================

function computeCalibrationStats(confidences, outcomes) {
  const n = confidences.length
  if (n === 0) return { ece: 0, mce: 0, brier_score: 0, overconfidence_ratio: 0 }

  // Bin into 10 equal-width buckets (0-0.1, 0.1-0.2, ...)
  const numBins = 10
  const bins = Array.from({ length: numBins }, () => ({ confidences: [], outcomes: [] }))

  for (let i = 0; i < n; i++) {
    const binIdx = Math.min(Math.floor(confidences[i] * numBins), numBins - 1)
    bins[binIdx].confidences.push(confidences[i])
    bins[binIdx].outcomes.push(outcomes[i])
  }

  // Expected Calibration Error (ECE) - weighted average of |accuracy - confidence| per bin
  let ece = 0
  let mce = 0 // Maximum Calibration Error
  let overconfidentBins = 0
  let totalBins = 0
  const binDetails = []

  for (let b = 0; b < numBins; b++) {
    const binN = bins[b].confidences.length
    if (binN === 0) continue

    const avgConfidence = bins[b].confidences.reduce((s, v) => s + v, 0) / binN
    const avgAccuracy = bins[b].outcomes.reduce((s, v) => s + v, 0) / binN
    const gap = Math.abs(avgAccuracy - avgConfidence)

    ece += (binN / n) * gap
    mce = Math.max(mce, gap)

    if (avgConfidence > avgAccuracy) overconfidentBins++
    totalBins++

    binDetails.push({
      bin: `${(b * 10)}-${((b + 1) * 10)}%`,
      count: binN,
      avg_confidence: Math.round(avgConfidence * 1000) / 10,
      avg_accuracy: Math.round(avgAccuracy * 1000) / 10,
      gap: Math.round(gap * 1000) / 10,
    })
  }

  // Brier Score: mean squared error of probability predictions
  let brierScore = 0
  for (let i = 0; i < n; i++) {
    brierScore += Math.pow(confidences[i] - outcomes[i], 2)
  }
  brierScore /= n

  return {
    ece: Math.round(ece * 10000) / 10000,
    mce: Math.round(mce * 10000) / 10000,
    brier_score: Math.round(brierScore * 10000) / 10000,
    overconfidence_ratio: totalBins > 0 ? Math.round((overconfidentBins / totalBins) * 100) / 100 : 0,
    bin_details: binDetails,
  }
}

function computeLogLoss(confidences, outcomes, transformFn) {
  const n = confidences.length
  if (n === 0) return Infinity

  let totalLoss = 0
  const eps = 1e-15 // prevent log(0)

  for (let i = 0; i < n; i++) {
    const p = Math.max(eps, Math.min(1 - eps, transformFn(confidences[i])))
    const y = outcomes[i]
    totalLoss += -(y * Math.log(p) + (1 - y) * Math.log(1 - p))
  }

  return totalLoss / n
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function clampConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 50
  return Math.max(0, Math.min(100, value))
}

function normalizeModelName(model) {
  if (!model) return 'unknown'
  // Normalize common model name variations
  const name = model.toLowerCase().trim()
  if (name.includes('opus')) return 'opus'
  if (name.includes('sonnet') && name.includes('4.5')) return 'sonnet-4.5'
  if (name.includes('sonnet')) return 'sonnet'
  if (name.includes('haiku')) return 'haiku'
  if (name.includes('gemini')) return 'gemini'
  return name
}

function groupBy(arr, key) {
  const groups = {}
  for (const item of arr) {
    const k = item[key] || 'unknown'
    if (!groups[k]) groups[k] = []
    groups[k].push(item)
  }
  return groups
}

// ============================================================================
// FILE I/O HELPERS
// ============================================================================

function loadCalibrationData() {
  try {
    const raw = fs.readFileSync(CALIBRATION_DATA_PATH, 'utf-8')
    return CalibrationTracker.fromJSON(JSON.parse(raw))
  } catch (_err) {
    return new CalibrationTracker()
  }
}

function saveCalibrationData(tracker) {
  try {
    const dir = path.dirname(CALIBRATION_DATA_PATH)
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }
    fs.writeFileSync(CALIBRATION_DATA_PATH, JSON.stringify(tracker.toJSON(), null, 2))
    return true
  } catch (err) {
    return false
  }
}

function loadAutoresolveLearning() {
  try {
    const raw = fs.readFileSync(AUTORESOLVE_LEARNING_PATH, 'utf-8')
    return JSON.parse(raw)
  } catch (_err) {
    return null
  }
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

const action = args.action || (typeof args === 'string' ? args : 'report')

if (!['record', 'calibrate', 'report', 'fit', 'import'].includes(action)) {
  log('ERROR: Unknown action: ' + action)
  log('')
  log('Usage: workflow("ai-confidence-calibration", { action: "..." })')
  log('')
  log('Actions:')
  log('  record    - Record a new (model, confidence, outcome) observation')
  log('  calibrate - Get calibrated confidence for a model + raw score')
  log('  report    - Generate a calibration report across all models')
  log('  fit       - Refit calibration models (Platt/isotonic) from all data')
  log('  import    - Import observations from autoresolve-learning.json')
  return { error: 'Unknown action: ' + action }
}

// ---------------------------------------------------------------------------
// PHASE 1: Load
// ---------------------------------------------------------------------------
phase('Load')

log('='.repeat(60))
log('CONFIDENCE CALIBRATION TRACKER')
log('='.repeat(60))
log(`Action: ${action}`)
log('')

const tracker = loadCalibrationData()
log(`Loaded ${tracker.observations.length} existing observations`)
log(`Models tracked: ${Object.keys(tracker.models).length}`)

// ---------------------------------------------------------------------------
// PHASE 2: Execute
// ---------------------------------------------------------------------------
phase('Execute')

let result

switch (action) {

  // -------------------------------------------------------------------------
  case 'record': {
    const model = args.model
    const reportedConfidence = args.reported_confidence
    const actualOutcome = args.actual_outcome
    const taskType = args.task_type || null
    const workflowId = args.workflow_id || null

    if (!model) {
      log('ERROR: model is required for record action')
      return { error: 'model is required' }
    }
    if (reportedConfidence == null) {
      log('ERROR: reported_confidence is required for record action')
      return { error: 'reported_confidence is required' }
    }
    if (actualOutcome == null) {
      log('ERROR: actual_outcome is required for record action')
      return { error: 'actual_outcome is required' }
    }

    const observation = tracker.record(model, reportedConfidence, actualOutcome, taskType, workflowId)
    log(`Recorded observation: ${observation.model} reported ${observation.reported_confidence}%, outcome=${observation.actual_outcome}`)

    // Auto-refit if we have enough new data since last fit
    const modelObs = tracker.observations.filter(o => o.model === observation.model)
    const modelParams = tracker.models[observation.model]
    if (modelObs.length >= 5 && (!modelParams || !modelParams.last_fit || modelObs.length % 5 === 0)) {
      log('Auto-refitting calibration model...')
      tracker.fitModel(observation.model, modelObs)
    }

    result = {
      status: 'recorded',
      observation,
      total_observations: tracker.observations.length,
      model_observations: modelObs.length,
    }
    break
  }

  // -------------------------------------------------------------------------
  case 'calibrate': {
    const model = args.model
    const rawConfidence = args.raw_confidence

    if (!model) {
      log('ERROR: model is required for calibrate action')
      return { error: 'model is required' }
    }
    if (rawConfidence == null) {
      log('ERROR: raw_confidence is required for calibrate action')
      return { error: 'raw_confidence is required' }
    }

    const calibration = tracker.getCalibratedConfidence(model, rawConfidence)

    log(`Model: ${calibration.model}`)
    log(`Raw confidence: ${calibration.raw_confidence}%`)
    log(`Calibrated confidence: ${calibration.calibrated_confidence}%`)
    log(`Adjustment: ${calibration.adjustment >= 0 ? '+' : ''}${calibration.adjustment}%`)
    log(`Method: ${calibration.method}`)
    if (calibration.warning) {
      log(`Warning: ${calibration.warning}`)
    }

    result = calibration
    break
  }

  // -------------------------------------------------------------------------
  case 'report': {
    const report = tracker.generateReport()

    log(`Total observations: ${report.total_observations}`)
    log(`Models tracked: ${report.models_tracked}`)
    log(`Last fit: ${report.last_fit || 'never'}`)
    log('')

    for (const [model, modelReport] of Object.entries(report.model_reports)) {
      log(`--- ${model.toUpperCase()} ---`)
      log(`  Observations: ${modelReport.observations_count}`)
      log(`  Method: ${modelReport.calibration_method}`)
      log(`  ECE (Expected Calibration Error): ${(modelReport.ece * 100).toFixed(2)}%`)
      log(`  MCE (Maximum Calibration Error): ${(modelReport.mce * 100).toFixed(2)}%`)
      log(`  Brier Score: ${modelReport.brier_score.toFixed(4)}`)
      log(`  Overconfidence ratio: ${(modelReport.overconfidence_ratio * 100).toFixed(0)}%`)

      if (modelReport.bin_details && modelReport.bin_details.length > 0) {
        log(`  Bin breakdown:`)
        for (const bin of modelReport.bin_details) {
          log(`    ${bin.bin}: n=${bin.count}, conf=${bin.avg_confidence}%, acc=${bin.avg_accuracy}%, gap=${bin.gap}%`)
        }
      }

      if (modelReport.calibration_examples) {
        log(`  Calibration examples:`)
        for (const ex of modelReport.calibration_examples) {
          const arrow = ex.adjustment >= 0 ? '+' : ''
          log(`    ${ex.raw}% -> ${ex.calibrated}% (${arrow}${ex.adjustment}%)`)
        }
      }
      log('')
    }

    result = report
    break
  }

  // -------------------------------------------------------------------------
  case 'fit': {
    if (tracker.observations.length < 5) {
      log('WARNING: Fewer than 5 observations total; fit may be unreliable')
    }

    const fitResults = tracker.fitAll()

    log('Fit results:')
    for (const [model, fitResult] of Object.entries(fitResults)) {
      log(`  ${model}:`)
      log(`    Method: ${fitResult.method || 'none'}`)
      log(`    Observations: ${fitResult.observations_count}`)
      if (fitResult.method === 'platt') {
        log(`    Platt params: a=${fitResult.platt_params.a}, b=${fitResult.platt_params.b}`)
        log(`    Platt log-loss: ${fitResult.platt_log_loss.toFixed(4)}`)
      }
      if (fitResult.method === 'isotonic') {
        log(`    Isotonic breakpoints: ${fitResult.isotonic_breakpoints.length}`)
        log(`    Isotonic log-loss: ${fitResult.isotonic_log_loss.toFixed(4)}`)
      }
      if (fitResult.warning) {
        log(`    Warning: ${fitResult.warning}`)
      }
    }

    result = {
      status: 'fit_complete',
      models_fitted: Object.keys(fitResults).length,
      fit_results: fitResults,
    }
    break
  }

  // -------------------------------------------------------------------------
  case 'import': {
    log('Loading autoresolve-learning.json...')
    const autoresolveData = loadAutoresolveLearning()

    if (!autoresolveData) {
      log('WARNING: Could not load autoresolve-learning.json')
      result = { status: 'no_data', imported: 0, skipped: 0 }
      break
    }

    log(`Found ${autoresolveData.feedback?.length || 0} feedback entries`)
    log(`Found ${Object.keys(autoresolveData.model_stats || {}).length} model stat entries`)

    const importResult = tracker.importFromAutoresolveLearning(autoresolveData)
    log(`Imported: ${importResult.imported}, Skipped: ${importResult.skipped}`)

    // Auto-fit after import
    if (tracker.observations.length >= 5) {
      log('Auto-fitting calibration models after import...')
      tracker.fitAll()
    }

    result = {
      status: 'imported',
      ...importResult,
      total_observations: tracker.observations.length,
    }
    break
  }
}

// ---------------------------------------------------------------------------
// PHASE 3: Persist
// ---------------------------------------------------------------------------
phase('Persist')

const saved = saveCalibrationData(tracker)
if (saved) {
  log('Calibration data saved to: ' + CALIBRATION_DATA_PATH)
} else {
  log('WARNING: Failed to save calibration data')
}

log('')
log('='.repeat(60))
log('CALIBRATION COMPLETE')
log('='.repeat(60))

return result

}
