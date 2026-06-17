# Active Learning System - Quick Start Guide

## What is Active Learning?

Automatically identifies the most valuable research opportunities and prioritizes them by **ROI (return on investment)** = impact/cost.

- **Impact**: How important is this decision? (0-100)
- **Cost**: How expensive to validate? (0-100)
- **Efficiency**: Impact/Cost (higher = better ROI)

## Installation

Already installed! Files are at: `/home/sfloess/.claude/learning/`

## Quick Start (5 minutes)

### Step 1: Run the pipeline
```bash
cd ~/.claude/learning
./run-active-learning.sh --all
```

**What happens**:
1. Analyzes execution history
2. Identifies opportunities (knowledge gaps, untested combos, cost anomalies, etc.)
3. Creates experiment plan
4. (Optional) Runs experiments
5. Generates report

### Step 2: Review results
```bash
# View opportunities (sorted by ROI)
cat active-learning-results/[timestamp]/opportunities.json | jq '.[0:5]'

# View experiment plan
cat active-learning-results/[timestamp]/plan/learning-plan.json | jq '.summary'

# Read markdown report
cat active-learning-results/[timestamp]/REPORT.md
```

## Common Commands

### Discover opportunities only
```bash
./run-active-learning.sh --discover
```
Output: `opportunities.json` with top 20 by efficiency

### Create experiment plan
```bash
./run-active-learning.sh --plan
```
Output: `plan/learning-plan.json` + `plan/experiment-prompts.md`

### Execute experiments
```bash
./run-active-learning.sh --execute 10
```
Runs up to 10 experiments from the plan

### Run full pipeline
```bash
./run-active-learning.sh --all
```
All phases: discover → plan → execute → feedback

## Understanding Opportunities

### Example: Knowledge Gap
```json
{
  "id": "knowledge-gap-model-selection-code-review",
  "name": "Which model selection strategy optimizes code-review quality?",
  "type": "knowledge_gap",
  "impact": 72.5,        ← How important (0-100)
  "cost": 8,             ← Expense to validate (0-100)
  "efficiency": 9.06,    ← Impact/Cost (ROI)
  "context": {
    "task_type": "code-review",
    "model_count": 3,
    "quality_variance": 0.18
  },
  "recommendation": {
    "experiment": "Run 5 code-review tasks with different model sets...",
    "metrics": ["quality_score", "consensus_score", "selected_model"],
    "expectedOutcome": "Learn optimal model combination for code-review"
  }
}
```

**How to interpret**:
- `efficiency: 9.06` = Great ROI! Fixing this saves effort and improves quality
- `impact: 72.5` = Important decision (affects many executions)
- `cost: 8` = Reasonable expense (8 tokens to run)

## Opportunity Types

| Type | What It Means | Example |
|------|---------------|---------|
| `knowledge_gap` | Decision with uncertainty | Which model for X task? |
| `high_variance` | Unstable outcomes | Model Y produces wildly different results |
| `underexplored_space` | Few samples | Only tried [opus] once |
| `untested_combination` | Never tested together | Never tried [gpt-4o, opus] combo |
| `divergent_performance` | Models disagree | Opus 85%, Sonnet 65% on same task |
| `low_confidence` | Uncertain decisions | Arbiter confidence < 70% |
| `cost_anomaly` | Too expensive | Haiku costs 10x more than Sonnet for same quality |

## Real-World Examples

### Example 1: Save 30% on Costs
```
Opportunity: cost_anomaly-haiku-test_plan
Impact: 48 | Cost: 2 | Efficiency: 24 ⭐⭐⭐ (best ROI)

Experiment: Compare haiku vs sonnet on test generation
Expected: Sonnet same quality, 30% cheaper

Result: CONFIRMED
- Haiku: quality 0.78, cost $0.25
- Sonnet: quality 0.82, cost $0.30
Decision: Use Sonnet, save 20% while improving quality
```

### Example 2: Improve Quality by 15%
```
Opportunity: knowledge_gap-model_selection-code_review
Impact: 72.5 | Cost: 8 | Efficiency: 9.06

Experiment: Test [opus], [sonnet], [opus+sonnet] on code reviews
Expected: Find best combination

Result: [opus+sonnet] > individual models
- Opus: 82%
- Sonnet: 78%
- Opus+Sonnet: 89% ⬆️ 7 points better!
Decision: Use consensus model for code-review
```

### Example 3: Discover New Capability
```
Opportunity: untested_combination-['gpt-4o','opus']
Impact: 60 | Cost: 5 | Efficiency: 12

Experiment: Run 3 diverse tasks with [gpt-4o, opus]

Result: VIABLE
- Quality: 0.87 (excellent)
- Cost: $0.15
Decision: Add to standard high-quality combos
```

## Output Structure

```
~/.claude/learning/active-learning-results/20240613-113245/
├── opportunities.json                 # Top 20 opportunities
├── plan/
│   ├── learning-plan.json             # Experiment queue
│   └── experiment-prompts.md          # Readable experiments
├── discovery.log                      # Phase 1 logs
├── planning.log                       # Phase 2 logs
├── execution.log                      # Phase 3 logs
└── REPORT.md                          # Summary report
```

## Key Metrics

After running experiments, check:

1. **Quality Improvement**: Did we improve on the metric we targeted?
   - Goal: ≥ 5% improvement

2. **Confidence**: How confident are we in the result?
   - Goal: ≥ 80% confidence

3. **Sample Size**: Enough data to be statistically significant?
   - Goal: ≥ 3 samples minimum

4. **Cost Accuracy**: Did the experiment cost what we predicted?
   - Goal: < 20% error

## Configuration

Create `~/.claude/learning/config.json` (optional):

```json
{
  "active_learning": {
    "enabled": true,
    "opportunities_limit": 20
  },
  "strategic_planning": {
    "token_budget": 1000000,
    "confidence_threshold": 0.8
  },
  "experiment_execution": {
    "batch_size": 5,
    "validation_strict": true
  }
}
```

See `config-template.json` for all options.

## Continuous Improvement Loop

```
1. Run discovery     → Find top 20 opportunities
   ↓
2. Review            → Check if they make sense
   ↓
3. Plan              → Create experiment queue
   ↓
4. Execute           → Run experiments (5 at a time)
   ↓
5. Analyze           → Review results
   ↓
6. Implement         → Apply learnings (e.g., change model selection)
   ↓
7. Repeat (go back to step 1 with new execution data)
```

## Troubleshooting

### "No execution history found"
**Cause**: Database is empty or doesn't exist
**Fix**: Run some workflows first. System needs data to find patterns.

### "Failed to identify opportunities"
**Cause**: Database might be corrupted or inaccessible
**Fix**: Check database path: `~/.claude/learning/db/orchestration.db`

### "Token budget exhausted"
**Cause**: Plan requires more tokens than available
**Fix**: Increase budget with `--budget 2000000` or reduce experiment batch size

### "Quality below success threshold"
**Cause**: Experiment didn't improve as expected
**Fix**: Review success criteria in plan; may be too strict; try alternative model combo

## Next Steps

1. **Run discovery**: Find what to learn
   ```bash
   ./run-active-learning.sh --discover
   ```

2. **Review opportunities**: Check top 5 by efficiency
   ```bash
   jq '.[0:5]' active-learning-results/[timestamp]/opportunities.json
   ```

3. **Create plan**: Convert to experiments
   ```bash
   ./run-active-learning.sh --plan
   ```

4. **Run experiments**: Execute high-ROI opportunities
   ```bash
   ./run-active-learning.sh --execute 5
   ```

5. **Analyze results**: Review what you learned
   ```bash
   cat active-learning-results/[timestamp]/REPORT.md
   ```

## Files Reference

| File | Purpose |
|------|---------|
| `active-learning-engine.js` | Identify opportunities (Discovery phase) |
| `strategic-learning-planner.js` | Plan experiments (Planning phase) |
| `experiment-executor.js` | Run experiments (Execution phase) |
| `run-active-learning.sh` | Orchestrate workflow |
| `ACTIVE_LEARNING_README.md` | Full documentation |
| `IMPLEMENTATION_SUMMARY.md` | Technical overview |
| `config-template.json` | Configuration template |

## Get Help

```bash
# Show help
./run-active-learning.sh --help

# View logs
tail -f active-learning-results/[timestamp]/*.log

# Check database
sqlite3 ~/.claude/learning/db/orchestration.db "SELECT COUNT(*) FROM execution_log;"

# View current opportunities
./run-active-learning.sh --discover
cat active-learning-results/[timestamp]/opportunities.json | jq
```

---

**That's it!** You now have an automated system that identifies and prioritizes the most valuable research opportunities for your AI orchestration platform.
