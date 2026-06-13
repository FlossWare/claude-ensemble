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

## Model-Specific Directory Restrictions

**Feature**: Enforce compliance policies by restricting models per directory path.

### Configuration

**File**: `~/.claude/fleet.json`

```json
{
  "compliance": {
    "path_restrictions": [
      {
        "path": "/home/sfloess/Development/redhat/",
        "denied_models": ["gpt-*"],
        "reason": "Red Hat compliance - no OpenAI"
      },
      {
        "path": "/home/sfloess/Development/client-work/",
        "denied_models": ["ollama-*", "gemini-*"],
        "allowed_models": ["claude-*"],
        "reason": "Client work - Anthropic only"
      }
    ]
  }
}
```

### Wildcard Patterns

Models can be matched using wildcard patterns:

| Pattern | Matches | Example Models |
|---------|---------|----------------|
| `claude-*` | All Claude models | opus, sonnet, haiku, fable, claude-opus-4 |
| `gpt-*` | All OpenAI models | gpt-4o, gpt-4-turbo, gpt-3.5-turbo |
| `ollama-*` | All Ollama models | ollama-llama3, ollama-codellama, ollama-mistral |
| `gemini-*` | All Gemini models | gemini, gemini-pro |
| `*` | All models | Everything (allow/deny all) |

### Path Matching Rules

1. **Most specific path wins** (longest path match first)
2. `/home/sfloess/Development/redhat/project/` uses restriction for `/home/sfloess/Development/redhat/`
3. If multiple restrictions match, longest path takes precedence

### Use Cases

#### Red Hat Compliance (No OpenAI)

```json
{
  "path": "/home/sfloess/Development/redhat/",
  "denied_models": ["gpt-*"],
  "reason": "Red Hat compliance - no OpenAI"
}
```

**Result**:
- ✅ Allowed: opus, sonnet, haiku, fable, gemini, ollama-*
- ❌ Denied: gpt-4o, gpt-4-turbo, gpt-3.5-turbo

#### Client Work (Anthropic Only)

```json
{
  "path": "/home/sfloess/Development/client-work/",
  "allowed_models": ["claude-*"],
  "reason": "Client contract - Anthropic only"
}
```

**Result**:
- ✅ Allowed: opus, sonnet, haiku, fable
- ❌ Denied: gpt-4o, gemini, ollama-*

#### Privacy-Sensitive Work (Local Only)

```json
{
  "path": "/home/sfloess/Development/private/",
  "allowed_models": ["ollama-*"],
  "reason": "Privacy - local models only"
}
```

**Result**:
- ✅ Allowed: ollama-llama3, ollama-codellama, ollama-mistral
- ❌ Denied: opus, sonnet, gpt-4o, gemini (all cloud models)

### Implementation

**Automatic enforcement**:
- `fleet-agent-wrapper.js` checks compliance before creating agents
- Multi-AI workflows (ai-prompt.js) auto-filter workers/arbiters
- Clear error messages when model is denied

**Example error**:
```
Error: Model gpt-4o not allowed in /home/sfloess/Development/redhat/
Reason: Red Hat compliance - no OpenAI
Allowed models: claude-*, gemini-*, ollama-*
```

### Testing

**Verify compliance working**:
```bash
# Check model allowed in Red Hat directory
cd /home/sfloess/Development/redhat/claude-global-skills
node -e "import('./shared/model-compliance.js').then(m => {
  console.log(m.isModelAllowed('opus').allowed ? '✓ opus allowed' : '✗ opus denied');
  console.log(m.isModelAllowed('gpt-4o').allowed ? '✓ gpt-4o allowed' : '✗ gpt-4o denied');
})"

# Expected output:
# ✓ opus allowed
# ✗ gpt-4o denied
```

**Verify auto-filtering in workflows**:
```bash
# Multi-AI workflow should auto-filter out denied models
cd /home/sfloess/Development/redhat/claude-global-skills
# Run ai-prompt.js - should only use opus, sonnet, haiku, gemini (no gpt-4o)
```

### Backward Compatibility

- `forbidden_paths` still works (blocks ALL models from directory)
- Empty `path_restrictions` = no restrictions (allow all)
- Without `compliance` section = no restrictions

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

## Model Restrictions Per Directory

Model restrictions enforce compliance policies by denying or allowing specific model families based on the current working directory. This is configured via `path_restrictions` in `~/.claude/fleet.json`.

### How It Works

1. Workflows call `getCompliantWorkers()` or `getCompliantArbiter()` from `shared/model-compliance.js`
2. The function reads `compliance.path_restrictions` from `~/.claude/fleet.json`
3. It matches the current directory against restriction paths (longest path wins)
4. Models matching `denied_models` patterns are filtered out
5. If `allowed_models` is set, only matching models pass through
6. Filtered worker/arbiter lists are used for multi-AI execution

### Configuration

```json
{
  "compliance": {
    "path_restrictions": [
      {
        "path": "/home/sfloess/Development/redhat/",
        "denied_models": ["gpt-*"],
        "reason": "Red Hat compliance - no OpenAI"
      },
      {
        "path": "/home/sfloess/Development/client/",
        "allowed_models": ["fable", "opus", "sonnet", "haiku"],
        "reason": "Client policy - Anthropic only"
      }
    ]
  }
}
```

### Wildcard Patterns

| Pattern | What It Matches | Example Models |
|---------|-----------------|----------------|
| `gpt-*` | All OpenAI models | gpt-4o, gpt-4-turbo, gpt-3.5-turbo |
| `claude-*` | All Claude model IDs | claude-opus-4, claude-sonnet-4 |
| `ollama-*` | All Ollama local models | ollama-llama3, ollama-codellama |
| `gemini-*` | All Gemini variants | gemini, gemini-pro |
| `*` | Everything | Any model name |
| `opus` | Exact match | Only "opus" (not "claude-opus-4") |

### Active Restrictions by Directory

| Directory | Denied Models | Allowed Models | Effect |
|-----------|---------------|----------------|--------|
| `/home/sfloess/Development/redhat/` | `gpt-*` | (all others) | No OpenAI models in Red Hat work |
| `/home/sfloess/Development/redhat/.../search-engineering/` | (inherited) | gemini, opus, sonnet, haiku | Restricted to 4 models per project policy |
| `/home/sfloess/personal/` | (none) | (all) | All models allowed |
| `/tmp/` | (none) | (all) | All models allowed |

### Impact on Multi-AI Strategies

When model restrictions are active, strategy model lists are automatically filtered:

| Strategy | Default Workers | Red Hat Workers (gpt-* denied) |
|----------|----------------|-------------------------------|
| QualityFirst | fable, opus, sonnet, haiku, gpt-4o, gemini | fable, opus, sonnet, haiku, gemini |
| Balanced | opus, sonnet, haiku, gemini | opus, sonnet, haiku, gemini |
| CostOptimized | haiku, gemini-pro, gpt-3.5-turbo | haiku, gemini-pro |

### Verification

```bash
# Check what models are allowed in the current directory
node -e "
import { getCompliantWorkers, hasModelRestrictions, getActiveRestriction } from './shared/model-compliance.js';
console.log('Restrictions active:', hasModelRestrictions());
console.log('Active restriction:', JSON.stringify(getActiveRestriction(), null, 2));
console.log('Allowed workers:', getCompliantWorkers());
"

# Check a specific model
node -e "
import { isModelAllowed } from './shared/model-compliance.js';
['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'].forEach(m => {
  const r = isModelAllowed(m);
  console.log(m + ':', r.allowed ? 'ALLOWED' : 'DENIED - ' + r.reason);
});
"
```

### Interaction with Fallback Chains

When a model in a fallback chain is denied by compliance, the system skips it and tries the next model:

```
Cross-Vendor Fallback (in Red Hat directory):
  Primary: gemini        ← ALLOWED
    ↓
  Secondary: gpt-4o      ← DENIED (skipped)
    ↓
  Tertiary: opus          ← ALLOWED (used as fallback)
    ↓
  Fallback: sonnet        ← ALLOWED
    ↓
  Last Resort: haiku      ← ALLOWED
```

The `getCompliantArbiter()` function handles this automatically by iterating through the fallback list and returning the first allowed model.

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

## Model Restrictions Per Directory

Model availability can be restricted based on working directory path for compliance policies. For example, Red Hat work cannot use OpenAI models.

### Configuration in `~/.claude/fleet.json`

```json
{
  "compliance": {
    "path_restrictions": [
      {
        "path": "/home/sfloess/Development/redhat/",
        "denied_models": ["gpt-*"],
        "reason": "Red Hat compliance - no OpenAI"
      },
      {
        "path": "/home/sfloess/Development/client-work/",
        "denied_models": ["ollama-*", "gemini-*"],
        "allowed_models": ["claude-*"],
        "reason": "Client work - Anthropic only"
      }
    ]
  }
}
```

### Restriction Types

**Deny-list** (Block specific models):
```json
{
  "path": "/path/to/work/",
  "denied_models": ["gpt-*", "gemini-*"],
  "reason": "Internal policy"
}
```
- All models allowed EXCEPT those matching denied patterns
- Simple and flexible approach

**Allow-list** (Permit specific models):
```json
{
  "path": "/path/to/work/",
  "allowed_models": ["claude-*", "ollama-*"],
  "reason": "Security policy"
}
```
- ONLY models matching allowed patterns are permitted
- Most restrictive, explicit control

**Hybrid** (Both deny and allow):
```json
{
  "path": "/path/to/work/",
  "denied_models": ["gpt-*"],
  "allowed_models": ["*"],
  "reason": "Policy"
}
```
- Models must pass both checks
- Rarely needed

### Pattern Matching

All patterns support wildcards:

| Pattern | Matches | Examples |
|---------|---------|----------|
| `gpt-*` | OpenAI models | gpt-4o, gpt-4-turbo, gpt-3.5-turbo |
| `claude-*` | Anthropic models | claude-opus-4, claude-sonnet-4, claude-haiku-3 |
| `gemini-*` | Google models | gemini, gemini-pro |
| `ollama-*` | Local Ollama models | ollama-llama3, ollama-mistral-7b |
| `*` | All models | Any model name |

### Path Matching Rules

- **Most specific path wins**: Longest matching path takes precedence
  - `/home/sfloess/Development/redhat/scm/` restriction overrides `/home/sfloess/Development/redhat/`
- **Case-insensitive**: Paths and models compared without regard to case
- **Prefix match**: Directory path must be a prefix of current working directory
  - Restriction at `/home/sfloess/Development/` applies to `/home/sfloess/Development/redhat/` and subdirectories

### Example: Red Hat Compliance

In `/home/sfloess/Development/redhat/` directory:

```json
{
  "path": "/home/sfloess/Development/redhat/",
  "denied_models": ["gpt-*"],
  "reason": "Red Hat compliance - no OpenAI"
}
```

**Result**:
- ✅ opus, sonnet, haiku, fable (Anthropic)
- ✅ gemini, gemini-pro (Google)
- ✅ ollama-llama3, ollama-mistral (Local)
- ❌ gpt-4o, gpt-3.5-turbo (OpenAI blocked)

### Workflow Auto-Filtering

Multi-AI workflows automatically filter models based on restrictions:

```javascript
// In ai-prompt.js with Red Hat restriction active
workers = ["opus", "sonnet", "haiku", "gemini", "gpt-4o", "fable"]

// Auto-filtered to:
workers = ["opus", "sonnet", "haiku", "gemini", "fable"]  // gpt-* removed

// Arbiter selection:
arbiter = getCompliantArbiter(["fable", "opus"])  // Returns first allowed
```

### Error Handling

If all models in a workflow are restricted:

```
Error: No compliant arbiter available for /home/sfloess/Development/redhat/
Required: one of (opus, sonnet, haiku, fable)
Allowed by policy: (sonnet, haiku)
Suggestion: Check path_restrictions in ~/.claude/fleet.json
```

### Testing Model Availability

```bash
# Check what models are allowed in current directory
node -e "
import('./shared/model-compliance.js').then(m => {
  const models = ['opus', 'sonnet', 'haiku', 'gemini', 'gpt-4o', 'fable'];
  const allowed = m.filterAllowedModels(models);
  console.log('Allowed models:', allowed);
})
"

# Check if specific model is allowed
node -e "
import('./shared/model-compliance.js').then(m => {
  const result = m.isModelAllowed('gpt-4o');
  console.log('gpt-4o allowed:', result.allowed);
  if (!result.allowed) console.log('Reason:', result.reason);
})
"
```

---

## Documentation References

- **Fleet Dispatcher**: `docs/ARCHITECTURE.md`
- **Multi-AI Strategies**: `docs/INTEGRATION_GUIDE.md`
- **Model Compliance**: `FEATURE_MODEL_RESTRICTIONS.md`
- **Ollama Setup**: `docs/advanced-topics/local-models.md`
- **Model Extensibility**: `docs/advanced-topics/model-extensibility.md`
- **Cost Optimization**: Grafana dashboard at `http://pi-02:3000/d/cost-optimize`
- **Circuit Breaker**: `docs/OPERATIONS.md` → Circuit Breaker section
- **Performance Tuning**: `docs/PERFORMANCE_TUNING.md` (see next section)
