---
name: memory-first-decision-making
description: ALWAYS consult memory FIRST for ALL major decisions, not just info retrieval
metadata:
  type: feedback
  priority: CRITICAL
---

# Memory-First Decision Making

## The Rule

**BEFORE any major action or decision, ALWAYS read relevant memory files FIRST.**

This is not optional. Not "if you have time." Not "when you think to." **ALWAYS.**

Major actions include:
- Launching arbiter-worker reviews
- Making architectural decisions
- Planning multi-step tasks
- Choosing models/approaches
- Any decision affecting code or direction

## Why

Memory contains:
- Rules learned from past mistakes
- Proven patterns that work
- Anti-patterns to avoid
- Context from prior sessions

If you don't consult memory FIRST, you:
- Repeat the same mistakes (like asking workers to review summaries without code)
- Ignore proven rules (like "arbiters and workers MUST have code access")
- Waste time on approaches already proven wrong
- Frustrate the user by making preventable errors

## How to Apply

**FIRST:** Read memory relevant to the task
**THEN:** Base your decision on what you learned
**THEN:** Act with that context
**FINALLY:** Save any new lessons

Example:
- Task: Review code with arbiters
- Check memory → find "arbiters MUST have code access"
- Apply rule → provide code to all arbiters and workers
- Don't launch blind

## What This Fixes

User has said "this is getting old" about repeating mistakes. This is the fix: memory-first decision making ensures you DON'T repeat, because you're consulting the record of what failed before.

Decision-making power must be informed by past actions. That's what memory is for.
