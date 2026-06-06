// Enhanced AI Attribution Utility
// Full transparency: arbiter model + reasoning, all worker proposals + suggestions
// Used by code-test, code-solve, code-review, and other arbiter/worker workflows

/**
 * Creates comprehensive AI attribution metadata for arbiter/worker pattern
 *
 * INCLUDES:
 * - Arbiter AI: which model, why it accepted, why it rejected others
 * - Accepted Worker: which model, its full proposal/suggestion
 * - Rejected Workers: each model, their proposals, specific rejection reasons
 *
 * @param {Object} options - Attribution options
 * @param {string[]} options.workerModels - List of worker model identifiers
 * @param {Object[]} options.workerProposals - Proposals from each worker
 * @param {string} options.arbiterModel - Arbiter model identifier
 * @param {Object} options.arbiterDecision - Decision object from arbiter
 * @param {number} options.selectedIndex - Index of selected proposal
 * @returns {Object} Full attribution metadata with ALL details
 */
export function createArbiterAttribution({
  workerModels,
  workerProposals,
  arbiterModel,
  arbiterDecision,
  selectedIndex
}) {
  // Build detailed worker proposals (ALL workers, accepted and rejected)
  const allWorkerProposals = workerModels.map((model, idx) => ({
    worker_model: model,
    worker_index: idx,
    selected: idx === selectedIndex,
    confidence: workerProposals[idx]?.confidence || 0,
    approach: workerProposals[idx]?.approach || workerProposals[idx]?.test_strategy || workerProposals[idx]?.fix_approach || '',
    rationale: workerProposals[idx]?.rationale || workerProposals[idx]?.reasoning || '',
    details: workerProposals[idx]?.code_changes || workerProposals[idx]?.test_steps || workerProposals[idx]?.implementation || '',
    test_plan: workerProposals[idx]?.test_plan || '',
    files_modified: workerProposals[idx]?.files_modified || [],
    // Include full proposal for reference
    full_proposal: workerProposals[idx]
  }))

  const acceptedWorker = allWorkerProposals[selectedIndex]
  const rejectedWorkers = allWorkerProposals.filter((_, idx) => idx !== selectedIndex)

  return {
    total_models_reviewed: workerModels.length,

    // ARBITER DETAILS - WHO made the decision and WHY
    arbiter: {
      model: arbiterModel,
      decision: 'selected',
      selected_index: selectedIndex,
      selected_worker: workerModels[selectedIndex],

      // WHY accepted this proposal
      why_accepted: arbiterDecision?.reasoning || arbiterDecision?.why_accepted ||
        `Selected ${workerModels[selectedIndex]} proposal (highest quality/confidence)`,

      // WHY rejected others (specific reasons per model)
      rejection_reasons: arbiterDecision?.rejection_reasons || {},

      // Overall consensus score
      consensus_score: arbiterDecision?.consensus_score || 0,

      // Additional arbiter reasoning
      reasoning: arbiterDecision?.reasoning || '',
      timestamp: new Date().toISOString()
    },

    // ACCEPTED WORKER DETAILS - WHAT was selected
    accepted_worker: {
      model: workerModels[selectedIndex],
      index: selectedIndex,
      confidence: acceptedWorker.confidence,
      approach: acceptedWorker.approach,
      rationale: acceptedWorker.rationale,
      details: acceptedWorker.details,
      test_plan: acceptedWorker.test_plan,
      files_modified: acceptedWorker.files_modified,
      full_proposal: acceptedWorker.full_proposal
    },

    // REJECTED WORKERS DETAILS - WHAT was rejected and WHY
    rejected_workers: rejectedWorkers.map(worker => ({
      model: worker.worker_model,
      index: worker.worker_index,
      confidence: worker.confidence,
      approach: worker.approach,
      rationale: worker.rationale,
      details: worker.details,
      test_plan: worker.test_plan,
      files_modified: worker.files_modified,

      // Specific rejection reason for this model
      rejection_reason: arbiterDecision?.rejection_reasons?.[worker.worker_model] ||
        `Not selected by ${arbiterModel} arbiter - alternative approach considered`,

      full_proposal: worker.full_proposal
    })),

    // ALL WORKERS (for reference)
    all_workers: allWorkerProposals,

    // CONSENSUS SUMMARY
    consensus: {
      models_proposed: workerModels.length,
      selected_by_arbiter: 1,
      confidence_range: {
        min: Math.min(...allWorkerProposals.map(w => w.confidence)),
        max: Math.max(...allWorkerProposals.map(w => w.confidence)),
        avg: Math.round(allWorkerProposals.reduce((sum, w) => sum + w.confidence, 0) / allWorkerProposals.length)
      },
      approaches_considered: allWorkerProposals.map(w => w.approach).filter(Boolean)
    },

    // LEGACY FIELDS (backwards compatibility)
    worker_ai: {
      model: workerModels[selectedIndex],
      confidence: acceptedWorker.confidence,
      approach: acceptedWorker.approach,
      rationale: acceptedWorker.rationale
    },
    rejected_proposals: rejectedWorkers.map(w => ({
      model: w.worker_model,
      approach: w.approach,
      confidence: w.confidence,
      reason: w.rejection_reason,
      rationale: w.rationale
    }))
  }
}

/**
 * Formats attribution as comprehensive markdown
 *
 * Shows:
 * 1. Arbiter: who, why accepted, why rejected
 * 2. Accepted worker: model + full proposal
 * 3. Each rejected worker: model + proposal + rejection reason
 *
 * @param {Object} attribution - Attribution from createArbiterAttribution
 * @param {Object} options - Formatting options
 * @param {boolean} options.includeFullProposals - Show complete proposals (default: true)
 * @param {boolean} options.includeRejectionReasons - Show why each was rejected (default: true)
 * @param {boolean} options.includeConfidenceStats - Show confidence stats (default: true)
 * @param {boolean} options.compact - Compact format (default: false)
 * @returns {string} Markdown formatted attribution
 */
export function formatArbiterAttributionMarkdown(attribution, options = {}) {
  if (!attribution) return ''

  const {
    includeFullProposals = true,
    includeRejectionReasons = true,
    includeConfidenceStats = true,
    compact = false
  } = options

  const arbiter = attribution.arbiter || {}
  const acceptedWorker = attribution.accepted_worker || {}
  const rejectedWorkers = attribution.rejected_workers || []
  const consensus = attribution.consensus || {}

  let md = `## 🤖 AI Attribution\n\n`

  // ARBITER SECTION - WHO decided and WHY
  md += `### ⚖️ Arbiter AI Decision\n\n`
  md += `**Arbiter Model**: ${arbiter.model || 'unknown'}\n\n`

  md += `**✅ Why Accepted ${acceptedWorker.model}:**\n`
  md += `${arbiter.why_accepted || arbiter.reasoning || 'Best overall approach and implementation'}\n\n`

  if (includeRejectionReasons && rejectedWorkers.length > 0) {
    md += `**❌ Why Rejected Others:**\n`
    rejectedWorkers.forEach(worker => {
      md += `- **${worker.model}**: ${worker.rejection_reason}\n`
    })
    md += `\n`
  }

  md += `**Consensus Score**: ${arbiter.consensus_score || 0}%\n\n`

  // ACCEPTED WORKER SECTION - WHAT was selected
  md += `---\n\n`
  md += `### ✅ Accepted Proposal\n\n`
  md += `**Worker Model**: ${acceptedWorker.model || 'unknown'}\n`
  md += `**Confidence**: ${acceptedWorker.confidence || 0}%\n\n`

  if (!compact) {
    md += `**Approach:**\n${acceptedWorker.approach || 'N/A'}\n\n`

    if (acceptedWorker.rationale) {
      md += `**Rationale:**\n${acceptedWorker.rationale}\n\n`
    }

    if (includeFullProposals) {
      if (acceptedWorker.details) {
        md += `**Implementation Details:**\n\`\`\`\n${acceptedWorker.details}\n\`\`\`\n\n`
      }

      if (acceptedWorker.test_plan) {
        md += `**Test Plan:**\n${acceptedWorker.test_plan}\n\n`
      }

      if (acceptedWorker.files_modified?.length > 0) {
        md += `**Files Modified:**\n${acceptedWorker.files_modified.map(f => `- ${f}`).join('\n')}\n\n`
      }
    }
  }

  // REJECTED WORKERS SECTION - WHAT was rejected and WHY
  if (rejectedWorkers.length > 0) {
    md += `---\n\n`
    md += `### ❌ Rejected Proposals (${rejectedWorkers.length})\n\n`

    if (compact) {
      rejectedWorkers.forEach(worker => {
        md += `- **${worker.model}** (${worker.confidence}%): ${worker.rejection_reason}\n`
      })
      md += `\n`
    } else {
      rejectedWorkers.forEach((worker, idx) => {
        md += `#### ${idx + 1}. ${worker.model}\n\n`
        md += `**Confidence**: ${worker.confidence}%\n\n`
        md += `**Approach**: ${worker.approach || 'N/A'}\n\n`
        md += `**Why Not Selected**: ${worker.rejection_reason}\n\n`

        if (worker.rationale) {
          md += `**Rationale**: ${worker.rationale}\n\n`
        }

        if (includeFullProposals && worker.details) {
          md += `<details>\n<summary>View Full Proposal</summary>\n\n`
          md += `\`\`\`\n${worker.details}\n\`\`\`\n\n`
          md += `</details>\n\n`
        }
      })
    }
  }

  // CONSENSUS STATISTICS
  if (includeConfidenceStats && consensus.confidence_range) {
    md += `---\n\n`
    md += `### 📊 Consensus Statistics\n\n`
    md += `- **Total Models**: ${consensus.models_proposed || 0}\n`
    md += `- **Confidence Range**: ${consensus.confidence_range.min}% - ${consensus.confidence_range.max}%\n`
    md += `- **Average Confidence**: ${consensus.confidence_range.avg}%\n`
    md += `- **Approaches Considered**: ${consensus.approaches_considered?.length || 0}\n`
    md += `- **Final Decision By**: ${arbiter.model}\n`
    md += `- **Decision Time**: ${new Date(arbiter.timestamp).toLocaleString()}\n\n`
  }

  return md
}

/**
 * Compact one-line attribution summary
 */
export function formatAttributionSummary(attribution) {
  if (!attribution) return 'AI-generated'

  const arbiter = attribution.arbiter || {}
  const accepted = attribution.accepted_worker || {}
  const total = attribution.total_models_reviewed || 0

  return `${total} AI models reviewed | ${accepted.model} selected by ${arbiter.model} (${arbiter.consensus_score}% consensus)`
}

/**
 * Selects the best arbiter from available models
 * Prefers most capable models (opus > gpt-4 > grok-2 > gemini > sonnet)
 *
 * @param {string[]} models - Available models
 * @param {number} rotationIndex - Optional rotation index (default: 0 = most capable)
 * @returns {string} Selected arbiter model
 */
export function selectArbiter(models, rotationIndex = 0) {
  const ARBITER_PREFERENCE = [
    'opus', 'claude-3-opus', 'claude-opus',
    'gpt-4', 'gpt-4-turbo', 'gpt-4o',
    'grok-2', 'grok',
    'gemini-pro', 'gemini-2.0-flash-exp', 'gemini',
    'sonnet', 'claude-3-sonnet', 'claude-sonnet',
    'haiku', 'claude-3-haiku'
  ]

  // If rotation requested, rotate through available models
  if (rotationIndex > 0) {
    return models[rotationIndex % models.length]
  }

  // Otherwise, pick most capable
  for (const preferred of ARBITER_PREFERENCE) {
    if (models.includes(preferred)) {
      return preferred
    }
  }

  // Fallback to first available
  return models[0]
}

// ============================================================================
// INLINE VERSION (for workflows that can't use ES6 imports)
// ============================================================================

export const INLINE_ENHANCED_ATTRIBUTION = `
// Inline enhanced AI attribution (copy into workflows)

function createArbiterAttribution({workerModels, workerProposals, arbiterModel, arbiterDecision, selectedIndex}) {
  const allWorkerProposals = workerModels.map((model, idx) => ({
    worker_model: model,
    worker_index: idx,
    selected: idx === selectedIndex,
    confidence: workerProposals[idx]?.confidence || 0,
    approach: workerProposals[idx]?.approach || workerProposals[idx]?.test_strategy || '',
    rationale: workerProposals[idx]?.rationale || '',
    details: workerProposals[idx]?.code_changes || workerProposals[idx]?.test_steps || '',
    full_proposal: workerProposals[idx]
  }))

  const acceptedWorker = allWorkerProposals[selectedIndex]
  const rejectedWorkers = allWorkerProposals.filter((_, idx) => idx !== selectedIndex)

  return {
    total_models_reviewed: workerModels.length,
    arbiter: {
      model: arbiterModel,
      selected_worker: workerModels[selectedIndex],
      why_accepted: arbiterDecision?.reasoning || \`Selected \${workerModels[selectedIndex]} proposal\`,
      rejection_reasons: arbiterDecision?.rejection_reasons || {},
      consensus_score: arbiterDecision?.consensus_score || 0
    },
    accepted_worker: {
      model: workerModels[selectedIndex],
      confidence: acceptedWorker.confidence,
      approach: acceptedWorker.approach,
      rationale: acceptedWorker.rationale,
      details: acceptedWorker.details
    },
    rejected_workers: rejectedWorkers.map(w => ({
      model: w.worker_model,
      confidence: w.confidence,
      approach: w.approach,
      rejection_reason: arbiterDecision?.rejection_reasons?.[w.worker_model] || \`Not selected by \${arbiterModel}\`
    }))
  }
}
`
