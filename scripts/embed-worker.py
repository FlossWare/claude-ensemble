#!/usr/bin/env python3
"""
Direct embedding worker — bypasses queue system, directly queries for chunks
without embeddings, generates them, and stores via REST API.

Much faster than queue-based approach since it eliminates queue round trips.
Each worker claims a range of chunk IDs to avoid conflicts.

Usage:
  python3 embed-worker.py OFFSET LIMIT
  python3 embed-worker.py 0 30000       # chunks 0-30000
  python3 embed-worker.py 30000 30000   # chunks 30000-60000
"""
import hashlib
import json
import os
import socket
import sys
import time
from datetime import datetime

import requests

os.environ.setdefault('HF_HOME', os.path.expanduser('~/.cache/huggingface'))
os.environ.setdefault('SENTENCE_TRANSFORMERS_HOME',
                      os.path.expanduser('~/.cache/sentence_transformers'))
os.environ.setdefault('TRANSFORMERS_CACHE',
                      os.path.expanduser('~/.cache/huggingface/hub'))
os.environ.setdefault('XET_LOG_DIR', os.path.expanduser('~/.cache/xet_logs'))

API_BASE = "http://aio-01:5000"
BATCH_SIZE = 50
HOSTNAME = socket.gethostname()

_st_model = None
_has_local = None
_local_failed = False


def _can_local():
    global _has_local
    if _has_local is None:
        try:
            from sentence_transformers import SentenceTransformer
            _has_local = True
        except ImportError:
            _has_local = False
    return _has_local


def _get_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer('all-mpnet-base-v2')
    return _st_model


def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"  [{ts}] {msg}", flush=True)


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


def embed_batch(texts):
    global _local_failed
    texts = [t[:8000] for t in texts]

    if _can_local() and not _local_failed:
        try:
            model = _get_model()
            vecs = model.encode(texts).tolist()
            return [(v, "local") for v in vecs]
        except Exception as e:
            log(f"Local failed, switching to API: {e}")
            _local_failed = True

    try:
        r = requests.post(f"{API_BASE}/learning/embeddings/generate",
                          json={"texts": texts}, timeout=60)
        d = r.json()
        if d.get("embeddings"):
            return [(e, "api") for e in d["embeddings"]]
    except Exception as e:
        log(f"API embedding error: {e}")

    return [(None, "")] * len(texts)


def escape_vec(vec):
    return "[" + ",".join(str(v) for v in vec) + "]"


def main():
    offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50000

    mode = "local" if _can_local() else "API"
    print(f"\n{'='*60}", flush=True)
    print(f"Direct Embedding Worker on {HOSTNAME}", flush=True)
    print(f"Offset: {offset}, Limit: {limit}", flush=True)
    print(f"Batch: {BATCH_SIZE}, Mode: {mode}", flush=True)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"{'='*60}\n", flush=True)

    total_embedded = 0
    total_skipped = 0
    total_errors = 0
    batch_num = 0
    last_report = time.time()

    for batch_offset in range(offset, offset + limit, BATCH_SIZE):
        batch_num += 1

        rows = db_query(
            f"SELECT c.id, c.content "
            f"FROM knowledge.chunks c "
            f"WHERE c.id >= {batch_offset} "
            f"AND c.id < {batch_offset + BATCH_SIZE} "
            f"AND NOT EXISTS ("
            f"  SELECT 1 FROM knowledge.embeddings e WHERE e.chunk_id = c.id"
            f") "
            f"ORDER BY c.id"
        )

        if rows is None:
            total_errors += 1
            time.sleep(2)
            continue

        if not rows:
            total_skipped += BATCH_SIZE
            continue

        texts = [r[1][:8000] if r[1] else "" for r in rows]
        valid = [(i, r) for i, (r, t) in enumerate(zip(rows, texts))
                 if t and len(t.strip()) >= 10]

        if not valid:
            total_skipped += len(rows)
            continue

        valid_texts = [texts[i] for i, _ in valid]
        embeddings = embed_batch(valid_texts)

        values = []
        for (idx, row), (vec, provider) in zip(valid, embeddings):
            if vec is None:
                total_errors += 1
                continue
            cid = row[0]
            model_name = "all-mpnet-base-v2" if provider == "local" else "workflow"
            values.append(
                f"({cid}, '{provider}', '{model_name}', "
                f"'{escape_vec(vec)}'::vector)"
            )

        if values:
            for i in range(0, len(values), 25):
                batch_vals = values[i:i+25]
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
                    total_embedded += len(batch_vals)
                else:
                    total_errors += len(batch_vals)

        now = time.time()
        if now - last_report >= 30:
            pct = ((batch_offset - offset) / limit * 100) if limit > 0 else 0
            log(f"embedded={total_embedded} skipped={total_skipped} "
                f"errors={total_errors} progress={pct:.1f}% "
                f"batch={batch_num}")
            last_report = now

    print(f"\n{'='*60}", flush=True)
    print(f"DONE on {HOSTNAME}", flush=True)
    print(f"  Embedded: {total_embedded}", flush=True)
    print(f"  Skipped: {total_skipped}", flush=True)
    print(f"  Errors: {total_errors}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
