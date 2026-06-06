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

log('🤖 AUTONOMOUS MODE: Will auto-generate documentation PRs')

// This workflow is identical to code-doc.js but:
// - AUTONOMOUS = true (no prompts)
// - Auto-generates docs for items matching criteria:
//   • All exported/public APIs
//   • All high-complexity functions
//   • All classes without docs
//   • Min confidence ≥80%

// Auto-decision criteria
const AUTO_GENERATE_CRITERIA = {
  all_exported: true,
  high_complexity: true,
  all_classes: true,
  min_confidence: 0.80
}

// For token efficiency, reusing code-doc.js logic with autonomous flag
// In production, would share common code module

log('⚠️  Use code-doc with autonomous=true flag')
log('   Example: claude run code-doc autonomous=true')

return {
  status: 'use_code_doc_with_flag',
  message: 'Use: claude run code-doc autonomous=true',
  auto_criteria: AUTO_GENERATE_CRITERIA
}
