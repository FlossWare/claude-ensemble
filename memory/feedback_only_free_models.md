---
name: only-free-models
description: Only use free AI models for review/consensus — no paid model usage
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 87f86bea-63f4-4075-afa5-1899ccbce831
  modified: 2026-07-29T01:59:59.712Z
---

Only use free models for multi-AI review and consensus.

**Why:** Cost control — user wants maximum model coverage without spending money.

**How to apply:** When doing multi-AI review via orchestrator or fleet, restrict to free-tier models only (OpenRouter free models, Groq free tier, Cerebras free tier, Google free tier). Do not use paid API calls for review.

Related: [[feedback_always_multi_ai]], [[feedback_stop_limiting_models_use_maximum]]
