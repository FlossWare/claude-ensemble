# Model Capability Tracking System

## Current Status

**Models discovered:** 252 free models across 7 providers
**Models with capabilities:** 12 (5% coverage)
**Gap:** 240 models need profiling

## Problem

The orchestrator can't intelligently route tasks because 95% of discovered models have no capability ratings. It doesn't know:
- Which models are good at code generation vs research
- Which are fast vs accurate
- Which understand complex reasoning vs simple QA

## Solution Architecture

### 1. Database Schema

**Table:** `learning.model_capabilities`
```sql
Stores capability scores (0.0-1.0) for each model:
- code_generation
- code_review  
- research
- math_reasoning
- general_qa
- creative_writing
- security_analysis
- avg_latency_ms
- context_window
```

**View:** `learning.best_models_by_task`
```sql
Quick lookup: Top 10 models for each task type
```

### 2. Profiling Process

**Quick Benchmark (15 min per model):**
1. Code generation test
2. Code review test
3. Research/summarization test
4. Math/reasoning test
5. General QA test

**Scoring criteria:**
- Correctness (0.0-1.0)
- Completeness (0.0-1.0)
- Response time (faster = higher score)
- Context understanding (0.0-1.0)

**Final score:** Average of 4 criteria

### 3. Integration Points

**Router integration:**
```javascript
// shared/weighted-voting.cjs or similar
async function selectBestModel(taskType) {
  // 1. Check learned capabilities (from real usage)
  const learned = await getLearnedCapabilities(taskType);
  
  // 2. Check profiled capabilities (from benchmarks)
  const profiled = await db.query(`
    SELECT model_id, ${taskType} as score 
    FROM learning.model_capabilities 
    WHERE ${taskType} IS NOT NULL 
    ORDER BY ${taskType} DESC 
    LIMIT 10
  `);
  
  // 3. Combine with Thompson Sampling for exploration
  return thompsonSample([...learned, ...profiled]);
}
```

## Current Capability Data

### Models with ratings (12 total):

From `monitoring.execution_summary` (learned from real usage):
- Models that have been used by fleet
- Quality scores based on actual task performance

From `learning/model-capability-matrix.json` (static ratings):
- 9 models with pre-defined capabilities
- Manually curated ratings

### Models WITHOUT ratings (240 total):

**By provider:**
- Mistral: 62 models
- DeepInfra: 55 models
- HuggingFace: 50 models
- Google Gemini: 39 models
- OpenRouter: 26 models
- Groq: 17 models
- Cerebras: 3 models

## Priority Profiling Order

### Tier 1: High-value models (profile first)
1. **Large models (70B+)**
   - nousresearch/hermes-3-llama-3.1-405b:free (405B)
   - nvidia/nemotron-3-ultra-550b-a55b:free (550B)
   - nvidia/nemotron-3-super-120b-a12b:free (120B)
   - openai/gpt-oss-120b:free (120B)

2. **Code specialists**
   - qwen/qwen3-coder:free
   - cohere/north-mini-code:free
   - codestral-latest (Mistral)

3. **Reasoning models**
   - nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
   - liquid/lfm-2.5-1.2b-thinking:free

### Tier 2: Popular general models
- Gemini 2.5 Flash/Pro
- Mistral Large/Medium
- LLaMA 3.3 70B

### Tier 3: Rest of discovered models

## Profiling Workflow

**Option A: Overnight batch profiling**
```bash
# Profile top 50 models across 8 workers (10 hours)
./workflows/profile-model-capabilities.mjs --models=50 --parallel=8
```

**Option B: Progressive profiling**
```bash
# Profile 5 models per day (slow but safe)
# Cron: 0 2 * * * profile-next-5-models.sh
```

**Option C: On-demand profiling**
```bash
# Profile when orchestrator tries to use unknown model
# Automatic fallback: test model, cache result, use score
```

## Usage Examples

### Check if model has capabilities:
```sql
SELECT * FROM learning.model_capabilities 
WHERE model_id = 'qwen/qwen3-coder:free';
```

### Get best model for code generation:
```sql
SELECT model_id, code_generation, avg_latency_ms
FROM learning.model_capabilities 
WHERE code_generation IS NOT NULL
ORDER BY code_generation DESC 
LIMIT 5;
```

### Find fast models for quick tasks:
```sql
SELECT model_id, general_qa, avg_latency_ms
FROM learning.model_capabilities 
WHERE avg_latency_ms < 2000 AND general_qa > 0.7
ORDER BY avg_latency_ms ASC;
```

## Next Steps

**Option 1: Build profiling workflow** (~2 hours dev time)
- Create workflow to benchmark models
- Run overnight on fleet (8 hours for top 50)
- Integrate with router

**Option 2: Manual seeding** (~30 min)
- Add known capabilities for popular models
- Use provider documentation
- Better than nothing

**Option 3: Learn organically** (weeks/months)
- Let execution_summary build up naturally
- Slower but no profiling cost
- Only learns about models actually used

## Recommendation

**Hybrid approach:**
1. **Immediately:** Manual seed top 20 models (30 min)
2. **This week:** Build profiling workflow (2 hours)
3. **Next week:** Profile tier 1 models (10 hours overnight)
4. **Ongoing:** Organic learning via execution_summary

This gives orchestrator immediate basic routing + comprehensive data within a week.
