#!/usr/bin/env python3
"""REST-only chunk worker.

Consumes from the chunk:documents queue via REST API, fetches document
content via REST, chunks the text, stores chunks via REST API, and
pushes to embed:documents queue for the next pipeline stage.

Zero direct Redis or PostgreSQL connections.

Usage:
    python3 chunk-worker-rest.py --worker-id server-01-chunk-1
    python3 chunk-worker-rest.py --api-url http://localhost:5000 --batch 20
"""
import argparse
import hashlib
import logging
import signal
import sys
import time
from pathlib import Path

import requests

CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_RATIO = 0.37
CHARS_PER_TOKEN = 4
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


def fetch_chunk_batch(api_url, count, worker_id):
    resp = requests.post(
        f'{api_url}/pipeline/queues/chunk/fetch',
        json={'count': count, 'worker_id': worker_id},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['items'], data.get('remaining', 0)


def fetch_document_content(api_url, document_id):
    resp = requests.get(
        f'{api_url}/knowledge/chunks/pending',
        params={'document_id': document_id},
        timeout=30,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def store_chunks(api_url, document_id, chunks_data):
    resp = requests.post(
        f'{api_url}/knowledge/chunks/store',
        json={'document_id': document_id, 'chunks': chunks_data},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def enqueue_for_embedding(api_url, items):
    if not items:
        return 0
    resp = requests.post(
        f'{api_url}/pipeline/queues/embed/enqueue',
        json={'items': items},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get('enqueued', 0)


def requeue_items(api_url, items):
    resp = requests.post(
        f'{api_url}/pipeline/queues/chunk/requeue',
        json={'items': items},
        timeout=30,
    )
    resp.raise_for_status()


def run(api_url, batch_size, worker_id):
    stop_flag = Path.home() / f'chunk-worker-stop-{worker_id}'

    wid_filter = WorkerIdFilter(worker_id)
    for handler in logging.root.handlers:
        handler.addFilter(wid_filter)

    logger = logging.getLogger('chunk-worker')
    logger = logging.LoggerAdapter(logger, {'worker_id': worker_id})

    stop_flag.unlink(missing_ok=True)

    def stop_requested():
        return _shutdown or stop_flag.exists()

    try:
        resp = requests.get(f'{api_url}/pipeline/queues/chunk/status', timeout=10)
        resp.raise_for_status()
        qlen = resp.json().get('queue_length', 0)
    except Exception as e:
        logger.error(f'Cannot reach API at {api_url}: {e}')
        sys.exit(1)

    logger.info(f'Starting: api={api_url} batch={batch_size} queue={qlen}')

    chunked_docs = 0
    chunks_created = 0
    embed_queued = 0
    failed = 0
    start_time = time.time()
    backoff = 5

    while not stop_requested():
        try:
            items, remaining = fetch_chunk_batch(api_url, batch_size, worker_id)
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
        embed_batch = []
        requeue_batch = []

        for item in items:
            if not isinstance(item, dict) or 'document_id' not in item:
                failed += 1
                continue

            doc_id = item['document_id']
            content = item.get('content', '')

            if not content:
                try:
                    doc_data = fetch_document_content(api_url, doc_id)
                    if doc_data and 'content' in doc_data:
                        content = doc_data['content']
                    elif doc_data and 'chunks' in doc_data:
                        content = '\n'.join(c.get('content', '') for c in doc_data['chunks'])
                except Exception as e:
                    logger.error(f'Failed to fetch content for doc {doc_id}: {e}')
                    failed += 1
                    continue

            if not content or len(content.strip()) < 20:
                logger.warning(f'Empty/too-short content for doc {doc_id}, skipping')
                failed += 1
                continue

            text_chunks = chunk_text(content)
            if not text_chunks:
                failed += 1
                continue

            chunks_data = []
            for idx, cc in enumerate(text_chunks):
                chunks_data.append({
                    'chunk_index': idx,
                    'content': cc,
                    'content_hash': hashlib.md5(cc.encode()).hexdigest(),
                })

            try:
                result = store_chunks(api_url, doc_id, chunks_data)
                stored_ids = result.get('chunk_ids', [])
                chunks_created += len(stored_ids)
                chunked_docs += 1

                for cid, cc in zip(stored_ids, text_chunks):
                    embed_batch.append({
                        'chunk_id': cid,
                        'content': cc[:2000],
                    })
            except Exception as e:
                logger.error(f'Store chunks failed for doc {doc_id}: {e}')
                requeue_batch.append(item)
                failed += 1

        if requeue_batch:
            try:
                requeue_items(api_url, requeue_batch)
                logger.info(f'Requeued {len(requeue_batch)} failed items')
            except Exception as e:
                logger.error(f'Requeue failed — {len(requeue_batch)} items lost: {e}')

        if embed_batch:
            try:
                enqueued = enqueue_for_embedding(api_url, embed_batch)
                embed_queued += enqueued
            except Exception as e:
                logger.error(f'Embed enqueue failed: {e}')

        elapsed = time.time() - start_time
        rate = chunked_docs / max(1, elapsed)
        logger.info(
            f'Docs: {chunked_docs} | Chunks: {chunks_created} | '
            f'Embed queued: {embed_queued} | Failed: {failed} | '
            f'Rate: {rate:.1f} docs/s | Queue: {remaining}'
        )

    elapsed = time.time() - start_time
    logger.info(
        f'Done: {chunked_docs} docs, {chunks_created} chunks, '
        f'{embed_queued} embed-queued, {failed} failed, {elapsed:.0f}s'
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='REST-only chunk worker')
    parser.add_argument('--api-url', default='http://localhost:5000')
    parser.add_argument('--batch', type=int, default=20)
    parser.add_argument('--worker-id', default='chunk-worker-unknown')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s [%(worker_id)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(Path.home() / 'chunk-worker-rest.log'),
        ],
    )

    run(args.api_url, args.batch, args.worker_id)
