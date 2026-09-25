#!/usr/bin/env python3
"""Chunk worker — Redis queue consumer.

Consumes from Redis chunk queue, chunks text, stores chunks via REST,
marks items complete (auto-chains to embed queue).

Pipeline: scraper → store queue → ingest → chunk queue → [THIS] → embed queue → graph queue

Usage:
    python3 chunk-worker-redis.py --api http://192.168.2.5:5000
"""
import argparse
import hashlib
import json
import logging
import signal
import socket
import sys
import time
import urllib.request
import urllib.error

CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_RATIO = 0.37
CHARS_PER_TOKEN = 4
HOSTNAME = socket.gethostname()
_shutdown = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('chunk-redis')


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


def chunk_text(text):
    if not text or not text.strip():
        return []
    chunk_chars = CHUNK_SIZE_TOKENS * CHARS_PER_TOKEN
    overlap_chars = int(chunk_chars * CHUNK_OVERLAP_RATIO)
    step = max(chunk_chars - overlap_chars, 100)
    chunks = []
    for i in range(0, len(text), step):
        chunk = text[i:i + chunk_chars]
        if len(chunk.strip()) < 50:
            continue
        chunks.append(chunk)
    if not chunks and text.strip():
        chunks = [text[:chunk_chars]]
    return chunks


def main():
    parser = argparse.ArgumentParser(description='Redis chunk queue worker')
    parser.add_argument('--api', default='http://localhost:5000')
    parser.add_argument('--batch', type=int, default=10)
    parser.add_argument('--worker-id', default=f'{HOSTNAME}-chunk-redis')
    args = parser.parse_args()

    api = args.api
    worker_id = args.worker_id
    batch_size = args.batch

    log.info('Worker %s starting — api=%s batch=%d', worker_id, api, batch_size)

    start_time = time.time()
    total_docs = 0
    total_chunks = 0
    total_errors = 0
    empty_rounds = 0

    while not _shutdown:
        try:
            resp = http_post(f'{api}/queue/fetch/chunk',
                             {'limit': batch_size, 'worker_id': worker_id})
        except urllib.error.HTTPError as e:
            if e.code == 204:
                empty_rounds += 1
                if empty_rounds >= 10:
                    time.sleep(10)
                    empty_rounds = 0
                else:
                    time.sleep(3)
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
                time.sleep(10)
                empty_rounds = 0
            else:
                time.sleep(3)
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

            content = data.get('content', '')
            title = data.get('title', 'Untitled')
            url = data.get('url', '')
            category = data.get('category', 'unknown')

            if not content or len(content.strip()) < 50:
                try:
                    http_post(f'{api}/queue/complete',
                              {'item_id': item_id, 'worker_id': worker_id,
                               'chain': False})
                except Exception:
                    pass
                continue

            text_chunks = chunk_text(content)
            if not text_chunks:
                try:
                    http_post(f'{api}/queue/complete',
                              {'item_id': item_id, 'worker_id': worker_id,
                               'chain': False})
                except Exception:
                    pass
                total_errors += 1
                continue

            chunks_data = []
            for idx, cc in enumerate(text_chunks):
                chunks_data.append({
                    'chunk_index': idx,
                    'content': cc,
                    'content_hash': hashlib.md5(cc.encode()).hexdigest(),
                })

            try:
                doc_id = item.get('document_id', '')
                if not doc_id:
                    doc_resp = http_post(f'{api}/knowledge/documents', {
                        'title': title,
                        'content': content,
                        'url': url,
                        'category': category,
                    })
                    doc_id = str(doc_resp.get('id', ''))

                if doc_id:
                    store_resp = http_post(f'{api}/knowledge/chunks/store', {
                        'document_id': doc_id,
                        'chunks': chunks_data,
                    }, timeout=60)
                    stored_ids = store_resp.get('chunk_ids', [])
                    total_chunks += len(stored_ids)

                    http_post(f'{api}/queue/complete', {
                        'item_id': item_id,
                        'worker_id': worker_id,
                        'chain': True,
                        'document_id': doc_id,
                        'chunk_ids': stored_ids,
                    })
                else:
                    http_post(f'{api}/queue/complete', {
                        'item_id': item_id,
                        'worker_id': worker_id,
                        'chain': True,
                        'data': {'content': content[:2000], 'title': title,
                                 'url': url, 'category': category},
                    })

                total_docs += 1

            except Exception as e:
                total_errors += 1
                log.warning('Process error for item %s: %s', item_id, str(e)[:120])
                try:
                    http_post(f'{api}/queue/fail', {
                        'item_id': item_id,
                        'worker_id': worker_id,
                        'error': str(e)[:200],
                    })
                except Exception:
                    pass

        if total_docs > 0 and total_docs % 50 < batch_size:
            elapsed = time.time() - start_time
            rate = total_docs / elapsed if elapsed > 0 else 0
            log.info('[%s] docs=%d chunks=%d errors=%d (%.1f docs/sec)',
                     worker_id, total_docs, total_chunks, total_errors, rate)

    elapsed = time.time() - start_time
    log.info('=== %s FINAL: %d docs, %d chunks, %d errors in %.0fs ===',
             worker_id, total_docs, total_chunks, total_errors, elapsed)


if __name__ == '__main__':
    main()
