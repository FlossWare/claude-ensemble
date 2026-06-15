---
name: always-verify-before-documenting
description: Always verify implementation against actual code before documenting features as complete
metadata:
  type: feedback
  created: 2026-06-14
  priority: high
  originSessionId: session-2026-06-14-fleet-config-audit
---

**Always verify implementation in actual code before documenting features as complete.**

**Why:** Documentation that claims unimplemented features exist causes confusion, wastes time, and breaks trust.

**How to apply:**

1. **Read the actual code** - Don't trust other documentation, read the source
2. **Search for TODOs** - `grep -r TODO` before documenting as complete
3. **Verify with tests** - If tests don't exist or pass, feature isn't done
4. **Distinguish planned from implemented** - Use clear section headers:
   - "What Exists Today" (verified in code)
   - "Planned Features" (TODOs, design docs)
   - "What Does NOT Exist Yet" (explicit anti-section)

**What happened:**

Multi-AI consensus routing was documented in `~/fleet-coordinator/services/README.md` as:
> "Every job routed through the orchestrator uses 6-model consensus for optimal placement decisions"

With detailed descriptions of workers (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini) and arbiter fallback chains.

**Reality:** Line 68 of `pi02-job-queue.py`:
```python
# TODO: Replace with actual multi-AI consensus call
```

Current implementation uses simple if/elif heuristics, NOT multi-AI consensus.

**Impact:**
- README update workflow documented this as implemented
- Multi-AI review caught it and REJECTED (0/3 votes)
- Wasted review cycles
- Created confusion about what actually exists

**Correct approach:**

```markdown
## Job Routing

**Current Implementation:** Heuristic-based routing using if/elif logic (see line 68).

**Planned Enhancement:** Multi-AI consensus routing with 6-model worker analysis (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini) and arbiter synthesis. See issue #XXX.
```

**When documenting:**
1. Grep for the feature in actual code
2. If you find TODO/FIXME/XXX, it's NOT implemented
3. Document current state honestly
4. Put planned features in separate section with issue links

**Related:** [[feedback_fleet_consensus_timing]] - Review DESIGNS before building (catches this earlier)
