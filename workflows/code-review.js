// Code Review - Unified multi-model code review
// Combines: auto-review-brutal + built-in code-review
// Supports all consensus strategies with configurable workers/arbiter

import { ISSUE_SCHEMA, REVIEW_SCHEMA } from './shared/schemas.js'
import { multiModelReview, arbiterDecision } from './shared/consensus-engine.js'
import { formatAIAttribution } from './shared/ai-attribution.js'
import { detectPlatform, syncWithRemote, createIssue } from './shared/platform-detector.js'
import { calculateQualityScore, formatQualityReport } from './shared/quality-scorer.js'

export const meta = {
  name: 'code-review',
  description: 'Multi-model code review with configurable consensus strategies',
  whenToUse: 'When user wants code review with AI consensus voting',
  phases: [
    { title: 'Setup', detail: 'Sync and configure strategy' },
    { title: 'Scan', detail: 'Find issues in code' },
    { title: 'Multi-Model Review', detail: 'Worker models review', model: 'opus' },
    { title: 'Arbiter Decision', detail: 'Consensus voting' },
    { title: 'Results', detail: 'Create issues or report' },
  ],
}

// Parse arguments
const strategy = args?.strategy || args?.['--strategy'] || 'rotating'
const arbiterModel = args?.arbiter || args?.['--arbiter'] || null
const workersArg = args?.workers || args?.['--workers'] || 'opus,sonnet,haiku'
const workers = workersArg.split(',')
const shouldCreateIssues = args?.['create-issues'] !== false
const shouldSync = args?.sync !== false
const targetPath = args?.path || args?.['--path'] || '.'

log('')
log('═'.repeat(60))
log('🔍 Multi-Model Code Review')
log('═'.repeat(60))
log(`Strategy: ${strategy}`)
log(`Workers: ${workers.join(', ')}`)
log(`Arbiter: ${arbiterModel || 'auto (based on strategy)'}`)
log(`Path: ${targetPath}`)
log(`Create Issues: ${shouldCreateIssues ? 'YES' : 'NO'}`)
log('═'.repeat(60))
log('')

// PHASE 1: Setup
phase('Setup')

let platform = null

if (shouldCreateIssues) {
  log('🔧 Detecting platform...')
  platform = await detectPlatform(agent)
  log(`✅ Platform: ${platform.platform} (using ${platform.cli})`)
}

if (shouldSync) {
  log('📥 Syncing with remote...')
  const syncResult = await syncWithRemote(agent)

  if (syncResult.status === 'conflicts') {
    log(`⚠️ Rebase conflicts: ${syncResult.conflicts?.join(', ')}`)
    return { status: 'conflicts', message: 'Resolve conflicts first' }
  }

  log(`✅ ${syncResult.status === 'up_to_date' ? 'Up to date' : 'Synced'}`)
}

// PHASE 2: Scan
phase('Scan')

log(`🔍 Scanning ${targetPath}...`)

const scanResult = await agent(`Scan the code for issues.

Target: ${targetPath}

Focus on:
- Security vulnerabilities
- Code quality issues
- Bug patterns
- Critical style violations

Return structured list with evidence and confidence.
Avoid false positives.`, {
  label: 'Scan Code',
  schema: {
    type: 'object',
    properties: {
      issues: { type: 'array', items: ISSUE_SCHEMA },
      files_scanned: { type: 'number' },
    },
    required: ['issues'],
  }
})

const issues = scanResult.issues || []
log(`Found ${issues.length} potential issues`)

if (issues.length === 0) {
  log('✅ No issues found - code is clean!')
  return {
    status: 'success',
    issues_found: 0,
    strategy,
  }
}

// PHASE 3: Multi-Model Review
phase('Multi-Model Review')

log(`🤖 Running ${strategy} strategy review on ${Math.min(issues.length, 10)} issues...`)

const reviewedIssues = await pipeline(
  issues.slice(0, 10), // Limit to 10 for cost
  issue => multiModelReview(
    `Review this potential issue:

**Issue**: ${issue.description}
**File**: ${issue.file_path}:${issue.line_number || '?'}
**Severity**: ${issue.severity}
**Evidence**: ${issue.evidence || 'See code'}

Analyze: Is this real or false positive?
Provide confidence score.`,
    REVIEW_SCHEMA,
    {
      workers,
      strategy,
      arbiterModel,
      phase: 'Multi-Model Review',
      labelPrefix: issue.category,
    }
  ).then(reviews => ({ issue, reviews }))
)

log(`✅ Multi-model review complete`)

// PHASE 4: Arbiter Decision
phase('Arbiter Decision')

log(`⚖️ Arbiter making decisions (${strategy} strategy)...`)

const decisions = await pipeline(
  reviewedIssues.filter(Boolean),
  ({ issue, reviews }) => arbiterDecision(
    `${issue.description} (${issue.file_path})`,
    reviews,
    {
      strategy,
      arbiterModel,
      decisionType: 'issue',
      phase: 'Arbiter Decision',
    }
  ).then(decision => ({
    issue,
    reviews,
    decision,
  }))
)

log(`✅ Decisions complete`)

// PHASE 5: Results
phase('Results')

const realIssues = decisions.filter(d => d.decision?.final_decision === 'real_issue')
const falsePositives = decisions.filter(d => d.decision?.final_decision === 'false_positive')

log('')
log('═'.repeat(60))
log('📊 Code Review Results')
log('═'.repeat(60))
log(`Total Scanned: ${issues.length}`)
log(`Reviewed: ${reviewedIssues.length}`)
log(`Real Issues: ${realIssues.length}`)
log(`False Positives: ${falsePositives.length}`)
log(`Strategy: ${strategy}`)
log(`Consensus: ${decisions.length > 0 ? Math.round(decisions.reduce((sum, d) => sum + (d.decision?.consensus_score || 0), 0) / decisions.length) : 0}% avg`)
log('═'.repeat(60))
log('')

if (shouldCreateIssues && realIssues.length > 0) {
  log(`📝 Creating ${realIssues.length} GitHub issues...`)

  const createdIssues = await pipeline(
    realIssues.filter(d => d.decision?.create_issue),
    ({ issue, reviews, decision }) => {
      const attribution = formatAIAttribution(reviews, decision)

      const title = `[${decision.issue_priority}] ${issue.description}`
      const body = `## Issue

**Category**: ${issue.category}
**Severity**: ${issue.severity}
**File**: ${issue.file_path}:${issue.line_number || '?'}

### Evidence

${issue.evidence || 'See code'}

---

${attribution}

**Review Strategy**: ${strategy}
**Arbiter**: ${decision.arbiter || 'N/A'}
`

      return createIssue(agent, platform, title, body, [
        decision.issue_priority,
        'ai-review',
        issue.category,
      ]).then(result => result.issue_url)
    }
  )

  const urls = createdIssues.filter(Boolean)
  log(`✅ Created ${urls.length} issues`)

  if (urls.length > 0) {
    log('\nIssue URLs:')
    urls.forEach((url, i) => log(`  ${i + 1}. ${url}`))
  }

  return {
    status: 'success',
    strategy,
    issues_found: issues.length,
    real_issues: realIssues.length,
    false_positives: falsePositives.length,
    issues_created: urls.length,
    issue_urls: urls,
  }
} else {
  // Just report findings
  log('\n📋 Real Issues Found:\n')
  realIssues.forEach(({ issue, decision }, i) => {
    log(`${i + 1}. [${decision.issue_priority}] ${issue.description}`)
    log(`   File: ${issue.file_path}:${issue.line_number || '?'}`)
    log(`   Consensus: ${decision.consensus_score}%`)
    log(`   Arbiter: ${decision.arbiter}`)
    log('')
  })

  return {
    status: 'success',
    strategy,
    issues_found: issues.length,
    real_issues: realIssues.length,
    false_positives: falsePositives.length,
  }
}
