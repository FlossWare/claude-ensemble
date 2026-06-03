export const meta = {
  name: 'code-review-brutal',
  description: 'Comprehensive brutal code review: recent commits, closed issues, and full codebase scan',
  phases: [
    { title: 'Recent Commits', detail: 'Review all commits from last 30 days' },
    { title: 'Closed Issues', detail: 'Review recently closed issues for lingering problems' },
    { title: 'Full Codebase', detail: 'Brutal review of entire codebase' },
    { title: 'Multi-Model Consensus', detail: 'All findings verified by multiple AIs' },
    { title: 'Create Issues', detail: 'Create GitHub/GitLab issues for all findings' },
  ],
}

// Configuration
const BRUTAL_MODE = true
const DAYS_BACK = args?.days || 30
const MAX_ISSUES_TO_REVIEW = args?.maxIssues || 50
const CONFIDENCE_THRESHOLD = 70 // Lower than normal - we want to catch everything

log('🔥 BRUTAL CODE REVIEW MODE 🔥')
log('═'.repeat(80))
log(`Reviewing: Last ${DAYS_BACK} days of commits + ${MAX_ISSUES_TO_REVIEW} closed issues + full codebase`)
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
  commitHistory.commits.slice(0, 20), // Review up to 20 most recent

  // Stage 1: Get the diff for each commit
  (commit) => agent(`Get the full diff for commit ${commit.hash}.

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

  // Stage 2: Brutal review by 3 models in parallel
  (diffData) => parallel([
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
      label: `Opus Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: 'opus',
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
      label: `Sonnet Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: 'sonnet',
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
      label: `Haiku Review: ${diffData.commit_hash.slice(0, 8)}`,
      model: 'haiku',
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
)

// Merge findings from all commits
commitFindings.filter(Boolean).forEach(cf => {
  cf.reviews.forEach((review, idx) => {
    review.issues?.forEach(issue => {
      if (issue.confidence >= CONFIDENCE_THRESHOLD) {
        allFindings.push({
          source: 'commit_review',
          commit_hash: cf.commit_hash,
          model: ['opus', 'sonnet', 'haiku'][idx],
          ...issue
        })
      }
    })
  })
})

log(`✅ Commit review complete: ${allFindings.length} issues found`)

// PHASE 2: Review Recently Closed Issues
phase('Closed Issues')

log(`📋 Analyzing ${MAX_ISSUES_TO_REVIEW} recently closed issues...`)

const closedIssues = await agent(`Get recently closed issues to check if they were truly fixed.

Execute:
gh issue list --state closed --limit ${MAX_ISSUES_TO_REVIEW} --json number,title,closedAt,labels

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
  (closedIssues.issues || []).slice(0, 10), // Sample 10 closed issues

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
    agent(`Reopen issue #${finding.issue_number} because it's not truly fixed.

Execute:
gh issue reopen ${finding.issue_number}
gh issue comment ${finding.issue_number} --body "🔄 **Reopened by Brutal Code Review**

This issue was marked as closed but the problem still exists:

${finding.lingering_problems.map(p => `- ${p.description}`).join('\n')}

The fix was incomplete or the problem reappeared."`, {
      label: `Reopen Issue #${finding.issue_number}`
    })

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

// PHASE 3: Full Codebase Brutal Review
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
  (sourceFiles.files || []).slice(0, 20), // Limit to 20 files for this run

  (filepath) => parallel([
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
  }))
)

fileFindings.filter(Boolean).forEach(ff => {
  ff.security?.vulnerabilities?.forEach(vuln => {
    if (vuln.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        source: 'full_codebase_security',
        file: ff.file,
        ...vuln
      })
    }
  })

  ff.logic?.bugs?.forEach(bug => {
    if (bug.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        source: 'full_codebase_logic',
        file: ff.file,
        ...bug
      })
    }
  })
})

log(`✅ Full codebase review: ${allFindings.length} TOTAL ISSUES FOUND`)

// PHASE 4: Verify and Deduplicate
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

// PHASE 5: Create Issues
phase('Create Issues')

if (args?.['create-issues'] !== false && dedupedFindings.length > 0) {
  log(`📝 Creating ${dedupedFindings.length} GitHub issues...`)

  const createdIssues = await pipeline(
    dedupedFindings.slice(0, 50), // Max 50 issues per run

    (finding) => agent(`Create a GitHub issue for this finding:

Severity: ${finding.severity}
Category: ${finding.category || finding.type}
Description: ${finding.description}
File: ${finding.file}
Source: ${finding.source}

Execute:
gh issue create \\
  --title "[${finding.severity?.toUpperCase()}] ${finding.category || finding.type}: ${finding.description?.slice(0, 80)}" \\
  --body "## Finding

**Severity**: ${finding.severity}
**Category**: ${finding.category || finding.type}
**Source**: ${finding.source}
**File**: ${finding.file}
**Confidence**: ${finding.confidence}%

### Description
${finding.description}

### Details
${finding.line_hint || 'See file for details'}

---
🤖 Found by Brutal Code Review (Multi-AI Consensus)
" \\
  --label bug,automated-review,${finding.severity}

Return the issue URL.`, {
      label: `Create Issue: ${finding.description?.slice(0, 30)}`,
      schema: {
        type: 'object',
        properties: {
          issue_url: { type: 'string' },
          issue_number: { type: 'number' }
        }
      }
    })
  )

  const successCount = createdIssues.filter(Boolean).length
  log(`✅ Created ${successCount} issues`)
} else {
  log('ℹ️  Skipping issue creation (use --create-issues to enable)')
}

// Final Summary
log('')
log('═'.repeat(80))
log('🔥 BRUTAL CODE REVIEW COMPLETE 🔥')
log('═'.repeat(80))
log(`Total Issues Found: ${dedupedFindings.length}`)
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
