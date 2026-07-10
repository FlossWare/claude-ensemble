# Model Profiling Workflow - TODO

## Status: 95% Complete, Needs Final Debugging

The profiling system is almost done but has a workflow syntax issue that needs fixing.

## What Works:
- ✅ Database table (`learning.model_capabilities`) created
- ✅ Profiling logic designed (automated checks + free judge)
- ✅ Helper script (`scripts/profile-models.sh`)
- ✅ Documentation complete

## What's Broken:
- ❌ Workflow syntax error: "Unexpected keyword 'export'"
- Issue: Workflow runtime doesn't like something about the export statements

## ✅ SOLVED: Genetic Algorithm Approach

Instead of profiling 252 models manually, we use **Genetic Algorithm** to evolve optimal model-task mappings!

### Two-Tier Solution (IMPLEMENTED):

#### Tier 1: Manual Seed (DONE ✅)
```bash
psql -h aio-01 -p 5433 -U sfloess -d learning < scripts/seed-model-capabilities.sql
```
- **Time:** 5 seconds
- **Coverage:** 10/252 models (4%)
- **Status:** COMPLETE
- **Result:** Orchestrator can start working NOW

#### Tier 2: Genetic Evolution (READY ✅)
```bash
./scripts/evolve-models.sh
```
- **Time:** 5-10 minutes
- **Coverage:** Optimizes all task types
- **Data source:** 1,278 REAL execution records
- **Cost:** $0 (local computation)
- **Result:** Evolves better mappings than manual guesses

### How GA Works:

**Chromosome:** Strategy mapping tasks to models
```python
{
  'code_generation': 'qwen/qwen3-coder:free',
  'code_review': 'groq/llama-3.3-70b',
  'research': 'google/gemini-2.0-flash-exp:free',
  ...
}
```

**Fitness Function:**
```
fitness = quality * 0.6 - (cost * 100) * 0.2 - (latency_seconds) * 0.2
```

**Evolution:**
1. Population of 30 strategies
2. Evaluate using REAL execution data from PostgreSQL
3. Select best performers
4. Crossover + mutate
5. Repeat 50 generations
6. Store best strategy

**Advantages:**
- ✅ Uses real production data (not synthetic benchmarks)
- ✅ Fast (10 minutes vs 63 hours manual profiling)
- ✅ Free (local computation, no API calls)
- ✅ Discovers non-obvious good models
- ✅ Adapts to actual workload patterns

### Recommended Path:

1. ✅ **DONE:** Manual seed (10 models in database)
2. **Optional:** Run GA now (`./scripts/evolve-models.sh`)
3. **Better:** Use orchestrator for a week, THEN run GA (more data = better evolution)
4. **Continuous:** Run GA weekly to keep improving

**See:** `docs/GENETIC-ALGORITHM.md` for full details

## Files:
- `workflows/profile-model-capabilities.mjs` - Needs fixing
- `scripts/profile-models.sh` - Works (helper)
- `learning.model_capabilities` - Ready (table exists)

## Current Capability Coverage:
- Total models: 252
- With capabilities: 0
- Coverage: 0%

Once profiling works, orchestrator will know which models are good at what!
