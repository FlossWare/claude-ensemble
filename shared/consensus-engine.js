// Multi-Model Consensus Engine with Strategy Support
// Supports: rotating, single, majority, weighted, pairwise strategies
// Allows arbiter and worker model swapping
// OpenClaw integration: optional 7th worker with execution verification
//
// Feature flag: OPENCLAW_ENABLED=true (default: false)
// Graceful degradation: when OpenClaw unavailable, consensus continues with 6 models

import { recordArbiterOutcome } from './confidence-calibration-integration.cjs'

// Global state for rotating arbiter
let arbiterRotationIndex = 0

// ============================================================================
// OPENCLAW INTEGRATION
// ============================================================================

/**
 * Check if OpenClaw is enabled via feature flag.
 * Default: false. Set OPENCLAW_ENABLED=true to activate.
 */
function isOpenClawEnabled() {
  return process.env.OPENCLAW_ENABLED === 'true' || process.env.OPENCLAW_ENABLED === '1'
}

/**
 * Safely import and call getOpenClawVote. Returns null on any failure.
 * Uses dynamic import so the module never breaks if openclaw-client.js is missing.
 */
async function safeGetOpenClawVote(prompt, schema) {
  if (!isOpenClawEnabled()) return null
  try {
    const { getOpenClawVote } = await import('./openclaw-client.js')
    return await getOpenClawVote(prompt, schema)
  } catch (error) {
    // OpenClaw unavailable - graceful degradation
    return null
  }
}

/**
 * Format OpenClaw verification evidence for arbiter prompts.
 * Returns empty string when OpenClaw did not participate or is unavailable.
 */
function formatOpenClawEvidence(openclawResult) {
  if (!openclawResult) return ''

  const hasExecution = openclawResult.execution_performed === true
  const verificationStatus = openclawResult.verification_status || 'unknown'
  const confidence = openclawResult.confidence || 0

  let section = `
**OPENCLAW VERIFICATION** (unique: actual code execution):
- Verification Status: ${verificationStatus}
- Execution Performed: ${hasExecution ? 'YES' : 'NO'}
- Confidence: ${confidence}%
- Reasoning: ${openclawResult.reasoning || 'N/A'}`

  if (hasExecution && openclawResult.execution_results) {
    section += `
- Execution Results:
  - Command: ${openclawResult.execution_results.command || 'N/A'}
  - Exit Code: ${openclawResult.execution_results.exit_code ?? 'N/A'}
  - Output: ${openclawResult.execution_results.stdout || openclawResult.execution_results.stderr || 'N/A'}`
  }

  section += `

NOTE: OpenClaw provides execution-backed evidence. When execution was performed,
weight this evidence heavily as it represents ground truth, not just reasoning.
`
  return section
}

// ============================================================================
// MAIN API
// ============================================================================

export async function multiModelReview(prompt, schema, options = {}) {
  const {
    workers = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
    phase = 'Multi-Model Review',
    labelPrefix = 'Review',
    strategy = 'rotating', // rotating, single, majority, weighted, pairwise
    arbiterModel = null, // Auto-select based on strategy
    executionMode = 'parallel', // parallel, sequential
    includeOpenClaw = true, // Set false to explicitly exclude OpenClaw
  } = options

  const openclawActive = includeOpenClaw && isOpenClawEnabled()

  log(`🎯 Strategy: ${strategy} | Workers: ${workers.join(', ')}${openclawActive ? ' + openclaw' : ''}`)

  // Run all worker models (including OpenClaw if enabled)
  const workerReviews = await runWorkers(prompt, schema, workers, phase, labelPrefix, executionMode, openclawActive)

  // Build result object with named models
  const result = {
    allReviews: workerReviews.filter(Boolean)
  }

  // Map standard workers to named properties
  workers.forEach((model, i) => {
    result[model] = workerReviews[i]
  })

  // OpenClaw result is appended after standard workers
  if (openclawActive && workerReviews.length > workers.length) {
    result.openclaw = workerReviews[workers.length] || null
    if (result.openclaw) {
      log(`  OpenClaw: execution=${result.openclaw.execution_performed ? 'YES' : 'NO'}, confidence=${result.openclaw.confidence || 0}%`)
    } else {
      log(`  OpenClaw: unavailable, continuing with ${workers.length}-model consensus`)
    }
  } else {
    result.openclaw = null
  }

  // Legacy compatibility
  result.opus = result.opus || null
  result.sonnet = result.sonnet || null
  result.haiku = result.haiku || null
  result.gemini = result.gemini || null

  return result
}

async function runWorkers(prompt, schema, workers, phase, labelPrefix, executionMode, includeOpenClaw) {
  // Build standard worker tasks
  let workerTasks = workers.map(model =>
    () => agent(prompt, {
      schema,
      model,
      label: `${labelPrefix} (${capitalize(model)})`,
      phase
    })
  )

  // Add OpenClaw worker if enabled - runs in parallel with other workers
  if (includeOpenClaw) {
    workerTasks.push(
      () => safeGetOpenClawVote(prompt, schema)
    )
  }

  if (executionMode === 'sequential') {
    const results = []
    for (const task of workerTasks) {
      const result = await task()
      results.push(result)
    }
    return results
  } else {
    return await parallel(workerTasks)
  }
}

export async function arbiterDecision(context, reviews, options = {}) {
  const {
    phase = 'Arbiter Decision',
    decisionType = 'issue', // 'issue', 'pr', 'fix'
    strategy = 'rotating', // rotating, single, majority, weighted, pairwise
    arbiterModel = null, // Override arbiter model
  } = options

  // Select arbiter based on strategy
  const selectedArbiter = selectArbiter(strategy, arbiterModel, reviews)

  // Log strategy info
  log(`⚖️ Arbiter: ${capitalize(selectedArbiter)} (${strategy} strategy)`)

  // Strategy-specific decision making
  if (strategy === 'majority') {
    return majorityVoteDecision(reviews, decisionType)
  } else if (strategy === 'weighted') {
    return weightedConsensusDecision(context, reviews, decisionType, selectedArbiter, phase)
  } else if (strategy === 'pairwise') {
    return pairwiseDecision(context, reviews, decisionType, selectedArbiter, phase)
  } else {
    // rotating or single strategy - use standard arbiter
    return standardArbiterDecision(context, reviews, decisionType, selectedArbiter, phase)
  }
}

function selectArbiter(strategy, arbiterModel, reviews) {
  if (arbiterModel) {
    // Explicit arbiter specified
    return arbiterModel
  }

  if (strategy === 'rotating') {
    // Rotate between available models
    const availableModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'].filter(m => reviews[m])
    const selected = availableModels[arbiterRotationIndex % availableModels.length]
    arbiterRotationIndex++
    return selected
  } else if (strategy === 'single') {
    // Use Fable for single arbiter (most capable)
    return 'fable'
  } else if (strategy === 'weighted' || strategy === 'pairwise') {
    // Use Fable for complex strategies
    return 'fable'
  } else {
    // Default to Fable
    return 'fable'
  }
}

async function standardArbiterDecision(context, reviews, decisionType, arbiterModel, phase) {
  // Build arbiter prompt based on decision type, including OpenClaw evidence
  let arbiterPrompt = buildArbiterPrompt(context, reviews, decisionType)

  // Append OpenClaw execution evidence if available
  arbiterPrompt += formatOpenClawEvidence(reviews.openclaw)

  const decision = await agent(arbiterPrompt, {
    schema: {
      type: 'object',
      properties: {
        final_decision: { type: 'string' },
        consensus_score: { type: 'number', minimum: 0, maximum: 100 },
        accepted_model: { type: 'string' },
        accepted_reasoning: { type: 'string' },
        rejected_models: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              model: { type: 'string' },
              rejection_reason: { type: 'string' },
            },
            required: ['model', 'rejection_reason'],
          },
        },
        create_issue: { type: 'boolean' },
        issue_priority: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3', 'P4'] },
      },
      required: ['final_decision', 'consensus_score', 'accepted_model', 'accepted_reasoning', 'rejected_models'],
    },
    model: arbiterModel,
    label: `Arbiter (${capitalize(arbiterModel)})`,
    phase
  })

  decision.strategy = 'standard'
  decision.arbiter = arbiterModel
  decision.openclaw_evidence = reviews.openclaw?.execution_performed ? true : false

  // Record confidence calibration observations (Issue #264)
  try {
    const workerResults = Object.keys(reviews)
      .filter(k => k !== 'allReviews' && k !== 'openclaw' && reviews[k])
      .map(model => ({
        worker_id: model,
        model: model,
        confidence: reviews[model].confidence || 0,
        answer: reviews[model]
      }))

    await recordArbiterOutcome(
      workerResults,
      decision,
      decisionType,
      null // workflow_execution_id - can be passed via options if needed
    )
  } catch (err) {
    console.warn(`[confidence-calibration] Could not record arbiter outcome: ${err.message}`)
  }

  return decision
}

function majorityVoteDecision(reviews, decisionType) {
  // Simple majority vote - no arbiter overhead
  const allReviews = reviews.allReviews || Object.values(reviews).filter(Boolean)

  if (decisionType === 'issue') {
    const realIssueVotes = allReviews.filter(r => r.is_real_issue === true).length
    const falsePositiveVotes = allReviews.filter(r => r.is_real_issue === false).length

    const isRealIssue = realIssueVotes > falsePositiveVotes
    const consensusScore = Math.round((Math.max(realIssueVotes, falsePositiveVotes) / allReviews.length) * 100)

    // Find highest confidence model on winning side
    const winningSide = allReviews.filter(r => r.is_real_issue === isRealIssue)
    const bestModel = winningSide.sort((a, b) => (b.confidence || 0) - (a.confidence || 0))[0]

    return {
      final_decision: isRealIssue ? 'real_issue' : 'false_positive',
      consensus_score: consensusScore,
      accepted_model: 'majority_vote',
      accepted_reasoning: `${realIssueVotes}/${allReviews.length} models voted real issue`,
      rejected_models: [],
      create_issue: isRealIssue && consensusScore >= 60,
      issue_priority: bestModel?.severity_assessment === 'critical' ? 'P0' : 'P2',
      strategy: 'majority',
      arbiter: 'none'
    }
  }

  // Similar logic for other decision types
  return {
    final_decision: 'approved',
    consensus_score: 50,
    accepted_model: 'majority_vote',
    accepted_reasoning: 'Majority vote',
    rejected_models: [],
    strategy: 'majority',
    arbiter: 'none'
  }
}

async function weightedConsensusDecision(context, reviews, decisionType, arbiterModel, phase) {
  // Weight votes by confidence scores
  const allReviews = reviews.allReviews || Object.values(reviews).filter(Boolean)

  const openclawSection = formatOpenClawEvidence(reviews.openclaw)
  const arbiterPrompt = `You are the arbiter using WEIGHTED CONSENSUS strategy.

${buildArbiterPrompt(context, reviews, decisionType)}
${openclawSection}
IMPORTANT: Weight each model's vote by its confidence score.
Higher confidence models should have more influence on the final decision.
${openclawSection ? 'When OpenClaw provides execution evidence, weight it as near-ground-truth.' : ''}
Calculate weighted consensus and make your decision.`

  const decision = await agent(arbiterPrompt, {
    schema: {
      type: 'object',
      properties: {
        final_decision: { type: 'string' },
        consensus_score: { type: 'number', minimum: 0, maximum: 100 },
        accepted_model: { type: 'string' },
        accepted_reasoning: { type: 'string' },
        rejected_models: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              model: { type: 'string' },
              rejection_reason: { type: 'string' },
            },
            required: ['model', 'rejection_reason'],
          },
        },
        create_issue: { type: 'boolean' },
        issue_priority: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3', 'P4'] },
      },
      required: ['final_decision', 'consensus_score', 'accepted_model', 'accepted_reasoning'],
    },
    model: arbiterModel,
    label: `Weighted Arbiter (${capitalize(arbiterModel)})`,
    phase
  })

  decision.strategy = 'weighted'
  decision.arbiter = arbiterModel
  return decision
}

async function pairwiseDecision(context, reviews, decisionType, arbiterModel, phase) {
  // Workers review in pairs, arbiter synthesizes
  const openclawSection = formatOpenClawEvidence(reviews.openclaw)
  const arbiterPrompt = `You are the arbiter using PAIRWISE strategy.

${buildArbiterPrompt(context, reviews, decisionType)}
${openclawSection}
IMPORTANT: The models reviewed in pairs:
- Opus vs Sonnet
- Sonnet vs Haiku
- Haiku vs Opus
${openclawSection ? '\nOpenClaw execution evidence (if present) should be weighted as independent ground truth.' : ''}
Synthesize the pairwise comparisons into a final decision.`

  const decision = await agent(arbiterPrompt, {
    schema: {
      type: 'object',
      properties: {
        final_decision: { type: 'string' },
        consensus_score: { type: 'number', minimum: 0, maximum: 100 },
        accepted_model: { type: 'string' },
        accepted_reasoning: { type: 'string' },
        rejected_models: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              model: { type: 'string' },
              rejection_reason: { type: 'string' },
            },
          },
        },
        create_issue: { type: 'boolean' },
        issue_priority: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3', 'P4'] },
      },
      required: ['final_decision', 'consensus_score', 'accepted_model', 'accepted_reasoning'],
    },
    model: arbiterModel,
    label: `Pairwise Arbiter (${capitalize(arbiterModel)})`,
    phase
  })

  decision.strategy = 'pairwise'
  decision.arbiter = arbiterModel
  return decision
}

function buildArbiterPrompt(context, reviews, decisionType) {
  const { opus, sonnet, haiku, gemini } = reviews

  if (decisionType === 'issue') {
    return `You are the final arbiter. Review these AI assessments and make the final decision:

**Original Context**:
${context}

**OPUS ASSESSMENT**:
- Real Issue: ${opus?.is_real_issue ? 'YES' : 'NO'}
- Confidence: ${opus?.confidence || 0}%
- Severity: ${opus?.severity_assessment || 'N/A'}
- Reasoning: ${opus?.reasoning || 'N/A'}

**SONNET ASSESSMENT**:
- Real Issue: ${sonnet?.is_real_issue ? 'YES' : 'NO'}
- Confidence: ${sonnet?.confidence || 0}%
- Severity: ${sonnet?.severity_assessment || 'N/A'}
- Reasoning: ${sonnet?.reasoning || 'N/A'}

**HAIKU ASSESSMENT**:
- Real Issue: ${haiku?.is_real_issue ? 'YES' : 'NO'}
- Confidence: ${haiku?.confidence || 0}%
- Severity: ${haiku?.severity_assessment || 'N/A'}
- Reasoning: ${haiku?.reasoning || 'N/A'}

${gemini ? `**GEMINI ASSESSMENT**:
- Real Issue: ${gemini?.is_real_issue ? 'YES' : 'NO'}
- Confidence: ${gemini?.confidence || 0}%
- Severity: ${gemini?.severity_assessment || 'N/A'}
- Reasoning: ${gemini?.reasoning || 'N/A'}
` : ''}

Make your final decision:
1. Is this a real issue or false positive?
2. What's the consensus score (% agreement)?
3. Which model had the best analysis and WHY?
4. Why did you reject the other models?
5. Should we create a GitHub issue for this?
6. If yes, what priority (P0=critical, P1=high, P2=medium, P3=low)?`
  } else if (decisionType === 'pr') {
    return `You are the final arbiter. Review these AI PR assessments:

**Pull Request**:
${context}

**OPUS REVIEW**:
- Recommendation: ${opus?.approval_recommendation || 'N/A'}
- Quality: ${opus?.overall_quality || 0}%
- Confidence: ${opus?.confidence || 0}%

**SONNET REVIEW**:
- Recommendation: ${sonnet?.approval_recommendation || 'N/A'}
- Quality: ${sonnet?.overall_quality || 0}%
- Confidence: ${sonnet?.confidence || 0}%

**HAIKU REVIEW**:
- Recommendation: ${haiku?.approval_recommendation || 'N/A'}
- Quality: ${haiku?.overall_quality || 0}%
- Confidence: ${haiku?.confidence || 0}%

Final decision:
1. Should this PR be approved or require changes?
2. What's the consensus score?
3. Which model had the best analysis and WHY?
4. Why reject the others?`
  } else if (decisionType === 'fix') {
    return `You are the final arbiter. Review these AI fix proposals:

**Issue to Fix**:
${context}

**OPUS FIX**:
- Approach: ${opus?.approach || 'N/A'}
- Confidence: ${opus?.confidence || 0}%
- Rationale: ${opus?.rationale || 'N/A'}

**SONNET FIX**:
- Approach: ${sonnet?.approach || 'N/A'}
- Confidence: ${sonnet?.confidence || 0}%
- Rationale: ${sonnet?.rationale || 'N/A'}

**HAIKU FIX**:
- Approach: ${haiku?.approach || 'N/A'}
- Confidence: ${haiku?.confidence || 0}%
- Rationale: ${haiku?.rationale || 'N/A'}

Select the best fix:
1. Which fix is most appropriate?
2. What's the consensus score?
3. Why is this fix best?
4. Why reject the others?`
  }
}

export function calculateConsensus(reviews) {
  const total = reviews.filter(Boolean).length
  if (total === 0) return 0

  const trueCount = reviews.filter(r => r?.is_real_issue === true).length
  const falseCount = reviews.filter(r => r?.is_real_issue === false).length

  const majority = Math.max(trueCount, falseCount)
  return Math.round((majority / total) * 100)
}

export function formatConsensusVote(reviews) {
  const { opus, sonnet, haiku, gemini, openclaw } = reviews

  let voteText = `
**Voting Results**:
- Opus: ${opus?.is_real_issue ? 'REAL' : 'FALSE POSITIVE'} (${opus?.confidence || 0}%)
- Sonnet: ${sonnet?.is_real_issue ? 'REAL' : 'FALSE POSITIVE'} (${sonnet?.confidence || 0}%)
- Haiku: ${haiku?.is_real_issue ? 'REAL' : 'FALSE POSITIVE'} (${haiku?.confidence || 0}%)
${gemini ? `- Gemini: ${gemini?.is_real_issue ? 'REAL' : 'FALSE POSITIVE'} (${gemini?.confidence || 0}%)` : ''}`

  if (openclaw) {
    voteText += `
- OpenClaw: ${openclaw?.verification_status || 'N/A'} (${openclaw?.confidence || 0}%, execution: ${openclaw?.execution_performed ? 'YES' : 'NO'})`
  }

  const allVoters = [opus, sonnet, haiku, gemini, openclaw]
  voteText += `

**Consensus**: ${calculateConsensus(allVoters)}%
`
  return voteText
}

// Export OpenClaw helpers for use by other modules
export { isOpenClawEnabled, formatOpenClawEvidence, safeGetOpenClawVote }

// Utility functions
function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1)
}
