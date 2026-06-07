export const meta = {
  name: 'code-review',
  description: 'Find issues via multi-AI code review with impact analysis',
  phases: [
    { title: 'Sync', detail: 'Sync with remote branch' },
    { title: 'Find Files', detail: 'Identify files to review' },
    { title: 'Multi-AI Review', detail: 'Parallel reviews across models' },
    { title: 'Consensus', detail: 'Arbiter selects best findings' },
    { title: 'Impact Analysis', detail: 'Detect breaking changes' },
    { title: 'User Confirmation', detail: 'User approves issues to create' },
  ],
}

// INTERACTIVE WORKFLOW - Prompts before creating issues
// For fully autonomous mode, use code-review-auto

const AUTONOMOUS = args?.autonomous === true
log(`🤖 Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE (prompts before creating issues)'}`)
if (!AUTONOMOUS) {
  log(`💡 Use code-review-auto for fully autonomous mode (auto-creates issues)`)
}

// ============================================================================
// PHASE 1: Platform Detection & Sync
// ============================================================================

phase('Sync')

log('🔧 Detecting platform...')

const platformDetect = await agent(`Detect if this is a GitHub or GitLab repository.

Execute:
if git remote -v | grep -q 'github.com'; then
  echo "github"
elif git remote -v | grep -q 'gitlab'; then
  echo "gitlab"
else
  echo "unknown"
fi

Return the platform name and check for CLI tools.`, {
  label: 'Detect Platform',
  schema: {
    type: 'object',
    properties: {
      platform: { type: 'string', enum: ['github', 'gitlab', 'unknown'] },
      cli: { type: 'string' }
    }
  }
})

const isGitLab = platformDetect.platform === 'gitlab'

log(`✅ Platform: ${platformDetect.platform}`)
log('🔄 Syncing with remote...')

const syncResult = await agent(`Sync with remote repository.

Execute:
git fetch origin
git rebase origin/main || git rebase origin/master

Return sync status.`, {
  label: 'Sync with Remote',
  schema: {
    type: 'object',
    properties: {
      status: { type: 'string', enum: ['success', 'conflicts', 'failed', 'up_to_date'] },
      message: { type: 'string' }
    }
  }
})

if (syncResult.status === 'conflicts' || syncResult.status === 'failed') {
  log(`❌ Sync failed: ${syncResult.message}`)
  return {
    status: 'sync_failed',
    message: syncResult.message
  }
}

log(`✅ Synced: ${syncResult.status}`)

// ============================================================================
// PHASE 2: Find Files to Review
// ============================================================================

phase('Find Files')

const targetPath = args?.path || args?.[0] || '.'

log(`📂 Target: ${targetPath}`)

const filesToReview = await agent(`Find files to review in: ${targetPath}

If it's a directory, find all code files recursively.
If it's a file, review just that file.

Execute appropriate find/ls commands.

Return list of files to review (exclude node_modules, .git, build artifacts).`, {
  label: 'Find Files',
  schema: {
    type: 'object',
    properties: {
      files: { type: 'array', items: { type: 'string' } },
      total: { type: 'number' }
    }
  }
})

log(`✅ Found ${filesToReview.total} files`)

if (filesToReview.total === 0) {
  log(`⚠️ No files to review`)
  return {
    status: 'no_files',
    message: 'No files found to review'
  }
}

// ============================================================================
// PHASE 3: Multi-AI Review
// ============================================================================

phase('Multi-AI Review')

log('🤖 Launching worker models...')

const WORKERS = [
  'opus', 'sonnet', 'haiku'  // Claude models
]

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          description: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'number' },
          severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
          category: { type: 'string', enum: ['bug', 'security', 'performance', 'style', 'maintainability', 'documentation'] }
        }
      }
    },
    model: { type: 'string' }
  }
}

const reviews = await parallel(WORKERS.map(model => () =>
  agent(`Review these files for issues:

Files: ${filesToReview.files.slice(0, 20).join(', ')}
${filesToReview.total > 20 ? `... and ${filesToReview.total - 20} more` : ''}

Look for:
- Bugs and logical errors
- Security vulnerabilities
- Performance issues
- Code style/maintainability problems
- Missing documentation

Return structured issue list.`, {
    model,
    schema: REVIEW_SCHEMA,
    label: `review-${model}`,
    phase: 'Multi-AI Review'
  }).catch(() => null)
))

const validReviews = reviews.filter(Boolean)

log(`✅ ${validReviews.length} models completed review`)

const allIssues = validReviews.flatMap(r => r.issues.map(i => ({ ...i, found_by: r.model })))

log(`   Total issues found: ${allIssues.length}`)

if (allIssues.length === 0) {
  log(`✅ No issues found!`)
  return {
    status: 'no_issues',
    files_reviewed: filesToReview.total,
    workers: validReviews.length
  }
}

// ============================================================================
// PHASE 4: Arbiter Consensus
// ============================================================================

phase('Consensus')

log('👨‍⚖️ Arbiter resolving consensus...')

const consensus = await agent(`Review ${allIssues.length} issues from ${validReviews.length} models.

PROCESS:
1. Group similar issues (same root cause)
2. Count cross-references (how many models found it)
3. Resolve conflicts
4. Reject false positives
5. Prioritize by severity and impact

ISSUES:
${JSON.stringify(allIssues.slice(0, 100), null, 2)}
${allIssues.length > 100 ? `\n... and ${allIssues.length - 100} more` : ''}

Return final validated issues.`, {
  model: 'opus',
  schema: {
    type: 'object',
    properties: {
      validated_issues: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            title: { type: 'string' },
            description: { type: 'string' },
            file: { type: 'string' },
            line: { type: 'number' },
            severity: { type: 'string' },
            category: { type: 'string' },
            cross_references: { type: 'number' },
            found_by_models: { type: 'array', items: { type: 'string' } }
          }
        }
      },
      rejected_issues: { type: 'array' },
      arbiter_model: { type: 'string' }
    }
  },
  label: 'arbiter',
  phase: 'Consensus'
})

log(`✅ Consensus reached`)
log(`   Validated: ${consensus.validated_issues.length}`)
log(`   Rejected: ${consensus.rejected_issues.length}`)

if (consensus.validated_issues.length === 0) {
  log(`ℹ️ All issues rejected by arbiter (likely false positives)`)
  return {
    status: 'all_rejected',
    files_reviewed: filesToReview.total,
    raw_issues: allIssues.length,
    validated: 0
  }
}

// ============================================================================
// PHASE 5: Impact Analysis
// ============================================================================

phase('Impact Analysis')

log('🎯 Analyzing code impact...')

const impactAnalysis = await agent(`Analyze the impact of creating these issues.

Check if fixing these issues might:
1. Break other parts of the codebase
2. Require changes across multiple files
3. Affect public APIs or exports

Issues to analyze:
${JSON.stringify(consensus.validated_issues.slice(0, 20), null, 2)}

Return impact analysis.`, {
  schema: {
    type: 'object',
    properties: {
      high_impact: { type: 'array', items: { type: 'string' } },
      breaking_changes_possible: { type: 'boolean' },
      affected_areas: { type: 'array', items: { type: 'string' } },
      recommendations: { type: 'array', items: { type: 'string' } }
    }
  },
  label: 'impact-analysis',
  phase: 'Impact Analysis'
})

log(`✅ Impact analyzed`)
if (impactAnalysis.breaking_changes_possible) {
  log(`   ⚠️ Breaking changes possible`)
}
log(`   Affected areas: ${impactAnalysis.affected_areas.length}`)

// ============================================================================
// PHASE 6: User Confirmation
// ============================================================================

phase('User Confirmation')

if (!AUTONOMOUS) {
  log('')
  log('═'.repeat(60))
  log('📋 REVIEW RESULTS')
  log('═'.repeat(60))
  log(`Issues found: ${consensus.validated_issues.length}`)
  log(`Files reviewed: ${filesToReview.total}`)
  log(`Workers: ${validReviews.length}`)
  log('═'.repeat(60))
  
  consensus.validated_issues.slice(0, 5).forEach((issue, idx) => {
    log(`${idx + 1}. [${issue.severity}] ${issue.title}`)
    log(`   File: ${issue.file}:${issue.line || '?'}`)
    log(`   Category: ${issue.category}`)
    log(`   Found by: ${issue.found_by_models?.join(', ') || '?'} (${issue.cross_references}x)`)
    log('')
  })
  
  if (consensus.validated_issues.length > 5) {
    log(`... and ${consensus.validated_issues.length - 5} more issues`)
  }
  
  log('═'.repeat(60))
  log('')

  const userDecision = await agent(`Review these issues and decide whether to create them.

Should we create ${consensus.validated_issues.length} issues?

Options:
- YES: Create all issues
- SELECTIVE: I'll choose which ones to create
- NO: Don't create any issues

Return your decision.`, {
    label: 'User Decision',
    schema: {
      type: 'object',
      properties: {
        action: { type: 'string', enum: ['YES', 'SELECTIVE', 'NO'] },
        selected_indices: { type: 'array', items: { type: 'number' } },
        reasoning: { type: 'string' }
      },
      required: ['action']
    }
  })

  log(`\n👤 User Decision: ${userDecision.action}`)

  if (userDecision.action === 'NO') {
    log(`ℹ️ No issues created (user chose NO)`)
    return {
      status: 'preview_only',
      issues_found: consensus.validated_issues.length,
      files_reviewed: filesToReview.total,
      message: 'Issues found but not created'
    }
  }

  if (userDecision.action === 'SELECTIVE' && userDecision.selected_indices) {
    const selectedIssues = userDecision.selected_indices.map(i => consensus.validated_issues[i])
    consensus.validated_issues = selectedIssues.filter(Boolean)
    log(`✏️ Creating ${consensus.validated_issues.length} selected issues`)
  }
}

// ============================================================================
// Create Issues
// ============================================================================

log('🚀 Creating issues...')

const cli = isGitLab ? 'glab' : 'gh'

const createdIssues = await parallel(consensus.validated_issues.map(issue => () =>
  agent(`Create a ${platformDetect.platform} issue.

Title: ${issue.title}
Description:
${issue.description}

File: ${issue.file}:${issue.line || '?'}
Severity: ${issue.severity}
Category: ${issue.category}
Found by: ${issue.found_by_models?.join(', ') || 'multiple models'}

Execute:
echo "${issue.description}" > /tmp/issue-body.txt
${cli} issue create --title "${issue.title}" --body-file /tmp/issue-body.txt --label "code-review,${issue.severity},${issue.category}"

Return issue URL.`, {
    label: `create-issue:${issue.file}`,
    schema: {
      type: 'object',
      properties: {
        issue_url: { type: 'string' },
        issue_number: { type: 'number' },
        status: { type: 'string' }
      }
    }
  }).catch(() => null)
))

const successfulIssues = createdIssues.filter(Boolean)

log(`✅ Created ${successfulIssues.length}/${consensus.validated_issues.length} issues`)

log('')
log('═'.repeat(60))
log('🎉 CODE REVIEW COMPLETE')
log('═'.repeat(60))
log(`Files reviewed: ${filesToReview.total}`)
log(`Issues found: ${allIssues.length}`)
log(`Validated: ${consensus.validated_issues.length}`)
log(`Created: ${successfulIssues.length}`)
log('═'.repeat(60))

const result = {
  status: 'completed',
  files_reviewed: filesToReview.total,
  issues_found: allIssues.length,
  issues_validated: consensus.validated_issues.length,
  issues_created: successfulIssues.length,
  workers: validReviews.length,
  arbiter: consensus.arbiter_model,
  platform: platformDetect.platform,
  impact_analysis: impactAnalysis
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'code-review',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result
