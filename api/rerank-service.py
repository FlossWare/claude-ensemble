#!/usr/bin/env python3
"""
Cross-Encoder Re-Ranking Microservice
======================================

Lightweight Flask service that re-ranks search results using
cross-encoder/ms-marco-MiniLM-L-6-v2.

IMPORTANT: This service MUST run on laptop-01 (192.168.1.126) or
laptop-02 (localhost) -- NOT on fleet workers or aio-01 (CPU too weak
for torch inference).

Endpoints:
  POST /rerank  - Re-rank passages by relevance to a query
  GET  /health  - Health check and model status

Usage:
  python3 rerank-service.py                    # default port 5002
  python3 rerank-service.py --port 5003        # custom port
  python3 rerank-service.py --model <name>     # custom cross-encoder model

Example request:
  curl -X POST http://localhost:5002/rerank \
    -H "Content-Type: application/json" \
    -d '{"query": "kubernetes deployment", "passages": [{"content": "...", "chunk_id": 1}]}'

Author: Distributed LLM Orchestration Framework
"""

import argparse
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rerank-service")

# ---------------------------------------------------------------------------
# Singleton cross-encoder model
# ---------------------------------------------------------------------------
_model = None
_model_lock = threading.Lock()
_model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model_load_time: Optional[float] = None
_model_error: Optional[str] = None


def _load_model(name: str = _model_name):
    """Load the cross-encoder model (thread-safe singleton)."""
    global _model, _model_name, _model_load_time, _model_error

    with _model_lock:
        if _model is not None:
            return _model

        _model_name = name
        t0 = time.time()
        try:
            from sentence_transformers import CrossEncoder

            logger.info("Loading cross-encoder model: %s ...", name)
            _model = CrossEncoder(name)
            _model_load_time = time.time() - t0
            logger.info(
                "Model loaded in %.1f s  (device=%s)",
                _model_load_time,
                getattr(_model, "device", "cpu"),
            )
            return _model
        except Exception as exc:
            _model_error = str(exc)
            logger.error("Failed to load model %s: %s", name, exc)
            return None


# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------
app = Flask(__name__)


@app.route("/rerank", methods=["POST"])
def rerank():
    """
    Re-rank passages by relevance to a query.

    Request JSON:
    {
        "query": "search query text",
        "passages": [
            {"content": "passage text...", "chunk_id": 123, ...},
            ...
        ],
        "top_k": 10          // optional, default: return all
    }

    Response JSON:
    {
        "results": [
            {"content": "...", "chunk_id": 123, "score": 0.9832, ...},
            ...
        ],
        "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "count": 10,
        "latency_ms": 42.5
    }
    """
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    passages = data.get("passages", [])
    top_k = data.get("top_k")

    if not query:
        return jsonify({"error": "Missing 'query' field"}), 400
    if not passages:
        return jsonify({"error": "Missing or empty 'passages' list"}), 400

    model = _load_model()
    if model is None:
        return jsonify({
            "error": "Cross-encoder model not available",
            "detail": _model_error,
        }), 503

    t0 = time.time()

    try:
        # Build query-passage pairs
        texts = [p.get("content", "") for p in passages]
        pairs = [(query, t) for t in texts]

        # Score all pairs
        scores = model.predict(pairs)

        # Attach scores to passages
        scored = []
        for passage, score in zip(passages, scores):
            entry = dict(passage)  # shallow copy
            entry["score"] = float(score)
            scored.append(entry)

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        # Apply top_k if requested
        if top_k is not None and top_k > 0:
            scored = scored[:top_k]

        latency_ms = (time.time() - t0) * 1000

        return jsonify({
            "results": scored,
            "model": _model_name,
            "count": len(scored),
            "latency_ms": round(latency_ms, 1),
        })

    except Exception as exc:
        logger.exception("Reranking failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check with model status."""
    model = _load_model()
    return jsonify({
        "status": "ok" if model is not None else "degraded",
        "model": _model_name,
        "model_loaded": model is not None,
        "load_time_s": round(_model_load_time, 2) if _model_load_time else None,
        "error": _model_error,
        "device": str(getattr(model, "device", "n/a")) if model else None,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cross-encoder re-ranking service")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5002, help="Bind port (default: 5002)")
    parser.add_argument(
        "--model",
        default=os.environ.get("RERANK_MODEL", _model_name),
        help="Cross-encoder model name",
    )
    parser.add_argument("--preload", action="store_true", help="Preload model at startup")
    args = parser.parse_args()

    _model_name = args.model

    if args.preload:
        logger.info("Preloading model at startup...")
        _load_model(args.model)

    app.run(host=args.host, port=args.port, threaded=True)
