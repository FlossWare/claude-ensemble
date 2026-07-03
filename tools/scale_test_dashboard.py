#!/usr/bin/env python3
"""
Scale Test Performance Dashboard

Generates human-readable summary and production-readiness assessment.

Usage:
    python3 scale_test_dashboard.py /tmp/scale_test_full_results.json
    python3 scale_test_dashboard.py --compare baseline.json current.json
"""

import sys
import json
import argparse
from typing import Dict, Any


def format_number(n: float, precision: int = 1) -> str:
    """Format number with thousands separator"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.{precision}f}M"
    elif n >= 1_000:
        return f"{n/1_000:.{precision}f}K"
    else:
        return f"{n:.{precision}f}"


def print_dashboard(results: Dict[str, Any]):
    """Print formatted dashboard"""

    print("\n" + "="*80)
    print("SCALE TEST RESULTS - PostgreSQL + pgvector RAG System".center(80))
    print("="*80)

    # Ingestion metrics
    if 'ingestion' in results.get('tests', {}):
        ing = results['tests']['ingestion']
        print("\n📥 INGESTION PERFORMANCE")
        print("-" * 80)
        print(f"  Documents Inserted:     {format_number(ing['documents_inserted'], 0)}")
        print(f"  Total Time:             {ing['total_time_seconds']:.1f}s")
        print(f"  Throughput:             {ing['throughput_docs_per_second']:.1f} docs/s")
        print(f"  Batch Size:             {ing['batch_size']}")
        print(f"  Latency (P50/P95/P99):  {ing['p50_batch_time']:.1f}s / {ing['p95_batch_time']:.1f}s / {ing['p99_batch_time']:.1f}s")

    # Search load metrics
    if 'search_load' in results.get('tests', {}):
        search = results['tests']['search_load']
        print("\n🔍 SEARCH PERFORMANCE")
        print("-" * 80)
        print(f"  Total Searches:         {format_number(search['total_searches'], 0)}")
        print(f"  Duration:               {search['duration_seconds']:.1f}s")
        print(f"  Target QPS:             {search['target_qps']:.1f}")
        print(f"  Actual QPS:             {search['actual_qps']:.1f} {'✓' if search['actual_qps'] >= search['target_qps'] * 0.95 else '✗'}")
        print(f"  Concurrency:            {search['concurrency']} threads")
        print(f"  Latency P50:            {search['latency_p50_ms']:.1f}ms")
        print(f"  Latency P95:            {search['latency_p95_ms']:.1f}ms")
        print(f"  Latency P99:            {search['latency_p99_ms']:.1f}ms")
        print(f"  Error Rate:             {search['error_rate']*100:.2f}% ({search['error_count']} errors)")
        print(f"  Avg Results/Search:     {search['avg_results_per_search']:.1f}")

    # Concurrent write metrics
    if 'concurrent_writes' in results.get('tests', {}):
        writes = results['tests']['concurrent_writes']
        print("\n✍️  CONCURRENT WRITE PERFORMANCE")
        print("-" * 80)
        print(f"  Total Writes:           {format_number(writes['total_writes'], 0)}")
        print(f"  Workers:                {writes['num_workers']}")
        print(f"  Writes/Worker:          {writes['writes_per_worker']}")
        print(f"  Total Time:             {writes['total_time_seconds']:.1f}s")
        print(f"  Throughput:             {writes['throughput_writes_per_second']:.1f} writes/s")
        print(f"  Latency (P50/P95/P99):  {writes['latency_p50_ms']:.0f}ms / {writes['latency_p95_ms']:.0f}ms / {writes['latency_p99_ms']:.0f}ms")
        print(f"  Error Rate:             {writes['error_rate']*100:.2f}%")

    # Database growth
    if 'database_growth' in results.get('tests', {}):
        db = results['tests']['database_growth']
        print("\n💾 DATABASE METRICS")
        print("-" * 80)
        print(f"  Total Rows:             {format_number(db['total_rows'], 0)}")
        print(f"  Total Size:             {db['total_size']}")
        print(f"  Table Size:             {db['table_size']}")
        print(f"  Index Size:             {db['index_size']}")
        print(f"  Indexes:                {len(db.get('indexes', []))}")

    # Resource usage
    if 'resource_usage' in results.get('tests', {}):
        res = results['tests']['resource_usage']
        conn = res.get('connections', {})
        print("\n⚙️  RESOURCE USAGE")
        print("-" * 80)
        print(f"  Active Connections:     {conn.get('active_connections', 0)}")
        print(f"  Idle Connections:       {conn.get('idle_connections', 0)}")
        print(f"  Cache Hit Ratio:        {res.get('cache_hit_ratio', 0):.2f}%")

    # Scale projection
    if 'scale_projection' in results:
        proj = results['scale_projection']
        print("\n📈 SCALE PROJECTION")
        print("-" * 80)
        print(f"  Target:                 {format_number(proj['target_daily_searches'], 0)} searches/day ({proj['target_qps']:.1f} QPS)")
        print(f"  Tested Capacity:        {format_number(proj['max_daily_searches'], 0)} searches/day ({proj['tested_qps']:.1f} QPS)")
        print(f"  Headroom Factor:        {proj['headroom_factor']:.1f}x")
        print(f"  P99 Latency at Scale:   {proj['p99_latency_at_scale_ms']:.1f}ms")
        print(f"  Production Ready:       {'✓ YES' if proj['can_handle_target'] else '✗ NO - NEEDS OPTIMIZATION'}")
        print(f"  Recommendation:         {proj['recommendation']}")

    # Overall summary
    print("\n" + "="*80)
    print("PRODUCTION READINESS ASSESSMENT".center(80))
    print("="*80)

    checks = []

    if 'search_load' in results.get('tests', {}):
        search = results['tests']['search_load']
        checks.append(("Search QPS >= Target", search['actual_qps'] >= search['target_qps'] * 0.95))
        checks.append(("Error Rate < 1%", search['error_rate'] < 0.01))
        checks.append(("P99 Latency < 1000ms", search['latency_p99_ms'] < 1000))

    if 'scale_projection' in results:
        proj = results['scale_projection']
        checks.append(("Can Handle 1M/day", proj['can_handle_target']))
        checks.append(("Headroom > 1.2x", proj['headroom_factor'] > 1.2))

    if 'resource_usage' in results.get('tests', {}):
        res = results['tests']['resource_usage']
        checks.append(("Cache Hit > 95%", res.get('cache_hit_ratio', 0) > 95))

    for check_name, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {check_name:40s} {status}")

    passing_checks = sum(1 for _, passed in checks if passed)
    total_checks = len(checks)

    if total_checks > 0:
        print("\n" + "-"*80)
        print(f"  Overall:  {passing_checks}/{total_checks} checks passed ({passing_checks/total_checks*100:.0f}%)")

        if passing_checks == total_checks:
            print("\n  ✅ SYSTEM IS PRODUCTION READY")
        elif passing_checks >= total_checks * 0.8:
            print("\n  ⚠️  SYSTEM NEEDS MINOR OPTIMIZATIONS")
        else:
            print("\n  ❌ SYSTEM NEEDS SIGNIFICANT OPTIMIZATION")
    else:
        print("\n  ℹ️  Incomplete test suite - run full tests for production readiness assessment")

    print("="*80 + "\n")


def compare_results(baseline: Dict[str, Any], current: Dict[str, Any]):
    """Compare two test results"""

    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON".center(80))
    print("="*80)

    def percent_change(old: float, new: float) -> str:
        if old == 0:
            return "N/A"
        change = ((new - old) / old) * 100
        sign = "+" if change > 0 else ""
        color = "↗" if change > 0 else "↘" if change < 0 else "→"
        return f"{sign}{change:.1f}% {color}"

    # Compare search performance
    if 'search_load' in baseline.get('tests', {}) and 'search_load' in current.get('tests', {}):
        b_search = baseline['tests']['search_load']
        c_search = current['tests']['search_load']

        print("\n🔍 Search Performance")
        print("-" * 80)
        print(f"  QPS:           {b_search['actual_qps']:.1f} → {c_search['actual_qps']:.1f}  ({percent_change(b_search['actual_qps'], c_search['actual_qps'])})")
        print(f"  P50 Latency:   {b_search['latency_p50_ms']:.1f}ms → {c_search['latency_p50_ms']:.1f}ms  ({percent_change(b_search['latency_p50_ms'], c_search['latency_p50_ms'])})")
        print(f"  P99 Latency:   {b_search['latency_p99_ms']:.1f}ms → {c_search['latency_p99_ms']:.1f}ms  ({percent_change(b_search['latency_p99_ms'], c_search['latency_p99_ms'])})")
        print(f"  Error Rate:    {b_search['error_rate']*100:.2f}% → {c_search['error_rate']*100:.2f}%  ({percent_change(b_search['error_rate'], c_search['error_rate'])})")

    # Compare ingestion
    if 'ingestion' in baseline.get('tests', {}) and 'ingestion' in current.get('tests', {}):
        b_ing = baseline['tests']['ingestion']
        c_ing = current['tests']['ingestion']

        print("\n📥 Ingestion Performance")
        print("-" * 80)
        print(f"  Throughput:    {b_ing['throughput_docs_per_second']:.1f} → {c_ing['throughput_docs_per_second']:.1f} docs/s  ({percent_change(b_ing['throughput_docs_per_second'], c_ing['throughput_docs_per_second'])})")

    print("\n" + "="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(description='Performance dashboard for scale test results')
    parser.add_argument('results_file', help='Path to results JSON file')
    parser.add_argument('--compare', help='Baseline results file for comparison')

    args = parser.parse_args()

    # Load results
    with open(args.results_file, 'r') as f:
        results = json.load(f)

    # Print dashboard
    print_dashboard(results)

    # Comparison if requested
    if args.compare:
        with open(args.compare, 'r') as f:
            baseline = json.load(f)
        compare_results(baseline, results)


if __name__ == '__main__':
    main()
