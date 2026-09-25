---
name: mr-comments-arbiter-first
description: In MR comments with multi-phase reviews, list arbiter verdicts BEFORE workers and challengers
metadata:
  type: feedback
  priority: HIGH
---

# MR Comments: Arbiter Verdict First

## The Rule

When posting arbiter-worker multi-phase reviews to MRs:

**Order:**
1. Final verdict + action items
2. Phase 1 → Arbiter verdict FIRST, then workers
3. Phase 2 → Arbiter verdict FIRST, then challengers
4. Summary table

**Structure per phase:**
```
## Phase N Review

**Phase N Arbiter (Model) Verdict:** [The ruling]

**Phase N Workers/Challengers (Model names):**
- Worker/Challenger 1 (Model): ...
- Worker/Challenger 2 (Model): ...
```

## Why

Arbiter verdict is the decision. Workers/challengers are supporting evidence. Put the decision first, then show why.

Readers scan for the verdict, not the process. Make that scannable.

## How to Apply

Every MR comment with phases: arbiter before workers/challengers, every time.
