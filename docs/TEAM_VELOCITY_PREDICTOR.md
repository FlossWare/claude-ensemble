# Team Velocity Predictor

**Status:** Production Ready  
**Algorithm:** Gradient Boosting Regression (sklearn)  
**Created:** 2026-07-03  
**Location:** `tools/team_velocity_predictor.py`

## Overview

The Team Velocity Predictor estimates workflow performance metrics before execution using machine learning. It predicts:

1. **Total Duration** - How long the workflow will take
2. **Parallel Efficiency** - How effectively workers will parallelize
3. **Resource Utilization** - How much of available worker time will be used
4. **Success Probability** - Likelihood of successful completion

## Performance Metrics

Based on 1,000 training samples (synthetic data):

| Metric | Test R² | MAE | CV R² (mean ± std) |
|--------|---------|-----|-------------------|
| **Duration** | 0.9659 | 48.6s | 0.9356 ± 0.0180 |
| **Efficiency** | 0.8703 | 0.053 | 0.8380 ± 0.0184 |
| **Utilization** | 0.9461 | 0.032 | 0.9375 ± 0.0070 |
| **Success** | 0.7507 | 0.055 | 0.7630 ± 0.0292 |

**Top Features (Duration Prediction):**
1. Worker-to-task ratio (51.1%)
2. Complexity score (39.1%)
3. Parallel ratio (3.4%)

## Quick Start

### Python Usage

```python
from team_velocity_predictor import TeamVelocityPredictor

# Load trained model
predictor = TeamVelocityPredictor()
predictor.load('/home/sfloess/.claude/learning/team_velocity_predictor.pkl')

# Make prediction
config = {
    'num_workers': 6,
    'num_tasks': 20,
    'task_complexity': 'complex',
    'has_dependencies': True,
    'model_diversity': 5,
    'parallel_ratio': 0.65,
    'historical_success_rate': 0.80,
    'avg_worker_latency_ms': 4000,
}

result = predictor.predict(config)
print(f"Duration: {result['predicted_duration_minutes']:.1f} min")
print(f"Speedup: {result['actual_speedup']:.1f}x")
print(f"Success: {result['success_probability']:.1%}")
```

### JavaScript Usage

```javascript
const { predictVelocity, getOptimalWorkerCount } = 
  require('./shared/team-velocity-adapter.cjs');

// Make prediction
const config = {
  num_workers: 6,
  num_tasks: 20,
  task_complexity: 'complex',
  has_dependencies: true,
  model_diversity: 5,
  parallel_ratio: 0.65,
  historical_success_rate: 0.80,
  avg_worker_latency_ms: 4000,
};

const result = predictVelocity(config);
console.log(`Duration: ${result.predicted_duration_minutes} min`);
console.log(`Speedup: ${result.actual_speedup}x`);
console.log(`Success: ${result.success_probability * 100}%`);

// Get optimal worker count
const optimal = getOptimalWorkerCount(20, 'complex', true);
console.log(`Optimal workers: ${optimal}`);
```

### Command Line Usage

```bash
# Train model (first time only)
python3 tools/team_velocity_predictor.py

# Run usage examples
python3 tools/use_team_velocity_predictor.py

# Test JavaScript adapter
node workflows/test-team-velocity-adapter.mjs

# Run example workflow
node workflows/example-velocity-prediction-workflow.mjs
```

## Configuration Parameters

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `num_workers` | int | 1-8 | Number of workers available |
| `num_tasks` | int | 5-50 | Number of tasks to execute |
| `task_complexity` | string | simple/medium/complex/very_complex | Task difficulty |
| `has_dependencies` | bool | true/false | Whether tasks have dependencies |
| `model_diversity` | int | 2-8 | Number of unique models |
| `parallel_ratio` | float | 0.0-1.0 | How many tasks can run in parallel |
| `historical_success_rate` | float | 0.0-1.0 | Historical success rate |
| `avg_worker_latency_ms` | int | 1000-10000 | Average worker latency |

## Prediction Results

```javascript
{
  predicted_duration_ms: 156000,      // Duration in milliseconds
  predicted_duration_minutes: 2.6,    // Duration in minutes
  parallel_efficiency: 0.462,         // 0-1 (46.2%)
  resource_utilization: 0.469,        // 0-1 (46.9%)
  success_probability: 0.697,         // 0-1 (69.7%)
  theoretical_speedup: 6.0,           // Max possible speedup
  actual_speedup: 2.8,                // Predicted speedup
  efficiency_percent: 46.2,           // Efficiency as percentage
  features: { ... }                   // Input features
}
```

## Workflow Integration

### Before Execution

```javascript
import { estimateConfigFromTask, predictVelocity } from './shared/team-velocity-adapter.cjs';

// Estimate config from task description
const config = estimateConfigFromTask(
  'Implement user authentication with JWT tokens',
  availableWorkers
);

// Predict performance
const prediction = predictVelocity(config);

console.log(`Estimated duration: ${prediction.predicted_duration_minutes} min`);
console.log(`Success probability: ${prediction.success_probability * 100}%`);

// Decide whether to proceed
if (prediction.success_probability < 0.5) {
  console.warn('Low success probability - consider simplifying task');
}
```

### Optimize Worker Count

```javascript
import { getOptimalWorkerCount } from './shared/team-velocity-adapter.cjs';

const optimal = getOptimalWorkerCount(
  num_tasks,
  complexity,
  has_dependencies
);

console.log(`Using ${optimal} workers (of ${maxWorkers} available)`);
```

### Compare Configurations

```javascript
import { compareConfigurations } from './shared/team-velocity-adapter.cjs';

const configs = [
  { name: 'Small Team', num_workers: 3, ... },
  { name: 'Medium Team', num_workers: 6, ... },
  { name: 'Full Fleet', num_workers: 8, ... },
];

const comparisons = compareConfigurations(configs);

// Find best configuration
const best = comparisons.reduce((best, curr) => {
  const bestScore = best.prediction.success_probability / best.prediction.predicted_duration_ms;
  const currScore = curr.prediction.success_probability / curr.prediction.predicted_duration_ms;
  return currScore > bestScore ? curr : best;
});

console.log(`Best: ${best.name}`);
```

## Retraining with Real Data

When PostgreSQL database is available with workflow execution history:

```python
from team_velocity_predictor import TeamVelocityPredictor

predictor = TeamVelocityPredictor()

# This will automatically pull from workflow.executions and workflow.worker_results
predictor.train()  # Uses real data if available, synthetic otherwise

# Save updated model
predictor.save('/home/sfloess/.claude/learning/team_velocity_predictor.pkl')
```

The model will improve accuracy as more real workflow data accumulates.

## Key Insights

From training data analysis:

1. **Small teams (3-4 workers) excel at simple tasks**
   - Efficiency: ~87-90%
   - Best for quick fixes, simple updates

2. **Medium teams (5-6 workers) optimal for most workflows**
   - Efficiency: ~50-70%
   - Best balance for complex tasks

3. **Full fleet (8 workers) only for very large workflows**
   - Efficiency: ~40-50%
   - Only beneficial for 30+ independent tasks

4. **Dependencies kill parallelism**
   - Sequential workflows: 2-3x speedup max
   - Parallel workflows: 5-8x speedup possible

5. **Complexity impacts success more than duration**
   - Simple tasks: 90%+ success
   - Very complex tasks: 50-60% success

## Files

### Core Implementation
- `tools/team_velocity_predictor.py` - Main predictor class (600 lines)
- `tools/predict_team_velocity.py` - CLI interface for predictions
- `tools/use_team_velocity_predictor.py` - Usage examples

### JavaScript Integration
- `shared/team-velocity-adapter.cjs` - JavaScript API (300 lines)
- `workflows/test-team-velocity-adapter.mjs` - Adapter tests
- `workflows/example-velocity-prediction-workflow.mjs` - Integration example

### Model Files
- `~/.claude/learning/team_velocity_predictor.pkl` - Trained model (1.3MB)
- `~/.claude/learning/team_velocity_predictor_stats.json` - Training statistics

## Next Steps

1. **Collect Real Data:** Enable workflow execution logging to PostgreSQL
2. **Retrain Model:** Run training with real data after 100+ workflow executions
3. **Validate Predictions:** Compare predicted vs actual performance
4. **Tune Hyperparameters:** Adjust model parameters based on real data
5. **Add Features:** Consider additional predictive features (time of day, model availability, etc.)

## Related Components

- **Complexity Estimator** (`tools/complexity_estimator.py`) - Predicts individual task complexity
- **Workflow Storage** (`shared/workflow-storage-adapter.js`) - Stores execution results for training
- **Feedback Loop Optimizer** (`tools/feedback_loop_optimizer.py`) - Monitors model distribution

## Support

For issues or questions, see:
- Training logs: Check console output from `team_velocity_predictor.py`
- Model stats: `~/.claude/learning/team_velocity_predictor_stats.json`
- Test examples: Run `workflows/test-team-velocity-adapter.mjs`
