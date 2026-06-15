---
name: always-multi-ai-review-before-commit
description: ALWAYS run multi-AI consensus review before committing ANY code changes
metadata: 
  node_type: memory
  type: feedback
  created: 2026-06-14
  priority: critical
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

**ALWAYS run multi-AI review before committing code changes.**

**Why:** Catches issues, ensures quality, gets diverse perspectives before changes are permanent.

**How to apply:**
1. Make code changes
2. **STOP** - do NOT commit yet
3. Run 6-model consensus review workflow (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini)
4. Wait for arbiter decision: APPROVE_COMMIT, REJECT, or NEEDS_WORK
5. **Only if APPROVE_COMMIT:** commit, push, close issue
6. **If NEEDS_WORK:** fix issues, re-review
7. **If REJECT:** don't commit, investigate alternative approach

**No exceptions** - even "small" fixes get reviewed.

**Review workflow pattern:**
```javascript
// 6 workers review in parallel
const reviews = await parallel([
  fable, opus, sonnet, haiku, gpt4o, gemini
])

// Arbiter synthesizes
const decision = await agent('Synthesize reviews', {
  model: 'fable',
  schema: { final_decision: 'APPROVE_COMMIT|REJECT|NEEDS_WORK' }
})
```

**What gets reviewed:**
- Code changes (scripts, services, configs)
- Infrastructure changes (systemd services, cron jobs)
- Workflow implementations
- Bug fixes
- Everything

Related: [[feedback_fleet_consensus_timing]] - Review DESIGNS before building (6:1 ROI)
