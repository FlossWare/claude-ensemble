#!/usr/bin/env python3
"""OrientDB backfill — populate graph from PostgreSQL documents via REST API.

Scans PostgreSQL documents (via REST) and creates missing Document/Chunk
vertices and edges in OrientDB. Used after the graph worker silently failed
due to the /query vs /command endpoint bug.

Usage:
    python3 graph-backfill.py --api http://192.168.2.5:5000
    python3 graph-backfill.py --api http://192.168.2.5:5000 --batch 100 --offset 0
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
log = logging.getLogger('graph-backfill')


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


def http_get(url, timeout=30):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def graph_query(api, sql):
    return http_post(f'{api}/graph/query', {'query': sql})


def escape_orient(s):
    if not s:
        return ''
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def ensure_document(api, doc_id, title, url, category):
    title_esc = escape_orient(str(title)[:500])
    url_esc = escape_orient(str(url)[:1000])
    cat_esc = escape_orient(str(category)[:200])
    doc_id_int = int(doc_id)

    try:
        graph_query(api,
            f"UPDATE Document SET title='{title_esc}', url='{url_esc}', "
            f"category='{cat_esc}' UPSERT WHERE doc_id={doc_id_int}")
    except Exception:
        try:
            graph_query(api,
                f"CREATE VERTEX Document SET doc_id={doc_id_int}, "
                f"title='{title_esc}', url='{url_esc}', category='{cat_esc}'")
        except Exception as e:
            log.warning('Failed to create doc %s: %s', doc_id_int, str(e)[:80])
            return False

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

    return True


def ensure_chunks_for_doc(api, doc_id, chunk_ids):
    doc_id_int = int(doc_id)
    created = 0
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
            created += 1
        except Exception:
            pass
    return created


def main():
    parser = argparse.ArgumentParser(description='OrientDB backfill from PostgreSQL')
    parser.add_argument('--api', default='http://localhost:5000')
    parser.add_argument('--batch', type=int, default=50)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--limit', type=int, default=0,
                        help='Max documents to process (0=all)')
    parser.add_argument('--with-chunks', action='store_true',
                        help='Also backfill chunk vertices')
    args = parser.parse_args()

    api = args.api

    orient_count = 0
    try:
        r = graph_query(api, 'SELECT count(*) FROM Document')
        orient_count = r.get('result', [{}])[0].get('count(*)', 0)
    except Exception as e:
        log.warning('OrientDB count failed: %s', e)

    pg_stats = http_get(f'{api}/knowledge/stats')
    pg_count = pg_stats.get('documents', 0)
    log.info('OrientDB: %d docs, PostgreSQL: %d docs, gap: %d',
             orient_count, pg_count, pg_count - orient_count)

    start_time = time.time()
    offset = args.offset
    total_created = 0
    total_skipped = 0
    total_chunks = 0
    total_errors = 0
    batch_size = args.batch

    while not _shutdown:
        try:
            docs_resp = http_get(
                f'{api}/knowledge/documents?limit={batch_size}&offset={offset}')
        except Exception as e:
            log.warning('Failed to fetch docs at offset %d: %s', offset, str(e)[:80])
            time.sleep(2)
            continue

        docs = docs_resp.get('documents', [])
        if not docs:
            log.info('No more documents at offset %d', offset)
            break

        for doc in docs:
            if _shutdown:
                break

            doc_id = str(doc.get('id', ''))
            title = doc.get('title', 'Untitled')
            url = doc.get('url', '')
            category = doc.get('category', 'unknown')

            if not doc_id:
                total_skipped += 1
                continue

            ok = ensure_document(api, doc_id, title, url, category)
            if ok:
                total_created += 1
            else:
                total_errors += 1

            if args.with_chunks and ok:
                try:
                    chunks_resp = http_get(
                        f'{api}/knowledge/chunks?document_id={doc_id}&limit=50')
                    chunk_ids = [c.get('id', '') for c in chunks_resp.get('chunks', [])]
                    if chunk_ids:
                        total_chunks += ensure_chunks_for_doc(api, doc_id, chunk_ids)
                except Exception:
                    pass

        offset += batch_size

        if args.limit and total_created >= args.limit:
            log.info('Reached limit of %d', args.limit)
            break

        if total_created > 0 and total_created % 500 < batch_size:
            elapsed = time.time() - start_time
            rate = total_created / elapsed if elapsed > 0 else 0
            log.info('Progress: created=%d skipped=%d errors=%d chunks=%d '
                     'offset=%d (%.1f docs/sec)',
                     total_created, total_skipped, total_errors,
                     total_chunks, offset, rate)

    elapsed = time.time() - start_time
    log.info('=== BACKFILL COMPLETE: created=%d skipped=%d errors=%d '
             'chunks=%d in %.0fs (%.1f docs/sec) ===',
             total_created, total_skipped, total_errors, total_chunks,
             elapsed, total_created / max(elapsed, 1))


if __name__ == '__main__':
    main()
