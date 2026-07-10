#!/usr/bin/env python3
"""
Enhanced Contextual Bandits with Cost Model

Adds realistic cost estimation for validation testing.
"""

import psycopg2
import numpy as np
from datetime import datetime
import json
import math
from typing import Dict, List, Tuple, Optional

# Cost model (dollars per 1M tokens)
COST_MODEL = {
    # API models
    'sonnet': {'input': 3.0, 'output': 15.0},
    'haiku': {'input': 0.25, 'output': 1.25},
    'opus': {'input': 15.0, 'output': 75.0},
    'gpt-4o': {'input': 2.5, 'output': 10.0},
    'gemini-pro': {'input': 0.5, 'output': 1.5},
    'multi-model-adversarial': {'input': 3.0, 'output': 15.0},  # Assume similar to Sonnet

    # Local models (free but have quality/latency tradeoffs)
    'gemma2:2b': {'input': 0.0, 'output': 0.0},
    'phi3.5:latest': {'input': 0.0, 'output': 0.0},
    'qwen2.5:7b': {'input': 0.0, 'output': 0.0},
    'mistral-7b-instruct': {'input': 0.0, 'output': 0.0},
    'llama3:8b': {'input': 0.0, 'output': 0.0}
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost based on token usage"""
    if model not in COST_MODEL:
        # Unknown model, assume local (free)
        return 0.0

    pricing = COST_MODEL[model]
    cost = (input_tokens * pricing['input'] + output_tokens * pricing['output']) / 1_000_000
    return cost


class ContextualBandit:
    """LinUCB with Thompson Sampling"""

    def __init__(self, n_features: int, alpha: float = 1.0):
        self.n_features = n_features
        self.alpha = alpha
        self.arms: Dict[str, Dict] = {}
        self.task_types = []
        self.task_type_index = {}

    def _init_arm(self, arm_name: str):
        d = self.n_features
        self.arms[arm_name] = {
            'A': np.identity(d),
            'b': np.zeros(d),
            'theta': np.zeros(d),
            'A_inv': np.identity(d)
        }

    def _build_context(self, task_type: str, input_length: int,
                       timestamp: datetime, node_load: float = 0.5) -> np.ndarray:
        if task_type not in self.task_type_index:
            self.task_types.append(task_type)
            self.task_type_index[task_type] = len(self.task_types) - 1

        # Pad one-hot vector to max size
        max_task_types = 30  # Reserve space for future task types
        task_one_hot = np.zeros(max_task_types)
        if self.task_type_index[task_type] < max_task_types:
            task_one_hot[self.task_type_index[task_type]] = 1.0

        hour = timestamp.hour
        hour_sin = math.sin(hour * 2 * math.pi / 24)
        hour_cos = math.cos(hour * 2 * math.pi / 24)
        log_input = math.log(input_length + 1)

        context = np.concatenate([
            task_one_hot,
            [log_input, hour_sin, hour_cos, node_load]
        ])

        return context

    def select_arm(self, context: np.ndarray, available_arms: List[str]) -> Tuple[str, float]:
        best_arm = None
        best_score = -float('inf')

        for arm in available_arms:
            if arm not in self.arms:
                self._init_arm(arm)

            arm_data = self.arms[arm]
            theta = arm_data['A_inv'] @ arm_data['b']

            expected_reward = theta.T @ context
            uncertainty = self.alpha * math.sqrt(context.T @ arm_data['A_inv'] @ context)
            ucb_score = expected_reward + uncertainty

            if ucb_score > best_score:
                best_score = ucb_score
                best_arm = arm

        return best_arm, best_score

    def update(self, arm: str, context: np.ndarray, reward: float):
        if arm not in self.arms:
            self._init_arm(arm)

        arm_data = self.arms[arm]
        arm_data['A'] += np.outer(context, context)
        arm_data['b'] += reward * context

        v = arm_data['A_inv'] @ context
        arm_data['A_inv'] -= np.outer(v, v) / (1 + context.T @ v)
        arm_data['theta'] = arm_data['A_inv'] @ arm_data['b']


def run_enhanced_backtest():
    """Enhanced backtest with cost modeling"""
    print("=" * 70)
    print("CONTEXTUAL BANDITS BACKTEST (Enhanced with Cost Model)")
    print("=" * 70)

    db_config = {
        'host': 'laptop-01',
        'database': 'learning',
        'user': 'sfloess'
    }

    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()

    # Get task types
    cursor.execute("SELECT DISTINCT task_type FROM monitoring.execution_summary ORDER BY task_type")
    task_types = [row[0] for row in cursor.fetchall()]

    # Feature dimension: 30 (task types) + 4 (other features)
    n_features = 34
    bandit = ContextualBandit(n_features=n_features, alpha=1.0)
    bandit.task_types = task_types
    bandit.task_type_index = {t: i for i, t in enumerate(task_types)}

    # Get all models
    cursor.execute("SELECT DISTINCT model FROM monitoring.execution_summary")
    all_models = [row[0] for row in cursor.fetchall()]
    for model in all_models:
        bandit._init_arm(model)

    # Fetch all executions
    cursor.execute("""
        SELECT
            model,
            task_type,
            input_tokens,
            output_tokens,
            timestamp,
            quality_score,
            cost_usd,
            outcome
        FROM monitoring.execution_summary
        ORDER BY timestamp ASC
    """)

    rows = cursor.fetchall()

    # Split into training (80%) and test (20%)
    split_idx = int(len(rows) * 0.8)
    train_rows = rows[:split_idx]
    test_rows = rows[split_idx:]

    print(f"\nDataset split: {len(train_rows)} train, {len(test_rows)} test")

    # Training phase
    print("\n" + "=" * 70)
    print("TRAINING PHASE")
    print("=" * 70)

    train_reward = 0
    for row in train_rows:
        model, task_type, input_tokens, output_tokens, timestamp, quality_score, cost_usd, outcome = row

        # Multi-objective reward: quality - cost_penalty
        # Normalize: quality [0,1], cost scaled by 100× to make comparable
        actual_cost = cost_usd or estimate_cost(model, input_tokens or 0, output_tokens or 0)
        cost_penalty = actual_cost * 100  # Scale to [0,1] range

        reward = (quality_score if outcome == 'SUCCESS' else 0.0) - cost_penalty

        context = bandit._build_context(task_type, input_tokens or 0, timestamp, 0.5)
        bandit.update(model, context, reward)

        train_reward += reward

    avg_train_reward = train_reward / len(train_rows) if train_rows else 0
    print(f"Average training reward: {avg_train_reward:.4f}")

    # Test phase: Compare baseline vs contextual
    print("\n" + "=" * 70)
    print("TEST PHASE: Baseline vs Contextual Bandits")
    print("=" * 70)

    # Baseline: Random selection
    baseline_cost = 0
    baseline_quality = 0
    baseline_successes = 0

    # Contextual
    contextual_cost = 0
    contextual_quality = 0
    contextual_successes = 0

    for row in test_rows:
        actual_model, task_type, input_tokens, output_tokens, timestamp, quality_score, cost_usd, outcome = row

        context = bandit._build_context(task_type, input_tokens or 0, timestamp, 0.5)

        # What would contextual bandit select?
        selected_model, _ = bandit.select_arm(context, all_models)

        # Estimate costs
        actual_cost = cost_usd or estimate_cost(actual_model, input_tokens or 0, output_tokens or 0)

        # For contextual selection, we need to simulate what would have happened
        # Use historical average for selected model on this task type
        cursor.execute("""
            SELECT AVG(quality_score), AVG(COALESCE(cost_usd, 0))
            FROM monitoring.execution_summary
            WHERE model = %s AND task_type = %s AND outcome = 'SUCCESS'
        """, (selected_model, task_type))

        sim_row = cursor.fetchone()
        if sim_row and sim_row[0]:
            sim_quality, sim_cost = sim_row
            if sim_cost == 0:  # Estimate if not recorded
                sim_cost = estimate_cost(selected_model, input_tokens or 0, output_tokens or 0)
        else:
            # No historical data, use defaults
            sim_quality = 0.5
            sim_cost = estimate_cost(selected_model, input_tokens or 0, output_tokens or 0)

        # Baseline (actual execution)
        baseline_cost += actual_cost
        baseline_quality += quality_score if outcome == 'SUCCESS' else 0
        if outcome == 'SUCCESS':
            baseline_successes += 1

        # Contextual (simulated)
        contextual_cost += sim_cost
        contextual_quality += sim_quality
        if sim_quality > 0.5:  # Assume success threshold
            contextual_successes += 1

    cursor.close()
    conn.close()

    # Calculate metrics
    n_test = len(test_rows)
    baseline_avg_quality = baseline_quality / n_test if n_test > 0 else 0
    contextual_avg_quality = contextual_quality / n_test if n_test > 0 else 0

    cost_savings = baseline_cost - contextual_cost
    savings_pct = (cost_savings / baseline_cost * 100) if baseline_cost > 0 else 0

    # Quality-adjusted savings (account for quality difference)
    quality_ratio = contextual_avg_quality / baseline_avg_quality if baseline_avg_quality > 0 else 1
    adjusted_savings_pct = savings_pct * quality_ratio

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print("\nBaseline (Actual Execution):")
    print(f"  Total cost: ${baseline_cost:.4f}")
    print(f"  Avg quality: {baseline_avg_quality:.4f}")
    print(f"  Success rate: {baseline_successes}/{n_test} ({baseline_successes/n_test*100:.1f}%)")

    print("\nContextual Bandits (Simulated):")
    print(f"  Total cost: ${contextual_cost:.4f}")
    print(f"  Avg quality: {contextual_avg_quality:.4f}")
    print(f"  Success rate: {contextual_successes}/{n_test} ({contextual_successes/n_test*100:.1f}%)")

    print("\n" + "-" * 70)
    print(f"Cost savings: ${cost_savings:.4f} ({savings_pct:.1f}%)")
    print(f"Quality change: {(contextual_avg_quality - baseline_avg_quality):.4f}")
    print(f"Quality-adjusted savings: {adjusted_savings_pct:.1f}%")

    print("\n" + "=" * 70)
    print("VALIDATION vs RESEARCH CLAIMS")
    print("=" * 70)
    print("Research claim: 45-85% cost savings with contextual bandits")
    print(f"Our result: {savings_pct:.1f}% raw savings, {adjusted_savings_pct:.1f}% quality-adjusted")

    if 45 <= adjusted_savings_pct <= 85:
        validation = "✅ CLAIM VALIDATED"
    elif adjusted_savings_pct > 0:
        validation = "⚠ PARTIAL VALIDATION (positive savings but outside claimed range)"
    else:
        validation = "❌ CLAIM NOT VALIDATED"

    print(validation)

    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    print("\nKey findings:")
    print(f"1. Test samples: {n_test}")
    print(f"2. Cost reduction: {savings_pct:.1f}%")
    print(f"3. Quality impact: {(contextual_avg_quality/baseline_avg_quality - 1)*100:+.1f}%")
    print(f"4. Success rate change: {(contextual_successes - baseline_successes):+d} executions")

    if n_test < 100:
        print("\n⚠ WARNING: Small test set (<100 samples) may limit statistical significance")

    if baseline_cost < 0.01:
        print("⚠ WARNING: Very low baseline cost suggests mostly local models")
        print("           Cost savings may be underestimated")

    results = {
        'validation': validation,
        'baseline': {
            'cost': baseline_cost,
            'quality': baseline_avg_quality,
            'successes': baseline_successes
        },
        'contextual': {
            'cost': contextual_cost,
            'quality': contextual_avg_quality,
            'successes': contextual_successes
        },
        'savings': {
            'absolute': cost_savings,
            'percentage': savings_pct,
            'quality_adjusted_percentage': adjusted_savings_pct
        },
        'test_samples': n_test
    }

    # Save results
    with open('/tmp/contextual-bandits-enhanced-results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to /tmp/contextual-bandits-enhanced-results.json")

    return results


if __name__ == '__main__':
    run_enhanced_backtest()
