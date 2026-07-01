// AI Learning System
// Captures arbiter/worker decisions and learns from them over time
// Provides feedback to improve future decisions

/**
 * Captures a decision for learning
 * Stores: what workers proposed, what arbiter selected, why, outcome
 *
 * @param {Function} agent - The agent function
 * @param {Object} decision - Decision metadata
 * @param {string} decision.workflow - Which workflow (code-test, code-solve, pr-review)
 * @param {string} decision.task_type - Type of task (test_plan, bug_fix, pr_review)
 * @param {string[]} decision.worker_models - Models that proposed
 * @param {Object[]} decision.worker_proposals - What each worker proposed
 * @param {string} decision.arbiter_model - Model that decided
 * @param {number} decision.selected_index - Which proposal was selected
 * @param {string} decision.why_accepted - Why arbiter accepted it
 * @param {Object} decision.rejection_reasons - Why others were rejected
 * @param {number} decision.consensus_score - Consensus percentage
 * @param {string} decision.outcome - Optional: did it work? (success, failed, unknown)
 * @param {number} decision.quality_score - Optional: quality score 0-1
 * @returns {Promise<Object>} Learning entry
 */
export async function captureDecision(agent, decision) {
  const learningEntry = {
    // Metadata
    timestamp: new Date().toISOString(),
    workflow: decision.workflow,
    task_type: decision.task_type,

    // Workers
    worker_models: decision.worker_models,
    worker_proposals: decision.worker_proposals.map((p, idx) => ({
      model: decision.worker_models[idx],
      selected: idx === decision.selected_index,
      confidence: p?.confidence || 0,
      approach: p?.approach || p?.test_strategy || '',
      rationale: p?.rationale || ''
    })),

    // Arbiter
    arbiter_model: decision.arbiter_model,
    selected_model: decision.worker_models[decision.selected_index],
    selected_index: decision.selected_index,
    why_accepted: decision.why_accepted,
    rejection_reasons: decision.rejection_reasons || {},
    consensus_score: decision.consensus_score,

    // Outcome (if known)
    outcome: decision.outcome || 'unknown',
    outcome_timestamp: decision.outcome ? new Date().toISOString() : null,
    quality_score: decision.quality_score
  }

  // Store to learning database
  const learningDir = `${process.env.HOME}/.claude/learning`
  const learningFile = `${learningDir}/decisions.jsonl`

  await agent(`Store learning entry to database.

Create directory if needed and append to JSONL file:

mkdir -p ${learningDir}
echo '${JSON.stringify(learningEntry)}' >> ${learningFile}

Return status.`, {
    label: 'Capture Learning'
  })

  // Extract procedural rule if successful
  if (decision.outcome === 'success' && decision.quality_score >= 0.75) {
    try {
      const { recordProceduralRule } = await import('./procedural-rules-adapter.js')

      await recordProceduralRule({
        condition: {
          workflow: decision.workflow,
          task_type: decision.task_type
        },
        action: `use_model_${decision.worker_models[decision.selected_index]}`,
        confidence: decision.quality_score || decision.consensus_score / 100,
        evidence_count: 1
      })
    } catch (err) {
      // Silent fail - procedural rules are optional enhancement
      console.warn('Failed to extract procedural rule:', err.message)
    }
  }

  return learningEntry
}

/**
 * Queries learning database for patterns
 *
 * @param {Function} agent - The agent function
 * @param {Object} query - Query filters
 * @param {string} query.workflow - Filter by workflow
 * @param {string} query.task_type - Filter by task type
 * @param {string} query.arbiter_model - Filter by arbiter
 * @param {number} query.limit - Max results (default: 100)
 * @returns {Promise<Object>} Learning patterns
 */
export async function queryLearnings(agent, query = {}) {
  const {
    workflow = null,
    task_type = null,
    arbiter_model = null,
    limit = 100
  } = query

  const learningFile = `${process.env.HOME}/.claude/learning/decisions.jsonl`

  const result = await agent(`Query learning database for patterns.

Read decisions from:
${learningFile}

Filter by:
${workflow ? `- Workflow: ${workflow}` : ''}
${task_type ? `- Task type: ${task_type}` : ''}
${arbiter_model ? `- Arbiter: ${arbiter_model}` : ''}

Analyze and return:
1. Total decisions matching filter
2. Model selection frequency (which models selected most often)
3. Common rejection reasons
4. Average confidence scores by model
5. Arbiter agreement patterns
6. Success rates (if outcome data available)

Limit to most recent ${limit} decisions.

Return structured analysis.`, {
    label: 'Query Learnings',
    schema: {
      type: 'object',
      properties: {
        total_decisions: { type: 'number' },
        model_selection_frequency: {
          type: 'object',
          additionalProperties: { type: 'number' }
        },
        common_rejections: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              model: { type: 'string' },
              reason: { type: 'string' },
              count: { type: 'number' }
            }
          }
        },
        avg_confidence_by_model: {
          type: 'object',
          additionalProperties: { type: 'number' }
        },
        arbiter_patterns: {
          type: 'object',
          properties: {
            most_used_arbiter: { type: 'string' },
            arbiters_used: { type: 'object' }
          }
        },
        success_rate: {
          type: 'object',
          properties: {
            total_with_outcome: { type: 'number' },
            successful: { type: 'number' },
            failed: { type: 'number' }
          }
        }
      }
    }
  })

  return result
}

/**
 * Gets learning feedback for workers before they propose
 * Shows them what has worked well in the past
 *
 * @param {Function} agent - The agent function
 * @param {Object} context - Context for feedback
 * @param {string} context.workflow - Current workflow
 * @param {string} context.task_type - Current task type
 * @param {string} context.worker_model - This worker's model
 * @returns {Promise<string>} Feedback text to include in worker prompt
 */
export async function getWorkerFeedback(agent, context) {
  const patterns = await queryLearnings(agent, {
    workflow: context.workflow,
    task_type: context.task_type,
    limit: 50
  })

  if (!patterns || patterns.total_decisions === 0) {
    return '' // No historical data yet
  }

  // Build feedback text
  let feedback = `\n\n**Historical Context (Learn from Past Decisions):**\n\n`

  // Show which models are selected most often for this task
  const selectionFreq = patterns.model_selection_frequency || {}
  const sortedModels = Object.entries(selectionFreq).sort((a, b) => b[1] - a[1])

  if (sortedModels.length > 0) {
    feedback += `For ${context.task_type} tasks, models selected:\n`
    sortedModels.slice(0, 3).forEach(([model, count]) => {
      const percentage = Math.round((count / patterns.total_decisions) * 100)
      feedback += `- ${model}: ${count} times (${percentage}%)\n`
    })
    feedback += `\n`
  }

  // Show common rejection reasons for this worker's model
  const rejections = patterns.common_rejections || []
  const thisModelRejections = rejections.filter(r => r.model === context.worker_model)

  if (thisModelRejections.length > 0) {
    feedback += `Your model (${context.worker_model}) was previously rejected for:\n`
    thisModelRejections.slice(0, 3).forEach(r => {
      feedback += `- ${r.reason} (${r.count} times)\n`
    })
    feedback += `\nConsider avoiding these issues in your proposal.\n\n`
  }

  // Show average confidence scores
  const avgConfidence = patterns.avg_confidence_by_model || {}
  if (avgConfidence[context.worker_model]) {
    feedback += `Your model's average confidence: ${Math.round(avgConfidence[context.worker_model])}%\n`
    feedback += `(Aim higher to increase selection chances)\n\n`
  }

  return feedback
}

/**
 * Gets learning feedback for arbiter before decision
 * Shows them historical patterns to inform their decision
 *
 * @param {Function} agent - The agent function
 * @param {Object} context - Context for feedback
 * @param {string} context.workflow - Current workflow
 * @param {string} context.task_type - Current task type
 * @param {string[]} context.worker_models - Models proposing
 * @returns {Promise<string>} Feedback text to include in arbiter prompt
 */
export async function getArbiterFeedback(agent, context) {
  const patterns = await queryLearnings(agent, {
    workflow: context.workflow,
    task_type: context.task_type,
    limit: 50
  })

  if (!patterns || patterns.total_decisions === 0) {
    return '' // No historical data yet
  }

  let feedback = `\n\n**Historical Decision Patterns (Learn from Past Arbiters):**\n\n`

  // Show selection patterns
  const selectionFreq = patterns.model_selection_frequency || {}
  feedback += `For ${context.task_type} tasks:\n`
  context.worker_models.forEach(model => {
    const count = selectionFreq[model] || 0
    const percentage = patterns.total_decisions > 0
      ? Math.round((count / patterns.total_decisions) * 100)
      : 0
    feedback += `- ${model}: selected ${count}/${patterns.total_decisions} times (${percentage}%)\n`
  })
  feedback += `\n`

  // Show common rejection patterns
  const rejections = patterns.common_rejections || []
  const topRejections = rejections.slice(0, 5)

  if (topRejections.length > 0) {
    feedback += `Common rejection reasons in past decisions:\n`
    topRejections.forEach(r => {
      feedback += `- ${r.model}: "${r.reason}" (${r.count} times)\n`
    })
    feedback += `\n`
  }

  // Show success patterns if available
  const successRate = patterns.success_rate
  if (successRate && successRate.total_with_outcome > 5) {
    const successPct = Math.round((successRate.successful / successRate.total_with_outcome) * 100)
    feedback += `Historical success rate: ${successPct}% (${successRate.successful}/${successRate.total_with_outcome})\n`
    feedback += `Use these patterns to inform your decision.\n\n`
  }

  feedback += `**Make your decision based on proposal quality, but consider these patterns.**\n`

  return feedback
}

/**
 * Updates outcome for a previous decision
 * Call this when you know if the decision worked out
 *
 * @param {Function} agent - The agent function
 * @param {Object} update - Update data
 * @param {string} update.decision_id - ID or timestamp of decision
 * @param {string} update.outcome - 'success', 'failed', 'partial'
 * @param {string} update.notes - Optional notes about outcome
 * @param {Object} update.context - Optional context for rule extraction
 */
export async function updateOutcome(agent, update) {
  const learningFile = `${process.env.HOME}/.claude/learning/decisions.jsonl`

  await agent(`Update outcome for decision.

Find decision with timestamp: ${update.decision_id}
Update outcome to: ${update.outcome}
Notes: ${update.notes || 'none'}

Append updated record to outcomes log.

Return status.`, {
    label: 'Update Outcome'
  })

  // Extract procedural rule if successful
  if (update.outcome === 'success' && update.context) {
    try {
      const { recordProceduralRule } = await import('./procedural-rules-adapter.js')
      const { workflow, task_type, model, quality_score } = update.context

      if (workflow && task_type && model && quality_score >= 0.75) {
        await recordProceduralRule({
          condition: { workflow, task_type },
          action: `use_model_${model}`,
          confidence: quality_score,
          evidence_count: 1
        })
      }
    } catch (err) {
      // Silent fail - procedural rules are optional enhancement
      console.warn('Failed to extract procedural rule:', err.message)
    }
  }
}

/**
 * Generates a learning report
 * Summary of all learnings across all workflows
 *
 * @param {Function} agent - The agent function
 * @returns {Promise<Object>} Learning report
 */
export async function generateLearningReport(agent) {
  const allPatterns = await queryLearnings(agent, { limit: 1000 })

  const report = {
    total_decisions: allPatterns.total_decisions,

    model_performance: allPatterns.model_selection_frequency,

    top_models: Object.entries(allPatterns.model_selection_frequency || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([model, count]) => ({
        model,
        selected_count: count,
        percentage: Math.round((count / allPatterns.total_decisions) * 100)
      })),

    rejection_patterns: allPatterns.common_rejections,

    arbiter_patterns: allPatterns.arbiter_patterns,

    success_metrics: allPatterns.success_rate,

    recommendations: generateRecommendations(allPatterns)
  }

  return report
}

/**
 * Generates recommendations based on learning patterns
 */
function generateRecommendations(patterns) {
  const recommendations = []

  // Recommend most successful models
  const selectionFreq = patterns.model_selection_frequency || {}
  const topModel = Object.entries(selectionFreq).sort((a, b) => b[1] - a[1])[0]

  if (topModel) {
    recommendations.push({
      type: 'model_preference',
      message: `${topModel[0]} is selected most often (${topModel[1]} times) - consider prioritizing it for important tasks`
    })
  }

  // Warn about commonly rejected models
  const rejections = patterns.common_rejections || []
  const frequentlyRejected = rejections.filter(r => r.count > 5)

  frequentlyRejected.forEach(r => {
    recommendations.push({
      type: 'avoid_pattern',
      message: `${r.model} often rejected for: "${r.reason}" - address this in future proposals`
    })
  })

  // Success rate recommendations
  const successRate = patterns.success_rate
  if (successRate && successRate.total_with_outcome > 10) {
    const successPct = Math.round((successRate.successful / successRate.total_with_outcome) * 100)
    if (successPct < 70) {
      recommendations.push({
        type: 'improve_quality',
        message: `Success rate is ${successPct}% - review and improve decision quality`
      })
    }
  }

  return recommendations
}

// ============================================================================
// INLINE VERSION (for workflows that can't use imports)
// ============================================================================

export const INLINE_LEARNING_SYSTEM = `
// Inline learning system (copy into workflows)

async function captureDecision(agent, decision) {
  const learningEntry = {
    timestamp: new Date().toISOString(),
    workflow: decision.workflow,
    task_type: decision.task_type,
    worker_models: decision.worker_models,
    selected_model: decision.worker_models[decision.selected_index],
    arbiter_model: decision.arbiter_model,
    why_accepted: decision.why_accepted,
    rejection_reasons: decision.rejection_reasons,
    consensus_score: decision.consensus_score
  }

  const learningDir = \`\${process.env.HOME}/.claude/learning\`
  await agent(\`mkdir -p \${learningDir} && echo '\${JSON.stringify(learningEntry)}' >> \${learningDir}/decisions.jsonl\`, {
    label: 'Capture Learning'
  })

  return learningEntry
}

async function getWorkerFeedback(agent, context) {
  // Query past decisions and build feedback
  // (simplified version - see full implementation above)
  return \`Historical data shows \${context.worker_model} selected X% of time for \${context.task_type} tasks.\`
}
`
