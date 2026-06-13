// PR Review - Multi-Model Pull Request Review
// Uses shared consensus engine and platform detection
// Review-only mode: analyzes PRs, posts comments, can auto-approve
// FIXED VERSION: No imports, all dependencies inlined

// ============================================================================
// INLINED SCHEMAS (from shared/schemas.js)
// ============================================================================

const ISSUE_SCHEMA = {
  type: 'object',
  properties: {
    severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
    category: { type: 'string' },
    description: { type: 'string' },
    file_path: { type: 'string' },
    line_number: { type: 'number' },
    evidence: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
  },
  required: ['severity', 'category', 'description', 'file_path', 'confidence'],
}

const PR_REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    overall_quality: { type: 'number', minimum: 0, maximum: 100 },
    approval_recommendation: { type: 'string', enum: ['approve', 'request_changes', 'comment'] },
    issues_found: { type: 'array', items: ISSUE_SCHEMA },
    strengths: { type: 'array', items: { type: 'string' } },
    improvements_needed: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
  },
  required: ['overall_quality', 'approval_recommendation', 'issues_found', 'confidence'],
}

// ============================================================================
// INLINED CONSENSUS ENGINE (from shared/consensus-engine.js)
// ============================================================================

let arbiterRotationIndex = 0

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

async function multiModelReview(prompt, schema, options = {}) {
  const {
    workers = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
    phase = 'Multi-Model Review',
    labelPrefix = 'Review',
    strategy = 'rotating',
    executionMode = 'parallel',
  } = options

  log(`🎯 Strategy: ${strategy} | Workers: ${workers.join(', ')}`)

  const workerReviews = await runWorkers(prompt, schema, workers, phase, labelPrefix, executionMode)

  const result = { allReviews: workerReviews.filter(Boolean) }

  workers.forEach((model, i) => {
    result[model] = workerReviews[i]
  })

  result.opus = result.opus || null
  result.sonnet = result.sonnet || null
  result.haiku = result.haiku || null

  return result
}

async function runWorkers(prompt, schema, workers, phase, labelPrefix, executionMode) {
  if (executionMode === 'sequential') {
    const results = []
    for (const model of workers) {
      const result = await _agent(prompt, {
        schema,
        model,
        label: `${labelPrefix} (${capitalize(model)})`,
        phase
      })
      results.push(result)
    }
    return results
  } else {
    const workerTasks = workers.map(model =>
      () => agent(prompt, {
        schema,
        model,
        label: `${labelPrefix} (${capitalize(model)})`,
        phase
      })
    )
    return await parallel(workerTasks)
  }
}

function selectArbiter(strategy, arbiterModel, reviews) {
  if (arbiterModel) return arbiterModel

  if (strategy === 'rotating') {
    const availableModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'].filter(m => reviews[m])
    const selected = availableModels[arbiterRotationIndex % availableModels.length]
    arbiterRotationIndex++
    return selected
  } else if (strategy === 'single') {
    return 'fable'
  } else {
    return 'fable'
  }
}

function buildArbiterPrompt(context, reviews) {
  const { opus, sonnet, haiku } = reviews

  return `You are the final arbiter. Review these AI PR assessments:

**Pull Request**:
${context}

**OPUS REVIEW**:
- Recommendation: ${opus?.approval_recommendation || 'N/A'}
- Quality: ${opus?.overall_quality || 0}%
- Confidence: ${opus?.confidence || 0}%

**SONNET REVIEW**:
- Recommendation: ${sonnet?.approval_recommendation || 'N/A'}
- Quality: ${sonnet?.overall_quality || 0}%
- Confidence: ${sonnet?.confidence || 0}%

**HAIKU REVIEW**:
- Recommendation: ${haiku?.approval_recommendation || 'N/A'}
- Quality: ${haiku?.overall_quality || 0}%
- Confidence: ${haiku?.confidence || 0}%

Final decision:
1. Should this PR be approved or require changes?
2. What's the consensus score?
3. Which model had the best analysis and WHY?
4. Why reject the others?`
}

async function arbiterDecision(context, reviews, options = {}) {
  const {
    phase = 'Arbiter Decision',
    strategy = 'rotating',
    arbiterModel = null,
  } = options

  const selectedArbiter = selectArbiter(strategy, arbiterModel, reviews)
  log(`⚖️ Arbiter: ${capitalize(selectedArbiter)} (${strategy} strategy)`)

  const arbiterPrompt = buildArbiterPrompt(context, reviews)

  const decision = await _agent(arbiterPrompt, {
    schema: {
      type: 'object',
      properties: {
        final_decision: { type: 'string' },
        consensus_score: { type: 'number', minimum: 0, maximum: 100 },
        accepted_model: { type: 'string' },
        accepted_reasoning: { type: 'string' },
        rejected_models: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              model: { type: 'string' },
              rejection_reason: { type: 'string' },
            },
            required: ['model', 'rejection_reason'],
          },
        },
        create_issue: { type: 'boolean' },
        issue_priority: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3', 'P4'] },
      },
      required: ['final_decision', 'consensus_score', 'accepted_model', 'accepted_reasoning', 'rejected_models'],
    },
    model: selectedArbiter,
    label: `Arbiter (${capitalize(selectedArbiter)})`,
    phase
  })

  decision.strategy = 'standard'
  decision.arbiter = selectedArbiter
  return decision
}

// ============================================================================
// INLINED AI ATTRIBUTION (from shared/ai-attribution.js)
// ============================================================================

function formatPRComment(reviews, arbiterDecision, qualityScore) {
  const { opus, sonnet, haiku } = reviews

  return `## 🤖 AI Pull Request Review

### Quality Score: ${qualityScore}/100

### Multi-Model Consensus
🤖 **AI Review**: Consensus: ${arbiterDecision.consensus_score}% | Best: ${arbiterDecision.accepted_model}

### Detailed Reviews

**Opus** (${opus?.confidence || 0}% confidence):
- Recommendation: ${opus?.approval_recommendation || 'N/A'}
- Issues Found: ${opus?.issues_found?.length || 0}
${opus?.strengths ? `- Strengths: ${opus.strengths.slice(0, 2).join(', ')}` : ''}

**Sonnet** (${sonnet?.confidence || 0}% confidence):
- Recommendation: ${sonnet?.approval_recommendation || 'N/A'}
- Issues Found: ${sonnet?.issues_found?.length || 0}

**Haiku** (${haiku?.confidence || 0}% confidence):
- Recommendation: ${haiku?.approval_recommendation || 'N/A'}
- Issues Found: ${haiku?.issues_found?.length || 0}

### Arbiter Decision
**${arbiterDecision.final_decision.toUpperCase()}** (${arbiterDecision.consensus_score}% consensus)

**Reasoning**: ${arbiterDecision.accepted_reasoning}

---
*AI-powered PR review - Multi-model consensus*
`
}

// ============================================================================
// INLINED PLATFORM DETECTOR (from shared/platform-detector.js)
// ============================================================================

async function detectPlatform(agent) {
  const result = await _agent(`Detect the repository platform and return details.

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

  const result = await _agent(`Sync with remote repository.

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

async function fetchPR(agent, platform, prNumber) {
  const cli = platform.cli

  const result = await _agent(`Fetch PR/MR details.

Platform: ${platform.platform}
PR Number: ${prNumber}

Execute:
${cli} pr view ${prNumber} --json title,body,labels,state,author,url,headRefName,baseRefName

Parse and return the PR details.`, {
    label: `Fetch PR #${prNumber}`,
    schema: {
      type: 'object',
      properties: {
        number: { type: 'number' },
        title: { type: 'string' },
        body: { type: 'string' },
        state: { type: 'string' },
        author: { type: 'string' },
        url: { type: 'string' },
        head_branch: { type: 'string' },
        base_branch: { type: 'string' },
        labels: { type: 'array', items: { type: 'string' } },
      },
      required: ['number', 'title', 'body', 'state'],
    }
  })

  return result
}

async function postComment(agent, platform, issueOrPR, number, comment) {
  const cli = platform.cli
  const type = issueOrPR === 'issue' ? 'issue' : 'pr'

  const result = await _agent(`Post a comment to ${type} #${number}.

Platform: ${platform.platform}

Execute:
${cli} ${type} comment ${number} --body "${comment}"

Return success status.`, {
    label: `Comment on ${type} #${number}`,
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['posted', 'failed'] },
      },
      required: ['status'],
    }
  })

  return result
}

// ============================================================================
// INLINED QUALITY SCORER (from shared/quality-scorer.js)
// ============================================================================

function calculateQualityScore(issues) {
  if (!Array.isArray(issues) || issues.length === 0) {
    return {
      score: 100,
      critical_count: 0,
      high_count: 0,
      medium_count: 0,
      low_count: 0,
      meets_threshold: true
    }
  }

  const critical = issues.filter(i => i.severity === 'critical' || i.severity === 'P0').length
  const high = issues.filter(i => i.severity === 'high' || i.severity === 'major' || i.severity === 'P1').length
  const medium = issues.filter(i => i.severity === 'medium' || i.severity === 'P2').length
  const low = issues.filter(i => i.severity === 'low' || i.severity === 'minor' || i.severity === 'P3' || i.severity === 'P4').length

  const score = Math.max(0, 100 - (critical * 10 + high * 5 + medium * 1))

  return {
    score,
    critical_count: critical,
    high_count: high,
    medium_count: medium,
    low_count: low,
    meets_threshold: score >= 90
  }
}

function formatQualityReport(qualityScore) {
  const { score, critical_count, high_count, medium_count, low_count } = qualityScore

  let emoji = '✅'
  if (score < 60) emoji = '❌'
  else if (score < 80) emoji = '⚠️'
  else if (score < 90) emoji = '🟡'

  return `${emoji} **Quality Score**: ${score}/100

**Issues Breakdown**:
- Critical: ${critical_count} (×10 points each)
- High: ${high_count} (×5 points each)
- Medium: ${medium_count} (×1 point each)
- Low: ${low_count} (no penalty)

**Total Impact**: -${100 - score} points
`
}

// ============================================================================
// INLINED LOOP CONTROLLER (from shared/loop-controller.js)
// ============================================================================

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function continuousMonitor(checkFn, actionFn, options = {}) {
  const {
    interval = 300000,
    maxRuns = Infinity,
    stopOnNoWork = false,
  } = options

  let runs = 0

  log(`👀 Starting continuous monitoring (checking every ${interval}ms)`)

  while (runs < maxRuns) {
    runs++

    log(`\n🔍 Check ${runs}/${maxRuns === Infinity ? '∞' : maxRuns}`)

    const workItems = await checkFn(runs)

    if (!workItems || workItems.length === 0) {
      log('ℹ️  No work items found')

      if (stopOnNoWork) {
        log('✅ No work - stopping monitor')
        return {
          status: 'no_work',
          runs,
          totalProcessed: 0
        }
      }

      log(`⏸️  Waiting ${interval}ms...`)
      await sleep(interval)
      continue
    }

    log(`📋 Found ${workItems.length} work items`)

    const results = await actionFn(workItems, runs)

    log(`✅ Processed ${results.length} items`)

    if (runs < maxRuns) {
      log(`⏸️  Waiting ${interval}ms before next check...`)
      await sleep(interval)
    }
  }

  log(`🏁 Continuous monitoring stopped (${runs} runs)`)
  return {
    status: 'max_runs',
    runs
  }
}

// ============================================================================
// WORKFLOW METADATA
// ============================================================================

const meta = {
  name: 'pr-review',
  description: 'Multi-model PR review with consensus voting and auto-approve',
  whenToUse: 'When user wants to review pull requests with AI consensus',
  phases: [
    { title: 'Setup', detail: 'Detect platform and sync' },
    { title: 'Fetch PR', detail: 'Get PR details' },
    { title: 'Multi-Model Review', detail: 'Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini review PR (6 workers)' },
    { title: 'Arbiter Decision', detail: 'Final approval decision' },
    { title: 'Post Results', detail: 'Comment on PR with findings' },
  ],
}

module.exports = { meta }

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
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
    await fetch(`${FLEET_DISPATCHER}/complete`, {
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
    const result = await _agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


// ============================================================================
// MAIN WORKFLOW
// ============================================================================

// Parse arguments
const prNumber = args?.[0]
let isLoopMode = prNumber === 'loop' || args?.loop || !prNumber
const shouldPost = args?.post || args?.['--post'] || true
const shouldApprove = args?.approve || args?.['--approve'] || args?.['auto-approve']
const qualityThreshold = args?.threshold || args?.['--threshold'] || 90
const strategy = args?.strategy || args?.['--strategy'] || 'rotating'
const arbiterModel = args?.arbiter || args?.['--arbiter'] || null
const workersArg = args?.workers || args?.['--workers'] || 'fable,opus,sonnet,haiku,gpt-4o,gemini'
const workers = workersArg.split(',')

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

      const result = await _agent(`List all open pull requests.

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

      for (const num of prNumbers.slice(0, 5)) {
        log(`\n═══ Reviewing PR #${num} ═══`)

        const reviewResult = await reviewSinglePR(num, platform, shouldApprove, qualityThreshold, shouldPost, workers, strategy, arbiterModel)
        results.push(reviewResult)
      }

      return results
    },

    {
      interval: 300000,
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
  const diffResult = await _agent(`Get the diff for PR #${num}.

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

      await _agent(`Approve PR #${num}.

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
