// PR Review - Multi-Model Pull Request Review
// Uses shared consensus engine and platform detection
// Review-only mode: analyzes PRs, posts comments, can auto-approve

import { PR_REVIEW_SCHEMA, ARBITER_SCHEMA } from './shared/schemas.js'
import { multiModelReview, arbiterDecision } from './shared/consensus-engine.js'
import { formatPRComment } from './shared/ai-attribution.js'
import { detectPlatform, syncWithRemote, fetchPR, postComment } from './shared/platform-detector.js'
import { calculateQualityScore, formatQualityReport } from './shared/quality-scorer.js'
import { continuousMonitor } from './shared/loop-controller.js'

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
      interval: 300000, // 5 minutes
      maxRuns: Infinity,
      stopOnNoWork: false,
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

Analyze:
1. Code quality and correctness
2. Security vulnerabilities
3. Best practices
4. Testing coverage
5. Documentation

Provide:
- Overall quality score (0-100)
- Recommendation (approve, request_changes, comment)
- Issues found (if any)
- Strengths
- Improvements needed
- Your confidence (0-100)`

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

  // PHASE 5: Post Results
  phase('Post Results')

  if (shouldPost || shouldApprove) {
    log('📝 Posting review comment...')

    const comment = formatPRComment(reviews, decision, qualityScore.score)

    await postComment(agent, platform, 'pr', num, comment)
    log(`✅ Comment posted to PR #${num}`)

    // Auto-approve if quality meets threshold
    if (shouldApprove && qualityScore.score >= threshold) {
      log(`✅ Quality score (${qualityScore.score}) >= threshold (${threshold})`)
      log('👍 Approving PR...')

      await agent(`Approve PR #${num}.

Execute:
${platform.cli} pr review ${num} --approve --body "✅ AI Review: Quality score ${qualityScore.score}/100. ${decision.consensus_score}% consensus. Auto-approved."`, {
        label: `Approve PR #${num}`,
      })

      log(`✅ PR #${num} approved`)
    } else if (shouldApprove) {
      log(`⚠️ Quality score (${qualityScore.score}) < threshold (${threshold}) - not auto-approving`)
    }
  } else {
    log('ℹ️  Skipping post (use --post to post comment)')
  }

  return {
    status: 'success',
    pr_number: num,
    quality_score: qualityScore.score,
    decision: decision.final_decision,
    consensus: decision.consensus_score,
    approved: shouldApprove && qualityScore.score >= threshold,
  }
}
