---
name: reference-free-ai-models-tracker
description: ClawLabsAI/free-ai-models — daily-updated tracker of 21 free AI model APIs (OpenRouter + Pollinations)
metadata:
  type: reference
---

**Source:** https://github.com/ClawLabsAI/free-ai-models
**Data file:** https://raw.githubusercontent.com/ClawLabsAI/free-ai-models/main/data/models.json
**Updated:** Daily (automated)

Tracks 21 free AI models from 2 sources: OpenRouter (17 models) and Pollinations AI (4 models).

**New providers discovered (2026-07-30):**

1. **Pollinations AI** — No auth required, unlimited rate limit
   - Endpoint: `https://text.pollinations.ai/openai/chat/completions`
   - Model: `openai-fast` (GPT-OSS 20B via OVH)
   - OpenAI-compatible, no API key needed
   - Legacy API; new API at enter.pollinations.ai for authenticated users

2. **ZeroLimitAI** — Free API key (100 calls/day, 7-day trial)
   - Endpoint: `https://www.zerolimitai.com/api/v1/chat/completions`
   - Model: `auto` (ZeroOptimize routes to best free model)
   - Signup: zerolimitai.com/register (no credit card)

**New OpenRouter free models added:**
- `inclusionai/ling-3.0-flash:free` — 262K context, text
- `poolside/laguna-s-2.1:free` — 262K context, text

**How to apply:** Check this tracker periodically for new free models to add to the fleet roster. The JSON data file can be fetched and diffed against our current model list automatically.
