---
name: loop-until-perfect
description: No arbitrary cycle limits on review loops - keep iterating solve→review→fix until adversarial review passes
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9fade8ad-bb5a-4876-9bdd-1e92f63e9562
---

**Rule:** Never use arbitrary cycle limits (3, 5, 10, etc.) on review/fix loops.

**Why:** User directive 2026-06-15: "I want loop until perfect" - quality over speed, no compromise on correctness.

**How to apply:**

```javascript
// ❌ WRONG - arbitrary limit
while (!allPassed && reviewCycle < 3) {
  // review and fix
}

// ✅ CORRECT - loop until perfect
while (!allPassed) {
  reviewCycle++
  
  // Informational only (no hard stop)
  if (reviewCycle % 5 === 0) {
    log(`${reviewCycle} review cycles - persistent issues detected, continuing...`)
  }
  
  // review and fix - KEEP GOING
}
```

**Natural stop conditions (acceptable):**
- ✅ Adversarial review passes (allPassed = true)
- ✅ Token budget exhausted (user-set limit via +500k)
- ✅ System timeout (10-minute workflow max)
- ✅ User interrupt (Ctrl+C, TaskStop)

**Artificial limits (NEVER use):**
- ❌ Max review cycles (3, 5, 10)
- ❌ Max retry attempts
- ❌ "Best effort after N tries"
- ❌ Time-based limits shorter than system max

**Exception:** If same exact error repeats 10+ times with no change, that indicates a bug in the fix logic itself (not the implementation being fixed). Log the pattern and continue, but also alert user to potential infinite loop.

**Related principles:**
- [[feedback_always_review]] - Always review before marking complete
- [[feedback_maximum_autonomy]] - Full autonomy includes solving until correct
- [[feedback_always_multi_ai]] - Multi-AI review with max coverage (6 models)

**Context:** After discovering Haiku 0% success rate fiasco (2026-06-15), user wants systems that iterate until provably correct, not "good enough after 3 tries."
