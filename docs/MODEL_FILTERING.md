# Model Filtering & Task-Specific Rules

**Status:** ✅ Production Ready  
**Created:** 2026-07-08  
**Purpose:** Enforce task-specific model selection rules, including Red Hat compliance requirements

---

## Overview

The model filtering system allows fine-grained control over which models can be used for specific task types. This is critical for:

1. **Compliance** - Red Hat proprietary code MUST use Anthropic models only
2. **Quality** - Security audits require strong reasoning models
3. **Cost optimization** - Documentation doesn't need flagship models

---

## Red Hat Compliance Requirement

**CRITICAL: Red Hat work cannot be reviewed by third-party models!**

Only Anthropic's built-in (paid) models are allowed:
- ✅ `claude-opus` (4.7, 4.8, 5)
- ✅ `claude-sonnet` (4.5, 5)
- ✅ `claude-haiku` (4.5)
- ✅ `claude-fable` (5)

Third-party models are **BLOCKED** for Red Hat tasks:
- ❌ OpenAI (gpt-4o, gpt-4o-mini)
- ❌ Google (gemini-pro, gemini-flash)
- ❌ DeepSeek, Qwen, etc.

---

## Usage

### Automatic (Recommended)

When calling `get-next-arbiter` workflow, pass a task type:

```javascript
// For Red Hat code review (Anthropic-only)
const result = await workflow('get-next-arbiter', { 
  taskType: 'redhat_code_review' 
});
// Returns: { arbiter: 'opus', pool: ['opus', 'sonnet'], filterReason: '...' }

// For general code review (allows coding specialists)
const result = await workflow('get-next-arbiter', { 
  taskType: 'code_review' 
});
// Returns: { arbiter: 'deepseek-coder', pool: ['opus', 'sonnet', 'deepseek-coder', 'qwen-coder'] }
```

### Manual Filtering

```javascript
const { applyRules } = require('./shared/task-model-rules.cjs');

const allModels = ['opus', 'sonnet', 'gpt-4o', 'deepseek-coder'];
const filtered = applyRules(allModels, 'redhat_code_review');
// Returns: ['opus', 'sonnet']  (only Anthropic models)
```

---

## Task Types

### Red Hat Work (Anthropic-only)

| Task Type | Models Allowed | Min Score |
|-----------|---------------|-----------|
| `redhat_code_review` | opus, sonnet | 0.8 |
| `redhat_security_audit` | opus, sonnet | 0.9 |
| `redhat_architecture_review` | opus, sonnet | 0.8 |
| `redhat_bug_detection` | opus, sonnet | 0.8 |

### General Development (Allows specialists)

| Task Type | Models Allowed | Min Score |
|-----------|---------------|-----------|
| `code_review` | opus, sonnet, deepseek-coder, qwen-coder | 0.7 |
| `security_audit` | opus, sonnet, gpt-4o, deepseek-coder | 0.85 |
| `bug_detection` | opus, sonnet, deepseek-coder, qwen-coder, gpt-4o | 0.7 |
| `code_generation` | opus, sonnet, deepseek-coder, qwen-coder | 0.6 |

### Research & Analysis

| Task Type | Blacklist | Min Score |
|-----------|-----------|-----------|
| `research` | haiku, fable, gpt-3.5, gemini-flash | 0.6 |
| `fact_checking` | Only: opus, sonnet, gpt-4o, gemini-pro | 0.7 |
| `data_analysis` | haiku, fable | 0.6 |

### Low-Stakes Work (Cost optimization)

| Task Type | Blacklist | Min Score |
|-----------|-----------|-----------|
| `documentation` | opus (too expensive) | 0.5 |
| `creative_writing` | opus | 0.4 |

---

## Rule Format

Rules are defined in `shared/task-model-rules.cjs`:

```javascript
{
  redhat_code_review: {
    anthropic_only: true,              // ONLY Anthropic models
    whitelist: ['opus', 'sonnet'],     // Pattern matching
    blacklist: ['haiku', 'fable'],     // Never use these
    min_score: 0.8,                    // Minimum capability score
    reason: 'Red Hat proprietary code - Anthropic models only'
  }
}
```

### Filter Priority

1. **anthropic_only** - If true, filter to only Anthropic models first
2. **whitelist** - ONLY models matching these patterns
3. **blacklist** - NEVER models matching these patterns
4. **min_score** - Capability score threshold (applied by capability matrix)

---

## User Configuration

User preferences can override defaults in `~/.claude/config/model-preferences.json`:

```json
{
  "cost_preference": "balanced",
  
  "global_rules": {
    "never_use": ["gpt-3.5-turbo"]
  },
  
  "task_overrides": {
    "code_review": {
      "whitelist": ["opus", "sonnet"],
      "reason": "Personal preference for code review"
    }
  },
  
  "redhat_compliance": {
    "enabled": true,
    "enforce_anthropic_only": true
  }
}
```

**Note:** The config directory `~/.claude/config` is a symlink to `<repo>/config/` so it's version-controlled.

---

## Files

| File | Purpose |
|------|---------|
| `shared/anthropic-models.cjs` | List of official Anthropic models |
| `shared/task-model-rules.cjs` | Task-specific filtering rules |
| `config/model-preferences.json` | User configuration |
| `skills/misc/get-next-arbiter.js` | Applies rules during model selection |
| `tools/test-model-filtering.js` | Test suite |
| `docs/MODEL_FILTERING.md` | This document |

---

## Testing

Run the test suite:

```bash
node tools/test-model-filtering.js
```

Expected output:
```
TEST 1: Red Hat Code Review - PASS ✓
TEST 2: General Code Review - PASS ✓
TEST 3: Documentation - PASS ✓
TEST 4: Anthropic Detection - PASS ✓

OVERALL: ALL TESTS PASS ✓
```

---

## Integration Examples

### Consensus Workflow

```javascript
// workflows/ai-consensus.js
const arbiterResult = await workflow('get-next-arbiter', { 
  taskType: 'redhat_code_review'  // Enforce Anthropic-only
});
const arbiter = arbiterResult.arbiter;  // Will be 'opus' or 'sonnet'
```

### Code Review Skill

```javascript
// skills/code/review.js
export default async function({ args }) {
  const taskType = args.isRedHat ? 'redhat_code_review' : 'code_review';
  const arbiterResult = await workflow('get-next-arbiter', { taskType });
  // ... use arbiterResult.arbiter
}
```

---

## Monitoring

Check which models were selected:

```bash
# View recent arbiter selections
tail -100 ~/.claude/learning/model-usage-stats.json | jq '.recent_selections'

# Check for Red Hat compliance violations
grep "redhat_" ~/.claude/logs/workflows/*.log | grep -v "opus\|sonnet"
```

---

## FAQ

**Q: What happens if all models are filtered out?**  
A: The system falls back to the original unfiltered list (safety mechanism).

**Q: Can I add custom task types?**  
A: Yes! Add them to `shared/task-model-rules.cjs`.

**Q: How do I know if filtering is working?**  
A: Run `node tools/test-model-filtering.js` and check logs in `get-next-arbiter`.

**Q: What if I want to use GPT-4o for personal projects?**  
A: Use `code_review` (general) instead of `redhat_code_review`.

**Q: Can rules change mid-workflow?**  
A: No. Rules are loaded once at workflow start.

---

## Next Steps

1. ✅ Rules defined (15+ task types)
2. ✅ Anthropic-only enforcement working
3. ✅ Tests passing (4/4)
4. ✅ Integrated into `get-next-arbiter`
5. ⏳ TODO: Update 14 consensus workflows to use task-aware routing
6. ⏳ TODO: Monitor model distribution for compliance

**Status: Production ready for Red Hat work! 🎉**
