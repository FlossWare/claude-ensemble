#!/usr/bin/env python3
"""Fleet multi-AI review of embedding changes via FreeModelRouter.

Uses the orchestrator's routing engine (FreeModelRouter) to fan out
code review to 3 diverse models, then meta-review to 3 different models.
Zero overlap between panels.
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, "/exports/claude-orchestrator/api")

from loom_ai.backends.free_model_router import FreeModelRouter
from loom_ai.models import ChatMessage

PG_DSN = "postgresql://redhat_orchestrator:rh-orch-2026-laptop02@localhost:5433/learning"

REVIEW_MODELS = [
    "gemini-2.5-pro",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

META_REVIEW_MODELS = [
    "gemini-3.7-flash",
    "openai/gpt-oss-20b:free",
    "cohere/north-mini-code:free",
]

CODE_TO_REVIEW = r"""
=== FILE 1: knowledge.py (embedding endpoint additions) ===

_router = None
_router_lock = None

def _get_router():
    global _router, _router_lock
    if _router is not None:
        return _router
    if _router_lock is None:
        import threading
        _router_lock = threading.Lock()
    with _router_lock:
        if _router is not None:
            return _router
        from loom_ai.backends.free_model_router import FreeModelRouter
        _router = FreeModelRouter(
            pg_dsn="postgresql://redhat_orchestrator:rh-orch-2026-laptop02@localhost:5432/learning",
        )
        return _router

@knowledge_bp.route("/embed", methods=["POST"])
def embed_texts():
    import asyncio
    data = request.get_json()
    if not data or "texts" not in data:
        return jsonify({"error": "texts array required"}), 400
    texts = data["texts"]
    if not texts:
        return jsonify({"embeddings": [], "count": 0})
    if len(texts) > 50:
        return jsonify({"error": "max 50 texts per request"}), 400
    model = data.get("model")
    dimensions = data.get("dimensions", 1024)
    try:
        router = _get_router()
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(
                router.embed(texts, model=model, dimensions=dimensions))
        finally:
            loop.close()
        return jsonify({
            "embeddings": [{"vector": r.vector, "model": r.model,
                            "provider": r.provider, "dimensions": r.dimensions} for r in results],
            "count": len(results),
        })
    except Exception as e:
        logger.error("Embed failed: %s", str(e)[:200])
        return jsonify({"error": str(e)[:200]}), 503

=== FILE 2: generic-worker.py (embed handler) ===

def handle_embed(api, item, worker_id):
    chunk_id = item.get('chunk_id') or item.get('id')
    content = item.get('content', '')
    if not content or not content.strip():
        return {'action': 'skip', 'reason': 'no content'}
    check_resp = http_post_retry(f'{api}/knowledge/chunks/check-embedded',
                                 {'ids': [chunk_id]})
    if str(chunk_id) in [str(i) for i in check_resp.get('embedded', [])]:
        return {'action': 'skip', 'reason': 'already embedded'}
    embed_resp = http_post_retry(f'{api}/knowledge/embed',
                                 {'texts': [content[:4000]]}, timeout=60)
    embeddings = embed_resp.get('embeddings', [])
    if not embeddings:
        return {'action': 'error', 'reason': 'no embedding returned'}
    emb = embeddings[0]
    store_resp = http_post_retry(f'{api}/knowledge/chunks/store-embeddings-direct', {
        'embeddings': [{'chunk_id': chunk_id, 'vector': emb['vector'],
                        'model': emb.get('model', 'unknown'), 'provider': emb.get('provider', 'api')}]
    })
    return {'action': 'embedded', 'model': emb.get('model'), 'stored': store_resp.get('stored', 0)}

HANDLERS = {
    'ingest': handle_ingest,
    'chunk': handle_chunk,
    'embed': handle_embed,
    'embed-store': handle_embed_store,
    'graph': handle_graph,
    'store': handle_store,
    'knowledge': handle_knowledge,
}

=== FILE 3: free_model_router.py (embedding additions to FreeModelRouter) ===

_EMBEDDING_MODELS: dict[str, list[str]] = {
    "nvidia": ["nvidia/nv-embedqa-e5-v5", "nvidia/nv-embed-v1", ...],
    "gemini": ["gemini-embedding-001"],
    "cohere": ["embed-english-v3.0"],
    "openrouter": ["nvidia/llama-nemotron-embed-vl-1b-v2:free", "nvidia/nemotron-3-embed-1b:free"],
    "deepinfra": ["BAAI/bge-large-en-v1.5"],
    "mistral": ["mistral-embed"],
    "voyage": ["voyage-3", "voyage-4-lite", "voyage-code-3"],
}

# In FreeModelRouter class:
async def embed(self, texts, *, model=None, dimensions=1024):
    if not self._initialized:
        await self.initialize()
    candidates = [e for e in self._embed_endpoints]
    if model:
        candidates = [e for e in candidates if model in e.model_id]
    if not candidates:
        raise RuntimeError("No embedding endpoints available")
    last_err = None
    for ep in candidates:
        t0 = time.monotonic()
        try:
            result = await self._embed_call(ep, texts, dimensions)
            self._record(ep, True, time.monotonic() - t0)
            return result
        except Exception as exc:
            self._record(ep, False, time.monotonic() - t0)
            last_err = exc
    raise RuntimeError(f"All embedding endpoints failed. Last: {last_err}")

=== FILE 4: pipeline.py (fetch-any endpoint) ===

FETCH_ANY_PRIORITY = ["embed-store", "store", "graph", "knowledge", "embed", "chunk", "ingest"]

@pipeline_bp.route("/queues/fetch-any", methods=["POST"])
def queue_fetch_any():
    data = request.get_json() or {}
    allowed = data.get("allowed_queues", ["*"])
    max_kb = data.get("max_payload_kb", 0)
    worker_id = data.get("worker_id", "unknown")
    count = min(data.get("count", 1), 20)
    if allowed == ["*"] or "*" in allowed:
        allowed = FETCH_ANY_PRIORITY
    else:
        allowed = [q for q in FETCH_ANY_PRIORITY if q in allowed]
    r = _get_redis()
    for queue_name in allowed:
        keys = QUEUE_KEYS.get(queue_name)
        if not keys:
            continue
        queue_len = r.llen(keys["queue"])
        if queue_len == 0:
            continue
        items = []
        skipped = []
        for _ in range(count + 10):
            raw = r.rpop(keys["queue"])
            if not raw:
                break
            item = json.loads(raw)
            if max_kb > 0:
                item_size = len(raw) / 1024
                if item_size > max_kb:
                    skipped.append(raw)
                    continue
            item["fetched_at"] = time.time()
            item["worker_id"] = worker_id
            r.hset(keys["processing"], item.get("id", str(time.time())), json.dumps(item))
            items.append(item)
            if len(items) >= count:
                break
        for s in skipped:
            r.lpush(keys["queue"], s)
        if items:
            return jsonify({"queue": queue_name, "items": items, "count": len(items),
                            "remaining": r.llen(keys["queue"])})
    return "", 204
"""

REVIEW_PROMPT = """You are a senior security engineer and code reviewer. Review the following production Python code for:

1. BUGS: Logic errors, race conditions, missing error handling, data corruption risks
2. SECURITY: SQL injection, credential exposure, DoS vectors, information disclosure
3. RELIABILITY: Resource leaks, crash paths, data loss scenarios
4. ARCHITECTURE: REST-only design violations, coupling, missing validations

Context: This is a distributed pipeline system where workers NEVER talk directly to databases.
Workers call REST API endpoints only. The API uses FreeModelRouter (multi-provider free-tier LLM router)
for embedding generation. All queue processing goes through a generic worker that asks for any work
from a priority-ordered fetch-any endpoint.

Code to review:

{code}

Return ONLY valid JSON (no markdown, no backticks):
{{"score": 0.0-1.0, "verdict": "APPROVE|NEEDS_FIX|REJECT", "critical": ["issue1", ...], "warnings": ["warn1", ...], "suggestions": ["sug1", ...], "summary": "one paragraph"}}"""

META_REVIEW_PROMPT = """You are an adversarial meta-reviewer. Your job is to validate or refute the findings of other code reviewers.

Original code under review:
{code}

Previous reviews from other models:
{reviews}

Your task:
1. Are the identified bugs REAL or false positives?
2. Did the reviewers MISS anything critical?
3. Are the severity ratings accurate?
4. Is the overall verdict justified?

IMPORTANT: Try to REFUTE findings. Only confirm what you can independently verify.

Return ONLY valid JSON (no markdown, no backticks):
{{"confirmed_issues": ["issue1", ...], "false_positives": ["fp1", ...], "missed_issues": ["missed1", ...], "overall_verdict": "APPROVE|NEEDS_FIX|REJECT", "confidence": 0.0-1.0, "summary": "one paragraph"}}"""


async def review_with_model(router, model, prompt):
    """Send review to a specific model via FreeModelRouter."""
    t0 = time.time()
    try:
        resp = await router.chat(
            [ChatMessage(role="user", content=prompt)],
            model=model,
            temperature=0.1,
            max_tokens=4096,
        )
        elapsed = time.time() - t0
        content = resp.content.strip()
        # Try to parse JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return {"model": resp.model or model, "provider": resp.provider,
                        "result": parsed, "elapsed": round(elapsed, 1)}
            except json.JSONDecodeError:
                return {"model": model, "error": "JSON parse failed", "raw": content[:1000],
                        "elapsed": round(elapsed, 1)}
        return {"model": model, "error": "No JSON in response", "raw": content[:1000],
                "elapsed": round(elapsed, 1)}
    except Exception as e:
        elapsed = time.time() - t0
        return {"model": model, "error": str(e)[:500], "elapsed": round(elapsed, 1)}


async def main():
    print("=" * 70)
    print("FLEET MULTI-AI CODE REVIEW via FreeModelRouter (Orchestrator)")
    print("=" * 70)

    router = FreeModelRouter(pg_dsn=PG_DSN)
    await router.initialize()
    models = await router.list_models()
    print(f"\nDiscovered {len(models)} free model endpoints")

    # === PHASE 1: REVIEW ===
    print(f"\n{'='*70}")
    print(f"PHASE 1: REVIEW ({len(REVIEW_MODELS)} models)")
    print(f"{'='*70}")
    for m in REVIEW_MODELS:
        print(f"  -> {m}")

    prompt = REVIEW_PROMPT.format(code=CODE_TO_REVIEW)
    review_tasks = [review_with_model(router, m, prompt) for m in REVIEW_MODELS]
    reviews = await asyncio.gather(*review_tasks)

    print(f"\n--- Review Results ---")
    for r in reviews:
        model = r.get("model", "unknown")
        if "result" in r:
            res = r["result"]
            print(f"\n[{model}] ({r['elapsed']}s)")
            print(f"  Score: {res.get('score', 'N/A')} | Verdict: {res.get('verdict', 'N/A')}")
            for c in res.get("critical", []):
                print(f"  CRITICAL: {c}")
            for w in res.get("warnings", []):
                print(f"  WARNING: {w}")
            for s in res.get("suggestions", []):
                print(f"  SUGGEST: {s}")
        else:
            print(f"\n[{model}] ERROR ({r['elapsed']}s): {r.get('error', 'unknown')}")
            if r.get("raw"):
                print(f"  Raw: {r['raw'][:300]}")

    # === PHASE 2: META-REVIEW ===
    print(f"\n{'='*70}")
    print(f"PHASE 2: META-REVIEW ({len(META_REVIEW_MODELS)} models, zero overlap)")
    print(f"{'='*70}")
    for m in META_REVIEW_MODELS:
        print(f"  -> {m}")

    reviews_text = json.dumps([r.get("result", r) for r in reviews], indent=2, default=str)
    meta_prompt = META_REVIEW_PROMPT.format(code=CODE_TO_REVIEW, reviews=reviews_text)
    meta_tasks = [review_with_model(router, m, meta_prompt) for m in META_REVIEW_MODELS]
    meta_reviews = await asyncio.gather(*meta_tasks)

    print(f"\n--- Meta-Review Results ---")
    for r in meta_reviews:
        model = r.get("model", "unknown")
        if "result" in r:
            res = r["result"]
            print(f"\n[{model}] ({r['elapsed']}s)")
            print(f"  Verdict: {res.get('overall_verdict', 'N/A')} | Confidence: {res.get('confidence', 'N/A')}")
            for c in res.get("confirmed_issues", []):
                print(f"  CONFIRMED: {c}")
            for fp in res.get("false_positives", []):
                print(f"  FALSE POS: {fp}")
            for m_issue in res.get("missed_issues", []):
                print(f"  MISSED: {m_issue}")
            print(f"  Summary: {res.get('summary', 'N/A')}")
        else:
            print(f"\n[{model}] ERROR ({r['elapsed']}s): {r.get('error', 'unknown')}")
            if r.get("raw"):
                print(f"  Raw: {r['raw'][:300]}")

    # === SUMMARY ===
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")

    review_verdicts = [r.get("result", {}).get("verdict", "ERROR") for r in reviews]
    meta_verdicts = [r.get("result", {}).get("overall_verdict", "ERROR") for r in meta_reviews]
    print(f"Review verdicts: {review_verdicts}")
    print(f"Meta-review verdicts: {meta_verdicts}")

    all_critical = []
    for r in reviews:
        all_critical.extend(r.get("result", {}).get("critical", []))
    for r in meta_reviews:
        all_critical.extend(r.get("result", {}).get("confirmed_issues", []))
        all_critical.extend(r.get("result", {}).get("missed_issues", []))

    if all_critical:
        print(f"\nAll critical issues ({len(all_critical)}):")
        for i, c in enumerate(all_critical, 1):
            print(f"  {i}. {c}")

    # Return structured result
    return {
        "reviews": reviews,
        "meta_reviews": meta_reviews,
        "review_verdicts": review_verdicts,
        "meta_verdicts": meta_verdicts,
        "critical_issues": all_critical,
    }


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\n{'='*70}")
    print(json.dumps({"verdict_summary": {
        "review": result["review_verdicts"],
        "meta_review": result["meta_verdicts"],
        "critical_count": len(result["critical_issues"]),
    }}, indent=2))
