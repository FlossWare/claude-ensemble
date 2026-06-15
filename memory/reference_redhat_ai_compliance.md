---
name: redhat-ai-compliance
description: Red Hat proprietary code AI model restrictions - ONLY Anthropic + Local models allowed
metadata:
  type: reference
  created: 2026-06-14
  priority: critical
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Red Hat AI Model Compliance

**CRITICAL:** Red Hat proprietary code (disseminator, etc.) has strict AI model restrictions.

## ✅ ALLOWED Models for Red Hat Code (22 total)

### Anthropic Cloud Models (4)
- **Fable** (claude-fable-5)
- **Opus** (claude-opus-4-8)
- **Sonnet** (claude-sonnet-4-6)
- **Haiku** (claude-haiku-4-5)

**Access:** Via Vertex AI with data sharing enabled for Anthropic publisher

### Local Ollama Models (9)
- **starcoder2:7b** (code specialist)
- **sqlcoder:7b** (data specialist)
- **mathstral:7b** (reasoning specialist)
- **wizardlm2:7b** (complex patterns)
- **openchat:7b** (general)
- **zephyr:7b** (structure)
- **gemma3:4b** (lightweight)
- **phi3.5:3.8b** (lightweight)
- **stablelm-zephyr:3b** (ultra-light)

### Local Downloaded GGUF Models (7)
- **Llama 3.1 8B**
- **Llama 3.3 70B**
- **Phi-4 14B**
- **Gemma 2 27B**
- **Mixtral 8x7B**
- **Qwen 2.5 Coder 32B**
- **QwQ 32B**

### Local Embedding Models (2)
- **nomic-embed-text:latest**
- **granite-embedding:latest**

## ❌ BLOCKED Models for Red Hat Code

### External APIs (NOT ALLOWED)
- ❌ **OpenAI:** GPT-4o, GPT-4 Turbo, GPT-3.5 (all models)
- ❌ **Google:** Gemini Pro, Gemini Flash (all models)
- ❌ **DeepSeek:** deepseek-v4-flash, deepseek-v4-pro (all models)
- ❌ **Cerebras:** gpt-oss-120b, zai-glm-4.7 (all models)
- ❌ **OpenRouter:** ALL models (even free ones)
- ❌ **Cloudflare Workers AI:** ALL models

**Reason:** Red Hat compliance - proprietary code cannot be sent to these vendors' APIs

## Why Local Models Are Safe

**Local = On-Premise = No External API Calls**

1. **Ollama models** run entirely on fleet nodes (laptop-01, server-01, server-02, server-03, aio-01)
2. **GGUF models** run via llama.cpp/Ollama locally
3. **Zero network egress** - code never leaves your infrastructure
4. **Red Hat compliant** - data stays on-premise
5. **Privacy guaranteed** - runs on your hardware

## Implementation Rules

### Workflow Separation
```javascript
// RED HAT workflow (disseminator, etc.)
const redhatWorkflow = {
  models: ['fable', 'opus', 'sonnet', 'haiku'], // Anthropic only
  localModels: [...OLLAMA_MODELS, ...GGUF_MODELS], // All 18 local
  chromadb: 'redhat_disseminator_embeddings',
  metadata: { proprietary: 'RED_HAT', compliance: 'enforced' }
}

// PERSONAL workflow (GitHub repos)
const personalWorkflow = {
  models: [...ALL_MODELS], // All 40+ models allowed
  chromadb: 'personal_repos_embeddings',
  metadata: { proprietary: 'PERSONAL' }
}
```

### ChromaDB Collections
- **redhat_disseminator_embeddings** - Red Hat proprietary (embeddings via LOCAL nomic-embed only)
- **personal_repos_embeddings** - Personal repos (all embedding models allowed)

**NEVER mix collections!**

### Fine-Tuning Datasets
- **Red Hat:** Training data for LOCAL Ollama/GGUF models ONLY
- **Personal:** Training data can use any models

### Multi-AI Review
- **Red Hat code:** Use 4 Anthropic + 18 local = 22 models (99% confidence)
- **Personal code:** Use all 40+ models (98%+ confidence)

## Repository Paths

### Red Hat Proprietary (RESTRICTED)
- `~/Development/redhat/scm/gitlab/cee/sfloess/disseminator`
- `~/Development/redhat/scm/gitlab/cee/sfloess/*` (all GitLab repos)

**Rule:** Use ONLY Anthropic + Local models

### Personal (UNRESTRICTED)
- `~/Development/personal/scm/github/solenopsis`
- `~/Development/personal/scm/github/FlossWare`

**Rule:** All 40+ models allowed

## Confidence Levels with Safe Models

**22 models (Red Hat compliant):**
- **18+ models agree:** ULTRA-HIGH confidence (99%)
- **13-17 models agree:** HIGH confidence (97%)
- **10-12 models agree:** MEDIUM confidence (93%)

**Still better than 6-model consensus (95%)!**

## How to Apply

1. **Check repo path** - Red Hat GitLab vs Personal GitHub?
2. **Set model list** - 22 safe models vs 40+ all models?
3. **Create separate ChromaDB collection** - redhat_* vs personal_*
4. **Mark metadata** - RED_HAT_PROPRIETARY flag
5. **Fine-tune locally only** - For Red Hat data, use LOCAL models only

## Violation Prevention

**Before launching workflow:**
- [ ] Check repo path (~/Development/redhat/ = RESTRICTED)
- [ ] Verify model list (OpenAI/Google/DeepSeek NOT in list for Red Hat)
- [ ] Confirm ChromaDB collection separation
- [ ] Validate metadata flags (RED_HAT_PROPRIETARY)

## Related

- [[feedback_always_multi_ai]] - Multi-AI consensus (adapt for Red Hat compliance)
- [[reference_multi_ai_providers]] - Full model inventory (mark which are Red Hat safe)
- [[feedback_always_max_parallelism]] - Still applies, just use safe models only
