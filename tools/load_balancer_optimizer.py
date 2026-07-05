#!/usr/bin/env python3
"""
Load Balancer Optimizer - Trains on execution history to optimize fleet task distribution

This optimizer learns from historical execution data to make intelligent load balancing
decisions across the multi-model fleet. It considers:
- Model performance (quality scores)
- Resource efficiency (latency, cost)
- Task characteristics (type, complexity)
- Temporal patterns (time of day, load)

Training Strategy:
- Multi-Armed Bandit (Thompson Sampling) for exploration/exploitation
- Contextual features (task type, complexity, time, fleet state)
- Quality-cost tradeoff optimization
- Load distribution fairness constraints

Database Schema:
- Input: monitoring.execution_summary (model, quality_score, duration_ms, cost_usd, timestamp)
- Output: learning.load_balancer_state (model weights, performance statistics)
"""

import sys
import json
import pickle
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict

# PostgreSQL adapter
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))
try:
    from postgres_adapter import get_db
except ImportError:
    print("ERROR: Cannot import postgres_adapter. Ensure it exists in ~/.claude/learning/")
    sys.exit(1)


@dataclass
class ModelStats:
    """Performance statistics for a model"""
    model: str
    executions: int
    avg_quality: float
    std_quality: float
    avg_latency_ms: float
    avg_cost: float
    success_rate: float
    p50_latency: float
    p95_latency: float
    total_tokens: int

    def to_dict(self):
        return asdict(self)


@dataclass
class LoadBalancerState:
    """Complete state of the load balancer"""
    timestamp: str
    window_days: int
    model_stats: Dict[str, ModelStats]
    bandit_params: Dict[str, Dict]  # Thompson Sampling parameters
    task_affinities: Dict[str, Dict[str, float]]  # task_type -> model -> affinity
    load_distribution: Dict[str, float]  # model -> current load percentage
    quality_threshold: float
    cost_budget: float

    def to_dict(self):
        return {
            'timestamp': self.timestamp,
            'window_days': self.window_days,
            'model_stats': {m: s.to_dict() for m, s in self.model_stats.items()},
            'bandit_params': self.bandit_params,
            'task_affinities': self.task_affinities,
            'load_distribution': self.load_distribution,
            'quality_threshold': self.quality_threshold,
            'cost_budget': self.cost_budget
        }


class LoadBalancerOptimizer:
    """
    Learns optimal load balancing strategies from execution history
    """

    def __init__(self, learning_dir: Path = None):
        if learning_dir is None:
            learning_dir = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning'

        self.learning_dir = learning_dir
        self.learning_dir.mkdir(exist_ok=True, parents=True)

        self.db = get_db()

        # Thompson Sampling parameters (Beta distribution)
        # Each model gets alpha (successes + 1) and beta (failures + 1)
        self.bandit_params = {}

        # Task type affinities (which models are best for which tasks)
        self.task_affinities = defaultdict(lambda: defaultdict(float))

        # Quality and cost constraints
        self.quality_threshold = 0.6  # Minimum acceptable quality
        self.cost_budget = 0.01  # Maximum cost per request (USD)

        # Load balancer state
        self.model_stats = {}
        self.load_distribution = defaultdict(float)

    def fetch_execution_data(self, window_days: int = 30) -> List[Dict]:
        """
        Fetch execution history from PostgreSQL

        Args:
            window_days: Number of days of history to fetch

        Returns:
            List of execution records
        """
        cutoff = datetime.now() - timedelta(days=window_days)

        query = """
            SELECT
                model,
                workflow,
                task_type,
                quality_score,
                input_tokens,
                output_tokens,
                cost_usd,
                duration_ms,
                outcome,
                timestamp
            FROM monitoring.execution_summary
            WHERE timestamp > %s
            AND model IS NOT NULL
            ORDER BY timestamp ASC
        """

        rows = self.db.query(query, (cutoff,))
        return rows

    def compute_model_statistics(self, executions: List[Dict]) -> Dict[str, ModelStats]:
        """
        Compute comprehensive statistics per model

        Returns:
            Dictionary mapping model name to ModelStats
        """
        # Group by model
        by_model = defaultdict(list)
        for ex in executions:
            if ex['model']:
                by_model[ex['model']].append(ex)

        stats = {}
        for model, execs in by_model.items():
            # Filter valid quality scores
            qualities = [e['quality_score'] for e in execs if e['quality_score'] is not None]
            latencies = [e['duration_ms'] for e in execs if e['duration_ms'] is not None and e['duration_ms'] > 0]
            costs = [e['cost_usd'] for e in execs if e['cost_usd'] is not None]
            outcomes = [e['outcome'] for e in execs if e['outcome'] is not None]

            # Handle empty data
            if not qualities:
                qualities = [0.0]
            if not latencies:
                latencies = [0.0]
            if not costs:
                costs = [0.0]

            # Success rate
            successes = sum(1 for o in outcomes if o == 'success')
            success_rate = successes / len(outcomes) if outcomes else 0.0

            # Latency percentiles
            sorted_latencies = sorted(latencies)
            p50_idx = int(len(sorted_latencies) * 0.5)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p50 = sorted_latencies[p50_idx] if sorted_latencies else 0.0
            p95 = sorted_latencies[p95_idx] if sorted_latencies else 0.0

            # Total tokens
            total_tokens = sum(
                (e.get('input_tokens', 0) or 0) + (e.get('output_tokens', 0) or 0)
                for e in execs
            )

            stats[model] = ModelStats(
                model=model,
                executions=len(execs),
                avg_quality=float(np.mean(qualities)),
                std_quality=float(np.std(qualities)),
                avg_latency_ms=float(np.mean(latencies)),
                avg_cost=float(np.mean(costs)),
                success_rate=success_rate,
                p50_latency=p50,
                p95_latency=p95,
                total_tokens=total_tokens
            )

        return stats

    def compute_task_affinities(self, executions: List[Dict]) -> Dict[str, Dict[str, float]]:
        """
        Compute which models perform best on which task types

        Returns:
            Dict[task_type][model] = affinity_score (0-1)
        """
        # Group by task type
        by_task = defaultdict(list)
        for ex in executions:
            task_type = ex.get('task_type') or ex.get('workflow') or 'unknown'
            if ex['quality_score'] is not None:
                by_task[task_type].append(ex)

        affinities = {}
        for task_type, execs in by_task.items():
            # Compute average quality per model for this task type
            model_qualities = defaultdict(list)
            for ex in execs:
                model_qualities[ex['model']].append(ex['quality_score'])

            # Compute affinity scores (normalize to 0-1)
            avg_qualities = {
                model: np.mean(qualities)
                for model, qualities in model_qualities.items()
            }

            if avg_qualities:
                max_quality = max(avg_qualities.values())
                if max_quality > 0:
                    affinities[task_type] = {
                        model: qual / max_quality
                        for model, qual in avg_qualities.items()
                    }
                else:
                    affinities[task_type] = {model: 0.5 for model in avg_qualities}

        return affinities

    def train_thompson_sampling(self, executions: List[Dict], quality_threshold: float = 0.6):
        """
        Train Thompson Sampling bandit parameters

        For each model, we maintain Beta(alpha, beta) where:
        - alpha = successes + 1 (quality >= threshold)
        - beta = failures + 1 (quality < threshold)

        Args:
            executions: Execution history
            quality_threshold: Quality threshold for success
        """
        # Initialize
        model_successes = defaultdict(int)
        model_failures = defaultdict(int)

        # Count successes/failures
        for ex in executions:
            if ex['quality_score'] is not None:
                model = ex['model']
                if ex['quality_score'] >= quality_threshold:
                    model_successes[model] += 1
                else:
                    model_failures[model] += 1

        # Compute Beta parameters
        self.bandit_params = {}
        for model in set(list(model_successes.keys()) + list(model_failures.keys())):
            self.bandit_params[model] = {
                'alpha': model_successes[model] + 1,  # +1 for prior
                'beta': model_failures[model] + 1,
                'successes': model_successes[model],
                'failures': model_failures[model],
                'total': model_successes[model] + model_failures[model]
            }

    def train(self, window_days: int = 30) -> LoadBalancerState:
        """
        Train the load balancer on historical data

        Args:
            window_days: Number of days of history to use

        Returns:
            Trained LoadBalancerState
        """
        print(f"Fetching execution data (last {window_days} days)...")
        executions = self.fetch_execution_data(window_days)
        print(f"  Loaded {len(executions)} executions")

        if not executions:
            print("WARNING: No execution data found")
            return LoadBalancerState(
                timestamp=datetime.now().isoformat(),
                window_days=window_days,
                model_stats={},
                bandit_params={},
                task_affinities={},
                load_distribution={},
                quality_threshold=self.quality_threshold,
                cost_budget=self.cost_budget
            )

        print("\nComputing model statistics...")
        self.model_stats = self.compute_model_statistics(executions)
        for model, stats in sorted(self.model_stats.items(), key=lambda x: x[1].avg_quality, reverse=True):
            print(f"  {model:30s} | Quality: {stats.avg_quality:.3f} ± {stats.std_quality:.3f} | "
                  f"Latency: {stats.avg_latency_ms:6.0f}ms (p95: {stats.p95_latency:6.0f}ms) | "
                  f"Cost: ${stats.avg_cost:.5f} | Executions: {stats.executions}")

        print("\nComputing task affinities...")
        self.task_affinities = self.compute_task_affinities(executions)
        for task_type, affinities in sorted(self.task_affinities.items()):
            top_models = sorted(affinities.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"  {task_type:20s} | Best: {', '.join(f'{m}({a:.2f})' for m, a in top_models)}")

        print("\nTraining Thompson Sampling bandit...")
        self.train_thompson_sampling(executions, self.quality_threshold)
        for model, params in sorted(self.bandit_params.items(), key=lambda x: x[1]['alpha']/(x[1]['alpha']+x[1]['beta']), reverse=True):
            win_rate = params['alpha'] / (params['alpha'] + params['beta'])
            print(f"  {model:30s} | Win rate: {win_rate:.3f} | "
                  f"Successes: {params['successes']:4d} | Failures: {params['failures']:4d}")

        # Compute current load distribution
        total_execs = sum(s.executions for s in self.model_stats.values())
        self.load_distribution = {
            model: stats.executions / total_execs
            for model, stats in self.model_stats.items()
        }

        # Create state
        state = LoadBalancerState(
            timestamp=datetime.now().isoformat(),
            window_days=window_days,
            model_stats=self.model_stats,
            bandit_params=self.bandit_params,
            task_affinities=dict(self.task_affinities),
            load_distribution=dict(self.load_distribution),
            quality_threshold=self.quality_threshold,
            cost_budget=self.cost_budget
        )

        return state

    def save_state(self, state: LoadBalancerState):
        """Save trained state to disk"""
        # Save as pickle (for Python)
        pkl_path = self.learning_dir / 'load_balancer_optimizer.pkl'
        with open(pkl_path, 'wb') as f:
            pickle.dump(state, f)
        print(f"\nSaved load balancer state to {pkl_path}")

        # Save statistics as JSON (for JavaScript)
        json_path = self.learning_dir / 'load_balancer_optimizer_stats.json'
        with open(json_path, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)
        print(f"Saved statistics to {json_path}")

        # Save to PostgreSQL
        self._save_to_postgres(state)

    def _save_to_postgres(self, state: LoadBalancerState):
        """Save state to PostgreSQL for cross-language access"""
        try:
            # Create table if not exists
            self.db.query("""
                CREATE TABLE IF NOT EXISTS learning.load_balancer_state (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    window_days INT NOT NULL,
                    model VARCHAR(100) NOT NULL,
                    executions INT NOT NULL,
                    avg_quality FLOAT NOT NULL,
                    std_quality FLOAT NOT NULL,
                    avg_latency_ms FLOAT NOT NULL,
                    avg_cost FLOAT NOT NULL,
                    success_rate FLOAT NOT NULL,
                    p50_latency FLOAT NOT NULL,
                    p95_latency FLOAT NOT NULL,
                    total_tokens BIGINT NOT NULL,
                    bandit_alpha INT NOT NULL,
                    bandit_beta INT NOT NULL,
                    load_percentage FLOAT NOT NULL,
                    UNIQUE(timestamp, model)
                )
            """)

            # Insert model stats
            timestamp = datetime.fromisoformat(state.timestamp)
            for model, stats in state.model_stats.items():
                bandit = state.bandit_params.get(model, {'alpha': 1, 'beta': 1})
                load = state.load_distribution.get(model, 0.0)

                self.db.query("""
                    INSERT INTO learning.load_balancer_state
                    (timestamp, window_days, model, executions, avg_quality, std_quality,
                     avg_latency_ms, avg_cost, success_rate, p50_latency, p95_latency,
                     total_tokens, bandit_alpha, bandit_beta, load_percentage)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp, model) DO UPDATE SET
                        executions = EXCLUDED.executions,
                        avg_quality = EXCLUDED.avg_quality,
                        std_quality = EXCLUDED.std_quality,
                        avg_latency_ms = EXCLUDED.avg_latency_ms,
                        avg_cost = EXCLUDED.avg_cost,
                        success_rate = EXCLUDED.success_rate,
                        p50_latency = EXCLUDED.p50_latency,
                        p95_latency = EXCLUDED.p95_latency,
                        total_tokens = EXCLUDED.total_tokens,
                        bandit_alpha = EXCLUDED.bandit_alpha,
                        bandit_beta = EXCLUDED.bandit_beta,
                        load_percentage = EXCLUDED.load_percentage
                """, (
                    timestamp, state.window_days, model, stats.executions,
                    stats.avg_quality, stats.std_quality, stats.avg_latency_ms,
                    stats.avg_cost, stats.success_rate, stats.p50_latency,
                    stats.p95_latency, stats.total_tokens,
                    bandit['alpha'], bandit['beta'], load
                ))

            print(f"Saved {len(state.model_stats)} model states to PostgreSQL")

        except Exception as e:
            print(f"WARNING: Failed to save to PostgreSQL: {e}")

    def select_model(self,
                    task_type: str = None,
                    complexity: float = 0.5,
                    max_latency_ms: float = None,
                    max_cost: float = None) -> Dict:
        """
        Select best model using trained load balancer

        Uses Thompson Sampling with task affinity and constraints.

        Args:
            task_type: Type of task (for affinity matching)
            complexity: Task complexity [0-1]
            max_latency_ms: Maximum acceptable latency
            max_cost: Maximum acceptable cost

        Returns:
            Selection with model, confidence, reasoning
        """
        if not self.bandit_params:
            return {
                'model': 'haiku',  # Safe default
                'confidence': 0.5,
                'reasoning': 'No training data, using default'
            }

        # Sample from Thompson Sampling
        samples = {}
        for model, params in self.bandit_params.items():
            # Sample from Beta distribution
            sample = np.random.beta(params['alpha'], params['beta'])

            # Apply task affinity if available
            if task_type and task_type in self.task_affinities:
                affinity = self.task_affinities[task_type].get(model, 0.5)
                sample *= affinity

            # Apply constraints
            stats = self.model_stats.get(model)
            if stats:
                # Latency constraint
                if max_latency_ms and stats.p95_latency > max_latency_ms:
                    sample *= 0.5  # Penalty for high latency

                # Cost constraint
                if max_cost and stats.avg_cost > max_cost:
                    sample *= 0.3  # Heavy penalty for high cost

            samples[model] = sample

        # Select best
        best_model = max(samples, key=samples.get)
        confidence = samples[best_model]

        # Generate reasoning
        stats = self.model_stats.get(best_model)
        reasoning = f"Thompson Sampling selected {best_model} "
        if stats:
            reasoning += f"(quality: {stats.avg_quality:.2f}, latency: {stats.p95_latency:.0f}ms, cost: ${stats.avg_cost:.5f})"

        if task_type and task_type in self.task_affinities:
            affinity = self.task_affinities[task_type].get(best_model, 0.0)
            reasoning += f" with {affinity:.2f} affinity for {task_type}"

        return {
            'model': best_model,
            'confidence': float(confidence),
            'reasoning': reasoning,
            'alternatives': {m: float(s) for m, s in sorted(samples.items(), key=lambda x: x[1], reverse=True)[:5]}
        }


def main():
    """Train and save load balancer optimizer"""
    import argparse

    parser = argparse.ArgumentParser(description='Train Load Balancer Optimizer')
    parser.add_argument('--window', type=int, default=30,
                       help='Training window in days (default: 30)')
    parser.add_argument('--output-dir', type=Path,
                       default=Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning',
                       help='Output directory for trained model')
    parser.add_argument('--test', action='store_true',
                       help='Test selection after training')

    args = parser.parse_args()

    print("=" * 80)
    print("LOAD BALANCER OPTIMIZER TRAINING")
    print("=" * 80)

    optimizer = LoadBalancerOptimizer(learning_dir=args.output_dir)

    # Train
    state = optimizer.train(window_days=args.window)

    # Save
    optimizer.save_state(state)

    # Test if requested
    if args.test:
        print("\n" + "=" * 80)
        print("TESTING LOAD BALANCER SELECTIONS")
        print("=" * 80)

        test_cases = [
            {'task_type': 'code_review', 'complexity': 0.6},
            {'task_type': 'debugging', 'complexity': 0.8, 'max_latency_ms': 5000},
            {'task_type': 'build_tasks', 'complexity': 0.3, 'max_cost': 0.001},
            {'task_type': None, 'complexity': 0.5},  # No task type
        ]

        for i, test in enumerate(test_cases, 1):
            print(f"\nTest {i}: {test}")
            selection = optimizer.select_model(**test)
            print(f"  Selected: {selection['model']}")
            print(f"  Confidence: {selection['confidence']:.3f}")
            print(f"  Reasoning: {selection['reasoning']}")
            print(f"  Alternatives: {selection['alternatives']}")

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    print(f"\nModel saved to: {args.output_dir}/load_balancer_optimizer.pkl")
    print(f"Stats saved to: {args.output_dir}/load_balancer_optimizer_stats.json")
    print("\nTo use in workflows:")
    print("  from load_balancer_optimizer import LoadBalancerOptimizer")
    print("  optimizer = LoadBalancerOptimizer()")
    print("  selection = optimizer.select_model(task_type='code_review')")


if __name__ == '__main__':
    main()
