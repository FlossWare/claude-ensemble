export const meta = {
  name: 'ai-consensus',
  description: 'Multi-AI consensus helper - run any task with opus/sonnet/haiku workers + arbiter',
  whenToUse: 'Internal helper for multi-AI consensus pattern',
  phases: [
    { title: 'Get Arbiter', detail: 'Determine next arbiter via rotation' },
    { title: 'Workers', detail: 'Parallel opus/sonnet/haiku execution' },
    { title: 'Arbiter', detail: 'Synthesize best answer' },
    { title: 'Update State', detail: 'Record arbiter usage for rotation' },
    { title: 'Remote Execution (Phase 3)', detail: 'Optional SSH remote sync to fleet servers' },
  ],
  fixes: {
    '1_recursion': 'Agent calls use agent(prompt,opts) not _agent - verified correct',
    '2_endpoints': 'Fleet endpoints use /agent/execute and /agent/complete - verified correct',
    '3_timeout': 'Added AbortController with 30s timeout to learning API fetch calls',
    '4_phase3_ssh': 'Added remote execution via SSH when REMOTE_EXECUTION_ENABLED=true',
  }
}

// USAGE:
// const result = await workflow('ai-consensus', {
//   task: 'Analyze this code for bugs',
//   context: '<code here>',
//   schema: { type: 'object', properties: { ... } },
//   arbiter_instructions: 'Select the most thorough analysis'
// })

// ============================================================================
// LOCAL MODELS CONFIG LOADING
// ============================================================================

function loadLocalModelsConfig() {
  try {
    const fs = require('fs')
    const configPath = '/home/sfloess/.claude/repos/claude-global-skills/local-models-config.json'
    const configContent = fs.readFileSync(configPath, 'utf-8')
    const config = JSON.parse(configContent)
    return config
  } catch (error) {
    return {
      enabled: false,
      models: {},
      fallbackToClaude: true
    }
  }
}

// ============================================================================
// GET WORKER MODELS
// ============================================================================

function getWorkerModels() {
  const localConfig = loadLocalModelsConfig()
  const workers = []

  // Base models - always use (maximum coverage: 6 models)
  workers.push('fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini')

  // Add local Ollama models if enabled
  if (localConfig.enabled && localConfig.models) {
    const ollamaModels = Object.values(localConfig.models).filter(m => typeof m === 'string')
    if (ollamaModels.length > 0) {
      workers.push(...ollamaModels)
      log(`Added ${ollamaModels.length} local Ollama models: ${ollamaModels.join(', ')}`)
    }
  }

  return workers
}

// ============================================================================
// OPENCLAW INTEGRATION (graceful degradation when unavailable)
// ============================================================================

function isOpenClawEnabled() {
  return process.env.OPENCLAW_ENABLED === 'true' || process.env.OPENCLAW_ENABLED === '1'
}

async function getOpenClawWorkerVote(prompt, schema) {
  if (!isOpenClawEnabled()) return null
  try {
    const http = require('http')
    const host = process.env.OPENCLAW_HOST || 'localhost'
    const port = parseInt(process.env.OPENCLAW_PORT || '18789', 10)

    // Health check first (fast fail)
    const healthy = await new Promise((resolve) => {
      const req = http.request({ hostname: host, port, path: '/api/status', method: 'GET', timeout: 3000 },
        (res) => resolve(res.statusCode === 200))
      req.on('error', () => resolve(false))
      req.on('timeout', () => { req.destroy(); resolve(false) })
      req.end()
    })

    if (!healthy) return null

    const payload = JSON.stringify({
      message: prompt,
      ...(schema && { response_format: schema }),
      instruction: `You are a verification worker in a multi-AI consensus system.
Your unique role: EXECUTE CODE to verify claims, don't just reason.
1. If the claim can be tested with code/commands, RUN IT
2. Report both reasoning AND execution results
3. Flag when execution contradicts reasoning
Return structured response with:
- reasoning: Your analysis
- execution_performed: boolean
- execution_results: { command, stdout, stderr, exit_code }
- verification_status: "passed" | "failed" | "not_testable"
- confidence: 0-100 (boost when you have execution proof)`
    })

    const response = await new Promise((resolve, reject) => {
      const req = http.request({
        hostname: host, port,
        path: '/api/sessions/main/messages',
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) },
        timeout: 240000,
      }, (res) => {
        let data = ''
        res.on('data', chunk => data += chunk)
        res.on('end', () => { try { resolve(JSON.parse(data)) } catch(e) { resolve({ text: data }) } })
      })
      req.on('error', reject)
      req.on('timeout', () => { req.destroy(); reject(new Error('OpenClaw timeout')) })
      req.write(payload)
      req.end()
    })

    return { model: 'openclaw', ...response, label: 'Verification (OpenClaw)' }
  } catch (error) {
    return null
  }
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

// Generate execution ID (unique per run) - MUST be defined early
// Use args.execution_id if provided, otherwise generate unique ID
// Note: Can't use Date.now() or Math.random() in workflow scripts (breaks resume)
// Caller must pass execution_id to ensure uniqueness across concurrent workflows
const executionId = args.execution_id || `consensus_${args.task ? args.task.substring(0, 20).replace(/[^a-z0-9]/gi, '_') : 'unknown'}_CALLER_MUST_PROVIDE_ID`

const task = args.task || args
const context = args.context || ''
const schema = args.schema || {
  type: 'object',
  properties: {
    model: { type: 'string' },
    answer: { type: 'string' }
  }
}
const arbiterInstructions = args.arbiter_instructions || 'Select the best answer with highest quality and accuracy'

if (!task) {
  log('No task provided')
  log('Usage: workflow("ai-consensus", { task: "...", context: "...", schema: {...} })')
  return { error: 'No task provided' }
}

log('='.repeat(60))
log('MULTI-AI CONSENSUS')
log('='.repeat(60))
log(`Task: ${task}`)
log('')

// PHASE 0: Get next arbiter from rotation
phase('Get Arbiter')

const arbiterChoice = await workflow('get-next-arbiter')
log(`Arbiter for this run: ${arbiterChoice.arbiter} (previous: ${arbiterChoice.previous || 'none'})`)

// PHASE 1: Workers execute in parallel
phase('Workers')

// Get worker models (includes local Ollama models if enabled)
const workerModels = getWorkerModels()
log(`Workers executing (${workerModels.join(', ')})...`)

const workerPrompt = (model) => `[${model.toUpperCase()}] ${task}

${context ? `Context:\n${context}\n\n` : ''}

Return structured data per schema.`

// Build worker tasks dynamically based on available models
const workerTasks = workerModels.map(model =>
  () => agent(workerPrompt(model), {
    label: `${model}-worker`,
    model: model,
    schema
  })
)

// Add OpenClaw as optional 7th worker (execution verification)
if (isOpenClawEnabled()) {
  workerTasks.push(() => getOpenClawWorkerVote(workerPrompt('openclaw'), schema))
  log('OpenClaw worker enabled - adding execution verification')
}

const workers = await parallel(workerTasks)

const validWorkers = workers.filter(Boolean)
log(`${validWorkers.length}/${workerTasks.length} workers completed`)

// Extract OpenClaw result for arbiter enhancement
const openclawResult = validWorkers.find(w => w?.model === 'openclaw' || w?.label === 'Verification (OpenClaw)')

if (validWorkers.length === 0) {
  log('All workers failed')
  return { error: 'All workers failed', workers: [] }
}

// PHASE 2: Arbiter synthesis
phase('Arbiter')

log('')
log(`Arbiter (${arbiterChoice.arbiter}) synthesizing best answer...`)

const arbiterSchema = {
  type: 'object',
  properties: {
    winning_worker: { type: 'string' },
    why_selected: { type: 'string' },
    confidence: { type: 'number' },
    synthesis: schema
  }
}

// Build OpenClaw evidence section for arbiter
let openclawEvidenceSection = ''
if (openclawResult && openclawResult.execution_performed) {
  openclawEvidenceSection = `

**OPENCLAW VERIFICATION** (unique: actual code execution):
- Verification Status: ${openclawResult.verification_status || 'unknown'}
- Execution Performed: YES
- Confidence: ${openclawResult.confidence || 0}%
- Reasoning: ${openclawResult.reasoning || 'N/A'}
${openclawResult.execution_results ? `- Execution Results:
  - Command: ${openclawResult.execution_results.command || 'N/A'}
  - Exit Code: ${openclawResult.execution_results.exit_code ?? 'N/A'}
  - Output: ${openclawResult.execution_results.stdout || openclawResult.execution_results.stderr || 'N/A'}` : ''}

NOTE: OpenClaw provides execution-backed evidence. When execution was performed,
weight this evidence heavily as it represents ground truth, not just reasoning.
`
}

const synthesis = await agent(`[ARBITER] Review ${validWorkers.length} worker responses and synthesize the best answer.

Task: ${task}

Worker Responses:
${validWorkers.map((w, i) => `
Worker ${i + 1} (${w.model || 'unknown'}):
${JSON.stringify(w, null, 2)}
`).join('\n')}
${openclawEvidenceSection}
Instructions:
${arbiterInstructions}

Return:
1. winning_worker: Which model produced the best answer
2. why_selected: Why this answer is best
3. confidence: 0-100 rating
4. synthesis: The best answer (or synthesized combination)

`, {
  label: 'arbiter',
  model: arbiterChoice.arbiter,
  schema: arbiterSchema
})

log(`Winner: ${synthesis.winning_worker}`)
log(`   Confidence: ${synthesis.confidence}%`)
log(`   Reason: ${synthesis.why_selected}`)

log('')

// PHASE 3: Update arbiter state for rotation tracking + remote execution
phase('Update State')

await workflow('update-arbiter-state', { arbiter: arbiterChoice.arbiter, workflow_name: 'ai-consensus' })

// Issue #4: Phase 3 - Add remote execution via SSH when dispatch.server not localhost
if (process.env.REMOTE_EXECUTION_ENABLED === 'true') {
  try {
    const remoteServers = (process.env.REMOTE_SERVERS || '').split(',').filter(Boolean)

    if (remoteServers.length > 0) {
      log(`\nPhase 3b: Remote Execution on ${remoteServers.length} server(s)...`)

      // Replicate execution on remote servers via SSH
      for (const server of remoteServers) {
        try {
          const serverTrimmed = server.trim()

          // Validate hostname format (prevent injection)
          if (!/^[a-zA-Z0-9._:-]+$/.test(serverTrimmed)) {
            log(`Skipping invalid hostname: ${serverTrimmed}`)
            continue
          }

          const isLocalhost = serverTrimmed === 'localhost' || serverTrimmed === '127.0.0.1'

          if (!isLocalhost) {
            // Remote SSH execution when server is not localhost
            try {
              const { execFileSync } = require('child_process')

              const remotePayload = {
                arbiter: arbiterChoice.arbiter,
                winning_worker: synthesis.winning_worker,
                confidence: synthesis.confidence,
                server: serverTrimmed,
                execution_id: executionId
              }

              // Use execFileSync with array args (no shell interpolation)
              const payloadJson = JSON.stringify(remotePayload)

              try {
                const output = execFileSync('ssh', [
                  serverTrimmed,
                  `curl -X POST http://localhost:3004/agent/execute -H 'Content-Type: application/json' -d '${payloadJson}'`
                ], { encoding: 'utf-8', timeout: 30000 })
                log(`Remote execution via SSH completed on ${serverTrimmed}`)
              } catch (sshErr) {
                log(`Remote SSH execution failed on ${serverTrimmed}: ${sshErr.message || sshErr}`)
              }
            } catch (err) {
              log(`Remote SSH setup failed on ${serverTrimmed}: ${err.message || err}`)
            }
          } else {
            // Local HTTP execution for localhost
            const controller = new AbortController()
            const timeoutId = setTimeout(() => controller.abort(), 30000)

            try {
              const remotePayload = {
                arbiter: arbiterChoice.arbiter,
                winning_worker: synthesis.winning_worker,
                confidence: synthesis.confidence,
                server: serverTrimmed,
                execution_id: executionId
              }

              const response = await fetch(`http://localhost:3004/agent/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  type: 'remote-consensus-sync',
                  payload: remotePayload
                }),
                signal: controller.signal
              })

              clearTimeout(timeoutId)

              if (response.ok) {
                log(`Remote sync completed on ${serverTrimmed}`)
              } else {
                log(`Remote sync failed on ${serverTrimmed}: ${response.statusText}`)
              }
            } finally {
              clearTimeout(timeoutId)
            }
          }
        } catch (err) {
          log(`Remote execution error on ${server}: ${err.message || err}`)
        }
      }
    }
  } catch (err) {
    log(`Remote execution setup failed: ${err.message || err}`)
  }
}

// ============================================================================
// RECORD FEEDBACK TO LEARNING SYSTEM
// ============================================================================

// Record feedback for all workers
try {
  log('\nRecording feedback to learning system...')

  // Loop over all valid workers, marking winner vs non-winners
  for (const worker of validWorkers) {
    const isWinner = worker.model === synthesis.winning_worker

    const feedbackPayload = {
      worker_id: `${worker.model}-worker`,
      model: worker.model,
      consensus_score: synthesis.confidence,
      tokens_used: 0,
      cost_usd: 0.0,
      accepted: isWinner,
      execution_id: executionId,
      reasoning: isWinner ? synthesis.why_selected : `Non-winning response in consensus`,
      outcome: 'success',
      workflow_type: 'ai-consensus'
    }

    try {
      const token = process.env.LEARNING_API_TOKEN
      const authHeader = token ? { 'Authorization': `Bearer ${token}` } : {}

      // Issue #3: Add AbortController with 30s timeout
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 30000)

      try {
        const response = await fetch('http://localhost:8000/api/learning/record-feedback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...authHeader
          },
          body: JSON.stringify(feedbackPayload),
          signal: controller.signal
        })

        clearTimeout(timeoutId)

        if (response.ok) {
          const result = await response.json()
          log(`Feedback recorded for ${worker.model}: ${isWinner ? 'winner' : 'non-winner'}`)
        } else {
          log(`Failed to record feedback for ${worker.model}: ${response.statusText}`)
        }
      } finally {
        clearTimeout(timeoutId)
      }
    } catch (err) {
      log(`Feedback recording failed for ${worker.model}: ${err.message || err}`)
    }
  }
} catch (err) {
  log(`Learning system unavailable: ${err.message || err}`)
}

return {
  status: 'success',
  winner: synthesis.winning_worker,
  confidence: synthesis.confidence,
  result: synthesis.synthesis,
  all_workers: validWorkers,
  execution_id: executionId
}
