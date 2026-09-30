# Cost Tracking for Multi-Phase Arbitration

Every multi-phase arbitration review now tracks and reports comprehensive cost information.

## Overview

The arbitration orchestrator automatically tracks:
- Token usage per worker per phase
- Token usage per arbiter per phase
- Cost for each API call based on model pricing
- Aggregated totals by phase, model, and task type

## Model Pricing

Pricing is configured in `arbitration/cost_tracker.py`:

| Model | Input | Output |
|-------|-------|--------|
| claude-haiku-4-5 | $0.80/M | $2.40/M |
| claude-sonnet-5 | $3.00/M | $15.00/M |
| claude-opus-5-5 | $15.00/M | $45.00/M |
| gemini-2.0-flash | $0.075/M | $0.30/M |
| gemini-2.0-pro | $0.30/M | $1.20/M |
| cursor | $3.00/M | $15.00/M |

## Example Output

After running a security audit:

```
================================================================================
ARBITRATION COST REPORT
================================================================================

Task: Security audit of 3 files
Type: security_audit
Started: 2026-09-30T15:16:00.000Z
Completed: 2026-09-30T15:16:45.000Z

--------------------------------------------------------------------------------
COST BREAKDOWN BY PHASE
--------------------------------------------------------------------------------

PHASE 1
  Workers: claude-sonnet-5, gemini-2.0-flash, claude-haiku-4-5-20251001
  Arbiter: claude-sonnet-5

  Worker Usage:
    claude-sonnet-5            15,234 tokens   $0.181243
    gemini-2.0-flash            8,901 tokens   $0.002670
    claude-haiku-4-5-20251001    6,543 tokens   $0.012891
    Worker Subtotal:           30,678 tokens   $0.196804

  Arbiter Usage:
    claude-sonnet-5             5,432 tokens   $0.064890

  Phase 1 Total: 36,110 tokens, $0.261694

PHASE 2
  Workers: claude-opus-5-5, cursor, gemini-2.0-pro
  Arbiter: gemini-2.0-flash

  Worker Usage:
    claude-opus-5-5            12,100 tokens   $0.287250
    cursor                       9,876 tokens   $0.118020
    gemini-2.0-pro              4,321 tokens   $0.002592
    Worker Subtotal:           26,297 tokens   $0.407862

  Arbiter Usage:
    gemini-2.0-flash            7,654 tokens   $0.002296

  Phase 2 Total: 33,951 tokens, $0.410158

--------------------------------------------------------------------------------
SUMMARY
--------------------------------------------------------------------------------

Total Phases:        2
Total Workers:       6
Total Arbiters:      2
Total API Calls:     8

Total Tokens:        70,061
Total Cost:          $0.671852
Cost/Token:          $0.000009586
Cost/Phase:          $0.335926
Cost/Worker:         $0.111976

Cost by Model:
  claude-haiku-4-5-20251001      1 calls     6,543 tokens   $0.012891
  claude-opus-5-5                1 calls    12,100 tokens   $0.287250
  claude-sonnet-5                2 calls    20,666 tokens   $0.246133
  cursor                         1 calls     9,876 tokens   $0.118020
  gemini-2.0-flash               2 calls    16,555 tokens   $0.004966
  gemini-2.0-pro                 1 calls     4,321 tokens   $0.002592

================================================================================
```

## Usage

Cost reports are automatically generated at the end of each arbitration:

```bash
# Run security audit with 3 phases
python3 tools/arbitrate.py security-audit server/ --phases 3

# Output includes full cost breakdown

# Run code review with 2 phases
python3 tools/arbitrate.py code-review . --phases 2

# Cost report shows token usage and pricing
```

## JSON Export

The cost tracker can also export to JSON for dashboard integration:

```python
from arbitration.cost_tracker import CostTracker

tracker = CostTracker('My Task', 'security_audit')
# ... run phases, record tokens ...
json_report = tracker.to_json()
print(json_report)
```

Output:
```json
{
  "task_name": "My Task",
  "task_type": "security_audit",
  "start_time": "2026-09-30T15:16:00.000Z",
  "end_time": "2026-09-30T15:16:45.000Z",
  "total_tokens": 70061,
  "total_cost": 0.671852,
  "phases": [
    {
      "phase": 1,
      "workers": ["claude-sonnet-5", "gemini-2.0-flash", "claude-haiku-4-5-20251001"],
      "arbiter": "claude-sonnet-5",
      "total_workers_used": 3,
      "total_tokens": 36110,
      "total_cost": 0.261694,
      "cost_per_token": 0.000007247
    },
    ...
  ]
}
```

## Cost Optimization Tips

### 1. Use Cheaper Models for Workers

Use `gemini-2.0-flash` for worker phases (input/output is much cheaper):
- $0.075/M input vs $3.00/M for Sonnet
- Still provides quality analysis for phase 1

### 2. Use Expensive Arbiters

Use `opus` or `gemini-2.0-pro` for arbiters (smaller output, synthesis work):
- Better quality synthesis
- Lower token volume (arbiter output is ~5-10K tokens)
- Justifies higher per-token cost

### 3. Reduce Phase Count

3 phases is comprehensive but 2 phases may be sufficient:
- Each phase adds full worker cost
- Diminishing returns after phase 2
- `--phases 2` is faster and cheaper

### 4. Monitor Cost/Token

If `Cost/Token` is high:
- Too many expensive models as workers
- Outputs are unusually verbose
- Consider reducing output verbosity in instructions

## Integration with Dashboards

The `to_json()` method integrates with cost tracking dashboards:

```python
# In your dashboard
import json
from arbitration.cost_tracker import CostTracker

tracker = CostTracker(...)
data = json.loads(tracker.to_json())

# Plot cost by phase
phases = [p['phase'] for p in data['phases']]
costs = [p['total_cost'] for p in data['phases']]
# ... matplotlib/plotly chart ...

# Aggregate by model
model_costs = {}
for phase in data['phases']:
    # ... sum by model ...
```

## Tracking in Production

For production deployments, save cost reports to a log:

```bash
# Redirect to file
python3 tools/arbitrate.py security-audit . --phases 3 > results_$(date +%s).txt

# Parse JSON report for metrics
python3 -c "
import json
from pathlib import Path

# Extract just the cost report section
# Save to costs.jsonl for analysis
" 
```

## See Also

- `arbitration/orchestrator.py` — Main orchestrator (creates cost_tracker)
- `tools/arbitrate.py` — CLI (prints cost report)
- `cost_tracking/` — General toolkit cost tracking (different from arbitration)
