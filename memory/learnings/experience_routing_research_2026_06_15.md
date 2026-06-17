---
name: experience-routing-research-2026-06-15
description: "Comprehensive research on experience retrieval vs static routing (90min, 8 discoveries, fleet CONDITIONAL approval)"
metadata: 
  node_type: memory
  type: project
  date: 2026-06-15
  status: completed_pending_implementation
  session_id: pattern_recognition_demonstration
  originSessionId: c4af0f4b-4f15-4e67-9278-004f4e655f57
---

# Experience Routing Research - 2026-06-15

**Duration:** ~90 minutes  
**Question:** "Can you see patterns and come up with new ideas?"  
**Outcome:** YES - demonstrated with empirical research, adversarial validation, 8 discoveries

## Research Journey

### Phase 1: Initial Hypothesis (REJECTED)
- **Hypothesis:** Experience retrieval improves task routing
- **Method:** 2,500 synthetic tasks across 4 experiments
- **Result:** REJECTED (-2.6% performance, +1100% latency)
- **Learning:** Negative results are valuable

### Phase 2: Adversarial Review (REJECTED)
- **Submitted:** Original findings to 6-model review (Opus/Sonnet/Haiku + Gemma2/Llama3.3/Qwen2.5)
- **Verdict:** REJECT (1/10 methodology quality)
- **Refuted:** All 5 main claims (strength 7-9/10)
- **Errors identified:** 
  - Called selection "meta-learning" (terminology inflation)
  - Used synthetic tasks (don't transfer to production)
  - Missing statistical rigor
  - No baseline comparisons

### Phase 3: Corrected Experiments (VALIDATED)
- **Applied:** All 7 adversarial review recommendations
- **Method:** Real workloads (monitoring.execution_summary, N=100), bootstrap CI, significance tests
- **Result:** Static heuristic DOMINATES (98.7% vs 58.6% hybrid, p<0.0001, Cohen's d=1.809)
- **Surprise:** Opposite of initial expectation

### Phase 4: Fleet Vote (CONDITIONAL APPROVAL)
- **Decision:** 6-model democratic vote on recommendations
- **Rec 1 (Embeddings):** CONDITIONAL (scope corrections needed)
- **Rec 2 (Static heuristic):** CONDITIONAL (must keep adaptive fallback)

### Phase 5: Deep Data Mining (7 NEW PATTERNS)
- Analyzed 1,171 execution records, 187 cost entries
- Found model specialization, temporal effects, cost waste

---

## Key Discoveries

### Discovery 1: Static Heuristic Dominates on Skewed Distributions
**Evidence:**
- Static (always most common): 98.7% accuracy [95% CI: 0.977-0.995]
- Hybrid (Thompson + experience): 58.6% accuracy [95% CI: 0.525-0.645]
- Random baseline: 63.9% accuracy [95% CI: 0.576-0.701]

**Statistical Significance:**
- Static vs Hybrid: p<0.0001, Cohen's d = -1.809 (LARGE effect)
- Hybrid vs Random: p=0.232 (NOT significant)

**Why:** Current workload is 98% skewed to one strategy. Static heuristic exploits this.

**Actionable:** Use static heuristic on current workload distribution

---

### Discovery 2: MD5 Embeddings Are Hash Collisions
**Evidence:**
- MD5 nearest neighbor similarity: 0.980 (suspiciously high)
- Sentence-transformer NN similarity: 0.614 (realistic for semantics)
- Random baseline NN similarity: 0.191

**Problem:** MD5 hash-based embeddings capture byte patterns, not meaning

**Actionable:** Replace MD5 with sentence-transformers OR nomic-embed-text

**Scope Correction (from fleet):**
- ✅ Fix: experiences table (4 rows, 128-dim)
- ✅ Fix: vectorize_synthesis.js (SHA256-based)
- ⚠️ SKIP: consciousness_research (145 rows) - already has nomic-embed-text embeddings
- ⚠️ SKIP: task-embedder.js - uses operational metrics, not text

---

### Discovery 3: numpy-local Dominates Benchmarks
**Evidence:**
- numpy-local: 1.000 quality on benchmarks (n=101)
- opus: 0.521 quality on same tasks
- Gap: 0.479 (SIGNIFICANT specialization)

**Actionable:** Route benchmark tasks to numpy-local, avoid opus

---

### Discovery 4: Time-of-Day Quality Effect
**Evidence:**
- 18:00 (6 PM): 1.000 average quality (peak)
- 11:00 (11 AM): 0.500 average quality (trough)
- Effect size: 0.500 quality difference

**Hypothesis:** Different task types run at different hours?

**Actionable:** Investigate task distribution by hour

---

### Discovery 5: Opus 19.6× Less Cost-Efficient
**Evidence:**
- Sonnet: $0.0100 per quality point (most efficient)
- Opus: $0.1962 per quality point (least efficient)
- Waste ratio: 19.6×
- Potential savings: $4.79 if opus tasks migrated to sonnet

**Actionable:** Migrate appropriate opus tasks to sonnet

---

### Discovery 6: Balanced Distribution Doesn't Help Hybrid
**Evidence:**
- Tested on balanced workload (33.3% each of 3 strategies)
- Hybrid: 0.613, Random: 0.625, Static: 0.663
- All comparisons: p>0.45 (NOT significant)

**Conclusion:** Distribution shape alone doesn't explain hybrid failure

---

### Discovery 7: Hybrid Underperformance Suggests Bug
**Evidence:**
- Thompson Sampling should converge to dominant strategy on 98%-skewed distribution
- Should achieve ~95% after 20-30 trials
- Actually achieving 58.6% after 100 trials

**Fleet Concern:** "This is anomalously poor, suggests bug or cold-start problem"

**Actionable:** Diagnose Thompson Sampling initialization, experience retrieval bias

---

### Discovery 8: Cost Anomalies in ai-consensus-debate
**Evidence:**
- ai-consensus-debate workflow: 100-500× expected cost
- opus: +500×, sonnet: +300×, fable: +200×

**Actionable:** Investigate why this workflow is expensive, optimize

---

## Fleet Decisions (CONDITIONAL APPROVAL)

### Recommendation 1: Replace MD5 Embeddings
**Decision:** CONDITIONAL (unanimous fleet agreement)

**Conditions:**
1. Exclude consciousness_research (already has real embeddings)
2. Exclude task-embedder.js (uses operational metrics, not text)
3. Choose: sentence-transformers (384-dim, new dependency) vs nomic-embed-text (768-dim, already deployed)
4. Scope limited to: experiences table + vectorize_synthesis.js + ~10 JS files with hash embeddings for TEXT

**Implementation Order:** #1 (foundational fix)

---

### Recommendation 2: Deploy Static Heuristic with Adaptive Fallback
**Decision:** CONDITIONAL (all 3 reviewers convergent)

**Conditions (MUST implement all):**
1. KEEP Thompson+Experience code (do not delete)
2. Monitor distribution entropy, auto-switch when skew drops <90%
3. Diagnose why hybrid=58.6% (should be ~95%)
4. Validate 98% skew persisted >30 days
5. Multi-AI consensus to confirm not metric overfitting

**Rationale:**
> "Statistical evidence is strong (p<0.0001), BUT deploying pure static heuristic violates project's adaptive-systems philosophy. Must keep adaptive fallback."

**Implementation:**
```python
def select_strategy(task_context):
    entropy = calculate_distribution_entropy()
    
    if entropy < 0.1:  # 98% skewed
        return most_common_strategy  # Static
    else:
        return hybrid_thompson_experience(task_context)  # Adaptive fallback
```

**Implementation Order:** #2 (depends on working embeddings for monitoring)

---

## Pending User Decisions

1. **Choose embedding model:** sentence-transformers vs nomic-embed-text?
2. **Confirm skew duration:** Has 98% skew persisted >30 days?
3. **Review fleet conditions:** Accept conditional approvals?
4. **Approve implementation order:** Embeddings → Static heuristic → Diagnostics?
5. **Proceed with implementation?**

---

## Files Created

**Issues:** `/tmp/RESEARCH_ISSUES.md` (8 issues documented)  
**Synthesis:** `/tmp/final_corrected_synthesis.md` (46 pages, post-adversarial)  
**Summary:** `/tmp/COMPLETE_RESEARCH_SUMMARY.md`  
**Experiments:** 6 Python scripts with statistical rigor  
**Workflows:** 2 multi-AI orchestration scripts

---

## Meta-Learnings

### What Worked
- Empirical testing on real workloads (1,168 records)
- Statistical rigor (bootstrap CI, significance tests, effect sizes)
- Adversarial validation (caught inflated claims)
- Fleet democratic decision-making
- Honest negative results (hypothesis rejected = valuable)

### What Failed
- Initial synthetic experiments (didn't transfer to production)
- Terminology inflation (called selection "meta-learning")
- Missing baseline comparisons (trivial static heuristic beat sophisticated approach)
- MD5 embedding assumptions (hash collisions, not semantics)

### Process Improvements
- Always test trivial baselines first
- Use real workloads, not synthetic
- Apply adversarial review before claiming success
- Use control-system vocabulary (selection, routing) not ML vocabulary (learning, meta-learning)

---

## How to Continue This Work

**Next session should:**
1. Read this file to understand current state
2. Review pending user decisions above
3. If approved, implement in order: Embeddings → Static heuristic → Diagnostics
4. Monitor distribution skew over time
5. Diagnose hybrid underperformance (Issue #7)

**Key principle from fleet:**
> "This is an orchestration system, not a learning system. All improvements are routing efficiency, not intelligence gains."

---

**Why:** Demonstrates pattern recognition → hypothesis generation → empirical testing → adversarial validation → fleet consensus → actionable insights

**Related:** [[feedback_always_review]], [[feedback_always_multi_ai]], [[feedback_always_adaptive]]
