#!/usr/bin/env python3
"""
GA Tuning configuration.

Controls when and how genetic algorithm optimization runs.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class GAConfig:
    """Configuration for GA tuning"""

    # When to run GA optimization
    tuning_interval_seconds: int = 3600  # Default: every hour (3600 seconds)

    # GA-optimized parameters (defaults)
    cache_ttl_seconds: float = 246.87
    cache_threshold: float = 0.44
    compression_level: int = 8  # 0-9
    target_reduction: float = 0.64
    thompson_alpha: float = 2.0
    thompson_beta: float = 5.0

    # Last evolution timestamp
    last_evolution_timestamp: str = None

    def should_run_ga(self, last_run_timestamp: str = None) -> bool:
        """Check if GA should run based on last run time"""
        if last_run_timestamp is None:
            return True  # Never run before

        try:
            last_run = datetime.fromisoformat(last_run_timestamp)
            elapsed = datetime.utcnow() - last_run
            return elapsed.total_seconds() >= self.tuning_interval_seconds
        except (ValueError, TypeError):
            return True  # Invalid timestamp, run GA

    def next_ga_run_time(self, last_run_timestamp: str = None) -> str:
        """Calculate when next GA run should occur"""
        if last_run_timestamp is None:
            return "Immediately (never run)"

        try:
            last_run = datetime.fromisoformat(last_run_timestamp)
            next_run = last_run + timedelta(seconds=self.tuning_interval_seconds)
            if next_run < datetime.utcnow():
                return "Now (overdue)"
            return next_run.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, TypeError):
            return "Unknown (invalid timestamp)"

    def format_interval(self) -> str:
        """Human-readable interval"""
        seconds = self.tuning_interval_seconds
        if seconds >= 3600:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''}"
        elif seconds >= 60:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''}"
        else:
            return f"{seconds} second{'s' if seconds > 1 else ''}"


# Global default config
DEFAULT_GA_CONFIG = GAConfig()
