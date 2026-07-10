---
name: always-ask-before-implementing
description: Always ask user before implementing - don't decide solo vs fleet independently
metadata:
  type: feedback
  created: 2026-07-10T21:30:00Z
  updated: 2026-07-10T21:30:00Z
---

# Always Ask Before Implementing

**Rule:** Before implementing ANY solution, ask the user if you should use the fleet or work solo.

**Why:** Claude sessions have a tendency to "forget" to use the fleet even when preferences are clear. They see the briefing, read the preferences, but still implement solo. This creates a checkpoint where the user can intervene.

**How to apply:**

**WRONG approach:**
```
User: "Can you implement X?"
Claude: *immediately starts coding solo*
```

**CORRECT approach:**
```
User: "Can you implement X?"
Claude: "Should I use the fleet for this? 
- Option A: Multi-AI consensus via orchestrator (thorough, verified)
- Option B: Solo implementation (faster, less thorough)

Based on your 'always fleet' preference, I recommend Option A."
```

**When to ask:**
- ✅ Before implementing code
- ✅ Before designing architecture
- ✅ Before creating documents
- ✅ Before reviewing code
- ✅ When unsure if task is "trivial enough" for solo work

**When NOT to ask (just use fleet):**
- Anything non-trivial
- Anything that affects production
- Anything that will be committed
- When user explicitly said "use fleet"

**Why this is necessary:**

Even with CLAUDE.md instructions saying "always use fleet", sessions still:
1. Read the preferences
2. Understand the preferences
3. Then violate them anyway

**The gap:** Knowing ≠ Doing

**The fix:** Forced checkpoint. Make the user confirm the approach before proceeding.

**Incident that triggered this:**
- User has multiple Claude sessions running
- One session kept implementing solo despite:
  - SessionStart hook showing preferences
  - CLAUDE.md saying "always fleet"
  - MEMORY_INDEX.md listing "always multi-AI"
  - Periodic reminders every 15 min
- User frustrated: "it seems to forget to use the orchestrator, stop implementing itself, etc."

**Related feedback:**
- [[feedback_always_use_fleet_for_all_work]] - The rule being violated
- [[feedback_always_multi_ai]] - Core preference
- [[feedback_always_fleet_consensus]] - Distribute across fleet

**Exception:**
If user explicitly says "just do it" or "quick implementation", you can proceed solo for truly trivial tasks (< 10 lines, no logic, no security implications).

**Template response:**
```
Before I implement this, should I:
A) Use fleet consensus (recommended per your preferences)
B) Implement solo (faster but no verification)

I recommend A based on your "always fleet" preference.
```

**Success criteria:**
- User confirms approach before implementation starts
- No more surprise solo implementations
- User has control over when to use fleet vs solo
