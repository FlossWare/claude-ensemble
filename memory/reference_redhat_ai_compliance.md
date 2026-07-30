---
name: redhat-ai-compliance
description: Red Hat proprietary code AI model restrictions - Approved tools and models for Red Hat work
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-14
  updated: 2026-07-30
  priority: critical
  originSessionId: 57827c55-87bc-4cbe-9ad1-d24b7f943c25
  modified: 2026-07-30T20:15:47.471Z
---

# Red Hat AI Model Compliance

**CRITICAL:** Red Hat proprietary code has strict AI model restrictions. Models must be accessed through Red Hat-approved tools/agreements only.

## Approved AI Tools at Red Hat (as of 2026-07-30)

Per official emails from Josh Boyer, Bill Ryan, and Marco Bill:

### 1. Cursor IDE (Managed License)
- **Access:** Submit [intake form](https://docs.google.com/forms/d/e/1FAIpQLSdReAQc1yRWdKoklfc41L3U-qsdv0B7LtKDH8O2_5QsjNyoyg/viewform)
- **Team:** "RH - Enterprise" (Team ID: 10774657)
- **Privacy Mode:** Active (no code training, no code storage, cloud agent/some features limited)
- **Available models (pending verification):**
  - Claude Sonnet 4.5, Opus 4.7/4.8, Fable 5 (Anthropic)
  - GPT-5, GPT-5.5, GPT-5.3 Codex, GPT-5.6 Terra/Luna (OpenAI)
  - Gemini 3 Pro, 3.5 Flash (Google)
  - Grok 4.5, Grok Build (xAI)
  - Composer 2.5, Fusion (Cursor in-house)
- **Status:** NEEDS TESTING — verify which models are actually enabled under RH license
- **Support:** #help-rh-code-assist, #forum-pge-cloud-ops, pge-cloudops@redhat.com
- **Regional restrictions:** Germany, France, Austria, Netherlands pending; China/Crimea/Donetsk/Luhansk blocked; Spain cleared

### 2. Claude Code (via Google Vertex)
- **Access:** Submit [form](https://docs.google.com/forms/d/e/1FAIpQLSdIphsk9TlTR-TPSsk9xiNLqmgSCJJ2BLTOWLMM667X1vmsMg/viewform), P+GE and IT only
- **Models:** Sonnet (default), Opus (requires function leader approval due to 5x cost)
- **Hosted by:** Google under Red Hat data protection agreement
- **Note:** Claude Code can also run INSIDE Cursor for a combined environment
- **Restriction:** Only approved for code assistance use cases. Other uses require AI Assessment (AIA)

### 3. Gemini API
- **Access:** Available for code assistant use cases
- **Source page:** [GCP Gemini API](https://source.redhat.com/departments/it/datacenter_infrastructure/itcloudservices/itpubliccloudpage/cloud/gcp/gcpgeminiapi)

### 4. Models.corp Sandbox (Experimentation)
- **Models:** Granite, Mistral, Gemini endpoints
- **Duration:** Up to 3 weeks
- **Purpose:** Experimentation and proof-of-concept only, NOT production
- **Policy:** [AI sandbox acceptable use policy](https://source.redhat.com/projects_and_programs/ai/wiki/acceptable_use_policy__ai_experimentation)

### 5. MOSAIC Sandbox (OpenShift AI)
- **Purpose:** Build, deploy, and manage AI applications
- **Duration:** Up to 3 weeks

### 6. Production API Access
- **Requirement:** Contact [Velocity AI](https://redhat.service-now.com/help?id=sc_cat_item&sys_id=01dd108e1b715650b6ccea45624bcbae) for production use of model APIs (Gemini, Claude, etc.) outside sandboxes or approved code assistant use cases

## ✅ CONFIRMED Allowed Models for Red Hat Code

### Via Claude Code (Vertex)
- **Sonnet** (claude-sonnet-4-6) — default
- **Opus** (claude-opus-4-8) — requires function leader approval
- **Haiku** (claude-haiku-4-5) — available via Vertex
- **Fable** (claude-fable-5) — available via Vertex

### Via Cursor (PENDING VERIFICATION)
- All Cursor models potentially available under RH managed license
- **Must test** which models are actually enabled vs restricted
- Could significantly expand Red Hat-compliant model count

### Local Models (On-Premise, Always Safe)

#### Ollama Models (9)
- starcoder2:7b, sqlcoder:7b, mathstral:7b, wizardlm2:7b
- openchat:7b, zephyr:7b, gemma3:4b, phi3.5:3.8b, stablelm-zephyr:3b

#### Downloaded GGUF Models (7)
- Llama 3.1 8B, Llama 3.3 70B, Phi-4 14B, Gemma 2 27B
- Mixtral 8x7B, Qwen 2.5 Coder 32B, QwQ 32B

#### Local Embedding Models (2)
- nomic-embed-text:latest, granite-embedding:latest

## ❌ BLOCKED (Without Approved Tool)

Using these providers **directly with personal API keys** for Red Hat proprietary code is NOT allowed:
- ❌ OpenAI direct API
- ❌ Google direct API
- ❌ DeepSeek
- ❌ Cerebras
- ❌ OpenRouter
- ❌ Cloudflare Workers AI

**However:** If accessed THROUGH an approved tool (Cursor, Claude Code, Gemini API), they may be covered under Red Hat's data protection agreements. This is the key distinction.

## Key Contacts

- **PCO (PGE Cloud Ops):** pge-cloudops@redhat.com
- **Velocity AI:** For production API access outside approved code assistant use cases
- **Slack:** #help-rh-code-assist, #forum-pge-cloud-ops
- **Tickets:** devservices.dpp.openshift.com/support/ (VPN required)

## Implementation Rules

### Workflow Separation
```javascript
// RED HAT workflow — use only approved-tool models
const redhatWorkflow = {
  approvedTools: ['cursor', 'claude-code', 'gemini-api'],
  models: ['fable', 'opus', 'sonnet', 'haiku'], // confirmed
  cursorModels: ['TBD - pending verification'],   // test which are enabled
  localModels: [...OLLAMA_MODELS, ...GGUF_MODELS],
  metadata: { proprietary: 'RED_HAT', compliance: 'enforced' }
}

// PERSONAL workflow (GitHub repos)
const personalWorkflow = {
  models: [...ALL_MODELS], // All 500+ models allowed
  metadata: { proprietary: 'PERSONAL' }
}
```

## Related

- [[feedback_always_multi_ai]] - Multi-AI consensus (adapt for Red Hat compliance)
- [[reference_multi_ai_providers]] - Full model inventory
- [[feedback_always_max_parallelism]] - Still applies, just use safe models only
- [[feedback_gemini_not_redhat_supported]] - OUTDATED: Gemini IS now approved via Cursor and Gemini API
