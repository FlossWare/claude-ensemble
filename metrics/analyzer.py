"""
WORKER 3: Correlation Analyzer
===============================

Analyzes performance logs to find patterns in which workflows benefit from
compression and caching.

Generates correlation reports showing:
- Which workflows compress well (high reduction + low quality impact)
- Which workflows benefit from caching (high hit rate)
- Latency tradeoffs per strategy
- Confidence scores for recommendations

Output: JSON correlation report + human-readable summary

Author: Opus 4.8
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from statistics import mean, stdev, median


@dataclass
class WorkflowMetrics:
    """Aggregated metrics for a single workflow type."""
    workflow_type: str
    call_count: int
    avg_compression_percent: float
    avg_quality_impact: float  # Negative: higher = more quality loss
    avg_latency_ms: float
    cache_hit_rate: float
    avg_tokens_saved_per_hit: float
    recommendation: str  # "none", "light_compression", "moderate_compression", "aggressive_compression"
    confidence: float  # 0.0-1.0


@dataclass
class CorrelationReport:
    """Complete correlation analysis report."""
    period: str  # "2026-09-25" or "2026-w39"
    workflows_analyzed: int
    timestamp: str
    compression_analysis: Dict[str, Dict]  # by workflow_type
    cache_analysis: Dict[str, Dict]  # by workflow_type
    latency_impact: Dict
    overall_recommendations: List[str]

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class PerformanceAnalyzer:
    """
    Analyzes performance logs to find correlation patterns.

    Reads from PerformanceLogger output and generates recommendations
    for per-workflow compression and caching settings.
    """

    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize the analyzer.

        Args:
            log_file: Path to performance_calls.jsonl from PerformanceLogger
        """
        if log_file is None:
            log_file = Path.home() / ".claude" / "metrics" / "performance_calls.jsonl"

        self.log_file = log_file

    def analyze_daily(self, date: Optional[str] = None) -> Optional[CorrelationReport]:
        """
        Analyze performance for a specific day.

        Args:
            date: Date string "YYYY-MM-DD" (defaults to today)

        Returns:
            CorrelationReport for the day
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        entries = self._read_logs_for_date(date)
        if not entries:
            return None

        return self._analyze_entries(entries, period=date)

    def analyze_weekly(self, week_str: Optional[str] = None) -> Optional[CorrelationReport]:
        """
        Analyze performance for a specific week.

        Args:
            week_str: Week string "YYYY-wNN" (defaults to current week)

        Returns:
            CorrelationReport for the week
        """
        if week_str is None:
            now = datetime.utcnow()
            week_str = now.strftime("%Y-w%U")

        entries = self._read_logs_for_week(week_str)
        if not entries:
            return None

        return self._analyze_entries(entries, period=week_str)

    def analyze_all(self) -> Optional[CorrelationReport]:
        """
        Analyze all performance data available.

        Returns:
            CorrelationReport for all data
        """
        entries = self._read_all_logs()
        if not entries:
            return None

        return self._analyze_entries(entries, period="all_time")

    def _read_logs_for_date(self, date_str: str) -> List[Dict]:
        """Read logs for a specific date."""
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        entry_date = data.get("timestamp", "").split("T")[0]
                        if entry_date == date_str:
                            entries.append(data)
                    except json.JSONDecodeError:
                        pass

        return entries

    def _read_logs_for_week(self, week_str: str) -> List[Dict]:
        """Read logs for a specific week."""
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        timestamp = data.get("timestamp", "")
                        entry_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        entry_week = entry_date.strftime("%Y-w%U")
                        if entry_week == week_str:
                            entries.append(data)
                    except (json.JSONDecodeError, ValueError):
                        pass

        return entries

    def _read_all_logs(self) -> List[Dict]:
        """Read all logs from file."""
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        entries.append(data)
                    except json.JSONDecodeError:
                        pass

        return entries

    def _analyze_entries(self, entries: List[Dict], period: str) -> CorrelationReport:
        """Analyze a list of entries and generate report."""
        # Group by workflow type
        by_workflow = self._group_by_workflow(entries)

        # Analyze each workflow
        compression_analysis = {}
        cache_analysis = {}

        for workflow_type, workflow_entries in by_workflow.items():
            compression_analysis[workflow_type] = self._analyze_compression(
                workflow_type, workflow_entries
            )
            cache_analysis[workflow_type] = self._analyze_cache(
                workflow_type, workflow_entries
            )

        # Analyze overall latency impact
        latency_impact = self._analyze_latency(entries)

        # Generate overall recommendations
        recommendations = self._generate_recommendations(
            compression_analysis, cache_analysis
        )

        return CorrelationReport(
            period=period,
            workflows_analyzed=len(by_workflow),
            timestamp=datetime.utcnow().isoformat() + "Z",
            compression_analysis=compression_analysis,
            cache_analysis=cache_analysis,
            latency_impact=latency_impact,
            overall_recommendations=recommendations,
        )

    def _group_by_workflow(self, entries: List[Dict]) -> Dict[str, List[Dict]]:
        """Group entries by workflow type."""
        by_workflow = {}
        for entry in entries:
            workflow = entry.get("workflow_type", "unknown")
            if workflow not in by_workflow:
                by_workflow[workflow] = []
            by_workflow[workflow].append(entry)
        return by_workflow

    def _analyze_compression(self, workflow_type: str, entries: List[Dict]) -> Dict:
        """Analyze compression effectiveness for a workflow."""
        if not entries:
            return {}

        compressions = [e["compression"] for e in entries]
        reductions = [c["reduction_percent"] for c in compressions]
        latencies = [c["latency_ms"] for c in compressions]

        # Calculate quality impact (if available)
        qualities = [e["quality"].get("semantic_similarity", 1.0) for e in entries
                     if e["quality"].get("semantic_similarity") is not None]
        quality_impact = 1.0 - mean(qualities) if qualities else 0.0

        avg_reduction = mean(reductions)
        avg_latency = mean(latencies)

        # Determine recommendation
        recommendation, confidence = self._recommend_compression(
            avg_reduction, quality_impact, avg_latency, len(entries)
        )

        return {
            "avg_reduction_percent": round(avg_reduction, 1),
            "quality_impact": round(quality_impact, 3),
            "avg_latency_ms": round(avg_latency, 1),
            "call_count": len(entries),
            "recommendation": recommendation,
            "confidence": round(confidence, 2),
        }

    def _analyze_cache(self, workflow_type: str, entries: List[Dict]) -> Dict:
        """Analyze caching effectiveness for a workflow."""
        if not entries:
            return {}

        cache_hits = sum(1 for e in entries if e["cache"].get("is_hit", False))
        hit_rate = cache_hits / len(entries) if entries else 0.0

        # Calculate tokens saved per hit
        tokens_saved = [
            e["compression"]["original_tokens"] - e["cache"].get("cache_read_tokens", 0)
            for e in entries if e["cache"].get("is_hit", False)
        ]
        avg_tokens_saved = mean(tokens_saved) if tokens_saved else 0.0

        # Determine recommendation
        recommendation, confidence = self._recommend_cache(hit_rate, len(entries))

        return {
            "cache_hit_rate": round(hit_rate, 2),
            "cache_hits": cache_hits,
            "avg_tokens_saved_per_hit": round(avg_tokens_saved, 0),
            "call_count": len(entries),
            "recommendation": recommendation,
            "confidence": round(confidence, 2),
        }

    def _analyze_latency(self, entries: List[Dict]) -> Dict:
        """Analyze overall latency impact."""
        if not entries:
            return {}

        compressions = [e["compression"] for e in entries]
        compression_latencies = [c["latency_ms"] for c in compressions]

        return {
            "compression_avg_ms": round(mean(compression_latencies), 1),
            "compression_p95_ms": round(sorted(compression_latencies)[int(len(compression_latencies) * 0.95)], 1) if compression_latencies else 0,
            "cache_benefit_ms": "variable (depends on context size)",
            "recommendation": "latency_acceptable_for_savings"
            if mean(compression_latencies) < 100 else "monitor_latency"
        }

    def _recommend_compression(
        self, reduction: float, quality_impact: float, latency: float, count: int
    ) -> tuple:
        """
        Recommend compression level.

        Returns: (recommendation_str, confidence_score)
        """
        # Need at least 5 samples for confidence
        if count < 5:
            return "insufficient_data", 0.0

        # Quality is paramount - don't compress if loss > 15%
        if quality_impact > 0.15:
            return "light_compression", 0.9

        # Good compression and low quality loss
        if reduction > 40 and quality_impact < 0.05:
            return "aggressive_compression", 0.9
        elif reduction > 30:
            return "moderate_compression", 0.85
        elif reduction > 20:
            return "light_compression", 0.8
        else:
            return "none", 0.75

    def _recommend_cache(self, hit_rate: float, count: int) -> tuple:
        """
        Recommend caching strategy.

        Returns: (recommendation_str, confidence_score)
        """
        # Need at least 5 samples
        if count < 5:
            return "insufficient_data", 0.0

        if hit_rate > 0.6:
            return "aggressive_caching", 0.9
        elif hit_rate > 0.3:
            return "prefer_cache_hit", 0.85
        else:
            return "light_caching", 0.75

    def _generate_recommendations(
        self, compression: Dict, cache: Dict
    ) -> List[str]:
        """Generate overall recommendations."""
        recommendations = []

        # Compression recommendations
        aggressive_workflows = [
            wf for wf, stats in compression.items()
            if stats.get("recommendation") == "aggressive_compression"
        ]
        if aggressive_workflows:
            recommendations.append(
                f"Use aggressive compression for: {', '.join(aggressive_workflows)}"
            )

        no_compression = [
            wf for wf, stats in compression.items()
            if stats.get("recommendation") == "none"
        ]
        if no_compression:
            recommendations.append(
                f"Disable compression for: {', '.join(no_compression)}"
            )

        # Cache recommendations
        cache_friendly = [
            wf for wf, stats in cache.items()
            if stats.get("recommendation") == "aggressive_caching"
        ]
        if cache_friendly:
            recommendations.append(
                f"Enable aggressive caching for: {', '.join(cache_friendly)}"
            )

        if not recommendations:
            recommendations.append("Continue with current settings")

        return recommendations

    def save_report(self, report: CorrelationReport, output_file: Optional[Path] = None) -> None:
        """Save correlation report to file."""
        if output_file is None:
            output_file = Path.home() / ".claude" / "metrics" / "correlation_report.json"

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

    def print_report(self, report: CorrelationReport) -> None:
        """Print human-readable report."""
        print(f"\nPerformance Analysis Report - {report.period}")
        print("=" * 70)
        print(f"Workflows analyzed: {report.workflows_analyzed}")
        print(f"Report generated: {report.timestamp}\n")

        if report.compression_analysis:
            print("COMPRESSION ANALYSIS")
            print("-" * 70)
            for workflow, stats in report.compression_analysis.items():
                print(f"\n  {workflow}:")
                print(f"    Avg reduction: {stats.get('avg_reduction_percent', 0)}%")
                print(f"    Quality impact: {stats.get('quality_impact', 0):.1%}")
                print(f"    Recommendation: {stats.get('recommendation')}")
                print(f"    Confidence: {stats.get('confidence', 0):.0%}")

        if report.cache_analysis:
            print("\n\nCACHE ANALYSIS")
            print("-" * 70)
            for workflow, stats in report.cache_analysis.items():
                print(f"\n  {workflow}:")
                print(f"    Hit rate: {stats.get('cache_hit_rate', 0):.0%}")
                print(f"    Tokens saved/hit: {stats.get('avg_tokens_saved_per_hit', 0):.0f}")
                print(f"    Recommendation: {stats.get('recommendation')}")
                print(f"    Confidence: {stats.get('confidence', 0):.0%}")

        if report.overall_recommendations:
            print("\n\nOVERALL RECOMMENDATIONS")
            print("-" * 70)
            for rec in report.overall_recommendations:
                print(f"  • {rec}")


def main():
    """Demo the analyzer."""
    print("Performance Analyzer Demo")
    print("=" * 70)
    print("Note: Analyzer requires performance_calls.jsonl from PerformanceLogger")
    print("Run logger.py first to generate sample data")


if __name__ == "__main__":
    main()
