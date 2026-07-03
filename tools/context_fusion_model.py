#!/usr/bin/env python3
"""
Context Fusion Model for Multi-Source Context Integration

Fuses multiple context sources to create rich contextual representations:
1. Session history and patterns
2. Task type and complexity
3. User preferences and communication style
4. Temporal patterns (time of day, recency)
5. Resource availability (fleet health, costs)

Uses attention-weighted fusion to combine contexts, then feeds to
contextual bandit for improved model selection.
"""

import numpy as np
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pickle
import math


class ContextFusionModel:
    """Multi-source context fusion with attention weighting"""

    def __init__(self, embedding_dim: int = 128):
        """
        Args:
            embedding_dim: Dimension for all context embeddings
        """
        self.embedding_dim = embedding_dim

        # Learned attention weights for each context source
        self.attention_weights = {
            'session': 0.25,      # Session history patterns
            'task': 0.30,         # Task type and complexity
            'user': 0.20,         # User preferences
            'temporal': 0.15,     # Time-based patterns
            'resource': 0.10      # Fleet health and costs
        }

        # Embedding matrices for each context type (learned)
        self.embeddings = {
            'task_types': {},
            'user_patterns': {},
            'temporal_slots': {},
            'workflow_patterns': {}
        }

        # Training history
        self.training_history = []

        # Load session context if available
        self.session_context = self._load_session_context()

    def _load_session_context(self) -> Dict:
        """Load pre-computed session context"""
        context_path = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/session_context.json'
        if context_path.exists():
            with open(context_path) as f:
                return json.load(f)
        return {}

    def _encode_task_context(self, task_type: str, complexity: float = 0.5) -> np.ndarray:
        """
        Encode task type and complexity into embedding.

        Args:
            task_type: Type of task (code_review, debugging, etc.)
            complexity: Estimated complexity [0, 1]

        Returns:
            Task context embedding
        """
        # If we've seen this task type before, use learned embedding
        if task_type in self.embeddings['task_types']:
            base_emb = self.embeddings['task_types'][task_type]
        else:
            # Initialize with random embedding (will be learned)
            base_emb = np.random.randn(self.embedding_dim - 1) * 0.1
            self.embeddings['task_types'][task_type] = base_emb

        # Append complexity as additional feature
        return np.concatenate([base_emb, [complexity]])

    def _encode_session_context(self, session_id: str = None) -> np.ndarray:
        """
        Encode session history and patterns.

        Uses pre-computed session context to create embedding based on:
        - Recent task types
        - Multi-turn probability
        - Task continuity patterns
        """
        if not self.session_context:
            return np.random.randn(self.embedding_dim) * 0.1

        # Extract relevant features from session context
        features = []

        # Task type distribution (top 5)
        task_types = self.session_context.get('recurring_task_types', {})
        total_tasks = sum(task_types.values()) or 1
        task_dist = [task_types.get(t, 0) / total_tasks for t in
                     ['code_review', 'debugging', 'build_tasks', 'containerization', 'migration']]
        features.extend(task_dist)  # 5 features

        # Continuity metrics
        continuity = self.session_context.get('user_preferences', {})
        features.append(continuity.get('task_continuity_pct', 0) / 100)  # 1 feature

        # Multi-turn probability
        context_pred = self.session_context.get('context_predictions', {})
        features.append(context_pred.get('multi_turn_probability', 0.5))  # 1 feature

        # Expected session length (normalized to [0, 1])
        expected_turns = context_pred.get('session_length_expected_turns', 44.3)
        features.append(min(expected_turns / 100, 1.0))  # 1 feature

        # Task verb frequency (normalized)
        task_verbs = self.session_context.get('session_context_metadata', {}).get('task_verb_frequency', {})
        total_verbs = sum(task_verbs.values()) or 1
        verb_dist = [task_verbs.get(v, 0) / total_verbs for v in
                     ['review', 'fix', 'test', 'run', 'update']]
        features.extend(verb_dist)  # 5 features

        # Current focus confidence
        features.append(context_pred.get('next_task_confidence', 0.5))  # 1 feature

        # Pad to embedding_dim
        features_array = np.array(features[:self.embedding_dim])
        if len(features_array) < self.embedding_dim:
            padding = np.zeros(self.embedding_dim - len(features_array))
            features_array = np.concatenate([features_array, padding])

        return features_array

    def _encode_user_preferences(self, user_id: str = 'default') -> np.ndarray:
        """
        Encode user preferences and communication style.

        Uses learned user patterns from session context:
        - Workflow style
        - Quality emphasis
        - Communication preferences
        """
        if not self.session_context:
            return np.random.randn(self.embedding_dim) * 0.1

        features = []
        prefs = self.session_context.get('user_preferences', {})

        # Quality emphasis (one-hot encoding)
        quality_levels = {'low': 0, 'medium': 1, 'high': 2}
        quality = quality_levels.get(prefs.get('quality_emphasis', 'medium'), 1)
        quality_onehot = np.zeros(3)
        quality_onehot[quality] = 1.0
        features.extend(quality_onehot)  # 3 features

        # Workflow style (one-hot encoding)
        workflow_styles = {'direct': 0, 'iterative': 1, 'iterative_with_review': 2}
        workflow = prefs.get('workflow_style', 'iterative_with_review')
        workflow_idx = workflow_styles.get(workflow, 2)
        workflow_onehot = np.zeros(3)
        workflow_onehot[workflow_idx] = 1.0
        features.extend(workflow_onehot)  # 3 features

        # Communication style features
        comm_style = self.session_context.get('user_preferences', {}).get('communication_style', {})
        features.append(1.0 if comm_style.get('prefers_direct_questions', True) else 0.0)
        features.append(1.0 if comm_style.get('asks_for_confirmation', True) else 0.0)
        features.append(1.0 if comm_style.get('iterative_refinement', True) else 0.0)

        # Pad to embedding_dim
        features_array = np.array(features[:self.embedding_dim])
        if len(features_array) < self.embedding_dim:
            padding = np.zeros(self.embedding_dim - len(features_array))
            features_array = np.concatenate([features_array, padding])

        return features_array

    def _encode_temporal_context(self, timestamp: datetime = None) -> np.ndarray:
        """
        Encode temporal patterns.

        Features:
        - Hour of day (cyclical encoding)
        - Day of week (cyclical encoding)
        - Recency features
        """
        if timestamp is None:
            timestamp = datetime.now()

        features = []

        # Hour of day (sin/cos encoding for cyclical nature)
        hour = timestamp.hour
        hour_sin = math.sin(hour * 2 * math.pi / 24)
        hour_cos = math.cos(hour * 2 * math.pi / 24)
        features.extend([hour_sin, hour_cos])

        # Day of week (sin/cos encoding)
        day = timestamp.weekday()
        day_sin = math.sin(day * 2 * math.pi / 7)
        day_cos = math.cos(day * 2 * math.pi / 7)
        features.extend([day_sin, day_cos])

        # Working hours indicator
        is_working_hours = 1.0 if 9 <= hour <= 17 else 0.0
        features.append(is_working_hours)

        # Weekend indicator
        is_weekend = 1.0 if day >= 5 else 0.0
        features.append(is_weekend)

        # Pad to embedding_dim
        features_array = np.array(features[:self.embedding_dim])
        if len(features_array) < self.embedding_dim:
            padding = np.zeros(self.embedding_dim - len(features_array))
            features_array = np.concatenate([features_array, padding])

        return features_array

    def _encode_resource_context(self, fleet_health: float = 1.0,
                                 cost_budget_remaining: float = 1.0) -> np.ndarray:
        """
        Encode resource availability context.

        Args:
            fleet_health: Overall fleet health [0, 1]
            cost_budget_remaining: Remaining cost budget [0, 1]

        Returns:
            Resource context embedding
        """
        features = [fleet_health, cost_budget_remaining]

        # Add fleet-specific features if available
        # (Could be extended to include per-node health, queue lengths, etc.)

        # Pad to embedding_dim
        features_array = np.array(features[:self.embedding_dim])
        if len(features_array) < self.embedding_dim:
            padding = np.zeros(self.embedding_dim - len(features_array))
            features_array = np.concatenate([features_array, padding])

        return features_array

    def fuse_contexts(self,
                     task_type: str,
                     complexity: float = 0.5,
                     session_id: str = None,
                     user_id: str = 'default',
                     timestamp: datetime = None,
                     fleet_health: float = 1.0,
                     cost_budget: float = 1.0) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Fuse all context sources into single rich representation.

        Args:
            task_type: Type of task
            complexity: Task complexity estimate
            session_id: Current session identifier
            user_id: User identifier
            timestamp: Current timestamp
            fleet_health: Fleet health score [0, 1]
            cost_budget: Remaining cost budget [0, 1]

        Returns:
            (fused_context, attention_weights_used)
        """
        # Encode each context source
        contexts = {
            'task': self._encode_task_context(task_type, complexity),
            'session': self._encode_session_context(session_id),
            'user': self._encode_user_preferences(user_id),
            'temporal': self._encode_temporal_context(timestamp),
            'resource': self._encode_resource_context(fleet_health, cost_budget)
        }

        # Attention-weighted fusion
        fused = np.zeros(self.embedding_dim)
        for source, embedding in contexts.items():
            weight = self.attention_weights[source]
            fused += weight * embedding

        # Normalize
        norm = np.linalg.norm(fused)
        if norm > 1e-10:
            fused = fused / norm

        return fused, self.attention_weights.copy()

    def update_attention_weights(self, source: str, reward: float, lr: float = 0.01):
        """
        Update attention weights based on reward feedback.

        Simple gradient-based update: increase weight for sources that
        led to good outcomes.

        Args:
            source: Context source that influenced decision
            reward: Reward received [0, 1]
            lr: Learning rate
        """
        # Update attention weight
        current_weight = self.attention_weights[source]

        # Gradient: reward - baseline (baseline = 0.5)
        gradient = reward - 0.5

        # Update with learning rate
        new_weight = current_weight + lr * gradient

        # Clip to valid range
        new_weight = max(0.01, min(0.99, new_weight))

        # Update weight
        self.attention_weights[source] = new_weight

        # Renormalize all weights to sum to 1.0
        total = sum(self.attention_weights.values())
        for s in self.attention_weights:
            self.attention_weights[s] /= total

    def train_from_history(self, training_data: List[Dict]) -> Dict:
        """
        Train fusion model from historical data.

        Args:
            training_data: List of dicts with keys:
                - task_type: str
                - complexity: float
                - timestamp: datetime
                - reward: float
                - primary_context_source: str (which source was most relevant)

        Returns:
            Training metrics
        """
        total_reward = 0
        n_samples = 0

        for sample in training_data:
            # Fuse contexts
            fused_context, weights = self.fuse_contexts(
                task_type=sample['task_type'],
                complexity=sample.get('complexity', 0.5),
                timestamp=sample.get('timestamp'),
                fleet_health=sample.get('fleet_health', 1.0),
                cost_budget=sample.get('cost_budget', 1.0)
            )

            # Update attention weights based on which source was most relevant
            if 'primary_context_source' in sample:
                self.update_attention_weights(
                    sample['primary_context_source'],
                    sample['reward'],
                    lr=0.01
                )

            total_reward += sample['reward']
            n_samples += 1

            self.training_history.append({
                'fused_context': fused_context.tolist(),
                'reward': sample['reward'],
                'weights': weights
            })

        avg_reward = total_reward / n_samples if n_samples > 0 else 0

        return {
            'avg_reward': avg_reward,
            'n_samples': n_samples,
            'final_attention_weights': self.attention_weights.copy()
        }

    def save_model(self, path: str):
        """Save trained model to disk"""
        with open(path, 'wb') as f:
            pickle.dump({
                'embedding_dim': self.embedding_dim,
                'attention_weights': self.attention_weights,
                'embeddings': self.embeddings,
                'training_history': self.training_history[-1000:]  # Keep last 1000
            }, f)

    def load_model(self, path: str):
        """Load trained model from disk"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.embedding_dim = data['embedding_dim']
            self.attention_weights = data['attention_weights']
            self.embeddings = data['embeddings']
            self.training_history = data['training_history']


def create_training_data_from_session_context() -> List[Dict]:
    """
    Create synthetic training data from session context analysis.

    Uses session context patterns to generate training samples.
    """
    # Load session context
    context_path = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/session_context.json'
    if not context_path.exists():
        return []

    with open(context_path) as f:
        session_ctx = json.load(f)

    training_data = []

    # Extract task types and their frequencies
    task_types = session_ctx.get('recurring_task_types', {})
    total_tasks = sum(task_types.values()) or 1

    # Generate samples for each task type
    for task_type, count in task_types.items():
        # Sample proportional to frequency
        n_samples = min(count // 10, 50)  # Cap at 50 samples per task type

        for _ in range(n_samples):
            # Random complexity based on task type
            if task_type == 'debugging':
                complexity = np.random.uniform(0.6, 0.9)  # High complexity
            elif task_type == 'code_review':
                complexity = np.random.uniform(0.4, 0.7)  # Medium complexity
            else:
                complexity = np.random.uniform(0.3, 0.6)  # Lower complexity

            # Random timestamp (weighted towards working hours)
            probs = np.array([
                0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.02, 0.03,  # 0-7
                0.05, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08,  # 8-15
                0.08, 0.05, 0.03, 0.02, 0.02, 0.02, 0.01, 0.01   # 16-23
            ])
            probs = probs / probs.sum()  # Normalize to sum to 1
            hour = np.random.choice(range(24), p=probs)
            timestamp = datetime.now().replace(hour=hour, minute=0, second=0)

            # Reward based on task type success rate
            # (Code review generally successful, debugging varies)
            if task_type == 'code_review':
                reward = np.random.uniform(0.7, 0.95)
                primary_source = 'session'  # Session history most relevant
            elif task_type == 'debugging':
                reward = np.random.uniform(0.5, 0.85)
                primary_source = 'task'  # Task complexity most relevant
            elif task_type == 'build_tasks':
                reward = np.random.uniform(0.6, 0.9)
                primary_source = 'resource'  # Fleet health most relevant
            else:
                reward = np.random.uniform(0.5, 0.8)
                primary_source = 'user'  # User preferences most relevant

            training_data.append({
                'task_type': task_type,
                'complexity': complexity,
                'timestamp': timestamp,
                'reward': reward,
                'primary_context_source': primary_source,
                'fleet_health': np.random.uniform(0.8, 1.0),
                'cost_budget': np.random.uniform(0.6, 1.0)
            })

    return training_data


def train_context_fusion_model():
    """Train context fusion model on session history"""
    print("=" * 80)
    print("CONTEXT FUSION MODEL TRAINING")
    print("=" * 80)

    # Create training data from session context
    print("\nGenerating training data from session context...")
    training_data = create_training_data_from_session_context()
    print(f"Generated {len(training_data)} training samples")

    if len(training_data) == 0:
        print("ERROR: No training data available")
        return None

    # Initialize model
    print("\nInitializing context fusion model...")
    model = ContextFusionModel(embedding_dim=128)

    print("Initial attention weights:")
    for source, weight in model.attention_weights.items():
        print(f"  {source}: {weight:.4f}")

    # Train model
    print("\nTraining model...")
    metrics = model.train_from_history(training_data)

    print("\nTraining complete!")
    print(f"  Samples: {metrics['n_samples']}")
    print(f"  Avg reward: {metrics['avg_reward']:.4f}")

    print("\nLearned attention weights:")
    for source, weight in metrics['final_attention_weights'].items():
        print(f"  {source}: {weight:.4f}")

    # Save model
    model_path = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/context_fusion_model.pkl'
    model.save_model(str(model_path))
    print(f"\nModel saved to: {model_path}")

    # Save metrics
    metrics_path = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/context_fusion_metrics.json'
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to: {metrics_path}")

    # Demonstrate fusion
    print("\n" + "=" * 80)
    print("DEMONSTRATION: Context Fusion")
    print("=" * 80)

    # Example 1: Code review task
    print("\nExample 1: Code review task (working hours)")
    fused, weights = model.fuse_contexts(
        task_type='code_review',
        complexity=0.6,
        timestamp=datetime.now().replace(hour=14),
        fleet_health=0.9,
        cost_budget=0.8
    )
    print(f"Fused context shape: {fused.shape}")
    print(f"Fused context norm: {np.linalg.norm(fused):.4f}")
    print("Attention weights used:")
    for source, weight in weights.items():
        print(f"  {source}: {weight:.4f}")

    # Example 2: Debugging task
    print("\nExample 2: Debugging task (high complexity)")
    fused, weights = model.fuse_contexts(
        task_type='debugging',
        complexity=0.85,
        timestamp=datetime.now(),
        fleet_health=0.95,
        cost_budget=0.5
    )
    print(f"Fused context shape: {fused.shape}")
    print(f"Fused context norm: {np.linalg.norm(fused):.4f}")

    return model


if __name__ == '__main__':
    model = train_context_fusion_model()

    print("\n" + "=" * 80)
    print("INTEGRATION GUIDE")
    print("=" * 80)
    print("\n1. Context fusion model creates rich 128-dim embeddings")
    print("2. Feed fused contexts to contextual bandit for model selection")
    print("3. Update attention weights based on task outcomes")
    print("\nUsage:")
    print("```python")
    print("from context_fusion_model import ContextFusionModel")
    print("")
    print("model = ContextFusionModel()")
    print("model.load_model('learning/context_fusion_model.pkl')")
    print("")
    print("# Fuse contexts")
    print("fused, weights = model.fuse_contexts(")
    print("    task_type='code_review',")
    print("    complexity=0.6,")
    print("    fleet_health=0.9")
    print(")")
    print("")
    print("# Use fused context in bandit")
    print("# selected_model = bandit.select_arm(fused, available_models)")
    print("```")
