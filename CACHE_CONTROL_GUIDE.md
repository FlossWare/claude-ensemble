# Claude API Prompt Caching with cache_control

**Reference:** https://docs.anthropic.com/en/docs/build-a-system-with-claude/prompt-caching

## Overview

Cache control allows you to cache large static prompts (memory, documentation, system instructions) and only pay for dynamic content (user queries). This reduces costs by ~90% for repeated queries using the same cached context.

### Key Benefits
- **90% cost reduction** for cache hits (cached tokens cost 10% of normal)
- **Latency reduction** (cached content processed faster)
- **Perfect for scenarios** with large static prompts + many queries

### How It Works
1. **Structure prompts** with cacheable content FIRST, user query LAST
2. **Add cache_control** ephemeral blocks to cacheable messages
3. **First request** creates cache (costs extra, ~25% premium)
4. **Subsequent requests** reuse cache (90% cheaper per cached token)

## Architecture: Prompt Restructuring

The key to effective caching is **structure**: cacheable content must come BEFORE dynamic queries.

### Correct Structure (Maximum Cache Hits)
```
Message 1: [Cached MEMORY]        ← Add cache_control {"type": "ephemeral"}
Message 2: [Cached DOCS]          ← Add cache_control
Message 3: [Cached SYSTEM]        ← Add cache_control
Message 4: [User Query]           ← NO cache_control (dynamic)
```

### Why Order Matters
- Claude API caches **contiguous blocks** from the start of the message list
- Cacheable content must be at the **beginning**
- Dynamic content (user query) comes at the **end**
- Cache is created on first request, reused on subsequent requests

## Implementation Guide

### 1. Using PromptCacheControl Class

```python
from cache_control import PromptCacheControl

# Initialize cache controller
cache = PromptCacheControl()

# Structure your prompt
messages = cache.restructure_prompt(
    memory="<cached user memory>",
    documentation="<cached RH docs>",
    system_prompt="<cached system instructions>",
    user_query="<user's actual question>"
)

# Call API with cache
response, metrics = cache.call_with_cache(
    messages=messages,
    cache_eligible_indices=[0, 1, 2],  # First 3 messages are cacheable
    model="claude-3-5-sonnet-20241022",
    max_tokens=2000
)

# Check metrics
print(f"Cache hit: {metrics.is_cache_hit}")
print(f"Savings: ${metrics.savings:.6f}")
```

### 2. Manual Message Restructuring

```python
messages = [
    {"role": "user", "content": "[CACHED MEMORY]\n...large memory..."},
    {"role": "user", "content": "[CACHED DOCS]\n...documentation..."},
    {"role": "user", "content": "[CACHED SYSTEM]\n...system prompt..."},
    {"role": "user", "content": "User's specific question here"}
]

cache = PromptCacheControl()
cached_messages = cache.add_cache_control(messages, cache_eligible_indices=[0, 1, 2])
```

### 3. Decorator Pattern (Automatic Caching)

```python
from cache_control import restructure_prompt_decorator

@restructure_prompt_decorator(cache_eligible_blocks=[0, 1, 2])
def my_api_call(messages, model="claude-3-5-sonnet-20241022"):
    # messages will automatically have cache_control added
    client.messages.create(model=model, messages=messages)
```

## Cost Model & Pricing

Cache hits cost **90% less** than regular processing. Here's the pricing breakdown:

### Sonnet 3.5 Pricing
```
Regular input:        $3.00 per 1M tokens
Cache creation:       $3.75 per 1M tokens (25% premium)
Cache read:           $0.30 per 1M tokens (90% discount!)
Output:               $15.00 per 1M tokens
```

### Example: 3 Identical Requests
Assume: 5,000 cacheable tokens + 500 tokens per query

**Without Cache:**
- Request 1: 5,500 tokens × $0.003 = $0.0165
- Request 2: 5,500 tokens × $0.003 = $0.0165
- Request 3: 5,500 tokens × $0.003 = $0.0165
- **Total: $0.0495**

**With Cache:**
- Request 1: 5,000 cached × $0.00375 + 500 input × $0.003 = $0.01875 + $0.0015 = $0.02025
- Request 2: 5,000 cached (read) × $0.0003 + 500 input × $0.003 = $0.0015 + $0.0015 = $0.003
- Request 3: 5,000 cached (read) × $0.0003 + 500 input × $0.003 = $0.0015 + $0.0015 = $0.003
- **Total: $0.02625 (-47% vs without cache)**

### Token Budget for Different Models

| Model | Cache Hit Cost | Break-Even Point |
|-------|----------------|------------------|
| Haiku | $0.00008/1M | ~3 requests |
| Sonnet | $0.0003/1M | ~5 requests |
| Opus | $0.0015/1M | ~8 requests |

For most use cases (memory + docs as cache), you break even after 3-5 requests.

## Practical Examples

### Example 1: Red Hat Memory + Docs

```python
from cache_control import PromptCacheControl

# Reusable content
RED_HAT_MEMORY = """
Project: claude-global-skills
Status: Active
Team: csanders, loleary, grgardne (EST), ypant, rghandi (IST)
Known issues: AWX NetworkPolicy blocks, Sumo Logic API auth...
"""

RED_HAT_DOCS = """
Disseminator deployment modes: starting_at_qa vs only_qa
UXE integration: CPSEARCH-9479, XE Compass diagrams
Git workflow: Always worktrees, ask before push...
"""

cache = PromptCacheControl()

# User asks multiple questions with same context
questions = [
    "What's the status of CPSEARCH-9479?",
    "How do I deploy to production?",
    "Explain the keyset pagination issue",
]

for question in questions:
    messages = cache.restructure_prompt(
        memory=RED_HAT_MEMORY,
        documentation=RED_HAT_DOCS,
        system_prompt="You are a Red Hat development assistant.",
        user_query=question
    )
    
    response, metrics = cache.call_with_cache(
        messages=messages,
        cache_eligible_indices=[0, 1, 2],
        model="claude-3-5-sonnet-20241022"
    )
    
    cache.print_metrics(metrics)
```

### Example 2: Large Document Context

```python
# Cache a large document (e.g., RFC, specification)
with open('large_spec.txt', 'r') as f:
    spec = f.read()  # Could be 50KB+

messages = [
    {"role": "user", "content": f"[CACHED SPEC]\n{spec}"},
    {"role": "user", "content": "What are the security requirements?"},
]

# Add cache control to spec message
cached_messages = cache.add_cache_control(messages, [0])

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=2000,
    messages=cached_messages
)
```

### Example 3: Interactive Q&A Session

```python
# Start with cached context
cache = PromptCacheControl()

messages = cache.restructure_prompt(
    memory="User's background and preferences...",
    documentation="Domain-specific docs...",
    system_prompt="You are a domain expert...",
    user_query=""  # Start empty
)

# Interactive loop - cache reused for each follow-up
while True:
    user_input = input("Question (or 'quit'): ")
    if user_input.lower() == 'quit':
        break
    
    # Update query with new user input
    messages[-1]["content"] = user_input
    
    response, metrics = cache.call_with_cache(
        messages=messages,
        cache_eligible_indices=[0, 1, 2],
        model="claude-3-5-sonnet-20241022"
    )
    
    print(f"Response: {response}")
    if metrics.is_cache_hit:
        print(f"✓ Cache hit! Saved ${metrics.savings:.6f}")
```

## Testing Cache Control

Run the comprehensive test suite:

```bash
# Set your API key
export ANTHROPIC_API_KEY='your-key-here'

# Run tests
python3 test_cache_control.py
```

### What the Tests Measure

1. **Test 1**: Single request creates cache (cache creation tokens)
2. **Test 2**: Five identical requests show cache hit rate
3. **Test 3**: Different queries reuse same cache
4. **Test 4**: Cost savings analysis (concrete numbers)
5. **Test 5**: Quality check (cached outputs are correct)

### Expected Output

```
TEST 2: Five Identical Requests
================================================================================
Req   Cache Hit    Tokens       Cost         Savings
────────────────────────────────────────────────────
1     ✗ MISS       8,200        $0.02450     $0.00000
2     ✓ HIT        3,200        $0.00300     $0.02150
3     ✓ HIT        3,200        $0.00300     $0.02150
4     ✓ HIT        3,200        $0.00300     $0.02150
5     ✓ HIT        3,200        $0.00300     $0.02150
────────────────────────────────────────────────────
Average savings per request: $0.01710
Total savings across 5 requests: $0.08600
```

## Metrics & Monitoring

The `CacheMetrics` dataclass tracks everything:

```python
response, metrics = cache.call_with_cache(...)

# Token usage
print(f"Input tokens: {metrics.input_tokens}")
print(f"Cache creation tokens: {metrics.cache_creation_input_tokens}")
print(f"Cache read tokens: {metrics.cache_read_input_tokens}")
print(f"Output tokens: {metrics.output_tokens}")

# Cost tracking
print(f"Cost without cache: ${metrics.cost_without_cache:.6f}")
print(f"Cost with cache: ${metrics.cost_with_cache:.6f}")
print(f"Savings: ${metrics.savings:.6f}")

# Cache status
print(f"Cache hit: {metrics.is_cache_hit}")
```

## Common Patterns & Best Practices

### DO:
- ✅ Place cacheable content (memory, docs) FIRST
- ✅ Place user query LAST
- ✅ Use for repeated queries with same context
- ✅ Cache large documents (50KB+)
- ✅ Monitor cache hit rate
- ✅ Use Haiku for cache testing (cheapest)

### DON'T:
- ❌ Change cached content between requests (invalidates cache)
- ❌ Mix cacheable and dynamic content
- ❌ Cache tiny prompts (<1KB) - no savings
- ❌ Rely on cache across different users
- ❌ Cache sensitive information without encryption

## Limitations & Considerations

1. **Cache Size**: API limits cache to ~4 billion tokens (not a practical concern)
2. **Cache TTL**: Cache expires after 5 minutes of inactivity
3. **Different Models**: Can't use same cache across different models
4. **Cost Premium**: First request costs 25% more (amortized quickly)
5. **Break-Even**: Most scenarios break even after 3-8 requests

## Integrating with Existing Code

### Integration Pattern for api-proxy.py

```python
from cache_control import PromptCacheControl

@app.post("/api/cached-completion")
async def cached_completion(request: Request):
    """Use cache_control for repeated queries"""
    
    data = await request.json()
    
    cache = PromptCacheControl()
    messages = cache.restructure_prompt(
        memory=data.get('memory', ''),
        documentation=data.get('docs', ''),
        system_prompt=data.get('system', ''),
        user_query=data.get('query', '')
    )
    
    response, metrics = cache.call_with_cache(
        messages=messages,
        cache_eligible_indices=[0, 1, 2],
        model=data.get('model', 'claude-3-5-sonnet-20241022')
    )
    
    return {
        'response': response,
        'cache_hit': metrics.is_cache_hit,
        'savings': metrics.savings,
        'metrics': asdict(metrics)
    }
```

### Caching Memory + Docs Pattern

This is the most useful pattern for production:

```python
# Preload memory + docs (happens once)
MEMORY = load_memory_from_file('memory.md')
DOCS = load_docs_from_file('docs.md')

# User makes multiple requests
for user_query in user_queries:
    messages = restructure_prompt(
        memory=MEMORY,           # Cached (same for all requests)
        documentation=DOCS,      # Cached (same for all requests)
        system_prompt="...",     # Cached
        user_query=user_query    # Dynamic (changes each request)
    )
    
    response = call_with_cache(messages, cache_eligible=[0, 1, 2])
    # After first request, subsequent requests hit cache
```

## Troubleshooting

### Cache Hit Not Appearing

```python
# Check if cache_read_input_tokens > 0
if metrics.cache_read_input_tokens > 0:
    print("✓ Cache hit detected")
else:
    print("✗ Cache miss - check message structure")
```

### Cache TTL Expired

- Cache expires after 5 minutes of inactivity
- Solution: Make requests within 5 minutes to maintain cache
- Or: Implement periodic refresh calls

### No Cost Savings

- Cacheable content might be too small
- Minimum worthwhile cache: ~2,000 tokens
- First request always costs extra (25% premium)
- Need 3+ requests to break even on small caches

## References

- **Official Docs**: https://docs.anthropic.com/en/docs/build-a-system-with-claude/prompt-caching
- **Pricing**: https://www.anthropic.com/pricing
- **Best Practices**: See test suite examples in `test_cache_control.py`

## Summary

Cache control is a powerful tool for reducing costs when you have:
- **Large static context** (memory, documentation)
- **Repeated queries** with the same context
- **Multiple users** asking similar questions

Typical savings: **45-90% cost reduction** after initial cache creation.
