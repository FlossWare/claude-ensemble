#!/usr/bin/env python3
"""
Team Velocity Predictor Usage Example

Shows how to use the trained team velocity predictor to estimate
workflow performance before execution.
"""

import json
import sys
from pathlib import Path
from team_velocity_predictor import TeamVelocityPredictor


def predict_workflow_performance(workflow_config):
    """Predict team performance for a workflow configuration"""

    # Load trained model
    model_path = Path.home() / ".claude" / "learning" / "team_velocity_predictor.pkl"

    if not model_path.exists():
        print(f"❌ Model not found at {model_path}")
        print("Run: python3 tools/team_velocity_predictor.py")
        sys.exit(1)

    predictor = TeamVelocityPredictor()
    predictor.load(model_path)

    # Make prediction
    result = predictor.predict(workflow_config)

    return result


def main():
    """Example usage"""

    print("=" * 70)
    print("TEAM VELOCITY PREDICTOR - USAGE EXAMPLE")
    print("=" * 70)

    # Example 1: Current fleet configuration (8 workers)
    print("\n📊 EXAMPLE 1: Full Fleet - Deep Research Workflow")
    print("-" * 70)

    config1 = {
        'num_workers': 8,
        'num_tasks': 30,
        'task_complexity': 'complex',
        'has_dependencies': True,
        'model_diversity': 6,
        'parallel_ratio': 0.65,
        'historical_success_rate': 0.80,
        'avg_worker_latency_ms': 4000,
    }

    result1 = predict_workflow_performance(config1)

    print(f"Configuration:")
    print(f"  Workers: {config1['num_workers']}")
    print(f"  Tasks: {config1['num_tasks']}")
    print(f"  Complexity: {config1['task_complexity']}")
    print(f"  Model Diversity: {config1['model_diversity']}")
    print(f"\nPredictions:")
    print(f"  Duration:         {result1['predicted_duration_minutes']:.1f} min")
    print(f"  Parallel Speedup: {result1['actual_speedup']:.1f}x "
          f"({result1['efficiency_percent']:.1f}% efficient)")
    print(f"  Utilization:      {result1['resource_utilization']:.1%}")
    print(f"  Success Prob:     {result1['success_probability']:.1%}")

    # Example 2: Small team for quick tasks
    print("\n📊 EXAMPLE 2: Small Team - Quick Fix Workflow")
    print("-" * 70)

    config2 = {
        'num_workers': 4,
        'num_tasks': 8,
        'task_complexity': 'simple',
        'has_dependencies': False,
        'model_diversity': 4,
        'parallel_ratio': 0.9,
        'historical_success_rate': 0.92,
        'avg_worker_latency_ms': 1500,
    }

    result2 = predict_workflow_performance(config2)

    print(f"Configuration:")
    print(f"  Workers: {config2['num_workers']}")
    print(f"  Tasks: {config2['num_tasks']}")
    print(f"  Complexity: {config2['task_complexity']}")
    print(f"\nPredictions:")
    print(f"  Duration:         {result2['predicted_duration_minutes']:.1f} min")
    print(f"  Parallel Speedup: {result2['actual_speedup']:.1f}x "
          f"({result2['efficiency_percent']:.1f}% efficient)")
    print(f"  Utilization:      {result2['resource_utilization']:.1%}")
    print(f"  Success Prob:     {result2['success_probability']:.1%}")

    # Example 3: Very complex, high-dependency workflow
    print("\n📊 EXAMPLE 3: Complex Sequential Workflow")
    print("-" * 70)

    config3 = {
        'num_workers': 6,
        'num_tasks': 20,
        'task_complexity': 'very_complex',
        'has_dependencies': True,
        'model_diversity': 5,
        'parallel_ratio': 0.4,
        'historical_success_rate': 0.70,
        'avg_worker_latency_ms': 10000,
    }

    result3 = predict_workflow_performance(config3)

    print(f"Configuration:")
    print(f"  Workers: {config3['num_workers']}")
    print(f"  Tasks: {config3['num_tasks']}")
    print(f"  Complexity: {config3['task_complexity']}")
    print(f"  Parallel Ratio: {config3['parallel_ratio']} (high dependencies)")
    print(f"\nPredictions:")
    print(f"  Duration:         {result3['predicted_duration_minutes']:.1f} min")
    print(f"  Parallel Speedup: {result3['actual_speedup']:.1f}x "
          f"({result3['efficiency_percent']:.1f}% efficient)")
    print(f"  Utilization:      {result3['resource_utilization']:.1%}")
    print(f"  Success Prob:     {result3['success_probability']:.1%}")

    # Comparison
    print("\n📊 COMPARISON SUMMARY")
    print("=" * 70)
    print(f"{'Workflow':<25} {'Duration':<15} {'Speedup':<12} {'Success':<10}")
    print("-" * 70)
    print(f"{'Full Fleet (Complex)':<25} "
          f"{result1['predicted_duration_minutes']:.1f} min{'':<8} "
          f"{result1['actual_speedup']:.1f}x{'':<7} "
          f"{result1['success_probability']:.1%}")
    print(f"{'Small Team (Simple)':<25} "
          f"{result2['predicted_duration_minutes']:.1f} min{'':<8} "
          f"{result2['actual_speedup']:.1f}x{'':<7} "
          f"{result2['success_probability']:.1%}")
    print(f"{'Complex Sequential':<25} "
          f"{result3['predicted_duration_minutes']:.1f} min{'':<8} "
          f"{result3['actual_speedup']:.1f}x{'':<7} "
          f"{result3['success_probability']:.1%}")

    print("\n💡 INSIGHTS:")
    print("  - Small teams on simple tasks achieve highest efficiency")
    print("  - Complex workflows with dependencies limit parallelism")
    print("  - More workers doesn't always mean faster completion")
    print("  - Sweet spot: 4-6 workers for most workflows")

    # JSON output for programmatic use
    output = {
        'predictions': [
            {'name': 'Full Fleet (Complex)', **result1},
            {'name': 'Small Team (Simple)', **result2},
            {'name': 'Complex Sequential', **result3},
        ]
    }

    output_path = Path("/tmp/team_velocity_predictions.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Full results saved to: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
