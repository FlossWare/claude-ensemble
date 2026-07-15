#!/usr/bin/env python3
"""
Resource Usage Predictor

Trains a model to predict token usage, duration, and cost for workflow tasks
based on historical execution data from monitoring.execution_summary.

Features:
- Multi-output regression (tokens_in, tokens_out, duration_ms, cost_usd)
- Task embeddings via sentence-transformers
- Model/workflow/task_type categorical encoding
- 80/20 train/test split with evaluation metrics
- Saves trained model to ~/.claude/learning/resource_usage_predictor.pkl

Usage:
    python3 resource_usage_predictor.py
    python3 resource_usage_predictor.py --retrain  # Force retrain
"""

import sys
import json
import pickle
from pathlib import Path
from datetime import datetime
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Add postgres adapter to path
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))
from postgres_adapter import get_db

# Sentence transformers for task description embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    print("WARNING: sentence-transformers not available, using dummy embeddings")
    EMBEDDINGS_AVAILABLE = False


class ResourceUsagePredictor:
    """Predict resource usage (tokens, duration, cost) for workflow tasks."""

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.model_encoder = LabelEncoder()
        self.workflow_encoder = LabelEncoder()
        self.task_type_encoder = LabelEncoder()
        self.embedding_model = None
        self.feature_dim = None
        self.target_names = ['input_tokens', 'output_tokens', 'duration_ms', 'cost_usd']

        if EMBEDDINGS_AVAILABLE:
            self.embedding_model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

    def _generate_embedding(self, text):
        """Generate 384-dim embedding for task description."""
        if self.embedding_model:
            return self.embedding_model.encode(text)
        else:
            # Dummy embedding if transformers unavailable
            return np.random.randn(384)

    def _prepare_features(self, rows, fit_encoders=False):
        """Convert database rows to feature matrix."""
        features = []
        targets = []

        for row in rows:
            # Categorical features
            model = row['model']
            workflow = row['workflow'] or 'unknown'
            task_type = row['task_type'] or 'unknown'

            # Encode categoricals
            if fit_encoders:
                model_enc = self.model_encoder.fit_transform([model])[0]
                workflow_enc = self.workflow_encoder.fit_transform([workflow])[0]
                task_type_enc = self.task_type_encoder.fit_transform([task_type])[0]
            else:
                # Handle unseen categories
                try:
                    model_enc = self.model_encoder.transform([model])[0]
                except ValueError:
                    model_enc = -1
                try:
                    workflow_enc = self.workflow_encoder.transform([workflow])[0]
                except ValueError:
                    workflow_enc = -1
                try:
                    task_type_enc = self.task_type_encoder.transform([task_type])[0]
                except ValueError:
                    task_type_enc = -1

            # Task description embedding
            task_desc = f"{workflow} {task_type}"
            task_emb = self._generate_embedding(task_desc)

            # Combine features: [model_enc, workflow_enc, task_type_enc, embedding...]
            feat = np.concatenate([
                [model_enc, workflow_enc, task_type_enc],
                task_emb
            ])
            features.append(feat)

            # Targets: [input_tokens, output_tokens, duration_ms, cost_usd]
            target = [
                row['input_tokens'] or 0,
                row['output_tokens'] or 0,
                row['duration_ms'] or 0,
                row['cost_usd'] or 0.0
            ]
            targets.append(target)

        return np.array(features), np.array(targets)

    def train(self, min_samples=100):
        """Train predictor on historical execution data."""
        db = get_db()

        # Fetch all execution data (only successful outcomes for clean training)
        rows = db.query("""
            SELECT model, workflow, task_type,
                   input_tokens, output_tokens, duration_ms, cost_usd, outcome
            FROM monitoring.execution_summary
            WHERE outcome = 'success'
            ORDER BY id
        """)

        if len(rows) < min_samples:
            raise ValueError(f"Insufficient data: {len(rows)} samples (need {min_samples})")

        print(f"Training on {len(rows)} execution samples...")

        # Prepare features and targets
        X, y = self._prepare_features(rows, fit_encoders=True)
        self.feature_dim = X.shape[1]

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        print(f"  Train: {len(X_train)} samples")
        print(f"  Test:  {len(X_test)} samples")
        print(f"  Features: {self.feature_dim} dimensions")

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train multi-output regressor
        base_model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        self.model = MultiOutputRegressor(base_model, n_jobs=-1)

        print("\nTraining model...")
        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)

        print("\nEvaluation Metrics:")
        print("=" * 80)
        for i, target_name in enumerate(self.target_names):
            mae = mean_absolute_error(y_test[:, i], y_pred[:, i])
            rmse = np.sqrt(mean_squared_error(y_test[:, i], y_pred[:, i]))
            r2 = r2_score(y_test[:, i], y_pred[:, i])

            print(f"{target_name:15s}  MAE: {mae:10.2f}  RMSE: {rmse:10.2f}  R²: {r2:6.3f}")

        print("=" * 80)

        return {
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'feature_dim': self.feature_dim,
            'metrics': {
                self.target_names[i]: {
                    'mae': float(mean_absolute_error(y_test[:, i], y_pred[:, i])),
                    'rmse': float(np.sqrt(mean_squared_error(y_test[:, i], y_pred[:, i]))),
                    'r2': float(r2_score(y_test[:, i], y_pred[:, i]))
                }
                for i in range(len(self.target_names))
            }
        }

    def predict(self, model, workflow, task_type, task_description=None):
        """Predict resource usage for a task."""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # Prepare single feature vector
        task_desc = task_description or f"{workflow} {task_type}"

        # Encode categoricals (handle unseen)
        try:
            model_enc = self.model_encoder.transform([model])[0]
        except ValueError:
            model_enc = -1  # Unseen model

        try:
            workflow_enc = self.workflow_encoder.transform([workflow])[0]
        except ValueError:
            workflow_enc = -1

        try:
            task_type_enc = self.task_type_encoder.transform([task_type])[0]
        except ValueError:
            task_type_enc = -1

        # Task embedding
        task_emb = self._generate_embedding(task_desc)

        # Combine features
        feat = np.concatenate([
            [model_enc, workflow_enc, task_type_enc],
            task_emb
        ]).reshape(1, -1)

        # Scale and predict
        feat_scaled = self.scaler.transform(feat)
        pred = self.model.predict(feat_scaled)[0]

        return {
            'input_tokens': max(0, int(pred[0])),
            'output_tokens': max(0, int(pred[1])),
            'duration_ms': max(0, int(pred[2])),
            'cost_usd': max(0.0, float(pred[3]))
        }

    def save(self, path):
        """Save trained model to disk."""
        data = {
            'model': self.model,
            'scaler': self.scaler,
            'model_encoder': self.model_encoder,
            'workflow_encoder': self.workflow_encoder,
            'task_type_encoder': self.task_type_encoder,
            'feature_dim': self.feature_dim,
            'target_names': self.target_names,
            'embeddings_available': EMBEDDINGS_AVAILABLE
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)
        print(f"\nModel saved to: {path}")

    @classmethod
    def load(cls, path):
        """Load trained model from disk."""
        with open(path, 'rb') as f:
            data = pickle.load(f)

        predictor = cls()
        predictor.model = data['model']
        predictor.scaler = data['scaler']
        predictor.model_encoder = data['model_encoder']
        predictor.workflow_encoder = data['workflow_encoder']
        predictor.task_type_encoder = data['task_type_encoder']
        predictor.feature_dim = data['feature_dim']
        predictor.target_names = data['target_names']

        return predictor


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Train resource usage predictor')
    parser.add_argument('--retrain', action='store_true', help='Force retrain even if model exists')
    parser.add_argument('--output', default=str(Path.home() / '.claude' / 'learning' / 'resource_usage_predictor.pkl'),
                       help='Output path for trained model')
    parser.add_argument('--stats-output', default=str(Path.home() / '.claude' / 'learning' / 'resource_usage_predictor_stats.json'),
                       help='Output path for training statistics')
    args = parser.parse_args()

    output_path = Path(args.output)
    stats_path = Path(args.stats_output)

    # Check if model exists
    if output_path.exists() and not args.retrain:
        print(f"Model already exists: {output_path}")
        print("Use --retrain to force retraining")

        # Test prediction
        predictor = ResourceUsagePredictor.load(output_path)
        test_pred = predictor.predict(
            model='opus',
            workflow='deep-research',
            task_type='research',
            task_description='Research quantum computing applications'
        )
        print("\nTest prediction (opus, deep-research, research):")
        for key, val in test_pred.items():
            print(f"  {key}: {val}")

        return

    # Train new model
    predictor = ResourceUsagePredictor()
    stats = predictor.train()

    # Save model
    output_path.parent.mkdir(parents=True, exist_ok=True)
    predictor.save(output_path)

    # Save statistics
    stats['timestamp'] = datetime.now().isoformat()
    stats['model_path'] = str(output_path)
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Statistics saved to: {stats_path}")

    # Test prediction
    test_pred = predictor.predict(
        model='opus',
        workflow='deep-research',
        task_type='research',
        task_description='Research quantum computing applications'
    )
    print("\nTest prediction (opus, deep-research, research):")
    for key, val in test_pred.items():
        print(f"  {key}: {val}")


if __name__ == '__main__':
    main()
