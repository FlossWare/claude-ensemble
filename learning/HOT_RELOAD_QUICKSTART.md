# Hot-Reload System Quick Start

## 5-Minute Setup

### 1. Start Background Learner

The background learner keeps Thompson Sampling state and discoveries up-to-date:

```bash
# Start daemon (runs every 30s)
node background-learner.js --daemon

# Or in background
nohup node background-learner.js --daemon > learner.log 2>&1 &
```

### 2. Use Hot-Reload in Your Code

**Before (static imports):**

```javascript
import * as orchestrator from './orchestrator.js';

const model = await orchestrator.selectModel('code-review');
```

**After (hot-reload):**

```javascript
import { hotImport } from './shared/hot-reload.js';

const orchestrator = await hotImport('./orchestrator.js');
const model = await orchestrator.selectModel('code-review');
```

### 3. Apply Discoveries

Add context-aware model selection:

```javascript
import { applyDiscoveries } from './learning/apply-discoveries.js';

const context = {
  task_type: 'security-review',
  cost_sensitivity: 'high',
  requires_schema: false,
};

const config = await applyDiscoveries(['opus', 'sonnet', 'haiku'], context);
console.log('Filtered models:', config.models);
console.log('Biases:', config.biases);
```

### 4. Verify It Works

```bash
# Run tests
node learning/test-hot-reload.js

# Check Thompson Sampling state
node background-learner.js --status

# Enable debug logging
export HOT_RELOAD_DEBUG=1
export LEARNING_DEBUG=1
```

## Common Use Cases

### Use Case 1: Long-Running Workflow

```javascript
import { HotOrchestrator } from './learning/hot-reload-integration.js';

const orch = new HotOrchestrator();

while (true) {
  // Always uses latest Thompson state and discoveries
  const model = await orch.selectModel('task', { strategy: 'thompson' });
  
  await executeTask(model);
  await orch.recordResult(model, qualityScore);
  
  await sleep(60000); // Every minute
}
```

### Use Case 2: Background Daemon

```javascript
import { hotImport } from './shared/hot-reload.js';

async function cycle() {
  // Force reload to pick up code changes
  const workflow = await hotImport('./my-workflow.js', { force: true });
  await workflow.run();
}

setInterval(cycle, 30000); // Every 30s
```

### Use Case 3: Discovery-Driven Selection

```javascript
import { selectModelWithDiscoveries } from './learning/hot-reload-integration.js';

const selection = await selectModelWithDiscoveries('web-research', {
  cost_sensitivity: 'medium',
  quality_threshold: 0.8,
});

console.log('Selected:', selection.models[0]);
console.log('Worker count:', selection.worker_count);
```

## Key Timings

| What | When |
|------|------|
| Code changes picked up | ~1 second |
| Thompson state updates | <5 seconds |
| Discoveries reload | <5 seconds |
| Background learner cycle | 30 seconds (configurable) |

## Discovery Examples

### Example 1: Filter Expensive Models

```json
{
  "conditions": { "cost_sensitivity": "high" },
  "action": {
    "type": "filter_models",
    "params": { "exclude": ["opus"] }
  }
}
```

### Example 2: Bias Creative Tasks

```json
{
  "conditions": { "task_type": "code-generation" },
  "action": {
    "type": "bias_models",
    "params": {
      "bias": { "opus": 1.5, "fable": 1.3, "sonnet": 1.0 }
    }
  }
}
```

### Example 3: Increase Diversity

```json
{
  "conditions": { "task_type": "security-review" },
  "action": {
    "type": "increase_diversity",
    "params": { "diversity_weight": 0.8 }
  }
}
```

## Troubleshooting

### Changes not propagating?

```javascript
import { clearCache } from './shared/hot-reload.js';

// Clear all cache
clearCache();

// Force reload specific module
const fresh = await hotImport('./orchestrator.js', { force: true });
```

### Debug logging

```bash
export HOT_RELOAD_DEBUG=1
export LEARNING_DEBUG=1

node your-script.js
```

### Check state files

```bash
# Thompson Sampling state
cat ~/.claude/learning/bandit-state.json

# Discoveries
cat learning/discoveries.json

# Learning database
sqlite3 ~/.claude/learning/learning.db "SELECT COUNT(*) FROM executions"
```

## Next Steps

1. **Read full docs**: `learning/HOT_RELOAD_SYSTEM.md`
2. **Run tests**: `node learning/test-hot-reload.js`
3. **Add discoveries**: Edit `learning/discoveries.json`
4. **Monitor performance**: Use `getCacheStats()` API
5. **Integrate workflows**: Add hot-reload to your skills

## Pro Tips

1. Use `HotOrchestrator` wrapper class for cleaner code
2. Enable debug logging during development
3. Run background learner with short intervals (10s) for faster iteration
4. Add custom discoveries for your specific use cases
5. Monitor Thompson Sampling stats to verify learning
6. Use force reload in daemon cycles for guaranteed freshness
7. Test discoveries with dry-run mode before activating

## Architecture at a Glance

```
Your Code
    ↓
Hot-Reload Engine (1-5s TTL cache)
    ↓
Orchestrator (Thompson Sampling)
    ↓
Apply Discoveries (filter/bias)
    ↓
Model Selection
    ↓
Execution
    ↓
Record Result → Thompson State → Background Learner → Discoveries
```

## Summary

The hot-reload system gives you:
- ✅ **Zero-downtime updates** - Change code without restarts
- ✅ **Live learning** - Thompson state updates in <5s
- ✅ **Smart routing** - Discoveries auto-apply rules
- ✅ **Background improvement** - Continuous learning

Just replace static imports with `hotImport()` and you're ready to go!
