#!/usr/bin/env python3
"""Backfill embeddings for knowledge.code_embeddings via REST API.

Reads chunks without embeddings from the REST API, generates embeddings
locally with sentence-transformers (768-dim all-mpnet-base-v2), and
stores them back via REST API. NEVER connects to PostgreSQL directly.

Usage:
    python3 scripts/backfill-embeddings.py [--batch 64] [--api http://localhost:5000]
"""
import argparse
import json
import logging
import signal
import sys
import time
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('backfill-embeddings')

_shutdown = False

def handle_signal(signum, frame):
    global _shutdown
    log.info('Shutdown requested')
    _shutdown = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

MODEL_NAME = 'all-mpnet-base-v2'
TARGET_DIM = 1024


def api_post(url, data, timeout=60):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method='POST',
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def api_get(url, timeout=30):
    req = urllib.request.Request(url, method='GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=int, default=64)
    parser.add_argument('--api', default='http://localhost:5000')
    parser.add_argument('--max-batches', type=int, default=0,
                        help='Stop after N batches (0=unlimited)')
    args = parser.parse_args()

    log.info('Loading sentence-transformers model %s...', MODEL_NAME)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    test = model.encode(['test'])
    assert len(test[0]) == TARGET_DIM, f'Expected {TARGET_DIM}-dim, got {len(test[0])}'
    log.info('Model loaded, dim=%d', TARGET_DIM)

    stats = api_get(f'{args.api}/documents/stats')
    total_chunks = stats.get('total_chunks', 0)
    log.info('Total chunks in DB: %d', total_chunks)

    offset = 0
    batches_done = 0
    total_embedded = 0
    start_time = time.time()

    while not _shutdown:
        try:
            resp = api_post(f'{args.api}/documents/batch-embed', {
                'batch_size': args.batch,
                'model_name': MODEL_NAME,
            })

            fetched = resp.get('fetched', 0)
            if fetched == 0:
                log.info('No more chunks to embed. Done!')
                break

            chunks = resp.get('chunks', [])
            texts = []
            ids = []
            for c in chunks:
                text = c.get('content') or c.get('content_preview') or ''
                if not text.strip():
                    continue
                texts.append(text)
                ids.append(c['id'])

            if not texts:
                log.warning('Batch had no usable text, skipping')
                continue

            embeddings = model.encode(texts, show_progress_bar=False, batch_size=args.batch)

            store_resp = api_post(f'{args.api}/documents/store-embeddings', {
                'embeddings': [
                    {'id': id_, 'embedding': emb.tolist()}
                    for id_, emb in zip(ids, embeddings)
                ]
            }, timeout=120)

            stored = store_resp.get('updated', 0)
            total_embedded += stored
            batches_done += 1
            elapsed = time.time() - start_time
            rate = total_embedded / elapsed if elapsed > 0 else 0

            log.info('Batch %d: embedded %d/%d chunks (total: %d, %.1f/sec)',
                     batches_done, stored, fetched, total_embedded, rate)

            if args.max_batches and batches_done >= args.max_batches:
                log.info('Reached max batches (%d)', args.max_batches)
                break

        except urllib.error.HTTPError as e:
            if e.code == 404:
                log.warning('batch-embed endpoint not found, need to deploy it first')
                break
            log.error('HTTP error %d: %s', e.code, e.read().decode()[:200])
            time.sleep(5)
        except Exception as e:
            log.error('Error: %s', e)
            time.sleep(5)

    elapsed = time.time() - start_time
    log.info('Finished: %d chunks embedded in %.1fs (%.1f/sec)',
             total_embedded, elapsed, total_embedded / elapsed if elapsed > 0 else 0)


if __name__ == '__main__':
    main()
