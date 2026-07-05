# Temporal Reasoning System

**Status:** Production-ready  
**Created:** 2026-07-03  
**Model Location:** `/home/sfloess/.claude/learning/temporal_reasoning_model.pkl`  
**Trainer:** `tools/temporal_reasoning_trainer.py`  
**API:** `tools/use_temporal_reasoning.py`

## Overview

The Temporal Reasoning System is a machine learning model trained to understand and classify temporal logic, planning, and time-based reasoning tasks. It uses a Random Forest classifier with custom temporal feature extraction to analyze queries involving:

1. **Interval Relationships** (Allen's Interval Algebra)
2. **Temporal Constraints** (deadlines, dependencies, durations)
3. **Planning & Scheduling** (resource allocation, optimization)
4. **Temporal Logic** (eventually, always, reachability)
5. **Pattern Detection** (periodic, sequential, concurrent)
6. **Causal-Temporal Relationships** (temporal causality)

## Performance Metrics

- **Training Accuracy:** 89.3%
- **Test Accuracy:** 79.1%
- **F1 Score:** 78.4%
- **Total Examples:** 455 (244 synthetic + 211 historical)
- **Feature Dimensions:** 636 (500 TF-IDF + 136 custom temporal features)

## Pattern Distribution

| Category    | Examples | Percentage |
|-------------|----------|------------|
| Planning    | 234      | 51.4%      |
| Interval    | 70       | 15.4%      |
| Constraint  | 53       | 11.6%      |
| Logic       | 36       | 7.9%       |
| Pattern     | 31       | 6.8%       |
| Causal      | 31       | 6.8%       |

## Top Important Features

1. `with` - Contextual relationships
2. `temporal_late` - Lateness indicators
3. `time` - Temporal references
4. `error` - Failure patterns
5. `temporal_window` - Time window constraints
6. `workflow` - Workflow patterns
7. `path` - Sequential paths
8. `execution` - Execution patterns
9. `duration` - Duration references
10. `causality_cause` - Causal relationships

## Quick Start

### Command Line Usage

```bash
# Analyze a temporal query
python3 tools/use_temporal_reasoning.py "Task A must complete before Task B starts"

# Output:
# Category: interval
# Prediction: before_simple
# Confidence: 0.554
# Recommendation: Use Allen's Interval Algebra for formal reasoning
```

### Python API Usage

```python
from tools.use_temporal_reasoning import load_temporal_reasoning_model, analyze_temporal_query

# Load model
model_data = load_temporal_reasoning_model()

# Analyze query
result = analyze_temporal_query("Schedule 5 tasks with deadlines", model_data)

print(f"Category: {result['category']}")
print(f"Prediction: {result['subcategory']}")
print(f"Confidence: {result['confidence']:.3f}")
print(f"Recommendation: {result['interpretation']['recommendation']}")
```

### Re-training the Model

```bash
# Train with latest data from PostgreSQL
python3 tools/temporal_reasoning_trainer.py

# Model saved to: /home/sfloess/.claude/learning/temporal_reasoning_model.pkl
# Statistics saved to: /home/sfloess/.claude/learning/temporal_reasoning_stats.json
```

## Temporal Reasoning Categories

### 1. Interval Relationships (Allen's Interval Algebra)

13 possible relations between time intervals:

- **before** - X finishes before Y starts
- **meets** - X finishes exactly when Y starts
- **overlaps** - X starts before Y, ends during Y
- **finished_by** - X and Y finish together, X starts first
- **contains** - X starts before Y and ends after Y
- **starts** - X and Y start together, X ends first
- **equals** - X and Y have same start and end
- **started_by** - X and Y start together, Y ends first
- **during** - X starts after Y and ends before Y
- **finishes** - X and Y finish together, Y starts first
- **overlapped_by** - Y starts before X, ends during X
- **met_by** - Y finishes exactly when X starts
- **after** - X starts after Y finishes

**Example queries:**
- "Task A must complete before Task B starts" → `interval_before_simple`
- "Meeting ends exactly when presentation starts" → `interval_meets_simple`
- "Project phase 1 overlaps with phase 2" → `interval_overlaps_simple`

### 2. Temporal Constraints

**Constraint types:**
- **Point constraints** - before_point, after_point, at_point
- **Duration constraints** - minimum_duration, maximum_duration, exact_duration
- **Dependency constraints** - finish_to_start, start_to_start, lag_constraint
- **Resource constraints** - sequential_access, capacity_limit, time_window

**Feasibility:**
- `feasible` - Constraints can be satisfied
- `infeasible` - Constraints are contradictory

**Example queries:**
- "Task must complete before deadline" → `constraint_deadline_feasible`
- "Minimum 2 hour gap between executions" → `constraint_minimum_gap_feasible`
- "Circular dependency A→B→C→A" → `constraint_ordering_infeasible`

### 3. Planning & Scheduling

**Planning types:**
- **Classical planning** - state_space_search, forward_search, backward_search
- **Temporal planning** - simple_temporal_network, partial_order_planning
- **Scheduling** - job_shop, resource_constrained, critical_path
- **Multi-agent planning** - distributed, cooperative, negotiation_based

**Difficulty levels:**
- `easy` - Simple sequential tasks
- `medium` - Resource allocation, parallelization
- `hard` - Multi-objective optimization, robust planning
- `very_hard` - Distributed planning, real-time scheduling

**Example queries:**
- "Schedule 5 sequential tasks" → `planning_simple_sequence_easy`
- "Optimize parallel execution order" → `planning_parallelization_medium`
- "Multi-objective optimization (time, cost, quality)" → `planning_multi_objective_hard`

### 4. Temporal Logic

**Logic types:**
- **Linear Temporal Logic** - next, eventually, always, until
- **Computation Tree Logic** - exists_next, always_eventually
- **Metric Temporal Logic** - bounded_eventually, timed_until
- **Interval Temporal Logic** - chop, star, begin, end

**Common queries:**
- **Reachability** - "Will system reach goal state?"
- **Safety** - "Can deadlock occur?"
- **Liveness** - "Will resource be freed eventually?"
- **Consistency** - "Is schedule conflict-free?"

**Example queries:**
- "Will task eventually complete?" → `logic_eventually_true`
- "Is resource always available?" → `logic_always_false`
- "Does execution violate timing?" → `logic_violation_false`

### 5. Pattern Detection

**Pattern types:**
- **Periodic patterns** - fixed_period, seasonal, cyclic
- **Sequential patterns** - strictly_sequential, partial_order, dag_sequence
- **Concurrent patterns** - fully_parallel, fork_join, pipeline
- **Temporal anomalies** - time_travel, deadlock, race_condition

**Confidence levels:**
- `high` - Clear, consistent pattern
- `medium` - Detectable but variable pattern
- `low` - Weak or sporadic pattern

**Example queries:**
- "Task runs every hour" → `pattern_periodic_high`
- "Workflow follows A→B→C" → `pattern_sequential_high`
- "Error rate spikes every Monday" → `pattern_periodic_anomaly_medium`

### 6. Causal-Temporal Relationships

**Causal relations:**
- `causal` - Verified causal relationship
- `correlation` - Correlation without causation
- `spurious` - Coincidental, unrelated

**Temporal relations:**
- `immediate` - Cause and effect simultaneous
- `delayed_effect` - Effect occurs later
- `leading_indicator` - Cause precedes effect
- `persistent_effect` - Long-lasting effect
- `temporary_effect` - Short-lived effect
- `cyclic` - Feedback loop
- `counterfactual` - Preventive action

**Example queries:**
- "Error causes job failure 5 min later" → `causal_causal_delayed_effect`
- "Load increase precedes slowdown" → `causal_causal_leading_indicator`
- "Two events coincide but unrelated" → `causal_spurious_coincident`

## Feature Engineering

### Custom Temporal Features (136 features)

1. **Temporal Keywords** (36 features)
   - Time references: before, after, during, while, when, until
   - Frequency: always, eventually, sometimes, often, rarely
   - Modifiers: immediately, delayed, scheduled, periodic
   - Boundaries: start, end, begin, finish, complete

2. **Planning Keywords** (27 features)
   - Actions: schedule, plan, allocate, optimize
   - Operations: minimize, maximize, balance, prioritize
   - Structure: order, sequence, coordinate, orchestrate
   - Resources: resource, capacity, dependency, bottleneck

3. **Constraint Keywords** (24 features)
   - Modal: must, cannot, required, forbidden, mandatory
   - Quantifiers: minimum, maximum, exactly, at-least, at-most
   - Bounds: within, between, range, limit
   - Satisfaction: satisfy, violate, conflict, feasible

4. **Causality Keywords** (18 features)
   - Relationships: cause, effect, consequence, impact
   - Actions: trigger, enable, disable, prevent
   - Connectors: lead-to, due-to, because, therefore

5. **Complexity Indicators** (31 features)
   - Multiple timescales: second, minute, hour, day, week, month
   - Dependencies: depend, require, need, must
   - Concurrency: parallel, concurrent, simultaneous
   - Deadlines: deadline, due, by, before
   - Interval relations: Allen's 13 relations
   - Optimization: optimize, minimize, maximize, best
   - Multi-objective: time, cost, quality, resource

## Training Data Sources

### Synthetic Data (244 examples)

Generated from temporal reasoning patterns:
- 12 interval reasoning examples × variations
- 11 constraint satisfaction examples × variations
- 10 planning scenario examples × variations
- 10 temporal logic queries × variations
- 10 pattern detection examples × variations
- 10 causal-temporal examples × variations

### Historical Data (211 examples)

Loaded from PostgreSQL `learning` database:
- Workflow executions (past 30 days)
- Phase execution patterns
- Duration-based classifications
- Outcome tracking

### Data Augmentation

Automated paraphrasing with synonym replacement:
- task → job, process, operation, activity, work item
- complete → finish, end, conclude, finalize
- start → begin, initiate, commence, launch
- before → prior to, ahead of, preceding
- after → following, subsequent to, later than
- must → should, needs to, has to, required to

## Integration Points

### Workflow Integration

```javascript
// In workflow files
const { execSync } = require('child_process');

function analyzeTemporalQuery(query) {
  const result = execSync(
    `python3 tools/use_temporal_reasoning.py "${query}"`,
    { encoding: 'utf-8' }
  );
  return JSON.parse(result);
}

// Example usage
const analysis = analyzeTemporalQuery(
  "Schedule parallel tasks with deadline constraints"
);

if (analysis.category === 'planning') {
  console.log(`Planning type: ${analysis.subcategory}`);
  console.log(`Confidence: ${analysis.confidence}`);
}
```

### Python Integration

```python
import sys
sys.path.insert(0, '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools')

from use_temporal_reasoning import load_temporal_reasoning_model, analyze_temporal_query

# Load once, reuse many times
model = load_temporal_reasoning_model()

# Analyze multiple queries
queries = [
    "Task A before Task B",
    "Optimize schedule",
    "Detect circular dependency"
]

for query in queries:
    result = analyze_temporal_query(query, model)
    print(f"{query}: {result['category']} - {result['subcategory']}")
```

### PostgreSQL Integration

The model automatically loads historical workflow data from PostgreSQL:

```python
# Trainer automatically queries these tables:
# - workflow.executions (workflow patterns)
# - workflow.phases (phase execution patterns)

# To add more training data:
# 1. Execute workflows (data auto-captured)
# 2. Re-run trainer: python3 tools/temporal_reasoning_trainer.py
# 3. Model updates with new patterns
```

## Use Cases

### 1. Workflow Scheduling

**Problem:** Need to schedule complex multi-phase workflows with dependencies.

**Solution:**
```python
result = analyze_temporal_query(
    "Phase A and B must complete before Phase C, with minimum 10 minute gap"
)

if result['category'] == 'constraint':
    # Apply constraint propagation
    validate_constraints(phases, result['subcategory'])
elif result['category'] == 'planning':
    # Use planning algorithm
    schedule = apply_planning_algorithm(phases, result['subcategory'])
```

### 2. Temporal Logic Verification

**Problem:** Verify temporal properties of system behavior.

**Solution:**
```python
properties = [
    "Will all tasks eventually complete?",
    "Is the system always deadlock-free?",
    "Can resource exhaustion occur?"
]

for prop in properties:
    result = analyze_temporal_query(prop)
    if result['category'] == 'logic':
        verify_temporal_property(prop, result['subcategory'])
```

### 3. Causal Analysis

**Problem:** Determine if temporal correlation implies causation.

**Solution:**
```python
result = analyze_temporal_query(
    "Deployment timestamp correlates with error spike"
)

if result['category'] == 'causal':
    if 'spurious' in result['subcategory']:
        print("Correlation likely spurious")
    elif 'causal' in result['subcategory']:
        print(f"Causal relationship: {result['subcategory']}")
        # Investigate temporal precedence
```

### 4. Pattern Detection

**Problem:** Identify temporal patterns in system behavior.

**Solution:**
```python
observations = [
    "Jobs fail every Monday at 9am",
    "Performance degrades over 24 hours",
    "Batch processes run nightly"
]

for obs in observations:
    result = analyze_temporal_query(obs)
    if result['category'] == 'pattern':
        print(f"Pattern type: {result['subcategory']}")
        print(f"Confidence: {result['confidence']}")
```

## Model Files

### Model Pickle (`temporal_reasoning_model.pkl`)

Contains:
- **model** - Trained RandomForestClassifier (200 trees, max_depth=30)
- **vectorizer** - TfidfVectorizer (500 features, trigrams, min_df=2)
- **feature_names** - List of 136 custom temporal feature names
- **patterns** - Temporal reasoning knowledge base (all pattern definitions)
- **training_stats** - Performance metrics and feature importance

**Size:** 9.1 MB

### Statistics JSON (`temporal_reasoning_stats.json`)

```json
{
  "total_examples": 455,
  "training_accuracy": 0.893,
  "test_accuracy": 0.791,
  "f1_score": 0.784,
  "feature_importance": {
    "with": 0.0256,
    "temporal_late": 0.0208,
    ...
  },
  "patterns_learned": {
    "planning": 234,
    "interval": 70,
    ...
  },
  "timestamp": "2026-07-03T19:28:12.383142"
}
```

## Continual Learning

The model improves over time by learning from historical workflow executions:

1. **Automatic Data Collection**
   - Workflow executions logged to PostgreSQL
   - Phase patterns captured automatically
   - Duration and outcome tracked

2. **Periodic Retraining**
   - Re-run trainer monthly: `python3 tools/temporal_reasoning_trainer.py`
   - Model learns new temporal patterns from production data
   - Statistics updated with new performance metrics

3. **Model Versioning**
   - Previous model backed up before retraining
   - Statistics track improvement over time
   - Rollback available if performance degrades

## Future Enhancements

### Planned Features

1. **Deep Learning Model** - Replace Random Forest with LSTM/Transformer for better sequence understanding
2. **Temporal Knowledge Graph** - Build graph of temporal relationships for reasoning
3. **Constraint Solver Integration** - Interface with Z3/CVC5 for formal verification
4. **Planning Algorithm Library** - Auto-select and invoke planning algorithms
5. **Multi-language Support** - Extend to non-English temporal queries
6. **Real-time Learning** - Online learning from streaming workflow data

### Research Directions

1. **Neuro-symbolic Reasoning** - Combine neural networks with symbolic temporal logic
2. **Transfer Learning** - Pre-train on large temporal reasoning datasets
3. **Explainable AI** - Provide human-readable explanations for predictions
4. **Active Learning** - Request labels for uncertain predictions
5. **Few-shot Learning** - Learn new temporal patterns from few examples

## References

### Temporal Reasoning Theory

- **Allen's Interval Algebra** - James F. Allen (1983)
  - "Maintaining knowledge about temporal intervals"
  - Computational Intelligence 1(3):221-268

- **Linear Temporal Logic** - Amir Pnueli (1977)
  - "The temporal logic of programs"
  - 18th Annual Symposium on FOCS

- **Planning Domain Definition Language (PDDL)** - McDermott et al. (1998)
  - Standard for representing planning problems

### Implementation

- **scikit-learn RandomForestClassifier**
  - Ensemble learning with decision trees
  - Handles high-dimensional sparse features well

- **TF-IDF Vectorization**
  - Captures important temporal keywords
  - N-gram features (unigrams, bigrams, trigrams)

- **Custom Feature Engineering**
  - Domain-specific temporal indicators
  - Complexity and relationship features

## Troubleshooting

### Common Issues

**Issue:** Low confidence predictions (< 0.3)

**Solution:** Query may be ambiguous or contain multiple temporal patterns. Review top 3 predictions for alternatives.

**Issue:** Wrong category prediction

**Solution:** Add more training examples for that pattern type and retrain model.

**Issue:** Model file not found

**Solution:** Run trainer first: `python3 tools/temporal_reasoning_trainer.py`

**Issue:** Database connection error

**Solution:** Check PostgreSQL is running on aio-01:5433 and user `claude` has access to `learning` database.

## Contact

For questions or issues with the temporal reasoning system:

1. Check documentation in `/docs/TEMPORAL_REASONING.md`
2. Review training logs for model performance
3. Inspect statistics in `temporal_reasoning_stats.json`
4. Re-train model with latest data if performance degrades

---

**Last Updated:** 2026-07-03  
**Maintainer:** claude-global-skills project  
**License:** Internal use only
