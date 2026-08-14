#!/usr/bin/env python3
"""Ingest worker — consumes scraped items from ingest queue, stores as documents,
enqueues to chunk queue. All via REST API, no direct DB connections.

Pipeline: scraper → ingest queue → [THIS] → knowledge.documents + chunk queue → chunk-worker

Usage:
    python3 ingest-worker.py --api http://localhost:5000
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('ingest-worker')

_shutdown = False
HOSTNAME = socket.gethostname()


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


def main():
    parser = argparse.ArgumentParser(description='Ingest queue worker')
    parser.add_argument('--api', default='http://localhost:5000')
    parser.add_argument('--batch', type=int, default=10)
    args = parser.parse_args()

    api = args.api
    batch_size = args.batch

    log.info('Worker %s starting — api=%s batch=%d', HOSTNAME, api, batch_size)

    start_time = time.time()
    total_stored = 0
    total_dupes = 0
    total_errors = 0
    empty_rounds = 0

    while not _shutdown:
        try:
            resp = http_post(f'{api}/pipeline/queues/ingest/fetch',
                             {'count': batch_size, 'worker_id': HOSTNAME})
        except Exception as e:
            log.warning('Queue fetch error: %s', str(e)[:100])
            time.sleep(5)
            continue

        items = resp.get('items', [])
        if not items:
            empty_rounds += 1
            if empty_rounds >= 30:
                log.info('No work for 30 rounds, sleeping 30s')
                time.sleep(30)
                empty_rounds = 0
            else:
                time.sleep(2)
            continue

        empty_rounds = 0
        chunk_batch = []

        for item in items:
            content = item.get('content', '')
            url = item.get('url', '')
            title = item.get('title', 'Untitled')
            source = item.get('source', 'unknown')
            item_id = item.get('id', '')

            if not content or len(content.strip()) < 50:
                try:
                    http_post(f'{api}/pipeline/queues/ingest/complete',
                              {'id': item_id})
                except Exception:
                    pass
                continue

            try:
                doc_resp = http_post(f'{api}/knowledge/documents', {
                    'title': title,
                    'content': content,
                    'url': url,
                    'category': source,
                })
                doc_id = doc_resp.get('id')
                if doc_resp.get('stored'):
                    total_stored += 1
                    if doc_id:
                        chunk_batch.append({
                            'id': f'chunk-{doc_id}',
                            'document_id': doc_id,
                        })
                else:
                    total_dupes += 1

                http_post(f'{api}/pipeline/queues/ingest/complete',
                          {'id': item_id})
            except Exception as e:
                total_errors += 1
                log.warning('Store error: %s', str(e)[:120])
                try:
                    http_post(f'{api}/pipeline/queues/ingest/requeue',
                              {'items': [item]})
                except Exception:
                    pass

        if chunk_batch:
            try:
                http_post(f'{api}/pipeline/queues/chunk/enqueue',
                          {'items': chunk_batch})
            except Exception as e:
                log.warning('Chunk enqueue error: %s', str(e)[:100])

        if (total_stored + total_dupes) > 0 and (total_stored + total_dupes) % 50 < batch_size:
            elapsed = time.time() - start_time
            rate = total_stored / elapsed if elapsed > 0 else 0
            log.info('[%s] stored=%d dupes=%d errors=%d (%.1f/sec)',
                     HOSTNAME, total_stored, total_dupes, total_errors, rate)

    elapsed = time.time() - start_time
    log.info('=== %s FINAL: %d stored, %d dupes, %d errors in %.0fs ===',
             HOSTNAME, total_stored, total_dupes, total_errors, elapsed)


if __name__ == '__main__':
    main()
