---
name: strict-model-separation
description: NEVER use Red Hat approved models/keys for personal projects — strict separation between work and personal
metadata: 
  node_type: memory
  type: feedback
  created: 2026-07-30
  priority: critical
  originSessionId: 57827c55-87bc-4cbe-9ad1-d24b7f943c25
  modified: 2026-07-30T21:37:28.942Z
---

# Strict Model Separation: Red Hat vs Personal

NEVER use Red Hat approved models or API keys for personal projects.

**Why:** User wants clean separation — Red Hat resources for Red Hat work only, personal keys for personal work. No cross-contamination.

**How to apply:**
- Red Hat projects (`~/Development/redhat/`): Use ONLY Red Hat approved keys (Cursor RH-Enterprise, Gemini from itpc-gcp-uie-eng-claude, Claude Code via Vertex, local models)
- Personal projects (`~/Development/personal/`, `~/Development/github/`): Use ONLY personal API keys (personal GOOGLE_API_KEY, OpenRouter, Groq, Cerebras, DeepSeek, etc.)
- The model-compliance-enforcer.js already blocks non-approved models on Red Hat paths — now also enforce the REVERSE: no Red Hat keys on personal paths

## Naming Convention (2026-07-30)

All personal API keys use `PERSONAL_` prefix in env vars, auth.secrets, and code references.
Red Hat / infrastructure keys have NO prefix.

## Key Assignments

| Key | Use For |
|---|---|
| `GOOGLE_API_KEY` (AIzaSyDSNC5c...) | Red Hat work ONLY |
| `PERSONAL_GOOGLE_API_KEY` (AIzaSyBh7...) | Personal projects ONLY |
| `CURSOR_API_KEY` | Red Hat work ONLY |
| Claude Code (Vertex) | Red Hat work ONLY |
| `PERSONAL_OPENROUTER_API_KEY` | Personal projects ONLY |
| `PERSONAL_GROQ_API_KEY` | Personal projects ONLY |
| `PERSONAL_CEREBRAS_API_KEY` | Personal projects ONLY |
| `PERSONAL_DEEPSEEK_API_KEY` | Personal projects ONLY |
| `PERSONAL_MISTRAL_API_KEY` | Personal projects ONLY |
| All other `PERSONAL_*` keys | Personal projects ONLY |

## Related

- [[redhat-ai-compliance]] — Red Hat model restrictions
- [[model-classification-redhat-vs-personal]] — Full model delineation
