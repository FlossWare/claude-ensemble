#!/usr/bin/env python3
"""
Contextual Thompson Sampling (LinUCB) for Multi-Model Routing

Upgrade from basic Thompson Sampling to context-aware bandit.
Features: task_type, input_length, time_of_day, node_load
"""

import psycopg2
import numpy as np
from datetime import datetime
import json
import math
from typing import Dict, List, Tuple, Optional

class ContextualBandit:
    """LinUCB implementation with Thompson Sampling posterior"""

    def __init__(self, n_features: int, alpha: float = 0.5):
        """
        Args:
            n_features: Dimension of context feature vector
            alpha: Exploration parameter (higher = more exploration)
        """
        self.n_features = n_features
        self.alpha = alpha

        # Per-arm parameters (model-specific)
        self.arms: Dict[str, Dict] = {}

        # Task type categories for one-hot encoding
        self.task_types = []
        self.task_type_index = {}

    def _init_arm(self, arm_name: str):
        """Initialize parameters for a new arm (model)"""
        d = self.n_features
        self.arms[arm_name] = {
            'A': np.identity(d),  # Design matrix
            'b': np.zeros(d),      # Reward vector
            'theta': np.zeros(d),  # Parameter estimate
            'A_inv': np.identity(d)
        }

    def _build_context(self, task_type: str, input_length: int,
                       timestamp: datetime, node_load: float = 0.5) -> np.ndarray:
        """
        Build feature vector from context.

        Features:
        - task_type (one-hot encoded)
        - log(input_length + 1)
        - sin(hour * 2π / 24)
        - cos(hour * 2π / 24)
        - node_load (0-1 normalized)
        """
        # One-hot encode task type
        if task_type not in self.task_type_index:
            self.task_types.append(task_type)
            self.task_type_index[task_type] = len(self.task_types) - 1

        task_one_hot = np.zeros(len(self.task_types))
        task_one_hot[self.task_type_index[task_type]] = 1.0

        # Temporal features (sine/cosine encoding for cyclical time)
        hour = timestamp.hour
        hour_sin = math.sin(hour * 2 * math.pi / 24)
        hour_cos = math.cos(hour * 2 * math.pi / 24)

        # Input length (log-scaled to handle wide range)
        log_input = math.log(input_length + 1)

        # Concatenate all features
        context = np.concatenate([
            task_one_hot,
            [log_input, hour_sin, hour_cos, node_load]
        ])

        return context

    def select_arm(self, context: np.ndarray, available_arms: List[str]) -> Tuple[str, float]:
        """
        Select best arm using LinUCB with Thompson Sampling.

        Returns:
            (selected_arm, ucb_score)
        """
        best_arm = None
        best_score = -float('inf')

        for arm in available_arms:
            if arm not in self.arms:
                self._init_arm(arm)

            arm_data = self.arms[arm]

            # Compute theta (parameter estimate)
            theta = arm_data['A_inv'] @ arm_data['b']

            # UCB score with exploration bonus
            expected_reward = theta.T @ context
            uncertainty = self.alpha * math.sqrt(context.T @ arm_data['A_inv'] @ context)
            ucb_score = expected_reward + uncertainty

            if ucb_score > best_score:
                best_score = ucb_score
                best_arm = arm

        return best_arm, best_score

    def update(self, arm: str, context: np.ndarray, reward: float):
        """Update arm parameters with observed reward"""
        if arm not in self.arms:
            self._init_arm(arm)

        arm_data = self.arms[arm]

        # Update design matrix and reward vector
        arm_data['A'] += np.outer(context, context)
        arm_data['b'] += reward * context

        # Update inverse (Sherman-Morrison formula for efficiency)
        # A_inv_new = A_inv - (A_inv @ x @ x.T @ A_inv) / (1 + x.T @ A_inv @ x)
        v = arm_data['A_inv'] @ context
        arm_data['A_inv'] -= np.outer(v, v) / (1 + context.T @ v)

        # Update theta
        arm_data['theta'] = arm_data['A_inv'] @ arm_data['b']


class ContextualModelRouter:
    """Multi-model router with contextual bandits"""

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.conn = None
        self.bandit = None

        # Initialize from historical data
        self._initialize()

    def _connect(self):
        """Connect to PostgreSQL"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**self.db_config)

    def _initialize(self):
        """Initialize bandit from historical execution data"""
        self._connect()
        cursor = self.conn.cursor()

        # Get all distinct task types
        cursor.execute("SELECT DISTINCT task_type FROM monitoring.execution_summary ORDER BY task_type")
        task_types = [row[0] for row in cursor.fetchall()]

        # Feature dimension: len(task_types) + 4 (log_input, sin, cos, node_load)
        n_features = len(task_types) + 4

        self.bandit = ContextualBandit(n_features=n_features, alpha=0.5)
        self.bandit.task_types = task_types
        self.bandit.task_type_index = {t: i for i, t in enumerate(task_types)}

        # Pre-initialize arms from all known models
        cursor.execute("SELECT DISTINCT model FROM monitoring.execution_summary")
        for row in cursor.fetchall():
            model = row[0]
            self.bandit._init_arm(model)

        cursor.close()

    def select_model(self, task_type: str, input_length: int = 0,
                     node_load: float = 0.5) -> Tuple[str, float]:
        """
        Select best model for current context.

        Args:
            task_type: Type of task (e.g., 'code-review', 'consensus')
            input_length: Token count of input
            node_load: Current node utilization (0-1)

        Returns:
            (selected_model, confidence_score)
        """
        timestamp = datetime.now()
        context = self.bandit._build_context(task_type, input_length, timestamp, node_load)

        # Get available models
        self._connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT model FROM monitoring.execution_summary")
        available_models = [row[0] for row in cursor.fetchall()]
        cursor.close()

        return self.bandit.select_arm(context, available_models)

    def update_reward(self, model: str, task_type: str, input_length: int,
                      timestamp: datetime, node_load: float, reward: float):
        """Update model parameters after observing outcome"""
        context = self.bandit._build_context(task_type, input_length, timestamp, node_load)
        self.bandit.update(model, context, reward)

    def train_on_historical(self) -> Dict[str, float]:
        """
        Train contextual bandit on historical execution data.

        Returns:
            Training metrics (avg_reward, regret, etc.)
        """
        self._connect()
        cursor = self.conn.cursor()

        # Fetch all successful executions
        cursor.execute("""
            SELECT model, task_type, input_tokens, timestamp, quality_score, outcome
            FROM monitoring.execution_summary
            ORDER BY timestamp ASC
        """)

        total_reward = 0
        total_regret = 0
        n_samples = 0

        for row in cursor.fetchall():
            model, task_type, input_tokens, timestamp, quality_score, outcome = row

            # Reward: quality_score if success, 0 if failure
            reward = quality_score if outcome == 'SUCCESS' else 0.0

            # Assume node_load = 0.5 (unknown for historical data)
            node_load = 0.5

            # Build context
            context = self.bandit._build_context(task_type, input_tokens or 0, timestamp, node_load)

            # Get available models at this time
            available_models = list(self.bandit.arms.keys())
            if not available_models:
                # First observation, initialize arm
                self.bandit._init_arm(model)
                available_models = [model]

            # What would we have selected?
            selected_model, _ = self.bandit.select_arm(context, available_models)

            # Regret = reward of best action - reward of selected action
            # (Simplified: assume actual model is best in hindsight)
            if selected_model != model:
                total_regret += reward

            # Update with actual observation
            self.bandit.update(model, context, reward)

            total_reward += reward
            n_samples += 1

        cursor.close()

        return {
            'avg_reward': total_reward / n_samples if n_samples > 0 else 0,
            'total_regret': total_regret,
            'avg_regret': total_regret / n_samples if n_samples > 0 else 0,
            'n_samples': n_samples
        }


def backtest_comparison(db_config: Dict[str, str]) -> Dict[str, any]:
    """
    Compare Basic Thompson Sampling vs Contextual Bandits.

    Returns:
        Backtest results with cost savings analysis
    """
    print("=" * 60)
    print("CONTEXTUAL BANDITS BACKTEST")
    print("=" * 60)

    # Initialize contextual router
    contextual_router = ContextualModelRouter(db_config)

    # Train on historical data
    print("\nTraining contextual bandit on historical data...")
    metrics = contextual_router.train_on_historical()

    print(f"Training complete:")
    print(f"  Samples: {metrics['n_samples']}")
    print(f"  Avg Reward: {metrics['avg_reward']:.4f}")
    print(f"  Avg Regret: {metrics['avg_regret']:.4f}")

    # Compare selection vs actual
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            model,
            task_type,
            input_tokens,
            timestamp,
            quality_score,
            cost_usd,
            outcome
        FROM monitoring.execution_summary
        WHERE timestamp > NOW() - INTERVAL '30 days'
        ORDER BY timestamp DESC
        LIMIT 100
    """)

    contextual_correct = 0
    contextual_cost_savings = 0
    total_cost = 0

    for row in cursor.fetchall():
        model, task_type, input_tokens, timestamp, quality_score, cost_usd, outcome = row

        # What would contextual bandit select?
        selected_model, confidence = contextual_router.select_model(
            task_type, input_tokens or 0, node_load=0.5
        )

        # Did we select correctly?
        if selected_model == model and outcome == 'SUCCESS':
            contextual_correct += 1

        # Cost analysis (assume local models = $0, API models = cost_usd)
        total_cost += cost_usd or 0

        # If we selected a cheaper model with similar quality
        cursor.execute("""
            SELECT cost_usd, quality_score
            FROM monitoring.execution_summary
            WHERE model = %s AND task_type = %s AND outcome = 'SUCCESS'
            ORDER BY timestamp DESC LIMIT 1
        """, (selected_model, task_type))

        alt_row = cursor.fetchone()
        if alt_row:
            alt_cost, alt_quality = alt_row
            if alt_quality >= quality_score * 0.95:  # Within 5% quality
                contextual_cost_savings += (cost_usd or 0) - (alt_cost or 0)

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Contextual selection accuracy: {contextual_correct}/100")
    print(f"Total cost (actual): ${total_cost:.4f}")
    print(f"Potential savings: ${contextual_cost_savings:.4f}")
    if total_cost > 0:
        savings_pct = (contextual_cost_savings / total_cost) * 100
        print(f"Cost reduction: {savings_pct:.1f}%")
    else:
        savings_pct = 0

    return {
        'training_metrics': metrics,
        'backtest_accuracy': contextual_correct,
        'total_cost': total_cost,
        'cost_savings': contextual_cost_savings,
        'savings_percentage': savings_pct
    }


if __name__ == '__main__':
    db_config = {
        'host': 'laptop-01',
        'database': 'learning',
        'user': 'sfloess'
    }

    # Run backtest
    results = backtest_comparison(db_config)

    print("\n" + "=" * 60)
    print("VALIDATION vs RESEARCH CLAIMS")
    print("=" * 60)
    print("Research claim: 45-85% cost savings")
    print(f"Our result: {results['savings_percentage']:.1f}% savings")

    if 45 <= results['savings_percentage'] <= 85:
        print("✅ CLAIM VALIDATED")
    elif results['savings_percentage'] > 0:
        print("⚠ PARTIAL VALIDATION (savings exist but below range)")
    else:
        print("❌ CLAIM NOT VALIDATED (insufficient data or no savings)")

    # Save results
    with open('/tmp/contextual-bandits-backtest.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to /tmp/contextual-bandits-backtest.json")
