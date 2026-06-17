# Active Learning Implementation

## Overview

This system identifies and prioritizes the most valuable learning opportunities for the AI orchestration platform. It implements a data-driven approach to research prioritization:

1. **Identify Opportunities** - Detect knowledge gaps with high impact and low cost
2. **Create Strategy** - Build learning campaigns and experimental plans
3. **Execute Experiments** - Run targeted tests and collect metrics
4. **Measure Impact** - Validate outcomes and update system knowledge
5. **Close Loop** - Refine next experiments based on learnings

## Architecture

```
execution_log (SQLite)
      ↓
active-learning-engine.js (Identify opportunities)
      ↓
strategic-learning-planner.js (Plan experiments)
      ↓
experiment-executor.js (Run experiments)
      ↓
quality_ratings + model_performance (Learning feedback)
      ↓
[Next cycle: refined priorities based on learnings]
```

## Components

### 1. Active Learning Engine (`active-learning-engine.js`)

**Purpose**: Analyze execution history and identify valuable research gaps.

**Input**: SQLite database with execution_log, model_performance, parameter_tuning tables

**Output**: Prioritized list of learning opportunities with impact/cost scores

**Opportunity Types**:
- `knowledge_gap` - Decisions made with high uncertainty
- `high_variance` - Outcomes unstable across similar executions
- `underexplored_space` - Parameter combinations with few samples
- `untested_combination` - Promising model pairs never tested together
- `divergent_performance` - Models disagree on task quality
- `low_confidence` - Areas where arbiter confidence is low
- `cost_anomaly` - Unexpectedly expensive model/task combinations

**Scoring Formula**:
```
Efficiency = Impact / Cost

Impact (0-100):
  - How frequently this decision affects the system (sample count)
  - How much variance exists (quality range)
  - How much value fixing it would provide

Cost (0-100):
  - Token cost to run experiment
  - Time required
  - Compute resources needed
```

**Usage**:
```bash
node active-learning-engine.js \
  --db ~/.claude/learning/db/orchestration.db \
  --limit 20 \
  --output opportunities.json
```

**Output Example**:
```json
{
  "id": "knowledge-gap-model-selection-code-review",
  "name": "Which model selection strategy optimizes code-review quality?",
  "type": "knowledge_gap",
  "domain": "model_selection",
  "impact": 72.5,
  "cost": 8,
  "efficiency": 9.06,
  "context": {
    "task_type": "code-review",
    "model_count": 3,
    "quality_variance": 0.18
  },
  "recommendation": {
    "experiment": "Run 5 code-review tasks with different model sets...",
    "metrics": ["quality_score", "consensus_score", "selected_model"],
    "expectedOutcome": "Learn optimal model count and combination for code-review"
  }
}
```

### 2. Strategic Learning Planner (`strategic-learning-planner.js`)

**Purpose**: Convert opportunities into executable experiments with budgets and dependencies.

**Input**: Opportunities from active-learning-engine.js

**Output**: 
- Learning campaigns (grouped by domain)
- Experiment queue (prioritized by ROI)
- Token budget allocation
- Executable experiment prompts
- Success criteria and validation rules

**Campaign Organization**:
Opportunities are grouped by domain (model_selection, cost_optimization, etc.) and sorted by impact. This creates focused learning initiatives that provide complementary insights.

**Experiment Prioritization**:
1. Zero dependencies first (can execute immediately)
2. Then by efficiency (impact / cost)
3. Respects token budget constraints

**Success Criteria**:
Each experiment defines minimum thresholds:
- Minimum samples (≥ 3)
- Quality improvement required (≥ 5%)
- Confidence threshold (≥ 80%)
- Data completeness (≥ 95%)

**Validation Rules**:
- Reject if > 5% of metrics missing
- Reject if confidence < 0.6
- Only 1 sample (minimum 3 required)
- Contradicts high-confidence findings

**Usage**:
```bash
node strategic-learning-planner.js \
  --opportunities opportunities.json \
  --budget 1000000 \
  --output ./learning-plan
```

**Output Files**:
- `learning-plan.json` - Complete plan with experiments
- `experiment-prompts.md` - Readable experiment descriptions

### 3. Experiment Executor (`experiment-executor.js`)

**Purpose**: Execute learning experiments and collect outcomes.

**Workflow**:
1. Load experiment queue from strategic plan
2. For each experiment:
   - Get next executable experiment (dependencies met)
   - Generate experiment prompt
   - Execute with target models/task types
   - Collect all specified metrics
   - Validate against success criteria
   - Record in execution_log database
3. Generate learning feedback summarizing findings

**Integration Points**:
- Calls multi-ai-consensus system (or similar) to execute
- Stores results in SQLite execution_log table
- Updates quality_ratings with outcomes
- Records in model_performance for trending

**Validation**:
Each experiment outcome is validated against success criteria:
- Check sample count meets minimum
- Verify all metrics collected
- Validate statistical significance (p < 0.05 if possible)
- Cross-check against previous findings

**Usage**:
```bash
node experiment-executor.js \
  --plan learning-plan/learning-plan.json \
  --db ~/.claude/learning/db/orchestration.db \
  --limit 5
```

**Output**:
```json
{
  "result": {
    "executed": 3,
    "failed": 0,
    "tokensUsed": 28000,
    "experiments": [...]
  },
  "feedback": {
    "total_experiments": 3,
    "successful": 3,
    "findings": [
      "Average quality score: 0.85",
      "Average confidence: 0.88",
      "3 experiments provided statistically significant results"
    ],
    "recommendations": [
      "High quality outcomes suggest model selection strategy is sound"
    ],
    "next_experiments": [...]
  }
}
```

## Workflow: End-to-End

### Phase 1: Discovery (Analyze execution history)
```bash
# Identify opportunities from past executions
node active-learning-engine.js \
  --db ~/.claude/learning/db/orchestration.db \
  --limit 20
```

Output: Top 20 opportunities by efficiency (impact/cost)

### Phase 2: Planning (Build experimental strategy)
```bash
# Convert opportunities to executable experiments
node strategic-learning-planner.js \
  --opportunities opportunities.json \
  --budget 1000000 \
  --output ./learning-plan
```

Output: Prioritized queue of 15-20 experiments, token budget allocated

### Phase 3: Execution (Run experiments)
```bash
# Execute up to 5 experiments
node experiment-executor.js \
  --plan learning-plan/learning-plan.json \
  --db ~/.claude/learning/db/orchestration.db \
  --limit 5
```

Output: Experiment outcomes and learning feedback

### Phase 4: Feedback Loop (Iterate)
```bash
# Next iteration: run discovery again with new execution data
# This refines priorities based on learnings
```

## Example Use Cases

### Use Case 1: Model Selection Uncertainty
**Scenario**: We have 3-4 candidate models (opus, sonnet, haiku) but unclear which performs best for code reviews.

**Discovery Phase**:
```
Opportunity: knowledge-gap-model-selection-code-review
Impact: 72.5 (frequent decision, high variance)
Cost: 8 (3-4 runs with 2 models each)
Efficiency: 9.06 (best ROI)
```

**Experiment**:
```
Run 5 code-review tasks with:
  - [opus] alone
  - [sonnet] alone
  - [opus, sonnet] consensus
  - [opus, sonnet, haiku] consensus

Collect: quality_score, consensus_score, selected_model, total_cost_usd

Expected outcome: Clear winner or best combination for code-review
```

**Success**: Reduce future quality variance by 30%+ by using optimal model

### Use Case 2: Untested Model Combination
**Scenario**: Never tested [gpt-4o, opus] together despite both being high-quality.

**Discovery Phase**:
```
Opportunity: untested-combo-["gpt-4o","opus"]
Impact: 60 (potentially high-quality)
Cost: 5 (one experiment)
Efficiency: 12 (excellent ROI)
```

**Experiment**:
```
Run 3 representative tasks with:
  - worker_models: ["gpt-4o", "opus"]
  - arbiter_model: "fable"

Collect: quality_score, consensus_score, selected_model, cost

Expected outcome: Validate if [gpt-4o, opus] is viable high-quality combo
```

**Success**: If quality > 0.85, add to standard model combinations

### Use Case 3: Cost Optimization
**Scenario**: Haiku is expensive relative to quality it produces on test generation.

**Discovery Phase**:
```
Opportunity: cost-anomaly-haiku-test_plan
Impact: 48 (happens frequently)
Cost: 2 (analysis only)
Efficiency: 24 (exceptional ROI)
```

**Experiment**:
```
Compare haiku vs sonnet on 5 test generation tasks:
  - Same prompt, both models
  - Collect: quality_score, total_cost_usd

Expected outcome: Determine if sonnet produces same quality at lower cost
```

**Success**: If sonnet >= haiku quality, replace haiku with sonnet, save ~30% on test_plan costs

## Database Schema Integration

The system uses these tables in orchestration.db:

**execution_log**: Records of every workflow execution
- execution_id, timestamp
- workflow, task_type, task_description
- worker_models, arbiter_model, model_count
- quality_score, consensus_score, confidence
- total_cost_usd, duration_ms
- outcome, selected_model

**model_performance**: Aggregated metrics per model/task/time_window
- model, task_type, role (worker/arbiter)
- avg_quality, median_quality, stddev_quality
- selection_rate, win_rate
- avg_cost_usd, cost_per_quality
- quality_rank, efficiency_rank

**parameter_tuning**: Optimal parameters discovered
- model, task_type
- optimal_params (JSON)
- avg_quality, avg_cost_usd, success_rate
- quality_vs_baseline, cost_vs_baseline
- confidence in tuning

**quality_ratings**: User feedback and automated scores
- execution_id, workflow, task_type
- overall_score, accuracy_score, completeness_score
- thumbs_up, user_comment
- tests_passed, lint_errors, build_success

## Configuration

Create `~/.claude/learning/config.json`:

```json
{
  "active_learning": {
    "enabled": true,
    "update_interval_hours": 6,
    "opportunities_limit": 20,
    "min_samples_for_ranking": 3
  },
  "experiment_execution": {
    "batch_size": 5,
    "token_budget_per_cycle": 1000000,
    "validation_strict": true,
    "save_artifacts": true
  },
  "discovery_strategies": {
    "knowledge_gaps": true,
    "high_variance": true,
    "underexplored_space": true,
    "untested_combinations": true,
    "divergent_performance": true,
    "low_confidence": true,
    "cost_anomalies": true
  }
}
```

## Monitoring and Metrics

Track these metrics to assess active learning effectiveness:

1. **Opportunity Quality**: Are opportunities we identify actually valuable?
   - Metric: Post-experiment quality_score vs pre-experiment baseline
   - Target: ≥ 5% improvement

2. **Prediction Accuracy**: Do predictions about experiment outcomes match reality?
   - Metric: Estimated vs actual tokens used, time taken
   - Target: < 20% estimation error

3. **ROI**: Is efficiency (impact/cost) calculation accurate?
   - Metric: Actual learning value / predicted learning value
   - Target: > 0.8 (conservative predictions)

4. **Convergence**: Are we reducing variance and uncertainty over time?
   - Metric: Model consensus_score trend over 50 recent executions
   - Target: ≥ 0.8 average

5. **Coverage**: Are we exploring all important decision points?
   - Metric: Number of task_type × model combinations tested
   - Target: ≥ 80% of possible combinations

## Troubleshooting

**Problem**: "No execution history found"
**Solution**: Run some workflows first. System needs at least 10 executions to identify patterns.

**Problem**: "All experiments have unmet dependencies"
**Solution**: Start with cost_anomaly or low_confidence experiments (no dependencies). Execute those first.

**Problem**: "Token budget exhausted before completing queue"
**Solution**: Reduce experiment batch size (--limit flag) or increase budget (--budget flag).

**Problem**: "Quality scores below success threshold"
**Solution**: Review success criteria. May be too strict. Check if experiments were run with correct models/parameters.

## Future Enhancements

1. **Bayesian Optimization**: Use Gaussian Process to model parameter space and suggest optimal settings
2. **Multi-Armed Bandit**: Epsilon-greedy exploration/exploitation for model selection
3. **Transfer Learning**: Leverage findings from one task type to predict quality on similar tasks
4. **Causal Analysis**: Determine not just correlation but causation in model performance differences
5. **Cost-Benefit Analysis**: Dynamically adjust when to stop exploring vs exploit current best knowledge
6. **Curriculum Learning**: Order experiments by difficulty (easy validations before complex ones)

## References

- SQLite schema: `orchestration-schema.sql`
- Learning database: `~/.claude/learning/db/orchestration.db`
- Grafana dashboards: See `GRAFANA_DEPLOYMENT.md`
- Learning curves and trends: View in Grafana "Model Performance" and "Decision Distribution" dashboards
