export const meta = {
  name: 'code-sdlc-auto-continuous',
  description: 'Runs code-sdlc-auto in a loop until codebase is clean (all 7 SDLC phases)',
  whenToUse: 'When you want the full SDLC pipeline to run repeatedly until no issues remain',
  autonomous: true,
  phases: [
    { title: 'Development', detail: 'code-review-auto + code-solve-auto' },
    { title: 'Testing', detail: 'code-test-auto verification' },
    { title: 'PR Review', detail: 'code-pr-review-auto open PRs' },
    { title: 'Security', detail: 'code-security-auto audit' },
    { title: 'Documentation', detail: 'code-doc-auto generation' },
    { title: 'Release', detail: 'code-release-notes-auto publishing' },
    { title: 'Summary', detail: 'Aggregate results' },
  ],
}

log('═'.repeat(60))
log('🔄 CONTINUOUS SDLC LOOP')
log('═'.repeat(60))
log('Runs the full 7-phase SDLC pipeline repeatedly until clean:')
log('  1. Development → code-review-auto + code-solve-auto')
log('  2. Testing → code-test-auto')
log('  3. PR Review → code-pr-review-auto')
log('  4. Security → code-security-auto')
log('  5. Documentation → code-doc-auto')
log('  6. Release → code-release-notes-auto')
log('  7. Summary → Aggregate results')
log('')
log('Loop continues until:')
log('  ✅ No issues found')
log('  ✅ No PRs to review')
log('  ✅ No security vulnerabilities')
log('  ✅ All code documented')
log('  OR budget exhausted / max iterations reached')
log('═'.repeat(60))
log('')

const MAX_ITERATIONS = 5
const MIN_BUDGET_PER_ITERATION = 100_000

const stats = {
  iterations: 0,
  total_issues_created: 0,
  total_issues_fixed: 0,
  total_prs_reviewed: 0,
  total_security_issues: 0,
  total_docs_generated: 0,
  total_releases: 0,
}

let hasWork = true

while (hasWork && stats.iterations < MAX_ITERATIONS) {
  stats.iterations++

  log('')
  log('─'.repeat(60))
  log(`🔁 ITERATION ${stats.iterations}/${MAX_ITERATIONS}`)
  log('─'.repeat(60))
  log('')

  // Check budget
  if (budget.total && budget.remaining() < MIN_BUDGET_PER_ITERATION) {
    log(`⚠️  Insufficient budget (${Math.round(budget.remaining() / 1000)}k remaining, need ${MIN_BUDGET_PER_ITERATION / 1000}k)`)
    log('   Stopping loop')
    break
  }

  // Run the full SDLC pipeline
  log(`🚀 Running code-sdlc-auto (iteration ${stats.iterations})...`)
  log('')

  const result = await workflow('code-sdlc-auto', { autonomous: true })

  log('')
  log(`✅ Iteration ${stats.iterations} complete`)
  log('')

  // Aggregate stats
  if (result.development) {
    stats.total_issues_created += result.development.issues_created || 0
    if (result.development.solve_results) {
      stats.total_issues_fixed += result.development.solve_results.issues_fixed || 0
    }
  }

  if (result.pr_review) {
    stats.total_prs_reviewed += result.pr_review.prs_reviewed || 0
  }

  if (result.security) {
    stats.total_security_issues += result.security.total_issues || 0
  }

  if (result.documentation) {
    stats.total_docs_generated += result.documentation.documented || 0
  }

  if (result.release) {
    stats.total_releases++
  }

  // Determine if there's more work to do
  const issuesCreated = result.development?.issues_created || 0
  const prsOpen = result.pr_review?.prs_reviewed || 0
  const securityIssues = result.security?.total_issues || 0
  const breakingChanges = result.breaking_changes || false
  const criticalIssues = (result.critical_issues || []).length

  log(`📊 Iteration ${stats.iterations} results:`)
  log(`   Issues created: ${issuesCreated}`)
  log(`   Issues fixed: ${result.development?.solve_results?.issues_fixed || 0}`)
  log(`   PRs reviewed: ${prsOpen}`)
  log(`   Security issues: ${securityIssues}`)
  log(`   Docs generated: ${result.documentation?.documented || 0}`)
  log(`   Breaking changes: ${breakingChanges ? 'YES' : 'NO'}`)
  log(`   Critical issues: ${criticalIssues}`)
  log('')

  // Decide if we continue
  if (issuesCreated === 0 && prsOpen === 0 && securityIssues === 0 && !breakingChanges && criticalIssues === 0) {
    log('🎉 Codebase is clean - no more work to do!')
    hasWork = false
    break
  }

  log(`🔄 More work remains - continuing to iteration ${stats.iterations + 1}`)
}

// ============================================================================
// FINAL SUMMARY
// ============================================================================

log('')
log('═'.repeat(60))
log('🏁 CONTINUOUS SDLC LOOP COMPLETE')
log('═'.repeat(60))
log(`🔁 Iterations: ${stats.iterations}/${MAX_ITERATIONS}`)
log('')
log('📊 Cumulative Stats:')
log(`   Issues created: ${stats.total_issues_created}`)
log(`   Issues fixed: ${stats.total_issues_fixed}`)
log(`   PRs reviewed: ${stats.total_prs_reviewed}`)
log(`   Security issues: ${stats.total_security_issues}`)
log(`   Docs generated: ${stats.total_docs_generated}`)
log(`   Releases published: ${stats.total_releases}`)
log('')

// Determine final status
let finalStatus = ''
if (!hasWork) {
  finalStatus = '✅ Clean codebase - no issues remain!'
} else if (stats.iterations >= MAX_ITERATIONS) {
  finalStatus = '⚠️  Stopped - max iterations reached (work may remain)'
} else if (budget.total && budget.remaining() < MIN_BUDGET_PER_ITERATION) {
  finalStatus = `⚠️  Stopped - low budget (${Math.round(budget.remaining() / 1000)}k remaining)`
} else {
  finalStatus = '⚠️  Stopped - unknown reason (work may remain)'
}

log(`🎯 Final Status: ${finalStatus}`)
log('═'.repeat(60))

return {
  iterations: stats.iterations,
  clean: !hasWork,
  stats,
  stopped_reason: !hasWork ? 'clean' :
                 stats.iterations >= MAX_ITERATIONS ? 'max_iterations' :
                 budget.total && budget.remaining() < MIN_BUDGET_PER_ITERATION ? 'low_budget' : 'unknown',
}
