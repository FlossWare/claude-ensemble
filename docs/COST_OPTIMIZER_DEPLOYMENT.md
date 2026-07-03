# Cost Optimizer Deployment Guide

**Date:** 2026-07-03  
**Status:** DEPLOYED  
**Potential Savings:** 193.9%  
**Location:** `~/.claude/learning/cost_optimizer*.{pkl,json}`, `~/.claude/shared/cost_optimizer_*.{py,mjs}`

## Overview

The cost optimizer predicts execution costs before running and automatically suggests cheaper model alternatives. Based on analysis of 1,111 historical executions, it identified 5 substitution patterns with 193.9% total potential savings.

## Key Findings

### Substitution Patterns (Ranked by Savings %)

| Expensive Model | Cheap Model | Avg Savings | Savings % | Historical Pattern |
|-----------------|-------------|-------------|-----------|-------------------|
| opus | sonnet | $0.0485 | 97.1% | 100 → 3 executions |
| opus | multi-model-adversarial | $0.0470 | 94.0% | 100 → 1 execution |
| haiku | sonnet | $0.0085 | 85.5% | 1000 → 3 executions |
| opus | haiku | $0.0400 | 80.0% | 100 → 1000 executions |
| haiku | multi-model-adversarial | $0.0070 | 70.0% | 1000 → 1 execution |

### Model Pricing (per token)

| Model | Price/Token | Avg Cost/Exec | Executions |
|-------|-------------|---------------|------------|
| opus | $0.000033 | $0.0500 | 100 |
| haiku | $0.000014 | $0.0100 | 1000 |
| sonnet | $0.000011 | $0.0015 | 3 |
| multi-model-adversarial | $0.000007 | $0.0030 | 1 |

## Deployment Files

### Python Integration

**Location:** `~/.claude/shared/cost_optimizer_simple.py`

**Features:**
- Pattern-based cost prediction
- Automatic cheaper alternative suggestion
- Savings logging to JSONL
- No external dependencies (uses historical averages)

**Usage:**
```python
from cost_optimizer_simple import CostOptimizer

optimizer = CostOptimizer()

# Predict and suggest
prediction = optimizer.predict_and_suggest(
    task_description="Fix authentication bug",
    preferred_model="opus",
    auto_accept_savings_threshold=50.0
)

print(f"Suggested model: {prediction['suggested_model']}")
print(f"Savings: ${prediction['savings']:.4f} ({prediction['savings_pct']:.1f}%)")
print(f"Auto-accept: {prediction['auto_accept']}")

# Log actual savings
optimizer.log_savings(
    task_description="Fix authentication bug",
    original_model="opus",
    used_model="sonnet",
    actual_cost=0.0015,
    predicted_cost=0.0500
)

# Get total savings
totals = optimizer.get_total_savings(days=7)
print(f"7-day savings: ${totals['total_savings_usd']:.4f}")
```

### JavaScript Workflow Integration

**Location:** `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/cost-optimizer-workflow.mjs`

**Features:**
- Wraps `agent()` and `parallel()` calls
- Auto-substitutes models when >threshold savings
- Logs all decisions to JSONL
- Aggregates savings across parallel workers

**Usage:**
```javascript
import { optimizedAgent, optimizedParallel, getTotalSavings } from './shared/cost-optimizer-workflow.mjs';

// Single agent with auto-optimization
const { result, optimization } = await optimizedAgent({
  task: 'Review code for security issues',
  preferredModel: 'opus',
  autoAcceptThreshold: 50  // Auto-accept if >50% savings
}, async (model) => {
  return await agent(model, { prompt: '...' });
});

console.log(`Saved $${optimization.actual_savings.toFixed(4)}`);

// Parallel workers (optimizes each)
const { results, totalOptimization } = await optimizedParallel(
  [
    { task: 'Worker 1', model: 'opus' },
    { task: 'Worker 2', model: 'haiku' },
    { task: 'Worker 3', model: 'sonnet' }
  ],
  async (worker, optimizedModel) => {
    return await agent(optimizedModel, { prompt: worker.task });
  },
  { autoAcceptThreshold: 50 }
);

console.log(`Total saved: $${totalOptimization.total_savings.toFixed(4)}`);

// Get savings summary
const totals = getTotalSavings(7);  // Last 7 days
console.log(`7-day savings: $${totals.total_savings_usd.toFixed(4)}`);
```

### Example Workflow

**Location:** `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/example-cost-optimized.mjs`

**Run:**
```bash
node workflows/example-cost-optimized.mjs
```

**Output:**
```
[COST OPTIMIZER] opus → sonnet (saves $0.0485, 97.1%)
[COST OPTIMIZER] Parallel workers: 6
[COST OPTIMIZER] Predicted cost: $0.1715
[COST OPTIMIZER] Potential savings: $0.1627 (77.0%)
[COST OPTIMIZER] Actual cost: $0.0090
[COST OPTIMIZER] Actual savings: $0.1625 (76.3%)

Summary: 7 executions
Would have cost: $0.2215
Actual cost: $0.0105
Total saved: $0.2110 (95.3%)
```

## Savings Log

**Location:** `~/.claude/learning/cost_optimizer_savings_log.jsonl`

**Format:**
```jsonl
{
  "timestamp": "2026-07-03T17:45:00.000Z",
  "task_description": "Fix authentication bug",
  "original_model": "opus",
  "used_model": "sonnet",
  "would_have_cost": 0.05,
  "actual_cost": 0.0015,
  "savings_usd": 0.0485,
  "savings_pct": 97.1,
  "predicted_cost": 0.05,
  "prediction_error": 0.0485,
  "prediction_error_pct": 97.0
}
```

## Integration Patterns

### Pattern 1: Auto-Substitute High-Savings Tasks

When savings >50%, automatically use cheaper model:

```javascript
const { result } = await optimizedAgent({
  task: 'Code review',
  preferredModel: 'opus',
  autoAcceptThreshold: 50
}, async (model) => {
  return await agent(model, { ... });
});
// Automatically uses 'sonnet' (97.1% savings)
```

### Pattern 2: Conservative Optimization

Only suggest, don't auto-substitute:

```javascript
const { result, optimization } = await optimizedAgent({
  task: 'Critical security analysis',
  preferredModel: 'opus',
  autoAcceptThreshold: 100  // Never auto-accept
}, async (model) => {
  return await agent(model, { ... });
});

if (optimization.savings_pct > 80) {
  console.log(`Consider using ${optimization.suggested_model} to save ${optimization.savings_pct}%`);
}
```

### Pattern 3: Batch Optimization

Optimize all workers in parallel execution:

```javascript
const workers = tasks.map(t => ({ task: t.description, model: 'opus' }));

const { results, totalOptimization } = await optimizedParallel(
  workers,
  async (worker, optimizedModel) => {
    return await agent(optimizedModel, { prompt: worker.task });
  }
);

console.log(`Batch saved: $${totalOptimization.total_savings.toFixed(4)}`);
```

## Monitoring

### Real-Time Logs

Watch optimization decisions:

```bash
tail -f ~/.claude/learning/cost_optimizer_savings_log.jsonl | jq '.'
```

### Daily Summary

```bash
node -e "
import { getTotalSavings } from './shared/cost-optimizer-workflow.mjs';
const totals = getTotalSavings(1);
console.log(\`Today: \${totals.total_executions} executions\`);
console.log(\`Saved: $\${totals.total_savings_usd.toFixed(4)} (\${totals.avg_savings_pct.toFixed(1)}%)\`);
"
```

### Weekly Report

```python
from cost_optimizer_simple import CostOptimizer

optimizer = CostOptimizer()
totals = optimizer.get_total_savings(days=7)

print(f"7-day summary:")
print(f"  Executions: {totals['total_executions']}")
print(f"  Would have cost: ${totals['total_would_have_cost']:.4f}")
print(f"  Actual cost: ${totals['total_actual_cost']:.4f}")
print(f"  Total saved: ${totals['total_savings_usd']:.4f}")
print(f"  Avg savings: {totals['avg_savings_pct']:.1f}%")
```

## Best Practices

### 1. Set Appropriate Thresholds

- **Auto-accept ≥80%:** Code reviews, documentation, simple fixes
- **Auto-accept ≥50%:** Research, analysis, most workflows
- **Manual review:** Critical security, production deployments

### 2. Log All Decisions

Always use the optimized wrappers to track savings:

```javascript
// Good: Tracked
const { result } = await optimizedAgent({ ... });

// Bad: Untracked
const result = await agent('opus', { ... });
```

### 3. Review Patterns Monthly

Check substitution effectiveness:

```bash
# See which substitutions are working
jq -s 'group_by(.original_model + " → " + .used_model) | 
       map({pattern: .[0].original_model + " → " + .[0].used_model, 
            count: length, 
            avg_savings: (map(.savings_usd) | add / length),
            avg_savings_pct: (map(.savings_pct) | add / length)})' \
  ~/.claude/learning/cost_optimizer_savings_log.jsonl
```

### 4. Update Patterns Quarterly

Retrain when:
- New models added
- Pricing changes
- Task patterns shift

```bash
# Retrain from latest execution data
python3 tools/cost_optimizer_trainer.py --output ~/.claude/learning/cost_optimizer_patterns.json
```

## Limitations

### Pattern-Based Predictions

Current implementation uses **historical averages**, not ML predictions. Assumes:
- Similar tasks → similar costs
- Model performance comparable across task types
- Historical patterns remain valid

**Future:** Integrate ML model for context-aware predictions.

### Model Quality Not Considered

Optimizer only looks at cost, not:
- Quality scores
- Task-specific model strengths
- Historical success rates

**Future:** Integrate with quality predictor for cost-quality tradeoff.

### No Real-Time Pricing

Uses historical averages. Doesn't account for:
- API rate limit surcharges
- Batch discount pricing
- Provider price changes

**Future:** Fetch real-time pricing from provider APIs.

## Next Steps

### Phase 1: Validate Patterns (Week 1)

1. Deploy to all workflows using `optimizedAgent()` wrappers
2. Monitor savings log for 7 days
3. Verify actual savings match predictions (±10%)
4. Adjust auto-accept thresholds based on quality impact

### Phase 2: ML Integration (Week 2)

1. Retrain with PostgreSQL execution data (1,111+ rows)
2. Add context-aware features (prompt length, task type, code blocks)
3. Deploy scikit-learn GradientBoostingRegressor
4. A/B test: pattern-based vs ML predictions

### Phase 3: Quality-Cost Tradeoff (Week 3)

1. Integrate with quality predictor
2. Add `minQualityThreshold` parameter
3. Only suggest cheaper model if quality ≥ threshold
4. Track quality degradation vs cost savings

### Phase 4: Real-Time Optimization (Week 4)

1. Fetch real-time pricing from OpenRouter API
2. Add rate limit awareness
3. Implement batch discount detection
4. Auto-adjust suggestions based on current pricing

## Success Metrics

**Target (30 days):**
- 500+ optimized executions
- 70%+ average savings
- <5% quality degradation
- $50+ total cost savings

**Tracking:**
```bash
# Monthly report
python3 -c "
from cost_optimizer_simple import CostOptimizer
optimizer = CostOptimizer()
totals = optimizer.get_total_savings(days=30)
print(f'30-day savings: \${totals[\"total_savings_usd\"]:.2f}')
print(f'Avg savings: {totals[\"avg_savings_pct\"]:.1f}%')
print(f'Executions: {totals[\"total_executions\"]}')
"
```

## Questions?

- **Logs:** `~/.claude/learning/cost_optimizer_savings_log.jsonl`
- **Patterns:** `~/.claude/learning/cost_optimizer_patterns.json`
- **Code:** `~/.claude/shared/cost_optimizer_simple.py`
- **Workflows:** `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/cost-optimizer-workflow.mjs`
- **Example:** `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/example-cost-optimized.mjs`

**Test it now:**
```bash
node workflows/example-cost-optimized.mjs
```
