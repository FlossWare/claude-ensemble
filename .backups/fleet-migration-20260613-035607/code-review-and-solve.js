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

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: model === 'opus' || model === 'fable' ? 2.0 : model === 'haiku' ? 0.5 : 1.5,
        estimated_duration: 60
      }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    return null;
  }
}

async function _completeAgent(jobId, server, success, duration, jobType, model, error) {
  if (!FLEET_ENABLED) return;
  try {
    await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, server, success, duration, job_type: jobType, model, error }),
    });
  } catch (e) {}
}

const _agent = async (prompt, opts = {}) => {
  const model = opts.model || 'sonnet';
  const jobType = 'agent'; // Can enhance with job type inference
  const dispatch = await _dispatchAgent(model, prompt, jobType);
  if (!dispatch) return agent(prompt, opts);
  
  const start = Date.now();
  try {
    const result = await agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


log('🔄 CODE REVIEW + SOLVE WORKFLOW')
log('═'.repeat(80))

// CRITICAL: Use DIFFERENT arbiters for different phases
const REVIEW_ARBITER = 'opus'   // For code review
const SOLVE_ARBITER = 'sonnet'  // For solving - DIFFERENT from review!
const VERIFY_ARBITER = 'haiku'  // For verification - DIFFERENT from both!

// Multi-AI: Always use all available models for maximum coverage
const WORKER_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']

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

const commitHistory = await _agent(`Get detailed commit history for the last ${DAYS_BACK} days.

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

  // Review diff - multi-model consensus: all workers review independently
  (diffData, _, idx) => {
    log(`🔍 [${idx + 1}/${Math.min(MAX_COMMITS, commitHistory.total_commits)}] Multi-AI reviewing commit ${diffData.commit_hash.slice(0, 8)}...`)

    const reviewSchema = {
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

    const reviewPrompt = `Code review of commit ${diffData.commit_hash}:

Files: ${diffData.files_changed?.join(', ')}

${diffData.diff}

Find issues:
- Security vulnerabilities
- Logic bugs
- Performance problems
- Code quality issues

Focus on critical and major issues only.`

    return parallel(WORKER_MODELS.map(model =>
      () => agent(reviewPrompt, {
        label: `${model} Review: ${diffData.commit_hash.slice(0, 8)}`,
        model: model,
        schema: reviewSchema
      })
    )).then(reviews => {
      // Merge all worker findings
      const allIssues = reviews.filter(Boolean).flatMap(r => r.issues || [])
      return {
        issues: allIssues,
        commit_hash: diffData.commit_hash
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

const sourceFiles = await _agent(`Find source code files (exclude vendor, node_modules, tests).

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
    log(`🔍 [${idx + 1}/${Math.min(MAX_FILES, sourceFiles.files?.length || 0)}] Multi-AI reviewing file: ${filepath}`)

    const fileReviewSchema = {
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

    const fileReviewPrompt = `Security and logic review of ${filepath}

Find critical issues:
- Security vulnerabilities (SQL injection, XSS, secrets, auth issues)
- Logic bugs (null pointers, race conditions, edge cases)
- Critical performance issues

Focus on high-confidence findings only.`

    return parallel(WORKER_MODELS.map(model =>
      () => agent(fileReviewPrompt, {
        label: `${model}: ${filepath.split('/').pop()}`,
        model: model,
        schema: fileReviewSchema
      })
    )).then(reviews => ({
      file: filepath,
      issues: reviews.filter(Boolean).flatMap(r => r.issues || [])
    }))
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

  await _agent(`Wait for issues to be created.

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

    // Generate fix - multi-model: all workers propose, arbiter selects best
    (issue, _, idx) => {
      log(`🔧 [${idx + 1}/${validIssues.length}] Multi-AI generating fix for issue #${issue.number}...`)

      const fixSchema = {
        type: 'object',
        properties: {
          issue_number: { type: 'number' },
          fix_description: { type: 'string' },
          confidence: { type: 'number', minimum: 0, maximum: 100 },
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

      const fixPrompt = `Generate a fix for this issue:

**Issue #${issue.number}**: ${issue.title}

${issue.body}

Analyze the issue, identify the root cause, and propose a complete fix.
Include file paths, code changes, and explanation.`

      return parallel(WORKER_MODELS.map(model =>
        () => agent(fixPrompt, {
          label: `${model} Fix #${issue.number}`,
          model: model,
          schema: fixSchema
        })
      )).then(async fixes => {
        const validFixes = fixes.filter(Boolean)
        if (validFixes.length === 0) return { issue_number: issue.number, fix_description: '', files_to_modify: [] }

        // Arbiter selects best fix
        const arbiterResult = await _agent(`Review these ${validFixes.length} fix proposals for issue #${issue.number}:

${validFixes.map((f, i) => `Fix ${i + 1}: ${f.fix_description} (confidence: ${f.confidence || 'N/A'}%)`).join('\n')}

Select the best fix (return its index 0-${validFixes.length - 1}).`, {
          label: `Arbiter: Fix #${issue.number}`,
          model: SOLVE_ARBITER,
          schema: {
            type: 'object',
            properties: {
              selected_index: { type: 'number' },
              reasoning: { type: 'string' }
            },
            required: ['selected_index']
          }
        })

        const selectedIdx = Math.min(Math.max(0, arbiterResult.selected_index || 0), validFixes.length - 1)
        return validFixes[selectedIdx]
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
        log(`🔍 [${idx + 1}/${Math.min(10, modifiedFiles.length)}] Multi-AI verifying: ${filepath}`)

        const verifySchema = {
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

        const verifyPrompt = `Quick verification review of ${filepath} after fix was applied.

Look for:
- New bugs introduced by the fix
- Syntax errors
- Logic errors
- Regressions
- Edge cases not handled

Focus on critical issues only. Return empty array if fix looks good.`

        return parallel(WORKER_MODELS.map(model =>
          () => agent(verifyPrompt, {
            label: `${model} Verify: ${filepath.split('/').pop()}`,
            model: model,
            schema: verifySchema
          })
        )).then(results => ({
          file: filepath,
          new_issues: results.filter(Boolean).flatMap(r => r.new_issues || [])
        }))
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
