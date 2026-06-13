# Complete Model Catalog

## Cloud Models (API-based)

### Anthropic Models (Primary)

| Model | Size | Speed | Cost | Use Case | Circuit Breaker Key |
|-------|------|-------|------|----------|---------------------|
| **opus** | Large | Slow | High | Complex reasoning, synthesis, heavy tasks | `model:opus` |
| **sonnet** | Medium | Medium | Medium | Balanced tasks, most workflows | `model:sonnet` |
| **haiku** | Small | Fast | Low | Simple tasks, validation, light work | `model:haiku` |
| **fable** | Extra Large | Slowest | Highest | Expert-level arbiter synthesis | `model:fable` |

**Access**: Configured via `~/.claude/` or environment  
**Rate Limits**: Managed by circuit breaker  
**Fallback Chain**: `opus → sonnet → haiku`

---

### Google Models

| Model | Size | Speed | Cost | Use Case | Circuit Breaker Key |
|-------|------|-------|------|----------|---------------------|
| **gemini** | Large | Medium | Medium | Multi-modal, diverse perspective | `model:gemini` |
| **gemini-pro** | Medium | Fast | Low | Fast processing, code tasks | `model:gemini-pro` |

**Access**: Requires `gcloud auth application-default login`  
**Project**: `cloudability-it-gemini` (quota project)  
**Rate Limits**: Managed by circuit breaker  
**Fallback**: `gemini → gemini-pro → opus`

**Setup**:
```bash
# Initialize Gemini access
gcloud auth application-default login
gcloud auth application-default set-quota-project cloudability-it-gemini

# Verify
gcloud auth application-default print-access-token
```

---

### OpenAI Models

| Model | Size | Speed | Cost | Use Case | Circuit Breaker Key |
|-------|------|-------|------|----------|---------------------|
| **gpt-4o** | Large | Medium | High | Diverse perspective, coding | `model:gpt-4o` |
| **gpt-4-turbo** | Large | Fast | Medium | Fast complex tasks | `model:gpt-4-turbo` |
| **gpt-3.5-turbo** | Small | Fastest | Low | Simple tasks, quick responses | `model:gpt-3.5-turbo` |

**Access**: Requires OpenAI API key in environment  
**Rate Limits**: Managed by circuit breaker  
**Fallback**: `gpt-4o → gpt-4-turbo → gpt-3.5-turbo`

**Setup**:
```bash
export OPENAI_API_KEY="sk-..."
```

---

## Local Models (Ollama)

### Large Models (8GB+ VRAM)

| Model | Size | Speed | RAM | Use Case | Circuit Breaker Key |
|-------|------|-------|-----|----------|---------------------|
| **llama-70b** | 70B params | Slow | 40GB | Heavy reasoning, local opus alternative | `model:llama-70b` |
| **mixtral-8x7b** | 47B params | Medium | 24GB | Mixture of experts, diverse reasoning | `model:mixtral-8x7b` |
| **codellama-34b** | 34B params | Medium | 20GB | Code-specific tasks | `model:codellama-34b` |

---

### Medium Models (4-8GB VRAM)

| Model | Size | Speed | RAM | Use Case | Circuit Breaker Key |
|-------|------|-------|-----|----------|---------------------|
| **llama-13b** | 13B params | Fast | 8GB | Balanced local model | `model:llama-13b` |
| **mistral-7b** | 7B params | Fast | 4GB | Fast local processing | `model:mistral-7b` |
| **codellama-13b** | 13B params | Fast | 8GB | Code tasks, local sonnet alternative | `model:codellama-13b` |

---

### Small Models (2-4GB VRAM)

| Model | Size | Speed | RAM | Use Case | Circuit Breaker Key |
|-------|------|-------|-----|----------|---------------------|
| **llama-3b** | 3B params | Fastest | 2GB | Ultra-fast local tasks | `model:llama-3b` |
| **phi-2** | 2.7B params | Fastest | 2GB | Lightweight reasoning | `model:phi-2` |
| **tinyllama-1.1b** | 1.1B params | Instant | 1GB | Minimal tasks, validation | `model:tinyllama` |

---

### Ollama Installation

**Install Ollama**:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Pull Models**:
```bash
# Large models (server-03: 33GB RAM)
ollama pull llama-70b
ollama pull mixtral-8x7b
ollama pull codellama-34b

# Medium models (server-01/02: 16-25GB RAM)
ollama pull llama-13b
ollama pull mistral-7b
ollama pull codellama-13b

# Small models (aio-01: 4GB RAM)
ollama pull llama-3b
ollama pull phi-2
ollama pull tinyllama
```

**Fleet Distribution**:
- server-03 (33GB): llama-70b, mixtral-8x7b, codellama-34b
- server-02 (25GB): llama-13b, codellama-13b, mistral-7b
- server-01 (16GB): llama-13b, mistral-7b
- aio-01 (4GB): llama-3b, phi-2, tinyllama

---

## Model Detection

**Auto-detect available models**:
```bash
# Detect all available models (cloud + local)
node workflows/detect-local-models.js
```

**Output Example**:
```json
{
  "cloud": ["opus", "sonnet", "haiku", "fable", "gemini", "gpt-4o"],
  "ollama": ["llama-70b", "mistral-7b", "codellama-13b"],
  "total": 9
}
```

---

## Multi-AI Strategy Model Selection

### QualityFirst Strategy

**6 models, maximum diversity**:
```javascript
workers: ["fable", "opus", "sonnet", "haiku", "gemini", "gpt-4o"]
arbiter: "fable"
```

**Use when**: Accuracy critical, cost not a concern

---

### CostOptimized Strategy

**3 models, minimize API cost**:
```javascript
workers: ["haiku", "gemini-pro", "gpt-3.5-turbo"]
arbiter: "sonnet"
```

**Use when**: Simple tasks, budget constraints

---

### Balanced Strategy

**4 models, cost/quality tradeoff**:
```javascript
workers: ["opus", "sonnet", "haiku", "gemini"]
arbiter: "opus"
```

**Use when**: Most workflows, default choice

---

### Quantized Strategy (Zero Cost)

**Ollama workers + cloud arbiter**:
```javascript
workers: ["llama-70b", "mixtral-8x7b", "codellama-34b", "mistral-7b"]
arbiter: "opus"  // Cloud synthesis for quality
```

**Use when**: Budget zero, local compute available

**Performance**: ~3x slower than cloud, but zero API cost

---

### QuintupleVerification Strategy

**5-stage adversarial verification**:
```javascript
stage1_finders: ["opus", "sonnet", "haiku", "gemini", "gpt-4o", "fable"]  // 6 parallel
stage2_dedup: "opus"                                                      // 1 synthesis
stage3_verify: ["opus", "sonnet", "haiku"] × N findings                  // 3N parallel
stage4_synthesize: "fable"                                               // 1 final
```

**Use when**: Code review, security audit, critical validation

---

## Model Fallback Chains

### Cross-Vendor Fallback (Recommended)

```
Primary: gemini
   ↓ (if circuit breaker open)
Secondary: gpt-4o
   ↓ (if circuit breaker open)
Tertiary: opus
   ↓ (if circuit breaker open)
Fallback: sonnet
   ↓ (if circuit breaker open)
Last Resort: haiku
```

**Advantage**: Different vendors → different outages → high availability

---

### Anthropic-Only Fallback

```
Primary: opus
   ↓ (if circuit breaker open)
Secondary: sonnet
   ↓ (if circuit breaker open)
Fallback: haiku
```

**Advantage**: Simplicity, consistent style  
**Disadvantage**: Single vendor outage affects all

---

### Local-First Fallback

```
Primary: llama-70b (local, Ollama)
   ↓ (if server overloaded)
Secondary: mixtral-8x7b (local, Ollama)
   ↓ (if server overloaded)
Tertiary: opus (cloud, fallback)
   ↓ (if circuit breaker open)
Last Resort: sonnet (cloud)
```

**Advantage**: Zero cost for most requests  
**Disadvantage**: Slower, depends on local resources

---

## Fleet Model Distribution

### Current Fleet Assignment

**server-03 (Heavy, 33GB RAM):**
- Primary: `opus`, `fable`, `llama-70b`, `mixtral-8x7b`
- Job Types: `ai-heavy`, `ai-consensus`, `build-test`
- Circuit Breaker: Independent per model

**server-02 (Medium, 25GB RAM):**
- Primary: `sonnet`, `gemini`, `llama-13b`, `codellama-13b`
- Job Types: `code-review`, `ai-consensus`, `build-test`
- Circuit Breaker: Independent per model

**server-01 (Fast, 16GB RAM):**
- Primary: `haiku`, `gpt-4o`, `mistral-7b`
- Job Types: `ai-light`, `code-review`, `ai-consensus`
- Circuit Breaker: Independent per model

**aio-01 (Light, 4GB RAM):**
- Primary: `haiku`, `llama-3b`, `phi-2`
- Job Types: `ai-light`, `agent`
- Circuit Breaker: Independent per model

**pi-02 (Coordinator, 1GB RAM):**
- Role: Dispatcher only, no agent execution
- Services: Prometheus, Grafana, Fleet Dispatcher

---

## Circuit Breaker State Per Model

**Query circuit breaker state**:
```bash
curl -s http://pi-02:3004/fleet/status | jq '.circuit_breaker'
```

**Output Example**:
```json
{
  "model:opus": {"state": "closed", "failures": 0, "backoff_until": null},
  "model:sonnet": {"state": "closed", "failures": 0, "backoff_until": null},
  "model:haiku": {"state": "half_open", "failures": 1, "backoff_until": "2026-06-13T01:23:00"},
  "model:gemini": {"state": "open", "failures": 3, "backoff_until": "2026-06-13T02:45:00"}
}
```

**States**:
- `closed`: Normal, model available
- `half_open`: Probing after backoff, single test request
- `open`: Circuit broken, model unavailable until backoff expires

---

## Model Cost Comparison

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Total (typical 10K request) |
|-------|---------------------|----------------------|-----------------------------|
| opus | $15.00 | $75.00 | ~$0.90 |
| sonnet | $3.00 | $15.00 | ~$0.18 |
| haiku | $0.25 | $1.25 | ~$0.015 |
| fable | $20.00 | $100.00 | ~$1.20 |
| gemini | $0.35 | $1.05 | ~$0.014 |
| gpt-4o | $5.00 | $15.00 | ~$0.20 |
| **Ollama** | **$0.00** | **$0.00** | **$0.00** |

**Typical Multi-AI Workflow (6 workers + arbiter)**:
- QualityFirst: ~$3.00 per run (fable + opus + sonnet + haiku + gemini + gpt-4o)
- Balanced: ~$0.50 per run (opus + sonnet + haiku + gemini)
- CostOptimized: ~$0.05 per run (haiku + gemini + gpt-3.5-turbo)
- Quantized: **$0.00 per run** (all Ollama local)

---

## Model Selection Best Practices

### When to Use Each Model

**Fable**:
- ✅ Final arbiter synthesis (multi-AI)
- ✅ Expert-level analysis
- ✅ Complex architectural decisions
- ❌ Simple tasks (cost inefficient)

**Opus**:
- ✅ Complex reasoning
- ✅ Code review (deep analysis)
- ✅ Multi-step planning
- ❌ Simple validation

**Sonnet**:
- ✅ Most workflows (default)
- ✅ Balanced speed/quality
- ✅ Code generation
- ✅ Documentation

**Haiku**:
- ✅ Fast validation
- ✅ Simple Q&A
- ✅ Lightweight tasks
- ❌ Complex reasoning

**Gemini**:
- ✅ Multi-modal tasks
- ✅ Diverse perspective (multi-AI)
- ✅ Cost-effective alternative to opus

**GPT-4o**:
- ✅ Diverse perspective (multi-AI)
- ✅ Coding tasks
- ✅ Cross-vendor redundancy

**Ollama (Large)**:
- ✅ Zero-cost heavy tasks
- ✅ Privacy-sensitive work
- ❌ Time-critical tasks (slower)

**Ollama (Small)**:
- ✅ Ultra-fast local tasks
- ✅ Validation, simple Q&A
- ❌ Complex reasoning

---

## Testing Model Availability

**Test cloud models**:
```bash
# Test Anthropic models
claude --model opus -p "Test"
claude --model sonnet -p "Test"
claude --model haiku -p "Test"
claude --model fable -p "Test"

# Test Gemini (requires gcloud auth)
claude --model gemini -p "Test"

# Test OpenAI (requires OPENAI_API_KEY)
claude --model gpt-4o -p "Test"
```

**Test local Ollama models**:
```bash
# List installed models
ollama list

# Test model
ollama run llama-70b "Test"
ollama run mistral-7b "Test"
```

**Test via fleet dispatcher**:
```bash
# Dispatcher will auto-select available model
curl -X POST http://pi-02:3004/agent/execute \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "ai-consensus",
    "model": "opus",
    "prompt": "Test",
    "estimated_duration": 30
  }'
```

---

## Documentation References

- **Fleet Dispatcher**: `docs/ARCHITECTURE.md`
- **Multi-AI Strategies**: `docs/INTEGRATION_GUIDE.md`
- **Ollama Setup**: `docs/advanced-topics/local-models.md`
- **Model Extensibility**: `docs/advanced-topics/model-extensibility.md`
- **Cost Optimization**: Grafana dashboard at `http://pi-02:3000/d/cost-optimize`
- **Circuit Breaker**: `docs/OPERATIONS.md` → Circuit Breaker section
- **Performance Tuning**: `docs/PERFORMANCE_TUNING.md` (see next section)
