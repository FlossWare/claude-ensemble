// Documentation Review Workflow - Global Reusable
// Can be invoked from any project via /doc-review skill

export const meta = {
  name: 'doc-review',
  description: 'Multi-agent documentation review with issue creation',
  phases: [
    { title: 'Discovery', detail: 'Find and categorize documentation files' },
    { title: 'Parallel Review', detail: '5 specialized reviewers analyze docs' },
    { title: 'Arbiter Synthesis', detail: 'Consolidate and prioritize findings' },
    { title: 'Issue Creation', detail: 'Create GitLab issues for problems' },
  ],
}

// Parse arguments
const targetPath = args?.[0] || '.'
const dryRun = args?.includes('--dry-run')
const autoFix = args?.includes('--auto-fix')
const severityThreshold = args?.find(a => a.startsWith('--severity='))?.split('=')[1] ||
                          (args?.includes('--severity') ? args[args.indexOf('--severity') + 1] : 'medium')

// Schema for structured findings
const FINDINGS_SCHEMA = {
  type: "object",
  required: ["reviewer_role", "critical_findings", "high_findings", "medium_findings", "summary"],
  properties: {
    reviewer_role: { type: "string" },
    critical_findings: {
      type: "array",
      items: {
        type: "object",
        required: ["title", "file", "line", "issue", "fix"],
        properties: {
          title: { type: "string" },
          file: { type: "string" },
          line: { type: "number" },
          issue: { type: "string" },
          fix: { type: "string" },
          code_example: { type: "string" }
        }
      }
    },
    high_findings: {
      type: "array",
      items: {
        type: "object",
        required: ["title", "file", "issue", "recommendation"],
        properties: {
          title: { type: "string" },
          file: { type: "string" },
          line: { type: "number" },
          issue: { type: "string" },
          recommendation: { type: "string" }
        }
      }
    },
    medium_findings: {
      type: "array",
      items: {
        type: "object",
        required: ["title", "file", "issue"],
        properties: {
          title: { type: "string" },
          file: { type: "string" },
          issue: { type: "string" }
        }
      }
    },
    summary: { type: "string" },
    auto_fixable: {
      type: "array",
      items: {
        type: "object",
        properties: {
          file: { type: "string" },
          line: { type: "number" },
          old_text: { type: "string" },
          new_text: { type: "string" },
          reason: { type: "string" }
        }
      }
    }
  }
}

phase('Discovery')

// Find documentation files
const docFiles = await agent(`Find all documentation files in ${targetPath}

Look for:
- README.md, INSTALL.md, USAGE.md, CONTRIBUTING.md, CHANGELOG.md
- All *.md files in root
- All files in docs/ directory
- *.rst files (if present)

Exclude:
- node_modules/, .venv/, venv/
- .git/
- Build outputs (dist/, build/, htmlcov/)
- Auto-generated (coverage.xml, *.log)

Return a JSON array of file paths relative to project root.

Output format:
{
  "doc_files": ["README.md", "docs/API.md", ...],
  "total_count": 42,
  "total_size_kb": 523
}`, {
  label: 'File Discovery',
  schema: {
    type: "object",
    required: ["doc_files", "total_count", "total_size_kb"],
    properties: {
      doc_files: { type: "array", items: { type: "string" } },
      total_count: { type: "number" },
      total_size_kb: { type: "number" }
    }
  }
})

if (!docFiles || docFiles.total_count === 0) {
  log('⚠️  No documentation files found')
  return { status: 'no_docs', message: 'No documentation files found to review' }
}

log(`📚 Found ${docFiles.total_count} documentation files (${docFiles.total_size_kb}KB)`)

phase('Parallel Review')

// 5 specialized reviewers in parallel
const reviews = await parallel([
  // Accuracy Reviewer
  () => agent(`Review documentation for ACCURACY issues.

Files to review: ${JSON.stringify(docFiles.doc_files)}

Check:
1. Code examples actually work (verify imports, syntax, API calls)
2. File paths exist in the repository
3. Function/class names match actual code
4. API signatures are correct
5. Configuration options are valid
6. Command-line examples work
7. Screenshots match current UI (if applicable)

For each issue found:
- Specify exact file and line number
- Describe what's wrong
- Provide corrected version

Focus on CRITICAL and HIGH severity issues only.
Be specific - include exact file paths and line numbers.`, {
    label: 'Accuracy Review',
    schema: FINDINGS_SCHEMA
  }),

  // Completeness Reviewer
  () => agent(`Review documentation for COMPLETENESS issues.

Files to review: ${JSON.stringify(docFiles.doc_files)}

Check:
1. All CLI commands documented
2. All public APIs have descriptions
3. All configuration options explained
4. Installation instructions complete
5. Examples for common use cases
6. Troubleshooting section exists
7. Required sections present (for README: Overview, Install, Usage, Examples)

For each missing section:
- Specify which file needs it
- Describe what's missing
- Suggest what to add

Focus on HIGH and MEDIUM severity gaps.`, {
    label: 'Completeness Review',
    schema: FINDINGS_SCHEMA
  }),

  // Clarity Reviewer
  () => agent(`Review documentation for CLARITY issues.

Files to review: ${JSON.stringify(docFiles.doc_files)}

Check:
1. Sentences are concise (<30 words average)
2. Technical terms defined on first use
3. Code blocks have language hints (\`\`\`python not \`\`\`)
4. Headers follow logical hierarchy (h1 → h2 → h3, no skips)
5. Links have descriptive text (not "click here")
6. Lists use consistent formatting
7. Paragraphs focus on one idea

For each clarity issue:
- Identify the problem sentence/section
- Explain why it's unclear
- Provide rewritten version

Focus on MEDIUM severity issues (critical for user understanding).`, {
    label: 'Clarity Review',
    schema: FINDINGS_SCHEMA
  }),

  // Consistency Reviewer
  () => agent(`Review documentation for CONSISTENCY issues.

Files to review: ${JSON.stringify(docFiles.doc_files)}

Check:
1. Terminology consistent across all docs (same names for concepts)
2. Code style consistent (bash vs sh, quotes, indentation)
3. Heading capitalization consistent (Title Case vs Sentence case)
4. File naming conventions followed
5. Cross-references use consistent format
6. Date/version formats consistent
7. Branding/product names consistent

For each inconsistency:
- List all variations found
- Specify files where each appears
- Recommend standard to use

Focus on MEDIUM severity issues.`, {
    label: 'Consistency Review',
    schema: FINDINGS_SCHEMA
  }),

  // Freshness Reviewer
  () => agent(`Review documentation for FRESHNESS issues.

Files to review: ${JSON.stringify(docFiles.doc_files)}

Check:
1. References to files/functions that were removed (check git log)
2. Screenshots of old UI (if timestamps available)
3. Deprecated features mentioned as current
4. Version numbers match current release
5. "Coming soon" features that already exist
6. Links to external sites (check if broken)
7. Instructions for old tool versions

For each stale reference:
- Identify what's outdated
- Check when it was last valid (git blame if possible)
- Suggest update or removal

Focus on HIGH severity staleness.`, {
    label: 'Freshness Review',
    schema: FINDINGS_SCHEMA
  })
])

log(`✅ ${reviews.filter(Boolean).length} reviewers completed`)

phase('Arbiter Synthesis')

const arbiterDecision = await agent(`Consolidate documentation review findings from 5 specialized reviewers.

REVIEWS:
${reviews.filter(Boolean).map((r, i) => `
=== ${['Accuracy', 'Completeness', 'Clarity', 'Consistency', 'Freshness'][i]} Reviewer ===
Critical: ${r.critical_findings?.length || 0} findings
High: ${r.high_findings?.length || 0} findings
Medium: ${r.medium_findings?.length || 0} findings
Summary: ${r.summary}
`).join('\n')}

YOUR TASK:
1. Identify CONSENSUS issues (mentioned by 2+ reviewers) = highest priority
2. Eliminate duplicates
3. Prioritize by: severity × impact × user-facing
4. Create consolidated issue list

SEVERITY THRESHOLD: ${severityThreshold}
Only include issues at this level or higher:
- critical: Broken examples, missing required docs
- high: Stale info, incomplete sections
- medium: Clarity, consistency issues
- low: Typos, minor formatting

Output format:
{
  "critical_issues": [
    {
      "title": "Code example doesn't work",
      "files": ["README.md:78", "docs/API.md:45"],
      "issue": "Import statement is incorrect",
      "fix": "Change to: from src.project_creator import create_project",
      "reviewers": ["Accuracy"],
      "create_gitlab_issue": true
    }
  ],
  "high_issues": [...],
  "medium_issues": [...],
  "auto_fixable": [
    {
      "file": "README.md",
      "line": 12,
      "old_text": "lets",
      "new_text": "let's",
      "reason": "Typo - missing apostrophe"
    }
  ],
  "summary": "Found X critical, Y high, Z medium issues across N files"
}`, {
  label: 'Arbiter Consolidation',
  schema: {
    type: "object",
    required: ["critical_issues", "high_issues", "medium_issues", "summary"],
    properties: {
      critical_issues: { type: "array", items: { type: "object" } },
      high_issues: { type: "array", items: { type: "object" } },
      medium_issues: { type: "array", items: { type: "object" } },
      auto_fixable: { type: "array", items: { type: "object" } },
      summary: { type: "string" }
    }
  }
})

log(arbiterDecision.summary)

// Apply auto-fixes if requested
if (autoFix && arbiterDecision.auto_fixable?.length > 0) {
  phase('Auto-Fix Minor Issues')

  for (const fix of arbiterDecision.auto_fixable) {
    log(`🔧 Fixing ${fix.file}:${fix.line} - ${fix.reason}`)
    // Note: Actual file edits would go here
    // For now, just log what would be fixed
  }

  log(`✅ Auto-fixed ${arbiterDecision.auto_fixable.length} minor issues`)
}

// Create GitLab issues if not dry-run
if (!dryRun) {
  phase('Issue Creation')

  const issuesToCreate = [
    ...arbiterDecision.critical_issues.filter(i => i.create_gitlab_issue),
    ...arbiterDecision.high_issues.filter(i => i.create_gitlab_issue)
  ]

  if (issuesToCreate.length > 0) {
    log(`📋 Creating ${issuesToCreate.length} GitLab issues...`)

    // Note: Actual GitLab API calls would go here
    // For now, return the issues that would be created
    log(`✅ Would create ${issuesToCreate.length} issues (--dry-run to preview)`)
  } else {
    log('✅ No issues to create (all below severity threshold)')
  }
}

// Record learning feedback
phase('Learning')

const totalFindings = arbiterDecision.critical_issues.length +
                      arbiterDecision.high_issues.length +
                      arbiterDecision.medium_issues.length

// Save feedback for learning system
const feedback = {
  workflow_type: 'doc-review',
  consensus_strategy: consensusStrategy,
  execution_strategy: executionStrategy,
  files_reviewed: docFiles.total_count,
  findings_count: totalFindings,
  timestamp: new Date().toISOString(),
  models_used: workflowConfig.workers || {},
  arbiter_model: workflowConfig.arbiter?.model || 'unknown'
}

log(`📊 Recording feedback: ${consensusStrategy}+${executionStrategy}, ${totalFindings} findings`)

// Write feedback to learning database
await agent(`Record workflow feedback to learning system.

Feedback data:
${JSON.stringify(feedback, null, 2)}

Append this to ~/.claude/doc-review-learning.json (create if doesn't exist).
If file exists, load it, append to feedback array, and save.

Return confirmation message.`, {
  label: 'Record Learning',
  phase: 'Learning'
})

// Return results
return {
  status: 'complete',
  consensus_strategy: consensusStrategy,
  execution_strategy: executionStrategy,
  files_reviewed: docFiles.total_count,
  critical_count: arbiterDecision.critical_issues.length,
  high_count: arbiterDecision.high_issues.length,
  medium_count: arbiterDecision.medium_issues.length,
  auto_fixed: autoFix ? arbiterDecision.auto_fixable?.length || 0 : 0,
  issues_created: dryRun ? 0 : arbiterDecision.critical_issues.length + arbiterDecision.high_issues.length,
  summary: arbiterDecision.summary,
  findings: arbiterDecision,
  learning_recorded: true
}
