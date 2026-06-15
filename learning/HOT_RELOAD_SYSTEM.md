# Hot-Reload System Documentation

## Overview

The hot-reload system enables **zero-downtime updates** to code, learning state, and AI discoveries. Changes to workflows, orchestrator logic, Thompson Sampling state, and discovered patterns propagate to running processes in **under 5 seconds** without requiring restarts.

## Components

### 1. Core Hot-Reload (`shared/hot-reload.js`)

Dynamic import system with cache busting and TTL-based caching.

**Key Features:**
- Cache-busted imports using query parameters
- TTL-based caching (1s for code, 5s for data)
- Automatic retry on import failures
- Support for both ES modules and JSON data
- Cache statistics and cleanup

**API:**

```javascript
import { hotImport, hotImportJSON, clearCache } from './shared/hot-reload.js';

// Hot-reload code module
const orchestrator = await hotImport('./orchestrator.js');
const model = await orchestrator.selectModel('code-review');

// Hot-reload JSON data
const discoveries = await hotImportJSON('./learning/discoveries.json');

// Force reload (bypass cache)
const fresh = await hotImport('./orchestrator.js', { force: true });

// Clear cache
clearCache(); // Clear all
clearCache('./orchestrator.js'); // Clear specific module
```

### 2. Thompson Sampling Integration

Thompson Sampling state reloads every **5 seconds** (reduced from 60s).

**State Propagation:**
1. Background learner updates `~/.claude/learning/bandit-state.json`
2. Thompson Sampling module reloads state every 5s
3. Orchestrator uses hot-import to get latest module
4. Model selection reflects new learnings within 5s

**Example:**

```javascript
import { hotImport } from './shared/hot-reload.js';

// Get latest Thompson Sampling state
const orchestrator = await hotImport('./orchestrator.js');
const model = await orchestrator.selectModel('task', { strategy: 'thompson' });

// Record result (updates state immediately)
await orchestrator.recordResult(model, 0.95);

// Within 5s, next selection will reflect updated state
```

### 3. Discoveries System (`learning/discoveries.json`)

AI-discovered patterns stored as JSON rules that apply to model selection.

**Discovery Types:**

1. **Model Filtering**: Exclude models based on context
2. **Selection Biasing**: Adjust model probabilities
3. **Diversity Control**: Increase/decrease ensemble diversity
4. **Task Routing**: Prefer specific models for task types
5. **Performance Optimization**: Route based on cost/quality tradeoffs

**Example Discovery:**

```json
{
  "id": "discovery_002",
  "type": "model_filter",
  "pattern": "cost-sensitive-avoid-opus",
  "description": "Cost-sensitive tasks should prefer sonnet/haiku over opus",
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
  },
  "confidence": 0.90,
  "quality_impact": -0.05,
  "cost_savings": 0.75
}
```

### 4. Discovery Application (`learning/apply-discoveries.js`)

Interprets and applies discovery rules to model selection.

**API:**

```javascript
import { applyDiscoveries, filterModels, biasSelection } from './apply-discoveries.js';

// Apply all discoveries
const context = {
  task_type: 'security-review',
  cost_sensitivity: 'high',
  requires_schema: false,
};

const config = await applyDiscoveries(['opus', 'sonnet', 'haiku', 'fable'], context);
// => {
//   models: ['sonnet', 'haiku'],  // opus filtered (cost), fable ok
//   biases: { sonnet: 1.5, haiku: 1.0 },
//   diversity_weight: 0.8,
//   worker_count: 3
// }

// Or use individual functions
const filtered = await filterModels(models, context);
const biases = await biasSelection(models, context);
```

## Integration Patterns

### Pattern 1: Workflow Integration

```javascript
import { hotImport } from './shared/hot-reload.js';
import { applyDiscoveries } from './learning/apply-discoveries.js';

async function runConsensus(taskType) {
  // Hot-reload orchestrator
  const orchestrator = await hotImport('./orchestrator.js');
  
  // Select models with latest Thompson state
  const workers = await orchestrator.selectWorkers(taskType, {
    strategy: 'thompson',
    count: 3,
  });
  
  // Apply discoveries
  const context = { task_type: taskType, workflow: 'consensus' };
  const config = await applyDiscoveries(workers, context);
  
  // Execute with filtered/biased models
  return executeConsensus(config.models, config);
}
```

### Pattern 2: Background Daemon

```javascript
import { hotImport } from './shared/hot-reload.js';

async function daemonCycle() {
  // Force reload on each cycle
  const logger = await hotImport('./shared/learning-logger.js', { force: true });
  const orchestrator = await hotImport('./orchestrator.js', { force: true });
  
  // Process with latest code
  const stats = await orchestrator.getThompsonStats();
  console.log('Thompson stats:', stats);
}

setInterval(daemonCycle, 30000); // Every 30s
```

### Pattern 3: Discovery-Driven Selection

```javascript
import { selectModelWithDiscoveries } from './learning/hot-reload-integration.js';

const selection = await selectModelWithDiscoveries('code-review', {
  requires_schema: true,
  cost_sensitivity: 'medium',
});

console.log('Selected:', selection.models[0]);
console.log('Biases:', selection.biases);
```

### Pattern 4: Feedback Loop

```javascript
import { recordExecutionResult } from './learning/hot-reload-integration.js';

// After execution
const result = await recordExecutionResult('opus', 0.92, {
  task_type: 'security-review',
});

console.log('Thompson state updated:', result.thompson_state);
console.log('Active discoveries:', result.active_discoveries);
```

## Performance Characteristics

### Cache TTLs

- **Code modules**: 1 second (fast updates for workflow changes)
- **JSON data**: 5 seconds (balance between freshness and load)
- **Thompson state**: 5 seconds (internal reload interval)

### Propagation Times

| Update Type | Propagation Time | Mechanism |
|-------------|------------------|-----------|
| Code changes | ~1s | Hot-import cache TTL |
| Thompson state | <5s | State file reload interval |
| Discoveries | <5s | JSON hot-reload TTL |
| Learning DB | Real-time | Direct DB queries |

### Performance Impact

- **Cold import**: <1s (initial module load)
- **Cached import**: <50ms (cache hit)
- **Force reload**: <1s (cache-busted import)
- **JSON load**: <10ms (file read + parse)

## Configuration

### Environment Variables

```bash
# Enable debug logging
export HOT_RELOAD_DEBUG=1
export LEARNING_DEBUG=1

# Custom quality thresholds
export QUALITY_THRESHOLDS='{"security":{"high":0.9,"medium":0.75}}'
```

### Discovery Confidence Threshold

```javascript
import { loadDiscoveries } from './learning/apply-discoveries.js';

// Only apply discoveries with confidence >= 0.8
const discoveries = await loadDiscoveries({ minConfidence: 0.8 });
```

## Testing

Run the comprehensive test suite:

```bash
# All tests
node learning/test-hot-reload.js

# Specific test
node learning/test-hot-reload.js --test=thompson

# Verbose output
node learning/test-hot-reload.js --verbose
```

**Test Coverage:**
1. Code module hot-reload (cache busting)
2. JSON data hot-reload (discoveries, learnings)
3. Thompson Sampling state propagation (<5s)
4. Discovery application and filtering
5. Orchestrator integration
6. Cache management
7. Performance benchmarks

## Creating New Discoveries

Discoveries can be added manually or generated by learning systems:

```javascript
import { writeFileSync, readFileSync } from 'fs';

// Load current discoveries
const data = JSON.parse(readFileSync('./learning/discoveries.json', 'utf-8'));

// Add new discovery
data.discoveries.push({
  id: `discovery_${Date.now()}`,
  type: 'model_preference',
  pattern: 'my-new-pattern',
  description: 'My discovered pattern',
  conditions: {
    task_type: 'my-task',
  },
  action: {
    type: 'bias_models',
    params: {
      bias: { opus: 1.5, sonnet: 1.0 }
    }
  },
  confidence: 0.85,
  evidence_count: 10,
  quality_impact: 0.10,
  discovered_at: new Date().toISOString(),
  status: 'active'
});

// Update metadata
data.metadata.total_discoveries = data.discoveries.length;
data.metadata.active_discoveries = data.discoveries.filter(d => d.status === 'active').length;
data.updated = new Date().toISOString();

// Save
writeFileSync('./learning/discoveries.json', JSON.stringify(data, null, 2));

// Discovery will be live within 5s
```

## Troubleshooting

### Issue: Changes not propagating

**Solution:**
```javascript
// Force cache clear
import { clearCache } from './shared/hot-reload.js';
clearCache();

// Force reload specific module
const fresh = await hotImport('./orchestrator.js', { force: true });
```

### Issue: Discovery not applying

**Check:**
1. Discovery status is `active`
2. Discovery confidence >= threshold (default 0.7)
3. Conditions match execution context
4. Action type is supported

**Debug:**
```bash
export LEARNING_DEBUG=1
export HOT_RELOAD_DEBUG=1
```

### Issue: Thompson state not updating

**Verify:**
1. Background learner is running (`node background-learner.js --status`)
2. State file exists (`~/.claude/learning/bandit-state.json`)
3. State file updated timestamp is recent
4. Orchestrator cache cleared after state update

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Hot-Reload System                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐│
│  │   Workflows  │────▶│ Hot-Reload   │────▶│ Orchestrator││
│  │              │     │   Engine     │     │             ││
│  └──────────────┘     └──────────────┘     └─────────────┘│
│         │                     │                     │       │
│         │                     ▼                     ▼       │
│         │             ┌──────────────┐     ┌─────────────┐│
│         │             │ Cache Layer  │     │  Thompson   ││
│         │             │  (1s-5s TTL) │     │  Sampling   ││
│         │             └──────────────┘     └─────────────┘│
│         │                     │                     │       │
│         ▼                     ▼                     ▼       │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐│
│  │ Discoveries  │◀────│Apply Engine  │◀────│ State File  ││
│  │   (JSON)     │     │              │     │   (5s TTL)  ││
│  └──────────────┘     └──────────────┘     └─────────────┘│
│         │                                           │       │
│         └───────────────────┬───────────────────────┘       │
│                             ▼                               │
│                   ┌──────────────────┐                     │
│                   │ Background       │                     │
│                   │ Learner (30s)    │                     │
│                   └──────────────────┘                     │
│                             │                               │
│                             ▼                               │
│                   ┌──────────────────┐                     │
│                   │  Learning DB     │                     │
│                   │  (SQLite + WAL)  │                     │
│                   └──────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## Best Practices

1. **Use hot-imports in long-running processes**: Daemons, background jobs, continuous workflows
2. **Force reload in daemon cycles**: Ensure fresh code on each iteration
3. **Apply discoveries before execution**: Filter/bias models based on context
4. **Record results after execution**: Update Thompson Sampling state
5. **Monitor cache stats**: Use `getCacheStats()` to track cache health
6. **Set appropriate TTLs**: Balance freshness vs. performance
7. **Test discovery changes**: Validate new discoveries before activating
8. **Use debug logging**: Enable `LEARNING_DEBUG` for troubleshooting

## Future Enhancements

1. **Auto-discovery generation**: ML-based pattern extraction from execution logs
2. **Discovery A/B testing**: Test new discoveries on subset of tasks
3. **Confidence calibration**: Adjust discovery confidence based on outcomes
4. **Discovery versioning**: Track discovery evolution over time
5. **Hot-reload webhooks**: Trigger reloads via API/webhook
6. **Distributed cache**: Share cache across multiple processes
7. **Discovery conflicts**: Detect and resolve conflicting discoveries
8. **Performance profiling**: Track hot-reload overhead per workflow

## Summary

The hot-reload system enables **live updates** to:
- ✅ Code changes (workflows, orchestrator)
- ✅ Thompson Sampling state (<5s propagation)
- ✅ AI discoveries (pattern-based model selection)
- ✅ Background learning (continuous improvement)

All without requiring process restarts or manual intervention.
