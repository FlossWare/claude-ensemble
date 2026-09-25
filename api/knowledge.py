"""Knowledge API Blueprint - Hybrid search, chunking, embedding, title extraction"""

import json
import logging
from flask import Blueprint, request, jsonify
import redis as redis_lib
import requests as http_requests

logger = logging.getLogger(__name__)
knowledge_bp = Blueprint("knowledge", __name__)

_redis_pool = None

def _get_redis():
    global _redis_pool
    if _redis_pool is None:
        import os
        _redis_pool = redis_lib.ConnectionPool(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=0, decode_responses=True, max_connections=20,
            socket_connect_timeout=5, socket_timeout=10)
    return redis_lib.Redis(connection_pool=_redis_pool)


EMBED_ENDPOINTS = ["http://server-03:5001/embed", "http://localhost:5000/learning/embeddings/generate", "http://localhost:5001/embed"]
RRF_K = 60
EMBED_DIM = 1024
EMBED_MODEL = "bge-base-en-v1.5"

RERANK_PROVIDERS = [
    {
        "name": "cohere",
        "url": "https://api.cohere.com/v2/rerank",
        "model": "rerank-v3.5",
        "key_env": "PERSONAL_COHERE_API_KEY",
        "auth_prefix": "Bearer ",
        "top_n_field": "top_n",
        "results_key": "results",
    },
    {
        "name": "voyage",
        "url": "https://api.voyageai.com/v1/rerank",
        "model": "rerank-2.5",
        "key_env": "PERSONAL_VOYAGEAI_API_KEY",
        "auth_prefix": "Bearer ",
        "top_n_field": "top_k",
        "results_key": "data",
    },
    {
        "name": "openrouter",
        "url": "https://openrouter.ai/api/v1/rerank",
        "model": "nvidia/llama-nemotron-rerank-vl-1b-v2:free",
        "key_env": "PERSONAL_OPENROUTER_API_KEY",
        "auth_prefix": "Bearer ",
        "top_n_field": "top_n",
        "results_key": "results",
    },
    {
        "name": "jina",
        "url": "https://api.jina.ai/v1/rerank",
        "model": "jina-reranker-v2-base-multilingual",
        "key_env": "PERSONAL_JINA_API_KEY",
        "auth_prefix": "Bearer ",
        "top_n_field": "top_n",
        "results_key": "results",
    },
]

HUGGINGFACE_RERANKER = {
    "name": "huggingface",
    "url": "https://router.huggingface.co/hf-inference/models/BAAI/bge-reranker-v2-m3",
    "key_env": "PERSONAL_HUGGINGFACE_API_KEY",
}

_secret_cache = {}
_SECRET_TTL = 3600

def _get_secret(key_name):
    """Get API key from environment or secrets API (cached with 1h TTL)."""
    import os, time
    val = os.environ.get(key_name)
    if val:
        return val
    cached = _secret_cache.get(key_name)
    if cached and (time.time() - cached[1]) < _SECRET_TTL:
        return cached[0]
    try:
        resp = http_requests.get(f"http://localhost:5000/secrets/{key_name}", timeout=5)
        if resp.ok:
            val = resp.json().get("value")
            if val:
                _secret_cache[key_name] = (val, time.time())
                return val
    except Exception:
        pass
    return cached[0] if cached else None


_MAX_RERANK_DOCS = 200

def _rerank_with_api(query, passages, limit):
    """Rerank passages using external API providers with cascading fallback.

    Tries batch rerankers (Cohere, Voyage, OpenRouter, Jina) first,
    then falls back to HuggingFace cross-encoder (pair-based scoring).
    Returns list of passage dicts with added rerank_score, sorted by relevance.
    Raises RuntimeError if all providers fail.
    """
    if not passages:
        return []
    passages = passages[:_MAX_RERANK_DOCS]
    documents = [p["content"] for p in passages]
    errors = []

    for provider in RERANK_PROVIDERS:
        api_key = _get_secret(provider["key_env"])
        if not api_key:
            errors.append(f"{provider['name']}: no API key")
            continue
        try:
            body = {
                "model": provider["model"],
                "query": query,
                "documents": documents,
                provider["top_n_field"]: limit,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": provider["auth_prefix"] + api_key,
            }
            resp = http_requests.post(provider["url"], json=body,
                                      headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            ranked_items = data.get(provider["results_key"], [])
            results = []
            for item in ranked_items:
                idx = item.get("index")
                if idx is None or not (0 <= idx < len(passages)):
                    logger.warning("Rerank provider %s returned invalid index %s (max %d)",
                                   provider["name"], idx, len(passages) - 1)
                    continue
                score = item.get("relevance_score", item.get("score", 0))
                entry = dict(passages[idx])
                entry["rerank_score"] = round(float(score), 4)
                entry["rerank_provider"] = provider["name"]
                results.append(entry)
            logger.info("Reranked %d→%d results via %s", len(passages), len(results), provider["name"])
            return results
        except Exception as e:
            errors.append(f"{provider['name']}: {e}")
            logger.debug("Rerank provider %s failed: %s", provider["name"], e)
            continue

    hf_key = _get_secret(HUGGINGFACE_RERANKER["key_env"])
    if hf_key:
        try:
            inputs = [{"text": query, "text_pair": doc} for doc in documents]
            resp = http_requests.post(
                HUGGINGFACE_RERANKER["url"],
                json={"inputs": inputs},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + hf_key,
                },
                timeout=60,
            )
            resp.raise_for_status()
            raw = resp.json()
            if isinstance(raw, list) and raw and isinstance(raw[0], list):
                scores_list = raw[0]
            elif isinstance(raw, list):
                scores_list = raw
            else:
                raise ValueError(f"Unexpected HuggingFace response format: {type(raw)}")
            scored_pairs = []
            for idx, item in enumerate(scores_list):
                if isinstance(item, dict):
                    score = item.get("score", 0)
                elif isinstance(item, (int, float)):
                    score = float(item)
                else:
                    continue
                if idx < len(passages):
                    scored_pairs.append((idx, score))
            scored_pairs.sort(key=lambda x: x[1], reverse=True)
            results = []
            for idx, score in scored_pairs[:limit]:
                entry = dict(passages[idx])
                entry["rerank_score"] = round(float(score), 4)
                entry["rerank_provider"] = "huggingface"
                results.append(entry)
            logger.info("Reranked %d→%d results via huggingface bge-reranker", len(passages), len(results))
            return results
        except Exception as e:
            errors.append(f"huggingface: {e}")
            logger.debug("HuggingFace reranker failed: %s", e)

    raise RuntimeError(f"All rerank providers failed: {'; '.join(errors)}")


def _get_query_embedding(query):
    """Generate query embedding with cascading fallback across providers."""
    for endpoint in EMBED_ENDPOINTS:
        try:
            resp = http_requests.post(endpoint, json={"texts": [query]}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            # Handle both response formats:
            # /embed returns {"embeddings": [[...]]}
            # /learning/embeddings/generate returns {"embeddings": [[...]]}
            embeddings = data.get("embeddings", [])
            if embeddings and isinstance(embeddings[0], list):
                return embeddings[0]
            return embeddings
        except Exception as e:
            logger.debug("Embedding endpoint %s failed: %s", endpoint, e)
            continue
    raise RuntimeError("All embedding services unavailable")


def _vector_search(cur, vec_str, category, limit):
    sql = """
        SELECT c.id, c.content, c.chunk_index,
               d.title, d.url, d.category, d.id as doc_id,
               (1 - (e.embedding <=> %s::vector))::float as score
        FROM knowledge.embeddings e
        JOIN knowledge.chunks c ON c.id = e.chunk_id
        JOIN knowledge.documents d ON d.id = c.document_id
    """
    params = [vec_str]
    if category:
        sql += " WHERE d.category = %s"
        params.append(category)
    if category:
        sql += " AND e.embedding IS NOT NULL"
    else:
        sql += " WHERE e.embedding IS NOT NULL"
    sql += " ORDER BY e.embedding <=> %s::vector LIMIT %s"
    params.extend([vec_str, limit])
    cur.execute(sql, params)
    return cur.fetchall()


def _fulltext_search(cur, query, category, limit):
    sql = """
        SELECT c.id, c.content, c.chunk_index,
               d.title, d.url, d.category, d.id as doc_id,
               ts_rank_cd(c.tsv, plainto_tsquery('english', %s))::float as score
        FROM knowledge.chunks c
        JOIN knowledge.documents d ON d.id = c.document_id
        WHERE c.tsv @@ plainto_tsquery('english', %s)
    """
    params = [query, query]
    if category:
        sql += " AND d.category = %s"
        params.append(category)
    sql += " ORDER BY score DESC LIMIT %s"
    params.append(limit)
    cur.execute(sql, params)
    return cur.fetchall()


def _rrf_fusion(vector_results, text_results, limit):
    scores = {}
    items = {}
    for rank, row in enumerate(vector_results):
        cid = row[0]
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
        items[cid] = row
    for rank, row in enumerate(text_results):
        cid = row[0]
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
        if cid not in items:
            items[cid] = row
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [(items[cid], rrf_score) for cid, rrf_score in ranked]


@knowledge_bp.route("/search", methods=["GET", "POST"])
def semantic_search():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        query = data.get("query", "")
        limit = int(data.get("limit", 10))
        category = data.get("category")
        min_score = float(data.get("min_score", 0.0))
        mode = data.get("mode", "hybrid")
        rerank = data.get("rerank", False)
    else:
        query = request.args.get("q", "")
        limit = int(request.args.get("limit", 10))
        category = request.args.get("category")
        min_score = float(request.args.get("min_score", 0.0))
        mode = request.args.get("mode", "hybrid")
        rerank = request.args.get("rerank", "false").lower() == "true"

    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        from app.shared.db import get_cursor
        fetch_limit = limit * 5 if rerank else (limit * 3 if mode == "hybrid" else limit)
        results = []
        search_mode_used = mode

        pre_embedding = data.get("query_embedding") if data else None

        with get_cursor(dict_cursor=False) as cur:
            if mode in ("vector", "hybrid"):
                if pre_embedding and isinstance(pre_embedding, list):
                    emb_list = pre_embedding
                else:
                    emb_list = _get_query_embedding(query)
                vec_str = "[" + ",".join(str(v) for v in emb_list) + "]"
                vector_rows = _vector_search(cur, vec_str, category, fetch_limit)
            else:
                vector_rows = []

            if mode in ("text", "hybrid"):
                text_rows = _fulltext_search(cur, query, category, fetch_limit)
            else:
                text_rows = []

        if mode == "hybrid" and vector_rows and text_rows:
            fused = _rrf_fusion(vector_rows, text_rows, fetch_limit)
            for (row, rrf_score) in fused:
                cid, content, chunk_idx, title, url, cat, doc_id, raw_score = row
                results.append({
                    "chunk_id": cid, "content": content[:500],
                    "chunk_index": chunk_idx, "title": title,
                    "url": url, "category": cat, "doc_id": doc_id,
                    "similarity": round(float(raw_score or 0), 4),
                    "rrf_score": round(float(rrf_score or 0), 6),
                })
        elif mode == "hybrid" and vector_rows:
            search_mode_used = "vector_only"
            for row in vector_rows:
                cid, content, chunk_idx, title, url, cat, doc_id, score = row
                results.append({
                    "chunk_id": cid, "content": content[:500],
                    "chunk_index": chunk_idx, "title": title,
                    "url": url, "category": cat, "doc_id": doc_id,
                    "similarity": round(float(score), 4),
                })
        else:
            rows = vector_rows or text_rows
            for row in rows:
                cid, content, chunk_idx, title, url, cat, doc_id, score = row
                results.append({
                    "chunk_id": cid, "content": content[:500],
                    "chunk_index": chunk_idx, "title": title,
                    "url": url, "category": cat, "doc_id": doc_id,
                    "similarity": round(float(score), 4),
                })

        if min_score > 0 and not rerank and results:
            # Always filter on similarity (cosine), not rrf_score
            # RRF scores are on a different scale (~0.016) vs cosine (~0.0-1.0)
            results = [r for r in results if r.get("similarity", 0) >= min_score]

        if rerank and results:
            try:
                passages = [{"content": r["content"], "chunk_id": r["chunk_id"],
                            "title": r.get("title"), "url": r.get("url"),
                            "category": r.get("category"), "doc_id": r.get("doc_id"),
                            "chunk_index": r.get("chunk_index"),
                            "similarity": r.get("similarity", 0),
                            "rrf_score": r.get("rrf_score", 0)} for r in results]
                reranked = _rerank_with_api(query, passages, limit)
                results = [{
                    "chunk_id": r["chunk_id"], "content": r["content"][:500],
                    "chunk_index": r.get("chunk_index"),
                    "title": r.get("title"), "url": r.get("url"),
                    "category": r.get("category"), "doc_id": r.get("doc_id"),
                    "similarity": r.get("similarity", 0),
                    "rerank_score": r.get("rerank_score", 0),
                    "rerank_provider": r.get("rerank_provider"),
                } for r in reranked[:limit]]
                search_mode_used += "+rerank"
            except Exception as e:
                logger.warning("Reranking failed: %s", e)
                results = results[:limit]
        else:
            results = results[:limit]

        return jsonify({
            "query": query, "count": len(results),
            "mode": search_mode_used, "results": results
        })
    except Exception as e:
        logger.exception("Knowledge search error")
        return jsonify({"error": str(e)}), 500


# --- Embedding endpoints ---

@knowledge_bp.route("/embeddings/pending", methods=["GET"])
def get_pending_embeddings():
    """Get chunks that need embedding"""
    limit = int(request.args.get("limit", 100))
    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("""
                SELECT c.id, c.content
                FROM knowledge.chunks c
                WHERE NOT EXISTS (SELECT 1 FROM knowledge.embeddings e WHERE e.chunk_id = c.id)
                ORDER BY c.id
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
        return jsonify({
            "count": len(rows),
            "items": [{"chunk_id": r[0], "content": r[1]} for r in rows]
        })
    except Exception as e:
        logger.exception("Embeddings pending error")
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/embeddings/store", methods=["POST"])
def store_embeddings():
    """Store embeddings for chunks"""
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not items:
        return jsonify({"error": "Missing items"}), 400
    try:
        from app.shared.db import get_cursor
        stored = 0
        with get_cursor(dict_cursor=False) as cur:
            for item in items:
                chunk_id = item["chunk_id"]
                embedding = item["embedding"]
                vec_str = "[" + ",".join(str(float(v)) for v in embedding) + "]"
                cur.execute("""
                    INSERT INTO knowledge.embeddings (chunk_id, embedding, model, provider)
                    VALUES (%s, %s::vector, %s, %s)
                    ON CONFLICT (chunk_id) DO NOTHING
                """, (chunk_id, vec_str, EMBED_MODEL, "local-cpu"))
                stored += 1
        return jsonify({"stored": stored})
    except Exception as e:
        logger.exception("Store embeddings error")
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/embeddings/count", methods=["GET"])
def embeddings_count():
    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("SELECT COUNT(*) FROM knowledge.embeddings")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge.chunks c WHERE NOT EXISTS (SELECT 1 FROM knowledge.embeddings e WHERE e.chunk_id = c.id)")
            pending = cur.fetchone()[0]
        return jsonify({"total": total, "pending": pending})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Direct Answer + Caching ---

_CACHE_TTL = 3600  # 1 hour
_CACHE_PREFIX = "ka:"  # knowledge answer cache

def _cache_key(query):
    """Deterministic cache key from normalized query."""
    import hashlib
    normalized = query.strip().lower()
    h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return _CACHE_PREFIX + h


@knowledge_bp.route("/direct-answer", methods=["GET", "POST"])
def direct_answer():
    """Direct-answer endpoint: returns high-confidence knowledge base matches.

    If a cached answer exists in Redis, returns it instantly (no DB query).
    Otherwise searches the knowledge base and caches high-confidence results.

    Returns:
      - answer: the content (if confidence >= threshold)
      - confidence: "high" (>=0.85), "medium" (>=0.65), or "low"
      - cached: true if served from Redis cache
      - results: array of matching chunks with scores
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        query = data.get("query", data.get("q", ""))
        threshold = float(data.get("threshold", 0.65))
        limit = int(data.get("limit", 3))
        category = data.get("category")
        skip_cache = data.get("skip_cache", False)
    else:
        query = request.args.get("q", request.args.get("query", ""))
        threshold = float(request.args.get("threshold", "0.65"))
        limit = int(request.args.get("limit", "3"))
        category = request.args.get("category")
        skip_cache = request.args.get("skip_cache", "false").lower() == "true"

    if not query or len(query.strip()) < 3:
        return jsonify({"error": "Query too short"}), 400

    # Check Redis cache first
    if not skip_cache:
        try:
            r = _get_redis()
            cached = r.get(_cache_key(query))
            if cached:
                result = json.loads(cached)
                result["cached"] = True
                return jsonify(result)
        except Exception as e:
            logger.debug("Cache read failed: %s", e)

    # Search the knowledge base
    try:
        from app.shared.db import get_cursor
        fetch_limit = limit * 5

        # Direct-answer uses text search only for speed (no embedding generation)
        # The full /knowledge/search endpoint handles vector+hybrid when needed
        with get_cursor(dict_cursor=False) as cur:
            text_rows = _fulltext_search(cur, query, category, fetch_limit)
        vector_rows = []

        # Fuse results
        if vector_rows and text_rows:
            fused = _rrf_fusion(vector_rows, text_rows, limit)
            results = []
            for (row, rrf_score) in fused:
                cid, content, chunk_idx, title, url, cat, doc_id, raw_score = row
                results.append({
                    "content": content[:800],
                    "title": title, "url": url, "category": cat,
                    "similarity": round(float(raw_score or 0), 4),
                })
        else:
            rows = vector_rows or text_rows
            results = []
            for row in rows[:limit]:
                cid, content, chunk_idx, title, url, cat, doc_id, score = row
                results.append({
                    "content": content[:800],
                    "title": title, "url": url, "category": cat,
                    "similarity": round(float(score), 4),
                })

        if not results:
            return jsonify({
                "query": query, "confidence": "none",
                "answer": None, "results": [], "cached": False
            })

        top_score = results[0].get("similarity", 0)

        # Scores can be cosine similarity (0-1) or ts_rank/rrf (0-10+)
        # Normalize: if score > 1.0, it's ts_rank — map to 0-1 range
        if top_score > 1.0:
            normalized = min(top_score / 10.0, 1.0)
        else:
            normalized = top_score

        if normalized >= 0.55:
            confidence = "high"
        elif normalized >= 0.35:
            confidence = "medium"
        else:
            confidence = "low"

        meets_threshold = normalized >= threshold

        response = {
            "query": query,
            "confidence": confidence,
            "top_score": round(top_score, 4),
            "normalized_score": round(normalized, 4),
            "answer": results[0]["content"] if meets_threshold else None,
            "answer_title": results[0].get("title") if meets_threshold else None,
            "answer_url": results[0].get("url") if meets_threshold else None,
            "answer_category": results[0].get("category") if meets_threshold else None,
            "results": results[:limit],
            "cached": False,
        }

        # Cache if confidence is medium or high
        if confidence in ("high", "medium"):
            try:
                r = _get_redis()
                r.setex(_cache_key(query), _CACHE_TTL, json.dumps(response))
            except Exception as e:
                logger.debug("Cache write failed: %s", e)

        return jsonify(response)

    except Exception as e:
        logger.exception("Direct answer error")
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/cache/stats", methods=["GET"])
def cache_stats():
    """Show knowledge answer cache statistics."""
    try:
        r = _get_redis()
        keys = r.keys(_CACHE_PREFIX + "*")
        total_keys = len(keys)
        sample_ttls = []
        for k in keys[:10]:
            ttl = r.ttl(k)
            sample_ttls.append(ttl)
        return jsonify({
            "cached_answers": total_keys,
            "cache_prefix": _CACHE_PREFIX,
            "ttl_seconds": _CACHE_TTL,
            "sample_ttls": sample_ttls,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/cache/clear", methods=["POST"])
def cache_clear():
    """Clear all cached knowledge answers."""
    try:
        r = _get_redis()
        keys = r.keys(_CACHE_PREFIX + "*")
        if keys:
            r.delete(*keys)
        return jsonify({"cleared": len(keys)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/chunks/batch-embed", methods=["POST"])
def batch_embed_chunks():
    """Get chunks needing embedding — format compatible with multi-provider-embedder.
    Supports cursor pagination via min_id for bulk loading."""
    data = request.get_json(silent=True) or {}
    limit = int(data.get("batch_size", data.get("limit", 100)))
    min_id = int(data.get("min_id", 0))
    skip_embed_check = data.get("skip_embed_check", False)
    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            if skip_embed_check:
                cur.execute("""
                    SELECT c.id, c.content
                    FROM knowledge.chunks c
                    WHERE c.id > %s
                      AND c.content IS NOT NULL AND length(c.content) > 10
                    ORDER BY c.id
                    LIMIT %s
                """, (min_id, limit))
            else:
                cur.execute("""
                    SELECT c.id, c.content
                    FROM knowledge.chunks c
                    WHERE c.id > %s
                      AND NOT EXISTS (SELECT 1 FROM knowledge.embeddings e WHERE e.chunk_id = c.id)
                      AND c.content IS NOT NULL AND length(c.content) > 10
                    ORDER BY c.id
                    LIMIT %s
                """, (min_id, limit))
            rows = cur.fetchall()
        return jsonify({
            "fetched": len(rows),
            "chunks": [{"id": r[0], "content": r[1][:2000]} for r in rows]
        })
    except Exception as e:
        logger.exception("Batch embed chunks error")
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/chunks/store-embeddings", methods=["POST"])
def store_chunk_embeddings():
    """Store embeddings — format compatible with multi-provider-embedder."""
    data = request.get_json(silent=True) or {}
    items = data.get("embeddings", [])
    if not items:
        return jsonify({"error": "Missing embeddings"}), 400
    try:
        from app.shared.db import get_cursor
        stored = 0
        with get_cursor(dict_cursor=False) as cur:
            for item in items:
                chunk_id = item["id"]
                embedding = item["embedding"]
                vec_str = "[" + ",".join(str(float(v)) for v in embedding) + "]"
                cur.execute("""
                    INSERT INTO knowledge.embeddings (chunk_id, embedding, model, provider)
                    VALUES (%s, %s::vector, %s, %s)
                    ON CONFLICT (chunk_id) DO NOTHING
                """, (chunk_id, vec_str, EMBED_MODEL, item.get("provider", "multi-api")))
                stored += 1
        return jsonify({"updated": stored})
    except Exception as e:
        logger.exception("Store chunk embeddings error")
        return jsonify({"error": str(e)}), 500


# --- Chunking endpoints ---

@knowledge_bp.route("/chunks/pending", methods=["GET"])
def get_pending_chunks():
    limit = int(request.args.get("limit", 10))
    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("""
                SELECT d.id, d.content, d.category, d.url
                FROM knowledge.documents d
                WHERE d.content IS NOT NULL AND d.content != ''
                  AND NOT EXISTS (SELECT 1 FROM knowledge.chunks c WHERE c.document_id = d.id)
                ORDER BY d.id LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
        return jsonify({
            "count": len(rows),
            "items": [{"id": r[0], "content": r[1], "category": r[2], "url": r[3]} for r in rows]
        })
    except Exception as e:
        logger.exception("Chunks pending error")
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/chunks/store", methods=["POST"])
def store_chunks():
    data = request.get_json(silent=True) or {}
    document_id = data.get("document_id")
    chunks = data.get("chunks", [])
    if not document_id or not chunks:
        return jsonify({"error": "Missing document_id or chunks"}), 400
    try:
        from app.shared.db import get_cursor
        chunk_ids = []
        with get_cursor(dict_cursor=False) as cur:
            for chunk in chunks:
                cur.execute("""
                    INSERT INTO knowledge.chunks (document_id, content, chunk_index, token_count, content_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (document_id, chunk_index) DO NOTHING
                    RETURNING id
                """, (document_id, chunk["content"], chunk["index"],
                      chunk.get("token_count", 0), chunk.get("content_hash", "")))
                row = cur.fetchone()
                if row:
                    chunk_ids.append(row[0])

            embeddings = data.get("embeddings", [])
            stored_emb = 0
            for cid, emb in zip(chunk_ids, embeddings):
                if emb:
                    vec_str = "[" + ",".join(str(float(v)) for v in emb) + "]"
                    cur.execute("""
                        INSERT INTO knowledge.embeddings (chunk_id, embedding, model, provider)
                        VALUES (%s, %s::vector, %s, %s)
                        ON CONFLICT (chunk_id) DO NOTHING
                    """, (cid, vec_str, EMBED_MODEL, "local-cpu"))
                    stored_emb += 1
        return jsonify({"stored_chunks": len(chunk_ids), "stored_embeddings": stored_emb})
    except Exception as e:
        logger.exception("Store chunks error")
        return jsonify({"error": str(e)}), 500


# --- Title endpoints ---

@knowledge_bp.route("/titles/pending", methods=["GET"])
def get_pending_titles():
    """Get pending titles from Redis queue."""
    limit = int(request.args.get("limit", 50))
    worker_id = request.args.get("worker_id", "unknown")
    try:
        from datetime import datetime, timezone
        r = _get_redis()
        now_iso = datetime.now(timezone.utc).isoformat()
        items_raw = r.zpopmin("pipeline:title:pending", limit)
        if not items_raw:
            return jsonify({"count": 0, "items": []})
        results = []
        for member, score in items_raw:
            item_key = f"pipeline:item:{member}"
            item_data = r.hgetall(item_key)
            if not item_data:
                continue
            data = json.loads(item_data.get("data", "{}"))
            r.hset("pipeline:title:processing", member, now_iso)
            r.hset(item_key, "worker_id", worker_id)
            r.hset(item_key, "status", "processing")
            results.append({
                "queue_id": member,
                "document_id": data.get("document_id"),
                "url": data.get("url", "")
            })
        return jsonify({"count": len(results), "items": results})
    except Exception as e:
        logger.exception("Title pending error (Redis)")
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/titles/update", methods=["POST"])
def update_title():
    """Update title and mark Redis queue item complete."""
    data = request.get_json(silent=True) or {}
    queue_id = data.get("queue_id")
    document_id = data.get("document_id")
    title = data.get("title")
    error = data.get("error")
    if not queue_id:
        return jsonify({"error": "Missing queue_id"}), 400
    try:
        from datetime import datetime, timezone
        from app.shared.db import get_cursor
        if title:
            with get_cursor(dict_cursor=False) as cur:
                cur.execute("UPDATE knowledge.documents SET title = %s WHERE id = %s",
                           (title[:500], document_id))
        r = _get_redis()
        now_iso = datetime.now(timezone.utc).isoformat()
        item_key = f"pipeline:item:{queue_id}"
        if title:
            r.hdel("pipeline:title:processing", queue_id)
            r.incr("pipeline:title:completed_count")
            r.sadd("pipeline:title:completed_set", queue_id)
            r.hset(item_key, "status", "completed")
            r.hset(item_key, "completed_at", now_iso)
            r.expire(item_key, 604800)
        else:
            r.hdel("pipeline:title:processing", queue_id)
            r.incr("pipeline:title:failed_count")
            r.hset(item_key, "status", "failed")
            r.hset(item_key, "error", str(error)[:500] if error else "no title found")
            r.hset(item_key, "completed_at", now_iso)
            r.expire(item_key, 86400)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/titles/status", methods=["GET"])
def title_extraction_status():
    """Title queue status from Redis."""
    try:
        r = _get_redis()
        pending = r.zcard("pipeline:title:pending") or 0
        processing = r.hlen("pipeline:title:processing") or 0
        completed = int(r.get("pipeline:title:completed_count") or 0)
        failed = int(r.get("pipeline:title:failed_count") or 0)
        return jsonify({
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/stats", methods=["GET"])
def knowledge_stats():
    try:
        from app.shared.db import get_cursor
        stats = {}
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("SELECT COUNT(*) FROM knowledge.documents")
            stats["documents"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge.chunks")
            stats["chunks"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge.embeddings")
            stats["embeddings"] = cur.fetchone()[0]
            stats["embed_model"] = EMBED_MODEL
            stats["embed_dim"] = EMBED_DIM
            cur.execute("SELECT COUNT(*) FROM knowledge.documents d WHERE NOT EXISTS (SELECT 1 FROM knowledge.chunks c WHERE c.document_id = d.id) AND d.content IS NOT NULL AND d.content != ''")
            stats["unchunked_docs"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge.chunks c WHERE NOT EXISTS (SELECT 1 FROM knowledge.embeddings e WHERE e.chunk_id = c.id)")
            stats["unembedded_chunks"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM knowledge.chunks WHERE tsv IS NOT NULL")
            stats["fulltext_indexed"] = cur.fetchone()[0]
            cur.execute("SELECT category, COUNT(*) FROM knowledge.documents GROUP BY category ORDER BY 2 DESC LIMIT 20")
            stats["categories"] = [{"category": r[0], "count": r[1]} for r in cur.fetchall()]
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Queue-based embedding endpoints ---

@knowledge_bp.route("/embeddings/claim", methods=["GET"])
def claim_embedding_batch():
    """Claim a batch of chunks for embedding via Redis queue."""
    limit = int(request.args.get("limit", 500))
    worker_id = request.args.get("worker_id", "unknown")
    try:
        from datetime import datetime, timezone
        r = _get_redis()
        now_iso = datetime.now(timezone.utc).isoformat()
        items_raw = r.zpopmin("pipeline:embedding:pending", limit)
        if not items_raw:
            return jsonify({"count": 0, "items": []})
        chunk_ids = []
        item_ids = []
        for member, score in items_raw:
            item_key = f"pipeline:item:{member}"
            item_data = r.hgetall(item_key)
            if not item_data:
                continue
            data = json.loads(item_data.get("data", "{}"))
            cid = data.get("chunk_id")
            if cid:
                chunk_ids.append(cid)
                item_ids.append(member)
                r.hset("pipeline:embedding:processing", member, now_iso)
                r.hset(item_key, "worker_id", worker_id)
                r.hset(item_key, "status", "processing")
                r.hset(item_key, "started_at", now_iso)
        if not chunk_ids:
            return jsonify({"count": 0, "items": []})
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("SELECT id, content FROM knowledge.chunks WHERE id = ANY(%s)", (chunk_ids,))
            text_map = {row[0]: row[1] for row in cur.fetchall()}
        results = []
        for cid, iid in zip(chunk_ids, item_ids):
            if cid in text_map:
                results.append({"chunk_id": cid, "content": text_map[cid], "_item_id": iid})
        return jsonify({"count": len(results), "items": results})
    except Exception as e:
        logger.exception("Claim error (Redis)")
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/embeddings/complete", methods=["POST"])
def complete_embedding_batch():
    """Store embeddings and mark Redis queue items complete."""
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not items:
        return jsonify({"error": "Missing items"}), 400
    try:
        from app.shared.db import get_cursor
        from psycopg2.extras import execute_values
        from datetime import datetime, timezone
        with get_cursor(dict_cursor=False) as cur:
            values = []
            for item in items:
                cid = item["chunk_id"]
                emb = item["embedding"]
                vec_str = "[" + ",".join(str(float(v)) for v in emb) + "]"
                values.append((cid, vec_str, EMBED_MODEL, "local-cpu"))
            execute_values(cur, """
                INSERT INTO knowledge.embeddings (chunk_id, embedding, model, provider)
                VALUES %s ON CONFLICT (chunk_id) DO NOTHING
            """, values, template="(%s, %s::vector, %s, %s)")
        r = _get_redis()
        now_iso = datetime.now(timezone.utc).isoformat()
        completed = 0
        for item in items:
            item_id = item.get("_item_id")
            if item_id:
                r.hdel("pipeline:embedding:processing", item_id)
                r.incr("pipeline:embedding:completed_count")
                r.sadd("pipeline:embedding:completed_set", item_id)
                item_key = f"pipeline:item:{item_id}"
                r.hset(item_key, "status", "completed")
                r.hset(item_key, "completed_at", now_iso)
                r.expire(item_key, 604800)
                completed += 1
        return jsonify({"stored": len(items), "queue_completed": completed})
    except Exception as e:
        logger.exception("Complete error (Redis)")
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/embeddings/status", methods=["GET"])
def embedding_queue_status():
    """Embedding queue status from Redis."""
    try:
        r = _get_redis()
        pending = r.zcard("pipeline:embedding:pending") or 0
        processing = r.hlen("pipeline:embedding:processing") or 0
        completed = int(r.get("pipeline:embedding:completed_count") or 0)
        failed = int(r.get("pipeline:embedding:failed_count") or 0)
        return jsonify({
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/titles/reset-stale", methods=["POST"])
def reset_stale_titles():
    """Reset titles stuck in processing back to pending."""
    data = request.get_json(silent=True) or {}
    minutes = int(data.get("minutes", 1))
    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("""
                UPDATE queue.title_extract
                SET status = 'pending', worker_id = NULL, started_at = NULL
                WHERE status = 'processing'
                  AND (started_at IS NULL OR started_at < NOW() - make_interval(mins => %s))
                RETURNING id
            """, (minutes,))
            count = cur.rowcount
        return jsonify({"reset": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/embeddings/pending-chunks", methods=["GET"])
def get_pending_embedding_chunks():
    """Read-only dump of pending embedding chunk IDs for Redis migration."""
    limit = int(request.args.get("limit", 500))
    offset = int(request.args.get("offset", 0))
    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("""
                SELECT chunk_id FROM queue.embedding_v2
                WHERE status = 'pending'
                ORDER BY id
                LIMIT %s OFFSET %s
            """, (limit, offset))
            rows = cur.fetchall()
        return jsonify({"chunk_ids": [r[0] for r in rows], "count": len(rows)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/titles/pending-dump", methods=["GET"])
def dump_pending_titles():
    """Read-only dump of pending title items for Redis migration."""
    limit = int(request.args.get("limit", 500))
    offset = int(request.args.get("offset", 0))
    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("""
                SELECT id, document_id, url FROM queue.title_extract
                WHERE status = 'pending'
                ORDER BY id
                LIMIT %s OFFSET %s
            """, (limit, offset))
            rows = cur.fetchall()
        return jsonify({
            "items": [{"queue_id": r[0], "document_id": r[1], "url": r[2]} for r in rows],
            "count": len(rows)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
