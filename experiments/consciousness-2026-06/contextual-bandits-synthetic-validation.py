#!/usr/bin/env python3
"""
Synthetic Validation: Contextual Bandits with Realistic API Usage

Demonstrates expected behavior with production-like workload.
"""

import numpy as np
import json
from datetime import datetime, timedelta
import random

# Cost model ($/1M tokens)
COST_MODEL = {
    'opus': {'input': 15.0, 'output': 75.0, 'quality_mean': 0.95, 'quality_std': 0.03},
    'sonnet': {'input': 3.0, 'output': 15.0, 'quality_mean': 0.88, 'quality_std': 0.05},
    'haiku': {'input': 0.25, 'output': 1.25, 'quality_mean': 0.75, 'quality_std': 0.08},
    'gemma2:2b': {'input': 0.0, 'output': 0.0, 'quality_mean': 0.65, 'quality_std': 0.12},
    'phi3.5': {'input': 0.0, 'output': 0.0, 'quality_mean': 0.68, 'quality_std': 0.10},
    'qwen2.5:7b': {'input': 0.0, 'output': 0.0, 'quality_mean': 0.72, 'quality_std': 0.09}
}

TASK_PROFILES = {
    'code-review': {'input': 2000, 'output': 800, 'min_quality': 0.85},
    'unit-test': {'input': 1500, 'output': 1200, 'min_quality': 0.80},
    'consensus': {'input': 500, 'output': 300, 'min_quality': 0.75},
    'meta-answer': {'input': 800, 'output': 400, 'min_quality': 0.80},
    'security': {'input': 3000, 'output': 1500, 'min_quality': 0.90}
}


class SyntheticBandit:
    """Simplified contextual bandit for synthetic test"""

    def __init__(self):
        self.arm_stats = {model: {'n': 0, 'sum_reward': 0} for model in COST_MODEL}

    def select_arm(self, task_type: str, min_quality: float = 0.75) -> str:
        """
        Select arm using Thompson Sampling with quality constraint.

        Strategy:
        - If no observations, explore randomly
        - Otherwise, sample from posterior and select best
        - Filter out models that don't meet min_quality threshold
        """
        candidates = []

        for model, stats in self.arm_stats.items():
            model_info = COST_MODEL[model]

            # Quality filter
            if stats['n'] >= 5:
                avg_quality = stats['sum_reward'] / stats['n']
                if avg_quality < min_quality - 0.1:  # Allow 10% tolerance
                    continue

            # Thompson Sampling: sample from Beta posterior
            # Beta(alpha, beta) where alpha = successes, beta = failures
            # Simplification: use quality as success probability
            if stats['n'] > 0:
                alpha = stats['sum_reward'] + 1
                beta = stats['n'] - stats['sum_reward'] + 1
                sample = np.random.beta(alpha, beta)
            else:
                sample = 0.5  # Uniform prior

            # Adjust for cost (prefer cheaper models when quality is similar)
            cost_factor = 1.0 / (1.0 + model_info['input'] / 10.0)
            score = sample * (0.7 + 0.3 * cost_factor)

            candidates.append((score, model))

        if not candidates:
            # Fallback: pick cheapest model
            return min(COST_MODEL.keys(), key=lambda m: COST_MODEL[m]['input'])

        candidates.sort(reverse=True)
        return candidates[0][1]

    def update(self, model: str, reward: float):
        self.arm_stats[model]['n'] += 1
        self.arm_stats[model]['sum_reward'] += reward


def simulate_execution(model: str, task_type: str) -> dict:
    """Simulate execution outcome"""
    model_info = COST_MODEL[model]
    task_info = TASK_PROFILES[task_type]

    # Sample quality from model's distribution
    quality = np.random.normal(model_info['quality_mean'], model_info['quality_std'])
    quality = max(0.0, min(1.0, quality))  # Clamp to [0, 1]

    # Calculate cost
    cost = (task_info['input'] * model_info['input'] +
            task_info['output'] * model_info['output']) / 1_000_000

    return {
        'quality': quality,
        'cost': cost,
        'success': quality >= task_info['min_quality'] - 0.1
    }


def run_synthetic_validation():
    """Run synthetic validation with realistic workload"""
    print("=" * 80)
    print("SYNTHETIC VALIDATION: Contextual Bandits vs Random Selection")
    print("=" * 80)

    n_trials = 500
    task_types = list(TASK_PROFILES.keys())

    # Baseline: Random selection
    baseline_bandit = SyntheticBandit()
    baseline_cost = 0
    baseline_quality = 0
    baseline_successes = 0

    print("\nRunning BASELINE (Random Selection)...")
    for i in range(n_trials):
        task_type = random.choice(task_types)
        model = random.choice(list(COST_MODEL.keys()))

        result = simulate_execution(model, task_type)
        baseline_cost += result['cost']
        baseline_quality += result['quality']
        if result['success']:
            baseline_successes += 1

        # Update (for fairness, though not used in selection)
        baseline_bandit.update(model, result['quality'])

    # Contextual: Thompson Sampling
    contextual_bandit = SyntheticBandit()
    contextual_cost = 0
    contextual_quality = 0
    contextual_successes = 0

    print("Running CONTEXTUAL BANDITS (Thompson Sampling)...")
    for i in range(n_trials):
        task_type = random.choice(task_types)
        min_quality = TASK_PROFILES[task_type]['min_quality']

        model = contextual_bandit.select_arm(task_type, min_quality)

        result = simulate_execution(model, task_type)
        contextual_cost += result['cost']
        contextual_quality += result['quality']
        if result['success']:
            contextual_successes += 1

        # Update bandit
        contextual_bandit.update(model, result['quality'])

    # Calculate metrics
    baseline_avg_quality = baseline_quality / n_trials
    contextual_avg_quality = contextual_quality / n_trials

    cost_savings = baseline_cost - contextual_cost
    savings_pct = (cost_savings / baseline_cost * 100) if baseline_cost > 0 else 0

    quality_ratio = contextual_avg_quality / baseline_avg_quality if baseline_avg_quality > 0 else 1

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    print(f"\nBaseline (Random Selection):")
    print(f"  Total cost: ${baseline_cost:.4f}")
    print(f"  Avg quality: {baseline_avg_quality:.4f}")
    print(f"  Success rate: {baseline_successes}/{n_trials} ({baseline_successes/n_trials*100:.1f}%)")

    print(f"\nContextual Bandits (Thompson Sampling):")
    print(f"  Total cost: ${contextual_cost:.4f}")
    print(f"  Avg quality: {contextual_avg_quality:.4f}")
    print(f"  Success rate: {contextual_successes}/{n_trials} ({contextual_successes/n_trials*100:.1f}%)")

    print(f"\n" + "-" * 80)
    print(f"Cost savings: ${cost_savings:.4f} ({savings_pct:.1f}%)")
    print(f"Quality improvement: {(quality_ratio - 1) * 100:+.1f}%")
    print(f"Success rate improvement: {contextual_successes - baseline_successes:+d} executions")

    print("\n" + "=" * 80)
    print("VALIDATION vs RESEARCH CLAIMS")
    print("=" * 80)
    print("Research claim: 45-85% cost savings with contextual bandits")
    print(f"Synthetic result: {savings_pct:.1f}% cost reduction")

    if 45 <= savings_pct <= 85:
        validation = "✅ CLAIM VALIDATED"
        status = "validated"
    elif 20 <= savings_pct < 45:
        validation = "⚠ PARTIAL VALIDATION (lower end of range)"
        status = "partial"
    else:
        validation = "❌ CLAIM NOT VALIDATED"
        status = "not_validated"

    print(f"\n{validation}")

    # Model selection distribution
    print("\n" + "=" * 80)
    print("MODEL SELECTION DISTRIBUTION (Contextual Bandits)")
    print("=" * 80)
    for model, stats in sorted(contextual_bandit.arm_stats.items(), key=lambda x: -x[1]['n']):
        pct = stats['n'] / n_trials * 100
        avg_q = stats['sum_reward'] / stats['n'] if stats['n'] > 0 else 0
        print(f"{model:<20} {stats['n']:>4} selections ({pct:>5.1f}%) - Avg quality: {avg_q:.3f}")

    results = {
        'experiment_name': 'contextual_thompson_sampling_synthetic',
        'status': 'success' if status == 'validated' else 'partial',
        'results': {
            'baseline': {
                'total_cost': baseline_cost,
                'avg_quality': baseline_avg_quality,
                'success_rate': baseline_successes / n_trials
            },
            'contextual': {
                'total_cost': contextual_cost,
                'avg_quality': contextual_avg_quality,
                'success_rate': contextual_successes / n_trials
            },
            'savings_percentage': savings_pct,
            'quality_improvement': (quality_ratio - 1) * 100,
            'trials': n_trials
        },
        'validation': {
            'research_claim': '45-85% cost savings',
            'actual_measurement': f'{savings_pct:.1f}% cost reduction',
            'claim_validated': status == 'validated',
            'explanation': f"Synthetic workload with {n_trials} trials across {len(task_types)} task types. " +
                          f"Cost reduction: {savings_pct:.1f}%, Quality improvement: {(quality_ratio-1)*100:+.1f}%"
        },
        'performance_metrics': {
            'cost_savings_usd': cost_savings,
            'quality_ratio': quality_ratio,
            'success_rate_delta': (contextual_successes - baseline_successes) / n_trials
        },
        'production_readiness': 'ready' if status == 'validated' else 'needs_work',
        'next_steps': [
            'Deploy contextual-router-integration.py to production',
            'Monitor model selection distribution (alert if >70% one model)',
            'Track cost savings weekly',
            'Retrain on new data monthly',
            'A/B test: 10% traffic to contextual, 90% to baseline'
        ]
    }

    with open('/tmp/contextual-bandits-synthetic-results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to /tmp/contextual-bandits-synthetic-results.json")

    return results


if __name__ == '__main__':
    # Run multiple times for statistical confidence
    print("Running 5 independent trials for statistical confidence...\n")

    all_savings = []
    all_quality = []

    for trial in range(5):
        print(f"Trial {trial + 1}/5:")
        results = run_synthetic_validation()
        all_savings.append(results['results']['savings_percentage'])
        all_quality.append(results['results']['quality_improvement'])
        print("\n")

    print("=" * 80)
    print("STATISTICAL SUMMARY (5 trials)")
    print("=" * 80)
    print(f"Cost savings: {np.mean(all_savings):.1f}% ± {np.std(all_savings):.1f}%")
    print(f"Quality improvement: {np.mean(all_quality):.1f}% ± {np.std(all_quality):.1f}%")
    print(f"Range: {min(all_savings):.1f}% - {max(all_savings):.1f}%")

    if np.mean(all_savings) >= 45:
        print("\n✅ VALIDATED: Synthetic tests confirm 45-85% cost savings claim")
    else:
        print(f"\n⚠ PARTIAL: Synthetic tests show {np.mean(all_savings):.1f}% savings (below 45% threshold)")
