#!/usr/bin/env python3
"""Rechunk worker — processes all docs, rechunks at 512 tokens, queues for embedding via REST API.

Runs on aio-01 (controller). Uses direct PostgreSQL for heavy batch operations
(read docs, delete/insert chunks) and REST API for embedding queue enqueue.

Usage:
    python3 rechunk-worker-rest.py
    python3 rechunk-worker-rest.py --api-url http://localhost:5000 --batch 100
"""
import argparse
import hashlib
import json
import sys
import time

import psycopg2
import requests

CHUNK_SIZE = 512
CHUNK_OVERLAP_RATIO = 0.37
CHARS_PER_TOKEN = 4


def chunk_text(text, chunk_size=CHUNK_SIZE):
    if not text or not text.strip():
        return []
    chunk_chars = chunk_size * CHARS_PER_TOKEN
    overlap_chars = int(chunk_chars * CHUNK_OVERLAP_RATIO)
    step = max(chunk_chars - overlap_chars, 100)
    chunks = []
    for i in range(0, len(text), step):
        chunk = text[i:i + chunk_chars]
        if len(chunk.strip()) < 50:
            continue
        chunks.append(chunk)
    return chunks if chunks else [text[:chunk_chars]] if text.strip() else []


def enqueue_for_embedding(api_url, chunks_to_queue):
    """Enqueue chunks for embedding via REST API instead of direct Redis."""
    if not chunks_to_queue:
        return 0
    resp = requests.post(
        f'{api_url}/pipeline/embedding-queue/enqueue',
        json={'chunks': chunks_to_queue},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get('enqueued', 0)


def main():
    parser = argparse.ArgumentParser(description='Rechunk worker with REST queue')
    parser.add_argument('--api-url', default='http://localhost:5000')
    parser.add_argument('--batch', type=int, default=50)
    parser.add_argument('--db-host', default='localhost')
    parser.add_argument('--db-port', type=int, default=5433)
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=args.db_host, port=args.db_port,
        dbname='learning', user='sfloess',
    )
    conn.autocommit = False
    cur = conn.cursor()

    offset = 0
    processed = 0
    queued = 0
    errors = 0
    start = time.time()

    print(f'Starting rechunk at {CHUNK_SIZE} tokens ({CHUNK_SIZE * CHARS_PER_TOKEN} chars)')

    while True:
        cur.execute(
            'SELECT id, title, content FROM knowledge.documents ORDER BY id LIMIT %s OFFSET %s',
            (args.batch, offset),
        )
        rows = cur.fetchall()
        if not rows:
            break

        queue_batch = []
        for doc_id, title, content in rows:
            if not content or len(content.strip()) < 20:
                continue
            try:
                cur.execute(
                    'DELETE FROM knowledge.embeddings WHERE chunk_id IN '
                    '(SELECT id FROM knowledge.chunks WHERE document_id = %s)',
                    (doc_id,),
                )
                cur.execute('DELETE FROM knowledge.chunks WHERE document_id = %s', (doc_id,))

                new_chunks = chunk_text(content)
                for idx, cc in enumerate(new_chunks):
                    cur.execute(
                        "INSERT INTO knowledge.chunks (document_id, chunk_index, content, content_hash, tsv) "
                        "VALUES (%s, %s, %s, %s, to_tsvector('english', %s)) RETURNING id",
                        (doc_id, idx, cc, hashlib.md5(cc.encode()).hexdigest(), cc),
                    )
                    cid = cur.fetchone()[0]
                    queue_batch.append({'chunk_id': cid, 'content': cc[:2000]})

                conn.commit()
                processed += 1
            except Exception as e:
                conn.rollback()
                errors += 1
                print(f'  Error doc {doc_id}: {e}', file=sys.stderr)

        if queue_batch:
            try:
                enqueued = enqueue_for_embedding(args.api_url, queue_batch)
                queued += enqueued
            except Exception as e:
                print(f'  Enqueue failed: {e}', file=sys.stderr)
                errors += len(queue_batch)

        offset += args.batch
        elapsed = time.time() - start
        rate = processed / elapsed if elapsed > 0 else 0
        print(f'  Processed: {processed} | Queued: {queued} | Errors: {errors} | Rate: {rate:.1f}/s | Doc: {title or doc_id}')
        sys.stdout.flush()

    elapsed = time.time() - start
    print(f'\nDone! Processed {processed} docs, queued {queued} chunks, {errors} errors in {elapsed:.0f}s')
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
