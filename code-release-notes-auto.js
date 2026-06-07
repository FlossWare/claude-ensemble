export const meta = {
  name: 'code-release-notes-auto',
  description: 'Autonomous release notes generation - auto-publishes releases',
  whenToUse: 'When you want fully automated release generation without manual intervention',
  autonomous: true,
  phases: [
    { title: 'Detect Platform', detail: 'Identify GitHub/GitLab' },
    { title: 'Find Last Release', detail: 'Get previous release tag' },
    { title: 'Analyze Commits', detail: 'Categorize commits' },
    { title: 'Multi-AI Categorization', detail: 'Consensus categorization', model: 'opus' },
    { title: 'Impact Analysis', detail: 'Prioritize changes' },
    { title: 'Generate Notes', detail: 'Create release notes' },
    { title: 'Auto-Publish', detail: 'Tag and publish automatically' },
  ],
}

// Note: This is essentially the same as release-notes.js but with:
// - AUTONOMOUS = true (no user prompts)
// - Auto-publishes without confirmation
// - Follows same multi-AI categorization
// - Same impact analysis

// For brevity, using simplified inline version
// In production, would share code with release-notes.js

const VERSION = args?.version || args?.[0] || null

log('🤖 AUTONOMOUS MODE: Will auto-publish release')
if (VERSION) {
  log(`📦 Target version: ${VERSION}`)
}

// ... (Same phases as release-notes.js, but skips user confirmation)
// Auto-publishes at the end

// Placeholder for now - full implementation follows same pattern
log('⚠️  This is a simplified version - use release-notes with autonomous=true flag')
log('   Example: claude run release-notes autonomous=true')

return {
  status: 'use_release_notes_with_flag',
  message: 'Use: claude run release-notes autonomous=true'
}
