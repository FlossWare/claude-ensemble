/**
 * Example: Fleet-Aware Workflow with Inline Telemetry
 *
 * This demonstrates the recommended approach for Phase 2 integration:
 * - Minimal fleet telemetry (dispatch + complete)
 * - Inline code (no imports, works in sandboxed runtime)
 * - Optional fleet dispatcher (silent fallback without it)
 * - Works with all 34 existing workflows
 *
 * To use this pattern in your workflows:
 * 1. Copy the telemetry dispatch code (after meta block)
 * 2. Wrap agent calls with startTime tracking
 * 3. Call complete on success or error
 *
 * This is the RECOMMENDED approach for Phase 2.
 */

export const meta = {
  name: 'example-fleet-inline',
  description: 'Demonstrates fleet telemetry integration using inline approach',
  whenToUse: 'See how to add fleet telemetry to any workflow without imports or dependencies',
  phases: [
    { title: 'Setup', detail: 'Initialize fleet telemetry' },
    { title: 'Analyze', detail: 'Run agent call with telemetry' },
    { title: 'Report', detail: 'Complete job and show results' }
  ]
}

phase('Setup')

// ============================================================================
// FLEET TELEMETRY - INLINE
// This is the 15-line pattern you add to each workflow.
// Copy this to any workflow that calls agent() to add fleet telemetry.
// ============================================================================

const FLEET_DISPATCHER = process.env.FLEET_DISPATCHER_URL || 'http://pi-02:3004'

// Dispatch this workflow job to fleet
const _fleetJobId = (() => {
  if (process.env.FLEET_DISPATCHER === 'false') return null
  return (async () => {
    try {
      const res = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'sonnet',
          prompt: '[example-fleet-inline]',
          job_type: 'agent',
          estimated_ram_gb: 1.0,
          estimated_duration_seconds: 60
        })
      })
      if (!res.ok) return null
      const data = await res.json()
      return data?.job_id || null
    } catch {
      return null
    }
  })()
})()

// Helper: Complete fleet job (used below)
const completeFleetJob = async (success, errorMsg = null) => {
  if (!_fleetJobId) return
  try {
    await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: _fleetJobId,
        instance: 'workflow',
        success,
        duration_seconds: (Date.now() - _startTime) / 1000,
        job_type: 'agent',
        model: 'sonnet',
        error: errorMsg
      })
    }).catch(() => {})
  } catch {}
}

const _startTime = Date.now()

// ============================================================================
// END TELEMETRY BLOCK - use pattern above in your workflows
// ============================================================================

log(`✅ Fleet telemetry initialized (job ID: ${_fleetJobId || 'disabled'})`)

phase('Analyze')

try {
  // Example agent call
  const response = await agent(
    'Analyze this JavaScript function and suggest improvements: function calculate(x, y) { if (x > 0) { return x * y; } else { return 0; } }',
    {
      label: 'code-analysis',
      schema: {
        type: 'object',
        properties: {
          summary: { type: 'string' },
          improvements: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                issue: { type: 'string' },
                suggestion: { type: 'string' },
                priority: { type: 'string', enum: ['high', 'medium', 'low'] }
              },
              required: ['issue', 'suggestion']
            }
          },
          refactored_code: { type: 'string' }
        },
        required: ['summary', 'improvements']
      }
    }
  )

  phase('Report')

  log(`\n📊 Analysis Results:`)
  log(`Summary: ${response.summary}`)
  log(`\nImprovements (${response.improvements.length}):`)

  for (const imp of response.improvements) {
    log(`  • [${imp.priority || 'medium'}] ${imp.issue}`)
    log(`    → ${imp.suggestion}`)
  }

  if (response.refactored_code) {
    log(`\nRefactored Code:`)
    log('```javascript')
    log(response.refactored_code)
    log('```')
  }

  // Complete fleet job with success
  await completeFleetJob(true)

  log(`\n✅ Example workflow complete`)
  return response

} catch (error) {
  log(`\n❌ Analysis failed: ${error.message}`)

  // Complete fleet job with error
  await completeFleetJob(false, error.message)

  throw error
}
