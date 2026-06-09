// AUTONOMOUS WORKFLOW - Full Code Review + Auto-Solve
// Self-contained implementation without nested workflow() calls
// Uses pipeline with inline agent calls for issue solving

export const meta = {
  name: 'code-review-and-solve',
  description: 'Complete code quality loop: review finds issues, solve fixes them, verify fixes (AUTONOMOUS)',
  phases: [
    { title: 'Code Review', detail: 'Find issues across commits, files, and security' },
    { title: 'Create Issues', detail: 'Create GitHub/GitLab issues for findings' },
    { title: 'Wait', detail: 'Allow issues to be created' },
    { title: 'Code Solve', detail: 'Auto-resolve all found issues' },
    { title: 'Verify Fixes', detail: 'Check fixes didn\'t introduce new bugs' },
    { title: 'Summary', detail: 'Report on issues found, fixed, and verified' },
  ],
}

log('🔄 CODE REVIEW + SOLVE WORKFLOW')
log('═'.repeat(80))

// CRITICAL: Use DIFFERENT arbiters for different phases
const REVIEW_ARBITER = 'opus'   // For code review
const SOLVE_ARBITER = 'sonnet'  // For solving - DIFFERENT from review!
const VERIFY_ARBITER = 'haiku'  // For verification - DIFFERENT from both!

const allFindings = []
const DAYS_BACK = args?.days || 30
const MAX_COMMITS = args?.maxCommits || 5
const MAX_FILES = args?.maxFiles || 10
const CONFIDENCE_THRESHOLD = 70

log('⚙️  Configuration:')
log(`   Review window: Last ${DAYS_BACK} days`)
log(`   Max commits: ${MAX_COMMITS}`)
log(`   Max files: ${MAX_FILES}`)
log(`   Confidence threshold: ${CONFIDENCE_THRESHOLD}%`)
log(`   Max issues to create: 20`)
log(`   Arbiters: Review=${REVIEW_ARBITER}, Solve=${SOLVE_ARBITER}, Verify=${VERIFY_ARBITER}`)
log('')

// PHASE 1: Code Review
phase('Code Review')

log('🔍 Running focused code review...')
log(`   Commits: last ${DAYS_BACK} days (max ${MAX_COMMITS})`)
log(`   Files: max ${MAX_FILES}`)
log(`   Confidence threshold: ${CONFIDENCE_THRESHOLD}%`)

// 1.1: Review Recent Commits
log('📅 Analyzing recent commits...')

const commitHistory = await agent(`Get detailed commit history for the last ${DAYS_BACK} days.

Execute:
git log --since="${DAYS_BACK} days ago" --pretty=format:"%H|%an|%ad|%s" --date=short

Return structured data about each commit.`, {
  label: 'Fetch Commit History',
  schema: {
    type: 'object',
    properties: {
      commits: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            hash: { type: 'string' },
            author: { type: 'string' },
            date: { type: 'string' },
            message: { type: 'string' },
          }
        }
      },
      total_commits: { type: 'number' }
    },
    required: ['commits', 'total_commits']
  }
})

log(`✅ Found ${commitHistory.total_commits} commits`)

// Review each commit
const commitFindings = await pipeline(
  commitHistory.commits.slice(0, MAX_COMMITS),

  // Get diff
  (commit, idx) => {
    log(`📝 [${idx + 1}/${Math.min(MAX_COMMITS, commitHistory.total_commits)}] Getting diff for ${commit.hash.slice(0, 8)}: "${commit.message.slice(0, 60)}..."`)
    return agent(`Get the full diff for commit ${commit.hash}.

Execute:
git show ${commit.hash} --stat
git diff ${commit.hash}^..${commit.hash}

Return the files changed and diff content.`, {
      label: `Diff: ${commit.hash.slice(0, 8)}`,
      schema: {
        type: 'object',
        properties: {
          files_changed: { type: 'array', items: { type: 'string' } },
          diff: { type: 'string' },
          commit_hash: { type: 'string' }
        }
      }
    })
  },

  // Review diff
  (diffData, _, idx) => {
    log(`🔍 [${idx + 1}/${Math.min(MAX_COMMITS, commitHistory.total_commits)}] Reviewing commit ${diffData.commit_hash.slice(0, 8)}...`)
    return agent(`Code review of commit ${diffData.commit_hash}:

Files: ${diffData.files_changed?.join(', ')}

${diffData.diff}

Find issues:
- Security vulnerabilities
- Logic bugs
- Performance problems
- Code quality issues

Focus on critical and major issues only.`, {
      label: `Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: REVIEW_ARBITER,
      schema: {
        type: 'object',
        properties: {
          issues: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
                category: { type: 'string' },
                description: { type: 'string' },
                file: { type: 'string' },
                line_hint: { type: 'string' },
                confidence: { type: 'number', minimum: 0, maximum: 100 }
              }
            }
          },
          commit_hash: { type: 'string' }
        }
      }
    })
  }
)

// Collect commit findings
let commitIssueCount = 0
commitFindings.filter(Boolean).forEach(cf => {
  cf.issues?.forEach(issue => {
    if (issue.confidence >= CONFIDENCE_THRESHOLD) {
      commitIssueCount++
      allFindings.push({
        source: 'commit_review',
        commit_hash: cf.commit_hash,
        ...issue
      })
    }
  })
})

log(`✅ Commit review complete: ${commitIssueCount} issues found (${allFindings.length} total so far)`)
log(`   Breakdown: ${commitFindings.filter(Boolean).map(cf => `${cf.commit_hash?.slice(0, 8)}: ${cf.issues?.filter(i => i.confidence >= CONFIDENCE_THRESHOLD).length || 0}`).join(', ')}`)

// 1.2: Review Source Files
log('🔍 Scanning source files...')

const sourceFiles = await agent(`Find source code files (exclude vendor, node_modules, tests).

Execute:
find . -type f \\( -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.java" -o -name "*.go" -o -name "*.rb" -o -name "*.sh" \\) | grep -v node_modules | grep -v vendor | grep -v ".git" | grep -v test | head -${MAX_FILES}

Return list of files.`, {
  label: 'Find Source Files',
  schema: {
    type: 'object',
    properties: {
      files: { type: 'array', items: { type: 'string' } }
    }
  }
})

log(`✅ Found ${sourceFiles.files?.length || 0} files to review`)

// Review files
const fileFindings = await pipeline(
  (sourceFiles.files || []).slice(0, MAX_FILES),

  (filepath, idx) => {
    log(`🔍 [${idx + 1}/${Math.min(MAX_FILES, sourceFiles.files?.length || 0)}] Reviewing file: ${filepath}`)
    return agent(`Security and logic review of ${filepath}

Find critical issues:
- Security vulnerabilities (SQL injection, XSS, secrets, auth issues)
- Logic bugs (null pointers, race conditions, edge cases)
- Critical performance issues

Focus on high-confidence findings only.`, {
      label: `Review: ${filepath}`,
      schema: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          issues: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                severity: { type: 'string' },
                category: { type: 'string' },
                description: { type: 'string' },
                line_hint: { type: 'string' },
                confidence: { type: 'number' }
              }
            }
          }
        }
      }
    })
  }
)

// Collect file findings
let fileIssueCount = 0
fileFindings.filter(Boolean).forEach(ff => {
  ff.issues?.forEach(issue => {
    if (issue.confidence >= CONFIDENCE_THRESHOLD) {
      fileIssueCount++
      allFindings.push({
        source: 'file_review',
        file: ff.file,
        ...issue
      })
    }
  })
})

log(`✅ File review complete: ${fileIssueCount} issues found (${allFindings.length} total so far)`)
log(`   Top issues: ${fileFindings.filter(Boolean).sort((a, b) => (b.issues?.length || 0) - (a.issues?.length || 0)).slice(0, 3).map(ff => `${ff.file}: ${ff.issues?.filter(i => i.confidence >= CONFIDENCE_THRESHOLD).length || 0}`).join(', ')}`)

// Deduplicate findings
const uniqueFindings = allFindings.reduce((acc, finding) => {
  const key = `${finding.file}:${finding.description?.slice(0, 50)}`
  if (!acc[key]) {
    acc[key] = finding
  }
  return acc
}, {})

const dedupedFindings = Object.values(uniqueFindings)
const duplicatesRemoved = allFindings.length - dedupedFindings.length

log(`✅ Deduplicated: ${dedupedFindings.length} unique issues (removed ${duplicatesRemoved} duplicates)`)

// Show severity breakdown
const severityBreakdown = dedupedFindings.reduce((acc, f) => {
  acc[f.severity || 'unknown'] = (acc[f.severity || 'unknown'] || 0) + 1
  return acc
}, {})
log(`   Severity: critical=${severityBreakdown.critical || 0}, major=${severityBreakdown.major || 0}, minor=${severityBreakdown.minor || 0}`)

// PHASE 2: Create Issues
phase('Create Issues')

let createdIssues = []

if (dedupedFindings.length > 0) {
  const issuesToCreate = Math.min(dedupedFindings.length, 20)
  log(`📝 Creating ${issuesToCreate} GitHub issues...`)
  if (dedupedFindings.length > 20) {
    log(`   ⚠️  Limiting to 20 issues (found ${dedupedFindings.length})`)
  }

  createdIssues = await pipeline(
    dedupedFindings.slice(0, 20), // Max 20 issues

    (finding, idx) => {
      log(`📝 [${idx + 1}/${issuesToCreate}] Creating issue: [${finding.severity?.toUpperCase()}] ${finding.category} - ${finding.description?.slice(0, 60)}...`)

      const issueTitle = finding.severity + ' ' + finding.category + ' in ' + finding.file
      const issueBody = 'Severity: ' + finding.severity + ', Description: ' + finding.description

      return agent(`Create a GitHub issue.

Title: ${issueTitle}
Body: ${issueBody}

Execute:
gh issue create --title "${issueTitle}" --body "${issueBody}" --label bug,automated-review

Return the issue number.`, {
      label: `Create Issue: ${finding.description?.slice(0, 30)}`,
      schema: {
        type: 'object',
        properties: {
          issue_number: { type: 'number' }
        }
      }
    })
  )

  const successCount = createdIssues.filter(Boolean).length
  const failedCount = issuesToCreate - successCount
  log(`✅ Created ${successCount}/${issuesToCreate} issues${failedCount > 0 ? ` (${failedCount} failed)` : ''}`)

  // Show created issue numbers
  const issueNums = createdIssues.filter(Boolean).map(i => i.issue_number).filter(Boolean)
  if (issueNums.length > 0) {
    log(`   Issue numbers: ${issueNums.join(', ')}`)
  }
} else {
  log('✅ No issues to create')
}

// PHASE 3: Wait for Issues
phase('Wait')

if (createdIssues.length > 0) {
  log('⏳ Waiting 10 seconds for GitHub to process issues...')

  await agent(`Wait for issues to be created.

Execute:
sleep 10

This gives GitHub time to create all the issues.`, {
    label: 'Wait for Issues'
  })

  log('✅ Wait complete')
}

// PHASE 4: Code Solve
phase('Code Solve')

const validIssues = createdIssues.filter(Boolean)
let solveResults = []

if (validIssues.length > 0) {
  log(`🔧 Auto-resolving ${validIssues.length} issues...`)

  // Get the issue numbers
  const issueNumbers = validIssues.map(r => r.issue_number)

  log(`📝 Will attempt to solve: ${issueNumbers.join(', ')}`)
  log('')

  // Solve each issue - simplified inline approach without nested workflow calls
  solveResults = await pipeline(
    issueNumbers,

    // Fetch issue details
    (issueNum, idx) => {
      log(`📥 [${idx + 1}/${validIssues.length}] Fetching issue #${issueNum}...`)
      return agent(`Get full details for issue #${issueNum}.

Execute:
gh issue view ${issueNum} --json number,title,body,labels

Return the issue details.`, {
        label: `Fetch #${issueNum}`,
        schema: {
          type: 'object',
          properties: {
            number: { type: 'number' },
            title: { type: 'string' },
            body: { type: 'string' },
            labels: { type: 'array' }
          }
        }
      })
    },

    // Generate fix
    (issue, _, idx) => {
      log(`🔧 [${idx + 1}/${validIssues.length}] Generating fix for issue #${issue.number}...`)
      return agent(`Generate a fix for this issue:

**Issue #${issue.number}**: ${issue.title}

${issue.body}

Analyze the issue, identify the root cause, and propose a complete fix.
Include file paths, code changes, and explanation.`, {
        label: `Fix #${issue.number}`,
        model: SOLVE_ARBITER,
        schema: {
          type: 'object',
          properties: {
            issue_number: { type: 'number' },
            fix_description: { type: 'string' },
            files_to_modify: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  file: { type: 'string' },
                  changes: { type: 'string' }
                }
              }
            }
          }
        }
      })
    },

    // Apply fix and close issue
    (fix, _, idx) => {
      log(`✅ [${idx + 1}/${validIssues.length}] Applying fix for issue #${fix.issue_number}...`)

      const filesToModify = fix.files_to_modify || []
      if (filesToModify.length === 0) {
        log(`⚠️  No files to modify for #${fix.issue_number}`)
        return { status: 'skipped', issue_number: fix.issue_number, reason: 'No files to modify' }
      }

      return agent(`Apply the fix for issue #${fix.issue_number}.

Fix description: ${fix.fix_description}

Files to modify:
${filesToModify.map(f => `- ${f.file}: ${f.changes}`).join('\n')}

Execute the following steps:
1. Apply the changes to each file
2. Create a commit with message: "Fix #${fix.issue_number}: ${fix.fix_description?.slice(0, 50)}"
3. Close issue #${fix.issue_number} with: gh issue close ${fix.issue_number} --comment "Fixed via automated code-solve"

Return the status.`, {
        label: `Apply #${fix.issue_number}`,
        schema: {
          type: 'object',
          properties: {
            status: { type: 'string', enum: ['success', 'error'] },
            issue_number: { type: 'number' },
            files_modified: { type: 'array', items: { type: 'string' } },
            commit_hash: { type: 'string' }
          }
        }
      })
    }
  )

  const successful = solveResults.filter(r => r?.status === 'success').length
  const failed = validIssues.length - successful

  log('')
  log(`✅ Code solve complete: ${successful}/${validIssues.length} issues resolved${failed > 0 ? ` (${failed} failed)` : ''}`)

  // Show which issues were solved
  const solvedIssues = solveResults.filter(r => r?.status === 'success').map(r => r.issue_number).filter(Boolean)
  const failedIssues = issueNumbers.filter(n => !solvedIssues.includes(n))

  if (solvedIssues.length > 0) {
    log(`   ✅ Solved: ${solvedIssues.join(', ')}`)
  }
  if (failedIssues.length > 0) {
    log(`   ❌ Failed: ${failedIssues.join(', ')}`)
  }
} else {
  log('ℹ️  No issues to solve')
}

// PHASE 5: Verify Fixes
phase('Verify Fixes')

let verificationResults = []

// Calculate issues solved before using it
const issuesSolved = solveResults?.filter(r => r?.status === 'success').length || 0

if (issuesSolved > 0) {
  log(`🔍 Verifying ${issuesSolved} fixes didn't introduce new bugs...`)

  // Get list of files modified by successful fixes
  const modifiedFiles = solveResults
    .filter(r => r?.status === 'success')
    .flatMap(r => r?.files_modified || [])
    .filter(Boolean)
    .filter((f, idx, arr) => arr.indexOf(f) === idx) // dedupe

  if (modifiedFiles.length > 0) {
    log(`   Files to verify: ${modifiedFiles.slice(0, 5).join(', ')}${modifiedFiles.length > 5 ? ` + ${modifiedFiles.length - 5} more` : ''}`)

    // Quick review of modified files
    verificationResults = await pipeline(
      modifiedFiles.slice(0, 10), // Max 10 files to verify

      (filepath, idx) => {
        log(`🔍 [${idx + 1}/${Math.min(10, modifiedFiles.length)}] Verifying: ${filepath}`)
        return agent(`Quick verification review of ${filepath} after fix was applied.

Look for:
- New bugs introduced by the fix
- Syntax errors
- Logic errors
- Regressions
- Edge cases not handled

Focus on critical issues only. Return empty array if fix looks good.`, {
          label: `Verify: ${filepath}`,
          model: VERIFY_ARBITER,
          schema: {
            type: 'object',
            properties: {
              file: { type: 'string' },
              new_issues: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    severity: { type: 'string' },
                    description: { type: 'string' }
                  }
                }
              }
            }
          }
        })
      }
    )

    const newIssuesFound = verificationResults
      .filter(Boolean)
      .flatMap(v => v.new_issues || [])
      .filter(Boolean)

    if (newIssuesFound.length > 0) {
      log(`⚠️  Verification found ${newIssuesFound.length} new issues introduced by fixes`)
      newIssuesFound.forEach(issue => {
        log(`   - [${issue.severity?.toUpperCase()}] ${issue.description}`)
      })
    } else {
      log(`✅ Verification passed - no new issues found in fixes`)
    }
  } else {
    log('ℹ️  No files to verify')
  }
} else {
  log('ℹ️  No fixes to verify (none succeeded)')
}

// PHASE 6: Summary
phase('Summary')

const bySeverity = dedupedFindings.reduce((acc, f) => {
  const sev = f.severity || 'unknown'
  acc[sev] = (acc[sev] || 0) + 1
  return acc
}, {})

const bySource = dedupedFindings.reduce((acc, f) => {
  acc[f.source] = (acc[f.source] || 0) + 1
  return acc
}, {})

const issuesAttempted = validIssues.length

const newIssuesIntroduced = verificationResults
  .filter(Boolean)
  .flatMap(v => v.new_issues || [])
  .filter(Boolean)
  .length

const summary = {
  review: {
    total_findings: dedupedFindings.length,
    by_severity: bySeverity,
    by_source: bySource,
    issues_created: createdIssues.filter(Boolean).length
  },
  solve: {
    issues_attempted: issuesAttempted,
    issues_solved: issuesSolved,
    success_rate: issuesAttempted > 0
      ? Math.round((issuesSolved / issuesAttempted) * 100)
      : 0
  },
  verification: {
    files_verified: verificationResults.filter(Boolean).length,
    new_issues_introduced: newIssuesIntroduced,
    verification_passed: newIssuesIntroduced === 0
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
log(`   Issues created: ${summary.review.issues_created}`)
log('')
log('🔧 SOLVE RESULTS:')
log(`   Issues attempted: ${summary.solve.issues_attempted}`)
log(`   Issues solved: ${summary.solve.issues_solved}`)
log(`   Success rate: ${summary.solve.success_rate}%`)
log('')
log('🔍 VERIFICATION RESULTS:')
log(`   Files verified: ${summary.verification.files_verified}`)
log(`   New issues introduced: ${summary.verification.new_issues_introduced}`)
log(`   Verification: ${summary.verification.verification_passed ? '✅ PASSED' : '⚠️  FAILED'}`)
log('')
log('═'.repeat(80))

return summary
