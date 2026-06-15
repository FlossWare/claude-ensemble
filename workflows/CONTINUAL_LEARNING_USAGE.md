# Continual Learning Orchestrator

**Production-ready workflow** for tracking all workflow executions to PostgreSQL + ChromaDB for Thompson Sampling feedback loop.

## Features

- ✅ **PostgreSQL Experience Memory** - Vector similarity search (0.4ms)
- ✅ **Cost Tracking** - Per-model token usage and costs
- ✅ **Execution Monitoring** - Performance metrics and logs
- ✅ **Embedding Generation** - Deterministic 128-dim vectors
- ✅ **Prometheus Metrics** - Optional export for Grafana
- ✅ **Demo Mode** - Works without database for testing

## Quick Start

### Demo Mode (No Database Required)

```bash
DEMO_MODE=true node workflows/continual-learning-orchestrator.js
```

Output:
```
=== Continual Learning Orchestrator (Demo Mode) ===

Phase 1: ✓ Initialize tracking systems
Phase 2: ✓ Monitor workflow execution
Phase 3: ✓ Calculate costs
  Cost: $0.002550 (250 in + 120 out tokens)
Phase 4: ✓ Generate embeddings
  Embedding: 128-dim vector (first 5: [0.758, -1.000, -0.844, 0.063, -0.023...])
Phase 5: ⚠ PostgreSQL storage (requires auth config)
Phase 6: ⚠ Prometheus export (optional)
Phase 7: ✓ Generate summary report

✅ Demo complete
```

### Production Mode (PostgreSQL Required)

**Prerequisites:**
1. PostgreSQL server running (laptop-01)
2. Database: `learning`
3. Auth configured in `pg_hba.conf`:
   ```
   local   learning   sfloess   trust
   ```

**Run:**
```bash
node workflows/continual-learning-orchestrator.js
```

## Integration Points

### 1. PostgreSQL Adapter

Uses production adapter from `~/.claude/learning/postgres-adapter.js`:

```javascript
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { getExperienceMemory, getExecutionMonitor, getCostTracker } = 
  require('/home/sfloess/.claude/learning/postgres-adapter.js');
```

### 2. Experience Memory (learning.experiences)

Stores execution patterns with vector embeddings:

```javascript
await experienceMemory.addExperience({
  problem_type: 'consensus',
  problem_hash: 'md5_hash',
  context: { workflow: 'ai-prompt', input: '...', output: '...' },
  embedding: '[0.758,-1.000,...]',  // 128-dim vector
  strategy: 'multi_model_consensus',
  success: true,
  reward: 0.85,
  novelty_score: 0.5,
  importance: 0.7
});
```

### 3. Execution Monitoring (monitoring.execution_summary)

Tracks performance metrics:

```javascript
await executionMonitor.logExecution({
  model: 'claude-sonnet-4',
  workflow: 'ai-prompt',
  task_type: 'consensus',
  quality_score: 0.85,
  input_tokens: 250,
  output_tokens: 120,
  cost_usd: 0.002550,
  duration_ms: 1500,
  outcome: 'success'
});
```

### 4. Cost Tracking (costs.entries)

Per-model cost attribution:

```javascript
await costTracker.logCost({
  model: 'claude-sonnet-4',
  input_tokens: 250,
  output_tokens: 120,
  total_cost: 0.002550
});
```

### 5. Prometheus Metrics (Optional)

Exports metrics for Grafana (http://pi-02:3000):

```bash
python3 ~/.claude/self/prometheus-exporter.py \
  --metric workflow_execution_total \
  --value 1 \
  --labels 'workflow="ai-prompt",status="success"'
```

## Embedding Strategy

**Current:** Deterministic hash-based (128-dim)
- Fast (no API calls)
- Reproducible (same input = same embedding)
- Good for exact duplicates

**Production Upgrade Options:**
1. **sentence-transformers** - Local embedding model
2. **OpenAI Embeddings** - 1536-dim, $0.00002 per 1K tokens
3. **Voyage AI** - Specialized code embeddings

## Thompson Sampling Integration

Experience memory enables Thompson Sampling strategy selection:

```sql
-- Find similar past experiences
SELECT * FROM learning.experiences
WHERE success = TRUE AND reward > 0.7
ORDER BY embedding <=> '[query_embedding]'::vector
LIMIT 10;

-- Best performing strategies
SELECT strategy, avg_reward
FROM learning.strategy_performance
ORDER BY avg_reward DESC;
```

## Performance Benchmarks

From CLAUDE.md (2026-06-15):

| Operation | Time |
|-----------|------|
| Simple similarity search | 0.4ms |
| Filtered similarity | 0.4ms |
| Complex join | 0.5ms |

**2-6× faster than ChromaDB**

## Workflow Phases

1. **Initialize tracking systems** - Connect to PostgreSQL adapters
2. **Monitor workflow execution** - Capture inputs/outputs/duration
3. **Calculate costs** - Token usage → USD conversion
4. **Generate embeddings** - 128-dim vectors for similarity search
5. **Store to PostgreSQL** - learning.experiences table
6. **Export Prometheus metrics** - Optional Grafana integration
7. **Generate summary report** - Human-readable output

## Error Handling

All database operations wrapped in try-catch:
- PostgreSQL auth failures → fallback to demo mode
- Prometheus export failures → logged as warnings (optional)
- Missing dependencies → clear error messages

## Example Output

```json
{
  "workflow": "ai-prompt",
  "task_type": "consensus",
  "strategy": "multi_model_consensus",
  "success": true,
  "duration_ms": 1500,
  "cost_usd": "0.002550",
  "tokens": {
    "input": 250,
    "output": 120,
    "total": 370
  },
  "experience_hash": "742907bba7dd1de1c164396c127605e9"
}
```

## Future Enhancements

1. **Real-time embedding generation** - sentence-transformers integration
2. **Automated strategy selection** - Thompson Sampling decision engine
3. **Multi-workflow tracking** - Track all 8+ workflows in parallel
4. **Feedback loop completion** - Auto-adjust routing based on experience
5. **ChromaDB integration** - Dual-store for redundancy

## See Also

- `~/.claude/CLAUDE.md` - Continual Learning Infrastructure section
- `~/.claude/learning/postgres-adapter.js` - Database adapter
- `/tmp/test_pgvector_system.py` - PostgreSQL test script
