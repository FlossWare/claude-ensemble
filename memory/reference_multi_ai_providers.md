---
name: multi-ai-providers
description: AI provider endpoints and configuration for multi-AI consensus workflows
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-14
  priority: high
  originSessionId: 39a38f09-c545-4579-9ac1-6c31a694eba2
---

# Multi-AI Provider Configuration

**Purpose:** Enable multi-AI consensus with maximum coverage across different AI providers for arbiter/worker patterns

## Available AI Providers

### 1. Anthropic Claude (Primary)
- **Models:** Opus 4.8, Sonnet 4.6, Haiku 4.5
- **Access:** Direct API + Vertex AI
- **Use:** Primary arbiter, high-quality workers

### 2. OpenAI
- **Models:** GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo
- **API Key:** Stored in [[.secrets]]
- **Endpoint:** https://api.openai.com/v1
- **Use:** Diversity in multi-model consensus

### 3. Google Gemini
- **Models:** Gemini Pro, Gemini Flash
- **Access:** Via Vertex AI
- **Use:** Alternative perspective in consensus

### 4. OpenRouter (Aggregator)
- **Access:** Aggregates 100+ models from multiple providers
- **API Key:** Stored in [[.secrets]]
- **Endpoint:** https://openrouter.ai/api/v1
- **Free Models:** 26 models with $0 pricing (NVIDIA Nemotron 550B/120B/30B, Google Gemma 4 31B/26B, Qwen 3 Next 80B, Liquid LFM 2.5, etc.)
- **Paid Models:**
  - Claude (Anthropic)
  - GPT-4 (OpenAI)
  - Llama (Meta)
  - Mistral, DeepSeek, Qwen, etc.
- **Use:** Access to models not directly available, cost optimization, 26 FREE high-quality models

### 5. Cerebras Inference
- **Access:** Ultra-fast inference (1800+ tok/s)
- **API Key:** Stored in [[.secrets]]
- **Endpoint:** https://api.cerebras.ai/v1
- **Available Models:**
  - Llama 3.1 70B
  - Llama 3.1 8B
- **Use:** Speed-critical tasks, real-time processing

### 6. Cloudflare Workers AI
- **Access:** Serverless AI inference
- **Credentials:** Account ID + API Key in [[.secrets]]
- **Endpoint:** https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}
- **Available Models:**
  - Llama 2/3
  - Mistral 7B
  - CodeLlama
  - Embeddings models
- **Use:** Fast, low-latency inference for specific models

### 7. Local Fleet (Ollama + GGUF)
- **Platforms:** Ollama, llama.cpp, LocalAI, etc.
- **Models:** 27 Ollama models + 7 GGUF models on fleet
- **Servers:** server-01/02/03, laptop-01, aio-01
- **Use:** Privacy, no API costs, offline capability

## Multi-AI Consensus Patterns

### Pattern 1: Maximum Diversity (7+ models)
```javascript
const providers = [
  { provider: 'anthropic', model: 'claude-opus-4.8' },      // Arbiter
  { provider: 'anthropic', model: 'claude-sonnet-4.6' },
  { provider: 'openai', model: 'gpt-4o' },
  { provider: 'google', model: 'gemini-pro' },
  { provider: 'cerebras', model: 'llama-3.1-70b' },         // Ultra-fast
  { provider: 'openrouter', model: 'meta-llama/llama-3.1-70b' },
  { provider: 'cloudflare', model: 'llama-3-8b' }
]
```

### Pattern 2: Free-Only (OpenRouter Free + Local)
```javascript
const providers = [
  { provider: 'openrouter', model: 'nvidia/nemotron-3-super-120b-a12b:free' }, // Arbiter (FREE!)
  { provider: 'openrouter', model: 'google/gemma-4-31b-it:free' },
  { provider: 'openrouter', model: 'qwen/qwen3-next-80b-a3b-instruct:free' },
  { provider: 'local', model: 'mixtral:8x7b' },
  { provider: 'local', model: 'qwen2.5-coder:32b' },
  { provider: 'local', model: 'deepseek-r1:32b' }
]
// Zero API costs, all FREE models!
```

### Pattern 3: Cost-Optimized (Mix Paid + Free)

```javascript
const providers = [
  { provider: 'anthropic', model: 'claude-sonnet-4.6' }, // Arbiter (paid)
  { provider: 'openrouter', model: 'nvidia/nemotron-3-super-120b-a12b:free' }, // FREE
  { provider: 'openrouter', model: 'google/gemma-4-31b-it:free' },              // FREE
  { provider: 'local', model: 'mixtral:8x7b' }                                   // FREE
]
// Low cost: only arbiter is paid
```

### Pattern 4: Local-First (Privacy)
```javascript
const providers = [
  { provider: 'local-ollama', model: 'deepseek-r1:32b', node: 'server-03' },
  { provider: 'local-ollama', model: 'codestral:22b', node: 'server-02' },
  { provider: 'local-gguf', model: 'mixtral-8x7b-q4', platform: 'llama.cpp' },
  { provider: 'local-gguf', model: 'qwq-32b-q4', platform: 'llama.cpp' }
]
```

## Configuration Files

**API Keys Location:** `~/.claude/projects/-home-sfloess/memory/.secrets.md`

**Environment Variables (from ~/.bashrc):**
- `PERSONAL_OPENAI_API_KEY`
- `PERSONAL_OPENROUTER_API_KEY`
- `PERSONAL_CLOUDFLARE_ACCOUNT_ID`
- `PERSONAL_CLOUDFLARE_API_KEY`
- `ANTHROPIC_VERTEX_PROJECT_ID`

## Integration Points

**Hardware-Aware Orchestrator:** `/home/sfloess/fleet-coordinator/hardware-aware-orchestrator.js`
- Add OpenRouter/Cloudflare as "cloud" tier providers
- Route to cloud when fleet is overloaded
- Cost tracking per provider

**Multi-Model Workflows:** Use in arbiter/worker patterns
- Arbiter: Claude Opus (highest quality)
- Workers: Mix of Claude, GPT-4o, Gemini, OpenRouter models, local models
- Synthesis: Combine diverse perspectives

## Usage Example

```javascript
// Multi-AI consensus with all providers
const workers = await parallel([
  () => callClaude('opus', prompt),           // Anthropic
  () => callOpenAI('gpt-4o', prompt),         // OpenAI
  () => callGemini('pro', prompt),            // Google
  () => callOpenRouter('llama-3.1-70b', prompt), // OpenRouter
  () => callCloudflare('mistral-7b', prompt), // Cloudflare
  () => callLocal('server-03', 'deepseek-r1:32b', prompt) // Local
])

const arbiter = await callClaude('opus', `Synthesize: ${workers}`)
```

## Related

- [[feedback_always_multi_ai]] - Always use multi-AI with max coverage
- [[feedback_arbiter_worker_multi_model]] - Different models for diversity
- [[.secrets]] - API keys storage
