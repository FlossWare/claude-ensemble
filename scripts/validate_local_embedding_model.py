#!/usr/bin/env python3
"""Validate the provisioned Nomic model offline on CPU.

This intentionally requires pre-provisioned local model files. It must never
download weights or resolve a model from a remote repository.
"""
from __future__ import annotations

import math
import os
import sys

# Set offline guards before Sentence Transformers / Transformers are imported.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from pathlib import Path

from runtime.embedding import EXPECTED_DIMENSIONS, EXPECTED_MODEL_ID, EmbeddingEngine


def main() -> int:
    expected_revision = os.environ.get("CE_EMBEDDING_MODEL_VERSION", "")
    model_path = Path(os.environ.get(
        "CE_EMBEDDING_MODEL_PATH",
        str(Path.home() / ".FlossWare" / "models" / "nomic-embed-text-v1.5"),
    )).expanduser()
    if len(expected_revision) != 40 or any(ch not in "0123456789abcdef" for ch in expected_revision):
        print("FAIL: CE_EMBEDDING_MODEL_VERSION must be an immutable 40-character commit SHA", file=sys.stderr)
        return 1
    if model_path.resolve().name != expected_revision:
        print("FAIL: resolved model snapshot directory does not match the pinned revision", file=sys.stderr)
        return 1

    engine = EmbeddingEngine()
    try:
        model, results = engine.embed(
            [
                {"input_id": "offline-query-check", "input_type": "query",
                 "text": "How are source revisions indexed?"},
                {"input_id": "offline-document-check", "input_type": "document",
                 "text": "Index stores vector representations of source revisions."},
            ],
            "l2",
        )
    except Exception as exc:
        print(f"FAIL: local embedding validation failed ({type(exc).__name__})", file=sys.stderr)
        return 1

    if model.get("model_id") != EXPECTED_MODEL_ID:
        print("FAIL: loaded model identity does not match the configured Nomic profile", file=sys.stderr)
        return 1
    if model.get("model_version") != expected_revision:
        print("FAIL: loaded model metadata does not match the pinned revision", file=sys.stderr)
        return 1
    if model.get("dimensions") != EXPECTED_DIMENSIONS:
        print("FAIL: loaded model does not produce 768-dimensional vectors", file=sys.stderr)
        return 1
    if len(results) != 2 or any(item.get("status") != "complete" for item in results):
        print("FAIL: query/document inference did not complete for both inputs", file=sys.stderr)
        return 1

    for item in results:
        vector = item.get("vector")
        if not isinstance(vector, list) or len(vector) != EXPECTED_DIMENSIONS:
            print("FAIL: inference returned an invalid vector shape", file=sys.stderr)
            return 1
        if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in vector):
            print("FAIL: inference returned a non-finite vector value", file=sys.stderr)
            return 1
        norm = math.sqrt(sum(float(value) * float(value) for value in vector))
        if not math.isfinite(norm) or abs(norm - 1.0) > 1e-4:
            print("FAIL: L2-normalized vector is outside tolerance", file=sys.stderr)
            return 1

    print("PASS: Nomic model loaded from local files in offline CPU mode.")
    print("PASS: query/document inference completed with 768-dimensional finite L2-normalized vectors.")
    print(f"PASS: resolved local model snapshot matches pinned revision {expected_revision}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
