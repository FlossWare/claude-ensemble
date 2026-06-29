/**
 * Test: Dynamic import() in Workflow Runtime
 *
 * This workflow tests whether dynamic import() works in the Claude Code
 * workflow runtime environment.
 *
 * EXPECTED OUTCOME:
 * - If dynamic import() works: Can proceed with Option 2 approach
 * - If it fails: Must fall back to Option 5 (inline telemetry)
 *
 * SUCCESS CRITERIA:
 * - import() resolves without error
 * - fleet-telemetry-minimal.js functions are accessible
 * - dispatch/complete functions can be called
 *
 * RUN THIS FIRST before implementing Phase 2 integration.
 */

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'test-fleet-dynamic-import',
  description: 'Test if dynamic import() works in Claude Code workflow runtime',
  whenToUse: 'Run once to determine Phase 2 integration approach',
  phases: [
    { title: 'Test', detail: 'Attempt dynamic import of fleet-telemetry-minimal.js' },
    { title: 'Validate', detail: 'Check if functions are accessible' },
    { title: 'Report', detail: 'Document findings' }
  ]
}

export default async function({ args, phase, log, agent, parallel }) {

phase('Test')

log('Testing dynamic import() in workflow runtime...\n')

let telemetryModule = null
let importSuccess = false
let importError = null

// Test 1: Can we import at all?
log('Test 1: Basic dynamic import()')
try {
  telemetryModule = await import('./fleet-telemetry-minimal.js')
  importSuccess = true
  log('✅ import() succeeded\n')
} catch (error) {
  importError = error.message
  log(`❌ import() failed: ${error.message}\n`)
}

// Test 2: If import succeeded, check functions
if (importSuccess) {
  log('Test 2: Function accessibility')

  const functions = [
    'dispatchAgent',
    'completeAgent',
    'telemetryWrap',
    'inferJobType',
    'default'
  ]

  for (const fn of functions) {
    if (fn in telemetryModule) {
      log(`  ✅ ${fn} is accessible`)
    } else {
      log(`  ❌ ${fn} is NOT accessible`)
      importSuccess = false
    }
  }
  log('')
}

// Test 3: If import succeeded, try using functions
if (importSuccess) {
  log('Test 3: Function execution (no side effects)')

  try {
    // These should work but not actually call the dispatcher
    const jobType = telemetryModule.inferJobType({ label: 'test', model: 'sonnet' })
    log(`  ✅ inferJobType returned: "${jobType}"`)

    // Test with dispatcher disabled (should be instant and safe)
    const originalEnv = process.env.FLEET_DISPATCHER
    process.env.FLEET_DISPATCHER = 'false'

    const jobId = await telemetryModule.dispatchAgent('sonnet')
    log(`  ✅ dispatchAgent returned: ${jobId === null ? 'null (expected)' : jobId}`)

    process.env.FLEET_DISPATCHER = originalEnv

    log('')
  } catch (error) {
    log(`  ❌ Function execution failed: ${error.message}\n`)
    importSuccess = false
  }
}

phase('Validate')

log('Validation Results:')
log('-------------------\n')

if (importSuccess) {
  log('✅ DYNAMIC IMPORT WORKS')
  log('\nThis means:')
  log('  • Option 2 approach is VIABLE')
  log('  • Can apply: import telemetry at top of workflow body')
  log('  • Minimal code per workflow (1-2 lines)')
  log('  • Implementation time: ~1 hour for all 34 workflows')
} else {
  log('❌ DYNAMIC IMPORT FAILED')
  log('\nReason:', importError || 'Function validation failed')
  log('\nThis means:')
  log('  • Must use Option 5 (inline telemetry)')
  log('  • Will need to copy ~15 lines per workflow')
  log('  • Implementation time: ~2-3 hours for all 34 workflows')
}

phase('Report')

// Return detailed test results
const result = {
  timestamp: new Date().toISOString(),
  environment: 'Claude Code Workflow Runtime',
  test_results: {
    dynamic_import_supported: importSuccess,
    import_error: importError,
    functions_available: importSuccess ? [
      'dispatchAgent',
      'completeAgent',
      'telemetryWrap',
      'inferJobType'
    ] : [],
    module_structure: importSuccess ? Object.keys(telemetryModule).sort() : []
  },
  recommendation: importSuccess
    ? 'Option 2: Use dynamic import() - 1 hour implementation'
    : 'Option 5: Use inline telemetry - 2-3 hours implementation',
  next_steps: importSuccess
    ? [
      'Apply dynamic import() to all 34 workflows',
      'Wrap agent() calls with telemetry dispatch/complete',
      'Test in 5 sample workflows first',
      'Validate fleet dispatcher integration'
    ]
    : [
      'Create fleet-telemetry-inline.js snippet',
      'Create migration script for all workflows',
      'Apply to 5 sample workflows first',
      'Test fleet dispatcher integration',
      'Roll out to remaining 29 workflows'
    ]
}

log('\n📊 Full Results:')
log(JSON.stringify(result, null, 2))

return result

}
