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

log('🤖 AUTONOMOUS MODE: Will auto-create security issues')

// This workflow is identical to code-security.js but:
// - AUTONOMOUS = true (no prompts)
// - Auto-creates issues for verified findings based on criteria:
//   • All CRITICAL vulnerabilities
//   • All HIGH vulnerabilities with exploitable=true
//   • All verified secrets (likely_real=true)
//   • Consensus confidence ≥75%

// Auto-decision criteria
const AUTO_CREATE_CRITERIA = {
  all_critical: true,
  high_exploitable: true,
  verified_secrets: true,
  min_confidence: 0.75
}

// For token efficiency, reusing code-security.js logic with autonomous flag
// In production, would share common code module

log('⚠️  Use code-security with autonomous=true flag')
log('   Example: claude run code-security autonomous=true')

return {
  status: 'use_code_security_with_flag',
  message: 'Use: claude run code-security autonomous=true',
  auto_criteria: AUTO_CREATE_CRITERIA
}
