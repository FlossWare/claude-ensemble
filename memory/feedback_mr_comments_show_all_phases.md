---
name: mr-comments-show-all-phases
description: When commenting on MRs with arbiter-worker reviews, always show all workers' and arbiters' findings for all phases
metadata:
  type: feedback
  priority: HIGH
---

# MR Comments Must Show All Phases

## The Rule

When posting an arbiter-worker consensus review to an MR, always include:

1. **Each worker's finding** (by name/identifier) — what they discovered and why
2. **Each arbiter's synthesis** (by phase) — how they interpreted the workers, what they ruled
3. **Why arbiters agreed or disagreed** (with evidence) — not just the verdict

## Why

The consensus process is **part of the value**. Showing only the final verdict hides:
- What workers tested (execution evidence vs. theory)
- Where workers diverged or aligned
- Why arbiters trusted or rejected findings
- The reasoning chain that led to the decision

Without this transparency, readers see "we decided X" but not "we tested this and found..."

## How to Apply

Structure MR comments as:

```markdown
### What Phase N Workers Found

**Worker 1 - [Area]**
- Finding: ...
- Evidence/method: ...

**Worker 2 - [Area]**
- Finding: ...
- Evidence/method: ...

### What Phase N Arbiter Synthesized

- Key insight: ...
- Agreed with Worker X because: ...
- Disagreed with Worker Y because: ...
```

Then verdict. The process matters as much as the outcome.

## What This Fixes

When only the verdict is posted, readers don't see the rigor. Showing all workers + arbiters demonstrates that the decision is grounded in evidence, not guesswork.
