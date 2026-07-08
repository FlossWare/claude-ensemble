# Dry-Run Mode for Model Selection

**Status:** ✅ Production Ready  
**Created:** 2026-07-08  
**Purpose:** Preview model selection WITHOUT executing workflows or consuming credits

---

## Overview

Dry-run mode lets you preview **what would happen** before actually doing it:

✅ **What you see:**
- Which models would be selected
- What filters would be applied
- Which models would be excluded (and why)
- What the rotation pool would be
- Red Hat compliance status

❌ **What does NOT happen:**
- No workflows executed
- No API credits consumed
- No database logging
- No actual model calls

**Perfect for:**
- Testing new task types before deployment
- Understanding why a model was/wasn't selected
- Debugging filtering rules
- Red Hat compliance verification

---

## Quick Start

### Preview single task type

```bash
# Preview Red Hat code review
node tools/dry-run-model-selection.cjs redhat_code_review

# Preview general code review
node tools/dry-run-model-selection.cjs code_review

# Preview documentation task
node tools/dry-run-model-selection.cjs documentation
```

### Compare multiple task types

```bash
# Compare Red Hat vs general code review
node tools/dry-run-model-selection.cjs --compare redhat_code_review,code_review

# Compare 4 task types
node tools/dry-run-model-selection.cjs --compare code_review,security_audit,documentation,research
```

### Check specific model availability

```bash
# Can deepseek-coder be used for Red Hat work?
node tools/dry-run-model-selection.cjs --check-model deepseek-coder redhat_code_review
# Output: ✗ NO - Filtered by Anthropic-only requirement

# Can deepseek-coder be used for general code review?
node tools/dry-run-model-selection.cjs --check-model deepseek-coder code_review
# Output: ✓ YES - Available in rotation pool (position #3)
```

---

## Example Output

### Red Hat Code Review (Anthropic-only)

```
========================================
DRY-RUN: MODEL SELECTION PREVIEW
Task Type: redhat_code_review
========================================

TASK RULES:
─────────────────────────────
  Anthropic-only: YES ✓
  Whitelist: opus, sonnet
  Blacklist: haiku, fable
  Min score: 0.8
  Reason: Red Hat proprietary code - Anthropic models only

MODEL COUNTS:
─────────────────────────────
  Total available: 11
  Anthropic models: 4
  Third-party models: 7
  After filtering: 2
  Rotation pool size: 2
  Removed by filters: 9

ANTHROPIC MODELS AVAILABLE:
─────────────────────────────
  claude-opus-4.8                ✓ AVAILABLE
  claude-sonnet-4.5              ✓ AVAILABLE
  claude-haiku-4.5               ✗ FILTERED OUT
  claude-fable-5                 ✗ FILTERED OUT

THIRD-PARTY MODELS AVAILABLE:
─────────────────────────────
  gpt-4o                         ✗ FILTERED OUT
  gpt-4o-mini                    ✗ FILTERED OUT
  deepseek-coder                 ✗ FILTERED OUT
  (all third-party models blocked)

FILTERING DETAILS:
─────────────────────────────
  Removed by Anthropic-only (7):
    - gpt-4o, gpt-4o-mini, gemini-pro, deepseek-coder, etc.
  
  Removed by whitelist (2):
    - claude-haiku-4.5 (not opus/sonnet)
    - claude-fable-5 (not opus/sonnet)

ROTATION POOL (top 6):
─────────────────────────────
  1. claude-opus-4.8           [ANTHROPIC] ← WOULD BE SELECTED NEXT
  2. claude-sonnet-4.5         [ANTHROPIC]

========================================
SUMMARY
========================================
Task: redhat_code_review
Selected model: claude-opus-4.8
Pool size: 2
Compliance: Anthropic-only enforced ✓

This was a DRY-RUN - no workflows executed, no database logging.
```

### General Code Review (Allows specialists)

```
TASK RULES:
─────────────────────────────
  Anthropic-only: NO
  Whitelist: opus, sonnet, deepseek-coder, qwen-coder
  Blacklist: fable, haiku, gpt-3.5

ROTATION POOL (top 6):
─────────────────────────────
  1. claude-opus-4.8           [ANTHROPIC]
  2. claude-sonnet-4.5         [ANTHROPIC]
  3. deepseek-coder            [THIRD-PARTY]
  4. qwen-coder                [THIRD-PARTY]

Compliance: Third-party models allowed
```

---

## Use Cases

### 1. Verify Red Hat Compliance

**Before deploying a new task type for Red Hat work:**

```bash
node tools/dry-run-model-selection.cjs redhat_new_feature_review
```

**Check:**
- ✅ "Anthropic-only: YES ✓"
- ✅ All third-party models filtered out
- ✅ Only opus/sonnet in rotation pool

### 2. Debug Why a Model Wasn't Selected

**"Why wasn't GPT-4o used for my code review?"**

```bash
node tools/dry-run-model-selection.cjs --check-model gpt-4o code_review
```

**Output:**
```
Available: ✗ NO
Reason: Not in whitelist: opus, sonnet, deepseek-coder, qwen-coder
```

### 3. Compare Task Types

**"What's the difference between `code_review` and `redhat_code_review`?"**

```bash
node tools/dry-run-model-selection.cjs --compare code_review,redhat_code_review
```

**Output shows side-by-side:**
- `code_review`: 4 models (opus, sonnet, deepseek, qwen)
- `redhat_code_review`: 2 models (opus, sonnet only)

### 4. Test New Rules Before Deployment

**Created new task type `redhat_security_critical`:**

```javascript
// shared/task-model-rules.cjs
redhat_security_critical: {
  anthropic_only: true,
  whitelist: ['opus'],  // ONLY opus, not even sonnet
  min_score: 0.95,
  reason: 'Critical security - highest accuracy required'
}
```

**Test it:**
```bash
node tools/dry-run-model-selection.cjs redhat_security_critical
```

**Verify:**
- ✅ Only `claude-opus-4.8` in pool
- ✅ Sonnet filtered out (not in whitelist)
- ✅ All third-party filtered (Anthropic-only)

### 5. Cost Optimization

**"Will expensive models be used for documentation?"**

```bash
node tools/dry-run-model-selection.cjs documentation
```

**Check:**
- ✅ Opus NOT in pool (blacklisted)
- ✅ Cheaper models available (sonnet, haiku, fable)

---

## Programmatic Usage

### In JavaScript/Node.js

```javascript
const { previewModelSelection } = require('./shared/model-preview.cjs');

// Preview Red Hat code review
const preview = await previewModelSelection({ 
  taskType: 'redhat_code_review' 
});

console.log('Would select:', preview.result.selected_model);
console.log('Pool:', preview.result.rotation_pool);
console.log('Anthropic-only:', preview.rules.anthropic_only);
console.log('Filtered out:', preview.filtering.removed_count);
```

### Compare task types

```javascript
const { compareTaskTypes } = require('./shared/model-preview.cjs');

const comparison = await compareTaskTypes([
  'redhat_code_review',
  'code_review',
  'security_audit'
]);

for (const [taskType, preview] of Object.entries(comparison)) {
  console.log(`${taskType}: ${preview.result.rotation_pool.join(', ')}`);
}
```

### Check specific model

```javascript
const { checkModelAvailability } = require('./shared/model-preview.cjs');

const check = await checkModelAvailability('deepseek-coder', 'redhat_code_review');

if (!check.available) {
  console.error(`Cannot use ${check.model}: ${check.reason}`);
}
```

---

## Integration with Workflows

### Add dry-run flag to get-next-arbiter

```javascript
// workflows/my-consensus.js
export default async function({ args }) {
  // Preview before executing
  if (args.dryRun) {
    const { previewModelSelection } = require('../shared/model-preview.cjs');
    const preview = await previewModelSelection({ 
      taskType: args.taskType 
    });
    return { 
      preview,
      message: 'DRY-RUN: No workflows executed'
    };
  }
  
  // Real execution
  const arbiter = await workflow('get-next-arbiter', { 
    taskType: args.taskType 
  });
  // ... continue workflow
}
```

---

## Files

| File | Purpose |
|------|---------|
| `shared/model-preview.cjs` | Core dry-run logic |
| `tools/dry-run-model-selection.cjs` | CLI interface |
| `docs/DRY_RUN_MODE.md` | This document |

---

## API Reference

### `previewModelSelection(options)`

Preview model selection for a task type.

**Parameters:**
- `options.taskType` (string) - Task type to preview
- `options.allModels` (Array<string>) - Override available models
- `options.poolSize` (number) - Rotation pool size (default: 6)

**Returns:**
```javascript
{
  taskType: 'redhat_code_review',
  rules: {
    anthropic_only: true,
    whitelist: ['opus', 'sonnet'],
    blacklist: ['haiku', 'fable'],
    min_score: 0.8,
    reason: 'Red Hat proprietary code...'
  },
  models: {
    total_available: 11,
    anthropic_count: 4,
    third_party_count: 7,
    after_filtering: 2,
    rotation_pool_size: 2
  },
  categorized: {
    anthropic: ['claude-opus-4.8', ...],
    third_party: ['gpt-4o', ...]
  },
  filtering: {
    removed_count: 9,
    by_anthropic_only: ['gpt-4o', ...],
    by_whitelist: ['claude-haiku-4.5', ...],
    by_blacklist: []
  },
  result: {
    rotation_pool: ['claude-opus-4.8', 'claude-sonnet-4.5'],
    selected_model: 'claude-opus-4.8',
    all_filtered_models: [...]
  }
}
```

### `compareTaskTypes(taskTypes)`

Compare multiple task types side-by-side.

**Parameters:**
- `taskTypes` (Array<string>) - Task types to compare

**Returns:**
```javascript
{
  'redhat_code_review': { /* preview */ },
  'code_review': { /* preview */ },
  ...
}
```

### `checkModelAvailability(model, taskType)`

Check if specific model is available for a task.

**Parameters:**
- `model` (string) - Model to check
- `taskType` (string) - Task type

**Returns:**
```javascript
{
  model: 'deepseek-coder',
  taskType: 'redhat_code_review',
  available: false,
  in_rotation_pool: false,
  reason: 'Filtered by Anthropic-only requirement',
  pool_position: null
}
```

---

## Common Questions

**Q: Does dry-run show the EXACT model that would be selected?**  
A: Almost. It shows which model would be first in the rotation pool. The actual selection depends on arbiter state (last_arbiter), which changes over time.

**Q: Can I test with custom model lists?**  
A: Yes! Pass `allModels: ['model1', 'model2']` to `previewModelSelection()`.

**Q: Does this work for all task types?**  
A: Yes! Including custom task types you add to `task-model-rules.cjs`.

**Q: What if no models pass filters?**  
A: You'll see "NO MODELS AVAILABLE" - this is a configuration error, fix your rules!

**Q: Can I use this in CI/CD tests?**  
A: Absolutely! Great for testing compliance before deployment:
```bash
# Test Red Hat compliance
node tools/dry-run-model-selection.cjs redhat_code_review | grep "Anthropic-only: YES" || exit 1
```

---

## Next Steps

1. ✅ Dry-run implemented
2. ✅ CLI tool created
3. ✅ Comparison mode working
4. ✅ Model availability checker working
5. ⏳ TODO: Add to pre-commit hooks (verify Red Hat compliance)
6. ⏳ TODO: Add to CI/CD (test all task types)
7. ⏳ TODO: Create web UI for visual preview

**Status: Production ready! Test before you execute! 🎉**
