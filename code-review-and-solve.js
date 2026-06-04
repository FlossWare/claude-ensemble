// AUTONOMOUS WORKFLOW - Full Code Review + Auto-Solve
// Runs code-review to find issues, then code-solve to fix them

export const meta = {
  name: 'code-review-and-solve',
  description: 'Complete code quality loop: review finds issues, solve fixes them (AUTONOMOUS)',
  phases: [
    { title: 'Code Review', detail: 'Find all issues across 5 review types' },
    { title: 'Wait', detail: 'Allow issues to be created in GitHub/GitLab' },
    { title: 'Code Solve', detail: 'Auto-resolve all found issues' },
    { title: 'Summary', detail: 'Report on issues found and fixed' },
  ],
}

log('🔄 CODE REVIEW + SOLVE WORKFLOW')
log('═'.repeat(80))

// PHASE 1: Run Code Review
phase('Code Review')
log('🔍 Running comprehensive code review...')

const reviewResult = await workflow('code-review', {
  autonomous: true,
  multiModel: args?.multiModel !== false,
  days: args?.days || 30,
  maxCommits: args?.maxCommits || 5,
  maxFiles: args?.maxFiles || 10
})

log(`✅ Code review complete`)
log(`   Issues found: ${reviewResult.total_findings}`)
log(`   Critical: ${reviewResult.by_severity?.critical || 0}`)
log(`   Major: ${reviewResult.by_severity?.major || 0}`)
log(`   Minor: ${reviewResult.by_severity?.minor || 0}`)

// PHASE 2: Wait for Issues to Be Created
phase('Wait')
log('⏳ Waiting 30 seconds for GitHub/GitLab to process issues...')

await agent(`Wait for issues to be created.

Execute:
sleep 30

This gives GitHub/GitLab time to create all the issues.`, {
  label: 'Wait for Issues'
})

log('✅ Wait complete')

// PHASE 3: Run Code Solve
phase('Code Solve')
log('🔧 Auto-resolving issues...')

const maxIssues = args?.maxSolve || 10

log(`📝 Will attempt to solve up to ${maxIssues} issues`)

const solveResult = await workflow('code-solve', {
  issueNumber: 'all',
  maxIssues
})

log(`✅ Code solve complete`)
log(`   Issues attempted: ${solveResult.issues_attempted || 0}`)
log(`   PRs created: ${solveResult.prs_created || 0}`)

// PHASE 4: Summary
phase('Summary')

const summary = {
  review: {
    total_findings: reviewResult.total_findings,
    by_severity: reviewResult.by_severity,
    by_source: reviewResult.by_source
  },
  solve: {
    issues_attempted: solveResult.issues_attempted || 0,
    prs_created: solveResult.prs_created || 0,
    success_rate: solveResult.issues_attempted > 0
      ? Math.round((solveResult.prs_created / solveResult.issues_attempted) * 100)
      : 0
  }
}

log('═'.repeat(80))
log('✅ CODE REVIEW + SOLVE COMPLETE')
log('═'.repeat(80))
log('')
log('📊 REVIEW RESULTS:')
log(`   Total findings: ${summary.review.total_findings}`)
log(`   Critical: ${summary.review.by_severity?.critical || 0}`)
log(`   Major: ${summary.review.by_severity?.major || 0}`)
log(`   Minor: ${summary.review.by_severity?.minor || 0}`)
log('')
log('🔧 SOLVE RESULTS:')
log(`   Issues attempted: ${summary.solve.issues_attempted}`)
log(`   PRs created: ${summary.solve.prs_created}`)
log(`   Success rate: ${summary.solve.success_rate}%`)
log('')
log('═'.repeat(80))

return summary
