"""
Redis-backed queue blueprint for the document processing pipeline.

Replaces PostgreSQL-based queue endpoints with Redis for atomic operations,
lower latency, and native support for sorted-set priority queues.

Data Structures
---------------
pipeline:{queue}:pending           ZSET    score = priority_band + timestamp_ms
pipeline:{queue}:processing        HASH    field = item_id, value = claimed_at ISO
pipeline:{queue}:completed_count   STRING  atomic counter (cumulative)
pipeline:{queue}:completed_set     SET     completed item IDs (for purge)
pipeline:{queue}:failed_count      STRING  atomic counter (terminal failures only)
pipeline:{queue}:dlq               LIST    dead-letter item IDs
pipeline:item:{item_id}            HASH    full item data
pipeline:idempotency:{key}         STRING  item_id, with TTL
pipeline:next_id                   STRING  atomic sequential counter

Priority Scoring
----------------
score = (10 - priority) * 10_000_000_000_000 + timestamp_ms

The multiplier (1e13) is deliberately chosen over the spec's 1e6 because
epoch-millisecond timestamps are ~1.7e12.  With 1e6 the timestamp would
completely dominate the priority component, making all priorities equivalent.
1e13 ensures priority always dominates while remaining within IEEE 754
double precision (15.9 significant digits).  This matches the existing
codebase convention in redis_atomic_operations.py, test-priority-formula.py,
migrate-pg-to-redis.py, and verify-redis-migration-fixes.py.

Endpoints (13 + 2 admin)
------------------------
 1. POST   /queue/add                          Add a single item
 2. GET    /queue/status                       Per-queue and aggregate counts
 3. POST   /queue/fetch/<queue_name>           Claim items (atomic ZPOPMIN)
 4. POST   /queue/complete                     Mark item completed (item_id in body)
 5. POST   /queue/fail                         Mark item failed (item_id in body)
 6. GET    /queue/item/<id>                    Item details
 7. POST   /queue/retry-failed/<queue_name>    Move DLQ items back to pending
 8. POST   /queue/purge/<queue_name>           Remove completed items
 9. POST   /queue/dequeue                      Batch dequeue (multi-queue)
10. POST   /queue/enqueue                      Batch enqueue (multi-item)
11. GET    /queue/metrics                      Prometheus-compatible metrics
12. POST   /queue/reclaim-stuck                Recover stuck processing items
13. POST   /queue/heartbeat                    Update processing heartbeat
"""

import json
import os
import time
import logging
from datetime import datetime, timezone

import redis
import redis.sentinel
from flask import Blueprint, request, jsonify, Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint -- named 'queue' for url_for() compatibility with existing
# PostgreSQL-backed queue_endpoints.py / queue_endpoints_with_ownership.py
# ---------------------------------------------------------------------------
queue_bp = Blueprint('queue', __name__, url_prefix='/queue')

# ---------------------------------------------------------------------------
# Redis connection (supports Sentinel or direct connection)
# ---------------------------------------------------------------------------
REDIS_HOST = os.environ.get('REDIS_HOST', 'aio-01')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_DB = int(os.environ.get('REDIS_DB', '0'))
REDIS_MAX_CONNECTIONS = int(os.environ.get('REDIS_MAX_CONNECTIONS', '50'))
# Comma-separated host:port pairs, e.g. "laptop-01:26379,aio-01:26379,server-01:26379"
REDIS_SENTINEL_HOSTS = os.environ.get('REDIS_SENTINEL_HOSTS', '')
REDIS_SENTINEL_SERVICE = os.environ.get('REDIS_SENTINEL_SERVICE', 'mymaster')

_pool = None
_sentinel = None


def _init_redis():
    """Initialize Redis connection pool (Sentinel or direct)."""
    global _pool, _sentinel

    if REDIS_SENTINEL_HOSTS:
        sentinels = []
        for hp in REDIS_SENTINEL_HOSTS.split(','):
            hp = hp.strip()
            if not hp:
                continue
            if ':' in hp:
                h, p = hp.rsplit(':', 1)
                sentinels.append((h, int(p)))
            else:
                sentinels.append((hp, 26379))
        if sentinels:
            _sentinel = redis.sentinel.Sentinel(
                sentinels,
                socket_timeout=5,
                socket_connect_timeout=5,
                decode_responses=True,
                db=REDIS_DB,
            )
            logger.info(
                'Redis Sentinel initialized with %d nodes', len(sentinels),
            )
            return

    _pool = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        max_connections=REDIS_MAX_CONNECTIONS,
        socket_connect_timeout=5,
        socket_timeout=10,
        retry_on_timeout=True,
    )
    logger.info(
        'Redis direct connection pool initialized (%s:%d, max=%d)',
        REDIS_HOST, REDIS_PORT, REDIS_MAX_CONNECTIONS,
    )


def get_redis():
    """Return a Redis client backed by Sentinel or the shared connection pool."""
    global _pool, _sentinel
    if _pool is None and _sentinel is None:
        _init_redis()
    if _sentinel is not None:
        return _sentinel.master_for(REDIS_SENTINEL_SERVICE)
    return redis.Redis(connection_pool=_pool)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VALID_QUEUES = ('store', 'chunk', 'embed', 'graph')
PIPELINE_ORDER = ('store', 'chunk', 'embed', 'graph')
PIPELINE_NEXT = {'store': 'chunk', 'chunk': 'embed', 'embed': 'graph'}
MAX_RETRIES_DEFAULT = 3
IDEMPOTENCY_TTL = 86400          # 24 hours (seconds)
COMPLETED_ITEM_TTL = 604800      # 7 days (seconds)
STUCK_THRESHOLD_SECONDS = 600    # 10 minutes
NEXT_ID_KEY = 'pipeline:next_id'

# Priority multiplier: 1e13 ensures priority always dominates over
# epoch-millisecond timestamps (~1.7e12).  All existing code in this
# project uses this value.
PRIORITY_MULTIPLIER = 10_000_000_000_000  # 1e13


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------
def _k_pending(q):
    return f'pipeline:{q}:pending'


def _k_processing(q):
    return f'pipeline:{q}:processing'


def _k_completed(q):
    return f'pipeline:{q}:completed_count'


def _k_completed_set(q):
    return f'pipeline:{q}:completed_set'


def _k_failed(q):
    return f'pipeline:{q}:failed_count'


def _k_dlq(q):
    return f'pipeline:{q}:dlq'


def _k_item(item_id):
    return f'pipeline:item:{item_id}'


def _k_idemp(key):
    return f'pipeline:idempotency:{key}'


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def _priority_score(priority, timestamp_ms=None):
    """Compute sorted-set score: lower score = higher priority + older item.

    Formula: (10 - priority) * 1e13 + timestamp_ms

    Priority 10 (highest) yields the smallest multiplier component (0),
    so items with higher priority get lower scores and are popped first
    by ZPOPMIN.  Within the same priority band, older items (smaller
    timestamp) sort first (FIFO).
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    return (10 - int(priority)) * PRIORITY_MULTIPLIER + timestamp_ms


def _now_iso():
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _now_ms():
    """Return the current time as integer milliseconds since epoch."""
    return int(time.time() * 1000)


def _validate_queue(queue_name):
    """Validate queue_name is one of the known pipeline stages.

    Returns (True, None) on success or (False, flask_response_tuple) on
    failure so callers can ``return err`` directly.
    """
    if queue_name in VALID_QUEUES:
        return True, None
    return False, (jsonify({
        'error': f'Invalid queue: {queue_name}',
        'valid_queues': list(VALID_QUEUES),
    }), 400)


def _next_queue(current):
    """Return the next pipeline stage, or None for the last stage."""
    return PIPELINE_NEXT.get(current)


def _format_item_response(raw):
    """Convert raw Redis hash data (all string values) to API response dict.

    Handles JSON-encoded sub-fields (data, chunk_ids) and numeric coercion.
    """
    if not raw:
        return None

    data = raw.get('data', '{}')
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            pass

    chunk_ids = raw.get('chunk_ids', '[]')
    if isinstance(chunk_ids, str):
        try:
            chunk_ids = json.loads(chunk_ids)
        except (json.JSONDecodeError, TypeError):
            chunk_ids = []

    def _int(val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    return {
        'id': raw.get('id', ''),
        'queue_name': raw.get('queue_name', ''),
        'data': data,
        'document_id': raw.get('document_id', ''),
        'chunk_ids': chunk_ids,
        'priority': _int(raw.get('priority'), 5),
        'status': raw.get('status', 'unknown'),
        'created_at': raw.get('created_at', ''),
        'updated_at': raw.get('updated_at', ''),
        'retries': _int(raw.get('retries')),
        'max_retries': _int(raw.get('max_retries'), MAX_RETRIES_DEFAULT),
        'worker_id': raw.get('worker_id', ''),
        'error': raw.get('error', ''),
    }


# ---------------------------------------------------------------------------
# Lua scripts
#
# All state-mutating operations use Lua scripts for atomicity.
# Scripts are registered lazily; redis-py handles EVALSHA/EVAL fallback
# transparently if the server flushes its script cache.
# ---------------------------------------------------------------------------

# -- ADD: Atomic enqueue with idempotency check ----------------------------
LUA_ADD = """
local idemp_key   = KEYS[1]
local pending_key = KEYS[2]
local next_id_key = KEYS[3]

local has_idemp   = tonumber(ARGV[1])
local idemp_ttl   = tonumber(ARGV[2])
local score       = tonumber(ARGV[3])
local queue_name  = ARGV[4]
local data        = ARGV[5]
local document_id = ARGV[6]
local chunk_ids   = ARGV[7]
local priority    = ARGV[8]
local created_at  = ARGV[9]
local max_retries = ARGV[10]
local idemp_val   = ARGV[11]

-- 1. Idempotency check (atomic with SET NX semantics)
if has_idemp == 1 then
    local existing = redis.call('GET', idemp_key)
    if existing then
        return cjson.encode({duplicate = true, existing_id = existing})
    end
end

-- 2. Generate sequential item ID
local item_id  = redis.call('INCR', next_id_key)
local item_key = 'pipeline:item:' .. item_id

-- 3. Store the full item hash
redis.call('HSET', item_key,
    'id',              tostring(item_id),
    'queue_name',      queue_name,
    'data',            data,
    'document_id',     document_id,
    'chunk_ids',       chunk_ids,
    'priority',        priority,
    'status',          'pending',
    'created_at',      created_at,
    'updated_at',      created_at,
    'retries',         '0',
    'max_retries',     max_retries,
    'worker_id',       '',
    'error',           '',
    'idempotency_key', idemp_val
)

-- 4. Add to priority sorted set (lower score = higher priority)
redis.call('ZADD', pending_key, score, tostring(item_id))

-- 5. Guard against duplicate submission
if has_idemp == 1 then
    redis.call('SET', idemp_key, tostring(item_id), 'EX', idemp_ttl)
end

return cjson.encode({duplicate = false, item_id = item_id})
"""

# -- FETCH: Atomic claim with full item data return -----------------------
# ZPOPMIN atomically removes the lowest-scored items.  For each popped
# item the script verifies the item hash still exists (guards against
# orphans from expired/deleted keys), marks it as processing, records
# the worker and timestamp, and returns the full item data -- all in
# one atomic operation, eliminating the TOCTOU race of a separate
# HGETALL after ZPOPMIN.
LUA_FETCH = """
local pending_key    = KEYS[1]
local processing_key = KEYS[2]

local limit     = tonumber(ARGV[1])
local worker_id = ARGV[2]
local now       = ARGV[3]

local raw = redis.call('ZPOPMIN', pending_key, limit)
local results  = {}
local orphaned = 0

for i = 1, #raw, 2 do
    local item_id  = raw[i]
    local item_key = 'pipeline:item:' .. item_id

    -- Guard: verify item hash still exists (prevents silent data loss
    -- if the key expired or was deleted between enqueue and claim)
    local exists = redis.call('EXISTS', item_key)
    if exists == 1 then
        -- Mark item as processing with worker assignment
        redis.call('HSET', item_key,
            'status',     'processing',
            'worker_id',  worker_id,
            'updated_at', now
        )
        -- Register in processing hash (value = claimed_at ISO for
        -- stuck-task detection via lexicographic comparison)
        redis.call('HSET', processing_key, item_id, now)

        -- Return full item data (avoids a second round-trip)
        local fields = redis.call('HGETALL', item_key)
        local item = {}
        for j = 1, #fields, 2 do
            item[fields[j]] = fields[j + 1]
        end
        table.insert(results, cjson.encode(item))
    else
        orphaned = orphaned + 1
    end
end

return cjson.encode({items = results, orphaned = orphaned})
"""

# -- COMPLETE: Atomic completion with worker ownership verification --------
# Verifies that the completing worker is the one that claimed the item,
# preserves worker_id in the item hash for audit trail, validates that
# the item belongs to the specified queue, and returns the full item
# data for pipeline chaining.
LUA_COMPLETE = """
local processing_key = KEYS[1]
local completed_key  = KEYS[2]
local completed_set  = KEYS[3]

local item_id    = ARGV[1]
local worker_id  = ARGV[2]
local now        = ARGV[3]
local force      = tonumber(ARGV[4])
local item_ttl   = tonumber(ARGV[5])
local queue_name = ARGV[6]

local item_key = 'pipeline:item:' .. item_id

-- 1. Verify item is in the processing hash
local claimed_at = redis.call('HGET', processing_key, item_id)
if not claimed_at then
    return cjson.encode({found = false, error = 'Item not in processing'})
end

-- 2. Validate item belongs to the specified queue
local actual_queue = redis.call('HGET', item_key, 'queue_name')
if actual_queue and actual_queue ~= queue_name then
    return cjson.encode({
        found = false,
        error = 'Item belongs to queue ' .. tostring(actual_queue) .. ', not ' .. queue_name
    })
end

-- 3. Verify worker ownership (unless force override)
if force ~= 1 then
    local actual_worker = redis.call('HGET', item_key, 'worker_id')
    if actual_worker and actual_worker ~= '' and actual_worker ~= worker_id then
        return cjson.encode({
            found = true,
            error = 'Worker mismatch',
            expected = actual_worker,
            got = worker_id
        })
    end
end

-- 4. Remove from processing hash
redis.call('HDEL', processing_key, item_id)

-- 5. Update item status (preserve worker_id for audit trail)
redis.call('HSET', item_key,
    'status',       'completed',
    'updated_at',   now,
    'completed_at', now
)

-- 6. Track in completed set (for efficient purge) and set TTL
redis.call('SADD', completed_set, item_id)
if item_ttl > 0 then
    redis.call('EXPIRE', item_key, item_ttl)
end

-- 7. Increment cumulative completed counter
redis.call('INCR', completed_key)

-- 8. Return full item data for pipeline chaining
local fields = redis.call('HGETALL', item_key)
local item = {}
for j = 1, #fields, 2 do
    item[fields[j]] = fields[j + 1]
end

return cjson.encode({found = true, item = item})
"""

# -- FAIL: Atomic failure with retry/DLQ logic ----------------------------
# Verifies worker ownership, reads priority from the item hash internally
# (no external read needed), and uses retries <= max_retries so that
# max_retries=3 yields 3 retry attempts (4 total processing attempts)
# before dead-lettering.
LUA_FAIL = """
local processing_key   = KEYS[1]
local pending_key      = KEYS[2]
local dlq_key          = KEYS[3]
local failed_count_key = KEYS[4]

local item_id       = ARGV[1]
local error_msg     = ARGV[2]
local max_retries   = tonumber(ARGV[3])
local no_retry      = tonumber(ARGV[4])
local now           = ARGV[5]
local priority_mult = tonumber(ARGV[6])
local now_ms        = tonumber(ARGV[7])
local worker_id     = ARGV[8]
local force         = tonumber(ARGV[9])
local queue_name    = ARGV[10]

local item_key = 'pipeline:item:' .. item_id

-- 1. Verify item is in the processing hash
local claimed_at = redis.call('HGET', processing_key, item_id)
if not claimed_at then
    return cjson.encode({found = false, retries = 0, will_retry = false})
end

-- 2. Validate item belongs to the specified queue
local actual_queue = redis.call('HGET', item_key, 'queue_name')
if actual_queue and actual_queue ~= queue_name then
    return cjson.encode({
        found = false,
        error = 'Item belongs to queue ' .. tostring(actual_queue) .. ', not ' .. queue_name
    })
end

-- 3. Verify worker ownership (unless force override)
if force ~= 1 then
    local actual_worker = redis.call('HGET', item_key, 'worker_id')
    if actual_worker and actual_worker ~= '' and actual_worker ~= worker_id then
        return cjson.encode({
            found = true,
            error = 'Worker mismatch',
            expected = actual_worker,
            got = worker_id
        })
    end
end

-- 4. Remove from processing hash
redis.call('HDEL', processing_key, item_id)

-- 5. Increment retry counter
local retries = tonumber(redis.call('HGET', item_key, 'retries') or '0')
retries = retries + 1

redis.call('HSET', item_key,
    'retries',    tostring(retries),
    'error',      error_msg,
    'updated_at', now
)

-- 6. Retry or dead-letter
-- retries <= max_retries: max_retries=3 yields 3 retry attempts before DLQ
if no_retry == 0 and retries <= max_retries then
    -- Re-enqueue: read priority from item hash (fully atomic, no TOCTOU)
    local priority = tonumber(redis.call('HGET', item_key, 'priority') or '5')
    local score = (10 - priority) * priority_mult + now_ms

    redis.call('HSET', item_key, 'status', 'pending', 'worker_id', '')
    redis.call('ZADD', pending_key, score, item_id)
    return cjson.encode({
        found = true, retries = retries,
        will_retry = true, status = 'pending'
    })
else
    -- Terminal failure: dead-letter
    redis.call('HSET', item_key, 'status', 'dead_letter')
    redis.call('LPUSH', dlq_key, item_id)
    -- failed_count tracks terminal failures only (not retries)
    redis.call('INCR', failed_count_key)
    return cjson.encode({
        found = true, retries = retries,
        will_retry = false, status = 'dead_letter'
    })
end
"""

# -- RETRY-FAILED: Move DLQ items back to pending -------------------------
LUA_RETRY_FAILED = """
local dlq_key          = KEYS[1]
local pending_key      = KEYS[2]
local failed_count_key = KEYS[3]

local now           = ARGV[1]
local base_ts       = tonumber(ARGV[2])
local priority_mult = tonumber(ARGV[3])

local count = 0
while true do
    local item_id = redis.call('RPOP', dlq_key)
    if not item_id then break end

    local item_key = 'pipeline:item:' .. item_id
    redis.call('HSET', item_key,
        'status',     'pending',
        'worker_id',  '',
        'error',      '',
        'retries',    '0',
        'updated_at', now
    )

    local priority = tonumber(redis.call('HGET', item_key, 'priority') or '5')
    local score    = (10 - priority) * priority_mult + base_ts
    redis.call('ZADD', pending_key, score, item_id)

    count = count + 1
end

-- Adjust failed counter (clamp to zero)
if count > 0 then
    local current = tonumber(redis.call('GET', failed_count_key) or '0')
    if current > count then
        redis.call('DECRBY', failed_count_key, count)
    else
        redis.call('SET', failed_count_key, '0')
    end
end

return count
"""

# -- RECLAIM: Recover stuck processing items -------------------------------
# Compares the claimed_at ISO timestamp in the processing hash against
# a threshold (ISO timestamps are lexicographically sortable in UTC).
LUA_RECLAIM = """
local processing_key = KEYS[1]
local pending_key    = KEYS[2]

local threshold_iso = ARGV[1]
local now           = ARGV[2]
local priority_mult = tonumber(ARGV[3])
local base_ts       = tonumber(ARGV[4])

local all = redis.call('HGETALL', processing_key)
local reclaimed = 0

for i = 1, #all, 2 do
    local item_id    = all[i]
    local claimed_at = all[i + 1]

    -- Lexicographic comparison works for ISO-8601 UTC timestamps
    if claimed_at < threshold_iso then
        local item_key = 'pipeline:item:' .. item_id
        local exists = redis.call('EXISTS', item_key)

        if exists == 1 then
            redis.call('HSET', item_key,
                'status',     'pending',
                'worker_id',  '',
                'updated_at', now
            )
            local priority = tonumber(redis.call('HGET', item_key, 'priority') or '5')
            local score = (10 - priority) * priority_mult + base_ts
            redis.call('ZADD', pending_key, score, item_id)
        end

        redis.call('HDEL', processing_key, item_id)
        reclaimed = reclaimed + 1
    end
end

return reclaimed
"""

# -- PURGE: Remove completed items -----------------------------------------
LUA_PURGE = """
local completed_set = KEYS[1]
local completed_key = KEYS[2]

local members = redis.call('SMEMBERS', completed_set)
local count = 0

for _, item_id in ipairs(members) do
    local item_key = 'pipeline:item:' .. item_id
    redis.call('DEL', item_key)
    count = count + 1
end

if count > 0 then
    redis.call('DEL', completed_set)
end

redis.call('SET', completed_key, '0')

return count
"""

# -- HEARTBEAT: Atomic timestamp update with ownership check ---------------
LUA_HEARTBEAT = """
local processing_key = KEYS[1]

local worker_id = ARGV[1]
local now       = ARGV[2]

local updated = 0
for i = 3, #ARGV do
    local item_id = ARGV[i]
    local claimed = redis.call('HEXISTS', processing_key, item_id)
    if claimed == 1 then
        local item_key = 'pipeline:item:' .. item_id
        local actual_worker = redis.call('HGET', item_key, 'worker_id')
        if actual_worker == worker_id then
            redis.call('HSET', processing_key, item_id, now)
            redis.call('HSET', item_key, 'updated_at', now)
            updated = updated + 1
        end
    end
end

return updated
"""

# ---------------------------------------------------------------------------
# Script registration cache
# ---------------------------------------------------------------------------
_scripts = {}


def _get_script(name, source):
    """Lazily register a Lua script and return the cached Script object.

    The returned Script object supports a ``client`` keyword argument so
    that Sentinel failover is handled correctly: always pass the current
    Redis client when calling the script.
    """
    if name not in _scripts:
        r = get_redis()
        _scripts[name] = r.register_script(source)
    return _scripts[name]


# ===================================================================
# ENDPOINT  1 -- POST /queue/add
# ===================================================================
@queue_bp.route('/add', methods=['POST'])
def add_item():
    """Add a single item to a named queue.

    Request body::

        {
            "queue":           "store",       # store|chunk|embed|graph
            "data":            { ... },       # arbitrary payload
            "document_id":     "doc-123",     # optional
            "chunk_ids":       [1, 2, 3],     # optional
            "priority":        7,             # 1 (lowest) - 10 (highest)
            "idempotency_key": "abc-xyz",     # optional dedup guard
            "max_retries":     3              # optional, default 3
        }

    Returns 201 on success, 409 on duplicate idempotency key.
    """
    try:
        body = request.get_json(force=True) or {}
        queue_name = body.get('queue', 'store')

        valid, err = _validate_queue(queue_name)
        if not valid:
            return err

        data = body.get('data', {})
        document_id = body.get('document_id', '')
        chunk_ids = body.get('chunk_ids', [])
        priority = max(1, min(10, int(body.get('priority', 5))))
        idempotency_key = body.get('idempotency_key', '')
        max_retries = int(body.get('max_retries', MAX_RETRIES_DEFAULT))

        now_iso = _now_iso()
        ts_ms = _now_ms()
        score = _priority_score(priority, ts_ms)

        r = get_redis()
        script = _get_script('add', LUA_ADD)

        has_idemp = 1 if idempotency_key else 0
        idemp_redis_key = (
            _k_idemp(idempotency_key) if idempotency_key
            else 'pipeline:idempotency:__none__'
        )

        result_raw = script(
            keys=[idemp_redis_key, _k_pending(queue_name), NEXT_ID_KEY],
            args=[
                has_idemp,
                IDEMPOTENCY_TTL,
                score,
                queue_name,
                json.dumps(data) if isinstance(data, (dict, list)) else str(data),
                str(document_id),
                json.dumps(chunk_ids) if isinstance(chunk_ids, list) else str(chunk_ids),
                str(priority),
                now_iso,
                str(max_retries),
                idempotency_key or '',
            ],
            client=r,
        )

        parsed = json.loads(result_raw)

        if parsed.get('duplicate'):
            existing_id = parsed['existing_id']
            logger.info(
                'Duplicate idempotency_key=%s, existing item=%s',
                idempotency_key, existing_id,
            )
            return jsonify({
                'error': 'Duplicate idempotency key',
                'existing_queue_id': existing_id,
                'idempotency_key': idempotency_key,
            }), 409

        item_id = str(parsed['item_id'])
        logger.info(
            'Added item %s to queue %s (priority=%d)',
            item_id, queue_name, priority,
        )

        return jsonify({
            'queue_id': item_id,
            'queue_name': queue_name,
            'priority': priority,
            'created_at': now_iso,
        }), 201

    except redis.RedisError as e:
        logger.error('Redis error in add_item: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500
    except Exception as e:
        logger.error('Error in add_item: %s', e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# ENDPOINT  2 -- GET /queue/status
# ===================================================================
@queue_bp.route('/status', methods=['GET'])
def queue_status():
    """Return per-queue and aggregate counts.

    ``failed`` reports the current DLQ size (actionable items).
    ``completed`` is cumulative throughput.  Use the /queue/metrics
    endpoint for Prometheus counters.

    Response::

        {
            "queues": [
                {"queue_name": "store", "pending": 4, "processing": 1,
                 "completed": 12, "failed": 0, "total": 17},
                ...
            ],
            "totals": {"pending": ..., "processing": ..., ...}
        }
    """
    try:
        r = get_redis()
        pipe = r.pipeline(transaction=False)

        for q in VALID_QUEUES:
            pipe.zcard(_k_pending(q))       # pending  (sorted-set cardinality)
            pipe.hlen(_k_processing(q))     # processing  (hash length)
            pipe.get(_k_completed(q))       # completed counter (cumulative)
            pipe.llen(_k_dlq(q))            # dead-letter list length

        values = pipe.execute()

        queues = []
        totals = {
            'pending': 0, 'processing': 0,
            'completed': 0, 'failed': 0, 'total': 0,
        }

        for i, q in enumerate(VALID_QUEUES):
            off = i * 4
            pending    = values[off] or 0
            processing = values[off + 1] or 0
            completed  = int(values[off + 2] or 0)
            dlq_len    = values[off + 3] or 0

            # Use DLQ length only (not failed_count) to avoid double-counting.
            # failed_count is a cumulative terminal failure counter used in
            # Prometheus metrics; DLQ length is the current actionable backlog.
            total = pending + processing + completed + dlq_len

            queues.append({
                'queue_name': q,
                'pending':    pending,
                'processing': processing,
                'completed':  completed,
                'failed':     dlq_len,
                'total':      total,
            })

            totals['pending']    += pending
            totals['processing'] += processing
            totals['completed']  += completed
            totals['failed']     += dlq_len
            totals['total']      += total

        return jsonify({'queues': queues, 'totals': totals})

    except redis.RedisError as e:
        logger.error('Redis error in queue_status: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500


# ===================================================================
# ENDPOINT  3 -- POST /queue/fetch/<queue_name>
# ===================================================================
@queue_bp.route('/fetch/<queue_name>', methods=['POST'])
def fetch_items(queue_name):
    """Atomically claim the next *limit* highest-priority items from the
    queue for the given worker.

    The entire claim is executed inside a Lua script: ZPOPMIN, item-hash
    update, processing-hash registration, and full-item-data retrieval
    all happen in one atomic operation.  No TOCTOU race is possible.

    Request body::

        {"limit": 5, "worker_id": "worker-3"}

    Returns the claimed items or 204 if the queue is empty.
    """
    valid, err = _validate_queue(queue_name)
    if not valid:
        return err

    try:
        body = request.get_json(force=True) or {}
        limit = max(1, min(50, int(body.get('limit', 1))))
        worker_id = body.get('worker_id', 'unknown')

        r = get_redis()
        script = _get_script('fetch', LUA_FETCH)

        now_iso = _now_iso()
        result_raw = script(
            keys=[_k_pending(queue_name), _k_processing(queue_name)],
            args=[limit, worker_id, now_iso],
            client=r,
        )

        parsed = json.loads(result_raw)
        orphaned = parsed.get('orphaned', 0)
        if orphaned > 0:
            logger.warning(
                'Skipped %d orphaned items in queue %s (missing item keys)',
                orphaned, queue_name,
            )

        raw_items = parsed.get('items', [])
        if not raw_items:
            return '', 204

        items = []
        for raw_json in raw_items:
            item_data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            items.append(_format_item_response(item_data))

        logger.info(
            'Worker %s fetched %d items from %s',
            worker_id, len(items), queue_name,
        )

        return jsonify({
            'items': items,
            'count': len(items),
            'queue_name': queue_name,
        })

    except redis.RedisError as e:
        logger.error('Redis error in fetch_items: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500
    except Exception as e:
        logger.error('Error in fetch_items: %s', e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# ENDPOINT  4 -- POST /queue/complete
# ===================================================================
@queue_bp.route('/complete', methods=['POST'])
def complete_item():
    """Mark an item as completed and optionally chain to the next pipeline stage.

    Worker ownership is verified atomically inside the Lua script.
    The worker_id is preserved on the completed item for audit trail.

    The item's queue is looked up from its stored data — no need to
    specify it in the URL.

    Request body::

        {
            "item_id":       "42",         # required
            "worker_id":     "worker-3",   # required
            "force":         false,         # bypass ownership check
            "chain":         true,          # auto-enqueue to next stage
            "data":          { ... },       # override data for next stage
            "document_id":   "doc-123",     # override for next stage
            "chunk_ids":     [4, 5],        # override for next stage
            "next_priority": 7              # override priority for next stage
        }
    """
    try:
        body = request.get_json(force=True) or {}
        item_id = str(body.get('item_id', ''))
        if not item_id:
            return jsonify({'error': 'item_id is required'}), 400

        r = get_redis()
        queue_name = r.hget(_k_item(item_id), 'queue_name')
        if not queue_name:
            return jsonify({'error': f'Item {item_id} not found'}), 404

        valid, err = _validate_queue(queue_name)
        if not valid:
            return err

        worker_id = body.get('worker_id', 'unknown')
        force = 1 if body.get('force', False) else 0
        chain = body.get('chain', True)
        next_priority = body.get('next_priority')
        chain_data = body.get('data')
        chain_document_id = body.get('document_id')
        chain_chunk_ids = body.get('chunk_ids')

        r = get_redis()
        script = _get_script('complete', LUA_COMPLETE)

        now_iso = _now_iso()
        result_raw = script(
            keys=[
                _k_processing(queue_name),
                _k_completed(queue_name),
                _k_completed_set(queue_name),
            ],
            args=[item_id, worker_id, now_iso, force,
                  COMPLETED_ITEM_TTL, queue_name],
            client=r,
        )

        parsed = json.loads(result_raw)

        if not parsed.get('found'):
            return jsonify({
                'error': parsed.get('error', 'Item not found in processing'),
            }), 404

        if 'expected' in parsed:
            return jsonify({
                'error': 'Worker ownership mismatch',
                'expected_worker': parsed['expected'],
                'actual_worker': parsed['got'],
            }), 403

        logger.info(
            'Item %s completed in queue %s by worker %s',
            item_id, queue_name, worker_id,
        )

        result = {
            'item_id': item_id,
            'queue_name': queue_name,
            'status': 'completed',
        }

        # Pipeline chaining to next stage
        next_q = _next_queue(queue_name) if chain else None
        if next_q:
            completed_item = parsed.get('item', {})

            # Determine chained item fields (caller overrides > completed item)
            c_data = chain_data
            if c_data is None:
                raw_data = completed_item.get('data', '{}')
                c_data = (json.loads(raw_data) if isinstance(raw_data, str)
                          else raw_data)

            c_doc_id = chain_document_id or completed_item.get('document_id', '')
            c_priority = next_priority or int(completed_item.get('priority', 5))

            c_cids = chain_chunk_ids
            if c_cids is None:
                raw_cids = completed_item.get('chunk_ids', '[]')
                c_cids = (json.loads(raw_cids) if isinstance(raw_cids, str)
                          else raw_cids)

            ts_ms = _now_ms()
            score = _priority_score(c_priority, ts_ms)
            add_script = _get_script('add', LUA_ADD)

            chain_raw = add_script(
                keys=[
                    'pipeline:idempotency:__none__',
                    _k_pending(next_q),
                    NEXT_ID_KEY,
                ],
                args=[
                    0,  # no idempotency for chained items
                    IDEMPOTENCY_TTL,
                    score,
                    next_q,
                    json.dumps(c_data) if isinstance(c_data, (dict, list)) else str(c_data),
                    str(c_doc_id),
                    json.dumps(c_cids) if isinstance(c_cids, list) else str(c_cids),
                    str(c_priority),
                    now_iso,
                    str(MAX_RETRIES_DEFAULT),
                    '',
                ],
                client=r,
            )
            chain_parsed = json.loads(chain_raw)
            result['chained_to'] = {
                'queue': next_q,
                'item_id': str(chain_parsed.get('item_id', '')),
            }

            logger.info(
                'Chained item %s from %s to %s (new id=%s)',
                item_id, queue_name, next_q,
                chain_parsed.get('item_id', ''),
            )

        return jsonify(result)

    except redis.RedisError as e:
        logger.error('Redis error in complete_item: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500
    except Exception as e:
        logger.error('Error in complete_item: %s', e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# ENDPOINT  5 -- POST /queue/fail
# ===================================================================
@queue_bp.route('/fail', methods=['POST'])
def fail_item():
    """Mark an item as failed with optional retry or DLQ routing.

    Worker ownership is verified atomically.  The priority for
    re-enqueue scoring is read from the item hash inside the Lua
    script (no external read, no TOCTOU race).

    With max_retries=3, the item gets 3 retry attempts (4 total
    processing attempts) before being dead-lettered.

    Request body::

        {
            "item_id":     "42",           # required
            "worker_id":   "worker-3",     # required
            "error":       "timeout",      # error description
            "no_retry":    false,          # skip retries, go straight to DLQ
            "force":       false,          # bypass ownership check
            "max_retries": 3               # override default
        }
    """
    try:
        body = request.get_json(force=True) or {}
        item_id = str(body.get('item_id', ''))
        if not item_id:
            return jsonify({'error': 'item_id is required'}), 400

        r = get_redis()
        queue_name = r.hget(_k_item(item_id), 'queue_name')
        if not queue_name:
            return jsonify({'error': f'Item {item_id} not found'}), 404

        valid, err = _validate_queue(queue_name)
        if not valid:
            return err

        error_msg = body.get('error', 'Unknown error')
        no_retry = 1 if body.get('no_retry', False) else 0
        worker_id = body.get('worker_id', 'unknown')
        force = 1 if body.get('force', False) else 0
        max_retries = int(body.get('max_retries', MAX_RETRIES_DEFAULT))

        r = get_redis()
        script = _get_script('fail', LUA_FAIL)
        now_iso = _now_iso()
        now_ms = _now_ms()

        result_raw = script(
            keys=[
                _k_processing(queue_name),
                _k_pending(queue_name),
                _k_dlq(queue_name),
                _k_failed(queue_name),
            ],
            args=[
                item_id, error_msg, max_retries, no_retry,
                now_iso, PRIORITY_MULTIPLIER, now_ms,
                worker_id, force, queue_name,
            ],
            client=r,
        )

        parsed = json.loads(result_raw)

        if not parsed.get('found'):
            err_msg = parsed.get('error', 'Item not found in processing')
            return jsonify({'error': err_msg}), 404

        if 'expected' in parsed:
            return jsonify({
                'error': 'Worker ownership mismatch',
                'expected_worker': parsed['expected'],
                'actual_worker': parsed['got'],
            }), 403

        logger.info(
            'Item %s failed in queue %s (retries=%d, will_retry=%s)',
            item_id, queue_name,
            parsed.get('retries', 0), parsed.get('will_retry', False),
        )

        return jsonify({
            'item_id': item_id,
            'queue_name': queue_name,
            'retries': parsed.get('retries', 0),
            'max_retries': max_retries,
            'will_retry': parsed.get('will_retry', False),
            'status': parsed.get('status', 'unknown'),
        })

    except redis.RedisError as e:
        logger.error('Redis error in fail_item: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500
    except Exception as e:
        logger.error('Error in fail_item: %s', e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# ENDPOINT  6 -- GET /queue/item/<item_id>
# ===================================================================
@queue_bp.route('/item/<item_id>', methods=['GET'])
def get_item(item_id):
    """Return full details for a specific item."""
    try:
        r = get_redis()
        raw = r.hgetall(_k_item(item_id))

        if not raw:
            return jsonify({'error': f'Item {item_id} not found'}), 404

        return jsonify(_format_item_response(raw))

    except redis.RedisError as e:
        logger.error('Redis error in get_item: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500


# ===================================================================
# ENDPOINT  7 -- POST /queue/retry-failed/<queue_name>
# ===================================================================
@queue_bp.route('/retry-failed/<queue_name>', methods=['POST'])
def retry_failed(queue_name):
    """Move all DLQ items back to pending for retry.

    Resets retry counters to zero and recomputes priority scores
    from each item's original priority value.
    """
    valid, err = _validate_queue(queue_name)
    if not valid:
        return err

    try:
        r = get_redis()
        script = _get_script('retry_failed', LUA_RETRY_FAILED)

        now_iso = _now_iso()
        base_ts = _now_ms()

        count = script(
            keys=[
                _k_dlq(queue_name),
                _k_pending(queue_name),
                _k_failed(queue_name),
            ],
            args=[now_iso, base_ts, PRIORITY_MULTIPLIER],
            client=r,
        )

        logger.info('Retried %d failed items in queue %s', count, queue_name)

        return jsonify({
            'queue_name': queue_name,
            'retried_count': int(count),
        })

    except redis.RedisError as e:
        logger.error('Redis error in retry_failed: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500


# ===================================================================
# ENDPOINT  8 -- POST /queue/purge/<queue_name>
# ===================================================================
@queue_bp.route('/purge/<queue_name>', methods=['POST'])
def purge_completed(queue_name):
    """Remove all completed items from a queue.

    Deletes the item hashes and clears the completed set/counter.
    """
    valid, err = _validate_queue(queue_name)
    if not valid:
        return err

    try:
        r = get_redis()
        script = _get_script('purge', LUA_PURGE)

        count = script(
            keys=[
                _k_completed_set(queue_name),
                _k_completed(queue_name),
            ],
            args=[],
            client=r,
        )

        logger.info('Purged %d completed items from queue %s', count, queue_name)

        return jsonify({
            'queue_name': queue_name,
            'purged_count': int(count),
        })

    except redis.RedisError as e:
        logger.error('Redis error in purge_completed: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500


# ===================================================================
# ENDPOINT  9 -- POST /queue/dequeue
# ===================================================================
@queue_bp.route('/dequeue', methods=['POST'])
def batch_dequeue():
    """Dequeue items from one or more queues in a single request.

    Request body::

        {
            "queues": [
                {"queue_name": "store", "limit": 5},
                {"queue_name": "chunk", "limit": 3}
            ],
            "worker_id": "worker-3"
        }
    """
    try:
        body = request.get_json(force=True) or {}
        queue_requests = body.get('queues', [])
        worker_id = body.get('worker_id', 'unknown')

        if not queue_requests:
            return jsonify({'error': 'No queues specified'}), 400

        r = get_redis()
        script = _get_script('fetch', LUA_FETCH)
        now_iso = _now_iso()

        results = {}
        total_count = 0

        for qr in queue_requests:
            qname = qr.get('queue_name', '')
            valid, _ = _validate_queue(qname)
            if not valid:
                results[qname] = {
                    'error': f'Invalid queue: {qname}',
                    'items': [],
                    'count': 0,
                }
                continue

            limit = max(1, min(50, int(qr.get('limit', 1))))
            result_raw = script(
                keys=[_k_pending(qname), _k_processing(qname)],
                args=[limit, worker_id, now_iso],
                client=r,
            )

            parsed = json.loads(result_raw)
            raw_items = parsed.get('items', [])
            items = []
            for raw_json in raw_items:
                item_data = (json.loads(raw_json)
                             if isinstance(raw_json, str) else raw_json)
                items.append(_format_item_response(item_data))

            results[qname] = {'items': items, 'count': len(items)}
            total_count += len(items)

        return jsonify({
            'results': results,
            'total_count': total_count,
            'worker_id': worker_id,
        })

    except redis.RedisError as e:
        logger.error('Redis error in batch_dequeue: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500
    except Exception as e:
        logger.error('Error in batch_dequeue: %s', e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# ENDPOINT 10 -- POST /queue/enqueue
# ===================================================================
@queue_bp.route('/enqueue', methods=['POST'])
def batch_enqueue():
    """Enqueue multiple items in a single request.

    Request body::

        {
            "items": [
                {"queue": "store", "data": {...}, "priority": 7},
                {"queue": "store", "data": {...}, "priority": 5}
            ]
        }
    """
    try:
        body = request.get_json(force=True) or {}
        items = body.get('items', [])

        if not items:
            return jsonify({'error': 'No items provided'}), 400

        r = get_redis()
        script = _get_script('add', LUA_ADD)
        now_iso = _now_iso()

        results = []
        errors = []

        for idx, item in enumerate(items):
            queue_name = item.get('queue', 'store')
            valid, _ = _validate_queue(queue_name)
            if not valid:
                errors.append({
                    'index': idx,
                    'error': f'Invalid queue: {queue_name}',
                })
                continue

            data = item.get('data', {})
            document_id = item.get('document_id', '')
            chunk_ids = item.get('chunk_ids', [])
            priority = max(1, min(10, int(item.get('priority', 5))))
            idempotency_key = item.get('idempotency_key', '')
            max_retries = int(item.get('max_retries', MAX_RETRIES_DEFAULT))

            ts_ms = _now_ms()
            score = _priority_score(priority, ts_ms)

            has_idemp = 1 if idempotency_key else 0
            idemp_redis_key = (
                _k_idemp(idempotency_key) if idempotency_key
                else 'pipeline:idempotency:__none__'
            )

            try:
                result_raw = script(
                    keys=[idemp_redis_key, _k_pending(queue_name), NEXT_ID_KEY],
                    args=[
                        has_idemp, IDEMPOTENCY_TTL, score, queue_name,
                        json.dumps(data) if isinstance(data, (dict, list))
                        else str(data),
                        str(document_id),
                        json.dumps(chunk_ids) if isinstance(chunk_ids, list)
                        else str(chunk_ids),
                        str(priority), now_iso, str(max_retries),
                        idempotency_key or '',
                    ],
                    client=r,
                )
                parsed = json.loads(result_raw)

                if parsed.get('duplicate'):
                    results.append({
                        'index': idx,
                        'duplicate': True,
                        'existing_queue_id': parsed['existing_id'],
                    })
                else:
                    results.append({
                        'index': idx,
                        'queue_id': str(parsed['item_id']),
                        'queue_name': queue_name,
                        'priority': priority,
                    })
            except Exception as item_err:
                errors.append({'index': idx, 'error': str(item_err)})

        return jsonify({
            'enqueued': results,
            'errors': errors,
            'total_enqueued': len(
                [r for r in results if not r.get('duplicate')]
            ),
            'total_duplicates': len(
                [r for r in results if r.get('duplicate')]
            ),
            'total_errors': len(errors),
        }), 201

    except redis.RedisError as e:
        logger.error('Redis error in batch_enqueue: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500
    except Exception as e:
        logger.error('Error in batch_enqueue: %s', e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# ENDPOINT 11 -- POST /queue/complete (batch)
# ===================================================================
@queue_bp.route('/complete', methods=['POST'])
def batch_complete():
    """Complete multiple items in a single request.

    Request body::

        {
            "items": [
                {"item_id": "1"},
                {"item_id": "2"}
            ],
            "worker_id": "worker-3",
            "chain": true,
            "force": false
        }
    """
    try:
        body = request.get_json(force=True) or {}
        items = body.get('items', [])
        worker_id = body.get('worker_id', 'unknown')
        chain = body.get('chain', True)
        force = 1 if body.get('force', False) else 0

        if not items:
            return jsonify({'error': 'No items provided'}), 400

        r = get_redis()
        complete_script = _get_script('complete', LUA_COMPLETE)
        add_script = _get_script('add', LUA_ADD)
        now_iso = _now_iso()

        results = []
        errors = []

        for item_spec in items:
            iid = str(item_spec.get('item_id', ''))

            qname = r.hget(_k_item(iid), 'queue_name')
            if not qname:
                errors.append({
                    'item_id': iid,
                    'error': f'Item {iid} not found',
                })
                continue

            valid, _ = _validate_queue(qname)
            if not valid:
                errors.append({
                    'item_id': iid,
                    'error': f'Invalid queue: {qname}',
                })
                continue

            try:
                result_raw = complete_script(
                    keys=[
                        _k_processing(qname),
                        _k_completed(qname),
                        _k_completed_set(qname),
                    ],
                    args=[iid, worker_id, now_iso, force,
                          COMPLETED_ITEM_TTL, qname],
                    client=r,
                )
                parsed = json.loads(result_raw)

                if not parsed.get('found'):
                    errors.append({
                        'item_id': iid,
                        'error': parsed.get('error', 'Not found in processing'),
                    })
                    continue

                if 'expected' in parsed:
                    errors.append({
                        'item_id': iid,
                        'error': (
                            f'Worker mismatch: expected {parsed["expected"]}'
                        ),
                    })
                    continue

                entry = {
                    'item_id': iid,
                    'queue_name': qname,
                    'status': 'completed',
                }

                # Pipeline chaining
                next_q = _next_queue(qname) if chain else None
                if next_q:
                    completed_item = parsed.get('item', {})
                    ts_ms = _now_ms()
                    p = int(completed_item.get('priority', 5))
                    score = _priority_score(p, ts_ms)

                    data_str = completed_item.get('data', '{}')
                    cids_str = completed_item.get('chunk_ids', '[]')

                    chain_raw = add_script(
                        keys=[
                            'pipeline:idempotency:__none__',
                            _k_pending(next_q),
                            NEXT_ID_KEY,
                        ],
                        args=[
                            0, IDEMPOTENCY_TTL, score, next_q,
                            data_str,
                            completed_item.get('document_id', ''),
                            cids_str,
                            str(p), now_iso, str(MAX_RETRIES_DEFAULT), '',
                        ],
                        client=r,
                    )
                    chain_parsed = json.loads(chain_raw)
                    entry['chained_to'] = {
                        'queue': next_q,
                        'item_id': str(chain_parsed.get('item_id', '')),
                    }

                results.append(entry)

            except Exception as item_err:
                errors.append({'item_id': iid, 'error': str(item_err)})

        return jsonify({
            'completed': results,
            'errors': errors,
            'total_completed': len(results),
            'total_errors': len(errors),
        })

    except redis.RedisError as e:
        logger.error('Redis error in batch_complete: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500
    except Exception as e:
        logger.error('Error in batch_complete: %s', e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# ENDPOINT 12 -- POST /queue/fail (batch)
# ===================================================================
@queue_bp.route('/fail', methods=['POST'])
def batch_fail():
    """Fail multiple items in a single request.

    Request body::

        {
            "items": [
                {"item_id": "1", "error": "timeout"},
                {"item_id": "2", "error": "parse error"}
            ],
            "worker_id": "worker-3",
            "force": false
        }
    """
    try:
        body = request.get_json(force=True) or {}
        items = body.get('items', [])
        worker_id = body.get('worker_id', 'unknown')
        force = 1 if body.get('force', False) else 0

        if not items:
            return jsonify({'error': 'No items provided'}), 400

        r = get_redis()
        fail_script = _get_script('fail', LUA_FAIL)
        now_iso = _now_iso()
        now_ms = _now_ms()

        results = []
        errors = []

        for item_spec in items:
            iid = str(item_spec.get('item_id', ''))
            error_msg = item_spec.get('error', 'Unknown error')
            no_retry = 1 if item_spec.get('no_retry', False) else 0
            max_retries = int(
                item_spec.get('max_retries', MAX_RETRIES_DEFAULT)
            )

            qname = r.hget(_k_item(iid), 'queue_name')
            if not qname:
                errors.append({
                    'item_id': iid,
                    'error': f'Item {iid} not found',
                })
                continue

            valid, _ = _validate_queue(qname)
            if not valid:
                errors.append({
                    'item_id': iid,
                    'error': f'Invalid queue: {qname}',
                })
                continue

            try:
                result_raw = fail_script(
                    keys=[
                        _k_processing(qname),
                        _k_pending(qname),
                        _k_dlq(qname),
                        _k_failed(qname),
                    ],
                    args=[
                        iid, error_msg, max_retries, no_retry,
                        now_iso, PRIORITY_MULTIPLIER, now_ms,
                        worker_id, force, qname,
                    ],
                    client=r,
                )
                parsed = json.loads(result_raw)

                if not parsed.get('found'):
                    err_detail = parsed.get('error', 'Not found in processing')
                    errors.append({'item_id': iid, 'error': err_detail})
                    continue

                if 'expected' in parsed:
                    errors.append({
                        'item_id': iid,
                        'error': (
                            f'Worker mismatch: expected {parsed["expected"]}'
                        ),
                    })
                    continue

                results.append({
                    'item_id': iid,
                    'queue_name': qname,
                    'retries': parsed.get('retries', 0),
                    'will_retry': parsed.get('will_retry', False),
                    'status': parsed.get('status', 'unknown'),
                })

            except Exception as item_err:
                errors.append({'item_id': iid, 'error': str(item_err)})

        return jsonify({
            'failed': results,
            'errors': errors,
            'total_failed': len(results),
            'total_errors': len(errors),
        })

    except redis.RedisError as e:
        logger.error('Redis error in batch_fail: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500
    except Exception as e:
        logger.error('Error in batch_fail: %s', e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# ENDPOINT 13 -- GET /queue/metrics
# ===================================================================
@queue_bp.route('/metrics', methods=['GET'])
def queue_metrics():
    """Return Prometheus-compatible metrics for all queues.

    Exposes gauges for pending, processing, and DLQ sizes, and
    cumulative counters for completed and terminal-failure totals.
    """
    try:
        r = get_redis()
        pipe = r.pipeline(transaction=False)

        for q in VALID_QUEUES:
            pipe.zcard(_k_pending(q))
            pipe.hlen(_k_processing(q))
            pipe.get(_k_completed(q))
            pipe.get(_k_failed(q))
            pipe.llen(_k_dlq(q))

        values = pipe.execute()

        lines = [
            '# HELP pipeline_queue_pending '
            'Number of items waiting to be processed',
            '# TYPE pipeline_queue_pending gauge',
        ]
        for i, q in enumerate(VALID_QUEUES):
            off = i * 5
            lines.append(
                f'pipeline_queue_pending{{queue="{q}"}} {values[off] or 0}'
            )

        lines.extend([
            '# HELP pipeline_queue_processing '
            'Number of items currently being processed',
            '# TYPE pipeline_queue_processing gauge',
        ])
        for i, q in enumerate(VALID_QUEUES):
            off = i * 5
            lines.append(
                f'pipeline_queue_processing{{queue="{q}"}} '
                f'{values[off + 1] or 0}'
            )

        lines.extend([
            '# HELP pipeline_queue_completed_total '
            'Cumulative number of completed items',
            '# TYPE pipeline_queue_completed_total counter',
        ])
        for i, q in enumerate(VALID_QUEUES):
            off = i * 5
            lines.append(
                f'pipeline_queue_completed_total{{queue="{q}"}} '
                f'{int(values[off + 2] or 0)}'
            )

        lines.extend([
            '# HELP pipeline_queue_failed_total '
            'Cumulative number of terminally failed items',
            '# TYPE pipeline_queue_failed_total counter',
        ])
        for i, q in enumerate(VALID_QUEUES):
            off = i * 5
            lines.append(
                f'pipeline_queue_failed_total{{queue="{q}"}} '
                f'{int(values[off + 3] or 0)}'
            )

        lines.extend([
            '# HELP pipeline_queue_dlq '
            'Number of items in dead letter queue',
            '# TYPE pipeline_queue_dlq gauge',
        ])
        for i, q in enumerate(VALID_QUEUES):
            off = i * 5
            lines.append(
                f'pipeline_queue_dlq{{queue="{q}"}} {values[off + 4] or 0}'
            )

        lines.append('')  # trailing newline

        return Response(
            '\n'.join(lines),
            mimetype='text/plain; version=0.0.4; charset=utf-8',
        )

    except redis.RedisError as e:
        logger.error('Redis error in queue_metrics: %s', e)
        return Response(
            '# Error collecting metrics\n',
            status=500,
            mimetype='text/plain',
        )


# ===================================================================
# ADMIN: POST /queue/reclaim-stuck
# ===================================================================
@queue_bp.route('/reclaim-stuck', methods=['POST'])
def reclaim_stuck():
    """Recover items stuck in processing state beyond the threshold.

    Items whose processing-hash timestamp is older than
    ``threshold_seconds`` are moved back to pending with their original
    priority.  This handles worker crashes where items were claimed
    via ZPOPMIN but never completed or failed.

    Request body (optional)::

        {"threshold_seconds": 600, "queue_name": "store"}

    If queue_name is omitted, all queues are checked.
    """
    try:
        body = request.get_json(force=True) or {}
        threshold = int(body.get('threshold_seconds', STUCK_THRESHOLD_SECONDS))
        target_queue = body.get('queue_name')

        queues = [target_queue] if target_queue else list(VALID_QUEUES)
        if target_queue:
            valid, err = _validate_queue(target_queue)
            if not valid:
                return err

        r = get_redis()
        script = _get_script('reclaim', LUA_RECLAIM)

        now = datetime.now(timezone.utc)
        threshold_dt = datetime.fromtimestamp(
            now.timestamp() - threshold, tz=timezone.utc,
        )
        threshold_iso = threshold_dt.isoformat()
        now_iso = now.isoformat()
        base_ts = _now_ms()

        total_reclaimed = 0
        per_queue = {}

        for q in queues:
            count = script(
                keys=[_k_processing(q), _k_pending(q)],
                args=[threshold_iso, now_iso, PRIORITY_MULTIPLIER, base_ts],
                client=r,
            )
            per_queue[q] = int(count)
            total_reclaimed += int(count)

        logger.info(
            'Reclaimed %d stuck items across %d queues',
            total_reclaimed, len(queues),
        )

        return jsonify({
            'total_reclaimed': total_reclaimed,
            'per_queue': per_queue,
            'threshold_seconds': threshold,
        })

    except redis.RedisError as e:
        logger.error('Redis error in reclaim_stuck: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500


# ===================================================================
# ADMIN: POST /queue/heartbeat
# ===================================================================
@queue_bp.route('/heartbeat', methods=['POST'])
def update_heartbeat():
    """Update the processing timestamp for items a worker is still working on.

    Call this periodically to prevent items from being reclaimed by the
    stuck-task recovery mechanism.  Worker ownership is verified
    atomically inside the Lua script.

    Request body::

        {
            "queue_name": "store",
            "item_ids": ["1", "2", "3"],
            "worker_id": "worker-3"
        }
    """
    try:
        body = request.get_json(force=True) or {}
        queue_name = body.get('queue_name', '')
        item_ids = body.get('item_ids', [])
        worker_id = body.get('worker_id', 'unknown')

        valid, err = _validate_queue(queue_name)
        if not valid:
            return err

        if not item_ids:
            return jsonify({'error': 'No item_ids provided'}), 400

        r = get_redis()
        script = _get_script('heartbeat', LUA_HEARTBEAT)
        now_iso = _now_iso()

        # Pass item_ids as ARGV[3..N] to the Lua script
        updated = script(
            keys=[_k_processing(queue_name)],
            args=[worker_id, now_iso] + [str(iid) for iid in item_ids],
            client=r,
        )

        return jsonify({
            'queue_name': queue_name,
            'updated': int(updated),
            'total_requested': len(item_ids),
        })

    except redis.RedisError as e:
        logger.error('Redis error in update_heartbeat: %s', e)
        return jsonify({'error': 'Queue service unavailable'}), 500

