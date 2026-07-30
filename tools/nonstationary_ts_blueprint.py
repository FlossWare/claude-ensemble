"""
Non-stationary Thompson Sampling - Flask Blueprint

Provides REST API endpoints for Thompson Sampling with exponential decay
and sliding-window variants.  Designed to be imported into the unified
API on aio-01:5000.

Endpoints
---------
GET  /learning/strategies/nonstationary
    List all strategies with decayed Beta parameters.

    Query params:
        decay_factor  float   Per-round decay (default 0.995)
        window_size   int     Sliding-window cap (optional)
        round_hours   float   Hours per decay round (default 6.0)

POST /learning/strategies/select-nonstationary
    Select a strategy using decayed Thompson Sampling.

    JSON body (all optional):
        decay_factor  float   Per-round decay (default 0.995)
        window_size   int     Sliding-window cap (optional)
        round_hours   float   Hours per decay round (default 6.0)
        candidates    list    Restrict selection to these strategy names (optional)

Registration
------------
In your main Flask application (application.py or equivalent):

    from nonstationary_ts_blueprint import nonstationary_ts_bp
    app.register_blueprint(nonstationary_ts_bp)

Or if running from the tools/ directory:

    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
    from nonstationary_ts_blueprint import nonstationary_ts_bp
    app.register_blueprint(nonstationary_ts_bp)

Created: 2026-07-26
"""

import logging
import os
import sys
from datetime import datetime

from flask import Blueprint, request, jsonify

# Ensure the tools directory is on sys.path so we can import the core module
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from nonstationary_thompson_sampling import (
    DEFAULT_DECAY,
    DEFAULT_WINDOW,
    MIN_PARAM,
    apply_decay,
    apply_sliding_window,
    estimate_rounds_since_update,
    select_strategy_nonstationary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

nonstationary_ts_bp = Blueprint(
    "nonstationary_ts",
    __name__,
    url_prefix="/learning/strategies",
)


# ---------------------------------------------------------------------------
# Internal: fetch strategies from the database
# ---------------------------------------------------------------------------

def _get_strategies_from_db():
    """Fetch strategy data from PostgreSQL via the parent app's DB helper.

    Uses the parent Flask app's get_db() function.  ALL database access
    goes through the app's connection pool -- never via direct psycopg2
    connections to port 5433.

    Returns a list of dicts or raises RuntimeError.
    """
    try:
        from application import get_db
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM learning.strategy_performance ORDER BY avg_reward DESC"
        )
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return rows
    except ImportError:
        logger.error(
            "Cannot import get_db from application -- "
            "blueprint must be registered within the main Flask app"
        )
        raise RuntimeError(
            "Cannot import get_db from application. "
            "This blueprint must be registered within the main Flask app."
        )
    except Exception as exc:
        logger.error("Failed to fetch strategies from DB: %s", exc)
        raise RuntimeError(f"Cannot fetch strategies: {exc}") from exc


def _parse_decay_params(source):
    """Extract decay parameters from a dict-like source (request.args or JSON body).

    Returns (decay_factor, window_size, round_hours).
    """
    decay = DEFAULT_DECAY
    window = None
    round_hours = 6.0

    raw_decay = source.get("decay_factor")
    if raw_decay is not None:
        try:
            decay = float(raw_decay)
            if not 0.0 < decay <= 1.0:
                raise ValueError("decay_factor must be in (0, 1]")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid decay_factor: {exc}") from exc

    raw_window = source.get("window_size")
    if raw_window is not None:
        try:
            window = int(raw_window)
            if window <= 0:
                raise ValueError("window_size must be > 0")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid window_size: {exc}") from exc

    raw_rh = source.get("round_hours")
    if raw_rh is not None:
        try:
            round_hours = float(raw_rh)
            if round_hours <= 0:
                raise ValueError("round_hours must be > 0")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid round_hours: {exc}") from exc

    return decay, window, round_hours


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@nonstationary_ts_bp.route("/nonstationary", methods=["GET"])
def list_nonstationary():
    """GET /learning/strategies/nonstationary

    Returns all strategies annotated with decayed Beta parameters.
    """
    try:
        decay, window, round_hours = _parse_decay_params(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        strategies = _get_strategies_from_db()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    if not strategies:
        return jsonify({"strategies": [], "count": 0})

    annotated = []
    for s in strategies:
        # Extract alpha/beta -- preserve legitimate 0 (do NOT use ``or 1``)
        raw_alpha = s.get("alpha", s.get("successes"))
        alpha = float(raw_alpha) if raw_alpha is not None else MIN_PARAM
        raw_beta = s.get("beta", s.get("failures"))
        beta_param = float(raw_beta) if raw_beta is not None else MIN_PARAM
        alpha = max(MIN_PARAM, alpha)
        beta_param = max(MIN_PARAM, beta_param)

        rounds = estimate_rounds_since_update(
            s.get("last_updated"), round_hours
        )

        alpha_d, beta_d = apply_decay(alpha, beta_param, decay, rounds)

        if window is not None:
            alpha_d, beta_d = apply_sliding_window(alpha_d, beta_d, window)

        entry = {
            "strategy": s.get("strategy", s.get("name")),
            "original_alpha": alpha,
            "original_beta": beta_param,
            "original_mean": round(alpha / (alpha + beta_param), 4),
            "decayed_alpha": round(alpha_d, 4),
            "decayed_beta": round(beta_d, 4),
            "effective_mean": round(alpha_d / (alpha_d + beta_d), 4),
            "decay_rounds": rounds,
            "avg_reward": s.get("avg_reward"),
            "total_reward": s.get("total_reward"),
            "last_updated": (
                s["last_updated"].isoformat()
                if isinstance(s.get("last_updated"), datetime)
                else s.get("last_updated")
            ),
        }
        annotated.append(entry)

    # Sort by effective_mean descending
    annotated.sort(key=lambda x: x["effective_mean"], reverse=True)

    return jsonify({
        "strategies": annotated,
        "count": len(annotated),
        "params": {
            "decay_factor": decay,
            "window_size": window,
            "round_hours": round_hours,
        },
    })


@nonstationary_ts_bp.route("/select-nonstationary", methods=["POST"])
def select_nonstationary():
    """POST /learning/strategies/select-nonstationary

    Select a strategy using non-stationary Thompson Sampling.
    """
    body = request.get_json(silent=True) or {}

    try:
        decay, window, round_hours = _parse_decay_params(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        strategies = _get_strategies_from_db()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    if not strategies:
        return jsonify({"error": "No strategies available"}), 404

    # Optional candidate filtering
    candidates = body.get("candidates")
    if candidates and isinstance(candidates, list):
        candidate_set = set(candidates)
        strategies = [
            s for s in strategies
            if s.get("strategy", s.get("name")) in candidate_set
        ]
        if not strategies:
            return jsonify({
                "error": "None of the requested candidates found",
                "requested": candidates,
            }), 404

    # Convert datetime objects to strings for JSON serialization
    # Work on copies to avoid mutating the DB-layer dicts
    strategies = [
        {**s, "last_updated": s["last_updated"].isoformat()}
        if isinstance(s.get("last_updated"), datetime)
        else dict(s)
        for s in strategies
    ]

    winner = select_strategy_nonstationary(
        strategies, decay=decay, window=window,
        round_interval_hours=round_hours,
    )

    if winner is None:
        return jsonify({"error": "Selection failed (empty strategy list)"}), 500

    # Clean up datetime objects in the winner dict
    result = {}
    for k, v in winner.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v

    return jsonify({
        "selected": result.get("strategy", result.get("name")),
        "sample": result.get("sample"),
        "decayed_alpha": result.get("decayed_alpha"),
        "decayed_beta": result.get("decayed_beta"),
        "decay_rounds": result.get("decay_rounds"),
        "params": {
            "decay_factor": decay,
            "window_size": window,
            "round_hours": round_hours,
        },
        "full": result,
    })


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register(app):
    """Register the non-stationary TS blueprint with a Flask app.

    Usage:
        import nonstationary_ts_blueprint
        nonstationary_ts_blueprint.register(app)
    """
    app.register_blueprint(nonstationary_ts_bp)
    logger.info("Registered non-stationary Thompson Sampling blueprint")
