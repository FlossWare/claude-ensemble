# Active Learning Implementation - Complete System

## Executive Summary

A complete **Active Learning System** has been implemented that automatically identifies the most valuable research opportunities for the AI orchestration platform. The system prioritizes learning by computing an **efficiency score** (impact/cost) for each opportunity, ensuring that experimentation focuses on high-impact, low-cost research areas.

**Key Achievement**: The system shifts from reactive testing (run whatever experiments seem interesting) to **proactive discovery** (systematically identify and rank the most valuable research questions).

## What Was Implemented

### 1. **Active Learning Engine** (`active-learning-engine.js`)
   - **Purpose**: Analyze execution history and identify learning gaps
   - **Identifies**: 7 types of opportunities (knowledge gaps, high variance, untested combinations, etc.)
   - **Scoring**: Impact (0-100) based on frequency/variance, Cost (0-100) based on tokens/time
   - **Output**: Prioritized opportunity list with efficiency scores

   **Key Features**:
   - Detects high-variance outcomes (unstable results across runs)
   - Finds underexplored parameter spaces (few executions, high potential)
   - Discovers untested model combinations (promising pairs never run)
   - Identifies divergent performance (models disagree on quality)
   - Flags low-confidence decisions (arbiter uncertain on outcomes)
   - Detects cost anomalies (unexpectedly expensive operations)

### 2. **Strategic Learning Planner** (`strategic-learning-planner.js`)
   - **Purpose**: Convert opportunities into executable experiment plan
   - **Organizes**: Opportunities into learning campaigns by domain
   - **Prioritizes**: Experiments by efficiency (impact/cost), respecting dependencies
   - **Budgets**: Token allocation across all experiments
   - **Generates**: 
     - Learning campaign structure (grouped initiatives)
     - Experiment queue (ordered by ROI)
     - Executable prompts (ready to run)
     - Success criteria (minimum thresholds)
     - Validation rules (quality gates)

   **Key Features**:
   - Dependency tracking (some experiments enable others)
   - Token budget allocation per experiment
   - Success metrics per opportunity type
   - Comprehensive experiment prompts
   - Validation rules to ensure rigor

### 3. **Experiment Executor** (`experiment-executor.js`)
   - **Purpose**: Execute learning experiments and collect outcomes
   - **Executes**: Experiments in priority order
   - **Collects**: Full metrics (quality, cost, tokens, confidence)
   - **Validates**: Outcomes against success criteria
   - **Stores**: Results in SQLite execution_log database
   - **Reports**: Learning feedback and recommendations

   **Key Features**:
   - Automatic validation of experiment outcomes
   - Database integration (records in execution_log)
   - Learning feedback generation
   - Progress tracking and status reporting

### 4. **Quick-Start Pipeline** (`run-active-learning.sh`)
   - **Purpose**: Orchestrate the entire workflow
   - **Phases**:
     1. Discovery - Identify opportunities
     2. Planning - Create experiment queue
     3. Execution - Run experiments (interactive)
     4. Feedback - Generate learning report
   
   **Usage**:
   ```bash
   ./run-active-learning.sh --all        # Full pipeline
   ./run-active-learning.sh --discover   # Discovery only
   ./run-active-learning.sh --execute 10 # Run 10 experiments
   ```

### 5. **Comprehensive Documentation** (`ACTIVE_LEARNING_README.md`)
   - Architecture overview
   - Component descriptions
   - End-to-end workflow examples
   - Configuration guide
   - Troubleshooting tips
   - Future enhancements

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXECUTION HISTORY                            │
│              (SQLite: execution_log, model_performance)             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 PHASE 1: DISCOVERY                                  │
│         active-learning-engine.js                                   │
│  • Analyzes execution patterns                                      │
│  • Identifies 7 types of learning opportunities                     │
│  • Scores by impact (how important) and cost (expense)              │
│  • Output: opportunities.json (top 20 by efficiency)               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 PHASE 2: PLANNING                                   │
│         strategic-learning-planner.js                               │
│  • Groups opportunities into learning campaigns                     │
│  • Builds experiment queue (prioritized by ROI)                     │
│  • Allocates token budget                                           │
│  • Generates executable experiment prompts                          │
│  • Output: learning-plan.json + experiment-prompts.md               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 PHASE 3: EXECUTION                                  │
│          experiment-executor.js                                     │
│  • Runs experiments in priority order                               │
│  • Collects metrics (quality, cost, tokens, etc.)                   │
│  • Validates against success criteria                               │
│  • Stores in execution_log database                                 │
│  • Output: execution outcomes + feedback                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 PHASE 4: FEEDBACK LOOP                              │
│  • Learning feedback report                                         │
│  • Recommendations for future iterations                            │
│  • Next experiment queue                                            │
│  • Back to Phase 1 with new data...                                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
           ┌───────────────────────────────────┐
           │  CONTINUOUS IMPROVEMENT CYCLE     │
           │  (Repeat with refined priorities) │
           └───────────────────────────────────┘
```

## Core Algorithms

### Opportunity Identification (Phase 1)

**Impact Score** (0-100):
```
Impact = Frequency * Variance + Sample_Count

Examples:
- High-variance outcome: Impact = 18% variance * 100 + 45 samples = 63
- Rare model combo: Impact = 25 (few samples, untested)
- Divergent models: Impact = Quality_Gap * 150
```

**Cost Score** (0-100):
```
Cost = Base_Type_Cost * (Cost_Factor / 10)

Base costs by type:
- cost_anomaly: 3
- low_confidence: 4
- underexplored_space: 5
- untested_combination: 7
- knowledge_gap: 8
- high_variance: 6
- divergent_performance: 10
```

**Efficiency** (primary ranking):
```
Efficiency = Impact / Cost

Examples:
- cost_anomaly (I=48, C=2): E=24 ⭐⭐⭐ (exceptional)
- untested_combo (I=60, C=5): E=12 ⭐⭐ (excellent)
- divergent_perf (I=72.5, C=8): E=9.06 ⭐⭐ (good)
```

### Experiment Planning (Phase 2)

**Priority Queue**:
1. First: Experiments with zero dependencies (can execute immediately)
2. Then: Sorted by efficiency (impact/cost)
3. Respect: Token budget constraints

**Success Criteria** (per experiment):
- Minimum samples: ≥ 3
- Quality improvement: ≥ 5%
- Confidence threshold: ≥ 80%
- Data completeness: ≥ 95%

### Experiment Execution (Phase 3)

**Validation Rules**:
- Reject if > 5% of metrics missing
- Reject if confidence < 0.6
- Reject if only 1 sample (minimum 3)
- Flag if contradicts high-confidence findings

## Opportunity Types

### 1. Knowledge Gaps
**What**: Decisions made with high uncertainty
**Impact**: Frequent decisions with high variance
**Cost**: Medium (3-4 runs with multiple models)
**Example**: "Which model selection strategy optimizes code-review quality?"

### 2. High Variance
**What**: Task/model combinations with unstable results
**Impact**: High (fixing reduces variance by 30%+)
**Cost**: Medium (need stratified analysis)
**Example**: "Model X produces wildly different results on code-review depending on input"

### 3. Underexplored Space
**What**: Parameter combinations with few samples
**Impact**: Medium (promising but uncertain)
**Cost**: Low (one experiment)
**Example**: "Only tried [opus] once; need more data"

### 4. Untested Combinations
**What**: High-potential model pairs never tested
**Impact**: High (may discover better combo)
**Cost**: Medium (requires experiment)
**Example**: "Never tried [gpt-4o, opus] together despite both being strong"

### 5. Divergent Performance
**What**: Models disagree on task quality (high diversity)
**Impact**: High (unclear which model is right)
**Cost**: Medium (need direct comparison + ratings)
**Example**: "Opus scores 85% on code-review, Sonnet scores 65% on same task"

### 6. Low Confidence
**What**: Arbiter uncertain about decisions
**Impact**: Medium (low confidence = risky)
**Cost**: Low (just need user feedback)
**Example**: "Arbiter confidence < 70% on test generation"

### 7. Cost Anomalies
**What**: Unexpectedly expensive models/task combinations
**Impact**: Medium-High (cost directly affects budget)
**Cost**: Low (analysis only)
**Example**: "Haiku costs $2 per quality point; Sonnet costs $0.50"

## Example Workflows

### Scenario 1: Optimize Model Selection for Code Review

**Discovery**:
```json
{
  "id": "knowledge-gap-model-selection-code-review",
  "name": "Which model optimizes code-review quality?",
  "type": "knowledge_gap",
  "impact": 72.5,
  "cost": 8,
  "efficiency": 9.06
}
```

**Plan**:
- Run 5 code-review tasks with [opus], [sonnet], [haiku], [opus+sonnet], [opus+sonnet+haiku]
- Collect: quality_score, consensus_score, selected_model, total_cost
- Success: ≥ 5% quality improvement over current strategy

**Execution**:
- Execute 5 experiments (20 min total)
- Collect all metrics
- Validate: Data complete, confidence > 80%

**Outcome**:
- Discover [opus+sonnet] achieves 87% quality at lower cost
- Update orchestration to use this combo for code-reviews
- Save 15-20% on tokens while improving quality

### Scenario 2: Validate Untested Model Combination

**Discovery**:
```json
{
  "id": "untested-combo-['gpt-4o','opus']",
  "name": "Never tested: ['gpt-4o','opus']",
  "type": "untested_combination",
  "impact": 60,
  "cost": 5,
  "efficiency": 12
}
```

**Plan**:
- Run 3 diverse tasks with worker_models=[gpt-4o, opus]
- Use Fable as arbiter
- Collect: quality_score, consensus_score, selected_model, cost

**Execution**:
- 3 experiments (15 min)
- Cost: ~7,000 tokens

**Outcome**:
- If quality > 0.85: Add to standard combos for high-stakes tasks
- If quality < 0.75: Skip this combo, use other pairings

### Scenario 3: Reduce Costs on Test Generation

**Discovery**:
```json
{
  "id": "cost-anomaly-haiku-test_plan",
  "name": "Haiku on test_plan expensive: $2.10/quality",
  "type": "cost_anomaly",
  "impact": 48,
  "cost": 2,
  "efficiency": 24
}
```

**Plan**:
- Compare haiku vs sonnet on 5 test_plan tasks
- Same prompts, collect both outputs
- Compare: quality_score, total_cost_usd

**Execution**:
- 5 experiments (20 min)
- Cost: ~3,000 tokens

**Outcome**:
- Sonnet: quality 0.82, cost $0.30
- Haiku: quality 0.78, cost $0.25
- **Decision**: Use Sonnet for test_plan (slightly better quality, worth the cost)
- Expected savings: 12% cost reduction while improving quality

## Integration Points

### Input: SQLite Database
```sql
-- execution_log: Records of every workflow execution
SELECT workflow, task_type, quality_score, total_cost_usd, worker_models
FROM execution_log
WHERE outcome = 'success'
ORDER BY timestamp DESC
LIMIT 100;

-- model_performance: Aggregated metrics per model
SELECT model, task_type, avg_quality, cost_per_quality, sample_count
FROM model_performance
WHERE time_window = 'week';

-- parameter_tuning: Optimal parameters discovered
SELECT model, task_type, optimal_params, avg_quality, confidence
FROM parameter_tuning
WHERE confidence > 0.6;
```

### Output: Updated Database
```sql
-- New executions recorded
INSERT INTO execution_log (
  execution_id, workflow, task_type, task_description,
  worker_models, quality_score, confidence, duration_ms, outcome
);

-- New ratings recorded
INSERT INTO quality_ratings (
  execution_id, workflow, task_type, overall_score, rating_source
);

-- Model performance updated
INSERT INTO model_performance (
  model, task_type, avg_quality, sample_count, success_rate
);
```

## Files Delivered

| File | Purpose | Type |
|------|---------|------|
| `active-learning-engine.js` | Identify opportunities | Node.js (850 lines) |
| `strategic-learning-planner.js` | Plan experiments | Node.js (530 lines) |
| `experiment-executor.js` | Execute experiments | Node.js (580 lines) |
| `run-active-learning.sh` | Orchestrate workflow | Bash script (250 lines) |
| `ACTIVE_LEARNING_README.md` | User guide | Documentation (450 lines) |
| `IMPLEMENTATION_SUMMARY.md` | This file | Documentation |

**Total Implementation**: ~2,500 lines of code + documentation

## Usage

### Quick Start
```bash
# Make script executable
chmod +x ~/.claude/learning/run-active-learning.sh

# Run full pipeline (interactive)
cd ~/.claude/learning
./run-active-learning.sh --all

# Or run individual phases
./run-active-learning.sh --discover      # Phase 1 only
./run-active-learning.sh --plan          # Phase 2 only
./run-active-learning.sh --execute 10    # Phase 3 with 10 experiments
```

### Output
Results saved to: `~/.claude/learning/active-learning-results/[timestamp]/`
```
├── opportunities.json              # 20 top opportunities
├── plan/
│   ├── learning-plan.json          # Prioritized queue
│   └── experiment-prompts.md       # Readable experiments
├── discovery.log                   # Phase 1 logs
├── planning.log                    # Phase 2 logs
├── execution.log                   # Phase 3 logs
└── REPORT.md                       # Summary report
```

## Monitoring & Metrics

Track system effectiveness:

1. **Opportunity Quality**: Post-experiment quality vs baseline
   - Target: ≥ 5% improvement

2. **Prediction Accuracy**: Estimated vs actual tokens/time
   - Target: < 20% error

3. **ROI**: Learning value / predicted value
   - Target: > 0.8

4. **Convergence**: Model consensus trend
   - Target: ≥ 0.8 average

5. **Coverage**: % of important decision points explored
   - Target: ≥ 80%

## Future Enhancements

1. **Bayesian Optimization**: Model parameter space with Gaussian Process
2. **Multi-Armed Bandit**: Epsilon-greedy exploration/exploitation
3. **Transfer Learning**: Apply findings from one task to similar tasks
4. **Causal Analysis**: Determine causation, not just correlation
5. **Curriculum Learning**: Order experiments by difficulty

## Benefits

✅ **Systematic Approach**: No more ad-hoc experiments; prioritize by ROI

✅ **Data-Driven**: Decisions based on execution history analysis

✅ **Efficient**: Focus on high-impact, low-cost research

✅ **Automatic**: Identifies opportunities without manual analysis

✅ **Measurable**: Track impact of each experiment

✅ **Scalable**: Works with growing execution database

✅ **Integrated**: Uses existing SQLite schema; compatible with current system

## Conclusion

The **Active Learning System** transforms the orchestration platform from reactive optimization to **proactive discovery**. By systematically identifying and prioritizing learning opportunities, the system ensures experimentation effort is spent where it matters most:

- **High-impact** decisions (frequent, high-variance)
- **Low-cost** to validate (few tokens, quick execution)
- **High-ROI** research (impact/cost efficiency)

This creates a virtuous cycle: execute experiments → record outcomes → refine priorities → execute better experiments → continuous improvement.
