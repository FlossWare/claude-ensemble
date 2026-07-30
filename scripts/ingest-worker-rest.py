#!/usr/bin/env python3
"""REST-only ingest worker.

Consumes from the ingest:documents queue via REST API, stores documents
via the /store endpoint, and pushes to chunk:documents queue for the
next pipeline stage.

Zero direct Redis or PostgreSQL connections.

Usage:
    python3 ingest-worker-rest.py --worker-id server-01-ingest-1
    python3 ingest-worker-rest.py --api-url http://localhost:5000 --batch 50
"""
import argparse
import logging
import signal
import sys
import time
from pathlib import Path

import requests

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


def fetch_ingest_batch(api_url, count, worker_id):
    resp = requests.post(
        f'{api_url}/pipeline/queues/ingest/fetch',
        json={'count': count, 'worker_id': worker_id},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['items'], data.get('remaining', 0)


def store_document(api_url, doc):
    resp = requests.post(
        f'{api_url}/store/',
        json=doc,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def enqueue_for_chunking(api_url, items):
    if not items:
        return 0
    resp = requests.post(
        f'{api_url}/pipeline/queues/chunk/enqueue',
        json={'items': items},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get('enqueued', 0)


def requeue_items(api_url, items):
    resp = requests.post(
        f'{api_url}/pipeline/queues/ingest/requeue',
        json={'items': items},
        timeout=30,
    )
    resp.raise_for_status()


def run(api_url, batch_size, worker_id):
    stop_flag = Path.home() / f'ingest-worker-stop-{worker_id}'

    wid_filter = WorkerIdFilter(worker_id)
    for handler in logging.root.handlers:
        handler.addFilter(wid_filter)

    logger = logging.getLogger('ingest-worker')
    logger = logging.LoggerAdapter(logger, {'worker_id': worker_id})

    stop_flag.unlink(missing_ok=True)

    def stop_requested():
        return _shutdown or stop_flag.exists()

    try:
        resp = requests.get(f'{api_url}/pipeline/queues/ingest/status', timeout=10)
        resp.raise_for_status()
        qlen = resp.json().get('queue_length', 0)
    except Exception as e:
        logger.error(f'Cannot reach API at {api_url}: {e}')
        sys.exit(1)

    logger.info(f'Starting: api={api_url} batch={batch_size} queue={qlen}')

    ingested = 0
    queued = 0
    failed = 0
    start_time = time.time()
    backoff = 5

    while not stop_requested():
        try:
            items, remaining = fetch_ingest_batch(api_url, batch_size, worker_id)
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
        chunk_queue_batch = []

        requeue_batch = []

        for item in items:
            if not isinstance(item, dict):
                failed += 1
                continue

            try:
                result = store_document(api_url, item)
                doc_id = result.get('id') or result.get('document_id')
                if doc_id:
                    chunk_queue_batch.append({
                        'document_id': doc_id,
                        'source': item.get('source', 'unknown'),
                        'title': item.get('title', ''),
                    })
                ingested += 1
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 409:
                    ingested += 1
                else:
                    logger.error(f'Store failed for {item.get("url", "?")}: {e}')
                    requeue_batch.append(item)
                    failed += 1
            except Exception as e:
                logger.error(f'Store failed: {e}')
                requeue_batch.append(item)
                failed += 1

        if requeue_batch:
            try:
                requeue_items(api_url, requeue_batch)
                logger.info(f'Requeued {len(requeue_batch)} failed items')
            except Exception as e:
                logger.error(f'Requeue failed — {len(requeue_batch)} items lost: {e}')

        if chunk_queue_batch:
            try:
                enqueued = enqueue_for_chunking(api_url, chunk_queue_batch)
                queued += enqueued
            except Exception as e:
                logger.error(f'Chunk enqueue failed: {e}')

        elapsed = time.time() - start_time
        rate = ingested / max(1, elapsed)
        logger.info(
            f'Ingested: {ingested} | Queued: {queued} | Failed: {failed} | '
            f'Rate: {rate:.1f}/s | Queue: {remaining}'
        )

    elapsed = time.time() - start_time
    logger.info(f'Done: {ingested} ingested, {queued} queued, {failed} failed, {elapsed:.0f}s')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='REST-only ingest worker')
    parser.add_argument('--api-url', default='http://localhost:5000')
    parser.add_argument('--batch', type=int, default=50)
    parser.add_argument('--worker-id', default='ingest-worker-unknown')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s [%(worker_id)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path.home() / 'ingest-worker-rest.log'),
        ],
    )

    run(args.api_url, args.batch, args.worker_id)
