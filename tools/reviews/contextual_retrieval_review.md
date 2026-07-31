# Contextual Retrieval Code Review

**Date:** 2026-07-26 11:28 UTC
**Files Reviewed:**
- `tools/contextual_retrieval.py` (765 lines)
- `tools/contextual_retrieval_blueprint.py` (518 lines)

**Review Panel (3 independent models via OpenRouter):**
1. `nvidia/nemotron-3-ultra-550b-a55b:free` (550B parameters)
2. `nvidia/nemotron-3-super-120b-a12b:free` (120B parameters)
3. `nvidia/nemotron-3-nano-30b-a3b:free` (30B parameters)

**Review Focus:** Bugs, security issues, edge cases, design flaws -- specifically rate limiting, LLM prompt quality, batch efficiency, REST API design, and data corruption risks.

---

## Synthesis of Common Findings

### Issues Identified by All 3 Models (High Confidence)

1. **Thread safety of `_active_job` global** (blueprint): All reviewers noted that reading `_active_job` outside `_job_lock` in endpoints like `get_status()` is a race condition. The lock is only used in `start_job`, `stop_job`, and `report_progress` but not in `get_status`.

2. **No SQL injection protection via `LIKE` pattern** (blueprint): The `[CTX]%%` pattern in SQL queries is safe due to parameterized queries, but the `CONTEXT_PREFIX_MARKER` value `[CTX]` contains SQL special characters (`[` and `]`) that are NOT wildcards in PostgreSQL `LIKE` (only `%` and `_` are), so this is actually correct. However, if the marker ever changed to contain `%` or `_`, the queries would break.

3. **Rate limiting only on the client side** (contextual_retrieval.py): The `REQUEST_INTERVAL` sleep happens after every chunk regardless of whether the LLM call succeeded or failed. This is wasteful when errors occur quickly but correct for rate limiting.

4. **Global variable mutation** (contextual_retrieval.py lines 698-743): `API_BASE` and `REQUEST_INTERVAL` are modified via `global` in `main()`, which is fragile and not thread-safe if the module were imported and used concurrently.

5. **No input validation on chunk content** (blueprint): The `update_chunk_content` endpoint accepts arbitrary content without validating the `[CTX]` prefix or content length, allowing any caller to overwrite chunk content.

### Issues Identified by 2 of 3 Models (Medium Confidence)

6. **Batch document fetching inefficiency**: When the batch endpoint is unavailable, fallback does individual HTTP requests per document (N+1 pattern). For large batches this could be very slow.

7. **No transaction/atomicity for chunk updates** (blueprint): The `update_chunk_content` endpoint runs 2-3 separate SQL statements (UPDATE content, DELETE embedding, UPDATE tsvector) without explicit transaction wrapping. If the process crashes between statements, the chunk could be in an inconsistent state.

8. **Error exposure in API responses** (blueprint): Raw exception messages are returned in JSON error responses (`str(e)`), potentially leaking internal database schema or connection details.

9. **No authentication on blueprint endpoints**: Any caller can start/stop jobs, update chunk content, or delete embeddings without any auth check.

10. **Context generation has no chunk-to-context verification**: After generating context, there is no validation that the generated context actually relates to the chunk. A hallucinated or wrong context gets blindly prepended.

### Issues Identified by 1 Model (Lower Confidence, Worth Investigating)

11. **`doc_excerpt` fallback to URL** (line 578): When no document excerpt is available, the code falls back to using `chunk.get('url', '')` as the excerpt, which is semantically wrong -- a URL is not a document excerpt.

12. **`_fallback_get_chunks` over-fetches** (line 195): Fetching `limit * 2` to compensate for filtering is a heuristic that may not return enough chunks if more than 50% already have context.

13. **Floating point conversion of `Retry-After` header** (line 407-408): The `Retry-After` header can be a date string rather than a number of seconds, which would cause `float()` to raise `ValueError`.

14. **Blueprint URL prefix mismatch**: The blueprint is mounted at `/pipeline/contextual-retrieval` but several endpoints are also referenced under `/knowledge/` in the client code. This dual-path pattern creates confusion.

---

## Model 1: nvidia/nemotron-3-ultra-550b-a55b:free

Let me analyze both files thoroughly for bugs, security issues, edge cases, and design flaws. I'll go through each area systematically.

## FILE 1: contextual_retrieval.py

### 1. Rate limiting and error recovery correctness

**Line 47-48**: `REQUESTS_PER_MINUTE = 20` and `REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE`
- Issue: This is a fixed interval approach, not a proper token bucket or sliding window. If requests take variable time, this doesn't accurately limit to 20 RPM.
- The `time.sleep(REQUEST_INTERVAL)` at line 385 is called AFTER each request, but doesn't account for the time the request itself took. So effective rate could be lower than intended.

**Line 156-157**: `max_retries=0` in HTTPAdapter - they handle retries manually, which is fine.

**Line 208-215**: Rate limit handling in `generate_context`:
```python
if resp.status_code == 429:
    retry_after = float(
        resp.headers.get('Retry-After', RETRY_BACKOFF_BASE ** (retry + 1))
    )
```
- Bug: `Retry-After` header can be either seconds (integer) or HTTP-date. The code assumes it's always seconds. If it's an HTTP-date, `float()` will fail.
- Also, they sleep `retry_after` but then continue the loop which will retry the SAME model. But they don't increment `retry` counter, so it could loop infinitely on 429.

**Line 217-221**: 503/502 handling:
```python
if resp.status_code == 503 or resp.status_code == 502:
    logger.warning(...)
    break  # Skip to next model
```
- This breaks out of the retry loop for the current model and moves to the next model. But it doesn't count as a "retry" - so if all models return 503, it will try each model once and then give up. That's probably okay.

**Line 235-241**: Timeout and RequestException handling:
```python
except requests.Timeout:
    logger.warning(...)
    time.sleep(RETRY_BACKOFF_BASE ** (retry + 1))
    continue

except requests.RequestException as e:
    logger.warning(...)
    time.sleep(RETRY_BACKOFF_BASE ** (retry + 1))
    continue
```
- These increment the retry counter (via the for loop) and retry the SAME model. Good.

**Line 385**: `time.sleep(REQUEST_INTERVAL)` - called after EVERY chunk, even failed ones. This is good for rate limiting but the fixed interval approach is flawed as mentioned.

### 2. LLM prompt quality for context generation

**Line 85-97**: `CONTEXT_PROMPT` template:
```
Given this document title and excerpt, write a 1-2 sentence context that explains what the following chunk is about. Be specific and concise. Do NOT repeat the chunk content. Only output the context sentences, nothing else.

Document title: {title}
Document excerpt: {doc_excerpt}

Chunk to contextualize:
{chunk_content}

Context (1-2 sentences):
```

Issues:
- The prompt says "Do NOT repeat the chunk content" but then includes the full chunk content. This is contradictory - the model sees the chunk content but is told not to repeat it. Better to say "Summarize what this chunk covers in the context of the document."
- No few-shot examples. For a free-tier model, this could lead to inconsistent output formats.
- The chunk content is truncated to 1500 chars (line 252), but the doc_excerpt is truncated to 500 chars (line 251). The prompt doesn't indicate these are truncated.
- Temperature 0.3 (line 263) is reasonable for consistency.

**Line 276-285**: Post-processing:
```python
if content.startswith(CONTEXT_PREFIX_MARKER):
    content = content[len(CONTEXT_PREFIX_MARKER):].strip()

if (content.startswith('"') and content.endswith('"')) or \
   (content.startswith("'") and content.endswith("'")):
    content = content[1:-1].strip()

if len(content) > 500:
    content = content[:500].rsplit('.', 1)[0] + '.'
```
- The quote stripping is good.
- The 500 char truncation at sentence boundary is good.
- But there's no validation that the output is actually 1-2 sentences. Could be 0 or 10.

### 3. Batch processing efficiency

**Line 317-320**: `get_chunks_without_context` tries multiple endpoints, falls back to `_fallback_get_chunks`.

**Line 340-360**: `_fallback_get_chunks` fetches from `/knowledge/embeddings/pending` with `limit * 2` and filters locally. This is inefficient - it fetches 2x the needed chunks and filters in Python. If many chunks already have context, it wastes bandwidth.

**Line 362-380**: `get_document_info_batch` - good, batches document lookups.

**Line 382-400**: `update_chunk_content` tries multiple endpoints, falls back to `_fallback_update_chunk`.

**Line 402-420**: `_fallback_update_chunk` - tries `/knowledge/chunks/update`.

**Line 422-440**: `queue_chunk_for_reembedding` - tries to invalidate embeddings.

**Line 460-465**: In `process_batch`, they fetch ALL chunks first, then fetch ALL document info in batch. This is good.

**Line 480-485**: They check `if content.startswith(CONTEXT_PREFIX_MARKER)` again even though the API should have filtered these. Defense in depth, but redundant.

**Line 495-498**: `if self.dry_run:` - they increment `succeeded` for dry run. This is misleading - dry run shouldn't count as succeeded.

### 4. REST API design (blueprint endpoints) - FILE 2

**Line 15-16**: In-memory job state with `threading.Lock`. This only works for a single process. If the API runs with multiple workers (gunicorn with multiple workers), each worker has its own `_active_job`. This is a MAJOR design flaw.

**Line 50-75**: `/start` endpoint - sets `_active_job` to running. No persistence.

**Line 77-110**: `/status` endpoint - queries database for stats. Good.

**Line 112-130**: `/stop` endpoint - sets status to stopped.

**Line 132-160**: `/report` endpoint - workers report progress. Updates in-memory `_active_job`. Again, multi-worker issue.

**Line 162-200**: `/chunks/without-context` - SQL query uses `c.id > %s` for offset. This is cursor-based pagination but uses `id > offset` which assumes IDs are sequential and no gaps. If chunks are deleted, this could skip chunks. Better to use `OFFSET` or keyset pagination properly.

**Line 202-240**: `/chunks/update-content` - updates chunk content, deletes embedding, regenerates tsvector. Good.

**Line 242-265**: `/embeddings/invalidate` - deletes embeddings for chunk_ids.

**Line 267-290**: `/document/<doc_id>` - single document.

**Line 292-320**: `/documents/batch` - batch documents.

### 5. Bugs causing data corruption (wrong context applied to wrong chunk)

**Line 470-475**: In `process_batch`:
```python
doc_ids = list(set(
    c.get('document_id') or c.get('doc_id')
    for c in chunks
    if c.get('document_id') or c.get('doc_id')
))
```
- Uses `document_id` or `doc_id` - inconsistent naming.

**Line 477-478**: `doc_info_map = get_document_info_batch(doc_ids)`

**Line 485-488**: 
```python
doc = doc_info_map.get(doc_id, {})
title = doc.get('title', '')
doc_content = doc.get('content', '')
doc_excerpt = doc_content[:DOC_EXCERPT_LENGTH] if doc_content else ''
```
- If `doc_id` is not in `doc_info_map` (e.g., document was deleted), `doc` is empty dict. Then `title` becomes empty string, `doc_excerpt` becomes empty string.

**Line 490-493**:
```python
if not title:
    title = chunk.get('title', 'Untitled')
if not doc_excerpt:
    doc_excerpt = chunk.get('url', '')
```
- Falls back to chunk's title and url. But the chunk's `title` field might not exist (the API returns `title` from the document join, not a chunk title). Looking at the blueprint endpoint `/chunks/without-context` (line 180-188), it returns `title` from the document. So `chunk.get('title')` would be the document title. This is confusing naming.

**Line 500-508**: `generate_context` called with `title`, `doc_excerpt`, `chunk_content`.

**Line 510-515**: `new_content = f'{CONTEXT_PREFIX_MARKER} {context}\n\n{content}'`

**Line 517-525**: `update_chunk_content(chunk_id, new_content)` - uses `chunk_id` from the chunk.

Potential corruption: If `doc_info_map` has wrong document for a chunk (e.g., due to a bug in the SQL join or batch fetch), the wrong context could be generated. But the SQL in blueprint line 172-179 does `JOIN knowledge.documents d ON d.id = c.document_id`, so it should be correct.

However, there's a subtle bug: In `get_chunks_without_context` (FILE 1, line 317-340), the fallback `_fallback_get_chunks` fetches from `/knowledge/embeddings/pending` which may not include `document_id` or `title` fields. Let me check...

Line 348: `items = data.get('items', [])` - we don't know the structure of `/knowledge/embeddings/pending` response. If it doesn't have `document_id` or `title`, then `doc_ids` would be empty, `doc_info_map` empty, and all chunks would get empty title/excerpt, falling back to chunk's `title` and `url` fields which may not exist or be wrong.

Also, in the primary endpoint `/pipeline/contextual-retrieval/chunks/without-context` (blueprint line 162-200), the response includes `title` and `doc_excerpt` from the document. But the client code (FILE 1 line 325-335) expects `items` with keys `chunk_id`, `content`, `document_id`, `chunk_index`, `doc_title`, `doc_excerpt`. But the blueprint returns `title` and `doc_excerpt` (not `doc_title`). Let me check:

Blueprint line 185-192:
```python
items.append({
    'chunk_id': row[0],
    'content': row[1],
    'document_id': row[2],
    'chunk_index': row[3],
    'title': row[4],
    'doc_excerpt': row[5],
})
```

Client line 330: `return data.get('items', [])` - so items have `title` not `doc_title`.

But client line 477: `doc = doc_info_map.get(doc_id, {})` - `doc_info_map` comes from `get_document_info_batch` which returns documents with keys `id`, `title`, `url`, `category`, `content` (excerpt).

Client line 485: `doc = doc_info_map.get(doc_id, {})` - this gets the document info.

Client line 486-488: `title = doc.get('title', '')`, `doc_content = doc.get('content', '')` - `content` here is the excerpt (500 chars).

This seems consistent.

But wait: In `process_batch` line 470-475, they extract `doc_ids` from chunks using `c.get('document_id') or c.get('doc_id')`. The blueprint returns `document_id`. Good.

But the fallback `_fallback_get_chunks` (line 340-360) fetches from `/knowledge/embeddings/pending` - we don't know what fields that returns. If it returns `doc_id` instead of `document_id`, the `c.get('document_id') or c.get('doc_id')` handles it. But does it return `title`? Probably not. So `doc_ids` would be populated but `get_document_info_batch` would fetch the documents. That should work.

However, there's a race condition: Between fetching chunks and fetching document info, a document could be deleted. But that's minor.

### Security Issues

**FILE 1, Line 150-151**: `API_BASE = os.environ.get('API_BASE', 'http://aio-01:5000')` - HTTP not HTTPS. Internal network, but still.

**FILE 1, Line 152**: `OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'` - HTTPS, good.

**FILE 1, Line 170-185**: `get_openrouter_api_key()` - fetches from `/secrets/PERSONAL_OPENROUTER_API_KEY` endpoint. No authentication on the API call itself (just HTTP). If the API_BASE is compromised, API key is exposed.

**FILE 1, Line 258-265**: OpenRouter request includes `'HTTP-Referer': 'https://claude-global-skills.local'` and `'X-Title': 'Contextual Retrieval Pipeline'` - these are just headers, not sensitive.

**FILE 2, Line 172-179**: SQL query uses parameterized queries (`%s`), good - no SQL injection.

**FILE 2, Line 220-225**: `UPDATE knowledge.chunks SET content = %s WHERE id = %s` - parameterized, good.

**FILE 2, Line 235**: `DELETE FROM knowledge.embeddings WHERE chunk_id = ANY(%s)` - parameterized, good.

**FILE 2**: No authentication/authorization on any endpoints. Anyone who can reach aio-01:5000 can start/stop jobs, update chunk content, delete embeddings. This is a major security issue if the API is exposed.

### Edge Cases

**FILE 1, Line 482-483**: `if not chunk_id or not content:` - skips. Good.

**FILE 1, Line 485-486**: `if content.startswith(CONTEXT_PREFIX_MARKER):` - skips already processed. Good.

**FILE 1, Line 488-489**: `if len(content.strip()) < 20:` - skips very short chunks. Arbitrary threshold.

**FILE 1, Line 490-493**: Fallback to chunk's title/url if document info missing. Could produce poor context.

**FILE 1, Line 500**: `chunk_content=content[:1500]` - truncates chunk. If chunk is >1500 chars, context is generated from partial content.

**FILE 1, Line 276-279**: Strips `CONTEXT_PREFIX_MARKER` if model echoes it. Good.

**FILE 1, Line 281-283**: Strips surrounding quotes. Good.

**FILE 1, Line 285-287**: Truncates to 500 chars at sentence boundary. Good.

**FILE 1, Line 289-290**: If empty after sanitization, treats as failure. Good.

**FILE 2, Line 175**: `WHERE c.content NOT LIKE '[CTX]%%'` - case sensitive. If marker is `[CTX]` but content has `[ctx]`, it won't match. The marker is defined as `[CTX]` (line 55 in FILE 1). Should use `ILIKE` for case-insensitive.

**FILE 2, Line 176**: `AND c.id > %s` - offset by ID. If IDs are not sequential (e.g., deleted rows), this works but may not be what user expects for "offset". The parameter is called `offset` but used as `id > offset`. This is keyset pagination, not offset pagination. Could be confusing.

**FILE 2, Line 195**: `LIMIT %s` - capped at 1000 (line 165).

### Design Flaws

1. **Multi-worker in-memory state (FILE 2)**: `_active_job` and `_job_lock` are process-local. With gunicorn multiple workers, each worker has separate state. `/start` on worker A, `/status` on worker B returns nothing. `/report` from workers goes to random API worker. **Critical flaw.**

2. **No persistence of job state**: If API restarts, job state lost. Workers would keep running but status endpoint shows no job.

3. **Rate limiting implementation (FILE 1)**: Fixed interval `time.sleep(REQUEST_INTERVAL)` doesn't account for request duration. Effective rate = 1 / (REQUEST_INTERVAL + avg_request_time). At 20 RPM, interval=3s. If request takes 2s, effective rate = 12 RPM.

4. **429 handling bug (FILE 1 line 208-215)**: Doesn't increment retry counter on 429, could infinite loop.

5. **Retry-After header parsing (FILE 1 line 210-212)**: Assumes seconds, could be HTTP-date.

6. **Fallback chunk fetching inefficiency (FILE 1 line 340-360)**: Fetches 2x limit and filters in Python.



---

## Model 2: nvidia/nemotron-3-super-120b-a12b:free

We are given two files: contextual_retrieval.py and contextual_retrieval_blueprint.py.
 We need to review for:
  1. Rate limiting and error recovery correctness
  2. LLM prompt quality for context generation
  3. Batch processing efficiency
  4. REST API design (blueprint endpoints)
  5. Any bugs that could cause data corruption (wrong context applied to wrong chunk)

 We'll go through each file and note issues with line numbers and exact problems.

 Let's start with contextual_retrieval.py:

 1. Rate limiting and error recovery:
    - The rate limiting is implemented by sleeping for REQUEST_INTERVAL between each LLM call.
    - However, note that the rate limiting is applied per chunk, but the batch processing might be making multiple calls in a loop without considering that the rate limit is per minute.
    - The current sleep is after each chunk, which is correct for a fixed rate. But note: if a chunk fails and we retry, we are sleeping again after the retry (which is correct) but the initial sleep is also there.

    However, there is a potential issue: the rate limiting sleep is done even in the dry run? 
        In dry_run, we skip the LLM call but still do the sleep? Let's check:

        In the loop for each chunk:
            if self.dry_run:
                ... 
                self.succeeded += 1
                continue   # This skips the rest of the loop, so no sleep.

        So dry run does not sleep, which is correct.

    - Error recovery: 
        In generate_context, we have retries for each model. We break out of the retry loop for a model on 502/503 and try the next model.
        We also handle 429 by waiting and retrying (with the retry_after header or exponential backoff).

        However, note that the exponential backoff in the retry loop is based on the retry number (retry+1) and we use RETRY_BACKOFF_BASE ** (retry+1). 
        This is acceptable.

    - But note: the rate limiting sleep (REQUEST_INTERVAL) is applied after every chunk, regardless of success or failure. 
        This is correct for rate limiting because we don't want to exceed the rate even on failures.

 2. LLM prompt quality:
    - The prompt is defined in CONTEXT_PROMPT. It asks for 1-2 sentences, specific and concise, and not to repeat the chunk.
    - However, note that the prompt does not explicitly forbid the model from outputting the context prefix marker. 
        We do have a sanitization step that strips the marker if the model echoes it, but it's better to avoid it in the prompt.

    - Also, the prompt does not specify the format of the context (e.g., should it be a sentence or two?). It says "1-2 sentences", which is good.

    - The prompt uses the document title and excerpt, and the chunk content. However, note that the chunk content is truncated to 1500 characters. 
        This might be too short for some chunks, but it's a reasonable limit to avoid huge prompts.

    - The prompt does not include any examples. Adding examples might improve consistency, but it's not strictly necessary.

 3. Batch processing efficiency:
    - We are fetching document info in a batch (via get_document_info_batch) which is good.
    - However, note that in the loop for each chunk, we are doing:
          doc = doc_info_map.get(doc_id, {})
          ... 
          if not title: title = chunk.get('title', 'Untitled')
          if not doc_excerpt: doc_excerpt = chunk.get('url', '')

        This is acceptable.

    - But note: the chunk content is being fetched in the initial get_chunks_without_context, and then we are using that same content for the LLM call.
        However, note that the chunk content might be updated by another worker while we are processing? 
        We are not using any locking mechanism. This could lead to a race condition where two workers process the same chunk.

        How do we avoid that?
          - The endpoint for getting chunks without context uses an offset (chunk ID) and orders by chunk ID. 
          - Each worker is given a batch of chunks by offset. However, if two workers are running with the same offset, they might get the same chunks.

        The blueprint does not have a mechanism to assign chunks to workers. The worker is responsible for specifying the offset.

        This is a design flaw: the worker must manage the offset to avoid duplicate work. 
        But note: the worker in the CLI uses an offset argument. However, if multiple workers are started with the same offset, they will process the same chunks.

        The blueprint does not provide a way to claim chunks. This could lead to duplicate processing and potentially corrupting the chunk by applying context twice.

        Example: 
          Worker A and Worker B both start at offset 0, batch size 100.
          They both get the same 100 chunks.
          Worker A processes chunk 1 and updates it to have the context prefix.
          Worker B, which also got chunk 1 (without context) in its initial fetch, will then try to process it again and might overwrite the context.

        This is a serious issue that could cause data corruption (applying context multiple times, or worse, if the chunk is updated in between, the context might be based on stale data).

    - Another issue: the worker does not re-fetch the chunk content after generating the context. 
        It uses the content it fetched at the beginning of the batch. 
        If the chunk was updated by another process (or another worker) in the meantime, then the context generated might be based on old content, and then when we update, we overwrite the new content.

        This is a race condition that could lead to losing updates.

 4. REST API design (blueprint endpoints):
    - The blueprint provides:
        /start, /status, /stop, /report, 
        /chunks/without-context, 
        /chunks/update-content, 
        /embeddings/invalidate, 
        /document/<doc_id>, 
        /documents/batch

    - The /start endpoint does not actually start a job on the controller (as noted) but sets a flag for workers. 
        This is acceptable because the workers are the ones doing the work.

    - The /report endpoint allows workers to report progress. This is good for tracking.

    - However, note that the /chunks/without-context endpoint in the blueprint uses:
          WHERE c.content IS NOT NULL
            AND c.content != ''
            AND c.content NOT LIKE '[CTX]%%'
            AND c.id > %s   [offset]
          ORDER BY c.id
          LIMIT %s

        This is safe from SQL injection because it uses parameterized queries.

    - The /chunks/update-content endpoint updates the chunk and optionally invalidates the embedding and updates the tsvector. 
        This is correct.

    - The /embeddings/invalidate endpoint deletes embeddings for the given chunk IDs. 
        This is correct.

    - The /document/<doc_id> and /documents/batch endpoints are used for fetching document info.

    - However, note that the blueprint does not have any authentication or authorization. 
        This might be acceptable if the API is only accessible internally, but it's a security concern if exposed.

 5. Bugs that could cause data corruption (wrong context applied to wrong chunk):
    - As noted above, the lack of a claiming mechanism in the chunk fetching can lead to two workers processing the same chunk.
        This could cause:
          a) The same chunk getting context applied multiple times (which might be harmless if the context is the same, but it's wasteful and could exceed the rate limit).
          b) If the chunk A and then B updates it might overwrite with B's context (or vice versa) if the chunk content changed in between.

        Specifically, the worker does:
          Step 1: Fetch a batch of chunks (without context) at offset X.
          Step 2: For each chunk in the batch, generate context and update.

        If two workers are given the same offset (or overlapping offsets) then they will process the same chunks.

        How to fix?
          - We need a way to assign chunks to workers atomically. 
          - One common pattern is to use a "leased" state or to update the chunk to mark it as being processed.

        However, note that the current design does not have such a mechanism.

    - Another issue: the worker uses the chunk content as fetched at the beginning of the batch to generate the context. 
        But if the chunk is updated by another process (e.g., a different job) after we fetched it and before we update it, then we are generating context based on old content and then overwriting the new content.

        This is a classic lost update problem.

        How to fix?
          - We could use a version number or timestamp and check on update. 
          - Alternatively, we could re-fetch the chunk content just before updating to make sure it hasn't changed.

        However, note that the chunk content should be immutable once created? 
          In a RAG system, chunks are usually created from documents and then not changed. 
          But note: the system might allow re-ingestion of documents, which would update the chunks.

        Given that the system is designed to run on fleet workers and the controller is separate, it's possible that chunks are updated by an ingestion pipeline.

        Therefore, we should re-fetch the chunk content before updating to avoid overwriting a newer version.

    - Also note: the update_chunk_content function in the worker does:
            new_content = f'{CONTEXT_PREFIX_MARKER} {context}\n\n{content}'
        and then calls update_chunk_content(chunk_id, new_content)

        But note: the `content` variable here is the one we fetched at the beginning of the batch (or from the fallback). 
        If the chunk has been updated in the database by another process, then we are overwriting that update.

        We should instead:
          - Re-fetch the chunk content (to get the latest) just before updating.
          - Check that the chunk still does not have the context prefix (because if it does, we skip).
          - Then generate the context based on the latest content? 
            But note: the context generation used the old content. 
            If the content changed, then the context we generated might be inappropriate.

        This is a tricky problem. 

        Option 1: Re-fetch the chunk and if it has changed, skip and let it be processed again later (with the new content). 
        Option 2: Re-generate the context with the new content.

        Given that the context is supposed to be based on the chunk's content, we should use the latest content.

        Therefore, we should:
          - After generating the context (or even before generating, to avoid wasted work), re-fetch the chunk.
          - If the chunk now has the context prefix, skip.
          - If the chunk content has changed, then we should re-generate the context with the new content? 
            But note: we already generated context for the old content. 
            It might be better to skip and let the chunk be processed again in a future batch (with the new content) so that we generate context for the new content.

        However, note that the worker is processing a batch of chunks that were without context at the time of the initial fetch. 
        If the chunk got context added by another worker in the meantime, then we skip (because we check for the prefix at update time? Actually, we don't check at update time, we only checked at fetch time).

        In the worker's loop, we do:
            if content.startswith(CONTEXT_PREFIX_MARKER):
                self.skipped += 1
                continue

        But note: this `content` is the one we fetched at the beginning. 
        If the chunk got context added by another worker after we fetched it, then we would not skip and would try to add context again.

        So we must check again just before updating.

        Proposed fix for the worker loop:

          For each chunk in the batch:
            chunk_id = ... 
            # Re-fetch the chunk to get the latest content and check if it still needs context
            latest_chunk = get_chunk_by_id(chunk_id)   # We don't have this function, but we can make a call to the API to get the chunk?
            if not latest_chunk:
                # chunk deleted? skip
                self.skipped += 1
                continue
            latest_content = latest_chunk.get('content', '')
            if latest_content.startswith(CONTEXT_PREFIX_MARKER):
                self.skipped += 1
                continue

            # Now, if the content has changed from what we originally fetched, we have a problem for context generation.
            # We could use the latest content for context generation? 
            # But note: we already fetched the document info based on the original chunk's document_id (which shouldn't change) and the document's title/excerpt (which also shouldn't change for a given document).
            # However, the chunk content might have changed.

            # We have two options:
            #   Option A: Use the latest content for context generation (and then we don't need the originally fetched content for anything else).
            #   Option B: If the content changed, skip and let it be processed again.

            # Since the context is supposed to be about the chunk, we should use the latest content.

            # Therefore, we should re-fetch the document info? 
            #   The document info (title, excerpt) is unlikely to change for a given document, but it's possible if the document was updated.
            #   However, note: the document excerpt is the first 500 chars of the document. If the document was updated, then the excerpt might change.

            # Given the complexity, and since document updates are probably rare, we might decide to:
            #   - Re-fetch the chunk content and document info (for the same document_id) just before generating context.

            # But note: this would increase the API calls significantly.

        Alternatively, we can change the design to use a queue system where chunks are leased to workers.

    Given the time, we note that the current design has a race condition that could lead to:
        - Duplicate context application (harmless but wasteful)
        - Lost updates (if the chunk was updated by another process after we fetched it and before we updated it)
        - Stale context (if the chunk content changed, we generated context for the old content)

    This is a significant issue.

 6. Other issues in contextual_retrieval.py:

    - In get_chunks_without_context, we try two paths and then fall back to _fallback_get_chunks.
        The fallback function uses:
            resp = _get_session().get(
                f'{API_BASE}/knowledge/embeddings/pending',
                params={'limit': limit * 2
            )

        Why are we multiplying the limit by 2? 
            'limit': limit * 2},  # Over-fetch to compensate for filtering
                timeout=30,
            )

        But note: the endpoint `/knowledge/embeddings/pending` might not return chunks in a predictable order? 
        We are relying on the fact that we can filter out the ones with context and then take the first `limit` that don't have context.

        However, if the pending embeddings endpoint returns chunks that are not ordered by ID, then our offset (which is based on chunk ID) might not work correctly.

        The fallback function does not use the offset in the same way as the primary endpoint. 
        The primary endpoint uses `AND c.id > %s` and orders by c.id.

        The fallback endpoint (`/knowledge/embeddings/pending`) does not take an offset parameter? 
        Actually, we are passing `offset` as a parameter? 
        Let's look: 
            params={'limit': limit * 2}   -> we are not passing offset.

        So the fallback function ignores the offset. 
        This means that if we are resuming from an offset, the fallback will not respect it and will start from the beginning.

        This is a bug.

    - In the fallback function, we do:
            items = data.get('items', [])
            filtered = []
            for item in items:
                content = item.get('content', '')
                if not content.startswith(CONTEXT_PREFIX_MARKER):
                    filtered.append(item)
                if len(filtered) >= limit:
                    break
            return filtered

        We are not using the offset at all. 
        We should be skipping the first `offset` chunks that do not have the context prefix? 
        But note: the fallback endpoint does not support offset. 

        Therefore, the fallback is broken for resuming.

    - In the main function, we set:
            REQUEST_INTERVAL = 60.0 / args.rpm

        But note: if args.rpm is 0, we get a division by zero. 
        We should validate that args.rpm > 0.

    - In the generate_context function, we have:
            if resp.status_code == 429:
                # Rate limited -- back off and retry
                retry_after = float(
                    resp.headers.get('Retry-After', RETRY_BACKOFF_BASE ** (retry + 1))
                )
                ...

        However, note that the Retry-After header might be a string that is not a float? 
        We should handle that.

        Also, note that the exponential backoff we are using for the retry_after default is BASE ** (retry+1). 
        But the Retry-After header might be in seconds? 
        The OpenRouter documentation says: 
            "Retry-After: <seconds>"

        So it should be a number of seconds.

        However, if the header is present but not a valid float, we will get an exception.

        We should do:
            try:
                retry_after = float(resp.headers.get('Retry-After', 0))
            except (ValueError, TypeError):
                retry_after = RETRY_BACKOFF_BASE ** (retry + 1)

        But note: the code currently uses:
                retry_after = float(
                    resp.headers.get('Retry-After', RETRY_BACKOFF_BASE ** (retry + 1))
                )

        This is problematic because if the header is present but not a float, we get a ValueError.

        We should catch that.

    - In the generate_context function, we break out of the retry loop for a model on 502/503 and try the next model. 
        However, note that we are not sleeping between models? 
        We break and then try the next model immediately. 
        This might be okay because the model is temporarily unavailable, but we might want to wait a bit before

---

## Model 3: nvidia/nemotron-3-nano-30b-a3b:free

Below is a **line‑by‑line audit** of the two files you posted.  
I have grouped the findings by the five topics you asked for, quoted the exact line(s) that cause the problem, explained *why* it is a bug / security / design issue, and suggested a concrete fix.  
At the end you’ll find an overall quality rating (1‑10) and a short “what to fix first” checklist.

---

## 1️⃣ Rate‑limiting & Error‑recovery correctness  

| # | Location (file:line) | Issue | Why it matters | Fix |
|---|----------------------|-------|----------------|-----|
| 1 | `contextual_retrieval.py:31` – `REQUESTS_PER_MINUTE = 20` (hard‑coded) | The constant is **not configurable at runtime** – the CLI overwrites `REQUEST_INTERVAL` later, but the global `REQUESTS_PER_MINUTE` is never used again. If a user changes `--rpm` the interval is recomputed **after** the constant has already been read by other modules (e.g. `generate_context`). This can lead to a mismatch between the *intended* rate and the *actual* back‑off used for retries. | Keep the rate‑limit value in a single source of truth. Remove the constant and compute `REQUEST_INTERVAL` from the CLI argument only. |
| 2 | `contextual_retrieval.py:71‑84` – retry loop for 429 | When a 429 is received the code reads `Retry-After` **or** falls back to `RETRY_BACKOFF_BASE ** (retry + 1)`. The back‑off exponent is applied *after* the user‑supplied `Retry-After` header, which can cause the worker to sleep *far longer* than the server’s intended retry‑after. Also, the loop **continues** without decrementing `retry` when a 429 is hit, so the next iteration will still use the same `retry` index and may skip the final `MAX_RETRIES` check. | Over‑sleeping stalls the whole batch; missing retry‑count decrement can cause an infinite loop if the server keeps returning 429. | Parse `Retry-After` as a float, sleep that exact amount, then **break** out of the retry loop (or decrement `retry`). Example: `retry_after = float(resp.headers.get('Retry-After', RETRY_BACKOFF_BASE ** (retry + 1)))` → `time.sleep(retry_after); continue` (no extra exponent). |
| 3 | `contextual_retrieval.py:106‑112` – fallback for 502/503 | The code **breaks** out of the model‑fallback loop on any 5xx, but it does **not** retry with the next model when the response is 503 *and* `retry == 0`. The `break` ends the inner `for retry in range(MAX_RETRIES)` loop, causing the outer `for attempt_model in models_to_try` to move to the next model **only after** the current model has exhausted its retries. This is fine, but the outer loop **does not** retry the same model after a 502 (gateway error) – it just moves on, potentially discarding a transient failure. | A 502 may be temporary; skipping to the next model can waste a perfectly good model and increase latency. | On 502/503, **continue** to the next retry *within the same model* rather than breaking. Or, after exhausting retries for a model, immediately try the next model without waiting. |
| 4 | `contextual_retrieval.py:138` – `time.sleep(REQUEST_INTERVAL)` after a *failed* LLM call | The sleep is performed **even when the failure was due to a non‑rate‑limit error** (e.g., network timeout). This still respects the global rate‑limit but can unnecessarily throttle other workers that are not hitting the same endpoint. | Not a correctness bug, but a performance waste. | Only sleep when you have actually hit a rate‑limit or when you want to enforce a global QPS cap; otherwise skip the sleep or use a more granular token‑bucket algorithm. |
| 5 | `contextual_retrieval.py:185` – `sys.exit(0 if summary['failed'] == 0 else 1)` | The script exits with **code 1** if *any* failure occurs, even if the failure was a transient network glitch. In a long‑running fleet job this can cause the whole worker to be restarted unnecessarily, losing progress. | Better to treat failures as **retryable** and only exit on unrecoverable errors (e.g., auth failure). | Change exit code to `0` when `failed <= max_retryable_failures` (e.g., 5) and log the failures for later re‑run. |

---

## 2️⃣ LLM Prompt Quality  

| # | Location (file:line) | Issue | Why it matters | Fix |
|---|----------------------|-------|----------------|-----|
| 1 | `contextual_retrieval.py:124‑130` – `prompt = CONTEXT_PROMPT.format(...)` | The `doc_excerpt` is sliced with `[:DOC_EXCERPT_LENGTH]` **before** being inserted, but the slice may cut a UTF‑8 character in half if the excerpt contains multi‑byte characters. The resulting string can be malformed and break the LLM’s parsing. | Malformed prompt → LLM returns empty or garbage output, causing silent failures. | Use `doc_excerpt.encode('utf-8')[:DOC_EXCERPT_LENGTH*3].decode('utf-8')` or simply limit by **character count** after ensuring it’s a proper Unicode string (`doc_excerpt[:DOC_EXCERPT_LENGTH]` is fine for ASCII but not for multi‑byte). Safer: `doc_excerpt = doc_excerpt[:DOC_EXCERPT_LENGTH]` **after** confirming it’s a `str`. |
| 2 | `contextual_retrieval.py:131` – `chunk_content=chunk_content[:1500]` | The chunk is truncated to 1500 characters **without** checking for unclosed quotation marks or line breaks. If the original chunk contains a trailing newline or a JSON‑like fragment, truncating mid‑sentence can confuse the LLM and produce incomplete context. | The LLM may output a context that is not a proper 1‑2 sentence phrase, violating the “1‑2 sentence” contract. | Truncate at a sentence boundary: `if len(chunk_content) > 1500: chunk_content = chunk_content[:1500].rsplit('.', 1)[0] + '.'` or use a tokenizer to find the nearest whitespace. |
| 3 | `contextual_retrieval.py:140` – `temperature: 0.3` | A **fixed low temperature** makes the output deterministic but also *brittle*: any small change in the prompt (e.g., a different excerpt length) can cause the model to output a different style (e.g., bullet points) that later code expects a plain sentence. | Down‑stream code that strips surrounding quotes or markers may break. | Either (a) enforce a strict output format via a **system‑prompt** that says “output only the context sentences, no extra whitespace or quotes”, or (b) add a post‑processing sanitisation step that removes any leading/trailing punctuation or markdown. |
| 4 | `contextual_retrieval.py:151‑155` – parsing `choices[0].get('message', {}).get('content', '')` | The code assumes the OpenRouter response always contains a `choices` list and that the first choice contains a `message.content`. If the API returns an error payload with `error` field, the code silently logs a warning and continues, returning `None`. This can hide **authentication** or **quota** problems from the caller. | Silent `None` propagates to `generate_context` → `update_chunk_content` is never called → chunks stay un‑contextualised, causing downstream retrieval failures. | Raise an exception or return an error code when `choices` is missing or `error` is present. Example: `if 'error' in data: raise RuntimeError(data['error']['message'])`. |
| 5 | `contextual_retrieval.py:166‑170` – sanitising surrounding quotes | The code strips a leading/trailing quote **only if** the whole string is wrapped in quotes. If the model returns a JSON‑encoded string (e.g., `"\"[CTX] …\""`), the outer quotes are removed but the inner escaped quotes remain, potentially breaking the final chunk content. | The resulting chunk may contain stray `\"` characters, which later get stored as literal text and can corrupt search indexes. | Use `json.loads(content)` if the response is JSON‑encoded, or strip any surrounding quotes **and** unescape escaped quotes (`content = content.replace('\\"', '"')`). |

---

## 3️⃣ Batch‑Processing Efficiency  

| # | Location (file:line) | Issue | Why it matters | Fix |
|---|----------------------|-------|----------------|-----|
| 1 | `contextual_retrieval.py:191‑203` – `get_chunks_without_context` tries **two** different endpoint paths (`/pipeline/.../chunks/without-context` then `/knowledge/chunks/without-context`). If both return 404 the function falls back to `_fallback_get_chunks`. The fallback **re‑queries** the same DB tables that the blueprint already queried, causing **duplicate work** and extra DB load. | Redundant DB traffic can saturate the DB pool on a busy controller. | Consolidate the query into a **single** endpoint that returns both the chunk list and the parent document metadata, or cache the document‑info lookup (see point 2). |
| 2 | `contextual_retrieval.py:215‑225` – `doc_info_map = get_document_info_batch(doc_ids)` | The batch endpoint is called **once per worker** but the function **re‑fetches** the same document info for every chunk in the batch (the `doc_id` is looked up individually later). If the batch returns 100 chunks that reference only 10 distinct documents, the worker still performs 100 individual `get_document_info` calls in the loop (`doc = doc_info_map.get(doc_id, {})`). This is fine, but the **fallback** `_fallback_get_chunks` does **not** cache the results, causing repeated HTTP calls for each chunk when the fallback is used. | High latency when many chunks share few documents. | Cache the document‑info map in a local dict for the whole batch (already done) and **reuse** it; also add a tiny TTL (e.g., 30 s) to avoid hammering the controller if the same doc IDs appear across batches. |
| 3 | `contextual_retrieval.py:254‑260` – `queue_chunk_for_reembedding` | The function tries several endpoints (`/pipeline/.../embeddings/invalidate`, `/knowledge/embeddings/invalidate`). If **none** are available it simply logs a debug message and returns `True`. However, the **caller** (`update_chunk_content`) already set `invalidate_embedding=True`. If the endpoint is missing, the embedding is **not** actually deleted, leading to stale embeddings that no longer match the updated chunk text. | Down‑stream retrieval may use an outdated vector, causing missed matches. | Ensure that **at least one** endpoint is guaranteed to exist (e.g., the blueprint must implement `/knowledge/embeddings/invalidate`). If not, raise an explicit error during startup rather than silently succeeding. |
| 4 | `contextual_retrieval.py:274‑284` – `update_chunk_content` fallback `_fallback_update_chunk` | The fallback uses a **POST** to `/knowledge/chunks/update` with a JSON body that does **not** include the `chunk_id` as a top‑level key (it expects the server to read it from the body). If the server expects `chunk_id` in a different field (e.g., `id`), the update will silently fail. Moreover, the fallback **does not** guarantee atomicity: if the DB update succeeds but the embedding deletion fails, the chunk stays embedded with old vectors. | Partial updates can cause **data inconsistency** (new context but old embedding). | Make the fallback **explicit** about the expected payload shape, and add a **transaction** (or at least a retry) that updates the chunk and deletes the embedding in a single DB transaction. |
| 5 | `contextual_retrieval.py:311` – `if content.startswith(CONTEXT_PREFIX_MARKER):` | The marker check is performed **after** the chunk has already been fetched from the DB. If a previous run partially succeeded (e.g., the marker was added but the DB transaction rolled back), the chunk may still be considered “needs context” and be processed again, leading to **duplicate context prefixes** (multiple `[CTX]` markers). | Duplicate markers inflate the chunk size and can eventually exceed token limits. | Store a **dedicated column** (`has_context`) in the DB or use a transaction that writes the marker *and* commits before returning, ensuring idempotency. |

---

## 4️⃣ REST‑API Design (Blueprint)  

| # | Location (file:line) | Issue | Why it matters | Fix |
|---|----------------------|-------|----------------|-----|
| 1 | `contextual_retrieval_blueprint.py:46` – `@contextual_retrieval_bp.route('/start', methods=['POST'])` | No **authentication** or **authorization** check. Any fleet worker (or an external attacker who discovers the URL) can start a job, potentially exhausting CPU/GPU resources on the controller. | Resource exhaustion → denial‑of‑service. | Add a token‑based check (e.g., JWT) or require a secret header (`X-Controller-Key`). |
| 2 | `contextual_retrieval_blueprint.py:71` – `include_db = request.args.get('include_db_stats', 'true').lower() == 'true'` | The default is **`'true'`** (string) but the code treats any non‑`'true'` as false. If a client sends `include_db_stats=0` or `include_db_stats=False` (boolean) the default fallback will be **`'true'`** because the comparison is case‑sensitive and only matches the exact string `'true'`. This can leak DB stats unintentionally. | Information leakage. | Normalize input: `include_db = request.args.get('include_db_stats', '').lower() in ('1','true','yes','yes')`. |
| 3 | `contextual_retrieval_blueprint.py:96` – `if _active_job and _active_job.get('status') == 'running':` | The check only looks at `'running'`. If a job was previously **stopped** but the `_active_job` dict was never cleared, a subsequent `start` call will see a stale dict and refuse to start a new job, even though the previous job is idle. | Stalls the pipeline indefinitely. | Reset `_active_job = None` after a job finishes or is stopped, or store a separate `job_id` and allow a new job with a fresh ID. |
| 4 | `contextual_retrieval_blueprint.py:119‑124` – `GET /knowledge/document/<doc_id>` returns **only the first 500 characters** of the content (`LEFT(d.content, 500) AS excerpt`). If a document’s title is long, it is returned unchanged, but the excerpt may be **truncated mid‑word**, causing the LLM to receive an incomplete context. | The LLM may generate a context that references “the …” without a clear subject, leading to low‑quality prefixes. | Return the **full** excerpt (or at least up to a safe token limit) and ensure it ends at a sentence boundary. |
| 5 | `contextual_retrieval_blueprint.py:158‑166` – `POST /knowledge/documents/batch` does **not** validate that `document_ids` are **integers**. If a client sends `["abc", 12]` the DB query will raise a PostgreSQL error (`invalid input syntax for integer`). The endpoint returns a 500 error, but the client gets no helpful message. | Bad client input can crash the controller. | Validate with `if not all(isinstance(i, int) for i in doc_ids): return jsonify({'error': 'document_ids must be integers'}), 400`. |
| 6 | `contextual_retrieval_blueprint.py:1
