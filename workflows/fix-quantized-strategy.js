// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'fix-quantized-strategy',
  description: 'Fix QuantizedStrategy prefix bug and expand to appropriate workflows',
  phases: [
    { title: 'Analyze', detail: 'Multi-AI identifies all files needing updates' },
    { title: 'Fix Bug', detail: 'Multi-AI fixes ollama: → ollama/ prefix' },
    { title: 'Expand', detail: 'Multi-AI adds QuantizedStrategy to high-benefit workflows' },
    { title: 'Verify', detail: 'Multi-AI validates all changes' }
  ]
}

// Multi-AI workflow to fix quantization and expand to appropriate workflows
// Phase 1: Analyze - identify all files
// Phase 2: Fix Bug - correct ollama: → ollama/ prefix
// Phase 3: Expand - add to code-doc, code-release-notes, ai-extract-learning, etc.
// Phase 4: Verify - multi-AI review

const FILE_LIST_SCHEMA = {
  type: 'object',
  properties: {
    files_to_fix: {
      type: 'array',
      items: { type: 'string' }
    },
    files_to_expand: {
      type: 'array',
      items: { type: 'string' }
    },
    rationale: { type: 'string' }
  },
  required: ['files_to_fix', 'files_to_expand']
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    approved: { type: 'boolean' },
    issues: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'number' }
  },
  required: ['approved', 'issues', 'confidence']
}

// ============================================================================
// PHASE 1: ANALYZE - Multi-AI identifies files
// ============================================================================

phase('Analyze')

log('Phase 1: Multi-AI analyzing which files need updates...')

const analyzePrompt = `Analyze the claude-global-skills codebase for QuantizedStrategy updates.

Tasks:
1. List files with ollama: prefix that need fixing (4 files found: workflows/code-review.js, workflows/code-solve.js, code-review.js, code-solve.js)
2. List high-benefit workflows that should get QuantizedStrategy added:
   - code-doc.js / code-doc-auto.js (template-based documentation)
   - code-release-notes.js / code-release-notes-auto.js (changelog generation)
   - ai-extract-learning.js (batch learning extraction)
   - memory-rag-index.js (batch file indexing)
   - ai-web-learn.js (high-volume fact extraction)

Return JSON with files_to_fix, files_to_expand, rationale.`

const analyses = await parallel([
  () => agent(analyzePrompt, { model: 'opus', label: 'Analyze (opus)', phase: 'Analyze', schema: FILE_LIST_SCHEMA }),
  () => agent(analyzePrompt, { model: 'sonnet', label: 'Analyze (sonnet)', phase: 'Analyze', schema: FILE_LIST_SCHEMA }),
  () => agent(analyzePrompt, { model: 'haiku', label: 'Analyze (haiku)', phase: 'Analyze', schema: FILE_LIST_SCHEMA })
]).then(r => r.filter(Boolean))

const analysisArbiter = await _agent(`Synthesize file lists from ${analyses.length} analyses.

Analyses:
${analyses.map((a, i) => `Analysis ${i+1}: ${JSON.stringify(a)}`).join('\n')}

Return consensus file lists.`, {
  model: 'opus',
  label: 'Analysis Arbiter',
  phase: 'Analyze',
  schema: FILE_LIST_SCHEMA
})

log(`✓ Analysis: ${analysisArbiter.files_to_fix.length} files to fix, ${analysisArbiter.files_to_expand.length} files to expand`)

// ============================================================================
// PHASE 2: FIX BUG - Multi-AI fixes ollama: → ollama/ prefix
// ============================================================================

phase('Fix Bug')

log('Phase 2: Multi-AI fixing ollama: → ollama/ prefix bug...')

const fixPrompt = `Fix the ollama: → ollama/ prefix bug in QuantizedStrategy classes.

Files to fix:
${analysisArbiter.files_to_fix.join('\n')}

Change:
- OLD: ['ollama:llama3', 'ollama:mistral', 'ollama:codellama', ...]
- NEW: ['ollama/llama3', 'ollama/mistral', 'ollama/codellama', ...]

This aligns with discoverAvailableModels() which uses ollama/ format.

Return: List of file paths with exact line numbers changed.`

const fixes = await parallel([
  () => agent(fixPrompt, { model: 'opus', label: 'Fix (opus)', phase: 'Fix Bug' }),
  () => agent(fixPrompt, { model: 'sonnet', label: 'Fix (sonnet)', phase: 'Fix Bug' }),
  () => agent(fixPrompt, { model: 'haiku', label: 'Fix (haiku)', phase: 'Fix Bug' })
]).then(r => r.filter(Boolean))

const fixArbiter = await _agent(`Synthesize fix instructions from ${fixes.length} proposals.

Proposals:
${fixes.map((f, i) => `Proposal ${i+1}:\n${f}`).join('\n\n')}

Return precise fix instructions for each file.`, {
  model: 'opus',
  label: 'Fix Arbiter',
  phase: 'Fix Bug'
})

log(`✓ Fix instructions: ${fixArbiter.length} chars`)

// ============================================================================
// PHASE 3: EXPAND - Multi-AI adds QuantizedStrategy to workflows
// ============================================================================

phase('Expand')

log('Phase 3: Multi-AI expanding QuantizedStrategy to high-benefit workflows...')

const expandPrompt = `Add QuantizedStrategy to high-benefit workflows.

Files to expand:
${analysisArbiter.files_to_expand.join('\n')}

For each file:
1. Add QuantizedStrategy class definition (after other strategy classes)
2. Add 'quantized' to STRATEGIES map
3. Ensure strategy is selectable via args.strategy
4. Use ollama/ prefix format

Example QuantizedStrategy:
\`\`\`javascript
class QuantizedStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['ollama/llama3', 'ollama/mistral', 'ollama/codellama', 'haiku', 'sonnet']
    return this.filterAvailable(ideal)
  }
  getArbiterFallback() {
    return ['fable', 'opus', 'sonnet']
  }
}
\`\`\`

Return: Implementation plan for each file with line numbers.`

const expansions = await parallel([
  () => agent(expandPrompt, { model: 'opus', label: 'Expand (opus)', phase: 'Expand' }),
  () => agent(expandPrompt, { model: 'sonnet', label: 'Expand (sonnet)', phase: 'Expand' }),
  () => agent(expandPrompt, { model: 'haiku', label: 'Expand (haiku)', phase: 'Expand' })
]).then(r => r.filter(Boolean))

const expandArbiter = await _agent(`Synthesize expansion plan from ${expansions.length} proposals.

Proposals:
${expansions.map((e, i) => `Proposal ${i+1}:\n${e}`).join('\n\n')}

Return final implementation instructions.`, {
  model: 'opus',
  label: 'Expand Arbiter',
  phase: 'Expand'
})

log(`✓ Expansion plan: ${expandArbiter.length} chars`)

// ============================================================================
// PHASE 4: VERIFY - Multi-AI validates all changes
// ============================================================================

phase('Verify')

log('Phase 4: Multi-AI verification...')

const verifyPrompt = `Verify the QuantizedStrategy fix and expansion plan.

Fix instructions:
${fixArbiter.substring(0, 2000)}...

Expansion plan:
${expandArbiter.substring(0, 2000)}...

Check:
1. Are all ollama: prefixes being changed to ollama/?
2. Are high-benefit workflows getting QuantizedStrategy?
3. Is it opt-in via --strategy=quantized (not default)?
4. Will it work with filterAvailable()?
5. Are security/critical workflows excluded?

Return: {approved: boolean, issues: string[], confidence: number}`

const verifications = await parallel([
  () => agent(verifyPrompt, { model: 'opus', label: 'Verify (opus)', phase: 'Verify', schema: VERIFY_SCHEMA }),
  () => agent(verifyPrompt, { model: 'sonnet', label: 'Verify (sonnet)', phase: 'Verify', schema: VERIFY_SCHEMA }),
  () => agent(verifyPrompt, { model: 'haiku', label: 'Verify (haiku)', phase: 'Verify', schema: VERIFY_SCHEMA })
]).then(r => r.filter(Boolean))

const approvedCount = verifications.filter(v => v.approved).length
const avgConfidence = verifications.reduce((sum, v) => sum + v.confidence, 0) / verifications.length

log(`✓ Verification: ${approvedCount}/${verifications.length} approved, ${avgConfidence.toFixed(0)}% avg confidence`)

// ============================================================================
// OUTPUT
// ============================================================================

return {
  status: 'success',
  approved: approvedCount >= 2,
  analysis: analysisArbiter,
  fix_instructions: fixArbiter,
  expansion_plan: expandArbiter,
  verification: {
    approved_count: approvedCount,
    total_reviewers: verifications.length,
    avg_confidence: avgConfidence,
    all_issues: verifications.flatMap(v => v.issues)
  },
  next_steps: [
    'Apply prefix fixes to 4 existing files',
    'Add QuantizedStrategy to high-benefit workflows',
    'Test with Ollama models',
    'Update documentation',
    'Add to CHANGELOG.md'
  ]
}
