export const meta = {
  name: 'code-security-auto',
  description: 'Autonomous security audit - auto-creates issues for verified vulnerabilities',
  whenToUse: 'When you want fully automated security scanning without manual intervention',
  autonomous: true,
  phases: [
    { title: 'Detect Platform', detail: 'Identify GitHub/GitLab' },
    { title: 'Dependency Scan', detail: 'Check for vulnerable dependencies' },
    { title: 'Secrets Detection', detail: 'Find hardcoded secrets' },
    { title: 'OWASP Scan', detail: 'Check for common vulnerabilities' },
    { title: 'License Compliance', detail: 'Check dependency licenses' },
    { title: 'Multi-AI Verification', detail: 'Reduce false positives', model: 'opus' },
    { title: 'Impact Analysis', detail: 'Exploitability scoring' },
    { title: 'Auto-Decision', detail: 'Auto-create issues based on criteria' },
    { title: 'Create Issues', detail: 'Create security issues' },
  ],
}

log('')
log('═'.repeat(60))
log('🤖 AUTONOMOUS SECURITY SCANNER')
log('═'.repeat(60))
log('This workflow auto-creates issues for verified vulnerabilities')
log('')
log('Auto-decision criteria:')
log('  • All CRITICAL vulnerabilities')
log('  • All HIGH vulnerabilities with exploitable=true')
log('  • All verified secrets (likely_real=true)')
log('  • Consensus confidence ≥75%')
log('═'.repeat(60))
log('')

// Auto-decision criteria
const AUTO_CREATE_CRITERIA = {
  all_critical: true,
  high_exploitable: true,
  verified_secrets: true,
  min_confidence: 0.75
}

log('🔄 Delegating to code-security workflow with autonomous=true...')
log('')

// Call the base workflow with autonomous flag
const result = await workflow('code-security', { autonomous: true })

log('')
log('═'.repeat(60))
log('✅ AUTONOMOUS SECURITY SCAN COMPLETE')
log('═'.repeat(60))
if (result.issues_created) {
  log(`Issues created: ${result.issues_created}`)
}
if (result.critical_count) {
  log(`Critical: ${result.critical_count}`)
}
if (result.high_count) {
  log(`High: ${result.high_count}`)
}
log('═'.repeat(60))
log('')

return result
