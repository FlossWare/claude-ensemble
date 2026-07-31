---
name: model-classification-redhat-vs-personal
description: Clear delineation of which AI models/APIs are Red Hat approved vs personal-only use
metadata: 
  node_type: memory
  type: reference
  created: 2026-07-30
  priority: critical
  originSessionId: 57827c55-87bc-4cbe-9ad1-d24b7f943c25
  modified: 2026-07-30T21:08:03.600Z
---

# AI Model Classification: Red Hat Approved vs Personal

**Purpose:** Single source of truth for which models can be used on Red Hat proprietary code vs personal projects only.

## Red Hat Approved Models/APIs

These have been approved through official Red Hat channels (data protection agreements, managed licenses, or on-premise).

### Via Claude Code (Google Vertex Agreement)
| Model | ID | Status | Notes |
|---|---|---|---|
| Claude Sonnet | claude-sonnet-4-6 | **CONFIRMED** | Default model |
| Claude Opus | claude-opus-4-8 | **CONFIRMED** | Requires function leader approval (5x cost) |
| Claude Haiku | claude-haiku-4-5 | **CONFIRMED** | Available via Vertex |
| Claude Fable | claude-fable-5 | **CONFIRMED** | Available via Vertex |

### Via Cursor (Red Hat Managed License — "RH - Enterprise", Team ID: 10774657)
**Privacy Mode:** Active (no code training, no code storage, cloud agent limited)
**API tested:** 2026-07-30 — **20 models confirmed available**

| Model ID | Display Name | Provider | Parameters |
|---|---|---|---|
| default | Auto | Cursor router | — |
| grok-4.5 | Cursor Grok 4.5 | xAI | effort, fast |
| composer-2.5 | Composer 2.5 | Cursor (in-house) | fast |
| claude-sonnet-5 | Sonnet 5 | Anthropic | thinking, context, effort |
| claude-sonnet-4-6 | Sonnet 4.6 | Anthropic | thinking, context, effort |
| gpt-5.3-codex | Codex 5.3 | OpenAI | reasoning, fast |
| gpt-5.4 | GPT-5.4 | OpenAI | context, reasoning, fast |
| claude-opus-4-6 | Opus 4.6 | Anthropic | thinking, context, effort |
| claude-opus-4-5 | Opus 4.5 | Anthropic | thinking |
| gpt-5.2 | GPT-5.2 | OpenAI | reasoning, fast |
| gemini-3.1-pro | Gemini 3.1 Pro | Google | — |
| gpt-5.4-mini | GPT-5.4 Mini | OpenAI | reasoning |
| gpt-5.4-nano | GPT-5.4 Nano | OpenAI | reasoning |
| claude-haiku-4-5 | Haiku 4.5 | Anthropic | thinking |
| claude-sonnet-4-5 | Sonnet 4.5 | Anthropic | thinking, context |
| gpt-5.1 | GPT-5.1 | OpenAI | reasoning |
| gemini-3-flash | Gemini 3 Flash | Google | — |
| claude-sonnet-4 | Sonnet 4 | Anthropic | thinking, context |
| gpt-5-mini | GPT-5 Mini | OpenAI | — |
| gemini-2.5-flash | Gemini 2.5 Flash | Google | — |

**By provider:**
- **Anthropic (6):** Sonnet 5, Sonnet 4.6, Sonnet 4.5, Sonnet 4, Opus 4.6, Opus 4.5, Haiku 4.5
- **OpenAI (6):** GPT-5.4, GPT-5.4 Mini, GPT-5.4 Nano, GPT-5.3 Codex, GPT-5.2, GPT-5.1, GPT-5 Mini
- **Google (3):** Gemini 3.1 Pro, Gemini 3 Flash, Gemini 2.5 Flash
- **xAI (1):** Grok 4.5
- **Cursor (2):** Auto, Composer 2.5
- **Not available:** Fable 5, Fusion (Tab-only, not selectable)

### Via Red Hat Gemini API (CONFIRMED 2026-07-30)
**Project:** `itpc-gcp-uie-eng-claude` | **Key:** `REDACTED_RH_GEMINI_KEY`
| Model | Status |
|---|---|
| gemini-2.5-flash | **CONFIRMED** |
| gemini-2.5-pro | **CONFIRMED** |
| gemini-3-pro-preview | **CONFIRMED** |
| gemini-3-flash-preview | **CONFIRMED** |
| gemini-3.1-pro-preview | **CONFIRMED** |
| gemini-2.5-flash-lite | **CONFIRMED** |
| gemma-4-26b-a4b-it | **CONFIRMED** |
| gemma-4-31b-it | **CONFIRMED** |

### Via Models.corp Sandbox (Experimentation Only)
| Model | Status | Notes |
|---|---|---|
| Granite | Available | Red Hat's own model |
| Mistral | Available | Sandbox only, not production |
| Gemini | Available | Sandbox only, not production |

### On-Premise / Local (Always Safe)
| Model | Platform | Node(s) |
|---|---|---|
| starcoder2:7b | Ollama | Fleet nodes |
| sqlcoder:7b | Ollama | Fleet nodes |
| mathstral:7b | Ollama | Fleet nodes |
| wizardlm2:7b | Ollama | Fleet nodes |
| openchat:7b | Ollama | Fleet nodes |
| zephyr:7b | Ollama | Fleet nodes |
| gemma3:4b | Ollama | Fleet nodes |
| phi3.5:3.8b | Ollama | Fleet nodes |
| stablelm-zephyr:3b | Ollama | Fleet nodes |
| Llama 3.1 8B | GGUF | Fleet nodes |
| Llama 3.3 70B | GGUF | Fleet nodes |
| Phi-4 14B | GGUF | Fleet nodes |
| Gemma 2 27B | GGUF | Fleet nodes |
| Mixtral 8x7B | GGUF | Fleet nodes |
| Qwen 2.5 Coder 32B | GGUF | Fleet nodes |
| QwQ 32B | GGUF | Fleet nodes |
| nomic-embed-text | Ollama | Embeddings |
| granite-embedding | Ollama | Embeddings |

**Total Red Hat confirmed:** 4 (Claude Code) + 20 (Cursor) + 8 (Gemini API) + 18 (local) = **50 models**

---

## Personal-Only Models/APIs

These are accessed through personal API keys and must NEVER be used on Red Hat proprietary code.

### Personal API Keys (from aio-01:5000/secrets)
| Provider | API Key | Models | Notes |
|---|---|---|---|
| OpenRouter | PERSONAL_OPENROUTER_API_KEY | 500+ models (26 free) | Personal account, aggregator |
| OpenAI | PERSONAL_OPENAI_API_KEY | GPT-4o, GPT-5.x | Personal key |
| Google | GOOGLE_API_KEY | Gemini Pro/Flash | **Personal free-tier** (NOT Red Hat's) |
| Groq | PERSONAL_GROQ_API_KEY | Llama 3.3 70B | Personal, ultra-fast inference |
| Cerebras | PERSONAL_CEREBRAS_API_KEY | Llama 3.1 70B/8B | Personal, fast inference |
| DeepSeek | PERSONAL_DEEPSEEK_API_KEY | DeepSeek V4 | Personal key |
| Mistral | PERSONAL_MISTRAL_API_KEY | Mistral models | Personal key |
| Cohere | PERSONAL_COHERE_API_KEY | Command models | Personal key |
| Cloudflare | PERSONAL_CLOUDFLARE_API_KEY | Workers AI models | Personal account |
| Jina | PERSONAL_JINA_API_KEY | Embeddings/reranking | Personal key |
| VoyageAI | PERSONAL_VOYAGEAI_API_KEY | Embeddings | Personal key |

**Total personal-only providers:** 11
**Total personal-only models:** 500+ (via OpenRouter alone)

---

## Decision Matrix

```
Is it Red Hat proprietary code?
├── YES → Use ONLY:
│   ├── Claude Code (Vertex): Sonnet, Opus*, Haiku, Fable
│   ├── Cursor (RH license): [TEST which models are enabled]
│   ├── Red Hat Gemini API: [SETUP needed]
│   ├── Models.corp sandbox: Granite, Mistral, Gemini (experiment only)
│   └── Local models: 18 Ollama/GGUF models
│   
│   * Opus requires function leader approval
│
└── NO (personal project) → Use ALL:
    ├── Everything above, PLUS
    ├── OpenRouter (500+ models, 26 free)
    ├── Personal OpenAI, Google, Groq, Cerebras, DeepSeek, etc.
    └── Any model available through any provider
```

## Testing Results (2026-07-30)

**API test confirmed 20 models available** under Red Hat's Cursor "RH - Enterprise" license.
All models listed above are accessible via the Cursor API.

## Action Items

- [ ] Get Red Hat's Gemini API key (separate from personal GOOGLE_API_KEY)
- [ ] Test Cursor model availability under RH license
- [ ] Contact Velocity AI if production API access needed beyond code assistance
- [ ] Update fleet router to tag models as redhat-approved vs personal-only

## Related

- [[redhat-ai-compliance]] — Full compliance rules and contacts
- [[multi-ai-providers]] — All provider configurations (needs RH/personal tags added)
- [[feedback_gemini_not_redhat_supported]] — Personal Google key excluded; RH Gemini API is separate
