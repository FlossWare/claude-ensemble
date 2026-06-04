// Code Solve - Auto-Resolve GitHub/GitLab Issues
// Uses shared consensus engine for multi-model fix generation
// Review-only mode by default: creates PRs, doesn't push directly

import { ISSUE_SCHEMA, FIX_SCHEMA, ARBITER_SCHEMA } from './shared/schemas.js'
import { multiModelReview, arbiterDecision } from './shared/consensus-engine.js'
import { formatAIAttribution } from './shared/ai-attribution.js'
import { detectPlatform, syncWithRemote, fetchIssue, createPR, postComment } from './shared/platform-detector.js'
import { continuousMonitor } from './shared/loop-controller.js'

export const meta = {
  name: 'code-solve',
  description: 'Auto-resolve GitHub/GitLab issues with multi-model consensus',
  whenToUse: 'When user wants to automatically fix issues with AI',
  phases: [
    { title: 'Setup', detail: 'Detect platform and sync' },
    { title: 'Fetch Issue', detail: 'Get issue details' },
    { title: 'Generate Fixes', detail: 'Opus, Sonnet, Haiku propose solutions', model: 'opus' },
    { title: 'Arbiter Decision', detail: 'Select best fix' },
    { title: 'Create PR', detail: 'Generate pull request with fix' },
  ],
}

// Parse arguments
const issueNumber = args?.[0]
const isLoopMode = issueNumber === 'loop' || args?.loop
const shouldCreatePR = args?.['create-pr'] !== false // Default: true
const applyDirectly = args?.apply || args?.['--apply'] // Default: false (review-only)

// Validation
if (!isLoopMode && !issueNumber) {
  log('❌ Error: Issue number required')
  log('Usage: /code-solve <issue_number> [--create-pr] [--apply]')
  log('   or: /code-solve loop')
  return { status: 'error', message: 'Issue number required' }
}

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

// Loop mode or single issue
if (isLoopMode) {
  log('🔄 Starting continuous issue resolution...')

  const monitorResult = await continuousMonitor(
    // Check function: fetch open issues
    async (run) => {
      log('📋 Checking for open issues...')

      const result = await agent(`List all open issues.

Platform: ${platform.platform}
CLI: ${platform.cli}

Execute:
${platform.cli} issue list --json number,title,labels,state --limit 50

Return array of issue numbers that are:
- Open
- Not already being worked on (check for PR references)
- Labeled as 'bug' or 'enhancement' (priority)

Sort by priority: bugs first, then enhancements.`, {
        label: 'List Open Issues',
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
                  priority: { type: 'number' },
                },
                required: ['number', 'priority']
              }
            }
          },
          required: ['issues']
        }
      })

      return result.issues
        .sort((a, b) => b.priority - a.priority)
        .slice(0, 3) // Resolve max 3 issues per iteration
        .map(i => i.number)
    },

    // Action function: resolve issues
    async (issueNumbers) => {
      const results = []

      for (const num of issueNumbers) {
        log(`\n═══ Resolving Issue #${num} ═══`)

        const resolveResult = await resolveSingleIssue(num, platform, shouldCreatePR, applyDirectly)
        results.push(resolveResult)
      }

      return results
    },

    {
      interval: 600000, // 10 minutes
      maxRuns: Infinity,
      stopOnNoWork: true,
    }
  )

  return monitorResult

} else {
  // Single issue resolution
  return await resolveSingleIssue(issueNumber, platform, shouldCreatePR, applyDirectly)
}

// Helper function to resolve a single issue
async function resolveSingleIssue(num, platform, shouldCreatePR, applyDirectly) {
  // PHASE 2: Fetch Issue
  phase('Fetch Issue')

  log(`📥 Fetching issue #${num}...`)
  const issue = await fetchIssue(agent, platform, num)
  log(`✅ Issue: "${issue.title}"`)
  log(`   Author: ${issue.author}`)
  log(`   Labels: ${issue.labels?.join(', ') || 'none'}`)

  // PHASE 3: Generate Fixes
  phase('Generate Fixes')

  log('🤖 Generating fixes with multi-model consensus...')

  const fixPrompt = `Generate a fix for this issue:

**Issue #${num}**: ${issue.title}

**Description**:
${issue.body || 'No description'}

**Labels**: ${issue.labels?.join(', ') || 'none'}

Analyze the issue and provide:
1. Approach - How to fix this issue
2. Code changes - Actual code/files to modify
3. Files modified - List of files that will change
4. Rationale - Why this fix works
5. Confidence - How confident you are (0-100)
6. Risks - Potential issues with this fix
7. Test plan - How to verify the fix

Provide a complete, implementable solution.`

  const fixes = await multiModelReview(fixPrompt, FIX_SCHEMA, {
    phase: 'Generate Fixes',
    labelPrefix: `Issue #${num}`,
    includeGemini: false,
  })

  log(`✅ Generated fixes from ${fixes.allReviews.length} models`)

  // PHASE 4: Arbiter Decision
  phase('Arbiter Decision')

  log('⚖️ Arbiter selecting best fix...')

  const decision = await arbiterDecision(
    `Issue #${num}: "${issue.title}"`,
    fixes,
    {
      decisionType: 'fix',
      phase: 'Arbiter Decision',
    }
  )

  log(`✅ Selected: ${decision.accepted_model}'s fix (${decision.consensus_score}% consensus)`)

  // Get the accepted fix
  const acceptedFix = fixes[decision.accepted_model.toLowerCase()]

  if (!acceptedFix || !acceptedFix.code_changes) {
    log('❌ No valid fix selected')
    return {
      status: 'failed',
      issue_number: num,
      reason: 'No valid fix generated'
    }
  }

  log(`📝 Fix approach: ${acceptedFix.approach}`)
  log(`📂 Files to modify: ${acceptedFix.files_modified?.join(', ') || 'unspecified'}`)

  // PHASE 5: Apply Fix and Create PR
  phase('Create PR')

  if (applyDirectly) {
    log('⚠️ APPLY MODE: Applying fix directly to codebase...')

    // Apply the fix
    const applyResult = await agent(`Apply this fix to the codebase:

**Fix for Issue #${num}**:
${acceptedFix.code_changes}

**Files to modify**: ${acceptedFix.files_modified?.join(', ') || 'determine from code_changes'}

Apply these changes to the appropriate files.
Create/modify files as needed.
Return list of files actually modified.`, {
      label: `Apply Fix #${num}`,
      schema: {
        type: 'object',
        properties: {
          files_modified: { type: 'array', items: { type: 'string' } },
          status: { type: 'string', enum: ['applied', 'failed'] },
          message: { type: 'string' },
        },
        required: ['status'],
      }
    })

    if (applyResult.status === 'failed') {
      log(`❌ Failed to apply fix: ${applyResult.message}`)
      return {
        status: 'failed',
        issue_number: num,
        reason: applyResult.message
      }
    }

    log(`✅ Applied fix to ${applyResult.files_modified?.length || 0} files`)

    // Commit the changes
    await agent(`Commit the fix for issue #${num}.

Execute:
git add ${applyResult.files_modified?.join(' ') || '.'}
git commit -m "fix: resolve issue #${num} - ${issue.title}

${acceptedFix.approach}

Fixes #${num}

Co-Authored-By: Claude AI <noreply@anthropic.com>"`, {
      label: `Commit Fix #${num}`,
    })

    log(`✅ Committed fix for issue #${num}`)
  }

  if (shouldCreatePR) {
    log('📝 Creating pull request...')

    // Create branch for the fix
    const branchName = `fix/issue-${num}`

    await agent(`Create a new branch for the fix.

Execute:
git checkout -b ${branchName}`, {
      label: `Create Branch ${branchName}`,
    })

    if (!applyDirectly) {
      // Apply the fix (if not already applied)
      log('Applying fix to branch...')

      const applyResult = await agent(`Apply this fix to the codebase:

**Fix for Issue #${num}**:
${acceptedFix.code_changes}

Apply and commit the changes.`, {
        label: `Apply Fix #${num}`,
      })

      log(`✅ Applied and committed fix`)
    }

    // Push branch
    await agent(`Push the fix branch.

Execute:
git push -u origin ${branchName}`, {
      label: `Push Branch ${branchName}`,
    })

    log(`✅ Pushed branch ${branchName}`)

    // Create PR body with AI attribution
    const attribution = formatAIAttribution(fixes, decision, {
      includeVerboseDetails: true,
    })

    const prBody = `## Fix for Issue #${num}

**Approach**: ${acceptedFix.approach}

**Rationale**: ${acceptedFix.rationale}

**Files Modified**:
${acceptedFix.files_modified?.map(f => `- ${f}`).join('\n') || '- (see commits)'}

**Test Plan**:
${acceptedFix.test_plan || 'Manual testing required'}

**Risks**:
${acceptedFix.risks && acceptedFix.risks.length > 0
  ? acceptedFix.risks.map(r => `- ${r}`).join('\n')
  : '- None identified'}

---

${attribution}

Closes #${num}
`

    // Create the PR
    const prResult = await createPR(agent, platform, `Fix: ${issue.title}`, prBody, {
      baseBranch: 'main',
      headBranch: branchName,
      labels: ['automated-fix', 'ai-generated'],
    })

    if (prResult.status === 'created') {
      log(`✅ PR created: ${prResult.pr_url}`)

      // Post comment on original issue
      await postComment(agent, platform, 'issue', num,
        `🤖 **Automated Fix Generated**\n\nA fix has been proposed in ${prResult.pr_url}\n\nPlease review and merge if acceptable.`
      )

      log(`✅ Commented on issue #${num}`)

      return {
        status: 'success',
        issue_number: num,
        pr_url: prResult.pr_url,
        pr_number: prResult.pr_number,
        fix_approach: acceptedFix.approach,
        confidence: acceptedFix.confidence,
      }
    } else {
      log(`❌ Failed to create PR`)
      return {
        status: 'failed',
        issue_number: num,
        reason: 'PR creation failed'
      }
    }
  } else {
    log('ℹ️ Skipping PR creation (use --create-pr to create)')
    return {
      status: 'fix_generated',
      issue_number: num,
      fix_approach: acceptedFix.approach,
      confidence: acceptedFix.confidence,
    }
  }
}
