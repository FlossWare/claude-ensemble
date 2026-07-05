#!/usr/bin/env python3
"""
Pattern Selector Model Training

Predicts optimal workflow pattern (pipeline, parallel, sequential, nested)
based on task characteristics and historical execution data.

Data source: PostgreSQL workflow.executions + worker_results + phases
Features: worker_count, task_count, estimated_interdependence, data_size
Model: RandomForestClassifier (4 classes)

Output: ~/.claude/learning/predictors/pattern-selector.pkl
"""

import os
import sys
import json
import psycopg2
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, f1_score
import pickle

# Configuration
DB_CONFIG = {
    'host': os.environ.get('PGHOST', 'aio-01'),
    'port': int(os.environ.get('PGPORT', '5433')),
    'database': os.environ.get('PGDATABASE', 'learning'),
    'user': os.environ.get('PGUSER', os.environ.get('USER')),
    'password': os.environ.get('PGPASSWORD', None)
}

OUTPUT_DIR = Path.home() / '.claude' / 'learning' / 'predictors'
OUTPUT_FILE = OUTPUT_DIR / 'pattern-selector.pkl'
METADATA_FILE = OUTPUT_DIR / 'pattern-selector-metadata.json'

# Pattern definitions (inferred from workflow characteristics)
PATTERNS = {
    'parallel': 0,      # Multiple independent workers, no phases
    'sequential': 1,    # Single worker or linear phases
    'pipeline': 2,      # Multiple phases with worker handoffs
    'nested': 3         # Multiple workers + multiple phases (complex)
}

PATTERN_NAMES = {v: k for k, v in PATTERNS.items()}


def connect_db():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)


def infer_pattern(row):
    """
    Infer workflow pattern from execution characteristics.

    Pattern detection logic:
    - parallel: worker_count > 1, phase_count <= 1 (fan-out parallelism)
    - sequential: worker_count <= 1, phase_count <= 1 (single-threaded)
    - pipeline: worker_count >= 1, phase_count >= 2 (staged processing)
    - nested: worker_count > 3, phase_count > 2 (complex orchestration)
    """
    worker_count = row['worker_count'] or 0
    phase_count = row['phase_count'] or 0
    total_workers = row['total_workers'] or 0

    # Use total_workers if worker_count is 0 (workers not yet recorded)
    if worker_count == 0 and total_workers > 0:
        worker_count = total_workers

    # Pattern inference rules
    if worker_count > 3 and phase_count > 2:
        return PATTERNS['nested']
    elif phase_count >= 2:
        return PATTERNS['pipeline']
    elif worker_count > 1:
        return PATTERNS['parallel']
    else:
        return PATTERNS['sequential']


def extract_features(row):
    """
    Extract feature vector from workflow execution.

    Features:
    1. worker_count: Number of parallel workers
    2. phase_count: Number of sequential phases
    3. task_complexity: Estimated from description length
    4. avg_worker_duration: Average worker execution time (ms)
    5. total_duration_ms: Total workflow duration
    6. interdependence_score: Ratio of phases to workers (higher = more dependencies)
    7. parallelism_potential: Worker count normalized by duration
    """
    worker_count = row['worker_count'] or 0
    phase_count = row['phase_count'] or 0
    total_workers = row['total_workers'] or 0
    total_duration_ms = row['total_duration_ms'] or 1
    task_description = row['task_description'] or ''

    # Use total_workers if worker_count is 0
    if worker_count == 0 and total_workers > 0:
        worker_count = total_workers

    # Task complexity from description length (log scale)
    task_complexity = min(np.log1p(len(task_description)), 10.0)

    # Average worker duration (estimate from total duration)
    avg_worker_duration = total_duration_ms / max(worker_count, 1)

    # Interdependence score (higher phase/worker ratio = more sequential)
    interdependence_score = phase_count / max(worker_count, 1)

    # Parallelism potential (workers per second)
    parallelism_potential = (worker_count * 1000) / max(total_duration_ms, 1)

    return [
        worker_count,
        phase_count,
        task_complexity,
        avg_worker_duration,
        total_duration_ms,
        interdependence_score,
        parallelism_potential
    ]


def load_training_data(conn):
    """
    Load workflow executions and extract features + labels.

    Returns:
    - X: Feature matrix (n_samples, n_features)
    - y: Label vector (n_samples,)
    - metadata: Dict with sample info
    """
    query = """
    SELECT
        e.id,
        e.workflow_id,
        e.workflow_name,
        e.task_description,
        e.total_workers,
        e.total_duration_ms,
        e.outcome,
        COUNT(DISTINCT w.id) as worker_count,
        COUNT(DISTINCT p.phase_name) as phase_count,
        e.created_at
    FROM workflow.executions e
    LEFT JOIN workflow.worker_results w ON e.id = w.workflow_execution_id
    LEFT JOIN workflow.phases p ON e.id = p.workflow_execution_id
    WHERE e.outcome = 'success'
    GROUP BY e.id, e.workflow_id, e.workflow_name, e.task_description,
             e.total_workers, e.total_duration_ms, e.outcome, e.created_at
    ORDER BY e.created_at DESC
    """

    cursor = conn.cursor()
    cursor.execute(query)

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()

    if len(rows) == 0:
        print("ERROR: No training data found in database")
        sys.exit(1)

    # Convert to dict rows
    data = [dict(zip(columns, row)) for row in rows]

    print(f"Loaded {len(data)} workflow executions from database")

    # Extract features and labels
    X = []
    y = []
    metadata = []

    for row in data:
        features = extract_features(row)
        label = infer_pattern(row)

        X.append(features)
        y.append(label)
        metadata.append({
            'workflow_id': row['workflow_id'],
            'workflow_name': row['workflow_name'],
            'pattern': PATTERN_NAMES[label],
            'worker_count': row['worker_count'],
            'phase_count': row['phase_count']
        })

    X = np.array(X)
    y = np.array(y)

    # Print pattern distribution
    print("\nPattern distribution:")
    for pattern_name, pattern_id in PATTERNS.items():
        count = np.sum(y == pattern_id)
        percentage = (count / len(y)) * 100
        print(f"  {pattern_name:12s}: {count:4d} ({percentage:5.1f}%)")

    return X, y, metadata


def balance_classes(X, y, metadata):
    """
    Balance classes using SMOTE-like oversampling for minority classes.
    For small datasets, duplicate minority samples with small noise.
    """
    from collections import Counter

    class_counts = Counter(y)
    max_count = max(class_counts.values())
    min_count = min(class_counts.values())

    # Only balance if imbalance ratio > 3:1
    if max_count / max(min_count, 1) < 3:
        print("Classes reasonably balanced, skipping resampling")
        return X, y, metadata

    print(f"\nBalancing classes (max={max_count}, min={min_count})...")

    X_balanced = []
    y_balanced = []
    metadata_balanced = []

    for class_id in range(4):
        class_mask = y == class_id
        class_X = X[class_mask]
        class_y = y[class_mask]
        class_meta = [m for m, mask in zip(metadata, class_mask) if mask]

        if len(class_X) == 0:
            continue

        # Oversample to 70% of max class (not full balance)
        target_count = int(max_count * 0.7)

        if len(class_X) < target_count:
            # Duplicate samples with small noise
            needed = target_count - len(class_X)
            indices = np.random.choice(len(class_X), needed, replace=True)

            noise = np.random.normal(0, 0.05, (needed, X.shape[1]))
            synthetic_X = class_X[indices] + noise

            X_balanced.append(class_X)
            X_balanced.append(synthetic_X)
            y_balanced.extend([class_id] * len(class_X))
            y_balanced.extend([class_id] * needed)
            metadata_balanced.extend(class_meta)
            metadata_balanced.extend([{**m, 'synthetic': True} for m in [class_meta[i] for i in indices]])
        else:
            X_balanced.append(class_X)
            y_balanced.extend([class_id] * len(class_X))
            metadata_balanced.extend(class_meta)

    X_balanced = np.vstack(X_balanced)
    y_balanced = np.array(y_balanced)

    print(f"Balanced dataset: {len(X)} → {len(X_balanced)} samples")

    return X_balanced, y_balanced, metadata_balanced


def train_model(X, y):
    """
    Train RandomForestClassifier for pattern prediction.

    Uses 80/20 train/test split with stratification.
    """
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\nTrain/test split: {len(X_train)} train, {len(X_test)} test")

    # Train Random Forest
    print("\nTraining RandomForestClassifier...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        class_weight='balanced',  # Handle class imbalance
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    # Evaluate on test set
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"\nTest Accuracy: {accuracy:.3f}")

    # Cross-validation score
    cv_scores = cross_val_score(model, X_train, y_train, cv=min(5, len(X_train)), scoring='accuracy')
    print(f"Cross-validation accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std() * 2:.3f})")

    # Per-class metrics
    print("\nPer-class F1 scores:")
    f1_scores = f1_score(y_test, y_pred, average=None, zero_division=0)
    for pattern_name, pattern_id in PATTERNS.items():
        f1 = f1_scores[pattern_id] if pattern_id < len(f1_scores) else 0.0
        print(f"  {pattern_name:12s}: {f1:.3f}")

    # Confusion matrix
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print("         ", "  ".join([f"{PATTERN_NAMES[i]:>10s}" for i in range(4)]))
    for i, row in enumerate(cm):
        print(f"{PATTERN_NAMES[i]:>10s}", "  ".join([f"{val:>10d}" for val in row]))

    # Feature importances
    feature_names = [
        'worker_count',
        'phase_count',
        'task_complexity',
        'avg_worker_duration',
        'total_duration_ms',
        'interdependence_score',
        'parallelism_potential'
    ]

    print("\nFeature Importances:")
    importances = model.feature_importances_
    for name, importance in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True):
        print(f"  {name:25s}: {importance:.3f}")

    return model, accuracy, f1_scores, cm, importances, feature_names


def save_model(model, accuracy, f1_scores, cm, importances, feature_names, training_samples):
    """
    Save trained model and metadata to disk.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save model
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(model, f)

    print(f"\nModel saved to: {OUTPUT_FILE}")

    # Save metadata
    metadata = {
        'model_name': 'pattern-selector',
        'model_type': 'RandomForestClassifier',
        'accuracy': float(accuracy),
        'training_samples': int(training_samples),
        'feature_count': len(feature_names),
        'feature_names': feature_names,
        'feature_importances': {name: float(imp) for name, imp in zip(feature_names, importances)},
        'f1_scores': {PATTERN_NAMES[i]: float(score) for i, score in enumerate(f1_scores)},
        'confusion_matrix': cm.tolist(),
        'patterns': PATTERN_NAMES,
        'trained_at': datetime.now().isoformat(),
        'ready_for_production': accuracy > 0.7,
        'pkl_path': str(OUTPUT_FILE)
    }

    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved to: {METADATA_FILE}")

    return metadata


def main():
    """Main training pipeline."""
    print("=" * 80)
    print("PATTERN SELECTOR MODEL TRAINING")
    print("=" * 80)

    # Connect to database
    print("\nConnecting to PostgreSQL database...")
    conn = connect_db()

    # Load training data
    X, y, metadata = load_training_data(conn)
    conn.close()

    if len(X) < 10:
        print(f"\nWARNING: Only {len(X)} samples available. Model may not be reliable.")
        print("Continuing with training for demonstration purposes...")

    # Balance classes (if needed)
    X_balanced, y_balanced, metadata_balanced = balance_classes(X, y, metadata)

    # Train model
    model, accuracy, f1_scores, cm, importances, feature_names = train_model(X_balanced, y_balanced)

    # Save model
    saved_metadata = save_model(model, accuracy, f1_scores, cm, importances, feature_names, len(X_balanced))

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    print(f"\nModel: {saved_metadata['model_name']}")
    print(f"Accuracy: {saved_metadata['accuracy']:.3f}")
    print(f"Training samples: {saved_metadata['training_samples']}")
    print(f"Feature count: {saved_metadata['feature_count']}")
    print(f"Production ready: {saved_metadata['ready_for_production']}")
    print(f"PKL path: {saved_metadata['pkl_path']}")

    # Return structured output
    return saved_metadata


if __name__ == '__main__':
    try:
        metadata = main()
        # Print JSON for structured output tool
        print("\n" + "=" * 80)
        print("STRUCTURED OUTPUT (JSON)")
        print("=" * 80)
        print(json.dumps(metadata, indent=2))
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
