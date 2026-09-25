#!/usr/bin/env python3
"""REST-only embedding worker.

Pulls chunks from the embedding queue via REST API, embeds locally via
sentence-transformers service, stores embeddings via REST API.

Zero direct Redis or PostgreSQL connections — all access through aio-01:5000.

Usage:
    python3 embed-worker-rest.py --embed-port 8101 --worker-id cabin-laptop-01-w1
    python3 embed-worker-rest.py --embed-port 8102 --worker-id cabin-laptop-01-w2 --batch 25
"""
import argparse
import logging
import signal
import sys
import time
from pathlib import Path

import requests

TARGET_DIM = 1024
MAX_BACKOFF = 60

_shutdown = False


class WorkerIdFilter(logging.Filter):
    def __init__(self, worker_id='system'):
        super().__init__()
        self.worker_id = worker_id

    def filter(self, record):
        if not hasattr(record, 'worker_id'):
            record.worker_id = self.worker_id
        return True


def handle_signal(signum, frame):
    global _shutdown
    _shutdown = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def fetch_batch(api_url, count, worker_id):
    resp = requests.post(
        f'{api_url}/pipeline/embedding-queue/fetch',
        json={'count': count, 'worker_id': worker_id},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['items'], data.get('remaining', 0)


def embed_batch(embed_url, texts):
    resp = requests.post(
        embed_url,
        json={'texts': [t[:8000] for t in texts]},
        timeout=120,
    )
    resp.raise_for_status()
    result = []
    for emb in resp.json()['embeddings']:
        if len(emb) > TARGET_DIM:
            emb = emb[:TARGET_DIM]
        elif len(emb) < TARGET_DIM:
            emb = emb + [0.0] * (TARGET_DIM - len(emb))
        result.append(emb)
    return result


def store_embeddings(api_url, items, worker_id):
    resp = requests.post(
        f'{api_url}/pipeline/chunks/store-embeddings',
        json={'embeddings': items, 'worker_id': worker_id},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def requeue_items(api_url, items):
    resp = requests.post(
        f'{api_url}/pipeline/embedding-queue/requeue',
        json={'items': items},
        timeout=30,
    )
    resp.raise_for_status()


def get_queue_status(api_url):
    resp = requests.get(
        f'{api_url}/pipeline/embedding-queue/status',
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get('queue_length', 0)


def run(api_url, embed_url, batch_size, worker_id):
    stop_flag = Path.home() / f'embed-worker-rest-stop-{worker_id}'

    wid_filter = WorkerIdFilter(worker_id)
    for handler in logging.root.handlers:
        handler.addFilter(wid_filter)

    logger = logging.getLogger('embed-worker')
    logger = logging.LoggerAdapter(logger, {'worker_id': worker_id})

    stop_flag.unlink(missing_ok=True)

    def stop_requested():
        return _shutdown or stop_flag.exists()

    try:
        qlen = get_queue_status(api_url)
    except Exception as e:
        logger.error(f'Cannot reach API at {api_url}: {e}')
        sys.exit(1)

    logger.info(f'Starting: api={api_url} embed={embed_url} batch={batch_size} queue={qlen}')

    embedded = 0
    failed = 0
    requeued = 0
    start_time = time.time()
    backoff = 5

    while not stop_requested():
        try:
            items, remaining = fetch_batch(api_url, batch_size, worker_id)
        except Exception as e:
            logger.error(f'Fetch failed: {e} — retrying in {backoff}s')
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue

        if not items:
            logger.info(f'Queue empty, waiting {backoff}s...')
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue

        backoff = 5

        valid_items = [
            item for item in items
            if isinstance(item, dict) and 'content' in item and 'chunk_id' in item
        ]
        if len(valid_items) < len(items):
            skipped = len(items) - len(valid_items)
            logger.warning(f'Skipped {skipped} malformed items (missing content or chunk_id)')
            failed += skipped

        if not valid_items:
            continue

        texts = [item['content'] for item in valid_items]
        chunk_ids = [item['chunk_id'] for item in valid_items]

        try:
            embeddings = embed_batch(embed_url, texts)
        except Exception as e:
            logger.error(f'Embed failed: {e} — re-queuing {len(valid_items)} items')
            try:
                requeue_items(api_url, valid_items)
                requeued += len(valid_items)
            except Exception as re_err:
                logger.error(f'Requeue also failed: {re_err} — {len(valid_items)} items lost')
                failed += len(valid_items)
            time.sleep(5)
            continue

        if len(embeddings) != len(texts):
            logger.error(
                f'Embedding count mismatch: sent {len(texts)}, got {len(embeddings)} — '
                f're-queuing unmatched items'
            )
            matched = min(len(embeddings), len(texts))
            unmatched = valid_items[matched:]
            if unmatched:
                try:
                    requeue_items(api_url, unmatched)
                    requeued += len(unmatched)
                except Exception:
                    failed += len(unmatched)
            embeddings = embeddings[:matched]
            chunk_ids = chunk_ids[:matched]

        store_items = []
        for cid, emb in zip(chunk_ids, embeddings):
            if emb is not None:
                store_items.append({
                    'chunk_id': cid,
                    'embedding': emb,
                    'model': 'all-mpnet-base-v2',
                    'provider': 'local-cpu',
                })

        if store_items:
            try:
                result = store_embeddings(api_url, store_items, worker_id)
                embedded += result.get('stored', 0)
                failed += result.get('failed', result.get('errors', 0))
            except Exception as e:
                logger.error(f'Store failed: {e} — re-queuing {len(valid_items)} items')
                try:
                    requeue_items(api_url, valid_items)
                    requeued += len(valid_items)
                except Exception as re_err:
                    logger.error(f'Requeue also failed: {re_err} — {len(valid_items)} items lost')
                    failed += len(valid_items)

        elapsed = time.time() - start_time
        rate = embedded / max(1, elapsed)
        logger.info(f'Embedded: {embedded} | Failed: {failed} | Requeued: {requeued} | Rate: {rate:.1f}/s | Queue: {remaining}')

    elapsed = time.time() - start_time
    logger.info(f'Done: {embedded} embedded, {failed} failed, {requeued} requeued, {elapsed:.0f}s')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='REST-only embedding worker')
    parser.add_argument('--api-url', default='http://localhost:5000')
    parser.add_argument('--embed-port', type=int, default=8101)
    parser.add_argument('--batch', type=int, default=50)
    parser.add_argument('--worker-id', default='worker-unknown')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s [%(worker_id)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path.home() / 'embed-worker-rest.log'),
        ],
    )

    embed_url = f'http://localhost:{args.embed_port}/embeddings'
    run(args.api_url, embed_url, args.batch, args.worker_id)
