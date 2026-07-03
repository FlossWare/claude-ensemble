#!/usr/bin/env python3
"""
Contextual Thompson Sampling Trainer v2

Trains LinUCB bandit to select best MODEL for a given task context.
Uses actual workflow.worker_results data.

Key improvement: Maps task context → best model (not workflow → strategy)
"""

import psycopg2
import numpy as np
import json
from collections import defaultdict
from datetime import datetime

def get_db():
    return psycopg2.connect(
        host='aio-01',
        port=5433,
        user='sfloess',
        database='learning'
    )

class ContextualBandit:
    """LinUCB contextual bandit for model selection"""

    def __init__(self, num_models, context_dim=10, alpha=1.0):
        """
        num_models: Number of available models
        context_dim: Dimension of context vector
        alpha: Exploration parameter (higher = more exploration)
        """
        self.num_models = num_models
        self.context_dim = context_dim
        self.alpha = alpha

        # LinUCB parameters (one per model)
        self.A = [np.identity(context_dim) for _ in range(num_models)]
        self.b = [np.zeros(context_dim) for _ in range(num_models)]

    def get_theta(self, model_id):
        """Get parameter vector for model"""
        A_inv = np.linalg.inv(self.A[model_id])
        return A_inv.dot(self.b[model_id])

    def select_model(self, context):
        """Select best model given context"""
        context = np.array(context)
        ucb_scores = []

        for i in range(self.num_models):
            theta = self.get_theta(i)
            A_inv = np.linalg.inv(self.A[i])

            # UCB = expected reward + exploration bonus
            expected = theta.dot(context)
            bonus = self.alpha * np.sqrt(context.dot(A_inv).dot(context))
            ucb = expected + bonus

            ucb_scores.append(ucb)

        return int(np.argmax(ucb_scores)), ucb_scores

    def update(self, model_id, context, reward):
        """Update model parameters after observing reward"""
        context = np.array(context)

        self.A[model_id] += np.outer(context, context)
        self.b[model_id] += reward * context

    def save(self, filepath):
        """Save model to disk"""
        state = {
            'num_models': self.num_models,
            'context_dim': self.context_dim,
            'alpha': self.alpha,
            'A': [A.tolist() for A in self.A],
            'b': [b.tolist() for b in self.b]
        }
        with open(filepath, 'w') as f:
            json.dump(state, f)

    @classmethod
    def load(cls, filepath):
        """Load model from disk"""
        with open(filepath, 'r') as f:
            state = json.load(f)

        model = cls(state['num_models'], state['context_dim'], state['alpha'])
        model.A = [np.array(A) for A in state['A']]
        model.b = [np.array(b) for b in state['b']]
        return model

def extract_context(task_text, workflow_name):
    """Extract context features from task description and workflow"""
    task_lower = task_text.lower() if task_text else ""
    workflow_lower = workflow_name.lower() if workflow_name else ""

    # Task type features (one-hot encoded)
    is_code = 1.0 if any(kw in task_lower for kw in ['implement', 'write', 'create', 'code']) else 0.0
    is_review = 1.0 if any(kw in task_lower for kw in ['review', 'analyze', 'check']) else 0.0
    is_fix = 1.0 if any(kw in task_lower for kw in ['fix', 'bug', 'issue']) else 0.0
    is_research = 1.0 if any(kw in task_lower for kw in ['research', 'find', 'search', 'deep-research']) else 0.0

    # Workflow type
    is_orchestrator = 1.0 if 'orchestrator' in workflow_lower else 0.0
    is_test = 1.0 if 'test' in workflow_lower else 0.0

    # Complexity features
    prompt_length = len(task_text) / 1000.0 if task_text else 0.0  # Normalize
    has_code_block = 1.0 if '```' in task_text else 0.0
    mentions_file = 1.0 if any(kw in task_lower for kw in ['.py', '.java', '.js', 'file']) else 0.0
    mentions_test = 1.0 if 'test' in task_lower else 0.0

    return [
        is_code,
        is_review,
        is_fix,
        is_research,
        is_orchestrator,
        is_test,
        prompt_length,
        has_code_block,
        mentions_file,
        mentions_test
    ]

def train_contextual_bandit():
    """Train contextual bandit from historical data"""
    db = get_db()
    cursor = db.cursor()

    print("=== Contextual Thompson Sampling Trainer v2 ===\n")

    # Load successful models
    cursor.execute("""
        SELECT DISTINCT wr.model
        FROM workflow.worker_results wr
        WHERE wr.outcome = 'success'
          AND wr.confidence > 0.5
        ORDER BY wr.model
    """)
    models = [row[0] for row in cursor.fetchall()]
    model_to_id = {m: i for i, m in enumerate(models)}

    print(f"Models with successful executions: {len(models)}")
    for i, m in enumerate(models[:10]):
        print(f"  {i}: {m}")
    if len(models) > 10:
        print(f"  ... and {len(models) - 10} more")

    # Load execution history
    cursor.execute("""
        SELECT
            wr.task_assigned,
            we.workflow_name,
            wr.model,
            wr.confidence,
            wr.outcome,
            wr.duration_ms
        FROM workflow.worker_results wr
        JOIN workflow.executions we ON wr.workflow_execution_id = we.id
        WHERE wr.outcome IN ('success', 'error')
          AND wr.task_assigned IS NOT NULL
          AND wr.model IN (%s)
        ORDER BY we.created_at
    """ % ','.join(['%s'] * len(models)), models)

    records = cursor.fetchall()
    print(f"\nTraining records: {len(records)}")

    # Initialize bandit
    context_dim = 10
    bandit = ContextualBandit(
        num_models=len(models),
        context_dim=context_dim,
        alpha=0.3  # Lower exploration (we have good data)
    )

    # Train on historical data
    correct_selections = 0
    total_selections = 0
    total_reward = 0.0

    # Split data: 80% train, 20% test
    split_idx = int(len(records) * 0.8)
    train_records = records[:split_idx]
    test_records = records[split_idx:]

    print(f"\nTraining on {len(train_records)} records...")
    for task, workflow, model, confidence, outcome, duration in train_records:
        if model not in model_to_id:
            continue

        context = extract_context(task, workflow)
        model_id = model_to_id[model]

        # Calculate reward: success + high confidence + fast execution
        if outcome == 'success' and confidence:
            reward = float(confidence)
            # Bonus for fast execution (< 5 seconds)
            if duration and duration < 5000:
                reward = min(1.0, reward * 1.1)
        else:
            reward = 0.0

        bandit.update(model_id, context, reward)
        total_reward += reward

    avg_reward_train = total_reward / len(train_records) if train_records else 0

    # Test on holdout set
    print(f"\nTesting on {len(test_records)} records...")
    test_correct = 0
    test_total = 0

    for task, workflow, actual_model, confidence, outcome, duration in test_records:
        if actual_model not in model_to_id:
            continue

        context = extract_context(task, workflow)
        predicted_id, scores = bandit.select_model(context)

        # Check if prediction matches what was actually used
        actual_id = model_to_id[actual_model]
        if predicted_id == actual_id:
            test_correct += 1
        test_total += 1

    test_accuracy = test_correct / test_total if test_total > 0 else 0

    print(f"\n=== Training Results ===")
    print(f"  Training records: {len(train_records)}")
    print(f"  Average reward (train): {avg_reward_train:.3f}")
    print(f"  Test accuracy: {test_accuracy:.1%} ({test_correct}/{test_total})")
    print(f"  Unique models: {len(models)}")

    # Save model
    model_path = '/home/sfloess/.claude/learning/contextual_bandit_v2.json'
    bandit.save(model_path)
    print(f"  Model saved: {model_path}")

    # Store metadata in PostgreSQL
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning.bandit_models (
            model_name VARCHAR PRIMARY KEY,
            model_type VARCHAR,
            num_strategies INTEGER,
            context_dim INTEGER,
            alpha FLOAT,
            training_records INTEGER,
            accuracy FLOAT,
            model_path VARCHAR,
            trained_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("""
        INSERT INTO learning.bandit_models
        (model_name, model_type, num_strategies, context_dim, alpha,
         training_records, accuracy, model_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (model_name) DO UPDATE SET
            training_records = EXCLUDED.training_records,
            accuracy = EXCLUDED.accuracy,
            trained_at = NOW()
    """, ('contextual_thompson_v2', 'LinUCB', len(models), context_dim,
          0.3, len(train_records), test_accuracy, model_path))

    db.commit()

    # Save model mapping for reference
    mapping_path = '/home/sfloess/.claude/learning/model_mapping.json'
    with open(mapping_path, 'w') as f:
        json.dump({
            'models': models,
            'model_to_id': model_to_id,
            'context_features': [
                'is_code', 'is_review', 'is_fix', 'is_research',
                'is_orchestrator', 'is_test', 'prompt_length',
                'has_code_block', 'mentions_file', 'mentions_test'
            ]
        }, f, indent=2)
    print(f"  Model mapping saved: {mapping_path}")

    cursor.close()
    db.close()

    print("\n✅ Contextual bandit v2 trained and saved!")
    print(f"\nTo use in orchestrator:")
    print(f"  from contextual_bandit_trainer_v2 import ContextualBandit, extract_context")
    print(f"  bandit = ContextualBandit.load('{model_path}')")
    print(f"  with open('{mapping_path}') as f:")
    print(f"      mapping = json.load(f)")
    print(f"  context = extract_context(task_description, workflow_name)")
    print(f"  model_id, scores = bandit.select_model(context)")
    print(f"  best_model = mapping['models'][model_id]")

    return {
        'bandit': bandit,
        'test_accuracy': test_accuracy,
        'avg_reward': avg_reward_train,
        'num_models': len(models),
        'training_records': len(train_records),
        'test_records': len(test_records)
    }

if __name__ == '__main__':
    results = train_contextual_bandit()
    print(f"\n=== Summary ===")
    print(f"Test Accuracy: {results['test_accuracy']:.1%}")
    print(f"Avg Training Reward: {results['avg_reward']:.3f}")
    print(f"Models Learned: {results['num_models']}")
    print(f"Training Records: {results['training_records']}")
