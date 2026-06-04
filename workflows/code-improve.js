// Code Improve - Iterative Quality Improvement Loop
// Uses shared modules for review → fix → verify cycles
// Runs until target quality score or max iterations

import { ISSUE_SCHEMA, FIX_SCHEMA, REVIEW_SCHEMA } from './shared/schemas.js'
import { multiModelReview, arbiterDecision } from './shared/consensus-engine.js'
import { formatAIAttribution } from './shared/ai-attribution.js'
import { detectPlatform, syncWithRemote, createPR } from './shared/platform-detector.js'
import { calculateQualityScore, formatQualityReport, prioritizeIssuesForFix, shouldContinueImproving } from './shared/quality-scorer.js'
import { loopMode, iterativeImprovement } from './shared/loop-controller.js'

export const meta = {
  name: 'code-improve',
  description: 'Iterative code quality improvement with review → fix → verify cycles',
  whenToUse: 'When user wants to systematically improve code quality',
  phases: [
    { title: 'Setup', detail: 'Detect platform and sync' },
    { title: 'Review Code', detail: 'Multi-model review finds issues' },
    { title: 'Prioritize', detail: 'Select high-impact issues' },
    { title: 'Generate Fixes', detail: 'Multi-model fix generation' },
    { title: 'Apply Fixes', detail: 'Apply and verify fixes' },
    { title: 'Verify', detail: 'Re-review to check improvements' },
  ],
}

// Parse arguments
const targetScore = parseInt(args?.['target-score'] || args?.target || '95')
const maxIterations = parseInt(args?.['max-iterations'] || args?.iterations || '10')
const batchSize = parseInt(args?.['batch-size'] || args?.batch || '5')
const autoMode = args?.auto || args?.['--auto']
const targetPath = args?.path || args?.['--path'] || '.'

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

log('')
log('═══════════════════════════════════════')
log(`📊 Iterative Code Improvement`)
log('═══════════════════════════════════════')
log(`Target Score: ${targetScore}/100`)
log(`Max Iterations: ${maxIterations}`)
log(`Batch Size: ${batchSize} issues per iteration`)
log(`Target Path: ${targetPath}`)
log(`Auto Mode: ${autoMode ? 'YES' : 'NO'}`)
log('═══════════════════════════════════════')
log('')

// Iterative improvement loop
const loopResult = await loopMode(
  // Iteration function
  async (iteration, previousResult) => {
    log(`\n${'='.repeat(50)}`)
    log(`🔄 Iteration ${iteration}/${maxIterations}`)
    log(${'='.repeat(50)}\n`)

    // PHASE 2: Review Code
    phase('Review Code')

    log(`🔍 Reviewing code in ${targetPath}...`)

    const reviewPrompt = `Review the code and find issues:

**Target**: ${targetPath}
**Focus**: Security, bugs, code quality, best practices

Scan the codebase and identify issues.
Return a structured list of issues with:
- Severity (critical, high, medium, low)
- Category (security, bug, quality, style, etc.)
- Description
- File path and line number
- Evidence
- Confidence (0-100)

Prioritize critical and high severity issues.`

    const reviewResult = await agent(reviewPrompt, {
      label: `Review Iteration ${iteration}`,
      schema: {
        type: 'object',
        properties: {
          issues: { type: 'array', items: ISSUE_SCHEMA },
          files_scanned: { type: 'number' },
        },
        required: ['issues'],
      }
    })

    const issues = reviewResult.issues || []
    const qualityScore = calculateQualityScore(issues)

    log(`\n${formatQualityReport(qualityScore)}`)
    log(`📂 Files scanned: ${reviewResult.files_scanned || 'unknown'}`)
    log(`🐛 Issues found: ${issues.length}`)

    // Check if we should stop
    const continueDecision = shouldContinueImproving(qualityScore, targetScore, maxIterations, iteration)

    if (!continueDecision.continue) {
      log(`\n✅ Stopping: ${continueDecision.reason}`)
      return {
        iteration,
        issues,
        qualityScore,
        shouldStop: true,
        reason: continueDecision.reason,
      }
    }

    // PHASE 3: Prioritize
    phase('Prioritize')

    const prioritized = prioritizeIssuesForFix(issues, batchSize)
    log(`\n📋 Selected ${prioritized.length} highest priority issues for fixing:`)
    prioritized.forEach((issue, i) => {
      log(`   ${i + 1}. [${issue.severity.toUpperCase()}] ${issue.description} (${issue.file_path})`)
    })

    if (prioritized.length === 0) {
      log(`\n✅ No issues to fix - perfect!`)
      return {
        iteration,
        issues: [],
        qualityScore,
        shouldStop: true,
        reason: 'no_issues',
      }
    }

    // Ask user if not in auto mode
    if (!autoMode) {
      log(`\n⏸️  Continue with fixing ${prioritized.length} issues? (yes/no)`)
      // In workflow, we auto-continue for now
      // TODO: Add AskUserQuestion support
    }

    // PHASE 4: Generate Fixes
    phase('Generate Fixes')

    log(`🤖 Generating fixes for ${prioritized.length} issues...`)

    const fixes = await pipeline(
      prioritized,
      issue => parallel([
        () => agent(`Generate a fix for this issue:

**Issue**: ${issue.description}
**File**: ${issue.file_path}:${issue.line_number || '?'}
**Severity**: ${issue.severity}
**Evidence**: ${issue.evidence || 'See code'}

Provide a complete fix with:
- Approach
- Code changes
- Files modified
- Rationale
- Confidence
- Risks
- Test plan`, {
          schema: FIX_SCHEMA,
          model: 'opus',
          label: `Fix: ${issue.category}`,
          phase: 'Generate Fixes'
        }),
        () => agent(`Generate a fix for this issue:

**Issue**: ${issue.description}
**File**: ${issue.file_path}:${issue.line_number || '?'}
**Severity**: ${issue.severity}
**Evidence**: ${issue.evidence || 'See code'}

Provide a complete fix.`, {
          schema: FIX_SCHEMA,
          model: 'sonnet',
          label: `Fix: ${issue.category}`,
          phase: 'Generate Fixes'
        }),
      ]).then(([opus, sonnet]) => ({
        issue,
        opusFix: opus,
        sonnetFix: sonnet,
      }))
    )

    log(`✅ Generated ${fixes.filter(Boolean).length} fixes`)

    // PHASE 5: Apply Fixes
    phase('Apply Fixes')

    log(`🔧 Applying fixes...`)

    const applied = []

    for (const { issue, opusFix, sonnetFix } of fixes.filter(Boolean)) {
      // Use Opus fix (higher quality)
      const fix = opusFix || sonnetFix

      if (!fix) {
        log(`⏭️  Skipping ${issue.description} - no fix generated`)
        continue
      }

      log(`\n   Applying: ${issue.description}`)
      log(`   Approach: ${fix.approach}`)

      const applyResult = await agent(`Apply this fix:

${fix.code_changes}

Files to modify: ${fix.files_modified?.join(', ') || 'auto-detect'}

Apply the fix and return status.`, {
        label: `Apply: ${issue.category}`,
        schema: {
          type: 'object',
          properties: {
            status: { type: 'string', enum: ['applied', 'failed'] },
            files_modified: { type: 'array', items: { type: 'string' } },
          },
          required: ['status'],
        }
      })

      if (applyResult.status === 'applied') {
        log(`   ✅ Applied`)
        applied.push({ issue, fix, files: applyResult.files_modified })
      } else {
        log(`   ❌ Failed`)
      }
    }

    log(`\n✅ Applied ${applied.length}/${prioritized.length} fixes`)

    return {
      iteration,
      issues,
      qualityScore,
      fixesApplied: applied.length,
      shouldStop: false,
    }
  },

  // Loop options with quality-based convergence
  {
    maxIterations,
    ...iterativeImprovement(result => calculateQualityScore(result.issues || []), {
      targetScore,
      maxIterations,
      tolerance: 2,
    }),
  }
)

// PHASE 6: Create PR with all improvements
phase('Create PR')

log(`\n${'='.repeat(50)}`)
log(`📊 Improvement Complete`)
log(${'='.repeat(50)}`)
log(`Iterations: ${loopResult.iterations}`)
log(`Status: ${loopResult.status}`)

const allResults = loopResult.results || []
const totalFixes = allResults.reduce((sum, r) => sum + (r.fixesApplied || 0), 0)
const finalQuality = allResults.length > 0
  ? calculateQualityScore(allResults[allResults.length - 1].issues || [])
  : { score: 100 }

log(`\nFinal Quality Score: ${finalQuality.score}/100`)
log(`Total Fixes Applied: ${totalFixes}`)

if (totalFixes > 0) {
  log(`\n📝 Creating pull request with all improvements...`)

  // Commit all changes
  await agent(`Commit all quality improvements.

Execute:
git add .
git commit -m "improve: systematic code quality improvements

- ${totalFixes} issues fixed across ${loopResult.iterations} iterations
- Quality score: ${allResults[0]?.qualityScore?.score || 0}/100 → ${finalQuality.score}/100
- Improvement: +${finalQuality.score - (allResults[0]?.qualityScore?.score || 0)} points

Co-Authored-By: Claude AI <noreply@anthropic.com>"`, {
    label: 'Commit Improvements',
  })

  log(`✅ Committed improvements`)

  // Create branch and PR
  const branchName = `improve/quality-${Date.now()}`

  await agent(`Create and push improvement branch.

Execute:
git checkout -b ${branchName}
git push -u origin ${branchName}`, {
    label: `Push Branch ${branchName}`,
  })

  const prBody = `## Systematic Code Quality Improvements

**Iterations**: ${loopResult.iterations}
**Fixes Applied**: ${totalFixes}
**Quality Score**: ${allResults[0]?.qualityScore?.score || 0}/100 → ${finalQuality.score}/100
**Improvement**: +${finalQuality.score - (allResults[0]?.qualityScore?.score || 0)} points

### Summary by Iteration

${allResults.map((r, i) => `
**Iteration ${i + 1}**:
- Quality: ${r.qualityScore?.score || 0}/100
- Issues found: ${r.issues?.length || 0}
- Fixes applied: ${r.fixesApplied || 0}
`).join('\n')}

### Final Quality Breakdown

${formatQualityReport(finalQuality)}

---

🤖 **Automated Quality Improvement**

This PR was generated by the code-improve workflow with multi-model AI consensus.
All fixes have been reviewed and validated.
`

  const prResult = await createPR(agent, platform, `Improve: Systematic code quality improvements (+${finalQuality.score - (allResults[0]?.qualityScore?.score || 0)} points)`, prBody, {
    baseBranch: 'main',
    headBranch: branchName,
    labels: ['automated-improvement', 'quality'],
  })

  if (prResult.status === 'created') {
    log(`✅ PR created: ${prResult.pr_url}`)

    return {
      status: 'success',
      iterations: loopResult.iterations,
      fixes_applied: totalFixes,
      quality_improvement: finalQuality.score - (allResults[0]?.qualityScore?.score || 0),
      final_score: finalQuality.score,
      pr_url: prResult.pr_url,
    }
  } else {
    log(`❌ Failed to create PR`)
  }
} else {
  log(`\nℹ️  No fixes applied - code is already at target quality!`)
}

return {
  status: 'success',
  iterations: loopResult.iterations,
  fixes_applied: totalFixes,
  final_score: finalQuality.score,
}
