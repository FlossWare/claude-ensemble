# Rate Limit Manager Integration Guide

## Overview

The Rate Limit Manager provides sliding window rate limiting for API providers to prevent 429 errors and quota exhaustion.

## Features

- **Sliding Window Counters**: 60-second rolling window for accurate rate limiting
- **Auto-Throttling**: Blocks requests when approaching limits (configurable buffer)
- **Multi-Provider Support**: Groq (30/min), Perplexity (5/hour), OpenRouter (various), local (unlimited)
- **PostgreSQL Backend**: Persistent tracking with cleanup
- **Graceful Degradation**: Fails open on database errors

## Integration with weighted-voting.cjs

Add rate limit checks before model execution:

```javascript
// In weighted-voting.cjs, add at top:
const { checkRateLimit, recordRequest } = require('./rate-limit-manager.cjs');

// In weightedVoting() function, before circuit breaker filter:
async function weightedVoting(votes, taskType, options = {}) {
  // PRIORITY -1: Rate limit check (before circuit breaker)
  let rateLimitAnalysis = null;
  const votesBeforeRateLimit = votes.length;

  if (!options.skipRateLimitCheck) {
    try {
      // Get unique providers from votes
      const providerSet = new Set(votes.map(v => getProviderFromModel(v.model)));
      const providers = Array.from(providerSet);

      // Check rate limits for each provider
      for (const provider of providers) {
        const check = await checkRateLimit(provider, { throwOnLimit: false });
        
        if (check.throttled) {
          console.warn(`[weighted-voting] Provider ${provider} throttled (${check.current_count}/${check.limit} requests)`);
        }
      }

      // Filter votes from rate-limited providers
      const availableProviders = [];
      for (const provider of providers) {
        const check = await checkRateLimit(provider, { throwOnLimit: false });
        if (!check.throttled) {
          availableProviders.push(provider);
        }
      }

      const unavailableProviders = providers.filter(p => !availableProviders.includes(p));

      if (unavailableProviders.length > 0) {
        votes = votes.filter(v => {
          const provider = getProviderFromModel(v.model);
          return availableProviders.includes(provider);
        });

        rateLimitAnalysis = {
          detected: true,
          throttled_providers: unavailableProviders,
          votes_filtered: votesBeforeRateLimit - votes.length,
          votes_remaining: votes.length,
          warning: `Rate limiting filtered ${unavailableProviders.length} providers: ${unavailableProviders.join(', ')}`,
        };

        console.warn(`[weighted-voting] ${rateLimitAnalysis.warning}`);
        console.warn(`[weighted-voting] Votes filtered: ${votesBeforeRateLimit} → ${votes.length}`);
      }

    } catch (err) {
      console.warn(`[weighted-voting] Rate limit check failed: ${err.message}`);
      // Continue without rate limiting (graceful degradation)
    }
  }

  // ... rest of weightedVoting() function ...

  // Add rate limit analysis to result
  if (rateLimitAnalysis) {
    result.rate_limit_analysis = rateLimitAnalysis;
  }

  return result;
}

// Helper function to extract provider from model name
function getProviderFromModel(model) {
  // Examples:
  //   'groq/llama-3-70b' → 'groq'
  //   'openrouter/anthropic/claude-3-haiku' → 'openrouter/anthropic/claude-3-haiku'
  //   'ollama/deepseek-coder' → 'ollama'
  //   'opus' → 'anthropic' (default)

  if (model.includes('/')) {
    // Extract provider prefix
    const parts = model.split('/');
    if (parts[0] === 'openrouter' && parts.length >= 3) {
      // Keep full model path for OpenRouter (different models have different limits)
      return model;
    }
    return parts[0];
  }

  // Map internal model names to providers
  const providerMap = {
    'opus': 'anthropic',
    'sonnet': 'anthropic',
    'haiku': 'anthropic',
    'fable': 'anthropic',
    'gpt-4o': 'openai',
    'gpt-4': 'openai',
    'gpt-3.5-turbo': 'openai',
    'gemini': 'google',
    'gemini-pro': 'google',
    'gemini-flash': 'google',
  };

  return providerMap[model] || 'unknown';
}
```

## Integration with Model Execution

After making API calls, record the request:

```javascript
// After successful API call:
await recordRequest(provider, true, { model: modelName, tokens: outputTokens });

// After failed API call:
await recordRequest(provider, false, { error: err.message });
```

## Configuration

Edit `RATE_LIMITS` in `rate-limit-manager.cjs`:

```javascript
const RATE_LIMITS = {
  'groq': { rpm: 30, rph: 1800, buffer: 2 },
  'perplexity': { rpm: 0.083, rph: 5, buffer: 1 },
  'openrouter/anthropic/claude-3-haiku': { rpm: 10, rph: 100, buffer: 1 },
  'default': { rpm: 60, rph: 3600, buffer: 5 },
};
```

## Testing

Run comprehensive test suite:

```bash
node shared/rate-limit-manager.test.cjs
```

Expected: 22/23 tests pass (1 schema permission warning is non-fatal)

## Monitoring

Check rate limit statistics:

```javascript
const { getRateLimitStats } = require('./rate-limit-manager.cjs');

const stats = await getRateLimitStats();
console.log(stats);
// [
//   {
//     provider: 'groq',
//     total_requests: 1524,
//     throttled_count: 12,
//     current_window_count: 28,
//     limit: 30,
//     utilization_percent: '93.3',
//     last_request: '2026-06-28T20:54:32.123Z'
//   },
//   ...
// ]
```

## Database Schema

Tables created in `monitoring` schema:

- `monitoring.rate_limits` - Summary statistics per provider
- `monitoring.rate_limit_requests` - Request history (60-second sliding window)

Migration file: `db/migrations/004-rate-limit-manager.sql`

## Next Steps

1. **Deploy to production**: Copy `rate-limit-manager.cjs` to all workers
2. **Integrate with weighted-voting.cjs**: Add rate limit checks before voting
3. **Update model execution**: Record requests after API calls
4. **Monitor statistics**: Check `getRateLimitStats()` to verify throttling works
5. **Tune limits**: Adjust `RATE_LIMITS` based on actual API quotas

## Troubleshooting

**Issue**: Database permission errors

**Solution**: Run migration manually:
```bash
psql -h aio-01 -p 5433 -U sfloess -d learning < db/migrations/004-rate-limit-manager.sql
```

**Issue**: Throttling too aggressive

**Solution**: Increase `buffer` value in `RATE_LIMITS` config (default: 2)

**Issue**: Rate limit not enforced

**Solution**: Verify `checkRateLimit()` is called BEFORE API requests, not after
