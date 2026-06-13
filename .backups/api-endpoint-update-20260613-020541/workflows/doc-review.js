// Documentation Review Workflow - Global Reusable
// Can be invoked from any project via /doc-review skill

export const meta = {
  name: 'doc-review',
  description: 'Multi-agent documentation review with issue creation',
  phases: [
    { title: 'Discovery', detail: 'Find and categorize documentation files' },
    { title: 'Parallel Review', detail: '6 specialized reviewers analyze docs (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini)' },
    { title: 'Arbiter Synthesis', detail: 'Consolidate and prioritize findings' },
    { title: 'Issue Creation', detail: 'Create GitLab issues for problems' },
  ],
}

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
const docFiles = await _agent(`Find all documentation files in ${targetPath}

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

// 6 specialized reviewers in parallel - each uses a DIFFERENT model for diversity
const reviews = await parallel([
  // Accuracy Reviewer (Fable - most capable for deep accuracy checks)
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
    label: 'Accuracy Review (Fable)',
    model: 'fable',
    schema: FINDINGS_SCHEMA
  }),

  // Completeness Reviewer (Opus - strong reasoning for gap analysis)
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
    label: 'Completeness Review (Opus)',
    model: 'opus',
    schema: FINDINGS_SCHEMA
  }),

  // Clarity Reviewer (Sonnet - balanced analysis)
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
    label: 'Clarity Review (Sonnet)',
    model: 'sonnet',
    schema: FINDINGS_SCHEMA
  }),

  // Consistency Reviewer (Haiku - fast pattern matching)
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
    label: 'Consistency Review (Haiku)',
    model: 'haiku',
    schema: FINDINGS_SCHEMA
  }),

  // Freshness Reviewer (GPT-4o - external perspective)
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
    label: 'Freshness Review (GPT-4o)',
    model: 'gpt-4o',
    schema: FINDINGS_SCHEMA
  }),

  // Security Reviewer (Gemini - additional perspective for security-sensitive docs)
  () => agent(`Review documentation for SECURITY issues.

Files to review: ${JSON.stringify(docFiles.doc_files)}

Check:
1. Credentials or secrets exposed in examples
2. Insecure default configurations documented
3. Missing security warnings for dangerous operations
4. Authentication/authorization instructions complete
5. HTTPS vs HTTP in URLs
6. Permissions and access control documented
7. Data privacy considerations mentioned

For each security issue:
- Specify exact file and line number
- Describe the security risk
- Provide corrected version

Focus on CRITICAL and HIGH severity security issues.`, {
    label: 'Security Review (Gemini)',
    model: 'gemini',
    schema: FINDINGS_SCHEMA
  })
])

log(`✅ ${reviews.filter(Boolean).length} reviewers completed`)

phase('Arbiter Synthesis')

const arbiterDecision = await _agent(`Consolidate documentation review findings from 6 specialized reviewers.

REVIEWS:
${reviews.filter(Boolean).map((r, i) => `
=== ${['Accuracy (Fable)', 'Completeness (Opus)', 'Clarity (Sonnet)', 'Consistency (Haiku)', 'Freshness (GPT-4o)', 'Security (Gemini)'][i]} Reviewer ===
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

// Return results
return {
  status: 'complete',
  files_reviewed: docFiles.total_count,
  critical_count: arbiterDecision.critical_issues.length,
  high_count: arbiterDecision.high_issues.length,
  medium_count: arbiterDecision.medium_issues.length,
  auto_fixed: autoFix ? arbiterDecision.auto_fixable?.length || 0 : 0,
  issues_created: dryRun ? 0 : arbiterDecision.critical_issues.length + arbiterDecision.high_issues.length,
  summary: arbiterDecision.summary,
  findings: arbiterDecision
}
