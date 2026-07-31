---
name: daily-model-discovery
description: Free model discovery should run DAILY across all providers — user expected this was already automated
metadata: 
  node_type: memory
  type: feedback
  created: 2026-07-30
  priority: critical
  originSessionId: 57827c55-87bc-4cbe-9ad1-d24b7f943c25
  modified: 2026-07-30T21:54:08.395Z
---

# Daily Free Model Discovery

User expected free model discovery to run daily across all personal providers. It wasn't — last run was July 16 (2 weeks stale).

**Why:** Model landscape changes fast. New free models appear on OpenRouter, Groq, Cerebras, etc. regularly. Missing them means missed capability.

**How to apply:**
- Automate daily sweep of ALL personal providers: OpenRouter, Groq, Cerebras, Mistral, Cohere, DeepInfra, HuggingFace, Cloudflare, Gemini, OpenAI
- Store results in PostgreSQL for tracking changes over time
- Alert on new free models discovered
- Script: `scripts/discover-all-free-models.sh` (exists but not cron'd)

## Related

- [[only-free-models]] — Only free models for consensus
- [[only-free-personal]] — Only free tiers for personal projects
