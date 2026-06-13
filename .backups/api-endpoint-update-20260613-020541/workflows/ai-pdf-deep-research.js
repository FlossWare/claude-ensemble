// ============================================================================
// ai-pdf-deep-research.js - Adversarial PDF Content Verification Workflow
// ============================================================================
// Location: workflows/ai-pdf-deep-research.js
// Pattern: Arbiter/Worker with adversarial verification + challenger exclusion
// Models: 6-model maximum coverage (fable, opus, sonnet, haiku, gpt-4o, gemini)
// Execution: pipeline() for sequential processing, nested parallel() for worker fan-out
// Fleet-aware: Auto-detects fleet with --fleet/--local flags, 10-PDF break-even threshold
// Based on: TEMPLATE-arbiter-worker.js + deep-research adversarial pattern
// ============================================================================

import { resolveFleetMode } from '../shared/fleet-utils.js';
import { execSync } from 'child_process';

export const meta = {
  name: 'ai-pdf-deep-research',
  description: 'Adversarial verification of PDF content - extract claims, 3-vote refutation, synthesize findings (fleet-aware)',
  whenToUse: 'When you need to critically analyze PDF documents and verify their claims against adversarial challenge',
  phases: [
    { title: 'Read PDFs', detail: 'Chunk large PDFs into 20-page ranges and read content' },
    { title: 'Extract Claims', detail: '6 workers extract falsifiable claims per chunk, arbiter deduplicates' },
    { title: 'Adversarial Verify', detail: '3-vote adversarial challenge per claim, 2/3 refutes to kill' },
    { title: 'Synthesize', detail: 'Merge semantic duplicates, group by category, rank by confidence' },
    { title: 'Save to Memory', detail: 'Persist findings with PDF citations to memory system' },
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


// ============================================================================
// INLINE INSTRUCTIONS (no imports allowed in workflows)
// ============================================================================

const NO_BASH_INSTRUCTION = `
IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
- Do not use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data
`.trim()

const STRUCTURED_OUTPUT_INSTRUCTION = `
Return ONLY valid JSON matching the schema.
- All required fields must be present
- Use correct types (number, string, boolean, array, object)
- No extra fields not in the schema
`.trim()

// ============================================================================
// SCHEMAS
// ============================================================================

const CLAIM_EXTRACTION_SCHEMA = {
  type: 'object',
  properties: {
    claims: {
      type: 'array',
      maxItems: 5,  // Cap per-worker to control volume
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string', description: 'The falsifiable claim extracted from the PDF' },
          page: { type: 'number', description: 'Page number where claim appears' },
          quote: { type: 'string', description: 'Direct quote from PDF supporting the claim' },
          confidence: { type: 'number', minimum: 0, maximum: 100 },
          category: { type: 'string', enum: ['factual', 'statistical', 'causal', 'other'] },
          importance: { type: 'string', enum: ['central', 'supporting', 'tangential'] },
          falsifiable: { type: 'boolean', description: 'Whether this claim can be empirically tested' }
        },
        required: ['claim', 'page', 'quote', 'confidence', 'importance', 'falsifiable']
      }
    },
    model: { type: 'string' }
  },
  required: ['claims', 'model']
}

const DEDUP_SCHEMA = {
  type: 'object',
  properties: {
    deduplicated_claims: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          page: { type: 'number' },
          pdf_path: { type: 'string' },
          quote: { type: 'string' },
          confidence: { type: 'number' },
          category: { type: 'string' },
          importance: { type: 'string' },
          falsifiable: { type: 'boolean' },
          proposed_by: { type: 'array', items: { type: 'string' } }
        },
        required: ['claim', 'page', 'confidence', 'importance', 'falsifiable']
      }
    },
    duplicates_removed: { type: 'number' },
    non_falsifiable_removed: { type: 'number' }
  },
  required: ['deduplicated_claims', 'duplicates_removed', 'non_falsifiable_removed']
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean', description: 'true if claim is refuted, false if it survives' },
    reason: { type: 'string', description: 'Detailed reasoning for verdict' },
    confidence: { type: 'number', minimum: 0, maximum: 100 }
  },
  required: ['refuted', 'reason', 'confidence']
}

const SYNTHESIS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          finding: { type: 'string' },
          claims: { type: 'array', items: { type: 'string' } },
          sources: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                pdf_path: { type: 'string' },
                pages: { type: 'array', items: { type: 'number' } }
              }
            }
          },
          category: { type: 'string' },
          confidence: { type: 'number' },
          merged_count: { type: 'number' }
        },
        required: ['finding', 'sources', 'confidence']
      }
    },
    narrative: { type: 'string', description: 'Coherent summary with caveats and open questions' }
  },
  required: ['findings', 'narrative']
}

// ============================================================================
// CONFIGURATION
// ============================================================================

const ALL_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
const PAGES_PER_CHUNK = 20
const VOTES_PER_CLAIM = 3
const REFUTE_THRESHOLD = 2  // 2 of 3 refutes = killed
const MAX_VERIFY_CLAIMS = 25  // Cap verification to control cost
const MIN_WORKERS_REQUIRED = 2  // Graceful degradation floor

// Arbiter rotation: different arbiter per phase (ARBITER_ROTATION_INSTRUCTION)
const EXTRACTION_ARBITER = 'fable'
const VERIFICATION_ARBITER = 'opus'
const SYNTHESIS_ARBITER = 'sonnet'

// Importance ranking for sorting
const IMPORTANCE_RANK = { central: 0, supporting: 1, tangential: 2, other: 3 }

// ============================================================================
// INPUT PARSING AND VALIDATION
// ============================================================================

// Parse args if it's a JSON-stringified object or array
let parsedArgs = args
if (typeof args === 'string' && (args.startsWith('[') || args.startsWith('{'))) {
  try {
    parsedArgs = JSON.parse(args)
  } catch (e) {
    log(`WARNING: Failed to parse args as JSON: ${e.message}`)
    // Use as-is
  }
}

// Extract PDF paths from various possible formats
const pdfPaths = parsedArgs?.pdf_paths || parsedArgs?.pdfs || parsedArgs?.paths || []
const topic = parsedArgs?.topic || parsedArgs?.question || 'general analysis'

if (!pdfPaths.length) {
  log('ERROR: No PDF paths provided')
  log('Usage: workflow("ai-pdf-deep-research", {')
  log('  pdfs: ["/path/to/paper1.pdf", "/path/to/paper2.pdf"],')
  log('  topic: "research question or topic"')
  log('})')
  log(`Received args: ${JSON.stringify(args)}`)
  return { error: 'No pdf_paths provided', status: 'failed' }
}

// ============================================================================
// FLEET-AWARE MODE DETECTION (PDFs: break-even threshold = 10)
// ============================================================================

const BREAK_EVEN_PDFS = 10;
const fleetArgs = Array.isArray(args) ? args :
                  (typeof args === 'string' ? args.split(/\s+/) : []);

const fleetDecision = resolveFleetMode(fleetArgs, pdfPaths.length, BREAK_EVEN_PDFS);

log('='.repeat(80))
log('AI-PDF-DEEP-RESEARCH: Adversarial PDF Verification')
log('='.repeat(80))
log(`Fleet Detection: ${fleetDecision.reason}`)

if (fleetDecision.mode === 'fleet') {
  log(`✅ Fleet mode: Distributing ${pdfPaths.length} PDFs across ${fleetDecision.workers.length} workers`)
  log(`   Workers: ${fleetDecision.workers.map(w => w.hostname).join(', ')}`)
  log(`   Delegating to multi-session orchestration...`)

  // Delegate to bash multi-session script
  const scriptPath = '../scripts/fleet/bulk-pdf-ingest.sh'
  try {
    const result = execSync(
      `${scriptPath} ${pdfPaths.map(p => `"${p}"`).join(' ')} --topic="${topic}"`,
      {
        encoding: 'utf8',
        cwd: process.cwd(),
        stdio: 'inherit',
        timeout: 7200000  // 2 hour timeout for fleet work
      }
    )

    return {
      status: 'success',
      mode: 'fleet',
      workers_used: fleetDecision.workers.length,
      pdfs_processed: pdfPaths.length,
      delegation_result: result
    }
  } catch (error) {
    log(`❌ Fleet delegation failed: ${error.message}`)
    log(`   Falling back to local mode...`)
    // Fall through to local mode
  }
}

log(`📍 Local mode: Processing sequentially on current machine`)
log(`Topic: ${topic}`)
log(`PDFs: ${pdfPaths.length}`)
log(`Models: ${ALL_MODELS.join(', ')}`)
log(`Votes per claim: ${VOTES_PER_CLAIM} (threshold: ${REFUTE_THRESHOLD}/${VOTES_PER_CLAIM} to kill)`)
log(`Max claims to verify: ${MAX_VERIFY_CLAIMS}`)
log('='.repeat(80))

// ============================================================================
// HELPER: Generate page ranges for chunking
// ============================================================================

function generatePageRanges(totalPages, chunkSize) {
  const ranges = []
  for (let start = 1; start <= totalPages; start += chunkSize) {
    const end = Math.min(start + chunkSize - 1, totalPages)
    ranges.push(`${start}-${end}`)
  }
  return ranges
}

// ============================================================================
// HELPER: Select N random challenger models, excluding specified models
// ============================================================================

function selectChallengers(count, excludeModels) {
  const available = ALL_MODELS.filter(m => !excludeModels.includes(m))
  // If exclusion leaves fewer than count, allow some excluded models back
  const pool = available.length >= count ? available : ALL_MODELS
  const shuffled = [...pool].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, count)
}

// ============================================================================
// HELPER: Extract basename from path (no imports allowed)
// ============================================================================

function basename(filePath) {
  return filePath.split('/').pop() || filePath
}

// ============================================================================
// PHASE 1: READ PDFs (chunk into 20-page ranges)
// ============================================================================

phase('Read PDFs')

log(`Reading ${pdfPaths.length} PDFs with ${PAGES_PER_CHUNK}-page chunking...`)

const pdfChunks = await pipeline(
  pdfPaths,

  // Stage 1: Probe each PDF to determine page count, then read chunks
  async (pdfPath) => {
    log(`  Reading: ${pdfPath}`)

    // Read first page to probe (Read tool returns PDF content with page info)
    let probe
    try {
      probe = await _agent(`Read the PDF file at ${pdfPath} using the Read tool with pages "1".
Report the total number of pages if visible in the output, otherwise estimate from content length.

${NO_BASH_INSTRUCTION}

Return JSON: { "total_pages": <number>, "title": "<string>" }`, {
        label: `Probe ${basename(pdfPath)}`,
        model: 'haiku',  // lightweight probe
        schema: {
          type: 'object',
          properties: {
            total_pages: { type: 'number' },
            title: { type: 'string' }
          },
          required: ['total_pages']
        }
      })
    } catch (e) {
      log(`  WARNING: Failed to read PDF: ${pdfPath} -- skipping`)
      return []  // Graceful degradation: skip unreadable PDFs
    }

    const totalPages = probe?.total_pages || 20  // fallback
    const pageRanges = generatePageRanges(totalPages, PAGES_PER_CHUNK)

    log(`    ${basename(pdfPath)}: ~${totalPages} pages, ${pageRanges.length} chunks`)

    // Read each chunk sequentially within this PDF
    const chunks = []
    for (const range of pageRanges) {
      let content
      try {
        content = await _agent(`Read the PDF file at ${pdfPath} using the Read tool with pages "${range}".
Return the full text content you read from those pages.

${NO_BASH_INSTRUCTION}

Return JSON: { "content": "<full text content>", "page_range": "${range}" }`, {
          label: `Read ${basename(pdfPath)} p.${range}`,
          model: 'haiku',
          schema: {
            type: 'object',
            properties: {
              content: { type: 'string' },
              page_range: { type: 'string' }
            },
            required: ['content', 'page_range']
          }
        })
      } catch (e) {
        log(`    WARNING: Failed to read chunk ${range} of ${basename(pdfPath)} -- skipping`)
        continue
      }

      chunks.push({
        pdf_path: pdfPath,
        filename: basename(pdfPath),
        chunk_index: chunks.length,
        content: content?.content || '',
        page_range: range,
        title: probe?.title || basename(pdfPath)
      })
    }

    return chunks
  }
)

const allChunks = pdfChunks.flat().filter(Boolean)
log(`Read ${allChunks.length} chunks from ${pdfPaths.length} PDFs`)

if (allChunks.length === 0) {
  log('ERROR: No PDF chunks could be read. Aborting.')
  return { error: 'No PDF content could be read', status: 'failed' }
}

// ============================================================================
// PHASE 2: EXTRACT FALSIFIABLE CLAIMS (6 workers per chunk, arbiter dedup)
// ============================================================================

phase('Extract Claims')

log(`Extracting falsifiable claims with ${ALL_MODELS.length} workers per chunk...`)

const extractionResults = await pipeline(
  allChunks,

  // Stage 1: All 6 workers extract claims from each chunk in parallel
  (chunk) => {
    log(`  Extracting from ${chunk.filename} chunk ${chunk.chunk_index} (p.${chunk.page_range})`)

    return parallel(ALL_MODELS.map(model =>
      () => agent(`Extract all FALSIFIABLE claims from this PDF content.

${NO_BASH_INSTRUCTION}
${STRUCTURED_OUTPUT_INSTRUCTION}

Research topic: ${topic}
PDF: ${chunk.filename}
Pages: ${chunk.page_range}

Content:
${chunk.content}

INSTRUCTIONS:
- Focus on claims that can be empirically verified or refuted
- Include the page number for each claim
- Include a direct quote from the text as evidence
- Rate confidence 0-100 based on how clearly the claim is stated
- Rate importance: central (core thesis), supporting (backs core), tangential (side point)
- Mark falsifiable=true only for testable claims (not opinions or definitions)
- Categorize: factual, statistical, causal, or other
- Maximum 5 claims per chunk -- prioritize the most important ones`, {
        label: `${model}: Extract ${chunk.filename} p.${chunk.page_range}`,
        model: model,
        phase: 'Extract Claims',
        schema: CLAIM_EXTRACTION_SCHEMA
      })
    )).then(workerResults => {
      const valid = workerResults.filter(Boolean)
      if (valid.length < MIN_WORKERS_REQUIRED) {
        log(`    WARNING: Only ${valid.length}/${ALL_MODELS.length} workers succeeded (minimum ${MIN_WORKERS_REQUIRED})`)
      }
      const totalClaims = valid.reduce((sum, r) => sum + (r.claims?.length || 0), 0)
      log(`    ${valid.length}/${ALL_MODELS.length} workers returned ${totalClaims} claims`)
      return { chunk, workerResults: valid }
    })
  },

  // Stage 2: Arbiter deduplicates and filters claims per chunk
  (extractionResult) => {
    const { chunk, workerResults } = extractionResult
    const allClaims = workerResults.flatMap(r =>
      (r.claims || []).map(c => ({ ...c, pdf_path: chunk.pdf_path, proposed_by: r.model }))
    )

    if (allClaims.length === 0) {
      return { deduplicated_claims: [], duplicates_removed: 0, non_falsifiable_removed: 0 }
    }

    log(`  Arbiter (${EXTRACTION_ARBITER}) deduplicating ${allClaims.length} claims for ${chunk.filename} p.${chunk.page_range}...`)

    return agent(`Deduplicate and filter these claims extracted by ${ALL_MODELS.length} AI workers.

${STRUCTURED_OUTPUT_INSTRUCTION}

Claims from all workers:
${JSON.stringify(allClaims, null, 2)}

INSTRUCTIONS:
1. Merge semantically identical claims (keep highest confidence, combine proposing models into proposed_by array)
2. Remove non-falsifiable claims (opinions, definitions, vague statements)
3. Keep the best direct quote for each claim
4. Preserve page numbers and PDF path
5. Preserve importance ratings (use highest importance if claims differ)
6. Return deduplicated list with proposed_by arrays showing which models found each claim`, {
      label: `Arbiter: Dedup ${chunk.filename} p.${chunk.page_range}`,
      model: EXTRACTION_ARBITER,
      phase: 'Extract Claims',
      schema: DEDUP_SCHEMA
    })
  }
)

// Flatten, filter, rank, and cap
const allExtractedClaims = extractionResults
  .filter(Boolean)
  .flatMap(r => r.deduplicated_claims || [])
  .filter(c => c.falsifiable !== false)

const totalRemoved = extractionResults
  .filter(Boolean)
  .reduce((sum, r) => sum + (r.duplicates_removed || 0) + (r.non_falsifiable_removed || 0), 0)

// Rank by importance then confidence, cap at MAX_VERIFY_CLAIMS
const rankedClaims = allExtractedClaims
  .sort((a, b) =>
    ((IMPORTANCE_RANK[a.importance] || 3) - (IMPORTANCE_RANK[b.importance] || 3)) ||
    ((b.confidence || 0) - (a.confidence || 0))
  )
  .slice(0, MAX_VERIFY_CLAIMS)

log(`Extracted ${allExtractedClaims.length} unique falsifiable claims (${totalRemoved} removed)`)
log(`Ranked and capped to ${rankedClaims.length} claims for verification`)

// ============================================================================
// PHASE 3: ADVERSARIAL VERIFICATION (3-vote per claim, 2/3 refutes to kill)
// ============================================================================

phase('Adversarial Verify')

log(`Adversarially verifying ${rankedClaims.length} claims (${VOTES_PER_CLAIM} votes each, ${REFUTE_THRESHOLD}/${VOTES_PER_CLAIM} to kill)...`)

const verificationResults = await pipeline(
  rankedClaims,

  // For each claim: select challengers, run adversarial verification, tally votes
  (claim, _, idx) => {
    const excludeModels = Array.isArray(claim.proposed_by) ? claim.proposed_by : [claim.proposed_by].filter(Boolean)
    const challengers = selectChallengers(VOTES_PER_CLAIM, excludeModels)

    log(`  [${idx + 1}/${rankedClaims.length}] "${claim.claim.substring(0, 60)}..." challengers: ${challengers.join(', ')}`)

    return parallel(challengers.map(model =>
      () => agent(`ADVERSARIAL CHALLENGE: Attempt to REFUTE this claim.

${NO_BASH_INSTRUCTION}
${STRUCTURED_OUTPUT_INSTRUCTION}

Your role is ADVERSARIAL. You are trying to find reasons this claim is FALSE, misleading, unsupported, or logically flawed.
DEFAULT STANCE: Skeptical. Assume the claim is false unless the evidence strongly supports it.

CLAIM: "${claim.claim}"
EVIDENCE QUOTE: "${claim.quote}"
SOURCE: ${claim.pdf_path}, page ${claim.page}
IMPORTANCE: ${claim.importance}
RESEARCH TOPIC: ${topic}

INSTRUCTIONS:
- Look for logical fallacies, unsupported leaps, contradictions
- Check if the quoted evidence actually supports the claim
- Consider whether the claim is overgeneralized or taken out of context
- Check if the claim could be outdated or superseded
- If the claim is well-supported and you cannot find valid refutation, set refuted=false
- Be rigorous but fair -- do not refute well-supported claims just to be contrarian
- Confidence: how confident are you in your verdict (0-100)`, {
        label: `${model}: Challenge claim ${idx + 1}`,
        model: model,
        phase: 'Adversarial Verify',
        schema: VERDICT_SCHEMA
      })
    )).then(votes => {
      const validVotes = votes.filter(Boolean)
      const refuteCount = validVotes.filter(v => v.refuted).length
      const verified = refuteCount < REFUTE_THRESHOLD

      log(`    ${verified ? 'SURVIVED' : 'KILLED'}: ${refuteCount}/${validVotes.length} refuted`)

      return {
        claim: claim.claim,
        page: claim.page,
        pdf_path: claim.pdf_path,
        quote: claim.quote,
        category: claim.category,
        importance: claim.importance,
        original_confidence: claim.confidence,
        proposed_by: claim.proposed_by,
        verified,
        votes: validVotes,
        refute_count: refuteCount,
        vote_count: validVotes.length,
        kill_reason: !verified
          ? validVotes.filter(v => v.refuted).map(v => v.reason).join('; ')
          : null,
        survivor_confidence: verified
          ? Math.round(
              validVotes.filter(v => !v.refuted)
                .reduce((sum, v) => sum + v.confidence, 0) /
              Math.max(1, validVotes.filter(v => !v.refuted).length)
            )
          : 0
      }
    })
  }
)

const verifiedClaims = verificationResults.filter(Boolean).filter(r => r.verified)
const killedClaims = verificationResults.filter(Boolean).filter(r => !r.verified)

log(`Verification complete: ${verifiedClaims.length} survived, ${killedClaims.length} killed`)

// ============================================================================
// PHASE 4: SYNTHESIZE FINDINGS (merge semantic duplicates, group, rank)
// ============================================================================

phase('Synthesize')

log(`Synthesizing ${verifiedClaims.length} verified claims into findings...`)

let synthesis = { findings: [], narrative: 'No claims survived adversarial verification.' }

if (verifiedClaims.length > 0) {
  // Use synthesis arbiter (different from extraction and verification arbiters)
  synthesis = await _agent(`Synthesize verified claims into coherent research findings.

${STRUCTURED_OUTPUT_INSTRUCTION}

RESEARCH TOPIC: ${topic}

VERIFIED CLAIMS (survived adversarial challenge):
${JSON.stringify(verifiedClaims, null, 2)}

INSTRUCTIONS:
1. Merge semantically similar claims into unified findings (second-level dedup)
2. Group findings by category/topic
3. For each finding, list ALL source PDFs and page numbers that contribute
4. Calculate confidence as weighted average of constituent claim confidences
5. Track merged_count (how many claims were merged into each finding)
6. Write a coherent narrative summary (2-4 paragraphs) linking all findings
7. Include caveats and open questions where evidence is limited
8. Order findings by confidence (highest first)`, {
    label: `Arbiter (${SYNTHESIS_ARBITER}): Synthesize findings`,
    model: SYNTHESIS_ARBITER,
    phase: 'Synthesize',
    schema: SYNTHESIS_SCHEMA
  })

  log(`Synthesized into ${synthesis.findings?.length || 0} findings`)
} else {
  log('No claims survived adversarial verification. All claims were refuted.')
}

// ============================================================================
// PHASE 5: SAVE TO MEMORY WITH PDF CITATIONS
// ============================================================================

phase('Save to Memory')

// Note: Date.now() and process.env unavailable in workflows. Memory path will be returned for external save.
const sanitizedTopic = topic.replace(/[^a-zA-Z0-9-_]/g, '-').substring(0, 50)
const memoryFilename = `pdf-research-${sanitizedTopic}.md`

const findings = synthesis?.findings || []
const narrative = synthesis?.narrative || 'No claims survived adversarial verification.'

// Build markdown content with YAML frontmatter (memory-rag-index compatible)
const markdownLines = [
  '---',
  `name: pdf-research-${sanitizedTopic}`,
  `description: Adversarial verification of PDF content for: ${topic}`,
  'metadata:',
  '  node_type: memory',
  '  type: research',
  `  pdfs_count: ${pdfPaths.length}`,
  `  claims_extracted: ${allExtractedClaims.length}`,
  `  claims_verified: ${verifiedClaims.length}`,
  `  claims_killed: ${killedClaims.length}`,
  `  models_used: ${ALL_MODELS.join(', ')}`,
  `  verification_votes: ${VOTES_PER_CLAIM}`,
  `  refute_threshold: ${REFUTE_THRESHOLD}`,
  '---',
  '',
  `# PDF Research: ${topic}`,
  '',
  `**PDFs:** ${pdfPaths.map(p => basename(p)).join(', ')}`,
  `**Models:** ${ALL_MODELS.join(', ')}`,
  `**Verification:** ${VOTES_PER_CLAIM}-vote adversarial, ${REFUTE_THRESHOLD}/${VOTES_PER_CLAIM} threshold`,
  `**Arbiters:** Extraction=${EXTRACTION_ARBITER}, Verification=${VERIFICATION_ARBITER}, Synthesis=${SYNTHESIS_ARBITER}`,
  '',
  '## Summary',
  '',
  narrative,
  '',
  '## Verified Findings',
  '',
]

findings.forEach((f, i) => {
  markdownLines.push(`### ${i + 1}. ${f.finding}`)
  markdownLines.push('')
  markdownLines.push(`**Confidence:** ${f.confidence}%`)
  markdownLines.push(`**Category:** ${f.category || 'uncategorized'}`)
  markdownLines.push(`**Merged from:** ${f.merged_count || 1} claims`)
  markdownLines.push('')
  if (f.sources) {
    markdownLines.push('**Sources:**')
    f.sources.forEach(s => {
      markdownLines.push(`- [PDF: ${basename(s.pdf_path)}, p.${(s.pages || []).join(', ')}]`)
    })
    markdownLines.push('')
  }
})

if (killedClaims.length > 0) {
  markdownLines.push('## Killed Claims (Refuted)')
  markdownLines.push('')
  killedClaims.forEach((k, i) => {
    markdownLines.push(`${i + 1}. **"${k.claim}"** (${basename(k.pdf_path)}, p.${k.page})`)
    markdownLines.push(`   - Refuted by: ${k.refute_count}/${k.vote_count} challengers`)
    markdownLines.push(`   - Reason: ${k.kill_reason}`)
    markdownLines.push('')
  })
}

markdownLines.push('## Methodology')
markdownLines.push('')
markdownLines.push(`- **Worker models:** ${ALL_MODELS.join(', ')}`)
markdownLines.push(`- **Extraction arbiter:** ${EXTRACTION_ARBITER}`)
markdownLines.push(`- **Verification arbiter:** ${VERIFICATION_ARBITER}`)
markdownLines.push(`- **Synthesis arbiter:** ${SYNTHESIS_ARBITER}`)
markdownLines.push(`- **Adversarial protocol:** ${VOTES_PER_CLAIM} voters per claim, ${REFUTE_THRESHOLD}/${VOTES_PER_CLAIM} refutations to kill`)
markdownLines.push(`- **Challenger exclusion:** Proposing models excluded from voting on their own claims`)
markdownLines.push(`- **Max claims verified:** ${MAX_VERIFY_CLAIMS} (ranked by importance then confidence)`)
markdownLines.push('')

const markdownContent = markdownLines.join('\n')

log(`Saving to: ${memoryFilename}`)
log(`Content: ${markdownContent.length} chars`)

// Write using agent (workflows cannot use fs directly)
await _agent(`Write the following content to the file ${memoryFilename} using the Write tool.
Do not modify the content in any way. Write it exactly as provided.

${markdownContent}`, {
  label: 'Save to memory',
  model: 'haiku',
  phase: 'Save to Memory'
})

log(`Saved research findings to: ${memoryFilename}`)

// ============================================================================
// FINAL REPORT
// ============================================================================

log('')
log('='.repeat(80))
log('RESEARCH COMPLETE')
log('='.repeat(80))
log(`Topic: ${topic}`)
log(`PDFs processed: ${pdfPaths.length}`)
log(`Chunks read: ${allChunks.length}`)
log(`Claims extracted: ${allExtractedClaims.length}`)
log(`Claims ranked for verification: ${rankedClaims.length}`)
log(`Claims verified (survived): ${verifiedClaims.length}`)
log(`Claims killed (refuted): ${killedClaims.length}`)
log(`Findings synthesized: ${findings.length}`)
log(`Memory saved: ${memoryFilename}`)
log('='.repeat(80))

return {
  status: 'success',
  topic,
  findings: findings,
  killed_claims: killedClaims.map(k => ({
    claim: k.claim,
    kill_reason: k.kill_reason,
    pdf_path: k.pdf_path,
    page: k.page
  })),
  narrative: narrative,
  metadata: {
    pdfs_processed: pdfPaths.length,
    chunks_read: allChunks.length,
    claims_extracted: allExtractedClaims.length,
    claims_ranked: rankedClaims.length,
    claims_verified: verifiedClaims.length,
    claims_killed: killedClaims.length,
    findings_synthesized: findings.length,
    models_used: ALL_MODELS,
    verification_votes: VOTES_PER_CLAIM,
    refute_threshold: REFUTE_THRESHOLD,
    max_verify_claims: MAX_VERIFY_CLAIMS,
    arbiters: {
      extraction: EXTRACTION_ARBITER,
      verification: VERIFICATION_ARBITER,
      synthesis: SYNTHESIS_ARBITER
    }
  },
  memory_path: memoryFilename
}
