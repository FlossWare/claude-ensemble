import { coordinateWork, createIssueClaimer } from '../shared/work-coordinator.js'

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'code-solve',
  description: 'Auto-resolve GitHub/GitLab issues with multi-AI consensus (AUTONOMOUS)',
  phases: [
    { title: 'Discovery', detail: 'Discover available AI models' },
    { title: 'Fetch Issue', detail: 'Get issue details from GitHub/GitLab' },
    { title: 'Generate Fixes', detail: 'Multiple AIs propose solutions' },
    { title: 'Select Best', detail: 'Choose best fix via consensus' },
    { title: 'Apply Fix', detail: 'Apply fix in isolated worktree (parallel-safe)' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// AUTONOMOUS WORKFLOW - No user prompts or confirmations
// This workflow is designed for automated/background execution
// It must complete without user interaction
//
// Configuration via args:
//   autonomous: true (default) - no prompts, auto-commit, auto-close
//   autonomous: false - interactive mode (future enhancement)
//   strategy: 'maximum-coverage' | 'quality-first' | 'cost-optimized' | 'speed-optimized' | 'balanced' (default: maximum-coverage)

// ============================================================================
// MULTI-MODEL STRATEGY PATTERN
// ============================================================================

/**
 * Multi-model selection strategy interface
 */
class ModelStrategy {
  constructor(availableModels = null) {
    this.availableModels = availableModels
  }

  getWorkerModels() {
    throw new Error('Must implement getWorkerModels()')
  }

  getArbiterFallback() {
    throw new Error('Must implement getArbiterFallback()')
  }

  getPreferredArbiter() {
    return this.getArbiterFallback()[0]
  }

  filterAvailable(models) {
    if (!this.availableModels) return models
    return models.filter(m => this.availableModels.includes(m))
  }
}

class QualityFirstStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }

  getArbiterFallback() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }
}

class CostOptimizedStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['sonnet', 'haiku', 'gemini', 'gpt-4o']
    return this.filterAvailable(ideal)
  }

  getArbiterFallback() {
    const ideal = ['sonnet', 'haiku', 'opus', 'fable', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }
}

class BalancedStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }

  getArbiterFallback() {
    const ideal = ['opus', 'fable', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }
}

class MaximumCoverageStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }

  getArbiterFallback() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }
}

class QuantizedStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['ollama/llama3', 'ollama/mistral', 'ollama/codellama', 'haiku', 'sonnet']
    return this.filterAvailable(ideal)
  }

  getArbiterFallback() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }
}

class QuintupleVerificationStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }

  getArbiterFallback() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    return this.filterAvailable(ideal)
  }

  getVerificationStages() {
    return {
      propose: { models: this.getWorkerModels(), phase: 'Propose Solutions' },
      review: { models: this.getWorkerModels(), phase: 'Peer Review' },
      verify: { models: this.getWorkerModels(), phase: 'Adversarial Verification' },
      validate: { models: ['opus', 'sonnet'], phase: 'Integration Validation' },
      confirm: { models: this.getArbiterFallback(), phase: 'Final Confirmation' }
    }
  }
}

const STRATEGIES = {
  'quality-first': QualityFirstStrategy,
  'cost-optimized': CostOptimizedStrategy,
  'balanced': BalancedStrategy,
  'maximum-coverage': MaximumCoverageStrategy,
  'quantized': QuantizedStrategy,
  'quintuple-verification': QuintupleVerificationStrategy,
}

/**
 * Discover available models dynamically
 */
async function discoverAvailableModels() {
  const ALL_MODELS = [
    'fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini',
    // Ollama local models
    'ollama/llama3', 'ollama/llama3:70b',
    'ollama/codestral', 'ollama/deepseek-coder', 'ollama/deepseek-coder:33b',
    'ollama/qwen2.5-coder', 'ollama/qwen2.5-coder:14b'
  ]
  const available = []

  for (const model of ALL_MODELS) {
    try {
      await _agent('test', {
        model,
        schema: {type: 'object', properties: {ok: {type: 'boolean'}}, required: ['ok']}
      })
      available.push(model)
      log(`✓ ${model} available`)
    } catch (e) {
      log(`✗ ${model} unavailable`)
    }
  }

  return available
}

/**
 * Run arbiter with fallback chain
 */
async function runArbiterWithFallback(prompt, strategy, label = 'Arbiter') {
  const fallbackChain = strategy.getArbiterFallback()

  for (const model of fallbackChain) {
    try {
      const decision = await _agent(prompt, {
        model,
        phase: 'Select Best',
        label: `${model} ${label}`,
        schema: {
          type: 'object',
          properties: {
            selected_index: { type: 'number' },
            reasoning: { type: 'string' },
            consensus_score: { type: 'number', minimum: 0, maximum: 100 },
          },
          required: ['selected_index', 'reasoning']
        }
      })
      return { decision, usedModel: model }
    } catch (e) {
      log(`⚠ ${model} arbiter failed: ${e.message}, trying next fallback`)
    }
  }

  throw new Error('All arbiter models failed')
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
      consensus_score: arbiterDecision?.consensus_score || 0,
      timestamp: new Date().toISOString()
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
  md += `- **Consensus Score**: ${arbiter.consensus_score || 0}%\n`
  md += `- **Timestamp**: ${arbiter.timestamp || 'N/A'}\n\n`

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

// Autonomous mode (default: true) - can be overridden via args.autonomous
const AUTONOMOUS = args?.autonomous !== false
log(`🤖 Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)

// PHASE 0: Model Discovery
phase('Discovery')
log('🔍 Discovering available AI models...')

const availableModels = await discoverAvailableModels()
if (availableModels.length === 0) {
  log('❌ FATAL: No AI models available. Check API keys and model access.')
  return { status: 'error', message: 'No AI models available' }
}
log(`✅ Available models: ${availableModels.join(', ')}`)

// Initialize strategy
const strategyName = args?.strategy || 'maximum-coverage'
const StrategyClass = STRATEGIES[strategyName] || MaximumCoverageStrategy
const strategy = new StrategyClass(availableModels)

log(`📊 Strategy: ${strategyName}`)
log(`   Workers: ${strategy.getWorkerModels().join(', ')}`)
log(`   Arbiter fallback: ${strategy.getArbiterFallback().join(', ')}`)

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
const platformDetect = await _agent(`Detect if this is a GitHub or GitLab repository.

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

      const allIssues = await _agent(`Get all open ${isGitLab ? 'GitLab' : 'GitHub'} issues.

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
        labels: i.labels || []
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

// Single issue solving logic - extracted to avoid recursive workflow() calls
// NOTE: This function handles claiming internally unless skipClaim=true (used by "solve all" mode where claiming happens earlier)
async function solveSingleIssue(issueNumber, isGitLab, isGitHub, skipClaim = false) {

if (!skipClaim) {
  // Claim the issue (only for single-issue mode)
  log(`🔒 Claiming issue #${issueNumber}...`)

  const claimCmd = isGitLab
    ? `glab issue update ${issueNumber} --label "code-solve-in-progress"`
    : `gh issue edit ${issueNumber} --add-label "code-solve-in-progress"`

  await _agent(`Claim issue #${issueNumber} to prevent duplicate work.

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

const issueData = await _agent(`Get ${isGitLab ? 'GitLab' : 'GitHub'} issue #${issueNumber} details.

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

// Use strategy to get worker models
const workerModels = strategy.getWorkerModels()
log(`🔄 Worker models: ${workerModels.join(', ')} (${workerModels.length} models)`)

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

// Generate fixes from all worker models in parallel
const fixes = await parallel(
  workerModels.map(model => () =>
    agent(fixPrompt, {
      label: `${model} Fix`,
      schema: fixSchema,
      model: model
    })
  )
).then(results => results.filter(Boolean))  // Remove nulls from failed models

const validFixes = fixes

if (validFixes.length === 0) {
  log('❌ No valid fixes generated')

  // Remove claim label on failure
  const unclaimCmd = isGitLab
    ? `glab issue update ${issueData.number || issueNumber} --unlabel "code-solve-in-progress"`
    : `gh issue edit ${issueData.number || issueNumber} --remove-label "code-solve-in-progress"`

  await _agent(`Remove claim label from issue #${issueData.number || issueNumber}.

${unclaimCmd}`, {
    label: 'Unclaim Issue'
  })

  return { status: 'error', message: 'Failed to generate fixes' }
}

log(`✅ Generated ${validFixes.length} fixes`)

// PHASE 3: Select Best Fix
phase('Select Best')

log(`⚖️ Selecting best fix via arbiter with fallback...`)

const arbiterPrompt = `Review these ${validFixes.length} proposed fixes for issue #${issueData.number || issueNumber}: "${issueData.title}"

${validFixes.map((fix, i) => `
**Fix ${i + 1}** (from ${workerModels[i] || 'AI'}):
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
- **selected_index** - Which fix to use (0 to ${validFixes.length - 1})
- **reasoning** - Why this fix is best
- **consensus_score** - Overall confidence in selection (0-100)`

const { decision, usedModel: arbiterModel } = await runArbiterWithFallback(arbiterPrompt, strategy)

const selectedFix = validFixes[decision.selected_index]
if (!selectedFix || decision.selected_index < 0 || decision.selected_index >= validFixes.length) {
  throw new Error(`Arbiter selected invalid index: ${decision.selected_index}`)
}

log(`✅ Selected Fix #${decision.selected_index + 1}`)
log(`   Reasoning: ${decision.reasoning}`)
log(`   Consensus: ${decision.consensus_score}%`)

// Create AI attribution for transparency
const aiAttribution = createArbiterAttribution({
  workerModels: workerModels,
  workerProposals: validFixes,
  arbiterModel: arbiterModel,
  arbiterDecision: decision,
  selectedIndex: decision.selected_index
})

log(`📊 AI Attribution captured: ${workerModels.length} workers, 1 arbiter, ${aiAttribution.rejected_proposals.length} alternatives rejected`)

// PHASE 4: Apply Fix and Commit
phase('Apply Fix and Commit')

log('📝 Applying fix to codebase...')

// Apply the fix in an isolated worktree to allow parallel runs
// Each agent gets its own working directory
await _agent(`Apply this fix to the codebase:

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
const commitInfo = await _agent(`Get the commit hash for the fix:

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

await _agent(`Close ${isGitLab ? 'GitLab' : 'GitHub'} issue #${issueData.number || issueNumber} with reference to the fix commit.

Execute:
${closeCmd}
echo "CLOSED_ISSUE: #${issueData.number || issueNumber}"`, {
  label: `Close Issue #${issueData.number || issueNumber}`
})

console.log(`CLOSED_ISSUE: #${issueData.number || issueNumber}`)
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
}

// Note: The main workflow logic ends here and calls solveSingleIssue() as needed

}
