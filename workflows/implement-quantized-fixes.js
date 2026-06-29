// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'implement-quantized-fixes',
  description: 'Implement QuantizedStrategy prefix fixes and expansions',
  phases: [
    { title: 'Fix Prefix', detail: 'Fix ollama: → ollama/ in 4 files (6 locations)' },
    { title: 'Expand Strategy', detail: 'Add QuantizedStrategy to 7 workflows' },
    { title: 'Verify', detail: 'Multi-AI verification of all changes' }
  ]
}

// Implement the QuantizedStrategy fixes approved by multi-AI
// Based on analysis from fix-quantized-strategy.js workflow

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    approved: { type: 'boolean' },
    files_modified: { type: 'number' },
    issues: { type: 'array', items: { type: 'string' } }
  },
  required: ['approved', 'files_modified', 'issues']
}

// ============================================================================
// PHASE 1: FIX PREFIX - ollama: → ollama/
// ============================================================================

phase('Fix Prefix')

log('Phase 1: Fixing ollama: → ollama/ prefix in 4 files (6 locations)...')

const PREFIX_FIXES = [
  {
    file: '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/code-review.js',
    locations: ['line 100: QuantizedStrategy.getWorkerModels()']
  },
  {
    file: '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/code-solve.js',
    locations: ['line 104: QuantizedStrategy.getWorkerModels()']
  },
  {
    file: '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/code-review.js',
    locations: ['line 114: QuantizedStrategy.getWorkers()', 'lines 162-164: discoverAvailableModels()']
  },
  {
    file: '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/code-solve.js',
    locations: ['line 88: QuantizedStrategy.getWorkers()', 'lines 136-138: discoverAvailableModels()']
  }
]

const fixResults = await pipeline(
  PREFIX_FIXES,
  // Stage 1: Read file and identify exact changes
  async (fix) => {
    const readPrompt = `Read ${fix.file} and find all instances of 'ollama:llama3', 'ollama:mistral', 'ollama:codellama' that need to be changed to 'ollama/llama3', 'ollama/mistral', 'ollama/codellama'.

Expected locations: ${fix.locations.join(', ')}

Return the exact old_string and new_string for each Edit tool call needed.`

    const changes = await _agent(readPrompt, {
      model: 'opus',
      label: `Read ${fix.file.split('/').pop()}`,
      phase: 'Fix Prefix'
    })
    return { file: fix.file, changes }
  },

  // Stage 2: Apply fixes
  async (result) => {
    const applyPrompt = `Apply the prefix fixes to ${result.file}.

Changes needed:
${result.changes}

Use Edit tool to change all instances of:
- 'ollama:llama3' → 'ollama/llama3'
- 'ollama:mistral' → 'ollama/mistral'
- 'ollama:codellama' → 'ollama/codellama'

Return confirmation of edits made.`

    const applied = await _agent(applyPrompt, {
      model: 'sonnet',
      label: `Apply fix ${result.file.split('/').pop()}`,
      phase: 'Fix Prefix'
    })
    return { file: result.file, applied }
  }
)

log(`✓ Prefix fixes applied to ${fixResults.filter(Boolean).length} files`)

// ============================================================================
// PHASE 2: EXPAND STRATEGY - Add QuantizedStrategy to 7 workflows
// ============================================================================

phase('Expand Strategy')

log('Phase 2: Adding QuantizedStrategy to 7 workflows...')

const EXPANSION_FILES = [
  '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/code-doc.js',
  '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/code-doc-auto.js',
  '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/code-release-notes.js',
  '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/code-release-notes-auto.js',
  '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/ai-extract-learning.js',
  '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/memory-rag-index.js',
  '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/ai-web-learn.js'
]

const QUANTIZED_STRATEGY_TEMPLATE = `
class QuantizedStrategy extends BaseStrategy {
  getWorkers() {
    return ['ollama/llama3', 'ollama/mistral', 'ollama/codellama', 'haiku', 'sonnet']
  }
  getArbiters() {
    return ['fable', 'opus', 'sonnet']
  }
}
`

const expansionResults = await pipeline(
  EXPANSION_FILES,
  // Stage 1: Analyze file structure
  async (file) => {
    const analyzePrompt = `Analyze ${file} to determine how to add QuantizedStrategy.

Check:
1. Does it have strategy classes already? (look for BaseStrategy, MaximumCoverageStrategy)
2. Does it have a STRATEGIES map?
3. Does it have hardcoded worker arrays that should use strategy.getWorkers()?
4. Is it an -auto.js file (needs passthrough only)?

Return implementation plan.`

    const plan = await _agent(analyzePrompt, {
      model: 'opus',
      label: `Analyze ${file.split('/').pop()}`,
      phase: 'Expand Strategy'
    })
    return { file, plan }
  },

  // Stage 2: Implement changes
  async (result) => {
    const implementPrompt = `Implement QuantizedStrategy for ${result.file}.

Plan:
${result.plan}

Template:
${QUANTIZED_STRATEGY_TEMPLATE}

Add QuantizedStrategy class, update STRATEGIES map, and make workers use strategy.getWorkers() if needed.

Return summary of changes made.`

    const implemented = await _agent(implementPrompt, {
      model: 'sonnet',
      label: `Implement ${result.file.split('/').pop()}`,
      phase: 'Expand Strategy'
    })
    return { file: result.file, implemented }
  }
)

log(`✓ QuantizedStrategy added to ${expansionResults.filter(Boolean).length} workflows`)

// ============================================================================
// PHASE 3: VERIFY - Multi-AI verification
// ============================================================================

phase('Verify')

log('Phase 3: Multi-AI verification of all changes...')

const verifyPrompt = `Verify all QuantizedStrategy fixes and expansions.

Prefix fixes applied: ${fixResults.filter(Boolean).length} files
Expansions applied: ${expansionResults.filter(Boolean).length} files

Check:
1. Are all ollama: prefixes now ollama/?
2. Is QuantizedStrategy available in the right workflows?
3. Is it opt-in via --strategy=quantized (not default)?
4. Will filterAvailable() work correctly now?

Return: {approved: boolean, files_modified: number, issues: string[]}`

const verifications = await parallel([
  () => agent(verifyPrompt, { model: 'opus', label: 'Verify (opus)', phase: 'Verify', schema: VERIFY_SCHEMA }),
  () => agent(verifyPrompt, { model: 'sonnet', label: 'Verify (sonnet)', phase: 'Verify', schema: VERIFY_SCHEMA }),
  () => agent(verifyPrompt, { model: 'haiku', label: 'Verify (haiku)', phase: 'Verify', schema: VERIFY_SCHEMA })
]).then(r => r.filter(Boolean))

const approvedCount = verifications.filter(v => v.approved).length

log(`✓ Verification: ${approvedCount}/${verifications.length} approved`)

// ============================================================================
// OUTPUT
// ============================================================================

return {
  status: 'success',
  approved: approvedCount >= 2,
  prefix_fixes: {
    files: fixResults.filter(Boolean).length,
    details: fixResults.filter(Boolean)
  },
  expansions: {
    files: expansionResults.filter(Boolean).length,
    details: expansionResults.filter(Boolean)
  },
  verification: {
    approved_count: approvedCount,
    total_reviewers: verifications.length,
    all_issues: verifications.flatMap(v => v.issues)
  },
  summary: `Fixed ${fixResults.filter(Boolean).length} files (prefix bug), expanded ${expansionResults.filter(Boolean).length} workflows (QuantizedStrategy)`
}

}
