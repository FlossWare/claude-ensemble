# Integrate AI discoveries into orchestrator model selection

**Labels:** enhancement, orchestrator  
**Priority:** High

## Problem

We have 6 AI-discovered patterns in `learning/discoveries.json` but they're never applied. The `apply_count` is 0.

**Discovered patterns:**
1. Security reviews need diversity
2. Cost-sensitive tasks avoid opus (75% savings)
3. Creative tasks prefer opus/fable
4. Never use fable for structured output
5. Haiku best for simple classification (90% savings)
6. Three-model consensus optimal

## Current State

- ✅ `learning/discoveries.json` exists with 6 patterns
- ✅ `learning/apply-discoveries.js` exists (15K implementation)
- ❌ `orchestrator.js` doesn't import or use discoveries

## Missing Integration

```javascript
// orchestrator.js needs:
import { applyDiscoveries } from './learning/apply-discoveries.js'

export async function selectModel(taskType, options = {}) {
  // Apply discovered patterns BEFORE Thompson Sampling
  const config = await applyDiscoveries(baseModels, { 
    task_type: taskType,
    cost_sensitivity: options.cost_sensitivity,
    requires_schema: options.schema !== undefined,
    ...options 
  })
  
  // Then use filtered/biased models in Thompson
  return selectWithThompson(config.models, config.biases, config.diversity_weight)
}
```

## Benefits

- **75% cost savings** on cost-sensitive tasks (exclude opus)
- **90% cost savings** on simple classification (use haiku)
- **20% quality improvement** on structured output (exclude fable)
- **15% quality improvement** on creative tasks (bias opus/fable)

## Acceptance Criteria

- [ ] Orchestrator imports `apply-discoveries.js`
- [ ] `selectModel()` applies discoveries before Thompson Sampling
- [ ] `selectWorkers()` applies discoveries to worker selection
- [ ] `apply_count` in metadata increases with each call
- [ ] `last_applied` timestamp updates
- [ ] Test: Cost-sensitive task excludes opus
- [ ] Test: Structured output task (schema provided) excludes fable
- [ ] Test: Creative task biases opus/fable higher
- [ ] Documentation updated in orchestrator.js

## Implementation Notes

- Use `hotImport()` for hot-reload support
- Discoveries should filter/bias models BEFORE Thompson Sampling selection
- Update discovery metadata (apply_count, last_applied) after each use
- Add graceful fallback if discoveries unavailable
