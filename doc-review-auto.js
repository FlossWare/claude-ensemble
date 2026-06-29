export const meta = {
  name: 'doc-review-auto',
  description: 'Autonomous documentation review - auto-creates issues for documentation problems',
  whenToUse: 'When you want fully automated documentation audit without manual intervention',
  autonomous: true,
  phases: [
    { title: 'Sync', detail: 'Sync with remote branch' },
    { title: 'Find Docs', detail: 'Identify documentation files' },
    { title: 'Code Analysis', detail: 'Analyze actual codebase features' },
    { title: 'Multi-AI Review', detail: 'Parallel doc reviews across models' },
    { title: 'Consensus', detail: 'Arbiter validates findings' },
    { title: 'Create Issues', detail: 'Auto-create issues for doc problems' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// AUTONOMOUS WORKFLOW - Auto-creates issues without prompting
// For interactive mode (prompts before creating), use doc-review

log('🤖 Mode: AUTONOMOUS (auto-creates issues)')
log('💡 Use doc-review for interactive mode (prompts before creating issues)')
log('')

// Delegate to doc-review workflow with autonomous flag
const result = await workflow('doc-review', {
  autonomous: true,
  ...(args || {})
})

// Return result from delegated workflow
return result

}
