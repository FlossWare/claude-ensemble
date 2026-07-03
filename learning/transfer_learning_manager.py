#!/usr/bin/env python3
"""
Transfer Learning Manager
==========================

Optimizes knowledge transfer across models and domains by learning:
1. Which model knowledge transfers best to which tasks
2. Domain adaptation strategies (fine-tuning vs few-shot)
3. Few-shot learning optimization (k-shot selection)
4. Cross-task knowledge reuse patterns

Integrates with PostgreSQL monitoring.execution_summary for historical data.
"""

import pickle
import json
import numpy as np
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class TransferLearningManager:
    """
    Learns optimal transfer strategies across models and domains.

    Key features:
    - Transfer matrix: Which source model transfers best to which target task
    - Domain adaptation: When to fine-tune vs few-shot
    - Few-shot optimization: Optimal k-shot and example selection
    - Cross-domain knowledge reuse patterns
    """

    def __init__(self):
        self.transfer_matrix = defaultdict(self._make_list_dict)
        self.domain_adaptations = defaultdict(list)
        self.few_shot_performance = defaultdict(self._make_list_dict)
        self.cross_domain_patterns = []
        self.model_specializations = {}
        self.task_similarities = {}
        self.transfer_history = []

    @staticmethod
    def _make_list_dict():
        """Factory for nested defaultdict (pickle-safe)."""
        return defaultdict(list)

        # Transfer learning strategies
        self.strategies = {
            'zero_shot': {'requires_finetuning': False, 'requires_examples': 0},
            'few_shot_1': {'requires_finetuning': False, 'requires_examples': 1},
            'few_shot_3': {'requires_finetuning': False, 'requires_examples': 3},
            'few_shot_5': {'requires_finetuning': False, 'requires_examples': 5},
            'few_shot_10': {'requires_finetuning': False, 'requires_examples': 10},
            'domain_adaptation': {'requires_finetuning': True, 'requires_examples': 100},
            'full_finetune': {'requires_finetuning': True, 'requires_examples': 1000},
        }

        # Performance history
        self.transfer_history = []

    def record_transfer(self, source_model, target_task, task_type, quality_score,
                       strategy='zero_shot', num_examples=0):
        """
        Record a transfer learning outcome.

        Args:
            source_model: Model used (e.g., 'opus', 'sonnet', 'haiku')
            target_task: Task identifier
            task_type: Task category (e.g., 'security', 'code-review')
            quality_score: 0-1 quality metric
            strategy: Transfer strategy used
            num_examples: Number of examples provided (for few-shot)
        """
        transfer_record = {
            'timestamp': datetime.now().isoformat(),
            'source_model': source_model,
            'target_task': target_task,
            'task_type': task_type,
            'quality_score': quality_score,
            'strategy': strategy,
            'num_examples': num_examples,
        }

        self.transfer_history.append(transfer_record)

        # Update transfer matrix
        self.transfer_matrix[source_model][task_type].append(quality_score)

        # Update few-shot performance
        if strategy.startswith('few_shot'):
            self.few_shot_performance[task_type][num_examples].append(quality_score)

        # Update domain adaptation tracking
        if strategy in ['domain_adaptation', 'full_finetune']:
            self.domain_adaptations[task_type].append({
                'model': source_model,
                'strategy': strategy,
                'quality': quality_score,
                'num_examples': num_examples,
            })

    def get_best_transfer_model(self, task_type, strategy='zero_shot'):
        """
        Find the best model for transferring to a given task type.

        Returns:
            tuple: (best_model, expected_quality, confidence)
        """
        candidates = []

        for model, tasks in self.transfer_matrix.items():
            if task_type in tasks and len(tasks[task_type]) > 0:
                scores = tasks[task_type]
                avg_quality = np.mean(scores)
                confidence = len(scores) / (len(scores) + 5)  # Confidence increases with samples
                candidates.append((model, avg_quality, confidence))

        if not candidates:
            return None, 0.0, 0.0

        # Sort by quality * confidence (balance quality and certainty)
        candidates.sort(key=lambda x: x[1] * x[2], reverse=True)
        return candidates[0]

    def get_optimal_few_shot_k(self, task_type):
        """
        Determine optimal number of examples (k) for few-shot learning.

        Returns:
            dict: {k: expected_quality} for different k values
        """
        if task_type not in self.few_shot_performance:
            return {0: 0.5, 1: 0.6, 3: 0.7, 5: 0.75, 10: 0.8}  # Defaults

        perf = self.few_shot_performance[task_type]
        k_performance = {}

        for k, scores in perf.items():
            if len(scores) > 0:
                k_performance[k] = np.mean(scores)

        return k_performance

    def recommend_strategy(self, task_type, available_examples=0):
        """
        Recommend best transfer learning strategy for a task.

        Args:
            task_type: Task category
            available_examples: Number of training examples available

        Returns:
            dict: {strategy, expected_quality, reasoning}
        """
        # Check historical performance for this task type
        k_performance = self.get_optimal_few_shot_k(task_type)

        # If we have domain adaptation history, check if it's worth it
        domain_perf = []
        if task_type in self.domain_adaptations:
            domain_perf = [d['quality'] for d in self.domain_adaptations[task_type]]

        avg_domain_quality = np.mean(domain_perf) if domain_perf else 0.0

        # Decision logic
        if available_examples == 0:
            strategy = 'zero_shot'
            expected_quality = k_performance.get(0, 0.5)
            reasoning = "No examples available, using zero-shot"

        elif available_examples < 10:
            # Few-shot learning
            best_k = min(available_examples, 5)
            strategy = f'few_shot_{best_k}'
            expected_quality = k_performance.get(best_k, 0.6)
            reasoning = f"Using {best_k}-shot learning with limited examples"

        elif available_examples < 100:
            # Compare few-shot vs domain adaptation
            few_shot_quality = k_performance.get(10, 0.7)

            if avg_domain_quality > few_shot_quality + 0.1:
                strategy = 'domain_adaptation'
                expected_quality = avg_domain_quality
                reasoning = f"Domain adaptation outperforms few-shot ({avg_domain_quality:.2f} vs {few_shot_quality:.2f})"
            else:
                strategy = 'few_shot_10'
                expected_quality = few_shot_quality
                reasoning = f"Few-shot sufficient ({few_shot_quality:.2f}), avoiding fine-tuning cost"

        else:
            # Full fine-tuning recommended
            strategy = 'full_finetune'
            expected_quality = avg_domain_quality if avg_domain_quality > 0 else 0.85
            reasoning = f"Sufficient examples ({available_examples}) for full fine-tuning"

        return {
            'strategy': strategy,
            'expected_quality': expected_quality,
            'reasoning': reasoning,
            'alternative_strategies': k_performance,
        }

    def detect_cross_domain_transfer(self):
        """
        Detect which task types benefit from cross-domain knowledge transfer.

        Returns:
            list: [(source_task, target_task, transfer_gain)]
        """
        task_types = list(set(r['task_type'] for r in self.transfer_history))
        cross_domain_gains = []

        for target_task in task_types:
            # Get baseline quality (direct training)
            baseline_scores = [
                r['quality_score'] for r in self.transfer_history
                if r['task_type'] == target_task and r['strategy'] in ['zero_shot', 'few_shot_1']
            ]

            if not baseline_scores:
                continue

            baseline = np.mean(baseline_scores)

            # Check if models trained on other tasks perform better
            for source_task in task_types:
                if source_task == target_task:
                    continue

                # Find transfers from models specialized in source_task
                transfer_scores = []
                for r in self.transfer_history:
                    if r['task_type'] == target_task:
                        # Check if this model is strong on source_task
                        source_perf = self.transfer_matrix.get(r['source_model'], {}).get(source_task, [])
                        if source_perf and np.mean(source_perf) > 0.7:
                            transfer_scores.append(r['quality_score'])

                if transfer_scores:
                    transfer_quality = np.mean(transfer_scores)
                    gain = transfer_quality - baseline

                    if gain > 0.05:  # Significant improvement
                        cross_domain_gains.append((source_task, target_task, gain))

        cross_domain_gains.sort(key=lambda x: x[2], reverse=True)
        return cross_domain_gains

    def get_model_specializations(self):
        """
        Identify which models specialize in which task types.

        Returns:
            dict: {model: [(task_type, quality_score)]}
        """
        specializations = {}

        for model, tasks in self.transfer_matrix.items():
            model_strengths = []
            for task_type, scores in tasks.items():
                if len(scores) >= 3:  # Require minimum sample size
                    avg_quality = np.mean(scores)
                    if avg_quality > 0.7:
                        model_strengths.append((task_type, avg_quality))

            model_strengths.sort(key=lambda x: x[1], reverse=True)
            specializations[model] = model_strengths

        return specializations

    def get_statistics(self):
        """Get transfer learning statistics."""
        return {
            'total_transfers': len(self.transfer_history),
            'models_tracked': len(self.transfer_matrix),
            'task_types_tracked': len(set(r['task_type'] for r in self.transfer_history)),
            'strategies_used': len(set(r['strategy'] for r in self.transfer_history)),
            'avg_transfer_quality': np.mean([r['quality_score'] for r in self.transfer_history]) if self.transfer_history else 0.0,
            'model_specializations': self.get_model_specializations(),
            'cross_domain_patterns': len(self.detect_cross_domain_transfer()),
        }

    def save(self, filepath):
        """Save transfer learning manager to pickle file."""
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)
        print(f"Transfer learning manager saved to {filepath}")

    @staticmethod
    def load(filepath):
        """Load transfer learning manager from pickle file."""
        if not Path(filepath).exists():
            return TransferLearningManager()

        with open(filepath, 'rb') as f:
            return pickle.load(f)


def load_from_postgres():
    """
    Load execution data from PostgreSQL and populate transfer learning manager.

    Queries monitoring.execution_summary for historical model performance.
    """
    import psycopg2

    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host='aio-01',
        port=5433,
        database='learning',
        user='sfloess'
    )

    cursor = conn.cursor()

    # Query execution data
    cursor.execute("""
        SELECT model, workflow, task_type, quality_score, outcome, timestamp
        FROM monitoring.execution_summary
        WHERE quality_score > 0 AND quality_score <= 1
        ORDER BY timestamp DESC
        LIMIT 5000
    """)

    rows = cursor.fetchall()
    conn.close()

    # Create transfer learning manager
    manager = TransferLearningManager()

    # Process each execution record
    for model, workflow, task_type, quality_score, outcome, timestamp in rows:
        if not model or not task_type:
            continue

        # Infer strategy based on context
        # (In production, this would be explicitly tracked)
        strategy = 'zero_shot'  # Default assumption
        num_examples = 0

        manager.record_transfer(
            source_model=model,
            target_task=workflow or task_type,
            task_type=task_type,
            quality_score=float(quality_score),
            strategy=strategy,
            num_examples=num_examples
        )

    return manager


def main():
    """Train transfer learning manager and save to disk."""
    print("Transfer Learning Manager Training")
    print("=" * 60)
    print()

    # Load data from PostgreSQL
    print("Loading execution data from PostgreSQL...")
    manager = load_from_postgres()

    print(f"Loaded {len(manager.transfer_history)} transfer records")
    print()

    # Analyze transfer patterns
    print("Transfer Learning Statistics:")
    print("-" * 60)
    stats = manager.get_statistics()
    print(f"Total transfers: {stats['total_transfers']}")
    print(f"Models tracked: {stats['models_tracked']}")
    print(f"Task types tracked: {stats['task_types_tracked']}")
    print(f"Avg transfer quality: {stats['avg_transfer_quality']:.3f}")
    print(f"Cross-domain patterns: {stats['cross_domain_patterns']}")
    print()

    # Model specializations
    print("Model Specializations:")
    print("-" * 60)
    for model, strengths in stats['model_specializations'].items():
        if strengths:
            print(f"{model}:")
            for task_type, quality in strengths[:3]:  # Top 3
                print(f"  - {task_type}: {quality:.3f}")
    print()

    # Cross-domain transfer patterns
    print("Cross-Domain Transfer Gains:")
    print("-" * 60)
    cross_domain = manager.detect_cross_domain_transfer()
    for source, target, gain in cross_domain[:5]:  # Top 5
        print(f"{source} → {target}: +{gain:.3f}")
    print()

    # Example recommendations
    print("Example Strategy Recommendations:")
    print("-" * 60)
    task_types = list(set(r['task_type'] for r in manager.transfer_history))[:5]
    for task_type in task_types:
        rec = manager.recommend_strategy(task_type, available_examples=10)
        print(f"{task_type}:")
        print(f"  Strategy: {rec['strategy']}")
        print(f"  Expected quality: {rec['expected_quality']:.3f}")
        print(f"  Reasoning: {rec['reasoning']}")
    print()

    # Save manager
    output_path = Path.home() / '.claude' / 'learning' / 'transfer_learning.pkl'
    manager.save(str(output_path))

    # Save statistics as JSON
    stats_path = Path.home() / '.claude' / 'learning' / 'transfer_learning_stats.json'
    with open(stats_path, 'w') as f:
        # Convert numpy types for JSON serialization
        json_stats = {
            'total_transfers': stats['total_transfers'],
            'models_tracked': stats['models_tracked'],
            'task_types_tracked': stats['task_types_tracked'],
            'strategies_used': stats['strategies_used'],
            'avg_transfer_quality': float(stats['avg_transfer_quality']),
            'cross_domain_patterns': stats['cross_domain_patterns'],
            'model_specializations': {
                model: [(task, float(quality)) for task, quality in strengths]
                for model, strengths in stats['model_specializations'].items()
            },
            'cross_domain_gains': [
                {'source': source, 'target': target, 'gain': float(gain)}
                for source, target, gain in cross_domain[:10]
            ],
            'timestamp': datetime.now().isoformat(),
        }
        json.dump(json_stats, f, indent=2)

    print(f"Statistics saved to {stats_path}")

    return manager


if __name__ == '__main__':
    main()
