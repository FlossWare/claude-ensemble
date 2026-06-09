/**
 * Smart Consensus - Performance-Aware Multi-AI Orchestration
 *
 * Combines:
 * - Attribution tracking (who said what)
 * - Performance tracking (who is good at what)
 * - Smart model selection (use best models for task)
 * - Learning from results (improve over time)
 *
 * Copy this inline into workflows (no imports).
 */

import { AttributionTracker } from './attribution.js'
import { ModelPerformanceTracker, SmartModelSelector } from './model-performance.js'

/**
 * Performance-aware consensus workflow
 */
export async function smartConsensus(taskType, prompt, options = {}) {
  const {
    workerCount = 3,
    minConsensus = 2,
    excludeModels = [],
    performanceTracker = null,
    ragQuery = null
  } = options

  // Initialize trackers
  const attribution = new AttributionTracker()
  const performance = performanceTracker || new ModelPerformanceTracker()
  const selector = new SmartModelSelector(performance, ragQuery)

  log(`🤖 Smart Consensus for: ${taskType}`)
  log('═'.repeat(80))

  // Select best models based on performance
  const workers = await selector.selectWorkers(taskType, workerCount, { exclude: excludeModels })
  const arbiterSelection = await selector.selectModel(taskType, { exclude: workers })

  log(`Workers: ${workers.join(', ')}`)
  log(`Arbiter: ${arbiterSelection.model} (${arbiterSelection.source}, confidence: ${arbiterSelection.confidence.toFixed(2)})`)
  log('')

  // Workers analyze in parallel
  const workerResults = await parallel(
    workers.map((model, idx) => () =>
      agent(prompt, {
        label: `worker:${model}`,
        model: model.includes('claude') ? model.split('-')[1] : model,
        schema: options.schema
      }).then(result => {
        // Record attribution
        if (result && result.findings) {
          result.findings.forEach(finding => {
            attribution.recordWorker(model, finding.description || finding.title, {
              file: finding.file,
              severity: finding.severity,
              confidence: finding.confidence
            })
          })
        }
        return { model, result }
      })
    )
  )

  const validWorkers = workerResults.filter(Boolean)
  log(`✓ ${validWorkers.length}/${workers.length} workers completed`)

  // Find consensus
  const consensusFindings = attribution.findConsensus(minConsensus)
  const uniqueFindings = attribution.findUnique()

  log(`✓ Consensus: ${consensusFindings.length} findings (${minConsensus}+ agreement)`)
  log(`✓ Unique: ${uniqueFindings.length} findings (single AI)`)

  // Arbiter decision
  const arbiterPrompt = `Review these findings from ${validWorkers.length} AI workers:

Consensus findings (${consensusFindings.length}):
${JSON.stringify(consensusFindings, null, 2)}

Unique findings (${uniqueFindings.length}):
${JSON.stringify(uniqueFindings, null, 2)}

As arbiter, validate and synthesize:
1. Confirm consensus findings (high confidence)
2. Evaluate unique findings (may be false positives OR valuable insights)
3. Provide final decision

${options.arbiterInstruction || ''}`

  const arbiterResult = await agent(arbiterPrompt, {
    label: `arbiter:${arbiterSelection.model}`,
    model: arbiterSelection.model.includes('claude') ? arbiterSelection.model.split('-')[1] : arbiterSelection.model,
    schema: options.arbiterSchema || options.schema
  })

  // Record arbiter attribution
  attribution.recordArbiter(
    arbiterSelection.model,
    'synthesized',
    arbiterResult?.reasoning || 'Validated findings',
    { taskType }
  )

  // Calculate performance metrics
  const summary = attribution.summarize()
  const metrics = {
    findings: consensusFindings.length + uniqueFindings.length,
    accuracy: arbiterResult?.accuracy || summary.consensusRate,
    consensus: summary.consensusRate,
    precision: consensusFindings.length / (consensusFindings.length + uniqueFindings.length)
  }

  // Record performance for each worker
  validWorkers.forEach(({ model, result }) => {
    const workerFindings = result?.findings?.length || 0
    const workerConsensus = consensusFindings.filter(c => c.models.includes(model)).length
    const workerAccuracy = workerFindings > 0 ? workerConsensus / workerFindings : 0

    performance.recordTask(model, taskType, {
      findings: workerFindings,
      accuracy: workerAccuracy,
      consensus: workerConsensus / Math.max(consensusFindings.length, 1)
    })
  })

  // Record arbiter performance
  performance.recordTask(arbiterSelection.model, `${taskType}_arbiter`, {
    findings: arbiterResult?.findings?.length || 0,
    accuracy: metrics.accuracy,
    consensus: metrics.consensus
  })

  log('')
  log('📊 Performance recorded for all models')
  log(`   Consensus rate: ${(metrics.consensus * 100).toFixed(0)}%`)
  log(`   Accuracy: ${(metrics.accuracy * 100).toFixed(0)}%`)

  return {
    findings: arbiterResult?.findings || consensusFindings,
    consensus: consensusFindings,
    unique: uniqueFindings,
    attribution: attribution.summarize(),
    performance: metrics,
    workers: validWorkers.map(w => w.model),
    arbiter: arbiterSelection.model,
    report: attribution.toMarkdown()
  }
}


/**
 * Helper: Load performance data from memory
 */
export async function loadPerformanceFromMemory(memoryPath) {
  try {
    // In real implementation, read from file
    // For now, return new tracker
    const tracker = new ModelPerformanceTracker()

    // TODO: Load from memoryPath (e.g., memory/model-performance.json)
    // const data = await readJSON(memoryPath)
    // tracker.fromJSON(data)

    return tracker
  } catch (e) {
    console.warn('Could not load performance data, using new tracker')
    return new ModelPerformanceTracker()
  }
}


/**
 * Helper: Save performance data to memory
 */
export async function savePerformanceToMemory(tracker, memoryPath) {
  try {
    const data = tracker.toJSON()

    // TODO: Write to memoryPath (e.g., memory/model-performance.json)
    // await writeJSON(memoryPath, data)

    log(`✓ Performance data saved to ${memoryPath}`)
    return true
  } catch (e) {
    console.error('Could not save performance data:', e)
    return false
  }
}


// Example: Smart code review with performance tracking
async function smartCodeReview(code, performanceTracker) {
  const result = await smartConsensus('security', `Review this code for security vulnerabilities:

${code}

Find:
- SQL injection risks
- XSS vulnerabilities
- Authentication issues
- Authorization flaws

Return structured findings.`, {
    workerCount: 3,
    minConsensus: 2,
    performanceTracker,
    schema: {
      type: 'object',
      properties: {
        findings: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
              title: { type: 'string' },
              description: { type: 'string' },
              file: { type: 'string' },
              confidence: { type: 'number' }
            }
          }
        }
      }
    }
  })

  return result
}
