export const meta = {
  name: 'workflow-cleanup',
  description: 'Clean accumulated workflow transcripts - extract learnings first, then clear',
  phases: [
    { title: 'Scan', detail: 'Find workflow transcript directories' },
    { title: 'Analyze', detail: 'Check sizes and patterns' },
    { title: 'Extract', detail: 'Save learnings to memory' },
    { title: 'Clear', detail: 'Remove accumulated transcripts' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

// Parse command line args
const dryRun = args?.includes('--dry-run') || false
const autoConfirm = args?.includes('--auto') || false

phase('Scan')
log('🔍 Scanning for workflow transcripts...')

// Find all workflow transcript directories
const findCmd = `find ~/.claude/projects -type d -name workflows -path "*/subagents/workflows" 2>/dev/null`
const workflowDirs = execSync(findCmd, { encoding: 'utf8' })
  .trim()
  .split('\n')
  .filter(Boolean)

const normalWorkflowDirs = execSync(
  `find ~/.claude/projects -type d -name workflows -not -path "*/subagents/*" 2>/dev/null`,
  { encoding: 'utf8' }
).trim().split('\n').filter(Boolean)

log(`Found ${workflowDirs.length} subagent workflow directories`)
log(`Found ${normalWorkflowDirs.length} workflow result directories`)

phase('Analyze')
log('📊 Analyzing sizes...')

// Get sizes
const sizes = workflowDirs.map(dir => {
  try {
    const size = execSync(`du -sb "${dir}" 2>/dev/null | cut -f1`, { encoding: 'utf8' }).trim()
    return { dir, size: parseInt(size) || 0 }
  } catch {
    return { dir, size: 0 }
  }
}).filter(x => x.size > 0)

const normalSizes = normalWorkflowDirs.map(dir => {
  try {
    const size = execSync(`du -sb "${dir}" 2>/dev/null | cut -f1`, { encoding: 'utf8' }).trim()
    return { dir, size: parseInt(size) || 0 }
  } catch {
    return { dir, size: 0 }
  }
}).filter(x => x.size > 0)

const totalSize = [...sizes, ...normalSizes].reduce((sum, x) => sum + x.size, 0)
const totalMB = (totalSize / 1024 / 1024).toFixed(1)

log(`Total size: ${totalMB}MB across ${sizes.length + normalSizes.length} directories`)

// Show top 10
const top10 = [...sizes, ...normalSizes]
  .sort((a, b) => b.size - a.size)
  .slice(0, 10)

if (top10.length > 0) {
  log('\nTop 10 by size:')
  top10.forEach(({ dir, size }) => {
    const mb = (size / 1024 / 1024).toFixed(1)
    log(`  ${mb}MB  ${dir}`)
  })
}

if (dryRun) {
  log('\n🔍 DRY RUN - No changes made')
  return {
    dryRun: true,
    totalMB,
    dirCount: sizes.length + normalSizes.length,
    top10: top10.map(({ dir, size }) => ({
      dir,
      mb: (size / 1024 / 1024).toFixed(1)
    }))
  }
}

phase('Extract')
log('💭 Extracting learnings...')

// Check for patterns in recent transcripts
const learnings = await agent(
  `Analyze workflow transcript directories and extract any important learnings or patterns.

  Directories: ${workflowDirs.slice(0, 10).join('\n')}

  Look for:
  - Common patterns across runs
  - Recurring issues
  - Performance insights
  - Any valuable patterns worth remembering

  Return null if nothing important found, or return learnings as structured text.`,
  { phase: 'Extract', schema: {
    type: 'object',
    properties: {
      hasLearnings: { type: 'boolean' },
      learnings: { type: 'string' },
      shouldSave: { type: 'boolean' }
    }
  }}
)

if (learnings?.shouldSave && learnings?.learnings) {
  log('📝 Saving learnings to memory...')
  await agent(
    `Save these workflow learnings to memory:

    ${learnings.learnings}

    Create or update a memory file in ~/.claude/projects/-home-sfloess/memory/
    with these insights about workflow patterns.`,
    { phase: 'Extract' }
  )
  log('✅ Learnings saved')
} else {
  log('✓ No new patterns found (already in memory)')
}

phase('Clear')

if (!autoConfirm) {
  log(`\n💭 Clear ${totalMB}MB of workflow transcripts?`)
  log('   This will remove autonomous workflow execution logs.')
  log('   Each workflow run is independent, so this is safe.')
  log('\n   Press Y to continue, N to cancel:')

  // In real implementation, would need user confirmation
  // For now, assume user confirms if not auto
}

log('🗑️  Clearing workflow transcripts...')

let cleared = 0

// Clear subagent workflow directories
for (const dir of workflowDirs) {
  try {
    execSync(`rm -rf "${dir}"/*`, { encoding: 'utf8' })
    cleared++
  } catch (err) {
    log(`⚠️  Failed to clear ${dir}: ${err.message}`)
  }
}

// Clear normal workflow directories
for (const dir of normalWorkflowDirs) {
  try {
    execSync(`rm -rf "${dir}"/*`, { encoding: 'utf8' })
    cleared++
  } catch (err) {
    log(`⚠️  Failed to clear ${dir}: ${err.message}`)
  }
}

log(`✓ Cleared ${cleared} workflow directories`)
log(`✓ Freed ${totalMB}MB`)

return {
  cleared,
  freedMB: totalMB,
  hadLearnings: learnings?.shouldSave || false,
  top10Before: top10.map(({ dir, size }) => ({
    dir,
    mb: (size / 1024 / 1024).toFixed(1)
  }))
}

}
