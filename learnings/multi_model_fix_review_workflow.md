---
name: multi-model-fix-review-workflow
description: Global standard - always use multi-model fix followed by multi-model review with rotated agents
metadata:
  type: feedback
  scope: global
---

# Multi-Model Fix and Review Workflow (Global Standard)

Always follow this two-step workflow when fixing issues across all projects:

## Workflow Steps

1. **Multi-model fix** - Use workflow with multiple AI models to analyze and fix the issue
2. **Multi-model review** - After applying the fix, immediately launch a multi-model review workflow to verify it

## Critical Rule: Agent Rotation

**DO NOT use the same models/agents in both workflows**

- Fix workflow uses set A of workers + arbiter X
- Review workflow uses set B of workers + arbiter Y
- This avoids confirmation bias - reviewers won't rubber-stamp their own fix
- Forces fresh perspective on the solution

**Why:** User wants high confidence in fixes through adversarial verification. Single-model fixes can miss edge cases or introduce subtle bugs. Multi-model consensus with rotated agents catches these before they reach production.

## Example Pattern

```
1. Issue reported → Multi-agent diagnostic & fix workflow
   - Workers: Domain Expert A, Domain Expert B, Domain Expert C
   - Arbiter: Claude Sonnet 4.5
   - Output: Proposed fix with consensus
   
2. Fix applied → Multi-agent review workflow (DIFFERENT AGENTS!)
   - Workers: Different Expert D, Different Expert E, Different Expert F
   - Arbiter: Claude Opus 4.8 or different model
   - Output: Verification with adversarial testing
   
3. Results → Report consensus verdict with vote breakdown
   - Which agents approved/rejected
   - Reasoning from each perspective
   - Final confidence level
```

## Agent Rotation Strategies

- **Vary expertise focus** between fix and review
- **Use different model tiers** (Sonnet for fix, Opus for review, or vice versa)
- **Ensure no agent appears in both workflows** for the same issue
- **Adversarial skeptics** in review phase should actively try to break the fix

## When to Apply

- **All substantive fixes** - CI/CD, code, configuration, infrastructure
- **Security changes** - always multi-model with extra scrutiny
- **Production deployments** - consensus required before push
- **Complex refactors** - architectural decisions benefit from multiple perspectives

Trivial changes (typos, comments, formatting) can skip multi-model but still benefit from quick review.

## How to Apply

When user reports an issue or asks for a fix:
1. Use Workflow tool with multiple agents to diagnose and fix
2. Apply the consensus fix
3. Immediately launch review workflow with DIFFERENT agents and arbiter
4. Document which models agreed/disagreed and the consensus verdict
5. Report final verdict with vote breakdown to user
6. Never skip the review step

This is the standard for all AI-assisted work.
