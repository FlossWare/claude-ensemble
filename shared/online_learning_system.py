#!/usr/bin/env python3
"""
Online Learning System - Continuous model updates from streaming workflow data

Implements:
1. Online Gradient Descent - Incremental model updates
2. Hedge Algorithm - Exponential weights for expert selection
3. Follow-the-Regularized-Leader (FTRL) - Online convex optimization
4. Online Passive-Aggressive - Margin-based updates
5. Continual Learning - Experience replay to prevent forgetting

Integrates with PostgreSQL workflow.* tables for real-time feedback.

Usage:
    from online_learning_system import OnlineLearningOrchestrator

    orchestrator = OnlineLearningOrchestrator()

    # Subscribe to workflow feedback stream
    orchestrator.start_learning_loop()

    # Get best model for task
    model = orchestrator.select_model(task_context)

    # Update based on outcome
    orchestrator.update(model, task_context, reward, outcome_data)
"""

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pickle
import sys
from collections import deque
import hashlib

# Add learning directory to path
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))
# Note: Import only what's needed from Python adapter
# (Workflows learning is in JS adapter only)


class OnlineLinearModel:
    """
    Online linear model with multiple update strategies.

    Supports:
    - OGD (Online Gradient Descent)
    - FTRL (Follow-the-Regularized-Leader)
    - PA (Passive-Aggressive)
    """

    def __init__(self, dim: int, learning_rate: float = 0.01, update_method: str = 'ogd'):
        self.dim = dim
        self.learning_rate = learning_rate
        self.update_method = update_method

        # Model parameters
        self.weights = np.zeros(dim)
        self.bias = 0.0

        # FTRL-specific parameters
        if update_method == 'ftrl':
            self.z = np.zeros(dim)  # Accumulator
            self.n = np.zeros(dim)  # Per-coordinate learning rates
            self.alpha = 0.1
            self.beta = 1.0
            self.lambda1 = 0.0  # L1 regularization
            self.lambda2 = 1.0  # L2 regularization

        # Statistics
        self.num_updates = 0
        self.cumulative_loss = 0.0

    def predict(self, context: np.ndarray) -> float:
        """Predict reward given context."""
        return np.dot(self.weights, context) + self.bias

    def update_ogd(self, context: np.ndarray, true_reward: float):
        """Online Gradient Descent update."""
        pred_reward = self.predict(context)
        error = pred_reward - true_reward

        # Gradient descent step
        self.weights -= self.learning_rate * error * context
        self.bias -= self.learning_rate * error

        # Track loss
        loss = 0.5 * error ** 2
        self.cumulative_loss += loss

        return loss

    def update_ftrl(self, context: np.ndarray, true_reward: float):
        """Follow-the-Regularized-Leader update."""
        pred_reward = self.predict(context)
        gradient = (pred_reward - true_reward) * context

        # Update accumulators
        self.n += gradient ** 2
        self.z += gradient - (np.sqrt(self.n + gradient ** 2) - np.sqrt(self.n)) * self.weights / self.alpha

        # Update weights using FTRL formula
        for i in range(self.dim):
            if abs(self.z[i]) <= self.lambda1:
                self.weights[i] = 0
            else:
                sign_zi = np.sign(self.z[i])
                self.weights[i] = -(self.z[i] - sign_zi * self.lambda1) / (
                    (self.beta + np.sqrt(self.n[i])) / self.alpha + self.lambda2
                )

        loss = 0.5 * (pred_reward - true_reward) ** 2
        self.cumulative_loss += loss
        return loss

    def update_pa(self, context: np.ndarray, true_reward: float, C: float = 1.0):
        """Passive-Aggressive update."""
        pred_reward = self.predict(context)
        loss = max(0, abs(pred_reward - true_reward) - 0.1)  # Epsilon-insensitive loss

        if loss > 0:
            # Calculate step size
            tau = loss / (np.dot(context, context) + 1e-8)
            tau = min(C, tau)  # Clip to C (PA-I variant)

            # Update weights
            sign = np.sign(true_reward - pred_reward)
            self.weights += sign * tau * context

        self.cumulative_loss += loss
        return loss

    def update(self, context: np.ndarray, true_reward: float) -> float:
        """Update model based on configured method."""
        context = np.array(context)

        if self.update_method == 'ogd':
            loss = self.update_ogd(context, true_reward)
        elif self.update_method == 'ftrl':
            loss = self.update_ftrl(context, true_reward)
        elif self.update_method == 'pa':
            loss = self.update_pa(context, true_reward)
        else:
            raise ValueError(f"Unknown update method: {self.update_method}")

        self.num_updates += 1
        return loss

    def get_average_loss(self) -> float:
        """Get average loss over all updates."""
        return self.cumulative_loss / max(1, self.num_updates)


class HedgeAlgorithm:
    """
    Hedge algorithm for expert selection with exponential weights.

    Classic online learning algorithm that maintains a probability distribution
    over experts and updates based on observed losses.
    """

    def __init__(self, num_experts: int, learning_rate: float = 0.1):
        self.num_experts = num_experts
        self.learning_rate = learning_rate

        # Initialize uniform weights
        self.weights = np.ones(num_experts) / num_experts
        self.cumulative_losses = np.zeros(num_experts)
        self.num_selections = np.zeros(num_experts)

    def select_expert(self, deterministic: bool = False) -> int:
        """Select expert according to current probability distribution."""
        if deterministic:
            return int(np.argmax(self.weights))
        else:
            return np.random.choice(self.num_experts, p=self.weights)

    def update(self, expert_id: int, loss: float):
        """Update weights based on expert's loss."""
        self.cumulative_losses[expert_id] += loss
        self.num_selections[expert_id] += 1

        # Exponential update
        self.weights = np.exp(-self.learning_rate * self.cumulative_losses)

        # Normalize to probability distribution
        self.weights /= self.weights.sum()

    def get_best_expert(self) -> Tuple[int, float]:
        """Get expert with lowest average loss."""
        avg_losses = np.where(
            self.num_selections > 0,
            self.cumulative_losses / self.num_selections,
            np.inf
        )
        best_idx = int(np.argmin(avg_losses))
        return best_idx, avg_losses[best_idx]


class ExperienceReplay:
    """
    Experience replay buffer for continual learning.

    Stores past experiences and replays them to prevent catastrophic forgetting.
    """

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)

    def add(self, context: np.ndarray, reward: float, metadata: Dict = None):
        """Add experience to buffer."""
        self.buffer.append({
            'context': context.copy(),
            'reward': reward,
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat()
        })

    def sample(self, batch_size: int) -> List[Dict]:
        """Sample random batch from buffer."""
        if len(self.buffer) == 0:
            return []

        batch_size = min(batch_size, len(self.buffer))
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)

        return [self.buffer[i] for i in indices]

    def get_all(self) -> List[Dict]:
        """Get all experiences."""
        return list(self.buffer)

    def clear(self):
        """Clear all experiences."""
        self.buffer.clear()


class OnlineLearningOrchestrator:
    """
    Main orchestrator for online learning system.

    Integrates:
    - Online linear models (per model)
    - Hedge algorithm (model selection)
    - Experience replay (continual learning)
    - PostgreSQL integration (workflow feedback)
    """

    def __init__(
        self,
        context_dim: int = 20,
        learning_rate: float = 0.01,
        update_method: str = 'ftrl',
        replay_capacity: int = 1000,
        replay_frequency: int = 10,
        db_connection: Optional[Any] = None
    ):
        self.context_dim = context_dim
        self.learning_rate = learning_rate
        self.update_method = update_method
        self.replay_frequency = replay_frequency

        # Database connection
        self.db = db_connection or self._get_db()

        # Get available models from PostgreSQL
        self.models = self._load_available_models()
        self.model_to_id = {model: i for i, model in enumerate(self.models)}
        self.num_models = len(self.models)

        print(f"Initialized with {self.num_models} models: {self.models[:5]}...")

        # One linear model per available model
        self.learners = {
            model: OnlineLinearModel(context_dim, learning_rate, update_method)
            for model in self.models
        }

        # Hedge algorithm for model selection
        self.hedge = HedgeAlgorithm(self.num_models, learning_rate=0.05)

        # Experience replay
        self.replay_buffer = ExperienceReplay(capacity=replay_capacity)

        # Statistics
        self.total_updates = 0
        self.last_replay_update = 0

    def _get_db(self):
        """Get database connection."""
        return psycopg2.connect(
            host='aio-01',
            port=5433,
            user='sfloess',
            database='learning',
            cursor_factory=RealDictCursor
        )

    def _load_available_models(self) -> List[str]:
        """Load list of available models from PostgreSQL."""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT DISTINCT model
            FROM workflow.worker_results
            WHERE model IS NOT NULL
            ORDER BY model
        """)
        models = [row['model'] for row in cursor.fetchall()]

        if len(models) == 0:
            # Fallback to default models if no data yet
            models = ['opus', 'sonnet', 'haiku', 'fable', 'gpt4o', 'gemini']

        return models

    def extract_context(self, task_description: str, metadata: Dict = None) -> np.ndarray:
        """
        Extract context features from task.

        Features (20-dim):
        - Task type indicators (10 dims): code, debug, research, write, review, test, deploy, design, optimize, other
        - Complexity indicators (5 dims): length, technical terms, uncertainty markers, dependencies, constraints
        - Metadata features (5 dims): workflow type, phase, priority, time constraints, resource constraints
        """
        metadata = metadata or {}
        task_lower = task_description.lower() if task_description else ""

        context = np.zeros(self.context_dim)

        # Task type features (dims 0-9)
        task_types = [
            'code', 'debug', 'research', 'write', 'review',
            'test', 'deploy', 'design', 'optimize', 'analyze'
        ]
        for i, task_type in enumerate(task_types):
            if task_type in task_lower:
                context[i] = 1.0

        # Complexity features (dims 10-14)
        context[10] = min(1.0, len(task_description) / 1000)  # Length

        technical_terms = ['api', 'class', 'function', 'database', 'algorithm', 'optimization', 'performance']
        context[11] = min(1.0, sum(1 for term in technical_terms if term in task_lower) / 5)

        uncertainty_markers = ['maybe', 'unclear', 'not sure', 'investigate', 'explore']
        context[12] = min(1.0, sum(1 for marker in uncertainty_markers if marker in task_lower) / 3)

        context[13] = 1.0 if 'depend' in task_lower or 'require' in task_lower else 0.0
        context[14] = 1.0 if 'constraint' in task_lower or 'limit' in task_lower else 0.0

        # Metadata features (dims 15-19)
        if metadata:
            workflow_types = ['deep-research', 'code-generation', 'debugging', 'testing', 'deployment']
            workflow = metadata.get('workflow', '')
            for i, wf_type in enumerate(workflow_types):
                if wf_type in workflow.lower():
                    context[15] = i / len(workflow_types)
                    break

            context[16] = metadata.get('phase_progress', 0.0)  # How far into workflow
            context[17] = metadata.get('priority', 0.5)  # Task priority
            context[18] = metadata.get('time_constraint', 0.0)  # Time pressure
            context[19] = metadata.get('resource_constraint', 0.0)  # Resource limits

        return context

    def select_model(self, task_description: str, metadata: Dict = None, explore: bool = True) -> str:
        """
        Select best model for task using online learning.

        Args:
            task_description: Task description text
            metadata: Additional task metadata
            explore: Whether to explore (use Hedge) or exploit (use best model)

        Returns:
            Model name to use
        """
        context = self.extract_context(task_description, metadata)

        if explore:
            # Use Hedge algorithm for exploration/exploitation
            model_id = self.hedge.select_expert(deterministic=False)
            selected_model = self.models[model_id]
        else:
            # Exploit: use model with best predicted reward
            predictions = {
                model: learner.predict(context)
                for model, learner in self.learners.items()
            }
            selected_model = max(predictions, key=predictions.get)

        return selected_model

    def update(
        self,
        model: str,
        task_description: str,
        reward: float,
        metadata: Dict = None
    ):
        """
        Update online models based on observed reward.

        Args:
            model: Model that was used
            task_description: Task description
            reward: Observed reward (0.0 to 1.0)
            metadata: Additional metadata
        """
        if model not in self.learners:
            print(f"Warning: Unknown model {model}, skipping update")
            return

        context = self.extract_context(task_description, metadata)

        # Update model's learner
        loss = self.learners[model].update(context, reward)

        # Update Hedge weights
        model_id = self.model_to_id[model]
        self.hedge.update(model_id, 1.0 - reward)  # Hedge uses loss, not reward

        # Add to experience replay
        self.replay_buffer.add(context, reward, metadata={
            'model': model,
            'task': task_description[:200],
            **(metadata or {})
        })

        self.total_updates += 1

        # Periodic replay for continual learning
        if self.total_updates - self.last_replay_update >= self.replay_frequency:
            self._replay_experiences()
            self.last_replay_update = self.total_updates

        return loss

    def _replay_experiences(self, batch_size: int = 10):
        """Replay past experiences to prevent catastrophic forgetting."""
        batch = self.replay_buffer.sample(batch_size)

        for exp in batch:
            context = exp['context']
            reward = exp['reward']
            model = exp['metadata'].get('model')

            if model and model in self.learners:
                # Re-train on past experience
                self.learners[model].update(context, reward)

    def get_model_rankings(self) -> List[Tuple[str, float]]:
        """Get models ranked by average predicted reward."""
        # Use zero context for baseline ranking
        baseline_context = np.zeros(self.context_dim)

        rankings = []
        for model, learner in self.learners.items():
            avg_pred = learner.predict(baseline_context)
            rankings.append((model, avg_pred))

        return sorted(rankings, key=lambda x: x[1], reverse=True)

    def get_statistics(self) -> Dict:
        """Get learning statistics."""
        best_expert, best_loss = self.hedge.get_best_expert()

        return {
            'total_updates': self.total_updates,
            'num_models': self.num_models,
            'replay_buffer_size': len(self.replay_buffer.buffer),
            'best_model': self.models[best_expert],
            'best_model_loss': float(best_loss),
            'hedge_weights': {
                model: float(weight)
                for model, weight in zip(self.models, self.hedge.weights)
            },
            'model_update_counts': {
                model: learner.num_updates
                for model, learner in self.learners.items()
            },
            'model_avg_losses': {
                model: learner.get_average_loss()
                for model, learner in self.learners.items()
            }
        }

    def save(self, directory: str = None):
        """Save online learning state."""
        if directory is None:
            directory = str(Path.home() / '.claude' / 'learning')

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        state = {
            'context_dim': self.context_dim,
            'learning_rate': self.learning_rate,
            'update_method': self.update_method,
            'models': self.models,
            'model_to_id': self.model_to_id,
            'total_updates': self.total_updates,
            'last_replay_update': self.last_replay_update,
            'learners': {
                model: {
                    'weights': learner.weights.tolist(),
                    'bias': float(learner.bias),
                    'num_updates': learner.num_updates,
                    'cumulative_loss': learner.cumulative_loss
                }
                for model, learner in self.learners.items()
            },
            'hedge': {
                'weights': self.hedge.weights.tolist(),
                'cumulative_losses': self.hedge.cumulative_losses.tolist(),
                'num_selections': self.hedge.num_selections.tolist()
            },
            'replay_buffer': [
                {
                    'context': exp['context'].tolist(),
                    'reward': exp['reward'],
                    'metadata': exp['metadata'],
                    'timestamp': exp['timestamp']
                }
                for exp in self.replay_buffer.get_all()
            ]
        }

        filepath = directory / 'online_learning_state.json'
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)

        print(f"Online learning state saved to {filepath}")
        return filepath

    @classmethod
    def load(cls, filepath: str = None, db_connection=None):
        """Load online learning state from disk."""
        if filepath is None:
            filepath = str(Path.home() / '.claude' / 'learning' / 'online_learning_state.json')

        filepath = Path(filepath)

        if not filepath.exists():
            print(f"No saved state at {filepath}, creating new orchestrator")
            return cls(db_connection=db_connection)

        with open(filepath, 'r') as f:
            state = json.load(f)

        # Create new orchestrator
        orchestrator = cls(
            context_dim=state['context_dim'],
            learning_rate=state['learning_rate'],
            update_method=state['update_method'],
            db_connection=db_connection
        )

        # Restore state
        orchestrator.models = state['models']
        orchestrator.model_to_id = {k: int(v) for k, v in state['model_to_id'].items()}
        orchestrator.total_updates = state['total_updates']
        orchestrator.last_replay_update = state['last_replay_update']

        # Restore learners
        for model, learner_state in state['learners'].items():
            if model in orchestrator.learners:
                learner = orchestrator.learners[model]
                learner.weights = np.array(learner_state['weights'])
                learner.bias = learner_state['bias']
                learner.num_updates = learner_state['num_updates']
                learner.cumulative_loss = learner_state['cumulative_loss']

        # Restore hedge
        orchestrator.hedge.weights = np.array(state['hedge']['weights'])
        orchestrator.hedge.cumulative_losses = np.array(state['hedge']['cumulative_losses'])
        orchestrator.hedge.num_selections = np.array(state['hedge']['num_selections'])

        # Restore replay buffer
        for exp_data in state['replay_buffer']:
            orchestrator.replay_buffer.add(
                np.array(exp_data['context']),
                exp_data['reward'],
                exp_data['metadata']
            )

        print(f"Online learning state loaded from {filepath}")
        return orchestrator


def demo():
    """Demonstration of online learning system."""
    print("=== Online Learning System Demo ===\n")

    # Create orchestrator
    orchestrator = OnlineLearningOrchestrator()

    # Simulate workflow tasks
    tasks = [
        ("Debug authentication bug in Java service", {'workflow': 'debugging', 'priority': 0.9}),
        ("Research firmware reverse engineering methods", {'workflow': 'deep-research', 'priority': 0.7}),
        ("Write unit tests for API endpoints", {'workflow': 'testing', 'priority': 0.6}),
        ("Optimize database query performance", {'workflow': 'optimization', 'priority': 0.8}),
        ("Code review pull request #123", {'workflow': 'code-review', 'priority': 0.5}),
    ]

    print("Training on simulated tasks...\n")

    for iteration in range(3):
        print(f"--- Iteration {iteration + 1} ---")

        for task_desc, metadata in tasks:
            # Select model
            selected_model = orchestrator.select_model(task_desc, metadata, explore=True)

            # Simulate reward (in reality, comes from workflow outcome)
            base_reward = np.random.uniform(0.6, 0.95)

            # Some models are better at certain tasks
            if 'debug' in task_desc.lower() and selected_model in ['opus', 'sonnet']:
                reward = min(1.0, base_reward + 0.1)
            elif 'research' in task_desc.lower() and selected_model in ['gpt4o', 'gemini']:
                reward = min(1.0, base_reward + 0.1)
            else:
                reward = base_reward

            # Update online learner
            loss = orchestrator.update(selected_model, task_desc, reward, metadata)

            print(f"  {task_desc[:50]:50s} -> {selected_model:10s} (reward: {reward:.3f}, loss: {loss:.4f})")

        print()

    # Show statistics
    print("=== Learning Statistics ===")
    stats = orchestrator.get_statistics()

    print(f"Total updates: {stats['total_updates']}")
    print(f"Best model: {stats['best_model']} (loss: {stats['best_model_loss']:.4f})")
    print(f"Replay buffer: {stats['replay_buffer_size']} experiences")
    print()

    print("Model rankings (by predicted reward):")
    for rank, (model, pred_reward) in enumerate(orchestrator.get_model_rankings()[:5], 1):
        print(f"  {rank}. {model:10s} - {pred_reward:.4f}")
    print()

    print("Hedge weights (exploration distribution):")
    for model, weight in list(stats['hedge_weights'].items())[:5]:
        print(f"  {model:10s}: {weight:.4f}")
    print()

    # Save state
    save_path = orchestrator.save()

    # Test load
    loaded = OnlineLearningOrchestrator.load(str(save_path))
    print(f"Successfully loaded orchestrator with {loaded.total_updates} updates")

    return {
        'model_saved': save_path.exists(),
        'total_updates': stats['total_updates'],
        'best_model': stats['best_model']
    }


if __name__ == '__main__':
    result = demo()
    print("\n=== Final Result ===")
    print(json.dumps(result, indent=2))
