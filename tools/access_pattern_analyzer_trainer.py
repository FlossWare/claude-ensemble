#!/usr/bin/env python3
"""
Access Pattern Analyzer Trainer

Learns access patterns from workflow execution data to predict:
1. Which models are best for which task types
2. Optimal data source selection based on query patterns
3. Cache hit prediction
4. Resource usage forecasting

Trains on PostgreSQL workflow.* tables:
- workflow.executions (workflow metadata)
- workflow.worker_results (model execution patterns)
- workflow.response_cache (cache access patterns)

Output: /home/sfloess/.claude/learning/access_pattern_analyzer.pkl
"""

import sys
from pathlib import Path
import json
import pickle
import numpy as np
from datetime import datetime, timedelta
from collections import Counter
from typing import Dict, List, Tuple, Optional

# Add learning directory to path
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))
from postgres_adapter import get_db

class AccessPatternAnalyzer:
    """
    Multi-dimensional access pattern learning system

    Learns:
    1. Model-Task Affinity (which models work best for which tasks)
    2. Temporal Access Patterns (when are resources accessed)
    3. Cache Effectiveness (predict cache hits)
    4. Resource Usage Patterns (predict tokens/cost/duration)
    5. Failure Pattern Detection (predict likely failures)
    """

    def __init__(self):
        self.model_task_affinity = {}  # Changed from defaultdict to regular dict
        self.temporal_patterns = {}
        self.cache_patterns = {}
        self.resource_patterns = {}
        self.failure_patterns = {}
        self.task_clusters = {}
        self.trained_at = None

    def extract_task_features(self, task_description: str) -> Dict[str, float]:
        """Extract features from task description"""
        if not task_description:
            return {}

        features = {
            'length': len(task_description),
            'has_code': 1.0 if any(kw in task_description.lower() for kw in
                                   ['python', 'javascript', 'function', 'class', 'import']) else 0.0,
            'has_fix': 1.0 if 'fix' in task_description.lower() else 0.0,
            'has_review': 1.0 if 'review' in task_description.lower() else 0.0,
            'has_test': 1.0 if 'test' in task_description.lower() else 0.0,
            'has_issue': 1.0 if 'issue' in task_description.lower() else 0.0,
            'has_implement': 1.0 if any(kw in task_description.lower() for kw in
                                        ['implement', 'create', 'build']) else 0.0,
            'has_question': 1.0 if '?' in task_description else 0.0,
            'word_count': len(task_description.split()),
        }
        return features

    def cluster_tasks(self, tasks: List[str]) -> Dict[str, int]:
        """Simple task clustering based on features"""
        clusters = {}
        for task in tasks:
            features = self.extract_task_features(task)

            # Simple rule-based clustering
            if features.get('has_fix', 0) > 0:
                cluster = 'fix'
            elif features.get('has_review', 0) > 0:
                cluster = 'review'
            elif features.get('has_test', 0) > 0:
                cluster = 'test'
            elif features.get('has_code', 0) > 0:
                cluster = 'code'
            elif features.get('has_question', 0) > 0:
                cluster = 'query'
            else:
                cluster = 'general'

            clusters[task] = cluster

        return clusters

    def train(self, window_days: int = 30, min_samples: int = 3):
        """Train on recent workflow data"""
        db = get_db()
        cutoff_date = datetime.now() - timedelta(days=window_days)

        print(f"Training Access Pattern Analyzer (window: {window_days} days)")
        print("=" * 80)

        # 1. Load workflow executions
        print("\n1. Loading workflow executions...")
        executions = db.query("""
            SELECT id, workflow_name, task_description,
                   total_workers, outcome, created_at,
                   total_duration_ms
            FROM workflow.executions
            WHERE created_at > %s
            ORDER BY created_at DESC
        """, [cutoff_date])

        print(f"   Loaded {len(executions)} executions")

        # 2. Load worker results (model performance data)
        print("\n2. Loading worker results...")
        worker_results = db.query("""
            SELECT wr.workflow_execution_id, wr.model, wr.task_assigned,
                   wr.duration_ms, wr.input_tokens, wr.output_tokens,
                   wr.cost_usd, wr.outcome, wr.confidence,
                   we.task_description as workflow_task
            FROM workflow.worker_results wr
            JOIN workflow.executions we ON wr.workflow_execution_id = we.id
            WHERE wr.created_at > %s
        """, [cutoff_date])

        print(f"   Loaded {len(worker_results)} worker results")

        # 3. Load cache patterns
        print("\n3. Analyzing cache patterns...")
        cache_data = db.query("""
            SELECT request_hash, model, prompt_hash, hit_count, last_hit_at, created_at
            FROM workflow.response_cache
            WHERE created_at > %s
        """, [cutoff_date])

        print(f"   Loaded {len(cache_data)} cache entries")

        # 4. Build model-task affinity matrix
        print("\n4. Building model-task affinity patterns...")
        task_list = []
        for row in worker_results:
            if not row['task_assigned']:
                continue

            model = row['model']
            task = row['task_assigned']
            outcome = row['outcome']
            duration = row['duration_ms'] or 0
            confidence = row['confidence'] or 0.5

            task_list.append(task)

            # Record success/failure patterns
            success = 1.0 if outcome == 'success' else 0.0

            if model not in self.model_task_affinity:
                self.model_task_affinity[model] = {}
            if task not in self.model_task_affinity[model]:
                self.model_task_affinity[model][task] = []

            self.model_task_affinity[model][task].append({
                'success': success,
                'duration_ms': duration,
                'confidence': confidence,
                'outcome': outcome
            })

            # Resource usage patterns
            if model not in self.resource_patterns:
                self.resource_patterns[model] = {
                    'duration_ms': [],
                    'input_tokens': [],
                    'output_tokens': [],
                    'cost_usd': []
                }

            self.resource_patterns[model]['duration_ms'].append(duration)
            self.resource_patterns[model]['input_tokens'].append(row['input_tokens'] or 0)
            self.resource_patterns[model]['output_tokens'].append(row['output_tokens'] or 0)
            self.resource_patterns[model]['cost_usd'].append(row['cost_usd'] or 0.0)

            # Failure patterns
            if outcome != 'success':
                if model not in self.failure_patterns:
                    self.failure_patterns[model] = []
                self.failure_patterns[model].append({
                    'task': task,
                    'outcome': outcome,
                    'duration_ms': duration
                })

        # Cluster tasks
        print("\n5. Clustering tasks...")
        self.task_clusters = self.cluster_tasks(task_list)
        cluster_counts = Counter(self.task_clusters.values())
        for cluster, count in cluster_counts.most_common():
            print(f"   {cluster:15} {count:4} tasks")

        # 6. Temporal patterns (hour of day distribution)
        print("\n6. Analyzing temporal patterns...")
        for row in worker_results:
            # This would need created_at from worker_results
            # Simplified for now - just count by model
            model = row['model']
            if model not in self.temporal_patterns:
                self.temporal_patterns[model] = []
            self.temporal_patterns[model].append(row['duration_ms'] or 0)

        # 7. Cache effectiveness
        print("\n7. Analyzing cache effectiveness...")
        total_cache_entries = len(cache_data)
        high_hit_caches = sum(1 for row in cache_data if row['hit_count'] > 5)
        if total_cache_entries > 0:
            cache_hit_rate = high_hit_caches / total_cache_entries
            print(f"   High-value cache entries: {high_hit_caches}/{total_cache_entries} ({cache_hit_rate:.1%})")

        for row in cache_data:
            cache_key = f"{row['request_hash']}:{row['model']}"
            self.cache_patterns[cache_key] = {
                'request_hash': row['request_hash'],
                'model': row['model'],
                'prompt_hash': row['prompt_hash'],
                'hit_count': row['hit_count'],
                'last_hit_at': row['last_hit_at'],
                'created_at': row['created_at']
            }

        self.trained_at = datetime.now()

        # 8. Print summary statistics
        print("\n" + "=" * 80)
        print("TRAINING SUMMARY")
        print("=" * 80)
        print(f"\nModels analyzed: {len(self.model_task_affinity)}")
        print(f"Unique tasks: {len(set(task_list))}")
        print(f"Task clusters: {len(cluster_counts)}")
        print(f"Cache entries: {total_cache_entries}")

        print("\n" + "=" * 80)

    def predict_best_model(self, task_description: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """Predict best models for a task based on learned patterns"""
        task_features = self.extract_task_features(task_description)

        # Simple clustering
        if task_features.get('has_fix', 0) > 0:
            cluster = 'fix'
        elif task_features.get('has_review', 0) > 0:
            cluster = 'review'
        elif task_features.get('has_test', 0) > 0:
            cluster = 'test'
        elif task_features.get('has_code', 0) > 0:
            cluster = 'code'
        elif task_features.get('has_question', 0) > 0:
            cluster = 'query'
        else:
            cluster = 'general'

        # Score models based on similar task performance
        model_scores = {}

        for model, tasks in self.model_task_affinity.items():
            for task, results in tasks.items():
                # Check if task is in same cluster
                if self.task_clusters.get(task) == cluster:
                    # Calculate average success rate for this model on similar tasks
                    successes = [r['success'] for r in results]
                    confidences = [r['confidence'] for r in results]
                    durations = [r['duration_ms'] for r in results]

                    if successes:
                        avg_success = np.mean(successes)
                        avg_confidence = np.mean(confidences)
                        avg_duration = np.mean(durations)

                        # Combined score (success rate + confidence - normalized duration penalty)
                        score = (avg_success * 0.5 + avg_confidence * 0.3 -
                                min(avg_duration / 10000, 0.2))  # Cap duration penalty
                        if model not in model_scores:
                            model_scores[model] = []
                        model_scores[model].append(score)

        # Average scores per model
        final_scores = []
        for model, scores in model_scores.items():
            if scores:
                final_scores.append((model, np.mean(scores)))

        # Sort by score descending
        final_scores.sort(key=lambda x: x[1], reverse=True)

        return final_scores[:top_k]

    def predict_resource_usage(self, model: str) -> Dict[str, float]:
        """Predict expected resource usage for a model"""
        if model not in self.resource_patterns:
            return {
                'expected_duration_ms': 5000,
                'expected_input_tokens': 1000,
                'expected_output_tokens': 500,
                'expected_cost_usd': 0.01
            }

        patterns = self.resource_patterns[model]

        return {
            'expected_duration_ms': np.median(patterns['duration_ms']) if patterns['duration_ms'] else 5000,
            'expected_input_tokens': np.median(patterns['input_tokens']) if patterns['input_tokens'] else 1000,
            'expected_output_tokens': np.median(patterns['output_tokens']) if patterns['output_tokens'] else 500,
            'expected_cost_usd': np.median(patterns['cost_usd']) if patterns['cost_usd'] else 0.01
        }

    def predict_failure_risk(self, model: str, task_description: str) -> float:
        """Predict failure probability for a model on a task"""
        if model not in self.failure_patterns:
            return 0.1  # Default 10% failure risk

        failures = self.failure_patterns[model]
        if not failures:
            return 0.05  # Very low risk if no failures recorded

        # Check similar task failures
        task_features = self.extract_task_features(task_description)
        similar_failures = 0
        total_similar = 0

        for failure in failures:
            failure_features = self.extract_task_features(failure['task'])
            # Simple similarity: check if same cluster
            if (failure_features.get('has_code') == task_features.get('has_code') and
                failure_features.get('has_fix') == task_features.get('has_fix')):
                similar_failures += 1
                total_similar += 1

        if total_similar == 0:
            return 0.1

        return min(similar_failures / total_similar, 0.95)  # Cap at 95%

    def get_stats(self) -> Dict:
        """Get analyzer statistics"""
        return {
            'trained_at': self.trained_at.isoformat() if self.trained_at else None,
            'models_tracked': len(self.model_task_affinity),
            'unique_tasks': sum(len(tasks) for tasks in self.model_task_affinity.values()),
            'task_clusters': len(set(self.task_clusters.values())),
            'cache_entries': len(self.cache_patterns),
            'failure_patterns': sum(len(failures) for failures in self.failure_patterns.values())
        }


def main():
    """Train and save access pattern analyzer"""
    import argparse

    parser = argparse.ArgumentParser(description='Train Access Pattern Analyzer')
    parser.add_argument('--window', type=int, default=30,
                       help='Training window in days (default: 30)')
    parser.add_argument('--output', type=str,
                       default=str(Path.home() / '.claude' / 'learning' / 'access_pattern_analyzer.pkl'),
                       help='Output pickle file')
    parser.add_argument('--stats', type=str,
                       default=str(Path.home() / '.claude' / 'learning' / 'access_pattern_analyzer_stats.json'),
                       help='Output stats JSON file')
    parser.add_argument('--test', action='store_true',
                       help='Run prediction tests after training')

    args = parser.parse_args()

    # Train analyzer
    analyzer = AccessPatternAnalyzer()
    analyzer.train(window_days=args.window)

    # Save model
    print(f"\nSaving model to {args.output}...")
    with open(args.output, 'wb') as f:
        pickle.dump(analyzer, f)
    print(f"✓ Model saved ({Path(args.output).stat().st_size / 1024:.1f} KB)")

    # Save stats
    stats = analyzer.get_stats()
    print(f"\nSaving stats to {args.stats}...")
    with open(args.stats, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✓ Stats saved")

    # Print stats
    print("\n" + "=" * 80)
    print("MODEL STATISTICS")
    print("=" * 80)
    for key, value in stats.items():
        print(f"{key:25} {value}")

    # Run tests if requested
    if args.test:
        print("\n" + "=" * 80)
        print("PREDICTION TESTS")
        print("=" * 80)

        test_tasks = [
            "FIX Issue #123: Memory leak in cache manager",
            "Implement user authentication with JWT",
            "REVIEW: Database migration script",
            "What is the capital of France?",
            "Write unit tests for API endpoints"
        ]

        for task in test_tasks:
            print(f"\nTask: {task[:60]}...")

            # Predict best models
            predictions = analyzer.predict_best_model(task, top_k=3)
            if predictions:
                print(f"  Best models:")
                for model, score in predictions:
                    print(f"    {model:40} score={score:.3f}")

                    # Resource prediction for top model
                    if model == predictions[0][0]:
                        resources = analyzer.predict_resource_usage(model)
                        print(f"      Expected: {resources['expected_duration_ms']:.0f}ms, "
                              f"${resources['expected_cost_usd']:.4f}")

                        # Failure risk
                        risk = analyzer.predict_failure_risk(model, task)
                        print(f"      Failure risk: {risk:.1%}")
            else:
                print("  No predictions available (insufficient training data)")

    print("\n" + "=" * 80)
    print("✓ Training complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
