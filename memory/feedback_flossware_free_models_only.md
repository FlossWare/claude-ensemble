---
name: flossware-free-models-only
description: FlossWare and Solenopsis GitHub repos must ONLY use free models/APIs — no paid services
metadata: 
  node_type: memory
  type: feedback
  created: 2026-07-30
  priority: critical
  originSessionId: 57827c55-87bc-4cbe-9ad1-d24b7f943c25
  modified: 2026-07-30T21:58:13.879Z
---

# FlossWare / Solenopsis: Free Models Only

When working on FlossWare or Solenopsis GitHub repos, ONLY use truly free models and APIs. Free means $0.00 — not cheap, not paid, not credits-based.

**Why:** These are personal open-source projects. Zero cost — no exceptions.

**How to apply:**
- FlossWare repos (`~/Development/github/FlossWare/`): Free APIs only (PERSONAL_ keys)
- Solenopsis repos (`~/Development/github/solenopsis/`): Free APIs only (PERSONAL_ keys)
- **ALLOWED (genuinely free):** OpenRouter :free models, Groq, Cerebras, Gemini free tier, Mistral free tier, Cloudflare Workers AI, HuggingFace, Cohere free tier, Jina free tier
- **NEVER use:** Red Hat keys (GOOGLE_API_KEY, CURSOR_API_KEY, Vertex)
- **NEVER use:** Any paid/credit-based service (OpenAI, DeepSeek, DeepInfra embeddings, MiniMax, Qwen Cloud paid tier)

## Related

- [[only-free-personal]] — Free tiers only for all personal projects
- [[strict-model-separation]] — Red Hat vs personal key separation
- [[only-free-models]] — Free models for consensus/review
