"""
Flask blueprint for the LLM Cascade Router.

Endpoints
---------
POST /cascade/query       Run a cascading query
GET  /cascade/stats       Tier distribution, escalation rates, latency
POST /cascade/configure   Adjust confidence threshold, max tier, etc.
GET  /cascade/classify    Classify difficulty of a prompt without querying
POST /cascade/record      Record a cascade result (analytics sink)

Usage::

    from flask import Flask
    from cascade_blueprint import cascade_bp

    app = Flask(__name__)
    app.register_blueprint(cascade_bp)
    app.run(host='0.0.0.0', port=5000)
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from flask import Blueprint, request, jsonify

from llm_cascade import (
    LLMCascade,
    classify_difficulty,
    estimate_confidence,
    TIER_ORDER,
    TIERS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
cascade_bp = Blueprint('cascade', __name__, url_prefix='/cascade')

# ---------------------------------------------------------------------------
# Shared cascade instance (created once per process)
# ---------------------------------------------------------------------------
_cascade: Optional[LLMCascade] = None
_cascade_lock = threading.Lock()

# In-memory analytics ring buffer (last N results)
_ANALYTICS_MAX = 500
_analytics: List[Dict] = []
_analytics_lock = threading.Lock()


def _get_cascade() -> LLMCascade:
    """Lazily initialize the shared LLMCascade instance (thread-safe)."""
    global _cascade
    if _cascade is None:
        with _cascade_lock:
            if _cascade is None:
                _cascade = LLMCascade()
    return _cascade


# ===================================================================
# POST /cascade/query
# ===================================================================
@cascade_bp.route('/query', methods=['POST'])
def cascade_query():
    """Run a cascading query.

    Request body::

        {
            "prompt":        "What is 2+2?",      // required
            "max_tier":      "paid",               // optional override
            "system_prompt": "You are helpful.",    // optional
            "max_tokens":    1024                   // optional override
        }

    Returns 200 with the cascade result on success.
    Returns 400 if prompt is missing.
    Returns 500 on unexpected errors.
    """
    try:
        body = request.get_json(force=True) or {}
        prompt = body.get('prompt', '').strip()

        if not prompt:
            return jsonify({'error': 'prompt is required'}), 400

        cascade = _get_cascade()

        # Per-request overrides (passed to query, not mutated on instance)
        max_tier = body.get('max_tier', None)
        system_prompt = body.get('system_prompt', None)
        req_max_tokens = body.get('max_tokens')
        if req_max_tokens is not None:
            req_max_tokens = max(64, min(16384, int(req_max_tokens)))

        result = cascade.query(
            prompt=prompt,
            max_tier=max_tier,
            system_prompt=system_prompt,
            max_tokens=req_max_tokens,
        )

        # Store in analytics buffer (fire-and-forget: never fail the
        # request just because analytics recording had an issue)
        try:
            _record_analytics(result)
        except Exception as analytics_exc:
            logger.warning('Failed to record analytics: %s', analytics_exc)

        return jsonify(result)

    except Exception as exc:
        logger.error('Error in cascade_query: %s', exc, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# GET /cascade/stats
# ===================================================================
@cascade_bp.route('/stats', methods=['GET'])
def cascade_stats():
    """Return tier distribution, escalation rates, and latency statistics.

    Response::

        {
            "total_queries": 42,
            "tier_counts": {"free_small": 30, "free_large": 10, "paid": 2},
            "escalation_count": 12,
            "escalation_rate": 0.286,
            "avg_confidence": 0.78,
            "avg_latency_ms": 450,
            "free_tier_rate": 0.952,
            "threshold": 0.65,
            "max_tier": "paid",
            "tiers": { ... },
            "recent_analytics_count": 42
        }
    """
    try:
        cascade = _get_cascade()
        stats = cascade.get_stats()

        # Enrich with tier definitions
        stats['tiers'] = {
            name: {
                'models': models,
                'model_count': len(models),
            }
            for name, models in TIERS.items()
        }

        snapshot = _snapshot_analytics()
        stats['recent_analytics_count'] = len(snapshot)

        # Compute per-tier confidence averages from analytics
        tier_confidence: Dict[str, List[float]] = {}
        for entry in snapshot:
            t = entry.get('tier', '')
            c = entry.get('confidence', 0.0)
            if t:
                tier_confidence.setdefault(t, []).append(c)

        stats['tier_avg_confidence'] = {
            t: round(sum(vals) / len(vals), 4) if vals else 0.0
            for t, vals in tier_confidence.items()
        }

        # Difficulty distribution from recent queries
        diff_counts: Dict[str, int] = {'easy': 0, 'medium': 0, 'hard': 0}
        for entry in snapshot:
            cat = entry.get('difficulty_category', '')
            if cat in diff_counts:
                diff_counts[cat] += 1
        stats['difficulty_distribution'] = diff_counts

        return jsonify(stats)

    except Exception as exc:
        logger.error('Error in cascade_stats: %s', exc, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# POST /cascade/configure
# ===================================================================
@cascade_bp.route('/configure', methods=['POST'])
def cascade_configure():
    """Update cascade configuration.

    Request body (all fields optional)::

        {
            "threshold":  0.7,           // confidence threshold [0.0, 1.0]
            "max_tier":   "free_large",  // 'free_small' | 'free_large' | 'paid'
            "max_tokens": 2048,          // [64, 16384]
            "timeout":    45,            // seconds [5, 120]
            "reset_stats": true          // reset statistics counters
        }

    Returns the updated configuration.
    """
    try:
        body = request.get_json(force=True) or {}
        cascade = _get_cascade()

        # --- Type validation before passing to configure() ---
        threshold = body.get('threshold')
        if threshold is not None:
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                return jsonify({
                    'error': 'threshold must be a number between 0.0 and 1.0',
                }), 400

        max_tier = body.get('max_tier')
        if max_tier is not None:
            if not isinstance(max_tier, str) or max_tier not in TIER_ORDER:
                return jsonify({
                    'error': f'max_tier must be one of: {", ".join(TIER_ORDER)}',
                }), 400

        max_tokens = body.get('max_tokens')
        if max_tokens is not None:
            try:
                max_tokens = int(max_tokens)
            except (TypeError, ValueError):
                return jsonify({
                    'error': 'max_tokens must be an integer between 64 and 16384',
                }), 400

        timeout = body.get('timeout')
        if timeout is not None:
            try:
                timeout = int(timeout)
            except (TypeError, ValueError):
                return jsonify({
                    'error': 'timeout must be an integer between 5 and 120',
                }), 400

        new_config = cascade.configure(
            threshold=threshold,
            max_tier=max_tier,
            max_tokens=max_tokens,
            timeout=timeout,
        )

        if body.get('reset_stats', False):
            cascade.reset_stats()
            new_config['stats_reset'] = True

        return jsonify(new_config)

    except Exception as exc:
        logger.error('Error in cascade_configure: %s', exc, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# GET /cascade/classify
# ===================================================================
@cascade_bp.route('/classify', methods=['GET'])
def cascade_classify():
    """Classify difficulty of a prompt without sending it to a model.

    Query parameter:
        ?prompt=What+is+2%2B2

    Returns difficulty classification.
    """
    prompt = request.args.get('prompt', '').strip()
    if not prompt:
        return jsonify({'error': 'prompt query parameter is required'}), 400

    difficulty = classify_difficulty(prompt)
    difficulty['starting_tier'] = (
        'free_large' if difficulty['category'] == 'hard' else 'free_small'
    )
    return jsonify(difficulty)


# ===================================================================
# POST /cascade/record
# ===================================================================
@cascade_bp.route('/record', methods=['POST'])
def cascade_record():
    """Record a cascade result for analytics.

    Called by the CLI and external callers to centralize statistics.
    Also called internally by the /query endpoint.

    Request body::

        {
            "model": "qwen/qwen3-4b:free",
            "tier": "free_small",
            "confidence": 0.82,
            "escalated": false,
            "difficulty_score": 0.25,
            "difficulty_category": "easy",
            "latency_ms": 320,
            "attempts": 1,
            "timestamp": "2026-07-26T..."
        }
    """
    try:
        body = request.get_json(force=True) or {}
        _record_analytics_from_body(body)
        return jsonify({'status': 'recorded'}), 201

    except Exception as exc:
        logger.error('Error in cascade_record: %s', exc, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ===================================================================
# Analytics helpers
# ===================================================================

def _append_analytics(entry: Dict) -> None:
    """Append an entry to the ring buffer (thread-safe)."""
    with _analytics_lock:
        _analytics.append(entry)
        if len(_analytics) > _ANALYTICS_MAX:
            _analytics.pop(0)


def _snapshot_analytics() -> List[Dict]:
    """Return a shallow copy of the analytics buffer (thread-safe)."""
    with _analytics_lock:
        return list(_analytics)


def _record_analytics(result: dict) -> None:
    """Extract key fields from a cascade result and store in the ring buffer."""
    entry = {
        'model': result.get('model', ''),
        'tier': result.get('tier', ''),
        'confidence': result.get('confidence', 0.0),
        'escalated': result.get('escalated', False),
        'difficulty_score': result.get('difficulty', {}).get('score', 0.0),
        'difficulty_category': result.get('difficulty', {}).get('category', ''),
        'latency_ms': result.get('latency_ms', 0),
        'attempts': len(result.get('attempts', [])),
        'error': result.get('error', ''),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    _append_analytics(entry)


def _record_analytics_from_body(body: dict) -> None:
    """Store a raw analytics entry from an external caller."""
    entry = {
        'model': body.get('model', ''),
        'tier': body.get('tier', ''),
        'confidence': body.get('confidence', 0.0),
        'escalated': body.get('escalated', False),
        'difficulty_score': body.get('difficulty_score', 0.0),
        'difficulty_category': body.get('difficulty_category', ''),
        'latency_ms': body.get('latency_ms', 0),
        'attempts': body.get('attempts', 0),
        'error': body.get('error', ''),
        'timestamp': body.get('timestamp', datetime.now(timezone.utc).isoformat()),
    }
    _append_analytics(entry)
