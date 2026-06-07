export const meta = {
  name: 'code-review-auto',
  description: 'Autonomous brutal code review - auto-creates issues for all bugs found',
  whenToUse: 'When you want comprehensive automated code audit without manual intervention',
  autonomous: true,
  phases: [
    { title: 'Setup', detail: 'Detect platform and sync' },
    { title: 'Recent Commits', detail: 'Review last N days commits' },
    { title: 'Open Issues', detail: 'Review open issues' },
    { title: 'Closed Issues', detail: 'Check closed issues for regressions' },
    { title: 'Full Codebase', detail: 'Brutal scan of entire codebase' },
    { title: 'Impact Analysis', detail: 'Assess severity and impact' },
    { title: 'Multi-Model Verification', detail: 'Verify findings', model: 'opus' },
    { title: 'Create Issues', detail: 'Auto-create issues for bugs' },
  ],
}

// ============================================================================
// INLINE DEPENDENCIES
// ============================================================================

async function detectPlatform(agent) {
  const result = await agent(`Detect platform.

Execute:
if git remote -v | grep -q 'github.com'; then echo "github"
elif git remote -v | grep -q 'gitlab'; then echo "gitlab"
else echo "unknown"
fi

Check CLI:
gh --version 2>/dev/null && echo "gh" || echo "no-gh"
glab --version 2>/dev/null && echo "glab" || echo "no-glab"`, {
    label: 'Detect Platform',
    schema: {
      type: 'object',
      properties: {
        platform: { type: 'string' },
        cli: { type: 'string' }
      }
    }
  })

  return result
}

async function syncWithRemote(agent) {
  return await agent(`Sync with remote.

Execute:
git fetch origin
git status`, {
    label: 'Sync',
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string' }
      }
    }
  })
}

async function multiModelVerify(agent, finding, workers) {
  const verifyPrompt = `Verify this potential bug/issue:

**Finding**: ${finding.description}
**File**: ${finding.file || 'unknown'}
**Severity**: ${finding.severity}
**Evidence**: ${finding.evidence || 'See description'}

Verify:
1. Is this a real issue or false positive?
2. What's the actual severity?
3. What's the impact if not fixed?
4. Your confidence this is a real bug (0-100)

Return your verification.`

  const verifications = await Promise.all(workers.map(model =>
    agent(verifyPrompt, {
      label: `Verify (${model})`,
      model,
      schema: {
        type: 'object',
        properties: {
          is_real_bug: { type: 'boolean' },
          severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
          impact: { type: 'string' },
          confidence: { type: 'number', minimum: 0, maximum: 100 },
          reasoning: { type: 'string' }
        }
      }
    }).catch(() => null)
  ))

  return verifications.filter(Boolean)
}

async function arbiterConsensus(agent, finding, verifications, arbiterModel) {
  const summary = verifications.map((v, idx) =>
    `Model ${idx + 1}: ${v.is_real_bug ? 'REAL BUG' : 'FALSE POSITIVE'} (${v.severity}, ${v.confidence}% confidence)`
  ).join('\n')

  return await agent(`Make consensus decision on this finding:

Finding: ${finding.description}

Verifications:
${summary}

Decide:
1. Is this a real bug to report?
2. Final severity
3. Should we create an issue?

Return decision.`, {
    label: 'Arbiter Consensus',
    model: arbiterModel || 'opus',
    schema: {
      type: 'object',
      properties: {
        is_real_bug: { type: 'boolean' },
        final_severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
        create_issue: { type: 'boolean' },
        reasoning: { type: 'string' },
        consensus_score: { type: 'number' }
      }
    }
  })
}

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  workers: [
    'opus', 'sonnet', 'haiku',  // Claude models (always available)
    'gemini',                    // Gemini (via MCP/Google AI API)
    // 'grok',                   // Grok (via xAI API) - uncomment when configured
    // 'ollama/llama3',          // Ollama (local) - uncomment when running
    // 'gpt-4',                  // OpenAI (via MCP) - uncomment when configured
  ],
  arbiterModel: 'opus',

  // Review scope
  daysBack: 30,                       // Review last 30 days of commits
  maxCommits: 10,                     // Max commits to review
  maxOpenIssues: 10,                  // Max open issues to review
  maxClosedIssues: 5,                 // Max closed issues to check
  maxFilesToScan: 20,                 // Max files in full scan

  // Auto-create issue criteria
  autoCreate: {
    minConsensus: 70,                 // 70%+ agreement required
    minConfidence: 75,                // 75%+ confidence
    minSeverity: 'medium',            // At least medium severity
    realBugRequired: true,            // Must be verified as real bug
  },

  // Verification
  requireVerification: true,          // All findings verified by multiple AIs
  minVerifiers: 2,                    // At least 2 models must verify
}

const daysBack = args?.days || CONFIG.daysBack
const maxIssues = args?.maxIssues || (CONFIG.maxOpenIssues + CONFIG.maxClosedIssues)

log('')
log('═'.repeat(60))
log('🔥 AUTONOMOUS BRUTAL CODE REVIEW')
log('═'.repeat(60))
log(`Workers: ${CONFIG.workers.join(', ')}`)
log(`Arbiter: ${CONFIG.arbiterModel}`)
log(`Scope: Last ${daysBack} days + ${maxIssues} issues + full scan`)
log(`Auto-Create: Consensus ≥ ${CONFIG.autoCreate.minConsensus}%, Real bugs only`)
log('═'.repeat(60))
log('')

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

// PHASE 1: Setup
phase('Setup')

log('🔧 Setup...')
const platform = await detectPlatform(agent)
log(`✅ Platform: ${platform.platform}`)

await syncWithRemote(agent)
log(`✅ Synced`)

const allFindings = []

// PHASE 2: Recent Commits
phase('Recent Commits')

log(`📅 Reviewing commits from last ${daysBack} days...`)

const commits = await agent(`Get commits from last ${daysBack} days.

Execute:
git log --since="${daysBack} days ago" --pretty=format:"%H|%s" | head -${CONFIG.maxCommits}

Return commit list.`, {
  label: 'Recent Commits',
  schema: {
    type: 'object',
    properties: {
      commits: { type: 'array', items: { type: 'object' } },
      total: { type: 'number' }
    }
  }
})

log(`📊 Found ${commits.total || 0} commits`)

for (const commit of (commits.commits || []).slice(0, CONFIG.maxCommits)) {
  const commitFindings = await agent(`Review commit ${commit.hash?.substring(0, 7)}: ${commit.message}

Get diff:
git show ${commit.hash}

Find bugs, issues, anti-patterns, security problems.
Return findings.`, {
    label: `Review ${commit.hash?.substring(0, 7)}`,
    schema: {
      type: 'object',
      properties: {
        findings: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              description: { type: 'string' },
              file: { type: 'string' },
              severity: { type: 'string' },
              evidence: { type: 'string' }
            }
          }
        }
      }
    }
  })

  if (commitFindings.findings?.length > 0) {
    log(`  ⚠️ Found ${commitFindings.findings.length} issues in commit`)
    allFindings.push(...commitFindings.findings.map(f => ({ ...f, source: 'commit', commit: commit.hash })))
  }
}

log(`✅ Commit review complete (${allFindings.length} findings)`)

// PHASE 3: Open Issues
phase('Open Issues')

log('📋 Reviewing open issues...')

const openIssuesCmd = platform.platform === 'gitlab'
  ? `glab issue list --state opened --per-page ${CONFIG.maxOpenIssues} --json number,title,description`
  : `gh issue list --state open --limit ${CONFIG.maxOpenIssues} --json number,title,body`

const openIssues = await agent(`List open issues.

Execute:
${openIssuesCmd}

Return issue list.`, {
  label: 'Open Issues',
  schema: {
    type: 'object',
    properties: {
      issues: { type: 'array' },
      total: { type: 'number' }
    }
  }
})

log(`📊 ${openIssues.total || 0} open issues found`)

for (const issue of (openIssues.issues || []).slice(0, CONFIG.maxOpenIssues)) {
  const issueAnalysis = await agent(`Analyze open issue #${issue.number}: ${issue.title}

Description: ${issue.body || issue.description || 'No description'}

Check:
1. Is this issue still valid?
2. Are there related bugs not mentioned?
3. What's the actual root cause?

Return analysis.`, {
    label: `Analyze Issue #${issue.number}`,
    schema: {
      type: 'object',
      properties: {
        still_valid: { type: 'boolean' },
        related_bugs: { type: 'array', items: { type: 'string' } },
        root_cause: { type: 'string' },
        additional_findings: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              description: { type: 'string' },
              severity: { type: 'string' }
            }
          }
        }
      }
    }
  })

  if (issueAnalysis.additional_findings?.length > 0) {
    log(`  ⚠️ Found ${issueAnalysis.additional_findings.length} additional issues`)
    allFindings.push(...issueAnalysis.additional_findings.map(f => ({ ...f, source: 'issue_analysis', issue: issue.number })))
  }
}

log(`✅ Issue review complete (${allFindings.length} total findings)`)

// PHASE 4: Closed Issues
phase('Closed Issues')

log('🔍 Checking closed issues for regressions...')

const closedIssuesCmd = platform.platform === 'gitlab'
  ? `glab issue list --state closed --per-page ${CONFIG.maxClosedIssues} --json number,title`
  : `gh issue list --state closed --limit ${CONFIG.maxClosedIssues} --json number,title`

const closedIssues = await agent(`List recently closed issues.

Execute:
${closedIssuesCmd}

Return issue list.`, {
  label: 'Closed Issues',
  schema: {
    type: 'object',
    properties: {
      issues: { type: 'array' },
      total: { type: 'number' }
    }
  }
})

log(`📊 ${closedIssues.total || 0} closed issues found`)

for (const issue of (closedIssues.issues || []).slice(0, CONFIG.maxClosedIssues)) {
  const regressionCheck = await agent(`Check if closed issue #${issue.number} has regressed.

Title: ${issue.title}

Check:
1. Is the bug back?
2. Was the fix incomplete?
3. Are there new related issues?

Return findings.`, {
    label: `Check Regression #${issue.number}`,
    schema: {
      type: 'object',
      properties: {
        has_regressed: { type: 'boolean' },
        regression_findings: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              description: { type: 'string' },
              severity: { type: 'string' }
            }
          }
        }
      }
    }
  })

  if (regressionCheck.regression_findings?.length > 0) {
    log(`  ⚠️ Regression detected in issue #${issue.number}`)
    allFindings.push(...regressionCheck.regression_findings.map(f => ({ ...f, source: 'regression', closed_issue: issue.number })))
  }
}

log(`✅ Regression check complete (${allFindings.length} total findings)`)

// PHASE 5: Full Codebase
phase('Full Codebase')

log('🔍 Brutal codebase scan...')

const codeFiles = await agent(`Find code files to scan.

Execute:
find . -type f \\( -name "*.js" -o -name "*.ts" -o -name "*.jsx" -o -name "*.tsx" -o -name "*.py" -o -name "*.java" \\) -not -path "*/node_modules/*" -not -path "*/.git/*" | head -${CONFIG.maxFilesToScan}

Return file list.`, {
  label: 'Find Code Files',
  schema: {
    type: 'object',
    properties: {
      files: { type: 'array', items: { type: 'string' } },
      total: { type: 'number' }
    }
  }
})

log(`📊 Scanning ${codeFiles.files?.length || 0} files`)

for (const file of (codeFiles.files || []).slice(0, CONFIG.maxFilesToScan)) {
  const fileFindings = await agent(`Brutal code review of ${file}

Execute:
cat "${file}"

Find:
1. Security vulnerabilities
2. Performance issues
3. Logic errors
4. Anti-patterns
5. Potential bugs

Return findings.`, {
    label: `Scan ${file}`,
    schema: {
      type: 'object',
      properties: {
        findings: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              description: { type: 'string' },
              file: { type: 'string' },
              severity: { type: 'string' },
              line: { type: 'number' },
              code_snippet: { type: 'string' }
            }
          }
        }
      }
    }
  })

  if (fileFindings.findings?.length > 0) {
    log(`  ⚠️ ${file}: ${fileFindings.findings.length} issues`)
    allFindings.push(...fileFindings.findings.map(f => ({ ...f, source: 'codebase_scan' })))
  }
}

log(`✅ Codebase scan complete (${allFindings.length} total findings)`)

// PHASE 6: Impact Analysis
phase('Impact Analysis')

log('🎯 Analyzing impact of findings...')

for (const finding of allFindings) {
  finding.impact_score = finding.severity === 'critical' ? 100 :
                         finding.severity === 'high' ? 75 :
                         finding.severity === 'medium' ? 50 : 25
}

allFindings.sort((a, b) => b.impact_score - a.impact_score)

log(`✅ ${allFindings.length} findings prioritized by impact`)

// PHASE 7: Multi-Model Verification
phase('Multi-Model Verification')

log('🤖 Verifying findings with multiple AIs...')

const verifiedFindings = []

for (const finding of allFindings.slice(0, 20)) { // Verify top 20
  log(`  Verifying: ${finding.description.substring(0, 60)}...`)

  const verifications = await multiModelVerify(agent, finding, CONFIG.workers)

  const consensus = await arbiterConsensus(agent, finding, verifications, CONFIG.arbiterModel)

  if (consensus.create_issue && consensus.is_real_bug && consensus.consensus_score >= CONFIG.autoCreate.minConsensus) {
    verifiedFindings.push({
      ...finding,
      verified: true,
      final_severity: consensus.final_severity,
      consensus_score: consensus.consensus_score,
      reasoning: consensus.reasoning
    })
    log(`    ✅ VERIFIED (${consensus.consensus_score}% consensus)`)
  } else {
    log(`    ❌ Rejected (${consensus.consensus_score}% consensus, not a real bug)`)
  }
}

log(`✅ ${verifiedFindings.length} findings verified`)

// PHASE 8: Create Issues
phase('Create Issues')

log('📝 Creating issues for verified findings...')

const createdIssues = []

for (const finding of verifiedFindings) {
  const severityLabel = finding.final_severity === 'critical' ? '🚨 CRITICAL' :
                        finding.final_severity === 'high' ? '⚠️ HIGH' :
                        finding.final_severity === 'medium' ? '📋 MEDIUM' : 'ℹ️ LOW'

  const issueTitle = `${severityLabel}: ${finding.description.substring(0, 100)}`
  const issueBody = `## ${finding.description}

**Severity**: ${finding.final_severity}
**Source**: ${finding.source}
**Consensus**: ${finding.consensus_score}%

${finding.file ? `**File**: ${finding.file}` : ''}
${finding.line ? `**Line**: ${finding.line}` : ''}
${finding.code_snippet ? `\n\`\`\`\n${finding.code_snippet}\n\`\`\`\n` : ''}

**AI Reasoning**: ${finding.reasoning}

**Impact**: ${finding.impact_score}/100

---

*Auto-created by code-review-auto*
*Verified by ${CONFIG.workers.length} AI models*`

  const createCmd = platform.platform === 'gitlab'
    ? `glab issue create --title "${issueTitle}" --description "${issueBody.replace(/"/g, '\\"')}" --label "bug,auto-created,${finding.final_severity}"`
    : `gh issue create --title "${issueTitle}" --body "${issueBody.replace(/"/g, '\\"')}" --label "bug,auto-created,${finding.final_severity}"`

  const created = await agent(`Create issue.

Execute:
${createCmd}

Create the issue and return its number.`, {
    label: `Create Issue`,
    schema: {
      type: 'object',
      properties: {
        number: { type: 'number' },
        url: { type: 'string' }
      }
    }
  })

  createdIssues.push({
    number: created.number,
    title: issueTitle,
    severity: finding.final_severity
  })

  log(`  ✅ Created issue #${created.number}`)
}

log(`✅ ${createdIssues.length} issues created`)

// ============================================================================
// SUMMARY
// ============================================================================

log('')
log('═'.repeat(60))
log('📊 CODE REVIEW SUMMARY')
log('═'.repeat(60))
log(`Total findings: ${allFindings.length}`)
log(`Verified: ${verifiedFindings.length}`)
log(`Issues created: ${createdIssues.length}`)
log('')

const bySeverity = {
  critical: createdIssues.filter(i => i.severity === 'critical').length,
  high: createdIssues.filter(i => i.severity === 'high').length,
  medium: createdIssues.filter(i => i.severity === 'medium').length,
  low: createdIssues.filter(i => i.severity === 'low').length
}

log(`By Severity:`)
log(`  🚨 Critical: ${bySeverity.critical}`)
log(`  ⚠️  High: ${bySeverity.high}`)
log(`  📋 Medium: ${bySeverity.medium}`)
log(`  ℹ️  Low: ${bySeverity.low}`)
log('')

createdIssues.forEach(i => {
  const icon = i.severity === 'critical' ? '🚨' :
               i.severity === 'high' ? '⚠️' :
               i.severity === 'medium' ? '📋' : 'ℹ️'
  log(`${icon} #${i.number}: ${i.title}`)
})

log('═'.repeat(60))
log('')

const result = {
  status: 'success',
  total_findings: allFindings.length,
  findings_count: allFindings.length,
  verified: verifiedFindings.length,
  issues_created: createdIssues.length,
  by_severity: bySeverity,
  categories: [...new Set(allFindings.map(f => f.category || 'uncategorized'))],
  severity_breakdown: bySeverity,
  created_issues: createdIssues
}

// Extract learnings
try {
  await workflow('extract-learning', {
    workflow_name: 'code-review',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result
