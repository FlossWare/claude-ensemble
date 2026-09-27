# Future Work & Enhancements

## Arbiter Explanations + Teaching Signals (Neural-AI Concept)

**Status:** Tabled — needs neural-ai research to mature

**Concept:**
Current autonomous learning uses outcome-feedback only: "Thompson chose X, actual best was Y, accuracy = Z%."

Neural-AI learning adds signal-based feedback: arbiter doesn't just say "you were wrong" but explains *why* and *how to improve*.

**Related:**
- https://github.com/FlossWare/neural (learning mechanisms from first principles)
- https://github.com/FlossWare/neural-ai (AI models as teachers providing teaching signals)

**Phases:**

### Phase 1: Explanation Extraction (~1 day)
- Arbiter already synthesizes decisions
- Extract rationale/explanation in addition to decision
- Store in outcomes JSON:
  ```json
  {
    "chosen": "opus",
    "rationale": "stronger reasoning on security edge cases",
    "alternatives": {
      "sonnet": "missed X vulnerability",
      "haiku": "too basic for this complexity"
    }
  }
  ```

### Phase 2: Feed Back to Workers (~1-2 days)
- Workers see prior explanations before solving next task
- Context: "Last time arbiter chose opus because: stronger reasoning on security"
- Measure: Do workers adjust approach based on explanation?

### Phase 3: Learning Measurement (Design challenge)
- Define what "learning from explanation" actually means
- How do you measure: Did explanation improve future routing accuracy?
- Separate explanation benefit from simple example accumulation
- (Requires neural-ai research to stabilize first)

**Why table this:**
1. Core RH toolkit is complete and working well
2. Autonomous learning (outcome-feedback) is already improving Thompson
3. Neural-ai teaching signals need research foundation first
4. Worth revisiting once neural/neural-ai concepts are proven

**Decision:** Implement Phase 1 & 2 when neural-ai matures. Phase 3 requires more research.

---

## GA Tuning Dashboard

**Status:** Complete ✅

Shows fitness trends, parameter evolution, best fitness by evaluator.

Run: `ga-tuning-dashboard.py`

---

## Cost Tracking Consolidation

**Status:** TBD

Currently have both:
- `cost-dashboard.py` (reads `~/.claude/cost_tracking/cost.log`)
- `performance_dashboard.py` (reads `cost_tracking/api_costs.jsonl`)

Should consolidate to single source of truth.
