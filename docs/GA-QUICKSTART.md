# Genetic Algorithm - Quick Start

## TL;DR

**Problem:** 445+ free models, don't know which to use for what  
**Solution:** Genetic algorithm evolves optimal model-task mappings using REAL execution data  
**Status:** ✅ Ready to run (10 models already seeded, 1,274 execution records available)

## Two Commands

### 1. Bootstrap (DONE ✅)
```bash
curl -s http://aio-01:5000/db/execute \
  -H 'Content-Type: application/json' \
  -d '{"file": "scripts/seed-model-capabilities.sql"}'
```
**Result:** 10 models with known capabilities (orchestrator works NOW)

### 2. Evolve (Optional)
```bash
./scripts/evolve-models.sh
```
**Result:** GA finds better model combinations from 1,274 real executions (5-10 min)

## Current Status

```
Total Free Models:    445+
With Capabilities:    10  (4% coverage)
Execution Records:    1,274
GA Status:            Ready to run
```

## What GA Does

1. **Loads** 1,274 execution records from PostgreSQL
2. **Creates** 30 random strategies (model-task mappings)
3. **Evaluates** fitness using real quality/cost/latency data
4. **Evolves** for 50 generations (selection + crossover + mutation)
5. **Stores** best strategy in `learning.model_capabilities`

## Fitness Function

```
fitness = quality * 0.6 - (cost * 100) * 0.2 - (latency_seconds) * 0.2
```

Higher fitness = better strategy

## When to Run

| Scenario | Recommendation |
|----------|----------------|
| **Right now** | Optional - already have 10 seeds |
| **After 1 week of usage** | YES - more execution data = better evolution |
| **After adding new models** | YES - GA will discover their strengths |
| **Monthly** | YES - keeps mappings optimized |

## Expected Results

**Before GA (manual seeds):**
```
code_generation  → qwen/qwen3-coder:free         (0.85 quality)
code_review      → groq/llama-3.3-70b            (0.70 quality)
research         → google/gemini-2.0-flash-exp   (0.85 quality)
```

**After GA (evolved):**
```
code_generation  → ??? (GA might find better)
code_review      → ??? (learns from actual reviews)
research         → ??? (optimizes for YOUR workload)
```

GA learns what works for YOUR specific tasks, not generic benchmarks.

## Files

- `tools/genetic_model_optimizer.py` - GA implementation
- `scripts/evolve-models.sh` - Runner script
- `scripts/seed-model-capabilities.sql` - Bootstrap data
- `docs/GENETIC-ALGORITHM.md` - Full documentation

## Run Now?

**YES if:**
- Want to see GA in action
- Have 10+ minutes
- Curious what it finds

**WAIT if:**
- Want more execution data first (better evolution)
- Busy right now (orchestrator works with current seeds)

**Command:**
```bash
./scripts/evolve-models.sh
```

**Output:**
```
Generation 0: Best fitness = 0.523
Generation 15: NEW BEST! Fitness = 0.587
Generation 50: Best = 0.612
✅ Evolution complete!
```

Then check results:
```bash
curl -s http://aio-01:5000/db/query \
  -H 'Content-Type: application/json' \
  -d '{"sql": "SELECT model_id, ROUND((code_generation + code_review + research)::numeric / 3, 2) as avg_score, notes FROM learning.model_capabilities WHERE notes LIKE '\''%GA evolved%'\'' ORDER BY avg_score DESC LIMIT 10"}' | python3 -m json.tool
```

## Truth in Labeling

**GA optimizes:** Model selection for tasks (routing decisions)  
**GA does NOT:** Train models, create new capabilities, improve intelligence

This is **orchestration optimization**, not **AI improvement**.
