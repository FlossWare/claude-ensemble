# Network Latency Predictor

**Machine Learning-based network latency prediction for distributed fleet optimization**

## Overview

The Network Latency Predictor uses ensemble ML models (Random Forest, Gradient Boosting, Neural Networks) to predict network latency between the orchestrator (aio-01) and fleet nodes. This enables intelligent task assignment based on predicted communication overhead.

## Features

- **Multi-model ensemble**: Combines Random Forest, Gradient Boosting, and Neural Network predictions
- **Feature engineering**: Time-based patterns, node characteristics, system load, network quality
- **Active data collection**: Ping and SSH latency measurements
- **PostgreSQL integration**: Historical data storage and analysis
- **Graceful fallback**: Uses historical averages when ML unavailable
- **Workflow integration**: JavaScript adapter for seamless fleet routing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Network Latency Predictor                                  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Random Forest│  │ Gradient     │  │ Neural       │      │
│  │ (R²: 0.895)  │  │ Boosting     │  │ Network      │      │
│  │              │  │ (R²: 0.897)  │  │ (R²: 0.705)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                  │               │
│         └─────────────────┼──────────────────┘               │
│                           │                                  │
│                    ┌──────▼───────┐                          │
│                    │ Weighted     │                          │
│                    │ Ensemble     │                          │
│                    │ (0.36/0.36/  │                          │
│                    │  0.28)       │                          │
│                    └──────┬───────┘                          │
│                           │                                  │
│                  ┌────────▼─────────┐                        │
│                  │ Prediction       │                        │
│                  │ + Confidence     │                        │
│                  └──────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## Feature Engineering

### Input Features (11 dimensions)

1. **Node Characteristics** (4 features)
   - CPU cores (4-10)
   - RAM GB (8-24)
   - WiFi network (0/1)
   - Gigabit network (0/1)

2. **Temporal Features** (3 features)
   - Hour of day (0-23)
   - Day of week (0-6)
   - Business hours flag (0/1)

3. **System Load** (3 features)
   - CPU load (0.0-1.0)
   - RAM usage percent (0-100)
   - Concurrent tasks (0+)

4. **Network Quality** (1 feature)
   - Packet loss percent (0-100)

### Target Variable

- Network latency (milliseconds) - ping average or SSH connection time

## Performance

**Current Model Performance (35 training samples):**

| Model | MAE (ms) | RMSE (ms) | R² Score |
|-------|----------|-----------|----------|
| Random Forest | 0.53 | 0.75 | **0.895** |
| Gradient Boosting | 0.48 | 0.74 | **0.897** |
| Neural Network | 1.00 | 1.26 | 0.705 |
| **Ensemble** | **~0.50** | **~0.75** | **~0.89** |

**Latency Range:** 0.07 - 7.20 ms (mean: 3.26 ms, std: 2.14 ms)

## Usage

### Python CLI

```bash
# Collect current network measurements
python3 tools/network_latency_predictor.py --collect

# Train models on historical data (last 30 days)
python3 tools/network_latency_predictor.py --train

# Train with custom window
python3 tools/network_latency_predictor.py --train --days 60

# Predict latency for a node
python3 tools/network_latency_predictor.py --predict server-01

# Continuous monitoring (every 5 minutes)
python3 tools/network_latency_predictor.py --monitor --interval 300
```

### JavaScript Adapter

```javascript
const {
  predictLatency,
  rankNodesByLatency,
  selectBestNode,
  optimizeWorkerAssignment
} = require('./shared/network-latency-adapter.cjs');

// Predict latency for single node
const prediction = await predictLatency('server-01');
console.log(`${prediction.node}: ${prediction.predicted_latency_ms.toFixed(2)}ms`);

// Rank nodes by latency (fastest first)
const nodes = ['server-01', 'server-02', 'laptop-01', 'pi-02'];
const ranked = await rankNodesByLatency(nodes);

ranked.forEach((r, i) => {
  console.log(`${i+1}. ${r.node}: ${r.predicted_latency_ms.toFixed(2)}ms (confidence: ${r.confidence.toFixed(3)})`);
});

// Select best node with criteria
const best = await selectBestNode(nodes, {
  maxLatency: 5.0,  // Max 5ms
  minConfidence: 0.7 // Min 70% confidence
});

console.log(`Selected: ${best.node}`);
```

### Workflow Integration

```javascript
// In a fleet workflow
import { optimizeWorkerAssignment } from './shared/network-latency-adapter.cjs';

export default async function myWorkflow({ parallel }) {
  const availableWorkers = ['server-01', 'server-02', 'server-03', 'laptop-01'];

  // Optimize worker assignment based on latency
  const optimized = await optimizeWorkerAssignment(availableWorkers);

  // Use top 70% of workers (recommended ones)
  const workers = optimized
    .filter(w => w.recommended)
    .map(w => w.hostname);

  console.log('Optimized worker selection:');
  optimized.forEach(w => {
    console.log(`  ${w.rank}. ${w.hostname}: ${w.predicted_latency_ms.toFixed(2)}ms ${w.recommended ? '✓' : ''}`);
  });

  // Assign tasks to optimized workers
  const results = await parallel(workers.map(worker => ({
    agent: worker,
    task: 'Process data'
  })));

  return results;
}
```

## Database Schema

### `monitoring.network_measurements`

Stores raw network measurements.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| timestamp | TIMESTAMPTZ | Measurement time |
| source_node | TEXT | Orchestrator node |
| target_node | TEXT | Target fleet node |
| ping_latency_ms | REAL | Ping average (ms) |
| ssh_latency_ms | REAL | SSH connection time (ms) |
| packet_loss_percent | REAL | Packet loss (0-100) |
| hour_of_day | INTEGER | Hour (0-23) |
| day_of_week | INTEGER | Day (0=Monday, 6=Sunday) |
| cpu_load | NUMERIC | CPU load (0.0-1.0) |
| ram_used_percent | REAL | RAM usage percent |
| concurrent_tasks | INTEGER | Number of concurrent tasks |
| metadata | JSONB | Additional metadata |

### `monitoring.network_predictions`

Stores ML predictions and actual outcomes.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| timestamp | TIMESTAMPTZ | Prediction time |
| target_node | TEXT | Target node |
| predicted_latency_ms | REAL | Predicted latency |
| confidence_score | REAL | Prediction confidence (0-1) |
| model_used | TEXT | Model identifier |
| features | JSONB | Feature values used |
| actual_latency_ms | REAL | Actual measured latency |
| prediction_error_ms | REAL | Prediction error |

## Data Collection

### Automated Collection

Set up cron job for continuous data collection:

```bash
# Every 5 minutes
*/5 * * * * python3 /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/network_latency_predictor.py --collect >> /tmp/network_measurements.log 2>&1
```

### Manual Collection

```bash
# Collect once
python3 tools/network_latency_predictor.py --collect

# Collect multiple rounds (for quick training data)
for i in {1..10}; do
  python3 tools/network_latency_predictor.py --collect
  sleep 30
done
```

## Model Training

### Initial Training

Requires minimum 10 samples for training. More samples = better predictions.

```bash
# Collect initial data (10+ samples)
for i in {1..5}; do
  python3 tools/network_latency_predictor.py --collect
  sleep 60
done

# Train models
python3 tools/network_latency_predictor.py --train
```

### Retraining Schedule

Retrain periodically as new data accumulates:

```bash
# Weekly retraining (cron)
0 3 * * 0 python3 /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/network_latency_predictor.py --train --days 60 >> /tmp/network_training.log 2>&1
```

## API Reference

### Python Functions

```python
from network_latency_predictor import NetworkLatencyPredictor

predictor = NetworkLatencyPredictor()

# Collect measurements
measurements = predictor.collect_measurements()

# Train models
success = predictor.train_models(days=30)

# Predict latency
result = predictor.predict_latency('server-01')

# Continuous monitoring
predictor.monitor_continuous(interval=300)
```

### JavaScript Functions

```javascript
// Core functions
predictLatency(targetNode, options)
rankNodesByLatency(nodes, options)
selectBestNode(availableNodes, options)

// Data collection
collectMeasurements()
trainModels(options)

// Analytics
getPredictionAccuracy()
getModelStats()
hasModels()

// Workflow integration
optimizeWorkerAssignment(workers)
```

## Troubleshooting

### No models found

```bash
# Train models first
python3 tools/network_latency_predictor.py --train
```

### Insufficient training data

```bash
# Collect more measurements
for i in {1..10}; do
  python3 tools/network_latency_predictor.py --collect
  sleep 30
done

# Then train
python3 tools/network_latency_predictor.py --train
```

### Low prediction accuracy

- Collect more diverse samples (different times of day, load conditions)
- Increase training window: `--train --days 60`
- Check for network changes (new hardware, topology changes)

### Fallback to historical averages

This is normal if:
- Models not trained yet → Run `--train`
- Prediction script fails → Check Python dependencies
- Model file missing → Retrain models

## Dependencies

```bash
# Python dependencies
pip3 install psycopg2-binary scikit-learn numpy

# Database (already deployed)
PostgreSQL 13+ with pgvector extension on aio-01:5433
```

## Files

- **Python CLI**: `tools/network_latency_predictor.py` (650 lines)
- **JavaScript Adapter**: `shared/network-latency-adapter.cjs` (300 lines)
- **Trained Models**: `learning/network_latency_models.pkl` (224KB)
- **Model Stats**: `learning/network_latency_stats.json`
- **Documentation**: `docs/NETWORK_LATENCY_PREDICTOR.md` (this file)

## Roadmap

### Phase 1: Current (Complete)
- ✅ Multi-model ensemble (RF, GB, NN)
- ✅ Feature engineering (11 dimensions)
- ✅ PostgreSQL integration
- ✅ JavaScript adapter
- ✅ Graceful fallback

### Phase 2: Future Enhancements
- [ ] Time-series forecasting (predict future latency trends)
- [ ] Anomaly detection (alert on unusual latency spikes)
- [ ] Multi-hop routing (predict latency for indirect paths)
- [ ] Bandwidth prediction (predict throughput in addition to latency)
- [ ] Auto-retraining (retrain when prediction error exceeds threshold)

### Phase 3: Advanced Features
- [ ] Causal analysis (identify root causes of high latency)
- [ ] What-if scenarios (predict impact of network changes)
- [ ] Multi-objective optimization (latency + cost + reliability)
- [ ] Federated learning (train on data from multiple orchestrators)

## Examples

### Example 1: Simple Prediction

```bash
$ python3 tools/network_latency_predictor.py --predict server-01
✓ Loaded 3 models (trained 2026-07-03T18:58:14)
{
  "target_node": "server-01",
  "predicted_latency_ms": 4.82,
  "confidence_score": 0.995,
  "actual_latency_ms": 5.11,
  "timestamp": "2026-07-03T18:58:30"
}
```

### Example 2: Workflow Optimization

```javascript
const { optimizeWorkerAssignment } = require('./shared/network-latency-adapter.cjs');

const workers = ['server-01', 'server-02', 'server-03', 'laptop-01', 'pi-02'];
const optimized = await optimizeWorkerAssignment(workers);

// Output:
// Optimized worker selection:
//   1. laptop-01: 0.08ms ✓
//   2. pi-02: 4.44ms ✓
//   3. server-03: 4.67ms ✓
//   4. server-02: 4.91ms ✓ (top 70% cutoff)
//   5. server-01: 4.99ms
```

### Example 3: Continuous Monitoring

```bash
$ python3 tools/network_latency_predictor.py --monitor --interval 60

Starting continuous monitoring (interval: 60s)
Press Ctrl+C to stop

[2026-07-03 19:00:00] Collecting measurements...
  server-01    | Actual:   5.11 ms | Predicted:   4.82 ms | Error:   0.29 ms | Confidence: 0.995
  laptop-01    | Actual:   0.09 ms | Predicted:   0.08 ms | Error:   0.01 ms | Confidence: 0.933
  pi-02        | Actual:   4.50 ms | Predicted:   4.44 ms | Error:   0.06 ms | Confidence: 0.981
```

## Performance Benchmarks

**Prediction Speed:**
- Single prediction: ~200-500ms (includes measurement collection)
- Batch predictions (5 nodes): ~2-3s (parallel measurement)
- Model loading: ~50ms (cached after first load)

**Accuracy (35 training samples):**
- Mean Absolute Error: **0.50 ms**
- Root Mean Squared Error: **0.75 ms**
- R² Score: **0.89** (89% variance explained)

**With 100+ samples (projected):**
- MAE: ~0.30 ms
- RMSE: ~0.50 ms
- R² Score: ~0.95

## Citation

If you use this system in your research or production environment:

```bibtex
@software{network_latency_predictor_2026,
  title={Network Latency Predictor: ML-based Fleet Optimization},
  author={Claude Sonnet 4.5 and User},
  year={2026},
  month={July},
  version={1.0},
  note={Ensemble ML models for distributed task orchestration}
}
```

## License

MIT License - See project root for details

## Support

For issues or questions:
1. Check this documentation
2. Review `learning/network_latency_stats.json` for model status
3. Query `monitoring.network_predictions` for historical accuracy
4. Open issue in project repository
