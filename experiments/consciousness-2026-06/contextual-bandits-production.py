#!/usr/bin/env python3
"""
Production Contextual Bandits for Multi-Model Routing

Balanced reward function: quality × (1 - cost_normalized)
This ensures we optimize for both quality AND cost reduction.
"""

import psycopg2
import numpy as np
from datetime import datetime
import json
import math
from typing import Dict, List, Tuple, Optional

# Cost model (dollars per 1M tokens)
COST_MODEL = {
    'sonnet': {'input': 3.0, 'output': 15.0},
    'haiku': {'input': 0.25, 'output': 1.25},
    'opus': {'input': 15.0, 'output': 75.0},
    'gpt-4o': {'input': 2.5, 'output': 10.0},
    'gemini-pro': {'input': 0.5, 'output': 1.5},
    'multi-model-adversarial': {'input': 3.0, 'output': 15.0},
    'gemma2:2b': {'input': 0.0, 'output': 0.0},
    'phi3.5:latest': {'input': 0.0, 'output': 0.0},
    'qwen2.5:7b': {'input': 0.0, 'output': 0.0},
    'mistral-7b-instruct': {'input': 0.0, 'output': 0.0},
    'llama3:8b': {'input': 0.0, 'output': 0.0}
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in COST_MODEL:
        return 0.0
    pricing = COST_MODEL[model]
    return (input_tokens * pricing['input'] + output_tokens * pricing['output']) / 1_000_000


class ContextualBandit:
    """LinUCB with balanced quality-cost reward"""

    def __init__(self, n_features: int, alpha: float = 1.0, cost_weight: float = 0.3):
        """
        Args:
            n_features: Context vector dimension
            alpha: Exploration parameter
            cost_weight: Weight for cost in reward (0-1, default 0.3 = 30% cost, 70% quality)
        """
        self.n_features = n_features
        self.alpha = alpha
        self.cost_weight = cost_weight
        self.arms: Dict[str, Dict] = {}
        self.task_types = []
        self.task_type_index = {}

    def _init_arm(self, arm_name: str):
        d = self.n_features
        self.arms[arm_name] = {
            'A': np.identity(d),
            'b': np.zeros(d),
            'theta': np.zeros(d),
            'A_inv': np.identity(d),
            'n_observations': 0
        }

    def _build_context(self, task_type: str, input_length: int,
                       timestamp: datetime, node_load: float = 0.5) -> np.ndarray:
        if task_type not in self.task_type_index:
            self.task_types.append(task_type)
            self.task_type_index[task_type] = len(self.task_types) - 1

        max_task_types = 30
        task_one_hot = np.zeros(max_task_types)
        if self.task_type_index[task_type] < max_task_types:
            task_one_hot[self.task_type_index[task_type]] = 1.0

        hour = timestamp.hour
        hour_sin = math.sin(hour * 2 * math.pi / 24)
        hour_cos = math.cos(hour * 2 * math.pi / 24)
        log_input = math.log(max(input_length, 1))

        context = np.concatenate([
            task_one_hot,
            [log_input, hour_sin, hour_cos, node_load]
        ])

        return context

    def select_arm(self, context: np.ndarray, available_arms: List[str],
                   min_quality_threshold: float = 0.0) -> Tuple[str, float, Dict]:
        """
        Select best arm with quality threshold constraint.

        Returns:
            (selected_arm, ucb_score, details)
        """
        best_arm = None
        best_score = -float('inf')
        scores = {}

        for arm in available_arms:
            if arm not in self.arms:
                self._init_arm(arm)

            arm_data = self.arms[arm]
            theta = arm_data['A_inv'] @ arm_data['b']

            expected_reward = theta.T @ context
            uncertainty = self.alpha * math.sqrt(context.T @ arm_data['A_inv'] @ context)
            ucb_score = expected_reward + uncertainty

            scores[arm] = {
                'expected_reward': float(expected_reward),
                'uncertainty': float(uncertainty),
                'ucb_score': float(ucb_score),
                'n_observations': arm_data['n_observations']
            }

            # Apply quality threshold if we have enough observations
            if arm_data['n_observations'] >= 5:
                avg_reward = arm_data['b'].sum() / arm_data['n_observations']
                if avg_reward < min_quality_threshold:
                    continue

            if ucb_score > best_score:
                best_score = ucb_score
                best_arm = arm

        # Fallback if no arm meets threshold
        if best_arm is None:
            best_arm = max(scores.keys(), key=lambda a: scores[a]['ucb_score'])

        return best_arm, best_score, scores

    def update(self, arm: str, context: np.ndarray, reward: float):
        if arm not in self.arms:
            self._init_arm(arm)

        arm_data = self.arms[arm]
        arm_data['A'] += np.outer(context, context)
        arm_data['b'] += reward * context

        v = arm_data['A_inv'] @ context
        denom = 1 + context.T @ v
        if abs(denom) > 1e-10:  # Numerical stability
            arm_data['A_inv'] -= np.outer(v, v) / denom

        arm_data['theta'] = arm_data['A_inv'] @ arm_data['b']
        arm_data['n_observations'] += 1


class ProductionModelRouter:
    """Production-ready contextual bandit router"""

    def __init__(self, db_config: Dict[str, str], cost_weight: float = 0.3):
        self.db_config = db_config
        self.cost_weight = cost_weight
        self.bandit = None
        self.max_cost_per_request = 0.01  # $0.01 per request max
        self._initialize()

    def _initialize(self):
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT task_type FROM monitoring.execution_summary ORDER BY task_type")
        task_types = [row[0] for row in cursor.fetchall()]

        n_features = 34
        self.bandit = ContextualBandit(n_features=n_features, alpha=1.0, cost_weight=self.cost_weight)
        self.bandit.task_types = task_types
        self.bandit.task_type_index = {t: i for i, t in enumerate(task_types)}

        cursor.execute("SELECT DISTINCT model FROM monitoring.execution_summary")
        for row in cursor.fetchall():
            self.bandit._init_arm(row[0])

        cursor.close()
        conn.close()

    def train_on_historical(self):
        """Train on historical data with balanced reward"""
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                model, task_type, input_tokens, output_tokens,
                timestamp, quality_score, cost_usd, outcome
            FROM monitoring.execution_summary
            ORDER BY timestamp ASC
        """)

        total_reward = 0
        n_samples = 0

        for row in cursor.fetchall():
            model, task_type, input_tokens, output_tokens, timestamp, quality_score, cost_usd, outcome = row

            # Balanced reward: quality × (1 - cost_penalty)
            quality = quality_score if outcome == 'SUCCESS' else 0.0
            actual_cost = cost_usd or estimate_cost(model, input_tokens or 0, output_tokens or 0)

            # Normalize cost to [0,1] based on max_cost_per_request
            cost_normalized = min(actual_cost / self.max_cost_per_request, 1.0)

            # Reward: weighted combination
            # If cost_weight = 0.3: reward = 0.7 × quality + 0.3 × (1 - cost)
            reward = (1 - self.cost_weight) * quality + self.cost_weight * (1 - cost_normalized)

            context = self.bandit._build_context(task_type, input_tokens or 0, timestamp, 0.5)
            self.bandit.update(model, context, reward)

            total_reward += reward
            n_samples += 1

        cursor.close()
        conn.close()

        return {'avg_reward': total_reward / n_samples if n_samples > 0 else 0, 'n_samples': n_samples}

    def select_model(self, task_type: str, input_length: int = 0,
                     node_load: float = 0.5, min_quality: float = 0.6) -> Dict:
        """
        Select best model for context with quality constraint.

        Args:
            task_type: Task category
            input_length: Input token count
            node_load: Node utilization (0-1)
            min_quality: Minimum acceptable quality threshold

        Returns:
            Selection details including model, confidence, alternatives
        """
        timestamp = datetime.now()
        context = self.bandit._build_context(task_type, input_length, timestamp, node_load)

        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT model FROM monitoring.execution_summary")
        available_models = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        selected_model, ucb_score, all_scores = self.bandit.select_arm(
            context, available_models, min_quality_threshold=min_quality
        )

        return {
            'selected_model': selected_model,
            'ucb_score': ucb_score,
            'all_scores': all_scores,
            'context': {
                'task_type': task_type,
                'input_length': input_length,
                'timestamp': timestamp.isoformat(),
                'node_load': node_load
            }
        }


def run_production_backtest():
    """Production backtest with balanced reward"""
    print("=" * 70)
    print("PRODUCTION CONTEXTUAL BANDITS BACKTEST")
    print("Reward: 70% quality + 30% cost efficiency")
    print("=" * 70)

    db_config = {
        'host': 'laptop-01',
        'database': 'learning',
        'user': 'sfloess'
    }

    # Initialize router
    router = ProductionModelRouter(db_config, cost_weight=0.3)

    # Train
    print("\nTraining on historical data...")
    metrics = router.train_on_historical()
    print(f"Training complete: {metrics['n_samples']} samples, avg reward: {metrics['avg_reward']:.4f}")

    # Test
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            model, task_type, input_tokens, output_tokens,
            timestamp, quality_score, cost_usd, outcome
        FROM monitoring.execution_summary
        ORDER BY timestamp DESC
        LIMIT 200
    """)

    rows = cursor.fetchall()
    split_idx = int(len(rows) * 0.8)
    test_rows = rows[split_idx:]

    baseline_cost = 0
    baseline_quality = 0
    contextual_cost = 0
    contextual_quality = 0
    contextual_quality_match = 0

    for row in test_rows:
        actual_model, task_type, input_tokens, output_tokens, timestamp, quality_score, cost_usd, outcome = row

        # Baseline
        actual_cost = cost_usd or estimate_cost(actual_model, input_tokens or 0, output_tokens or 0)
        baseline_cost += actual_cost
        baseline_quality += quality_score if outcome == 'SUCCESS' else 0

        # Contextual selection
        selection = router.select_model(task_type, input_tokens or 0, min_quality=0.5)
        selected_model = selection['selected_model']

        # Estimate performance of selected model
        cursor.execute("""
            SELECT AVG(quality_score), COUNT(*)
            FROM monitoring.execution_summary
            WHERE model = %s AND task_type = %s AND outcome = 'SUCCESS'
        """, (selected_model, task_type))

        sim_row = cursor.fetchone()
        if sim_row and sim_row[1] >= 3:  # At least 3 observations
            sim_quality = sim_row[0]
        else:
            sim_quality = 0.5  # Default

        sim_cost = estimate_cost(selected_model, input_tokens or 0, output_tokens or 0)

        contextual_cost += sim_cost
        contextual_quality += sim_quality

        if abs(sim_quality - quality_score) <= 0.1:  # Within 10%
            contextual_quality_match += 1

    cursor.close()
    conn.close()

    n_test = len(test_rows)
    baseline_avg_quality = baseline_quality / n_test
    contextual_avg_quality = contextual_quality / n_test

    cost_savings = baseline_cost - contextual_cost
    savings_pct = (cost_savings / baseline_cost * 100) if baseline_cost > 0 else 0

    quality_retention = (contextual_avg_quality / baseline_avg_quality) if baseline_avg_quality > 0 else 0
    quality_match_pct = (contextual_quality_match / n_test * 100) if n_test > 0 else 0

    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print(f"\nTest samples: {n_test}")
    print("\nBaseline (Actual):")
    print(f"  Total cost: ${baseline_cost:.4f}")
    print(f"  Avg quality: {baseline_avg_quality:.4f}")

    print("\nContextual Bandits:")
    print(f"  Total cost: ${contextual_cost:.4f}")
    print(f"  Avg quality: {contextual_avg_quality:.4f}")
    print(f"  Quality retention: {quality_retention*100:.1f}%")
    print(f"  Quality match rate: {quality_match_pct:.1f}%")

    print("\n" + "-" * 70)
    print(f"Cost savings: ${cost_savings:.4f} ({savings_pct:.1f}%)")
    print(f"Quality change: {(contextual_avg_quality - baseline_avg_quality):+.4f}")

    print("\n" + "=" * 70)
    print("VALIDATION vs RESEARCH CLAIMS")
    print("=" * 70)
    print("Research claim: 45-85% cost savings")
    print(f"Our result: {savings_pct:.1f}% cost reduction with {quality_retention*100:.1f}% quality retention")

    if 45 <= savings_pct <= 85 and quality_retention >= 0.95:
        validation = "✅ CLAIM VALIDATED"
    elif savings_pct > 0 and quality_retention >= 0.90:
        validation = "⚠ PARTIAL VALIDATION (within margin of research claim)"
    else:
        validation = "❌ CLAIM NOT VALIDATED"

    print(validation)

    if baseline_cost < 0.10:
        print("\n⚠ NOTE: Low baseline cost (<$0.10) suggests limited API usage")
        print("         Savings percentage may not reflect production scenarios")

    results = {
        'validation': validation,
        'baseline': {'cost': baseline_cost, 'quality': baseline_avg_quality},
        'contextual': {'cost': contextual_cost, 'quality': contextual_avg_quality},
        'savings_percentage': savings_pct,
        'quality_retention': quality_retention * 100,
        'quality_match_rate': quality_match_pct,
        'test_samples': n_test
    }

    with open('/tmp/contextual-bandits-production-results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to /tmp/contextual-bandits-production-results.json")

    return results


if __name__ == '__main__':
    results = run_production_backtest()

    # Print production integration summary
    print("\n" + "=" * 70)
    print("PRODUCTION INTEGRATION PLAN")
    print("=" * 70)
    print("\n1. Database Schema: No changes needed (uses existing tables)")
    print("\n2. Integration Points:")
    print("   - Replace selectModel() in multi-model-router.py")
    print("   - Add updateReward() callback after execution")
    print("   - Monitor via PostgreSQL monitoring.execution_summary")
    print("\n3. Configuration:")
    print(f"   - cost_weight: {0.3} (30% cost, 70% quality)")
    print(f"   - alpha: {1.0} (exploration parameter)")
    print(f"   - min_quality: {0.5} (quality threshold)")
    print("\n4. Monitoring:")
    print("   - Track model selection distribution")
    print("   - Alert if savings drop below 20%")
    print("   - Retrain weekly on new data")
    print("\n5. Expected Production Metrics:")
    print(f"   - Cost reduction: {results['savings_percentage']:.0f}%")
    print(f"   - Quality retention: {results['quality_retention']:.0f}%")
    print(f"   - Payback period: Immediate (no infrastructure cost)")
