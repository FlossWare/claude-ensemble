"""
Flask Blueprint for Graph RAG API endpoints.

Provides REST API endpoints for Graph RAG operations:
  - Entity triple extraction from document chunks
  - Graph-enhanced RAG queries
  - Statistics and progress monitoring

Register this blueprint on the aio-01 unified API to expose Graph RAG
capabilities.  The actual LLM extraction runs on fleet workers via
``graph_rag.py``; this blueprint coordinates jobs and provides query endpoints.

Endpoints
---------
POST /graph-rag/extract/start    Start batch extraction job
GET  /graph-rag/extract/status   Check extraction progress
POST /graph-rag/extract/stop     Stop running extraction job
POST /graph-rag/query            Graph-enhanced RAG query
GET  /graph-rag/stats            Entity/relation counts and distributions

Database: OrientDB via /graph/query (unified API proxy), knowledge base
via /knowledge/* endpoints.  All access through REST API -- no direct
database connections.

Author: Distributed LLM Orchestration Framework
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

graph_rag_bp = Blueprint(
    'graph_rag',
    __name__,
    url_prefix='/graph-rag',
)

# ---------------------------------------------------------------------------
# In-memory job state
# ---------------------------------------------------------------------------

_job_lock = threading.Lock()
_active_job: Optional[Dict[str, Any]] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# POST /graph-rag/extract/start
# ---------------------------------------------------------------------------

@graph_rag_bp.route('/extract/start', methods=['POST'])
def start_extraction():
    """Start a batch entity extraction job.

    This sets job state so fleet workers know to start processing.
    LLM calls do NOT run on aio-01 (controller only).

    Request body (all optional)::

        {
            "batch_size": 50,
            "limit": 1000,
            "model": "google/gemma-4-26b-a4b-it:free",
            "requested_by": "user"
        }
    """
    global _active_job

    with _job_lock:
        if _active_job and _active_job.get('status') == 'running':
            return jsonify({
                'error': 'An extraction job is already running',
                'job': _active_job,
            }), 409

        body = request.get_json(silent=True) or {}

        _active_job = {
            'status': 'running',
            'started_at': _now_iso(),
            'batch_size': body.get('batch_size', 50),
            'limit': body.get('limit', 1000),
            'model': body.get('model', 'google/gemma-4-26b-a4b-it:free'),
            'requested_by': body.get('requested_by', 'api'),
            'workers': {},
            'stats': {
                'chunks_processed': 0,
                'triples_extracted': 0,
                'triples_stored': 0,
                'errors': 0,
                'skipped': 0,
            },
        }

    logger.info(
        'Graph RAG extraction job started (batch=%d, limit=%d, model=%s)',
        _active_job['batch_size'],
        _active_job['limit'],
        _active_job['model'],
    )

    return jsonify({
        'status': 'started',
        'job': _active_job,
    }), 201


# ---------------------------------------------------------------------------
# GET /graph-rag/extract/status
# ---------------------------------------------------------------------------

@graph_rag_bp.route('/extract/status', methods=['GET'])
def extraction_status():
    """Return current extraction job status and graph statistics.

    If include_graph_stats=true (default), also queries OrientDB for
    entity and relation counts.
    """
    include_graph = request.args.get('include_graph_stats', 'true').lower() == 'true'

    result: Dict[str, Any] = {
        'job': _active_job,
        'timestamp': _now_iso(),
    }

    if include_graph:
        try:
            import requests as http_requests

            base_url = request.host_url.rstrip('/')

            # Entity count
            entity_resp = http_requests.post(
                f'{base_url}/graph/query',
                json={'query': 'SELECT count(*) as cnt FROM Entity'},
                timeout=10,
            )
            if entity_resp.ok:
                data = entity_resp.json()
                results = data.get('results', [])
                entity_count = results[0].get('cnt', 0) if results else 0
            else:
                entity_count = 'error'

            # Relation count
            rel_resp = http_requests.post(
                f'{base_url}/graph/query',
                json={'query': 'SELECT count(*) as cnt FROM RELATED_TO'},
                timeout=10,
            )
            if rel_resp.ok:
                data = rel_resp.json()
                results = data.get('results', [])
                relation_count = results[0].get('cnt', 0) if results else 0
            else:
                relation_count = 'error'

            result['graph_stats'] = {
                'entity_count': entity_count,
                'relation_count': relation_count,
            }
        except Exception as e:
            logger.warning('Failed to fetch graph stats: %s', e)
            result['graph_stats'] = {'error': str(e)}

    return jsonify(result)


# ---------------------------------------------------------------------------
# POST /graph-rag/extract/stop
# ---------------------------------------------------------------------------

@graph_rag_bp.route('/extract/stop', methods=['POST'])
def stop_extraction():
    """Stop the current extraction job.

    Workers polling the status endpoint will see status='stopped'.
    """
    global _active_job

    with _job_lock:
        if not _active_job or _active_job.get('status') != 'running':
            return jsonify({
                'error': 'No running extraction job to stop',
                'job': _active_job,
            }), 404

        _active_job['status'] = 'stopped'
        _active_job['stopped_at'] = _now_iso()

    logger.info('Graph RAG extraction job stopped')

    return jsonify({
        'status': 'stopped',
        'job': _active_job,
    })


# ---------------------------------------------------------------------------
# POST /graph-rag/extract/report
# ---------------------------------------------------------------------------

@graph_rag_bp.route('/extract/report', methods=['POST'])
def report_progress():
    """Accept a progress report from a fleet worker.

    Request body::

        {
            "worker_id": "graph-rag-server-01-12345",
            "chunks_processed": 50,
            "triples_extracted": 180,
            "triples_stored": 175,
            "errors": 2,
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
            'chunks_processed': body.get('chunks_processed', 0),
            'triples_extracted': body.get('triples_extracted', 0),
            'triples_stored': body.get('triples_stored', 0),
            'errors': body.get('errors', 0),
            'skipped': body.get('skipped', 0),
        }

        # Recalculate totals
        stats = _active_job['stats']
        for key in stats:
            stats[key] = sum(
                w.get(key, 0) for w in _active_job['workers'].values()
            )

    return jsonify({'status': 'ok', 'stats': stats})


# ---------------------------------------------------------------------------
# POST /graph-rag/query
# ---------------------------------------------------------------------------

@graph_rag_bp.route('/query', methods=['POST'])
def graph_rag_query():
    """Execute a graph-enhanced RAG query.

    Combines entity lookup in OrientDB with vector search in pgvector
    for multi-hop reasoning.

    Request body::

        {
            "query": "What algorithms relate to Thompson Sampling?",
            "limit": 10,
            "max_hops": 2,
            "graph_expansion": true
        }

    Returns combined results from graph traversal and vector search.
    """
    body = request.get_json(silent=True) or {}
    query = body.get('query', '').strip()

    if not query:
        return jsonify({'error': 'Missing query field'}), 400

    limit = min(int(body.get('limit', 10)), 50)
    max_hops = min(int(body.get('max_hops', 2)), 3)
    graph_expansion = body.get('graph_expansion', True)

    try:
        # Import the graph_rag module functions
        # These work via REST API calls, not direct DB access
        import importlib
        import sys
        from pathlib import Path

        # Add tools directory to path if needed
        tools_dir = str(Path(__file__).parent)
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        from graph_rag import graph_enhanced_search

        result = graph_enhanced_search(
            query=query,
            limit=limit,
            graph_expansion=graph_expansion,
            max_hops=max_hops,
        )

        return jsonify(result)

    except ImportError:
        # Fallback: minimal implementation without the full module
        return _fallback_query(query, limit, max_hops, graph_expansion)

    except Exception as e:
        logger.exception('Graph RAG query error')
        return jsonify({'error': str(e)}), 500


def _fallback_query(
    query: str,
    limit: int,
    max_hops: int,
    graph_expansion: bool,
) -> Any:
    """Minimal graph RAG query without the full graph_rag module.

    Uses only REST API calls available from the blueprint context.
    """
    import re
    import requests as http_requests

    t0 = time.time()
    base_url = request.host_url.rstrip('/')

    result: Dict[str, Any] = {
        'query': query,
        'entities': [],
        'graph_entities': [],
        'related_entities': [],
        'expanded_query': query,
        'vector_results': [],
        'combined_results': [],
        'search_time_ms': 0,
        'fallback': True,
    }

    # Simple entity extraction (stop-word removal)
    stop_words = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
        'of', 'in', 'to', 'for', 'with', 'on', 'at', 'by', 'from',
        'and', 'but', 'or', 'not', 'what', 'which', 'who', 'how',
        'when', 'where', 'why', 'that', 'this', 'does', 'do', 'did',
        'relate', 'related', 'use', 'used', 'using',
    }
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9_.-]*', query)
    entities = [w.lower() for w in words if w.lower() not in stop_words and len(w) > 1]
    result['entities'] = entities

    # Graph entity lookup
    if graph_expansion and entities:
        for name in entities[:5]:
            # Sanitize: remove null bytes, escape single quotes, strip backslashes
            safe = name.replace('\0', '').replace("'", "''").replace('\\', '')[:200]
            try:
                resp = http_requests.post(
                    f'{base_url}/graph/query',
                    json={'query': f"SELECT @rid, name, entity_type FROM Entity WHERE name = '{safe}'"},
                    timeout=10,
                )
                if resp.ok:
                    for e in resp.json().get('results', []):
                        result['graph_entities'].append({
                            'name': e.get('name'),
                            'type': e.get('entity_type'),
                            'rid': e.get('@rid'),
                        })
            except Exception:
                pass

        # Traverse from found entities
        for ge in result['graph_entities'][:3]:
            rid = ge.get('rid', '')
            if rid and re.match(r'^#\d+:\d+$', rid):
                try:
                    resp = http_requests.post(
                        f'{base_url}/graph/query',
                        json={
                            'query': (
                                f"SELECT @rid, name, entity_type "
                                f"FROM (TRAVERSE outE(), inE(), outV(), inV() "
                                f"FROM {rid} MAXDEPTH {max_hops}) "
                                f"WHERE @class = 'Entity' AND @rid <> {rid} LIMIT 10"
                            )
                        },
                        timeout=10,
                    )
                    if resp.ok:
                        for r in resp.json().get('results', []):
                            result['related_entities'].append({
                                'name': r.get('name'),
                                'type': r.get('entity_type'),
                            })
                except Exception:
                    pass

    # Expand query
    related_names = [r['name'] for r in result['related_entities'] if r.get('name')]
    if related_names:
        expanded = query + ' ' + ' '.join(related_names[:5])
        result['expanded_query'] = expanded
    else:
        expanded = query

    # Vector search
    try:
        resp = http_requests.post(
            f'{base_url}/knowledge/search',
            json={'query': expanded, 'limit': limit, 'mode': 'hybrid'},
            timeout=60,
        )
        if resp.ok:
            result['vector_results'] = resp.json().get('results', [])
    except Exception:
        pass

    result['combined_results'] = result['vector_results'][:limit]
    result['search_time_ms'] = round((time.time() - t0) * 1000, 1)

    return jsonify(result)


# ---------------------------------------------------------------------------
# GET /graph-rag/stats
# ---------------------------------------------------------------------------

@graph_rag_bp.route('/stats', methods=['GET'])
def graph_rag_stats():
    """Return Graph RAG statistics.

    Queries OrientDB for entity count, relation count, type distributions,
    and most connected entities.
    """
    import requests as http_requests

    base_url = request.host_url.rstrip('/')
    stats: Dict[str, Any] = {
        'entity_count': 0,
        'relation_count': 0,
        'entity_types': [],
        'predicate_types': [],
        'top_entities': [],
        'timestamp': _now_iso(),
    }

    def _query(sql: str) -> List[Dict]:
        try:
            resp = http_requests.post(
                f'{base_url}/graph/query',
                json={'query': sql},
                timeout=15,
            )
            if resp.ok:
                return resp.json().get('results', [])
        except Exception as e:
            logger.debug('Stats query failed: %s', e)
        return []

    try:
        # Entity count
        results = _query('SELECT count(*) as cnt FROM Entity')
        if results:
            stats['entity_count'] = results[0].get('cnt', 0)

        # Relation count
        results = _query('SELECT count(*) as cnt FROM RELATED_TO')
        if results:
            stats['relation_count'] = results[0].get('cnt', 0)

        # Entity type distribution
        results = _query(
            'SELECT entity_type, count(*) as cnt FROM Entity '
            'GROUP BY entity_type ORDER BY cnt DESC LIMIT 20'
        )
        stats['entity_types'] = [
            {'type': r.get('entity_type'), 'count': r.get('cnt')}
            for r in results
        ]

        # Predicate type distribution
        results = _query(
            'SELECT predicate, count(*) as cnt FROM RELATED_TO '
            'GROUP BY predicate ORDER BY cnt DESC LIMIT 20'
        )
        stats['predicate_types'] = [
            {'predicate': r.get('predicate'), 'count': r.get('cnt')}
            for r in results
        ]

        # Top entities by connections
        results = _query(
            "SELECT name, entity_type, both('RELATED_TO').size() as connections "
            "FROM Entity ORDER BY connections DESC LIMIT 20"
        )
        stats['top_entities'] = [
            {'name': r.get('name'), 'type': r.get('entity_type'),
             'connections': r.get('connections')}
            for r in results
        ]

    except Exception as e:
        stats['error'] = str(e)
        logger.error('Failed to get graph RAG stats: %s', e)

    return jsonify(stats)
