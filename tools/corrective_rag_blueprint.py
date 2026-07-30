"""
Flask Blueprint for Corrective RAG (CRAG) pipeline endpoints.

Register this blueprint on the aio-01 REST API to expose server-side
Corrective RAG operations: graded retrieval with automatic fallback
when results are irrelevant.

Endpoints
---------
POST /rag/corrective-search   Run the full CRAG pipeline
GET  /rag/corrective/stats    Grading distribution, fallback rates, quality metrics

Usage::

    from flask import Flask
    from corrective_rag_blueprint import corrective_rag_bp

    app = Flask(__name__)
    app.register_blueprint(corrective_rag_bp)
    app.run(host='0.0.0.0', port=5000)

The CRAG pipeline flow:
  1. Retrieve documents from the knowledge base
  2. Grade each result with a fast LLM (CORRECT / AMBIGUOUS / INCORRECT)
  3. Based on grading distribution:
     - All CORRECT  -> return directly
     - Mix          -> return CORRECT + refine AMBIGUOUS
     - All bad      -> fallback (reformulate, alt mode, web search)
"""

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from flask import Blueprint, request, jsonify

from corrective_rag import (
    CorrectiveRAG,
    SEARCH_MODES,
    DEFAULT_LIMIT,
    DEFAULT_MODE,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

corrective_rag_bp = Blueprint(
    'corrective_rag',
    __name__,
    url_prefix='/rag',
)

# ---------------------------------------------------------------------------
# Analytics (per-process)
# ---------------------------------------------------------------------------

# Analytics ring buffer: last N pipeline runs
_ANALYTICS_MAX = 1000
_analytics: Deque[Dict[str, Any]] = deque(maxlen=_ANALYTICS_MAX)
_analytics_lock = threading.Lock()

# Aggregate counters (never reset unless explicit)
_aggregate_stats: Dict[str, Any] = {
    'total_queries': 0,
    'grading_distribution': {'CORRECT': 0, 'AMBIGUOUS': 0, 'INCORRECT': 0},
    'actions_taken': {'direct_use': 0, 'refined': 0, 'fallback': 0},
    'fallback_triggers': {
        'reformulate': 0,
        'alt_mode': 0,
        'web_search': 0,
        'refined_ambiguous': 0,
        'exhausted': 0,
    },
    'total_results_graded': 0,
    'total_refinements': 0,
    'total_grading_failures': 0,
    'total_latency_ms': 0,
    'started_at': datetime.now(timezone.utc).isoformat(),
}
_agg_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_analytics(result: Dict[str, Any]) -> None:
    """Record a pipeline run in the ring buffer and update aggregates."""
    entry = {
        'timestamp': _now_iso(),
        'query': result.get('query', ''),
        'action': result.get('action', ''),
        'fallback_type': result.get('fallback_type'),
        'result_count': result.get('result_count', 0),
        'grading': result.get('grading', {}),
        'elapsed_ms': result.get('metadata', {}).get('elapsed_ms', 0),
    }

    with _analytics_lock:
        _analytics.append(entry)

    with _agg_lock:
        _aggregate_stats['total_queries'] += 1

        grading = result.get('grading', {})
        for grade in ('CORRECT', 'AMBIGUOUS', 'INCORRECT'):
            _aggregate_stats['grading_distribution'][grade] += grading.get(grade, 0)

        _aggregate_stats['total_results_graded'] += sum(grading.values())

        action = result.get('action', '')
        if action in _aggregate_stats['actions_taken']:
            _aggregate_stats['actions_taken'][action] += 1

        ft = result.get('fallback_type')
        if ft and ft in _aggregate_stats['fallback_triggers']:
            _aggregate_stats['fallback_triggers'][ft] += 1

        elapsed = result.get('metadata', {}).get('elapsed_ms', 0)
        _aggregate_stats['total_latency_ms'] += elapsed

        gf = result.get('metadata', {}).get('grading_failures', 0)
        _aggregate_stats['total_grading_failures'] += gf


# ===================================================================
# POST /rag/corrective-search
# ===================================================================

@corrective_rag_bp.route('/corrective-search', methods=['POST'])
def corrective_search():
    """Run the full Corrective RAG pipeline.

    Request body::

        {
            "query":   "What is Thompson Sampling?",   // required
            "limit":   5,                               // optional (default 5)
            "mode":    "hybrid",                        // optional (hybrid|fulltext|vector)
            "verbose": false                            // optional
        }

    Response::

        {
            "query": "What is Thompson Sampling?",
            "results": [ ... ],
            "action": "direct_use",
            "fallback_type": null,
            "grading": {"CORRECT": 3, "AMBIGUOUS": 1, "INCORRECT": 1},
            "result_count": 4,
            "metadata": { ... }
        }
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'error': 'Request body must be JSON'}), 400

    query = body.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Missing required field: query'}), 400

    if len(query) > 1000:
        return jsonify({'error': 'Query too long (max 1000 characters)'}), 400

    limit = body.get('limit', DEFAULT_LIMIT)
    if not isinstance(limit, int) or limit < 1 or limit > 50:
        return jsonify({'error': 'limit must be an integer between 1 and 50'}), 400

    mode = body.get('mode', DEFAULT_MODE)
    if mode not in SEARCH_MODES:
        return jsonify({
            'error': f'Invalid mode: {mode}. Must be one of: {SEARCH_MODES}',
        }), 400

    verbose = body.get('verbose', False)

    try:
        crag = CorrectiveRAG(limit=limit, mode=mode)
        result = crag.query(query, verbose=verbose)
        _record_analytics(result)
        return jsonify(result), 200
    except Exception as exc:
        logger.exception('CRAG pipeline failed for query: %s', query)
        return jsonify({
            'error': 'Internal pipeline error',
            'detail': str(exc),
        }), 500


# ===================================================================
# GET /rag/corrective/stats
# ===================================================================

@corrective_rag_bp.route('/corrective/stats', methods=['GET'])
def corrective_stats():
    """Return grading distribution, fallback rates, and quality metrics.

    Query params:
        last  int  Only consider the last N queries (default: all)

    Response::

        {
            "total_queries": 42,
            "grading_distribution": {"CORRECT": 100, "AMBIGUOUS": 50, "INCORRECT": 60},
            "correct_ratio": 0.476,
            "actions_taken": {"direct_use": 20, "refined": 12, "fallback": 10},
            "fallback_rates": { ... },
            "avg_latency_ms": 1234,
            "recent": [ ... last 10 entries ... ]
        }
    """
    last_n = request.args.get('last', type=int)

    with _agg_lock:
        stats = dict(_aggregate_stats)

    with _analytics_lock:
        if last_n and last_n > 0:
            recent_entries = list(_analytics)[-last_n:]
        else:
            recent_entries = list(_analytics)[-10:]

    # Compute derived metrics
    total_graded = sum(stats['grading_distribution'].values())
    correct_count = stats['grading_distribution']['CORRECT']

    stats['correct_ratio'] = (
        round(correct_count / total_graded, 4) if total_graded > 0 else 0.0
    )

    total_queries = stats['total_queries']
    stats['avg_latency_ms'] = (
        round(stats['total_latency_ms'] / total_queries)
        if total_queries > 0
        else 0
    )

    # Fallback rate: proportion of queries that needed fallback
    fallback_count = stats['actions_taken'].get('fallback', 0)
    stats['fallback_rate'] = (
        round(fallback_count / total_queries, 4) if total_queries > 0 else 0.0
    )

    # Quality improvement estimate: how many fallbacks recovered useful results
    if last_n:
        window_entries = recent_entries
    else:
        window_entries = list(_analytics)

    fallback_entries = [e for e in window_entries if e.get('action') == 'fallback']
    recovered = [e for e in fallback_entries if e.get('result_count', 0) > 0]
    stats['fallback_recovery_rate'] = (
        round(len(recovered) / len(fallback_entries), 4)
        if fallback_entries
        else 0.0
    )

    stats['recent'] = recent_entries

    return jsonify(stats), 200
