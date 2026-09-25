# Claude API Prompt Caching Implementation

Complete implementation of cache_control integration for the Anthropic Claude API, enabling 90% cost reduction for repeated queries with cached static content.

## Files

- **`cache_control.py`** - Core implementation with `PromptCacheControl` class
- **`test_cache_control.py`** - Comprehensive test suite (5 tests, measures cache hit rates)
- **`example_cache_control_usage.py`** - Practical examples (Red Hat docs, large documents, interactive sessions)
- **`CACHE_CONTROL_GUIDE.md`** - Complete documentation and best practices

## Quick Start

### 1. Installation

```bash
# Ensure anthropic package is installed
pip install anthropic

# Set your API key
export ANTHROPIC_API_KEY='your-key-here'
```

### 2. Basic Usage

```python
from cache_control import PromptCacheControl

cache = PromptCacheControl()

# Restructure prompt: cacheable content first, query last
messages = cache.restructure_prompt(
    memory="<cached user memory>",
    documentation="<cached docs>",
    system_prompt="<cached instructions>",
    user_query="<user question>"
)

# Call API with cache
response, metrics = cache.call_with_cache(
    messages=messages,
    cache_eligible_indices=[0, 1, 2],  # First 3 messages are cacheable
    model="claude-3-5-sonnet-20241022",
    max_tokens=2000
)

# Check results
print(f"Cache hit: {metrics.is_cache_hit}")
print(f"Savings: ${metrics.savings:.6f}")
```

### 3. Run Tests

```bash
python3 test_cache_control.py
```

Expected output:
```
TEST 2: Five Identical Requests
================================================================================
Req   Cache Hit    Tokens       Cost         Savings
────────────────────────────────────────────────────
1     ✗ MISS       8,200        $0.02450     $0.00000
2     ✓ HIT        3,200        $0.00300     $0.02150
3     ✓ HIT        3,200        $0.00300     $0.02150
...
```

## Architecture

### Prompt Structure (Critical for Caching)

```
Message 0: [Cached MEMORY]          ← Add cache_control
Message 1: [Cached DOCUMENTATION]   ← Add cache_control
Message 2: [Cached SYSTEM PROMPT]   ← Add cache_control
Message 3: [User Query]             ← NO cache_control (dynamic)
```

**Why order matters:**
- Cache is created/reused for contiguous blocks
- Cacheable content must come FIRST
- Dynamic content (user query) comes LAST
- Claude API processes cached blocks more efficiently

### Token Flow

```
First Request (Cache Creation):
Input: [cacheable context] + [user query]
Tokens: 
  - Cacheable: cost 1.25x (cache creation premium)
  - Query: cost 1.0x (normal)

Subsequent Requests (Cache Hit):
Input: [cached context] + [user query]
Tokens:
  - Cached: cost 0.1x (90% discount!)
  - Query: cost 1.0x (normal)
```

## Cost Comparison

### Real Example: 5 Identical Requests

```
Scenario: 5,000 cached tokens + 500 query tokens

Without Cache:
  Request 1: 5,500 × $0.003 = $0.0165
  Request 2: 5,500 × $0.003 = $0.0165
  Request 3: 5,500 × $0.003 = $0.0165
  Request 4: 5,500 × $0.003 = $0.0165
  Request 5: 5,500 × $0.003 = $0.0165
  ────────────────────────────
  Total: $0.0825

With Cache:
  Request 1: 5,000 × $0.00375 + 500 × $0.003 = $0.0195
  Request 2: 5,000 × $0.0003 + 500 × $0.003 = $0.0030
  Request 3: 5,000 × $0.0003 + 500 × $0.003 = $0.0030
  Request 4: 5,000 × $0.0003 + 500 × $0.003 = $0.0030
  Request 5: 5,000 × $0.0003 + 500 × $0.003 = $0.0030
  ────────────────────────────
  Total: $0.0315

Savings: $0.051 (61% reduction)
```

## Core Features

### PromptCacheControl Class

```python
class PromptCacheControl:
    """
    Main interface for cache_control functionality
    
    Methods:
    - restructure_prompt()    - Arrange cacheable content first
    - add_cache_control()     - Add ephemeral cache blocks
    - call_with_cache()       - Call API with cache
    - calculate_cost()        - Pricing calculations
    - print_metrics()         - Pretty-print results
    - print_comparison()      - Compare multiple requests
    """
```

### CacheMetrics Dataclass

Tracks all information about a single request:

```python
@dataclass
class CacheMetrics:
    request_id: str                      # API response ID
    timestamp: datetime                  # When request was made
    is_cache_hit: bool                   # Cache was used?
    input_tokens: int                    # Regular input tokens
    cache_creation_input_tokens: int     # Tokens creating cache
    cache_read_input_tokens: int         # Tokens read from cache
    output_tokens: int                   # Tokens generated
    total_tokens: int                    # Total token count
    cost_without_cache: float            # Hypothetical cost
    cost_with_cache: float               # Actual cost
    savings: float                       # Dollar savings
    response: str                        # API response
```

## Test Suite Overview

### Test 1: Single Request (Cache Creation)
- Creates cache on first request
- Verifies cache_creation_input_tokens > 0
- Expected: No cache hit, but cache created

### Test 2: Five Identical Requests
- Makes 5 identical requests
- Measures cache hit rate
- Expected: Request 1 misses, Requests 2-5 hit

### Test 3: Different Queries (Same Cache)
- Different queries reuse same cached memory/docs
- Verifies cache efficiency across variations
- Expected: Cache hits on requests 2+

### Test 4: Cost Savings Analysis
- Concrete cost comparison
- Shows token costs breakdown
- Expected: ~50-90% savings on requests 2+

### Test 5: Quality Check
- Verifies cache_control doesn't affect output quality
- Sanity check on response reasonableness
- Expected: All responses relevant and correct

## Practical Examples

### Example 1: Red Hat Project Documentation

Cache team memory + RH documentation, answer multiple questions:

```python
memory = """Project status, team info, known issues..."""
docs = """Git workflow, deployment modes, API patterns..."""

cache = PromptCacheControl()

for question in questions:
    messages = cache.restructure_prompt(
        memory=memory,
        documentation=docs,
        system_prompt="Red Hat assistant",
        user_query=question
    )
    response, metrics = cache.call_with_cache(
        messages=messages,
        cache_eligible_indices=[0, 1, 2]
    )
```

### Example 2: Large Document Context

Cache technical spec/RFC, answer multiple questions:

```python
doc = load_large_spec()  # 50KB+ file

messages = [
    {"role": "user", "content": f"[CACHED SPEC]\n{doc}"},
    {"role": "user", "content": f"Question: {question}"}
]

cached_msgs = cache.add_cache_control(messages, [0])
response = call_with_cache(cached_msgs, cache_eligible=[0])
```

### Example 3: Interactive Q&A Session

Cache context, reuse for follow-ups:

```python
messages = cache.restructure_prompt(
    memory=user_context,
    documentation="",
    system_prompt="Assistant",
    user_query=""  # Empty initially
)

while True:
    user_input = input("Question: ")
    messages[-1]["content"] = user_input  # Update query only
    
    response, metrics = cache.call_with_cache(
        messages=messages,
        cache_eligible_indices=[0, 2]
    )
```

## When to Use Cache Control

### Great Use Cases:
- ✅ Large static documentation + many queries
- ✅ User memory/preferences cached across sessions
- ✅ System prompts reused for many requests
- ✅ FAQ scenarios (same knowledge base)
- ✅ Chat with persistent context

### Not Worth Using:
- ❌ Single one-off queries (no reuse)
- ❌ Tiny prompts (<1KB total)
- ❌ Content changes every request
- ❌ Cost savings < $0.001

## Integration Patterns

### Pattern 1: API Endpoint with Cache

```python
@app.post("/api/chat")
async def chat_with_cache(request: Request):
    data = await request.json()
    cache = PromptCacheControl()
    
    messages = cache.restructure_prompt(
        memory=data['memory'],
        documentation=data['docs'],
        system_prompt=data['system'],
        user_query=data['query']
    )
    
    response, metrics = cache.call_with_cache(messages)
    return {'response': response, 'metrics': asdict(metrics)}
```

### Pattern 2: Session-Based Cache

```python
class UserSession:
    def __init__(self, user_id, memory, docs):
        self.cache = PromptCacheControl()
        self.memory = memory
        self.docs = docs
    
    def ask(self, question):
        messages = self.cache.restructure_prompt(
            memory=self.memory,
            documentation=self.docs,
            system_prompt="...",
            user_query=question
        )
        return self.cache.call_with_cache(messages)
```

### Pattern 3: Batch Processing

```python
cache = PromptCacheControl()

for user_query in batch:
    messages = cache.restructure_prompt(
        memory=SHARED_MEMORY,  # Cached once
        documentation=SHARED_DOCS,
        system_prompt=SYSTEM,
        user_query=user_query
    )
    response = cache.call_with_cache(messages)
    # Each query after first hits cache
```

## Monitoring & Metrics

### Track Cache Performance

```python
metrics_list = []

for query in queries:
    response, metrics = cache.call_with_cache(messages)
    metrics_list.append(metrics)

# Summary
cache.print_comparison(metrics_list)

# Statistics
hits = sum(1 for m in metrics_list if m.is_cache_hit)
total_saved = sum(m.savings for m in metrics_list)

print(f"Cache hit rate: {hits}/{len(metrics_list)}")
print(f"Total savings: ${total_saved:.6f}")
```

## Limitations

1. **Cache TTL**: Expires after 5 minutes of inactivity
   - Solution: Keep requests within 5-minute windows

2. **Cache Size**: Limited to ~4 billion tokens
   - Practical limit rarely hit

3. **Model Specific**: Different models have different caches
   - Can't share cache between claude-sonnet and claude-haiku

4. **Cost Premium**: First request costs 25% more
   - Need 3+ requests to break even

5. **Contiguous Blocks**: Cache must be at message start
   - Dynamic content must come after cached content

## Troubleshooting

### Cache Hit Not Detected

```python
# Debug: Check raw metrics
print(f"Input tokens: {metrics.input_tokens}")
print(f"Cache read tokens: {metrics.cache_read_input_tokens}")
print(f"Cache creation tokens: {metrics.cache_creation_input_tokens}")

if metrics.cache_read_input_tokens == 0:
    print("No cache hit - check message structure")
```

### Cache Expired

```python
# Make requests within 5 minutes to maintain cache
if time.time() - last_request > 300:
    print("Cache TTL expired, will create new cache")
```

### No Cost Savings

```python
# Check if savings is worth it
if metrics.savings < 0.001:
    print("Cache savings < $0.001 - not worth caching for this use case")
```

## Performance Characteristics

| Metric | Without Cache | With Cache (Hit) | Improvement |
|--------|--------------|-----------------|------------|
| Cost per 1M tokens | $3.00 | $0.30 | 90% ↓ |
| Latency (est.) | 2-3s | 1-2s | 33% ↓ |
| Cache creation | N/A | +25% | First req |

## Documentation

- **Full Guide**: See `CACHE_CONTROL_GUIDE.md`
- **Examples**: See `example_cache_control_usage.py`
- **Tests**: See `test_cache_control.py`
- **API Docs**: https://docs.anthropic.com/en/docs/build-a-system-with-claude/prompt-caching

## Summary

This implementation provides:
- ✅ Production-ready cache_control integration
- ✅ Automatic prompt restructuring
- ✅ Comprehensive cost tracking
- ✅ Test suite with metrics
- ✅ Practical examples
- ✅ Complete documentation

Typical ROI: **45-90% cost reduction** after initial setup.
