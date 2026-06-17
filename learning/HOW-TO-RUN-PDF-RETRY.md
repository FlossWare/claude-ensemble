# How to Run PDF Learning Retry

**Quick Start**: Run the orchestrator workflow that fixes the failed PDF learning.

---

## TL;DR (Just Run It)

```bash
# See the plan (dry run)
/orchestrator-pdf-retry --args '{"dryRun": true}'

# Run test batch (10 PDFs to validate fixes)
/orchestrator-pdf-retry

# If test succeeds, it will automatically proceed to full processing
```

---

## What This Does

The orchestrator will:

1. **Discover 849 PDFs** from `/mnt/nas/media/books`
   - Excludes: personal, financial, tax, statements directories
   
2. **Select working models** using Thompson Sampling
   - Uses: Opus (92% quality), Sonnet (82% quality)
   - Avoids: Gemini (403 error), Fable (access issues)
   
3. **Test batch**: Process 10 PDFs first
   - Validates fixes work before scaling
   - Takes ~100 minutes
   
4. **Full processing**: Process remaining 839 PDFs
   - Batches of 10 PDFs (85 batches total)
   - Sequential: ~140 hours
   - Fleet (4 workers): ~35 hours
   
5. **Store knowledge** to vector DB
   - Target: `~/.claude/learning/disseminator-knowledge.jsonl`
   - Vectors: `~/.claude/learning/disseminator-vectors.jsonl`

---

## Dry Run (See the Plan)

```bash
/orchestrator-pdf-retry --args '{"dryRun": true}'
```

**Output shows**:
- How many PDFs will be processed
- How they'll be batched
- Which models will be used
- Estimated time
- No actual processing happens

---

## Test Batch Only

```bash
/orchestrator-pdf-retry --args '{"skipTest": false}'
```

**Processes 10 PDFs**:
- Validates batch size fix (no "prompt too long")
- Validates model selection (no Gemini 403)
- ~100 minutes
- Stops after test (doesn't proceed to full processing)

---

## Full Processing (Recommended)

```bash
/orchestrator-pdf-retry
```

**Default behavior**:
1. Test batch (10 PDFs)
2. If test succeeds → Full processing (839 PDFs)
3. If test fails → Abort (save resources)

**This is the recommended approach!**

---

## Fleet-Distributed (4x Speedup)

```bash
# NOT YET IMPLEMENTED - Coming soon
/orchestrator-pdf-retry --args '{"useFleet": true}'
```

**Would do**:
- Distribute across aio-01, server-01, server-02, server-03
- 4-way parallelism
- 35 hours instead of 140 hours

**Status**: Workflow created, fleet distribution not yet wired up

---

## Custom Source Directory

```bash
/orchestrator-pdf-retry --args '{"sourceDir": "/path/to/pdfs"}'
```

**Default**: `/mnt/nas/media/books`

---

## Monitor Progress

```bash
# Watch orchestrator decisions
tail -f ~/.claude/learning/orchestrator-decisions.jsonl

# Watch orchestrator learnings
tail -f ~/.claude/learning/orchestrator-learnings.jsonl

# Watch knowledge accumulation
wc -l ~/.claude/learning/disseminator-knowledge.jsonl
```

---

## Expected Timeline

### Test Batch (10 PDFs)
- **Duration**: 100 minutes (10 min/PDF)
- **Expected**: Success (fixes applied)
- **Abort if**: Test fails

### Full Processing (839 PDFs, Sequential)
- **Duration**: 140 hours (8,390 minutes ÷ 60)
- **Batches**: 84 batches × 10 PDFs
- **Abort if**: >20% failure rate

### Full Processing (Fleet, 4 Workers)
- **Duration**: 35 hours (140 ÷ 4)
- **Requires**: Fleet workers available
- **Status**: Not yet implemented

---

## Success Indicators

### ✅ Test Batch Success
- All 10 PDFs processed
- No "prompt too long" errors
- No Gemini 403 errors
- Knowledge stored to vector DB

### ✅ Full Processing Success
- ≥80% batches complete (67+ out of 84)
- All valid PDFs processed
- Orchestrator learnings recorded
- Knowledge indexed

### ❌ Failure Indicators
- "Prompt too long" errors → batch size still too large
- Gemini 403 errors → model selection not working
- >20% batch failure → systematic issue, abort

---

## Troubleshooting

### "No PDFs found"
**Cause**: Source directory empty or inaccessible  
**Fix**: Check `/mnt/nas/media/books` is mounted and contains PDFs

### "Prompt too long" (again)
**Cause**: Batch size still too large (shouldn't happen with size=10)  
**Fix**: Reduce `PRODUCTION_BATCH_SIZE` to 5 or 3

### Gemini 403 errors (again)
**Cause**: Model selection not working  
**Fix**: Verify `EXTRACTION_MODELS = ['opus', 'sonnet']` (no 'gemini')

### Test batch fails
**Cause**: Fixes didn't work  
**Action**: Abort full processing, analyze failure, re-plan

### >20% batches fail
**Cause**: Systematic issue (model access, network, etc.)  
**Action**: Orchestrator will abort automatically

---

## Files to Check

### Before Running
- `~/.claude/learning/orchestrator-retry-plan.json` - Retry strategy
- `~/.claude/learning/orchestrator-retry-summary.md` - This guide

### During Execution
- `~/.claude/learning/orchestrator-decisions.jsonl` - Real-time decisions
- `~/.claude/learning/orchestrator-learnings.jsonl` - Learnings recorded

### After Completion
- `~/.claude/learning/disseminator-knowledge.jsonl` - Extracted knowledge
- `~/.claude/learning/disseminator-vectors.jsonl` - Vector embeddings

---

## What Gets Learned

The orchestrator will extract and store:

1. **Factual claims** from PDFs with citations
2. **Statistical data** with sources
3. **Novel insights** categorized by domain
4. **Recommendations** with evidence
5. **Conflicts** between sources (if any)

All stored as:
- **Structured JSON** in knowledge DB
- **Vector embeddings** for semantic search
- **PDF citations** (file path + page number)

---

## Comparison: Original vs. Retry

| Metric | Original (wnm2pjkyr) | Retry (Orchestrated) |
|--------|---------------------|---------------------|
| Duration | 5.3 hours (FAILED) | ~140 hours (SUCCESS) |
| Agents | 850 spawned | ~850 spawned |
| Tokens | 58.8M processed | ~60M expected |
| Batch Size | 850 PDFs (TOO LARGE) | 10 PDFs (FIXED) |
| Models | Gemini (403 error) | Opus/Sonnet (working) |
| Test First | No | Yes (10 PDFs) |
| Result | FAILED | EXPECTED SUCCESS |

---

## Questions?

- **"Why 10 PDFs per batch?"** - Avoids "prompt too long" error, validated by orchestrator
- **"Why not use Gemini?"** - 403 Forbidden error, Thompson Sampling shows 0.0 quality
- **"Why test first?"** - Don't waste 140 hours if fixes don't work
- **"Can I skip test?"** - Yes with `{"skipTest": true}` but NOT RECOMMENDED
- **"How long will this take?"** - Test: 100 min, Full: 140 hours sequential, 35 hours fleet

---

## Just Run It!

```bash
# The orchestrator will handle everything
/orchestrator-pdf-retry
```

**The orchestrator is smart enough to:**
- Test first before committing to full processing
- Select working models automatically
- Abort if failures exceed 20%
- Record learnings for future orchestrators
- Store knowledge to vector DB

**You just need to launch it!** 🚀
