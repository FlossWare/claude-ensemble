/**
 * @returns {{
 *   status: 'success' | 'complete' | 'conflicts',
 *   prs_reviewed?: number,
 *   approved?: number,
 *   rejected?: number,
 *   remaining?: number,
 *   breaking_changes?: number,
 *   failed?: number,
 *   results?: object[],
 *   message?: string
 * }}
 */
export const meta = {
  name: 'code-pr-review',
  description: 'Interactive PR review with multi-AI consensus - prompts before approve/reject',
  whenToUse: 'When you want to review PRs with AI consensus but manual approval',
  phases: [
    { title: 'Setup', detail: 'Detect platform and sync' },
    { title: 'Discover PRs', detail: 'Find open PRs needing review' },
    { title: 'Fetch PR', detail: 'Get PR details and diff' },
    { title: 'Impact Analysis', detail: 'Detect breaking changes' },
    { title: 'Multi-Model Review', detail: 'AI consensus review', model: 'opus' },
    { title: 'Arbiter Decision', detail: 'Final AI decision' },
    { title: 'User Confirmation', detail: 'User decides approve/reject' },
    { title: 'Post Results', detail: 'Comment and approve/reject' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// ============================================================================
// INLINE DEPENDENCIES (no imports - workflow compatibility)
// ============================================================================

// Inlined from shared/platform-detector.js
async function detectPlatform(agent) {
  const result = await agent(`Detect the repository platform and return details.

Execute these commands:
git remote get-url origin
which gh
which glab

Based on the remote URL and available CLIs, determine:
- Platform (github, gitlab, or bitbucket)
- CLI tool available (gh, glab, or bb)
- Repository owner/name

Return structured data.`, {
    label: 'Detect Platform',
    schema: {
      type: 'object',
      properties: {
        platform: { type: 'string', enum: ['github', 'gitlab', 'bitbucket', 'unknown'] },
        cli: { type: 'string', enum: ['gh', 'glab', 'bb', 'none'] },
        remote_url: { type: 'string' },
        repo_owner: { type: 'string' },
        repo_name: { type: 'string' },
      },
      required: ['platform', 'cli', 'remote_url'],
    }
  })

  return result
}

async function syncWithRemote(agent, options = {}) {
  const { branch = 'main' } = options

  const result = await agent(`Sync with remote repository.

Execute these commands:
git fetch origin
git rebase origin/${branch}

Return the status of the sync operation.
If there are conflicts, list them.`, {
    label: 'Sync with Remote',
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['success', 'conflicts', 'failed', 'up_to_date'] },
        message: { type: 'string' },
        conflicts: { type: 'array', items: { type: 'string' } },
        branch: { type: 'string' },
      },
      required: ['status'],
    }
  })

  return result
}

// Fetch PR details
async function fetchPR(agent, platform, prNumber) {
  const result = await agent(`Fetch PR #${prNumber} details.

Execute:
${platform.cli} pr view ${prNumber} --json number,title,author,body,headRefName,baseRefName,state

Return PR information.`, {
    label: `Fetch PR #${prNumber}`,
    schema: {
      type: 'object',
      properties: {
        number: { type: 'number' },
        title: { type: 'string' },
        author: { type: 'string' },
        body: { type: 'string' },
        head_branch: { type: 'string' },
        base_branch: { type: 'string' },
        state: { type: 'string' }
      }
    }
  })

  return result
}

// Post comment
async function postComment(agent, platform, type, number, comment) {
  await agent(`Post comment to ${type} #${number}.

Execute:
${platform.cli} ${type} comment ${number} --body "${comment.replace(/"/g, '\\"')}"

Post the comment.`, {
    label: `Comment on ${type} #${number}`
  })
}

// Simple impact analysis (inline version)
async function analyzeImpactSimple(agent, changedFiles, diff) {
  // Find what depends on changed files
  const grepCommands = changedFiles.slice(0, 10).map(f =>
    `grep -r "from ['\"].*${f.replace(/^.*\//, '')}['\"]" . --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx" 2>/dev/null | head -20`
  ).join('; echo "---"; ')

  const result = await agent(`Analyze impact of these changes on the codebase.

Changed files (${changedFiles.length}):
${changedFiles.slice(0, 20).join('\n')}

Diff excerpt:
${diff.substring(0, 2000)}

Find dependencies:
${grepCommands}

Analyze:
1. Are there breaking changes? (function signatures, removed exports, type changes)
2. How many files are impacted?
3. What's the risk level?
4. Are there missing tests?

Return structured impact assessment.`, {
    label: 'Impact Analysis',
    schema: {
      type: 'object',
      properties: {
        breaking_changes: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              entity: { type: 'string' },
              reason: { type: 'string' },
              severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] }
            }
          }
        },
        high_risk_changes: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              entity: { type: 'string' },
              reason: { type: 'string' }
            }
          }
        },
        impacted_files: { type: 'number' },
        missing_tests: { type: 'number' },
        risk_level: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] }
      }
    }
  })

  return result
}

// Multi-model review (simplified)
async function multiModelReview(agent, prompt, workers) {
  log(`🤖 Running ${workers.length}-model review...`)

  const reviews = await Promise.all(workers.map((model, idx) =>
    agent(prompt, {
      label: `Review (${model})`,
      model,
      phase: 'Multi-Model Review',
      schema: {
        type: 'object',
        properties: {
          quality_score: { type: 'number', minimum: 0, maximum: 100 },
          recommendation: { type: 'string', enum: ['approve', 'request_changes', 'comment'] },
          issues_found: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
                description: { type: 'string' },
                file: { type: 'string' }
              }
            }
          },
          strengths: { type: 'array', items: { type: 'string' } },
          improvements_needed: { type: 'array', items: { type: 'string' } },
          confidence: { type: 'number', minimum: 0, maximum: 100 }
        }
      }
    }).catch(err => {
      log(`⚠️ ${model} review failed: ${err.message}`)
      return null
    })
  ))

  const validReviews = reviews.filter(Boolean)

  return {
    reviews: validReviews,
    models: workers.filter((_, idx) => reviews[idx] !== null)
  }
}

// Arbiter decision
async function arbiterDecision(agent, prTitle, reviews, arbiterModel) {
  const reviewSummary = reviews.map((r, idx) =>
    `Model ${idx + 1}: ${r.recommendation} (score: ${r.quality_score}, confidence: ${r.confidence}%)`
  ).join('\n')

  const result = await agent(`Make final decision on PR: "${prTitle}"

Reviews from ${reviews.length} models:
${reviewSummary}

Analyze the reviews and make a consensus decision.
Consider:
- Overall quality scores
- Confidence levels
- Critical issues found
- Agreement among models

Return your final decision with reasoning.`, {
    label: 'Arbiter Decision',
    model: arbiterModel || 'fable',
    phase: 'Arbiter Decision',
    schema: {
      type: 'object',
      properties: {
        final_decision: { type: 'string', enum: ['approve', 'request_changes', 'comment'] },
        reasoning: { type: 'string' },
        consensus_score: { type: 'number', minimum: 0, maximum: 100 },
        key_concerns: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  return result
}

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  workers: [
    'fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini',
    // Gemini (via MCP/Google AI API)
    // 'grok',                   // Grok (via xAI API) - uncomment when configured
    // 'ollama/llama3',          // Ollama (local) - uncomment when running
    // 'gpt-4',                  // OpenAI (via MCP) - uncomment when configured
  ],
  arbiterModel: 'fable',

  // AUTO-APPROVAL CRITERIA (strict by default)
  autoApprove: {
    minQualityScore: 90,              // Must score 90+ to auto-approve
    minConsensus: 85,                 // 85%+ agreement required
    maxBreakingChanges: 0,            // NO breaking changes allowed
    maxHighRiskChanges: 2,            // Max 2 high-risk changes
    maxImpactedFiles: 50,             // Max 50 files impacted
    requireAllApprove: false,         // If true, ALL models must approve
  },

  // AUTO-REJECT CRITERIA
  autoReject: {
    hasBreakingChanges: true,         // Reject if breaking changes
    hasCriticalIssues: true,          // Reject if critical severity issues
    lowQualityScore: 60,              // Reject if quality < 60
    highRiskLevel: 'critical',        // Reject if risk = critical
  },

  // LOOP SETTINGS
  maxPRsPerRun: 10,                   // Review max 10 PRs per iteration
  stopWhenEmpty: true,                // Stop when no PRs left
}

// Parse args (allow override)
const maxPRs = args?.max || args?.['--max'] || CONFIG.maxPRsPerRun
const minQuality = args?.quality || args?.['--quality'] || CONFIG.autoApprove.minQualityScore

log('')
log('═'.repeat(60))
log('🤖 INTERACTIVE PR REVIEW BOT')
log('═'.repeat(60))
log(`Workers: ${CONFIG.workers.join(', ')}`)
log(`Arbiter: ${CONFIG.arbiterModel}`)
log(`Auto-Approve: Quality ≥ ${minQuality}, No breaking changes`)
log(`Auto-Reject: Breaking changes, Critical issues, Quality < ${CONFIG.autoReject.lowQualityScore}`)
log(`Max PRs/run: ${maxPRs}`)
log('═'.repeat(60))
log('')

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

// PHASE 1: Setup
phase('Setup')

log('🔧 Detecting platform...')
const platform = await detectPlatform(agent)
log(`✅ Platform: ${platform.platform} (${platform.cli})`)

log('🔄 Syncing with remote...')
const syncResult = await syncWithRemote(agent)
if (syncResult.status === 'conflicts') {
  log(`❌ Rebase conflicts detected: ${syncResult.conflicts.join(', ')}`)
  return { status: 'conflicts', message: 'Resolve conflicts first' }
}
log(`✅ ${syncResult.status === 'up_to_date' ? 'Up to date' : 'Synced'}`)

// PHASE 2: Discover PRs
phase('Discover PRs')

log('📋 Finding open PRs needing review...')

const prListResult = await agent(`List all open pull requests that need review.

Platform: ${platform.platform}
CLI: ${platform.cli}

Execute:
${platform.cli} pr list --json number,title,author,state --limit 100

Filter for:
1. Open PRs only
2. Not already reviewed by AI (check for "🤖 INTERACTIVE PR REVIEW" in comments)
3. Not draft PRs

Return list of PR numbers to review.`, {
  label: 'List Open PRs',
  schema: {
    type: 'object',
    properties: {
      prs: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            number: { type: 'number' },
            title: { type: 'string' },
            needs_review: { type: 'boolean' }
          }
        }
      },
      total_open: { type: 'number' },
      needs_review_count: { type: 'number' }
    }
  }
})

const prsToReview = prListResult.prs.filter(pr => pr.needs_review).map(pr => pr.number)

log(`📊 Found ${prListResult.total_open} open PRs, ${prsToReview.length} need review`)

if (prsToReview.length === 0) {
  log('✅ No PRs to review - all done!')
  return {
    status: 'complete',
    message: 'No PRs needing review',
    prs_reviewed: 0
  }
}

// Limit to maxPRs
const prsThisRun = prsToReview.slice(0, maxPRs)
log(`🎯 Reviewing ${prsThisRun.length} PRs this run`)
log('')

// ============================================================================
// REVIEW SINGLE PR FUNCTION (for parallel execution)
// ============================================================================

const reviewSinglePR = async (prNum, platform) => {
  log('')
  log('═'.repeat(60))
  log(`📝 PR #${prNum}`)
  log('═'.repeat(60))

  // PHASE 3: Fetch PR
  phase('Fetch PR')

  log(`📥 Fetching PR #${prNum}...`)
  const pr = await fetchPR(agent, platform, prNum)
  log(`✅ "${pr.title}" by ${pr.author}`)
  log(`   ${pr.head_branch} → ${pr.base_branch}`)

  // Get diff and files
  const diffResult = await agent(`Get diff and changed files for PR #${prNum}.

Execute:
${platform.cli} pr diff ${prNum}
${platform.cli} pr view ${prNum} --json files

Return diff and file list.`, {
    label: `Get PR #${prNum} Diff`,
    schema: {
      type: 'object',
      properties: {
        diff: { type: 'string' },
        files: { type: 'array', items: { type: 'string' } },
        files_changed: { type: 'number' },
        additions: { type: 'number' },
        deletions: { type: 'number' }
      }
    }
  })

  log(`📊 ${diffResult.files_changed || diffResult.files?.length || 0} files, +${diffResult.additions || 0}/-${diffResult.deletions || 0}`)

  // PHASE 4: Impact Analysis
  phase('Impact Analysis')

  log('🎯 Analyzing impact...')
  const impact = await analyzeImpactSimple(agent, diffResult.files || [], diffResult.diff)

  log(`✅ Impact: ${impact.risk_level}`)
  log(`   Breaking: ${impact.breaking_changes.length}`)
  log(`   High-risk: ${impact.high_risk_changes.length}`)
  log(`   Impacted files: ${impact.impacted_files}`)

  // PHASE 5: Multi-Model Review
  phase('Multi-Model Review')

  const reviewPrompt = `Review this pull request:

**PR #${prNum}**: ${pr.title}
**Author**: ${pr.author}
**Branch**: ${pr.head_branch} → ${pr.base_branch}

**Changes** (${diffResult.files_changed || 0} files):
\`\`\`diff
${diffResult.diff.substring(0, 2500)}
${diffResult.diff.length > 2500 ? '\n... (truncated)' : ''}
\`\`\`

**Impact Analysis**:
${impact.breaking_changes.length > 0 ? `⚠️ BREAKING CHANGES (${impact.breaking_changes.length}):
${impact.breaking_changes.map(bc => `  - ${bc.entity}: ${bc.reason}`).join('\n')}
` : ''}Risk Level: ${impact.risk_level}
Impacted Files: ${impact.impacted_files}
Missing Tests: ${impact.missing_tests}

Analyze and provide:
1. Quality score (0-100)
2. Recommendation (approve/request_changes/comment)
3. Issues found (with severity)
4. Strengths
5. Improvements needed
6. Confidence level (0-100)

**IMPORTANT**: If breaking changes detected, strongly consider "request_changes".`

  const { reviews, models } = await multiModelReview(agent, reviewPrompt, CONFIG.workers)

  log(`✅ ${reviews.length} models completed review`)

  // PHASE 6: Arbiter Decision
  phase('Arbiter Decision')

  log('⚖️ Arbiter deciding...')
  const decision = await arbiterDecision(agent, pr.title, reviews, CONFIG.arbiterModel)

  log(`✅ Decision: ${decision.final_decision}`)
  log(`   Consensus: ${decision.consensus_score}%`)

  // Calculate quality score
  const avgQuality = reviews.reduce((sum, r) => sum + r.quality_score, 0) / reviews.length

  // PHASE 7: Auto-Decision
  phase('Auto-Decision')

  log('🤖 Determining auto-action...')

  let autoAction = 'COMMENT' // Default: just comment
  let reasoning = ''

  // AUTO-REJECT criteria
  if (impact.breaking_changes.length > 0) {
    autoAction = 'REJECT'
    reasoning = `Breaking changes detected: ${impact.breaking_changes.map(bc => bc.entity).join(', ')}`
  } else if (impact.risk_level === 'critical') {
    autoAction = 'REJECT'
    reasoning = `Critical risk level`
  } else if (avgQuality < CONFIG.autoReject.lowQualityScore) {
    autoAction = 'REJECT'
    reasoning = `Low quality score (${Math.round(avgQuality)}/100)`
  } else if (reviews.some(r => r.issues_found?.some(i => i.severity === 'critical'))) {
    autoAction = 'REJECT'
    reasoning = `Critical issues found`
  }
  // AUTO-APPROVE criteria
  else if (
    decision.final_decision === 'approve' &&
    avgQuality >= minQuality &&
    decision.consensus_score >= CONFIG.autoApprove.minConsensus &&
    impact.breaking_changes.length === 0 &&
    impact.high_risk_changes.length <= CONFIG.autoApprove.maxHighRiskChanges &&
    impact.impacted_files <= CONFIG.autoApprove.maxImpactedFiles
  ) {
    autoAction = 'APPROVE'
    reasoning = `High quality (${Math.round(avgQuality)}/100), ${decision.consensus_score}% consensus, ${impact.risk_level} risk`
  }
  // REQUEST_CHANGES
  else if (decision.final_decision === 'request_changes') {
    autoAction = 'REJECT'
    reasoning = `AI consensus: request changes (quality ${Math.round(avgQuality)}/100)`
  }

  log(`🎯 Auto-Action: ${autoAction}`)
  log(`   Reasoning: ${reasoning}`)

  // PHASE 8: Post Results
  phase('Post Results')

  log('📝 Posting review...')

  // Build comment
  let comment = `## 🤖 INTERACTIVE PR REVIEW

**Quality Score**: ${Math.round(avgQuality)}/100
**AI Consensus**: ${decision.final_decision} (${decision.consensus_score}% agreement)
**Impact Risk**: ${impact.risk_level}
**Auto-Decision**: ${autoAction}

### Decision Reasoning
${reasoning}

### Impact Analysis
- **Breaking Changes**: ${impact.breaking_changes.length}
${impact.breaking_changes.length > 0 ? impact.breaking_changes.map(bc => `  - ⚠️ ${bc.entity}: ${bc.reason}`).join('\n') : ''}
- **High-Risk Changes**: ${impact.high_risk_changes.length}
- **Files Impacted**: ${impact.impacted_files}
- **Missing Tests**: ${impact.missing_tests}

### AI Reviews (${reviews.length} models)

${reviews.map((r, idx) => `**${models[idx]}** - ${r.recommendation} (${r.quality_score}/100, ${r.confidence}% confidence)
- Issues: ${r.issues_found?.length || 0} (${r.issues_found?.filter(i => i.severity === 'critical').length || 0} critical)
${r.issues_found?.slice(0, 3).map(i => `  - ${i.severity}: ${i.description}`).join('\n') || ''}
${r.strengths?.slice(0, 2).map(s => `  - ✅ ${s}`).join('\n') || ''}
`).join('\n')}

### Arbiter Decision (${CONFIG.arbiterModel})
${decision.reasoning}

${decision.key_concerns.length > 0 ? `**Key Concerns**:
${decision.key_concerns.map(c => `- ${c}`).join('\n')}
` : ''}

---

*Automated review by pr-review-auto workflow*
*Approval Criteria: Quality ≥ ${minQuality}, Consensus ≥ ${CONFIG.autoApprove.minConsensus}%, No breaking changes*`

  await postComment(agent, platform, 'pr', prNum, comment)
  log(`✅ Comment posted`)

  // Execute action
  if (autoAction === 'APPROVE') {
    log('👍 Auto-approving PR...')

    await agent(`Approve PR #${prNum}.

Execute:
${platform.cli} pr review ${prNum} --approve --body "✅ Auto-approved: Quality ${Math.round(avgQuality)}/100, ${decision.consensus_score}% AI consensus, ${impact.risk_level} risk"`, {
      label: `Approve PR #${prNum}`
    })

    log(`✅ PR #${prNum} APPROVED`)

  } else if (autoAction === 'REJECT') {
    log('⚠️  Requesting changes...')

    await agent(`Request changes on PR #${prNum}.

Execute:
${platform.cli} pr review ${prNum} --request-changes --body "⚠️ Changes requested: ${reasoning}"`, {
      label: `Request Changes PR #${prNum}`
    })

    log(`✅ PR #${prNum} REJECTED (changes requested)`)

  } else {
    log('💬 Comment-only (no approve/reject)')
  }

  return {
    pr_number: prNum,
    title: pr.title,
    quality_score: Math.round(avgQuality),
    ai_decision: decision.final_decision,
    auto_action: autoAction,
    consensus: decision.consensus_score,
    impact_risk: impact.risk_level,
    breaking_changes: impact.breaking_changes.length,
    approved: autoAction === 'APPROVE',
    rejected: autoAction === 'REJECT'
  }
}

// ============================================================================
// REVIEW ALL PRs IN PARALLEL
// ============================================================================

log('')
log('🚀 Reviewing PRs in parallel for faster processing...')
log('')

const results = await parallel(prsThisRun.map(prNum => () =>
  reviewSinglePR(prNum, platform)
))

const validResults = results.filter(Boolean)

// ============================================================================
// SUMMARY
// ============================================================================

log('')
log('═'.repeat(60))
log('📊 INTERACTIVE REVIEW SUMMARY')
log('═'.repeat(60))
log(`Total PRs reviewed: ${validResults.length}/${prsThisRun.length}`)
log(`Auto-approved: ${validResults.filter(r => r.approved).length}`)
log(`Changes requested: ${validResults.filter(r => r.rejected).length}`)
log(`Comment-only: ${validResults.filter(r => !r.approved && !r.rejected).length}`)
log('')

validResults.forEach(r => {
  const icon = r.approved ? '✅' : r.rejected ? '⚠️' : '💬'
  log(`${icon} PR #${r.pr_number}: ${r.title}`)
  log(`   Action: ${r.auto_action}, Quality: ${r.quality_score}/100, Risk: ${r.impact_risk}`)
})

log('═'.repeat(60))
log('')

if (prsToReview.length > maxPRs) {
  log(`ℹ️  ${prsToReview.length - maxPRs} more PRs remain - run again to continue`)
} else {
  log(`✅ All PRs reviewed!`)
}

const result = {
  status: 'success',
  prs_reviewed: validResults.length,
  approved: validResults.filter(r => r.approved).length,
  rejected: validResults.filter(r => r.rejected).length,
  remaining: Math.max(0, prsToReview.length - maxPRs),
  breaking_changes: validResults.filter(r => r.breaking_changes > 0).length,
  failed: results.length - validResults.length,
  results: validResults
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'code-pr-review',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result

}
