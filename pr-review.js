// PR Review - Multi-Model Pull Request Review
// Uses shared consensus engine and platform detection
// Review-only mode: analyzes PRs, posts comments, can auto-approve
// NOW WITH IMPACT ANALYSIS: Detects breaking changes and cross-codebase impacts

import { PR_REVIEW_SCHEMA, ARBITER_SCHEMA } from './shared/schemas.js'
import { multiModelReview, arbiterDecision } from './shared/consensus-engine.js'
import { formatPRComment, formatPRCommentEnhanced } from './shared/ai-attribution.js'
import { detectPlatform, syncWithRemote, fetchPR, postComment } from './shared/platform-detector.js'
import { calculateQualityScore, formatQualityReport } from './shared/quality-scorer.js'
import { continuousMonitor } from './shared/loop-controller.js'
import { analyzeImpact, formatImpactAnalysis } from './shared/impact-analysis.js'

export const meta = {
  name: 'pr-review',
  description: 'Multi-model PR review with consensus voting and auto-approve',
  whenToUse: 'When user wants to review pull requests with AI consensus',
  phases: [
    { title: 'Setup', detail: 'Detect platform and sync' },
    { title: 'Fetch PR', detail: 'Get PR details' },
    { title: 'Multi-Model Review', detail: 'Opus, Sonnet, Haiku review PR', model: 'opus' },
    { title: 'Arbiter Decision', detail: 'Final approval decision' },
    { title: 'Post Results', detail: 'Comment on PR with findings' },
  ],
}

// Parse arguments
const prNumber = args?.[0]
let isLoopMode = prNumber === 'loop' || args?.loop || !prNumber  // Default to loop if no PR specified
const shouldPost = args?.post || args?.['--post'] || true  // Auto-post by default
const shouldApprove = args?.approve || args?.['--approve'] || args?.['auto-approve']
const qualityThreshold = args?.threshold || args?.['--threshold'] || 90
const strategy = args?.strategy || args?.['--strategy'] || 'rotating'
const arbiterModel = args?.arbiter || args?.['--arbiter'] || null
const workersArg = args?.workers || args?.['--workers'] || 'opus,sonnet,haiku'
const workers = workersArg.split(',')

// If PR number provided, not loop mode
if (prNumber && prNumber !== 'loop' && !isNaN(parseInt(prNumber))) {
  isLoopMode = false
}

log('')
log('═'.repeat(60))
log('🔍 Multi-Model PR Review')
log('═'.repeat(60))
log(`Mode: ${isLoopMode ? 'CONTINUOUS (auto-discover)' : `Single PR #${prNumber}`}`)
log(`Strategy: ${strategy}`)
log(`Workers: ${workers.join(', ')}`)
log(`Arbiter: ${arbiterModel || 'auto (based on strategy)'}`)
log(`Auto-post: ${shouldPost ? 'YES' : 'NO'}`)
log(`Auto-approve: ${shouldApprove ? `YES (threshold ${qualityThreshold})` : 'NO'}`)
log('═'.repeat(60))
log('')

// PHASE 1: Setup
phase('Setup')

log('🔧 Detecting platform and syncing...')
const platform = await detectPlatform(agent)
log(`✅ Platform: ${platform.platform} (using ${platform.cli})`)

const syncResult = await syncWithRemote(agent)
if (syncResult.status === 'conflicts') {
  log(`⚠️ Rebase conflicts: ${syncResult.conflicts?.join(', ')}`)
  return { status: 'conflicts', message: 'Resolve conflicts first' }
}
log(`✅ ${syncResult.status === 'up_to_date' ? 'Already up to date' : 'Synced with remote'}`)

// Loop mode or single PR
if (isLoopMode) {
  log('🔄 Starting continuous PR monitoring...')

  const monitorResult = await continuousMonitor(
    // Check function: fetch open PRs
    async (run) => {
      log('📋 Checking for open PRs...')

      const result = await agent(`List all open pull requests.

Platform: ${platform.platform}
CLI: ${platform.cli}

Execute:
${platform.cli} pr list --json number,title,author,state --limit 50

Return array of PR numbers that need review.
Skip PRs already reviewed by this bot (check for AI review comments).`, {
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
                  needs_review: { type: 'boolean' },
                },
                required: ['number', 'needs_review']
              }
            }
          },
          required: ['prs']
        }
      })

      return result.prs.filter(pr => pr.needs_review).map(pr => pr.number)
    },

    // Action function: review PRs
    async (prNumbers) => {
      const results = []

      for (const num of prNumbers.slice(0, 5)) { // Review max 5 PRs per iteration
        log(`\n═══ Reviewing PR #${num} ═══`)

        const reviewResult = await reviewSinglePR(num, platform, shouldApprove, qualityThreshold, shouldPost, workers, strategy, arbiterModel)
        results.push(reviewResult)
      }

      return results
    },

    {
      interval: 600000, // 10 minutes (rate limit protection)
      maxRuns: 100, // Bounded to prevent resource exhaustion
      stopOnNoWork: true, // Stop when no PRs to review (prevents wasted runs)
    }
  )

  return monitorResult

} else {
  // Single PR review
  return await reviewSinglePR(prNumber, platform, shouldApprove, qualityThreshold, shouldPost, workers, strategy, arbiterModel)
}

// Helper function to review a single PR
async function reviewSinglePR(num, platform, shouldApprove, threshold, shouldPost, workers, strategy, arbiterModel) {
  // PHASE 2: Fetch PR
  phase('Fetch PR')

  log(`📥 Fetching PR #${num}...`)
  const pr = await fetchPR(agent, platform, num)
  log(`✅ PR: "${pr.title}" by ${pr.author}`)
  log(`   ${pr.head_branch} → ${pr.base_branch}`)

  // Get PR diff
  const diffResult = await agent(`Get the diff for PR #${num}.

Execute:
${platform.cli} pr diff ${num}

Return the full diff content (first 5000 lines max).`, {
    label: `Get PR #${num} Diff`,
    schema: {
      type: 'object',
      properties: {
        diff: { type: 'string' },
        files_changed: { type: 'number' },
        additions: { type: 'number' },
        deletions: { type: 'number' },
      },
      required: ['diff'],
    }
  })

  log(`📊 Changes: ${diffResult.files_changed || 0} files, +${diffResult.additions || 0}/-${diffResult.deletions || 0}`)

  // NEW: PHASE 2.5: Impact Analysis
  phase('Impact Analysis')

  log('🎯 Analyzing impact on rest of codebase...')

  // Extract changed files from diff or PR data
  const changedFiles = pr.files || await agent(`Extract list of changed files from PR #${num}.

Execute:
${platform.cli} pr view ${num} --json files | jq -r '.files[].path'

Return array of file paths.`, {
    label: 'Get Changed Files',
    schema: {
      type: 'object',
      properties: {
        files: { type: 'array', items: { type: 'string' } }
      }
    }
  }).then(r => r.files || [])

  log(`📁 Changed files: ${changedFiles.length}`)

  const impact = await analyzeImpact(agent, {
    files: changedFiles,
    diff: diffResult.diff
  }, {
    includeTests: true,
    maxDepth: 2,
    checkBreakingChanges: true
  })

  log(`✅ Impact analysis complete`)
  log(`   Breaking changes: ${impact.breaking_changes.length}`)
  log(`   High risk: ${impact.high_risk_changes.length}`)
  log(`   Impacted files: ${impact.impacted_files.length}`)
  log(`   Missing tests: ${impact.missing_tests.length}`)

  // PHASE 3: Multi-Model Review
  phase('Multi-Model Review')

  log('🤖 Running multi-model PR review...')

  const reviewPrompt = `Review this pull request and provide your assessment:

**PR Title**: ${pr.title}
**Author**: ${pr.author}
**Branch**: ${pr.head_branch} → ${pr.base_branch}
**Description**: ${pr.body || 'No description'}

**Changes**:
\`\`\`diff
${diffResult.diff.substring(0, 3000)}
${diffResult.diff.length > 3000 ? '\n... (truncated)' : ''}
\`\`\`

**Impact Analysis**:
${impact.breaking_changes.length > 0 ? `⚠️ BREAKING CHANGES DETECTED (${impact.breaking_changes.length}):
${impact.breaking_changes.slice(0, 3).map(bc => `  - ${bc.entity}: ${bc.reason}`).join('\n')}
` : ''}${impact.high_risk_changes.length > 0 ? `🔥 High Risk Changes (${impact.high_risk_changes.length}):
${impact.high_risk_changes.slice(0, 3).map(hr => `  - ${hr.entity}: ${hr.reason}`).join('\n')}
` : ''}Files Impacted: ${impact.impacted_files.length}
Missing Tests: ${impact.missing_tests.length}

Analyze:
1. Code quality and correctness
2. Security vulnerabilities
3. Best practices
4. Testing coverage
5. Documentation
6. **CRITICAL**: Impact on other parts of codebase (see impact analysis above)

Provide:
- Overall quality score (0-100)
- Recommendation (approve, request_changes, comment)
- Issues found (if any)
- Strengths
- Improvements needed
- Your confidence (0-100)

**NOTE**: If breaking changes or high-risk changes detected, consider recommending "request_changes" unless properly mitigated.`

  const reviews = await multiModelReview(reviewPrompt, PR_REVIEW_SCHEMA, {
    workers,
    strategy,
    arbiterModel,
    phase: 'Multi-Model Review',
    labelPrefix: `PR #${num}`,
  })

  log(`✅ Multi-model review complete`)

  // PHASE 4: Arbiter Decision
  phase('Arbiter Decision')

  log('⚖️ Arbiter making final decision...')

  const decision = await arbiterDecision(
    `Pull Request #${num}: "${pr.title}"`,
    reviews,
    {
      strategy,
      arbiterModel,
      decisionType: 'pr',
      phase: 'Arbiter Decision',
    }
  )

  log(`✅ Decision: ${decision.final_decision} (${decision.consensus_score}% consensus)`)

  // Calculate quality score from issues
  const allIssues = [
    ...(reviews.opus?.issues_found || []),
    ...(reviews.sonnet?.issues_found || []),
    ...(reviews.haiku?.issues_found || []),
  ]
  const qualityScore = calculateQualityScore(allIssues)

  log(formatQualityReport(qualityScore))

  // ASK USER: Accept or reject the PR?
  const impactSummary = impact.breaking_changes.length > 0 ? `⚠️ ${impact.breaking_changes.length} breaking change(s)` :
                        impact.high_risk_changes.length > 0 ? `🔥 ${impact.high_risk_changes.length} high-risk change(s)` :
                        impact.impacted_files.length > 10 ? `📊 ${impact.impacted_files.length} files impacted` :
                        '✅ Low impact'

  log(`\n📋 Review Summary:`)
  log(`   AI Decision: ${decision.final_decision}`)
  log(`   Quality Score: ${qualityScore.score}/100`)
  log(`   Consensus: ${decision.consensus_score}%`)
  log(`   Impact: ${impactSummary}`)
  if (impact.breaking_changes.length > 0) {
    log(`   ⚠️ Breaking: ${impact.breaking_changes.map(bc => bc.entity).join(', ')}`)
  }
  log('')

  // This will be filled by agent since AskUserQuestion not available in workflows
  // User will see the summary above and workflow will use AI decision by default
  // TODO: When workflow runtime supports AskUserQuestion, replace this with interactive prompt

  // For now: auto-decide based on AI recommendation and impact
  let userDecision = { action: 'COMMENT', reasoning: null }

  if (decision.final_decision === 'approve' && impact.breaking_changes.length === 0 && impact.high_risk_changes.length < 3) {
    userDecision.action = 'APPROVE'
    userDecision.reasoning = `High quality (${qualityScore.score}/100), ${decision.consensus_score}% consensus, low risk`
  } else if (impact.breaking_changes.length > 0) {
    userDecision.action = 'REQUEST_CHANGES'
    userDecision.reasoning = `Breaking changes detected: ${impact.breaking_changes.map(bc => bc.entity).join(', ')}`
  } else if (decision.final_decision === 'request_changes') {
    userDecision.action = 'REQUEST_CHANGES'
    userDecision.reasoning = `AI recommends changes, quality ${qualityScore.score}/100`
  }

  log(`\n🤖 Auto-Decision: ${userDecision.action}`)
  if (userDecision.reasoning) {
    log(`   Reasoning: ${userDecision.reasoning}`)
  }

  // PHASE 5: Post Results
  phase('Post Results')

  if (userDecision.action === 'SKIP') {
    log('ℹ️  Skipping post (user chose SKIP)')
  } else {
    log('📝 Posting review comment...')

    // Use enhanced format for full AI transparency + impact analysis
    let comment = formatPRCommentEnhanced(reviews, decision, qualityScore.score, {
      showFullReviews: true,
      showRejectionReasons: true
    })

    // Append impact analysis
    comment += '\n\n' + formatImpactAnalysis(impact)

    // Add user decision to comment if reasoning provided
    if (userDecision.reasoning) {
      comment += `\n\n---\n\n**User Decision**: ${userDecision.action}\n> ${userDecision.reasoning}`
    }

    await postComment(agent, platform, 'pr', num, comment)
    log(`✅ Comment posted to PR #${num}`)

    // Execute user's decision
    if (userDecision.action === 'APPROVE') {
      log('👍 Approving PR...')

      await agent(`Approve PR #${num}.

Execute:
${platform.cli} pr review ${num} --approve --body "✅ Approved after AI review: Quality score ${qualityScore.score}/100. ${decision.consensus_score}% AI consensus. ${impactSummary}${userDecision.reasoning ? ' - ' + userDecision.reasoning : ''}"`, {
        label: `Approve PR #${num}`,
      })

      log(`✅ PR #${num} approved`)
    } else if (userDecision.action === 'REQUEST_CHANGES') {
      log('⚠️  Requesting changes...')

      await agent(`Request changes on PR #${num}.

Execute:
${platform.cli} pr review ${num} --request-changes --body "⚠️ Changes requested after AI review: Quality score ${qualityScore.score}/100. ${impactSummary}${userDecision.reasoning ? ' - ' + userDecision.reasoning : ''}"`, {
        label: `Request Changes PR #${num}`,
      })

      log(`✅ Changes requested on PR #${num}`)
    } else {
      log('💬 Comment-only mode (no approve/reject)')
    }
  }

  return {
    status: 'success',
    pr_number: num,
    quality_score: qualityScore.score,
    ai_decision: decision.final_decision,
    user_action: userDecision.action,
    consensus: decision.consensus_score,
    approved: userDecision.action === 'APPROVE',
    changes_requested: userDecision.action === 'REQUEST_CHANGES',
    impact: {
      breaking_changes: impact.breaking_changes.length,
      high_risk: impact.high_risk_changes.length,
      impacted_files: impact.impacted_files.length,
      missing_tests: impact.missing_tests.length,
      has_breaking_changes: impact.breaking_changes.length > 0,
      has_high_risk: impact.high_risk_changes.length > 0,
    }
  }
}
