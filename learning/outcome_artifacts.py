"""Portable outcome-feedback artifacts built from CE learning outcomes.

The adapter deliberately exports operational outcome data and explicit external
ground truth while excluding prompts, credentials, private reasoning, and source
payloads.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from .portable_artifacts import LearningArtifact

ARTIFACT_TYPE = "outcome-feedback"


def _mapping(value: Any) -> Mapping[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return value
    raise TypeError("outcome and feedback values must be mappings or dataclasses")


def build_outcome_artifact(
    outcome: Any,
    *,
    feedback: Any | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> LearningArtifact:
    """Convert an autonomous outcome into a portable learning artifact."""
    record = _mapping(outcome)
    feedback_record = _mapping(feedback) if feedback is not None else {}

    ground_truth = {
        "source": record.get("ground_truth_source", "none"),
        "correct": record.get("ground_truth_correct"),
        "evidence_id": record.get("ground_truth_evidence_id"),
    }

    payload = {
        "outcome": {
            "task_id": record.get("task_id"),
            "task_type": record.get("task_type"),
            "selected_model": record.get("thompson_selected"),
            "actual_model_used": record.get("actual_model_used"),
            "candidates": record.get("thompson_candidates", []),
            "quality_score": record.get("quality_score"),
            "latency_ms": record.get("latency_ms"),
            "cost": record.get("cost"),
        },
        "feedback": feedback_record,
        "ground_truth": ground_truth,
    }

    artifact_provenance = dict(provenance or {})
    artifact_provenance.setdefault("source", "claude-ensemble")
    artifact_provenance.setdefault("task_id", record.get("task_id"))
    artifact_provenance.setdefault("task_type", record.get("task_type"))

    return LearningArtifact.create(
        artifact_type=ARTIFACT_TYPE,
        payload=payload,
        provenance=artifact_provenance,
        created_at=record.get("timestamp"),
    )
