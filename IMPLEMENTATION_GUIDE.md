# Fleet Dispatcher Migration - Implementation Guide

## Quick Start

### What You Need

1. **fleet-utils.js** ✅ (already in place)
   - Provides `dispatchAgent()`, `completeAgent()`, `remoteAgent()`

2. **fleet-agent-dispatcher.js** ✅ (created)
   - Main wrapper: `dispatchViaFleet(model, prompt, opts)`
   - Helpers: `detectJobType()`, `estimateResources()`, `analyzeWorkflow()`

3. **Workflow files** (14 files)
   - Each has `import fleetUtils from './fleet-utils.js'` ✅
   - Each has `const USE_FLEET_DISPATCHER = process.env.FLEET_DISPATCHER !== 'false'` ✅
   - Now need agent() call conversions

### Testing Infrastructure

1. **fleet-agent-dispatcher.test.js** ✅ (created)
   - 25 unit tests covering all core functions
   - Run: `node fleet-agent-dispatcher.test.js`

2. **Per-workflow tests**
   - Need to add: `FLEET_DISPATCHER=false` vs `FLEET_DISPATCHER=true` comparison

---

## Implementation Phases

### Phase 1: Setup & Validation (Week 1)

**Deliverables:**
- [ ] Run test suite: `node fleet-agent-dispatcher.test.js`
- [ ] Verify all tests pass (should be 25/25)
- [ ] Create test fixtures for Phase 2 workflows
- [ ] Document any issues

**Estimated time:** 4 hours

**Commands:**
```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Run all tests
node fleet-agent-dispatcher.test.js

# Should output:
# ============================================================
# Tests passed: 25
# Tests failed: 0
# Total tests: 25
# ============================================================
```

---

### Phase 2: Simple Workflows (Week 2)

**Target workflows:** 14 calls total
- `ai-web-learn.js` (7 calls)
- `memory-rag-search.js` (7 calls)

**Reasons to start here:**
- Fewest agent() calls in codebase
- Simplest patterns (mostly model/schema, no parallel/pipeline)
- Fast iteration cycle
- Quick validation of approach

**Process per workflow:**

1. **Analyze:**
   ```javascript
   // In Node REPL:
   import fs from 'fs';
   import { analyzeWorkflow } from './fleet-agent-dispatcher.js';
   
   const code = fs.readFileSync('ai-web-learn.js', 'utf8');
   const analysis = analyzeWorkflow(code);
   console.log(analysis);
   // Output: {
   //   totalCalls: 7,
   //   usesParallel: false,
   //   usesPipeline: false,
   //   schemaUsage: 5,
   //   modelOverride: 3,
   //   ...
   // }
   ```

2. **Migrate:**
   - Convert each agent() call using Pattern 1-3 from MIGRATION_EXAMPLES.md
   - Keep changes minimal and surgical
   - Run syntax check after each change

3. **Test:**
   ```bash
   # Baseline
   FLEET_DISPATCHER=false node workflow-runner.js ai-web-learn
   
   # With fleet
   FLEET_DISPATCHER=true node workflow-runner.js ai-web-learn
   
   # Should produce identical output
   ```

4. **Review:**
   - Check for regressions
   - Verify job tracking logs
   - Validate resource estimation is reasonable

5. **Commit:**
   ```bash
   git commit -m "chore: migrate ai-web-learn.js to fleet dispatcher

   - Converted 7 agent() calls
   - Automatic job type detection
   - Resource estimation based on prompt length and schema
   - Backwards compatible: USE_FLEET_DISPATCHER=false uses direct agent()

   Test: FLEET_DISPATCHER=true npm test
   ```

**Estimated time per workflow:** 2-3 hours
**Total Phase 2:** 4-6 hours

**Files to modify:**
```
ai-web-learn.js
├── Change 1: agent(prompt) → wrapper
├── Change 2: agent(prompt, {model, schema}) → wrapper
└── Change 3: agent(prompt, {label, schema}) → wrapper

memory-rag-search.js
├── 7 similar changes
└── Same pattern
```

---

### Phase 3: Medium Complexity (Week 3)

**Target workflows:** 17 calls total
- `code-review.js` (8 calls)
- `code-security.js` (9 calls)

**Why these next:**
- Mix of patterns but no parallel/pipeline
- Good testing of job type detection (review, audit, security)
- Medium complexity - more realistic scenarios

**New patterns introduced:**
- Pattern 3 (full schema) extensively
- Pattern 6 (error handling) in functions
- Pattern 7 (conditional calls)

**Process:** Same as Phase 2, but:
- More careful schema handling
- Validate job type detection (should be "code-review" and "code-security")
- Test resource estimation accuracy

**Estimated time per workflow:** 3-4 hours
**Total Phase 3:** 6-8 hours

---

### Phase 4: Complex Consensus Workflows (Week 4)

**Target workflows:** 35 calls total
- `ai-consensus-weighted.js` (12+ calls)
- `ai-consensus-filtered.js` (similar)
- Other consensus patterns

**New patterns introduced:**
- Pattern 4: Parallel thunks (multi-AI workers)
- Multiple models running in parallel on different servers
- Advanced job type detection (ai-consensus)
- Error handling with null checks

**Special handling:**
```javascript
// Pattern 4 requires wrapping the thunk:
const results = await parallel(
  models.map(model => () =>
    // BEFORE:
    agent(prompt, {model, schema})
    // AFTER:
    USE_FLEET_DISPATCHER
      ? dispatchViaFleet(model, prompt, {schema})
      : agent(prompt, {model, schema})
  )
);
```

**Performance verification:**
- Should see better model distribution across fleet
- Monitor job completion times
- Validate circuit breaker is learning from failures

**Estimated time per workflow:** 4-5 hours
**Total Phase 4:** 8-10 hours

---

### Phase 5: Autonomous Workflows (Week 4)

**Target workflows:** 40+ calls total
- `code-review-auto.js` (13 calls)
- `code-solve-auto.js` (17 calls)
- `code-test-auto.js` (10 calls)
- Others

**Why last:**
- Depend on earlier workflows working correctly
- Most complex error handling
- Heavy integration testing required
- Full end-to-end validation needed

**Testing approach:**
1. Verify Phase 2-4 migrations working
2. Enable fleet dispatcher in CI/CD
3. Run autonomous workflows against test repo
4. Validate same decisions made (code-review, fixes, tests)
5. Check performance improvements

**Estimated time:** 5-7 hours

---

## Detailed Conversion Checklist

Use this for each agent() call:

```
Agent call: await agent('...', {...})

[ ] 1. Identify the model (opts.model || 'sonnet')
[ ] 2. Extract model from opts
[ ] 3. Extract schema (if present)
[ ] 4. Extract label (if present)
[ ] 5. Extract phase (if present)
[ ] 6. Identify pattern (1-7 from MIGRATION_EXAMPLES.md)
[ ] 7. Apply conversion for that pattern
[ ] 8. Validate syntax (no typos, balanced braces)
[ ] 9. Test with FLEET_DISPATCHER=false (baseline)
[ ] 10. Test with FLEET_DISPATCHER=true (fleet)
[ ] 11. Compare outputs (should be identical)
[ ] 12. Check logs for job tracking
[ ] 13. Commit change
```

---

## Validation Commands

### Pre-Migration
```bash
# Analyze workflow
node -e "
import { analyzeWorkflow } from './fleet-agent-dispatcher.js';
import fs from 'fs';
const code = fs.readFileSync('target-workflow.js', 'utf8');
console.log(analyzeWorkflow(code));
"
```

### Post-Migration (per workflow)
```bash
# 1. Syntax check
node -c target-workflow.js

# 2. Baseline test (direct agent)
FLEET_DISPATCHER=false node test-runner.js target-workflow > baseline.json

# 3. Fleet test
FLEET_DISPATCHER=true node test-runner.js target-workflow > fleet.json

# 4. Compare (should be identical)
diff baseline.json fleet.json

# 5. Check logs for job tracking
grep "📤 Dispatching" fleet.json
grep "✅ Job complete" fleet.json
```

### Integration Testing
```bash
# Run all workflows with fleet enabled
FLEET_DISPATCHER=true npm test

# Run with fallback testing (simulator dispatcher unavailable)
PORT=0 FLEET_DISPATCHER=true npm test

# Should see fallback warnings and correct results
```

---

## Code Review Checklist

For each PR migrating workflows:

### Correctness
- [ ] All agent() calls converted using correct pattern
- [ ] Model extraction is accurate
- [ ] Schema, label, phase preserved in opts
- [ ] parallel() and pipeline() wrappers intact
- [ ] Error handling unchanged
- [ ] No behavioral changes when FLEET_DISPATCHER=false

### Quality
- [ ] No duplicate conversions
- [ ] Consistent formatting
- [ ] Comments explain conversions if complex
- [ ] No commented-out code

### Testing
- [ ] Unit tests pass (fleet-agent-dispatcher.test.js)
- [ ] Baseline test passes (FLEET_DISPATCHER=false)
- [ ] Fleet test passes (FLEET_DISPATCHER=true)
- [ ] Outputs identical (diff baseline fleet)
- [ ] Job completion logs present

### Documentation
- [ ] Commit message clear
- [ ] Links to MIGRATION_EXAMPLES.md if needed
- [ ] Any blockers noted

---

## Rollback Procedures

### If Issues Found

**Option 1: Disable feature (immediate)**
```bash
# Set environment variable to use direct agent()
export FLEET_DISPATCHER=false

# All workflows now use direct agent()
# No code changes needed
```

**Option 2: Revert single workflow**
```bash
# If one workflow has issues:
git revert <commit-hash-of-workflow-migration>

# Other workflows still migrated, this one rolls back
```

**Option 3: Full rollback**
```bash
# Revert all migration commits
git revert <first-migration-commit>..<last-migration-commit>

# Or set feature flag to false system-wide
export FLEET_DISPATCHER=false
```

### Recovery

1. Identify which workflow has issues
2. Review conversion for that workflow
3. Check logs from last run:
   ```bash
   grep "❌\|⚠️" workflow-output.log
   ```
4. Fix conversion (usually missing model extraction)
5. Re-test with new conversion
6. Commit fix

---

## Performance Expectations

### Before Fleet Dispatcher
- All agent() calls on local machine
- Sequential execution (no parallelization)
- Single point of failure (local resource exhaustion)

### After Fleet Dispatcher
- Agent calls distributed across 4-5 fleet servers
- Parallel execution (different servers for different jobs)
- Better resource utilization
- Job completion tracking for circuit breaker learning

### Metrics to Track

1. **Execution time per workflow:**
   ```bash
   time FLEET_DISPATCHER=false node workflow.js
   time FLEET_DISPATCHER=true node workflow.js
   
   # Expected: comparable or faster with fleet
   ```

2. **Resource usage:**
   - Memory: Should decrease (work distributed)
   - CPU: Should decrease (work distributed)
   - Disk: Unchanged

3. **Job completion rate:**
   - Should improve (some jobs may succeed on different server)
   - Circuit breaker learns from failures

---

## Migration Command Sequence

### Complete Phase 1-5 Automation (optional)

If you want to create an automated script to run migrations:

```bash
#!/bin/bash
# migrate-all-workflows.sh

set -euo pipefail

WORKFLOWS=(
  "ai-web-learn"
  "memory-rag-search"
  "code-review"
  "code-security"
  "ai-consensus-weighted"
  "code-review-auto"
)

for workflow in "${WORKFLOWS[@]}"; do
  echo "Migrating: $workflow"
  
  # Analyze
  node analyze.js "$workflow.js"
  
  # Convert (manual step, can't be fully automated)
  # See MIGRATION_EXAMPLES.md for patterns
  
  # Test baseline
  FLEET_DISPATCHER=false npm test "$workflow" > "$workflow.baseline.json"
  
  # Test fleet
  FLEET_DISPATCHER=true npm test "$workflow" > "$workflow.fleet.json"
  
  # Compare
  if diff "$workflow.baseline.json" "$workflow.fleet.json"; then
    echo "✅ $workflow migration validated"
    git add "$workflow.js"
    git commit -m "chore: migrate $workflow to fleet dispatcher"
  else
    echo "❌ $workflow migration failed validation"
    exit 1
  fi
done

echo "✅ All workflows migrated"
```

---

## Monitoring & Metrics

### Setup Prometheus Metrics (optional)

Add to fleet-agent-dispatcher.js for production monitoring:

```javascript
import promClient from 'prom-client';

const dispatchCounter = new promClient.Counter({
  name: 'fleet_dispatch_total',
  help: 'Total jobs dispatched',
  labelNames: ['job_type', 'model', 'success']
});

const jobDurationHistogram = new promClient.Histogram({
  name: 'fleet_job_duration_seconds',
  help: 'Job execution duration',
  labelNames: ['job_type'],
  buckets: [5, 10, 20, 30, 60, 120, 300]
});

const resourceEstimateGauge = new promClient.Gauge({
  name: 'fleet_resource_estimate_ram_gb',
  help: 'Estimated RAM usage',
  labelNames: ['job_type']
});

// Record metrics in dispatchViaFleet():
dispatchCounter.labels(jobType, model, success ? 'true' : 'false').inc();
jobDurationHistogram.labels(jobType).observe(duration);
```

---

## Success Criteria

Migration is complete and successful when:

1. ✅ All 158 agent() calls wrapped
2. ✅ All 25 unit tests passing
3. ✅ All 14 workflows migrated
4. ✅ Baseline vs fleet outputs identical
5. ✅ No regressions in functionality
6. ✅ Job completion logs for all calls
7. ✅ Circuit breaker learning from failures
8. ✅ Performance metrics improve or stay same
9. ✅ Fallback behavior tested
10. ✅ Documentation updated

---

## Timeline Summary

| Phase | Workflows | Calls | Complexity | Time | Cumulative |
|-------|-----------|-------|-----------|------|-----------|
| 1. Setup | - | - | Low | 4h | 4h |
| 2. Simple | 2 | 14 | Low | 4-6h | 8-10h |
| 3. Medium | 2 | 17 | Medium | 6-8h | 14-18h |
| 4. Complex | 3+ | 35 | High | 8-10h | 22-28h |
| 5. Autonomous | 3+ | 40+ | Very High | 5-7h | 27-35h |
| 6. Hardening | - | - | Medium | 3-5h | 30-40h |

**Total estimated effort: 30-40 hours (1 week full-time)**

**Safe schedule: 1 workflow per day = 3-4 weeks**

---

## Getting Help

If you get stuck:

1. **Check MIGRATION_EXAMPLES.md** for pattern matching
2. **Run analyzeWorkflow()** to understand structure
3. **Read fleet-utils.js** for dispatcher API details
4. **Look at fleet-agent-dispatcher.js** for helper function docs
5. **Run tests:** `node fleet-agent-dispatcher.test.js`
6. **Check logs:** `FLEET_DISPATCHER=true npm run workflow | grep "📤\|✅\|❌"`

---

## Appendix: Model Mapping

Default model assignments (used when not specified):

```javascript
// Workflow convention:
const DEFAULT_MODEL = 'sonnet';  // Fast, balanced

// Model assignments by capability:
'fable'         // Lightweight, fast for simple tasks
'haiku'         // Fast, suitable for data extraction
'sonnet'        // Balanced, default choice
'opus'          // Heavy, multi-AI consensus (arbiter)
'gemini-1.5-pro' // Heavy, good at code analysis
'gpt-4'         // Heavy, when using OpenAI MCP
'gpt-4-turbo'   // Fast variant of GPT-4
```

When extracting model from opts:
```javascript
const model = opts.model || 'sonnet';
```

---

## Next Steps

1. Run: `node fleet-agent-dispatcher.test.js`
2. Read: MIGRATION_EXAMPLES.md
3. Start: Phase 2 workflows (ai-web-learn.js)
4. Document: Issues and solutions
5. Review: Code quality and test coverage
6. Deploy: FLEET_DISPATCHER=true in production
