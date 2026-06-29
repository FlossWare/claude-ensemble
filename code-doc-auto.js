export const meta = {
  name: 'code-doc-auto',
  description: 'Autonomous documentation generation - auto-creates documentation PRs',
  whenToUse: 'When you want fully automated documentation generation without manual intervention',
  autonomous: true,
  phases: [
    { title: 'Detect Platform', detail: 'Identify GitHub/GitLab and project type' },
    { title: 'Find Undocumented Code', detail: 'Scan for missing docs' },
    { title: 'Analyze Signatures', detail: 'Extract function/class signatures' },
    { title: 'Multi-AI Doc Generation', detail: 'Generate docs with consensus', model: 'opus' },
    { title: 'Impact Analysis', detail: 'Prioritize by importance' },
    { title: 'README Completeness', detail: 'Check README gaps' },
    { title: 'Auto-Decision', detail: 'Auto-create docs based on criteria' },
    { title: 'Generate Documentation', detail: 'Create PR with docs' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

log('')
log('═'.repeat(60))
log('📝 AUTONOMOUS DOCUMENTATION GENERATOR')
log('═'.repeat(60))
log('This workflow auto-creates documentation PRs')
log('')
log('Auto-decision criteria:')
log('  • All exported/public APIs')
log('  • All high-complexity functions')
log('  • All classes without docs')
log('  • Min confidence ≥80%')
log('═'.repeat(60))
log('')

// Auto-decision criteria
const AUTO_GENERATE_CRITERIA = {
  all_exported: true,
  high_complexity: true,
  all_classes: true,
  min_confidence: 0.80
}

log('🔄 Delegating to code-doc workflow with autonomous=true...')
log('')

// Pass through doc_branch and strategy from args if provided
const result = await workflow('code-doc', {
  autonomous: true,
  doc_branch: args?.doc_branch,
  strategy: args?.strategy
})

log('')
log('═'.repeat(60))
log('✅ AUTONOMOUS DOCUMENTATION COMPLETE')
log('═'.repeat(60))
if (result.pr_number) {
  log(`PR created: #${result.pr_number}`)
}
if (result.docs_generated) {
  log(`Docs generated: ${result.docs_generated}`)
}
if (result.coverage) {
  log(`Coverage: ${result.coverage}%`)
}
log('═'.repeat(60))
log('')

return result

}
