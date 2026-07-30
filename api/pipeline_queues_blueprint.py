"""Pipeline Queue Endpoints Blueprint

Unified REST API for all three pipeline Redis queues:
  - ingest:documents  (scrapers → ingest workers)
  - chunk:documents   (ingest workers → chunk workers)
  - embed:documents   (chunk workers → embed workers)

Workers fetch items, process locally, store results via REST API,
and push to the next queue. Zero direct Redis or PostgreSQL connections.

Replaces the embedding-queue-only endpoints in pipeline.py with a
generic queue interface supporting all pipeline stages.
"""

import json
import logging
import re

import redis
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

pipeline_queues_bp = Blueprint('pipeline_queues', __name__)

QUEUE_KEYS = {
    'ingest': 'ingest:documents',
    'chunk': 'chunk:documents',
    'embed': 'embed:documents',
}

VALID_QUEUES = set(QUEUE_KEYS.keys())
MAX_FETCH = 100
MAX_ENQUEUE = 1000

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
    return _redis_client


def _sanitize(raw):
    return re.sub(r'[\x00-\x1f\x7f]', '', str(raw))[:64]


def _resolve_queue(queue_name):
    if queue_name not in VALID_QUEUES:
        return None
    return QUEUE_KEYS[queue_name]


@pipeline_queues_bp.route('/stats', methods=['GET'])
def all_queue_stats():
    """Return depths for all pipeline queues.

    Response: {"ingest": 0, "chunk": 0, "embed": 0, "total": 0}
    """
    try:
        r = _get_redis()
        stats = {}
        for name, key in QUEUE_KEYS.items():
            stats[name] = r.llen(key)
        stats['total'] = sum(stats.values())
    except redis.RedisError as e:
        logger.error(f'Redis error in queue stats: {e}')
        return jsonify({'error': 'Redis unavailable'}), 503

    return jsonify(stats)


@pipeline_queues_bp.route('/<queue_name>/fetch', methods=['POST'])
def fetch_items(queue_name):
    """Fetch a batch of items from a pipeline queue (atomic lpop).

    POST /pipeline/queues/<ingest|chunk|embed>/fetch
    Body: {"count": 50, "worker_id": "server-01-w1"}
    Response: {"items": [...], "fetched": N, "remaining": M}
    """
    queue_key = _resolve_queue(queue_name)
    if queue_key is None:
        return jsonify({'error': f'Unknown queue: {queue_name}', 'valid': list(VALID_QUEUES)}), 400

    data = request.get_json(silent=True) or {}
    count = min(data.get('count', 1), MAX_FETCH)
    worker_id = _sanitize(data.get('worker_id', 'unknown'))

    try:
        r = _get_redis()
        pipe = r.pipeline()
        for _ in range(count):
            pipe.lpop(queue_key)
        raw_items = pipe.execute()
    except redis.RedisError as e:
        logger.error(f'Redis error fetching from {queue_key}: {e}')
        return jsonify({'error': 'Queue unavailable'}), 503

    items = []
    for raw in raw_items:
        if raw is None:
            break
        try:
            items.append(json.loads(raw) if isinstance(raw, str) else raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f'Skipping malformed item in {queue_key}: {str(raw)[:100]}')

    try:
        remaining = r.llen(queue_key)
    except redis.RedisError:
        remaining = -1

    if items:
        logger.info(f'{worker_id} fetched {len(items)} from {queue_key}, {remaining} remaining')

    return jsonify({'items': items, 'fetched': len(items), 'remaining': remaining})


@pipeline_queues_bp.route('/<queue_name>/enqueue', methods=['POST'])
def enqueue_items(queue_name):
    """Push items onto a pipeline queue (rpush to tail).

    POST /pipeline/queues/<ingest|chunk|embed>/enqueue
    Body: {"items": [{"document_id": 123, ...}, ...]}
    Response: {"enqueued": N}
    """
    queue_key = _resolve_queue(queue_name)
    if queue_key is None:
        return jsonify({'error': f'Unknown queue: {queue_name}', 'valid': list(VALID_QUEUES)}), 400

    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': 'Missing items'}), 400

    items = data['items']
    if len(items) > MAX_ENQUEUE:
        return jsonify({'error': f'Max {MAX_ENQUEUE} per batch'}), 400

    if not all(isinstance(item, dict) for item in items):
        return jsonify({'error': 'All items must be JSON objects'}), 400

    try:
        r = _get_redis()
        pipe = r.pipeline()
        for item in items:
            pipe.rpush(queue_key, json.dumps(item))
        pipe.execute()
    except redis.RedisError as e:
        logger.error(f'Redis error enqueuing to {queue_key}: {e}')
        return jsonify({'error': 'Queue unavailable'}), 503

    return jsonify({'enqueued': len(items)})


@pipeline_queues_bp.route('/<queue_name>/requeue', methods=['POST'])
def requeue_items(queue_name):
    """Re-queue failed items (push back to tail).

    POST /pipeline/queues/<ingest|chunk|embed>/requeue
    Body: {"items": [...]}
    Response: {"requeued": N}
    """
    queue_key = _resolve_queue(queue_name)
    if queue_key is None:
        return jsonify({'error': f'Unknown queue: {queue_name}', 'valid': list(VALID_QUEUES)}), 400

    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': 'Missing items'}), 400

    try:
        r = _get_redis()
        pipe = r.pipeline()
        for item in data['items']:
            pipe.rpush(queue_key, json.dumps(item))
        pipe.execute()
    except redis.RedisError as e:
        logger.error(f'Redis error requeuing to {queue_key}: {e}')
        return jsonify({'error': 'Queue unavailable'}), 503

    return jsonify({'requeued': len(data['items'])})


@pipeline_queues_bp.route('/<queue_name>/status', methods=['GET'])
def queue_status(queue_name):
    """Get status for a specific queue.

    GET /pipeline/queues/<ingest|chunk|embed>/status
    Response: {"queue_length": N, "queue_key": "ingest:documents"}
    """
    queue_key = _resolve_queue(queue_name)
    if queue_key is None:
        return jsonify({'error': f'Unknown queue: {queue_name}', 'valid': list(VALID_QUEUES)}), 400

    try:
        r = _get_redis()
        length = r.llen(queue_key)
    except redis.RedisError as e:
        logger.error(f'Redis error checking {queue_key}: {e}')
        return jsonify({'error': 'Queue unavailable'}), 503

    return jsonify({'queue_length': length, 'queue_key': queue_key})


@pipeline_queues_bp.route('/<queue_name>/clear', methods=['POST'])
def clear_queue(queue_name):
    """Clear all items from a queue (destructive).

    POST /pipeline/queues/<ingest|chunk|embed>/clear
    Response: {"cleared": N, "queue_key": "..."}
    """
    queue_key = _resolve_queue(queue_name)
    if queue_key is None:
        return jsonify({'error': f'Unknown queue: {queue_name}', 'valid': list(VALID_QUEUES)}), 400

    try:
        r = _get_redis()
        length = r.llen(queue_key)
        r.delete(queue_key)
    except redis.RedisError as e:
        logger.error(f'Redis error clearing {queue_key}: {e}')
        return jsonify({'error': 'Queue unavailable'}), 503

    logger.warning(f'Cleared {length} items from {queue_key}')
    return jsonify({'cleared': length, 'queue_key': queue_key})
