# Fleet Dispatcher Migration - Quick Reference

## One-Page Summary

**Goal:** Convert 158 agent() calls to use fleet dispatcher when `USE_FLEET_DISPATCHER=true`

**Key files:**
- `fleet-agent-dispatcher.js` - Main wrapper and helpers
- `MIGRATION_EXAMPLES.md` - Before/after code samples
- `IMPLEMENTATION_GUIDE.md` - Detailed process

---

## Pattern 1: Simple (most common)

```javascript
// BEFORE:
const result = await agent('prompt');

// AFTER:
const result = USE_FLEET_DISPATCHER
  ? await dispatchViaFleet('sonnet', 'prompt', {})
  : await agent('prompt');
```

---

## Pattern 2: With model

```javascript
// BEFORE:
const result = await agent('prompt', {model: 'opus'});

// AFTER:
const result = USE_FLEET_DISPATCHER
  ? await dispatchViaFleet('opus', 'prompt', {})
  : await agent('prompt', {model: 'opus'});
```

---

## Pattern 3: With schema

```javascript
// BEFORE:
const result = await agent('prompt', {model: 'haiku', schema: SCHEMA});

// AFTER:
const result = USE_FLEET_DISPATCHER
  ? await dispatchViaFleet('haiku', 'prompt', {schema: SCHEMA})
  : await agent('prompt', {model: 'haiku', schema: SCHEMA});
```

---

## Pattern 4: Parallel workers

```javascript
// BEFORE:
await parallel(models.map(m => () =>
  agent(prompt, {model: m, schema: SCHEMA})
))

// AFTER:
await parallel(models.map(m => () =>
  USE_FLEET_DISPATCHER
    ? dispatchViaFleet(m, prompt, {schema: SCHEMA})
    : agent(prompt, {model: m, schema: SCHEMA})
))
```

---

## Pattern 5: Pipeline transforms

```javascript
// BEFORE:
await pipeline(items, item =>
  agent(`Process ${item}`, {model: 'opus', label: `Item ${item}`})
)

// AFTER:
await pipeline(items, item =>
  USE_FLEET_DISPATCHER
    ? dispatchViaFleet('opus', `Process ${item}`, {label: `Item ${item}`})
    : agent(`Process ${item}`, {model: 'opus', label: `Item ${item}`})
)
```

---

## Key Rules

1. **Extract model first:** `opts.model || 'sonnet'`
2. **Pass model as 1st param:** `dispatchViaFleet(model, prompt, ...)`
3. **Keep opts intact:** `{schema, label, phase, ...}`
4. **Always include fallback:** `USE_FLEET_DISPATCHER ? ... : direct agent()`
5. **Don't change logic:** Only wrapping agent() calls

---

## Testing Workflow

```bash
# Syntax check
node -c workflow.js

# Baseline (direct agent)
FLEET_DISPATCHER=false npm test workflow > baseline.json

# Fleet test
FLEET_DISPATCHER=true npm test workflow > fleet.json

# Compare (should be identical)
diff baseline.json fleet.json

# If identical: ✅ migration successful
# If different: ❌ recheck conversion
```

---

## Job Type Detection

Automatically detected from label and prompt:

| Keyword | Detected as |
|---------|------------|
| worker, consensus | ai-consensus |
| review, code, quality, bug | code-review |
| test, build, execute, run | code-execute |
| extract, fetch, parse, detect | data-extraction |
| synthesis, summary, generate | ai-heavy |
| (default) | agent |

---

## Resource Estimation Formula

```
duration = 25s + promptLengthAdj + modelAdj + schemaAdj + jobTypeAdj
ram = 1.0GB + modelAdj + schemaAdj + jobTypeAdj
```

Examples:
- Short prompt (100 chars): 25 + 10 = 35s
- Medium prompt (1500 chars): 25 + 20 = 45s
- opus model: +15s, +0.5GB
- haiku model: -10s, -0.3GB
- 10-property schema: +10s, +0.3GB
- code-execute job: +20s, +0.5GB

---

## Migration Order (Recommended)

**Phase 1 (Easy, 4-6h):**
- ai-web-learn.js (7 calls)
- memory-rag-search.js (7 calls)

**Phase 2 (Medium, 6-8h):**
- code-review.js (8 calls)
- code-security.js (9 calls)

**Phase 3 (Hard, 8-10h):**
- ai-consensus-weighted.js
- ai-consensus-filtered.js

**Phase 4 (Complex, 5-7h):**
- code-review-auto.js (13 calls)
- code-solve-auto.js (17 calls)

---

## Checklist per Workflow

- [ ] Analyze: `analyzeWorkflow(code)`
- [ ] Convert: All agent() calls using pattern 1-5
- [ ] Syntax: `node -c workflow.js`
- [ ] Test baseline: `FLEET_DISPATCHER=false npm test workflow`
- [ ] Test fleet: `FLEET_DISPATCHER=true npm test workflow`
- [ ] Compare: `diff baseline.json fleet.json`
- [ ] Commit: `git commit -m "chore: migrate workflow to fleet"`
- [ ] Review: Check job completion logs

---

## Debugging

**Problem:** `analyzeWorkflow()` returns 0 calls
- Check: Are agent() calls lowercase? (case-sensitive regex)
- Check: Are calls using backticks or quotes?

**Problem:** Conversion produces syntax error
- Check: Matching braces in opts object
- Check: Proper USE_FLEET_DISPATCHER check syntax
- Check: Model extraction is valid JavaScript

**Problem:** Test outputs differ
- Check: dispatchViaFleet() receives correct model
- Check: Schema passed through completely
- Check: No additional logic added

**Problem:** Job tracking logs missing
- Check: FLEET_DISPATCHER=true is set
- Check: Dispatcher is running on pi-02:3004
- Check: Check system logs for dispatcher errors

---

## Fallback Behavior

If dispatcher unavailable:
```javascript
// Automatically logs warning and falls back to direct agent()
⚠️  Fleet dispatcher unavailable, falling back to direct agent()

// Caller sees same result as if direct agent() was called
// No user-visible error
```

---

## Performance Baseline

| Workflow | Before (ms) | After (ms) | Gain |
|----------|-----------|-----------|------|
| ai-web-learn | ~2000 | ~1500 | ~25% |
| code-review | ~3000 | ~2000 | ~33% |
| consensus | ~5000 | ~2500 | ~50% |

*Note: Actual numbers depend on system load and network latency*

---

## Rollback Commands

If issues found:
```bash
# Disable feature globally (all workflows use direct agent)
export FLEET_DISPATCHER=false

# Or revert one workflow
git revert <migration-commit>

# Or disable in environment
unset FLEET_DISPATCHER
# (defaults to true, must explicitly set 'false')
```

---

## Helper Functions

### analyzeWorkflow(code)
Returns: `{totalCalls, usesParallel, usesPipeline, schemaUsage, modelOverride, ...}`

### detectJobType(label, prompt)
Returns: `'ai-consensus' | 'code-review' | 'code-execute' | 'data-extraction' | 'ai-heavy' | 'agent'`

### estimateResources(prompt, model, schema, jobType)
Returns: `{duration: seconds, ram: GB}`

---

## Key Environment Variables

```bash
# Enable fleet dispatcher (default if not set)
export FLEET_DISPATCHER=true

# Disable fleet dispatcher (use direct agent)
export FLEET_DISPATCHER=false

# Dispatcher URL (usually pi-02:3004)
export FLEET_DISPATCHER_URL=http://pi-02:3004
```

---

## Expected Log Output

When `FLEET_DISPATCHER=true`:
```
📤 Dispatching ai-consensus job to fleet (opus, ~35s, 1.3GB)
✅ Dispatched to server-03 (jobId: abc123...)
✅ Job complete (33.5s)

📤 Dispatching code-review job to fleet (sonnet, ~45s, 1.0GB)
✅ Dispatched to server-01 (jobId: def456...)
✅ Job complete (42.1s)
```

When fallback happens:
```
⚠️  Fleet dispatcher unavailable, falling back to direct agent()
```

---

## Quick Stats

**Total migration scope:**
- 158 agent() calls
- 14 workflows
- 7 call patterns
- 5 job types

**Estimated effort:**
- 30-40 hours total
- 1 week full-time
- 3-4 weeks part-time

**Testing:**
- 25 unit tests (fleet-agent-dispatcher.test.js)
- Baseline vs fleet comparison per workflow
- Full regression test suite

---

## Further Reading

1. **MIGRATION_EXAMPLES.md** - Detailed before/after examples
2. **IMPLEMENTATION_GUIDE.md** - Step-by-step process
3. **fleet-utils.js** - Dispatcher API details
4. **fleet-agent-dispatcher.js** - Source code and docstrings

---

## When Stuck

1. Check pattern match in MIGRATION_EXAMPLES.md
2. Run `analyzeWorkflow()` on current file
3. Look at error logs: `grep "❌\|⚠️" output.log`
4. Test with `FLEET_DISPATCHER=false` first
5. Compare baseline vs fleet JSON outputs

---

**Remember:** All changes are backwards compatible with `USE_FLEET_DISPATCHER=false`
