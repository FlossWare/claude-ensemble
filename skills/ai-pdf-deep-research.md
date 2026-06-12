---
name: ai-pdf-deep-research
description: Adversarial PDF verification - extract claims, 3-vote refutation, synthesize findings
---

# AI PDF Deep Research - Adversarial PDF Content Verification

Critically analyze PDF documents by extracting falsifiable claims, adversarially challenging them with multi-model consensus, and synthesizing verified findings into a cited research report.

## Features

- **6-Model Maximum Coverage** - Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini all participate
- **Adversarial Verification** - 3-vote refutation protocol: 2/3 refutations kill a claim
- **Challenger Exclusion** - Models that proposed a claim cannot vote on it
- **Arbiter Rotation** - Different arbiter per phase (Fable, Opus, Sonnet) to eliminate single-model bias
- **Smart Chunking** - PDFs split into 20-page chunks for thorough reading
- **Importance Ranking** - Claims ranked central > supporting > tangential before verification
- **Memory Persistence** - Findings saved as YAML-frontmatter markdown compatible with memory-rag-index
- **Graceful Degradation** - Unreadable PDFs, failed chunks, and insufficient workers handled without aborting

## When to Use

Use this skill when you need to:

- **Critically analyze PDF documents** - Extract and verify claims against adversarial challenge
- **Fact-check research papers** - Determine which claims survive skeptical scrutiny
- **Assess document reliability** - See what survives adversarial refutation attempts
- **Multi-source verification** - Cross-check claims from multiple PDFs
- **Create verified research summaries** - Generate findings with confidence scores and refutation data
- **Policy or legal analysis** - Verify statistical and causal claims in regulatory or legal documents

**Not suitable for:**
- Simple text extraction (use Read tool directly)
- Document classification without verification
- High-volume batch processing (designed for deep analysis, not speed)
- Scanned/image-only PDFs (requires text-based PDFs)

## Usage

```bash
# Analyze a single PDF
/ai-pdf-deep-research { "pdfs": ["/path/to/paper.pdf"], "topic": "climate change mitigation strategies" }

# Analyze multiple PDFs on a topic
/ai-pdf-deep-research { "pdfs": ["/path/to/paper1.pdf", "/path/to/paper2.pdf", "/path/to/paper3.pdf"], "topic": "effectiveness of microservices vs monoliths" }

# General analysis (no specific topic)
/ai-pdf-deep-research { "pdfs": ["/path/to/report.pdf"] }
```

## Input Parameters

| Parameter | Aliases | Type | Required | Description |
|-----------|---------|------|----------|-------------|
| `pdf_paths` | `pdfs` | `string[]` | Yes | Array of absolute paths to PDF files |
| `topic` | `question` | `string` | No | Research question or topic to focus analysis (default: "general analysis") |

All other behavior is controlled by internal configuration constants (see below).

## Workflow Phases

### Phase 1: Read PDFs

- Probes each PDF with Haiku to determine total page count
- Chunks into 20-page ranges using `generatePageRanges()`
- Reads each chunk sequentially within a PDF via `pipeline()`
- Skips unreadable PDFs or chunks gracefully (try/catch with `continue`)

**Output:** Array of chunks with `{ pdf_path, filename, content, page_range, title }`

### Phase 2: Extract Claims

1. **Parallel worker extraction**: All 6 models independently extract up to 5 falsifiable claims per chunk via `parallel()`
   - Workers rate by confidence (0-100), importance (central/supporting/tangential), and category (factual/statistical/causal/other)
   - Marks claims as falsifiable (testable) or not

2. **Arbiter deduplication (Fable)**:
   - Merges semantically identical claims, keeping highest confidence
   - Combines `proposed_by` arrays to track which models found each claim
   - Removes non-falsifiable claims (opinions, definitions)

3. **Ranking and capping**:
   - Sorts by importance (central > supporting > tangential) then confidence
   - Caps at MAX_VERIFY_CLAIMS (25) to control verification cost

**Output:** Deduplicated claims with page numbers, quotes, confidence, and `proposed_by` array

### Phase 3: Adversarial Verify

1. **Challenger selection (per claim)**: 3 random models selected, excluding the models that proposed the claim. Falls back to full model pool if exclusion leaves fewer than 3 challengers.

2. **Adversarial voting (parallel per claim)**: Each challenger defaults to a skeptical stance and attempts to refute the claim, looking for:
   - Logical fallacies and unsupported leaps
   - Contradictions with established knowledge
   - Overgeneralization or out-of-context quotation
   - Outdated or superseded information

3. **Vote tallying**: If 2 of 3 challengers refute a claim, it is **killed**. Surviving claims carry a `survivor_confidence` averaged from non-refuting voters. Killed claims retain `kill_reason` with concatenated refutation reasoning.

**Output:** Verification results with `{ verified, votes, refute_count, kill_reason, survivor_confidence }`

### Phase 4: Synthesize

- **Arbiter (Sonnet):** Merges semantically similar surviving claims into unified findings
- Groups findings by category/topic
- Calculates confidence as weighted average of constituent claims
- Writes a 2-4 paragraph narrative summary with caveats and open questions
- Findings ordered by confidence (highest first)

**Output:** `{ findings[], narrative }`

### Phase 5: Save to Memory

- Saves findings to `~/.claude/memory/pdf-research-<sanitized-topic>-<date>.md`
- YAML frontmatter includes all metadata (compatible with memory-rag-index)
- Sections: Summary, Verified Findings (with PDF citations), Killed Claims, Methodology
- Written via agent using the Write tool to maintain workflow isolation

## Output Format

### Return Value

```json
{
  "status": "success",
  "topic": "research question",
  "findings": [
    {
      "finding": "Unified finding statement",
      "claims": ["claim1", "claim2"],
      "sources": [
        { "pdf_path": "/path/to/paper.pdf", "pages": [5, 12] }
      ],
      "category": "factual",
      "confidence": 87,
      "merged_count": 3
    }
  ],
  "killed_claims": [
    {
      "claim": "Refuted claim text",
      "kill_reason": "Challenger reasoning for refutation",
      "pdf_path": "/path/to/paper.pdf",
      "page": 7
    }
  ],
  "narrative": "Coherent 2-4 paragraph summary of all findings...",
  "metadata": {
    "pdfs_processed": 2,
    "chunks_read": 8,
    "claims_extracted": 42,
    "claims_ranked": 25,
    "claims_verified": 18,
    "claims_killed": 7,
    "findings_synthesized": 12,
    "models_used": ["fable", "opus", "sonnet", "haiku", "gpt-4o", "gemini"],
    "verification_votes": 3,
    "refute_threshold": 2,
    "max_verify_claims": 25,
    "arbiters": {
      "extraction": "fable",
      "verification": "opus",
      "synthesis": "sonnet"
    }
  },
  "memory_path": "~/.claude/memory/pdf-research-topic-2026-06-12.md"
}
```

### Memory File

Saved to `~/.claude/memory/pdf-research-<sanitized-topic>-<date>.md` with:

- YAML frontmatter (memory-rag-index compatible)
- Summary narrative
- Numbered verified findings with confidence, category, and PDF source citations
- Killed claims section with refutation reasons
- Methodology section documenting models and parameters

**Frontmatter example:**
```yaml
---
name: pdf-research-quantum-computing-2026-06-12
description: Adversarial verification of PDF content for: quantum computing benchmarks
metadata:
  node_type: memory
  type: research
  date: 2026-06-12
  pdfs_count: 3
  claims_extracted: 45
  claims_verified: 28
  claims_killed: 17
  models_used: fable, opus, sonnet, haiku, gpt-4o, gemini
  verification_votes: 3
  refute_threshold: 2
---
```

## Example

```bash
$ /ai-pdf-deep-research { "pdfs": ["/tmp/climate-report-2025.pdf", "/tmp/ipcc-ar6.pdf"], "topic": "carbon capture effectiveness" }

================================================================================
AI-PDF-DEEP-RESEARCH: Adversarial PDF Verification
================================================================================
Topic: carbon capture effectiveness
PDFs: 2
Models: fable, opus, sonnet, haiku, gpt-4o, gemini
Votes per claim: 3 (threshold: 2/3 to kill)
Max claims to verify: 25
================================================================================

Phase: Read PDFs
  Reading: /tmp/climate-report-2025.pdf
    climate-report-2025.pdf: ~45 pages, 3 chunks
  Reading: /tmp/ipcc-ar6.pdf
    ipcc-ar6.pdf: ~120 pages, 6 chunks
Read 9 chunks from 2 PDFs

Phase: Extract Claims
  Extracting from climate-report-2025.pdf chunk 0 (p.1-20)
    6/6 workers returned 24 claims
  ...
Extracted 38 unique falsifiable claims (14 removed)
Ranked and capped to 25 claims for verification

Phase: Adversarial Verify
  [1/25] "DAC costs have fallen below $200/ton..." challengers: haiku, gemini, opus
    SURVIVED: 0/3 refuted
  [2/25] "Carbon capture can offset 50% of emissions..." challengers: sonnet, gpt-4o, haiku
    KILLED: 2/3 refuted
  ...
Verification complete: 18 survived, 7 killed

Phase: Synthesize
Synthesized into 12 findings

Phase: Save to Memory
Saved research findings to: ~/.claude/memory/pdf-research-carbon-capture-effectiveness-2026-06-12.md

================================================================================
RESEARCH COMPLETE
================================================================================
```

## Use Cases

- **Literature Review** - Verify claims across multiple research papers
- **Report Validation** - Check whether a report's claims withstand adversarial scrutiny
- **Due Diligence** - Critically assess whitepapers, technical reports, or proposals
- **Fact-Checking** - Identify unsupported or refutable claims in documents
- **Research Synthesis** - Merge findings across multiple PDFs into coherent analysis
- **Policy Analysis** - Verify statistical and causal claims in policy documents

## Configuration Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `ALL_MODELS` | 6 models | fable, opus, sonnet, haiku, gpt-4o, gemini |
| `PAGES_PER_CHUNK` | 20 | Pages per reading chunk |
| `VOTES_PER_CLAIM` | 3 | Adversarial challengers per claim |
| `REFUTE_THRESHOLD` | 2 | Votes needed to kill a claim (2/3) |
| `MAX_VERIFY_CLAIMS` | 25 | Maximum claims sent to verification |
| `MIN_WORKERS_REQUIRED` | 2 | Minimum workers for graceful degradation |
| `EXTRACTION_ARBITER` | fable | Arbiter for claim extraction/dedup |
| `VERIFICATION_ARBITER` | opus | Arbiter for adversarial verification |
| `SYNTHESIS_ARBITER` | sonnet | Arbiter for final synthesis |
| `IMPORTANCE_RANK` | central=0, supporting=1, tangential=2 | Sorting priority for claim ranking |

### Cost Optimization Tips

1. **Reduce `PAGES_PER_CHUNK`** to 10 for shorter PDFs
2. **Lower `MAX_VERIFY_CLAIMS`** to 10-15 for budget constraints
3. **Use smaller model set** - modify `ALL_MODELS` to `['sonnet', 'haiku']`
4. **Sample pages** - call workflow on first 50 pages for quick analysis

## Architecture

```
Input: pdf_paths[], topic
  |
  v
Phase 1: Read PDFs [pipeline]
  haiku probes each PDF -> chunk into 20-page ranges -> read sequentially
  |
  v
Phase 2: Extract Claims [pipeline(parallel + arbiter)]
  6 workers extract claims per chunk in parallel
  fable arbiter deduplicates and filters
  ranked by importance -> confidence, capped at 25
  |
  v
Phase 3: Adversarial Verify [pipeline(parallel)]
  3 challengers per claim (proposing models excluded)
  2/3 refutations = claim killed
  |
  v
Phase 4: Synthesize [arbiter]
  sonnet merges surviving claims into findings
  generates narrative with caveats
  |
  v
Phase 5: Save to Memory [agent]
  YAML frontmatter markdown -> ~/.claude/memory/
  |
  v
Output: { status, findings, killed_claims, narrative, metadata, memory_path }
```

### Claim Extraction Pipeline

```
PDF Chunks
    |
[6 Workers in parallel] -- Extract falsifiable claims (max 5 each)
    |
[Fable Arbiter] -- Deduplicate, remove non-falsifiable
    |
Rank by importance + confidence
    |
Cap at MAX_VERIFY_CLAIMS (25)
```

### Adversarial Verification Pipeline

```
Each Ranked Claim
    |
Select 3 challengers (exclude proposers)
    |
[3 Challengers in parallel] -- Try to REFUTE the claim
    |
Tally votes:
  - 2+ refutations -> KILL claim
  - 0-1 refutations -> VERIFY claim
    |
Track survivor confidence
```

## JSON Schemas

Four schemas govern structured output across all phases:

### Claim Extraction Schema

```json
{
  "claims": [
    {
      "claim": "string (falsifiable statement)",
      "page": "number",
      "quote": "string (direct PDF quote)",
      "confidence": "0-100",
      "category": "factual|statistical|causal|other",
      "importance": "central|supporting|tangential",
      "falsifiable": "boolean"
    }
  ],
  "model": "string (model name)"
}
```

### Deduplication Schema

```json
{
  "deduplicated_claims": [
    {
      "claim": "string",
      "page": "number",
      "pdf_path": "string",
      "quote": "string",
      "confidence": "0-100",
      "category": "string",
      "importance": "string",
      "falsifiable": "boolean",
      "proposed_by": ["model1", "model2"]
    }
  ],
  "duplicates_removed": "number",
  "non_falsifiable_removed": "number"
}
```

### Verdict Schema

```json
{
  "refuted": "boolean",
  "reason": "string (detailed refutation logic)",
  "confidence": "0-100"
}
```

### Synthesis Schema

```json
{
  "findings": [
    {
      "finding": "string",
      "claims": ["claim1", "claim2"],
      "sources": [
        { "pdf_path": "string", "pages": [5, 12] }
      ],
      "category": "string",
      "confidence": "0-100",
      "merged_count": "number"
    }
  ],
  "narrative": "string (2-4 paragraphs)"
}
```

## Error Handling and Graceful Degradation

| Scenario | Behavior | Fallback |
|----------|----------|----------|
| **Unreadable PDF** | Logs warning, skips PDF | Returns results from processable PDFs |
| **Failed chunk read** | Catches error, uses `continue` | Processes remaining chunks |
| **Insufficient workers** | Logs warning if < MIN_WORKERS_REQUIRED succeed | Proceeds with valid responses (floor: 2 workers) |
| **Model exclusion leaves too few challengers** | Falls back to full model pool | All 6 models become eligible challengers |
| **All claims killed** | Returns empty findings with narrative explaining outcome | `kill_reason` fields document refutation logic |
| **No PDF chunks readable** | Aborts with error status | Returns `{ error, status: "failed" }` |

## Integration with Other Skills

### memory-rag-index
After workflow completes, index the memory file for semantic search:

```javascript
await workflow("memory-rag-index", {
  memory_file: result.memory_path
});
```

### ai-web-learn-production
Combine with web learning for multi-source verification:

```javascript
const webLearnings = await workflow("ai-web-learn-production", {
  urls: ["https://example.com/article1"]
});

const pdfAnalysis = await workflow("ai-pdf-deep-research", {
  pdfs: ["/path/to/paper.pdf"],
  topic: webLearnings.metadata.topic
});
```

## Debugging and Troubleshooting

### Common Issues

**No claims extracted**
- PDF content not being read properly. Manually read first chunk using Read tool to verify PDF is accessible.

**All claims killed**
- Claims may be overgeneralized or sourcing is weak. Review `kill_reason` field in output.

**Memory file not created**
- Write tool permission issue or path problem. Check `~/.claude/memory/` exists and is writable.

**Worker failures**
- Model overload or quota issues. Reduce `ALL_MODELS` array or wait and retry.

## Known Limitations

- **PDF format**: Text-based PDFs only; scanned/image PDFs require OCR preprocessing
- **Language**: Optimized for English; other languages may reduce accuracy
- **Citation precision**: Page numbers accurate to +/-1 page for chunked extractions
- **Maximum size**: Recommended <500 pages per PDF; larger documents should be split
- **Math/Code**: Complex mathematical proofs or code snippets may be extracted as non-falsifiable
- **Rate limits**: Processes PDFs sequentially to respect API rate limits

## Comparison to deep-research

| Feature | ai-pdf-deep-research | deep-research |
|---------|---------------------|---------------|
| Input | Local PDF files | Web URLs |
| Extraction | PDF.js page parsing via Read tool | HTML markdown conversion |
| Citations | [PDF: file.pdf, p.X] | [Source: url] |
| Offline capable | Yes (after download) | No |
| Rate limits | API only | API + web scraping |

## Installation Requirements

- Claude Code CLI with workflow support
- Workflow file: `~/.claude/workflows/ai-pdf-deep-research.js`
- Skill file: `~/.claude/skills/ai-pdf-deep-research.md`
- Access to all 6 models (fable, opus, sonnet, haiku, gpt-4o, gemini)
- PDF files must be locally accessible (absolute paths)
- Memory directory: `~/.claude/memory/` (created automatically)

## Related

- `/deep-research` - Web-based adversarial research (same verification pattern, web sources)
- `/ai-prompt` - Multi-model consensus for single questions
- `/memory-rag-index` - Index memory files for RAG retrieval
- `/memory-rag-search` - Search indexed memory files
- Workflow: `ai-pdf-deep-research.js`
- Pattern: TEMPLATE-arbiter-worker.js

---

**Version**: 1.0
**Created**: 2026-06-12
**Global**: Works on any PDF files
