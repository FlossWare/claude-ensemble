import { coordinateWork, createIssueClaimer } from '../shared/work-coordinator.js'

export const meta = {
  name: 'code-debug',
  description: 'Multi-AI debugging workflow with remote execution support',
  phases: [
    { title: 'Discovery', detail: 'Discover available AI models' }
  ]
}

export default async function({ args, phase, log, agent, parallel }) {

// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

// AUTONOMOUS WORKFLOW - No user prompts or confirmations
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

// Parse bug report from args
const bugReport = args?.bug || args?.description || 'No bug description provided'
const severity = args?.severity || 'medium'

log(`🐛 Bug Report: ${bugReport}`)
log(`⚠️  Severity: ${severity}`)

// PHASE 1: Analyze Bug
phase('Analyze Bug')

const analysisPrompt = `Analyze this bug report:

**Bug**: ${bugReport}
**Severity**: ${severity}

Provide:
1. **root_cause** - Likely root cause
2. **affected_components** - Which parts of the system are affected
3. **reproduction_steps** - How to reproduce the bug
4. **fix_strategy** - High-level strategy to fix it`

const bugAnalysis = await _agent(analysisPrompt, {
  label: 'Analyze Bug',
  schema: {
    type: 'object',
    properties: {
      root_cause: { type: 'string' },
      affected_components: { type: 'array', items: { type: 'string' } },
      reproduction_steps: { type: 'string' },
      fix_strategy: { type: 'string' }
    },
    required: ['root_cause', 'fix_strategy']
  }
})

log(`✅ Root cause: ${bugAnalysis.root_cause}`)
log(`   Strategy: ${bugAnalysis.fix_strategy}`)

// PHASE 2: Generate Fixes
phase('Generate Fixes')

log('🤖 Generating fixes from multiple AI models...')

const workerModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'].filter(m =>
  availableModels.includes(m)
)
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

const fixPrompt = `Generate a fix for this bug:

**Bug**: ${bugReport}
**Root Cause**: ${bugAnalysis.root_cause}
**Fix Strategy**: ${bugAnalysis.fix_strategy}

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
    _agent(fixPrompt, {
      label: `${model} Fix`,
      schema: fixSchema,
      model: model
    })
  )
).then(results => results.filter(Boolean))

const validFixes = fixes

if (validFixes.length === 0) {
  log('❌ No valid fixes generated')
  return { status: 'error', message: 'Failed to generate fixes' }
}

log(`✅ Generated ${validFixes.length} fixes`)

// PHASE 3: Select Best Fix
phase('Select Best')

log(`⚖️ Selecting best fix via arbiter...`)

const arbiterPrompt = `Review these ${validFixes.length} proposed fixes for bug: "${bugReport}"

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

const decision = await _agent(arbiterPrompt, {
  model: 'fable',
  phase: 'Select Best',
  label: 'Arbiter',
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

const selectedFix = validFixes[decision.selected_index]
if (!selectedFix || decision.selected_index < 0 || decision.selected_index >= validFixes.length) {
  throw new Error(`Arbiter selected invalid index: ${decision.selected_index}`)
}

log(`✅ Selected Fix #${decision.selected_index + 1}`)
log(`   Reasoning: ${decision.reasoning}`)
log(`   Consensus: ${decision.consensus_score}%`)

// PHASE 4: Apply Fix
phase('Apply Fix')

log('📝 Applying fix to codebase...')

await _agent(`Apply this debugging fix:

**Fix**: ${selectedFix.code_changes}

**Files to modify**: ${selectedFix.files_modified?.join(', ') || 'determine from code_changes'}

1. Make the necessary code changes
2. Stage the changes: git add <files>
3. Commit: git commit -m "fix: ${bugReport}

${selectedFix.approach}

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

return {
  status: 'success',
  bug_report: bugReport,
  root_cause: bugAnalysis.root_cause,
  fix_approach: selectedFix.approach,
  confidence: selectedFix.confidence,
  consensus_score: decision.consensus_score,
}

/**
 * Discover available models dynamically
 */
async function discoverAvailableModels() {
  const ALL_MODELS = [
    'fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini',
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

}
