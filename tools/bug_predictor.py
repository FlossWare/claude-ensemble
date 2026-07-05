#!/usr/bin/env python3
"""
Bug Likelihood Predictor - Random Forest Classifier

Predicts the probability of bugs/errors before task execution based on:
- Task characteristics (length, keywords, complexity)
- Historical failure patterns
- Model performance on similar tasks
- Code language and operation type

Algorithm: Random Forest Classifier with probability estimates
Training data: Execution logs from SQLite learning.db
Output: Bug probability (0.0-1.0) and risk category
"""

import json
import re
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
from collections import Counter
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
import pickle


class BugPredictor:
    """Predicts bug likelihood before task execution"""

    def __init__(self):
        self.model = None
        self.features = []
        self.training_stats = {}
        self.class_weights = None

    def extract_features(self, task_description, model=None, workflow=None, task_type=None):
        """Extract features from task metadata"""
        text = task_description.lower() if task_description else ""

        # Basic text features
        features = {
            'prompt_length': len(task_description) if task_description else 0,
            'word_count': len(task_description.split()) if task_description else 0,

            # Operation keywords (bug indicators)
            'num_implement': text.count('implement'),
            'num_fix': text.count('fix'),
            'num_review': text.count('review'),
            'num_create': text.count('create'),
            'num_update': text.count('update'),
            'num_analyze': text.count('analyze'),
            'num_test': text.count('test'),
            'num_refactor': text.count('refactor'),
            'num_debug': text.count('debug'),
            'num_optimize': text.count('optimize'),

            # File and code indicators
            'file_mentions': len(re.findall(r'\.\w{2,4}\b', task_description)) if task_description else 0,
            'code_blocks': text.count('```'),
            'has_path': 1 if re.search(r'[/\\]', text) else 0,

            # Language indicators (higher complexity = higher bug risk)
            'has_java': 1 if 'java' in text else 0,
            'has_python': 1 if 'python' in text else 0,
            'has_javascript': 1 if 'javascript' in text or ' js' in text else 0,
            'has_c_cpp': 1 if (' c ' in text or 'c++' in text or 'cpp' in text) else 0,
            'has_sql': 1 if 'sql' in text else 0,

            # Explicit bug/error mentions
            'has_bug': 1 if 'bug' in text else 0,
            'has_error': 1 if 'error' in text else 0,
            'has_crash': 1 if 'crash' in text else 0,
            'has_fail': 1 if 'fail' in text else 0,
            'has_exception': 1 if 'exception' in text else 0,

            # Complexity indicators
            'has_performance': 1 if 'performance' in text or 'optimize' in text else 0,
            'has_security': 1 if 'security' in text or 'vulnerability' in text else 0,
            'has_parallel': 1 if 'parallel' in text or 'concurrent' in text else 0,
            'has_async': 1 if 'async' in text or 'asynchronous' in text else 0,
            'has_distributed': 1 if 'distributed' in text else 0,

            # Sentiment indicators
            'num_questions': text.count('?'),
            'num_exclamations': text.count('!'),
            'has_urgent': 1 if 'urgent' in text or 'critical' in text or 'asap' in text else 0,

            # Multi-file/complex operations
            'has_multiple': 1 if 'multiple' in text or 'several' in text or 'all' in text else 0,
            'has_entire': 1 if 'entire' in text or 'whole' in text or 'complete' in text else 0,
        }

        # Model-specific features (some models have higher failure rates)
        if model:
            model_lower = model.lower()
            features.update({
                'model_is_haiku': 1 if 'haiku' in model_lower else 0,
                'model_is_opus': 1 if 'opus' in model_lower else 0,
                'model_is_sonnet': 1 if 'sonnet' in model_lower else 0,
                'model_is_gpt': 1 if 'gpt' in model_lower else 0,
                'model_is_gemini': 1 if 'gemini' in model_lower else 0,
                'model_is_local': 1 if any(x in model_lower for x in ['llama', 'mistral', 'qwen', 'phi']) else 0,
            })
        else:
            features.update({
                'model_is_haiku': 0,
                'model_is_opus': 0,
                'model_is_sonnet': 0,
                'model_is_gpt': 0,
                'model_is_gemini': 0,
                'model_is_local': 0,
            })

        # Workflow-specific features
        if workflow:
            workflow_lower = workflow.lower()
            features.update({
                'workflow_is_review': 1 if 'review' in workflow_lower else 0,
                'workflow_is_consensus': 1 if 'consensus' in workflow_lower else 0,
                'workflow_is_research': 1 if 'research' in workflow_lower else 0,
                'workflow_is_code': 1 if 'code' in workflow_lower else 0,
            })
        else:
            features.update({
                'workflow_is_review': 0,
                'workflow_is_consensus': 0,
                'workflow_is_research': 0,
                'workflow_is_code': 0,
            })

        # Task type features
        if task_type:
            task_type_lower = task_type.lower()
            features.update({
                'task_is_security': 1 if 'security' in task_type_lower else 0,
                'task_is_refactor': 1 if 'refactor' in task_type_lower else 0,
                'task_is_test': 1 if 'test' in task_type_lower else 0,
            })
        else:
            features.update({
                'task_is_security': 0,
                'task_is_refactor': 0,
                'task_is_test': 0,
            })

        return features

    def load_training_data_from_db(self, db_path):
        """Load execution logs from SQLite database"""
        print(f"Loading training data from {db_path}...")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get execution logs - use quality_score and error to determine bugs
        cursor.execute("""
            SELECT
                task_description,
                model,
                workflow,
                task_type,
                outcome,
                quality_score,
                duration_ms,
                error
            FROM execution_log
            WHERE task_description IS NOT NULL
              AND task_description != ''
              AND (
                  outcome IN ('success', 'failed', 'error')
                  OR quality_score IS NOT NULL
                  OR error IS NOT NULL
              )
            ORDER BY timestamp DESC
            LIMIT 5000
        """)

        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 10:
            print(f"⚠ Only {len(rows)} training examples from DB - will use synthetic data")
            return None

        # Convert to training data
        training_data = []
        for task_desc, model, workflow, task_type, outcome, quality, duration, error in rows:
            features = self.extract_features(task_desc, model, workflow, task_type)

            # Label: Infer bug from multiple signals
            has_bug = 0
            if outcome in ('failed', 'error', 'failure'):
                has_bug = 1
            elif error is not None and error != '':
                has_bug = 1
            elif quality is not None and quality < 0.4:  # Low quality indicates bug
                has_bug = 1

            # Add quality score as feature if available
            if quality is not None:
                features['historical_quality'] = float(quality)
            else:
                features['historical_quality'] = 0.5  # neutral

            # Add duration as feature if available
            if duration:
                features['historical_duration'] = min(duration, 300000) / 1000.0  # cap at 5min, scale to seconds
            else:
                features['historical_duration'] = 0.0

            training_data.append({
                'task': task_desc,
                'features': features,
                'has_bug': has_bug,
                'outcome': outcome,
            })

        print(f"✅ Loaded {len(training_data)} training examples from database")

        # Show class distribution
        bug_count = sum(1 for d in training_data if d['has_bug'] == 1)
        success_count = len(training_data) - bug_count
        print(f"   Bugs/Errors: {bug_count} ({100*bug_count/len(training_data):.1f}%)")
        print(f"   Success:     {success_count} ({100*success_count/len(training_data):.1f}%)")

        return training_data

    def generate_synthetic_training_data(self, n_samples=1000):
        """Generate synthetic training data with realistic bug patterns"""
        print(f"Generating {n_samples} synthetic training examples...")

        # Task templates with bug likelihood (task, model, workflow, task_type, bug_probability)
        task_templates = [
            # Low bug risk (0-20%)
            ("Fix typo in README.md", "sonnet", None, None, 0.05),
            ("Update variable name from x to count", "haiku", "code", "refactor", 0.10),
            ("Add comment to explain algorithm", "opus", None, None, 0.05),
            ("Review documentation for completeness", "sonnet", "review", None, 0.08),
            ("Create simple hello world script", "haiku", "code", None, 0.12),

            # Medium bug risk (20-50%)
            ("Implement new user authentication endpoint", "sonnet", "code", None, 0.35),
            ("Refactor database query to use prepared statements", "opus", "code", "refactor", 0.30),
            ("Create unit tests for payment processing", "haiku", "code", "test", 0.25),
            ("Update API to handle edge cases", "gpt-4o", "code", None, 0.40),
            ("Fix bug in error handling logic", "sonnet", "code", None, 0.38),

            # High bug risk (50-80%)
            ("IMPLEMENT complete OAuth2 flow with JWT tokens and refresh", "haiku", "code", "security", 0.65),
            ("FIX critical security vulnerability in authentication system", "opus", "review", "security", 0.70),
            ("Debug NullPointerException in Java multi-threaded payment processor", "gpt-4o", "code", None, 0.75),
            ("Refactor entire async/await patterns across all services", "haiku", "code", "refactor", 0.68),
            ("Implement distributed transaction coordinator with rollback", "sonnet", "code", None, 0.72),
            ("Fix crash in C++ memory management for concurrent access", "opus", "code", None, 0.78),

            # Very high bug risk (80-95%)
            ("URGENT: Fix production crash in multi-threaded async job queue", "haiku", "code", None, 0.85),
            ("Debug race condition in distributed consensus algorithm", "gpt-4o", "code", None, 0.88),
            ("Fix all security vulnerabilities in entire codebase", "haiku", "review", "security", 0.90),
            ("Implement complete distributed system with leader election and replication", "opus", "code", None, 0.92),
            ("CRITICAL: Fix memory leak causing production crashes every hour", "sonnet", "code", None, 0.87),
        ]

        training_data = []

        for _ in range(n_samples):
            # Pick random template
            template, model, workflow, task_type, base_bug_prob = task_templates[
                np.random.randint(len(task_templates))
            ]

            # Add random variation to bug probability
            bug_probability = min(0.95, max(0.05, base_bug_prob + np.random.uniform(-0.1, 0.1)))

            # Determine if this sample has a bug
            has_bug = 1 if np.random.random() < bug_probability else 0

            # Optionally add complexity modifiers
            task = template
            if np.random.random() < 0.2:
                task += " with error handling"
                bug_probability *= 1.15
            if np.random.random() < 0.15:
                task += " and comprehensive tests"
                bug_probability *= 0.9

            # Extract features
            features = self.extract_features(task, model, workflow, task_type)

            # Add synthetic quality/duration based on bug status
            if has_bug:
                features['historical_quality'] = np.random.uniform(0.2, 0.5)
                features['historical_duration'] = np.random.uniform(20, 120)  # seconds
            else:
                features['historical_quality'] = np.random.uniform(0.6, 0.95)
                features['historical_duration'] = np.random.uniform(5, 60)  # seconds

            training_data.append({
                'task': task,
                'features': features,
                'has_bug': has_bug,
                'outcome': 'failed' if has_bug else 'success',
            })

        return training_data

    def train(self, training_data=None, db_path=None, use_synthetic=True):
        """Train Random Forest classifier for bug prediction"""

        # Load data from database if not provided
        if training_data is None:
            if db_path is None:
                db_path = Path.home() / "Development" / "redhat" / "scm" / "gitlab" / "cee" / "sfloess" / "claude-global-skills" / "learning" / "db" / "learning.db"

            training_data = self.load_training_data_from_db(db_path)

            # Fall back to synthetic data if insufficient real data
            if training_data is None or len(training_data) < 10:
                if use_synthetic:
                    print("⚠ Insufficient real data - generating synthetic training data")
                    training_data = self.generate_synthetic_training_data(n_samples=1000)
                else:
                    raise ValueError("Insufficient training data - need at least 10 examples")

        # Extract features and labels
        feature_names = list(training_data[0]['features'].keys())
        X = np.array([[sample['features'][f] for f in feature_names]
                      for sample in training_data])
        y = np.array([sample['has_bug'] for sample in training_data])

        # Handle class imbalance with class weights
        bug_count = np.sum(y)
        success_count = len(y) - bug_count
        if bug_count > 0 and success_count > 0:
            self.class_weights = {
                0: len(y) / (2 * success_count),  # success
                1: len(y) / (2 * bug_count)       # bug
            }
        else:
            self.class_weights = {0: 1.0, 1: 1.0}

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print(f"\n📊 Training on {len(X_train)} samples, testing on {len(X_test)} samples")
        print(f"Features: {len(feature_names)}")
        print(f"Class weights: {self.class_weights}")

        # Train Random Forest with class balancing
        print("\n🌲 Training bug predictor (Random Forest Classifier)...")
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight=self.class_weights,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X_train, y_train)

        # Predictions
        y_pred_train = self.model.predict(X_train)
        y_pred_test = self.model.predict(X_test)
        y_prob_train = self.model.predict_proba(X_train)[:, 1]
        y_prob_test = self.model.predict_proba(X_test)[:, 1]

        # Evaluate
        train_acc = accuracy_score(y_train, y_pred_train)
        test_acc = accuracy_score(y_test, y_pred_test)

        # Handle case where there are no bugs in test set
        try:
            precision = precision_score(y_test, y_pred_test, zero_division=0)
            recall = recall_score(y_test, y_pred_test, zero_division=0)
            f1 = f1_score(y_test, y_pred_test, zero_division=0)
            roc_auc = roc_auc_score(y_test, y_prob_test) if len(np.unique(y_test)) > 1 else 0.5
        except Exception as e:
            print(f"⚠ Metric calculation warning: {e}")
            precision = recall = f1 = roc_auc = 0.0

        # Cross-validation
        try:
            cv_scores = cross_val_score(self.model, X_train, y_train, cv=5, scoring='roc_auc')
        except Exception as e:
            print(f"⚠ Cross-validation warning: {e}")
            cv_scores = np.array([0.5])

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred_test)

        # Store stats
        self.training_stats = {
            'n_train': len(X_train),
            'n_test': len(X_test),
            'n_features': len(feature_names),
            'feature_names': feature_names,
            'class_weights': {int(k): float(v) for k, v in self.class_weights.items()},
            'metrics': {
                'train_accuracy': float(train_acc),
                'test_accuracy': float(test_acc),
                'precision': float(precision),
                'recall': float(recall),
                'f1_score': float(f1),
                'roc_auc': float(roc_auc),
                'cv_roc_auc_mean': float(cv_scores.mean()),
                'cv_roc_auc_std': float(cv_scores.std()),
            },
            'confusion_matrix': cm.tolist(),
        }

        # Feature importance
        importance = dict(zip(feature_names, self.model.feature_importances_))
        self.training_stats['feature_importance'] = {
            k: float(v) for k, v in sorted(importance.items(), key=lambda x: x[1], reverse=True)
        }

        # Print results
        print("\n" + "="*60)
        print("📊 TRAINING RESULTS")
        print("="*60)
        print(f"\n🎯 BUG LIKELIHOOD PREDICTOR:")
        print(f"  Train Accuracy: {train_acc:.4f}")
        print(f"  Test Accuracy:  {test_acc:.4f}")
        print(f"  Precision:      {precision:.4f}")
        print(f"  Recall:         {recall:.4f}")
        print(f"  F1 Score:       {f1:.4f}")
        print(f"  ROC AUC:        {roc_auc:.4f}")
        print(f"  CV ROC AUC:     {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

        print(f"\n📋 Confusion Matrix:")
        print(f"  [[TN={cm[0,0]:4d}, FP={cm[0,1]:4d}]")
        print(f"   [FN={cm[1,0]:4d}, TP={cm[1,1]:4d}]]")

        print("\n🔝 TOP BUG INDICATORS (Feature Importance):")
        for feat, imp in list(self.training_stats['feature_importance'].items())[:10]:
            print(f"  {feat:30s} {imp:.4f}")

        return self.training_stats

    def predict(self, task_description, model=None, workflow=None, task_type=None):
        """Predict bug likelihood for a new task"""
        if self.model is None:
            raise RuntimeError("Model not trained yet - call train() first")

        features = self.extract_features(task_description, model, workflow, task_type)

        # Add default historical features if not present
        if 'historical_quality' not in features:
            features['historical_quality'] = 0.5  # neutral default
        if 'historical_duration' not in features:
            features['historical_duration'] = 0.0  # no history

        feature_names = self.training_stats['feature_names']
        X = np.array([[features.get(f, 0) for f in feature_names]])

        # Get probability and prediction
        bug_probability = self.model.predict_proba(X)[0, 1]
        prediction = self.model.predict(X)[0]

        # Risk category
        if bug_probability < 0.2:
            risk = "LOW"
        elif bug_probability < 0.4:
            risk = "MEDIUM"
        elif bug_probability < 0.6:
            risk = "HIGH"
        else:
            risk = "CRITICAL"

        # Get top contributing features
        feature_values = np.array([features[f] for f in feature_names])
        feature_importance = np.array([self.training_stats['feature_importance'][f] for f in feature_names])
        contributions = feature_values * feature_importance
        top_indices = np.argsort(contributions)[-5:][::-1]
        top_features = [(feature_names[i], features[feature_names[i]], contributions[i])
                       for i in top_indices if contributions[i] > 0]

        return {
            'bug_probability': float(bug_probability),
            'risk_category': risk,
            'prediction': 'BUG_LIKELY' if prediction == 1 else 'SUCCESS_LIKELY',
            'top_risk_factors': [
                {'feature': f, 'value': v, 'contribution': float(c)}
                for f, v, c in top_features
            ],
            'features': features
        }

    def save(self, filepath):
        """Save trained model to disk"""
        data = {
            'model': self.model,
            'training_stats': self.training_stats,
            'class_weights': self.class_weights,
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Model saved to {filepath}")

    def load(self, filepath):
        """Load trained model from disk"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.model = data['model']
        self.training_stats = data['training_stats']
        self.class_weights = data.get('class_weights', {0: 1.0, 1: 1.0})
        print(f"✅ Model loaded from {filepath}")


def main():
    """Train and evaluate the bug predictor"""

    print("=" * 60)
    print("BUG LIKELIHOOD PREDICTOR - TRAINING")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize predictor
    predictor = BugPredictor()

    # Train
    stats = predictor.train()

    # Save model
    model_path = Path.home() / ".claude" / "learning" / "bug_predictor.pkl"
    predictor.save(model_path)

    # Save stats
    stats_path = Path.home() / ".claude" / "learning" / "bug_predictor_stats.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✅ Stats saved to {stats_path}")

    # Test predictions
    print("\n" + "="*60)
    print("🧪 TESTING PREDICTIONS")
    print("="*60)

    test_tasks = [
        ("Fix typo in README", None, None, None),
        ("Implement user authentication with JWT and database", "sonnet", "code", None),
        ("CRITICAL: Fix security vulnerability in authentication", "opus", "review", "security"),
        ("Refactor entire codebase for async/await patterns", "haiku", "code", "refactor"),
        ("Debug NullPointerException in Java payment processor", "gpt-4o", "code", None),
        ("Create simple hello world script", "haiku", None, None),
    ]

    for task, model, workflow, task_type in test_tasks:
        result = predictor.predict(task, model, workflow, task_type)
        print(f"\nTask: {task}")
        if model:
            print(f"  Model: {model}")
        print(f"  Risk:        {result['risk_category']}")
        print(f"  Probability: {result['bug_probability']:.2%}")
        print(f"  Prediction:  {result['prediction']}")
        if result['top_risk_factors']:
            print(f"  Top risks:   {', '.join(f['feature'] for f in result['top_risk_factors'][:3])}")

    print("\n" + "="*60)
    print("✅ TRAINING COMPLETE")
    print("="*60)
    print(f"Model saved to: {model_path}")
    print(f"Stats saved to:  {stats_path}")

    # Return summary
    summary = {
        'status': 'SUCCESS',
        'test_accuracy': stats['metrics']['test_accuracy'],
        'roc_auc': stats['metrics']['roc_auc'],
        'precision': stats['metrics']['precision'],
        'recall': stats['metrics']['recall'],
        'f1_score': stats['metrics']['f1_score'],
        'n_train': stats['n_train'],
        'n_test': stats['n_test'],
        'model_path': str(model_path),
        'stats_path': str(stats_path),
    }

    return summary


if __name__ == "__main__":
    try:
        result = main()
        print(f"\n📊 Final Results: {json.dumps(result, indent=2)}")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
