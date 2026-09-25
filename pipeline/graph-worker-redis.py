#!/usr/bin/env python3
"""Graph worker — Redis queue consumer for OrientDB ingestion.

Consumes from Redis graph queue, creates/updates Document and Chunk vertices
and HAS_CHUNK/IN_CATEGORY edges in OrientDB via REST API.

Pipeline: ... → embed queue → [THIS] → OrientDB graph

Usage:
    python3 graph-worker-redis.py --api http://192.168.2.5:5000
"""
import argparse
import json
import logging
import signal
import socket
import sys
import time
import urllib.request
import urllib.error

HOSTNAME = socket.gethostname()
_shutdown = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('graph-redis')


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


def graph_query(api, sql):
    return http_post(f'{api}/graph/query', {'query': sql})


def escape_orient(s):
    if not s:
        return ''
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def ensure_document(api, doc_id, title, url, category):
    title_esc = escape_orient(title[:500])
    url_esc = escape_orient(url[:1000])
    cat_esc = escape_orient(category[:200])
    doc_id_int = int(doc_id)

    try:
        graph_query(api,
            f"UPDATE Document SET title='{title_esc}', url='{url_esc}', "
            f"category='{cat_esc}' UPSERT WHERE doc_id={doc_id_int}")
    except Exception as e:
        try:
            graph_query(api,
                f"CREATE VERTEX Document SET doc_id={doc_id_int}, "
                f"title='{title_esc}', url='{url_esc}', category='{cat_esc}'")
        except Exception:
            pass

    if cat_esc:
        try:
            graph_query(api,
                f"UPDATE Category SET name='{cat_esc}' UPSERT WHERE name='{cat_esc}'")
            graph_query(api,
                f"CREATE EDGE IN_CATEGORY FROM "
                f"(SELECT FROM Document WHERE doc_id={doc_id_int}) TO "
                f"(SELECT FROM Category WHERE name='{cat_esc}')")
        except Exception:
            pass


def ensure_chunks(api, doc_id, chunk_ids):
    doc_id_int = int(doc_id)
    for cid in chunk_ids[:50]:
        cid_int = int(cid)
        try:
            graph_query(api,
                f"UPDATE Chunk SET chunk_id={cid_int}, doc_id={doc_id_int} "
                f"UPSERT WHERE chunk_id={cid_int}")
            graph_query(api,
                f"CREATE EDGE HAS_CHUNK FROM "
                f"(SELECT FROM Document WHERE doc_id={doc_id_int}) TO "
                f"(SELECT FROM Chunk WHERE chunk_id={cid_int})")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description='Redis graph queue worker')
    parser.add_argument('--api', default='http://localhost:5000')
    parser.add_argument('--batch', type=int, default=5)
    parser.add_argument('--worker-id', default=f'{HOSTNAME}-graph')
    args = parser.parse_args()

    api = args.api
    worker_id = args.worker_id

    log.info('Worker %s starting — api=%s', worker_id, api)

    try:
        health = http_post(f'{api}/graph/query', {'query': 'SELECT count(*) FROM Document'})
        log.info('OrientDB connected — documents: %s', health)
    except Exception as e:
        log.warning('OrientDB check failed (will retry): %s', str(e)[:100])

    start_time = time.time()
    total = 0
    errors = 0
    empty_rounds = 0

    while not _shutdown:
        try:
            resp = http_post(f'{api}/queue/fetch/graph',
                             {'limit': args.batch, 'worker_id': worker_id})
        except urllib.error.HTTPError as e:
            if e.code == 204:
                empty_rounds += 1
                if empty_rounds >= 10:
                    time.sleep(15)
                    empty_rounds = 0
                else:
                    time.sleep(5)
                continue
            log.warning('Queue fetch error: HTTP %d', e.code)
            time.sleep(5)
            continue
        except Exception as e:
            log.warning('Queue fetch error: %s', str(e)[:100])
            time.sleep(5)
            continue

        items = resp.get('items', [])
        if not items:
            empty_rounds += 1
            if empty_rounds >= 10:
                time.sleep(15)
                empty_rounds = 0
            else:
                time.sleep(5)
            continue

        empty_rounds = 0

        for item in items:
            item_id = item.get('id', '')
            data = item.get('data', {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    data = {}

            doc_id = item.get('document_id', '') or data.get('document_id', '')
            title = data.get('title', 'Untitled')
            url = data.get('url', '')
            category = data.get('category', 'unknown')
            chunk_ids = item.get('chunk_ids', [])
            if isinstance(chunk_ids, str):
                try:
                    chunk_ids = json.loads(chunk_ids)
                except (json.JSONDecodeError, TypeError):
                    chunk_ids = []

            try:
                if doc_id:
                    ensure_document(api, doc_id, title, url, category)
                    if chunk_ids:
                        ensure_chunks(api, doc_id, chunk_ids)

                http_post(f'{api}/queue/complete', {
                    'item_id': item_id,
                    'worker_id': worker_id,
                    'chain': False,
                })
                total += 1

            except Exception as e:
                errors += 1
                log.warning('Graph error for item %s: %s', item_id, str(e)[:120])
                try:
                    http_post(f'{api}/queue/fail', {
                        'item_id': item_id,
                        'worker_id': worker_id,
                        'error': str(e)[:200],
                    })
                except Exception:
                    pass

        if total > 0 and total % 50 < args.batch:
            elapsed = time.time() - start_time
            rate = total / elapsed if elapsed > 0 else 0
            log.info('[%s] graphed=%d errors=%d (%.1f/sec)',
                     worker_id, total, errors, rate)

    elapsed = time.time() - start_time
    log.info('=== %s FINAL: %d graphed, %d errors in %.0fs ===',
             worker_id, total, errors, elapsed)


if __name__ == '__main__':
    main()
