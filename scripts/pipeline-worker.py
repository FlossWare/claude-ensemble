#!/usr/bin/env python3
"""
Pipeline queue worker — consumes from pipeline queues via REST API.

Handles:
  - embedding: fetch chunk content → generate embedding → store → complete
  - chunk: chunk content → store chunks → add to embedding queue → complete
  - store: store document content → complete with chain to chunk

All DB and queue access goes through the REST API at aio-01:5000.
Workers with sentence-transformers generate embeddings locally;
others fall back to the REST API embedding endpoint.

Usage:
  python3 pipeline-worker.py                     # all stages
  python3 pipeline-worker.py embedding           # embedding only
  python3 pipeline-worker.py chunk embedding      # chunk + embedding
"""
import hashlib
import json
import os
import socket
import sys
import time
from datetime import datetime

import requests

API_BASE = "http://aio-01:5000"
WORKER_ID = f"worker-{socket.gethostname()}"
BATCH_SIZE = 5
EMBED_BATCH = 50
IDLE_SLEEP = 3
MAX_IDLE_ROUNDS = 100
CHUNK_SIZE_CHARS = 4096
CHUNK_OVERLAP_CHARS = 1500

os.environ.setdefault('HF_HOME', os.path.expanduser('~/.cache/huggingface'))
os.environ.setdefault('SENTENCE_TRANSFORMERS_HOME',
                      os.path.expanduser('~/.cache/sentence_transformers'))
os.environ.setdefault('TRANSFORMERS_CACHE',
                      os.path.expanduser('~/.cache/huggingface/hub'))
os.environ.setdefault('XET_LOG_DIR', os.path.expanduser('~/.cache/xet_logs'))

_st_model = None
_has_local_embed = None


def _can_embed_locally():
    global _has_local_embed
    if _has_local_embed is None:
        try:
            from sentence_transformers import SentenceTransformer
            _has_local_embed = True
        except ImportError:
            _has_local_embed = False
    return _has_local_embed


def _get_local_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer('all-mpnet-base-v2')
    return _st_model


def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"  [{ts}] {msg}", flush=True)


def api_post(path, data, timeout=60):
    try:
        r = requests.post(f"{API_BASE}{path}",
                          json=data, timeout=timeout)
        return r.json()
    except Exception as e:
        log(f"API error {path}: {e}")
        return None


def db_query(sql, timeout=120):
    try:
        r = requests.post(f"{API_BASE}/storage/query",
                          json={"query": sql}, timeout=timeout)
        d = r.json()
        if d.get("success"):
            return d.get("results", [])
        else:
            log(f"DB error: {str(d.get('error',''))[:200]}")
            return None
    except Exception as e:
        log(f"DB request error: {e}")
        return None


def queue_fetch(queue_name, batch=1):
    result = api_post(f"/queue/fetch/{queue_name}",
                      {"batch": batch, "worker_id": WORKER_ID})
    if result and result.get("items"):
        return result["items"]
    return []


def queue_complete(item_id, chain=True, data=None, document_id=None,
                   chunk_ids=None):
    body = {
        "item_id": str(item_id),
        "worker_id": WORKER_ID,
        "chain": chain,
    }
    if data is not None:
        body["data"] = data
    if document_id is not None:
        body["document_id"] = str(document_id)
    if chunk_ids is not None:
        body["chunk_ids"] = chunk_ids
    return api_post("/queue/complete", body)


def queue_complete_batch(item_ids, chain=False):
    if not item_ids:
        return
    body = {
        "items": [{"item_id": str(iid)} for iid in item_ids],
        "worker_id": WORKER_ID,
        "chain": chain,
    }
    return api_post("/queue/complete", body)


def queue_fail(item_id, error_msg):
    return api_post("/queue/fail", {
        "item_id": str(item_id),
        "worker_id": WORKER_ID,
        "error": str(error_msg)[:500],
    })


_local_failed_permanently = False


def generate_embedding(text):
    global _local_failed_permanently
    text = text[:8000]

    if _can_embed_locally() and not _local_failed_permanently:
        try:
            model = _get_local_model()
            vec = model.encode([text])[0].tolist()
            return vec, "local"
        except Exception as e:
            log(f"Local embedding failed, switching to API: {e}")
            _local_failed_permanently = True

    result = api_post("/learning/embeddings/generate",
                      {"texts": [text]}, timeout=30)
    if result and result.get("embeddings"):
        return result["embeddings"][0], "api"
    return None, ""


def generate_embeddings_batch(texts):
    global _local_failed_permanently
    texts = [t[:8000] for t in texts]

    if _can_embed_locally() and not _local_failed_permanently:
        try:
            model = _get_local_model()
            vecs = model.encode(texts).tolist()
            return [(v, "local") for v in vecs]
        except Exception as e:
            log(f"Local batch embed failed, switching to API: {e}")
            _local_failed_permanently = True

    result = api_post("/learning/embeddings/generate",
                      {"texts": texts}, timeout=60)
    if result and result.get("embeddings"):
        return [(e, "api") for e in result["embeddings"]]
    return [(None, "")] * len(texts)


def escape_sql(s):
    if s is None:
        return "NULL"
    s = str(s)
    s = ''.join(c for c in s if c.isprintable() or c in '\n\r\t')
    return "'" + s.replace("\\", "\\\\").replace("'", "''")[:50000] + "'"


def chunk_text(text):
    if not text or len(text.strip()) < 50:
        return []

    step = max(CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS, 1)
    chunks = []
    seen = set()

    for i in range(0, len(text), step):
        chunk = text[i:i + CHUNK_SIZE_CHARS].strip()
        if not chunk or len(chunk) < 50:
            continue
        h = hashlib.sha256(chunk.encode('utf-8', errors='replace')).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        chunks.append({
            'content': chunk,
            'index': len(chunks),
            'token_count': max(1, len(chunk) // 4),
            'content_hash': h,
        })
    return chunks


def process_embedding_items(items):
    chunk_ids = []
    item_map = {}
    for item in items:
        data = item.get("data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}
        cid = data.get("chunk_id")
        if cid:
            chunk_ids.append(int(cid))
            item_map[int(cid)] = item

    if not chunk_ids:
        for item in items:
            queue_fail(item["id"], "No chunk_id in data")
        return 0

    id_list = ",".join(str(c) for c in chunk_ids)
    rows = db_query(
        f"SELECT c.id, c.content FROM knowledge.chunks c "
        f"WHERE c.id IN ({id_list}) "
        f"AND NOT EXISTS (SELECT 1 FROM knowledge.embeddings e WHERE e.chunk_id = c.id)"
    )

    if rows is None:
        for item in items:
            queue_fail(item["id"], "DB query failed")
        return 0

    already_done = set(chunk_ids) - {r[0] for r in rows}
    done_item_ids = [item_map[cid]["id"] for cid in already_done if cid in item_map]
    if done_item_ids:
        queue_complete_batch(done_item_ids, chain=False)

    if not rows:
        return len(already_done)

    texts = [r[1][:8000] for r in rows]
    embeddings = generate_embeddings_batch(texts)

    values = []
    success_items = []
    for (row, (vec, provider)) in zip(rows, embeddings):
        cid = row[0]
        item = item_map.get(cid)
        if not item:
            continue
        if vec is None:
            queue_fail(item["id"], "Embedding generation failed")
            continue

        vec_str = "[" + ",".join(str(v) for v in vec) + "]"
        model_name = "all-mpnet-base-v2" if provider == "local" else "workflow"
        values.append(
            f"({cid}, '{provider}', '{model_name}', '{vec_str}'::vector)"
        )
        success_items.append(item)

    stored = 0
    if values:
        for i in range(0, len(values), 25):
            batch_vals = values[i:i+25]
            batch_items = success_items[i:i+25]
            sql = (
                "INSERT INTO knowledge.embeddings "
                "(chunk_id, provider, model, embedding) VALUES "
                + ", ".join(batch_vals)
                + " ON CONFLICT (chunk_id) DO UPDATE SET "
                "embedding = EXCLUDED.embedding, model = EXCLUDED.model, "
                "provider = EXCLUDED.provider, created_at = NOW()"
            )
            result = db_query(sql, timeout=180)
            if result is not None:
                queue_complete_batch(
                    [item["id"] for item in batch_items], chain=False
                )
                stored += len(batch_items)
            else:
                for item in batch_items:
                    queue_fail(item["id"], "Batch insert failed")

    return stored + len(already_done)


def process_chunk_item(item):
    data = item.get("data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            data = {}

    content = data.get("content", "")
    url = data.get("url", "")
    doc_id = item.get("document_id", "")

    if not content:
        if doc_id:
            rows = db_query(
                f"SELECT content FROM knowledge.documents WHERE id = {int(doc_id)}"
            )
            if rows and rows[0]:
                content = rows[0][0]

    if not content or len(content.strip()) < 50:
        queue_fail(item["id"], "No content to chunk")
        return 0

    chunks = chunk_text(content)
    if not chunks:
        queue_fail(item["id"], "No chunks produced")
        return 0

    if not doc_id:
        content_hash = hashlib.sha256(
            content.encode('utf-8', errors='replace')
        ).hexdigest()
        rows = db_query(
            f"SELECT id FROM knowledge.documents WHERE url = {escape_sql(url)}"
        )
        if rows and rows[0]:
            doc_id = rows[0][0]
        else:
            result = db_query(
                f"INSERT INTO knowledge.documents (content, url, content_hash, created_at) "
                f"VALUES ({escape_sql(content)}, {escape_sql(url)}, "
                f"'{content_hash}', NOW()) "
                f"ON CONFLICT (url) DO UPDATE SET content_hash = EXCLUDED.content_hash "
                f"RETURNING id"
            )
            if result and result[0]:
                doc_id = result[0][0]
            else:
                queue_fail(item["id"], "Failed to get/create document")
                return 0

    chunk_ids = []
    for chunk in chunks:
        sql = (
            f"INSERT INTO knowledge.chunks (document_id, chunk_index, content, "
            f"content_hash, token_count) VALUES ({doc_id}, {chunk['index']}, "
            f"{escape_sql(chunk['content'])}, '{chunk['content_hash']}', "
            f"{chunk['token_count']}) "
            f"ON CONFLICT (document_id, chunk_index) DO UPDATE SET "
            f"content = EXCLUDED.content, content_hash = EXCLUDED.content_hash "
            f"RETURNING id"
        )
        result = db_query(sql)
        if result and result[0]:
            chunk_ids.append(result[0][0])

    if chunk_ids:
        for cid in chunk_ids:
            api_post("/queue/add", {
                "queue_name": "embedding",
                "data": {"chunk_id": cid},
                "document_id": str(doc_id),
                "priority": 5,
            })

        queue_complete(item["id"], chain=True,
                       document_id=str(doc_id),
                       chunk_ids=chunk_ids)
        return len(chunk_ids)

    queue_fail(item["id"], "No chunks stored")
    return 0


def process_store_item(item):
    data = item.get("data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            data = {}

    content = data.get("content", "")
    url = data.get("url", "")
    title = data.get("title", "")
    category = data.get("category", "unknown")

    if not content or len(content.strip()) < 50:
        queue_complete(item["id"], chain=False)
        return 0

    content_hash = hashlib.sha256(
        content.encode('utf-8', errors='replace')
    ).hexdigest()

    sql = (
        f"INSERT INTO knowledge.documents (title, content, url, category, "
        f"content_hash, created_at) VALUES ({escape_sql(title)}, "
        f"{escape_sql(content)}, {escape_sql(url)}, {escape_sql(category)}, "
        f"'{content_hash}', NOW()) "
        f"ON CONFLICT (url) DO NOTHING RETURNING id"
    )
    result = db_query(sql)
    if result and result[0]:
        doc_id = result[0][0]
        queue_complete(item["id"], chain=True,
                       document_id=str(doc_id),
                       data={"content": content, "url": url})
        return 1
    else:
        queue_complete(item["id"], chain=False)
        return 0


def run_stage(stage, stats):
    batch = EMBED_BATCH if stage == "embedding" else BATCH_SIZE

    items = queue_fetch(stage, batch)
    if not items:
        return 0

    if stage == "embedding":
        processed = process_embedding_items(items)
    elif stage == "chunk":
        processed = 0
        for item in items:
            processed += process_chunk_item(item)
    elif stage == "store":
        processed = 0
        for item in items:
            processed += process_store_item(item)
    else:
        for item in items:
            queue_complete(item["id"], chain=True)
        processed = len(items)

    stats[stage] = stats.get(stage, 0) + processed
    return len(items)


def main():
    stages = sys.argv[1:] if len(sys.argv) > 1 else ["embedding", "chunk", "store"]

    hostname = socket.gethostname()
    embed_mode = "local" if _can_embed_locally() else "API"

    print(f"\n{'='*60}", flush=True)
    print(f"Pipeline Queue Worker on {hostname}", flush=True)
    print(f"Worker ID: {WORKER_ID}", flush=True)
    print(f"Stages: {', '.join(stages)}", flush=True)
    print(f"Embedding mode: {embed_mode}", flush=True)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"{'='*60}\n", flush=True)

    stats = {}
    idle_count = 0
    last_report = time.time()
    total_fetched = 0

    while True:
        fetched_this_round = 0

        for stage in stages:
            fetched = run_stage(stage, stats)
            fetched_this_round += fetched

        if fetched_this_round > 0:
            idle_count = 0
            total_fetched += fetched_this_round
        else:
            idle_count += 1
            if idle_count >= MAX_IDLE_ROUNDS:
                log(f"Idle for {MAX_IDLE_ROUNDS * IDLE_SLEEP}s. Exiting.")
                break
            time.sleep(IDLE_SLEEP)

        now = time.time()
        if now - last_report >= 30:
            stat_str = " ".join(f"{k}={v}" for k, v in stats.items())
            log(f"total={total_fetched} {stat_str}")
            last_report = now

    print(f"\n{'='*60}", flush=True)
    print(f"DONE on {hostname}", flush=True)
    for k, v in stats.items():
        print(f"  {k}: {v}", flush=True)
    print(f"  total fetched: {total_fetched}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
