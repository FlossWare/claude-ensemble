# Online Learning System

Real-time, incremental learning system that continuously improves model selection based on workflow outcomes.

## Overview

The Online Learning System implements **true online learning** with incremental model updates after each workflow execution. Unlike batch learning systems that require periodic retraining, this system updates continuously in real-time.

### Key Features

1. **Online Gradient Descent** - Incremental weight updates (no batch retraining)
2. **Hedge Algorithm** - Exponential weights for exploration/exploitation
3. **Follow-the-Regularized-Leader (FTRL)** - Advanced online convex optimization
4. **Passive-Aggressive Updates** - Margin-based learning
5. **Experience Replay** - Prevents catastrophic forgetting
6. **Real-time Integration** - Updates from PostgreSQL workflow feedback

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  JavaScript Workflows                                       │
│  ├─ Select workers using online learning                   │
│  ├─ Execute tasks                                           │
│  └─ Update models based on outcomes                        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────────────┐
│  Python Online Learning Engine                              │
│  ├─ OnlineLinearModel (per model)                          │
│  │  ├─ OGD (Online Gradient Descent)                       │
│  │  ├─ FTRL (Follow-the-Regularized-Leader)               │
│  │  └─ PA (Passive-Aggressive)                            │
│  ├─ HedgeAlgorithm (exploration/exploitation)              │
│  └─ ExperienceReplay (continual learning)                  │
└────────────────┬────────────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL Learning Database (aio-01:5433)                 │
│  └─ workflow.* tables (execution logs, outcomes)           │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### JavaScript Integration

```javascript
import { OnlineLearningClient, OnlineLearningWorkflow } from './shared/online-learning-integration.js';

// Create client
const learner = new OnlineLearningClient();

// Select best model for task
const model = await learner.selectModel(
  'Debug authentication bug in Java service',
  { workflow: 'debugging', priority: 0.8 }
);

// Execute task with selected model...
// (your workflow logic here)

// Update based on outcome
const reward = learner.calculateReward({
  outcome: 'success',
  quality_score: 0.85,
  duration_ms: 5000,
  metadata: { confidence: 0.9 }
});

await learner.update(model, taskDescription, reward, metadata);
```

### Workflow Integration

```javascript
import { OnlineLearningWorkflow } from './shared/online-learning-integration.js';

const workflow = new OnlineLearningWorkflow();

// Select diverse workers (mix exploration + exploitation)
const workers = await workflow.selectWorkers(
  'Research firmware reverse engineering methods',
  3,  // num workers
  { workflow: 'deep-research', priority: 0.9 }
);

// Execute tasks...
const workerResults = await executeWorkers(workers, task);

// Arbiter selects best result...
const arbiterDecision = await arbiter(workerResults);

// Update online learning from all workers
await workflow.updateFromWorkers(
  taskDescription,
  workerResults,
  arbiterDecision
);
```

### Python Direct Usage

```python
from online_learning_system import OnlineLearningOrchestrator

# Create orchestrator
orchestrator = OnlineLearningOrchestrator(
    context_dim=20,
    learning_rate=0.01,
    update_method='ftrl'  # or 'ogd', 'pa'
)

# Select model
model = orchestrator.select_model(
    task_description='Write unit tests for API',
    metadata={'workflow': 'testing'},
    explore=True
)

# Update after execution
orchestrator.update(
    model='opus',
    task_description='Write unit tests for API',
    reward=0.85,
    metadata={'workflow': 'testing', 'phase': 'execution'}
)

# Save state
orchestrator.save()  # Saves to ~/.claude/learning/online_learning_state.json

# Get statistics
stats = orchestrator.get_statistics()
print(f"Best model: {stats['best_model']}")
print(f"Total updates: {stats['total_updates']}")
```

## Update Methods

### Online Gradient Descent (OGD)

**Best for**: Simple, stable updates

```python
orchestrator = OnlineLearningOrchestrator(update_method='ogd')
```

- Classic online learning algorithm
- Simple gradient descent on each example
- Guaranteed convergence for convex problems

### Follow-the-Regularized-Leader (FTRL)

**Best for**: Sparse solutions, feature selection (default)

```python
orchestrator = OnlineLearningOrchestrator(update_method='ftrl')
```

- State-of-the-art for online learning
- L1/L2 regularization built-in
- Used in Google's ad click prediction
- Better generalization than OGD

### Passive-Aggressive (PA)

**Best for**: Margin-based tasks, high-confidence updates

```python
orchestrator = OnlineLearningOrchestrator(update_method='pa')
```

- Only updates on mistakes (passive when correct)
- Aggressive correction when wrong
- Good for classification-like tasks

## Context Features (20-dim)

The system extracts 20 features from each task:

### Task Type Features (dims 0-9)
- code, debug, research, write, review, test, deploy, design, optimize, analyze

### Complexity Features (dims 10-14)
- Task length (normalized)
- Technical term density
- Uncertainty markers
- Dependencies
- Constraints

### Metadata Features (dims 15-19)
- Workflow type
- Phase progress
- Priority
- Time constraints
- Resource constraints

## Reward Calculation

Rewards are calculated automatically from workflow outcomes:

```javascript
const reward = learner.calculateReward({
  outcome: 'success' | 'failed' | 'error',
  quality_score: 0.0-1.0,
  duration_ms: number,
  timeout_ms: number (optional),
  metadata: {
    confidence: 0.0-1.0,
    was_selected: boolean
  }
});
```

**Reward formula**:
- Base: success=0.7, failed=0.3, error=0.1
- Adjusted by quality_score: `reward * 0.5 + quality * 0.5`
- Penalty for near-timeout: `reward * 0.9`
- Bonus for high confidence: `reward * 1.1`
- Bonus if arbiter selected: `reward * 1.2`

## Exploration vs Exploitation

### Hedge Algorithm

The system uses the **Hedge algorithm** to balance exploration/exploitation:

```javascript
// 40% exploration, 60% exploitation
const workers = await workflow.selectWorkers(task, 3);
```

- Maintains probability distribution over models
- Exponentially weights by cumulative loss
- Automatically balances exploration based on uncertainty

### Manual Control

```javascript
// Pure exploitation (use best known model)
const model = await learner.selectModel(task, metadata, false);

// Pure exploration (random from distribution)
const model = await learner.selectModel(task, metadata, true);
```

## Continual Learning

### Experience Replay

Prevents catastrophic forgetting by replaying past experiences:

```python
orchestrator = OnlineLearningOrchestrator(
    replay_capacity=1000,      # Max experiences to store
    replay_frequency=10        # Replay every N updates
)
```

- Stores last 1000 experiences
- Replays batch of 10 every 10 updates
- Maintains performance on old tasks while learning new ones

### Diversity Protection

The system tracks model selection diversity to prevent >70/30 dominance (anti-feedback-loop safeguard from CLAUDE.md):

```javascript
const stats = await learner.getStatistics();
// stats.hedge_weights shows current distribution
```

## Performance

### Latency

- **Model selection**: <50ms (Python execution)
- **Update**: <100ms (with disk persistence)
- **State load (cached)**: <1ms (JavaScript only)

### Memory

- **Per model**: 20 floats (weights) + 1 float (bias) = ~170 bytes
- **36 models**: ~6KB total
- **Replay buffer (1000 items)**: ~100KB

### Throughput

- **Updates/second**: ~50 (limited by disk I/O)
- **Concurrent workflows**: Unlimited (stateless per request)

## State Persistence

State is automatically saved to:
```
~/.claude/learning/online_learning_state.json
```

**Backup strategy**:
- Integrated with existing PostgreSQL backups
- Daily backups to `server-ap:/exports/backups/laptop-01-learning/`
- 30-day retention

**State includes**:
- Model weights and biases
- Hedge algorithm weights
- Experience replay buffer
- Update counters and statistics

## Monitoring

### Get Statistics

```javascript
const stats = await learner.getStatistics();

console.log(stats.total_updates);          // Total number of updates
console.log(stats.best_model);             // Model with lowest avg loss
console.log(stats.num_models);             // Number of models tracked
console.log(stats.hedge_weights);          // Current exploration distribution
console.log(stats.model_update_counts);    // Updates per model
console.log(stats.model_avg_losses);       // Average loss per model
```

### Get Rankings

```javascript
const rankings = await learner.getModelRankings();

rankings.forEach(r => {
  console.log(`${r.model}: ${r.score}`);
});
```

## Integration with Existing Systems

### PostgreSQL Workflow Tables

The system reads from:
- `workflow.worker_results` - Worker execution logs
- `workflow.executions` - Workflow metadata
- `workflow.learnings` - Extracted insights

### Model Selection

Replaces static model selection with learned selection:

**Before**:
```javascript
const workers = ['opus', 'sonnet', 'haiku'];  // Static
```

**After**:
```javascript
const workers = await workflow.selectWorkers(task, 3);  // Learned
```

### Thompson Sampling Integration

Works alongside existing Thompson Sampling bandit:
- **Thompson Sampling**: Strategy-level selection
- **Online Learning**: Model-level selection

Both systems can coexist and complement each other.

## Testing

Run tests:
```bash
# Python unit tests
python3 shared/online_learning_system.py

# JavaScript integration tests
node shared/test-online-learning.js
```

## Troubleshooting

### Issue: Module not found

```bash
# Ensure Python file uses underscores, not dashes
ls shared/online_learning_system.py  # ✓ Correct
ls shared/online-learning-system.py  # ✗ Wrong (Python can't import)
```

### Issue: State file permission denied

```bash
# Check directory permissions
ls -la ~/.claude/learning/
chmod 755 ~/.claude/learning
```

### Issue: Database connection failed

```bash
# Verify PostgreSQL is running
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT 1"
```

### Issue: Slow Python execution

```bash
# Use cached state loading (JavaScript only, no Python)
const state = await learner.loadState();
```

## Future Enhancements

### Planned Features

1. **Multi-Armed Bandits** - LinUCB, Thompson Sampling integration
2. **Neural Online Learning** - Online gradient descent for neural networks
3. **Batch Updates** - Efficient mini-batch processing
4. **A/B Testing** - Built-in statistical testing framework
5. **AutoML Integration** - Hyperparameter tuning via online learning

### Research Directions

1. **Meta-Learning** - Learn-to-learn across workflows
2. **Transfer Learning** - Share knowledge across domains
3. **Multi-Task Learning** - Joint optimization across task types
4. **Active Learning** - Select most informative examples to label

## References

- **Online Learning**: Shalev-Shwartz, 2011 (Online Learning and Online Convex Optimization)
- **FTRL**: McMahan et al., 2013 (Ad Click Prediction: a View from the Trenches)
- **Hedge Algorithm**: Freund & Schapire, 1997 (A Decision-Theoretic Generalization of On-Line Learning)
- **Experience Replay**: Lin, 1992 (Self-Improving Reactive Agents Based on Reinforcement Learning)

## Authors

- **Implementation**: Built 2026-07-03
- **Architecture**: Multi-AI consensus design
- **Integration**: Distributed LLM Orchestration Framework

## License

Internal use only. Part of Distributed LLM Orchestration Framework.
