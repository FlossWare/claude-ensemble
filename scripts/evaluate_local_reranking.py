#!/usr/bin/env python3
"""Evaluate the provisioned local reranker against a versioned CE fixture.

Model weights must already be installed locally. This script never downloads
models. It reports relevance metrics and median CPU latency for 1/5/10/20 inputs.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from runtime.reranking import RerankingEngine


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "docs" / "evaluation" / "reranking-fixtures.json"


def ndcg_at_k(ranked_ids: list[str], relevant: set[str], k: int = 10) -> float:
    def dcg(ids: list[str]) -> float:
        return sum(
            (1.0 / math.log2(position + 2))
            for position, chunk_id in enumerate(ids[:k])
            if chunk_id in relevant
        )
    ideal_count = min(len(relevant), k)
    ideal = sum(1.0 / math.log2(position + 2) for position in range(ideal_count))
    return dcg(ranked_ids) / ideal if ideal else 0.0


def mrr_at_k(ranked_ids: list[str], relevant: set[str], k: int = 10) -> float:
    for position, chunk_id in enumerate(ranked_ids[:k], 1):
        if chunk_id in relevant:
            return 1.0 / position
    return 0.0


def build_request(fixture: dict[str, Any], candidates: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    prepared = []
    for raw in candidates:
        candidate = dict(raw)
        candidate["matched_exact_identifiers"] = []
        candidate["provenance"] = {"origin": "versioned-reranking-evaluation-fixture"}
        prepared.append(candidate)
    return {
        "request_id": "local-reranking-evaluation",
        "profile": {"name": "default-reranker", "version": "0.1"},
        "query": fixture["query"],
        "candidates": prepared,
        "limit": limit,
    }


def main() -> int:
    fixture_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FIXTURE
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        candidates = sorted(fixture["candidates"], key=lambda item: item["prior_rank"])
        relevant = set(fixture["relevant_chunk_ids"])
        if len(candidates) != 20 or len(relevant) < 1:
            raise ValueError("fixture must contain exactly 20 candidates and at least one relevant chunk")
        engine = RerankingEngine()
        # Load local weights before measuring per-request latency.
        engine._load()
    except Exception as exc:
        print(f"FAIL: unable to load fixture or local model ({type(exc).__name__})", file=sys.stderr)
        return 1

    baseline_ids = [item["chunk_id"] for item in candidates]
    try:
        full_result = engine.rerank(build_request(fixture, candidates, 20))
    except Exception as exc:
        print(f"FAIL: local reranking inference failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    reranked_ids = [item["chunk_id"] for item in full_result["candidates"]]
    quality = {
        "baseline_ndcg_at_10": round(ndcg_at_k(baseline_ids, relevant), 6),
        "reranked_ndcg_at_10": round(ndcg_at_k(reranked_ids, relevant), 6),
        "baseline_mrr_at_10": round(mrr_at_k(baseline_ids, relevant), 6),
        "reranked_mrr_at_10": round(mrr_at_k(reranked_ids, relevant), 6),
    }
    quality["ndcg_improved"] = quality["reranked_ndcg_at_10"] > quality["baseline_ndcg_at_10"]
    quality["mrr_improved"] = quality["reranked_mrr_at_10"] > quality["baseline_mrr_at_10"]

    latency = {}
    for count in (1, 5, 10, 20):
        subset = candidates[:count]
        request = build_request(fixture, subset, count)
        samples = []
        for _ in range(3):
            start = time.perf_counter()
            engine.rerank(request)
            samples.append((time.perf_counter() - start) * 1000.0)
        latency[str(count)] = round(statistics.median(samples), 2)

    report = {
        "fixture_version": fixture.get("fixture_version"),
        "query_id": fixture.get("query_id"),
        "model_id": full_result["candidates"][0]["evidence"]["model_id"],
        "model_version": full_result["candidates"][0]["evidence"]["model_version"],
        "device": "cpu",
        "sequence_length": 512,
        "quality": quality,
        "median_latency_ms_by_candidate_count": latency,
        "baseline_order": baseline_ids,
        "reranked_order": reranked_ids,
        "note": "One fixture is a smoke/evaluation baseline, not sufficient evidence for a production quality claim.",
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
