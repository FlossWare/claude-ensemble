# Model Profiling - Quick Start Guide

## What This Does

Automatically tests all 252 discovered free models to determine what they're good at:
- ✅ Code generation
- ✅ Code review
- ✅ Research/summarization
- ✅ Math/reasoning
- ✅ General QA

Results stored in PostgreSQL so the orchestrator knows which model to use for which task.

## Quick Commands

### Check current status:
```bash
./scripts/profile-models.sh status
```

### Profile top 10 models (Quick test - ~2 hours):
```bash
./scripts/profile-models.sh quick
```

### Profile top 50 models (Recommended - ~10 hours):
```bash
./scripts/profile-models.sh tier1
```

### Profile specific provider:
```bash
./scripts/profile-models.sh provider mistral
./scripts/profile-models.sh provider groq
```

### Profile single model:
```bash
./scripts/profile-models.sh single qwen/qwen3-coder:free
```

### View top models:
```bash
./scripts/profile-models.sh top
```

## How It Works

**For each model, the workflow:**
1. Sends 5 standard test tasks
2. Uses Opus to evaluate the responses
3. Calculates scores (0.0-1.0) for each capability
4. Stores in `learning.model_capabilities`

**Example test tasks:**
- Code: "Write a merge sort implementation"
- Review: "Find bugs in this code" (tests for division-by-zero detection)
- Research: "Explain the Transformer architecture"
- Math: "If 5 machines take 5 min to make 5 widgets..."
- QA: "What is dependency injection?"

## Results

**After profiling, you can:**

Query best model for code:
```sql
SELECT model_id, code_generation, avg_latency_ms
FROM learning.model_capabilities
WHERE code_generation IS NOT NULL
ORDER BY code_generation DESC
LIMIT 5;
```

Find fast models:
```sql
SELECT model_id, general_qa
FROM learning.model_capabilities
WHERE avg_latency_ms < 2000 AND general_qa > 0.7;
```

Get all capabilities for a model:
```sql
SELECT * FROM learning.model_capabilities
WHERE model_id = 'qwen/qwen3-coder:free';
```

## Recommended Strategy

**Day 1: Quick validation**
```bash
./scripts/profile-models.sh quick
# Profiles 10 models in ~2 hours
# Validates the system works
```

**Day 2: Overnight batch**
```bash
# Start before bed:
./scripts/profile-models.sh tier1
# Completes in ~10 hours
# Covers top 50 high-value models
```

**Week 1: Provider-by-provider**
```bash
# Each day, profile one provider:
./scripts/profile-models.sh provider mistral    # ~15 hours
./scripts/profile-models.sh provider groq       # ~4 hours
./scripts/profile-models.sh provider cerebras   # ~1 hour
```

## Integration with Orchestrator

Once models are profiled, update routing logic:

**In `shared/weighted-voting.cjs` or router:**
```javascript
async function selectBestModelForTask(taskType) {
  // Query profiled capabilities
  const result = await db.query(`
    SELECT model_id, ${taskType} as score, avg_latency_ms
    FROM learning.model_capabilities
    WHERE ${taskType} > 0.6
    ORDER BY ${taskType} DESC
    LIMIT 10
  `);

  // Use Thompson Sampling for exploration
  return thompsonSample(result.rows);
}
```

## Cost Estimate

**Per model profiling:**
- 5 tasks × ~1000 tokens output = ~5K tokens
- Opus evaluation: ~2K tokens per task × 5 = ~10K tokens
- Total: ~15K tokens per model

**For 50 models:**
- 50 × 15K = 750K tokens
- At Opus rates: ~$0.015 per 1K output tokens
- Estimated cost: ~$11

**For all 252 models:**
- 252 × 15K = 3.78M tokens
- Estimated cost: ~$57

**Worth it?** YES - saves much more in wasted API calls from using wrong models.

## Files Created

- `workflows/profile-model-capabilities.mjs` - Main profiling workflow
- `scripts/profile-models.sh` - Helper script
- `learning.model_capabilities` - PostgreSQL table
- `docs/MODEL-CAPABILITIES.md` - Detailed documentation
- `docs/PROFILING-QUICKSTART.md` - This file

## Next Steps

1. ✅ **Test it:** `./scripts/profile-models.sh quick`
2. ⏰ **Schedule overnight:** `./scripts/profile-models.sh tier1`
3. 📊 **Check results:** `./scripts/profile-models.sh top`
4. 🔌 **Wire to router:** Update model selection logic
5. 📈 **Monitor:** Track which models perform best in production

## Troubleshooting

**Workflow fails:**
- Check model API keys are valid
- Some models may be rate-limited (retry later)
- Failed models get score 0.0 (excluded from routing)

**Slow performance:**
- Add `--parallel` flag for parallel execution
- Reduce batch size: `--count=10`
- Profile one provider at a time

**Want to re-test a model:**
```bash
./scripts/profile-models.sh single <model_id>
# Overwrites existing scores
```
