---
name: parallel-phase-launches
description: Launch each phase as soon as its predecessor completes, not waiting for all items in a phase
metadata:
  type: feedback
  priority: HIGH
---

# Parallel Phase Launches: Maximum Throughput

## The Rule

When running multi-phase arbiter-worker reviews across multiple findings (Finding 1, Finding 2, Finding 3, etc.):

**Do NOT wait** for all Phase N to complete before launching Phase N+1.

Instead: **As soon as Phase N completes for item X, launch Phase N+1 for item X immediately.**

## Pattern

```
Finding 1 Phase 1 ──→ completes ──→ launch Finding 1 Phase 2 immediately
Finding 2 Phase 1 ──→ completes ──→ launch Finding 2 Phase 2 immediately
(don't wait for all Phase 1s)

Finding 1 Phase 2 ──→ completes ──→ launch Finding 1 Phase 3 immediately
Finding 2 Phase 2 ──→ completes ──→ launch Finding 2 Phase 3 immediately
(don't wait for all Phase 2s)

...and so on for Phase 4, 5, 6, etc.
```

Each finding's phase pipeline runs independently. No blocking across findings.

## Why

- **Maximizes parallelism:** If Finding 1 Phase 2 is ready but Finding 2 Phase 1 is still running, start Finding 1 Phase 2 anyway
- **Reduces wall-clock time:** Instead of (Phase 1 time) + (Phase 2 time) + (Phase 3 time), you get closer to max(each finding's pipeline)
- **Practical:** Findings rarely take identical time; waiting for the slowest finding blocks faster ones unnecessarily

## How to Apply

```
On Phase N completion (notification):
  IF finding X has Phase N complete:
    IF finding X hasn't launched Phase N+1 yet:
      Launch Phase N+1 immediately
    (don't check other findings)
```

Each finding proceeds at its own pace through all phases.

## What This Fixes

Without this rule: You launch all Phase 1s, wait for slowest one, then launch all Phase 2s, wait for slowest one, etc. With 4 findings and 3 phases, you wait 3 times unnecessarily.

With this rule: Findings run in parallel pipelines; you see results as soon as each finding completes all phases.
