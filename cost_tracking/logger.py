"""
Cost tracking logger for API calls.

Records model usage, token counts, and calculated costs for audit and budget tracking.
Supports Claude (Haiku, Sonnet, Opus) and Google Gemini models with current pricing.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Literal


# Pricing per 1M tokens (input / output)
PRICING = {
    "haiku": {"input": 0.80, "output": 2.40},
    "sonnet": {"input": 3.00, "output": 15.00},
    "opus": {"input": 15.00, "output": 45.00},
    "gemini": {"input": 0.075, "output": 0.30},  # Gemini 2.0 Flash pricing
}

ModelName = Literal["haiku", "sonnet", "opus", "gemini"]


class CostLogger:
    """Logger for tracking API call costs and token usage."""

    def __init__(self, log_path: str = None):
        """
        Initialize the cost logger.

        Args:
            log_path: Path to JSON log file. Defaults to cost_tracking/api_costs.jsonl
        """
        if log_path is None:
            log_path = os.path.join(
                os.path.dirname(__file__), "api_costs.jsonl"
            )
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def calculate_cost(
        self, model: ModelName, input_tokens: int, output_tokens: int
    ) -> float:
        """
        Calculate the cost for an API call.

        Args:
            model: Model name (haiku, sonnet, opus, gemini)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD as a float
        """
        if model not in PRICING:
            raise ValueError(
                f"Unknown model: {model}. "
                f"Supported: {', '.join(PRICING.keys())}"
            )

        prices = PRICING[model]
        input_cost = (input_tokens / 1_000_000) * prices["input"]
        output_cost = (output_tokens / 1_000_000) * prices["output"]
        return input_cost + output_cost

    def log_call(
        self,
        model: ModelName,
        input_tokens: int,
        output_tokens: int,
        task_name: str,
        source: str = "api",
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Log an API call with cost calculation.

        Args:
            model: Model name (haiku, sonnet, opus, gemini)
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated
            task_name: Human-readable task name (e.g., "code_review", "refactoring")
            source: Source of the call (e.g., "api", "cached", "batch")
            metadata: Optional additional context dict

        Returns:
            The logged entry as a dictionary
        """
        total_tokens = input_tokens + output_tokens
        cost = self.calculate_cost(model, input_tokens, output_tokens)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost, 6),
            "task_name": task_name,
            "source": source,
        }

        if metadata:
            entry["metadata"] = metadata

        # Append to log file (append-only JSON Lines format)
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def get_stats(self) -> dict:
        """
        Get aggregate statistics from the log file.

        Returns:
            Dictionary with total calls, tokens, cost by model
        """
        stats = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "by_model": {model: {
                "calls": 0,
                "tokens": 0,
                "cost": 0.0,
            } for model in PRICING},
            "by_task": {},
        }

        if not self.log_path.exists():
            return stats

        with open(self.log_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)

                # Update totals
                stats["total_calls"] += 1
                tokens = entry["total_tokens"]
                cost = entry["cost_usd"]
                stats["total_tokens"] += tokens
                stats["total_cost_usd"] += cost

                # Update by model
                model = entry["model"]
                stats["by_model"][model]["calls"] += 1
                stats["by_model"][model]["tokens"] += tokens
                stats["by_model"][model]["cost"] += cost

                # Update by task
                task = entry["task_name"]
                if task not in stats["by_task"]:
                    stats["by_task"][task] = {
                        "calls": 0,
                        "tokens": 0,
                        "cost": 0.0,
                    }
                stats["by_task"][task]["calls"] += 1
                stats["by_task"][task]["tokens"] += tokens
                stats["by_task"][task]["cost"] += cost

        # Round costs for readability
        stats["total_cost_usd"] = round(stats["total_cost_usd"], 6)
        for model_stats in stats["by_model"].values():
            model_stats["cost"] = round(model_stats["cost"], 6)
        for task_stats in stats["by_task"].values():
            task_stats["cost"] = round(task_stats["cost"], 6)

        return stats

    def read_logs(self) -> list:
        """
        Read all logged entries from the log file.

        Returns:
            List of log entry dictionaries in order
        """
        logs = []
        if not self.log_path.exists():
            return logs

        with open(self.log_path, "r") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))

        return logs
