"""
WORKER 2: Performance Logger
============================

Records compression/cache effectiveness metrics for each workflow.

Captures:
- Original vs compressed tokens (reduction %)
- Cache hit/miss and source
- Quality metrics (semantic similarity, test pass rate)
- Latency impact (compression overhead)
- Cost impact

Stores in append-only JSONL format for audit trail and Phase 3 analysis.

Author: Sonnet 4.5
"""

import json
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum


class CacheSource(Enum):
    """Source of cache hit."""
    PROMPT_CACHE = "prompt_cache"
    REDIS = "redis"
    MEMORY = "memory"
    NONE = "none"


@dataclass
class CompressionMetrics:
    """Compression effectiveness metrics."""
    original_tokens: int
    compressed_tokens: int
    method: str = "hierarchical_summarizer"
    latency_ms: float = 0.0
    reduction_percent: float = field(init=False)

    def __post_init__(self):
        """Calculate reduction percentage."""
        if self.original_tokens > 0:
            self.reduction_percent = (
                (self.original_tokens - self.compressed_tokens) /
                self.original_tokens * 100
            )
        else:
            self.reduction_percent = 0.0


@dataclass
class CacheMetrics:
    """Cache effectiveness metrics."""
    is_hit: bool
    source: str = "none"  # prompt_cache, redis, memory, none
    cache_tokens_used: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass
class QualityMetrics:
    """Quality impact metrics."""
    test_pass_rate: Optional[float] = None  # 0.0-1.0
    semantic_similarity: Optional[float] = None  # 0.0-1.0 (vs uncompressed)
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class PerformanceLogEntry:
    """Complete performance log entry for a single API call."""
    call_id: str
    timestamp: str
    workflow_type: str
    model: str
    compression: CompressionMetrics
    cache: CacheMetrics
    quality: QualityMetrics
    tags: List[str] = field(default_factory=list)

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        result = {
            "call_id": self.call_id,
            "timestamp": self.timestamp,
            "workflow_type": self.workflow_type,
            "model": self.model,
            "compression": asdict(self.compression),
            "cache": asdict(self.cache),
            "quality": asdict(self.quality),
            "tags": self.tags,
        }
        return result


class PerformanceLogger:
    """
    Logs compression and cache effectiveness metrics.

    Thread-safe append-only JSONL logger following cost_tracking/logger.py pattern.
    Each entry captures full performance characteristics for a single API call.
    """

    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize the logger.

        Args:
            log_file: Path to JSONL log file. Defaults to
                ~/.claude/metrics/performance_calls.jsonl
        """
        if log_file is None:
            log_file = Path.home() / ".claude" / "metrics" / "performance_calls.jsonl"

        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._call_counter = 0

    def log_call(
        self,
        workflow_type: str,
        model: str,
        original_tokens: int,
        compressed_tokens: int,
        cache_hit: bool = False,
        cache_source: str = "none",
        test_pass_rate: Optional[float] = None,
        semantic_similarity: Optional[float] = None,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        compression_latency_ms: float = 0.0,
        call_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> PerformanceLogEntry:
        """
        Log a single API call with performance metrics.

        Args:
            workflow_type: Type of workflow (e.g., "code_review")
            model: Model used (haiku, sonnet, opus, gemini)
            original_tokens: Token count before compression
            compressed_tokens: Token count after compression
            cache_hit: Whether this call hit cache
            cache_source: Source of cache (prompt_cache, redis, memory, none)
            test_pass_rate: Quality metric: fraction of tests passing
            semantic_similarity: Quality metric: similarity to uncompressed (0.0-1.0)
            output_tokens: Number of output tokens
            cost_usd: Cost in USD
            compression_latency_ms: Latency of compression in milliseconds
            call_id: Unique call ID (auto-generated if None)
            tags: Optional list of tags for this call

        Returns:
            PerformanceLogEntry with all logged information
        """
        if call_id is None:
            with self._lock:
                self._call_counter += 1
                call_id = f"perf_{self._call_counter:08d}"

        if tags is None:
            tags = []

        # Create metrics objects
        compression = CompressionMetrics(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            latency_ms=compression_latency_ms,
        )

        cache = CacheMetrics(
            is_hit=cache_hit,
            source=cache_source,
        )

        quality = QualityMetrics(
            test_pass_rate=test_pass_rate,
            semantic_similarity=semantic_similarity,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

        # Create log entry
        entry = PerformanceLogEntry(
            call_id=call_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            workflow_type=workflow_type,
            model=model,
            compression=compression,
            cache=cache,
            quality=quality,
            tags=tags,
        )

        # Write to log (thread-safe)
        with self._lock:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        return entry

    def read_logs(self) -> List[PerformanceLogEntry]:
        """
        Read all logs from the file.

        Returns:
            List of PerformanceLogEntry objects
        """
        if not self.log_file.exists():
            return []

        entries = []
        with self._lock:
            with open(self.log_file, "r") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            # Reconstruct dataclass objects
                            comp_data = data["compression"].copy()
                            comp_data.pop("reduction_percent", None)  # Remove calculated field
                            compression = CompressionMetrics(**comp_data)
                            cache = CacheMetrics(**data["cache"])
                            quality = QualityMetrics(**data["quality"])

                            entry = PerformanceLogEntry(
                                call_id=data["call_id"],
                                timestamp=data["timestamp"],
                                workflow_type=data["workflow_type"],
                                model=data["model"],
                                compression=compression,
                                cache=cache,
                                quality=quality,
                                tags=data.get("tags", []),
                            )
                            entries.append(entry)
                        except (json.JSONDecodeError, KeyError) as e:
                            print(f"Warning: Could not parse log entry: {e}")

        return entries

    def get_stats(self) -> Dict:
        """
        Get aggregate statistics across all logged calls.

        Returns:
            Dictionary with aggregated metrics by model and workflow
        """
        entries = self.read_logs()

        if not entries:
            return {
                "total_calls": 0,
                "total_tokens_original": 0,
                "total_tokens_compressed": 0,
                "by_model": {},
                "by_workflow": {},
            }

        # Aggregate by model
        by_model = {}
        for entry in entries:
            model = entry.model
            if model not in by_model:
                by_model[model] = {
                    "calls": 0,
                    "tokens_original": 0,
                    "tokens_compressed": 0,
                    "cache_hits": 0,
                    "quality_scores": [],
                }

            stats = by_model[model]
            stats["calls"] += 1
            stats["tokens_original"] += entry.compression.original_tokens
            stats["tokens_compressed"] += entry.compression.compressed_tokens
            if entry.cache.is_hit:
                stats["cache_hits"] += 1
            if entry.quality.semantic_similarity is not None:
                stats["quality_scores"].append(entry.quality.semantic_similarity)

        # Calculate averages
        for model, stats in by_model.items():
            total_tokens = stats["tokens_original"]
            stats["compression_percent"] = (
                (stats["tokens_original"] - stats["tokens_compressed"]) /
                total_tokens * 100 if total_tokens > 0 else 0
            )
            stats["cache_hit_rate"] = (
                stats["cache_hits"] / stats["calls"] if stats["calls"] > 0 else 0
            )
            if stats["quality_scores"]:
                stats["avg_quality"] = sum(stats["quality_scores"]) / len(stats["quality_scores"])
            del stats["quality_scores"]  # Remove raw scores from output

        # Aggregate by workflow
        by_workflow = {}
        for entry in entries:
            workflow = entry.workflow_type
            if workflow not in by_workflow:
                by_workflow[workflow] = {
                    "calls": 0,
                    "tokens_original": 0,
                    "tokens_compressed": 0,
                    "cache_hits": 0,
                }

            stats = by_workflow[workflow]
            stats["calls"] += 1
            stats["tokens_original"] += entry.compression.original_tokens
            stats["tokens_compressed"] += entry.compression.compressed_tokens
            if entry.cache.is_hit:
                stats["cache_hits"] += 1

        for workflow, stats in by_workflow.items():
            total_tokens = stats["tokens_original"]
            stats["compression_percent"] = (
                (stats["tokens_original"] - stats["tokens_compressed"]) /
                total_tokens * 100 if total_tokens > 0 else 0
            )
            stats["cache_hit_rate"] = (
                stats["cache_hits"] / stats["calls"] if stats["calls"] > 0 else 0
            )

        return {
            "total_calls": len(entries),
            "total_tokens_original": sum(e.compression.original_tokens for e in entries),
            "total_tokens_compressed": sum(e.compression.compressed_tokens for e in entries),
            "by_model": by_model,
            "by_workflow": by_workflow,
        }

    def clear_logs(self) -> None:
        """Clear all logged data. Use with caution."""
        with self._lock:
            self.log_file.unlink(missing_ok=True)
        self._call_counter = 0


def main():
    """Demo the logger."""
    logger = PerformanceLogger()

    # Log some sample calls
    print("Performance Logger Demo")
    print("=" * 60)

    test_data = [
        {
            "workflow_type": "code_review",
            "model": "opus",
            "original_tokens": 12500,
            "compressed_tokens": 7300,
            "semantic_similarity": 0.94,
        },
        {
            "workflow_type": "deployment",
            "model": "haiku",
            "original_tokens": 8000,
            "compressed_tokens": 6400,
            "cache_hit": True,
            "semantic_similarity": 0.98,
        },
        {
            "workflow_type": "release_notes",
            "model": "sonnet",
            "original_tokens": 15000,
            "compressed_tokens": 7800,
            "test_pass_rate": 1.0,
            "semantic_similarity": 0.92,
        },
    ]

    for data in test_data:
        entry = logger.log_call(**data)
        print(f"\n✓ Logged {data['workflow_type']:20} | "
              f"{data['model']:8} | "
              f"Compression: {entry.compression.reduction_percent:.1f}%")

    # Show stats
    print("\n" + "=" * 60)
    print("Aggregate Statistics")
    print("=" * 60)
    stats = logger.get_stats()
    print(f"Total calls: {stats['total_calls']}")
    print(f"Tokens original: {stats['total_tokens_original']}")
    print(f"Tokens compressed: {stats['total_tokens_compressed']}")

    if stats["by_model"]:
        print("\nBy Model:")
        for model, model_stats in stats["by_model"].items():
            print(f"  {model:10} | calls: {model_stats['calls']:3} | "
                  f"compression: {model_stats['compression_percent']:5.1f}% | "
                  f"cache_hit_rate: {model_stats['cache_hit_rate']:.0%}")


if __name__ == "__main__":
    main()
