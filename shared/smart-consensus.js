/**
 * Smart Consensus - Performance-Aware Multi-AI Orchestration
 *
 * Combines:
 * - Attribution tracking (who said what)
 * - Performance tracking (who is good at what)
 * - Smart model selection (use best models for task)
 * - Learning from results (improve over time)
 * - PostgreSQL model loading (all 135+ models from database)
 *
 * Copy this inline into workflows (no imports).
 */

import { AttributionTracker } from './attribution.js'
import { ModelPerformanceTracker, SmartModelSelector } from './model-performance.js'
import { captureConsensusFeedback } from './workflow-feedback-capture.js'
import { selectWorkerModels, selectArbiterModel } from './model-loader.js'

/**
 * Format model name for agent() calls
 * Handles complex Claude model names like "claude-3-5-sonnet-20241022"
 */
function formatModelForAgent(modelName) {
  if (!modelName.includes('claude')) return modelName;
  if (modelName.includes('opus')) return 'opus';
  if (modelName.includes('sonnet')) return 'sonnet';
  if (modelName.includes('haiku')) return 'haiku';
  return modelName; // Fallback to original
}

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

  // Select best models based on performance + PostgreSQL availability
  // Load workers from PostgreSQL (diverse tier mix)
  const workersFromDB = await selectWorkerModels(workerCount, excludeModels)

  // Use performance tracker to refine selection if available
  const workers = workersFromDB.length > 0
    ? workersFromDB
    : await selector.selectWorkers(taskType, workerCount, { exclude: excludeModels })

  // Arbiter: Always highest tier available
  const arbiterFromDB = await selectArbiterModel([...excludeModels, ...workers])
  const arbiterSelection = arbiterFromDB
    ? { model: arbiterFromDB, source: 'postgresql', confidence: 1.0 }
    : await selector.selectModel(taskType, { exclude: workers })

  log(`Workers: ${workers.join(', ')}`)
  log(`Arbiter: ${arbiterSelection.model} (${arbiterSelection.source}, confidence: ${arbiterSelection.confidence.toFixed(2)})`)
  log('')

  // Workers analyze in parallel
  const workerResults = await parallel(
    workers.map((model, idx) => () =>
      agent(prompt, {
        label: `worker:${model}`,
        model: formatModelForAgent(model),
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
    model: formatModelForAgent(arbiterSelection.model),
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

  // Capture consensus feedback (Issue #249)
  if (options.workflow_execution_id) {
    try {
      await captureConsensusFeedback({
        workflow_execution_id: options.workflow_execution_id,
        performance: metrics,
        attribution: attribution.summarize()
      });
    } catch (feedbackError) {
      console.warn(`⚠️  Feedback capture failed (non-fatal): ${feedbackError.message}`);
    }
  }

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
 * Helper: Load performance data from PostgreSQL
 */
export async function loadPerformanceFromMemory(memoryPath) {
  try {
    const tracker = new ModelPerformanceTracker()

    // Load from PostgreSQL learning.model_capabilities
    const { execSync } = await import('child_process')
    const query = `
      SELECT model_id, code_generation, code_review, research,
             math_reasoning, general_qa, creative_writing,
             security_analysis, test_count, avg_latency_ms
      FROM learning.model_capabilities
      WHERE test_count > 0
      ORDER BY last_tested DESC
    `

    const result = execSync(
      `psql -h aio-01 -p 5433 -U sfloess -d learning -t -A -F'|' -c "${query}"`,
      { encoding: 'utf-8' }
    )

    // Parse results and load into tracker
    const lines = result.trim().split('\n').filter(Boolean)
    lines.forEach(line => {
      const [model, codeGen, codeReview, research, math, qa, creative, security, testCount, latency] = line.split('|')

      // Record historical performance for each task type
      if (codeGen && parseFloat(codeGen) > 0) {
        tracker.recordTask(model, 'code_generation', { accuracy: parseFloat(codeGen), latency: parseInt(latency) || 1000 })
      }
      if (codeReview && parseFloat(codeReview) > 0) {
        tracker.recordTask(model, 'code_review', { accuracy: parseFloat(codeReview), latency: parseInt(latency) || 1000 })
      }
      if (research && parseFloat(research) > 0) {
        tracker.recordTask(model, 'research', { accuracy: parseFloat(research), latency: parseInt(latency) || 1000 })
      }
      if (math && parseFloat(math) > 0) {
        tracker.recordTask(model, 'math_reasoning', { accuracy: parseFloat(math), latency: parseInt(latency) || 1000 })
      }
      if (qa && parseFloat(qa) > 0) {
        tracker.recordTask(model, 'general_qa', { accuracy: parseFloat(qa), latency: parseInt(latency) || 1000 })
      }
      if (creative && parseFloat(creative) > 0) {
        tracker.recordTask(model, 'creative_writing', { accuracy: parseFloat(creative), latency: parseInt(latency) || 1000 })
      }
      if (security && parseFloat(security) > 0) {
        tracker.recordTask(model, 'security', { accuracy: parseFloat(security), latency: parseInt(latency) || 1000 })
      }
    })

    if (typeof log !== 'undefined') {
      log(`✓ Loaded performance data for ${lines.length} models from PostgreSQL`)
    } else {
      console.log(`✓ Loaded performance data for ${lines.length} models from PostgreSQL`)
    }
    return tracker
  } catch (e) {
    console.warn('Could not load performance data from PostgreSQL, using new tracker:', e.message)
    return new ModelPerformanceTracker()
  }
}


/**
 * Helper: Save performance data to PostgreSQL
 */
export async function savePerformanceToMemory(tracker, memoryPath) {
  try {
    const data = tracker.toJSON()
    const { execSync } = await import('child_process')

    // Save to PostgreSQL learning.model_capabilities
    // For each model in tracker, update or insert capabilities
    Object.entries(data.models || {}).forEach(([model, tasks]) => {
      const taskMetrics = {}

      Object.entries(tasks).forEach(([taskType, metrics]) => {
        const accuracy = metrics.accuracy || metrics.successRate || 0
        const normalizedType = taskType.replace('_arbiter', '')

        switch (normalizedType) {
          case 'code_generation':
          case 'code':
            taskMetrics.code_generation = accuracy
            break
          case 'code_review':
          case 'review':
            taskMetrics.code_review = accuracy
            break
          case 'research':
            taskMetrics.research = accuracy
            break
          case 'math_reasoning':
          case 'math':
            taskMetrics.math_reasoning = accuracy
            break
          case 'general_qa':
          case 'qa':
            taskMetrics.general_qa = accuracy
            break
          case 'creative_writing':
          case 'creative':
            taskMetrics.creative_writing = accuracy
            break
          case 'security':
          case 'security_analysis':
            taskMetrics.security_analysis = accuracy
            break
        }
      })

      if (Object.keys(taskMetrics).length > 0) {
        const setClauses = Object.entries(taskMetrics)
          .map(([key, val]) => `${key} = ${val}`)
          .join(', ')

        const query = `
          INSERT INTO learning.model_capabilities
          (model_id, ${Object.keys(taskMetrics).join(', ')}, last_tested, test_count)
          VALUES ('${model}', ${Object.values(taskMetrics).join(', ')}, NOW(), 1)
          ON CONFLICT (model_id) DO UPDATE SET
            ${setClauses},
            test_count = learning.model_capabilities.test_count + 1,
            last_tested = NOW()
        `

        try {
          execSync(
            `psql -h aio-01 -p 5433 -U sfloess -d learning -c "${query.replace(/\n/g, ' ')}"`,
            { encoding: 'utf-8', stdio: 'ignore' }
          )
        } catch (err) {
          console.warn(`Could not save performance for ${model}:`, err.message)
        }
      }
    })

    if (typeof log !== 'undefined') {
      log(`✓ Performance data saved to PostgreSQL for ${Object.keys(data.models || {}).length} models`)
    } else {
      console.log(`✓ Performance data saved to PostgreSQL for ${Object.keys(data.models || {}).length} models`)
    }
    return true
  } catch (e) {
    console.error('Could not save performance data to PostgreSQL:', e.message)
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
