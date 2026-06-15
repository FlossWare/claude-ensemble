---
name: fleet-consensus-timing
description: "Run fleet consensus on DESIGNS before building, not on finished implementations"
metadata: 
  node_type: memory
  type: feedback
  created: 2026-06-13
  relates_to: 
    - - feedback_always_fleet_consensus
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

Always run fleet consensus on **designs and architecture**, NOT on finished implementations.

**Why:** Validating after building means wasted effort if the approach is wrong. Validating before building catches issues when they're cheap to fix.

**How to apply:**
1. **Before building:** Write design doc → Fleet review → Build
2. **Not after building:** Build → Fleet review → Rebuild

**Evidence from 2026-06-13 session:**
- Built custom session orchestration (6 hours, 500 lines)
- Fleet review found 6 CRITICAL flaws
- Discarded entire implementation
- Rebuilt with Git LFS (2 hours)

**What it cost:**
- 6 hours of wasted implementation time
- 500 lines of deleted code
- Could have been 3.5 hours total if reviewed design first

**When to review:**
- ✅ During planning/design phase
- ✅ Before writing significant code
- ✅ When choosing between architectural approaches
- ❌ After implementation is complete
- ❌ When code is already deployed

**The pattern:**
```
CORRECT:
  Problem → Design options → Fleet review → Build winner
  Time: Design (30min) + Review (1hr) + Build (2hr) = 3.5hr

INCORRECT (what we did today):
  Problem → Build first idea → Fleet review → Discard → Build again
  Time: Build (6hr) + Review (1hr) + Rebuild (2hr) = 9hr
```

**Red flags that mean "review the design now":**
- About to modify production services
- Building new infrastructure
- Choosing between multiple approaches
- Solving distributed systems problems
- Anything that takes >2 hours to build

**Cost/benefit:**
- Design review: 1 hour investment
- Bad implementation: 6+ hours wasted
- **ROI: 6:1** when review catches major flaws

**Related:** [[feedback_always_fleet_consensus]] - Always use multi-AI for decisions
