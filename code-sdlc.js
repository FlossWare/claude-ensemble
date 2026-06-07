export const meta = {
  name: 'code-sdlc',
  description: 'Complete SDLC automation - all phases from development to release',
  whenToUse: 'When you want end-to-end SDLC automation with manual approval gates',
  phases: [
    { title: 'Development', detail: 'code-review + code-solve' },
    { title: 'Testing', detail: 'Comprehensive test verification' },
    { title: 'PR Review', detail: 'Review and merge open PRs' },
    { title: 'Security', detail: 'OWASP + secrets + dependencies' },
    { title: 'Documentation', detail: 'Generate missing docs' },
    { title: 'Release', detail: 'Publish release notes' },
    { title: 'Summary', detail: 'Aggregate results and report' },
  ],
}

const AUTONOMOUS = args?.autonomous === true

log('🚀 SDLC AUTOMATION PIPELINE')
log(`   Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)
log(`   Budget: ${budget.total ? `${Math.round(budget.total/1000)}k tokens` : 'unlimited'}`)
log('')

// Track results across all phases
const results = {
  development: null,
  testing: null,
  pr_review: null,
  security: null,
  documentation: null,
  release: null,
  phases_run: [],
  phases_skipped: [],
  breaking_changes: false,
  critical_issues: [],
}

// ============================================================================
// PHASE 1: DEVELOPMENT (code-review + code-solve)
// ============================================================================

phase('Development')

log('')
log('═'.repeat(60))
log('📋 PHASE 1/6: DEVELOPMENT')
log('═'.repeat(60))
log('Running: code-review + code-solve')
log('')

// Check budget before starting
if (budget.total && budget.remaining() < 50_000) {
  log('⚠️  Insufficient budget for development phase (need 50k min)')
  return { status: 'budget_exhausted', results }
}

// Run code-review
log('🔍 Running code-review...')
const reviewResults = await workflow('code-review', { autonomous: AUTONOMOUS })
results.development = reviewResults
results.phases_run.push('development')

log(`✅ Review complete: ${reviewResults.issues_created || 0} issues created`)

// If issues found and we have budget, run code-solve
let solveResults = null
if (reviewResults.issues_created > 0) {
  if (budget.total && budget.remaining() < 100_000) {
    log('⚠️  Insufficient budget for code-solve (skipping fixes)')
  } else {
    log(`🔧 Running code-solve for ${reviewResults.issues_created} issues...`)
    solveResults = await workflow('code-solve', { autonomous: AUTONOMOUS })
    results.development.solve_results = solveResults

    // Check for breaking changes
    if (solveResults.breaking_changes_detected) {
      results.breaking_changes = true
      log('⚠️  BREAKING CHANGES detected in fixes!')
    }

    log(`✅ Solve complete: ${solveResults.issues_fixed || 0} issues fixed`)
  }
} else {
  log('ℹ️  No issues found, skipping code-solve')
}

// ============================================================================
// PHASE 2: TESTING (code-test)
// ============================================================================

phase('Testing')

log('')
log('═'.repeat(60))
log('🧪 PHASE 2/6: TESTING')
log('═'.repeat(60))
log('Running: code-test')
log('')

// Only run if issues were fixed or if autonomous
const shouldTest = solveResults || AUTONOMOUS

if (!shouldTest) {
  log('ℹ️  No fixes applied, skipping testing phase')
  results.phases_skipped.push('testing')
} else {
  if (budget.total && budget.remaining() < 80_000) {
    log('⚠️  Insufficient budget for testing phase (skipping)')
    results.phases_skipped.push('testing')
  } else {
    log('🧪 Running comprehensive tests...')
    const testResults = await workflow('code-test', { autonomous: AUTONOMOUS })
    results.testing = testResults
    results.phases_run.push('testing')

    // Check for critical test failures
    if (testResults.critical_failures > 0) {
      results.critical_issues.push(`${testResults.critical_failures} critical test failures`)
      log(`⚠️  ${testResults.critical_failures} CRITICAL test failures detected!`)
    }

    log(`✅ Testing complete: ${testResults.tests_run || 0} tests run`)
  }
}

// ============================================================================
// PHASE 3: PR REVIEW (code-pr-review)
// ============================================================================

phase('PR Review')

log('')
log('═'.repeat(60))
log('🔀 PHASE 3/6: PR REVIEW')
log('═'.repeat(60))
log('Running: code-pr-review')
log('')

// Check if there are open PRs first
const prCheck = await agent(`Check for open PRs/MRs.

Run: gh pr list --json number
or: glab mr list

Return count of open PRs.`, {
  label: 'Check PRs',
  schema: {
    type: 'object',
    properties: {
      open_prs: { type: 'number' },
      platform: { type: 'string' }
    }
  }
})

if (prCheck.open_prs === 0) {
  log('ℹ️  No open PRs/MRs, skipping PR review phase')
  results.phases_skipped.push('pr_review')
} else {
  if (budget.total && budget.remaining() < 100_000) {
    log('⚠️  Insufficient budget for PR review phase (skipping)')
    results.phases_skipped.push('pr_review')
  } else {
    log(`🔀 Reviewing ${prCheck.open_prs} open PRs...`)
    const prResults = await workflow('code-pr-review', { autonomous: AUTONOMOUS })
    results.pr_review = prResults
    results.phases_run.push('pr_review')

    // Check for breaking changes in PRs
    if (prResults.breaking_changes_detected) {
      results.breaking_changes = true
      log('⚠️  BREAKING CHANGES detected in PRs!')
    }

    log(`✅ PR Review complete: ${prResults.prs_approved || 0} approved, ${prResults.prs_rejected || 0} rejected`)
  }
}

// ============================================================================
// DECISION GATE: Proceed to security/docs/release?
// ============================================================================

log('')
log('═'.repeat(60))
log('🚦 DECISION GATE: Continue to Security/Docs/Release?')
log('═'.repeat(60))

// Check if we should continue
const shouldContinue = !results.breaking_changes &&
                       results.critical_issues.length === 0 &&
                       (budget.total ? budget.remaining() > 150_000 : true)

if (!shouldContinue) {
  log('🛑 STOPPING PIPELINE')
  if (results.breaking_changes) log('   Reason: Breaking changes detected')
  if (results.critical_issues.length > 0) log(`   Reason: ${results.critical_issues.length} critical issues`)
  if (budget.total && budget.remaining() < 150_000) log('   Reason: Insufficient budget')
  log('')
  log('ℹ️  Fix critical issues before proceeding to security/docs/release')

  return {
    status: 'stopped_at_gate',
    reason: results.breaking_changes ? 'breaking_changes' : 'critical_issues',
    results
  }
}

log('✅ Gate passed: Proceeding to security/docs/release phases')

// ============================================================================
// PHASE 4: SECURITY (code-security)
// ============================================================================

phase('Security')

log('')
log('═'.repeat(60))
log('🔒 PHASE 4/6: SECURITY')
log('═'.repeat(60))
log('Running: code-security')
log('')

if (budget.total && budget.remaining() < 80_000) {
  log('⚠️  Insufficient budget for security phase (skipping)')
  results.phases_skipped.push('security')
} else {
  log('🔒 Running security audit...')
  const securityResults = await workflow('code-security', { autonomous: AUTONOMOUS })
  results.security = securityResults
  results.phases_run.push('security')

  // Check for critical vulnerabilities
  if (securityResults.critical_vulns > 0) {
    results.critical_issues.push(`${securityResults.critical_vulns} critical security vulnerabilities`)
    log(`⚠️  ${securityResults.critical_vulns} CRITICAL vulnerabilities found!`)

    // Block release if critical vulns and not autonomous
    if (!AUTONOMOUS) {
      log('🛑 Release blocked due to critical security vulnerabilities')
      return {
        status: 'stopped_at_security',
        reason: 'critical_vulnerabilities',
        results
      }
    }
  }

  log(`✅ Security audit complete: ${securityResults.total_issues || 0} issues found`)
}

// ============================================================================
// PHASE 5: DOCUMENTATION (code-doc)
// ============================================================================

phase('Documentation')

log('')
log('═'.repeat(60))
log('📚 PHASE 5/6: DOCUMENTATION')
log('═'.repeat(60))
log('Running: code-doc')
log('')

if (budget.total && budget.remaining() < 80_000) {
  log('⚠️  Insufficient budget for documentation phase (skipping)')
  results.phases_skipped.push('documentation')
} else {
  log('📚 Generating documentation...')
  const docResults = await workflow('code-doc', { autonomous: AUTONOMOUS })
  results.documentation = docResults
  results.phases_run.push('documentation')

  log(`✅ Documentation complete: ${docResults.documented || 0} items documented`)
}

// ============================================================================
// PHASE 6: RELEASE (code-release-notes)
// ============================================================================

phase('Release')

log('')
log('═'.repeat(60))
log('📦 PHASE 6/6: RELEASE')
log('═'.repeat(60))
log('Running: code-release-notes')
log('')

// Check if we should release
const canRelease = results.critical_issues.length === 0 &&
                   !results.breaking_changes

if (!canRelease) {
  log('🛑 Release blocked due to critical issues or breaking changes')
  results.phases_skipped.push('release')
} else {
  if (budget.total && budget.remaining() < 50_000) {
    log('⚠️  Insufficient budget for release phase (skipping)')
    results.phases_skipped.push('release')
  } else {
    // Check if there are commits to release
    const commitCheck = await agent(`Check for unreleased commits.

Run: git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~10")..HEAD | wc -l

Return count of commits since last release.`, {
      label: 'Check Commits',
      schema: {
        type: 'object',
        properties: {
          unreleased_commits: { type: 'number' }
        }
      }
    })

    if (commitCheck.unreleased_commits === 0) {
      log('ℹ️  No unreleased commits, skipping release phase')
      results.phases_skipped.push('release')
    } else {
      log(`📦 Creating release for ${commitCheck.unreleased_commits} commits...`)
      const releaseResults = await workflow('code-release-notes', { autonomous: AUTONOMOUS })
      results.release = releaseResults
      results.phases_run.push('release')

      log(`✅ Release complete: ${releaseResults.version || 'unknown'}`)
    }
  }
}

// ============================================================================
// PHASE 7: SUMMARY & REPORT
// ============================================================================

phase('Summary')

log('')
log('═'.repeat(60))
log('🎉 SDLC PIPELINE COMPLETE')
log('═'.repeat(60))

const tokensUsed = budget.total ? budget.spent() : 'unknown'

log(`💰 Tokens: ${tokensUsed === 'unknown' ? 'unlimited' : Math.round(tokensUsed/1000) + 'k'}`)
log(`✅ Phases run: ${results.phases_run.length}`)
log(`⏭️  Phases skipped: ${results.phases_skipped.length}`)
log('')

// Detailed results
if (results.development) {
  log(`📋 Development: ${results.development.issues_created || 0} issues created, ${results.development.solve_results?.issues_fixed || 0} fixed`)
}
if (results.testing) {
  log(`🧪 Testing: ${results.testing.tests_run || 0} tests run, ${results.testing.failures || 0} failures`)
}
if (results.pr_review) {
  log(`🔀 PR Review: ${results.pr_review.prs_reviewed || 0} PRs reviewed`)
}
if (results.security) {
  log(`🔒 Security: ${results.security.total_issues || 0} issues found`)
}
if (results.documentation) {
  log(`📚 Documentation: ${results.documentation.documented || 0} items documented`)
}
if (results.release) {
  log(`📦 Release: ${results.release.version || 'created'}`)
}

log('')

if (results.phases_skipped.length > 0) {
  log(`⚠️  Skipped phases: ${results.phases_skipped.join(', ')}`)
}

if (results.critical_issues.length > 0) {
  log('')
  log('🚨 CRITICAL ISSUES:')
  results.critical_issues.forEach(issue => log(`   - ${issue}`))
}

log('═'.repeat(60))

const result = {
  status: 'complete',
  elapsed_minutes: elapsed,
  tokens_used: tokensUsed,
  phases_run: results.phases_run,
  phases_skipped: results.phases_skipped,
  breaking_changes: results.breaking_changes,
  critical_issues: results.critical_issues,
  results
}

// Extract learnings from full SDLC
try {
  await workflow('extract-learning', {
    workflow_name: 'code-sdlc',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result
