# Complete Model Catalog

## Cloud Models (API-based)

> **Note:** This catalog lists commonly-used models only. The authoritative source is the `/models/` REST API on aio-01:5000, which tracks **445+ models across 21 providers** (OpenRouter, Anthropic, Google, Groq, Cerebras, DeepSeek, Pollinations, ZeroLimitAI, Eden AI, GitHub Models, Cohere, Cloudflare, Jina, DeepInfra, HuggingFace, Mistral, and others). Model registry is stored in PostgreSQL `learning.free_models` and exposed via `/models/` REST endpoints.

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
export PERSONAL_OPENAI_API_KEY="sk-..."
```

---

Local models archived 2026-06-28; system is API-only. See `/models/` REST API for current model registry.

---

## Model Detection

**Query available models via REST API**:
```bash
# List all available models
curl -s http://aio-01:5000/models/ | jq '.total'

# List models by provider
curl -s http://aio-01:5000/models/by-provider | jq 'keys'
```

**Output Example**:
```json
{
  "total": 445,
  "providers": ["openrouter", "anthropic", "google", "groq", "cerebras", "deepseek", "pollinations", "zerolimitai", "eden-ai", "github-models", "cohere", "cloudflare", "jina", "deepinfra", "huggingface", "mistral"]
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
        "allowed_models": ["claude-*"],
        "reason": "Red Hat compliance - Anthropic only"
      },
      {
        "path": "/home/sfloess/Development/client-work/",
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
| `gemini-*` | All Gemini models | gemini, gemini-pro |
| `*` | All models | Everything (allow/deny all) |

### Path Matching Rules

1. **Most specific path wins** (longest path match first)
2. `/home/sfloess/Development/redhat/project/` uses restriction for `/home/sfloess/Development/redhat/`
3. If multiple restrictions match, longest path takes precedence

### Use Cases

#### Red Hat Compliance (Anthropic Only)

```json
{
  "path": "/home/sfloess/Development/redhat/",
  "allowed_models": ["claude-*"],
  "reason": "Red Hat compliance - Anthropic only"
}
```

**Result**:
- ✅ Allowed: opus, sonnet, haiku, fable (Anthropic/Claude only)
- ❌ Denied: gpt-4o, gemini, all OpenRouter models, all third-party LLMs

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
- ❌ Denied: gpt-4o, gemini, all non-Claude models

#### Privacy-Sensitive Work (Anthropic Only)

```json
{
  "path": "/home/sfloess/Development/private/",
  "allowed_models": ["claude-*"],
  "reason": "Privacy - Anthropic only"
}
```

**Result**:
- ✅ Allowed: opus, sonnet, haiku, fable (Anthropic/Claude only)
- ❌ Denied: gpt-4o, gemini, all third-party models

### Implementation

**Automatic enforcement**:
- `fleet-agent-wrapper.js` checks compliance before creating agents
- Multi-AI workflows (ai-prompt.js) auto-filter workers/arbiters
- Clear error messages when model is denied

**Example error**:
```
Error: Model gpt-4o not allowed in /home/sfloess/Development/redhat/
Reason: Red Hat compliance - no OpenAI
Allowed models: claude-*
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

### FreeTier Strategy (Zero Cost)

**Free API models + cloud arbiter**:
```javascript
workers: ["deepseek/deepseek-chat-v3-0324:free", "qwen/qwen3-235b-a22b:free", "google/gemini-2.5-pro-exp-03-25:free", "nvidia/llama-3.1-nemotron-ultra-253b-v1:free"]
arbiter: "opus"  // Cloud synthesis for quality
```

**Use when**: Budget zero, maximize model diversity

**Performance**: Comparable to paid models for most tasks, zero API cost via OpenRouter/Pollinations/ZeroLimitAI free tiers

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

### Free-Tier-First Fallback

```
Primary: deepseek-chat (free, DeepSeek API)
   ↓ (if rate limited)
Secondary: qwen3-235b (free, OpenRouter)
   ↓ (if rate limited)
Tertiary: opus (paid, Anthropic)
   ↓ (if circuit breaker open)
Last Resort: sonnet (paid, Anthropic)
```

**Advantage**: Zero cost for most requests via free-tier APIs  
**Disadvantage**: Free-tier rate limits may require fallback to paid

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
| `gemini-*` | All Gemini variants | gemini, gemini-pro |
| `*` | Everything | Any model name |
| `opus` | Exact match | Only "opus" (not "claude-opus-4") |

### Active Restrictions by Directory

| Directory | Denied Models | Allowed Models | Effect |
|-----------|---------------|----------------|--------|
| `/home/sfloess/Development/redhat/` | (all non-Claude) | `claude-*` | Anthropic only for Red Hat work |
| `/home/sfloess/Development/redhat/.../search-engineering/` | (inherited) | opus, sonnet, haiku, fable | Anthropic only per project policy |
| `/home/sfloess/personal/` | (none) | (all) | All models allowed |

### Impact on Multi-AI Strategies

When model restrictions are active, strategy model lists are automatically filtered:

| Strategy | Default Workers | Red Hat Workers (claude-* only) |
|----------|----------------|-------------------------------|
| QualityFirst | fable, opus, sonnet, haiku, gpt-4o, gemini | fable, opus, sonnet, haiku |
| Balanced | opus, sonnet, haiku, gemini | opus, sonnet, haiku |
| CostOptimized | haiku, gemini-pro, gpt-3.5-turbo | haiku |

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
  Primary: gemini        ← DENIED (skipped, not claude-*)
    ↓
  Secondary: gpt-4o      ← DENIED (skipped, not claude-*)
    ↓
  Tertiary: opus          ← ALLOWED (claude-*)
    ↓
  Fallback: sonnet        ← ALLOWED (claude-*)
    ↓
  Last Resort: haiku      ← ALLOWED (claude-*)
```

The `getCompliantArbiter()` function handles this automatically by iterating through the fallback list and returning the first allowed model.

---

## Fleet Model Distribution

### Current Fleet Assignment

**server-03 (Heavy, 31GB RAM):**
- Primary: `opus`, `fable` (API calls to Anthropic)
- Job Types: `ai-heavy`, `ai-consensus`, `build-test`
- Circuit Breaker: Independent per model

**server-02 (Medium, 31GB RAM):**
- Primary: `sonnet`, `gemini` (API calls to Anthropic/Google)
- Job Types: `code-review`, `ai-consensus`, `build-test`
- Circuit Breaker: Independent per model

**server-01 (Fast, 15GB RAM):**
- Primary: `haiku` (API calls to Anthropic)
- Job Types: `ai-light`, `code-review`, `ai-consensus`
- Circuit Breaker: Independent per model

**aio-01 (Controller, 7GB RAM):**
- Role: Controller/orchestrator ONLY, never runs worker tasks
- Services: REST API (:5000), PostgreSQL (:5433), OrientDB, Redis (:6379), Prometheus (:9090), Grafana (:3000)

---

## Circuit Breaker State Per Model

**Query circuit breaker state**:
```bash
curl -s http://aio-01:5000/fleet/status | jq '.circuit_breaker'
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
| **Free-tier (OpenRouter/etc.)** | **$0.00** | **$0.00** | **$0.00** |

**Typical Multi-AI Workflow (6 workers + arbiter)**:
- QualityFirst: ~$3.00 per run (fable + opus + sonnet + haiku + gemini + gpt-4o)
- Balanced: ~$0.50 per run (opus + sonnet + haiku + gemini)
- CostOptimized: ~$0.05 per run (haiku + gemini + gpt-3.5-turbo)
- FreeTier: **$0.00 per run** (all free-tier API models via OpenRouter/Pollinations/ZeroLimitAI)

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

**Free-Tier API Models**:
- ✅ Zero-cost tasks via OpenRouter/Pollinations/ZeroLimitAI free tiers
- ✅ High-quality models (DeepSeek, Qwen, Llama, Gemini free variants)
- ❌ Rate limits may apply on free tiers

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

# Test OpenAI (requires PERSONAL_OPENAI_API_KEY)
claude --model gpt-4o -p "Test"
```

**Test via REST API**:
```bash
# List all available models
curl -s http://aio-01:5000/models/ | jq '.total'

# Test via fleet dispatcher
curl -X POST http://aio-01:5000/agent/execute \
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
        "allowed_models": ["claude-*"],
        "reason": "Red Hat compliance - Anthropic only"
      },
      {
        "path": "/home/sfloess/Development/client-work/",
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
  "allowed_models": ["claude-*"],
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
  "allowed_models": ["claude-*"],
  "reason": "Red Hat compliance - Anthropic only"
}
```

**Result**:
- ✅ opus, sonnet, haiku, fable (Anthropic/Claude only)
- ❌ gpt-4o, gpt-3.5-turbo (OpenAI blocked)
- ❌ gemini, gemini-pro (Google blocked)
- ❌ All OpenRouter/third-party models (blocked)

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
- **Model Registry**: REST API at `http://aio-01:5000/models/`
- **Model Extensibility**: `docs/advanced-topics/model-extensibility.md`
- **Cost Optimization**: Grafana dashboard at `http://aio-01:3000/d/cost-optimize`
- **Circuit Breaker**: `docs/OPERATIONS.md` → Circuit Breaker section
- **Performance Tuning**: `docs/PERFORMANCE_TUNING.md` (see next section)
