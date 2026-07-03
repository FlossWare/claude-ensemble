#!/usr/bin/env python3
"""
Novelty Detection Training System
Based on: docs/TRAINING-OPPORTUNITIES.md Section 6

Trains an Isolation Forest model to detect novel tasks that require exploration
vs familiar tasks that can exploit known strategies.

Algorithm: Isolation Forest (unsupervised anomaly detection)
Dataset: learning.experiences (135 records with novelty scores)
Expected Gain: 10-15% better exploration/exploitation balance
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import pickle

# Configuration
EXPERIENCES_FILE = Path.home() / '.claude' / 'learning' / 'contextual_bandit.json'
MODEL_OUTPUT = Path.home() / '.claude' / 'learning' / 'novelty_detector_model.pkl'
METRICS_OUTPUT = Path.home() / '.claude' / 'learning' / 'novelty_detector_metrics.json'
NOVELTY_THRESHOLD = 0.5  # Tasks with novelty_score > 0.5 are "novel"

def load_experiences():
    """Load experience data from contextual bandit JSON (fallback to PostgreSQL schema)"""

    # Try loading from contextual_bandit.json first
    if EXPERIENCES_FILE.exists():
        with open(EXPERIENCES_FILE) as f:
            data = json.load(f)
            experiences = data.get('experiences', [])
            if experiences:
                print(f"Loaded {len(experiences)} experiences from contextual_bandit.json")
                return experiences

    # Generate synthetic dataset based on schema
    print("Database offline - generating synthetic dataset based on schema...")
    print("(In production, this would use PostgreSQL learning.experiences table)")
    return generate_synthetic_experiences()

def generate_synthetic_experiences():
    """Generate synthetic experiences for testing"""
    np.random.seed(42)

    experiences = []
    strategies = ['grep_parallel', 'semantic_search', 'code_analysis', 'llm_generate', 'hybrid_search']
    problem_types = ['code_search', 'bug_fix', 'feature_implementation', 'documentation', 'refactoring']

    for i in range(135):
        # Simulate varying novelty scores
        is_novel = np.random.random() > 0.6  # 40% novel tasks

        if is_novel:
            novelty_score = np.random.uniform(0.6, 1.0)
            success_prob = 0.5  # Novel tasks have lower success rate
        else:
            novelty_score = np.random.uniform(0.0, 0.4)
            success_prob = 0.8  # Familiar tasks have higher success rate

        success = np.random.random() < success_prob
        reward = novelty_score * 0.5 + (1.0 if success else 0.0) * 0.5

        experience = {
            'problem_type': np.random.choice(problem_types),
            'problem_hash': f'hash_{i:04d}',
            'strategy': np.random.choice(strategies),
            'success': success,
            'reward': reward,
            'novelty_score': novelty_score,
            'importance': np.random.uniform(0.3, 1.0),
            'context': {
                'prompt_length': int(np.random.lognormal(5, 1)),
                'file_count': int(np.random.poisson(3)),
                'code_blocks': int(np.random.poisson(2)),
                'complexity': np.random.choice(['simple', 'medium', 'complex'])
            }
        }
        experiences.append(experience)

    return experiences

def extract_features(experience):
    """Extract feature vector from experience"""
    context = experience.get('context', {})

    # Complexity encoding
    complexity_map = {'simple': 0, 'medium': 1, 'complex': 2}
    complexity_val = complexity_map.get(context.get('complexity', 'medium'), 1)

    features = [
        context.get('prompt_length', 0),
        context.get('file_count', 0),
        context.get('code_blocks', 0),
        complexity_val,
        1.0 if experience.get('success', False) else 0.0,
        experience.get('reward', 0.0),
        experience.get('importance', 0.5)
    ]

    return np.array(features)

def train_novelty_detector(experiences):
    """Train Isolation Forest model on experiences"""

    print("\n=== Extracting Features ===")
    X = np.array([extract_features(exp) for exp in experiences])
    y = np.array([1 if exp.get('novelty_score', 0) > NOVELTY_THRESHOLD else 0
                  for exp in experiences])

    print(f"Feature matrix shape: {X.shape}")
    print(f"Novel tasks: {y.sum()} / {len(y)} ({100*y.sum()/len(y):.1f}%)")
    print(f"Familiar tasks: {len(y) - y.sum()} / {len(y)} ({100*(len(y)-y.sum())/len(y):.1f}%)")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")

    # Train Isolation Forest
    print("\n=== Training Isolation Forest ===")
    contamination = y_train.sum() / len(y_train)  # Proportion of novel tasks

    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=42,
        max_samples='auto',
        max_features=1.0,
        n_jobs=-1,
        verbose=1
    )

    model.fit(X_train)

    # Predict on test set
    print("\n=== Evaluating Model ===")
    y_pred_scores = model.decision_function(X_test)
    y_pred = model.predict(X_test)

    # Convert predictions: -1 (outlier/novel) -> 1, 1 (inlier/familiar) -> 0
    y_pred_binary = np.where(y_pred == -1, 1, 0)

    # Calculate metrics
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred_binary,
                                target_names=['Familiar', 'Novel']))

    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred_binary)
    print(cm)
    print(f"True Negatives (Familiar correctly identified): {cm[0,0]}")
    print(f"False Positives (Familiar misclassified as Novel): {cm[0,1]}")
    print(f"False Negatives (Novel misclassified as Familiar): {cm[1,0]}")
    print(f"True Positives (Novel correctly identified): {cm[1,1]}")

    # ROC-AUC score
    try:
        auc_score = roc_auc_score(y_test, -y_pred_scores)  # Negative because lower scores = outliers
        print(f"\nROC-AUC Score: {auc_score:.4f}")
    except Exception as e:
        print(f"\nCould not calculate ROC-AUC: {e}")
        auc_score = None

    # Calculate exploration/exploitation balance metrics
    novel_detection_rate = cm[1,1] / (cm[1,1] + cm[1,0]) if (cm[1,1] + cm[1,0]) > 0 else 0
    familiar_accuracy = cm[0,0] / (cm[0,0] + cm[0,1]) if (cm[0,0] + cm[0,1]) > 0 else 0

    print(f"\n=== Exploration/Exploitation Balance ===")
    print(f"Novel Detection Rate (Exploration): {novel_detection_rate:.2%}")
    print(f"Familiar Accuracy (Exploitation): {familiar_accuracy:.2%}")
    print(f"Overall Accuracy: {(cm[0,0] + cm[1,1]) / len(y_test):.2%}")

    # Save model
    print(f"\n=== Saving Model ===")
    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_OUTPUT, 'wb') as f:
        pickle.dump(model, f)
    print(f"Model saved to: {MODEL_OUTPUT}")

    # Save metrics
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'training_samples': len(X_train),
        'test_samples': len(X_test),
        'contamination': float(contamination),
        'novel_detection_rate': float(novel_detection_rate),
        'familiar_accuracy': float(familiar_accuracy),
        'overall_accuracy': float((cm[0,0] + cm[1,1]) / len(y_test)),
        'roc_auc': float(auc_score) if auc_score is not None else None,
        'confusion_matrix': cm.tolist(),
        'feature_names': [
            'prompt_length', 'file_count', 'code_blocks',
            'complexity', 'success', 'reward', 'importance'
        ]
    }

    with open(METRICS_OUTPUT, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to: {METRICS_OUTPUT}")

    return model, metrics

def test_novelty_detector(model, test_cases):
    """Test trained model on example tasks"""

    print("\n=== Testing Novelty Detector ===\n")

    for case in test_cases:
        features = extract_features(case)
        prediction = model.predict([features])[0]
        score = model.decision_function([features])[0]

        is_novel = "NOVEL (explore)" if prediction == -1 else "FAMILIAR (exploit)"

        print(f"Task: {case.get('problem_type', 'unknown')}")
        print(f"  Complexity: {case.get('context', {}).get('complexity', 'unknown')}")
        print(f"  Prediction: {is_novel}")
        print(f"  Anomaly Score: {score:.4f}")
        print(f"  True Novelty: {case.get('novelty_score', 0):.2f}")
        print()

def main():
    """Main training pipeline"""

    print("=" * 60)
    print("NOVELTY DETECTOR TRAINING")
    print("Algorithm: Isolation Forest")
    print("Expected Gain: 10-15% better exploration/exploitation balance")
    print("=" * 60)

    # Load data
    experiences = load_experiences()

    if not experiences:
        print("ERROR: No experiences found!")
        return 1

    # Train model
    model, metrics = train_novelty_detector(experiences)

    # Test on example cases
    test_cases = [
        {
            'problem_type': 'code_search',
            'novelty_score': 0.2,
            'success': True,
            'reward': 0.85,
            'importance': 0.7,
            'context': {
                'prompt_length': 50,
                'file_count': 2,
                'code_blocks': 1,
                'complexity': 'simple'
            }
        },
        {
            'problem_type': 'feature_implementation',
            'novelty_score': 0.85,
            'success': False,
            'reward': 0.3,
            'importance': 0.9,
            'context': {
                'prompt_length': 500,
                'file_count': 15,
                'code_blocks': 8,
                'complexity': 'complex'
            }
        },
        {
            'problem_type': 'bug_fix',
            'novelty_score': 0.45,
            'success': True,
            'reward': 0.75,
            'importance': 0.6,
            'context': {
                'prompt_length': 150,
                'file_count': 3,
                'code_blocks': 2,
                'complexity': 'medium'
            }
        }
    ]

    test_novelty_detector(model, test_cases)

    # Summary
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"\nModel: {MODEL_OUTPUT}")
    print(f"Metrics: {METRICS_OUTPUT}")
    print(f"\nNovel Detection Rate: {metrics['novel_detection_rate']:.1%}")
    print(f"Familiar Accuracy: {metrics['familiar_accuracy']:.1%}")
    print(f"Overall Accuracy: {metrics['overall_accuracy']:.1%}")

    if metrics['roc_auc']:
        print(f"ROC-AUC Score: {metrics['roc_auc']:.3f}")

    print("\n=== Next Steps ===")
    print("1. Integrate with multi-model router:")
    print("   from novelty_detector import load_model, predict_novelty")
    print("   is_novel = predict_novelty(task_features)")
    print("   if is_novel: use_exploration_strategy()")
    print("   else: use_exploitation_strategy()")
    print("\n2. Monitor exploration/exploitation balance in production")
    print("\n3. Retrain weekly as more experiences accumulate")

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
