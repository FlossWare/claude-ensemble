---
name: always-use-fleet-for-all-work
description: User requires fleet usage for ALL work, including implementation tasks
metadata:
  type: feedback
  created: 2026-07-10T16:45:00Z
  updated: 2026-07-10T16:45:00Z
---

# Always Use Fleet for All Work

User corrected me when I implemented auto-memory-saver.js solo without using the fleet.

**Rule:** Always use fleet for ALL work, including:
- Design tasks
- Implementation (writing scripts/code)
- Review tasks
- Documentation
- Architecture decisions

**Why:** User has distributed fleet infrastructure (9 nodes, 200+ models) specifically for multi-AI consensus. Solo work violates the "always multi-AI" preference.

**How to apply:** Before starting ANY task, use orchestrator (aio-01:5000) to distribute work across fleet with multi-AI consensus.

**Incident that triggered this memory:**
- Task: Implement auto-memory-saver system
- What I did: Solo implementation (just Claude Sonnet)
- What I should have done: Fleet consensus on design, multi-AI review of scripts
- User's correction: "why was the fleet not used?"

**Related memories:** 
- [[feedback_always_multi_ai]]
- [[feedback_always_fleet_consensus]]
- [[reference_orchestrator_usage]]
- [[feedback_always_verify_before_documenting]]
