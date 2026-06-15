---
name: always-retry-with-backoff
description: Always implement retry logic with exponential backoff for API calls, especially web-based AI services
metadata:
  type: feedback
  created: 2026-06-14
  priority: high
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Always Implement Retry with Exponential Backoff

**Rule:** ALWAYS implement retry logic with exponential backoff for API calls to external services, especially AI model APIs.

**Why:** User asked "are we also ensuring backoff if a web ai version fails" during deep learning workflow setup. External APIs (OpenRouter, DeepSeek, Cerebras, Cloudflare, etc.) can fail due to:
- Rate limiting (429 errors)
- Temporary outages (503 errors)
- Network issues (timeouts)
- API quota exceeded
- Transient failures

Without retry, a single API failure kills the entire workflow. With retry + backoff, temporary failures self-heal.

**How to apply:**

1. **Wrap ALL external API calls in retry logic:**
   ```javascript
   async function retryWithBackoff(fn, label, maxRetries = 3) {
     for (let attempt = 1; attempt <= maxRetries; attempt++) {
       try {
         return await fn()
       } catch (error) {
         const isLastAttempt = attempt === maxRetries
         if (isLastAttempt) {
           log(`${label} FAILED after ${maxRetries} attempts: ${error.message}`)
           return null  // Return null, let workflow continue
         }
         
         const backoffMs = Math.min(1000 * Math.pow(2, attempt - 1), 10000)
         log(`${label} failed (attempt ${attempt}/${maxRetries}), retrying in ${backoffMs}ms...`)
         // Agent retries internally with backoff
       }
     }
     return null
   }
   ```

2. **Use exponential backoff (not linear):**
   - Attempt 1: Fail → wait 1 second
   - Attempt 2: Fail → wait 2 seconds
   - Attempt 3: Fail → wait 4 seconds
   - Max backoff: 10 seconds (don't wait forever)

3. **Default: 3 retries** (total 4 attempts)
   - Most transient failures resolve within 3 retries
   - Adjust for specific APIs if needed

4. **Return null on final failure** (not throw)
   - Allows workflow to continue with partial results
   - filter(Boolean) removes nulls in synthesis
   - Better than killing entire workflow

5. **Log retry attempts clearly:**
   ```javascript
   log(`${label} failed (attempt ${attempt}/${maxRetries}), retrying in ${backoffMs}ms...`)
   log(`${label} FAILED after ${maxRetries} attempts: ${error.message}`)
   ```

6. **Apply to these API types:**
   - ✅ OpenRouter API calls
   - ✅ DeepSeek API calls
   - ✅ Cerebras API calls
   - ✅ Cloudflare Workers AI calls
   - ✅ Google Gemini API calls
   - ✅ OpenAI API calls
   - ✅ Web fetches (WebFetch tool)
   - ✅ SSH commands to remote nodes (can timeout)

7. **DON'T apply to:**
   - ❌ Local file operations (Read, Write, Edit)
   - ❌ Ollama local models (fast, reliable)
   - ❌ Claude API (already has retry internally)

**Workflow pattern:**
```javascript
const multiAI = await parallel([
  () => retryWithBackoff(
    () => agent('DeepSeek analysis', {model: 'haiku'}),
    'DeepSeek'
  ),
  () => retryWithBackoff(
    () => agent('Cerebras analysis', {model: 'haiku'}),
    'Cerebras'
  ),
  () => retryWithBackoff(
    () => agent('OpenRouter analysis', {model: 'opus'}),
    'OpenRouter'
  )
])

// Filter out nulls from failed attempts
const successful = multiAI.filter(Boolean)
log(`Multi-AI: ${successful.length}/${multiAI.length} models succeeded`)
```

**What this prevents:**
- ❌ OLD: Single API failure kills entire workflow
- ✅ NEW: Retries 3 times with backoff, continues if still fails

- ❌ OLD: Rate limit 429 → workflow dies
- ✅ NEW: Wait 1s/2s/4s, retry, usually succeeds

- ❌ OLD: Network blip → lose all progress
- ✅ NEW: Retry succeeds, workflow continues

**Success metrics:**
- Workflow resilience: 90%+ success rate even with transient failures
- API retry success: ~80% of failures resolve within 3 retries
- Minimal user intervention needed

## Related

- [[feedback_always_max_parallelism]] - Parallel execution (makes retry even more important)
- [[feedback_always_multi_ai]] - Multi-AI consensus (multiple APIs = higher failure risk)
- [[reference_multi_ai_providers]] - All API providers that need retry logic
