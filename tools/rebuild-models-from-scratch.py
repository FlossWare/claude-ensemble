#!/usr/bin/env python3
"""
Rebuild all ML models from scratch with current sklearn versions.

This script:
1. Finds all .pkl models in ~/.claude/learning/predictors/
2. Loads real data from PostgreSQL learning.experiences table
3. Trains new models with current sklearn versions
4. Saves updated .pkl files

Usage:
    python3 tools/rebuild-models-from-scratch.py
"""

import os
import sys
import pickle
import psycopg2
import psycopg2.extras
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Database connection
def get_db():
    return psycopg2.connect(
        dbname='learning',
        user=os.environ.get('PGUSER', os.environ.get('USER')),
        password=os.environ.get('PGPASSWORD'),
        host=os.environ.get('PGHOST', 'aio-01'),
        port=int(os.environ.get('PGPORT', 5433))
    )

# Load all experiences from database
def load_training_data():
    """Load all experiences from PostgreSQL."""
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    problem_type,
                    strategy,
                    success,
                    COALESCE(reward, 0.0) as reward,
                    COALESCE(novelty_score, 0.0) as novelty_score,
                    COALESCE(importance, 0.0) as importance,
                    COALESCE(execution_time_ms, 0) as execution_time_ms,
                    COALESCE(memory_mb, 0.0) as memory_mb,
                    COALESCE(cpu_usage_pct, 0.0) as cpu_usage_pct
                FROM learning.experiences
                ORDER BY timestamp DESC
            """)

            rows = cur.fetchall()
            print(f"Loaded {len(rows)} training samples from database")

            if len(rows) < 10:
                print(f"WARNING: Only {len(rows)} samples available. Models may not be accurate.")
                return None, None

            # Build feature matrix
            X = []
            y = []

            for row in rows:
                features = [
                    float(row['reward']),
                    float(row['novelty_score']),
                    float(row['importance']),
                    float(row['execution_time_ms']),
                    float(row['memory_mb']),
                    float(row['cpu_usage_pct'])
                ]
                X.append(features)
                y.append(int(bool(row['success'])))

            return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)

    finally:
        conn.close()

# Model definitions
MODELS = {
    'bug-predictor': RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42),
    'failure-mode-predictor': GradientBoostingClassifier(n_estimators=50, max_depth=5, random_state=42),
    'memory-usage-predictor': RandomForestClassifier(n_estimators=30, max_depth=8, random_state=42),
    'pattern-selector': LogisticRegression(max_iter=1000, random_state=42),
    'worker-allocation-optimizer': RandomForestClassifier(n_estimators=40, max_depth=12, random_state=42),
}

def main():
    print("="*70)
    print("REBUILD ML MODELS FROM SCRATCH")
    print("="*70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load training data
    print("Loading training data from PostgreSQL...")
    X, y = load_training_data()

    if X is None or y is None:
        print("ERROR: No training data available")
        return 1

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
    )

    print(f"Training samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    print()

    # Model directory
    predictor_dir = Path.home() / '.claude' / 'learning' / 'predictors'
    predictor_dir.mkdir(parents=True, exist_ok=True)

    # Track results
    results = {
        'rebuilt': 0,
        'failed': 0,
        'models': {}
    }

    # Train and save each model
    for model_name, model in MODELS.items():
        print(f"[{len(results['models'])+1}/{len(MODELS)}] {model_name}")
        print("-" * 60)

        try:
            # Train model
            start = datetime.now()
            model.fit(X_train, y_train)
            duration = (datetime.now() - start).total_seconds()

            # Evaluate
            y_pred = model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)

            # Save model
            model_path = predictor_dir / f"{model_name}.pkl"

            # Backup old model if exists
            if model_path.exists():
                backup_path = predictor_dir / f"{model_name}.pkl.bak"
                if backup_path.exists():
                    backup_path.unlink()
                model_path.rename(backup_path)

            # Save new model
            with open(model_path, 'wb') as f:
                pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

            print(f"  Training time: {duration:.2f}s")
            print(f"  Test accuracy: {accuracy:.4f}")
            print(f"  Saved to: {model_path}")
            print(f"  Status: SUCCESS ✓")

            results['rebuilt'] += 1
            results['models'][model_name] = {
                'status': 'success',
                'accuracy': accuracy,
                'duration': duration,
                'path': str(model_path)
            }

        except Exception as e:
            print(f"  Status: FAILED ✗")
            print(f"  Error: {e}")

            results['failed'] += 1
            results['models'][model_name] = {
                'status': 'failed',
                'error': str(e)
            }

        print()

    # Summary
    print("="*70)
    print("REBUILD SUMMARY")
    print("="*70)
    print(f"Total models: {len(MODELS)}")
    print(f"  Rebuilt:    {results['rebuilt']}")
    print(f"  Failed:     {results['failed']}")
    print("="*70)

    # Verify critical models
    print("\nVerifying critical models...")
    critical_models = ['bug-predictor', 'worker-allocation-optimizer']

    for model_name in critical_models:
        model_path = predictor_dir / f"{model_name}.pkl"
        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)

            # Test prediction
            test_input = X_test[0:1]
            prediction = model.predict(test_input)

            print(f"  {model_name}: ✓ (prediction: {prediction[0]})")

        except Exception as e:
            print(f"  {model_name}: ✗ ({e})")

    print()

    return 0 if results['failed'] == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
