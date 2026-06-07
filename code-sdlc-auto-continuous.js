export const meta = {
  name: 'code-sdlc-auto-continuous',
  description: 'Autonomous continuous SDLC loop - scan for bugs/security/quality, fix, test, commit until clean',
  whenToUse: 'When you want fully automated code fixing that loops until all issues (including critical security vulns) are resolved',
  autonomous: true,
  phases: [
    { title: 'Scan', detail: 'Find code issues' },
    { title: 'Fix', detail: 'Apply code fixes' },
    { title: 'Test', detail: 'Verify fixes work' },
    { title: 'Commit', detail: 'Commit successful fixes' },
    { title: 'Summary', detail: 'Report results' },
  ],
}

log('═'.repeat(60))
log('🔄 CONTINUOUS SDLC LOOP - AUTO-FIX MODE')
log('═'.repeat(60))
log('Scans: bugs, security vulnerabilities, code quality')
log('Fixes: all critical/high severity issues automatically')
log('')

const MAX_ITERATIONS = 10
const MAX_FIXES_PER_ITERATION = 5

const stats = {
  iterations: 0,
  total_issues_found: 0,
  total_fixes_applied: 0,
  total_commits: 0,
  failed_fixes: 0,
  phases_completed: [],
}

// Helper schema definitions
const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'number' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          category: { type: 'string' },
          title: { type: 'string' },
          description: { type: 'string' },
          suggested_fix: { type: 'string' }
        },
        required: ['file', 'severity', 'title', 'description']
      }
    }
  },
  required: ['findings']
}

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    files_modified: { type: 'array', items: { type: 'string' } },
    fix_applied: { type: 'boolean' },
    fix_description: { type: 'string' }
  },
  required: ['fix_applied']
}

const TEST_SCHEMA = {
  type: 'object',
  properties: {
    project_type: { type: 'string' },
    tests_passed: { type: 'number' },
    tests_failed: { type: 'number' },
    success: { type: 'boolean' }
  },
  required: ['success']
}

// ============================================================================
// MAIN LOOP
// ============================================================================

let hasIssues = true

while (hasIssues && stats.iterations < MAX_ITERATIONS) {
  stats.iterations++

  log('')
  log('─'.repeat(60))
  log(`🔁 ITERATION ${stats.iterations}/${MAX_ITERATIONS}`)
  log('─'.repeat(60))
  log('')

  // ==========================================================================
  // PHASE 1: SCAN
  // ==========================================================================

  phase('Scan')

  log('')
  log('═'.repeat(60))
  log(`📋 ITERATION ${stats.iterations}: SCAN PHASE`)
  log('═'.repeat(60))
  log('Scanning codebase for issues...')
  log('')

  const SCAN_DIMENSIONS = [
    {
      key: 'bugs',
      prompt: `Find critical bugs in the codebase: null pointer exceptions, resource leaks, race conditions, logic errors, infinite loops, incorrect error handling.

For each bug found, provide a suggested_fix field with specific code changes needed.
Return empty array if no bugs found.

Focus on high-impact issues that could cause runtime failures.`
    },
    {
      key: 'security',
      prompt: `Find CRITICAL security vulnerabilities: SQL injection, XSS, command injection, path traversal, insecure deserialization, hardcoded secrets, weak crypto, authentication bypasses.

For each vulnerability found, provide a suggested_fix field with specific secure code changes needed.
Return empty array if no vulnerabilities found.

Focus on CRITICAL/HIGH severity security issues that could lead to system compromise.`
    },
    {
      key: 'code-quality',
      prompt: `Find code quality issues: unused variables, duplicate code, overly complex methods, missing null checks, poor error messages.

For each issue found, provide a suggested_fix field with specific code changes needed.
Return empty array if no issues found.

Focus on issues that impact maintainability or could hide bugs.`
    },
  ]

  const scanResults = await parallel(SCAN_DIMENSIONS.map(dim => () =>
    agent(dim.prompt, {
      label: `scan-${dim.key}-iter${stats.iterations}`,
      phase: 'Scan',
      schema: FINDING_SCHEMA
    })
  ))

  const allFindings = scanResults
    .filter(Boolean)
    .flatMap(r => r.findings || [])
    .filter(f => f.severity === 'critical' || f.severity === 'high')

  stats.total_issues_found += allFindings.length
  log(`✅ Scan complete: ${allFindings.length} high/critical issues found`)

  if (allFindings.length === 0) {
    log('🎉 No more issues found - codebase is clean!')
    hasIssues = false
    break
  }

  // Limit fixes per iteration to avoid overwhelming the system
  const findingsToFix = allFindings.slice(0, MAX_FIXES_PER_ITERATION)

  if (allFindings.length > MAX_FIXES_PER_ITERATION) {
    log(`⚠️  Found ${allFindings.length} issues, fixing top ${MAX_FIXES_PER_ITERATION} this iteration`)
  }

  // ==========================================================================
  // PHASE 2: FIX CODE
  // ==========================================================================

  phase('Fix')

  log('')
  log('═'.repeat(60))
  log(`🔧 ITERATION ${stats.iterations}: FIX PHASE`)
  log('═'.repeat(60))
  log(`Applying fixes for ${findingsToFix.length} issues...`)
  log('')

  const fixResults = await pipeline(
    findingsToFix,
    // Stage 1: Apply fix
    (finding, idx) => agent(`Fix this code issue:

**File**: ${finding.file}${finding.line ? `:${finding.line}` : ''}
**Issue**: ${finding.title}
**Severity**: ${finding.severity}
**Description**: ${finding.description}
${finding.suggested_fix ? `\n**Suggested Fix**: ${finding.suggested_fix}` : ''}

Read the file, understand the issue, and apply the fix using the Edit tool.
Make minimal changes - only fix the specific issue, don't refactor surrounding code.

Return the list of files you modified and a brief description of what you changed.`, {
      label: `fix-${idx + 1}`,
      phase: 'Fix',
      schema: FIX_SCHEMA
    }),

    // Stage 2: Verify fix and test
    (fixResult, finding, idx) => {
      if (!fixResult || !fixResult.fix_applied) {
        log(`❌ Fix ${idx + 1} failed: ${finding.title}`)
        stats.failed_fixes++
        return null
      }

      log(`✅ Fix ${idx + 1} applied: ${fixResult.fix_description || finding.title}`)
      return { finding, fixResult }
    }
  )

  const successfulFixes = fixResults.filter(Boolean)
  stats.total_fixes_applied += successfulFixes.length

  log(`✅ Applied ${successfulFixes.length}/${findingsToFix.length} fixes`)

  if (successfulFixes.length === 0) {
    log('⚠️  No fixes could be applied - stopping')
    break
  }

  // ==========================================================================
  // PHASE 3: RUN TESTS
  // ==========================================================================

  phase('Test')

  log('')
  log('═'.repeat(60))
  log(`🧪 ITERATION ${stats.iterations}: TEST PHASE`)
  log('═'.repeat(60))
  log('Running tests to verify fixes...')
  log('')

  const testResult = await agent(`Run the project's test suite to verify the fixes didn't break anything.

For Maven: mvn test
For Gradle: ./gradlew test
For npm: npm test
For Python: pytest

Run the appropriate command and report results.`, {
    label: `test-iter${stats.iterations}`,
    phase: 'Test',
    schema: TEST_SCHEMA
  })

  if (!testResult || !testResult.success) {
    log('❌ Tests FAILED - rolling back changes')

    // Rollback
    await agent(`Tests failed after applying fixes. Rollback all changes from this iteration:

git checkout -- .
git clean -fd

Verify the working directory is clean.`, {
      label: `rollback-iter${stats.iterations}`,
      phase: 'Test'
    })

    log('↩️  Rolled back - will try different fixes next iteration')
    continue
  }

  log(`✅ Tests passed: ${testResult.tests_passed || 0} passed, ${testResult.tests_failed || 0} failed`)

  // ==========================================================================
  // PHASE 4: COMMIT
  // ==========================================================================

  phase('Commit')

  log('')
  log('═'.repeat(60))
  log(`💾 ITERATION ${stats.iterations}: COMMIT PHASE`)
  log('═'.repeat(60))
  log('Committing successful fixes...')
  log('')

  await agent(`Create a git commit for the fixes applied in iteration ${stats.iterations}:

Files modified: ${successfulFixes.flatMap(f => f.fixResult.files_modified || []).join(', ')}

Issues fixed:
${successfulFixes.map((f, i) => `${i + 1}. ${f.finding.title} (${f.finding.file})`).join('\n')}

Use git add and git commit with a descriptive message.
Format: "fix: [iteration ${stats.iterations}] Fixed ${successfulFixes.length} issues - <brief summary>"

Include Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`, {
    label: `commit-iter${stats.iterations}`,
    phase: 'Commit'
  })

  stats.total_commits++
  log(`✅ Committed ${successfulFixes.length} fixes`)

  // Check token budget if available
  if (budget.total && budget.remaining() < 30000) {
    log(`⚠️  Token budget low (${Math.round(budget.remaining() / 1000)}k remaining) - stopping`)
    break
  }
}

// ============================================================================
// FINAL SUMMARY
// ============================================================================

phase('Summary')

log('')
log('═'.repeat(60))
log('🏁 CONTINUOUS SDLC LOOP COMPLETE')
log('═'.repeat(60))
log(`🔁 Iterations: ${stats.iterations}/${MAX_ITERATIONS}`)
log(`📊 Total issues found: ${stats.total_issues_found}`)
log(`✅ Fixes applied: ${stats.total_fixes_applied}`)
log(`❌ Failed fixes: ${stats.failed_fixes}`)
log(`💾 Commits created: ${stats.total_commits}`)
log(`🎯 Status: ${hasIssues ? 'Stopped (max iterations or budget)' : 'Clean codebase!'}`)
log('═'.repeat(60))

return {
  iterations: stats.iterations,
  issues_found: stats.total_issues_found,
  fixes_applied: stats.total_fixes_applied,
  commits: stats.total_commits,
  clean: !hasIssues,
}
