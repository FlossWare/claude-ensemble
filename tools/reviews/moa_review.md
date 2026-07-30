# Mixture of Agents (MoA) - Fleet Code Review

**Date:** 2026-07-26
**Files Reviewed:**
- `tools/mixture_of_agents.py` (824 lines)
- `tools/moa_blueprint.py` (227 lines)

**Reviewing Models:**
1. NVIDIA Nemotron 3 Ultra 550B (`nvidia/nemotron-3-ultra-550b-a55b:free`)
2. NVIDIA Nemotron 3 Nano 30B (`nvidia/nemotron-3-nano-30b-a3b:free`)
3. Google Gemma 4 26B (`google/gemma-4-26b-a4b-it:free`)

**Ratings:** 6/10, 8/10, 7/10 -- **Average: 7.0/10**

---

## Synthesis of Common Findings

All three reviewers independently identified the same core issues, listed here by consensus strength:

### UNANIMOUS (3/3 reviewers flagged)

1. **Thread-unsafe API key cache (CRITICAL)**
   - Location: `mixture_of_agents.py` lines 138-183
   - Global variables `_cached_api_key` and `_cache_expiry` are read and written without any synchronization
   - Under concurrent Flask requests, multiple threads can simultaneously miss the cache and hammer the secrets endpoint
   - The check-then-act pattern (`if _cached_api_key and time.monotonic() < _cache_expiry`) is not atomic
   - Fix: Use `threading.Lock` to protect the cache, or use `functools.lru_cache` with a wrapper

2. **Silent fallback using content length as quality proxy (CRITICAL)**
   - Location: `mixture_of_agents.py` line 583
   - When all Layer 2 aggregators fail, code falls back to `max(successful_l1, key=lambda o: len(o.content))`
   - Length is a terrible quality metric -- verbose hallucinations beat concise correct answers
   - Arbiter fallback (line 619) uses a different strategy (first successful), creating inconsistency
   - Fix: Return a 502 error or use a more robust quality signal

3. **Error details leaked to clients (MEDIUM)**
   - Location: `moa_blueprint.py` lines 162-167
   - Raw exception strings returned via `f'Configuration error: {exc}'` and `f'Internal error: {exc}'`
   - Could expose internal IPs (aio-01), URLs, or request headers to external callers
   - Fix: Log full exception server-side, return generic error messages to clients

### MAJORITY (2/3 reviewers flagged)

4. **ThreadPoolExecutor created per layer per request**
   - Location: `mixture_of_agents.py` line 436
   - Under high load, constant creation/destruction of thread pools adds overhead and may hit OS thread limits
   - Fix: Use a persistent, shared ThreadPoolExecutor

5. **Silent truncation of model outputs**
   - Location: `mixture_of_agents.py` lines 342-344
   - `text[:MAX_OUTPUT_CHARS]` is a "dumb" truncation that can break mid-sentence, mid-JSON, or mid-instruction
   - Aggregators receive truncated content with no indication of what was lost
   - Critical facts at the end of long responses are silently dropped

6. **Inconsistent HTTP status codes for partial failures**
   - Location: `moa_blueprint.py` line 159
   - `status = 200 if result.answer else 502` returns 200 even when `result.error` is set (e.g., aggregator failure with L1 fallback)
   - Automated clients expecting 200 = success will miss degraded responses

7. **Position bias in aggregation prompts**
   - Location: `mixture_of_agents.py` lines 338-345
   - Responses presented as "Response 1, Response 2, ..." in fixed order
   - Position bias is well-documented in LLM literature -- earlier responses get disproportionate attention
   - Fix: Shuffle the order randomly per request

8. **Overlap validation only warns, does not prevent**
   - Location: `mixture_of_agents.py` lines 505-513
   - Code documents "ZERO overlap" between proposers and aggregators but only logs a warning when overlap exists
   - Self-confirmation bias risk remains active

### SINGLE REVIEWER (noteworthy)

9. **API key cache doesn't distinguish by `key_name`** -- the function accepts a `key_name` parameter but the single global cache slot means different keys would thrash each other (Nemotron Ultra)

10. **`num_layers` silently clamped to 2-4** without warning -- user intent ignored if they pass values outside range (Nemotron Ultra)

11. **No rate limiting on `/moa/query`** -- expensive endpoint (7+ model calls per request) with no protection against abuse or DoS (Nemotron Ultra)

12. **No request ID or tracing** -- impossible to correlate logs across concurrent requests (Nemotron Ultra)

13. **Health check doesn't verify model connectivity** -- returns "healthy" as long as API key is fetchable, even when all models are down (Nemotron Ultra)

14. **Uniform temperature/max_tokens across layers** -- synthesis needs lower temperature for determinism but gets the same 0.7 as proposers (Nemotron Ultra)

15. **Hardcoded model lists will stale** -- `list_available_free_models()` is static, no versioning or freshness checks (Gemma)

---

## Individual Model Reviews

### Review 1: NVIDIA Nemotron 3 Ultra 550B

**Rating: 6/10**

Solid architectural foundation with good separation of concerns, but significant production-readiness gaps in thread safety, error handling, and operational concerns.

#### Thread Safety Under Concurrent Flask Requests

**Critical: Global API Key Cache Race Condition** (mixture_of_agents.py:107-145)
```python
_cached_api_key: Optional[str] = None
_cache_expiry: float = 0.0

def _fetch_api_key(key_name: str = 'OPENROUTER_API_KEY') -> str:
    global _cached_api_key, _cache_expiry
    if _cached_api_key and time.monotonic() < _cache_expiry:
        return _cached_api_key  # RACE: check-then-act not atomic
```
Under concurrent requests, multiple threads can simultaneously miss the cache and hammer the secrets endpoint. If `key_name` ever varies, the single global cache slot would thrash between different keys.

**Module-Level State Leakage:** With gunicorn `--workers > 1`, each worker has independent cache (acceptable), but within a multi-threaded worker the race is real.

#### API Key Handling and Caching

| Issue | Location | Severity |
|-------|----------|----------|
| Cache doesn't distinguish by `key_name` | Line 109, 122 | High |
| Env var checked AFTER cache | Lines 122-127 | Medium |
| No sanitization of `key_name` in URL | Line 133 | Low |
| API key potentially leaked via requests debug logging | Line 203 | Medium |
| Private function `_fetch_api_key` imported by blueprint | moa_blueprint.py:17 | Design flaw |

#### Error Propagation and Fallback Logic

**Inconsistent Fallback Heuristics:** Three different strategies used (longest, first, first). Length is a poor quality proxy.

**Silent Partial Success Returns HTTP 200:** Returns 200 even when `result.error` is set.

**Internal Error Details Leaked:** `f'Configuration error: {exc}'` and `f'Internal error: {exc}'`.

#### Model Selection and Bias Prevention

- Overlap check only warns, doesn't prevent self-confirmation bias
- Position bias in prompts (fixed order of responses)
- Hardcoded model lists will stale
- Good: model names replaced with generic "Response N" labels

#### Bugs Causing Silent Wrong Results

- Silent truncation of model outputs drops critical information
- Uniform temperature/max-tokens across layers (synthesis needs lower temp)
- `_call_model` swallows errors into return values -- missed checks = silent empty strings
- `num_layers` silently clamped without warning

#### Design Flaws

| Issue | Location | Impact |
|-------|----------|--------|
| No rate limiting on `/moa/query` | moa_blueprint.py | DoS risk |
| No auth on any endpoint | moa_blueprint.py | Security risk |
| Health check incomplete | moa_blueprint.py | False "healthy" |
| No request ID / tracing | Both files | Debug impossible |
| Prompt length limit 50K chars | moa_blueprint.py:43 | May exceed context window |
| `max_tokens` capped at 32768 | moa_blueprint.py:158 | Some models support 128K+ |

---

### Review 2: NVIDIA Nemotron 3 Nano 30B

**Rating: 8/10**

Well-structured, heavily documented, implements a genuinely useful pipeline. Most architectural decisions are sound. Main problems are thread-safety bugs, incomplete error handling, and design-level oversights.

#### Thread Safety

| Issue | Location | Fix |
|-------|----------|-----|
| Global API-key cache mutated without lock | Lines 71-108 | Use `threading.Lock` |
| Cache-expiry check not atomic | Same block | Double-checked locking |

Under multi-threaded WSGI (e.g., gunicorn with 4-8 workers), two requests can read the stale value, both decide the cache is expired, both call the secrets endpoint, and the later write overwrites the earlier one -- lost update and race condition.

---

### Review 3: Google Gemma 4 26B

**Rating: 7/10**

Well-structured, uses modern Python features. Implements a sophisticated pattern. Contains significant thread-safety issues and potential silent failures in fallback logic.

#### Thread Safety

**Race Condition in API Key Caching** (Lines 157-178): Multiple threads may enter the expired-cache path simultaneously. One thread could update `_cache_expiry` while `_cached_api_key` is still being written.

**Thread Pool Management** (Line 345): New `ThreadPoolExecutor` created on every layer of every query. Under high load, constant thread creation/destruction causes overhead.

#### API Key & Security

**Sensitive Data Leakage** (moa_blueprint.py Lines 155-178): Exception strings may contain internal URLs, IPs, or request headers.

#### Error Propagation

**Silent Degradation:** `len(o.content)` is a terrible proxy for quality. Hallucination-heavy responses chosen over concise correct ones.

**Inconsistent Status Codes:** 200 returned for degraded responses with `error` field set.

#### Model Selection

- Hardcoded model strings are fragile
- Bias prevention via generic labels (good design)

#### Edge Cases

- Dumb truncation can break mid-JSON or mid-instruction
- Timeout mismatches between layers can cause zombie requests

---

## Prioritized Fix List

| Priority | Issue | Effort |
|----------|-------|--------|
| P0 | Add `threading.Lock` to API key cache | Small |
| P0 | Fix fallback quality heuristic (replace `len()` with better signal or 502) | Medium |
| P1 | Sanitize error messages returned to clients | Small |
| P1 | Shuffle response order in aggregation prompts to prevent position bias | Small |
| P1 | Make overlap validation enforce, not just warn | Small |
| P2 | Use persistent ThreadPoolExecutor | Medium |
| P2 | Add request ID / tracing | Medium |
| P2 | Add rate limiting to `/moa/query` | Medium |
| P2 | Improve truncation (token-based or semantic) | Medium |
| P3 | Per-layer temperature/max_tokens configuration | Small |
| P3 | Dynamic model discovery instead of hardcoded lists | Large |
| P3 | Health check with lightweight model call | Small |
