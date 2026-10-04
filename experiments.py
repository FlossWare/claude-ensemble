"""Minimal, dependency-free experiment definitions and evaluation."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "experiment-result"
VERSION = "0.1"
DEFAULT_PATH = Path(__file__).resolve().parent / "learning" / "experiments.jsonl"
DIRECTIONS = {"higher", "lower"}

def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("experiment values must be JSON-serializable") from exc
    return value

def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)

@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    hypothesis: str
    baseline: Any
    variant: Any
    inputs: Any
    measurements: dict[str, dict[str, Any]]

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise ValueError("experiment_id must be a non-empty string")
        if not isinstance(self.hypothesis, str) or not self.hypothesis.strip():
            raise ValueError("hypothesis must be a non-empty string")
        _jsonable(self.baseline)
        _jsonable(self.variant)
        _jsonable(self.inputs)
        if not isinstance(self.measurements, dict) or not self.measurements:
            raise ValueError("measurements must be a non-empty object")
        for name, measurement in self.measurements.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("measurement names must be non-empty strings")
            if not isinstance(measurement, dict):
                raise ValueError(f"measurement {name!r} must be an object")
            direction = measurement.get("direction", "higher")
            if direction not in DIRECTIONS:
                raise ValueError(f"measurement {name!r} direction must be 'higher' or 'lower'")
            _number(measurement.get("baseline"), f"{name}.baseline")
            _number(measurement.get("variant"), f"{name}.variant")

        # frozen dataclasses do not freeze nested dictionaries/lists. Snapshot the
        # validated JSON-compatible values so callers cannot mutate the experiment
        # definition after construction and invalidate evaluation/digest identity.
        object.__setattr__(self, "baseline", copy.deepcopy(self.baseline))
        object.__setattr__(self, "variant", copy.deepcopy(self.variant))
        object.__setattr__(self, "inputs", copy.deepcopy(self.inputs))
        object.__setattr__(self, "measurements", copy.deepcopy(self.measurements))

    @classmethod
    def from_dict(cls, data: Any) -> "Experiment":
        if not isinstance(data, dict):
            raise ValueError("experiment must be a JSON object")
        return cls(data.get("experiment_id"), data.get("hypothesis"), data.get("baseline"),
                   data.get("variant"), data.get("inputs", {}), data.get("measurements"))

    def to_dict(self) -> dict[str, Any]:
        return {"experiment_id": self.experiment_id, "hypothesis": self.hypothesis,
                "baseline": self.baseline, "variant": self.variant, "inputs": self.inputs,
                "measurements": self.measurements}

@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    hypothesis: str
    winner: str
    measurements: dict[str, dict[str, Any]]
    input_digest: str
    experiment_digest: str
    schema: str = SCHEMA
    version: str = VERSION

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "version": self.version, "experiment_id": self.experiment_id,
                "hypothesis": self.hypothesis, "winner": self.winner, "measurements": self.measurements,
                "input_digest": self.input_digest, "experiment_digest": self.experiment_digest}

    @classmethod
    def from_dict(cls, data: Any) -> "ExperimentResult":
        if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("version") != VERSION:
            raise ValueError("unsupported experiment result schema")
        return cls(data.get("experiment_id"), data.get("hypothesis"), data.get("winner"),
                   data.get("measurements"), data.get("input_digest"), data.get("experiment_digest"))

def evaluate(experiment: Experiment) -> ExperimentResult:
    scores = {"baseline": 0.0, "variant": 0.0}
    measurements = {}
    for name, measurement in experiment.measurements.items():
        baseline = _number(measurement["baseline"], f"{name}.baseline")
        variant = _number(measurement["variant"], f"{name}.variant")
        direction = measurement.get("direction", "higher")
        bscore, vscore = (baseline, variant) if direction == "higher" else (-baseline, -variant)
        winner = "variant" if vscore > bscore else "baseline" if bscore > vscore else "tie"
        if winner != "tie":
            scores[winner] += 1.0
        measurements[name] = {"baseline": baseline, "variant": variant,
                              "direction": direction, "winner": winner}
    overall = "variant" if scores["variant"] > scores["baseline"] else "baseline" if scores["baseline"] > scores["variant"] else "tie"
    return ExperimentResult(experiment.experiment_id, experiment.hypothesis, overall, measurements,
                            _digest(experiment.inputs), _digest(experiment.to_dict()))

class ExperimentStore:
    """Append-only JSONL store for lightweight experiment results."""
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_PATH

    def record(self, result: ExperimentResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result.to_dict(), sort_keys=True) + "\n")

    def get(self, experiment_id: str) -> ExperimentResult | None:
        if not isinstance(experiment_id, str) or not experiment_id or not self.path.exists():
            return None
        for line in reversed(self.path.read_text(encoding="utf-8").splitlines()):
            try:
                data = json.loads(line)
                if data.get("experiment_id") == experiment_id:
                    return ExperimentResult.from_dict(data)
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
        return None
