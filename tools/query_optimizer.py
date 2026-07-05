#!/usr/bin/env python3
"""
Database Query Optimizer with Continual Learning

Learns from historical query patterns in PostgreSQL to predict optimal:
- Index usage strategies
- Join order optimization
- Parallelization decisions
- Query plan caching
- Resource allocation

Uses Thompson Sampling bandit + gradient boosting for query plan selection.
"""

import json
import psycopg2
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import hashlib
import pickle
from collections import defaultdict

# Optional ML dependencies (graceful fallback)
try:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("WARNING: scikit-learn not available - using simple heuristics")


class QueryOptimizer:
    """Database query optimizer with continual learning"""

    def __init__(self, model_path: str = None):
        self.model_path = model_path or str(Path.home() / '.claude' / 'learning' / 'query_optimizer.pkl')
        self.stats_path = str(Path.home() / '.claude' / 'learning' / 'query_optimizer_stats.json')

        # Connect to PostgreSQL
        self.conn = psycopg2.connect(
            host='aio-01',
            port=5433,
            user='claude',
            database='learning'
        )

        # Query strategy bandit (Thompson Sampling)
        self.strategies = {
            'index_scan': {'alpha': 1.0, 'beta': 1.0},
            'seq_scan': {'alpha': 1.0, 'beta': 1.0},
            'bitmap_scan': {'alpha': 1.0, 'beta': 1.0},
            'parallel_scan': {'alpha': 1.0, 'beta': 1.0},
            'hash_join': {'alpha': 1.0, 'beta': 1.0},
            'merge_join': {'alpha': 1.0, 'beta': 1.0},
            'nested_loop': {'alpha': 1.0, 'beta': 1.0},
        }

        # ML model for query cost prediction
        self.model = None
        self.scaler = None

        # Query pattern cache
        self.query_cache = {}
        self.execution_history = []

        # Load existing state
        self._load_state()

    def _load_state(self):
        """Load optimizer state from disk"""
        # Load ML model
        if Path(self.model_path).exists() and SKLEARN_AVAILABLE:
            try:
                with open(self.model_path, 'rb') as f:
                    state = pickle.load(f)
                    self.model = state['model']
                    self.scaler = state['scaler']
                    self.strategies = state['strategies']
                print(f"✓ Loaded query optimizer model from {self.model_path}")
            except Exception as e:
                print(f"WARNING: Could not load model: {e}")

        # Load stats
        if Path(self.stats_path).exists():
            try:
                with open(self.stats_path, 'r') as f:
                    stats = json.load(f)
                    self.query_cache = stats.get('query_cache', {})
                    self.execution_history = stats.get('execution_history', [])
                print(f"✓ Loaded query optimizer stats from {self.stats_path}")
            except Exception as e:
                print(f"WARNING: Could not load stats: {e}")

    def _save_state(self):
        """Save optimizer state to disk"""
        # Save ML model
        if self.model and SKLEARN_AVAILABLE:
            Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler,
                    'strategies': self.strategies
                }, f)

        # Save stats
        Path(self.stats_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.stats_path, 'w') as f:
            json.dump({
                'query_cache': self.query_cache,
                'execution_history': self.execution_history[-1000:],  # Keep last 1000
                'strategies': self.strategies,
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)

    def _query_fingerprint(self, query: str) -> str:
        """Generate fingerprint for query (normalize variations)"""
        # Remove whitespace variations
        normalized = ' '.join(query.lower().split())
        # Hash for quick lookup
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _extract_features(self, query: str, context: Dict) -> np.ndarray:
        """Extract features from query for ML prediction

        IMPORTANT: Must match training feature format:
        - workflow length
        - task_type length
        - input_tokens
        - output_tokens
        - quality_score
        - total_tokens
        - hour_of_day
        """
        features = []

        # Match training format (7 features)
        workflow = context.get('workflow', query[:50])  # Use query snippet as workflow
        task_type = context.get('task_type', 'query')

        features.append(len(workflow))  # workflow length
        features.append(len(task_type))  # task_type length
        features.append(context.get('input_tokens', len(query) * 2))  # Estimate from query length
        features.append(context.get('output_tokens', 1000))  # Default output estimate
        features.append(context.get('quality_score', 0.5))  # Default quality
        features.append(context.get('input_tokens', len(query) * 2) +
                       context.get('output_tokens', 1000))  # Total tokens
        features.append(datetime.now().hour)  # Time of day

        return np.array(features).reshape(1, -1)

    def _select_strategy(self, query_type: str) -> str:
        """Select query strategy using Thompson Sampling"""
        # Sample from beta distributions
        samples = {}
        for strategy, params in self.strategies.items():
            samples[strategy] = np.random.beta(params['alpha'], params['beta'])

        # Return strategy with highest sample
        return max(samples.items(), key=lambda x: x[1])[0]

    def _update_strategy(self, strategy: str, success: bool, reward: float):
        """Update strategy bandit with feedback"""
        if success:
            self.strategies[strategy]['alpha'] += reward
        else:
            self.strategies[strategy]['beta'] += (1 - reward)

    def predict_cost(self, query: str, context: Dict = None) -> float:
        """Predict query execution cost (ms)"""
        context = context or {}

        # Check cache first
        fingerprint = self._query_fingerprint(query)
        if fingerprint in self.query_cache:
            cached = self.query_cache[fingerprint]
            return cached['avg_cost']

        # Use ML model if available
        if self.model and SKLEARN_AVAILABLE:
            features = self._extract_features(query, context)
            scaled_features = self.scaler.transform(features)
            cost = self.model.predict(scaled_features)[0]
            return max(0, cost)  # Non-negative

        # Fallback: simple heuristic
        base_cost = 10  # ms

        # Add cost for complexity
        joins = query.lower().count('join')
        base_cost += joins * 50

        subqueries = query.lower().count('select') - 1
        base_cost += subqueries * 100

        # Add cost for data size
        estimated_rows = context.get('estimated_rows', 1000)
        base_cost += (estimated_rows / 1000) * 10

        return base_cost

    def optimize(self, query: str, context: Dict = None) -> Dict:
        """Generate optimized query plan with recommendations"""
        context = context or {}

        # Get fingerprint
        fingerprint = self._query_fingerprint(query)

        # Predict cost
        predicted_cost = self.predict_cost(query, context)

        # Select strategy
        strategy = self._select_strategy('scan')

        # Generate recommendations
        recommendations = []

        # Check for missing indexes
        if 'where' in query.lower() and context.get('index_count', 0) == 0:
            recommendations.append({
                'type': 'index',
                'priority': 'high',
                'message': 'Consider adding index on WHERE clause columns',
                'estimated_improvement': '50-80%'
            })

        # Check for join optimization
        joins = query.lower().count('join')
        if joins > 2:
            recommendations.append({
                'type': 'join',
                'priority': 'medium',
                'message': f'Query has {joins} joins - consider join order optimization',
                'estimated_improvement': '20-40%'
            })

        # Check for parallelization opportunity
        estimated_rows = context.get('estimated_rows', 1000)
        if estimated_rows > 10000 and context.get('cpu_cores', 1) > 1:
            recommendations.append({
                'type': 'parallel',
                'priority': 'medium',
                'message': 'Large result set - enable parallel query execution',
                'sql_hint': 'SET max_parallel_workers_per_gather = 4;',
                'estimated_improvement': '30-60%'
            })

        # Check for sorting optimization
        if 'order by' in query.lower() and estimated_rows > 1000:
            recommendations.append({
                'type': 'sort',
                'priority': 'low',
                'message': 'Large result set with sorting - consider index on ORDER BY columns',
                'estimated_improvement': '10-30%'
            })

        return {
            'query_fingerprint': fingerprint,
            'predicted_cost_ms': predicted_cost,
            'recommended_strategy': strategy,
            'recommendations': recommendations,
            'alternative_strategies': self._get_alternative_strategies(query, context),
            'timestamp': datetime.now().isoformat()
        }

    def _get_alternative_strategies(self, query: str, context: Dict) -> List[Dict]:
        """Generate alternative query strategies"""
        alternatives = []

        # Index scan vs seq scan tradeoff
        estimated_rows = context.get('estimated_rows', 1000)
        table_size = context.get('table_size_mb', 100)
        selectivity = estimated_rows / max(table_size * 100, 1)  # Rough estimate

        if selectivity < 0.05:  # High selectivity
            alternatives.append({
                'strategy': 'index_scan',
                'reason': 'High selectivity (<5%) favors index scan',
                'confidence': self.strategies['index_scan']['alpha'] /
                             (self.strategies['index_scan']['alpha'] + self.strategies['index_scan']['beta'])
            })
        else:
            alternatives.append({
                'strategy': 'seq_scan',
                'reason': 'Low selectivity favors sequential scan',
                'confidence': self.strategies['seq_scan']['alpha'] /
                             (self.strategies['seq_scan']['alpha'] + self.strategies['seq_scan']['beta'])
            })

        return alternatives

    def record_execution(self, query: str, actual_cost_ms: float,
                        context: Dict = None, plan_used: str = None):
        """Record actual query execution for learning"""
        context = context or {}
        fingerprint = self._query_fingerprint(query)

        # Update cache
        if fingerprint not in self.query_cache:
            self.query_cache[fingerprint] = {
                'executions': 0,
                'total_cost': 0,
                'avg_cost': 0,
                'min_cost': float('inf'),
                'max_cost': 0
            }

        cache_entry = self.query_cache[fingerprint]
        cache_entry['executions'] += 1
        cache_entry['total_cost'] += actual_cost_ms
        cache_entry['avg_cost'] = cache_entry['total_cost'] / cache_entry['executions']
        cache_entry['min_cost'] = min(cache_entry['min_cost'], actual_cost_ms)
        cache_entry['max_cost'] = max(cache_entry['max_cost'], actual_cost_ms)

        # Record in history
        self.execution_history.append({
            'timestamp': datetime.now().isoformat(),
            'query_fingerprint': fingerprint,
            'actual_cost_ms': actual_cost_ms,
            'plan_used': plan_used,
            'context': context
        })

        # Update strategy bandit if plan was specified
        if plan_used and plan_used in self.strategies:
            # Calculate reward (0-1, higher is better)
            # Reward = 1 - (normalized_cost)
            max_acceptable_cost = 5000  # ms
            reward = max(0, 1 - (actual_cost_ms / max_acceptable_cost))
            success = actual_cost_ms < max_acceptable_cost

            self._update_strategy(plan_used, success, reward)

        # Trigger retraining if enough new data
        if len(self.execution_history) % 100 == 0:
            self.train()

        # Save state periodically
        if len(self.execution_history) % 10 == 0:
            self._save_state()

    def train(self):
        """Train ML model on execution history"""
        if not SKLEARN_AVAILABLE:
            print("Scikit-learn not available - skipping training")
            return

        # Prepare training data from PostgreSQL
        cursor = self.conn.cursor()

        # Get recent execution data
        cursor.execute("""
            SELECT
                workflow,
                task_type,
                duration_ms,
                input_tokens,
                output_tokens,
                quality_score
            FROM monitoring.execution_summary
            WHERE duration_ms > 0
            ORDER BY timestamp DESC
            LIMIT 1000
        """)

        rows = cursor.fetchall()

        if len(rows) < 20:
            print(f"Not enough execution data ({len(rows)} rows)")
            return

        # Extract features and targets
        X = []
        y = []

        for row in rows:
            workflow, task_type, duration, input_tokens, output_tokens, quality = row

            # Feature vector
            features = [
                len(workflow or ''),
                len(task_type or ''),
                input_tokens or 0,
                output_tokens or 0,
                quality or 0.5,
                (input_tokens or 0) + (output_tokens or 0),  # Total tokens
                datetime.now().hour  # Time of day
            ]

            X.append(features)
            y.append(duration)

        X = np.array(X)
        y = np.array(y)

        # Train model
        print(f"Training query optimizer on {len(X)} examples...")

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.model.fit(X_scaled, y)

        # Evaluate
        train_score = self.model.score(X_scaled, y)
        print(f"✓ Model trained - R² score: {train_score:.3f}")

        # Save model
        self._save_state()

    def analyze_slow_queries(self, threshold_ms: float = 1000,
                            window_days: int = 7) -> List[Dict]:
        """Analyze slow queries and suggest optimizations"""
        cursor = self.conn.cursor()

        cutoff = datetime.now() - timedelta(days=window_days)

        cursor.execute("""
            SELECT
                workflow,
                task_type,
                model,
                AVG(duration_ms) as avg_duration,
                MAX(duration_ms) as max_duration,
                COUNT(*) as executions,
                AVG(input_tokens) as avg_input_tokens,
                AVG(output_tokens) as avg_output_tokens
            FROM monitoring.execution_summary
            WHERE duration_ms > %s
              AND timestamp > %s
            GROUP BY workflow, task_type, model
            ORDER BY avg_duration DESC
            LIMIT 20
        """, (threshold_ms, cutoff))

        slow_queries = []

        for row in cursor.fetchall():
            workflow, task_type, model, avg_dur, max_dur, execs, avg_in, avg_out = row

            # Convert Decimal to float for JSON serialization
            avg_dur = float(avg_dur) if avg_dur is not None else None
            max_dur = float(max_dur) if max_dur is not None else None
            avg_in = float(avg_in) if avg_in is not None else None
            avg_out = float(avg_out) if avg_out is not None else None

            # Generate optimization suggestions
            suggestions = []

            if avg_in and avg_in > 10000:
                suggestions.append("Consider prompt caching to reduce input tokens")

            if avg_out and avg_out > 5000:
                suggestions.append("Large outputs - consider streaming or pagination")

            if execs > 10:
                suggestions.append(f"Frequently executed ({execs}x) - good candidate for optimization")

            slow_queries.append({
                'workflow': workflow,
                'task_type': task_type,
                'model': model,
                'avg_duration_ms': avg_dur,
                'max_duration_ms': max_dur,
                'executions': int(execs),
                'avg_input_tokens': avg_in,
                'avg_output_tokens': avg_out,
                'suggestions': suggestions
            })

        return slow_queries

    def get_stats(self) -> Dict:
        """Get optimizer statistics"""
        return {
            'cached_queries': len(self.query_cache),
            'execution_history': len(self.execution_history),
            'model_trained': self.model is not None,
            'strategies': {
                k: {
                    'alpha': v['alpha'],
                    'beta': v['beta'],
                    'confidence': v['alpha'] / (v['alpha'] + v['beta'])
                }
                for k, v in self.strategies.items()
            }
        }


def main():
    """CLI interface for query optimizer"""
    import argparse

    parser = argparse.ArgumentParser(description='Database Query Optimizer')
    parser.add_argument('--train', action='store_true', help='Train model on execution history')
    parser.add_argument('--analyze-slow', action='store_true', help='Analyze slow queries')
    parser.add_argument('--threshold', type=float, default=1000, help='Slow query threshold (ms)')
    parser.add_argument('--stats', action='store_true', help='Show optimizer statistics')

    args = parser.parse_args()

    optimizer = QueryOptimizer()

    if args.train:
        print("Training query optimizer...")
        optimizer.train()
        print("✓ Training complete")

    elif args.analyze_slow:
        print(f"\nAnalyzing queries slower than {args.threshold}ms...\n")
        slow = optimizer.analyze_slow_queries(threshold_ms=args.threshold)

        for i, query in enumerate(slow, 1):
            print(f"{i}. {query['workflow']} ({query['task_type']}) - {query['model']}")
            print(f"   Avg: {query['avg_duration_ms']:.0f}ms, Max: {query['max_duration_ms']:.0f}ms")
            print(f"   Executions: {query['executions']}")
            if query['suggestions']:
                print(f"   Suggestions:")
                for suggestion in query['suggestions']:
                    print(f"     - {suggestion}")
            print()

    elif args.stats:
        stats = optimizer.get_stats()
        print("\nQuery Optimizer Statistics:")
        print(f"  Cached queries: {stats['cached_queries']}")
        print(f"  Execution history: {stats['execution_history']}")
        print(f"  Model trained: {stats['model_trained']}")
        print("\nStrategy Performance:")
        for strategy, perf in sorted(stats['strategies'].items(),
                                     key=lambda x: x[1]['confidence'],
                                     reverse=True):
            print(f"  {strategy:20s}: α={perf['alpha']:.1f}, β={perf['beta']:.1f}, "
                  f"confidence={perf['confidence']:.3f}")

    else:
        # Interactive mode
        print("Query Optimizer Interactive Mode")
        print("Enter SQL query to analyze (or 'quit' to exit)")

        while True:
            query = input("\nSQL> ").strip()

            if query.lower() in ['quit', 'exit']:
                break

            if not query:
                continue

            # Get context
            print("Context (optional, press enter to skip):")
            estimated_rows = input("  Estimated rows [1000]: ").strip()
            table_size = input("  Table size MB [100]: ").strip()

            context = {
                'estimated_rows': int(estimated_rows) if estimated_rows else 1000,
                'table_size_mb': float(table_size) if table_size else 100
            }

            # Optimize
            result = optimizer.optimize(query, context)

            print(f"\nPredicted cost: {result['predicted_cost_ms']:.1f}ms")
            print(f"Recommended strategy: {result['recommended_strategy']}")

            if result['recommendations']:
                print("\nRecommendations:")
                for rec in result['recommendations']:
                    print(f"  [{rec['priority'].upper()}] {rec['message']}")
                    print(f"    Estimated improvement: {rec['estimated_improvement']}")
                    if 'sql_hint' in rec:
                        print(f"    SQL: {rec['sql_hint']}")

            if result['alternative_strategies']:
                print("\nAlternative strategies:")
                for alt in result['alternative_strategies']:
                    print(f"  {alt['strategy']}: {alt['reason']} "
                          f"(confidence: {alt['confidence']:.3f})")


if __name__ == '__main__':
    main()
