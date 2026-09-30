#!/usr/bin/env python3
"""
CLI to query and display review metrics history.

Usage:
  metrics-history today              # Show today's aggregated metrics
  metrics-history this-week          # Show this week's aggregated metrics
  metrics-history this-month         # Show this month's aggregated metrics
  metrics-history 2026-09-30         # Show specific date
  metrics-history 2026-09-20 2026-09-30  # Show date range
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

from .metrics_history import MetricsHistory

logger = logging.getLogger(__name__)


class MetricsHistoryCLI:
    """CLI for metrics history queries"""

    def __init__(self):
        self.parser = self._build_parser()
        self.history = MetricsHistory()

    def _build_parser(self) -> argparse.ArgumentParser:
        """Build argument parser"""
        parser = argparse.ArgumentParser(
            description="Query review metrics history",
            epilog="""
Examples:
  review-metrics today              # Aggregated metrics for today
  review-metrics this-week          # Aggregated metrics for this week
  review-metrics this-month         # Aggregated metrics for this month
  review-metrics 2026-09-30         # Metrics for specific date
  review-metrics 2026-09-20 2026-09-30  # Metrics for date range
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        parser.add_argument(
            "query",
            nargs="*",
            help="Query: 'today', 'this-week', 'this-month', DATE, or START_DATE END_DATE",
        )

        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Verbose output",
        )

        return parser

    def run(self, args: list = None) -> int:
        """Execute CLI"""
        parsed = self.parser.parse_args(args)

        if parsed.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        try:
            if not parsed.query:
                print(self.history.format_summary(
                    self.history.aggregate_metrics(self.history.query_today()),
                    "TODAY"
                ))
                return 0

            query = parsed.query[0]

            if query == "today":
                metrics = self.history.query_today()
                agg = self.history.aggregate_metrics(metrics)
                print(self.history.format_summary(agg, "TODAY"))

            elif query == "this-week":
                metrics = self.history.query_this_week()
                agg = self.history.aggregate_metrics(metrics)
                print(self.history.format_summary(agg, "THIS WEEK"))

            elif query == "this-month":
                metrics = self.history.query_this_month()
                agg = self.history.aggregate_metrics(metrics)
                print(self.history.format_summary(agg, "THIS MONTH"))

            elif len(parsed.query) == 1:
                # Single date
                try:
                    datetime.strptime(query, "%Y-%m-%d")
                    metrics = self.history.query_by_date(query)
                    agg = self.history.aggregate_metrics(metrics)
                    print(self.history.format_summary(agg, f"DATE: {query}"))
                except ValueError:
                    print(f"Invalid date format: {query}. Use YYYY-MM-DD")
                    return 1

            elif len(parsed.query) == 2:
                # Date range
                start_date = parsed.query[0]
                end_date = parsed.query[1]
                try:
                    datetime.strptime(start_date, "%Y-%m-%d")
                    datetime.strptime(end_date, "%Y-%m-%d")
                    metrics = self.history.query_by_date_range(start_date, end_date)
                    agg = self.history.aggregate_metrics(metrics)
                    print(self.history.format_summary(agg, f"{start_date} to {end_date}"))
                except ValueError:
                    print(f"Invalid date format. Use YYYY-MM-DD")
                    return 1
            else:
                print("Invalid query format")
                self.parser.print_help()
                return 1

            return 0

        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=parsed.verbose)
            return 1


def main():
    """Entry point"""
    cli = MetricsHistoryCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()
