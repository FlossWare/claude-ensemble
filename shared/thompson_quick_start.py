#!/usr/bin/env python3
"""
Thompson Sampling Quick Start
Simple example of using the router in your RH workflow
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from thompson_router import (
    StateTracker,
    BetaEstimator,
    ThompsonRouter,
    RHDisseminatorRouter
)

def quick_demo():
    """Quick demo of Thompson Sampling router usage"""

    print("\n" + "=" * 70)
    print("Thompson Sampling Router - Quick Start Demo")
    print("=" * 70 + "\n")

    # Step 1: Initialize components
    print("Step 1: Initializing Thompson Sampling router...")
    state_tracker = StateTracker()
    beta_estimator = BetaEstimator(alpha_prior=2, beta_prior=1)
    thompson_router = ThompsonRouter(state_tracker, beta_estimator, cost_weight=0.25)
    rh_router = RHDisseminatorRouter(state_tracker, thompson_router)
    print("✓ Router initialized\n")

    # Step 2: Show current model statistics
    print("Step 2: Current model performance (from Phase 1 learning):")
    stats = rh_router.get_model_stats()

    print(f"\n{'Model':<20} {'Calls':>8} {'Quality':>10} {'Avg Cost':>12}")
    print("-" * 50)
    for model, stat in sorted(stats.items()):
        print(f"{model:<20} {stat['calls']:>8} {stat['quality_rate']:>9.1%}  ${stat['avg_cost']:>11.4f}")
    print()

    # Step 3: Select models for different task types
    print("Step 3: Thompson selects models for different RH task types:")

    task_types = ['code_review', 'testing', 'documentation', 'bug_analysis',
                  'architecture', 'simple_task']

    for task_type in task_types:
        selected = rh_router.select_model_for_task(task_type)
        perf = stats.get(selected, {})
        print(f"  {task_type:20} → {selected:20} "
              f"(quality: {perf.get('quality_rate', 0):.1%}, cost: ${perf.get('avg_cost', 0):.4f})")
    print()

    # Step 4: Simulate a task completion
    print("Step 4: Simulating a code review task...")
    task = 'code_review'
    model = rh_router.select_model_for_task(task)
    print(f"  Selected model: {model}")
    print(f"  (In real workflow, you would call: response = call_model('{model}', prompt))")

    # Simulate completion
    quality_score = 0.94
    latency_ms = 8500
    cost = 0.12

    rh_router.record_performance(model, task, quality_score, latency_ms, cost)
    print(f"  Result recorded: quality={quality_score:.2f}, latency={latency_ms}ms, cost=${cost:.4f}")
    print()

    # Step 5: Show updated stats
    print("Step 5: Updated statistics after task:")
    stats = rh_router.get_model_stats()

    selected_stat = stats.get(model, {})
    print(f"  {model}: {selected_stat.get('calls', 0)} calls, "
          f"quality rate {selected_stat.get('quality_rate', 0):.1%}")
    print()

    # Step 6: Advanced: Force a specific model (useful for testing)
    print("Step 6: Override for testing (force specific model):")
    task = 'testing'
    force_model = 'opus'  # Use expensive model to test its quality
    model = rh_router.select_model_for_task(task, force_model=force_model)
    print(f"  Task '{task}' forced to '{model}' (overriding Thompson's choice)")
    print()

    # Step 7: Show how to monitor Thompson decisions
    print("Step 7: Monitoring Thompson's posterior estimates:")
    all_models = state_tracker.get_all()

    print(f"\n{'Model':<15} {'Expected Quality':>18} {'Success Rate':>15} {'Beta Parameters':>20}")
    print("-" * 70)

    for model_name, perf in sorted(all_models.items()):
        exp_quality = beta_estimator.expected_quality(perf)
        alpha, beta = beta_estimator.estimate_posterior(perf)
        print(f"{model_name:<15} {exp_quality:>17.2%}  {perf.quality_rate:>14.1%}  "
              f"Beta({alpha:.0f}, {beta:.0f})")
    print()

    # Summary
    print("=" * 70)
    print("Thompson Sampling is now routing your RH tasks intelligently!")
    print("\nKey points:")
    print("  • Each task type has preferred models")
    print("  • Thompson learns from every task to improve routing")
    print("  • Cost_weight (0.25) balances quality vs cost")
    print("  • Can force specific model for testing/validation")
    print("\nNext steps:")
    print("  • Integrate into your RH Disseminator workflow")
    print("  • Record task results with record_performance()")
    print("  • Monitor stats with get_model_stats()")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    quick_demo()
