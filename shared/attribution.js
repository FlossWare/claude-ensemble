/**
 * Attribution Tracking for Multi-AI Consensus
 *
 * Track which AI said what in consensus workflows.
 * Helps with trust, debugging, and understanding diverse perspectives.
 *
 * Borrows concepts from consensus-ai.
 *
 * Usage:
 *   const tracker = new AttributionTracker()
 *   tracker.recordWorker('opus', 'Finding: Bug in line 42')
 *   tracker.recordWorker('sonnet', 'Finding: Bug in line 42')
 *   tracker.recordWorker('gpt4', 'Finding: Performance issue')
 *
 *   const summary = tracker.summarize()
 *   console.log(summary.consensus)  // Which findings had agreement
 *   console.log(summary.unique)     // Which findings were unique to one AI
 */

export class AttributionTracker {
  constructor() {
    this.workers = {}      // worker -> contributions
    this.arbiter = null    // arbiter decision
    this.timeline = []     // chronological record
  }

  /**
   * Record worker contribution
   */
  recordWorker(model, contribution, metadata = {}) {
    const record = {
      timestamp: Date.now(),
      model,
      type: 'worker',
      contribution,
      metadata
    }

    if (!this.workers[model]) {
      this.workers[model] = []
    }

    this.workers[model].push(record)
    this.timeline.push(record)

    return record
  }

  /**
   * Record arbiter decision
   */
  recordArbiter(model, decision, reasoning, metadata = {}) {
    const record = {
      timestamp: Date.now(),
      model,
      type: 'arbiter',
      decision,
      reasoning,
      metadata
    }

    this.arbiter = record
    this.timeline.push(record)

    return record
  }

  /**
   * Find consensus across workers
   *
   * Returns findings that multiple workers agreed on
   */
  findConsensus(threshold = 2) {
    const contributions = {}

    // Group by normalized contribution text
    Object.entries(this.workers).forEach(([model, records]) => {
      records.forEach(record => {
        const key = this._normalizeContribution(record.contribution)
        if (!contributions[key]) {
          contributions[key] = {
            text: record.contribution,
            models: [],
            count: 0
          }
        }
        contributions[key].models.push(model)
        contributions[key].count++
      })
    })

    // Filter by threshold
    const consensus = Object.values(contributions)
      .filter(c => c.count >= threshold)
      .sort((a, b) => b.count - a.count)

    return consensus
  }

  /**
   * Find unique contributions (only one AI found it)
   */
  findUnique() {
    const contributions = {}

    Object.entries(this.workers).forEach(([model, records]) => {
      records.forEach(record => {
        const key = this._normalizeContribution(record.contribution)
        if (!contributions[key]) {
          contributions[key] = {
            text: record.contribution,
            model,
            count: 0
          }
        }
        contributions[key].count++
      })
    })

    const unique = Object.values(contributions)
      .filter(c => c.count === 1)

    return unique
  }

  /**
   * Summarize attribution
   */
  summarize() {
    const consensus = this.findConsensus(2)
    const unique = this.findUnique()

    const workerCounts = Object.entries(this.workers).map(([model, records]) => ({
      model,
      contributions: records.length
    }))

    return {
      workers: workerCounts,
      arbiter: this.arbiter ? this.arbiter.model : null,
      consensus,
      unique,
      totalContributions: this.timeline.filter(t => t.type === 'worker').length,
      consensusRate: consensus.length / (consensus.length + unique.length) || 0
    }
  }

  /**
   * Format as markdown report
   */
  toMarkdown() {
    const summary = this.summarize()
    const lines = []

    lines.push('# Attribution Report')
    lines.push('')

    // Workers
    lines.push('## Workers')
    summary.workers.forEach(w => {
      lines.push(`- **${w.model}**: ${w.contributions} contribution(s)`)
    })
    lines.push('')

    // Arbiter
    if (summary.arbiter) {
      lines.push('## Arbiter')
      lines.push(`- **${summary.arbiter}**`)
      if (this.arbiter.reasoning) {
        lines.push(`  - Reasoning: ${this.arbiter.reasoning}`)
      }
      lines.push('')
    }

    // Consensus
    lines.push('## Consensus Findings')
    lines.push(`Found ${summary.consensus.length} findings with agreement:`)
    lines.push('')
    summary.consensus.forEach((c, i) => {
      lines.push(`${i + 1}. **${c.models.join(', ')}** agreed:`)
      lines.push(`   ${c.text}`)
      lines.push('')
    })

    // Unique
    if (summary.unique.length > 0) {
      lines.push('## Unique Findings')
      lines.push(`Found ${summary.unique.length} findings from single AI:`)
      lines.push('')
      summary.unique.forEach((u, i) => {
        lines.push(`${i + 1}. **${u.model}** only:`)
        lines.push(`   ${u.text}`)
        lines.push('')
      })
    }

    // Stats
    lines.push('## Statistics')
    lines.push(`- Total contributions: ${summary.totalContributions}`)
    lines.push(`- Consensus rate: ${(summary.consensusRate * 100).toFixed(1)}%`)

    return lines.join('\n')
  }

  /**
   * Normalize contribution for comparison
   */
  _normalizeContribution(text) {
    return text.toLowerCase().trim().replace(/\s+/g, ' ')
  }
}


/**
 * Helper: Create attribution-aware worker results
 */
export function createAttributedWorkerResults(workerResponses, tracker) {
  return workerResponses.map((response, idx) => {
    const model = response.model || `worker-${idx}`
    const findings = response.findings || []

    // Record each finding
    findings.forEach(finding => {
      tracker.recordWorker(model, finding.title || finding.description, {
        file: finding.file,
        line: finding.line,
        severity: finding.severity
      })
    })

    return {
      ...response,
      model,
      attributed: true
    }
  })
}


/**
 * Helper: Format attribution for display
 */
export function formatAttributionSummary(tracker) {
  const summary = tracker.summarize()

  const lines = [
    `👥 Workers: ${summary.workers.map(w => w.model).join(', ')}`,
    `🧠 Arbiter: ${summary.arbiter || 'none'}`,
    `✓ Consensus: ${summary.consensus.length} findings`,
    `⚠ Unique: ${summary.unique.length} findings`,
    `📊 Agreement: ${(summary.consensusRate * 100).toFixed(0)}%`
  ]

  return lines.join('\n')
}


// Example usage (for testing)
if (typeof module !== 'undefined' && require.main === module) {
  console.log('Testing Attribution Tracker\n')

  const tracker = new AttributionTracker()

  // Worker contributions
  tracker.recordWorker('opus', 'Bug in authentication.js line 42', {
    file: 'authentication.js',
    line: 42,
    severity: 'high'
  })

  tracker.recordWorker('sonnet', 'Bug in authentication.js line 42', {
    file: 'authentication.js',
    line: 42,
    severity: 'high'
  })

  tracker.recordWorker('gpt4', 'Performance issue in database.js', {
    file: 'database.js',
    severity: 'medium'
  })

  tracker.recordWorker('opus', 'Security vulnerability in login flow', {
    severity: 'critical'
  })

  // Arbiter decision
  tracker.recordArbiter('opus', 'approve', 'All critical findings addressed')

  // Summary
  console.log('='.repeat(80))
  console.log(tracker.toMarkdown())
  console.log('='.repeat(80))

  const summary = tracker.summarize()
  console.log('\nFormatted summary:')
  console.log(formatAttributionSummary(tracker))
}
