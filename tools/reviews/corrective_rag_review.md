# Corrective RAG (CRAG) Implementation Review

**Date:** 2026-07-26
**Files:** `tools/corrective_rag.py`, `tools/corrective_rag_blueprint.py`
**Review Models:**
- nvidia/nemotron-3-ultra-550b-a55b:free (550B params)
- nvidia/nemotron-3-super-120b-a12b:free (120B params)
- google/gemma-4-31b-it:free (31B params - rate limited, did not complete)

**Note:** Originally requested models (google/gemini-2.5-flash-preview:free, nousresearch/hermes-3-llama-3.1-405b:free, qwen/qwen3-30b-a3b:free) were unavailable on OpenRouter at review time. Substituted with strongest available free models.

---

## Round 1 Review Scores

| Model | Score | Key Concerns |
|-------|-------|-------------|
| Nemotron Ultra 550B | **5/10** | Prompt quality, fallback duplication, rate limiting, thread safety |
| Nemotron Super 120B | **~6/10** | max_fallback_rounds unused, grading failures not tracked in blueprint |

## Issues Found and Fixed

### Critical (Fixed)

1. **Grading prompt lacked definitions** (Nemotron Ultra: 3/10 for prompt quality)
   - **Before:** Generic "rate relevance" with no grade definitions
   - **After:** Each grade (CORRECT/AMBIGUOUS/INCORRECT) has a clear definition
   - Prompt now instructs "Respond with exactly one word"

2. **Wrong fallback_type label** (both models)
   - `_handle_fallback` strategy 3 used `'reformulate'` in `_update_stats` but `'refined_ambiguous'` in the return dict
   - Fixed: both now use `'refined_ambiguous'`

3. **Global `_grading_failure_count` not thread-safe** (Nemotron Ultra)
   - Module-level counter caused race conditions in multi-threaded Flask
   - Fixed: moved to per-instance `self.grading_failures` on CorrectiveRAG
   - Added `_grade_results()` instance method that tracks failures per-request

4. **`_get_crag()` dead code in blueprint** (Nemotron Ultra)
   - Defined but never called; endpoint creates new CorrectiveRAG per request
   - Fixed: removed `_get_crag()`, `_crag`, and `_crag_lock`

### Major (Fixed)

5. **No pipeline timeout** (Nemotron Ultra)
   - Added `PIPELINE_TIMEOUT_S = 120` constant
   - Added `_check_timeout()` method checked before each fallback strategy
   - Returns early with `fallback_type: 'timeout'` when exceeded

6. **No Retry-After header handling** (Nemotron Ultra)
   - 429 responses now check `Retry-After` header and use its value
   - Falls back to exponential backoff if header absent

7. **CLI had no error handling** (Nemotron Ultra)
   - Added try/except around `main()` for KeyboardInterrupt and general exceptions

8. **Grading failures not tracked in blueprint** (Nemotron Super)
   - Added `grading_failures` to result metadata
   - Blueprint now reads and aggregates `total_grading_failures`

9. **Blueprint imported unused functions** (Code review)
   - Removed imports of `grade_result`, `grade_results`, `refine_result`, `reformulate_query`, `search_knowledge_base`

### Known Remaining Issues (Deferred)

10. **`max_fallback_rounds` unused** - Parameter stored but never enforced. Strategies run in fixed sequence. The pipeline timeout effectively bounds fallback attempts.

11. **Rate limiting is per-process** - `time.sleep(REQUEST_INTERVAL)` serializes requests within a process but doesn't coordinate across gunicorn workers. For production with multiple workers, consider Redis-based token bucket.

12. **Code duplication between `_handle_no_results` and `_handle_fallback`** - Both methods implement similar fallback sequences. Could be consolidated into a single `_execute_fallback_chain()` method. Left as-is for readability.

13. **API key caching doesn't handle rotation** - `_cached_api_key` is set once per process. For key rotation, restart the process.

14. **Hardcoded model lists** - GRADING_MODELS and REFINEMENT_MODELS are constants. Could be configurable via environment or API.

15. **Refinement output not validated** - LLM extraction may hallucinate content not in the original document. Could add overlap checking.

---

## Round 2 Re-Review

After fixes, re-reviewed by same 2 models (Gemma rate-limited again).

### Nemotron Ultra 550B Re-Review

Key remaining observations (post-fix):
- Thread safety for `_grading_failure_count` resolved (now per-instance)
- Dead code `_get_crag()` removed
- Pipeline timeout properly implemented at all fallback entry points
- Grading prompt quality significantly improved with definitions
- Rate limiting still per-process (acceptable for current scale)

### Nemotron Super 120B Re-Review

Key remaining observations (post-fix):
- Confirmed all 6 fixes properly applied
- Noted grading failures now tracked per-request via instance method
- Blueprint analytics correctly aggregating `total_grading_failures`
- Suggested: could re-grade after refinement (deferred as design choice)

---

## Architecture Summary

```
User Query
    |
    v
[Knowledge Base Search] --> POST /knowledge/search (hybrid/fulltext/vector)
    |
    v
[LLM Grading] --> Grade each result as CORRECT/AMBIGUOUS/INCORRECT
    |
    +-- All CORRECT -----------> Return results directly
    |
    +-- CORRECT + AMBIGUOUS ---> Return CORRECT + refine AMBIGUOUS via LLM
    |
    +-- All INCORRECT/AMBIGUOUS -> Fallback chain:
        |
        1. Reformulate query (LLM rephrase) + re-search + re-grade
        2. Try alternative search modes (fulltext, vector)
        3. Refine ambiguous results (extract relevant sentences)
        4. Web search (last resort)
        5. Return empty (exhausted)

Timeout: 120s max for entire pipeline
```

## Files

- `tools/corrective_rag.py` - Main CRAG module (CLI + library)
- `tools/corrective_rag_blueprint.py` - Flask blueprint (POST /rag/corrective-search, GET /rag/corrective/stats)
