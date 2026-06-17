# Free AI Vendors & Models Reference 2026

**Document Date:** 2026-06-16  
**Purpose:** Complete reference of all FREE AI vendors, models, and APIs used in the orchestration framework

---

## Executive Summary

This framework uses a **two-tier architecture** combining:
1. **Local Models** (Ollama) — 18 models running on personal fleet (FREE, zero cost)
2. **Free Cloud APIs** — 20+ free-tier APIs from various providers (FREE with rate limits)

**Total:** 38+ FREE AI models/APIs with **zero monetary cost**

---

## 1. Local Models (Ollama)

### 1.1 Running on Personal Fleet

**Infrastructure:**
- **server-01:** Fedora Server, AMD Ryzen 5 PRO 4650G (6 cores, 12 threads), 32GB RAM
- **server-02:** Fedora Server, Intel i5-9500T (6 cores), 23GB RAM (DIMM issue limits from 32GB)
- **server-03:** Fedora Server, AMD Ryzen 5 PRO 4650G (6 cores, 12 threads), 32GB RAM
- **laptop-01:** Fedora Laptop, 32GB RAM, NVMe SSD
- **aio-01:** Fedora AIO, limited resources
- **pi-02:** Raspberry Pi (orchestrator, not for heavy models)

**Total Compute:** 32 cores, 107GB usable RAM

### 1.2 Ollama Models Deployed (18 models)

**Based on CLAUDE.md democratic consensus (38-model vote):**

#### **Tier 1: Code Generation (Java/Salesforce)**
1. **deepseek-coder-v2-lite** (6.7B)
   - Primary use: Java/Maven/Salesforce code generation
   - Training data: 48,417 Java files from FlossWare, Solenopsis, JCollections
   - Host: server-03
   - Status: **Fine-tuned** (QDoRA + D2Z scheduler)

#### **Tier 2: Routing & Orchestration**
2. **phi-4-mini** (2.5GB)
   - Primary use: Thompson Sampling strategy routing
   - Training data: 1,168 execution logs + 31 strategy performance records
   - Host: laptop-01
   - Status: **Fine-tuned** for local routing decisions

3. **mistral-7b-instruct** (7B)
   - Primary use: Multi-AI local arbiter (diversity protection)
   - Training data: High-quality consensus patterns (reward > 0.75)
   - Host: server-03
   - Status: **Fine-tuned** to reduce API dependency

#### **Tier 3: General Purpose (Pre-trained)**
4. **llama-3.3-70b** (quantized)
   - Primary use: General reasoning tasks
   - Host: Distributed across server-01/02/03

5. **qwen2.5-coder** (14B/32B variants)
   - Primary use: Multi-language code generation
   - Supports: Python, JavaScript, Go, Rust, etc.

6. **gemma-2** (9B/27B variants)
   - Primary use: Lightweight reasoning
   - Google's open model

7. **yi-coder** (9B)
   - Primary use: Code completion
   - Strong on Python/JavaScript

8. **codestral** (22B, Mistral AI)
   - Primary use: Code generation and fill-in-the-middle
   - Supports 80+ programming languages

9. **llama-3.2** (3B/11B variants)
   - Primary use: Lightweight tasks, edge deployment
   - Vision variants available

10. **mixtral-8x7b** (MoE architecture)
    - Primary use: Complex reasoning with 8 experts
    - 47B total parameters, 12B active

#### **Tier 4: Specialized**
11. **nous-hermes-2** (various sizes)
    - Primary use: Instruction following
    - Fine-tuned for chat

12. **openchat** (7B)
    - Primary use: Conversational tasks
    - Optimized for dialogue

13. **starling-lm** (7B)
    - Primary use: RLHF-trained assistant
    - Strong on helpfulness

14. **zephyr** (7B)
    - Primary use: Aligned assistant
    - DPO-trained

15. **orca-mini** (3B/7B/13B)
    - Primary use: Lightweight reasoning
    - Distilled from GPT-4

16. **solar** (10.7B)
    - Primary use: Depth upscaling technique
    - Strong on Korean/English

17. **wizardlm** (7B/13B)
    - Primary use: Complex instructions
    - Evol-Instruct trained

18. **dolphin** (various)
    - Primary use: Uncensored assistant
    - Multiple base models

### 1.3 Ollama Management

**Installation:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
```

**Model Management:**
```bash
# List installed models
ollama list

# Pull a new model
ollama pull deepseek-coder-v2-lite

# Run a model
ollama run llama-3.3-70b

# Remove a model
ollama rm model-name

# Show model info
ollama show llama-3.3-70b
```

**API Usage:**
```bash
# Local API endpoint
curl http://localhost:11434/api/generate -d '{
  "model": "llama-3.3-70b",
  "prompt": "Why is the sky blue?"
}'
```

---

## 2. Free Cloud APIs (20+ providers)

### 2.1 OpenRouter (FREE tier)

**Website:** https://openrouter.ai/  
**Cost:** FREE tier available with rate limits  
**API Endpoint:** https://openrouter.ai/api/v1/chat/completions

**Free Models Available:**
- **google/gemini-2.0-flash-exp:free** (0 cost)
- **meta-llama/llama-3.3-70b-instruct:free** (0 cost)
- **microsoft/phi-3-medium-4k-instruct:free** (0 cost)
- **mistralai/mistral-7b-instruct:free** (0 cost)
- **qwen/qwen-2.5-7b-instruct:free** (0 cost)

**Authentication:**
```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

**Usage:**
```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/llama-3.3-70b-instruct:free",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 2.2 Groq (FREE tier)

**Website:** https://groq.com/  
**Cost:** FREE tier with generous rate limits  
**API Endpoint:** https://api.groq.com/openai/v1/chat/completions

**Free Models:**
- **llama-3.3-70b-versatile** (500+ tokens/sec)
- **llama-3.1-8b-instant** (800+ tokens/sec)
- **mixtral-8x7b-32768** (700+ tokens/sec)
- **gemma-2-9b-it** (600+ tokens/sec)

**Key Feature:** Extremely fast inference (500-800 tok/s on 70B models!)

**Authentication:**
```bash
export GROQ_API_KEY="gsk_..."
```

**Usage:**
```bash
curl https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": "Explain quantum computing"}]
  }'
```

**Rate Limits (FREE tier):**
- 30 requests per minute
- 14,400 requests per day
- 300,000 tokens per minute

### 2.3 Cloudflare Workers AI (FREE tier)

**Website:** https://developers.cloudflare.com/workers-ai/  
**Cost:** 10,000 neurons/day FREE  
**API Endpoint:** https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/...

**Free Models:**
- **@cf/meta/llama-3.3-70b-instruct-fp8-fast**
- **@cf/meta/llama-3.1-8b-instruct**
- **@cf/mistral/mistral-7b-instruct-v0.2**
- **@cf/qwen/qwen2.5-14b-instruct-awq**
- **@cf/google/gemma-2-9b-it**

**Authentication:**
```bash
export CLOUDFLARE_ACCOUNT_ID="..."
export CLOUDFLARE_API_TOKEN="..."
```

**Usage:**
```bash
curl https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 2.4 Google AI Studio (Gemini FREE tier)

**Website:** https://aistudio.google.com/  
**Cost:** FREE tier with generous limits  
**API Endpoint:** https://generativelanguage.googleapis.com/v1beta/models/...

**Free Models:**
- **gemini-2.0-flash-exp** (Latest, experimental)
- **gemini-1.5-flash** (Fast, production)
- **gemini-1.5-flash-8b** (Lightweight)
- **gemini-1.5-pro** (Advanced reasoning)

**Rate Limits (FREE):**
- 15 requests per minute
- 1,500 requests per day
- 4 million tokens per minute (gemini-1.5-flash)

**Authentication:**
```bash
export GOOGLE_API_KEY="..."
```

**Usage:**
```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=$GOOGLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{"parts": [{"text": "Explain AI"}]}]
  }'
```

### 2.5 Hugging Face Inference API (FREE tier)

**Website:** https://huggingface.co/inference-api  
**Cost:** FREE tier with rate limits  
**API Endpoint:** https://api-inference.huggingface.co/models/{model}

**Free Models (1000s available):**
- **meta-llama/Llama-3.3-70B-Instruct**
- **mistralai/Mistral-7B-Instruct-v0.3**
- **microsoft/Phi-3-medium-4k-instruct**
- **Qwen/Qwen2.5-72B-Instruct**
- **google/gemma-2-27b-it**

**Authentication:**
```bash
export HF_TOKEN="hf_..."
```

**Usage:**
```bash
curl https://api-inference.huggingface.co/models/meta-llama/Llama-3.3-70B-Instruct \
  -H "Authorization: Bearer $HF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"inputs": "What is machine learning?"}'
```

**Rate Limits:** Varies by model and account tier (FREE is limited)

### 2.6 DeepSeek (FREE tier)

**Website:** https://platform.deepseek.com/  
**Cost:** FREE credits on signup  
**API Endpoint:** https://api.deepseek.com/v1/chat/completions

**Free Models:**
- **deepseek-chat** (67B MoE)
- **deepseek-coder** (33B, code-specialized)

**Authentication:**
```bash
export DEEPSEEK_API_KEY="sk-..."
```

**Usage:**
```bash
curl https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 2.7 Cerebras (FREE tier)

**Website:** https://cerebras.ai/  
**Cost:** FREE tier available  
**API Endpoint:** https://api.cerebras.ai/v1/chat/completions

**Free Models:**
- **llama-3.3-70b** (Extremely fast inference)
- **llama-3.1-8b**

**Key Feature:** Fastest inference in the industry (2000+ tok/s)

**Authentication:**
```bash
export CEREBRAS_API_KEY="csk-..."
```

### 2.8 Together AI (FREE credits)

**Website:** https://together.ai/  
**Cost:** $25 FREE credits on signup  
**API Endpoint:** https://api.together.xyz/v1/chat/completions

**Free Models (while credits last):**
- **meta-llama/Llama-3.3-70B-Instruct-Turbo**
- **mistralai/Mixtral-8x22B-Instruct-v0.1**
- **Qwen/Qwen2.5-72B-Instruct-Turbo**

### 2.9 Replicate (FREE tier)

**Website:** https://replicate.com/  
**Cost:** Limited FREE tier  
**API Endpoint:** https://api.replicate.com/v1/predictions

**Free Models:**
- Various open-source models
- Pay-per-use after free credits

### 2.10 Perplexity AI (FREE tier)

**Website:** https://www.perplexity.ai/  
**Cost:** FREE tier with search-augmented responses  
**API Endpoint:** https://api.perplexity.ai/chat/completions

**Free Models:**
- **llama-3.1-sonar-small-128k-online** (search-enabled)
- **llama-3.1-sonar-large-128k-online**

---

## 3. Embedding Models (FREE)

### 3.1 Local: Sentence Transformers (Hugging Face)

**Model:** `all-MiniLM-L6-v2`  
**Location:** `~/.cache/huggingface/hub/`  
**Size:** 88MB  
**Dimensions:** 384  
**Cost:** FREE (runs locally)

**Usage:**
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(["Hello world", "How are you?"])
```

**Performance:**
- Model loads in ~1 second
- Used by session indexer and research doc indexer
- Used by PostgreSQL + pgvector searches

### 3.2 Cloud: OpenAI Embeddings (Paid, for reference)

**Note:** OpenAI embeddings are **NOT FREE** and **NOT USED** in this framework.

We use **only local embeddings** (all-MiniLM-L6-v2) to maintain zero cost.

---

## 4. Multi-Model Routing Strategy

### 4.1 Routing Logic

**From `~/.claude/self/multi-model-router.py`:**

```python
def route(self, task_type, budget_constraint=None):
    if budget_constraint == 'free':
        return 'local'  # Ollama models
    elif task_type == 'complex':
        return 'anthropic'  # Paid (Claude Opus/Sonnet/Haiku)
    else:
        return 'openrouter'  # FREE tier APIs
```

**Fallback Chain:**
1. Anthropic (Opus → Sonnet → Haiku) — **PAID**
2. OpenRouter (free tier) — **FREE**
3. Local Ollama — **FREE**

### 4.2 Free-First Strategy

**For cost-sensitive workloads:**
1. **Local Ollama** — Try first (0 cost, 0 latency)
2. **Groq** — Fallback for speed (FREE, 500+ tok/s)
3. **OpenRouter** — Fallback for variety (FREE tier)
4. **Google Gemini** — Fallback for advanced reasoning (FREE tier)

### 4.3 Hybrid Strategy (Best Quality)

**From memory (multi-AI quality comparison):**
- **FREE models:** 90-95% quality
- **PAID models:** 95-98% quality
- **Hybrid (FREE + PAID):** 95-98% quality with cost optimization

**Recommended:**
- Use FREE models for initial drafts
- Use PAID models (Anthropic) for final review
- Use consensus (3 FREE + 3 PAID) for critical decisions

---

## 5. API Key Management

### 5.1 Environment Variables

**Set in `~/.bashrc` or `~/.zshrc`:**

```bash
# Free APIs
export OPENROUTER_API_KEY="sk-or-v1-..."
export GROQ_API_KEY="gsk_..."
export CLOUDFLARE_ACCOUNT_ID="..."
export CLOUDFLARE_API_TOKEN="..."
export GOOGLE_API_KEY="..."
export HF_TOKEN="hf_..."
export DEEPSEEK_API_KEY="sk-..."
export CEREBRAS_API_KEY="csk-..."

# Paid APIs (for reference)
export ANTHROPIC_API_KEY="sk-ant-..."  # PAID
export OPENAI_API_KEY="sk-..."  # PAID (not used)
```

### 5.2 Secrets Management

**Recommended:** Store API keys in `~/.secrets.md` (git-ignored, 600 permissions)

**Never commit:**
- API keys to git repositories
- Keys to public code
- Keys to Confluence/Jira

---

## 6. Rate Limits & Quotas Summary

| Provider | Free Tier Limit | Models | Speed |
|----------|----------------|--------|-------|
| **Ollama (Local)** | Unlimited | 18+ | Fast (local) |
| **Groq** | 30 req/min, 14.4K/day | 4 | Very Fast (500+ tok/s) |
| **OpenRouter** | Varies by model | 5+ free | Medium |
| **Cloudflare** | 10K neurons/day | 5 | Fast |
| **Google Gemini** | 15 req/min, 1.5K/day | 4 | Medium |
| **Hugging Face** | Rate limited | 1000s | Slow (cold start) |
| **DeepSeek** | Credits | 2 | Medium |
| **Cerebras** | Limited | 2 | Very Fast (2000+ tok/s) |

---

## 7. Cost Comparison (Per 1M Tokens)

| Provider | Input Cost | Output Cost | Status |
|----------|-----------|-------------|--------|
| **Ollama (Local)** | $0 | $0 | ✅ FREE |
| **Groq** | $0 | $0 | ✅ FREE (rate limited) |
| **OpenRouter (free)** | $0 | $0 | ✅ FREE (rate limited) |
| **Cloudflare** | $0 | $0 | ✅ FREE (10K/day) |
| **Google Gemini** | $0 | $0 | ✅ FREE (rate limited) |
| **Claude Sonnet 4** | $3 | $15 | ❌ PAID |
| **GPT-4o** | $2.50 | $10 | ❌ PAID |

**Conclusion:** Use FREE models for 90-95% of workloads, PAID only for critical 5-10%

---

## 8. Usage Examples

### 8.1 Multi-Model Consensus (FREE only)

```python
from multi_model_router import MultiModelRouter

router = MultiModelRouter()

models = [
    'ollama:llama-3.3-70b',
    'groq:llama-3.3-70b-versatile',
    'openrouter:meta-llama/llama-3.3-70b-instruct:free',
    'gemini:gemini-2.0-flash-exp',
    'cloudflare:llama-3.3-70b-instruct-fp8-fast',
]

# Get consensus from 5 FREE models
results = []
for model in models:
    response = router.query(model, "What is the capital of France?")
    results.append(response)

# Vote on best answer
consensus = majority_vote(results)
```

### 8.2 Local-First with Cloud Fallback

```python
def smart_query(prompt):
    # Try local first (FREE, fast)
    try:
        return ollama_query("llama-3.3-70b", prompt)
    except Exception:
        pass
    
    # Fallback to Groq (FREE, very fast)
    try:
        return groq_query("llama-3.3-70b-versatile", prompt)
    except Exception:
        pass
    
    # Fallback to OpenRouter (FREE)
    try:
        return openrouter_query("meta-llama/llama-3.3-70b-instruct:free", prompt)
    except Exception:
        pass
    
    # Last resort: Google Gemini (FREE)
    return gemini_query("gemini-2.0-flash-exp", prompt)
```

---

## 9. Red Hat Compliance (CRITICAL)

**From memory: Red Hat AI Compliance**

### 9.1 Approved FREE Models (Red Hat Proprietary Code)

**SAFE for Red Hat proprietary code:**
1. **Anthropic (4 models)** — Claude Opus, Sonnet, Haiku, Fable (PAID, but approved)
2. **Local Ollama (18 models)** — All 18 models listed above (FREE, approved)

**Total SAFE:** 22 models (4 paid + 18 free)

### 9.2 PROHIBITED for Red Hat Proprietary Code

**NEVER use these with Red Hat code:**
- ❌ OpenAI (GPT-4, GPT-4o, GPT-3.5)
- ❌ Google Gemini (external API)
- ❌ DeepSeek (external API)
- ❌ OpenRouter (external API)
- ❌ Groq (external API)
- ❌ Cloudflare (external API)
- ❌ Hugging Face (external API)

**Reason:** Red Hat proprietary code must ONLY use:
- Anthropic models (approved vendor)
- Local models (on-premises, no data leaves network)

### 9.3 Safe Usage Pattern

```python
def is_redhat_code(file_path):
    """Check if code is Red Hat proprietary"""
    return 'redhat' in file_path.lower() or 'gitlab.cee.redhat.com' in file_path

def safe_model_selection(file_path, task):
    if is_redhat_code(file_path):
        # Only use approved models
        return random.choice([
            'anthropic:claude-opus',
            'anthropic:claude-sonnet',
            'ollama:llama-3.3-70b',
            'ollama:deepseek-coder-java:finetuned',
        ])
    else:
        # Use any FREE model
        return 'groq:llama-3.3-70b-versatile'
```

---

## 10. Summary

### 10.1 Total FREE Resources

**Local Models:** 18 (Ollama)  
**Free Cloud APIs:** 20+ (OpenRouter, Groq, Cloudflare, Gemini, etc.)  
**Total FREE Models:** 38+  
**Cost:** $0

### 10.2 Best Practices

1. **Local First:** Use Ollama for 80% of tasks (FREE, fast, private)
2. **Cloud Fallback:** Use Groq/OpenRouter for remaining 20% (FREE, fast)
3. **Consensus:** Use 3-6 FREE models for critical decisions
4. **Red Hat Code:** ONLY use Anthropic (paid) or Local Ollama (free)
5. **Cost Optimization:** Reserve PAID APIs (Anthropic) for final review only

### 10.3 Cost Savings

**Scenario:** 10M tokens per month

| Strategy | Cost | Models |
|----------|------|--------|
| **All Anthropic (Sonnet)** | $150,000 | Claude only |
| **All FREE (Ollama + Groq)** | $0 | 20+ models |
| **Hybrid (95% FREE, 5% Paid)** | $7,500 | 25+ models |

**Savings:** 95-100% cost reduction using FREE models

---

## 11. References

- **Ollama:** https://ollama.com/
- **OpenRouter:** https://openrouter.ai/
- **Groq:** https://groq.com/
- **Cloudflare Workers AI:** https://developers.cloudflare.com/workers-ai/
- **Google AI Studio:** https://aistudio.google.com/
- **Hugging Face:** https://huggingface.co/
- **DeepSeek:** https://platform.deepseek.com/
- **Cerebras:** https://cerebras.ai/

---

**Document Status:** Complete  
**Last Updated:** 2026-06-16  
**Maintained By:** AI Orchestration Framework
