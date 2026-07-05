#!/usr/bin/env python3
"""
Temporal Reasoning Trainer

Trains a Random Forest classifier to:
1. Understand temporal relationships (before/after/during/overlap)
2. Detect temporal constraints and dependencies
3. Plan sequences and schedules
4. Reason about causality and time
5. Handle temporal logic (Allen's interval algebra)
6. Identify temporal anomalies and conflicts
7. Optimize temporal resource allocation
8. Predict temporal patterns

Training data sources:
- Historical workflow executions (PostgreSQL)
- Scheduling patterns
- Temporal logic patterns
- Planning sequences
"""

import psycopg2
import numpy as np
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score
from collections import defaultdict

# Temporal reasoning knowledge base
TEMPORAL_PATTERNS = {
    'interval_relations': {
        # Allen's Interval Algebra - 13 possible relations
        'before': 'X finishes before Y starts',
        'meets': 'X finishes exactly when Y starts',
        'overlaps': 'X starts before Y, ends during Y',
        'finished_by': 'X and Y finish together, X starts first',
        'contains': 'X starts before Y and ends after Y',
        'starts': 'X and Y start together, X ends first',
        'equals': 'X and Y have same start and end',
        'started_by': 'X and Y start together, Y ends first',
        'during': 'X starts after Y and ends before Y',
        'finishes': 'X and Y finish together, Y starts first',
        'overlapped_by': 'Y starts before X, ends during X',
        'met_by': 'Y finishes exactly when X starts',
        'after': 'X starts after Y finishes'
    },
    'temporal_constraints': {
        'point_constraints': [
            'before_point', 'after_point', 'at_point',
            'not_before', 'not_after'
        ],
        'duration_constraints': [
            'minimum_duration', 'maximum_duration', 'exact_duration',
            'duration_range', 'flexible_duration'
        ],
        'dependency_constraints': [
            'finish_to_start', 'start_to_start', 'finish_to_finish',
            'start_to_finish', 'lag_constraint', 'lead_constraint'
        ],
        'resource_constraints': [
            'sequential_access', 'parallel_access', 'mutex',
            'capacity_limit', 'time_window'
        ]
    },
    'planning_types': {
        'classical_planning': [
            'state_space_search', 'forward_search', 'backward_search',
            'heuristic_search', 'graphplan', 'strips'
        ],
        'temporal_planning': [
            'simple_temporal_network', 'temporal_constraint_network',
            'partial_order_planning', 'timeline_planning',
            'reactive_planning', 'continuous_planning'
        ],
        'scheduling': [
            'job_shop_scheduling', 'flow_shop_scheduling',
            'resource_constrained_scheduling', 'priority_scheduling',
            'critical_path_method', 'earliest_deadline_first',
            'rate_monotonic_scheduling'
        ],
        'multi_agent_planning': [
            'distributed_planning', 'cooperative_planning',
            'coordination_planning', 'negotiation_based',
            'auction_based', 'contract_net'
        ]
    },
    'temporal_logic': {
        'linear_temporal_logic': [
            'next', 'eventually', 'always', 'until', 'release',
            'weak_until', 'strong_release'
        ],
        'computation_tree_logic': [
            'exists_next', 'always_next', 'exists_eventually',
            'always_eventually', 'exists_always', 'always_always'
        ],
        'metric_temporal_logic': [
            'bounded_eventually', 'bounded_always',
            'timed_until', 'timed_release',
            'time_constrained_next'
        ],
        'interval_temporal_logic': [
            'chop', 'star', 'begin', 'end', 'length',
            'subset', 'overlap_interval'
        ]
    },
    'temporal_patterns': {
        'periodic_patterns': [
            'fixed_period', 'variable_period', 'cron_pattern',
            'seasonal', 'cyclic', 'oscillating'
        ],
        'sequential_patterns': [
            'strictly_sequential', 'partial_order', 'dag_sequence',
            'tree_sequence', 'graph_sequence'
        ],
        'concurrent_patterns': [
            'fully_parallel', 'fork_join', 'pipeline',
            'map_reduce', 'scatter_gather', 'barrier_sync'
        ],
        'temporal_anomalies': [
            'time_travel', 'causality_violation', 'temporal_loop',
            'deadlock', 'livelock', 'race_condition',
            'ordering_violation', 'timing_violation'
        ]
    },
    'time_representations': {
        'point_based': [
            'instant', 'timestamp', 'event_time', 'clock_time',
            'logical_time', 'vector_clock', 'lamport_clock'
        ],
        'interval_based': [
            'duration', 'time_span', 'time_window', 'epoch',
            'period', 'phase', 'session'
        ],
        'relative_time': [
            'before_after', 'simultaneous', 'overlapping',
            'contained', 'adjacent', 'distant'
        ],
        'granularity': [
            'microsecond', 'millisecond', 'second', 'minute',
            'hour', 'day', 'week', 'month', 'quarter', 'year',
            'decade', 'century'
        ]
    }
}

# Temporal reasoning training examples
TEMPORAL_TRAINING_DATA = {
    'interval_reasoning': [
        # (description, interval_relation, complexity)
        ('Task A must complete before Task B starts', 'before', 'simple'),
        ('Meeting ends exactly when presentation starts', 'meets', 'simple'),
        ('Project phase 1 overlaps with phase 2', 'overlaps', 'simple'),
        ('Both workflows finish together', 'finished_by', 'simple'),
        ('Training period contains evaluation period', 'contains', 'simple'),
        ('Process A and B start together', 'starts', 'simple'),
        ('Deployment window equals maintenance window', 'equals', 'simple'),
        ('Task starts after dependency completes', 'after', 'simple'),
        ('Sprint planning during sprint execution', 'during', 'medium'),
        ('Multiple overlapping time windows', 'overlaps', 'complex'),
        ('Cascading dependencies with lag times', 'before', 'complex'),
        ('Parallel workflows with synchronization points', 'meets', 'complex'),
    ],
    'constraint_satisfaction': [
        # (description, constraint_type, feasibility)
        ('Task must complete before deadline', 'deadline', 'feasible'),
        ('Minimum 2 hour gap between executions', 'minimum_gap', 'feasible'),
        ('Resource available only 9-5 weekdays', 'time_window', 'feasible'),
        ('Tasks A, B, C must be sequential', 'ordering', 'feasible'),
        ('Maximum 4 concurrent processes', 'capacity', 'feasible'),
        ('Finish A before starting B and C', 'dependency', 'feasible'),
        ('Task duration between 1-3 hours', 'duration_range', 'feasible'),
        ('Conflicting time window requirements', 'time_window', 'infeasible'),
        ('Circular dependency A→B→C→A', 'ordering', 'infeasible'),
        ('Over-constrained scheduling problem', 'mixed', 'infeasible'),
        ('Deadline before minimum duration', 'deadline', 'infeasible'),
    ],
    'planning_scenarios': [
        # (description, planning_type, difficulty)
        ('Schedule 5 sequential tasks', 'simple_sequence', 'easy'),
        ('Allocate 3 resources to 7 tasks', 'resource_allocation', 'easy'),
        ('Find shortest path in workflow DAG', 'pathfinding', 'easy'),
        ('Optimize parallel execution order', 'parallelization', 'medium'),
        ('Balance load across time windows', 'load_balancing', 'medium'),
        ('Plan with uncertainty and contingencies', 'robust_planning', 'hard'),
        ('Multi-objective optimization (time, cost, quality)', 'multi_objective', 'hard'),
        ('Dynamic replanning with new constraints', 'reactive_planning', 'hard'),
        ('Distributed planning across agents', 'multi_agent', 'very_hard'),
        ('Real-time scheduling with deadlines', 'real_time', 'very_hard'),
    ],
    'temporal_logic_queries': [
        # (query, logic_type, result)
        ('Will task eventually complete?', 'eventually', 'true'),
        ('Is resource always available?', 'always', 'false'),
        ('Does A happen before B?', 'ordering', 'true'),
        ('Can deadlock occur?', 'safety', 'false'),
        ('Will system reach goal state?', 'reachability', 'true'),
        ('Is schedule conflict-free?', 'consistency', 'true'),
        ('Does execution violate timing?', 'violation', 'false'),
        ('Will resource be freed eventually?', 'liveness', 'true'),
        ('Is there a path to completion?', 'existential', 'true'),
        ('Must all paths succeed?', 'universal', 'false'),
    ],
    'pattern_detection': [
        # (description, pattern_type, confidence)
        ('Task runs every hour', 'periodic', 'high'),
        ('Workflow follows A→B→C', 'sequential', 'high'),
        ('Peak usage on weekdays 9-5', 'temporal_pattern', 'high'),
        ('Batch jobs run overnight', 'scheduled', 'high'),
        ('Error rate spikes every Monday', 'periodic_anomaly', 'medium'),
        ('Gradual performance degradation', 'trend', 'medium'),
        ('Random sporadic failures', 'stochastic', 'low'),
        ('Cascading failure pattern', 'causal_chain', 'high'),
        ('Seasonal variation detected', 'seasonal', 'medium'),
        ('Cyclic behavior with drift', 'cyclic_drift', 'medium'),
    ],
    'causality_temporal': [
        # (description, causal_relation, temporal_relation)
        ('Error causes job failure 5 min later', 'causal', 'delayed_effect'),
        ('Timeout triggers retry', 'causal', 'immediate'),
        ('Load increase precedes slowdown', 'causal', 'leading_indicator'),
        ('Deployment correlates with errors', 'correlation', 'coincident'),
        ('Restart fixes issue temporarily', 'causal', 'temporary_effect'),
        ('Configuration change causes instability', 'causal', 'persistent_effect'),
        ('Two events coincide but unrelated', 'spurious', 'coincident'),
        ('Feedback loop creates oscillation', 'causal', 'cyclic'),
        ('Preventive action blocks failure', 'causal', 'counterfactual'),
        ('Root cause identified upstream', 'causal', 'distant_cause'),
    ]
}

# Feature extraction patterns
FEATURE_PATTERNS = {
    'temporal_keywords': [
        'before', 'after', 'during', 'while', 'when', 'until', 'since',
        'always', 'eventually', 'never', 'sometimes', 'often', 'rarely',
        'immediately', 'delayed', 'scheduled', 'periodic', 'continuous',
        'sequential', 'parallel', 'concurrent', 'simultaneous', 'overlapping',
        'deadline', 'timeout', 'duration', 'interval', 'period', 'phase',
        'start', 'end', 'begin', 'finish', 'complete', 'terminate',
        'wait', 'delay', 'lag', 'lead', 'gap', 'window', 'span',
        'early', 'late', 'on-time', 'overdue', 'ahead', 'behind'
    ],
    'planning_keywords': [
        'schedule', 'plan', 'allocate', 'assign', 'distribute', 'arrange',
        'optimize', 'minimize', 'maximize', 'balance', 'prioritize',
        'order', 'sequence', 'rank', 'sort', 'organize',
        'coordinate', 'synchronize', 'align', 'orchestrate',
        'resource', 'capacity', 'constraint', 'requirement', 'goal',
        'dependency', 'prerequisite', 'successor', 'predecessor',
        'critical-path', 'bottleneck', 'slack', 'float', 'buffer'
    ],
    'constraint_keywords': [
        'must', 'cannot', 'required', 'forbidden', 'mandatory', 'optional',
        'minimum', 'maximum', 'exactly', 'at-most', 'at-least',
        'within', 'outside', 'between', 'range', 'limit', 'bound',
        'violate', 'satisfy', 'conflict', 'compatible', 'feasible',
        'impossible', 'possible', 'allowed', 'prohibited'
    ],
    'causality_keywords': [
        'cause', 'effect', 'result', 'consequence', 'impact', 'influence',
        'trigger', 'activate', 'enable', 'disable', 'block', 'prevent',
        'lead-to', 'result-in', 'due-to', 'because', 'therefore',
        'precondition', 'postcondition', 'invariant', 'assumption'
    ]
}

class TemporalReasoningTrainer:
    def __init__(self):
        self.db_config = {
            'dbname': 'learning',
            'user': 'claude',
            'host': 'aio-01',
            'port': 5433
        }
        self.model = None
        self.vectorizer = None
        self.feature_names = []
        self.training_stats = {
            'total_examples': 0,
            'training_accuracy': 0.0,
            'test_accuracy': 0.0,
            'f1_score': 0.0,
            'feature_importance': {},
            'patterns_learned': {},
            'timestamp': None
        }

    def get_db_connection(self):
        """Connect to PostgreSQL learning database"""
        return psycopg2.connect(**self.db_config)

    def extract_temporal_features(self, text):
        """Extract temporal reasoning features from text"""
        features = {}
        text_lower = text.lower()

        # Count temporal keywords
        for keyword in FEATURE_PATTERNS['temporal_keywords']:
            features[f'temporal_{keyword}'] = text_lower.count(keyword)

        # Count planning keywords
        for keyword in FEATURE_PATTERNS['planning_keywords']:
            features[f'planning_{keyword}'] = text_lower.count(keyword)

        # Count constraint keywords
        for keyword in FEATURE_PATTERNS['constraint_keywords']:
            features[f'constraint_{keyword}'] = text_lower.count(keyword)

        # Count causality keywords
        for keyword in FEATURE_PATTERNS['causality_keywords']:
            features[f'causality_{keyword}'] = text_lower.count(keyword)

        # Temporal complexity indicators
        features['has_multiple_timescales'] = int(
            sum(1 for t in ['second', 'minute', 'hour', 'day', 'week', 'month']
                if t in text_lower) > 1
        )
        features['has_dependencies'] = int(
            any(dep in text_lower for dep in ['depend', 'require', 'need', 'must'])
        )
        features['has_concurrency'] = int(
            any(conc in text_lower for conc in ['parallel', 'concurrent', 'simultaneous'])
        )
        features['has_deadlines'] = int(
            any(dl in text_lower for dl in ['deadline', 'due', 'by', 'before'])
        )

        # Interval algebra indicators
        features['interval_relation_count'] = sum(
            1 for rel in TEMPORAL_PATTERNS['interval_relations'].keys()
            if rel.replace('_', ' ') in text_lower
        )

        # Planning complexity
        features['has_optimization'] = int(
            any(opt in text_lower for opt in ['optimize', 'minimize', 'maximize', 'best'])
        )
        features['has_multi_objective'] = int(
            sum(1 for obj in ['time', 'cost', 'quality', 'resource']
                if obj in text_lower) > 1
        )

        return features

    def generate_training_data(self):
        """Generate comprehensive training dataset"""
        X_text = []
        y_labels = []

        print("Generating training data from temporal patterns...")

        # Interval reasoning examples
        for desc, relation, complexity in TEMPORAL_TRAINING_DATA['interval_reasoning']:
            X_text.append(desc)
            y_labels.append(f'interval_{relation}_{complexity}')

        # Constraint satisfaction examples
        for desc, constraint_type, feasibility in TEMPORAL_TRAINING_DATA['constraint_satisfaction']:
            X_text.append(desc)
            y_labels.append(f'constraint_{constraint_type}_{feasibility}')

        # Planning scenario examples
        for desc, planning_type, difficulty in TEMPORAL_TRAINING_DATA['planning_scenarios']:
            X_text.append(desc)
            y_labels.append(f'planning_{planning_type}_{difficulty}')

        # Temporal logic query examples
        for query, logic_type, result in TEMPORAL_TRAINING_DATA['temporal_logic_queries']:
            X_text.append(query)
            y_labels.append(f'logic_{logic_type}_{result}')

        # Pattern detection examples
        for desc, pattern_type, confidence in TEMPORAL_TRAINING_DATA['pattern_detection']:
            X_text.append(desc)
            y_labels.append(f'pattern_{pattern_type}_{confidence}')

        # Causality-temporal examples
        for desc, causal_relation, temporal_relation in TEMPORAL_TRAINING_DATA['causality_temporal']:
            X_text.append(desc)
            y_labels.append(f'causal_{causal_relation}_{temporal_relation}')

        # Add synthetic variations
        X_text_augmented = []
        y_labels_augmented = []

        for text, label in zip(X_text, y_labels):
            X_text_augmented.append(text)
            y_labels_augmented.append(label)

            # Add variations with different phrasings
            variations = self.generate_variations(text, label)
            X_text_augmented.extend(variations['texts'])
            y_labels_augmented.extend(variations['labels'])

        return X_text_augmented, y_labels_augmented

    def generate_variations(self, text, label):
        """Generate variations of training examples"""
        variations = {'texts': [], 'labels': []}

        # Simple paraphrasing patterns
        replacements = {
            'task': ['job', 'process', 'operation', 'activity', 'work item'],
            'complete': ['finish', 'end', 'conclude', 'finalize'],
            'start': ['begin', 'initiate', 'commence', 'launch'],
            'before': ['prior to', 'ahead of', 'preceding'],
            'after': ['following', 'subsequent to', 'later than'],
            'must': ['should', 'needs to', 'has to', 'required to'],
        }

        text_lower = text.lower()
        # Generate multiple variations per example for better coverage
        for original, alternatives in replacements.items():
            if original in text_lower:
                for alt in alternatives[:3]:  # Use first 3 alternatives
                    new_text = text_lower.replace(original, alt)
                    variations['texts'].append(new_text)
                    variations['labels'].append(label)

        # Add at least 2 variations per example to avoid single-class issues
        if len(variations['texts']) < 2:
            # Fallback: simple word order changes
            variations['texts'].append(text.lower())
            variations['labels'].append(label)
            variations['texts'].append(text.title())
            variations['labels'].append(label)

        return variations

    def load_historical_data(self):
        """Load historical workflow execution data"""
        X_text = []
        y_labels = []

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Query workflow execution patterns
            cursor.execute("""
                SELECT
                    workflow_name,
                    task_description,
                    total_duration_ms,
                    outcome,
                    created_at
                FROM workflow.executions
                WHERE created_at > NOW() - INTERVAL '30 days'
                ORDER BY created_at DESC
                LIMIT 1000
            """)

            for row in cursor.fetchall():
                workflow_name, task_desc, duration_ms, outcome, timestamp = row

                # Create temporal description
                desc = f"{workflow_name}: {task_desc} (duration: {duration_ms}ms, outcome: {outcome})"
                X_text.append(desc)

                # Classify based on duration and outcome
                if duration_ms < 5000:
                    label = f'planning_fast_{outcome}'
                elif duration_ms < 30000:
                    label = f'planning_medium_{outcome}'
                else:
                    label = f'planning_slow_{outcome}'

                y_labels.append(label)

            # Query phase execution patterns
            cursor.execute("""
                SELECT
                    phase_name,
                    phase_order,
                    duration_ms,
                    outcome
                FROM workflow.phases
                WHERE created_at > NOW() - INTERVAL '30 days'
                ORDER BY created_at DESC
                LIMIT 500
            """)

            for row in cursor.fetchall():
                phase_name, phase_order, duration_ms, outcome = row
                desc = f"Phase {phase_order}: {phase_name} (duration: {duration_ms}ms)"
                X_text.append(desc)
                y_labels.append(f'interval_sequential_{outcome}')

            cursor.close()
            conn.close()

            print(f"Loaded {len(X_text)} historical examples")

        except Exception as e:
            print(f"Warning: Could not load historical data: {e}")
            print("Continuing with synthetic data only")

        return X_text, y_labels

    def train(self):
        """Train the temporal reasoning model"""
        print("=" * 80)
        print("TEMPORAL REASONING TRAINER")
        print("=" * 80)

        # Generate synthetic training data
        X_synthetic, y_synthetic = self.generate_training_data()
        print(f"Generated {len(X_synthetic)} synthetic examples")

        # Load historical data
        X_historical, y_historical = self.load_historical_data()

        # Combine datasets
        X_text = X_synthetic + X_historical
        y_labels = y_synthetic + y_historical

        print(f"\nTotal training examples: {len(X_text)}")
        self.training_stats['total_examples'] = len(X_text)

        # Vectorize text using TF-IDF
        print("\nVectorizing text features...")
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 3),
            min_df=2,
            max_df=0.8
        )
        X_tfidf = self.vectorizer.fit_transform(X_text)

        # Extract custom temporal features
        print("Extracting temporal features...")
        X_custom_list = [self.extract_temporal_features(text) for text in X_text]

        # Get all feature names
        all_feature_names = set()
        for features in X_custom_list:
            all_feature_names.update(features.keys())
        all_feature_names = sorted(all_feature_names)
        self.feature_names = all_feature_names

        # Convert to numpy array
        X_custom = np.zeros((len(X_text), len(all_feature_names)))
        for i, features in enumerate(X_custom_list):
            for j, fname in enumerate(all_feature_names):
                X_custom[i, j] = features.get(fname, 0)

        # Combine TF-IDF and custom features
        X_combined = np.hstack([X_tfidf.toarray(), X_custom])

        print(f"Feature dimensions: TF-IDF={X_tfidf.shape[1]}, Custom={X_custom.shape[1]}, Total={X_combined.shape[1]}")

        # Split train/test (no stratify to handle single-example classes)
        X_train, X_test, y_train, y_test = train_test_split(
            X_combined, y_labels, test_size=0.2, random_state=42
        )

        print(f"\nTraining set: {len(X_train)} examples")
        print(f"Test set: {len(X_test)} examples")

        # Train Random Forest
        print("\nTraining Random Forest classifier...")
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=30,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        )

        self.model.fit(X_train, y_train)

        # Evaluate
        print("\n" + "=" * 80)
        print("EVALUATION RESULTS")
        print("=" * 80)

        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)

        train_acc = accuracy_score(y_train, y_train_pred)
        test_acc = accuracy_score(y_test, y_test_pred)
        f1 = f1_score(y_test, y_test_pred, average='weighted')

        print(f"\nTraining Accuracy: {train_acc:.3f}")
        print(f"Test Accuracy: {test_acc:.3f}")
        print(f"F1 Score (weighted): {f1:.3f}")

        self.training_stats['training_accuracy'] = train_acc
        self.training_stats['test_accuracy'] = test_acc
        self.training_stats['f1_score'] = f1
        self.training_stats['timestamp'] = datetime.now().isoformat()

        # Feature importance
        print("\n" + "=" * 80)
        print("TOP 20 MOST IMPORTANT FEATURES")
        print("=" * 80)

        feature_names_combined = (
            list(self.vectorizer.get_feature_names_out()) +
            self.feature_names
        )

        importances = self.model.feature_importances_
        indices = np.argsort(importances)[::-1]

        for i in range(min(20, len(indices))):
            idx = indices[i]
            fname = feature_names_combined[idx]
            importance = importances[idx]
            print(f"{i+1:2d}. {fname:50s} {importance:.4f}")
            self.training_stats['feature_importance'][fname] = float(importance)

        # Pattern statistics
        print("\n" + "=" * 80)
        print("LEARNED PATTERN DISTRIBUTION")
        print("=" * 80)

        pattern_counts = defaultdict(int)
        for label in y_labels:
            pattern_type = label.split('_')[0]
            pattern_counts[pattern_type] += 1

        for pattern_type, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = 100.0 * count / len(y_labels)
            print(f"{pattern_type:20s}: {count:4d} ({percentage:5.1f}%)")
            self.training_stats['patterns_learned'][pattern_type] = count

        print("\n" + "=" * 80)
        print("CLASSIFICATION REPORT")
        print("=" * 80)
        print(classification_report(y_test, y_test_pred, zero_division=0))

        return self.model

    def save_model(self, base_path='/home/sfloess/.claude/learning'):
        """Save trained model and stats"""
        base_path = Path(base_path)
        base_path.mkdir(parents=True, exist_ok=True)

        # Save model
        model_file = base_path / 'temporal_reasoning_model.pkl'
        with open(model_file, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'vectorizer': self.vectorizer,
                'feature_names': self.feature_names,
                'patterns': TEMPORAL_PATTERNS,
                'training_stats': self.training_stats
            }, f)

        print(f"\nModel saved to: {model_file}")

        # Save stats
        stats_file = base_path / 'temporal_reasoning_stats.json'
        with open(stats_file, 'w') as f:
            json.dump(self.training_stats, f, indent=2)

        print(f"Statistics saved to: {stats_file}")

        return str(model_file)

    def predict(self, text):
        """Predict temporal reasoning classification for new text"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # Vectorize
        X_tfidf = self.vectorizer.transform([text])

        # Extract custom features
        custom_features = self.extract_temporal_features(text)
        X_custom = np.zeros((1, len(self.feature_names)))
        for j, fname in enumerate(self.feature_names):
            X_custom[0, j] = custom_features.get(fname, 0)

        # Combine
        X_combined = np.hstack([X_tfidf.toarray(), X_custom])

        # Predict
        prediction = self.model.predict(X_combined)[0]
        probabilities = self.model.predict_proba(X_combined)[0]
        confidence = max(probabilities)

        return {
            'prediction': prediction,
            'confidence': confidence,
            'top_classes': self.model.classes_[np.argsort(probabilities)[::-1][:5]].tolist(),
            'top_probabilities': sorted(probabilities, reverse=True)[:5]
        }

def main():
    """Main training function"""
    trainer = TemporalReasoningTrainer()

    # Train model
    model = trainer.train()

    # Save model
    model_path = trainer.save_model()

    # Test predictions
    print("\n" + "=" * 80)
    print("EXAMPLE PREDICTIONS")
    print("=" * 80)

    test_examples = [
        "Schedule 5 tasks to run sequentially with minimum 10 minute gaps",
        "Task A must complete before Task B starts",
        "Optimize parallel execution of independent workflows",
        "Detect temporal anomaly in periodic job schedule",
        "Plan resource allocation with deadline constraints",
    ]

    for example in test_examples:
        result = trainer.predict(example)
        print(f"\nInput: {example}")
        print(f"Prediction: {result['prediction']}")
        print(f"Confidence: {result['confidence']:.3f}")
        print(f"Top alternatives: {', '.join(result['top_classes'][:3])}")

    print("\n" + "=" * 80)
    print(f"TRAINING COMPLETE - Model saved to: {model_path}")
    print("=" * 80)

    return model_path

if __name__ == '__main__':
    main()
