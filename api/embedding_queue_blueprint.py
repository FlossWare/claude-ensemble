"""Embedding Queue Blueprint

REST API wrapper for the Redis embedding_queue LIST.
Workers fetch chunks, embed locally, and store embeddings via these endpoints.
No direct Redis or PostgreSQL connections from workers.
"""

import json
import logging
import re
import threading

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
import redis
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

embedding_queue_bp = Blueprint('embedding_queue', __name__)

QUEUE_KEY = 'embedding_queue'
MAX_STORE_BATCH = 500
MAX_ENQUEUE_BATCH = 1000

_db_pool = None
_redis_client = None
_init_lock = threading.Lock()


def _sanitize_worker_id(raw):
    return re.sub(r'[\x00-\x1f\x7f]', '', str(raw))[:64]


def get_redis():
    global _redis_client
    if _redis_client is None:
        with _init_lock:
            if _redis_client is None:
                _redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
    return _redis_client


def get_db_connection():
    global _db_pool
    if _db_pool is None:
        with _init_lock:
            if _db_pool is None:
                _db_pool = ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    host='aio-01',
                    port=5433,
                    database='learning',
                    user='claude'
                )
    return _db_pool.getconn()


def release_db_connection(conn):
    global _db_pool
    if _db_pool:
        _db_pool.putconn(conn)


@embedding_queue_bp.route('/fetch', methods=['POST'])
def fetch_items():
    """Fetch a batch of items from the embedding queue.

    Request: {"count": 50, "worker_id": "cabin-laptop-01"}
    Response: {"items": [{"chunk_id": 123, "content": "..."}, ...], "fetched": 50, "remaining": 2900000}
    """
    data = request.get_json(silent=True) or {}
    count = min(data.get('count', 1), 100)
    worker_id = _sanitize_worker_id(data.get('worker_id', 'unknown'))

    try:
        r = get_redis()
        pipe = r.pipeline()
        for _ in range(count):
            pipe.lpop(QUEUE_KEY)
        raw_items = pipe.execute()
    except redis.RedisError as e:
        logger.error(f'Redis error in fetch: {e}')
        return jsonify({'error': 'Queue unavailable'}), 503

    items = []
    for raw in raw_items:
        if raw is None:
            break
        try:
            item = json.loads(raw) if isinstance(raw, str) else raw
            items.append(item)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f'Skipping malformed queue item: {str(raw)[:100]}')

    try:
        remaining = r.llen(QUEUE_KEY)
    except redis.RedisError:
        remaining = -1

    if items:
        logger.info(f'Worker {worker_id} fetched {len(items)} items, {remaining} remaining')

    return jsonify({
        'items': items,
        'fetched': len(items),
        'remaining': remaining,
    })


@embedding_queue_bp.route('/store-embeddings', methods=['POST'])
def store_embeddings():
    """Store computed embeddings for chunks.

    Request: {
        "embeddings": [
            {"chunk_id": 123, "embedding": [0.1, 0.2, ...], "model": "all-mpnet-base-v2", "provider": "local-cpu"},
            ...
        ],
        "worker_id": "cabin-laptop-01"
    }
    Response: {"stored": 50, "errors": 0}
    """
    data = request.get_json()
    if not data or 'embeddings' not in data:
        return jsonify({'error': 'Missing embeddings'}), 400

    embeddings_list = data['embeddings']
    if len(embeddings_list) > MAX_STORE_BATCH:
        return jsonify({'error': f'Max {MAX_STORE_BATCH} per batch'}), 400

    worker_id = _sanitize_worker_id(data.get('worker_id', 'unknown'))
    stored = 0
    errors = 0

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        for item in embeddings_list:
            chunk_id = item.get('chunk_id')
            embedding = item.get('embedding')
            model = item.get('model', 'all-mpnet-base-v2')
            provider = item.get('provider', 'local-cpu')

            if not chunk_id or not embedding:
                errors += 1
                continue

            if not all(isinstance(x, (int, float)) for x in embedding):
                errors += 1
                continue

            try:
                cur.execute('SAVEPOINT embed_sp')
                vec_str = '[' + ','.join(str(x) for x in embedding) + ']'
                cur.execute(
                    """INSERT INTO knowledge.embeddings (chunk_id, embedding, model, provider, created_at)
                       VALUES (%s, %s::vector, %s, %s, NOW())
                       ON CONFLICT (chunk_id) DO UPDATE SET
                         embedding = EXCLUDED.embedding,
                         model = EXCLUDED.model,
                         provider = EXCLUDED.provider,
                         created_at = NOW()""",
                    (chunk_id, vec_str, model, provider)
                )
                cur.execute('RELEASE SAVEPOINT embed_sp')
                stored += 1
            except Exception as e:
                logger.warning(f'Failed to store embedding for chunk {chunk_id}: {e}')
                cur.execute('ROLLBACK TO SAVEPOINT embed_sp')
                errors += 1

        conn.commit()
    finally:
        release_db_connection(conn)

    logger.info(f'Worker {worker_id} stored {stored} embeddings, {errors} errors')
    return jsonify({'stored': stored, 'errors': errors})


@embedding_queue_bp.route('/requeue', methods=['POST'])
def requeue_items():
    """Re-queue items that failed embedding (push back to queue tail).

    Request: {"items": [{"chunk_id": 123, "content": "..."}, ...]}
    """
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': 'Missing items'}), 400

    try:
        r = get_redis()
        pipe = r.pipeline()
        for item in data['items']:
            pipe.rpush(QUEUE_KEY, json.dumps(item))
        pipe.execute()
    except redis.RedisError as e:
        logger.error(f'Redis error in requeue: {e}')
        return jsonify({'error': 'Queue unavailable'}), 503

    return jsonify({'requeued': len(data['items'])})


@embedding_queue_bp.route('/status', methods=['GET'])
def queue_status():
    """Get embedding queue status.

    Response: {"queue_length": 2900000, "queue_key": "embedding_queue"}
    """
    try:
        r = get_redis()
        length = r.llen(QUEUE_KEY)
    except redis.RedisError as e:
        logger.error(f'Redis error in status: {e}')
        return jsonify({'error': 'Queue unavailable'}), 503

    return jsonify({
        'queue_length': length,
        'queue_key': QUEUE_KEY,
    })


@embedding_queue_bp.route('/enqueue', methods=['POST'])
def enqueue_chunks():
    """Enqueue chunks for embedding (used by rechunker).

    Request: {"chunks": [{"chunk_id": 123, "content": "text..."}, ...]}
    Response: {"enqueued": 50}
    """
    data = request.get_json()
    if not data or 'chunks' not in data:
        return jsonify({'error': 'Missing chunks'}), 400

    chunks = data['chunks']
    if len(chunks) > MAX_ENQUEUE_BATCH:
        return jsonify({'error': f'Max {MAX_ENQUEUE_BATCH} per batch'}), 400

    try:
        r = get_redis()
        pipe = r.pipeline()
        for chunk in chunks:
            pipe.rpush(QUEUE_KEY, json.dumps(chunk))
        pipe.execute()
    except redis.RedisError as e:
        logger.error(f'Redis error in enqueue: {e}')
        return jsonify({'error': 'Queue unavailable'}), 503

    return jsonify({'enqueued': len(chunks)})
