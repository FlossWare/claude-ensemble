#!/usr/bin/env python3
"""
Developer Preference Learner

Learns which models/strategies the developer prefers for different task types
based on historical workflow execution data.

Uses contextual Thompson Sampling (LinUCB) to balance exploration/exploitation.
"""

import psycopg2
import numpy as np
import json
import pickle
from collections import defaultdict
from datetime import datetime
from pathlib import Path

def get_db():
    """Connect to PostgreSQL learning database"""
    return psycopg2.connect(
        host='aio-01',
        port=5433,
        user='sfloess',
        database='learning'
    )

class DeveloperPreferenceLearner:
    """
    Contextual bandit for learning developer preferences.

    Maps: task context → preferred model
    Based on: historical success rates, confidence scores, execution time
    """

    def __init__(self, num_models, context_dim=15, alpha=0.5):
        """
        Initialize preference learner.

        Args:
            num_models: Number of available models
            context_dim: Dimension of context feature vector
            alpha: Exploration parameter (0.0 = pure exploitation, 1.0+ = more exploration)
        """
        self.num_models = num_models
        self.context_dim = context_dim
        self.alpha = alpha

        # LinUCB parameters (one set per model)
        # A: context covariance matrix
        # b: reward-weighted context vector
        self.A = [np.identity(context_dim) for _ in range(num_models)]
        self.b = [np.zeros(context_dim) for _ in range(num_models)]

        # Track statistics
        self.total_selections = defaultdict(int)
        self.successful_selections = defaultdict(int)

    def get_theta(self, model_id):
        """Compute parameter vector for model"""
        try:
            A_inv = np.linalg.inv(self.A[model_id])
            return A_inv.dot(self.b[model_id])
        except np.linalg.LinAlgError:
            # Matrix is singular, return zeros
            return np.zeros(self.context_dim)

    def select_model(self, context, return_scores=False):
        """
        Select best model for given context using Upper Confidence Bound.

        Args:
            context: Feature vector describing the task
            return_scores: If True, return (model_id, ucb_scores, confidence_intervals)

        Returns:
            model_id: Index of selected model
            (optional) ucb_scores: UCB score for each model
            (optional) confidence_intervals: Confidence interval widths
        """
        context = np.array(context).flatten()
        if len(context) != self.context_dim:
            raise ValueError(f"Context dimension mismatch: expected {self.context_dim}, got {len(context)}")

        ucb_scores = []
        confidence_intervals = []

        for i in range(self.num_models):
            theta = self.get_theta(i)

            try:
                A_inv = np.linalg.inv(self.A[i])
            except np.linalg.LinAlgError:
                # Singular matrix, use identity
                A_inv = np.identity(self.context_dim)

            # Expected reward
            expected_reward = theta.dot(context)

            # Exploration bonus (uncertainty)
            uncertainty = np.sqrt(context.dot(A_inv).dot(context))
            confidence_interval = self.alpha * uncertainty

            # UCB = expected reward + exploration bonus
            ucb = expected_reward + confidence_interval

            ucb_scores.append(ucb)
            confidence_intervals.append(confidence_interval)

        best_model = int(np.argmax(ucb_scores))

        if return_scores:
            return best_model, ucb_scores, confidence_intervals
        return best_model

    def update(self, model_id, context, reward):
        """
        Update model parameters after observing reward.

        Args:
            model_id: Index of selected model
            context: Feature vector for the task
            reward: Observed reward (0.0-1.0)
        """
        context = np.array(context).flatten()

        # Update covariance matrix
        self.A[model_id] += np.outer(context, context)

        # Update reward-weighted context
        self.b[model_id] += reward * context

        # Track statistics
        self.total_selections[model_id] += 1
        if reward > 0.7:  # Consider > 0.7 as success
            self.successful_selections[model_id] += 1

    def get_statistics(self):
        """Get model selection statistics"""
        stats = {}
        for model_id in range(self.num_models):
            total = self.total_selections.get(model_id, 0)
            success = self.successful_selections.get(model_id, 0)
            success_rate = success / total if total > 0 else 0.0

            stats[model_id] = {
                'total_selections': total,
                'successful_selections': success,
                'success_rate': success_rate
            }

        return stats

    def save(self, filepath):
        """Save model to disk (pickle format for numpy arrays)"""
        state = {
            'num_models': self.num_models,
            'context_dim': self.context_dim,
            'alpha': self.alpha,
            'A': self.A,
            'b': self.b,
            'total_selections': dict(self.total_selections),
            'successful_selections': dict(self.successful_selections)
        }

        with open(filepath, 'wb') as f:
            pickle.dump(state, f)

    @classmethod
    def load(cls, filepath):
        """Load model from disk"""
        with open(filepath, 'rb') as f:
            state = pickle.load(f)

        learner = cls(state['num_models'], state['context_dim'], state['alpha'])
        learner.A = state['A']
        learner.b = state['b']
        learner.total_selections = defaultdict(int, state.get('total_selections', {}))
        learner.successful_selections = defaultdict(int, state.get('successful_selections', {}))

        return learner

def extract_task_context(task_description, workflow_name=None):
    """
    Extract context features from task description and workflow.

    Features:
    - Task type indicators (code, review, fix, research, test, deploy, etc.)
    - Complexity indicators (length, has code blocks, mentions files)
    - Domain indicators (Java, Python, JavaScript, database, API, etc.)

    Returns:
        15-dimensional feature vector
    """
    task_lower = task_description.lower() if task_description else ""
    workflow_lower = workflow_name.lower() if workflow_name else ""

    # Task type features (one-hot style)
    is_code = 1.0 if any(kw in task_lower for kw in ['implement', 'write', 'create', 'code', 'develop']) else 0.0
    is_review = 1.0 if any(kw in task_lower for kw in ['review', 'analyze', 'check', 'audit']) else 0.0
    is_fix = 1.0 if any(kw in task_lower for kw in ['fix', 'bug', 'issue', 'error', 'problem']) else 0.0
    is_research = 1.0 if any(kw in task_lower for kw in ['research', 'find', 'search', 'investigate']) else 0.0
    is_test = 1.0 if any(kw in task_lower for kw in ['test', 'unit test', 'integration test']) else 0.0
    is_deploy = 1.0 if any(kw in task_lower for kw in ['deploy', 'release', 'publish']) else 0.0

    # Complexity features
    prompt_length = min(len(task_description) / 1000.0, 5.0) if task_description else 0.0  # Normalize, cap at 5
    has_code_block = 1.0 if '```' in task_description else 0.0
    mentions_file = 1.0 if any(ext in task_lower for ext in ['.py', '.java', '.js', '.ts', '.go', 'file']) else 0.0

    # Domain features
    is_java = 1.0 if any(kw in task_lower for kw in ['java', '.java', 'salesforce']) else 0.0
    is_python = 1.0 if any(kw in task_lower for kw in ['python', '.py', 'pip']) else 0.0
    is_javascript = 1.0 if any(kw in task_lower for kw in ['javascript', '.js', '.ts', 'node', 'npm']) else 0.0
    is_database = 1.0 if any(kw in task_lower for kw in ['database', 'sql', 'postgres', 'db']) else 0.0
    is_api = 1.0 if any(kw in task_lower for kw in ['api', 'rest', 'graphql', 'endpoint']) else 0.0

    # Workflow context
    is_orchestrator = 1.0 if workflow_lower and 'orchestrator' in workflow_lower else 0.0

    return [
        is_code,
        is_review,
        is_fix,
        is_research,
        is_test,
        is_deploy,
        prompt_length,
        has_code_block,
        mentions_file,
        is_java,
        is_python,
        is_javascript,
        is_database,
        is_api,
        is_orchestrator
    ]

def train_developer_preference_learner(verbose=True):
    """
    Train developer preference learner from historical workflow data.

    Returns:
        dict with learner, model_mapping, and statistics
    """
    db = get_db()
    cursor = db.cursor()

    if verbose:
        print("=== Developer Preference Learner Training ===\n")

    # Get actual LLM models (filter out strategy names)
    cursor.execute("""
        SELECT DISTINCT wr.model
        FROM workflow.worker_results wr
        WHERE wr.outcome IN ('success', 'error')
          AND wr.confidence IS NOT NULL
          AND wr.model NOT IN ('Epsilon-greedy exploration with 30% exploration rate', 'LinUCB')
          AND wr.model NOT LIKE '%exploration%'
          AND wr.model NOT LIKE '%UCB%'
        ORDER BY wr.model
    """)

    models = [row[0] for row in cursor.fetchall()]
    model_to_id = {m: i for i, m in enumerate(models)}

    if verbose:
        print(f"Available models: {len(models)}")
        for i, m in enumerate(models):
            print(f"  {i}: {m}")

    # Load training data
    cursor.execute("""
        SELECT
            wr.task_assigned,
            we.workflow_name,
            wr.model,
            wr.confidence,
            wr.outcome,
            wr.duration_ms,
            wr.cost_usd
        FROM workflow.worker_results wr
        JOIN workflow.executions we ON wr.workflow_execution_id = we.id
        WHERE wr.outcome IN ('success', 'error')
          AND wr.task_assigned IS NOT NULL
          AND wr.confidence IS NOT NULL
          AND wr.model IN (%s)
        ORDER BY we.created_at
    """ % ','.join(['%s'] * len(models)), models)

    records = cursor.fetchall()

    if verbose:
        print(f"\nTraining records: {len(records)}")

    if len(records) == 0:
        print("ERROR: No training data available!")
        return None

    # Initialize learner
    context_dim = 15
    learner = DeveloperPreferenceLearner(
        num_models=len(models),
        context_dim=context_dim,
        alpha=0.5  # Balanced exploration/exploitation
    )

    # Split into train/test
    split_idx = int(len(records) * 0.8)
    train_records = records[:split_idx]
    test_records = records[split_idx:]

    # Training
    total_reward = 0.0

    if verbose:
        print(f"\nTraining on {len(train_records)} records...")

    for task, workflow, model, confidence, outcome, duration, cost in train_records:
        if model not in model_to_id:
            continue

        context = extract_task_context(task, workflow)
        model_id = model_to_id[model]

        # Calculate reward
        if outcome == 'success' and confidence:
            reward = float(confidence)

            # Bonus for fast execution (< 5 seconds)
            if duration and duration < 5000:
                reward = min(1.0, reward * 1.05)

            # Bonus for low cost (< $0.01)
            if cost and cost < 0.01:
                reward = min(1.0, reward * 1.02)
        else:
            reward = 0.0

        learner.update(model_id, context, reward)
        total_reward += reward

    avg_reward_train = total_reward / len(train_records) if train_records else 0

    # Testing
    test_correct = 0
    test_total = 0
    test_rewards = []

    if verbose:
        print(f"Testing on {len(test_records)} records...")

    for task, workflow, actual_model, confidence, outcome, duration, cost in test_records:
        if actual_model not in model_to_id:
            continue

        context = extract_task_context(task, workflow)
        predicted_id = learner.select_model(context)

        actual_id = model_to_id[actual_model]

        if predicted_id == actual_id:
            test_correct += 1

        # Calculate what reward we would have gotten
        if outcome == 'success' and confidence:
            test_rewards.append(float(confidence))
        else:
            test_rewards.append(0.0)

        test_total += 1

    test_accuracy = test_correct / test_total if test_total > 0 else 0
    avg_test_reward = sum(test_rewards) / len(test_rewards) if test_rewards else 0

    # Save model
    model_path = Path.home() / '.claude' / 'learning' / 'developer_preference_learner.pkl'
    learner.save(model_path)

    # Save mapping
    mapping_path = Path.home() / '.claude' / 'learning' / 'developer_preference_mapping.json'
    mapping = {
        'models': models,
        'model_to_id': model_to_id,
        'context_dim': context_dim,
        'context_features': [
            'is_code', 'is_review', 'is_fix', 'is_research', 'is_test', 'is_deploy',
            'prompt_length', 'has_code_block', 'mentions_file',
            'is_java', 'is_python', 'is_javascript', 'is_database', 'is_api',
            'is_orchestrator'
        ],
        'trained_at': datetime.now().isoformat(),
        'training_records': len(train_records),
        'test_accuracy': test_accuracy,
        'avg_train_reward': avg_reward_train,
        'avg_test_reward': avg_test_reward
    }

    with open(mapping_path, 'w') as f:
        json.dump(mapping, f, indent=2)

    # Save statistics to PostgreSQL
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning.preference_learner_stats (
            model_name VARCHAR PRIMARY KEY,
            num_models INTEGER,
            context_dim INTEGER,
            alpha FLOAT,
            training_records INTEGER,
            test_accuracy FLOAT,
            avg_train_reward FLOAT,
            avg_test_reward FLOAT,
            model_path VARCHAR,
            trained_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("""
        INSERT INTO learning.preference_learner_stats
        (model_name, num_models, context_dim, alpha, training_records,
         test_accuracy, avg_train_reward, avg_test_reward, model_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (model_name) DO UPDATE SET
            training_records = EXCLUDED.training_records,
            test_accuracy = EXCLUDED.test_accuracy,
            avg_train_reward = EXCLUDED.avg_train_reward,
            avg_test_reward = EXCLUDED.avg_test_reward,
            trained_at = NOW()
    """, ('developer_preference_v1', len(models), context_dim, 0.5,
          len(train_records), test_accuracy, avg_reward_train, avg_test_reward,
          str(model_path)))

    db.commit()
    cursor.close()
    db.close()

    if verbose:
        print(f"\n=== Training Results ===")
        print(f"  Models learned: {len(models)}")
        print(f"  Training records: {len(train_records)}")
        print(f"  Test records: {len(test_records)}")
        print(f"  Avg training reward: {avg_reward_train:.3f}")
        print(f"  Avg test reward: {avg_test_reward:.3f}")
        print(f"  Test accuracy: {test_accuracy:.1%}")
        print(f"  Model saved: {model_path}")
        print(f"  Mapping saved: {mapping_path}")

        # Show model statistics
        stats = learner.get_statistics()
        print(f"\n=== Model Selection Statistics ===")
        for model_id, stat in sorted(stats.items(), key=lambda x: x[1]['total_selections'], reverse=True):
            if stat['total_selections'] > 0:
                print(f"  {models[model_id]}: {stat['total_selections']} selections, {stat['success_rate']:.1%} success rate")

        print(f"\n✅ Developer preference learner trained!")
        print(f"\nUsage example:")
        print(f"  from developer_preference_learner import DeveloperPreferenceLearner, extract_task_context")
        print(f"  learner = DeveloperPreferenceLearner.load('{model_path}')")
        print(f"  context = extract_task_context('Implement a Java service', 'orchestrator')")
        print(f"  model_id = learner.select_model(context)")

    return {
        'learner': learner,
        'mapping': mapping,
        'test_accuracy': test_accuracy,
        'avg_train_reward': avg_reward_train,
        'avg_test_reward': avg_test_reward
    }

def get_model_recommendation(task_description, workflow_name=None):
    """
    Get model recommendation for a task.

    Args:
        task_description: Description of the task
        workflow_name: Optional workflow name

    Returns:
        dict with recommended_model, confidence, alternatives
    """
    model_path = Path.home() / '.claude' / 'learning' / 'developer_preference_learner.pkl'
    mapping_path = Path.home() / '.claude' / 'learning' / 'developer_preference_mapping.json'

    if not model_path.exists():
        return {
            'error': 'Model not trained. Run train_developer_preference_learner() first.',
            'recommended_model': None
        }

    # Load learner
    learner = DeveloperPreferenceLearner.load(model_path)

    # Load mapping
    with open(mapping_path) as f:
        mapping = json.load(f)

    # Extract context and get recommendation
    context = extract_task_context(task_description, workflow_name)
    model_id, ucb_scores, confidence_intervals = learner.select_model(context, return_scores=True)

    recommended_model = mapping['models'][model_id]

    # Get top 3 alternatives
    model_scores = [(mapping['models'][i], ucb_scores[i], confidence_intervals[i])
                    for i in range(len(mapping['models']))]
    model_scores.sort(key=lambda x: x[1], reverse=True)

    return {
        'recommended_model': recommended_model,
        'ucbScore': float(ucb_scores[model_id]),  # JavaScript-friendly camelCase
        'ucb_score': float(ucb_scores[model_id]),  # Also keep snake_case for Python
        'confidence_interval': float(confidence_intervals[model_id]),
        'confidenceInterval': float(confidence_intervals[model_id]),
        'context': [float(c) for c in context],
        'context_features': mapping['context_features'],
        'contextFeatures': mapping['context_features'],
        'alternatives': [
            {
                'model': model,
                'ucbScore': float(score),
                'ucb_score': float(score),
                'confidenceInterval': float(ci),
                'confidence_interval': float(ci)
            }
            for model, score, ci in model_scores[:5]
        ]
    }

if __name__ == '__main__':
    # Train the model
    results = train_developer_preference_learner(verbose=True)

    if results:
        print("\n" + "="*80)
        print("Testing with example tasks...")
        print("="*80 + "\n")

        test_tasks = [
            "Implement a Java REST API endpoint for user authentication",
            "Review this Python code for security vulnerabilities",
            "Fix the database connection pool exhaustion bug",
            "Research best practices for PostgreSQL query optimization",
            "Write unit tests for the JavaScript payment service",
            "Deploy the updated microservice to production",
        ]

        for task in test_tasks:
            rec = get_model_recommendation(task, 'orchestrator')
            print(f"Task: {task}")
            print(f"  Recommended: {rec['recommended_model']}")
            print(f"  UCB Score: {rec['ucb_score']:.3f}")
            print(f"  Top 3 alternatives:")
            for alt in rec['alternatives'][:3]:
                print(f"    {alt['model']}: {alt['ucb_score']:.3f}")
            print()
