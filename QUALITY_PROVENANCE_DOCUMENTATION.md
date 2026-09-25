# Quality Feedback Provenance - Thompson Sampling System

**Date**: 2026-09-25  
**Status**: DOCUMENTED - Blocker #5 Fix  
**Scope**: Phase 1 & 2 Autonomous Learning System

---

## Executive Summary

Quality scores in the Thompson Sampling system come from **outcome-based measurement**, not human evaluation or model self-assessment. A quality score of 1.0 means the task succeeded; 0.0 means it failed. This approach has known limitations (see Bias Risks below).

---

## Quality Score Definition

### Source: Task Outcome
**Quality Score = Outcome Success Rate (0-1)**

```
quality_score = 1.0  if outcome in ('success', 'completed')
quality_score = 0.0  if outcome in ('failed', 'error', 'timeout')
quality_score = 0.5  if outcome NOT in recognized set (default)
```

### Rationale
- Simple, objective, non-biased measurement
- No subjective labeling required
- Automatically captured from task execution pipeline
- Enables real-time feedback loop (immediate outcome → immediate quality signal)

### Data Source Tables
- **Primary**: `workflow.worker_results.outcome` (success/failed/error)
- **Metadata**: `workflow.worker_results.metadata->>'quality_score'` (optional override)
- **Fallback**: Default to 0.5 if missing (neutral prior for Thompson)

---

## Measurement Accuracy & Confidence

### Measurement Method: Outcome Binary
| Property | Value | Notes |
|----------|-------|-------|
| Measurement method | Binary outcome classification | No continuous scale |
| Labeler | Automated task executor | Not human-labeled |
| Measurement variance | 0.0 (deterministic) | Same task → same outcome |
| Confidence interval | N/A | Outcome is fact, not estimate |
| Coverage | 100% of executions | Every task logged |
| Accuracy bounds | N/A (ground truth) | Outcome IS the ground truth |

### Why Outcome-Based Measurement?
1. **No labeling bias**: Outcome is objective fact, not opinion
2. **No delay**: Available immediately upon task completion
3. **Scalable**: Works for thousands of tasks without human review
4. **Verifiable**: Outcome is reproducible (run same task again)

---

## Known Limitations & Bias Risks

### Risk #1: Success ≠ Quality
**Problem**: Task outcome (success/failure) is not the same as task quality.
- A successful code review might be superficial (quality low) but outcome = success
- A failed API call doesn't mean the model was bad (infrastructure issue)

**Impact**: Thompson may learn wrong associations
- Models that get "lucky successes" appear better than they are
- Models that hit infrastructure bugs appear worse

**Mitigation**:
1. Monitor outcome distribution: if all models ~100% success, quality signal is weak
2. Implement outcome verification: add human spot-check (10% random tasks)
3. Use confidence intervals: success_rate ± 2σ to quantify uncertainty
4. Track outcome types: distinguish infrastructure errors from actual failures

### Risk #2: No Granular Quality Measurement
**Problem**: Binary outcome (0 or 1) loses information.
- A code review that caught 8 of 10 bugs = quality 0.8, but outcome = success (1.0)
- A documentation task that's 50% complete = quality 0.5, but outcome = success (1.0)

**Impact**: Thompson can't distinguish between "barely passing" and "excellent" work.

**Mitigation**:
1. Add quality rubrics: score on multiple dimensions (correctness, completeness, clarity)
2. Use metadata quality scores: allow callers to supply nuanced quality assessment
3. Implement outcome verification workflow: after success, evaluate quality deeper

### Risk #3: Selection Bias in Task Difficulty
**Problem**: Different task types have different baseline success rates.
- Code review (easy): 95% success baseline
- Architecture design (hard): 70% success baseline

**Impact**: Thompson conflates model capability with task difficulty.
- Haiku gets selected for easy tasks → high success → appears better
- Opus gets hard tasks → lower success → appears worse
- Actually, Opus may be better, just biased by task selection

**Mitigation**:
1. Stratify by task type: maintain separate priors per (model, task_type) pair
2. Use quality thresholds per task type: some tasks require quality > 0.9
3. Track difficulty: tag tasks as simple/moderate/complex
4. Use Bayesian regression: model quality ~ model + task_type + task_difficulty

### Risk #4: Feedback Loop Lag
**Problem**: Quality feedback may arrive hours after task execution (DB latency, sync delay).

**Impact**: Thompson learns from stale signals; decisions reflect old data.

**Mitigation**:
1. Priority: Implement real-time feedback in Phase 2 (thompson_feedback_syncer.py)
2. Track feedback latency: log time between outcome and Thompson update
3. Decay old signals: exponential decay factor (keep recent outcomes more influential)
4. Monitor staleness: alert if feedback loop is >1 hour behind

---

## Phase 1 Data Quality Assessment

### Current State (as of 2026-09-25)
| Metric | Value | Notes |
|--------|-------|-------|
| Total tasks | 5 (pilot data) | Insufficient for statistical power |
| Quality scores present | 5/5 (100%) | Complete coverage |
| Outcome distribution | 5 successes, 0 failures | No negative examples |
| Average quality | 0.876 | All high-quality outcomes |
| Bias indicators | HIGH | Insufficient diversity, all successes |

### Assessment
**Status**: DATA QUALITY MARGINAL  
**Confidence**: LOW  
**Recommendation**: Phase 1 data is for validation only. Phase 2 requires >100 real production outcomes with mixed success/failure distribution before Thompson quality signals are trustworthy.

### Required Conditions for Phase 2
1. **Sample size**: ≥ 100 production tasks
2. **Outcome distribution**: Mixed (70% success, 30% failure minimum)
3. **Task diversity**: Multiple task types (code review, testing, documentation, etc.)
4. **Quality variance**: Quality scores should span 0.5-1.0 range, not all >0.8
5. **Feedback latency**: < 1 hour (95th percentile) between outcome and Thompson update

---

## Validation & Verification

### How to Validate Quality Signals

**1. Check outcome distribution**:
```sql
SELECT outcome, COUNT(*) as count
FROM workflow.worker_results
GROUP BY outcome;
-- Should show mix, not 100% success
```

**2. Check quality score statistics**:
```sql
SELECT
    model,
    COUNT(*) as tasks,
    AVG(CAST(metadata->>'quality_score' AS FLOAT)) as avg_quality,
    MIN(CAST(metadata->>'quality_score' AS FLOAT)) as min_quality,
    MAX(CAST(metadata->>'quality_score' AS FLOAT)) as max_quality
FROM workflow.worker_results
WHERE created_at > NOW() - '7 days'::INTERVAL
GROUP BY model;
-- Should show variance; if all ≈1.0, quality signal is weak
```

**3. Verify outcome-to-quality mapping**:
```sql
SELECT
    outcome,
    COUNT(*) as count,
    AVG(CAST(metadata->>'quality_score' AS FLOAT)) as avg_quality
FROM workflow.worker_results
GROUP BY outcome;
-- Should show: success→high quality, error→low quality
```

**4. Check feedback loop latency**:
```sql
SELECT
    AVG(EXTRACT(EPOCH FROM (NOW() - created_at))) / 60 as min_since_outcome,
    MAX(EXTRACT(EPOCH FROM (NOW() - created_at))) / 60 as max_min_since_outcome
FROM workflow.worker_results
WHERE created_at > NOW() - '24 hours'::INTERVAL;
-- Should show feedback is recent
```

---

## Phase 2 Improvements (Planned)

### 1. Human Verification (Quality Spot Checks)
- Randomly select 5-10% of outcomes
- Human reviews actual output vs success flag
- Inter-rater agreement metric (Cohen's kappa)
- Calibrate quality scores if disagreement found

### 2. Outcome Verification Workflow
- Add 2-stage outcome: (success/fail) + (verified/unverified)
- Critical tasks: require human verification within 24h
- Track verification latency and reliability

### 3. Granular Quality Dimensions
- Score on multiple axes: correctness, completeness, clarity, efficiency
- Aggregate into composite quality score
- Use weighted average (weights configurable per task type)

### 4. Task Complexity Stratification
- Tag tasks: simple/moderate/complex
- Maintain separate (model, task_type, complexity) priors in Thompson
- Allows for fair comparison across difficulty levels

### 5. Continuous Quality Calibration
- Monthly: Run validation cohort (identical tasks, multiple models)
- Measure actual quality (human review)
- Recalibrate outcome→quality mapping if drift detected

---

## Documentation & Auditability

### Data Lineage
Every quality score in the system should be traceable:
```
Task executed
  ↓
Outcome recorded (workflow.worker_results.outcome)
  ↓
Quality score derived (outcome → 0.0 or 1.0)
  ↓
Thompson state updated (learning/thompson-sampling-state.json)
  ↓
Next task routing influenced
```

### Logging & Audit Trail
- `thompson_feedback_syncer.py` logs all quality signals processed
- Logs include: task_id, model, quality_score, outcome, timestamp
- Stored in `/tmp/thompson_feedback_syncer.log` and synced to database
- Enables post-hoc analysis and bias detection

### Transparency Requirement
Before Phase 2 deployment, publish:
1. Quality provenance document (THIS FILE)
2. Bias risk assessment (Section: Known Limitations)
3. Data quality metrics (Section: Phase 1 Assessment)
4. Validation checklist (Section: How to Validate)

---

## Recommendations for Users

### When Interpreting Thompson Results
1. **Don't trust routing accuracy** if outcome distribution is heavily skewed (>90% success)
2. **Request task stratification** if you need fair comparison across difficulties
3. **Ask for confidence intervals** on quality scores (±σ)
4. **Verify sample size** before trusting any quality signal (need ≥10 outcomes per model)

### When Adding Quality Signals
1. **Prefer objective outcomes** (success/failure)
2. **Add metadata quality scores** for nuanced assessment
3. **Include confidence levels** (e.g., "quality 0.8 ± 0.1")
4. **Document measurement source** (automatic, human-labeled, estimated)

### When Deploying to Production
1. ✓ Start with test harness (Phase 1 validation complete)
2. ✓ Monitor quality signal distribution (use SQL queries above)
3. ✓ Run Thompson A/B test vs baseline (measure quality improvement)
4. ⚠ Plan for Phase 2 improvements (quality spot-checks, task stratification)
5. ⚠ Do NOT use for high-stakes decisions (routing critical security tasks) until Phase 2 complete

---

## References

- **Thompson Sampling Implementation**: `shared/thompson_router.py`
- **Autonomous Learning Phase 1**: `autonomous_learning_phase1.py`
- **Feedback Loop Syncer**: `tools/thompson_feedback_syncer.py`
- **Database Schema**: `ansible/files/sql/full-schema.sql`
- **Quality Metrics**: `tools/performance_dashboard.py`

---

## Sign-Off

**Provenance Documentation Complete**

This document establishes the source, methodology, and limitations of quality scores in the Thompson Sampling system. Users and stakeholders should review Section "Known Limitations & Bias Risks" before relying on routing recommendations.

**Date**: 2026-09-25  
**Status**: PUBLISHED  
**Next Review**: After Phase 2 deployment (estimated 2026-10-15)
