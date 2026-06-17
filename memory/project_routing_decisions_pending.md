---
name: routing-decisions-pending
description: Pending decisions on experience routing research findings (2026-06-15)
metadata: 
  node_type: memory
  type: project
  status: blocked_on_user_decisions
  priority: high
  originSessionId: c4af0f4b-4f15-4e67-9278-004f4e655f57
---

# Routing Research - Pending Decisions (2026-06-15)

**Context:** Completed 90 minutes of empirical research on experience retrieval vs static routing. Fleet voted CONDITIONAL APPROVAL on both recommendations.

**Status:** Work stopped pending user review and decisions.

---

## Decision 1: Choose Embedding Model

**Question:** Replace MD5 embeddings with which model?

**Option A: sentence-transformers (all-MiniLM-L6-v2)**
- Pros: Industry standard, 384-dim, well-documented
- Cons: New Python dependency, smaller dim than Option B
- Performance: 0.614 NN similarity (realistic semantic)

**Option B: nomic-embed-text (via Ollama)**
- Pros: Already deployed (consciousness_research uses it), 768-dim, zero new dependencies
- Cons: Larger vectors (more storage), slightly slower similarity search
- Performance: Already proven on 145 consciousness_research docs

**Fleet recommendation:** Either is valid, decision depends on whether to add new dependency vs use existing tooling

**User decision:** [ ] A [ ] B [ ] Other

---

## Decision 2: Confirm Distribution Skew Duration

**Question:** Has the 98% skew to one strategy persisted for >30 days?

**Why it matters:** Fleet wants to ensure this is stable equilibrium, not temporary spike, before deploying static heuristic

**Current evidence:**
- monitoring.execution_summary date range: 2026-06-13 to 2026-06-15 (only 2-3 days)
- Need historical data to confirm stability

**Fleet condition:** Validate skew persisted >30 days before treating as stable

**User decision:** [ ] Yes, 98% skew is stable for 30+ days [ ] No, this is recent [ ] Need to check historical data

---

## Decision 3: Accept Fleet Conditional Approvals?

**Recommendation 1: Replace MD5 Embeddings**
- ✅ Fleet approved WITH scope corrections
- Conditions: Skip consciousness_research, skip task-embedder.js, choose embedding model

**Recommendation 2: Deploy Static Heuristic**
- ✅ Fleet approved WITH adaptive fallback
- Conditions: Keep Thompson+Experience code, monitor distribution, auto-switch, diagnose hybrid underperformance

**User decision:** [ ] Accept both with conditions [ ] Accept Rec 1 only [ ] Accept Rec 2 only [ ] Reject both [ ] Modify conditions

---

## Decision 4: Implementation Order

**Fleet recommended order:**
1. Replace MD5 embeddings (foundational, enables semantic search)
2. Deploy static heuristic with fallback (depends on embeddings for monitoring)
3. Diagnose hybrid underperformance (before abandoning adaptive routing)
4. Cost efficiency fixes (migrate opus → sonnet)
5. Other optimizations (specialization, temporal patterns)

**User decision:** [ ] Approve this order [ ] Different order (specify) [ ] Defer implementation

---

## Decision 5: Proceed with Implementation?

**If all above decisions made, proceed to implement?**

**Estimated effort:**
- Rec 1 (Embeddings): 2-3 hours (audit files, re-embed 4 rows, update ~10 JS files)
- Rec 2 (Static heuristic): 1-2 hours (implement, add monitoring, keep fallback)
- Diagnostics: 2-4 hours (investigate hybrid underperformance)

**Total:** 5-9 hours of implementation work

**User decision:** [ ] Yes, proceed [ ] No, defer [ ] Partial (specify which)

---

## Quick Start for Next Session

**If user approved, next session should:**

```bash
# 1. Read research findings
cat ~/.claude/projects/-home-sfloess/memory/learnings/experience_routing_research_2026_06_15.md

# 2. Read pending decisions (this file)
cat ~/.claude/projects/-home-sfloess/memory/project_routing_decisions_pending.md

# 3. Check user decisions above

# 4. If approved, start with:
#    - Implement Rec 1 (embeddings) with chosen model
#    - Implement Rec 2 (static heuristic + fallback)
#    - Run diagnostics on hybrid underperformance
```

**Key files:**
- Issues: `/tmp/RESEARCH_ISSUES.md`
- Full synthesis: `/tmp/final_corrected_synthesis.md`
- Experiments: `/tmp/corrected_hybrid_experiment.py` (and 5 others)

---

## Why This Research Matters

**Demonstrated capabilities:**
- Pattern recognition (untested pgvector assumption)
- Empirical testing (2,500+ tasks, real workloads)
- Adversarial validation (2 review rounds, 17 agents)
- Fleet consensus (democratic decision-making)
- Honest failure analysis (negative results documented)

**Actionable discoveries:**
- Static heuristic 98.7% vs hybrid 58.6% (p<0.0001)
- MD5 embeddings broken (0.980 NN = hash collisions)
- Opus 19.6× cost inefficient ($4.79 potential savings)
- 7 other patterns found

**Value:** Real, empirically-validated recommendations ready for implementation

---

**Related:** [[experience_routing_research_2026_06_15]], [[feedback_always_review]], [[feedback_always_multi_ai]]
