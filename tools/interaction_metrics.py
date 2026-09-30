#!/usr/bin/env python3
"""
Capture metrics for ALL interactions: prompts, API calls, tool usage, reviews, etc.

Logs every interaction with timestamps, tokens, costs, and service usage.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# Try to import Memory and Learning services
try:
    from learning.learning_client import LearningClient
    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False

try:
    from memory.memory_client import MemoryClient
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False


class InteractionMetrics:
    """Capture and store metrics for all user interactions"""

    def __init__(self, metrics_dir: str = ".interaction_metrics"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def log_prompt_submission(self, prompt: str, model: str, tokens_used: int, cost: float,
                            services_used: Optional[Dict] = None, metadata: Optional[Dict] = None) -> bool:
        """Log a prompt submission"""
        return self._log_interaction(
            interaction_type="prompt",
            description=prompt[:100],  # First 100 chars
            model=model,
            tokens_used=tokens_used,
            cost=cost,
            services_used=services_used or {},
            metadata=metadata or {}
        )

    def log_tool_call(self, tool_name: str, tokens_used: int, cost: float,
                     success: bool, services_used: Optional[Dict] = None,
                     metadata: Optional[Dict] = None) -> bool:
        """Log a tool invocation"""
        meta = metadata or {}
        meta["tool_name"] = tool_name
        meta["success"] = success
        return self._log_interaction(
            interaction_type="tool_call",
            description=tool_name,
            model="tool",
            tokens_used=tokens_used,
            cost=cost,
            services_used=services_used or {},
            metadata=meta
        )

    def log_api_call(self, endpoint: str, method: str, tokens_used: int, cost: float,
                    status_code: int, services_used: Optional[Dict] = None,
                    metadata: Optional[Dict] = None) -> bool:
        """Log an API call"""
        meta = metadata or {}
        meta["endpoint"] = endpoint
        meta["method"] = method
        meta["status"] = status_code
        return self._log_interaction(
            interaction_type="api_call",
            description=f"{method} {endpoint}",
            model="api",
            tokens_used=tokens_used,
            cost=cost,
            services_used=services_used or {},
            metadata=meta
        )

    def log_review(self, review_id: str, stages: int, consensus_score: float,
                  tokens_used: int, cost: float, findings_count: int,
                  services_used: Optional[Dict] = None) -> bool:
        """Log a review interaction"""
        return self._log_interaction(
            interaction_type="review",
            description=f"{stages}-stage review",
            model="multi-stage-arbiter",
            tokens_used=tokens_used,
            cost=cost,
            services_used=services_used or {},
            metadata={
                "review_id": review_id,
                "stages": stages,
                "consensus_score": consensus_score,
                "findings": findings_count
            }
        )

    def log_service_interaction(self, service_name: str, operation: str, success: bool,
                               tokens_used: int, cost: float, metadata: Optional[Dict] = None) -> bool:
        """Log interaction with any service"""
        return self._log_interaction(
            interaction_type="service",
            description=f"{service_name}/{operation}",
            model=service_name,
            tokens_used=tokens_used,
            cost=cost,
            services_used={service_name: {"calls": 1, "success": success}},
            metadata=metadata or {}
        )

    def _log_interaction(self, interaction_type: str, description: str, model: str,
                        tokens_used: int, cost: float, services_used: Dict,
                        metadata: Dict) -> bool:
        """Internal: log any interaction and feed to Memory/Learning"""
        try:
            now = datetime.utcnow()

            entry = {
                "timestamp": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "hour": now.strftime("%Y-%m-%d %H:00"),
                "type": interaction_type,
                "description": description,
                "model": model,
                "tokens": tokens_used,
                "cost": cost,
                "services": services_used,
                "metadata": metadata
            }

            # Save to file: .interaction_metrics/YYYY-MM-DD/HH-MM-SS-{type}.json
            date_dir = self.metrics_dir / now.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True, exist_ok=True)

            filename = date_dir / f"{now.strftime('%H-%M-%S')}-{interaction_type}.json"
            filename.write_text(json.dumps(entry, indent=2))

            logger.debug(f"Logged {interaction_type}: {description}")

            # Feed to Memory Service for knowledge base
            if MEMORY_AVAILABLE:
                try:
                    memory_client = MemoryClient()
                    memory_client.store_interaction(
                        interaction_type=interaction_type,
                        description=description,
                        tokens=tokens_used,
                        cost=cost,
                        metadata=metadata
                    )
                except Exception as e:
                    logger.debug(f"Could not store to Memory Service: {e}")

            # Feed to Learning Service for Thompson updates
            if LEARNING_AVAILABLE and interaction_type == "review":
                try:
                    learning_client = LearningClient()
                    consensus = metadata.get("consensus_score", 0.5)
                    rating = int(consensus * 5)
                    learning_client.process_outcome(
                        task_id=f"interaction_{metadata.get('review_id', 'unknown')}_{now.isoformat()}",
                        task_type="review",
                        model=model,
                        rating=rating,
                        tokens=tokens_used,
                        cost=cost
                    )
                except Exception as e:
                    logger.debug(f"Could not send to Learning Service: {e}")

            return True
        except Exception as e:
            logger.warning(f"Failed to log interaction: {e}")
            return False

    def query_by_date(self, date: str) -> List[Dict]:
        """Query all interactions for a specific date (YYYY-MM-DD)"""
        date_dir = self.metrics_dir / date
        if not date_dir.exists():
            return []

        interactions = []
        for file in sorted(date_dir.glob("*.json")):
            try:
                data = json.loads(file.read_text())
                interactions.append(data)
            except Exception as e:
                logger.warning(f"Failed to read {file}: {e}")

        return interactions

    def query_today(self) -> List[Dict]:
        """Query all interactions from today"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return self.query_by_date(today)

    @staticmethod
    def aggregate_interactions(interactions: List[Dict]) -> Dict:
        """Aggregate metrics across interactions"""
        if not interactions:
            return {}

        agg = {
            "total_interactions": len(interactions),
            "by_type": {},
            "by_model": {},
            "total_tokens": 0,
            "total_cost": 0.0,
            "all_services": {}
        }

        for interaction in interactions:
            itype = interaction.get("type", "unknown")
            model = interaction.get("model", "unknown")

            # Count by type
            if itype not in agg["by_type"]:
                agg["by_type"][itype] = {"count": 0, "tokens": 0, "cost": 0.0}
            agg["by_type"][itype]["count"] += 1
            agg["by_type"][itype]["tokens"] += interaction.get("tokens", 0)
            agg["by_type"][itype]["cost"] += interaction.get("cost", 0.0)

            # Count by model
            if model not in agg["by_model"]:
                agg["by_model"][model] = {"count": 0, "tokens": 0, "cost": 0.0}
            agg["by_model"][model]["count"] += 1
            agg["by_model"][model]["tokens"] += interaction.get("tokens", 0)
            agg["by_model"][model]["cost"] += interaction.get("cost", 0.0)

            # Aggregate services
            for service, stats in interaction.get("services", {}).items():
                if service not in agg["all_services"]:
                    agg["all_services"][service] = {"calls": 0, "successes": 0}
                agg["all_services"][service]["calls"] += stats.get("calls", 1)
                if stats.get("success", True):
                    agg["all_services"][service]["successes"] += 1

            # Totals
            agg["total_tokens"] += interaction.get("tokens", 0)
            agg["total_cost"] += interaction.get("cost", 0.0)

        return agg

    @staticmethod
    def format_summary(agg: Dict, label: str = "Period") -> str:
        """Format aggregated interactions as readable summary"""
        if not agg:
            return f"No interactions for {label}"

        lines = [
            "",
            "=" * 140,
            f"{label.upper()} ACTIVITY SUMMARY - TABLE FORMAT",
            "=" * 140,
            ""
        ]

        lines.append(f"Total Interactions: {agg.get('total_interactions', 0):4d} | Tokens: {agg.get('total_tokens', 0):,} | Cost: ${agg.get('total_cost', 0):.6f}")
        lines.append("")

        # By Type Table
        if agg.get("by_type"):
            lines.append("INTERACTIONS BY TYPE:")
            header = "Type".ljust(20) + "Count".ljust(12) + "Tokens".ljust(15) + "Cost".ljust(15) + "Avg Cost/Call".ljust(15)
            lines.append(header)
            lines.append("-" * 77)

            for itype, stats in sorted(agg["by_type"].items()):
                avg_cost = stats['cost'] / stats['count'] if stats['count'] > 0 else 0
                row = (itype.ljust(20) +
                       str(stats['count']).ljust(12) +
                       f"{stats['tokens']:,}".ljust(15) +
                       f"${stats['cost']:.6f}".ljust(15) +
                       f"${avg_cost:.6f}".ljust(15))
                lines.append(row)
            lines.append("")

        # By Model Table
        if agg.get("by_model"):
            lines.append("INTERACTIONS BY MODEL:")
            header = "Model".ljust(25) + "Count".ljust(12) + "Tokens".ljust(15) + "Cost".ljust(15) + "Avg Cost/Call".ljust(15)
            lines.append(header)
            lines.append("-" * 82)

            for model, stats in sorted(agg["by_model"].items()):
                avg_cost = stats['cost'] / stats['count'] if stats['count'] > 0 else 0
                row = (model.ljust(25) +
                       str(stats['count']).ljust(12) +
                       f"{stats['tokens']:,}".ljust(15) +
                       f"${stats['cost']:.6f}".ljust(15) +
                       f"${avg_cost:.6f}".ljust(15))
                lines.append(row)
            lines.append("")

        # Services Table
        if agg.get("all_services"):
            lines.append("SERVICES USED:")
            header = "Service".ljust(25) + "Calls".ljust(12) + "Success Rate".ljust(15)
            lines.append(header)
            lines.append("-" * 52)

            for service, stats in sorted(agg["all_services"].items()):
                success_rate = (stats['successes'] / stats['calls'] * 100) if stats['calls'] > 0 else 0
                row = (service.ljust(25) +
                       str(stats['calls']).ljust(12) +
                       f"{success_rate:.0f}%".ljust(15))
                lines.append(row)
            lines.append("")

        lines.append("=" * 140)

        return "\n".join(lines)
