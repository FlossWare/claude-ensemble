export const meta = {
  name: 'code-solve',
  description: 'Auto-resolve GitHub/GitLab issues with multi-AI consensus',
  phases: [
    { title: 'Fetch Issue', detail: 'Get issue details from GitHub/GitLab' },
    { title: 'Generate Fixes', detail: 'Multiple AIs propose solutions' },
    { title: 'Select Best', detail: 'Choose best fix via consensus' },
    { title: 'Apply Fix', detail: 'Apply fix in isolated worktree (parallel-safe)' },
  ],
}

// Parse and validate arguments - default to "all" if no issue number provided
const rawIssueNumber = args?.[0] || 'all'

const solveAll = rawIssueNumber === 'all' || rawIssueNumber === 'loop'
const issueNumber = solveAll ? rawIssueNumber : Number(rawIssueNumber)

// PHASE 1: Fetch Issue(s)
phase('Fetch Issue')

// If solving all issues, get the list and solve each in parallel
if (solveAll) {
  log('📥 Fetching all open issues...')

  const allIssues = await agent(`Get all open GitHub/GitLab issues.

Execute:
gh issue list --state open --json number,title --limit 100

Return the list of issues.`, {
    label: 'Fetch All Issues',
    schema: {
      type: 'object',
      properties: {
        issues: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              number: { type: 'number' },
              title: { type: 'string' }
            }
          }
        }
      }
    }
  })

  const issueNumbers = allIssues.issues?.map(i => i.number) || []

  if (issueNumbers.length === 0) {
    log('✅ No open issues found')
    return { status: 'success', message: 'No open issues to solve' }
  }

  log(`✅ Found ${issueNumbers.length} open issues - solving in parallel...`)

  // Solve each issue in parallel
  const results = await pipeline(
    issueNumbers,
    (num) => workflow({ scriptPath: '/home/sfloess/.claude/workflows/code-solve.js', args: [num] })
  )

  const successful = results.filter(r => r?.status === 'success').length
  log(`✅ Solved ${successful}/${issueNumbers.length} issues`)

  return {
    status: 'success',
    total_issues: issueNumbers.length,
    solved: successful,
    results
  }
}

// Validate numeric issue number
if (isNaN(issueNumber) || issueNumber <= 0) {
  log(`❌ Error: Invalid issue number: "${rawIssueNumber}"`)
  return {
    status: 'error',
    message: `Invalid issue number: "${rawIssueNumber}". Provide a positive integer or omit for all`
  }
}

log(`📥 Fetching issue #${issueNumber}...`)

const issueData = await agent(`Get GitHub issue #${issueNumber} details.

Execute:
gh issue view ${issueNumber} --json number,title,body,author,labels

Return the issue details.`, {
  label: `Fetch Issue #${issueNumber}`,
  schema: {
    type: 'object',
    properties: {
      number: { type: 'number' },
      title: { type: 'string' },
      body: { type: 'string' },
      author: { type: 'object' },
      labels: { type: 'array', items: { type: 'object' } }
    },
    required: ['number', 'title']
  }
})

log(`✅ Issue: "${issueData.title}"`)
log(`   Author: ${issueData.author?.login || 'unknown'}`)

// PHASE 2: Generate Fixes
phase('Generate Fixes')

log('🤖 Generating fixes from multiple AI models...')

const fixSchema = {
  type: 'object',
  properties: {
    approach: { type: 'string', description: 'High-level approach to fix' },
    code_changes: { type: 'string', description: 'Detailed code changes' },
    files_modified: { type: 'array', items: { type: 'string' } },
    rationale: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    test_plan: { type: 'string' },
  },
  required: ['approach', 'code_changes', 'confidence']
}

const fixPrompt = `Generate a fix for this GitHub issue:

**Issue #${issueData.number || issueNumber}**: ${issueData.title}

**Description**:
${issueData.body || 'No description provided'}

Provide:
1. **approach** - High-level fix strategy
2. **code_changes** - Specific code modifications needed
3. **files_modified** - List of files to change
4. **rationale** - Why this fix works
5. **confidence** - Your confidence level (0-100)
6. **test_plan** - How to verify the fix works

Be specific and implementable.`

// Generate fixes from 3 models in parallel
const fixes = await parallel([
  () => agent(fixPrompt, { label: 'Opus Fix', schema: fixSchema, model: 'opus' }),
  () => agent(fixPrompt, { label: 'Sonnet Fix', schema: fixSchema, model: 'sonnet' }),
  () => agent(fixPrompt, { label: 'Haiku Fix', schema: fixSchema, model: 'haiku' }),
])

const validFixes = fixes.filter(Boolean)

if (validFixes.length === 0) {
  log('❌ No valid fixes generated')
  return { status: 'error', message: 'Failed to generate fixes' }
}

log(`✅ Generated ${validFixes.length} fixes`)

// PHASE 3: Select Best Fix
phase('Select Best')

log('⚖️ Selecting best fix via arbiter...')

const arbiterPrompt = `Review these ${validFixes.length} proposed fixes for issue #${issueData.number || issueNumber}: "${issueData.title}"

${validFixes.map((fix, i) => `
**Fix ${i + 1}**:
- Approach: ${fix.approach}
- Confidence: ${fix.confidence}%
- Files: ${fix.files_modified?.join(', ') || 'unspecified'}
- Rationale: ${fix.rationale}
`).join('\n')}

Select the BEST fix based on:
1. Correctness and completeness
2. Confidence level
3. Implementation clarity
4. Minimal risk

Return:
- **selected_index** - Which fix to use (0, 1, or 2)
- **reasoning** - Why this fix is best
- **consensus_score** - Overall confidence in selection (0-100)`

const decision = await agent(arbiterPrompt, {
  label: 'Arbiter Decision',
  model: 'opus',
  schema: {
    type: 'object',
    properties: {
      selected_index: { type: 'number', minimum: 0, maximum: validFixes.length - 1 },
      reasoning: { type: 'string' },
      consensus_score: { type: 'number', minimum: 0, maximum: 100 },
    },
    required: ['selected_index', 'reasoning']
  }
})

const selectedFix = validFixes[decision.selected_index]

log(`✅ Selected Fix #${decision.selected_index + 1}`)
log(`   Reasoning: ${decision.reasoning}`)
log(`   Consensus: ${decision.consensus_score}%`)

// PHASE 4: Apply Fix and Commit
phase('Apply Fix and Commit')

log('📝 Applying fix to codebase...')

// Apply the fix in an isolated worktree to allow parallel runs
// Each agent gets its own working directory
await agent(`Apply this fix to the codebase:

**Fix for Issue #${issueData.number || issueNumber}**:
${selectedFix.code_changes}

**Files to modify**: ${selectedFix.files_modified?.join(', ') || 'determine from code_changes'}

1. Make the necessary code changes
2. Stage the changes: git add <files>
3. Commit: git commit -m "fix: resolve issue #${issueData.number || issueNumber} - ${issueData.title}

${selectedFix.approach}

Fixes #${issueData.number || issueNumber}

Co-Authored-By: Claude Code <noreply@anthropic.com>"

Return list of files modified.`, {
  label: 'Apply and Commit Fix',
  isolation: 'worktree',  // Each parallel run gets its own worktree
  schema: {
    type: 'object',
    properties: {
      files_modified: { type: 'array', items: { type: 'string' } },
      status: { type: 'string' }
    }
  }
})

log(`✅ Applied and committed fix`)

// Get the commit hash
const commitInfo = await agent(`Get the commit hash for the fix:

git log -1 --format="%H %s"

Return the commit hash and message.`, {
  label: 'Get Commit Info',
  schema: {
    type: 'object',
    properties: {
      commit_hash: { type: 'string' },
      commit_message: { type: 'string' }
    }
  }
})

log(`✅ Commit: ${commitInfo.commit_hash}`)

// Close the issue with commit reference
await agent(`Close issue #${issueData.number || issueNumber} with reference to the fix commit.

gh issue close ${issueData.number || issueNumber} --comment "✅ **Fixed in commit ${commitInfo.commit_hash}**

## Solution
${selectedFix.approach}

## Details
**Commit**: ${commitInfo.commit_hash}
**Files Modified**: ${selectedFix.files_modified?.join(', ') || 'See commit'}
**Confidence**: ${selectedFix.confidence}%
**Consensus**: ${decision.consensus_score}% agreement across ${validFixes.length} AI models

## Rationale
${selectedFix.rationale || 'See commit message'}

🤖 Automatically fixed and committed by code-solve workflow"`, {
  label: `Close Issue #${issueData.number || issueNumber}`
})

log(`✅ Closed issue #${issueData.number || issueNumber} with commit ${commitInfo.commit_hash}`)

// Worktree automatically merges changes if successful or cleans up if no changes made

return {
  status: 'success',
  issue_number: issueData.number || issueNumber,
  commit_hash: commitInfo.commit_hash,
  fix_approach: selectedFix.approach,
  confidence: selectedFix.confidence,
  consensus_score: decision.consensus_score,
}
