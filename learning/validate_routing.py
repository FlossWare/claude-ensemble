#!/usr/bin/env python3
"""Validation Framework for GA Model Routing.

Simulates routing 100+ real RH tasks using the capability matrix.
Measures routing accuracy without any API calls (all local).

GA will use this to evaluate fitness of evolved scoring functions.

Key metrics:
- Routing consistency: Does "recommended model" match expected based on task?
- Cost prediction: Does recommended model have lowest cost estimate?
- Confidence: Are CI bounds tight enough for decision-making?
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from scoring_function import (
    ScoringFunction,
    calculate_confidence_interval,
    detect_domain_markers,
    detect_task_type,
)


# Cost Model (for GA optimization)
# ---------

MODEL_COST_PER_MTOK: dict[str, float] = {
    "haiku": 0.80,    # Cheapest
    "gemini": 1.50,   # 2x Haiku
    "sonnet": 3.00,   # 3.75x Haiku
    "opus": 6.00,     # 7.5x Haiku (most expensive)
}

MODEL_SPEED_MS: dict[str, float] = {
    "haiku": 100.0,   # Fastest
    "gemini": 150.0,
    "sonnet": 200.0,
    "opus": 300.0,    # Slowest
}


@dataclass
class TaskProfile:
    """Profile of a single task from RH codebase."""

    name: str
    filepath: str
    content: str
    file_size_lines: int
    task_type: str | None = None
    domain_markers: dict[str, bool] | None = None

    def __post_init__(self):
        """Auto-detect task type and domains on creation."""
        if self.task_type is None:
            self.task_type = detect_task_type(self.content) or "code_review"
        if self.domain_markers is None:
            self.domain_markers = detect_domain_markers(self.content)


@dataclass
class RoutingDecision:
    """Result of routing a single task."""

    task_name: str
    task_type: str
    best_model: str
    best_score: float
    best_ci_lower: float
    best_ci_upper: float
    workable_models: list[str]
    predicted_cost_usd: float
    predicted_latency_ms: float
    confidence: float


class RoutingValidator:
    """Validates routing decisions against ground truth."""

    def __init__(self, matrix_path: Path):
        """Load capability matrix."""
        with open(matrix_path) as f:
            data = json.load(f)
        self.scores = data.get("scores", {})
        self.thresholds = data.get("routing_thresholds", {})
        self.scoring_fn = ScoringFunction()

    def route_task(self, task: TaskProfile) -> RoutingDecision:
        """Find best model for a task using capability matrix."""
        task_type = task.task_type or "code_review"
        models = ["haiku", "sonnet", "opus", "gemini"]

        # Look up scores from matrix
        candidates = []
        for model in models:
            key = f"{model}:{task_type}"
            entry = self.scores.get(key)

            if not entry:
                # Fallback to scoring function if not in matrix
                score = self.scoring_fn.score(
                    model=model,
                    task_type=task_type,
                    file_size_lines=task.file_size_lines,
                    domain_markers=task.domain_markers or {},
                )
                ci_lower, ci_upper = calculate_confidence_interval(score, samples=1)
            else:
                score = entry["score"]
                ci_lower = entry.get("ci_lower", score - 0.1)
                ci_upper = entry.get("ci_upper", score + 0.1)

            candidates.append({
                "model": model,
                "score": score,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
            })

        # Find best model (highest score in credible interval)
        best = max(candidates, key=lambda c: c["score"])
        best_model = best["model"]

        # Find workable models (threshold_workable or higher)
        threshold_workable = self.thresholds.get("threshold_workable", 0.60)
        workable = [
            c["model"] for c in candidates
            if c["score"] >= threshold_workable
        ]

        # Estimate cost and latency
        predicted_cost = self._estimate_cost(best_model, task.file_size_lines)
        predicted_latency = MODEL_SPEED_MS[best_model]

        # Confidence: How tight is the CI around best model?
        ci_width = best["ci_upper"] - best["ci_lower"]
        confidence = max(0.0, 1.0 - (ci_width / 0.5))  # 95% if width <= 0.5

        return RoutingDecision(
            task_name=task.name,
            task_type=task_type,
            best_model=best_model,
            best_score=round(best["score"], 3),
            best_ci_lower=round(best["ci_lower"], 3),
            best_ci_upper=round(best["ci_upper"], 3),
            workable_models=workable,
            predicted_cost_usd=predicted_cost,
            predicted_latency_ms=predicted_latency,
            confidence=round(confidence, 3),
        )

    @staticmethod
    def _estimate_cost(model: str, file_size_lines: int) -> float:
        """Estimate cost for routing a task to a model."""
        # Rough heuristic: 100 lines ~= 200 tokens
        estimated_tokens = file_size_lines * 2 / 1000  # Convert to 1000-token units
        cost_per_mtok = MODEL_COST_PER_MTOK.get(model, 3.0)
        return round(estimated_tokens * cost_per_mtok / 1000, 4)


class ValidationReport:
    """Summarizes routing validation results."""

    def __init__(self, decisions: list[RoutingDecision]):
        self.decisions = decisions

    @property
    def total_tasks(self) -> int:
        return len(self.decisions)

    def model_selection_freq(self) -> dict[str, int]:
        """How often each model was selected as "best"."""
        freq = {}
        for d in self.decisions:
            freq[d.best_model] = freq.get(d.best_model, 0) + 1
        return freq

    def avg_cost_per_model(self) -> dict[str, float]:
        """Average predicted cost by model."""
        costs = {}
        for d in self.decisions:
            if d.best_model not in costs:
                costs[d.best_model] = []
            costs[d.best_model].append(d.predicted_cost_usd)
        return {
            model: round(sum(c) / len(c), 4)
            for model, c in costs.items()
        }

    def avg_latency_per_model(self) -> dict[str, float]:
        """Average predicted latency by model."""
        latencies = {}
        for d in self.decisions:
            if d.best_model not in latencies:
                latencies[d.best_model] = []
            latencies[d.best_model].append(d.predicted_latency_ms)
        return {
            model: round(sum(l) / len(l), 1)
            for model, l in latencies.items()
        }

    def avg_confidence(self) -> float:
        """Average routing confidence across all tasks."""
        if not self.decisions:
            return 0.0
        return round(sum(d.confidence for d in self.decisions) / len(self.decisions), 3)

    def workable_model_count(self) -> dict[str, int]:
        """How many times each model appears in 'workable' set."""
        count = {}
        for d in self.decisions:
            for model in d.workable_models:
                count[model] = count.get(model, 0) + 1
        return count

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "total_tasks_evaluated": self.total_tasks,
            "model_selection_frequency": self.model_selection_freq(),
            "average_cost_usd_per_model": self.avg_cost_per_model(),
            "average_latency_ms_per_model": self.avg_latency_per_model(),
            "average_routing_confidence": self.avg_confidence(),
            "workable_model_frequency": self.workable_model_count(),
            "decisions": [
                {
                    "task_name": d.task_name,
                    "task_type": d.task_type,
                    "best_model": d.best_model,
                    "best_score": d.best_score,
                    "ci_bounds": [d.best_ci_lower, d.best_ci_upper],
                    "workable_models": d.workable_models,
                    "predicted_cost_usd": d.predicted_cost_usd,
                    "confidence": d.confidence,
                }
                for d in self.decisions
            ],
        }

    def print_summary(self):
        """Print validation results to stdout."""
        print("Routing Validation Report")
        print("=" * 70)
        print(f"Total tasks evaluated: {self.total_tasks}")
        print()

        print("Model Selection Frequency (tasks routed to each model):")
        for model, count in sorted(self.model_selection_freq().items()):
            pct = 100 * count / self.total_tasks
            print(f"  {model:8} {count:3} tasks ({pct:5.1f}%)")

        print()
        print("Average Cost per Model (predicted):")
        for model, cost in sorted(self.avg_cost_per_model().items()):
            print(f"  {model:8} ${cost:.6f} per task")

        print()
        print("Average Latency per Model (predicted):")
        for model, latency in sorted(self.avg_latency_per_model().items()):
            print(f"  {model:8} {latency:6.1f} ms")

        print()
        print(f"Average Routing Confidence: {self.avg_confidence():.3f}")
        print()

        print("Workable Model Frequency (appeared in acceptable set):")
        for model, count in sorted(self.workable_model_count().items()):
            pct = 100 * count / self.total_tasks
            print(f"  {model:8} {count:3} tasks ({pct:5.1f}%)")


def validate_from_file_corpus(
    file_paths: list[Path],
    matrix_path: Path,
) -> ValidationReport:
    """Validate routing on real files from RH codebase.

    Args:
        file_paths: Paths to .py, .java, .md, .sh files to analyze
        matrix_path: Path to capability_matrix.json

    Returns:
        Validation report with routing decisions
    """
    validator = RoutingValidator(matrix_path)
    decisions = []

    for filepath in file_paths:
        if not filepath.exists():
            continue

        try:
            content = filepath.read_text(errors="ignore")
            lines = content.count("\n")

            task = TaskProfile(
                name=filepath.stem,
                filepath=str(filepath),
                content=content,
                file_size_lines=lines,
            )

            decision = validator.route_task(task)
            decisions.append(decision)

        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            continue

    return ValidationReport(decisions)


def main():
    """Run validation on RH codebase."""
    matrix_path = Path(__file__).parent / "capability_matrix.json"

    if not matrix_path.exists():
        print(f"Error: {matrix_path} not found")
        print("Run: python expand_capability_matrix.py first")
        return

    # Find RH codebase files
    rh_base = Path("/home/sfloess/Development/redhat/scm/gitlab/search-engineering/disseminator")
    if not rh_base.exists():
        print(f"RH codebase not found at {rh_base}")
        return

    # Sample files for testing
    files_to_validate = list(rh_base.glob("src/**/*.java"))[:20]
    files_to_validate.extend(list(rh_base.glob("**/*.md"))[:10])
    files_to_validate.extend(list(rh_base.glob("scripts/**/*.sh"))[:5])

    print(f"Validating routing on {len(files_to_validate)} files...")
    print()

    report = validate_from_file_corpus(files_to_validate, matrix_path)
    report.print_summary()

    # Save report
    report_path = Path(__file__).parent / "validation_report.json"
    with open(report_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"\nDetailed report saved: {report_path}")


if __name__ == "__main__":
    main()
