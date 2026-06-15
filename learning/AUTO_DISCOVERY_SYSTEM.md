# Auto-Discovery System

Complete self-improving AI pipeline that automatically discovers optimization patterns and applies them.

## Overview

The auto-discovery system continuously learns from execution history to optimize model selection:

1. **Pattern Discovery** - Analyzes Thompson Sampling trends and execution logs to identify patterns
2. **Metadata Tracking** - Tracks discovery application and evidence collection
3. **Confidence Updates** - Adjusts confidence scores based on real-world outcomes
4. **Automatic Application** - Applies high-confidence discoveries to future selections

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Discovery Pipeline                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐      ┌──────────────────┐           │
│  │ Thompson Sampling│      │  Execution Logs  │           │
│  │     Trends       │      │   (SQLite DB)    │           │
│  └────────┬─────────┘      └────────┬─────────┘           │
│           │                         │                      │
│           └─────────┬───────────────┘                      │
│                     ▼                                      │
│          ┌────────────────────┐                           │
│          │ discover-patterns  │ ◄─── Every 6 hours        │
│          │     .js            │                           │
│          └──────────┬─────────┘                           │
│                     │                                      │
│                     ▼                                      │
│          ┌────────────────────┐                           │
│          │  New Discoveries   │                           │
│          │ (confidence ≥ 0.75)│                           │
│          └──────────┬─────────┘                           │
│                     │                                      │
│                     ▼                                      │
│          ┌────────────────────┐                           │
│          │ discoveries.json   │ ◄─── Auto-append          │
│          └──────────┬─────────┘                           │
│                     │                                      │
│                     ▼                                      │
│          ┌────────────────────┐                           │
│          │ apply-discoveries  │ ◄─── On each selection    │
│          │      .js           │                           │
│          └──────────┬─────────┘                           │
│                     │                                      │
│                     ▼                                      │
│          ┌────────────────────┐                           │
│          │   orchestrator.js  │                           │
│          │  (model selection) │                           │
│          └──────────┬─────────┘                           │
│                     │                                      │
│                     ▼                                      │
│          ┌────────────────────┐                           │
│          │   Execution        │                           │
│          └──────────┬─────────┘                           │
│                     │                                      │
│                     ▼                                      │
│          ┌────────────────────┐                           │
│          │ recordResult()     │ ◄─── Update evidence      │
│          │ update-discovery-  │                           │
│          │  metadata.js       │                           │
│          └────────────────────┘                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Pattern Discovery (`discover-patterns.js`)

Analyzes execution data to find optimization patterns.

**Pattern Sources:**
- Thompson Sampling trends (model success rates)
- Execution log analysis (task-specific performance)
- Cost-quality tradeoffs
- Schema compliance issues

**Confidence Scoring:**
```javascript
confidence = effectSize * log10(sampleCount) / 2
```

**Usage:**
```bash
# Discover patterns (dry run)
node learning/discover-patterns.js

# Auto-add high-confidence patterns
node learning/discover-patterns.js --apply

# Custom confidence threshold
node learning/discover-patterns.js --apply --min-conf 0.8
```

**Example Output:**
```
discovery_thompson_sonnet_over_haiku
  Pattern:     prefer-sonnet-over-haiku
  Description: sonnet outperforms haiku (success rate: 85.3% vs 62.1%)
  Confidence:  89.2%
  Evidence:    147 samples
  Source:      thompson-sampling
```

### 2. Metadata Tracking (`update-discovery-metadata.js`)

Tracks discovery usage and outcomes.

**Tracked Metrics:**
- `apply_count` - How many times discovery was used
- `evidence_count` - How many executions provided evidence
- `quality_impact` - Running average of quality improvement
- `confidence` - Bayesian updated confidence score

**Confidence Updates:**
```javascript
// Successful execution → boost confidence
confidence = min(0.99, confidence * 1.05)

// Failed execution → decay confidence
confidence = confidence * 0.95

// Mark inactive if confidence < 0.60
```

**Usage:**
```bash
# Recompute all confidence scores
node learning/update-discovery-metadata.js --recompute

# Prune low-confidence discoveries
node learning/update-discovery-metadata.js --prune

# Show statistics
node learning/update-discovery-metadata.js --stats
```

### 3. Discovery Scheduler (`discovery-scheduler.js`)

Runs discovery generation on a schedule.

**Default Schedule:**
- Discovery generation: Every 6 hours
- Confidence updates: Every run
- Pruning: Every run

**Usage:**
```bash
# Run once
node learning/discovery-scheduler.js

# Run as daemon (every 6 hours)
node learning/discovery-scheduler.js --daemon

# Custom interval (every 2 hours)
node learning/discovery-scheduler.js --daemon --interval 2

# Check status
node learning/discovery-scheduler.js --status
```

**Logs:**
- Location: `~/.claude/learning/logs/discovery-scheduler.log`
- Contains: All discovery activities, new patterns, errors

### 4. Integration Points

#### Orchestrator Integration

**Model Selection:**
```javascript
import { selectModel, recordResult } from './orchestrator.js';

// Select model with discoveries applied
const model = await selectModel('code-review', {
  strategy: 'thompson',
  requires_schema: true,
  cost_sensitivity: 'high',
});
// → Discoveries automatically filter/bias models

// After execution, record result with evidence tracking
await recordResult(model, qualityScore, {
  appliedDiscoveries: ['discovery_001', 'discovery_002'],
  context: { task_type: 'code-review' },
});
// → Updates Thompson Sampling AND discovery evidence
```

#### Apply Discoveries Integration

**Automatic Tracking:**
```javascript
import { applyDiscoveries } from './learning/apply-discoveries.js';

const config = await applyDiscoveries(
  ['opus', 'sonnet', 'haiku', 'fable'],
  {
    task_type: 'security-review',
    requires_schema: false,
    cost_sensitivity: 'high',
  }
);

// config contains:
// - models: filtered list
// - biases: model preference multipliers
// - diversity_weight: diversity parameter
// - worker_count: optimal worker count
// - applied_discoveries: IDs of applied patterns
```

## Discovery Types

### 1. Model Preference

Bias model selection based on performance.

**Example:**
```json
{
  "id": "discovery_001",
  "type": "model_preference",
  "pattern": "prefer-sonnet-over-haiku",
  "conditions": {},
  "action": {
    "type": "bias_models",
    "params": {
      "bias": {
        "sonnet": 1.5,
        "haiku": 0.7
      }
    }
  }
}
```

### 2. Model Filter

Exclude models from selection.

**Example:**
```json
{
  "id": "discovery_004",
  "type": "model_filter",
  "pattern": "never-fable-for-structured-output",
  "conditions": {
    "requires_schema": true
  },
  "action": {
    "type": "filter_models",
    "params": {
      "exclude": ["fable"]
    }
  }
}
```

### 3. Task Routing

Route specific tasks to optimal models.

**Example:**
```json
{
  "id": "discovery_003",
  "type": "task_routing",
  "pattern": "creative-tasks-prefer-opus-fable",
  "conditions": {
    "task_type": ["code-generation", "creative-writing"]
  },
  "action": {
    "type": "bias_models",
    "params": {
      "bias": {
        "opus": 1.5,
        "fable": 1.3
      }
    }
  }
}
```

### 4. Cost Optimization

Prefer cost-effective models.

**Example:**
```json
{
  "id": "discovery_002",
  "type": "model_filter",
  "pattern": "cost-sensitive-avoid-opus",
  "conditions": {
    "cost_sensitivity": "high",
    "budget_constraint": true
  },
  "action": {
    "type": "filter_models",
    "params": {
      "exclude": ["opus"],
      "prefer": ["sonnet", "haiku"]
    }
  }
}
```

## Deployment

### Standalone Daemon

Run discovery scheduler as a background service:

```bash
# Start daemon
nohup node learning/discovery-scheduler.js --daemon --interval 6 > /dev/null 2>&1 &

# Check logs
tail -f ~/.claude/learning/logs/discovery-scheduler.log

# Stop daemon
pkill -f discovery-scheduler.js
```

### Systemd Service

Create `/etc/systemd/system/claude-discovery.service`:

```ini
[Unit]
Description=Claude Auto-Discovery Scheduler
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/claude-global-skills
ExecStart=/usr/bin/node learning/discovery-scheduler.js --daemon --interval 6
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable claude-discovery
sudo systemctl start claude-discovery
sudo systemctl status claude-discovery
```

### Integration with Background Learner

The discovery scheduler is now integrated into `background-learner.js`:

```bash
# Background learner runs both:
# 1. Model tuning recompute (every 30s)
# 2. Discovery generation (every 6 hours)

node background-learner.js --daemon
```

## Monitoring

### Discovery Statistics

```bash
node learning/update-discovery-metadata.js --stats
```

Output:
```
============================================================
DISCOVERY STATISTICS
============================================================
Total discoveries:   12
Active:              10
Inactive:            2
Avg confidence:      82.3%
Avg evidence count:  34.2
Avg apply count:     156.8
Avg quality impact:  8.7%

By Type:
  model_preference     5
  model_filter         3
  task_routing         2
  consensus            2

By Source:
  thompson-sampling    6
  execution-log        4
  manual               2
============================================================
```

### Scheduler Status

```bash
node learning/discovery-scheduler.js --status
```

### Logs

```bash
# Discovery scheduler logs
tail -f ~/.claude/learning/logs/discovery-scheduler.log

# Background learner logs
journalctl -u claude-background-learner -f
```

## Environment Variables

```bash
# Enable debug logging
export LEARNING_DEBUG=1

# Custom quality thresholds
export QUALITY_THRESHOLDS='{"security":{"high":0.9,"medium":0.75}}'
```

## File Locations

```
~/.claude/learning/
├── discoveries.json              # Discovery database
├── bandit-state.json             # Thompson Sampling state
├── db/
│   └── learning.db               # Execution logs (SQLite)
└── logs/
    ├── discovery-scheduler.log   # Discovery generation logs
    └── background-learner.log    # Learning system logs
```

## Example Workflow

1. **Initial Bootstrap**
   ```bash
   # Bootstrap Thompson Sampling from execution history
   node learning/bootstrap-thompson.js
   
   # Generate initial discoveries
   node learning/discover-patterns.js --apply
   ```

2. **Start Automated Learning**
   ```bash
   # Start background learner (includes discovery scheduler)
   node background-learner.js --daemon
   ```

3. **Monitor Progress**
   ```bash
   # Check discovery stats
   node learning/update-discovery-metadata.js --stats
   
   # View recent discoveries
   jq '.discoveries | .[] | select(.status == "active")' ~/.claude/learning/discoveries.json
   ```

4. **Manual Intervention**
   ```bash
   # Force discovery generation
   node learning/discover-patterns.js --apply
   
   # Prune low-confidence patterns
   node learning/update-discovery-metadata.js --prune
   
   # Recompute confidence scores
   node learning/update-discovery-metadata.js --recompute
   ```

## Best Practices

1. **Minimum Sample Sizes**
   - Require ≥10 executions before discovering patterns
   - Require ≥0.75 confidence for auto-addition

2. **Confidence Management**
   - Start with conservative confidence (0.70-0.80)
   - Let evidence adjust confidence over time
   - Prune discoveries that drop below 0.60

3. **Monitoring**
   - Review discovery logs weekly
   - Check for inactive discoveries
   - Validate high-impact patterns

4. **Safety**
   - Never auto-add discoveries with confidence < 0.75
   - Always require minimum 10 samples
   - Manual review for patterns with large quality impact

## Troubleshooting

### No patterns discovered

**Cause:** Insufficient execution data

**Solution:**
```bash
# Check execution count
sqlite3 ~/.claude/learning/db/learning.db "SELECT COUNT(*) FROM execution_log"

# Run more executions to build history
```

### All discoveries inactive

**Cause:** Evidence contradicts patterns

**Solution:**
```bash
# Recompute confidence
node learning/update-discovery-metadata.js --recompute

# Generate fresh patterns
node learning/discover-patterns.js --apply --min-conf 0.70
```

### High apply_count, low evidence_count

**Cause:** recordResult() not being called with applied discoveries

**Solution:** Ensure orchestrator.js passes `appliedDiscoveries` to recordResult()

## Performance

- Discovery generation: ~200ms (10K executions)
- Confidence updates: ~50ms (100 discoveries)
- Pattern matching: <5ms per selection
- Storage: ~1KB per discovery

## Future Enhancements

1. **Multi-objective Optimization** - Balance quality, cost, and latency
2. **A/B Testing** - Automatically test new patterns against control
3. **Cross-task Learning** - Transfer patterns between related tasks
4. **Ensemble Discoveries** - Combine multiple patterns intelligently
5. **Temporal Patterns** - Discover time-of-day or workload patterns
6. **User Feedback** - Incorporate explicit user ratings
