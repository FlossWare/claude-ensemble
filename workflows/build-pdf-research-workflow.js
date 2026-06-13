export const meta = {
  name: 'build-pdf-research-workflow',
  description: 'Build ai-pdf-deep-research workflow using multi-AI for all phases',
  phases: [
    { title: 'Design', detail: 'Multi-AI designs workflow architecture' },
    { title: 'Schema', detail: 'Multi-AI defines data schemas' },
    { title: 'Implement', detail: 'Multi-AI writes workflow code' },
    { title: 'Document', detail: 'Multi-AI creates skill documentation' },
    { title: 'Verify', detail: 'Multi-AI reviews and validates' }
  ]
}

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
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
    await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
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
    const result = await agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


// Multi-AI workflow to build ai-pdf-deep-research
// Uses 6 models (fable, opus, sonnet, haiku, gpt-4o, gemini) for every phase

const CLAIM_SCHEMA = {
  type: 'object',
  properties: {
    claims: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          page: { type: 'number' },
          confidence: { type: 'number' },
          category: { type: 'string' },
          falsifiable: { type: 'boolean' }
        },
        required: ['claim', 'page', 'confidence']
      }
    }
  },
  required: ['claims']
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string' },
    confidence: { type: 'number' }
  },
  required: ['refuted', 'reason', 'confidence']
}

const DESIGN_SCHEMA = {
  type: 'object',
  properties: {
    architecture: { type: 'string' },
    phases: { type: 'array', items: { type: 'string' } },
    patterns: { type: 'array', items: { type: 'string' } },
    code_outline: { type: 'string' }
  },
  required: ['architecture', 'phases', 'code_outline']
}

// ============================================================================
// PHASE 1: DESIGN - Multi-AI designs the workflow architecture
// ============================================================================

phase('Design')

log('Phase 1: Multi-AI designing ai-pdf-deep-research workflow architecture...')

const designPrompt = `Design the ai-pdf-deep-research workflow for adversarial verification of PDF content.

Requirements:
- Input: PDF file paths + research topic
- Phase 1: Read PDFs (chunk large PDFs into 20-page ranges)
- Phase 2: Extract falsifiable claims (6 workers in pipeline across PDFs)
- Phase 3: Adversarial verification (3-vote per claim, 2/3 refutes to kill)
- Phase 4: Synthesize findings, merge semantic duplicates
- Phase 5: Save to memory with PDF citations

Reference /deep-research workflow patterns. Use pipeline() not parallel().

Return JSON with: architecture, phases, patterns, code_outline`

const designs = await parallel([
  () => agent(designPrompt, { model: 'opus', label: 'Design (opus)', phase: 'Design', schema: DESIGN_SCHEMA }),
  () => agent(designPrompt, { model: 'sonnet', label: 'Design (sonnet)', phase: 'Design', schema: DESIGN_SCHEMA }),
  () => agent(designPrompt, { model: 'haiku', label: 'Design (haiku)', phase: 'Design', schema: DESIGN_SCHEMA })
]).then(r => r.filter(Boolean))

if (designs.length === 0) {
  throw new Error('All design workers failed')
}

const designArbiter = await _agent(`Synthesize the best workflow architecture from ${designs.length} designs.

Designs:
${designs.map((d, i) => `Design ${i+1}: ${JSON.stringify(d)}`).join('\n\n')}

Select best patterns from each. Return final architecture.`, {
  model: 'opus',  // Phase 1: Opus arbiter
  label: 'Design Arbiter (Opus)',
  phase: 'Design',
  schema: DESIGN_SCHEMA
})

log(`✓ Design complete: ${designArbiter.phases.length} phases planned`)

// ============================================================================
// PHASE 2: SCHEMA - Multi-AI defines all data schemas
// ============================================================================

phase('Schema')

log('Phase 2: Multi-AI defining data schemas...')

const schemaPrompt = `Define all JSON schemas for ai-pdf-deep-research workflow.

Need schemas for:
1. Extracted claims (claim, page, confidence, category, falsifiable)
2. Adversarial verdict (refuted, reason, confidence)
3. Synthesized findings (claim, sources[], confidence, verified)
4. Final report (topic, verified_claims[], sources, metadata)

Return valid JSON Schema objects for each.`

const schemas = await parallel([
  () => agent(schemaPrompt, { model: 'opus', label: 'Schema (opus)', phase: 'Schema' }),
  () => agent(schemaPrompt, { model: 'sonnet', label: 'Schema (sonnet)', phase: 'Schema' }),
  () => agent(schemaPrompt, { model: 'haiku', label: 'Schema (haiku)', phase: 'Schema' })
]).then(r => r.filter(Boolean))

const schemaArbiter = await _agent(`Synthesize best schemas from ${schemas.length} proposals.

Schemas:
${schemas.map((s, i) => `Proposal ${i+1}: ${s}`).join('\n\n')}

Return final schemas as valid JSON.`, {
  model: 'sonnet',  // Phase 2: Sonnet arbiter (rotation)
  label: 'Schema Arbiter (Sonnet)',
  phase: 'Schema'
})

log(`✓ Schemas defined: ${schemaArbiter}`)

// ============================================================================
// PHASE 3: IMPLEMENT - Multi-AI writes the workflow code
// ============================================================================

phase('Implement')

log('Phase 3: Multi-AI implementing workflow code...')

const implementPrompt = `Write the ai-pdf-deep-research.js workflow code.

Architecture:
${designArbiter.code_outline}

Schemas:
${schemaArbiter}

Requirements:
- Use Read tool for PDFs with page ranges
- pipeline() for multi-PDF processing
- 6-model workers for claim extraction
- 3-vote adversarial verification per claim
- Semantic duplicate detection in synthesis
- Save to memory file with citations

Return complete JavaScript workflow code with meta block.`

const implementations = await parallel([
  () => agent(implementPrompt, { model: 'opus', label: 'Implement (opus)', phase: 'Implement' }),
  () => agent(implementPrompt, { model: 'sonnet', label: 'Implement (sonnet)', phase: 'Implement' }),
  () => agent(implementPrompt, { model: 'haiku', label: 'Implement (haiku)', phase: 'Implement' })
]).then(r => r.filter(Boolean))

if (implementations.length === 0) {
  throw new Error('All implementation workers failed')
}

const implementArbiter = await _agent(`Review ${implementations.length} implementations and synthesize the best one.

Implementations:
${implementations.map((impl, i) => `Implementation ${i+1}:\n${impl}`).join('\n\n---\n\n')}

Select best patterns, combine strengths. Return final production-ready code.`, {
  model: 'haiku',  // Phase 3: Haiku arbiter (rotation)
  label: 'Implement Arbiter (Haiku)',
  phase: 'Implement'
})

log(`✓ Implementation complete: ${implementArbiter.length} chars`)

// ============================================================================
// PHASE 4: DOCUMENT - Multi-AI creates skill documentation
// ============================================================================

phase('Document')

log('Phase 4: Multi-AI writing skill documentation...')

const docPrompt = `Write the ai-pdf-deep-research.md skill documentation.

Workflow code:
${implementArbiter}

Include:
- Frontmatter with skill metadata
- Description and use cases
- Input parameters
- Phase descriptions
- Output format
- Example usage
- Installation requirements

Return complete markdown documentation.`

const docs = await parallel([
  () => agent(docPrompt, { model: 'opus', label: 'Document (opus)', phase: 'Document' }),
  () => agent(docPrompt, { model: 'sonnet', label: 'Document (sonnet)', phase: 'Document' }),
  () => agent(docPrompt, { model: 'haiku', label: 'Document (haiku)', phase: 'Document' })
]).then(r => r.filter(Boolean))

if (docs.length === 0) {
  throw new Error('All documentation workers failed')
}

const docArbiter = await _agent(`Synthesize best documentation from ${docs.length} drafts.

Drafts:
${docs.map((d, i) => `Draft ${i+1}:\n${d}`).join('\n\n---\n\n')}

Combine strengths, ensure clarity. Return final markdown.`, {
  model: 'opus',  // Phase 4: Opus arbiter (cycle repeats)
  label: 'Document Arbiter (Opus)',
  phase: 'Document'
})

log(`✓ Documentation complete: ${docArbiter.length} chars`)

// ============================================================================
// PHASE 5: VERIFY - Multi-AI reviews and validates everything
// ============================================================================

phase('Verify')

log('Phase 5: Multi-AI verification...')

const verifyPrompt = `Review ai-pdf-deep-research workflow for correctness.

Code:
${implementArbiter.substring(0, 5000)}...

Documentation:
${docArbiter.substring(0, 2000)}...

Check:
1. Does code match design architecture?
2. Are all schemas properly defined?
3. Does pipeline() usage look correct?
4. Is adversarial verification implemented?
5. Are PDF citations included?
6. Is documentation complete?

Return: {approved: boolean, issues: string[], suggestions: string[]}`

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    approved: { type: 'boolean' },
    issues: { type: 'array', items: { type: 'string' } },
    suggestions: { type: 'array', items: { type: 'string' } }
  },
  required: ['approved', 'issues', 'suggestions']
}

const verifications = await parallel([
  () => agent(verifyPrompt, { model: 'opus', label: 'Verify (opus)', phase: 'Verify', schema: VERIFY_SCHEMA }),
  () => agent(verifyPrompt, { model: 'sonnet', label: 'Verify (sonnet)', phase: 'Verify', schema: VERIFY_SCHEMA }),
  () => agent(verifyPrompt, { model: 'haiku', label: 'Verify (haiku)', phase: 'Verify', schema: VERIFY_SCHEMA })
]).then(r => r.filter(Boolean))

const approvedCount = verifications.filter(v => v.approved).length

log(`✓ Verification: ${approvedCount}/${verifications.length} approved`)

// ============================================================================
// OUTPUT - Return all artifacts
// ============================================================================

return {
  status: 'success',
  approved: approvedCount >= 2,
  design: designArbiter,
  schemas: schemaArbiter,
  code: implementArbiter,
  documentation: docArbiter,
  verification: {
    approved_count: approvedCount,
    total_reviewers: verifications.length,
    issues: verifications.flatMap(v => v.issues),
    suggestions: verifications.flatMap(v => v.suggestions)
  },
  next_steps: [
    'Write code to /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/ai-pdf-deep-research.js',
    'Write documentation to /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/ai-pdf-deep-research.md',
    'Update skill registry',
    'Test with sample PDFs'
  ]
}
