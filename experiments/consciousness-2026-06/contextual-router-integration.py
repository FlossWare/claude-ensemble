#!/usr/bin/env python3
"""
Production Integration: Contextual Bandit Router

Drop-in replacement for multi-model-router.py with contextual awareness.
"""

import psycopg2
import numpy as np
from datetime import datetime
import math
from typing import Dict, List, Tuple, Optional
import os

# Cost model (dollars per 1M tokens)
COST_MODEL = {
    'sonnet': {'input': 3.0, 'output': 15.0},
    'haiku': {'input': 0.25, 'output': 1.25},
    'opus': {'input': 15.0, 'output': 75.0},
    'gpt-4o': {'input': 2.5, 'output': 10.0},
    'gemini-pro': {'input': 0.5, 'output': 1.5},
    'phi3.5': {'input': 0.0, 'output': 0.0},  # fable→phi3.5 (Ollama, free local)
    # Local models (free)
    'gemma2:2b': {'input': 0.0, 'output': 0.0},
    'phi3.5:latest': {'input': 0.0, 'output': 0.0},
    'qwen2.5:7b': {'input': 0.0, 'output': 0.0},
    'mistral-7b-instruct': {'input': 0.0, 'output': 0.0},
    'llama3:8b': {'input': 0.0, 'output': 0.0},
    'deepseek-coder-v2-lite': {'input': 0.0, 'output': 0.0}
}


class ContextualBandit:
    """LinUCB implementation"""

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
            'A_inv': np.identity(d),
            'n_obs': 0
        }

    def _build_context(self, task_type: str, input_length: int,
                       timestamp: datetime, node_load: float = 0.5) -> np.ndarray:
        if task_type not in self.task_type_index:
            if len(self.task_types) < 30:
                self.task_types.append(task_type)
                self.task_type_index[task_type] = len(self.task_types) - 1

        task_one_hot = np.zeros(30)
        if task_type in self.task_type_index:
            task_one_hot[self.task_type_index[task_type]] = 1.0

        hour = timestamp.hour
        hour_sin = math.sin(hour * 2 * math.pi / 24)
        hour_cos = math.cos(hour * 2 * math.pi / 24)
        log_input = math.log(max(input_length, 1))

        return np.concatenate([task_one_hot, [log_input, hour_sin, hour_cos, node_load]])

    def select_arm(self, context: np.ndarray, available_arms: List[str]) -> str:
        best_arm = None
        best_score = -float('inf')

        for arm in available_arms:
            if arm not in self.arms:
                self._init_arm(arm)

            arm_data = self.arms[arm]
            theta = arm_data['A_inv'] @ arm_data['b']

            expected_reward = theta.T @ context
            uncertainty = self.alpha * math.sqrt(max(context.T @ arm_data['A_inv'] @ context, 0))
            ucb_score = expected_reward + uncertainty

            if ucb_score > best_score:
                best_score = ucb_score
                best_arm = arm

        return best_arm

    def update(self, arm: str, context: np.ndarray, reward: float):
        if arm not in self.arms:
            self._init_arm(arm)

        arm_data = self.arms[arm]
        arm_data['A'] += np.outer(context, context)
        arm_data['b'] += reward * context

        v = arm_data['A_inv'] @ context
        denom = 1 + context.T @ v
        if abs(denom) > 1e-10:
            arm_data['A_inv'] -= np.outer(v, v) / denom

        arm_data['theta'] = arm_data['A_inv'] @ arm_data['b']
        arm_data['n_obs'] += 1


class ContextualModelRouter:
    """Drop-in replacement for MultiModelRouter with contextual awareness"""

    def __init__(self, db_host: str = 'laptop-01', db_name: str = 'learning',
                 db_user: str = 'sfloess', cost_weight: float = 0.3):
        self.db_config = {'host': db_host, 'database': db_name, 'user': db_user}
        self.cost_weight = cost_weight
        self.bandit = None
        self.available_models = []
        self._initialize()

    def _initialize(self):
        """Initialize from historical data"""
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()

        # Get task types
        cursor.execute("SELECT DISTINCT task_type FROM monitoring.execution_summary ORDER BY task_type")
        task_types = [row[0] for row in cursor.fetchall()]

        # Initialize bandit
        self.bandit = ContextualBandit(n_features=34, alpha=1.0)
        self.bandit.task_types = task_types[:30]
        self.bandit.task_type_index = {t: i for i, t in enumerate(self.bandit.task_types)}

        # Get available models
        cursor.execute("SELECT DISTINCT model FROM monitoring.execution_summary")
        self.available_models = [row[0] for row in cursor.fetchall()]

        for model in self.available_models:
            self.bandit._init_arm(model)

        # Train on historical successful executions
        cursor.execute("""
            SELECT
                model, task_type, input_tokens, output_tokens,
                timestamp, quality_score, cost_usd
            FROM monitoring.execution_summary
            WHERE UPPER(outcome) = 'SUCCESS' AND quality_score > 0
            ORDER BY timestamp ASC
        """)

        for row in cursor.fetchall():
            model, task_type, input_tokens, output_tokens, timestamp, quality_score, cost_usd = row

            # Estimate cost
            if cost_usd is None or cost_usd == 0:
                pricing = COST_MODEL.get(model, {'input': 0, 'output': 0})
                cost_usd = ((input_tokens or 0) * pricing['input'] +
                           (output_tokens or 0) * pricing['output']) / 1_000_000

            # Reward: quality - cost_penalty
            cost_penalty = min(cost_usd / 0.01, 1.0)
            reward = quality_score - self.cost_weight * cost_penalty

            context = self.bandit._build_context(task_type, input_tokens or 0, timestamp, 0.5)
            self.bandit.update(model, context, reward)

        cursor.close()
        conn.close()

    def route(self, task_type: str, input_tokens: int = 0,
              budget_constraint: Optional[str] = None,
              node_load: float = 0.5) -> str:
        """
        Select best model for task.

        Args:
            task_type: Task category (e.g., 'code-review', 'consensus')
            input_tokens: Input token count
            budget_constraint: Optional constraint ('free', 'low-cost', None)
            node_load: Current node utilization (0-1)

        Returns:
            Selected model name
        """
        timestamp = datetime.now()
        context = self.bandit._build_context(task_type, input_tokens, timestamp, node_load)

        # Filter by budget constraint
        if budget_constraint == 'free':
            available = [m for m in self.available_models
                        if COST_MODEL.get(m, {'input': 0})['input'] == 0]
        elif budget_constraint == 'low-cost':
            available = [m for m in self.available_models
                        if COST_MODEL.get(m, {'input': 1000})['input'] < 1.0]
        else:
            available = self.available_models

        if not available:
            available = self.available_models  # Fallback

        return self.bandit.select_arm(context, available)

    def update_reward(self, model: str, task_type: str, input_tokens: int,
                      quality_score: float, cost_usd: float,
                      timestamp: Optional[datetime] = None):
        """Update bandit after observing outcome"""
        if timestamp is None:
            timestamp = datetime.now()

        cost_penalty = min(cost_usd / 0.01, 1.0)
        reward = quality_score - self.cost_weight * cost_penalty

        context = self.bandit._build_context(task_type, input_tokens, timestamp, 0.5)
        self.bandit.update(model, context, reward)

    def fallback_chain(self) -> List[str]:
        """Define fallback order (compatibility with old API)"""
        return ['sonnet', 'haiku', 'gemma2:2b']


# Backward compatibility
class MultiModelRouter(ContextualModelRouter):
    """Alias for backward compatibility"""
    pass


if __name__ == '__main__':
    # Example usage
    router = ContextualModelRouter()

    # Select model for task
    model = router.route(task_type='code-review', input_tokens=500, budget_constraint=None)
    print(f"✅ Selected model: {model}")

    # Simulate execution and update
    router.update_reward(
        model=model,
        task_type='code-review',
        input_tokens=500,
        quality_score=0.92,
        cost_usd=0.005
    )

    print("✅ Contextual bandit updated with feedback")
