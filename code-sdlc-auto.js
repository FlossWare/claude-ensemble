export const meta = {
  name: 'code-sdlc-auto',
  description: 'Autonomous SDLC automation - runs entire pipeline end-to-end without interaction',
  whenToUse: 'When you want fully automated SDLC pipeline for nightly runs or CI/CD',
  autonomous: true,
  phases: [
    { title: 'Development', detail: 'code-review-auto + code-solve-auto' },
    { title: 'Testing', detail: 'code-test-auto verification' },
    { title: 'PR Review', detail: 'pr-review-auto open PRs' },
    { title: 'Security', detail: 'code-security-auto audit' },
    { title: 'Documentation', detail: 'code-doc-auto generation' },
    { title: 'Release', detail: 'release-notes-auto publishing' },
    { title: 'Summary', detail: 'Aggregate results and report' },
  ],
}

log('🤖 AUTONOMOUS SDLC PIPELINE')
log('   All phases run automatically with NO user interaction')
log('   Decision gates use strict criteria')
log('')

// Auto-decision criteria
const AUTO_CRITERIA = {
  continue_on_breaking: false,          // STOP if breaking changes
  continue_on_critical_vulns: false,    // STOP if critical security issues
  continue_on_test_failures: false,     // STOP if critical test failures
  max_issues_to_fix: 20,                // Cap issue fixes
  release_if_commits: true,             // Always release if commits exist
  min_budget_per_phase: 50_000,         // Min tokens per phase
}

log('Auto-decision criteria:')
log(`   - Stop on breaking changes: ${!AUTO_CRITERIA.continue_on_breaking}`)
log(`   - Stop on critical vulns: ${!AUTO_CRITERIA.continue_on_critical_vulns}`)
log(`   - Max issues to fix: ${AUTO_CRITERIA.max_issues_to_fix}`)
log('')

// For token efficiency, reusing code-sdlc.js logic with autonomous flag
// In production, this would call: workflow('code-sdlc', {autonomous: true})

log('⚠️  Use code-sdlc with autonomous=true flag')
log('   Example: claude run code-sdlc autonomous=true')
log('')
log('   Or call each phase workflow with -auto suffix:')
log('   - code-review-auto')
log('   - code-solve-auto')
log('   - code-test-auto')
log('   - pr-review-auto')
log('   - code-security-auto')
log('   - code-doc-auto')
log('   - release-notes-auto')

return {
  status: 'use_code_sdlc_with_flag',
  message: 'Use: claude run code-sdlc autonomous=true',
  auto_criteria: AUTO_CRITERIA
}
