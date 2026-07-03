#!/usr/bin/env python3
"""
Active Learning Selector - Which examples to label next

Implements:
1. Uncertainty Sampling - Select examples where model is most uncertain
2. Query-by-Committee - Select examples where multiple models disagree most
3. Expected Model Change - Select examples that would change model most
4. Diversity Sampling - Select diverse examples to cover feature space

Integrates with PostgreSQL learning database for experience storage.

Usage:
    from active_learning import ActiveLearningSelector

    selector = ActiveLearningSelector()
    next_to_label = selector.select_next_batch(
        unlabeled_pool=unlabeled_examples,
        strategy='uncertainty',
        batch_size=10
    )
"""

import numpy as np
import pickle
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import sys

# Add learning directory to path for postgres adapter
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))
from postgres_adapter import get_db

class ActiveLearningSelector:
    """
    Active learning selector for identifying most valuable examples to label.

    Strategies:
    - uncertainty: Select examples with highest prediction uncertainty
    - qbc: Query-by-committee - select where models disagree most
    - expected_change: Select examples that would change model most
    - diversity: Select diverse examples covering feature space
    """

    def __init__(self, db=None):
        self.db = db or get_db()
        self.strategies = {
            'uncertainty': self._uncertainty_sampling,
            'qbc': self._query_by_committee,
            'expected_change': self._expected_model_change,
            'diversity': self._diversity_sampling,
            'random': self._random_sampling
        }
        self.selection_history = []

    def select_next_batch(
        self,
        unlabeled_pool: List[Dict[str, Any]],
        strategy: str = 'uncertainty',
        batch_size: int = 10,
        model_predictions: Optional[List[np.ndarray]] = None,
        committee_predictions: Optional[List[List[np.ndarray]]] = None
    ) -> List[int]:
        """
        Select next batch of examples to label.

        Args:
            unlabeled_pool: List of unlabeled examples (dicts with 'features', 'metadata')
            strategy: Selection strategy name
            batch_size: Number of examples to select
            model_predictions: Model predictions for uncertainty/expected_change (N x C array)
            committee_predictions: List of predictions from committee members (M x N x C)

        Returns:
            List of indices into unlabeled_pool to label next
        """
        if strategy not in self.strategies:
            raise ValueError(f"Unknown strategy: {strategy}. Choose from {list(self.strategies.keys())}")

        # Get selection function
        select_fn = self.strategies[strategy]

        # Execute selection
        if strategy == 'uncertainty':
            if model_predictions is None:
                raise ValueError("uncertainty strategy requires model_predictions")
            selected_indices = select_fn(unlabeled_pool, model_predictions, batch_size)

        elif strategy == 'qbc':
            if committee_predictions is None:
                raise ValueError("qbc strategy requires committee_predictions")
            selected_indices = select_fn(unlabeled_pool, committee_predictions, batch_size)

        elif strategy == 'expected_change':
            if model_predictions is None:
                raise ValueError("expected_change strategy requires model_predictions")
            selected_indices = select_fn(unlabeled_pool, model_predictions, batch_size)

        elif strategy == 'diversity':
            selected_indices = select_fn(unlabeled_pool, batch_size)

        elif strategy == 'random':
            selected_indices = select_fn(unlabeled_pool, batch_size)

        # Log selection
        self._log_selection(strategy, selected_indices, unlabeled_pool)

        return selected_indices

    def _uncertainty_sampling(
        self,
        pool: List[Dict],
        predictions: np.ndarray,
        batch_size: int
    ) -> List[int]:
        """
        Uncertainty sampling: select examples where model is most uncertain.

        Uses entropy as uncertainty measure:
            H(p) = -sum(p * log(p))

        Higher entropy = more uncertain
        """
        # Calculate entropy for each example
        entropies = []
        for pred in predictions:
            # Ensure predictions are probabilities
            if pred.sum() > 0:
                prob = pred / pred.sum()
            else:
                prob = np.ones_like(pred) / len(pred)

            # Calculate entropy (avoid log(0))
            prob_safe = np.clip(prob, 1e-10, 1.0)
            entropy = -np.sum(prob_safe * np.log(prob_safe))
            entropies.append(entropy)

        entropies = np.array(entropies)

        # Select top-k most uncertain
        selected_indices = np.argsort(entropies)[-batch_size:].tolist()

        return selected_indices

    def _query_by_committee(
        self,
        pool: List[Dict],
        committee_predictions: List[List[np.ndarray]],
        batch_size: int
    ) -> List[int]:
        """
        Query-by-committee: select examples where committee members disagree most.

        Uses vote entropy as disagreement measure:
            - Each committee member votes for a class
            - Calculate entropy of vote distribution
            - Higher entropy = more disagreement
        """
        num_examples = len(pool)
        num_committee = len(committee_predictions)

        if num_committee == 0:
            raise ValueError("Committee must have at least one member")

        # For each example, get votes from committee
        vote_entropies = []

        for i in range(num_examples):
            # Get predictions from all committee members for this example
            votes = []
            for member_preds in committee_predictions:
                pred = member_preds[i]
                # Vote for class with highest probability
                vote = np.argmax(pred)
                votes.append(vote)

            # Calculate vote distribution
            vote_counts = np.bincount(votes, minlength=len(committee_predictions[0][0]))
            vote_probs = vote_counts / num_committee

            # Calculate entropy of votes
            vote_probs_safe = np.clip(vote_probs, 1e-10, 1.0)
            entropy = -np.sum(vote_probs_safe * np.log(vote_probs_safe))
            vote_entropies.append(entropy)

        vote_entropies = np.array(vote_entropies)

        # Select top-k with highest disagreement
        selected_indices = np.argsort(vote_entropies)[-batch_size:].tolist()

        return selected_indices

    def _expected_model_change(
        self,
        pool: List[Dict],
        predictions: np.ndarray,
        batch_size: int
    ) -> List[int]:
        """
        Expected model change: select examples that would change model parameters most.

        Approximation: select examples with predictions closest to decision boundary.
        For binary: closest to 0.5
        For multi-class: smallest margin between top-2 classes
        """
        margins = []

        for pred in predictions:
            # Normalize to probabilities
            if pred.sum() > 0:
                prob = pred / pred.sum()
            else:
                prob = np.ones_like(pred) / len(pred)

            # Calculate margin (difference between top-2 classes)
            sorted_probs = np.sort(prob)
            if len(sorted_probs) >= 2:
                margin = sorted_probs[-1] - sorted_probs[-2]
            else:
                margin = sorted_probs[-1]

            margins.append(margin)

        margins = np.array(margins)

        # Select examples with smallest margin (closest to decision boundary)
        selected_indices = np.argsort(margins)[:batch_size].tolist()

        return selected_indices

    def _diversity_sampling(
        self,
        pool: List[Dict],
        batch_size: int
    ) -> List[int]:
        """
        Diversity sampling: select diverse examples covering feature space.

        Uses k-means++ style selection:
        1. Select random first example
        2. Select subsequent examples furthest from already selected
        """
        if len(pool) == 0:
            return []

        # Extract features (assume 'embedding' or 'features' key)
        features = []
        for example in pool:
            if 'embedding' in example:
                features.append(example['embedding'])
            elif 'features' in example:
                features.append(example['features'])
            else:
                # No features available, fall back to random
                return self._random_sampling(pool, batch_size)

        features = np.array(features)

        # k-means++ selection
        selected_indices = []

        # Select first example randomly
        first_idx = np.random.randint(0, len(pool))
        selected_indices.append(first_idx)

        # Select remaining examples
        for _ in range(batch_size - 1):
            if len(selected_indices) >= len(pool):
                break

            # Calculate distance from each example to nearest selected example
            min_distances = []
            for i in range(len(pool)):
                if i in selected_indices:
                    min_distances.append(0)
                else:
                    # Distance to nearest selected
                    distances = [
                        np.linalg.norm(features[i] - features[j])
                        for j in selected_indices
                    ]
                    min_distances.append(min(distances))

            # Select example with maximum distance
            next_idx = int(np.argmax(min_distances))
            selected_indices.append(next_idx)

        return selected_indices

    def _random_sampling(
        self,
        pool: List[Dict],
        batch_size: int
    ) -> List[int]:
        """
        Random sampling baseline.
        """
        indices = list(range(len(pool)))
        np.random.shuffle(indices)
        return indices[:batch_size]

    def _log_selection(
        self,
        strategy: str,
        selected_indices: List[int],
        pool: List[Dict]
    ):
        """Log selection to history and database."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'strategy': strategy,
            'batch_size': len(selected_indices),
            'selected_indices': selected_indices,
            'pool_size': len(pool)
        }

        self.selection_history.append(log_entry)

        # Store in PostgreSQL
        try:
            self.db.execute(
                """
                INSERT INTO learning.active_learning_selections
                (strategy, batch_size, pool_size, selected_indices, metadata)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    strategy,
                    len(selected_indices),
                    len(pool),
                    json.dumps(selected_indices),
                    json.dumps({'timestamp': log_entry['timestamp']})
                )
            )
        except Exception as e:
            # Table might not exist yet, just log to history
            print(f"Warning: Could not log to database: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about selection history."""
        if not self.selection_history:
            return {
                'total_selections': 0,
                'total_examples_selected': 0,
                'strategies_used': {}
            }

        strategies_used = {}
        total_examples = 0

        for entry in self.selection_history:
            strategy = entry['strategy']
            batch_size = entry['batch_size']

            strategies_used[strategy] = strategies_used.get(strategy, 0) + 1
            total_examples += batch_size

        return {
            'total_selections': len(self.selection_history),
            'total_examples_selected': total_examples,
            'strategies_used': strategies_used,
            'avg_batch_size': total_examples / len(self.selection_history)
        }

    def save(self, path: str):
        """Save selector state to pickle."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        state = {
            'selection_history': self.selection_history,
            'statistics': self.get_statistics()
        }

        with open(path, 'wb') as f:
            pickle.dump(state, f)

        print(f"Active learning selector saved to {path}")

    @classmethod
    def load(cls, path: str, db=None):
        """Load selector state from pickle."""
        selector = cls(db=db)

        if Path(path).exists():
            with open(path, 'rb') as f:
                state = pickle.load(f)

            selector.selection_history = state.get('selection_history', [])
            print(f"Active learning selector loaded from {path}")
        else:
            print(f"No saved state found at {path}, starting fresh")

        return selector


def demo():
    """Demonstration of active learning selector."""
    print("=== Active Learning Selector Demo ===\n")

    # Create selector
    selector = ActiveLearningSelector()

    # Simulate unlabeled pool
    np.random.seed(42)
    pool_size = 100
    num_classes = 3

    unlabeled_pool = [
        {
            'id': i,
            'features': np.random.randn(10),
            'embedding': np.random.randn(10)
        }
        for i in range(pool_size)
    ]

    # Simulate model predictions (softmax outputs)
    model_predictions = np.random.rand(pool_size, num_classes)
    model_predictions = model_predictions / model_predictions.sum(axis=1, keepdims=True)

    # Simulate committee predictions (3 committee members)
    committee_size = 3
    committee_predictions = [
        np.random.rand(pool_size, num_classes)
        for _ in range(committee_size)
    ]
    for i in range(committee_size):
        committee_predictions[i] = committee_predictions[i] / committee_predictions[i].sum(axis=1, keepdims=True)

    # Test each strategy
    strategies_to_test = ['uncertainty', 'qbc', 'expected_change', 'diversity', 'random']
    batch_size = 10

    results = {}

    for strategy in strategies_to_test:
        print(f"\n--- Testing {strategy.upper()} strategy ---")

        if strategy == 'qbc':
            selected = selector.select_next_batch(
                unlabeled_pool,
                strategy=strategy,
                batch_size=batch_size,
                committee_predictions=committee_predictions
            )
        elif strategy == 'diversity':
            selected = selector.select_next_batch(
                unlabeled_pool,
                strategy=strategy,
                batch_size=batch_size
            )
        else:
            selected = selector.select_next_batch(
                unlabeled_pool,
                strategy=strategy,
                batch_size=batch_size,
                model_predictions=model_predictions
            )

        print(f"Selected {len(selected)} examples: {selected[:5]}..." if len(selected) > 5 else f"Selected: {selected}")
        results[strategy] = selected

    # Show statistics
    print("\n=== Selection Statistics ===")
    stats = selector.get_statistics()
    print(f"Total selections: {stats['total_selections']}")
    print(f"Total examples selected: {stats['total_examples_selected']}")
    print(f"Average batch size: {stats['avg_batch_size']:.1f}")
    print(f"Strategies used: {stats['strategies_used']}")

    # Save selector
    save_path = str(Path.home() / '.claude' / 'learning' / 'active_learning.pkl')
    selector.save(save_path)

    # Test load
    loaded_selector = ActiveLearningSelector.load(save_path)
    print(f"\nLoaded selector has {len(loaded_selector.selection_history)} history entries")

    return {
        'selection_strategies': len(strategies_to_test),
        'model_saved': Path(save_path).exists(),
        'sample_reduction_pct': (batch_size / pool_size) * 100
    }


if __name__ == '__main__':
    result = demo()
    print(f"\n=== Final Result ===")
    print(json.dumps(result, indent=2))
