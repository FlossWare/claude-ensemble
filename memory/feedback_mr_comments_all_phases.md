---
name: mr-comments-all-phases-complete
description: MR comments with multi-phase arbiter-worker reviews must include ALL phases (Phase 1 AND Phase 2 AND beyond)
metadata:
  type: feedback
  priority: CRITICAL
---

# MR Comments Must Include ALL Phases

## The Rule

When posting consensus reviews to MRs:

**Show every phase**, in order:
- Phase 1 findings (all 4+ workers, what they found)
- Phase 1 arbiter verdict (synthesis, reasoning)
- Phase 2 findings (all 4+ workers, what they challenged/confirmed)
- Phase 2 arbiter verdict (synthesis, reasoning)
- *repeat for Phase 3+ if they run*

Then final recommendation.

## Why

Readers need to see the **full dispute arc**:
- What Phase 1 found (the blockers)
- Why Phase 2 challenged it (the evidence)
- Why arbiters agreed/disagreed (the reasoning)

Omitting Phase 1 makes Phase 2's challenges invisible. Readers don't understand what was disputed or why it matters.

## How to Apply

Structure as:

```markdown
### Phase 1 Review

**Phase 1 Workers Found**
- Worker 1: ...
- Worker 2: ...

**Phase 1 Arbiter Verdict**
- Finding: REQUEST CHANGES (4 blockers)
- Reasoning: ...

---

### Phase 2 Review (Challenge)

**Phase 2 Workers Found**
- Worker 1 (challenges blocker A): ...
- Worker 2 (challenges blocker B): ...

**Phase 2 Arbiter Verdict**
- Finding: OVERTURNED to APPROVE WITH COMMENTS
- Reasoning: ...

---

### Recommendation

...
```

The dispute is the story.

## What This Fixes

Without Phase 1, readers see conclusions without context. With all phases, they see the full reasoning chain and can verify the logic themselves.
