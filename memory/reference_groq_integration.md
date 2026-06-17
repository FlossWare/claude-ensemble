---
name: groq-integration
description: Groq API integration into multi-AI arbiter/worker consensus system (llama-3.3-70b)
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-15
  priority: high
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Groq API Integration

**Status:** ACTIVE  
**Date:** 2026-06-15  
**Provider:** Groq (https://groq.com)

## API Credentials

- **API Key:** Stored in `~/.bashrc` as `GROQ_API_KEY`
- **Base URL:** `https://api.groq.com/openai/v1`
- **Secrets file:** `memory/.secrets.md`

## Available Models

**Primary (arbiter + worker):**
- `llama-3.3-70b-versatile` - Main model for consensus voting
  - Context: 128K tokens
  - Speed: **500+ tokens/sec** (FASTEST inference available)
  - Cost: $0.50/$0.80 per 1M input/output tokens
  - Strengths: Reasoning, code generation, fast iteration

**Fast (worker only):**
- `llama-3.1-8b-instant` - Ultra-fast simple tasks
  - Context: 128K tokens
  - Speed: **800+ tokens/sec**
  - Cost: $0.10/$0.20 per 1M input/output tokens
  - Use: Quick validation, simple queries

## Integration Points

### Multi-AI Consensus (Updated)

**Location:** `~/.claude/self/evaluation-harness.mjs`

**Default models:** `['opus', 'sonnet', 'haiku', 'groq']` (added groq)

**Arbiter rotation order:**
1. Fable
2. Opus
3. Sonnet
4. Haiku
5. GPT-4o
6. Gemini
7. **Groq** (NEW)

**Fallback chain:** groq → opus → sonnet → haiku

### Worker Pools

**Config:** `~/.claude/learning/groq-arbiter-config.json`

**Pools:**
- `default`: opus, sonnet, haiku, groq, gpt-4o, gemini (6 models)
- `fast`: groq-fast, haiku, groq (speed-optimized)
- `quality`: opus, groq, gpt-4o (best reasoning)
- `cost_optimized`: groq-fast, haiku, sonnet (lowest cost)

## Usage

**Bash export:**
```bash
export GROQ_API_KEY="REDACTED_GROQ_KEY"
```

**Direct API call:**
```bash
curl -s https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": "Test"}],
    "max_tokens": 100
  }' | jq -r '.choices[0].message.content'
```

**In workflows:**
```javascript
import { evaluateWithHarness } from '~/.claude/self/evaluation-harness.mjs'

const result = await evaluateWithHarness({
  output: candidateOutput,
  task: originalTask,
  models: ['opus', 'sonnet', 'haiku', 'groq'],  // groq included
  adversarial: true
})
```

**Python (OpenAI-compatible):**
```python
import openai

client = openai.OpenAI(
    api_key=os.environ['GROQ_API_KEY'],
    base_url='https://api.groq.com/openai/v1'
)

response = client.chat.completions.create(
    model='llama-3.3-70b-versatile',
    messages=[{'role': 'user', 'content': 'Test'}]
)
```

## Why Groq?

**Speed:**
- 500-800 tokens/sec vs 20-50 tok/s for other providers
- 10-40× faster inference = real-time multi-AI consensus
- Enables rapid iteration in worker/arbiter patterns

**Cost:**
- Cheaper than GPT-4o, Opus, Gemini
- Enables more consensus rounds within budget

**Quality:**
- LLaMA 3.3 70B competitive with GPT-4 on many tasks
- Strong reasoning capabilities
- Good code generation

## Test Results

**Arbiter test (2026-06-15):**
- Task: Evaluate 3 worker responses (async/await vs promises vs callbacks)
- Result: Correctly chose async/await with clear reasoning
- Response time: < 1 second
- Quality: Comparable to Opus/GPT-4o

## Integration Status

- ✅ API key stored in .bashrc
- ✅ Added to secrets.md
- ✅ Integrated into evaluation-harness.mjs
- ✅ Created groq-arbiter-config.json
- ✅ Tested as arbiter (PASS)
- ✅ Added to default model rotation

## Future Use

**Autonomous learning:**
- Use groq-fast for quick hypothesis testing
- Use groq (70B) for consensus voting
- Fallback to groq when other providers rate-limited

**Orchestrator:**
- Use groq for fast work assignment decisions
- Thompson Sampling node selection
- Real-time conflict resolution

**Fleet coordination:**
- Fast consensus across nodes
- Quick validation loops
- Rapid retry logic

---

**Why:** FASTEST multi-AI consensus iterations, cost-effective scaling, OpenAI-compatible API
