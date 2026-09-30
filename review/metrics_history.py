#!/usr/bin/env python3
"""
Store and query review metrics history by time range.

Saves metrics after each review and allows querying by date/time.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class MetricsHistory:
    """Store and retrieve review metrics over time"""

    def __init__(self, history_dir: str = ".review_metrics"):
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_review_metrics(self, request_id: str, stage_costs, consensus_score: float) -> bool:
        """Save metrics from a completed review"""
        try:
            now = datetime.utcnow()

            metrics = {
                "timestamp": now.isoformat(),
                "request_id": request_id,
                "date": now.strftime("%Y-%m-%d"),
                "hour": now.strftime("%Y-%m-%d %H:00"),
                "consensus_score": consensus_score,
                "stages": []
            }

            for stage_cost in stage_costs:
                stage_metrics = {
                    "stage_number": stage_cost.stage_number,
                    "tokens": stage_cost.total_tokens,
                    "cost": stage_cost.total_cost,
                    "worker_tokens": stage_cost.worker_tokens,
                    "arbiter_tokens": stage_cost.arbiter_tokens,
                    "cache_hits": stage_cost.cache_hits,
                    "cache_misses": stage_cost.cache_misses,
                    "compression_input": stage_cost.input_size_bytes,
                    "compression_output": stage_cost.compressed_size_bytes,
                    "memory_recalls": stage_cost.memory_recalls,
                    "knowledge_lookups": stage_cost.knowledge_lookups,
                    "messages_sent": stage_cost.messages_sent,
                    "messages_received": stage_cost.messages_received,
                    "alerts_triggered": stage_cost.alerts_triggered,
                    "graph_queries": stage_cost.graph_queries,
                    "arbitration_decisions": stage_cost.arbitration_decisions,
                    "thompson_updates": stage_cost.thompson_updates,
                    "secrets_accessed": stage_cost.secrets_accessed,
                    "mcp_calls": stage_cost.mcp_calls,
                    "ensemble_routing_hops": stage_cost.ensemble_routing_hops,
                }
                metrics["stages"].append(stage_metrics)

            # Save to file: .review_metrics/YYYY-MM-DD/HH-MM-SS-{request_id}.json
            date_dir = self.history_dir / now.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True, exist_ok=True)

            filename = date_dir / f"{now.strftime('%H-%M-%S')}-{request_id[:8]}.json"
            filename.write_text(json.dumps(metrics, indent=2))

            logger.info(f"Saved metrics to {filename}")
            return True
        except Exception as e:
            logger.warning(f"Failed to save metrics: {e}")
            return False

    def query_by_date(self, date: str) -> List[Dict]:
        """Query metrics for a specific date (YYYY-MM-DD)"""
        date_dir = self.history_dir / date
        if not date_dir.exists():
            return []

        metrics = []
        for file in sorted(date_dir.glob("*.json")):
            try:
                data = json.loads(file.read_text())
                metrics.append(data)
            except Exception as e:
                logger.warning(f"Failed to read {file}: {e}")

        return metrics

    def query_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Query metrics for date range (YYYY-MM-DD)"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        metrics = []
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            metrics.extend(self.query_by_date(date_str))
            current += timedelta(days=1)

        return metrics

    def query_today(self) -> List[Dict]:
        """Query all metrics from today"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return self.query_by_date(today)

    def query_this_week(self) -> List[Dict]:
        """Query all metrics from this week"""
        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())
        start_str = week_start.strftime("%Y-%m-%d")
        end_str = today.strftime("%Y-%m-%d")
        return self.query_by_date_range(start_str, end_str)

    def query_this_month(self) -> List[Dict]:
        """Query all metrics from this month"""
        today = datetime.utcnow()
        month_start = today.replace(day=1)
        start_str = month_start.strftime("%Y-%m-%d")
        end_str = today.strftime("%Y-%m-%d")
        return self.query_by_date_range(start_str, end_str)

    @staticmethod
    def aggregate_metrics(metrics_list: List[Dict]) -> Dict:
        """Aggregate metrics across multiple reviews"""
        if not metrics_list:
            return {}

        agg = {
            "review_count": len(metrics_list),
            "avg_consensus_score": 0.0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_cache_hit_rate": 0.0,
            "avg_compression_ratio": 0.0,
            "total_memory_recalls": 0,
            "total_knowledge_lookups": 0,
            "total_messages_sent": 0,
            "total_messages_received": 0,
            "total_alerts": 0,
            "total_graph_queries": 0,
            "total_arbitration_decisions": 0,
            "total_thompson_updates": 0,
            "total_secrets_accessed": 0,
            "total_mcp_calls": 0,
            "total_routing_hops": 0,
        }

        total_cache_hits = 0
        total_cache_misses = 0
        total_compression_input = 0
        total_compression_output = 0

        for metrics in metrics_list:
            agg["avg_consensus_score"] += metrics.get("consensus_score", 0)

            for stage in metrics.get("stages", []):
                agg["total_tokens"] += stage.get("tokens", 0)
                agg["total_cost"] += stage.get("cost", 0.0)
                agg["total_memory_recalls"] += stage.get("memory_recalls", 0)
                agg["total_knowledge_lookups"] += stage.get("knowledge_lookups", 0)
                agg["total_messages_sent"] += stage.get("messages_sent", 0)
                agg["total_messages_received"] += stage.get("messages_received", 0)
                agg["total_alerts"] += stage.get("alerts_triggered", 0)
                agg["total_graph_queries"] += stage.get("graph_queries", 0)
                agg["total_arbitration_decisions"] += stage.get("arbitration_decisions", 0)
                agg["total_thompson_updates"] += stage.get("thompson_updates", 0)
                agg["total_secrets_accessed"] += stage.get("secrets_accessed", 0)
                agg["total_mcp_calls"] += stage.get("mcp_calls", 0)
                agg["total_routing_hops"] += stage.get("ensemble_routing_hops", 0)

                total_cache_hits += stage.get("cache_hits", 0)
                total_cache_misses += stage.get("cache_misses", 0)
                total_compression_input += stage.get("compression_input", 0)
                total_compression_output += stage.get("compression_output", 0)

        agg["avg_consensus_score"] /= len(metrics_list)

        cache_total = total_cache_hits + total_cache_misses
        agg["avg_cache_hit_rate"] = (total_cache_hits / cache_total * 100) if cache_total > 0 else 0

        agg["avg_compression_ratio"] = (
            (1 - total_compression_output / total_compression_input) * 100
            if total_compression_input > 0 else 0
        )

        return agg

    @staticmethod
    def format_summary(agg: Dict, label: str = "Period") -> str:
        """Format aggregated metrics as readable summary"""
        if not agg:
            return f"No metrics for {label}"

        lines = [
            "",
            "=" * 100,
            f"{label.upper()} SUMMARY",
            "=" * 100,
            ""
        ]

        lines.append(f"Reviews: {agg.get('review_count', 0)}")
        lines.append(f"Avg Consensus: {agg.get('avg_consensus_score', 0):.1%}")
        lines.append(f"Total Tokens: {agg.get('total_tokens', 0):,}")
        lines.append(f"Total Cost: ${agg.get('total_cost', 0):.6f}")
        lines.append(f"Cache Hit Rate: {agg.get('avg_cache_hit_rate', 0):.1f}%")
        lines.append(f"Compression Ratio: {agg.get('avg_compression_ratio', 0):.1f}%")
        lines.append("")
        lines.append("Services Activity:")
        lines.append(f"  Memory recalls: {agg.get('total_memory_recalls', 0)}")
        lines.append(f"  Knowledge lookups: {agg.get('total_knowledge_lookups', 0)}")
        lines.append(f"  Messages: {agg.get('total_messages_sent', 0)} sent / {agg.get('total_messages_received', 0)} received")
        lines.append(f"  Alerts: {agg.get('total_alerts', 0)}")
        lines.append(f"  Graph queries: {agg.get('total_graph_queries', 0)}")
        lines.append(f"  Arbitration decisions: {agg.get('total_arbitration_decisions', 0)}")
        lines.append(f"  Thompson updates: {agg.get('total_thompson_updates', 0)}")
        lines.append(f"  Secrets accessed: {agg.get('total_secrets_accessed', 0)}")
        lines.append(f"  MCP calls: {agg.get('total_mcp_calls', 0)}")
        lines.append(f"  Routing hops: {agg.get('total_routing_hops', 0)}")
        lines.append("=" * 100)

        return "\n".join(lines)
