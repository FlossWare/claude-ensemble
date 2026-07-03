#!/usr/bin/env python3
"""
Performance Optimizer Usage Example

Shows how to load and use the trained performance optimizer
to analyze code and get optimization suggestions.
"""

import pickle
import json
from pathlib import Path


def analyze_file(optimizer, filepath):
    """Analyze a single file for performance issues"""

    code = Path(filepath).read_text()
    findings = optimizer.analyze_code(code, filepath)

    print(f"\n=== Analysis: {filepath} ===")
    print(f"Found {len(findings)} optimization opportunities\n")

    # Group by severity
    critical = [f for f in findings if f['severity'] >= 8]
    high = [f for f in findings if 6 <= f['severity'] < 8]
    medium = [f for f in findings if f['severity'] < 6]

    if critical:
        print(f"🔴 CRITICAL ({len(critical)} issues):")
        for f in critical[:3]:  # Top 3
            print(f"  Line {f['line']}: {f['type']}")
            print(f"  → {f['suggestion']}")
            print(f"  → Estimated speedup: {f['estimated_speedup_pct']}%")
            print()

    if high:
        print(f"🟡 HIGH ({len(high)} issues):")
        for f in high[:3]:
            print(f"  Line {f['line']}: {f['type']}")
            print(f"  → {f['suggestion']}")
            print(f"  → Estimated speedup: {f['estimated_speedup_pct']}%")
            print()

    if medium:
        print(f"🟢 MEDIUM ({len(medium)} issues)")

    # Calculate total speedup potential
    total_speedup = sum(f['estimated_speedup_pct'] for f in findings)
    avg_speedup = total_speedup / len(findings) if findings else 0

    print(f"\n📊 Total speedup potential: {total_speedup:.0f}%")
    print(f"📊 Average per fix: {avg_speedup:.0f}%")

    return findings


def get_model_recommendation(optimizer, task_type='code_generation'):
    """Get model recommendation for task type"""

    # Load from training results
    if not optimizer.optimization_history:
        print("No training history available")
        return None

    latest = optimizer.optimization_history[0]
    recommendations = latest.get('model_recommendations', [])

    for rec in recommendations:
        if rec['task_type'] == task_type:
            print(f"\n=== Model Recommendation: {task_type} ===")
            print(f"Use: {rec['current_best']}")
            print(f"Avoid: {rec['avoid']}")
            print(f"Speedup: {rec['speedup_pct']:.0f}%")
            print(f"Quality gain: {rec['quality_gain_pct']:.1f}%")
            return rec

    print(f"No recommendation for task type: {task_type}")
    return None


def main():
    # Load trained optimizer
    optimizer_path = '/home/sfloess/.claude/learning/performance_optimizer.pkl'

    print("Loading trained optimizer...")
    with open(optimizer_path, 'rb') as f:
        data = pickle.load(f)

    # Reconstruct optimizer
    from performance_optimizer import PerformanceOptimizer
    optimizer = PerformanceOptimizer()
    optimizer.model_performance = data['model_performance']
    optimizer.optimization_history = data['optimization_history']
    optimizer.learned_speedups = data.get('learned_speedups', {})

    print(f"✓ Loaded optimizer trained at {data['trained_at']}")
    print(f"✓ {optimizer.model_performance['total_models']} models analyzed")
    print(f"✓ Avg quality: {optimizer.model_performance['avg_quality']:.3f}")

    # Example 1: Analyze a file
    test_file = '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/performance_dashboard.py'
    findings = analyze_file(optimizer, test_file)

    # Example 2: Get model recommendation
    get_model_recommendation(optimizer, 'code_generation')

    # Example 3: Print top patterns
    print("\n=== Top Learned Patterns ===")
    latest = optimizer.optimization_history[0]
    for i, strategy in enumerate(latest['optimization_strategies'][:5], 1):
        print(f"\n{i}. {strategy['optimization_type']}")
        print(f"   Found {strategy['occurrences']} times")
        print(f"   Avg speedup: {strategy['estimated_avg_speedup_pct']:.0f}%")
        print(f"   Severity: {strategy['avg_severity']:.1f}/10")


if __name__ == '__main__':
    main()
