#!/usr/bin/env python3
"""Build a portable, provenance-preserving artifact from a GA run."""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Mapping

from learning.portable_artifacts import LearningArtifact


OPTIMIZER_VERSION = "0.1"


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("GA summary timestamp is required")
    for fmt in ("%Y%m%d_%H%M%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(value, fmt)
            # The GA filename timestamp has no timezone; preserve that fact.
            return parsed.isoformat()
        except ValueError:
            continue
    raise ValueError(f"unsupported GA summary timestamp: {value!r}")


def _candidate_parameters(candidate: Mapping[str, Any]) -> dict[str, Any]:
    nested = candidate.get("parameters")
    raw = nested if isinstance(nested, Mapping) else candidate
    return {
        str(key): value
        for key, value in raw.items()
        if key != "fitness" and isinstance(value, (str, int, float, bool, type(None)))
    }


def build_ga_learning_artifact(
    summary: Mapping[str, Any],
    best_by_system: Mapping[str, Any],
    fallback_parameters: Mapping[str, Any],
    *,
    best_parameters_source: str,
    summary_source: str,
) -> LearningArtifact:
    """Build a deterministic artifact; synthetic fitness is not ground truth."""
    timestamp = summary.get("timestamp")
    # Do not fabricate provenance or collapse unrelated malformed runs into
    # the same "ga-unknown" idempotency key.
    created_at = _timestamp(timestamp)
    timestamp_text = timestamp
    run_id = f"ga-{timestamp_text}"
    selected_parameters: dict[str, dict[str, Any]] = {}
    objectives: dict[str, float] = {}
    top_candidates: dict[str, list[dict[str, Any]]] = {}

    for system, candidates in best_by_system.items():
        if not isinstance(candidates, list) or not candidates:
            continue
        normalized = []
        for rank, candidate in enumerate(candidates[:3], start=1):
            if not isinstance(candidate, Mapping):
                continue
            parameters = _candidate_parameters(candidate)
            fitness = candidate.get("fitness")
            if (
                isinstance(fitness, (int, float))
                and not isinstance(fitness, bool)
                and math.isfinite(float(fitness))
            ):
                normalized.append({
                    "rank": rank,
                    "fitness": float(fitness),
                    "parameters": parameters,
                })
        if not normalized:
            continue
        top_candidates[str(system)] = normalized
        selected_parameters[str(system)] = dict(normalized[0]["parameters"])
        objectives[str(system)] = normalized[0]["fitness"]

    payload = {
        "run_id": run_id,
        "run_timestamp": timestamp_text,
        "optimizer": {"name": "genetic-algorithm", "version": OPTIMIZER_VERSION},
        "population_size": summary.get("population_size"),
        "generations": summary.get("generations"),
        "total_evaluations": summary.get("total_evaluations"),
        "evaluation_scope": {
            "systems_evaluated": sorted(selected_parameters),
            "evaluation_mode": "synthetic-local-evaluators",
            "api_calls": 0,
        },
        "candidate_population": {
            "kind": "top_candidates_per_system",
            "candidates": top_candidates,
        },
        "objectives": objectives,
        "selected_parameters": selected_parameters,
        "fallback_parameters": dict(fallback_parameters),
        "evidence": {
            "kind": "synthetic-fitness",
            "externally_validated": False,
            "confidence": None,
        },
        "configuration_status": "candidate",
        "knowledge_promotion": {
            "eligible": False,
            "reason": "synthetic GA fitness alone is not operational evidence",
        },
    }
    return LearningArtifact.create(
        "ga.tuning.result",
        payload,
        source="claude-ensemble.ga-tuning",
        provenance={
            "run_id": run_id,
            "optimizer": "genetic-algorithm",
            "optimizer_version": OPTIMIZER_VERSION,
            "source_files": {
                "summary": summary_source,
                "best_parameters": best_parameters_source,
            },
            "candidate_count_by_system": {
                system: len(candidates) for system, candidates in top_candidates.items()
            },
        },
        created_at=created_at,
    )
