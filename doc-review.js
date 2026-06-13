/**
 * @returns {{
 *   status: 'completed' | 'sync_failed' | 'no_docs' | 'no_issues' | 'all_rejected' | 'preview_only',
 *   docs_reviewed?: number,
 *   issues_found?: number,
 *   issues_validated?: number,
 *   issues_created?: number,
 *   workers?: number,
 *   arbiter?: string,
 *   platform?: string,
 *   alignment_score?: number,
 *   completeness_score?: number,
 *   quality_score?: number,
 *   message?: string
 * }}
 */
export const meta = {
  name: 'doc-review',
  description: 'Review documentation for code alignment, completeness, and quality via multi-AI consensus',
  phases: [
    { title: 'Sync', detail: 'Sync with remote branch' },
    { title: 'Find Docs', detail: 'Identify documentation files' },
    { title: 'Code Analysis', detail: 'Analyze actual codebase features' },
    { title: 'Multi-AI Review', detail: 'Parallel doc reviews across models' },
    { title: 'Consensus', detail: 'Arbiter validates findings' },
    { title: 'User Confirmation', detail: 'User approves issues to create' },
  ],
}


// INTERACTIVE WORKFLOW - Prompts before creating issues
// For fully autonomous mode, use doc-review-auto

const AUTONOMOUS = args?.autonomous === true
log(`🤖 Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE (prompts before creating issues)'}`)
if (!AUTONOMOUS) {
  log(`💡 Use doc-review-auto for fully autonomous mode (auto-creates issues)`)
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
// PHASE 2: Find Documentation Files
// ============================================================================

phase('Find Docs')

const targetPath = args?.path || args?.[0] || '.'

log(`📂 Target: ${targetPath}`)

const docsToReview = await agent(`Find all documentation files in: ${targetPath}

Look for:
- *.md files (README.md, CONTRIBUTING.md, etc.)
- README* files (README, README.txt, etc.)
- CLAUDE.md
- docs/ directory contents
- API documentation
- Tutorials and guides

Execute appropriate find commands.

Return list of documentation files (exclude node_modules, .git, build artifacts).`, {
  label: 'Find Documentation',
  schema: {
    type: 'object',
    properties: {
      files: { type: 'array', items: { type: 'string' } },
      total: { type: 'number' },
      categories: {
        type: 'object',
        properties: {
          readme: { type: 'number' },
          api_docs: { type: 'number' },
          guides: { type: 'number' },
          other: { type: 'number' }
        }
      }
    }
  }
})

log(`✅ Found ${docsToReview.total} documentation files`)

if (docsToReview.total === 0) {
  log(`⚠️ No documentation files to review`)
  return {
    status: 'no_docs',
    message: 'No documentation files found to review'
  }
}

// ============================================================================
// PHASE 3: Code Analysis
// ============================================================================

phase('Code Analysis')

log('🔍 Analyzing actual codebase features...')

const codebaseAnalysis = await agent(`Analyze the actual codebase to understand what exists.

Look for:
1. Public APIs (exported functions, classes, modules)
2. Configuration options
3. CLI commands
4. Features and capabilities
5. Dependencies and integrations

Execute:
- List source files
- Extract exports/public APIs
- Check package.json for scripts, dependencies
- Identify main entry points

Return a comprehensive feature inventory.`, {
  label: 'Analyze Codebase',
  schema: {
    type: 'object',
    properties: {
      features: { type: 'array', items: { type: 'string' } },
      public_apis: { type: 'array', items: { type: 'string' } },
      cli_commands: { type: 'array', items: { type: 'string' } },
      config_options: { type: 'array', items: { type: 'string' } },
      integrations: { type: 'array', items: { type: 'string' } },
      entry_points: { type: 'array', items: { type: 'string' } }
    }
  }
})

log(`✅ Codebase analyzed`)
log(`   Features: ${codebaseAnalysis.features.length}`)
log(`   Public APIs: ${codebaseAnalysis.public_apis.length}`)
log(`   CLI Commands: ${codebaseAnalysis.cli_commands.length}`)

// ============================================================================
// PHASE 4: Multi-AI Documentation Review
// ============================================================================

phase('Multi-AI Review')

log('🤖 Launching worker models...')

const WORKERS = [
  'opus', 'sonnet', 'haiku'  // Claude models
]

const DOC_REVIEW_SCHEMA = {
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
          category: {
            type: 'string',
            enum: [
              'code-doc-mismatch',
              'missing-feature-doc',
              'outdated-info',
              'missing-examples',
              'unclear-explanation',
              'broken-links',
              'incorrect-code-sample',
              'missing-api-doc',
              'incomplete-guide'
            ]
          },
          impact: { type: 'string' }
        }
      }
    },
    scores: {
      type: 'object',
      properties: {
        alignment: { type: 'number', description: 'Code-doc alignment (0-100)' },
        completeness: { type: 'number', description: 'Documentation completeness (0-100)' },
        quality: { type: 'number', description: 'Overall quality (0-100)' }
      }
    },
    model: { type: 'string' }
  }
}

const reviews = await parallel(WORKERS.map(model => () =>
  agent(`Review documentation files against actual codebase.

Documentation Files: ${docsToReview.files.slice(0, 10).join(', ')}
${docsToReview.total > 10 ? `... and ${docsToReview.total - 10} more` : ''}

Actual Codebase Features:
${JSON.stringify(codebaseAnalysis, null, 2)}

Review for:

1. CODE-DOC ALIGNMENT:
   - Does documentation match actual code?
   - Are examples correct and working?
   - Are API signatures accurate?
   - Are code samples up-to-date?

2. COMPLETENESS:
   - Are all features documented?
   - Are all public APIs documented?
   - Are all CLI commands documented?
   - Are configuration options explained?
   - Are dependencies mentioned?

3. QUALITY:
   - Clarity: Is it easy to understand?
   - Examples: Are there working examples?
   - Accuracy: Is information correct?
   - Organization: Is it well-structured?
   - Links: Do references work?

Provide a score (0-100) for each dimension and list specific issues.

Return structured issue list and scores.`, {
    model,
    schema: DOC_REVIEW_SCHEMA,
    label: `doc-review-${model}`,
    phase: 'Multi-AI Review'
  }).catch(() => null)
))

const validReviews = reviews.filter(Boolean)

log(`✅ ${validReviews.length} models completed review`)

const allIssues = validReviews.flatMap(r => r.issues.map(i => ({ ...i, found_by: r.model })))
const avgScores = {
  alignment: Math.round(validReviews.reduce((sum, r) => sum + (r.scores?.alignment || 0), 0) / validReviews.length),
  completeness: Math.round(validReviews.reduce((sum, r) => sum + (r.scores?.completeness || 0), 0) / validReviews.length),
  quality: Math.round(validReviews.reduce((sum, r) => sum + (r.scores?.quality || 0), 0) / validReviews.length)
}

log(`   Total issues found: ${allIssues.length}`)
log(`   Alignment Score: ${avgScores.alignment}/100`)
log(`   Completeness Score: ${avgScores.completeness}/100`)
log(`   Quality Score: ${avgScores.quality}/100`)

if (allIssues.length === 0) {
  log(`✅ No issues found! Documentation is in great shape.`)
  return {
    status: 'no_issues',
    docs_reviewed: docsToReview.total,
    workers: validReviews.length,
    alignment_score: avgScores.alignment,
    completeness_score: avgScores.completeness,
    quality_score: avgScores.quality
  }
}

// ============================================================================
// PHASE 5: Arbiter Consensus
// ============================================================================

phase('Consensus')

log('👨‍⚖️ Arbiter resolving consensus...')

const consensus = await agent(`Review ${allIssues.length} documentation issues from ${validReviews.length} models.

PROCESS:
1. Group similar issues (same root cause)
2. Count cross-references (how many models found it)
3. Verify against actual code (is it really wrong?)
4. Reject false positives or nitpicks
5. Prioritize by impact on users

ISSUES:
${JSON.stringify(allIssues.slice(0, 100), null, 2)}
${allIssues.length > 100 ? `\n... and ${allIssues.length - 100} more` : ''}

CODEBASE FEATURES:
${JSON.stringify(codebaseAnalysis, null, 2)}

Return final validated issues that genuinely need fixing.`, {
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
            impact: { type: 'string' },
            cross_references: { type: 'number' },
            found_by_models: { type: 'array', items: { type: 'string' } },
            verification: { type: 'string', description: 'How the issue was verified against code' }
          }
        }
      },
      rejected_issues: { type: 'array' },
      arbiter_model: { type: 'string' },
      recommendations: { type: 'array', items: { type: 'string' } }
    }
  },
  label: 'arbiter',
  phase: 'Consensus'
})

log(`✅ Consensus reached`)
log(`   Validated: ${consensus.validated_issues.length}`)
log(`   Rejected: ${consensus.rejected_issues.length}`)

if (consensus.validated_issues.length === 0) {
  log(`ℹ️ All issues rejected by arbiter (likely false positives or nitpicks)`)
  return {
    status: 'all_rejected',
    docs_reviewed: docsToReview.total,
    issues_found: allIssues.length,
    issues_validated: 0,
    alignment_score: avgScores.alignment,
    completeness_score: avgScores.completeness,
    quality_score: avgScores.quality
  }
}

// ============================================================================
// PHASE 6: User Confirmation
// ============================================================================

phase('User Confirmation')

if (!AUTONOMOUS) {
  log('')
  log('═'.repeat(60))
  log('📋 DOCUMENTATION REVIEW RESULTS')
  log('═'.repeat(60))
  log(`Issues found: ${consensus.validated_issues.length}`)
  log(`Docs reviewed: ${docsToReview.total}`)
  log(`Workers: ${validReviews.length}`)
  log('')
  log(`📊 SCORES:`)
  log(`   Alignment:    ${avgScores.alignment}/100 (code-doc match)`)
  log(`   Completeness: ${avgScores.completeness}/100 (feature coverage)`)
  log(`   Quality:      ${avgScores.quality}/100 (clarity & examples)`)
  log('═'.repeat(60))

  // Group issues by category
  const byCategory = {}
  consensus.validated_issues.forEach(issue => {
    if (!byCategory[issue.category]) byCategory[issue.category] = []
    byCategory[issue.category].push(issue)
  })

  Object.entries(byCategory).forEach(([category, issues]) => {
    log(`\n📌 ${category.toUpperCase().replace(/-/g, ' ')} (${issues.length})`)
    issues.slice(0, 3).forEach((issue, idx) => {
      log(`   ${idx + 1}. [${issue.severity}] ${issue.title}`)
      log(`      File: ${issue.file}:${issue.line || '?'}`)
      log(`      Found by: ${issue.found_by_models?.join(', ') || '?'} (${issue.cross_references}x)`)
    })
    if (issues.length > 3) {
      log(`      ... and ${issues.length - 3} more`)
    }
  })

  log('')
  log('═'.repeat(60))

  if (consensus.recommendations?.length > 0) {
    log('\n💡 RECOMMENDATIONS:')
    consensus.recommendations.forEach((rec, idx) => {
      log(`   ${idx + 1}. ${rec}`)
    })
    log('')
  }

  const userDecision = await agent(`Review these documentation issues and decide whether to create them.

Should we create ${consensus.validated_issues.length} documentation issues?

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
      docs_reviewed: docsToReview.total,
      alignment_score: avgScores.alignment,
      completeness_score: avgScores.completeness,
      quality_score: avgScores.quality,
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
  agent(`Create a ${platformDetect.platform} issue for documentation.

Title: ${issue.title}
Description:
${issue.description}

File: ${issue.file}:${issue.line || '?'}
Severity: ${issue.severity}
Category: ${issue.category}
Impact: ${issue.impact || 'Unknown'}
Found by: ${issue.found_by_models?.join(', ') || 'multiple models'}
Verification: ${issue.verification || 'Verified against codebase'}

Execute:
cat > /tmp/issue-body.txt << 'EOF'
${issue.description}

---
**File:** \`${issue.file}:${issue.line || '?'}\`
**Category:** ${issue.category}
**Impact:** ${issue.impact || 'Unknown'}
**Verified by:** ${issue.found_by_models?.join(', ') || 'multiple models'}

${issue.verification || ''}
EOF

${cli} issue create --title "${issue.title}" --body-file /tmp/issue-body.txt --label "documentation,${issue.severity},${issue.category}"

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
log('🎉 DOCUMENTATION REVIEW COMPLETE')
log('═'.repeat(60))
log(`Docs reviewed: ${docsToReview.total}`)
log(`Issues found: ${allIssues.length}`)
log(`Validated: ${consensus.validated_issues.length}`)
log(`Created: ${successfulIssues.length}`)
log('')
log(`📊 FINAL SCORES:`)
log(`   Alignment:    ${avgScores.alignment}/100`)
log(`   Completeness: ${avgScores.completeness}/100`)
log(`   Quality:      ${avgScores.quality}/100`)
log('═'.repeat(60))

const result = {
  status: 'completed',
  docs_reviewed: docsToReview.total,
  issues_found: allIssues.length,
  issues_validated: consensus.validated_issues.length,
  issues_created: successfulIssues.length,
  workers: validReviews.length,
  arbiter: consensus.arbiter_model,
  platform: platformDetect.platform,
  alignment_score: avgScores.alignment,
  completeness_score: avgScores.completeness,
  quality_score: avgScores.quality
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'doc-review',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result
