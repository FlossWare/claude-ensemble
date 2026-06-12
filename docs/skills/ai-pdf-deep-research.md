# ai-pdf-deep-research

Adversarial verification of PDF content using 6-model consensus with adversarial challenge voting.

## Skill Metadata

| Attribute | Value |
|-----------|-------|
| **ID** | `ai-pdf-deep-research` |
| **Type** | Workflow |
| **Location** | `workflows/ai-pdf-deep-research.js` |
| **Pattern** | Arbiter/Worker with adversarial verification + challenger exclusion |
| **Models** | 6-model maximum coverage (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini) |
| **Execution** | `pipeline()` for sequential processing, nested `parallel()` for worker fan-out |
| **Reliability** | Production-ready with graceful degradation |

## When to Use

Use this skill when you need to:

- **Critically analyze PDF documents** - Extract and verify claims against adversarial challenge
- **Fact-check research papers** - Determine which claims survive skeptical scrutiny
- **Assess document reliability** - See what survives adversarial refutation attempts
- **Multi-source verification** - Cross-check claims from multiple PDFs
- **Create verified research summaries** - Generate findings with confidence scores and refutation data

**Not suitable for:**
- Simple text extraction (use Read tool directly)
- Document classification without verification
- High-volume batch processing (designed for deep analysis, not speed)

## Input Parameters

### Required

```javascript
{
  pdfs: ["/absolute/path/to/paper1.pdf", "/absolute/path/to/paper2.pdf"],
  topic: "your research question or topic"
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `pdfs` (or `pdf_paths`) | `string[]` | Array of absolute paths to PDF files to analyze |
| `topic` (or `question`) | `string` | Research topic or question guiding claim extraction and verification |

### Optional

None. All behavior is controlled by internal configuration constants.

## Configuration Constants

These are hardcoded in the workflow and can be modified for different analysis depths:

```javascript
const ALL_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
const PAGES_PER_CHUNK = 20              // How many pages per read chunk
const VOTES_PER_CLAIM = 3               // Adversarial votes per claim
const REFUTE_THRESHOLD = 2              // 2 of 3 refutes = claim killed
const MAX_VERIFY_CLAIMS = 25            // Cap verification to control cost
const MIN_WORKERS_REQUIRED = 2          // Graceful degradation floor
```

**Arbiter rotation** (different per phase for diverse perspectives):
- `EXTRACTION_ARBITER = 'fable'` - Deduplicates extracted claims
- `VERIFICATION_ARBITER = 'opus'` - (For future use if desired)
- `SYNTHESIS_ARBITER = 'sonnet'` - Merges findings and writes narrative

## Workflow Phases

### Phase 1: Read PDFs (20-page chunks)

**What it does:**
1. Probes each PDF to determine page count
2. Chunks PDFs into 20-page ranges
3. Reads each chunk sequentially using the Read tool
4. Gracefully skips unreadable PDFs

**Why this design:**
- Avoids overwhelming the Read tool with massive PDFs
- Allows agent to extract page numbers and context from chunks
- Handles PDF corruption with fallback logic

**Output:** Array of chunks with `{ pdf_path, filename, content, page_range, title }`

---

### Phase 2: Extract Claims (6 workers per chunk, arbiter dedup)

**What it does:**
1. **Parallel worker extraction**: All 6 models extract falsifiable claims from each chunk
   - Each worker finds up to 5 claims per chunk
   - Workers rate by confidence, importance (central/supporting/tangential), category
   - Marks claims as falsifiable (testable) or not
   
2. **Arbiter deduplication** (Fable):
   - Merges semantically identical claims
   - Keeps highest confidence for duplicates
   - Removes non-falsifiable claims (opinions, definitions)
   - Tracks which models proposed each claim

3. **Ranking and capping**:
   - Sorts by importance (central → supporting → tangential) then confidence
   - Caps at MAX_VERIFY_CLAIMS to control verification cost
   - Removes non-falsifiable items

**Output:** Deduplicated claims with page numbers, quotes, confidence, and `proposed_by` array

---

### Phase 3: Adversarial Verification (3-vote per claim)

**What it does:**
1. **Challenger selection** (per claim):
   - Selects 3 random models to challenge the claim
   - **Excludes proposing models** - the models that proposed the claim don't vote on it
   - Falls back to full model pool if exclusion leaves too few models

2. **Adversarial voting** (parallel per claim):
   - Each challenger tries to REFUTE the claim
   - Looks for logical fallacies, unsupported leaps, context problems
   - Checks if evidence actually supports the claim
   - Returns verdict: `refuted` (boolean), `reason` (string), `confidence` (0-100)

3. **Vote tallying**:
   - **Kill threshold**: 2 or more refutations (out of 3) = claim killed
   - **Survive**: Fewer than 2 refutations = claim verified
   - Tracks survivor confidence from non-refuting voters

**Why adversarial:**
- Standard validation often confirms biases
- Adversarial refutation forces critical thinking
- Exclusion prevents models from defending their own claims

**Output:** Verification results with `{ verified, votes, refute_count, kill_reason, survivor_confidence }`

---

### Phase 4: Synthesize Findings

**What it does:**
1. **Second-level deduplication**: Merges semantically similar verified claims
2. **Categorization**: Groups findings by topic/theme
3. **Source tracking**: Records all PDFs and pages contributing to each finding
4. **Confidence calculation**: Weighted average of constituent claim confidences
5. **Narrative writing**: 2-4 paragraph coherent summary including:
   - Main findings and their relationships
   - Caveats where evidence is limited
   - Open questions and gaps

**Output:** `{ findings[], narrative }`

Each finding includes:
- `finding` - Synthesized statement
- `claims[]` - Original claim texts
- `sources[]` - Array of `{ pdf_path, pages[] }`
- `confidence` - 0-100 score
- `merged_count` - How many claims merged into this finding

---

### Phase 5: Save to Memory

**What it does:**
1. Creates markdown file in `~/.claude/memory/` with YAML frontmatter
2. Frontmatter includes metadata for `memory-rag-index` integration:
   - Document type, date, PDF count, claims metrics, models used
3. Sections:
   - Summary (narrative)
   - Verified Findings (with sources and confidence)
   - Killed Claims (with refutation reasons)
   - Methodology (transparent documentation of process)

**Memory path format:** `pdf-research-{sanitized-topic}-{date}.md`

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

## Output Format

### Return Value

```javascript
{
  status: "success",
  topic: "your research topic",
  findings: [
    {
      finding: "Synthesized claim statement",
      claims: ["original claim 1", "original claim 2"],
      sources: [{ pdf_path: "/path/to/file.pdf", pages: [5, 12] }],
      category: "factual|statistical|causal|other",
      confidence: 85,
      merged_count: 2
    }
  ],
  killed_claims: [
    {
      claim: "Refuted claim statement",
      kill_reason: "Reason for refutation",
      pdf_path: "/path/to/file.pdf",
      page: 42
    }
  ],
  narrative: "Coherent 2-4 paragraph summary...",
  metadata: {
    pdfs_processed: 3,
    chunks_read: 8,
    claims_extracted: 45,
    claims_ranked: 25,
    claims_verified: 28,
    claims_killed: 17,
    findings_synthesized: 12,
    models_used: ["fable", "opus", "sonnet", "haiku", "gpt-4o", "gemini"],
    verification_votes: 3,
    refute_threshold: 2,
    max_verify_claims: 25,
    arbiters: {
      extraction: "fable",
      verification: "opus",
      synthesis: "sonnet"
    }
  },
  memory_path: "/home/user/.claude/memory/pdf-research-topic-2026-06-12.md"
}
```

### Side Effects

- Writes markdown file to `~/.claude/memory/pdf-research-{topic}-{date}.md`
- Logs verbose execution trace to console
- **Note**: Use `memory-rag-index` to register the memory file for semantic search

## Example Usage

### Basic Usage

```javascript
const result = await workflow("ai-pdf-deep-research", {
  pdfs: [
    "/home/user/papers/paper1.pdf",
    "/home/user/papers/paper2.pdf"
  ],
  topic: "quantum computing error correction"
});

console.log(`Verified ${result.findings.length} findings`);
console.log(`Killed ${result.killed_claims.length} claims`);
console.log(`Memory saved to: ${result.memory_path}`);
```

### With CLI (via skill invocation)

```bash
# From Claude Code CLI
/ai-pdf-deep-research --pdfs /path/to/paper1.pdf,/path/to/paper2.pdf --topic "climate change impacts"
```

### Processing Multiple PDFs

```javascript
const pdfs = [
  "/research/climate-2020.pdf",
  "/research/climate-2021.pdf",
  "/research/climate-2022.pdf"
];

const result = await workflow("ai-pdf-deep-research", {
  pdfs: pdfs,
  topic: "global temperature trends 2020-2022"
});

// Results include all PDFs cross-referenced
result.findings.forEach(f => {
  console.log(`Finding: ${f.finding}`);
  f.sources.forEach(s => {
    console.log(`  - ${s.pdf_path}: pages ${s.pages.join(', ')}`);
  });
});
```

## How It Works: Detailed Architecture

### Claim Extraction Pipeline

```
PDF Chunks
    ↓
[6 Workers in parallel] ← Extract falsifiable claims (max 5 each)
    ↓
[Fable Arbiter] ← Deduplicate, remove non-falsifiable
    ↓
Rank by importance + confidence
    ↓
Cap at MAX_VERIFY_CLAIMS (25)
```

### Adversarial Verification Pipeline

```
Each Ranked Claim
    ↓
Select 3 challengers (exclude proposers)
    ↓
[3 Challengers in parallel] ← Try to REFUTE the claim
    ↓
Tally votes:
  - 2+ refutations → KILL claim
  - 0-1 refutations → VERIFY claim
    ↓
Track survivor confidence
```

### Synthesis Pipeline

```
Verified Claims
    ↓
[Sonnet Arbiter] ← Merge semantic duplicates
    ↓
Group by category
    ↓
Calculate confidence (weighted avg)
    ↓
Write coherent narrative
    ↓
Findings array + narrative text
```

## JSON Schemas

All agent outputs must match these schemas for structured validation.

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
        {
          "pdf_path": "string",
          "pages": [5, 12]
        }
      ],
      "category": "string",
      "confidence": "0-100",
      "merged_count": "number"
    }
  ],
  "narrative": "string (2-4 paragraphs)"
}
```

## Error Handling & Graceful Degradation

### Unreadable PDFs
- **Behavior**: Logs warning, skips PDF, continues processing
- **Mitigation**: Gracefully handles corrupted or protected PDFs
- **Fallback**: Returns results from processable PDFs

### Failed Agent Calls
- **Behavior**: Catches errors in chunk reading (try/catch at lines 267-288)
- **Mitigation**: Uses `continue` to skip failed chunks
- **Fallback**: Processes remaining chunks

### Insufficient Workers
- **Behavior**: Logs warning if fewer than MIN_WORKERS_REQUIRED succeed
- **Mitigation**: Proceeds with valid responses
- **Floor**: MIN_WORKERS_REQUIRED = 2 (requires at least 2 workers to proceed)

### Model Exclusion Fallback
- **Behavior**: If excluding proposing models leaves fewer challengers than needed
- **Mitigation**: Falls back to full model pool (lines 202-208)
- **Logic**: `available.length >= count ? available : ALL_MODELS`

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| **PDF Chunk Size** | 20 pages | Reduces per-call token usage |
| **Workers per chunk** | 6 | Full model set for diversity |
| **Claims per worker** | 5 max | Controls extraction volume |
| **Verification votes** | 3 per claim | Odd number ensures majority |
| **Max claims verified** | 25 | Ranked by importance + confidence |
| **Cost** | High | 6-model extraction + 3-vote verification |
| **Execution time** | Medium-High | Sequential phases with parallel workers |

### Cost Optimization Tips

1. **Reduce `PAGES_PER_CHUNK`** to 10 for shorter PDFs
2. **Lower `MAX_VERIFY_CLAIMS`** to 10-15 for budget constraints
3. **Use smaller model set** - modify `ALL_MODELS` to `['sonnet', 'haiku']`
4. **Sample pages** - call workflow on first 50 pages for quick analysis

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
  urls: ["https://example.com/article1", "https://example.com/article2"]
});

const pdfAnalysis = await workflow("ai-pdf-deep-research", {
  pdfs: ["/path/to/paper.pdf"],
  topic: webLearnings.metadata.topic
});
```

### code-security (for analyzing security documentation)
Verify security claims in technical PDFs:

```javascript
const analysis = await workflow("ai-pdf-deep-research", {
  pdfs: ["/docs/security-policy.pdf"],
  topic: "encryption algorithm security properties"
});
```

## Debugging & Troubleshooting

### Enable Verbose Logging
The workflow logs each phase and step. Review console output for:
- `Read PDFs` - chunk loading status
- `Extract Claims` - worker success rates
- `Adversarial Verify` - vote tallies per claim
- `Synthesize` - merged findings count
- `Save to Memory` - file path confirmation

### Common Issues

**No claims extracted**
- **Cause**: PDF content not being read properly
- **Solution**: Manually read first chunk using Read tool to verify PDF is accessible

**All claims killed**
- **Cause**: Claims may be overgeneralized or challenged too aggressively
- **Solution**: Review `kill_reason` field in output; may indicate weak sourcing

**Memory file not created**
- **Cause**: Write tool permission issue or path problem
- **Solution**: Check `~/.claude/memory/` directory exists and is writable

**Worker failures**
- **Cause**: Model overload or quota issues
- **Solution**: Reduce `ALL_MODELS` array or wait and retry

## Best Practices

1. **Use absolute paths** - Workflow requires absolute PDF paths
2. **Clear topic** - More specific topics yield better claim extraction
3. **Index results** - Use `memory-rag-index` to make findings searchable
4. **Review killed claims** - Understand refutation reasoning
5. **Check sources** - Verify findings link back to original PDF pages
6. **Update memory** - Re-run on updated PDFs for comparative analysis

## Technical Implementation Details

### No Bash in Workflows
The workflow uses `agent()` calls with Read tool instead of Bash commands for file reading (lines 268-273).

### Structured Agent Instructions
Agents receive explicit instructions to:
- Use Read tool only (not Bash)
- Return valid JSON matching schemas
- Write files using Write tool (line 639)
- Never modify provided content (line 640)

### Arbiter Rotation
Different arbiters per phase ensure diverse perspectives:
- **Extraction phase**: Fable (quick deduplication)
- **Synthesis phase**: Sonnet (coherent narrative)
- (Verification phase: Currently uses worker set, could add future optimization)

### Memory Persistence Format
YAML frontmatter compatible with `memory-rag-index`:
```yaml
---
name: pdf-research-{topic}-{date}
description: Adversarial verification findings
metadata:
  node_type: memory
  type: research
  ...
---
```

## Related Workflows

- **ai-deep-research** - Web-based adversarial research (sibling workflow)
- **deep-research** - Skill wrapper for ai-deep-research
- **memory-rag-index** - Index memory files for semantic search
- **ai-web-learn-production** - Learn from web sources with similar pattern

## Known Limitations

1. **PDF Complexity**: Scanned PDFs (images only) cannot be processed
2. **Large Files**: 500+ page PDFs may require memory.json adjustment
3. **Multilingual**: Primarily optimized for English content
4. **Math/Code**: Complex mathematical proofs or code snippets may be extracted as non-falsifiable
5. **Context Window**: Very long claim justifications may be truncated in agent calls

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-12 | Initial production release with 6-model adversarial verification |

## Support & Contributing

For issues, improvements, or feature requests:
- Check workflow logs for execution trace
- Review memory file generated for detailed methodology
- Verify PDF accessibility with Read tool
- Test with simpler PDFs first before complex documents
