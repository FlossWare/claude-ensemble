export const meta = {
  name: 'code-solve',
  description: 'Auto-resolve GitHub/GitLab issues with multi-AI consensus',
  phases: [
    { title: 'Fetch Issue', detail: 'Get issue details from GitHub/GitLab' },
    { title: 'Generate Fixes', detail: 'Multiple AIs propose solutions' },
    { title: 'Select Best', detail: 'Choose best fix via consensus' },
    { title: 'Create PR', detail: 'Generate pull request with fix' },
  ],
}

// Parse arguments
const issueNumber = args?.[0]

if (!issueNumber || issueNumber === 'loop') {
  log('❌ Error: Issue number required')
  log('Usage: code-solve-simple <issue_number>')
  return { status: 'error', message: 'Provide an issue number' }
}

// PHASE 1: Fetch Issue
phase('Fetch Issue')

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

**Issue #${issueNumber}**: ${issueData.title}

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

const arbiterPrompt = `Review these ${validFixes.length} proposed fixes for issue #${issueNumber}: "${issueData.title}"

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

// PHASE 4: Create PR
phase('Create PR')

log('📝 Creating pull request with fix...')

const branchName = `fix/issue-${issueNumber}`

// Create branch
await agent(`Create a new branch for the fix:

git checkout -b ${branchName}`, {
  label: 'Create Branch'
})

log(`✅ Created branch: ${branchName}`)

// Apply the fix
log('Applying fix to codebase...')

await agent(`Apply this fix to the codebase:

**Fix for Issue #${issueNumber}**:
${selectedFix.code_changes}

**Files to modify**: ${selectedFix.files_modified?.join(', ') || 'determine from code_changes'}

1. Make the necessary code changes
2. Stage the changes: git add <files>
3. Commit: git commit -m "fix: resolve issue #${issueNumber} - ${issueData.title}

${selectedFix.approach}

Fixes #${issueNumber}

Co-Authored-By: Claude Code <noreply@anthropic.com>"

Return list of files modified.`, {
  label: 'Apply and Commit Fix',
  schema: {
    type: 'object',
    properties: {
      files_modified: { type: 'array', items: { type: 'string' } },
      status: { type: 'string' }
    }
  }
})

log(`✅ Applied and committed fix`)

// Push branch
await agent(`Push the branch to remote:

git push -u origin ${branchName}`, {
  label: 'Push Branch'
})

log(`✅ Pushed branch: ${branchName}`)

// Create PR
const prBody = `## Fix for Issue #${issueNumber}

**Approach**: ${selectedFix.approach}

**Rationale**: ${selectedFix.rationale}

**Files Modified**:
${selectedFix.files_modified?.map(f => `- ${f}`).join('\n') || '- See commits'}

**Test Plan**:
${selectedFix.test_plan || 'Manual testing required'}

**Confidence**: ${selectedFix.confidence}%

---

🤖 Generated with multi-AI consensus (${validFixes.length} models, ${decision.consensus_score}% agreement)

Closes #${issueNumber}
`

const prResult = await agent(`Create a pull request:

gh pr create \\
  --title "Fix: ${issueData.title}" \\
  --body "${prBody.replace(/"/g, '\\"').replace(/\n/g, '\\n')}" \\
  --base main \\
  --head ${branchName}

Return the PR URL.`, {
  label: 'Create PR',
  schema: {
    type: 'object',
    properties: {
      pr_url: { type: 'string' },
      pr_number: { type: 'number' }
    }
  }
})

log(`✅ PR created: ${prResult.pr_url}`)

// Comment on original issue
await agent(`Post a comment on issue #${issueNumber}:

gh issue comment ${issueNumber} --body "🤖 **Automated Fix Generated**

A fix has been proposed in ${prResult.pr_url}

Please review and merge if acceptable."`, {
  label: 'Comment on Issue'
})

log(`✅ Commented on issue #${issueNumber}`)

return {
  status: 'success',
  issue_number: issueNumber,
  pr_url: prResult.pr_url,
  pr_number: prResult.pr_number,
  fix_approach: selectedFix.approach,
  confidence: selectedFix.confidence,
  consensus_score: decision.consensus_score,
}
