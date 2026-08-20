#!/usr/bin/env python3
"""Generic pipeline worker — handles ANY queue type via REST API.

Designed by fleet consensus (5 Gemini models) + adversarial meta-review (3 models).

Fetches work from /pipeline/queues/fetch-any which returns the highest-priority
item from any non-empty queue. Worker dispatches to the correct handler based
on queue type. All DB access through REST API — zero direct connections.

Queue types handled: ingest, chunk, embed, embed-store, graph, store, knowledge

Pipeline flow: ingest → chunk → embed (separate) → embed-store → graph

Usage:
    python3 generic-worker.py --api http://localhost:5000
    python3 generic-worker.py --api http://aio-01:25000 --queues chunk,store
    API_BASE=http://localhost:5000 ALLOWED_QUEUES=chunk,graph python3 generic-worker.py
    MAX_PAYLOAD_KB=500 python3 generic-worker.py  # limit item size for constrained devices
"""
import argparse
import hashlib
import json
import logging
import os
import signal
import socket
import sys
import time
import urllib.error
import urllib.request

HOSTNAME = socket.gethostname()
_shutdown = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('generic-worker')

CHUNK_SIZE_CHARS = 2048
CHUNK_OVERLAP_CHARS = 200
MIN_CHUNK_LENGTH = 50
MAX_RETRIES = 2
RETRY_DELAYS = [1, 3]


def handle_signal(signum, frame):
    global _shutdown
    log.info('Shutdown requested')
    _shutdown = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def http_post(url, data, timeout=30):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method='POST',
                                headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def http_get(url, timeout=15):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def http_post_retry(url, data, timeout=30):
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return http_post(url, data, timeout)
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
    raise last_err


def chunk_text(text):
    if not text or not text.strip():
        return []
    step = max(CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS, 100)
    chunks = []
    for i in range(0, len(text), step):
        chunk = text[i:i + CHUNK_SIZE_CHARS]
        if len(chunk.strip()) < MIN_CHUNK_LENGTH:
            continue
        chunks.append(chunk)
    if not chunks and text.strip():
        chunks = [text[:CHUNK_SIZE_CHARS]]
    return chunks


def escape_orient(s):
    if not s:
        return ''
    return (s.replace("\\", "\\\\")
             .replace("'", "\\'")
             .replace('"', '\\"')
             .replace('\n', '\\n')
             .replace('\r', '\\r')
             .replace('\t', '\\t')
             .replace(';', ''))


# ─────────────────── Queue Handlers ───────────────────

def handle_ingest(api, item, worker_id):
    """Store document in knowledge base, enqueue for chunking."""
    content = item.get('content', '')
    url = item.get('url', '')
    title = item.get('title', 'Untitled')
    source = item.get('source', item.get('category', 'unknown'))

    if not content or len(content.strip()) < MIN_CHUNK_LENGTH:
        return {'action': 'skip', 'reason': 'content too short'}

    doc_resp = http_post_retry(f'{api}/knowledge/documents', {
        'title': title,
        'content': content,
        'url': url,
        'category': source,
    })

    doc_id = doc_resp.get('id')
    if doc_resp.get('stored') and doc_id:
        http_post(f'{api}/pipeline/queues/chunk/enqueue', {
            'items': [{'id': f'chunk-{doc_id}', 'document_id': doc_id}]
        })
        return {'action': 'stored', 'doc_id': doc_id, 'enqueued': 'chunk'}

    return {'action': 'duplicate', 'doc_id': doc_id}


def handle_chunk(api, item, worker_id):
    """Chunk document text, store chunks, enqueue for embedding."""
    doc_id = item.get('document_id')
    if not doc_id:
        return {'action': 'skip', 'reason': 'no document_id'}

    content = item.get('content', '')
    if not content:
        try:
            doc_data = http_get(f'{api}/knowledge/chunks/pending?document_id={doc_id}')
            content = doc_data.get('content', '')
        except Exception as e:
            return {'action': 'error', 'reason': f'fetch content failed: {str(e)[:80]}'}

    if not content or len(content.strip()) < MIN_CHUNK_LENGTH:
        return {'action': 'skip', 'reason': 'content too short'}

    text_chunks = chunk_text(content)
    if not text_chunks:
        return {'action': 'skip', 'reason': 'no chunks produced'}

    chunks_data = []
    for idx, cc in enumerate(text_chunks):
        chunks_data.append({
            'chunk_index': idx,
            'content': cc,
            'content_hash': hashlib.md5(cc.encode()).hexdigest(),
        })

    result = http_post_retry(f'{api}/knowledge/chunks/store', {
        'document_id': doc_id,
        'chunks': chunks_data,
    })

    stored = result.get('stored', 0)
    embed_items = []
    for idx, cc in enumerate(text_chunks):
        embed_items.append({
            'id': f'embed-{doc_id}-{idx}',
            'chunk_id': f'{doc_id}-{idx}',
            'content': cc[:4000],
            'document_id': doc_id,
        })

    if embed_items:
        http_post(f'{api}/pipeline/queues/embed/enqueue', {'items': embed_items})

    return {'action': 'chunked', 'chunks': stored, 'embed_queued': len(embed_items)}


def handle_embed_store(api, item, worker_id):
    """Write embedding vectors from queue to PostgreSQL."""
    chunk_id = item.get('chunk_id') or item.get('id')
    embedding = item.get('embedding') or item.get('vector')
    model = item.get('model', 'unknown')
    provider = item.get('provider', 'api')

    if not chunk_id or not embedding:
        return {'action': 'skip', 'reason': 'missing chunk_id or embedding'}

    result = http_post_retry(f'{api}/knowledge/chunks/store-embeddings-direct', {
        'embeddings': [{
            'chunk_id': chunk_id,
            'vector': embedding,
            'model': model,
            'provider': provider,
        }]
    })

    return {'action': 'stored', 'stored': result.get('stored', 0)}


def handle_graph(api, item, worker_id):
    """Create document/chunk vertices and edges in OrientDB."""
    doc_id = item.get('document_id', '')
    title = escape_orient(str(item.get('title', 'Untitled'))[:500])
    url = escape_orient(str(item.get('url', ''))[:1000])
    category = escape_orient(str(item.get('category', 'unknown'))[:200])
    chunk_ids = item.get('chunk_ids', [])

    if isinstance(chunk_ids, str):
        try:
            chunk_ids = json.loads(chunk_ids)
        except (json.JSONDecodeError, TypeError):
            chunk_ids = []

    if not doc_id:
        return {'action': 'skip', 'reason': 'no document_id'}

    try:
        doc_id_int = int(doc_id)
    except (ValueError, TypeError):
        return {'action': 'skip', 'reason': f'invalid document_id: {str(doc_id)[:50]}'}

    try:
        http_post(f'{api}/graph/query', {'query':
            f"UPDATE Document SET title='{title}', url='{url}', "
            f"category='{category}' UPSERT WHERE doc_id={doc_id_int}"})
    except Exception:
        try:
            http_post(f'{api}/graph/query', {'query':
                f"CREATE VERTEX Document SET doc_id={doc_id_int}, "
                f"title='{title}', url='{url}', category='{category}'"})
        except Exception:
            pass

    if category:
        try:
            http_post(f'{api}/graph/query', {'query':
                f"UPDATE Category SET name='{category}' UPSERT WHERE name='{category}'"})
            http_post(f'{api}/graph/query', {'query':
                f"CREATE EDGE IN_CATEGORY FROM "
                f"(SELECT FROM Document WHERE doc_id={doc_id_int}) TO "
                f"(SELECT FROM Category WHERE name='{category}')"})
        except Exception:
            pass

    for cid in chunk_ids[:50]:
        try:
            cid_int = int(cid)
        except (ValueError, TypeError):
            continue
        try:
            http_post(f'{api}/graph/query', {'query':
                f"UPDATE Chunk SET chunk_id={cid_int}, doc_id={doc_id_int} "
                f"UPSERT WHERE chunk_id={cid_int}"})
            http_post(f'{api}/graph/query', {'query':
                f"CREATE EDGE HAS_CHUNK FROM "
                f"(SELECT FROM Document WHERE doc_id={doc_id_int}) TO "
                f"(SELECT FROM Chunk WHERE chunk_id={cid_int})"})
        except Exception:
            pass

    return {'action': 'graphed', 'doc_id': doc_id_int, 'chunks': len(chunk_ids)}


def handle_store(api, item, worker_id):
    """Generic store handler — writes item data to knowledge base."""
    content = item.get('content', '')
    if not content:
        return {'action': 'skip', 'reason': 'no content'}

    result = http_post_retry(f'{api}/knowledge/documents', {
        'title': item.get('title', 'Untitled'),
        'content': content,
        'url': item.get('url', ''),
        'category': item.get('category', 'store'),
    })

    return {'action': 'stored', 'doc_id': result.get('id'), 'new': result.get('stored', False)}


def handle_knowledge(api, item, worker_id):
    """Knowledge enrichment — placeholder for future processing."""
    return {'action': 'pass', 'reason': 'knowledge handler not yet implemented'}


def handle_embed(api, item, worker_id):
    """Generate embeddings via FreeModelRouter REST endpoint, then store."""
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
        'embeddings': [{
            'chunk_id': chunk_id,
            'vector': emb['vector'],
            'model': emb.get('model', 'unknown'),
            'provider': emb.get('provider', 'api'),
        }]
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


# ─────────────────── Main Loop ───────────────────

def main():
    parser = argparse.ArgumentParser(description='Generic pipeline worker')
    parser.add_argument('--api', default=os.getenv('API_BASE', 'http://localhost:5000'))
    parser.add_argument('--queues', default=os.getenv('ALLOWED_QUEUES', '*'),
                        help='Comma-separated queue names or * for all (except embed)')
    parser.add_argument('--max-payload-kb', type=int,
                        default=int(os.getenv('MAX_PAYLOAD_KB', '0')),
                        help='Max item size in KB (0=unlimited)')
    parser.add_argument('--batch', type=int, default=int(os.getenv('BATCH_SIZE', '5')))
    parser.add_argument('--poll-interval', type=float,
                        default=float(os.getenv('POLL_INTERVAL', '2.0')))
    parser.add_argument('--worker-id', default=os.getenv('WORKER_ID', f'{HOSTNAME}-generic'))
    args = parser.parse_args()

    api = args.api
    worker_id = args.worker_id
    allowed = args.queues.split(',') if args.queues != '*' else ['*']
    poll_interval = args.poll_interval

    log.info('Worker %s starting — api=%s queues=%s max_payload=%sKB batch=%d',
             worker_id, api, allowed, args.max_payload_kb or 'unlimited', args.batch)

    try:
        health = http_get(f'{api}/health')
        log.info('API healthy: %s', health.get('status', 'unknown'))
    except Exception as e:
        log.error('Cannot reach API at %s: %s', api, str(e)[:100])
        sys.exit(1)

    stats = {q: 0 for q in HANDLERS}
    stats['errors'] = 0
    stats['skips'] = 0
    start_time = time.time()
    empty_rounds = 0

    while not _shutdown:
        try:
            fetch_body = {
                'allowed_queues': allowed,
                'worker_id': worker_id,
                'count': args.batch,
            }
            if args.max_payload_kb > 0:
                fetch_body['max_payload_kb'] = args.max_payload_kb

            req = urllib.request.Request(
                f'{api}/pipeline/queues/fetch-any',
                data=json.dumps(fetch_body).encode(),
                method='POST',
                headers={'Content-Type': 'application/json'})
            resp = urllib.request.urlopen(req, timeout=30)

            if resp.status == 204:
                empty_rounds += 1
                sleep_time = min(poll_interval * (1 + empty_rounds * 0.5), 30)
                time.sleep(sleep_time)
                continue

            data = json.loads(resp.read())

        except urllib.error.HTTPError as e:
            if e.code == 204:
                empty_rounds += 1
                sleep_time = min(poll_interval * (1 + empty_rounds * 0.5), 30)
                time.sleep(sleep_time)
                continue
            log.warning('Fetch error: HTTP %d', e.code)
            time.sleep(5)
            continue
        except Exception as e:
            log.warning('Fetch error: %s', str(e)[:100])
            time.sleep(5)
            continue

        queue_name = data.get('queue', '')
        items = data.get('items', [])

        if not items:
            empty_rounds += 1
            time.sleep(poll_interval)
            continue

        empty_rounds = 0
        handler = HANDLERS.get(queue_name)

        if not handler:
            log.warning('No handler for queue: %s', queue_name)
            continue

        for item in items:
            item_id = item.get('id', '')
            try:
                result = handler(api, item, worker_id)
                action = result.get('action', 'unknown')

                if action == 'skip':
                    stats['skips'] += 1
                else:
                    stats[queue_name] = stats.get(queue_name, 0) + 1

                http_post(f'{api}/pipeline/queues/{queue_name}/complete', {'id': item_id})

            except Exception as e:
                stats['errors'] += 1
                log.warning('[%s] %s error on %s: %s', queue_name, worker_id, item_id, str(e)[:120])
                try:
                    http_post(f'{api}/pipeline/queues/{queue_name}/requeue', {'items': [item]})
                except Exception:
                    pass

        total = sum(v for k, v in stats.items() if k not in ('errors', 'skips'))
        if total > 0 and total % 20 < args.batch:
            elapsed = time.time() - start_time
            rate = total / elapsed if elapsed > 0 else 0
            breakdown = ' '.join(f'{k}={v}' for k, v in stats.items() if v > 0)
            log.info('[%s] %s (%.1f/sec) remaining=%s',
                     worker_id, breakdown, rate, data.get('remaining', '?'))

    elapsed = time.time() - start_time
    total = sum(v for k, v in stats.items() if k not in ('errors', 'skips'))
    log.info('=== %s FINAL: %d processed, %d errors, %d skips in %.0fs ===',
             worker_id, total, stats['errors'], stats['skips'], elapsed)


if __name__ == '__main__':
    main()
