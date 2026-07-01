/**
 * Model Performance Tracking
 *
 * Learn which models are good at what through attribution tracking.
 * Enables smart model assignment based on historical performance.
 *
 * Concepts:
 * - Track performance by task type (security, logic, refactoring, etc.)
 * - Analyze attribution data (which model found what)
 * - Smart model selection (use best model for task)
 * - Store learnings in global memory
 * - RAG-enabled queries
 * - PostgreSQL model loading (all 135+ models from database)
 *
 * Usage:
 *   const tracker = new ModelPerformanceTracker()
 *   tracker.recordTask('opus', 'security', { findings: 5, accuracy: 0.92 })
 *   tracker.recordTask('sonnet', 'security', { findings: 3, accuracy: 0.88 })
 *
 *   const best = tracker.getBestModel('security')
 *   // Returns: 'opus' (based on accuracy + findings)
 */

import { selectWorkerModels } from './model-loader.js'

export class ModelPerformanceTracker {
  constructor(learningAdapter = null) {
    this.tasks = []        // All task records
    this.models = {}       // Performance by model
    this.taskTypes = {}    // Performance by task type
    this.learningAdapter = learningAdapter  // Optional OrchestratorLearningAdapter for PostgreSQL
  }

  /**
   * Record task performance
   */
  recordTask(model, taskType, metrics) {
    const record = {
      timestamp: Date.now(),
      model,
      taskType,
      metrics: {
        findings: metrics.findings || 0,
        accuracy: metrics.accuracy || 0,
        precision: metrics.precision || 0,
        consensus: metrics.consensus || 0,
        unique: metrics.unique || 0,
        ...metrics
      }
    }

    this.tasks.push(record)

    // Update model stats
    if (!this.models[model]) {
      this.models[model] = {
        totalTasks: 0,
        taskTypes: {},
        overallScore: 0
      }
    }

    this.models[model].totalTasks++

    if (!this.models[model].taskTypes[taskType]) {
      this.models[model].taskTypes[taskType] = {
        count: 0,
        avgAccuracy: 0,
        avgFindings: 0,
        avgConsensus: 0,
        score: 0
      }
    }

    const taskStats = this.models[model].taskTypes[taskType]
    taskStats.count++
    taskStats.avgAccuracy = this._updateAverage(
      taskStats.avgAccuracy,
      metrics.accuracy || 0,
      taskStats.count
    )
    taskStats.avgFindings = this._updateAverage(
      taskStats.avgFindings,
      metrics.findings || 0,
      taskStats.count
    )
    taskStats.avgConsensus = this._updateAverage(
      taskStats.avgConsensus,
      metrics.consensus || 0,
      taskStats.count
    )

    // Calculate composite score (accuracy 50%, consensus 30%, findings 20%)
    taskStats.score = (
      taskStats.avgAccuracy * 0.5 +
      taskStats.avgConsensus * 0.3 +
      Math.min(taskStats.avgFindings / 10, 1.0) * 0.2
    )

    // Update task type stats
    if (!this.taskTypes[taskType]) {
      this.taskTypes[taskType] = {
        models: {}
      }
    }

    this.taskTypes[taskType].models[model] = taskStats.score

    // Wire to PostgreSQL monitoring.model_tuning (Issue #251)
    if (this.learningAdapter) {
      this.learningAdapter.recordFeedback(model, {
        success: (metrics.accuracy || 0) > 0.5,
        quality: taskStats.score,
        cost: metrics.cost_usd || 0,
        duration: metrics.duration_ms || 0,
        taskType: taskType,
        confidence: metrics.confidence || taskStats.avgConsensus
      }).catch(err => {
        console.warn(`[model-performance] Failed to record to PostgreSQL: ${err.message}`)
      })
    }

    return record
  }

  /**
   * Get best model for task type
   */
  getBestModel(taskType, options = {}) {
    const minTasks = options.minTasks || 3
    const excludeModels = options.exclude || []

    const candidates = []

    Object.entries(this.models).forEach(([model, stats]) => {
      if (excludeModels.includes(model)) return

      const taskStats = stats.taskTypes[taskType]
      if (!taskStats || taskStats.count < minTasks) return

      candidates.push({
        model,
        score: taskStats.score,
        accuracy: taskStats.avgAccuracy,
        consensus: taskStats.avgConsensus,
        findings: taskStats.avgFindings,
        tasks: taskStats.count
      })
    })

    if (candidates.length === 0) {
      return null
    }

    // Sort by score (highest first)
    candidates.sort((a, b) => b.score - a.score)

    return {
      recommended: candidates[0].model,
      alternatives: candidates.slice(1, 3).map(c => c.model),
      reasoning: `${candidates[0].model} has highest score (${candidates[0].score.toFixed(2)}) for ${taskType} based on ${candidates[0].tasks} tasks`,
      stats: candidates[0]
    }
  }

  /**
   * Get model strengths and weaknesses
   */
  getModelProfile(model) {
    const stats = this.models[model]
    if (!stats) {
      return null
    }

    const taskScores = Object.entries(stats.taskTypes).map(([taskType, taskStats]) => ({
      taskType,
      score: taskStats.score,
      count: taskStats.count
    }))

    taskScores.sort((a, b) => b.score - a.score)

    return {
      model,
      totalTasks: stats.totalTasks,
      strengths: taskScores.slice(0, 3),
      weaknesses: taskScores.slice(-3).reverse(),
      allTasks: taskScores
    }
  }

  /**
   * Recommend model rotation for diversity
   */
  recommendRotation(taskType, currentModels = []) {
    const candidates = []

    Object.entries(this.models).forEach(([model, stats]) => {
      const taskStats = stats.taskTypes[taskType]
      if (!taskStats) return

      candidates.push({
        model,
        score: taskStats.score,
        recentlyUsed: currentModels.includes(model)
      })
    })

    // Sort by: not recently used first, then by score
    candidates.sort((a, b) => {
      if (a.recentlyUsed !== b.recentlyUsed) {
        return a.recentlyUsed ? 1 : -1
      }
      return b.score - a.score
    })

    return candidates.slice(0, 5).map(c => c.model)
  }

  /**
   * Generate performance report
   */
  toMarkdown() {
    const lines = []

    lines.push('# Model Performance Report')
    lines.push('')

    // Overall stats
    lines.push('## Overall Statistics')
    lines.push(`- Total tasks tracked: ${this.tasks.length}`)
    lines.push(`- Models tracked: ${Object.keys(this.models).length}`)
    lines.push(`- Task types: ${Object.keys(this.taskTypes).length}`)
    lines.push('')

    // Model profiles
    lines.push('## Model Profiles')
    Object.keys(this.models).forEach(model => {
      const profile = this.getModelProfile(model)
      lines.push(`### ${model}`)
      lines.push(`- Total tasks: ${profile.totalTasks}`)

      if (profile.strengths.length > 0) {
        lines.push('- **Strengths:**')
        profile.strengths.forEach(s => {
          lines.push(`  - ${s.taskType}: ${s.score.toFixed(2)} (${s.count} tasks)`)
        })
      }

      if (profile.weaknesses.length > 0 && profile.weaknesses[0].count > 0) {
        lines.push('- **Weaknesses:**')
        profile.weaknesses.forEach(w => {
          if (w.count > 0) {
            lines.push(`  - ${w.taskType}: ${w.score.toFixed(2)} (${w.count} tasks)`)
          }
        })
      }

      lines.push('')
    })

    // Task type recommendations
    lines.push('## Recommended Models by Task Type')
    Object.keys(this.taskTypes).forEach(taskType => {
      const recommendation = this.getBestModel(taskType)
      if (recommendation) {
        lines.push(`### ${taskType}`)
        lines.push(`- **Best:** ${recommendation.recommended}`)
        lines.push(`- **Score:** ${recommendation.stats.score.toFixed(2)}`)
        lines.push(`- **Accuracy:** ${(recommendation.stats.accuracy * 100).toFixed(0)}%`)
        lines.push(`- **Consensus:** ${(recommendation.stats.consensus * 100).toFixed(0)}%`)
        if (recommendation.alternatives.length > 0) {
          lines.push(`- **Alternatives:** ${recommendation.alternatives.join(', ')}`)
        }
        lines.push('')
      }
    })

    return lines.join('\n')
  }

  /**
   * Export to JSON for storage in memory
   */
  toJSON() {
    return {
      tasks: this.tasks,
      models: this.models,
      taskTypes: this.taskTypes,
      generated: new Date().toISOString()
    }
  }

  /**
   * Load from JSON (from memory)
   */
  fromJSON(data) {
    this.tasks = data.tasks || []
    this.models = data.models || {}
    this.taskTypes = data.taskTypes || {}
    return this
  }

  /**
   * Update running average
   */
  _updateAverage(currentAvg, newValue, count) {
    return (currentAvg * (count - 1) + newValue) / count
  }
}


/**
 * Smart model selector using performance tracking + RAG
 */
export class SmartModelSelector {
  constructor(performanceTracker, ragQuery = null) {
    this.tracker = performanceTracker
    this.ragQuery = ragQuery  // Optional RAG function
  }

  /**
   * Select best model for task
   */
  async selectModel(taskType, options = {}) {
    const excludeModels = options.exclude || []
    const fallback = options.fallback || 'opus'

    // Try performance-based selection first
    const recommendation = this.tracker.getBestModel(taskType, { exclude: excludeModels })

    if (recommendation) {
      return {
        model: recommendation.recommended,
        source: 'performance_tracking',
        confidence: recommendation.stats.score,
        reasoning: recommendation.reasoning
      }
    }

    // Fall back to RAG query if available
    if (this.ragQuery) {
      try {
        const ragResult = await this.ragQuery(`Which AI model is best at ${taskType} tasks?`)
        if (ragResult && ragResult.answer) {
          return {
            model: this._extractModelFromAnswer(ragResult.answer, fallback),
            source: 'rag_query',
            confidence: ragResult.retrieval_score || 0.5,
            reasoning: ragResult.answer
          }
        }
      } catch (e) {
        // RAG failed, continue to fallback
      }
    }

    // Final fallback
    return {
      model: fallback,
      source: 'fallback',
      confidence: 0,
      reasoning: `No performance data for ${taskType}, using fallback: ${fallback}`
    }
  }

  /**
   * Select diverse worker models
   */
  async selectWorkers(taskType, count = 3, options = {}) {
    const rotation = this.tracker.recommendRotation(taskType, options.exclude || [])

    if (rotation.length >= count) {
      return rotation.slice(0, count)
    }

    // Not enough models in rotation, load from PostgreSQL
    try {
      const modelsFromDB = await selectWorkerModels(count, options.exclude || [])
      if (modelsFromDB.length > 0) {
        const selected = [...rotation]
        for (const model of modelsFromDB) {
          if (selected.length >= count) break
          if (!selected.includes(model)) {
            selected.push(model)
          }
        }
        return selected.slice(0, count)
      }
    } catch (err) {
      console.warn('[model-performance] PostgreSQL fallback failed:', err.message)
    }

    // Final fallback: hardcoded defaults
    const defaults = ['opus', 'sonnet', 'gpt-4o', 'gemini-2.0-flash-exp', 'haiku']
    const selected = [...rotation]

    for (const model of defaults) {
      if (selected.length >= count) break
      if (!selected.includes(model) && !(options.exclude || []).includes(model)) {
        selected.push(model)
      }
    }

    return selected.slice(0, count)
  }

  _extractModelFromAnswer(answer, fallback) {
    const models = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    for (const model of models) {
      if (answer.toLowerCase().includes(model)) {
        return model
      }
    }
    return fallback
  }
}


// Example usage
if (typeof module !== 'undefined' && require.main === module) {
  console.log('Testing Model Performance Tracking\n')

  const tracker = new ModelPerformanceTracker()

  // Simulate task records
  tracker.recordTask('opus', 'security', { findings: 5, accuracy: 0.92, consensus: 0.85 })
  tracker.recordTask('opus', 'security', { findings: 6, accuracy: 0.90, consensus: 0.88 })
  tracker.recordTask('opus', 'security', { findings: 4, accuracy: 0.94, consensus: 0.82 })

  tracker.recordTask('sonnet', 'security', { findings: 3, accuracy: 0.85, consensus: 0.90 })
  tracker.recordTask('sonnet', 'logic', { findings: 7, accuracy: 0.93, consensus: 0.91 })
  tracker.recordTask('sonnet', 'logic', { findings: 6, accuracy: 0.91, consensus: 0.89 })

  tracker.recordTask('gpt4', 'performance', { findings: 8, accuracy: 0.89, consensus: 0.87 })
  tracker.recordTask('gpt4', 'performance', { findings: 7, accuracy: 0.91, consensus: 0.88 })

  // Test recommendations
  console.log('='.repeat(80))
  const securityRec = tracker.getBestModel('security')
  console.log('Best for security:', securityRec.recommended)
  console.log('Reasoning:', securityRec.reasoning)
  console.log()

  const logicRec = tracker.getBestModel('logic')
  console.log('Best for logic:', logicRec.recommended)
  console.log('Reasoning:', logicRec.reasoning)
  console.log()

  // Test profile
  console.log('='.repeat(80))
  const opusProfile = tracker.getModelProfile('opus')
  console.log(`${opusProfile.model} Profile:`)
  console.log('Strengths:', opusProfile.strengths.map(s => s.taskType))
  console.log()

  // Full report
  console.log('='.repeat(80))
  console.log(tracker.toMarkdown())
}
