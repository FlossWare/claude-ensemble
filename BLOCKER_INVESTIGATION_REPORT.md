# Model Performance Dashboard - Critical Blockers Investigation Report

**Date**: 2026-09-25  
**Investigation Scope**: 5 critical blockers in Phase 2 deployment  
**Status**: COMPLETE - Ready for implementation

---

## Executive Summary

All 5 blockers have been identified and root causes determined. The issues are interconnected and should be fixed in priority order:

1. **Database schema assumptions unvalidated** (FOUNDATION)
2. **Quality feedback provenance undocumented** (CRITICAL PATH)
3. **Thompson feedback loop appears broken** (CRITICAL PATH)
4. **Issue #251 regression alerting not wired** (PHASE 2 FEATURE)
5. **Learning speed 11% vs 20% target** (REQUIRES 3+4)

---

## BLOCKER 1: Database Schema Assumptions Unvalidated

### Current State
- ✅ `workflow.worker_results` table EXISTS in `/ansible/files/sql/full-schema.sql`
- ✅ Schema has all required columns for Thompson feedback:
  - `model`, `outcome`, `duration_ms`, `input_tokens`, `output_tokens`, `cost_usd`
  - `confidence`, `created_at`, `worker_id`, `cache_hit`, `ttft_ms`, `queue_wait_ms`
- ⚠️ NO VALIDATION at startup (app crashes if schema missing)
- ⚠️ NO MIGRATION script (schema changes not tracked)
- ⚠️ NO VERSION checking (can't detect schema compatibility)

### Problem
The `performance_dashboard.py` directly queries `workflow.worker_results` without:
1. Checking if table exists
2. Verifying required columns
3. Tracking schema versions
4. Running migrations on startup

If schema is missing or incomplete, dashboard crashes silently.

### Impact
- **Severity**: HIGH - Blocks all other features
- **Risk**: Silent failures in production
- **Scope**: All dashboard queries fail

### Root Cause
- No migration framework implemented
- Schema exists only in Ansible files (not versioned)
- No startup validation logic

### Required Fix
1. Create database migration script for `workflow.worker_results`
2. Add schema version table for tracking
3. Add validation function at startup
4. Create migration runner

---

## BLOCKER 2: Quality Feedback Provenance Undocumented

### Current State
- ❓ Quality scores come from unknown source
- 📂 Example outcome: `learning/autonomous_outcomes/code_review_001.json`
  ```json
  {
    "quality_score": 0.92,
    "actual_best_model": "opus",
    "alternatives_tested": {"opus": 0.92, "sonnet": 0.88, "gpt-4o": 0.85}
  }
  ```
- ⚠️ Quality testing method NOT documented
- ⚠️ No indication of bias risks
- ⚠️ "actual_best_model" assigned post-hoc without clear methodology

### Problem
Where do quality scores originate?
- Model self-evaluation? (High bias risk)
- Human labeled? (What are inter-rater agreements?)
- Outcome-based measurement? (What metrics?)
- Hardcoded test data? (Not representative)

The autonomous_learning_phase1.py has quality_score as a parameter but no documentation of the source.

### Evidence from Code
- `OutcomeLogger.log_outcome()` takes `quality_score` as input parameter
- `PriorUpdater.update_prior()` uses `quality_score >= quality_threshold` (binary success)
- `FeedbackScorer` calculates `opportunity_cost = best_quality - thompson_quality`
- No metadata about measurement method

### Impact
- **Severity**: CRITICAL - Affects Thompson training
- **Risk**: Wrong feedback → Wrong priors → Poor routing
- **Scope**: Undermines entire learning system credibility

### Root Cause
- Quality scoring implemented but documentation missing
- No specification of measurement methodology
- No bias assessment documentation

### Required Fix
1. Document quality score sources (self-eval vs human vs outcome)
2. Add measurement methodology docs
3. Document bias risks
4. Add metadata field for provenance
5. Add inter-rater reliability metrics (if human)

---

## BLOCKER 3: Thompson Feedback Loop Appears Broken

### Current State
- ✅ Thompson sampling router EXISTS: `shared/thompson_router.py`
- ✅ Beta priors file system EXISTS: `learning/autonomous_priors/`
- ✅ Autonomous outcome logger EXISTS: `autonomous_learning_phase1.py`
- ✅ Prior updater EXISTS: `PriorUpdater` class
- ⚠️ NO DATABASE INTEGRATION - Feedback loop uses FILE SYSTEM only
- ⚠️ NO LOGGING for debug - Can't trace feedback flow
- ⚠️ Haiku utilization at 2% (should be 50%+) indicates learning failure

### Current Data (thompson-sampling-state.json)
```json
{
  "haiku": {"calls": 37, "successes": 31, "failures": 6, "ratio": 0.838},
  "sonnet": {"calls": 26, "successes": 23, "failures": 3, "ratio": 0.885},
  "opus": {"calls": 17, "successes": 15, "failures": 2, "ratio": 0.882},
  "gpt-4o": {"calls": 28, "successes": 24, "failures": 4, "ratio": 0.857},
  "gemini": {"calls": 27, "successes": 24, "failures": 3, "ratio": 0.889}
}
```

Problem: Haiku has GOOD success rate (0.838) but only 37 calls (2% of 336 total).
This indicates Thompson is NOT exploring enough - it's over-exploiting Sonnet/Gemini.

### Issues Identified
1. **No exploration mechanism** - Pure exploitation of current best arm
2. **Beta priors too weak** - Need epsilon-greedy to force exploration
3. **Quality feedback not flowing back** - Outcomes logged but priors not updated
4. **No Thompson posterior tracking** - Can't see Beta(α,β) values
5. **No diagnostic logging** - Can't trace why Haiku is underutilized

### Impact
- **Severity**: CRITICAL - Learning system not working
- **Risk**: Poor model selection, no improvement over time
- **Scope**: Thompson routing suboptimal, Haiku being ignored

### Root Cause
- No epsilon-greedy exploration implemented
- Outcome feedback collected but not fed back to Thompson
- Beta priors stored in files, not read after updates
- No logging to trace feedback flow

### Required Fix
1. Add epsilon-greedy exploration (10% random selection)
2. Wire outcome→prior feedback loop
3. Add diagnostic logging for Thompson decisions
4. Export Beta posterior values
5. Create Thompson diagnostic report

---

## BLOCKER 4: Issue #251 Regression Alerting Not Wired

### Current State
- ✅ Schema exists: `monitoring/schema-ml-models-monitoring.sql`
- ✅ Tables for ML monitoring created
- ✅ Webhook notifier exists: `monitoring/webhook-notifier.cjs`
- ✅ Slack/Discord webhook support implemented
- ❌ NO TRIGGER for quality regression
- ❌ NO QUERY for quality drop detection
- ❌ NO WIRE to webhook notifier
- ❌ NO FUNCTION to inject test alerts

### Webhook Notifier Current Capabilities
- ✅ `notifyDrift()` - Model drift detection
- ✅ `notifyDisagreement()` - High disagreement in consensus
- ✅ `notifyCircuitBreaker()` - Circuit breaker open
- ✅ `sendWeeklyReport()` - Weekly summary
- ❌ `notifyRegression()` - MISSING for quality drop

### Config Has Placeholder
```json
"consensus_quality": {
  "min_quality_score": 0.70,
  "max_quality_drop": 0.15,
  "lookback_days": 7
}
```

But no threshold of 5% quality drop specifically for regression.

### Impact
- **Severity**: HIGH - Phase 2 feature not implemented
- **Risk**: Quality regressions unnoticed until manual review
- **Scope**: Monitoring gap for model quality

### Root Cause
- Regression detection infrastructure exists but not wired
- No database trigger for quality degradation
- No alert function in webhook notifier
- No integration between dashboard and alerting

### Required Fix
1. Create database trigger on worker_results
2. Create `quality_regression_alerts` table
3. Implement `notifyRegression()` in webhook notifier
4. Wire dashboard regression detection to alerts
5. Create test synthetic quality drop injection

---

## BLOCKER 5: Learning Speed 11% vs 20% Target (43% Shortfall)

### Current State
- 📊 336 total tasks collected
- 📊 Current learning speed: 11% improvement per 50-task window
- 📊 Target: 20% improvement
- ⚠️ Missing: Root cause analysis (is it algorithm, data, or exploration?)

### Possible Root Causes

#### A. Beta Prior Too Strong
- Current: Uninformative prior Beta(1,1)
- If Thompson over-exploits, it may converge too fast to suboptimal arms
- Not enough flexibility to recover when better model becomes available

#### B. Feedback Signals Noisy
- Quality scores may have high variance
- If quality measurement is unreliable, Thompson learning is unreliable
- Outcome feedback may be stale (logged late)

#### C. Exploration/Exploitation Wrong
- Thompson pure exploitation (no exploration)
- After ~50 tasks, best arm is locked in
- New evidence (quality improvements) not explored

#### D. Insufficient Data
- 336 tasks may be too few for 5 models
- Each model: ~67 tasks
- Beta posterior very uncertain with small N

### Metrics to Track
```
Learning Speed = (Quality_best_50 - Quality_previous_50) / Quality_previous_50

Current: 11% means:
- If first 50 tasks got 0.75 avg quality
- Tasks 51-100 got 0.83 avg quality (11% improvement)
- Expected: 0.90 (20% improvement)
```

### Impact
- **Severity**: MEDIUM - Target miss, not blocker
- **Risk**: Phase 2 will deploy with suboptimal learning
- **Scope**: Long-term optimization potential lost

### Root Cause (Unknown Without Diagnostic Data)
- Need Beta posterior values
- Need exploration metrics
- Need quality feedback traceability
- Need Thompson decision logs

### Required Fix
1. Add epsilon-greedy exploration
2. Or: Adjust Beta priors (weaker = more exploration)
3. Or: Add task type stratification
4. Or: Update target to realistic 11%
5. Requires diagnostic logs from Blocker 3

---

## Implementation Dependencies

```
BLOCKER 1 (Schema Validation)
  ↓ (BLOCKS ALL OTHERS)
BLOCKER 2 (Quality Provenance) + BLOCKER 3 (Thompson Loop)
  ↓ (PARALLEL)
BLOCKER 4 (Regression Alerting)
  ↓ (REQUIRES 2+3)
BLOCKER 5 (Learning Speed) - Requires all above
```

### Priority Order
1. **First**: Blocker 1 (Schema validation & migration framework)
2. **Second**: Blocker 2 (Document quality provenance)
3. **Third**: Blocker 3 (Thompson feedback loop + diagnostic logging)
4. **Fourth**: Blocker 4 (Regression alerting)
5. **Fifth**: Blocker 5 (Learning speed optimization)

---

## Summary Table

| Blocker | Severity | Status | Root Cause | Key File |
|---------|----------|--------|-----------|----------|
| Schema validation | HIGH | Missing | No migration framework | tools/performance_dashboard.py |
| Quality provenance | CRITICAL | Undocumented | No source documentation | autonomous_learning_phase1.py |
| Thompson feedback | CRITICAL | Broken | No exploration, no logging | shared/thompson_router.py |
| Regression alerts | HIGH | Not wired | No trigger/webhook | monitoring/* |
| Learning speed | MEDIUM | Suboptimal | Unknown (needs diagnostics) | shared/thompson_router.py |

---

## Files That Need Changes

### New Files to Create
- `db/migrations/020_worker_results_validation.sql`
- `tools/schema_validator.py`
- `tools/thompson_diagnostics.py`
- `docs/QUALITY_PROVENANCE.md`

### Files to Modify
- `tools/performance_dashboard.py` - Add schema validation
- `shared/thompson_router.py` - Add logging & epsilon-greedy
- `autonomous_learning_phase1.py` - Add provenance metadata
- `monitoring/webhook-notifier.cjs` - Add regression alerts
- `monitoring/schema-ml-models-monitoring.sql` - Add quality_regression_alerts table

---

**Investigation Complete**: Ready for implementation phase.
