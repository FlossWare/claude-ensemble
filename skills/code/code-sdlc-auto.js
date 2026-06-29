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

export default async function({ args, phase, log, agent, parallel }) {

// Auto-decision criteria
const AUTO_CRITERIA = {
  continue_on_breaking: false,          // STOP if breaking changes
  continue_on_critical_vulns: false,    // STOP if critical security issues
  continue_on_test_failures: false,     // STOP if critical test failures
  max_issues_to_fix: 20,                // Cap issue fixes
  release_if_commits: true,             // Always release if commits exist
  min_budget_per_phase: 50_000,         // Min tokens per phase
}

log('')
log('═'.repeat(60))
log('🚀 AUTONOMOUS SDLC PIPELINE')
log('═'.repeat(60))
log('This workflow runs the entire SDLC end-to-end')
log('')
log('Phases:')
log('  1. Development → code-review + code-solve')
log('  2. Testing → code-test verification')
log('  3. PR Review → pr-review open PRs')
log('  4. Security → code-security audit')
log('  5. Documentation → code-doc generation')
log('  6. Release → release-notes publishing')
log('')
log('Auto-decision criteria:')
log(`  • Stop on breaking changes: ${AUTO_CRITERIA.continue_on_breaking ? 'NO' : 'YES'}`)
log(`  • Stop on critical vulns: ${AUTO_CRITERIA.continue_on_critical_vulns ? 'NO' : 'YES'}`)
log(`  • Stop on test failures: ${AUTO_CRITERIA.continue_on_test_failures ? 'NO' : 'YES'}`)
log(`  • Max issues to fix: ${AUTO_CRITERIA.max_issues_to_fix}`)
log(`  • Auto-release: ${AUTO_CRITERIA.release_if_commits ? 'YES' : 'NO'}`)
log('═'.repeat(60))
log('')

log('🔄 Delegating to code-sdlc workflow with autonomous=true...')
log('')

// Call the base workflow with autonomous flag and criteria
const result = await workflow('code-sdlc', { autonomous: true, AUTO_CRITERIA })

log('')
log('═'.repeat(60))
log('✅ AUTONOMOUS SDLC PIPELINE COMPLETE')
log('═'.repeat(60))
if (result.phases_run) {
  log(`Phases completed: ${result.phases_run.length}`)
}
if (result.phases_skipped) {
  log(`Phases skipped: ${result.phases_skipped.length}`)
}
if (result.breaking_changes !== undefined) {
  log(`Breaking changes: ${result.breaking_changes ? 'YES' : 'NO'}`)
}
if (result.critical_issues) {
  log(`Critical issues: ${result.critical_issues.length}`)
}
log('═'.repeat(60))
log('')

// Learning extraction handled by code-sdlc.js itself

return result

}
