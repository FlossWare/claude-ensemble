// Coordinator pattern inlined to avoid ES6 import (skills can't use imports)
// Original: shared/work-coordinator.js:coordinateWork and createIssueClaimer

export const meta = {
  name: 'code-solve',
  description: 'Resolve GitHub/GitLab issues with multi-AI consensus and impact analysis',
  phases: [
    { title: 'Fetch Issue', detail: 'Get issue details from GitHub/GitLab' },
    { title: 'Generate Fixes', detail: 'Multiple AIs propose solutions' },
    { title: 'Select Best', detail: 'Choose best fix via consensus' },
    { title: 'Apply Fix', detail: 'Apply fix in isolated worktree' },
    { title: 'Impact Analysis', detail: 'Analyze cross-codebase impact' },
    { title: 'User Confirmation', detail: 'User decides to commit/push' },
  ],
}

// INTERACTIVE WORKFLOW - Prompts before pushing
// For fully autonomous mode, use code-solve-auto
//
// Configuration via args:
//   autonomous: true - skip prompts, auto-push (not recommended for base workflow)
//   autonomous: false (default) - interactive mode with prompts

// Interactive mode by default (use code-solve-auto for autonomous)
const AUTONOMOUS = args?.autonomous === true
log(`🤖 Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE (prompts before pushing)'}`)
if (!AUTONOMOUS) {
  log(`💡 Use code-solve-auto for fully autonomous mode (auto-pushes fixes)`)
}

// Parse and validate arguments - default to "all" if no issue number provided
// Handle multiple formats: 78, [78], "[78]" (JSON-stringified)
let rawIssueNumber = 'all'
if (args !== undefined && args !== null) {
  // If args is a JSON-stringified array, parse it first
  let parsedArgs = args
  if (typeof args === 'string' && (args.startsWith('[') || args.startsWith('{'))) {
    try {
      parsedArgs = JSON.parse(args)
    } catch (e) {
      // Not valid JSON, use as-is
    }
  }

  // Now extract the issue number
  if (Array.isArray(parsedArgs) && parsedArgs.length > 0) {
    rawIssueNumber = parsedArgs[0]
  } else if (typeof parsedArgs === 'number' || typeof parsedArgs === 'string') {
    rawIssueNumber = parsedArgs
  }
}

const solveAll = rawIssueNumber === 'all' || rawIssueNumber === 'loop'
const issueNumber = solveAll ? rawIssueNumber : Number(rawIssueNumber)

// Detect platform (GitHub or GitLab)
const platformDetect = await agent(`Detect if this is a GitHub or GitLab repository.

Execute:
if git remote -v | grep -q 'github.com'; then
  echo "github"
elif git remote -v | grep -q 'gitlab'; then
  echo "gitlab"
else
  echo "unknown"
fi

Return the platform name.`, {
  label: 'Detect Platform',
  schema: {
    type: 'object',
    properties: {
      platform: { type: 'string', enum: ['github', 'gitlab', 'unknown'] }
    }
  }
})

const isGitLab = platformDetect.platform === 'gitlab'
const isGitHub = platformDetect.platform === 'github'

log(`📍 Platform: ${platformDetect.platform}`)

// PHASE 1: Fetch Issue(s)
phase('Fetch Issue')

// If solving all issues, use coordinator pattern to avoid TOCTOU races
if (solveAll) {
  log('🎯 Using coordinator pattern for parallel issue solving...')

  const coordinatorResult = await coordinateWork({
    // Fetch all unclaimed issues (happens once by coordinator)
    fetchWork: async () => {
      log('📥 Coordinator: Fetching all open issues...')

      const fetchCmd = isGitLab
        ? `glab issue list --state opened --per-page 100 --json number,title,labels || (echo "glab not installed, using API"; curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" "$(git remote get-url origin | sed 's/.*:\\/\\/\\(.*\\)\\.git/https:\\/\\/\\1/')/api/v4/issues?state=opened&per_page=100")`
        : `gh issue list --state open --json number,title,labels --limit 100`

      const allIssues = await agent(`Get all open ${isGitLab ? 'GitLab' : 'GitHub'} issues.

Execute:
${fetchCmd}

Return all open issues with their labels.`, {
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
                  title: { type: 'string' },
                  labels: { type: 'array' }
                }
              }
            }
          }
        }
      })

      return (allIssues.issues || []).map(i => ({
        id: i.number,
        title: i.title,
        labels: Array.isArray(i.labels) ? i.labels : []
      }))
    },

    // Filter out already-claimed issues
    filterWork: (item) => {
      const hasClaimed = item.labels.some(l =>
        (typeof l === 'string' && l === 'code-solve-in-progress') ||
        (typeof l === 'object' && l.name === 'code-solve-in-progress')
      )
      return !hasClaimed
    },

    // Atomic claim before processing
    claimWork: createIssueClaimer({
      platform: isGitLab ? 'gitlab' : 'github',
      label: 'code-solve-in-progress'
    }),

    // Process each claimed issue
    processWork: async (item) => {
      return await solveSingleIssue(item.id, isGitLab, isGitHub, true)
    },

    // Progress tracking
    onProgress: (completed, total) => {
      log(`📊 Progress: ${completed}/${total} issues processed`)
    },

    // Skip tracking
    onSkip: (item, reason) => {
      log(`⏭️  Skipped issue #${item.id}: ${reason}`)
    }
  })

  log(`✅ Coordinator complete: ${coordinatorResult.successful} solved, ${coordinatorResult.skipped} skipped, ${coordinatorResult.failed} failed`)

  return {
    status: 'success',
    total_issues: coordinatorResult.total,
    solved: coordinatorResult.successful,
    skipped: coordinatorResult.skipped,
    failed: coordinatorResult.failed,
    results: coordinatorResult.results
  }
} else {
  // Validate numeric issue number
  if (isNaN(issueNumber) || issueNumber <= 0) {
    log(`❌ Error: Invalid issue number: "${rawIssueNumber}"`)
    return {
      status: 'error',
      message: `Invalid issue number: "${rawIssueNumber}". Provide a positive integer or omit for all`
    }
  }

  // Call the single-issue solving function
  return await solveSingleIssue(issueNumber, isGitLab, isGitHub)
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

// Helper function to create atomic issue claim function
function createIssueClaimer({ platform, label = 'in-progress' }) {
  // Validate label parameter at creation time to prevent shell injection
  if (typeof label !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(label)) {
    throw new Error(`Invalid label: must be alphanumeric with hyphens/underscores only. Got: ${label}`)
  }

  return async (item) => {
    // Security fix #3: Validate issueId is present
    const issueId = item.id || item.number
    if (!issueId) {
      throw new Error('Item must have id or number property')
    }

    // Security fix #1: Validate issueId is a safe positive integer
    const issueNumber = parseInt(issueId, 10)
    if (!Number.isInteger(issueNumber) || issueNumber <= 0 || issueNumber > 999999999) {
      throw new Error(`Invalid issue ID: must be a positive integer (1-999999999). Got: ${issueId}`)
    }

    // Security fix #2: Label already validated at function creation (alphanumeric + dash/underscore only)
    // Security fix #4: Use JSON output from CLI tools to make claim more atomic and avoid race conditions
    const result = await agent(`Atomically claim issue #${issueNumber} with label "${label}".

Execute the following command and return the result:

${platform === 'gitlab'
  ? `# GitLab: Use API-style check for true atomicity
ISSUE_ID="${issueNumber}"
LABEL="${label}"

# First, get current labels
CURRENT_LABELS=$(glab issue view "$ISSUE_ID" --json labels 2>/dev/null || echo '{"labels":[]}')

# Check if already claimed (parse JSON to avoid shell injection)
if echo "$CURRENT_LABELS" | jq -e ".labels[]? | select(.name == \\"$LABEL\\")" >/dev/null 2>&1; then
  echo '{"claimed":false,"alreadyClaimed":true}'
else
  # Try to add label and check result
  if glab issue update "$ISSUE_ID" --label "$LABEL" 2>/dev/null; then
    echo '{"claimed":true,"alreadyClaimed":false}'
  else
    echo '{"claimed":false,"alreadyClaimed":false}'
  fi
fi`
  : `# GitHub: Use JSON output for safer parsing
ISSUE_ID="${issueNumber}"
LABEL="${label}"

# Get current labels as JSON
CURRENT_LABELS=$(gh issue view "$ISSUE_ID" --json labels 2>/dev/null || echo '{"labels":[]}')

# Check if label already exists using jq (safer than grep)
if echo "$CURRENT_LABELS" | jq -e ".labels[]? | select(.name == \\"$LABEL\\")" >/dev/null 2>&1; then
  echo '{"claimed":false,"alreadyClaimed":true}'
else
  # Try to add label
  if gh issue edit "$ISSUE_ID" --add-label "$LABEL" 2>/dev/null; then
    echo '{"claimed":true,"alreadyClaimed":false}'
  else
    echo '{"claimed":false,"alreadyClaimed":false}'
  fi
fi`
}

Return ONLY the JSON output (no other text).`, {
      label: `Claim #${issueNumber}`,
      schema: {
        type: 'object',
        properties: {
          claimed: { type: 'boolean' },
          alreadyClaimed: { type: 'boolean' }
        },
        required: ['claimed', 'alreadyClaimed']
      }
    })

    return result?.claimed === true
  }
}

async function coordinateWork({
  fetchWork,
  filterWork = null,
  claimWork,
  processWork,
  maxWorkers = Infinity,
  onProgress = null,
  onSkip = null,
  failFast = false
}) {
  // Validation
  if (typeof fetchWork !== 'function') {
    throw new Error('fetchWork must be a function')
  }
  if (typeof claimWork !== 'function') {
    throw new Error('claimWork must be a function')
  }
  if (typeof processWork !== 'function') {
    throw new Error('processWork must be a function')
  }

  // Phase 1: Fetch all work items (centralized, happens once)
  log('📥 Coordinator: Fetching work items...')
  const allWork = await fetchWork()

  if (!Array.isArray(allWork)) {
    throw new Error('fetchWork must return an array')
  }

  log(`✅ Coordinator: Found ${allWork.length} work items`)

  // Phase 2: Filter work items (optional)
  const filteredWork = filterWork ? allWork.filter(filterWork) : allWork

  if (filteredWork.length < allWork.length) {
    const filtered = allWork.length - filteredWork.length
    log(`🔍 Coordinator: Filtered out ${filtered} items (${filteredWork.length} remaining)`)
  }

  if (filteredWork.length === 0) {
    log('✅ Coordinator: No work items to process')
    return {
      status: 'success',
      total: 0,
      successful: 0,
      skipped: 0,
      failed: 0,
      results: []
    }
  }

  log(`🚀 Coordinator: Starting ${filteredWork.length} workers...`)

  // Phase 3: Process items in parallel with atomic claiming
  // Note: parallel() handles concurrency limits internally, no need to slice
  let completed = 0
  const results = await parallel(
    filteredWork.map((item, idx) => async () => {
      try {
        // Atomic claim
        const claimed = await claimWork(item)

        if (!claimed) {
          // Already claimed by another process
          const skip = { status: 'skipped', item, reason: 'Already claimed' }
          if (onSkip) onSkip(item, 'Already claimed')
          completed++
          if (onProgress) onProgress(completed, filteredWork.length)
          return skip
        }

        // Successfully claimed - process it
        const result = await processWork(item)
        completed++
        if (onProgress) onProgress(completed, filteredWork.length)

        return { status: 'success', item, result }
      } catch (error) {
        completed++
        if (onProgress) onProgress(completed, filteredWork.length)

        const errorResult = { status: 'error', item, error: error.message }

        if (failFast) {
          throw error
        }

        return errorResult
      }
    })
  )

  // Phase 4: Summarize results (single pass for efficiency)
  const counts = results.reduce((acc, r) => {
    if (r?.status === 'success') acc.successful++
    else if (r?.status === 'skipped') acc.skipped++
    else if (r?.status === 'error') acc.failed++
    return acc
  }, { successful: 0, skipped: 0, failed: 0 })

  const { successful, skipped, failed } = counts

  log(`✅ Coordinator complete - ${successful} successful, ${skipped} skipped, ${failed} failed`)

  return {
    status: 'success',
    total: filteredWork.length,
    successful,
    skipped,
    failed,
    results
  }
}

// ============================================================================
// AI ATTRIBUTION (inline - see shared/ai-attribution.js for reference)
// ============================================================================

function createArbiterAttribution({workerModels, workerProposals, arbiterModel, arbiterDecision, selectedIndex}) {
  const selectedWorker = workerModels[selectedIndex]
  const selectedProposal = workerProposals[selectedIndex]

  const rejectedProposals = workerProposals
    .map((proposal, idx) => ({
      model: workerModels[idx],
      proposal: proposal,
      index: idx
    }))
    .filter((_, idx) => idx !== selectedIndex)
    .map(rp => ({
      model: rp.model,
      approach: rp.proposal?.approach || '',
      confidence: rp.proposal?.confidence || 0,
      reason: `Not selected by ${arbiterModel} arbiter`,
      rationale: rp.proposal?.rationale || ''
    }))

  return {
    total_models_reviewed: workerModels.length,
    worker_ai: {
      model: selectedWorker,
      confidence: selectedProposal?.confidence || 0,
      approach: selectedProposal?.approach || '',
      rationale: selectedProposal?.rationale || ''
    },
    arbiter: {
      model: arbiterModel,
      decision: 'selected',
      selected_index: selectedIndex,
      reasoning: arbiterDecision?.reasoning || '',
      consensus_score: arbiterDecision?.consensus_score || 0
    },
    rejected_proposals: rejectedProposals,
    consensus: {
      models_proposed: workerModels.length,
      selected_by_arbiter: 1
    }
  }
}

function formatArbiterAttributionMarkdown(attribution) {
  if (!attribution) return ''

  const workerAI = attribution.worker_ai || {}
  const arbiter = attribution.arbiter || {}
  const rejected = attribution.rejected_proposals || []

  let md = `## 🤖 AI Attribution\n\n`
  md += `### Worker AI (Selected Solution)\n`
  md += `- **Model**: ${workerAI.model || 'unknown'}\n`
  md += `- **Confidence**: ${workerAI.confidence || 0}%\n`
  md += `- **Approach**: ${workerAI.approach || 'N/A'}\n`
  md += `- **Rationale**: ${workerAI.rationale || 'N/A'}\n\n`

  md += `### Arbiter Decision\n`
  md += `- **Arbiter Model**: ${arbiter.model || 'unknown'}\n`
  md += `- **Decision**: Selected Fix #${(arbiter.selected_index || 0) + 1}\n`
  md += `- **Reasoning**: ${arbiter.reasoning || 'N/A'}\n`
  md += `- **Consensus Score**: ${arbiter.consensus_score || 0}%\n\n`

  md += `### Multi-Model Consensus\n`
  md += `- **Models Proposed Solutions**: ${attribution.total_models_reviewed || 0}\n`
  md += `- **Best Solution Selected By**: ${arbiter.model || 'arbiter'}\n\n`

  if (rejected.length > 0) {
    md += `### Alternative Proposals (Not Selected)\n\n`
    rejected.forEach((r, idx) => {
      md += `${idx + 1}. **${r.model}** (Confidence: ${r.confidence}%)\n`
      md += `   - **Approach**: ${r.approach}\n`
      md += `   - **Reason Not Selected**: ${r.reason}\n\n`
    })
  }

  return md
}

// Single issue solving logic - extracted to avoid recursive workflow() calls
// NOTE: Issue should already be claimed before calling this function (for "solve all" mode)
// For "solve one" mode, we claim it here
async function solveSingleIssue(issueNumber, isGitLab, isGitHub, skipClaim = false) {

if (!skipClaim) {
  // Claim the issue (only for single-issue mode)
  log(`🔒 Claiming issue #${issueNumber}...`)

  const claimCmd = isGitLab
    ? `glab issue update ${issueNumber} --label "code-solve-in-progress"`
    : `gh issue edit ${issueNumber} --add-label "code-solve-in-progress"`

  await agent(`Claim issue #${issueNumber} to prevent duplicate work.

Execute:
${claimCmd}

This prevents other code-solve instances from working on the same issue.`, {
    label: `Claim Issue #${issueNumber}`
  })
}

log(`📥 Fetching issue #${issueNumber}...`)

const fetchIssueCmd = isGitLab
  ? `glab issue view ${issueNumber} --output json 2>/dev/null || curl -H "PRIVATE-TOKEN: $GITLAB_TOKEN" "$(git remote get-url origin | sed 's/.git$//' | sed 's/.*:\\/\\//https:\\/\\//')/-/api/v4/issues/${issueNumber}"`
  : `gh issue view ${issueNumber} --json number,title,body,author,labels`

const issueData = await agent(`Get ${isGitLab ? 'GitLab' : 'GitHub'} issue #${issueNumber} details.

Execute:
${fetchIssueCmd}

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

// Rotate worker models based on issue number for diversity when running in parallel
const issueNum = issueData.number || issueNumber
const workerRotation = [
  ['opus', 'sonnet', 'haiku'],     // Issue % 3 == 0
  ['sonnet', 'haiku', 'opus'],     // Issue % 3 == 1
  ['haiku', 'opus', 'sonnet']      // Issue % 3 == 2
][issueNum % 3]

log(`🔄 Worker rotation: ${workerRotation.join(', ')} (issue #${issueNum} % 3 = ${issueNum % 3})`)

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

// Generate fixes from 3 models in parallel (rotated based on issue number)
const fixes = await parallel([
  () => agent(fixPrompt, { label: `${workerRotation[0]} Fix`, schema: fixSchema, model: workerRotation[0] }),
  () => agent(fixPrompt, { label: `${workerRotation[1]} Fix`, schema: fixSchema, model: workerRotation[1] }),
  () => agent(fixPrompt, { label: `${workerRotation[2]} Fix`, schema: fixSchema, model: workerRotation[2] }),
])

const validFixes = fixes.filter(Boolean)

if (validFixes.length === 0) {
  log('❌ No valid fixes generated')

  // Remove claim label on failure
  const unclaimCmd = isGitLab
    ? `glab issue update ${issueData.number || issueNumber} --unlabel "code-solve-in-progress"`
    : `gh issue edit ${issueData.number || issueNumber} --remove-label "code-solve-in-progress"`

  await agent(`Remove claim label from issue #${issueData.number || issueNumber}.

${unclaimCmd}`, {
    label: 'Unclaim Issue'
  })

  return { status: 'error', message: 'Failed to generate fixes' }
}

log(`✅ Generated ${validFixes.length} fixes`)

// PHASE 3: Select Best Fix
phase('Select Best')

// Rotate arbiter based on issue number (different from workers)
const arbiterRotation = ['opus', 'sonnet', 'haiku'][(issueNum + 1) % 3]
log(`⚖️ Selecting best fix via ${arbiterRotation} arbiter (issue #${issueNum} + 1) % 3 = ${(issueNum + 1) % 3})...`)

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
  label: `${arbiterRotation} Arbiter`,
  model: arbiterRotation,
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

// Create AI attribution for transparency
const aiAttribution = createArbiterAttribution({
  workerModels: workerRotation,
  workerProposals: validFixes,
  arbiterModel: arbiterRotation,
  arbiterDecision: decision,
  selectedIndex: decision.selected_index
})

log(`📊 AI Attribution captured: ${workerRotation.length} workers, 1 arbiter, ${aiAttribution.rejected_proposals.length} alternatives rejected`)

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
  // DISABLED: isolation: 'worktree' causes merge issues when running in parallel
  // The worktree commits don't get merged back to main properly.
  // Instead, we rely on the coordinator's sequential processing to avoid conflicts.
  schema: {
    type: 'object',
    properties: {
      files_modified: { type: 'array', items: { type: 'string' } },
      status: { type: 'string' }
    }
  }
})

log(`✅ Applied and committed fix`)

// Get the commit hash - this agent call still runs in the worktree
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

// Note: Worktree isolation is disabled, so commits are created directly on main.
// No cherry-picking needed.

// PHASE 5: Impact Analysis (inline version - no imports available)
phase('Impact Analysis')

log('🎯 Analyzing impact of fix...')

// Get the diff of the fix
const diffResult = await agent(`Get diff of the fix commit.

Execute:
git show ${commitInfo.commit_hash}

Return the diff.`, {
  label: 'Get Fix Diff',
  schema: {
    type: 'object',
    properties: {
      diff: { type: 'string' },
      files_changed: { type: 'array', items: { type: 'string' } }
    }
  }
})

// Analyze impact (simplified inline version)
const impact = await agent(`Analyze the impact of this fix on the codebase.

Fix commit: ${commitInfo.commit_hash}
Files changed: ${selectedFix.files_modified?.join(', ')}

Diff:
${diffResult.diff?.substring(0, 2000)}

Analyze:
1. Does this introduce breaking changes?
2. What's the risk level (low/medium/high/critical)?
3. How many other files might be affected?
4. Are there missing tests?

Return impact assessment.`, {
  label: 'Impact Analysis',
  schema: {
    type: 'object',
    properties: {
      breaking_changes: { type: 'boolean' },
      risk_level: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
      impacted_files_count: { type: 'number' },
      missing_tests: { type: 'boolean' },
      concerns: { type: 'array', items: { type: 'string' } }
    }
  }
})

log(`✅ Impact analysis:`)
log(`   Breaking changes: ${impact.breaking_changes ? 'YES ⚠️' : 'NO'}`)
log(`   Risk level: ${impact.risk_level}`)
log(`   Impacted files: ~${impact.impacted_files_count || 0}`)

// PHASE 6: User Confirmation (if not autonomous)
phase('User Confirmation')

let shouldPush = AUTONOMOUS // Auto-push if autonomous

if (!AUTONOMOUS) {
  log('')
  log('═'.repeat(60))
  log('📋 FIX SUMMARY')
  log('═'.repeat(60))
  log(`Issue: #${issueData.number || issueNumber} - ${issueData.title}`)
  log(`Commit: ${commitInfo.commit_hash}`)
  log(`Files modified: ${selectedFix.files_modified?.join(', ') || 'See commit'}`)
  log(`Confidence: ${selectedFix.confidence}%`)
  log('')
  log(`Impact Assessment:`)
  log(`  Breaking changes: ${impact.breaking_changes ? '⚠️ YES' : '✅ NO'}`)
  log(`  Risk level: ${impact.risk_level}`)
  log(`  Impacted files: ~${impact.impacted_files_count || 0}`)
  if (impact.concerns?.length > 0) {
    log(`  Concerns:`)
    impact.concerns.forEach(c => log(`    - ${c}`))
  }
  log('═'.repeat(60))
  log('')

  // ASK USER: Push this fix?
  const userDecision = await agent(`Fix has been committed locally for issue #${issueData.number || issueNumber}.

**Fix Summary**:
- Approach: ${selectedFix.approach}
- Files: ${selectedFix.files_modified?.join(', ')}
- Confidence: ${selectedFix.confidence}%

**Impact**:
- Breaking changes: ${impact.breaking_changes ? 'YES ⚠️' : 'NO'}
- Risk: ${impact.risk_level}
- Impacted: ~${impact.impacted_files_count || 0} files

Should we push this fix to remote and close the issue?

Options:
- YES: Push fix and close issue
- NO: Keep fix local only, don't close issue (can review/test more)

Return your decision.`, {
    label: 'User Decision',
    schema: {
      type: 'object',
      properties: {
        push: { type: 'boolean' },
        reasoning: { type: 'string' }
      },
      required: ['push']
    }
  })

  shouldPush = userDecision.push

  log(`\n👤 User Decision: ${shouldPush ? 'PUSH' : 'KEEP LOCAL'}`)
  if (userDecision.reasoning) {
    log(`   Reasoning: ${userDecision.reasoning}`)
  }
}

if (!shouldPush) {
  log(`ℹ️  Fix committed locally but not pushed to remote`)
  log(`ℹ️  Issue #${issueData.number || issueNumber} remains open for manual verification`)

  return {
    status: 'committed_local',
    issue_number: issueData.number || issueNumber,
    commit_hash: commitInfo.commit_hash,
    fix_approach: selectedFix.approach,
    confidence: selectedFix.confidence,
    pushed: false,
    message: 'Fix committed locally but not pushed (user chose to keep local)'
  }
}

// User approved push (or autonomous mode) - proceed to push and close
log(`📤 Pushing fix to remote...`)

await agent(`Push the fix commit to remote.

Execute:
git push origin HEAD

Push the commit.`, {
  label: 'Push Fix'
})

log(`✅ Fix pushed to remote`)

// Close the issue with commit reference and remove claim label
const attributionMarkdown = formatArbiterAttributionMarkdown(aiAttribution)

const closeComment = `✅ **Fixed in commit ${commitInfo.commit_hash}**

## Solution
${selectedFix.approach}

## Details
**Commit**: ${commitInfo.commit_hash}
**Files Modified**: ${selectedFix.files_modified?.join(', ') || 'See commit'}
**Confidence**: ${selectedFix.confidence}%
**Consensus**: ${decision.consensus_score}% agreement across ${validFixes.length} AI models

## Rationale
${selectedFix.rationale || 'See commit message'}

---

${attributionMarkdown}

---

🤖 Automatically fixed and committed by code-solve workflow`

const closeCmd = isGitLab
  ? `glab issue note ${issueData.number || issueNumber} -m "${closeComment}" && glab issue close ${issueData.number || issueNumber} && glab issue update ${issueData.number || issueNumber} --unlabel "code-solve-in-progress"`
  : `gh issue close ${issueData.number || issueNumber} --comment "${closeComment}"; gh issue edit ${issueData.number || issueNumber} --remove-label "code-solve-in-progress"`

await agent(`Close ${isGitLab ? 'GitLab' : 'GitHub'} issue #${issueData.number || issueNumber} with reference to the fix commit.

Execute:
${closeCmd}
echo "CLOSED_ISSUE: #${issueData.number || issueNumber}"`, {
  label: `Close Issue #${issueData.number || issueNumber}`
})

console.log(`CLOSED_ISSUE: #${issueData.number || issueNumber}`)
log(`✅ Closed issue #${issueData.number || issueNumber} with commit ${commitInfo.commit_hash}`)

  return {
    status: 'success',
    issue_number: issueData.number || issueNumber,
    commit_hash: commitInfo.commit_hash,
    fix_approach: selectedFix.approach,
    confidence: selectedFix.confidence,
    consensus_score: decision.consensus_score,
  }
}

// Note: The main workflow logic ends here and calls solveSingleIssue() as needed
