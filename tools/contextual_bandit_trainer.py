#!/usr/bin/env python3
"""
Contextual Thompson Sampling Trainer

Improves strategy selection by considering task context:
- Task type (code vs research vs math)
- Task complexity (prompt length, mentions)
- Historical performance per context

Uses LinUCB (Linear Upper Confidence Bound) algorithm.
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
    """LinUCB contextual bandit for strategy selection"""

    def __init__(self, num_strategies, context_dim=10, alpha=1.0):
        """
        num_strategies: Number of available strategies
        context_dim: Dimension of context vector
        alpha: Exploration parameter (higher = more exploration)
        """
        self.num_strategies = num_strategies
        self.context_dim = context_dim
        self.alpha = alpha

        # LinUCB parameters (one per strategy)
        self.A = [np.identity(context_dim) for _ in range(num_strategies)]
        self.b = [np.zeros(context_dim) for _ in range(num_strategies)]

    def get_theta(self, strategy_id):
        """Get parameter vector for strategy"""
        A_inv = np.linalg.inv(self.A[strategy_id])
        return A_inv.dot(self.b[strategy_id])

    def select_strategy(self, context):
        """Select best strategy given context"""
        context = np.array(context)
        ucb_scores = []

        for i in range(self.num_strategies):
            theta = self.get_theta(i)
            A_inv = np.linalg.inv(self.A[i])

            # UCB = expected reward + exploration bonus
            expected = theta.dot(context)
            bonus = self.alpha * np.sqrt(context.dot(A_inv).dot(context))
            ucb = expected + bonus

            ucb_scores.append(ucb)

        return int(np.argmax(ucb_scores)), ucb_scores

    def update(self, strategy_id, context, reward):
        """Update strategy parameters after observing reward"""
        context = np.array(context)

        self.A[strategy_id] += np.outer(context, context)
        self.b[strategy_id] += reward * context

    def save(self, filepath):
        """Save model to disk"""
        state = {
            'num_strategies': self.num_strategies,
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

        model = cls(state['num_strategies'], state['context_dim'], state['alpha'])
        model.A = [np.array(A) for A in state['A']]
        model.b = [np.array(b) for b in state['b']]
        return model

def extract_context(task_text):
    """Extract context features from task description"""
    task_lower = task_text.lower() if task_text else ""

    # Task type features (one-hot encoded)
    is_code = 1.0 if any(kw in task_lower for kw in ['implement', 'write', 'create', 'code']) else 0.0
    is_review = 1.0 if any(kw in task_lower for kw in ['review', 'analyze', 'check']) else 0.0
    is_fix = 1.0 if any(kw in task_lower for kw in ['fix', 'bug', 'issue']) else 0.0
    is_research = 1.0 if any(kw in task_lower for kw in ['research', 'find', 'search']) else 0.0

    # Complexity features
    prompt_length = len(task_text) / 1000.0 if task_text else 0.0  # Normalize
    has_code_block = 1.0 if '```' in task_text else 0.0
    mentions_file = 1.0 if any(kw in task_lower for kw in ['.py', '.java', '.js', 'file']) else 0.0
    mentions_test = 1.0 if 'test' in task_lower else 0.0

    # Urgency features
    is_critical = 1.0 if 'critical' in task_lower else 0.0
    has_deadline = 1.0 if any(kw in task_lower for kw in ['asap', 'urgent', 'deadline']) else 0.0

    return [
        is_code,
        is_review,
        is_fix,
        is_research,
        prompt_length,
        has_code_block,
        mentions_file,
        mentions_test,
        is_critical,
        has_deadline
    ]

def train_contextual_bandit():
    """Train contextual bandit from historical data"""
    db = get_db()
    cursor = db.cursor()

    print("=== Contextual Thompson Sampling Trainer ===\n")

    # Load historical data
    cursor.execute("""
        SELECT DISTINCT strategy
        FROM learning.strategy_performance
        ORDER BY strategy
    """)
    strategies = [row[0] for row in cursor.fetchall()]
    strategy_to_id = {s: i for i, s in enumerate(strategies)}

    print(f"Strategies: {len(strategies)}")
    for i, s in enumerate(strategies):
        print(f"  {i}: {s}")

    # Load execution history
    cursor.execute("""
        SELECT
            wr.task_assigned,
            we.workflow_name,
            wr.confidence,
            wr.outcome
        FROM workflow.worker_results wr
        JOIN workflow.executions we ON wr.workflow_execution_id = we.id
        WHERE wr.outcome = 'success'
          AND wr.confidence IS NOT NULL
        ORDER BY we.created_at
    """)

    records = cursor.fetchall()
    print(f"\nTraining records: {len(records)}")

    # Initialize bandit
    context_dim = 10
    bandit = ContextualBandit(
        num_strategies=len(strategies),
        context_dim=context_dim,
        alpha=0.5  # Moderate exploration
    )

    # Train on historical data
    correct_selections = 0
    total_selections = 0

    for task, workflow, confidence, outcome in records:
        # Extract context
        context = extract_context(task)

        # Map workflow to strategy (simplified)
        # In production, would have explicit strategy field
        strategy = workflow if workflow in strategy_to_id else 'default'
        if strategy not in strategy_to_id:
            continue

        strategy_id = strategy_to_id[strategy]

        # Simulate selection
        predicted_id, scores = bandit.select_strategy(context)

        if predicted_id == strategy_id:
            correct_selections += 1
        total_selections += 1

        # Update with actual reward
        reward = float(confidence) if confidence else 0.5
        bandit.update(strategy_id, context, reward)

    accuracy = correct_selections / total_selections if total_selections > 0 else 0
    print(f"\nTraining complete!")
    print(f"  Accuracy: {accuracy:.1%} ({correct_selections}/{total_selections})")

    # Save model
    model_path = '/home/sfloess/.claude/learning/contextual_bandit.json'
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
    """, ('contextual_thompson', 'LinUCB', len(strategies), context_dim,
          0.5, total_selections, accuracy, model_path))

    db.commit()
    cursor.close()
    db.close()

    print("\n✅ Contextual bandit trained and saved!")
    print(f"\nTo use in orchestrator:")
    print(f"  from contextual_bandit_trainer import ContextualBandit, extract_context")
    print(f"  bandit = ContextualBandit.load('{model_path}')")
    print(f"  context = extract_context(task_description)")
    print(f"  strategy_id, scores = bandit.select_strategy(context)")

    return bandit, accuracy

if __name__ == '__main__':
    train_contextual_bandit()
