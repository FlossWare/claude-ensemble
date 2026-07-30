"""
Flask Blueprint for Contextual Retrieval pipeline endpoints.

Register this blueprint on the aio-01 REST API to provide server-side
coordination of contextual retrieval jobs running on fleet workers.

Endpoints
---------
POST /pipeline/contextual-retrieval/start    Start a batch contextual retrieval job
GET  /pipeline/contextual-retrieval/status   Check progress and statistics
POST /pipeline/contextual-retrieval/stop     Stop a running job

The actual LLM processing runs on fleet workers via ``contextual_retrieval.py``.
This blueprint provides:
  - Job coordination (start/stop, prevent duplicate runs)
  - Progress tracking (chunks processed, succeeded, failed)
  - Chunk queries (find chunks without context prefixes)
  - Content update (update chunk text and invalidate embeddings)

Database: All access via the app's shared DB cursor (PostgreSQL / pgvector).
"""

import logging
import threading
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

contextual_retrieval_bp = Blueprint(
    'contextual_retrieval',
    __name__,
    url_prefix='/pipeline/contextual-retrieval',
)

# ---------------------------------------------------------------------------
# In-memory job state (single controller pattern, no persistence needed)
# ---------------------------------------------------------------------------

_job_lock = threading.Lock()
_active_job = None  # Dict with job metadata when running, None otherwise


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Endpoint: POST /pipeline/contextual-retrieval/start
# ---------------------------------------------------------------------------

@contextual_retrieval_bp.route('/start', methods=['POST'])
def start_job():
    """Start a contextual retrieval batch job.

    This does NOT run LLM inference on aio-01 (controller only).  It sets
    the job state to 'running' so that fleet workers polling the status
    endpoint know they should start processing.

    Request body (all optional)::

        {
            "batch_size": 100,
            "model": "google/gemma-4-26b-a4b-it:free",
            "requested_by": "user"
        }
    """
    global _active_job

    with _job_lock:
        if _active_job and _active_job.get('status') == 'running':
            return jsonify({
                'error': 'A contextual retrieval job is already running',
                'job': _active_job,
            }), 409

        body = request.get_json(silent=True) or {}

        _active_job = {
            'status': 'running',
            'started_at': _now_iso(),
            'batch_size': body.get('batch_size', 100),
            'model': body.get('model', 'google/gemma-4-26b-a4b-it:free'),
            'requested_by': body.get('requested_by', 'api'),
            'workers': {},
            'stats': {
                'total_processed': 0,
                'total_succeeded': 0,
                'total_failed': 0,
                'total_skipped': 0,
            },
        }

    logger.info(
        'Contextual retrieval job started (batch=%d, model=%s)',
        _active_job['batch_size'], _active_job['model'],
    )

    return jsonify({
        'status': 'started',
        'job': _active_job,
    }), 201


# ---------------------------------------------------------------------------
# Endpoint: GET /pipeline/contextual-retrieval/status
# ---------------------------------------------------------------------------

@contextual_retrieval_bp.route('/status', methods=['GET'])
def get_status():
    """Return current job status and chunk statistics.

    If include_db_stats=true (default), also queries the database for
    counts of contextualized vs non-contextualized chunks.
    """
    include_db = request.args.get('include_db_stats', 'true').lower() == 'true'

    # Bug fix #1: Read _active_job under lock to prevent race conditions
    with _job_lock:
        job_snapshot = _active_job.copy() if _active_job else None

    result = {
        'job': job_snapshot,
        'timestamp': _now_iso(),
    }

    if include_db:
        try:
            from app.shared.db import get_cursor
            with get_cursor(dict_cursor=False) as cur:
                # Total chunks
                cur.execute('SELECT COUNT(*) FROM knowledge.chunks')
                total = cur.fetchone()[0]

                # Chunks with context prefix
                cur.execute(
                    "SELECT COUNT(*) FROM knowledge.chunks "
                    "WHERE content LIKE '[CTX]%%'"
                )
                contextualized = cur.fetchone()[0]

                # Chunks without context prefix
                without_context = total - contextualized

                # Chunks needing re-embedding (have context but no embedding)
                cur.execute("""
                    SELECT COUNT(*)
                    FROM knowledge.chunks c
                    WHERE c.content LIKE '[CTX]%%'
                      AND NOT EXISTS (
                          SELECT 1 FROM knowledge.embeddings e
                          WHERE e.chunk_id = c.id
                      )
                """)
                pending_reembed = cur.fetchone()[0]

                result['db_stats'] = {
                    'total_chunks': total,
                    'contextualized': contextualized,
                    'without_context': without_context,
                    'pending_reembedding': pending_reembed,
                    'progress_pct': round(
                        (contextualized / max(total, 1)) * 100, 2
                    ),
                }
        except Exception as e:
            logger.warning('Failed to fetch DB stats: %s', e)
            result['db_stats'] = {'error': 'Failed to retrieve database statistics'}

    return jsonify(result)


# ---------------------------------------------------------------------------
# Endpoint: POST /pipeline/contextual-retrieval/stop
# ---------------------------------------------------------------------------

@contextual_retrieval_bp.route('/stop', methods=['POST'])
def stop_job():
    """Stop the current contextual retrieval job.

    Workers polling the status endpoint will see status='stopped' and
    cease processing.
    """
    global _active_job

    with _job_lock:
        if not _active_job or _active_job.get('status') != 'running':
            return jsonify({
                'error': 'No running job to stop',
                'job': _active_job,
            }), 404

        _active_job['status'] = 'stopped'
        _active_job['stopped_at'] = _now_iso()

    logger.info('Contextual retrieval job stopped')

    return jsonify({
        'status': 'stopped',
        'job': _active_job,
    })


# ---------------------------------------------------------------------------
# Endpoint: POST /pipeline/contextual-retrieval/report
#
# Workers call this to report their progress.
# ---------------------------------------------------------------------------

@contextual_retrieval_bp.route('/report', methods=['POST'])
def report_progress():
    """Accept a progress report from a fleet worker.

    Request body::

        {
            "worker_id": "ctx-server-01-12345",
            "processed": 50,
            "succeeded": 48,
            "failed": 2,
            "skipped": 5
        }
    """
    body = request.get_json(silent=True) or {}
    worker_id = body.get('worker_id', 'unknown')

    with _job_lock:
        if _active_job is None:
            return jsonify({'error': 'No active job'}), 404

        _active_job['workers'][worker_id] = {
            'last_report': _now_iso(),
            'processed': body.get('processed', 0),
            'succeeded': body.get('succeeded', 0),
            'failed': body.get('failed', 0),
            'skipped': body.get('skipped', 0),
        }

        # Recalculate totals from all workers
        stats = _active_job['stats']
        stats['total_processed'] = sum(
            w['processed'] for w in _active_job['workers'].values()
        )
        stats['total_succeeded'] = sum(
            w['succeeded'] for w in _active_job['workers'].values()
        )
        stats['total_failed'] = sum(
            w['failed'] for w in _active_job['workers'].values()
        )
        stats['total_skipped'] = sum(
            w['skipped'] for w in _active_job['workers'].values()
        )

    return jsonify({'status': 'ok', 'stats': stats})


# ---------------------------------------------------------------------------
# Endpoint: GET /knowledge/chunks/without-context
#
# Used by contextual_retrieval.py to find chunks that need processing.
# ---------------------------------------------------------------------------

@contextual_retrieval_bp.route(
    '/chunks/without-context',
    methods=['GET'],
)
def get_chunks_without_context():
    """Fetch chunks that do not have a contextual prefix.

    Also returns parent document title and excerpt for context generation.

    Query params:
        limit (int):  Max chunks to return (default 100)
        offset (int): Chunk ID offset for pagination (default 0)
    """
    limit = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))

    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("""
                SELECT c.id AS chunk_id,
                       c.content,
                       c.document_id,
                       c.chunk_index,
                       d.title,
                       LEFT(d.content, 500) AS doc_excerpt
                FROM knowledge.chunks c
                JOIN knowledge.documents d ON d.id = c.document_id
                WHERE c.content IS NOT NULL
                  AND c.content != ''
                  AND c.content NOT LIKE '[CTX]%%'
                  AND c.id > %s
                ORDER BY c.id
                LIMIT %s
            """, (offset, limit))
            rows = cur.fetchall()

        items = []
        for row in rows:
            items.append({
                'chunk_id': row[0],
                'content': row[1],
                'document_id': row[2],
                'chunk_index': row[3],
                'title': row[4],
                'doc_excerpt': row[5],
            })

        return jsonify({'count': len(items), 'items': items})

    except Exception as e:
        logger.exception('Error fetching chunks without context')
        return jsonify({'error': 'Internal server error while fetching chunks'}), 500


# ---------------------------------------------------------------------------
# Endpoint: POST /knowledge/chunks/update-content
#
# Updates chunk content and optionally invalidates its embedding.
# ---------------------------------------------------------------------------

@contextual_retrieval_bp.route(
    '/chunks/update-content',
    methods=['POST'],
)
def update_chunk_content():
    """Update a chunk's text content and optionally invalidate its embedding.

    Request body::

        {
            "chunk_id": 12345,
            "content": "[CTX] This chunk is from ... \\n\\nOriginal content ...",
            "invalidate_embedding": true
        }
    """
    body = request.get_json(silent=True) or {}
    chunk_id = body.get('chunk_id')
    content = body.get('content')
    invalidate = body.get('invalidate_embedding', False)

    if not chunk_id or content is None:
        return jsonify({'error': 'chunk_id and content are required'}), 400

    # Bug fix #7: Validate content has [CTX] marker and reasonable length
    ctx_marker = '[CTX]'
    if not content.startswith(ctx_marker):
        return jsonify({
            'error': 'Content must start with the [CTX] context marker',
        }), 400

    max_content_length = 100_000  # ~100KB sanity limit
    if len(content) > max_content_length:
        return jsonify({
            'error': f'Content exceeds maximum length of {max_content_length} characters',
        }), 400

    if len(content.strip()) < 10:
        return jsonify({'error': 'Content is too short'}), 400

    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            # Bug fix #2: Combine content update and tsvector regeneration
            # into a single statement for atomicity, then handle embedding
            # invalidation in the same transaction block.
            cur.execute(
                "UPDATE knowledge.chunks "
                "SET content = %s, tsv = to_tsvector('english', %s) "
                "WHERE id = %s",
                (content, content, chunk_id),
            )
            updated = cur.rowcount

            if updated == 0:
                return jsonify({'error': f'Chunk {chunk_id} not found'}), 404

            # Invalidate embedding so it gets re-generated
            if invalidate:
                cur.execute(
                    'DELETE FROM knowledge.embeddings WHERE chunk_id = %s',
                    (chunk_id,),
                )

        return jsonify({
            'status': 'updated',
            'chunk_id': chunk_id,
            'embedding_invalidated': invalidate,
        })

    except Exception as e:
        logger.exception('Error updating chunk %s', chunk_id)
        # Bug fix #4: Return generic error message, details are logged above
        return jsonify({'error': 'Internal server error while updating chunk'}), 500


# ---------------------------------------------------------------------------
# Endpoint: POST /knowledge/embeddings/invalidate
#
# Deletes embeddings for specified chunks so they get re-embedded.
# ---------------------------------------------------------------------------

@contextual_retrieval_bp.route(
    '/embeddings/invalidate',
    methods=['POST'],
)
def invalidate_embeddings():
    """Delete embeddings for specified chunks, forcing re-embedding.

    Request body::

        {"chunk_ids": [1, 2, 3]}
    """
    body = request.get_json(silent=True) or {}
    chunk_ids = body.get('chunk_ids', [])

    if not chunk_ids:
        return jsonify({'error': 'chunk_ids required'}), 400

    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute(
                'DELETE FROM knowledge.embeddings WHERE chunk_id = ANY(%s)',
                (chunk_ids,),
            )
            deleted = cur.rowcount

        return jsonify({
            'status': 'invalidated',
            'deleted': deleted,
            'chunk_ids': chunk_ids,
        })

    except Exception as e:
        logger.exception('Error invalidating embeddings')
        return jsonify({'error': 'Internal server error while invalidating embeddings'}), 500


# ---------------------------------------------------------------------------
# Endpoint: GET /knowledge/document/<doc_id>
#
# Returns document metadata for context generation.
# ---------------------------------------------------------------------------

@contextual_retrieval_bp.route(
    '/document/<int:doc_id>',
    methods=['GET'],
)
def get_document(doc_id):
    """Fetch a single document's metadata (title, first 500 chars of content)."""
    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("""
                SELECT id, title, url, category, LEFT(content, 500) AS excerpt
                FROM knowledge.documents
                WHERE id = %s
            """, (doc_id,))
            row = cur.fetchone()

        if not row:
            return jsonify({'error': f'Document {doc_id} not found'}), 404

        return jsonify({
            'id': row[0],
            'title': row[1],
            'url': row[2],
            'category': row[3],
            'content': row[4],
        })

    except Exception as e:
        logger.exception('Error fetching document %s', doc_id)
        return jsonify({'error': 'Internal server error while fetching document'}), 500


# ---------------------------------------------------------------------------
# Endpoint: POST /knowledge/documents/batch
#
# Batch document info for efficient context generation.
# ---------------------------------------------------------------------------

@contextual_retrieval_bp.route(
    '/documents/batch',
    methods=['POST'],
)
def get_documents_batch():
    """Fetch metadata for multiple documents in one request.

    Request body::

        {"document_ids": [1, 2, 3]}
    """
    body = request.get_json(silent=True) or {}
    doc_ids = body.get('document_ids', [])

    if not doc_ids:
        return jsonify({'error': 'document_ids required'}), 400

    # Cap at 500 to avoid huge queries
    doc_ids = doc_ids[:500]

    try:
        from app.shared.db import get_cursor
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("""
                SELECT id, title, url, category, LEFT(content, 500) AS excerpt
                FROM knowledge.documents
                WHERE id = ANY(%s)
            """, (doc_ids,))
            rows = cur.fetchall()

        documents = []
        for row in rows:
            documents.append({
                'id': row[0],
                'title': row[1],
                'url': row[2],
                'category': row[3],
                'content': row[4],
            })

        return jsonify({
            'count': len(documents),
            'documents': documents,
        })

    except Exception as e:
        logger.exception('Error fetching documents batch')
        return jsonify({'error': 'Internal server error while fetching documents'}), 500
