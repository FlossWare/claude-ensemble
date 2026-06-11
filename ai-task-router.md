# AI Task Router - Dynamic Task Routing

Intelligently routes tasks to the optimal AI worker models based on task complexity, model specialization, and cost budget constraints.

## Features

- **Automatic Task Classification** - Detects task category (security, architecture, code-review, etc.) and complexity (simple/moderate/complex/critical) from keywords and context signals
- **Cost-Aware Routing** - Respects budget constraints; routes simple tasks to Haiku (cheap/fast), complex tasks to Opus (expensive/thorough)
- **Specialization Matching** - Each model has defined strengths; the router scores candidates by specialization fit
- **Performance History Integration** - Wraps SmartModelSelector from shared/model-performance.js to incorporate historical performance data when available
- **External Config Override** - Reads model-config.json for custom cost/specialization overrides
- **Preference Modes** - Optimize for quality, speed, or cost

## Usage

```bash
# Simple usage - let the router decide
/ai-task-router Review this code for security vulnerabilities
```

```javascript
// With budget constraint
workflow('ai-task-router', {
  task: 'Audit this authentication module for exploits',
  context: '<code here>',
  budget: 0.50
})

// Optimize for speed
workflow('ai-task-router', {
  task: 'Format these 10 files',
  prefer: 'speed'
})

// Force specific models
workflow('ai-task-router', {
  task: 'Analyze distributed system design',
  force_models: ['opus'],
  exclude_models: ['gemini'],
  count: 2
})
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| task | string | (required) | The task description |
| context | string | '' | Additional context (code, docs, etc.) |
| budget | number | unlimited | Max cost budget in relative units |
| count | number | 3 | Number of workers to select |
| prefer | string | 'quality' | 'quality', 'speed', or 'cost' |
| force_models | string[] | [] | Models to always include |
| exclude_models | string[] | [] | Models to never include |

## How It Works

### Phase 1: Classify

The task text and context are analyzed to determine:

- **Category** - Matched by keywords against 13 built-in categories (security, architecture, code-review, refactoring, testing, documentation, formatting, classification, extraction, summarization, logic, synthesis, general)
- **Complexity** - Determined by category defaults, then adjusted by complexity signals:
  - Complex signals: "critical", "production", "exploit", "race condition", "distributed", "at scale"
  - Simple signals: "trivial", "quick", "basic", "format", "rename", "typo"
  - Context length over 10K chars bumps simple to moderate; over 50K bumps to complex

### Phase 2: Load Config

- Reads built-in model cost/specialization data (Opus, Sonnet, Haiku, Gemini)
- Loads model-config.json overrides if present
- Loads historical performance data from memory/model-performance.json via SmartModelSelector wrapper

### Phase 3: Route

Each candidate model is scored on a 0-150+ point scale:

| Factor | Points | Description |
|--------|--------|-------------|
| Specialization match | 0-40 | Model specializations include the detected task category |
| Complexity fit | 0-30 | Model complexity_fit includes the detected complexity tier |
| Quality | 0-20 | Base quality score of the model |
| Preference bonus | -10 to +25 | Adjusted by speed/cost/quality preference mode |
| Performance history | 0-20 | Historical score from SmartModelSelector (if available) |

Models are sorted by score, then selected top-down within budget. If budget is too tight, cheaper models are backfilled.

## Routing Examples

### Simple task (formatting, extraction)

```
Task: "Format these files with prettier"
Complexity: simple
Result: [haiku, gemini, sonnet]
Reason: Simple formatting task - prioritized fast/cheap models
```

### Complex task (security, architecture)

```
Task: "Audit this auth system for security vulnerabilities in production"
Complexity: critical
Result: [opus, sonnet, haiku]
Reason: Critical security task - prioritized flagship models (Opus)
```

### Budget-constrained

```
Task: "Review this code for bugs"
Budget: 0.25
Result: [sonnet, haiku, gemini]  (Opus excluded - too expensive for budget)
```

### Speed-optimized

```
Task: "Classify these 50 issues by severity"
Prefer: speed
Result: [haiku, gemini, sonnet]  (fast models prioritized)
```

## Model Profiles

| Model | Tier | Cost | Speed | Specializations |
|-------|------|------|-------|-----------------|
| Opus | flagship | 1.00 | slow | security, architecture, logic, synthesis, complex-reasoning, code-review |
| Sonnet | mid | 0.20 | medium | code-review, refactoring, documentation, testing, general |
| Haiku | fast | 0.04 | fast | formatting, classification, extraction, simple-qa, summarization |
| Gemini | mid | 0.05 | fast | general, summarization, extraction, multimodal |

## Output Format

```json
{
  "workers": ["opus", "sonnet", "haiku"],
  "routing_reason": "Complex security task - selected high-quality models",
  "estimated_cost": 1.24,
  "complexity": "complex",
  "category": "security",
  "budget_remaining": 0.76,
  "classification": {
    "category": "security",
    "complexity": "complex",
    "keyword_hits": 3,
    "complex_signals": 2,
    "simple_signals": 0,
    "context_length": 4500
  },
  "model_scores": [
    { "model": "opus", "score": 105.0, "cost": 1.0 },
    { "model": "sonnet", "score": 67.0, "cost": 0.2 },
    { "model": "haiku", "score": 43.0, "cost": 0.04 }
  ]
}
```

## Customization

### model-config.json

Place a model-config.json in the skills directory to override model definitions:

```json
{
  "models": {
    "opus": {
      "relative_cost": 1.2,
      "specializations": ["security", "architecture", "logic", "synthesis"]
    },
    "my-custom-model": {
      "provider": "custom",
      "tier": "mid",
      "relative_cost": 0.15,
      "specializations": ["code-review", "testing"],
      "complexity_fit": ["moderate", "complex"],
      "speed": "medium",
      "quality": 0.80
    }
  }
}
```

### Integration with Other Workflows

The router is designed to be called by other workflows that need to decide which models to use:

```javascript
// In another workflow:
const routing = await workflow('ai-task-router', {
  task: myTask,
  context: myContext,
  budget: 0.50,
  prefer: 'quality'
})

// Use the selected workers
const workers = routing.workers  // e.g., ['opus', 'sonnet', 'haiku']
```

## Files

- ~/.claude/repos/claude-global-skills/ai-task-router.js - Main workflow
- ~/.claude/repos/claude-global-skills/ai-task-router.md - This documentation
- ~/.claude/repos/claude-global-skills/shared/model-performance.js - SmartModelSelector (wrapped by router)
- ~/.claude/repos/claude-global-skills/model-config.json - Optional cost/specialization overrides
- ~/.claude/repos/claude-global-skills/memory/model-performance.json - Historical performance data

## Complexity Tiers

| Tier | Budget Multiplier | Preferred Models | Min Quality |
|------|-------------------|------------------|-------------|
| simple | 0.1x | fast (Haiku) | 0.50 |
| moderate | 0.4x | mid (Sonnet) | 0.70 |
| complex | 0.8x | flagship (Opus) | 0.85 |
| critical | 1.0x | flagship (Opus) | 0.95 |

---

**Version**: 1.0
**Created**: 2026-06-10
**Dependencies**: shared/model-performance.js (SmartModelSelector)
