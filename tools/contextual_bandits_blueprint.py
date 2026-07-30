"""
LinUCB Contextual Bandits - Flask Blueprint

Provides REST API endpoints for per-task model routing using LinUCB
contextual bandits.  Designed to be imported into the unified API
on aio-01:5000.

Endpoints
---------
POST /learning/bandits/select
    Select the best model for a given context.

    JSON body:
        features     list[float]   Feature vector (FEATURE_DIM dimensions)
        candidates   list[str]     Restrict to these model names (optional)
        tier_filter  str           "free" or "paid" (optional)
        alpha        float         Exploration override (optional)

    OR (auto-extract features from query):
        query        str           Raw query text
        task_type    str           code|math|creative|factual|analytical|conversational
        complexity   str           simple|moderate|complex
        domain       str           programming|science|specialised|general
        has_code     bool          Whether query contains code

POST /learning/bandits/update
    Update arm parameters after observing a reward.

    JSON body:
        arm_name     str           Model name (required)
        features     list[float]   Feature vector (required)
        reward       float         Observed reward in [0, 1] (required)

GET /learning/bandits/stats
    Per-arm statistics: update count, avg reward, theta norm, A condition.

GET /learning/bandits/arms
    List all configured arms with metadata.

POST /learning/bandits/reset
    Reset all arms to initial state (requires confirmation).

    JSON body:
        confirm      bool          Must be true

Registration
------------
In your main Flask application:

    from contextual_bandits_blueprint import contextual_bandits_bp
    app.register_blueprint(contextual_bandits_bp)

Or:

    import contextual_bandits_blueprint
    contextual_bandits_blueprint.register(app)

Created: 2026-07-26
"""

import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify

# Ensure the tools directory is on sys.path so we can import the core module
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from contextual_bandits import (
    DEFAULT_ALPHA,
    DEFAULT_ARMS,
    FEATURE_DIM,
    ArmState,
    LinUCBBandits,
    extract_features,
    features_to_dict,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

contextual_bandits_bp = Blueprint(
    "contextual_bandits",
    __name__,
    url_prefix="/learning/bandits",
)

# ---------------------------------------------------------------------------
# Shared state: one LinUCBBandits instance per process
# ---------------------------------------------------------------------------

_bandits: Optional[LinUCBBandits] = None
_bandits_lock = threading.Lock()

# Lock for mutations (update, reset, add_arm) to prevent concurrent
# corruption of arm state.  Reads (select, stats, arms) are safe without
# this lock because they only read numpy arrays (atomic on CPython due
# to the GIL) and never mutate shared state.
_mutation_lock = threading.Lock()

# Persistence: state is saved to DB after every N updates
_SAVE_EVERY = 10
_updates_since_save = 0


def _get_bandits() -> LinUCBBandits:
    """Lazily initialise the shared bandits instance (thread-safe).

    On first call, tries to load saved state from the database.
    Falls back to fresh default arms if no saved state exists.
    """
    global _bandits
    if _bandits is None:
        with _bandits_lock:
            if _bandits is None:
                loaded = _load_from_db()
                if loaded is not None:
                    _bandits = loaded
                    logger.info(
                        "Loaded bandits state from DB: %d arms, alpha=%.2f",
                        len(_bandits.arms), _bandits.alpha,
                    )
                else:
                    _bandits = LinUCBBandits.new_default()
                    logger.info(
                        "Initialised fresh bandits: %d arms", len(_bandits.arms)
                    )
    return _bandits


# ---------------------------------------------------------------------------
# Database persistence via parent app (no direct connections)
# ---------------------------------------------------------------------------

def _load_from_db() -> Optional[LinUCBBandits]:
    """Load bandits state from the database.

    Tries multiple import paths to get a DB connection from the parent
    Flask application, then looks for saved state in the
    learning.bandit_state table.

    Returns a LinUCBBandits instance or None if nothing is saved.
    """
    try:
        # Strategy 1: Import from the parent Flask application
        try:
            from application import get_db
            conn = get_db()
        except (ImportError, Exception):
            # Strategy 2: Direct psycopg2 (only if running inside the API process)
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(
                dbname="learning",
                user="claude",
                host="aio-01",
                port=5433,
                cursor_factory=RealDictCursor,
                connect_timeout=5,
            )

        try:
            cur = conn.cursor()

            # Ensure table exists (algorithm has a UNIQUE constraint
            # so ON CONFLICT (algorithm) works for upsert)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS learning.bandit_state (
                    id SERIAL PRIMARY KEY,
                    algorithm TEXT NOT NULL DEFAULT 'linucb' UNIQUE,
                    state_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            conn.commit()

            # Load most recent state
            cur.execute("""
                SELECT state_json FROM learning.bandit_state
                WHERE algorithm = 'linucb'
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                state_json = row[0] if not isinstance(row, dict) else row.get("state_json")
                if isinstance(state_json, str):
                    state_json = json.loads(state_json)
                return LinUCBBandits.from_dict(state_json)
            return None
        finally:
            if conn and hasattr(conn, 'close'):
                try:
                    conn.close()
                except Exception:
                    pass

    except Exception as exc:
        logger.warning("Could not load bandits state from DB: %s", exc)
        return None


def _save_to_db(bandits: LinUCBBandits) -> bool:
    """Save bandits state to the database.

    Uses UPSERT to maintain a single row per algorithm.
    """
    try:
        try:
            from application import get_db
            conn = get_db()
        except (ImportError, Exception):
            import psycopg2
            conn = psycopg2.connect(
                dbname="learning",
                user="claude",
                host="aio-01",
                port=5433,
                connect_timeout=5,
            )

        try:
            cur = conn.cursor()
            state_json = json.dumps(bandits.to_dict())

            cur.execute("""
                INSERT INTO learning.bandit_state (algorithm, state_json, updated_at)
                VALUES ('linucb', %s::jsonb, NOW())
                ON CONFLICT (algorithm)
                DO UPDATE SET
                    state_json = EXCLUDED.state_json,
                    updated_at = NOW()
            """, (state_json,))
            conn.commit()
            logger.info("Saved bandits state to DB (%d arms)", len(bandits.arms))
            return True
        finally:
            if conn and hasattr(conn, 'close'):
                try:
                    conn.close()
                except Exception:
                    pass

    except Exception as exc:
        logger.error("Failed to save bandits state to DB: %s", exc)
        return False


def _maybe_save() -> None:
    """Save state to DB if enough updates have accumulated."""
    global _updates_since_save
    _updates_since_save += 1
    if _updates_since_save >= _SAVE_EVERY:
        _updates_since_save = 0
        bandits = _get_bandits()
        # Save in a background thread to avoid blocking the request
        t = threading.Thread(target=_save_to_db, args=(bandits,), daemon=True)
        t.start()


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def _validate_features(body: Dict) -> Any:
    """Extract and validate feature vector from request body.

    Accepts either:
      - "features": explicit feature vector (list of floats)
      - "query" + optional overrides: auto-extract features

    Returns:
        numpy array of shape (FEATURE_DIM,)

    Raises:
        ValueError on invalid input.
    """
    import numpy as np

    if "features" in body:
        raw = body["features"]
        if not isinstance(raw, list):
            raise ValueError("features must be a list of floats")
        if len(raw) != FEATURE_DIM:
            raise ValueError(
                f"features must have {FEATURE_DIM} dimensions, got {len(raw)}"
            )
        try:
            features = np.array(raw, dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"features contains non-numeric values: {exc}")
        if np.any(np.isnan(features)) or np.any(np.isinf(features)):
            raise ValueError("features must not contain NaN or Inf")
        return features

    # Auto-extract from query text and overrides
    query = body.get("query", "")
    if not isinstance(query, str):
        raise ValueError("query must be a string")

    return extract_features(
        query=query,
        task_type=body.get("task_type"),
        complexity=body.get("complexity"),
        domain=body.get("domain"),
        has_code=body.get("has_code"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@contextual_bandits_bp.route("/select", methods=["POST"])
def bandits_select():
    """POST /learning/bandits/select

    Select the best model for a given context using LinUCB.
    """
    body = request.get_json(force=True)
    if body is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    try:
        features = _validate_features(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Optional parameters
    candidates = body.get("candidates")
    if candidates is not None:
        if not isinstance(candidates, list):
            return jsonify({"error": "candidates must be a list of strings"}), 400
        if not all(isinstance(c, str) for c in candidates):
            return jsonify({"error": "each candidate must be a string"}), 400

    tier_filter = body.get("tier_filter")
    if tier_filter is not None and tier_filter not in ("free", "paid"):
        return jsonify({"error": "tier_filter must be 'free' or 'paid'"}), 400

    alpha_override = body.get("alpha")
    if alpha_override is not None:
        try:
            alpha_override = float(alpha_override)
        except (ValueError, TypeError):
            return jsonify({"error": "alpha must be a number"}), 400

    bandits = _get_bandits()

    # Use request-local alpha to avoid mutating shared state (thread-safe).
    # Save and restore is NOT safe under concurrent requests.
    effective_alpha = alpha_override if alpha_override is not None else bandits.alpha

    # select() is read-only on arm state, so no mutation lock needed.
    # We pass alpha directly to each arm's predict() to avoid touching
    # the shared bandits.alpha attribute.
    try:
        import numpy as np
        x = np.asarray(features, dtype=np.float64)

        # Determine eligible arms
        eligible = {}
        for name, arm in bandits.arms.items():
            if candidates and name not in candidates:
                continue
            if tier_filter and arm.tier != tier_filter:
                continue
            eligible[name] = arm

        if not eligible:
            return jsonify({"error": "No eligible arms after filtering"}), 400

        # Compute UCB for each arm with request-local alpha
        scores = {}
        for name, arm in eligible.items():
            scores[name] = arm.predict(x, effective_alpha)

        # Select best arm, break ties randomly
        max_score = max(scores.values())
        tied = [n for n, s in scores.items() if abs(s - max_score) < 1e-12]
        from contextual_bandits import _get_rng
        rng = _get_rng()
        selected = tied[int(rng.integers(len(tied)))] if len(tied) > 1 else tied[0]
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Build response without mutating any shared state
    feat_info = features_to_dict(features)
    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    return jsonify({
        "selected": selected,
        "ucb_score": round(scores[selected], 6),
        "scores": {k: round(v, 6) for k, v in sorted_scores},
        "context": feat_info,
        "alpha": effective_alpha,
        "n_arms": len(scores),
    })


@contextual_bandits_bp.route("/update", methods=["POST"])
def bandits_update():
    """POST /learning/bandits/update

    Update arm parameters after observing a reward.
    """
    body = request.get_json(force=True)
    if body is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    # Validate required fields
    arm_name = body.get("arm_name")
    if not arm_name or not isinstance(arm_name, str):
        return jsonify({"error": "arm_name is required (string)"}), 400

    reward = body.get("reward")
    if reward is None:
        return jsonify({"error": "reward is required (float in [0, 1])"}), 400
    try:
        reward = float(reward)
    except (ValueError, TypeError):
        return jsonify({"error": "reward must be a number"}), 400
    if not (0.0 <= reward <= 1.0):
        return jsonify({"error": "reward must be in [0, 1]"}), 400

    try:
        features = _validate_features(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    bandits = _get_bandits()

    # Mutation lock: serialise updates to prevent concurrent corruption
    # of A matrices and b vectors.
    with _mutation_lock:
        # Auto-add unknown arms (e.g. new models added to the fleet)
        if arm_name not in bandits.arms:
            provider = body.get("provider", "unknown")
            tier = body.get("tier", "free")
            bandits.add_arm(arm_name, provider, tier)
            logger.info("Auto-added new arm: %s (%s, %s)", arm_name, provider, tier)

        try:
            bandits.update(arm_name, features, reward)
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    # Trigger periodic save (outside mutation lock to avoid blocking)
    _maybe_save()

    arm = bandits.arms[arm_name]
    return jsonify({
        "status": "updated",
        "arm_name": arm_name,
        "reward": reward,
        "n_updates": arm.n_updates,
        "avg_reward": round(arm.total_reward / arm.n_updates, 4) if arm.n_updates > 0 else 0.0,
    })


@contextual_bandits_bp.route("/stats", methods=["GET"])
def bandits_stats():
    """GET /learning/bandits/stats

    Per-arm statistics: update count, avg reward, theta norm, A condition.
    """
    bandits = _get_bandits()
    arm_stats = bandits.stats()

    total_updates = sum(a["n_updates"] for a in arm_stats)
    total_reward = sum(a["total_reward"] for a in arm_stats)

    return jsonify({
        "alpha": bandits.alpha,
        "feature_dim": bandits.feature_dim,
        "n_arms": len(arm_stats),
        "total_updates": total_updates,
        "total_reward": round(total_reward, 4),
        "avg_reward": round(total_reward / total_updates, 4) if total_updates > 0 else 0.0,
        "arms": arm_stats,
    })


@contextual_bandits_bp.route("/arms", methods=["GET"])
def bandits_arms():
    """GET /learning/bandits/arms

    List all configured arms with metadata.
    """
    bandits = _get_bandits()

    arms = []
    for name, arm in sorted(bandits.arms.items()):
        arms.append({
            "name": name,
            "provider": arm.provider,
            "tier": arm.tier,
            "n_updates": arm.n_updates,
            "avg_reward": round(arm.total_reward / arm.n_updates, 4) if arm.n_updates > 0 else 0.0,
            "created_at": arm.created_at,
        })

    return jsonify({
        "arms": arms,
        "n_arms": len(arms),
        "feature_dim": bandits.feature_dim,
        "alpha": bandits.alpha,
    })


@contextual_bandits_bp.route("/reset", methods=["POST"])
def bandits_reset():
    """POST /learning/bandits/reset

    Reset all arms to initial state.  Requires {"confirm": true}.
    """
    global _bandits, _updates_since_save

    body = request.get_json(force=True)
    if body is None or not body.get("confirm"):
        return jsonify({
            "error": "Reset requires {\"confirm\": true} in request body",
            "warning": "This will erase all learned arm parameters",
        }), 400

    with _bandits_lock:
        _bandits = LinUCBBandits.new_default()
        _updates_since_save = 0

    # Save the reset state
    _save_to_db(_bandits)

    return jsonify({
        "status": "reset",
        "n_arms": len(_bandits.arms),
        "message": "All arms reset to initial state",
    })


@contextual_bandits_bp.route("/save", methods=["POST"])
def bandits_save():
    """POST /learning/bandits/save

    Force-save current state to the database.
    """
    global _updates_since_save
    bandits = _get_bandits()
    success = _save_to_db(bandits)
    _updates_since_save = 0

    if success:
        return jsonify({"status": "saved", "n_arms": len(bandits.arms)})
    else:
        return jsonify({"error": "Failed to save state to database"}), 500


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register(app):
    """Register the contextual bandits blueprint with a Flask app.

    Usage:
        import contextual_bandits_blueprint
        contextual_bandits_blueprint.register(app)
    """
    app.register_blueprint(contextual_bandits_bp)
    logger.info("Registered LinUCB contextual bandits blueprint")
