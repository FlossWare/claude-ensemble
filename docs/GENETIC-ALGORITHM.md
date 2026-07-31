# Genetic Algorithm Model Optimizer

## What It Does

Evolves **optimal model-task mappings** using REAL execution data from your production runs.

Instead of manually profiling 445+ models, the GA:
- Starts with random + seeded strategies
- Evaluates fitness using actual quality/cost/latency from `monitoring.execution_summary`
- Evolves better combinations through selection, crossover, and mutation
- Converges on the best model for each task type

## How It Works

### Chromosome (Strategy)

Each strategy is a mapping:
```python
{
  'code_generation': 'qwen/qwen3-coder:free',
  'code_review': 'groq/llama-3.3-70b',
  'research': 'google/gemini-2.0-flash-exp:free',
  'math_reasoning': 'deepseek/deepseek-chat',
  'general_qa': 'mistral/mistral-large-latest',
  'creative_writing': 'meta-llama/llama-3.3-70b-instruct:free',
  'security_analysis': 'nousresearch/hermes-3-llama-3.1-405b:free'
}
```

### Fitness Function

```
fitness = quality * 0.6 - (cost_usd * 100) * 0.2 - (latency_seconds) * 0.2
```

**Higher fitness = better strategy**

Quality comes from REAL execution results (not synthetic benchmarks).

### Evolution Process

1. **Initialize** 30 strategies:
   - Top performer per task (from history)
   - Hand-crafted seeds (code-focused, reasoning-focused)
   - Random combinations

2. **Evaluate** each strategy:
   - Look up actual execution results from PostgreSQL
   - Calculate fitness from real quality/cost/latency

3. **Select** parents (tournament selection)

4. **Crossover** (mix two strategies)

5. **Mutate** (15% chance to try random model)

6. **Repeat** for 50 generations

7. **Store** best strategy in `learning.model_capabilities`

## Quick Start

### Bootstrap NOW (manual seed)

Get orchestrator working immediately:

```bash
# Seed top 10 models with known capabilities
curl -s http://aio-01:5000/db/execute \
  -H 'Content-Type: application/json' \
  -d '{"file": "scripts/seed-model-capabilities.sql"}'

# Verify
curl -s http://aio-01:5000/db/query \
  -H 'Content-Type: application/json' \
  -d '{"sql": "SELECT model_id, ROUND((code_generation + code_review + research + math_reasoning + general_qa)::numeric / 5, 2) as avg_score FROM learning.model_capabilities ORDER BY avg_score DESC LIMIT 10"}' | python3 -m json.tool
```

**Coverage: 10/445+ models (~2%)**  
**Good enough to start!**

### Evolve Later (genetic algorithm)

Let GA optimize mappings based on actual usage:

```bash
# Run evolution (5-10 minutes)
./scripts/evolve-models.sh

# Or directly:
python3 tools/genetic_model_optimizer.py
```

**This will:**
- Use 1,278 execution records as fitness data
- Evolve for 50 generations
- Find better model combinations than manual guesses
- Update `learning.model_capabilities` with results

## What Gets Optimized

**Task Types:**
- `code_generation` - Writing code
- `code_review` - Analyzing/reviewing code
- `research` - Information gathering
- `math_reasoning` - Math/logic problems
- `general_qa` - General questions
- `creative_writing` - Content generation
- `security_analysis` - Security auditing

**For Each Task:**
- Best model selection (from 445+ free models)
- Quality vs speed vs cost tradeoff
- Based on YOUR actual workload patterns

## Advantages Over Manual Profiling

| Approach | Time | Cost | Accuracy |
|----------|------|------|----------|
| **Manual profiling** | 63 hours | $0 (free judge) | Synthetic benchmarks |
| **GA evolution** | 10 minutes | $0 (local compute) | Real production data |
| **Manual seed** | 5 minutes | $0 | Expert guesses |

**Winner:** Manual seed (5 min) → GA evolution (10 min) = Best of both worlds

## Architecture

```
monitoring.execution_summary (1,278 rows)
         ↓
   [Fitness Function]
         ↓
   Population of 30 strategies
         ↓
   [Selection + Crossover + Mutation]
         ↓
   50 generations
         ↓
   Best strategy → learning.model_capabilities
         ↓
   Orchestrator uses for routing decisions
```

## Parameters

```python
GeneticOptimizer(
  population_size=30,      # Number of strategies per generation
  mutation_rate=0.15,      # 15% chance to mutate
  tournament_size=5        # Select from 5 random candidates
)

optimizer.run(generations=50)
```

**Tuning:**
- More generations = better convergence (but slower)
- Higher mutation = more exploration (but slower convergence)
- Larger population = better diversity (but slower)

**Defaults are good for most cases.**

## Monitoring Progress

The script outputs:
```
Generation 0: Best fitness = 0.523
  Strategy: {'code_generation': 'qwen/qwen3-coder:free', ...}

Generation 15: NEW BEST! Fitness = 0.587 (avg = 0.512)
  Strategy: {'code_generation': 'qwen/qwen3-coder:free', ...}

Generation 50: Best = 0.612, Avg = 0.558
```

**Higher fitness = better strategy**

## Results

After evolution:

```sql
SELECT 
  model_id,
  code_generation,
  code_review,
  research,
  math_reasoning,
  notes
FROM learning.model_capabilities
WHERE notes LIKE '%GA evolved%'
ORDER BY (code_generation + code_review + research + math_reasoning) / 4 DESC;
```

Shows which models the GA chose for each task.

## Integration with Orchestrator

The orchestrator reads `learning.model_capabilities` to decide which model to use:

```python
# Get best model for task
cursor.execute("""
  SELECT model_id
  FROM learning.model_capabilities
  WHERE code_generation = (SELECT MAX(code_generation) FROM learning.model_capabilities)
  LIMIT 1
""")
best_for_code = cursor.fetchone()[0]
```

**After GA runs, orchestrator automatically uses evolved mappings!**

## Continuous Evolution

To keep improving:

1. **Use orchestrator normally** (execution data accumulates)
2. **Run GA weekly** (learns from new data)
3. **Strategies evolve** based on changing workload patterns

```bash
# Add to cron (every Sunday at 2am)
0 2 * * 0 /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/scripts/evolve-models.sh
```

## Files

- `tools/genetic_model_optimizer.py` - GA implementation
- `scripts/evolve-models.sh` - Runner script
- `scripts/seed-model-capabilities.sql` - Manual bootstrap
- `docs/GENETIC-ALGORITHM.md` - This file

## Dependencies

```bash
pip3 install --user numpy requests
```

Auto-installed by `evolve-models.sh` if missing.

## FAQ

**Q: Does this train the models?**  
A: No! This optimizes WHICH model to use for WHICH task. Models themselves are unchanged.

**Q: How is this different from fine-tuning?**  
A: Fine-tuning changes model weights. GA changes routing decisions.

**Q: Can I run this now?**  
A: Yes! Already has 1,278 execution records to learn from.

**Q: Will it overwrite manual seeds?**  
A: Yes, if GA finds better models. But manual seeds help it start.

**Q: How often should I run this?**  
A: Weekly, or when you notice new models performing well.

**Q: What if I don't have execution history?**  
A: Manual seed first (10 models), use orchestrator for a week, then run GA.

## Truth in Labeling

**What GA optimizes:**
- ✅ Model selection per task type
- ✅ Quality vs speed vs cost tradeoffs
- ✅ Learning from real production patterns

**What GA does NOT do:**
- ✗ Improve model intelligence
- ✗ Train or fine-tune models
- ✗ Create new capabilities
- ✗ Emergent reasoning

**GA is routing optimization, not AI improvement.**

## Next Steps

1. ✅ Manual seed done (10 models)
2. Use orchestrator for a few days (collect more data)
3. Run GA evolution (`./scripts/evolve-models.sh`)
4. Check if evolved strategy beats manual seeds
5. Repeat weekly to keep improving
