#!/usr/bin/env python3
"""
Task Complexity Estimator - Random Forest Regression

Predicts task difficulty (duration, confidence) before execution based on:
- Prompt length
- Number of action keywords (IMPLEMENT, FIX, REVIEW, etc.)
- Mentioned file count
- Code block count
- Task type classification

Algorithm: Random Forest Regression (sklearn)
Training data: Generated from typical task patterns + real execution data if available
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import pickle

# Try to import psycopg2 for database access, but don't fail if unavailable
try:
    import psycopg2
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("⚠ psycopg2 not available - using synthetic training data")


class ComplexityEstimator:
    """Predicts task complexity before execution"""

    def __init__(self):
        self.duration_model = None
        self.confidence_model = None
        self.features = []
        self.training_stats = {}

    def extract_features(self, task_description):
        """Extract features from task description"""
        text = task_description.lower()

        features = {
            'prompt_length': len(task_description),
            'word_count': len(task_description.split()),
            'num_implement': text.count('implement'),
            'num_fix': text.count('fix'),
            'num_review': text.count('review'),
            'num_create': text.count('create'),
            'num_update': text.count('update'),
            'num_analyze': text.count('analyze'),
            'num_test': text.count('test'),
            'num_refactor': text.count('refactor'),
            'file_mentions': len(re.findall(r'\.\w{2,4}\b', task_description)),
            'code_blocks': text.count('```'),
            'has_java': 1 if 'java' in text else 0,
            'has_python': 1 if 'python' in text else 0,
            'has_javascript': 1 if 'javascript' in text or 'js' in text else 0,
            'has_bug': 1 if 'bug' in text else 0,
            'has_error': 1 if 'error' in text else 0,
            'has_performance': 1 if 'performance' in text or 'optimize' in text else 0,
            'has_security': 1 if 'security' in text or 'vulnerability' in text else 0,
            'num_questions': text.count('?'),
            'num_exclamations': text.count('!'),
        }

        return features

    def generate_synthetic_training_data(self, n_samples=500):
        """Generate synthetic training data based on typical task patterns"""
        print(f"Generating {n_samples} synthetic training examples...")

        # Task templates with expected duration (ms) and confidence
        task_templates = [
            # Simple tasks
            ("Review code in file.py", 3000, 0.85),
            ("Fix typo in README", 1500, 0.95),
            ("Update variable name", 2000, 0.90),
            ("Add comment to function", 1000, 0.95),

            # Medium tasks
            ("Implement new feature for user authentication", 15000, 0.70),
            ("Fix bug in payment processing", 12000, 0.65),
            ("Refactor database query logic", 10000, 0.70),
            ("Create unit tests for API endpoints", 18000, 0.75),
            ("Analyze performance bottleneck", 20000, 0.60),

            # Complex tasks
            ("IMPLEMENT complete OAuth2 flow with JWT tokens", 45000, 0.50),
            ("FIX security vulnerability in authentication system", 35000, 0.55),
            ("REVIEW entire codebase for best practices", 60000, 0.45),
            ("CREATE distributed task orchestration framework", 120000, 0.40),
            ("Analyze and optimize SQL query performance across 10 tables", 40000, 0.55),

            # Java/Maven tasks
            ("Implement Java service with Maven dependencies", 25000, 0.60),
            ("Fix NullPointerException in Salesforce integration", 15000, 0.65),
            ("Create Java unit tests with JUnit", 12000, 0.75),

            # Multi-file tasks
            ("Update configuration in config.yaml and apply.py", 8000, 0.80),
            ("Refactor code across 5 Python files", 30000, 0.60),
            ("Review changes in 10+ JavaScript files", 45000, 0.50),
        ]

        training_data = []

        for _ in range(n_samples):
            # Pick random template
            template, base_duration, base_confidence = task_templates[np.random.randint(len(task_templates))]

            # Add random variation
            duration = int(base_duration * np.random.uniform(0.7, 1.3))
            confidence = min(1.0, max(0.3, base_confidence + np.random.uniform(-0.1, 0.1)))

            # Optionally add more complexity
            if np.random.random() < 0.3:
                template += " with error handling"
                duration = int(duration * 1.2)
                confidence *= 0.95

            if np.random.random() < 0.2:
                template += " and tests"
                duration = int(duration * 1.4)
                confidence *= 0.90

            features = self.extract_features(template)
            training_data.append({
                'task': template,
                'features': features,
                'duration_ms': duration,
                'confidence': confidence
            })

        return training_data

    def load_database_training_data(self):
        """Load real training data from PostgreSQL if available"""
        if not DB_AVAILABLE:
            return None

        try:
            conn = psycopg2.connect(
                host="laptop-01",
                database="learning",
                user="sfloess",
                connect_timeout=5
            )

            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_assigned, duration_ms, confidence, outcome
                FROM workflow.worker_results
                WHERE duration_ms IS NOT NULL
                  AND confidence IS NOT NULL
                  AND task_assigned IS NOT NULL
                LIMIT 1000
            """)

            rows = cursor.fetchall()
            conn.close()

            if len(rows) < 10:
                return None

            training_data = []
            for task, duration, confidence, outcome in rows:
                features = self.extract_features(task)
                training_data.append({
                    'task': task,
                    'features': features,
                    'duration_ms': duration,
                    'confidence': confidence
                })

            print(f"✅ Loaded {len(training_data)} real training examples from database")
            return training_data

        except Exception as e:
            print(f"⚠ Database unavailable: {e}")
            return None

    def train(self, training_data=None):
        """Train Random Forest models for duration and confidence prediction"""

        # Load data
        if training_data is None:
            # Try database first
            training_data = self.load_database_training_data()

            # Fall back to synthetic
            if training_data is None:
                training_data = self.generate_synthetic_training_data()

        # Extract features and targets
        feature_names = list(training_data[0]['features'].keys())
        X = np.array([[sample['features'][f] for f in feature_names]
                      for sample in training_data])
        y_duration = np.array([sample['duration_ms'] for sample in training_data])
        y_confidence = np.array([sample['confidence'] for sample in training_data])

        # Split data
        X_train, X_test, y_dur_train, y_dur_test, y_conf_train, y_conf_test = train_test_split(
            X, y_duration, y_confidence, test_size=0.2, random_state=42
        )

        print(f"\n📊 Training on {len(X_train)} samples, testing on {len(X_test)} samples")
        print(f"Features: {len(feature_names)}")

        # Train duration model
        print("\n🌲 Training duration predictor (Random Forest)...")
        self.duration_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        self.duration_model.fit(X_train, y_dur_train)

        # Evaluate duration model
        dur_pred_train = self.duration_model.predict(X_train)
        dur_pred_test = self.duration_model.predict(X_test)

        dur_train_r2 = r2_score(y_dur_train, dur_pred_train)
        dur_test_r2 = r2_score(y_dur_test, dur_pred_test)
        dur_mae = mean_absolute_error(y_dur_test, dur_pred_test)
        dur_rmse = np.sqrt(mean_squared_error(y_dur_test, dur_pred_test))

        # Cross-validation
        dur_cv_scores = cross_val_score(self.duration_model, X_train, y_dur_train,
                                        cv=5, scoring='r2')

        # Train confidence model
        print("🌲 Training confidence predictor (Random Forest)...")
        self.confidence_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        self.confidence_model.fit(X_train, y_conf_train)

        # Evaluate confidence model
        conf_pred_train = self.confidence_model.predict(X_train)
        conf_pred_test = self.confidence_model.predict(X_test)

        conf_train_r2 = r2_score(y_conf_train, conf_pred_train)
        conf_test_r2 = r2_score(y_conf_test, conf_pred_test)
        conf_mae = mean_absolute_error(y_conf_test, conf_pred_test)
        conf_rmse = np.sqrt(mean_squared_error(y_conf_test, conf_pred_test))

        # Cross-validation
        conf_cv_scores = cross_val_score(self.confidence_model, X_train, y_conf_train,
                                         cv=5, scoring='r2')

        # Store stats
        self.training_stats = {
            'n_train': len(X_train),
            'n_test': len(X_test),
            'n_features': len(feature_names),
            'feature_names': feature_names,
            'duration': {
                'train_r2': float(dur_train_r2),
                'test_r2': float(dur_test_r2),
                'mae_ms': float(dur_mae),
                'rmse_ms': float(dur_rmse),
                'cv_r2_mean': float(dur_cv_scores.mean()),
                'cv_r2_std': float(dur_cv_scores.std()),
            },
            'confidence': {
                'train_r2': float(conf_train_r2),
                'test_r2': float(conf_test_r2),
                'mae': float(conf_mae),
                'rmse': float(conf_rmse),
                'cv_r2_mean': float(conf_cv_scores.mean()),
                'cv_r2_std': float(conf_cv_scores.std()),
            }
        }

        # Feature importance
        dur_importance = dict(zip(feature_names,
                                  self.duration_model.feature_importances_))
        conf_importance = dict(zip(feature_names,
                                   self.confidence_model.feature_importances_))

        self.training_stats['feature_importance'] = {
            'duration': {k: float(v) for k, v in sorted(dur_importance.items(),
                                                        key=lambda x: x[1], reverse=True)},
            'confidence': {k: float(v) for k, v in sorted(conf_importance.items(),
                                                          key=lambda x: x[1], reverse=True)}
        }

        # Print results
        print("\n" + "="*60)
        print("📊 TRAINING RESULTS")
        print("="*60)
        print(f"\n⏱️  DURATION PREDICTOR:")
        print(f"  Train R²: {dur_train_r2:.4f}")
        print(f"  Test R²:  {dur_test_r2:.4f}")
        print(f"  MAE:      {dur_mae:.0f} ms")
        print(f"  RMSE:     {dur_rmse:.0f} ms")
        print(f"  CV R²:    {dur_cv_scores.mean():.4f} ± {dur_cv_scores.std():.4f}")

        print(f"\n🎯 CONFIDENCE PREDICTOR:")
        print(f"  Train R²: {conf_train_r2:.4f}")
        print(f"  Test R²:  {conf_test_r2:.4f}")
        print(f"  MAE:      {conf_mae:.4f}")
        print(f"  RMSE:     {conf_rmse:.4f}")
        print(f"  CV R²:    {conf_cv_scores.mean():.4f} ± {conf_cv_scores.std():.4f}")

        print("\n🔝 TOP FEATURES (Duration):")
        for feat, imp in list(self.training_stats['feature_importance']['duration'].items())[:5]:
            print(f"  {feat:20s} {imp:.4f}")

        print("\n🔝 TOP FEATURES (Confidence):")
        for feat, imp in list(self.training_stats['feature_importance']['confidence'].items())[:5]:
            print(f"  {feat:20s} {imp:.4f}")

        return self.training_stats

    def predict(self, task_description):
        """Predict complexity for a new task"""
        if self.duration_model is None or self.confidence_model is None:
            raise RuntimeError("Models not trained yet - call train() first")

        features = self.extract_features(task_description)
        feature_names = self.training_stats['feature_names']
        X = np.array([[features[f] for f in feature_names]])

        duration = self.duration_model.predict(X)[0]
        confidence = self.confidence_model.predict(X)[0]

        # Clamp confidence to [0, 1]
        confidence = min(1.0, max(0.0, confidence))

        # Estimate complexity category
        if duration < 5000:
            category = "SIMPLE"
        elif duration < 20000:
            category = "MEDIUM"
        elif duration < 60000:
            category = "COMPLEX"
        else:
            category = "VERY_COMPLEX"

        return {
            'predicted_duration_ms': int(duration),
            'predicted_confidence': float(confidence),
            'complexity_category': category,
            'features': features
        }

    def save(self, filepath):
        """Save trained models to disk"""
        data = {
            'duration_model': self.duration_model,
            'confidence_model': self.confidence_model,
            'training_stats': self.training_stats,
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Models saved to {filepath}")

    def load(self, filepath):
        """Load trained models from disk"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.duration_model = data['duration_model']
        self.confidence_model = data['confidence_model']
        self.training_stats = data['training_stats']
        print(f"✅ Models loaded from {filepath}")


def main():
    """Train and evaluate the complexity estimator"""

    print("=" * 60)
    print("TASK COMPLEXITY ESTIMATOR - TRAINING")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize estimator
    estimator = ComplexityEstimator()

    # Train
    stats = estimator.train()

    # Save models
    model_path = Path.home() / ".claude" / "learning" / "complexity_estimator.pkl"
    estimator.save(model_path)

    # Save stats
    stats_path = Path.home() / ".claude" / "learning" / "complexity_estimator_stats.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✅ Stats saved to {stats_path}")

    # Test predictions
    print("\n" + "="*60)
    print("🧪 TESTING PREDICTIONS")
    print("="*60)

    test_tasks = [
        "Fix typo in README",
        "Implement user authentication with JWT",
        "REVIEW entire codebase for security vulnerabilities",
        "Create Java service with Maven and Spring Boot",
        "Analyze performance bottleneck in database queries",
    ]

    for task in test_tasks:
        result = estimator.predict(task)
        print(f"\nTask: {task}")
        print(f"  Category:   {result['complexity_category']}")
        print(f"  Duration:   {result['predicted_duration_ms']:,} ms ({result['predicted_duration_ms']/1000:.1f}s)")
        print(f"  Confidence: {result['predicted_confidence']:.2f}")

    print("\n" + "="*60)
    print("✅ TRAINING COMPLETE")
    print("="*60)
    print(f"Models saved to: {model_path}")
    print(f"Stats saved to:  {stats_path}")

    # Return summary for orchestration script
    summary = {
        'status': 'SUCCESS',
        'duration_r2': stats['duration']['test_r2'],
        'confidence_r2': stats['confidence']['test_r2'],
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
