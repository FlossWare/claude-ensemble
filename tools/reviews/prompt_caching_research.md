# Prompt Caching Research: Comprehensive Findings

**Date:** 2026-07-26
**Scope:** Provider-level, application-level, and semantic caching for distributed LLM orchestration
**System Context:** 8-worker + 1-controller fleet, 200+ API models, PostgreSQL + pgvector (381K docs), Redis on aio-01:6379
**Research Method:** Autonomous web research across academic papers, production case studies, and provider documentation

---

## Table of Contents

1. [Provider-Level Prompt Caching](#1-provider-level-prompt-caching)
2. [Application-Level Response Caching](#2-application-level-response-caching)
3. [Semantic Caching](#3-semantic-caching)
4. [Prompt Prefix Caching](#4-prompt-prefix-caching)
5. [Multi-Turn Conversation Caching](#5-multi-turn-conversation-caching)
6. [Cost Analysis for Our Fleet](#6-cost-analysis-for-our-fleet)
7. [Implementation Patterns for Our System](#7-implementation-patterns-for-our-system)
8. [Open-Source Tools](#8-open-source-tools)
9. [Academic Research](#9-academic-research)
10. [Production Case Studies](#10-production-case-studies)
11. [Recommendations and Prioritized Roadmap](#11-recommendations-and-prioritized-roadmap)

---

## 1. Provider-Level Prompt Caching

Provider-level prompt caching stores the KV (key-value) attention tensors for prompt prefixes on the provider's GPU infrastructure. Subsequent requests with the same prefix skip recomputation and pay a reduced per-token rate. This is strictly an input-token optimization -- output token pricing is never affected by any provider's caching scheme.

### 1.1 Anthropic (Claude)

**Mechanism:** Explicit `cache_control` breakpoints on content blocks, or automatic top-level `cache_control`.

**Key details:**
- Cache reads cost **0.1x** standard input rate (90% discount)
- 5-minute TTL cache writes cost **1.25x** standard input rate
- 1-hour TTL cache writes cost **2x** standard input rate
- Minimum cacheable content: **1,024 tokens**
- Maximum **4 cache breakpoints** per request
- Cache TTL refreshes on each read (chatty conversations keep cache warm)
- Prompt prefix order: tools -> system -> messages
- Anything that changes by even one token invalidates everything after it

**Explicit caching example:**
```python
response = client.messages.create(
    model="claude-sonnet-4-5-20250514",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are an AI assistant. [large stable system prompt here]",
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": "User's question"}],
)
```

**Automatic caching example:**
```python
response = client.messages.create(
    model="claude-sonnet-4-5-20250514",
    max_tokens=1024,
    cache_control={"type": "ephemeral"},  # top-level automatic
    system="Your system prompt...",
    messages=[...],
)
```

**Gotchas:**
- Tools are part of the cached prefix; changing any tool definition invalidates the system cache
- Maximum 20 content blocks lookback window per breakpoint
- JSON key ordering must be stable (Swift, Go can randomize key order, breaking caches)
- Working memory or dynamic content in the system prompt destroys hit rates (ProjectDiscovery went from 7% to 84% by relocating dynamic content to a user message at the end)

**Applicability to our system:** HIGH. Every workflow sends the same system prompt + tool definitions repeatedly across 20-40 steps. Direct integration via the Anthropic SDK.

**Implementation complexity:** LOW (add `cache_control` to existing API calls)

**Expected benefit:** 60-90% reduction in Anthropic input token costs, up to 85% latency reduction

Sources: [Anthropic Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Introl Prompt Caching Infrastructure Guide](https://introl.com/blog/prompt-caching-infrastructure-llm-cost-latency-reduction-guide-2025)

---

### 1.2 OpenAI (GPT-4o, GPT-5.x)

**Mechanism:** Fully automatic -- no code changes required.

**Key details:**
- Cache reads cost **0.1x** on newer models (was 0.5x initially, raised to match Anthropic)
- **No cache write fee** on models before GPT-5.6; GPT-5.6+ charge for writes
- Activates automatically for prompts >= **1,024 tokens**
- Caches in **128-token increments** beyond initial 1,024
- TTL: 5-10 minutes of inactivity (cleared within 1 hour)
- Extended 24-hour retention available on GPT-5.1 series and GPT-4.1

**Gotchas:**
- Entirely automatic; no developer control over what gets cached
- Only exact prefix matching (no semantic similarity)
- No way to force cache writes or monitor breakpoints
- For low cache-hit workloads (<3 hits per write cycle), the no-write-fee structure wins over Anthropic

**Applicability to our system:** MEDIUM. We access OpenAI models primarily through OpenRouter, which handles pass-through. Automatic caching applies when prompts share stable prefixes.

**Implementation complexity:** ZERO (automatic)

**Expected benefit:** 50-90% input token cost reduction depending on prefix stability

Sources: [OpenAI Prompt Caching](https://openai.com/index/api-prompt-caching/), [OpenAI Caching Docs](https://developers.openai.com/api/docs/guides/prompt-caching), [PromptHub Comparison](https://www.prompthub.us/blog/prompt-caching-with-openai-anthropic-and-google-models)

---

### 1.3 Google Gemini

**Mechanism:** Two modes -- implicit (automatic) and explicit (developer-controlled).

**Implicit caching (Gemini 2.5+):**
- Enabled by default since May 2025
- 90% discount on cached tokens
- No storage costs
- No code changes required

**Explicit caching:**
- Developer creates caches with custom TTL (default 1 hour)
- Cache reads: ~90% discount ($0.20-0.40/M vs $2-4/M)
- Cache writes: $0.50/M (one-time)
- **Storage: $1.00-4.50/M tokens/hour** (this is the trap -- a 1M-token cache held for 24h costs $24-108 in storage alone)
- Minimum tokens: 1,024 (Flash), 4,096 (Pro)

**Gotchas:**
- Explicit cache storage costs can exceed savings if TTL is too long or reuse is low
- Must actively manage cache lifecycle (create, extend TTL, delete)
- Default recommendation: rely on implicit caching; only use explicit for high-reuse Pro-tier paths

**Applicability to our system:** MEDIUM. We use Gemini models via Google API and OpenRouter. Implicit caching gives automatic benefit; explicit caching requires careful cost modeling.

**Implementation complexity:** LOW (implicit), MEDIUM (explicit)

**Expected benefit:** 75-90% input token cost reduction; watch storage costs on explicit

Sources: [Gemini Context Caching Docs](https://ai.google.dev/gemini-api/docs/caching), [Gemini Pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini Cost Optimization Guide](https://techjacksolutions.com/ai-tools/google-gemini/gemini-context-caching-cost-optimization/)

---

### 1.4 DeepSeek

**Mechanism:** Automatic "Context Caching on Disk" -- enabled by default for all users.

**Key details:**
- Cache hits are **90% cheaper** than standard input pricing
- Automatic prefix matching; no code changes
- Best-effort system (no guaranteed 100% hit rate)
- Cache construction takes seconds; unused entries cleared within hours to days
- API response includes `prompt_cache_hit_tokens` and `prompt_cache_miss_tokens`

**Gotchas:**
- Best-effort, not guaranteed
- Only prefix caching (content must share the same front-loaded context)
- Not available through Azure AI Foundry (no prefix caching on Azure-hosted DeepSeek)

**Applicability to our system:** HIGH. DeepSeek models are used via direct API and OpenRouter. Automatic benefit with stable prompts.

**Implementation complexity:** ZERO (automatic)

**Expected benefit:** Up to 90% input cost reduction

Sources: [DeepSeek Context Caching Docs](https://api-docs.deepseek.com/guides/kv_cache/), [DeepSeek Caching Guide](https://deepseekv4pro.com/guides/deepseek-context-caching-hit-rules)

---

### 1.5 Groq

**Mechanism:** Automated prompt caching, currently available on select models only (Kimi K2).

**Key details:**
- Cache reads at **0.5x** standard input rate (50% discount)
- Limited model support
- No configuration required

**Applicability to our system:** LOW. Limited model support. Groq is primarily used for fast inference, not cost optimization.

**Implementation complexity:** ZERO

**Expected benefit:** Marginal (50% on limited models)

---

### 1.6 Cerebras

**No documented prompt caching support.** Cerebras focuses on raw inference speed via their wafer-scale chips rather than cost-optimization features.

**Applicability to our system:** NONE

---

### 1.7 OpenRouter (Aggregation Layer)

OpenRouter provides two distinct caching mechanisms:

**Provider prompt caching pass-through:**
- Passes `cache_control` and other caching directives to underlying providers
- Uses **sticky routing** to maximize cache hits (routes subsequent requests to same provider)
- Sticky routing keys based on `session_id` header or conversation fingerprint
- Provider-specific discounts apply (Anthropic 0.1x, DeepSeek 0.1x, OpenAI 0.1-0.5x, Gemini 0.25x, Groq 0.5x)
- Monitor via `prompt_tokens_details` and `cache_discount` in response

**Response caching (announced April 2026):**
- Completely separate from prompt caching
- Add `X-OpenRouter-Cache: true` header
- First call billed normally; subsequent identical calls return cached response at **zero cost**
- Cached responses in 80-300ms (cache lookup averages 4ms)
- Scoped to API key
- Default TTL: 300 seconds (configurable)
- Works with streaming, text, images, audio, tool calls
- Response headers: `X-OpenRouter-Cache-Status: HIT/MISS`, `X-OpenRouter-Cache-Age`, `X-OpenRouter-Cache-TTL`
- Clear cache: `X-OpenRouter-Cache-Clear: true`

**Applicability to our system:** VERY HIGH. OpenRouter is our primary model provider (150+ models). Response caching is immediately applicable for agent retries, test suites, and repeated context processing. Prompt caching pass-through benefits all supported providers.

**Implementation complexity:** LOW (add headers to API calls)

**Expected benefit:** Zero cost on identical retried requests; provider-level prompt caching savings pass through

Sources: [OpenRouter Prompt Caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching), [OpenRouter Response Caching](https://openrouter.ai/blog/announcements/response-caching/), [OpenRouter Sticky Routing](https://openrouter.ai/blog/tutorials/prompt-caching-sticky-routing/)

---

## 2. Application-Level Response Caching

Application-level response caching stores LLM outputs keyed by request parameters and serves them directly on cache hit, bypassing the API entirely.

### 2.1 Exact-Match Caching

**How it works:** SHA-256 hash of (prompt, model, temperature, other params) as cache key. O(1) lookup.

**When safe to cache:**
- `temperature=0` (deterministic output)
- Factual queries with stable answers
- Same model version, same system prompt
- NOT safe for: creative tasks, time-sensitive queries, personalized responses

**Cache key composition:**
```
SHA256(model + system_prompt_version + user_query + temperature + max_tokens + tool_definitions_hash)
```

**Redis implementation pattern:**
```javascript
const crypto = require('crypto');
const Redis = require('ioredis');
const redis = new Redis('redis://aio-01:6379');

function cacheKey(model, prompt, params) {
  const hash = crypto.createHash('sha256')
    .update(JSON.stringify({ model, prompt, temperature: params.temperature }))
    .digest('hex');
  return `llm:response:${hash}`;
}

async function cachedCall(model, prompt, params) {
  const key = cacheKey(model, prompt, params);
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached);
  
  const response = await callLLM(model, prompt, params);
  await redis.setex(key, 3600, JSON.stringify(response)); // 1h TTL
  return response;
}
```

**Implementation complexity:** LOW

**Expected benefit:** 100% cost savings on cache hits; 40-60% hit rate for FAQ/documentation workloads, lower for diverse queries

**Risks:**
- Stale responses served after underlying data changes
- Must invalidate on model version updates or system prompt changes
- Storage growth if TTL is too long

**Applicability to our system:** HIGH. Many fleet workflows repeat similar queries across workers. Redis on aio-01:6379 is already deployed.

---

### 2.2 Redis vs PostgreSQL for Cache Storage

| Factor | Redis | PostgreSQL |
|--------|-------|------------|
| Lookup latency | Sub-millisecond | 1-5ms |
| TTL support | Native (SETEX/EXPIRE) | Must implement manually |
| Memory model | In-memory | Disk + buffer cache |
| Eviction policy | Built-in (LRU, LFU, etc.) | Manual cleanup |
| Clustering | Redis Sentinel (already deployed) | Single instance |
| Vector search | Redis Search + FT.SEARCH | pgvector (already deployed) |
| Best for | Exact-match cache | Semantic cache, persistent storage |

**Recommendation:** Use Redis for exact-match caching (fast, TTL-native, already deployed). Use pgvector for semantic caching (already has 381K docs with embeddings, proven 2x faster for simple similarity).

---

## 3. Semantic Caching

Semantic caching uses vector embeddings to find "similar enough" past queries and reuse their responses, catching paraphrased queries that exact-match misses.

### 3.1 How It Works

1. Incoming query is converted to an embedding vector (768 or 1536 dimensions)
2. Vector similarity search against cached query embeddings (cosine similarity)
3. If similarity exceeds threshold, return cached response
4. If miss, call LLM, store response + embedding

### 3.2 Similarity Thresholds

| Threshold | Behavior | Use Case |
|-----------|----------|----------|
| 0.98 | Near-exact match only | Sensitive/factual queries |
| 0.92-0.95 | Catches clear rephrasings | Production sweet spot |
| 0.85-0.90 | Broader matching, more false positives | FAQ bots, low-risk |

**Critical insight:** The overlap zone between correct and incorrect cache hits is 0.85-0.92. There is no single threshold that eliminates false positives while maintaining good hit rates. Domain-specific embeddings improve precision from 64-78% to 84-92% at standard thresholds.

### 3.3 Risks and Gotchas

**False positive matches (CRITICAL):**
- "What is the capital of France?" and "What is the capital of Germany?" sit close in embedding space
- "How do I upgrade my subscription?" vs "How do I cancel my subscription?" -- semantically adjacent, opposite intent
- A system cached one user's delivery status and served it to another user asking the same question about *their* delivery

**Stale/outdated responses:**
- Unlike prefix cache (which triggers fresh LLM reasoning on cached context), semantic cache returns the old answer verbatim
- No mechanism to detect when a cached answer has become factually wrong

**Cache poisoning:**
- If the LLM hallucinates on the original query, every similar future query gets the same hallucination
- Error amplification is the worst failure mode

**Silent failures:**
- Bad cache hits return incorrect answers with 200 OK status
- Without instrumentation, you cannot tell if the system is working or silently degrading

### 3.4 Mitigation Strategies

1. **Scope caches narrowly:** Include model, tenant, locale, system_prompt_version in cache key metadata (hash exactly, not semantically)
2. **Only compare the last user message semantically:** Everything else (model, temperature, system prompt, prior messages) must be exact-matched via hash
3. **Never cache personalized, time-sensitive, or stateful responses**
4. **Use a cheap model as gatekeeper:** Route top semantic candidates through GPT-4o-mini to judge query equivalence before serving cached response
5. **Log every hit with similarity score:** Monitor for score clustering at the threshold boundary
6. **Correlate user feedback with cache hit/miss status:** If cached responses score lower, threshold is too low

### 3.5 Realistic Hit Rates

- Academic benchmarks claim 80-95% hit rates on curated datasets
- **Production reality: 20-45% hit rate** (60-70% of real queries are genuinely unique)
- FAQ-style applications can reach 50-60% with well-tuned thresholds
- Combined with exact-match as first layer, overall hit rate can reach 60-70%

### 3.6 pgvector Implementation for Our System

We already have pgvector with 381K docs and proven 2x performance advantage over ChromaDB. A semantic response cache table:

```sql
CREATE TABLE learning.response_cache (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding vector(384),  -- match our existing 384-dim embeddings
    model TEXT NOT NULL,
    system_prompt_version TEXT NOT NULL,
    temperature FLOAT NOT NULL,
    response_text TEXT NOT NULL,
    response_tokens INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INTEGER DEFAULT 0,
    similarity_score FLOAT  -- score when this was a cache miss (for analysis)
);

CREATE INDEX ON learning.response_cache 
  USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX ON learning.response_cache (model, system_prompt_version);
CREATE INDEX ON learning.response_cache (expires_at);
```

**Lookup query:**
```sql
SELECT response_text, 1 - (query_embedding <=> $1::vector) AS similarity
FROM learning.response_cache
WHERE model = $2
  AND system_prompt_version = $3
  AND temperature = $4
  AND expires_at > NOW()
  AND 1 - (query_embedding <=> $1::vector) > 0.92
ORDER BY query_embedding <=> $1::vector
LIMIT 1;
```

**Implementation complexity:** MEDIUM

**Expected benefit:** 20-45% additional cache hits beyond exact-match; 100% cost savings on those hits

**Applicability to our system:** HIGH. We already have pgvector infrastructure and embedding generation capabilities.

Sources: [Redis Semantic Caching](https://redis.io/blog/what-is-semantic-caching/), [Portkey Semantic Caching Thresholds](https://portkey.ai/blog/semantic-caching-thresholds/), [TrueFoundry Semantic Caching](https://www.truefoundry.com/blog/semantic-caching-ai-gateway), [PyImageSearch Semantic Caching](https://pyimagesearch.com/2026/04/27/semantic-caching-for-llms-fastapi-redis-and-embeddings/)

---

## 4. Prompt Prefix Caching

### 4.1 KV Cache Mechanics

During the prefill phase of LLM inference, each token attends to all previous tokens via causal self-attention, computing Query, Key, and Value tensors across all transformer layers. KV caching stores these intermediate attention states. Prefix caching extends this across requests: if request B shares a prefix with request A, request B can skip recomputing the KV states for that shared prefix.

### 4.2 Optimal Prompt Structure

The single most important optimization is **prompt ordering**. Content must be ordered from most stable to least stable:

```
1. Tool definitions        (rarely change)
2. System prompt          (changes per deployment, not per request)
3. Reference documents    (change per session, not per turn)
4. Conversation history   (grows each turn, but prefix is stable)
5. Working memory/state   (changes every step -- MUST be last)
6. Current user query     (changes every request)
```

**Anti-pattern:** Putting timestamps, session IDs, or dynamic state anywhere in the prefix. Even `"Today's date is July 26, 2026"` in a system prompt invalidates the entire cache every day.

### 4.3 Anthropic cache_control Breakpoint Strategy

With a maximum of 4 breakpoints across system + tools + messages:

```
Breakpoint 1: End of tool definitions (rarely changes)
Breakpoint 2: End of system prompt (changes per deployment)
Breakpoint 3: End of reference docs / few-shot examples
Breakpoint 4: Rolling window on recent conversation turns
```

**The 20-block lookback limitation:** A breakpoint can only see 20 content blocks before it. In long tool-use loops, add intermediate breakpoints every ~18 blocks to maintain cache coverage.

**Budget strategy:** System (1 BP) + tools (1 BP) + messages (remaining 2 BPs). Never exceed 4 total.

### 4.4 Multi-Provider Prefix Strategy

Since we use multiple providers, structure prompts uniformly:
- Same system prompt order across all providers
- Static content first, dynamic content last
- This benefits Anthropic (explicit), OpenAI (automatic), DeepSeek (automatic), and Gemini (implicit) simultaneously

**Implementation complexity:** LOW-MEDIUM (prompt restructuring, no new infrastructure)

**Expected benefit:** 60-90% input cost reduction across all providers with proper prefix structure

Sources: [KV-Cache Aware Prompt Engineering](https://ankitbko.github.io/blog/2025/08/prompt-engineering-kv-cache/), [Modular Prefix Caching Handbook](https://handbook.modular.com/inference-optimization/prefix-caching/), [ProjectDiscovery Case Study](https://projectdiscovery.io/blog/how-we-cut-llm-cost-with-prompt-caching)

---

## 5. Multi-Turn Conversation Caching

### 5.1 How It Applies

Multi-turn conversation is where prefix caching provides the largest benefit. Each turn re-sends the entire conversation history. As the conversation grows, the reusable prefix grows with it:

```
Turn 1: [system + tools] + user_1                    -> prefix: system+tools (cached)
Turn 2: [system + tools + user_1 + assistant_1] + user_2  -> prefix grows (more cached)
Turn 3: [system + tools + user_1 + asst_1 + user_2 + asst_2] + user_3 -> even more cached
```

Each turn benefits from progressively more cached computation.

### 5.2 Session-Based Caching Strategy

For our fleet's workflow execution:

1. **Workflow-level session:** All steps in a single workflow share the same system prompt and accumulate conversation context. Provider caching handles this naturally.
2. **Cross-workflow deduplication:** Different workflows using the same system prompt benefit from shared prefix caching.
3. **OpenRouter session_id:** Set `session_id` per workflow execution to ensure sticky routing keeps cache warm across all steps.

```javascript
const sessionId = `workflow-${workflowId}-${Date.now()}`;
const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
  headers: {
    'X-Session-Id': sessionId,
    'X-OpenRouter-Cache': 'true',  // response caching for retries
  },
  body: JSON.stringify({
    model: 'anthropic/claude-sonnet-4-5-20250514',
    messages: [...],
  }),
});
```

### 5.3 Incremental Context Building

Rather than reconstructing the full conversation from scratch each turn:
- Append new messages to the existing array (don't rebuild)
- Keep the system prompt byte-identical across turns
- Never inject turn-specific metadata (timestamps, step counters) into the prefix

**Implementation complexity:** LOW (mostly prompt discipline)

**Expected benefit:** Compounds with conversation length. A 20-step workflow can cache 90%+ of input tokens by step 20.

---

## 6. Cost Analysis for Our Fleet

### 6.1 Current Estimated Usage

Assuming 1,000+ queries/day across the fleet:

| Parameter | Estimate |
|-----------|----------|
| Average queries/day | 1,000-2,000 |
| Average input tokens/query | 4,000-8,000 |
| Average output tokens/query | 500-2,000 |
| Daily input tokens | 4M-16M |
| Monthly input tokens | 120M-480M |
| System prompt tokens (stable) | 2,000-4,000 per query |
| Tool definition tokens (stable) | 500-2,000 per query |

### 6.2 Cacheable Token Analysis

| Token Category | % of Input | Cacheable? | Cache Type |
|----------------|------------|------------|------------|
| System prompt | 30-50% | YES | Provider prefix cache |
| Tool definitions | 10-20% | YES | Provider prefix cache |
| Reference docs | 10-20% | YES | Provider prefix cache |
| Conversation history | 10-30% | YES (grows per turn) | Provider prefix cache |
| Dynamic state/query | 10-20% | NO (changes each request) | Not cacheable |

**Result:** 60-80% of input tokens are cacheable via provider prefix caching alone.

### 6.3 Savings Projections

**Scenario: 1,500 queries/day, 6,000 avg input tokens, 70% cacheable, 80% cache hit rate**

| Layer | Before | After | Monthly Savings |
|-------|--------|-------|-----------------|
| Provider prefix caching (Anthropic 90% discount) | $810/mo | $243/mo | $567 (70%) |
| Provider prefix caching (OpenAI 50-90% discount) | $405/mo | $162/mo | $243 (60%) |
| Application response cache (40% hit rate) | - | -$120/mo additional | $120 (eliminated API calls) |
| Semantic cache (20% additional hits) | - | -$60/mo additional | $60 |
| OpenRouter response cache (agent retries) | - | -$45/mo | $45 |
| **Combined estimate** | **$1,215/mo** | **$365-$500/mo** | **$715-$850/mo (60-70%)** |

**Conservative estimate:** 40-50% total cost reduction
**Optimistic estimate:** 70-80% total cost reduction (high cache hit rates + well-structured prompts)

### 6.4 Latency Impact

| Optimization | Latency Reduction |
|-------------|-------------------|
| Provider prefix cache hit | 50-85% TTFT reduction |
| Application response cache hit | 95%+ (Redis sub-ms vs 1-10s API) |
| Semantic cache hit | 90%+ (pgvector <1ms vs API call) |
| OpenRouter response cache hit | 95%+ (80-300ms vs 1-10s) |

### 6.5 Break-Even Analysis

**Provider prefix caching:** No infrastructure cost; break-even is immediate. Anthropic's 1.25x write fee is amortized if you get >= 2 cache reads per write within the TTL window. At >= 5 reads per write, the write fee is negligible.

**Application response cache (Redis):** Redis is already deployed. No additional infrastructure cost. Break-even: immediate.

**Semantic cache (pgvector):** PostgreSQL is already deployed. Embedding computation cost (~$0.01/1000 queries for local embeddings) vs savings from eliminated API calls (~$0.01-0.10/query). Break-even: ~100 queries cached.

**Gemini explicit cache (caution):** Storage costs $1-4.50/M tokens/hour. A 100K-token cache held for 24h costs $2.40-10.80. Only profitable if used >= 10 times during that window. Prefer implicit caching unless high-reuse is guaranteed.

Sources: [ProjectDiscovery 59% Cost Reduction](https://projectdiscovery.io/blog/how-we-cut-llm-cost-with-prompt-caching), [Enterprise LLM Cost Optimization](https://techcloudpro.com/blog/enterprise-llm-cost-optimization/), [AWS LLM Caching Guide](https://aws.amazon.com/blogs/database/optimize-llm-response-costs-and-latency-with-effective-caching/), [Mavik Labs Cost Optimization](https://www.maviklabs.com/blog/llm-cost-optimization-2026)

---

## 7. Implementation Patterns for Our System

### 7.1 Redis-Based Response Cache with TTL

**Priority: HIGH (implement first)**

```javascript
// shared/llm-response-cache.js
const Redis = require('ioredis');
const crypto = require('crypto');

const redis = new Redis('redis://aio-01:6379');
const DEFAULT_TTL = 3600; // 1 hour

function computeCacheKey(model, messages, params) {
  const normalized = {
    model,
    messages: messages.map(m => ({ role: m.role, content: m.content })),
    temperature: params.temperature || 0,
    max_tokens: params.max_tokens,
    system_prompt_hash: crypto.createHash('sha256')
      .update(params.system || '').digest('hex').slice(0, 16),
  };
  return 'llm:resp:' + crypto.createHash('sha256')
    .update(JSON.stringify(normalized)).digest('hex');
}

async function getCached(model, messages, params) {
  if ((params.temperature || 0) > 0) return null; // Only cache deterministic
  const key = computeCacheKey(model, messages, params);
  const cached = await redis.get(key);
  if (cached) {
    await redis.hincrby('llm:cache:stats', 'hits', 1);
    return JSON.parse(cached);
  }
  await redis.hincrby('llm:cache:stats', 'misses', 1);
  return null;
}

async function setCached(model, messages, params, response, ttl = DEFAULT_TTL) {
  if ((params.temperature || 0) > 0) return; // Don't cache non-deterministic
  const key = computeCacheKey(model, messages, params);
  await redis.setex(key, ttl, JSON.stringify(response));
  await redis.hincrby('llm:cache:stats', 'stores', 1);
}

async function getStats() {
  return redis.hgetall('llm:cache:stats');
}

module.exports = { getCached, setCached, getStats };
```

**TTL strategy by query type:**
- Code review system prompts: 24h (rarely change)
- Factual/documentation queries: 4h
- Analysis tasks: 1h
- Time-sensitive queries: 5-15m
- Creative/generative tasks: DO NOT CACHE

---

### 7.2 Semantic Similarity Cache Using pgvector

**Priority: MEDIUM (implement after exact-match)**

Uses our existing pgvector infrastructure and embedding generation.

```javascript
// shared/semantic-response-cache.js
const { getDB } = require('./postgres-adapter.js');

const SIMILARITY_THRESHOLD = 0.92;
const DEFAULT_TTL_HOURS = 4;

async function findSimilarCachedResponse(queryEmbedding, model, systemVersion) {
  const db = getDB();
  const result = await db.query(`
    SELECT response_text, 1 - (query_embedding <=> $1::vector) AS similarity,
           hit_count, created_at
    FROM learning.response_cache
    WHERE model = $2
      AND system_prompt_version = $3
      AND expires_at > NOW()
      AND 1 - (query_embedding <=> $1::vector) > $4
    ORDER BY query_embedding <=> $1::vector
    LIMIT 1
  `, [queryEmbedding, model, systemVersion, SIMILARITY_THRESHOLD]);
  
  if (result.rows.length > 0) {
    // Update hit count
    await db.query(`
      UPDATE learning.response_cache SET hit_count = hit_count + 1
      WHERE id = $1
    `, [result.rows[0].id]);
    return result.rows[0];
  }
  return null;
}

async function storeCachedResponse(queryText, queryEmbedding, model, systemVersion, 
                                    temperature, responseText, responseTokens) {
  const db = getDB();
  await db.query(`
    INSERT INTO learning.response_cache 
    (query_text, query_embedding, model, system_prompt_version, temperature, 
     response_text, response_tokens, expires_at)
    VALUES ($1, $2::vector, $3, $4, $5, $6, $7, NOW() + INTERVAL '${DEFAULT_TTL_HOURS} hours')
  `, [queryText, queryEmbedding, model, systemVersion, temperature, 
      responseText, responseTokens]);
}
```

**Safety guardrails:**
- Only cache when `temperature = 0`
- Never cache responses containing user-specific data
- Require model + system_prompt_version exact match before semantic comparison
- Log all hits with similarity scores for monitoring
- Start at threshold 0.95, tune down after validation

---

### 7.3 Provider-Specific cache_control Headers

**Priority: HIGH (implement alongside response cache)**

**For Anthropic (direct API):**
```javascript
// Restructured prompt for maximum cache hits
async function callAnthropic(systemPrompt, tools, messages) {
  return client.messages.create({
    model: 'claude-sonnet-4-5-20250514',
    max_tokens: 4096,
    system: [
      {
        type: 'text',
        text: systemPrompt,
        cache_control: { type: 'ephemeral', ttl: '1h' }  // BP1: system prompt
      }
    ],
    tools: tools.map((tool, i) => ({
      ...tool,
      ...(i === tools.length - 1 ? { cache_control: { type: 'ephemeral' } } : {})
      // BP2: last tool definition
    })),
    messages: messages,
  });
}
```

**For OpenRouter:**
```javascript
async function callOpenRouter(model, messages, workflowId) {
  return fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${PERSONAL_OPENROUTER_API_KEY}`,
      'Content-Type': 'application/json',
      'X-Session-Id': `wf-${workflowId}`,        // Sticky routing for cache hits
      'X-OpenRouter-Cache': 'true',               // Response caching for retries
    },
    body: JSON.stringify({
      model,
      messages,
      // For Anthropic models through OpenRouter, cache_control is passed through
    }),
  });
}
```

---

### 7.4 Cache Warming Strategies

**Priority: LOW (implement after monitoring shows cold-start issues)**

1. **Replay query logs after flush:** After cache clear or deployment, replay the top 100 most common queries from the last 24h
2. **Pre-warm during deployment:** Run standard system prompts through each provider to populate prefix caches
3. **Scheduled pre-warming:** During off-peak hours, pre-populate document chunk caches

```javascript
async function warmCache(topQueries) {
  for (const query of topQueries) {
    const response = await callLLM(query.model, query.messages, query.params);
    await setCached(query.model, query.messages, query.params, response);
  }
}

// Warm with top queries from learning.experiences
async function warmFromHistory() {
  const db = getDB();
  const topQueries = await db.query(`
    SELECT model, task_description, COUNT(*) as frequency
    FROM learning.experiences
    WHERE created_at > NOW() - INTERVAL '7 days'
    GROUP BY model, task_description
    ORDER BY frequency DESC
    LIMIT 100
  `);
  // ... generate and cache responses
}
```

---

### 7.5 Cache Hit Rate Monitoring

**Priority: HIGH (implement with any caching layer)**

```javascript
// shared/cache-metrics.js
const { getDB } = require('./postgres-adapter.js');

async function recordCacheMetrics(cacheType, hit, model, latencyMs, similarityScore) {
  const db = getDB();
  await db.query(`
    INSERT INTO monitoring.cache_metrics 
    (cache_type, is_hit, model, latency_ms, similarity_score, recorded_at)
    VALUES ($1, $2, $3, $4, $5, NOW())
  `, [cacheType, hit, model, latencyMs, similarityScore]);
}

// Prometheus-compatible metrics endpoint
async function getCacheMetricsSummary(windowHours = 24) {
  const db = getDB();
  return db.query(`
    SELECT cache_type, 
           COUNT(*) FILTER (WHERE is_hit) AS hits,
           COUNT(*) FILTER (WHERE NOT is_hit) AS misses,
           ROUND(100.0 * COUNT(*) FILTER (WHERE is_hit) / COUNT(*), 1) AS hit_rate_pct,
           AVG(latency_ms) FILTER (WHERE is_hit) AS avg_hit_latency_ms,
           AVG(latency_ms) FILTER (WHERE NOT is_hit) AS avg_miss_latency_ms
    FROM monitoring.cache_metrics
    WHERE recorded_at > NOW() - INTERVAL '${windowHours} hours'
    GROUP BY cache_type
  `);
}
```

**Alert thresholds:**
- Hit rate < 30% on stable-prompt workload: structural problem (check prompt ordering)
- Hit rate < 60% when expected > 70%: possible cache invalidation issue
- Similarity score clustering at threshold boundary: threshold needs adjustment
- Cache-hit response quality degradation (correlate with user feedback)

---

### 7.6 Cache Invalidation Strategy

**Versioned keys + TTL + event-driven invalidation:**

```javascript
const SYSTEM_PROMPT_VERSION = 'v3.2';  // Bump on system prompt changes
const TOOL_DEF_VERSION = 'v1.8';       // Bump on tool definition changes

function cacheKeyWithVersion(model, query, params) {
  return crypto.createHash('sha256').update(JSON.stringify({
    model,
    sys_version: SYSTEM_PROMPT_VERSION,
    tool_version: TOOL_DEF_VERSION,
    query,
    temperature: params.temperature,
  })).digest('hex');
}

// Event-driven: flush cache on deployment
async function onDeployment(newVersion) {
  // Old versioned keys stop matching automatically
  // Optionally flush entire cache namespace
  const keys = await redis.keys('llm:resp:*');
  if (keys.length) await redis.del(...keys);
}
```

---

## 8. Open-Source Tools

### 8.1 GPTCache (Zilliz)

**What:** Open-source semantic cache library for LLM applications (Python).

**Features:**
- Semantic caching via embeddings + vector store
- Integrations with LangChain, LlamaIndex, OpenAI, Anthropic
- Modular architecture: swap embedding model, vector store, eviction policy
- Supports OpenAI, Hugging Face, Cohere, SentenceTransformers embedding APIs

**Current status (2025-2026):** The project no longer adds support for new APIs/models. Recommends using the `get`/`set` API for custom integrations. Maintenance mode.

**Applicability:** LOW for our system. We already have pgvector and Redis. GPTCache adds complexity without providing infrastructure we lack. Better to build on what we have.

Sources: [GPTCache GitHub](https://github.com/zilliztech/GPTCache), [GPTCache Docs](https://gptcache.readthedocs.io/en/latest/)

---

### 8.2 LiteLLM Caching

**What:** Multi-provider LLM proxy with built-in caching.

**Features:**
- **Dual cache architecture:** L1 in-memory + L2 Redis
- Redis circuit breaker (CLOSED -> OPEN -> HALF_OPEN) for resilience
- Semantic caching via Redis or Qdrant
- Per-request cache control (`no-cache`, `no-store`, `ttl`, `namespace`)
- Redis Sentinel and Cluster support
- Provider-native prompt caching pass-through (Anthropic, Gemini)

**Configuration:**
```yaml
litellm_settings:
  cache: True
  cache_params:
    type: redis
    host: aio-01
    port: 6379
```

**Applicability:** MEDIUM. If we adopted LiteLLM as our API gateway, caching would come for free. However, integrating an entire proxy layer is a larger architectural decision. The caching patterns are worth studying for our own implementation.

Sources: [LiteLLM Caching Docs](https://docs.litellm.ai/docs/proxy/caching), [LiteLLM Cache Types](https://docs.litellm.ai/docs/caching/all_caches)

---

### 8.3 LangChain Cache

**What:** Built-in caching for LangChain LLM calls.

**Options:**
- `InMemoryCache` -- development/testing
- `RedisCache` -- production exact-match
- `RedisSemanticCache` -- production semantic matching
- `SQLiteCache` -- lightweight persistent cache

**Redis setup:**
```python
from langchain_redis import RedisCache, RedisSemanticCache
from langchain.globals import set_llm_cache

# Exact match
cache = RedisCache(redis_url="redis://aio-01:6379", ttl=3600)
set_llm_cache(cache)

# Semantic
semantic_cache = RedisSemanticCache(
    redis_url="redis://aio-01:6379",
    embedding=your_embedding_model,
    distance_threshold=0.1  # Redis cosine distance [0-2], lower = stricter
)
```

**Performance:** 25.4x speed improvement on cache hits.

**Applicability:** LOW-MEDIUM. Useful if we adopt LangChain for Python workflows. Our JavaScript-first architecture is better served by custom Redis/pgvector integration.

Sources: [LangChain Redis Integration](https://docs.langchain.com/oss/python/integrations/providers/redis), [langchain-redis PyPI](https://pypi.org/project/langchain-redis/)

---

### 8.4 Redis LangCache (Managed Service)

**What:** Redis's managed semantic caching service.

**Features:**
- Custom embedding model (`redis/langcache-embed-v3-small`) optimized for caching
- Managed infrastructure
- Drop-in integration with existing Redis deployments

**Applicability:** LOW. We run our own Redis. The custom embedding model is interesting but we already have embedding infrastructure.

---

### 8.5 LMCache

**What:** Open-source KV cache management library for self-hosted LLM inference (vLLM integration).

**Features:**
- Tiered storage: GPU -> CPU RAM -> local disk -> Redis
- Non-prefix KV reuse (CacheBlend) for RAG workloads (4.5x speedup)
- Engine-independent deployment
- 1.3-3x throughput improvement

**Applicability:** NONE for our current system (API-only fleet, no self-hosted inference). Would be relevant if we ever return to local model hosting.

Sources: [LMCache GitHub](https://github.com/LMCache/LMCache), [LMCache Technical Report](https://lmcache.ai/tech_report.pdf)

---

## 9. Academic Research

### 9.1 Key Papers

| Paper | Venue | Key Contribution |
|-------|-------|-----------------|
| **A Survey on LLM Acceleration based on KV Cache Management** (Li et al., 2024) | arXiv 2412.19442 | Comprehensive survey of KV cache strategies |
| **Don't Break the Cache** (Jan 2026) | arXiv 2601.06007 | First quantified evaluation of prompt caching for agentic workloads |
| **CacheGen** (Liu et al., 2024) | ACM SIGCOMM 2024 | KV cache compression + streaming for fast serving |
| **PromptCache** (2024) | MLSys 2024 | Modular attention reuse beyond simple prefix matching |
| **CacheBlend** (2025) | ACM EuroSys 2025 | Non-prefix KV reuse, 4.5x RAG speedup with 10% recomputation |
| **KVCache in the Wild** (Jun 2025) | arXiv 2506.02634 | Characterization at Aliyun scale: multi-turn reuse patterns |
| **The Pitfalls of KV Cache Compression** (Sep 2025) | arXiv 2510.00231 | Warns about quality degradation under multi-instruction prompting |
| **GPT Semantic Cache** (Nov 2024) | arXiv 2411.05276 | Semantic embedding caching for cost/latency reduction |

### 9.2 Key Findings from Research

1. **Prefix caching dominates:** Provider-managed prefix caching delivers the highest ROI with the lowest implementation complexity. It is a structural cost reduction with no quality tradeoff.

2. **Agentic workloads benefit most:** The "agentic tax" compounds quadratically -- step N re-sends everything from steps 1 through N-1. Caching is the only structural fix.

3. **Prompt structure matters more than cache tuning:** ProjectDiscovery's jump from 7% to 84% hit rate came from relocating dynamic content, not tuning TTL or breakpoints.

4. **Semantic caching has an inherent precision/recall ceiling:** The overlap zone between correct and incorrect hits (0.85-0.92 cosine similarity) cannot be eliminated by threshold tuning alone. Domain-specific embeddings are the best mitigation.

5. **Non-prefix caching is an emerging frontier:** CacheBlend and similar techniques enable KV reuse for RAG workloads where document ordering varies. Not yet available in commercial APIs.

Sources: [arXiv 2412.19442](https://arxiv.org/abs/2412.19442), [arXiv 2601.06007](https://arxiv.org/abs/2601.06007), [LMCache Blog](https://blog.lmcache.ai/en/2024/10/09/beyond-prefix-caching-how-lmcache-speeds-up-rag-by-4-5x-by-one-line-of-change/)

---

## 10. Production Case Studies

### 10.1 ProjectDiscovery (AI Security Agent)

- **Before:** 7% cache hit rate, system prompt in wrong position
- **Fix:** Moved dynamic working memory from system prompt to user message at end
- **After:** 84% hit rate, 59% cost reduction (peaking at 70%)
- **Scale:** 9.8 billion tokens served from cache
- **Key insight:** "The gap between 7% and 74% is not a model tuning problem. It is a token layout problem."

### 10.2 Aggregate Industry Data (2025-2026)

- Enterprise teams routinely spend $30K-100K/month on API calls
- Well-implemented caching achieves 40-65% cost reduction without quality degradation
- Average prompt length grew 4x between early 2024 and late 2025 (1,500 to 6,000 tokens), making caching more valuable
- Combined prompt caching + semantic caching + routing optimization achieves 60-80% savings

### 10.3 Lessons for Our Fleet

| Their Finding | Our Application |
|---------------|-----------------|
| Dynamic content in system prompt kills cache | Audit all workflow system prompts; relocate dynamic content to end |
| 1-hour TTL keeps cache warm across users | Use 1h TTL for Anthropic; our workflows run continuously |
| Intermediate breakpoints every 18 blocks | Implement for long-running multi-step workflows |
| Session-based sticky routing | Use OpenRouter `session_id` per workflow |
| Monitor cache_creation vs cache_read tokens | Add to Prometheus metrics |

Sources: [ProjectDiscovery Blog](https://projectdiscovery.io/blog/how-we-cut-llm-cost-with-prompt-caching), [DigitalApplied Guide](https://www.digitalapplied.com/blog/prompt-caching-2026-cut-llm-costs-engineering-guide)

---

## 11. Recommendations and Prioritized Roadmap

### Phase 1: Quick Wins (Week 1-2)

**Effort: LOW | Impact: HIGH | Risk: NONE**

1. **Audit and restructure all workflow system prompts**
   - Move ALL dynamic content (timestamps, session state, working memory) to the end of prompts
   - Order: tools -> system prompt (static) -> reference docs -> conversation history -> dynamic state -> user query
   - Expected: 50-80% of input tokens become cacheable

2. **Add Anthropic `cache_control` to all direct API calls**
   - Add `cache_control: {type: "ephemeral", ttl: "1h"}` to system prompts
   - Add breakpoint on last tool definition
   - Budget 4 breakpoints: system (1) + tools (1) + messages (2)

3. **Add OpenRouter `X-Session-Id` and `X-OpenRouter-Cache` headers**
   - Set `session_id` per workflow execution for sticky routing
   - Enable response caching for free on identical retries

4. **Add cache monitoring to API responses**
   - Log `cache_creation_input_tokens`, `cache_read_input_tokens` from Anthropic
   - Log `prompt_cache_hit_tokens`, `prompt_cache_miss_tokens` from DeepSeek
   - Log `X-OpenRouter-Cache-Status` from OpenRouter
   - Store in `monitoring.cache_metrics` table

### Phase 2: Application Response Cache (Week 3-4)

**Effort: MEDIUM | Impact: HIGH | Risk: LOW**

5. **Deploy Redis exact-match response cache**
   - Cache key: SHA-256(model + system_prompt_version + query + temperature)
   - Only cache when temperature=0
   - Default TTL: 1 hour; configurable per query type
   - Use existing Redis on aio-01:6379

6. **Implement versioned cache keys**
   - Include system_prompt_version and tool_def_version in cache keys
   - Auto-invalidate on deployment/version changes

7. **Build cache metrics dashboard**
   - Hit rate by cache type (provider prefix, response, semantic)
   - Latency comparison (cached vs uncached)
   - Cost savings tracking
   - Alert on hit rate < 30%

### Phase 3: Semantic Cache (Week 5-8)

**Effort: MEDIUM-HIGH | Impact: MEDIUM | Risk: MEDIUM**

8. **Deploy pgvector-based semantic response cache**
   - Use existing 384-dim embeddings
   - Start with threshold 0.95 (conservative)
   - Only compare last user message semantically; exact-match everything else
   - Never cache personalized or time-sensitive responses

9. **Implement semantic cache safety guardrails**
   - Scope by model + system_prompt_version + tenant
   - Log all hits with similarity scores
   - Correlate with downstream quality metrics
   - Consider cheap-model gatekeeper for borderline matches

10. **Tune and validate**
    - Build labeled evaluation set from real queries
    - Measure false positive rate at different thresholds
    - Gradually lower threshold from 0.95 toward 0.92 if precision holds

### Phase 4: Advanced Optimizations (Month 2+)

**Effort: HIGH | Impact: MEDIUM | Risk: LOW-MEDIUM**

11. **Cache warming pipeline**
    - Replay top-100 queries from last 24h after any cache flush
    - Pre-warm during deployment windows
    - Scheduled off-peak warming for predictable traffic patterns

12. **Multi-turn conversation optimization**
    - Ensure all workflow runners maintain stable message arrays
    - Implement intermediate breakpoints for workflows > 18 steps

13. **Gemini explicit caching (selective)**
    - Only for high-reuse Pro-tier paths where usage justifies storage cost
    - Monitor storage costs vs savings carefully

### Summary Table

| Technique | Complexity | Benefit | Risk | Priority |
|-----------|-----------|---------|------|----------|
| Prompt restructuring | LOW | 50-80% prefix cacheable | NONE | P0 |
| Anthropic cache_control | LOW | 60-90% input cost reduction | NONE | P0 |
| OpenRouter headers | LOW | Free retries + sticky routing | NONE | P0 |
| Cache monitoring | LOW | Visibility into savings | NONE | P0 |
| Redis response cache | MEDIUM | 40-60% hit rate, 100% savings/hit | LOW | P1 |
| Versioned invalidation | LOW | Prevents stale responses | NONE | P1 |
| pgvector semantic cache | MEDIUM-HIGH | 20-45% additional hits | MEDIUM | P2 |
| Cache warming | MEDIUM | Faster cold starts | LOW | P3 |
| Gemini explicit cache | MEDIUM | 90% on high-reuse paths | MEDIUM (storage cost) | P3 |

### Estimated Total Impact

With Phase 1-2 implemented:
- **Input token costs:** 50-70% reduction
- **Latency:** 40-60% reduction in average TTFT
- **Infrastructure cost:** Near-zero (uses existing Redis and PostgreSQL)

With all phases:
- **Input token costs:** 60-80% reduction
- **Latency:** 50-85% reduction
- **Cache hit rate:** 60-80% combined (exact + semantic + provider)

---

## Appendix A: Provider Caching Feature Matrix

| Feature | Anthropic | OpenAI | Google | DeepSeek | Groq | OpenRouter |
|---------|-----------|--------|--------|----------|------|------------|
| Caching type | Explicit + Auto | Automatic | Implicit + Explicit | Automatic | Automatic | Pass-through + Response |
| Cache read discount | 90% | 50-90% | 75-90% | 90% | 50% | Varies by provider + 100% (response) |
| Cache write cost | 1.25x (5m) / 2x (1h) | Free (pre-5.6) | $0.50/M write + storage/hour | Free | Free | Free |
| Min cacheable tokens | 1,024 | 1,024 | 1,024-4,096 | Not specified | Not specified | N/A |
| TTL | 5m or 1h | 5-10m (auto) / 24h (extended) | Custom (default 1h) | Hours to days | Not specified | 300s default (response) |
| Developer control | High (breakpoints) | None (automatic) | Medium (explicit) / None (implicit) | None | None | Headers |
| Monitoring fields | cache_creation/read_input_tokens | cached_tokens | cached_content_token_count | prompt_cache_hit/miss_tokens | N/A | X-OpenRouter-Cache-Status |

## Appendix B: Cache Key Design Patterns

**Exact-match cache key:**
```
SHA256(model || system_prompt_version || tool_def_version || temperature || max_tokens || messages_json)
```

**Semantic cache composite key:**
- Exact-match components (hashed): model, system_prompt_version, temperature, tool_def_version, tenant_id
- Semantic component (vector similarity): last user message embedding only

**Provider prefix cache key (implicit):**
- Byte-identical prefix of: tools + system_prompt + conversation_history
- Any token-level difference = full cache miss

## Appendix C: Monitoring SQL

```sql
-- Create monitoring table
CREATE TABLE IF NOT EXISTS monitoring.cache_metrics (
    id SERIAL PRIMARY KEY,
    cache_type TEXT NOT NULL,  -- 'provider_prefix', 'response_exact', 'response_semantic', 'openrouter_response'
    is_hit BOOLEAN NOT NULL,
    model TEXT,
    latency_ms FLOAT,
    similarity_score FLOAT,   -- for semantic cache
    tokens_cached INTEGER,    -- for provider prefix
    tokens_total INTEGER,
    cost_saved_usd FLOAT,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON monitoring.cache_metrics (cache_type, recorded_at);
CREATE INDEX ON monitoring.cache_metrics (model, recorded_at);

-- Dashboard query: Cache performance summary
SELECT 
    cache_type,
    DATE_TRUNC('hour', recorded_at) AS hour,
    COUNT(*) AS total_requests,
    COUNT(*) FILTER (WHERE is_hit) AS cache_hits,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_hit) / COUNT(*), 1) AS hit_rate_pct,
    ROUND(AVG(latency_ms) FILTER (WHERE is_hit)::numeric, 1) AS avg_hit_latency_ms,
    ROUND(AVG(latency_ms) FILTER (WHERE NOT is_hit)::numeric, 1) AS avg_miss_latency_ms,
    ROUND(SUM(COALESCE(cost_saved_usd, 0))::numeric, 4) AS total_saved_usd
FROM monitoring.cache_metrics
WHERE recorded_at > NOW() - INTERVAL '24 hours'
GROUP BY cache_type, DATE_TRUNC('hour', recorded_at)
ORDER BY hour DESC, cache_type;
```
