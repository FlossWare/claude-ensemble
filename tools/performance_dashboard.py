#!/usr/bin/env python3
"""
CLI Performance Dashboard - Real-time fleet and model performance monitoring
Shows model speeds, worker efficiency, task breakdowns with color-coded output
"""

import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Any

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

class PerformanceDashboard:
    def __init__(self, host="aio-01", port=5433, database="learning", user="claude"):
        """Initialize dashboard with PostgreSQL connection"""
        self.conn = psycopg2.connect(host=host, port=port, database=database, user=user)

    def get_model_performance(self, hours=24) -> List[Dict[str, Any]]:
        """Get model performance statistics"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                model,
                COUNT(*) as total_executions,
                COUNT(*) FILTER (WHERE outcome = 'success') as successes,
                ROUND(AVG(duration_ms)) as avg_duration_ms,
                ROUND(MIN(duration_ms)) as min_duration_ms,
                ROUND(MAX(duration_ms)) as max_duration_ms,
                ROUND(AVG(CASE WHEN duration_ms > 0
                    THEN (output_tokens::float / duration_ms * 1000)
                    ELSE 0 END)::numeric, 2) as tokens_per_sec,
                SUM(cost_usd) as total_cost,
                ROUND((SUM(cost_usd) / NULLIF(SUM(duration_ms), 0) * 1000)::numeric, 6) as cost_per_sec
            FROM workflow.worker_results
            WHERE created_at > NOW() - INTERVAL '%s hours'
            GROUP BY model
            ORDER BY successes DESC
        """, (hours,))

        results = []
        for row in cursor.fetchall():
            success_rate = (row[2] / row[1] * 100) if row[1] > 0 else 0
            results.append({
                'model': row[0],
                'executions': row[1],
                'successes': row[2],
                'success_rate': success_rate,
                'avg_duration_ms': row[3] or 0,
                'min_duration_ms': row[4] or 0,
                'max_duration_ms': row[5] or 0,
                'tokens_per_sec': row[6] or 0,
                'total_cost': row[7] or 0,
                'cost_per_sec': row[8] or 0
            })

        cursor.close()
        return results

    def get_worker_performance(self, hours=24) -> List[Dict[str, Any]]:
        """Get worker node performance statistics"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                worker_id,
                COUNT(*) as total_executions,
                COUNT(*) FILTER (WHERE outcome = 'success') as successes,
                ROUND(AVG(duration_ms)) as avg_duration_ms,
                COUNT(DISTINCT model) as models_used
            FROM workflow.worker_results
            WHERE created_at > NOW() - INTERVAL '%s hours'
            GROUP BY worker_id
            ORDER BY successes DESC
        """, (hours,))

        results = []
        for row in cursor.fetchall():
            success_rate = (row[2] / row[1] * 100) if row[1] > 0 else 0
            results.append({
                'worker': row[0],
                'executions': row[1],
                'successes': row[2],
                'success_rate': success_rate,
                'avg_duration_ms': row[3] or 0,
                'models_used': row[4]
            })

        cursor.close()
        return results

    def get_task_type_breakdown(self, hours=24) -> List[Dict[str, Any]]:
        """Get breakdown by task type"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                task_assigned,
                COUNT(*) as executions,
                COUNT(*) FILTER (WHERE outcome = 'success') as successes,
                ROUND(AVG(duration_ms)) as avg_duration_ms
            FROM workflow.worker_results
            WHERE created_at > NOW() - INTERVAL '%s hours'
            GROUP BY task_assigned
            ORDER BY executions DESC
            LIMIT 10
        """, (hours,))

        results = []
        for row in cursor.fetchall():
            success_rate = (row[2] / row[1] * 100) if row[1] > 0 else 0
            results.append({
                'task': row[0][:50] if row[0] else 'Unknown',
                'executions': row[1],
                'successes': row[2],
                'success_rate': success_rate,
                'avg_duration_ms': row[3] or 0
            })

        cursor.close()
        return results

    def get_peak_hours(self) -> List[Dict[str, Any]]:
        """Get peak vs off-peak performance (NEW METRIC)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                hour_of_day,
                executions,
                avg_duration_ms,
                success_rate,
                period_type
            FROM workflow.hourly_performance
            ORDER BY executions DESC
            LIMIT 5
        """)

        results = []
        for row in cursor.fetchall():
            results.append({
                'hour': int(row[0]),
                'executions': row[1],
                'avg_duration_ms': row[2] or 0,
                'success_rate': row[3] or 0,
                'type': row[4]
            })

        cursor.close()
        return results

    def get_realtime_stats(self, minutes=5) -> Dict[str, Any]:
        """Get real-time stats for last N minutes with NEW METRICS"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE outcome = 'success') as successes,
                COUNT(*) FILTER (WHERE outcome = 'error') as errors,
                ROUND(AVG(duration_ms)) as avg_duration,
                SUM(input_tokens + output_tokens) as total_tokens,
                ROUND(AVG(ttft_ms)) as avg_ttft,
                ROUND(AVG(queue_wait_ms)) as avg_queue_wait,
                SUM(retry_overhead_ms) as total_retry_overhead,
                COUNT(*) FILTER (WHERE cache_hit = TRUE) as cache_hits
            FROM workflow.worker_results
            WHERE created_at > NOW() - INTERVAL '%s minutes'
        """, (minutes,))

        row = cursor.fetchone()
        cursor.close()

        cache_hit_rate = (row[8] / row[0] * 100) if row[0] and row[8] else 0

        return {
            'total': row[0] or 0,
            'successes': row[1] or 0,
            'errors': row[2] or 0,
            'success_rate': (row[1] / row[0] * 100) if row[0] and row[1] else 0,
            'avg_duration': row[3] or 0,
            'total_tokens': row[4] or 0,
            'avg_ttft': row[5] or 0,
            'avg_queue_wait': row[6] or 0,
            'total_retry_overhead': row[7] or 0,
            'cache_hits': row[8] or 0,
            'cache_hit_rate': cache_hit_rate
        }

    def colorize_duration(self, ms: float) -> str:
        """Color-code duration (green=fast, yellow=medium, red=slow)"""
        if ms < 2000:
            return f"{GREEN}{ms:,.0f}ms{RESET}"
        elif ms < 5000:
            return f"{YELLOW}{ms:,.0f}ms{RESET}"
        else:
            return f"{RED}{ms:,.0f}ms{RESET}"

    def colorize_success_rate(self, rate: float) -> str:
        """Color-code success rate"""
        if rate >= 80:
            return f"{GREEN}{rate:.1f}%{RESET}"
        elif rate >= 50:
            return f"{YELLOW}{rate:.1f}%{RESET}"
        else:
            return f"{RED}{rate:.1f}%{RESET}"

    def print_table(self, headers: List[str], rows: List[List[str]], widths: List[int]):
        """Print ASCII table"""
        # Header
        header_line = "  ".join(f"{h:<{w}}" for h, w in zip(headers, widths))
        print(f"{BOLD}{header_line}{RESET}")
        print("─" * (sum(widths) + len(widths) * 2))

        # Rows
        for row in rows:
            print("  ".join(f"{str(cell):<{w}}" for cell, w in zip(row, widths)))

    def display(self, hours=24):
        """Display complete performance dashboard"""
        print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
        print(f"{BOLD}{BLUE}Fleet Performance Dashboard{RESET}")
        print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

        # Real-time stats with NEW METRICS
        print(f"{BOLD}📊 Real-Time Stats (Last 5 Minutes){RESET}")
        stats = self.get_realtime_stats(minutes=5)
        print(f"  Total: {stats['total']} | Success: {self.colorize_success_rate(stats['success_rate'])} | "
              f"Avg Duration: {self.colorize_duration(stats['avg_duration'])} | "
              f"Tokens: {stats['total_tokens']:,}")
        print(f"  {BLUE}NEW:{RESET} TTFT: {self.colorize_duration(stats['avg_ttft'])} | "
              f"Queue Wait: {self.colorize_duration(stats['avg_queue_wait'])} | "
              f"Retry Waste: {stats['total_retry_overhead']:,}ms | "
              f"Cache: {self.colorize_success_rate(stats['cache_hit_rate'])}")
        print()

        # Model performance
        print(f"{BOLD}🤖 Model Performance (Last {hours}h){RESET}")
        models = self.get_model_performance(hours)[:10]
        if models:
            headers = ["Model", "Exec", "Success", "Avg Time", "Tokens/s", "Cost"]
            rows = []
            for m in models:
                rows.append([
                    m['model'][:30],
                    str(m['executions']),
                    self.colorize_success_rate(m['success_rate']),
                    self.colorize_duration(m['avg_duration_ms']),
                    f"{m['tokens_per_sec']:.1f}" if m['tokens_per_sec'] > 0 else "N/A",
                    f"${m['total_cost']:.4f}"
                ])
            self.print_table(headers, rows, [32, 6, 12, 12, 10, 10])
        print()

        # Worker performance
        print(f"{BOLD}⚙️  Worker Performance (Last {hours}h){RESET}")
        workers = self.get_worker_performance(hours)
        if workers:
            headers = ["Worker", "Exec", "Success", "Avg Time", "Models"]
            rows = []
            for w in workers:
                rows.append([
                    w['worker'],
                    str(w['executions']),
                    self.colorize_success_rate(w['success_rate']),
                    self.colorize_duration(w['avg_duration_ms']),
                    str(w['models_used'])
                ])
            self.print_table(headers, rows, [15, 6, 12, 12, 8])
        print()

        # Task type breakdown
        print(f"{BOLD}📋 Task Type Breakdown (Last {hours}h){RESET}")
        tasks = self.get_task_type_breakdown(hours)[:5]
        if tasks:
            headers = ["Task Type", "Exec", "Success", "Avg Time"]
            rows = []
            for t in tasks:
                rows.append([
                    t['task'],
                    str(t['executions']),
                    self.colorize_success_rate(t['success_rate']),
                    self.colorize_duration(t['avg_duration_ms'])
                ])
            self.print_table(headers, rows, [52, 6, 12, 12])
        print()

        # Peak hours analysis (NEW METRIC)
        print(f"{BOLD}⏰ Peak vs Off-Peak Hours (Last 7 Days){RESET}")
        peak_hours = self.get_peak_hours()
        if peak_hours:
            headers = ["Hour", "Type", "Exec", "Success", "Avg Time"]
            rows = []
            for p in peak_hours:
                hour_label = f"{p['hour']:02d}:00"
                type_colored = f"{RED if p['type'] == 'peak' else GREEN}{p['type']}{RESET}"
                rows.append([
                    hour_label,
                    type_colored,
                    str(p['executions']),
                    self.colorize_success_rate(p['success_rate']),
                    self.colorize_duration(p['avg_duration_ms'])
                ])
            self.print_table(headers, rows, [8, 12, 6, 12, 12])
        print()

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fleet Performance Dashboard")
    parser.add_argument('--hours', type=int, default=24, help='Hours of data to show (default: 24)')
    args = parser.parse_args()

    dashboard = PerformanceDashboard()
    try:
        dashboard.display(hours=args.hours)
    finally:
        dashboard.close()


if __name__ == "__main__":
    main()
