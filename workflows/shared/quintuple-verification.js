// Quintuple Verification Helper - 5-Stage Multi-Model Verification
// Progressive filtering with confidence tracking
// Used by: autonomous workflows requiring high-confidence decisions

/**
 * Run 5-stage quintuple verification on an item
 *
 * Stages:
 * 1. Propose (given as input)
 * 2. Review (≥50% approval required)
 * 3. Verify (≥60% adversarial survival required)
 * 4. Validate (≥50% integration test pass required)
 * 5. Confirm (final arbiter approval)
 *
 * @param {Object} item - The proposal to verify
 * @param {Object} strategy - Strategy object with getVerificationStages()
 * @param {Object} options - Optional configuration
 * @returns {Promise<Object>} Detailed verification results with final verdict
 */
export async function runQuintupleVerification(item, strategy, options = {}) {
  const {
    phase = 'Quintuple Verification',
    verbose = false,
    failFast = true,
    confidenceThreshold = 50
  } = options

  // Validate inputs
  if (!item) {
    throw new Error('Item is required for quintuple verification')
  }

  if (!strategy || typeof strategy.getVerificationStages !== 'function') {
    throw new Error('Strategy must have getVerificationStages() method')
  }

  const stages = strategy.getVerificationStages()

  if (!stages) {
    throw new Error('Strategy.getVerificationStages() must return stages configuration')
  }

  // Initialize verification results
  const results = {
    item: item,
    stages: {},
    overallConfidence: 0,
    passed: false,
    finalVerdict: null,
    timestamp: new Date().toISOString(),
    metrics: {
      totalStages: 5,
      passedStages: 0,
      failedStage: null,
      confidenceByStage: {}
    }
  }

  log(`🔐 Starting Quintuple Verification | ${phase}`)

  // Stage 1: Propose (input is already the proposal)
  log(`\n📝 Stage 1: Propose`)
  results.stages.propose = {
    stage: 1,
    name: 'Propose',
    status: 'passed',
    proposal: item,
    confidence: 100,
    timestamp: new Date().toISOString()
  }
  results.metrics.passedStages++
  results.metrics.confidenceByStage.propose = 100

  if (verbose) {
    log(`  ✅ Proposal accepted (100% confidence)`)
  }

  // Stage 2: Review (Peer review by all worker models)
  log(`\n👥 Stage 2: Review (≥50% approval required)`)

  const reviewResult = await runReviewStage(item, stages)
  results.stages.review = reviewResult

  if (!reviewResult.passed) {
    if (failFast) {
      results.passed = false
      results.finalVerdict = 'rejected_at_review'
      results.metrics.failedStage = 'review'
      log(`  ❌ Review stage failed (${reviewResult.approvalRate}% < 50%)`)
      return results
    }
  } else {
    results.metrics.passedStages++
  }

  results.metrics.confidenceByStage.review = reviewResult.confidence

  // Stage 3: Verify (Adversarial verification)
  log(`\n⚔️  Stage 3: Verify (≥60% survival required)`)

  const verifyResult = await runVerifyStage(item, stages, reviewResult)
  results.stages.verify = verifyResult

  if (!verifyResult.passed) {
    if (failFast) {
      results.passed = false
      results.finalVerdict = 'rejected_at_verify'
      results.metrics.failedStage = 'verify'
      log(`  ❌ Verify stage failed (${verifyResult.survivalRate}% < 60%)`)
      return results
    }
  } else {
    results.metrics.passedStages++
  }

  results.metrics.confidenceByStage.verify = verifyResult.confidence

  // Stage 4: Validate (Integration testing)
  log(`\n🧪 Stage 4: Validate (≥50% validation pass required)`)

  const validateResult = await runValidateStage(item, stages, verifyResult)
  results.stages.validate = validateResult

  if (!validateResult.passed) {
    if (failFast) {
      results.passed = false
      results.finalVerdict = 'rejected_at_validate'
      results.metrics.failedStage = 'validate'
      log(`  ❌ Validate stage failed (${validateResult.passRate}% < 50%)`)
      return results
    }
  } else {
    results.metrics.passedStages++
  }

  results.metrics.confidenceByStage.validate = validateResult.confidence

  // Stage 5: Confirm (Final arbiter approval)
  log(`\n✔️  Stage 5: Confirm (Arbiter approval)`)

  const confirmResult = await runConfirmStage(item, stages, results)
  results.stages.confirm = confirmResult

  if (!confirmResult.passed) {
    results.passed = false
    results.finalVerdict = 'rejected_at_confirm'
    results.metrics.failedStage = 'confirm'
    log(`  ❌ Confirm stage failed (${confirmResult.arbiterDecision})`)
    return results
  }

  results.metrics.passedStages++
  results.metrics.confidenceByStage.confirm = confirmResult.confidence

  // All stages passed
  results.passed = true
  results.finalVerdict = 'approved'
  results.overallConfidence = calculateOverallConfidence(results)

  log(`\n✅ Quintuple Verification PASSED`)
  log(`   Overall Confidence: ${results.overallConfidence}%`)

  return results
}

/**
 * Stage 2: Review - Peer review by all worker models
 * Requirement: ≥50% must approve
 */
async function runReviewStage(item, stages) {
  const reviewModels = stages.review?.models || ['sonnet', 'haiku']
  const reviewPrompt = stages.review?.prompt || `Review this proposal and assess if it meets quality standards:\n\n${JSON.stringify(item, null, 2)}`

  const reviewSchema = {
    type: 'object',
    properties: {
      approved: { type: 'boolean', description: 'Is this proposal approved?' },
      confidence: { type: 'number', minimum: 0, maximum: 100, description: 'Confidence level' },
      reasoning: { type: 'string', description: 'Why approve or reject' },
      issues: { type: 'array', items: { type: 'string' }, description: 'List of issues if any' }
    },
    required: ['approved', 'confidence', 'reasoning']
  }

  // Run reviews in parallel
  const reviews = await parallel(
    reviewModels.map(model => () =>
      agent(reviewPrompt, {
        schema: reviewSchema,
        model,
        label: `Review (${capitalize(model)})`,
        phase: 'Review Stage'
      })
    )
  )

  // Calculate approval rate
  const approvedCount = reviews.filter(r => r.approved).length
  const approvalRate = (approvedCount / reviews.length) * 100

  return {
    stage: 2,
    name: 'Review',
    status: approvalRate >= 50 ? 'passed' : 'failed',
    passed: approvalRate >= 50,
    approvalRate: Math.round(approvalRate),
    approvedCount,
    totalReviewers: reviews.length,
    confidence: calculateAverageConfidence(reviews),
    reviews,
    timestamp: new Date().toISOString()
  }
}

/**
 * Stage 3: Verify - Adversarial verification
 * Requirement: ≥60% must survive refutation attempts
 */
async function runVerifyStage(item, stages, reviewResult) {
  const verifyModels = stages.verify?.models || ['opus', 'sonnet']
  const verifyPrompt = stages.verify?.prompt || `Try to refute or find flaws in this proposal. Be adversarial:\n\n${JSON.stringify(item, null, 2)}`

  const refutationSchema = {
    type: 'object',
    properties: {
      refuted: { type: 'boolean', description: 'Can this proposal be refuted?' },
      confidence: { type: 'number', minimum: 0, maximum: 100, description: 'Confidence in refutation' },
      flaws: { type: 'array', items: { type: 'string' }, description: 'Identified flaws' },
      reasoning: { type: 'string', description: 'Detailed adversarial analysis' }
    },
    required: ['refuted', 'confidence', 'reasoning']
  }

  // Run adversarial verification in parallel
  const refutations = await parallel(
    verifyModels.map(model => () =>
      agent(verifyPrompt, {
        schema: refutationSchema,
        model,
        label: `Verify (${capitalize(model)})`,
        phase: 'Verify Stage'
      })
    )
  )

  // Survival rate = proposals that were NOT refuted
  const survivedCount = refutations.filter(r => !r.refuted).length
  const survivalRate = (survivedCount / refutations.length) * 100

  return {
    stage: 3,
    name: 'Verify',
    status: survivalRate >= 60 ? 'passed' : 'failed',
    passed: survivalRate >= 60,
    survivalRate: Math.round(survivalRate),
    survivedCount,
    totalVerifiers: refutations.length,
    confidence: calculateAverageConfidence(refutations),
    refutations,
    timestamp: new Date().toISOString()
  }
}

/**
 * Stage 4: Validate - Integration testing
 * Requirement: ≥50% must validate successfully
 */
async function runValidateStage(item, stages, verifyResult) {
  const validateModels = stages.validate?.models || ['opus', 'haiku']
  const validatePrompt = stages.validate?.prompt || `Test this proposal in an integration scenario. Does it work in practice?\n\n${JSON.stringify(item, null, 2)}`

  const validationSchema = {
    type: 'object',
    properties: {
      validated: { type: 'boolean', description: 'Does this validate successfully?' },
      confidence: { type: 'number', minimum: 0, maximum: 100, description: 'Confidence in validation' },
      testResults: { type: 'array', items: { type: 'string' }, description: 'Test results' },
      issues: { type: 'array', items: { type: 'string' }, description: 'Validation issues' },
      reasoning: { type: 'string', description: 'Validation analysis' }
    },
    required: ['validated', 'confidence', 'reasoning']
  }

  // Run validation in parallel
  const validations = await parallel(
    validateModels.map(model => () =>
      agent(validatePrompt, {
        schema: validationSchema,
        model,
        label: `Validate (${capitalize(model)})`,
        phase: 'Validate Stage'
      })
    )
  )

  // Pass rate = validations that passed
  const passedCount = validations.filter(v => v.validated).length
  const passRate = (passedCount / validations.length) * 100

  return {
    stage: 4,
    name: 'Validate',
    status: passRate >= 50 ? 'passed' : 'failed',
    passed: passRate >= 50,
    passRate: Math.round(passRate),
    passedCount,
    totalValidators: validations.length,
    confidence: calculateAverageConfidence(validations),
    validations,
    timestamp: new Date().toISOString()
  }
}

/**
 * Stage 5: Confirm - Final arbiter approval
 * Requirement: Arbiter must approve
 */
async function runConfirmStage(item, stages, allResults) {
  const arbiterModel = stages.confirm?.arbiterModel || 'fable'

  const confirmPrompt = `You are the final arbiter. Review all previous stages and make a final decision:

**Proposal**:
${JSON.stringify(item, null, 2)}

**Previous Stages Summary**:
- Review: ${allResults.stages.review.status} (${allResults.stages.review.approvalRate}% approval)
- Verify: ${allResults.stages.verify.status} (${allResults.stages.verify.survivalRate}% survival)
- Validate: ${allResults.stages.validate.status} (${allResults.stages.validate.passRate}% pass rate)

Make your final decision: should this proposal be APPROVED or REJECTED?`

  const confirmSchema = {
    type: 'object',
    properties: {
      approved: { type: 'boolean', description: 'Final arbiter approval' },
      confidence: { type: 'number', minimum: 0, maximum: 100, description: 'Arbiter confidence' },
      reasoning: { type: 'string', description: 'Final decision reasoning' },
      recommendations: { type: 'array', items: { type: 'string' }, description: 'Any recommendations' }
    },
    required: ['approved', 'confidence', 'reasoning']
  }

  const arbiterDecision = await _agent(confirmPrompt, {
    schema: confirmSchema,
    model: arbiterModel,
    label: `Confirm (${capitalize(arbiterModel)})`,
    phase: 'Confirm Stage'
  })

  return {
    stage: 5,
    name: 'Confirm',
    status: arbiterDecision.approved ? 'passed' : 'failed',
    passed: arbiterDecision.approved,
    arbiterDecision: arbiterDecision.approved ? 'approved' : 'rejected',
    arbiterModel,
    confidence: arbiterDecision.confidence,
    reasoning: arbiterDecision.reasoning,
    recommendations: arbiterDecision.recommendations || [],
    timestamp: new Date().toISOString()
  }
}

/**
 * Calculate overall confidence across all stages
 */
function calculateOverallConfidence(results) {
  const confidences = Object.values(results.metrics.confidenceByStage).filter(c => typeof c === 'number')

  if (confidences.length === 0) {
    return 0
  }

  const average = confidences.reduce((a, b) => a + b, 0) / confidences.length

  // Weight by stage importance (later stages weight more)
  const weighted =
    (results.metrics.confidenceByStage.propose || 0) * 0.1 +
    (results.metrics.confidenceByStage.review || 0) * 0.15 +
    (results.metrics.confidenceByStage.verify || 0) * 0.2 +
    (results.metrics.confidenceByStage.validate || 0) * 0.25 +
    (results.metrics.confidenceByStage.confirm || 0) * 0.3

  return Math.round(weighted)
}

/**
 * Calculate average confidence from reviews
 */
function calculateAverageConfidence(reviews) {
  if (!Array.isArray(reviews) || reviews.length === 0) {
    return 0
  }

  const confidences = reviews
    .map(r => r.confidence)
    .filter(c => typeof c === 'number')

  if (confidences.length === 0) {
    return 0
  }

  const sum = confidences.reduce((a, b) => a + b, 0)
  return Math.round(sum / confidences.length)
}

/**
 * Format verification results for human reading
 */
export function formatVerificationResults(results) {
  const {
    stages,
    passed,
    finalVerdict,
    overallConfidence,
    metrics
  } = results

  let output = `\n${'='.repeat(60)}\n`
  output += `QUINTUPLE VERIFICATION RESULTS\n`
  output += `${'='.repeat(60)}\n\n`

  // Summary
  const verdict = passed ? '✅ APPROVED' : '❌ REJECTED'
  output += `Final Verdict: ${verdict}\n`
  output += `Reason: ${finalVerdict}\n`
  output += `Overall Confidence: ${overallConfidence}%\n`
  output += `Stages Passed: ${metrics.passedStages}/${metrics.totalStages}\n\n`

  // Stage details
  output += `STAGE BREAKDOWN:\n`
  output += `${'-'.repeat(60)}\n\n`

  const stageOrder = ['propose', 'review', 'verify', 'validate', 'confirm']

  stageOrder.forEach(stageName => {
    const stage = stages[stageName]
    if (!stage) return

    const icon = stage.passed || stage.status === 'passed' ? '✅' : '❌'
    output += `${icon} Stage ${stage.stage}: ${stage.name}\n`
    output += `   Status: ${stage.status}\n`
    output += `   Confidence: ${stage.confidence}%\n`

    if (stageName === 'review') {
      output += `   Approval Rate: ${stage.approvalRate}% (${stage.approvedCount}/${stage.totalReviewers})\n`
    } else if (stageName === 'verify') {
      output += `   Survival Rate: ${stage.survivalRate}% (${stage.survivedCount}/${stage.totalVerifiers})\n`
    } else if (stageName === 'validate') {
      output += `   Pass Rate: ${stage.passRate}% (${stage.passedCount}/${stage.totalValidators})\n`
    } else if (stageName === 'confirm') {
      output += `   Arbiter: ${stage.arbiterModel}\n`
      output += `   Decision: ${stage.arbiterDecision}\n`
      if (stage.recommendations.length > 0) {
        output += `   Recommendations: ${stage.recommendations.join(', ')}\n`
      }
    }

    output += `\n`
  })

  output += `${'='.repeat(60)}\n`

  return output
}

/**
 * Get detailed stage information
 */
export function getStageDetails(results, stageName) {
  const stage = results.stages[stageName]

  if (!stage) {
    return null
  }

  return {
    name: stage.name,
    status: stage.status,
    passed: stage.passed !== undefined ? stage.passed : stage.status === 'passed',
    confidence: stage.confidence,
    details: stage,
    timestamp: stage.timestamp
  }
}

/**
 * Utility: capitalize string
 */
function capitalize(str) {
  if (!str) return ''
  return str.charAt(0).toUpperCase() + str.slice(1)
}

// Export all functions
export default {

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('./fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback
}

  runQuintupleVerification,
  formatVerificationResults,
  getStageDetails
}
