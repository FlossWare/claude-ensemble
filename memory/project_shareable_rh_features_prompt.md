---
name: shareable-rh-features-prompt
description: Create shareable prompt for Thompson Sampling + Memory + Compression + Caching once stable
metadata:
  type: project
---

# Shareable RH Features Prompt (Pending Stability)

## Status

Implementing 4 RH cost-optimization features in Phase 1 Create:
1. **Thompson Sampling** (model selection router)
2. **Memory improvements** (TF-IDF semantic search)
3. **Prompt compression** (token reduction)
4. **Prompt caching** (90% cheaper cached tokens)

All in Phase 1 Create as of 2026-09-25. Pending Phase 2 verification and Phase 1/2 Review.

## Deliverable (When Stable)

Create a single, comprehensive prompt that a friend can use with their Claude to implement all 4 features.

**Prompt should include:**
- Architecture overview for each feature
- Implementation patterns and gotchas we discovered
- Code patterns and module design
- Integration points with existing systems
- Success metrics and testing approach
- Phase 1/2 review findings and how to avoid blockers

## Why This Matters

These 4 features together provide:
- **Cost savings:** 50%+ reduction in token costs (compression + caching)
- **Quality:** Thompson routing improves model selection (cheaper + better)
- **DX:** Memory system makes Claude more useful (context persistence + search)

Shareable prompt lets others replicate this without rediscovering the same pitfalls.

## Timeline

- Implement: Phase 1 Create (in progress)
- Verify: Phase 2 Create (pending)
- Review: Phase 1/2 Review (pending)
- Document: Once all 4 phases stable + tested

**Target:** Have shareable prompt ready by end of week if all reviews pass.
