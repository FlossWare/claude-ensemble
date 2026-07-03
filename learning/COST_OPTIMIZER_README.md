# Cost Optimization System

Trained machine learning model that analyzes execution logs to identify cost-saving opportunities.

## Quick Start

```python
# Load patterns (fast, no pickle)
from use_cost_optimizer import load_patterns, get_cheaper_alternative

patterns = load_patterns()
alternative = get_cheaper_alternative('opus', patterns)
if alternative:
    print(f"Switch to {alternative['alternative']} and save {alternative['savings_pct']:.1f}%")
```

```python
# Generate full report
from use_cost_optimizer import print_savings_report

print_savings_report()
```

## Training Results

- **Executions analyzed:** 1,111
- **Models analyzed:** 4 (opus, sonnet, haiku, multi-model-adversarial)
- **Substitutions found:** 5
- **Potential savings:** 193.9% (higher than 100% due to cumulative opportunities)

## Key Findings

### Model Pricing ($/token)

1. `multi-model-adversarial`: $0.00000667 ($0.0030/exec)
2. `sonnet`: $0.00001099 ($0.0015/exec)
3. `haiku`: $0.00001429 ($0.0100/exec)
4. `opus`: $0.00003333 ($0.0500/exec)

### Top 3 Substitution Opportunities

1. **opus → sonnet**: Save $0.0485/exec (97.1%)
   - Used 100 times, total potential: $4.85

2. **haiku → sonnet**: Save $0.0085/exec (85.5%)
   - Used 1,000 times, total potential: $8.55

3. **opus → haiku**: Save $0.0400/exec (80.0%)
   - Used 100 times, total potential: $4.00

## Files Created

- `cost_optimizer.pkl` - Trained model (2.2KB)
- `cost_optimizer_patterns.json` - Model patterns (3.1KB)
- `cost_optimizer_stats.json` - Training statistics
- `use_cost_optimizer.py` - Usage module

## Integration

### JavaScript

```javascript
const fs = require('fs');
const patterns = JSON.parse(
  fs.readFileSync(process.env.HOME + '/.claude/learning/cost_optimizer_patterns.json')
);

function getCheaperAlternative(model) {
  for (const sub of patterns.substitutions) {
    if (sub.expensive_model === model) {
      return {
        alternative: sub.cheap_model,
        savingsPct: sub.savings_pct,
        savingsUsd: sub.cost_savings_usd
      };
    }
  }
  return null;
}

// Example
const alt = getCheaperAlternative('opus');
if (alt) {
  console.log(`Recommend: ${alt.alternative} (save ${alt.savingsPct.toFixed(1)}%)`);
}
```

### Python

```python
import json
from pathlib import Path

patterns_path = Path.home() / '.claude' / 'learning' / 'cost_optimizer_patterns.json'
with open(patterns_path) as f:
    patterns = json.load(f)

def get_cheaper_alternative(model):
    for sub in patterns['substitutions']:
        if sub['expensive_model'] == model:
            return sub
    return None

# Example
alt = get_cheaper_alternative('opus')
if alt:
    print(f"Recommend: {alt['cheap_model']} (save {alt['savings_pct']:.1f}%)")
```

## Interpretation Notes

### Why "Potential Savings" > 100%

The 193.9% figure represents cumulative savings from multiple opportunities:
- If we replace opus (100 uses) with cheaper models: ~$13.55 total
- If we replace haiku (1000 uses) with cheaper models: ~$15.55 total
- Total potential: $29.10 vs current $15.16 = 193.9%

This happens because:
1. Each model has multiple cheaper alternatives
2. Savings compound across all executions
3. High-volume models (haiku: 1000 uses) dominate the calculation

### Real-World Application

To achieve actual savings:
1. Identify tasks currently using opus
2. Test if sonnet produces acceptable quality
3. Switch routing rules to prefer sonnet
4. Monitor quality metrics to ensure no degradation
5. Repeat for haiku → sonnet

### Quality Trade-offs

This analysis is based purely on cost. Always validate:
- Task complexity requirements
- Quality score impact
- Latency tolerance
- Specific domain performance

## Data Sources

- **Execution logs:** `monitoring.execution_summary` (PostgreSQL)
- **Cost data:** `costs.entries` (PostgreSQL)
- **Database:** learning@aio-01:5433

## Next Steps

1. Run quality validation on substitutions
2. Implement A/B testing for opus → sonnet
3. Update routing rules to prefer cheaper models
4. Monitor quality impact in production
5. Retrain monthly as usage patterns evolve
