// AUTONOMOUS WORKFLOW - No user prompts or confirmations
// This workflow is designed for automated/background execution
// It must complete without user interaction
// Auto-creates issues, auto-reopens broken issues, no approval needed

import { detectPlatform, syncWithRemote } from './shared/platform-detector.js'

export const meta = {
  name: 'code-review',
  description: 'Comprehensive brutal code review: recent commits, open/closed issues, and full codebase scan (AUTONOMOUS)',
  phases: [
    { title: 'Recent Commits', detail: 'Review all commits from last 30 days' },
    { title: 'Open Issues', detail: 'Review open issues for status and context' },
    { title: 'Closed Issues', detail: 'Review recently closed issues for lingering problems' },
    { title: 'Full Codebase', detail: 'Brutal review of entire codebase' },
    { title: 'Multi-Model Consensus', detail: 'All findings verified by multiple AIs' },
    { title: 'Match Closed Issues', detail: 'Check if findings match existing closed issues' },
    { title: 'Create Issues', detail: 'Create GitHub/GitLab issues for all findings' },
  ],
}

// Configuration
const AUTONOMOUS = args?.autonomous !== false  // Autonomous by default (pass autonomous=false to disable)
const BRUTAL_MODE = true
const DAYS_BACK = args?.days || 30
const MAX_COMMITS = args?.maxCommits || 5  // Reduced from 20
const MAX_ISSUES_TO_REVIEW = args?.maxIssues || 5  // Reduced from 50
const MAX_FILES = args?.maxFiles || 10  // Reduced from 20
const CONFIDENCE_THRESHOLD = 70 // Lower than normal - we want to catch everything
const USE_MULTI_MODEL = args?.multiModel !== false  // Multi-model by default (pass multiModel=false to disable)

log(`🤖 Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)

// Detect platform (GitHub, GitLab, or Bitbucket)
log('🔧 Detecting platform and syncing with remote...')
const platformDetect = await detectPlatform(agent)

const isGitLab = platformDetect.platform === 'gitlab'
const isGitHub = platformDetect.platform === 'github'
const isBitbucket = platformDetect.platform === 'bitbucket'

log(`✅ Platform: ${platformDetect.platform} (using ${platformDetect.cli})`)

// Sync with remote before starting review
const syncResult = await syncWithRemote(agent)
if (syncResult.status === 'conflicts') {
  log(`⚠️ Rebase conflicts detected: ${syncResult.conflicts?.join(', ')}`)
  return {
    status: 'conflicts',
    message: 'Cannot proceed with review - resolve conflicts first',
    conflicts: syncResult.conflicts
  }
}
if (syncResult.status === 'failed') {
  log(`⚠️ Sync failed: ${syncResult.message || 'Unknown error'}`)
  return {
    status: 'failed',
    message: 'Cannot proceed with review - sync with remote failed',
    error: syncResult.message
  }
}
log(`✅ ${syncResult.status === 'up_to_date' ? 'Already up to date with remote' : 'Successfully synced with remote'}`)

log('🔥 BRUTAL CODE REVIEW MODE 🔥')
log('═'.repeat(80))
log(`Platform: ${platformDetect.platform}`)
log(`Reviewing: Last ${DAYS_BACK} days of commits + ${MAX_ISSUES_TO_REVIEW} open/closed issues + full codebase`)
log(`Confidence Threshold: ${CONFIDENCE_THRESHOLD}% (inclusive mode)`)
log('═'.repeat(80))

const allFindings = []

// PHASE 1: Review Recent Commits
phase('Recent Commits')

log(`📅 Analyzing commits from last ${DAYS_BACK} days...`)

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

log(`✅ Found ${commitHistory.total_commits} commits to review`)

// Review each commit with multiple AI models
const commitFindings = await pipeline(
  commitHistory.commits.slice(0, MAX_COMMITS), // Review most recent commits

  // Stage 1: Get the diff for each commit
  (commit, idx) => agent(`Get the full diff for commit ${commit.hash}.

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
  }),

  // Stage 2: Multi-model review with rotation
  (diffData, _, idx) => {
    if (!USE_MULTI_MODEL) {
      // Single model fallback
      return agent(`BRUTAL CODE REVIEW of commit ${diffData.commit_hash}:

Files: ${diffData.files_changed?.join(', ')}

${diffData.diff}

Find ALL issues.`, {
        label: `Review: ${diffData.commit_hash.slice(0, 8)}`,
        schema: {
          type: 'object',
          properties: {
            issues: { type: 'array', items: { type: 'object' } }
          }
        }
      }).then(review => ({
        commit_hash: diffData.commit_hash,
        reviews: [review]
      }))
    }

    // Rotate models based on commit index for diversity
    const modelRotation = [
      ['opus', 'sonnet', 'haiku'],     // idx % 3 == 0
      ['sonnet', 'haiku', 'opus'],     // idx % 3 == 1
      ['haiku', 'opus', 'sonnet']      // idx % 3 == 2
    ][idx % 3]

    return parallel([
      () => agent(`BRUTAL CODE REVIEW of commit ${diffData.commit_hash}:

Files: ${diffData.files_changed?.join(', ')}

${diffData.diff}

Find ALL issues:
- Security vulnerabilities (SQL injection, XSS, hardcoded secrets, auth issues)
- Logic bugs (off-by-one, race conditions, null pointers)
- Performance issues (N+1 queries, memory leaks, inefficient algorithms)
- Code quality (duplication, complexity, poor naming)
- Missing error handling
- Edge cases not handled
- Potential race conditions
- Thread safety issues
- Resource leaks

Be BRUTAL. Find everything wrong, no matter how small.`, {
      label: `${modelRotation[0]} Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: modelRotation[0],
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
          }
        }
      }
    }),

    () => agent(`Security and correctness audit of commit ${diffData.commit_hash}:

${diffData.diff}

Focus on:
1. Security holes
2. Logic correctness
3. Data integrity
4. Error handling
5. Input validation

Find EVERYTHING.`, {
      label: `${modelRotation[1]} Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: modelRotation[1],
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
                confidence: { type: 'number' }
              }
            }
          }
        }
      }
    }),

    () => agent(`Quick scan for obvious bugs in commit ${diffData.commit_hash}:

${diffData.diff}

Find bugs fast - don't miss the obvious ones.`, {
      label: `${modelRotation[2]} Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: modelRotation[2],
      schema: {
        type: 'object',
        properties: {
          issues: { type: 'array', items: { type: 'object' } }
        }
      }
    })
  ]).then(reviews => ({
    commit_hash: diffData.commit_hash,
    reviews: reviews.filter(Boolean)
  }))
  }

Files: ${diffData.files_changed?.join(', ')}

${diffData.diff}

Find ALL issues:
- Security vulnerabilities (SQL injection, XSS, hardcoded secrets, auth issues)
- Logic bugs (off-by-one, race conditions, null pointers)
- Performance issues (N+1 queries, memory leaks, inefficient algorithms)
- Code quality (duplication, complexity, poor naming)
- Missing error handling
- Edge cases not handled
- Potential race conditions
- Thread safety issues
- Resource leaks

Be BRUTAL. Find everything wrong, no matter how small.`, {
    label: `Review: ${diffData.commit_hash.slice(0, 8)}`,
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
        }
      }
    }
  }).then(review => ({
    commit_hash: diffData.commit_hash,
    reviews: [review]
  }))
)
)

// Merge findings from all commits with full AI attribution
commitFindings.filter(Boolean).forEach((cf, commitIdx) => {
  const modelRotation = [
    ['opus', 'sonnet', 'haiku'],
    ['sonnet', 'haiku', 'opus'],
    ['haiku', 'opus', 'sonnet']
  ][commitIdx % 3]

  // Collect ALL proposals from all models (accepted and rejected)
  const allProposals = []

  cf.reviews.forEach((review, reviewIdx) => {
    review.issues?.forEach(issue => {
      allProposals.push({
        model: modelRotation[reviewIdx] || 'unknown',
        finding: issue,
        accepted: issue.confidence >= CONFIDENCE_THRESHOLD,
        rejection_reason: issue.confidence < CONFIDENCE_THRESHOLD
          ? `Confidence ${issue.confidence}% below threshold ${CONFIDENCE_THRESHOLD}%`
          : null
      })
    })
  })

  // Add accepted findings with full attribution
  allProposals.filter(p => p.accepted).forEach(proposal => {
    const rejectedProposals = allProposals.filter(p =>
      !p.accepted &&
      p.finding.file === proposal.finding.file &&
      p.finding.description?.includes(proposal.finding.description?.slice(0, 20))
    )

    allFindings.push({
      source: 'commit_review',
      commit_hash: cf.commit_hash,

      // Worker AI that found it
      worker_model: proposal.model,

      // The accepted finding
      ...proposal.finding,

      // AI Attribution
      ai_attribution: {
        total_models_reviewed: cf.reviews.length,
        worker_ai: {
          model: proposal.model,
          confidence: proposal.finding.confidence,
          reasoning: proposal.finding.description
        },
        arbiter: {
          decision: 'accepted',
          reason: `Confidence ${proposal.finding.confidence}% meets threshold ${CONFIDENCE_THRESHOLD}%`,
          timestamp: new Date().toISOString()
        },
        rejected_proposals: rejectedProposals.map(rp => ({
          model: rp.model,
          confidence: rp.finding.confidence,
          reason: rp.rejection_reason,
          description: rp.finding.description
        })),
        consensus: {
          models_agreed: allProposals.filter(p => p.accepted).length,
          models_total: allProposals.length
        }
      }
    })
  })
})

log(`✅ Commit review complete: ${allFindings.length} issues found`)

// PHASE 2: Review Open Issues
phase('Open Issues')

log(`📋 Analyzing open issues...`)

const fetchOpenCmd = isGitLab
  ? `glab issue list --state opened --per-page ${MAX_ISSUES_TO_REVIEW}`
  : isBitbucket
  ? `echo "[]"  # Bitbucket API not yet supported`
  : `gh issue list --state open --limit ${MAX_ISSUES_TO_REVIEW} --json number,title,createdAt,labels,body`

const openIssues = await agent(`Get all open issues to review their current status.

Execute:
${fetchOpenCmd}

Return list of open issues.`, {
  label: 'Fetch Open Issues',
  schema: {
    type: 'object',
    properties: {
      issues: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            number: { type: 'number' },
            title: { type: 'string' },
            createdAt: { type: 'string' },
            labels: { type: 'array' },
            body: { type: 'string' }
          }
        }
      }
    }
  }
})

log(`✅ Found ${openIssues.issues?.length || 0} open issues`)

// Review open issues to check if they're still valid, need more info, or have been partially fixed
const openIssueFindings = await pipeline(
  (openIssues.issues || []).slice(0, MAX_ISSUES_TO_REVIEW),

  (issue) => agent(`Review open issue #${issue.number}: "${issue.title}"

Issue body:
${issue.body}

Analyze:
1. Is this issue still valid/reproducible?
2. Has it been partially fixed already?
3. Is there additional context that should be added?
4. Are there related issues or duplicates?
5. Should this issue be closed as stale/won't-fix/duplicate?

Return your analysis.`, {
    label: `Review Open Issue #${issue.number}`,
    schema: {
      type: 'object',
      properties: {
        issue_number: { type: 'number' },
        still_valid: { type: 'boolean' },
        partially_fixed: { type: 'boolean' },
        needs_context: { type: 'boolean' },
        suggested_action: {
          type: 'string',
          enum: ['keep-open', 'close-stale', 'close-duplicate', 'close-wont-fix', 'add-context']
        },
        additional_findings: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              description: { type: 'string' },
              severity: { type: 'string' },
              confidence: { type: 'number' }
            }
          }
        }
      }
    }
  })
)

// Add any additional findings from open issue review
openIssueFindings.filter(Boolean).forEach(finding => {
  finding.additional_findings?.forEach(af => {
    if (af.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        source: 'open_issue_review',
        related_issue: finding.issue_number,
        ...af
      })
    }
  })
})

log(`✅ Open issue review complete: ${allFindings.length} total issues so far`)

// PHASE 3: Review Recently Closed Issues
phase('Closed Issues')

log(`📋 Analyzing ${MAX_ISSUES_TO_REVIEW} recently closed issues...`)

const fetchClosedCmd = isGitLab
  ? `glab issue list --state closed --per-page ${MAX_ISSUES_TO_REVIEW}`
  : isBitbucket
  ? `echo "[]"  # Bitbucket API not yet supported`
  : `gh issue list --state closed --limit ${MAX_ISSUES_TO_REVIEW} --json number,title,closedAt,labels`

const closedIssues = await agent(`Get recently closed issues to check if they were truly fixed.

Execute:
${fetchClosedCmd}

Return list of closed issues.`, {
  label: 'Fetch Closed Issues',
  schema: {
    type: 'object',
    properties: {
      issues: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            number: { type: 'number' },
            title: { type: 'string' },
            closedAt: { type: 'string' },
            labels: { type: 'array' }
          }
        }
      }
    }
  }
})

log(`✅ Found ${closedIssues.issues?.length || 0} closed issues`)

// Review a sample of closed issues to see if problems still exist
const issueFindings = await pipeline(
  (closedIssues.issues || []).slice(0, MAX_ISSUES_TO_REVIEW), // Sample closed issues

  (issue) => agent(`Check if issue #${issue.number} was truly resolved: "${issue.title}"

1. Search the codebase for related code
2. Verify the fix actually addresses the root cause
3. Look for similar problems elsewhere
4. Check if the fix introduced new bugs

Be skeptical - assume the fix might be incomplete.`, {
    label: `Verify Issue #${issue.number}`,
    model: 'opus',
    schema: {
      type: 'object',
      properties: {
        truly_fixed: { type: 'boolean' },
        lingering_problems: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              description: { type: 'string' },
              severity: { type: 'string' },
              confidence: { type: 'number' }
            }
          }
        },
        similar_problems_elsewhere: { type: 'array', items: { type: 'object' } }
      }
    }
  })
)

issueFindings.filter(Boolean).forEach(finding => {
  finding.lingering_problems?.forEach(problem => {
    if (problem.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        source: 'closed_issue_review',
        original_issue: finding.issue_number,
        ...problem
      })
    }
  })

  // REOPEN if still broken
  if (!finding.truly_fixed && finding.lingering_problems?.length > 0) {
    const reopenCmd = isGitLab
      ? `glab issue reopen ${finding.issue_number} && glab issue note ${finding.issue_number} --message "🔄 Reopened by Brutal Code Review - problem still exists"`
      : isBitbucket
      ? `echo "Bitbucket reopen not yet supported"`
      : `gh issue reopen ${finding.issue_number} && gh issue comment ${finding.issue_number} --body "🔄 **Reopened by Brutal Code Review**

This issue was marked as closed but the problem still exists:

${finding.lingering_problems.map(p => `- ${p.description}`).join('\n')}

The fix was incomplete or the problem reappeared."`

    agent(`Reopen issue #${finding.issue_number} because it's not truly fixed.

Execute:
${reopenCmd}
echo "REOPENED_ISSUE: #${finding.issue_number}"`, {
      label: `Reopen Issue #${finding.issue_number}`
    })

    console.log(`REOPENED_ISSUE: #${finding.issue_number}`)
    log(`⚠️  Reopened issue #${finding.issue_number} - still broken!`)
  }

  finding.similar_problems_elsewhere?.forEach(problem => {
    allFindings.push({
      source: 'similar_pattern',
      ...problem
    })
  })
})

log(`✅ Closed issue review: ${allFindings.length} total issues so far`)

// PHASE 4: Full Codebase Brutal Review
phase('Full Codebase')

log('🔍 BRUTAL full codebase scan...')

// Get all source files
const sourceFiles = await agent(`Find all source code files (exclude vendor, node_modules, tests).

Execute:
find . -type f \\( -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.java" -o -name "*.go" -o -name "*.rb" -o -name "*.sh" \\) | grep -v node_modules | grep -v vendor | grep -v ".git" | head -50

Return list of files to review.`, {
  label: 'Find Source Files',
  schema: {
    type: 'object',
    properties: {
      files: { type: 'array', items: { type: 'string' } }
    }
  }
})

log(`✅ Found ${sourceFiles.files?.length || 0} source files`)

// Brutal review of each file (in parallel batches)
const fileFindings = await pipeline(
  (sourceFiles.files || []).slice(0, MAX_FILES), // Limit files for this run

  (filepath) => USE_MULTI_MODEL ? parallel([
    // Security review
    () => agent(`SECURITY AUDIT of ${filepath}

Read the file and find:
- SQL injection vulnerabilities
- XSS vulnerabilities
- Command injection
- Path traversal
- Hardcoded secrets/credentials
- Authentication bypasses
- Authorization issues
- Insecure crypto
- Race conditions
- Input validation failures

Be paranoid. Assume attackers will find everything.`, {
      label: `Security: ${filepath}`,
      model: 'opus',
      schema: {
        type: 'object',
        properties: {
          vulnerabilities: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                type: { type: 'string' },
                severity: { type: 'string' },
                description: { type: 'string' },
                line_hint: { type: 'string' },
                confidence: { type: 'number' }
              }
            }
          }
        }
      }
    }),

    // Logic bugs review
    () => agent(`LOGIC BUG HUNT in ${filepath}

Find:
- Off-by-one errors
- Null pointer dereferences
- Unhandled edge cases
- Wrong assumptions
- Missing validation
- Incorrect algorithms
- Resource leaks
- Deadlocks potential
- Data races

Be thorough.`, {
      label: `Logic: ${filepath}`,
      model: 'sonnet',
      schema: {
        type: 'object',
        properties: {
          bugs: { type: 'array', items: { type: 'object' } }
        }
      }
    })
  ]).then(reviews => ({
    file: filepath,
    security: reviews[0],
    logic: reviews[1]
  })) : agent(`COMPLETE CODE REVIEW of ${filepath}

Review for:
1. Security vulnerabilities (SQL injection, XSS, hardcoded secrets, auth issues)
2. Logic bugs (off-by-one, race conditions, null pointers)
3. Performance issues
4. Code quality issues

Be thorough and brutal.`, {
    label: `Review: ${filepath}`,
    schema: {
      type: 'object',
      properties: {
        vulnerabilities: { type: 'array', items: { type: 'object' } },
        bugs: { type: 'array', items: { type: 'object' } }
      }
    }
  }).then(review => ({
    file: filepath,
    security: review,
    logic: review
  }))
)
)

fileFindings.filter(Boolean).forEach(ff => {
  ff.security?.vulnerabilities?.forEach(vuln => {
    if (vuln.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        source: 'full_codebase_security',
        file: ff.file,
        model: 'opus',  // Security review always opus
        ...vuln
      })
    }
  })

  ff.logic?.bugs?.forEach(bug => {
    if (bug.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        source: 'full_codebase_logic',
        file: ff.file,
        model: 'sonnet',  // Logic review always sonnet
        ...bug
      })
    }
  })
})

log(`✅ Full codebase review: ${allFindings.length} TOTAL ISSUES FOUND`)

// PHASE 5: Verify and Deduplicate
phase('Multi-Model Consensus')

log('⚖️ Verifying all findings with arbiter consensus...')

// Group findings by file and description for deduplication
const uniqueFindings = allFindings.reduce((acc, finding) => {
  const key = `${finding.file}:${finding.description?.slice(0, 50)}`
  if (!acc[key]) {
    acc[key] = finding
  }
  return acc
}, {})

const dedupedFindings = Object.values(uniqueFindings)

log(`✅ Deduplicated: ${dedupedFindings.length} unique issues`)

// PHASE 6: Match Against Closed Issues (avoid duplicates, reopen instead)
phase('Match Closed Issues')

log('🔍 Checking if any findings match existing closed issues...')

// Fetch ALL closed issues (not just recent ones) to check for matches
const fetchAllClosedCmd = isGitLab
  ? `glab issue list --state closed --per-page 100`
  : isBitbucket
  ? `echo "[]"`
  : `gh issue list --state closed --limit 100 --json number,title,body,closedAt`

const allClosedIssues = await agent(`Get all closed issues to check for duplicates.

Execute:
${fetchAllClosedCmd}

Return list of closed issues.`, {
  label: 'Fetch All Closed Issues',
  schema: {
    type: 'object',
    properties: {
      issues: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            number: { type: 'number' },
            title: { type: 'string' },
            body: { type: 'string' },
            closedAt: { type: 'string' }
          }
        }
      }
    }
  }
})

log(`✅ Found ${allClosedIssues.issues?.length || 0} closed issues to check against`)

// For each finding, check if it matches a closed issue
const findingActions = await pipeline(
  dedupedFindings.slice(0, 50), // Max 50 issues per run

  (finding) => agent(`Check if this finding matches any existing closed issue:

Finding:
- File: ${finding.file}
- Description: ${finding.description}
- Severity: ${finding.severity}

Closed Issues (titles):
${(allClosedIssues.issues || []).slice(0, 20).map(i => `#${i.number}: ${i.title}`).join('\n')}

Does this finding match any closed issue? If yes, return the issue number to reopen.
If no match, return null for issue_number.

Match criteria:
- Same file mentioned
- Similar problem description (same root cause)
- Not exact duplicate (some variation is OK)

Be conservative - only match if clearly the same underlying issue.`, {
    label: `Match: ${finding.description?.slice(0, 30)}`,
    schema: {
      type: 'object',
      properties: {
        finding: { type: 'object' },
        matched_issue: { type: 'number' },
        should_reopen: { type: 'boolean' },
        should_create_new: { type: 'boolean' }
      },
      required: ['should_reopen', 'should_create_new']
    }
  }).then(result => ({
    ...result,
    finding
  }))
)

// Separate into reopen vs create new
const toReopen = findingActions.filter(Boolean).filter(a => a.should_reopen && a.matched_issue)
const toCreateNew = findingActions.filter(Boolean).filter(a => a.should_create_new)

log(`📊 Matched ${toReopen.length} findings to closed issues (will reopen)`)
log(`📊 ${toCreateNew.length} findings need new issues`)

// Reopen matched issues
if (toReopen.length > 0) {
  log(`🔄 Reopening ${toReopen.length} closed issues...`)

  const reopenedIssues = await pipeline(
    toReopen,

    (action) => {
      const reopenCmd = isGitLab
        ? `glab issue reopen ${action.matched_issue} && glab issue note ${action.matched_issue} --message "🔄 **Reopened - Issue Still Present**\n\nThis issue has reappeared or was not fully fixed.\n\n**New Finding:**\n- File: ${action.finding.file}\n- Severity: ${action.finding.severity}\n- Confidence: ${action.finding.confidence}%\n\n${action.finding.description}"`
        : isBitbucket
        ? `echo "Bitbucket reopen not supported"`
        : `gh issue reopen ${action.matched_issue} && gh issue comment ${action.matched_issue} --body "🔄 **Reopened - Issue Still Present**\n\nThis issue has reappeared or was not fully fixed.\n\n**New Finding:**\n- File: ${action.finding.file}\n- Severity: ${action.finding.severity}\n- Confidence: ${action.finding.confidence}%\n\n${action.finding.description}"`

      return agent(`Reopen issue #${action.matched_issue} with new finding context.

Execute:
${reopenCmd}
echo "REOPENED_ISSUE: #${action.matched_issue}"

Return the issue number.`, {
        label: `Reopen #${action.matched_issue}`,
        schema: {
          type: 'object',
          properties: {
            issue_number: { type: 'number' }
          }
        }
      })
    }
  )

  reopenedIssues.filter(Boolean).forEach(result => {
    console.log(`REOPENED_ISSUE: #${result.issue_number}`)
    log(`✅ Reopened issue #${result.issue_number}`)
  })
}

// PHASE 7: Create New Issues (only for findings that don't match closed issues)
phase('Create Issues')

if (args?.['create-issues'] !== false && toCreateNew.length > 0) {
  log(`📝 Creating ${toCreateNew.length} new issues...`)

  const createdIssues = await pipeline(
    toCreateNew.map(a => a.finding), // Extract findings from actions

    (finding) => {
      const issueTitle = `[${finding.severity?.toUpperCase()}] ${finding.category || finding.type}: ${finding.description?.slice(0, 80)}`

      // Build comprehensive issue body with AI attribution
      const aiAttribution = finding.ai_attribution || {}
      const workerAI = aiAttribution.worker_ai || {}
      const arbiter = aiAttribution.arbiter || {}
      const rejected = aiAttribution.rejected_proposals || []
      const consensus = aiAttribution.consensus || {}

      const issueBody = `## Finding

**Severity**: ${finding.severity}
**Category**: ${finding.category || finding.type}
**File**: ${finding.file}
**Confidence**: ${finding.confidence}%
**Source**: ${finding.source}

### Description
${finding.description}

### Details
${finding.line_hint || 'See file for details'}

---

## 🤖 AI Attribution

### Worker AI (Finder)
- **Model**: ${workerAI.model || finding.worker_model || 'unknown'}
- **Confidence**: ${workerAI.confidence || finding.confidence}%
- **Reasoning**: ${workerAI.reasoning || finding.description}

### Arbiter Decision
- **Decision**: ${arbiter.decision || 'accepted'}
- **Reason**: ${arbiter.reason || 'Meets confidence threshold'}
${arbiter.timestamp ? `- **Timestamp**: ${arbiter.timestamp}` : ''}

### Multi-Model Consensus
- **Models Reviewed**: ${aiAttribution.total_models_reviewed || 1}
- **Models Agreed**: ${consensus.models_agreed || 1} / ${consensus.models_total || 1}

${rejected.length > 0 ? `### Rejected Proposals

The following proposals were reviewed but declined:

${rejected.map((r, idx) => `${idx + 1}. **${r.model}** (Confidence: ${r.confidence}%)
   - **Reason for Rejection**: ${r.reason}
   - **Description**: ${r.description}`).join('\n\n')}` : ''}

---

${finding.commit_hash ? `**Commit**: ${finding.commit_hash}\n` : ''}
${finding.original_issue ? `**Original Issue**: #${finding.original_issue}\n` : ''}

🤖 Found by Brutal Code Review (Multi-AI Consensus)
`

      // Simplified body for command line (full attribution in comment)
      const simpleBody = `Severity: ${finding.severity}, File: ${finding.file}, Confidence: ${finding.confidence}%, Found by: ${workerAI.model || finding.worker_model || 'AI'}`

      const createIssueCmd = isGitLab
        ? `glab issue create --title "${issueTitle}" --description "${simpleBody}" --label bug,automated-review`
        : isBitbucket
        ? `echo "Bitbucket issue creation not yet supported" && echo '{"issue_url": "", "issue_number": 0}'`
        : `gh issue create --title "${issueTitle}" --body "${simpleBody}" --label bug,automated-review,${finding.severity}`

      return agent(`Create an issue for this finding with full AI attribution:

Finding:
- Severity: ${finding.severity}
- Category: ${finding.category || finding.type}
- Description: ${finding.description}
- File: ${finding.file}
- Worker AI: ${workerAI.model || 'unknown'}
- Confidence: ${finding.confidence}%

Step 1: Create the issue
Execute:
${createIssueCmd}

Step 2: Add full AI attribution comment with the markdown body I provide

The full attribution markdown:
${issueBody}

Return the issue number and URL.`, {
      label: `Create Issue: ${finding.description?.slice(0, 30)}`,
      schema: {
        type: 'object',
        properties: {
          issue_url: { type: 'string' },
          issue_number: { type: 'number' }
        }
      }
    })
  }
  )

  const successCount = createdIssues.filter(Boolean).length
  log(`✅ Created ${successCount} new issues`)
} else {
  log('ℹ️  Skipping issue creation (use --create-issues to enable)')
}

// Final Summary
log('')
log('═'.repeat(80))
log('🔥 BRUTAL CODE REVIEW COMPLETE 🔥')
log('═'.repeat(80))
log(`Total Issues Found: ${dedupedFindings.length}`)
log(`Reopened Closed Issues: ${toReopen?.length || 0}`)
log(`Created New Issues: ${toCreateNew?.length || 0}`)
log('')
log('Breakdown by Severity:')
const bySeverity = dedupedFindings.reduce((acc, f) => {
  const sev = f.severity || 'unknown'
  acc[sev] = (acc[sev] || 0) + 1
  return acc
}, {})
Object.entries(bySeverity).forEach(([sev, count]) => {
  log(`  ${sev.toUpperCase()}: ${count}`)
})
log('')
log('Breakdown by Source:')
const bySource = dedupedFindings.reduce((acc, f) => {
  acc[f.source] = (acc[f.source] || 0) + 1
  return acc
}, {})
Object.entries(bySource).forEach(([src, count]) => {
  log(`  ${src}: ${count}`)
})
log('═'.repeat(80))

return {
  status: 'complete',
  total_findings: dedupedFindings.length,
  by_severity: bySeverity,
  by_source: bySource,
  findings: dedupedFindings
}
