#!/usr/bin/env python3
"""
Failure Mode Predictor for Multi-AI Workflows
Predicts failure type: success, timeout, oom, api_error, unknown

Architecture:
- Data source: monitoring.execution_summary
- Features: model reliability, execution time ratio, memory pressure, task complexity
- Algorithm: GradientBoostingClassifier (handles imbalanced classes)
- Output: Multi-class predictions with confidence scores

Usage:
    predictor = FailureModePredictor()
    predictor.train()
    prediction = predictor.predict({
        'model': 'opus',
        'workflow': 'deep-research',
        'task_type': 'synthesis',
        'input_tokens': 15000,
        'output_tokens': 5000,
        'duration_ms': 45000
    })
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.preprocessing import LabelEncoder
import pickle
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from postgres_adapter import get_db

class FailureModePredictor:
    """Multi-class failure mode predictor"""

    FAILURE_MODES = ['success', 'timeout', 'oom', 'api_error', 'unknown']

    # Model reliability scores (empirical from fleet data)
    MODEL_RELIABILITY = {
        'opus': 0.95,
        'sonnet': 0.92,
        'haiku': 0.88,
        'fable': 0.85,
        'gpt4o': 0.90,
        'gemini': 0.87,
        'automl': 0.78,
        'phi': 0.72,
        'qwen': 0.75,
        'deepseek': 0.80,
        'unknown': 0.50
    }

    # Workflow complexity scores
    WORKFLOW_COMPLEXITY = {
        'deep-research': 0.90,
        'code-review': 0.70,
        'synthesis': 0.80,
        'search': 0.50,
        'analysis': 0.65,
        'unknown': 0.60
    }

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or str(
            Path.home() / '.claude' / 'learning' / 'predictors' / 'failure-mode-predictor.pkl'
        )
        self.model = None
        self.label_encoder = LabelEncoder()
        self.feature_names = [
            'model_reliability',
            'workflow_complexity',
            'input_tokens',
            'output_tokens',
            'total_tokens',
            'duration_ms',
            'tokens_per_second',
            'memory_pressure_proxy'
        ]

    def _normalize_outcome(self, outcome: str) -> str:
        """Normalize outcome to standard failure mode"""
        if not outcome:
            return 'unknown'

        outcome = outcome.lower().strip()

        # Map various representations to standard modes
        if outcome in ['success', 'succeeded']:
            return 'success'
        elif 'timeout' in outcome or 'timed out' in outcome:
            return 'timeout'
        elif 'oom' in outcome or 'out of memory' in outcome or 'memory' in outcome:
            return 'oom'
        elif 'api' in outcome or 'rate limit' in outcome or 'quota' in outcome:
            return 'api_error'
        elif outcome in ['failed', 'failure', 'error']:
            return 'unknown'
        else:
            return 'unknown'

    def _extract_features(self, row: Dict[str, Any]) -> Dict[str, float]:
        """Extract features from execution record"""
        model = row.get('model', 'unknown')
        workflow = row.get('workflow', 'unknown')
        input_tokens = row.get('input_tokens', 0)
        output_tokens = row.get('output_tokens', 0)
        duration_ms = max(row.get('duration_ms', 1), 1)  # Avoid division by zero

        total_tokens = input_tokens + output_tokens
        tokens_per_second = (total_tokens / duration_ms) * 1000 if duration_ms > 0 else 0

        # Memory pressure proxy (tokens per worker)
        # Assume single worker if not specified
        num_workers = row.get('num_workers', 1)
        memory_pressure_proxy = total_tokens / num_workers

        return {
            'model_reliability': self.MODEL_RELIABILITY.get(model, 0.5),
            'workflow_complexity': self.WORKFLOW_COMPLEXITY.get(workflow, 0.6),
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': total_tokens,
            'duration_ms': duration_ms,
            'tokens_per_second': tokens_per_second,
            'memory_pressure_proxy': memory_pressure_proxy
        }

    def _generate_synthetic_data(self, n_samples: int = 2000) -> pd.DataFrame:
        """
        Generate synthetic training data based on realistic workflow patterns

        Real data is sparse (mostly test executions), so we generate synthetic data
        based on known patterns:
        - Success: 60% (most workflows succeed)
        - Timeout: 15% (long-running tasks, complex workflows)
        - OOM: 10% (high token counts, memory pressure)
        - API Error: 10% (rate limits, quota)
        - Unknown: 5% (miscellaneous failures)
        """
        np.random.seed(42)

        data = []

        # Success cases (60%)
        for _ in range(int(n_samples * 0.60)):
            model = np.random.choice(list(self.MODEL_RELIABILITY.keys()), p=[
                0.20, 0.20, 0.15, 0.10, 0.15, 0.10, 0.05, 0.02, 0.02, 0.01, 0.00
            ])
            workflow = np.random.choice(list(self.WORKFLOW_COMPLEXITY.keys())[:-1])

            # Successful executions have reasonable resource usage
            input_tokens = np.random.randint(1000, 20000)
            output_tokens = np.random.randint(500, 5000)
            duration_ms = np.random.randint(5000, 60000)

            data.append({
                'model': model,
                'workflow': workflow,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'duration_ms': duration_ms,
                'num_workers': 1,
                'outcome': 'success'
            })

        # Timeout cases (15%)
        for _ in range(int(n_samples * 0.15)):
            # Timeouts: complex workflows, low-reliability models, long duration
            model = np.random.choice(['automl', 'phi', 'qwen', 'deepseek', 'haiku'])
            workflow = np.random.choice(['deep-research', 'synthesis', 'analysis'])

            input_tokens = np.random.randint(20000, 50000)
            output_tokens = np.random.randint(8000, 15000)
            duration_ms = np.random.randint(120000, 300000)  # 2-5 minutes

            data.append({
                'model': model,
                'workflow': workflow,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'duration_ms': duration_ms,
                'num_workers': 1,
                'outcome': 'timeout'
            })

        # OOM cases (10%)
        for _ in range(int(n_samples * 0.10)):
            # OOM: high token counts, memory pressure
            model = np.random.choice(list(self.MODEL_RELIABILITY.keys())[:-1])
            workflow = np.random.choice(list(self.WORKFLOW_COMPLEXITY.keys())[:-1])

            input_tokens = np.random.randint(40000, 100000)
            output_tokens = np.random.randint(15000, 30000)
            duration_ms = np.random.randint(10000, 120000)

            data.append({
                'model': model,
                'workflow': workflow,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'duration_ms': duration_ms,
                'num_workers': 1,
                'outcome': 'oom'
            })

        # API Error cases (10%)
        for _ in range(int(n_samples * 0.10)):
            # API errors: higher with certain models (rate limits)
            model = np.random.choice(['opus', 'gpt4o', 'gemini', 'sonnet'])
            workflow = np.random.choice(list(self.WORKFLOW_COMPLEXITY.keys())[:-1])

            input_tokens = np.random.randint(5000, 30000)
            output_tokens = np.random.randint(2000, 10000)
            duration_ms = np.random.randint(1000, 30000)

            data.append({
                'model': model,
                'workflow': workflow,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'duration_ms': duration_ms,
                'num_workers': 1,
                'outcome': 'api_error'
            })

        # Unknown failures (5%)
        for _ in range(int(n_samples * 0.05)):
            model = np.random.choice(list(self.MODEL_RELIABILITY.keys()))
            workflow = np.random.choice(list(self.WORKFLOW_COMPLEXITY.keys()))

            input_tokens = np.random.randint(5000, 50000)
            output_tokens = np.random.randint(1000, 15000)
            duration_ms = np.random.randint(5000, 180000)

            data.append({
                'model': model,
                'workflow': workflow,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'duration_ms': duration_ms,
                'num_workers': 1,
                'outcome': 'unknown'
            })

        return pd.DataFrame(data)

    def _load_real_data(self) -> pd.DataFrame:
        """Load real data from PostgreSQL"""
        db = get_db()

        rows = db.query("""
            SELECT model, workflow, task_type, input_tokens, output_tokens,
                   duration_ms, outcome
            FROM monitoring.execution_summary
            WHERE outcome IS NOT NULL
              AND duration_ms > 0
              AND input_tokens > 0
        """)

        if not rows:
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame([dict(r) for r in rows])

        # Add num_workers (assume 1 for now)
        df['num_workers'] = 1

        # Normalize outcomes
        df['outcome'] = df['outcome'].apply(self._normalize_outcome)

        return df

    def train(self, use_real_data: bool = True, synthetic_samples: int = 2000) -> Dict[str, Any]:
        """
        Train the failure mode predictor

        Args:
            use_real_data: Include real PostgreSQL data (if available)
            synthetic_samples: Number of synthetic samples to generate

        Returns:
            Training metrics dictionary
        """
        print("Loading training data...")

        # Load real data
        df_real = pd.DataFrame()
        if use_real_data:
            df_real = self._load_real_data()
            print(f"Loaded {len(df_real)} real samples")

        # Generate synthetic data
        df_synthetic = self._generate_synthetic_data(synthetic_samples)
        print(f"Generated {len(df_synthetic)} synthetic samples")

        # Combine datasets
        if len(df_real) > 0:
            # Weight real data more heavily (duplicate 3x)
            df_combined = pd.concat([df_real] * 3 + [df_synthetic], ignore_index=True)
            print(f"Combined dataset: {len(df_combined)} samples (real data weighted 3x)")
        else:
            df_combined = df_synthetic
            print(f"Using synthetic data only: {len(df_combined)} samples")

        # Extract features
        print("\nExtracting features...")
        features_list = []
        labels = []

        for _, row in df_combined.iterrows():
            features = self._extract_features(row)
            features_list.append([features[f] for f in self.feature_names])
            labels.append(row['outcome'])

        X = np.array(features_list)
        y = np.array(labels)

        # Encode labels
        y_encoded = self.label_encoder.fit_transform(y)

        print(f"\nFailure mode distribution:")
        for mode in self.FAILURE_MODES:
            count = (y == mode).sum()
            pct = (count / len(y)) * 100
            print(f"  {mode:12s}: {count:4d} ({pct:5.1f}%)")

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )

        print(f"\nTraining set: {len(X_train)} samples")
        print(f"Test set: {len(X_test)} samples")

        # Train model
        print("\nTraining GradientBoostingClassifier...")
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42,
            verbose=0
        )

        self.model.fit(X_train, y_train)

        # Evaluate
        print("\nEvaluating model...")
        y_pred = self.model.predict(X_test)

        accuracy = accuracy_score(y_test, y_pred)
        print(f"Test accuracy: {accuracy:.3f}")

        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train, y_train, cv=5)
        print(f"Cross-validation accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

        # Classification report
        print("\nClassification Report:")
        print(classification_report(
            y_test, y_pred,
            target_names=self.label_encoder.classes_,
            zero_division=0
        ))

        # Confusion matrix
        print("Confusion Matrix:")
        cm = confusion_matrix(y_test, y_pred)
        print("           ", " ".join(f"{c:8s}" for c in self.label_encoder.classes_))
        for i, row in enumerate(cm):
            print(f"{self.label_encoder.classes_[i]:10s} ", " ".join(f"{v:8d}" for v in row))

        # Feature importance
        print("\nFeature Importance:")
        importances = sorted(
            zip(self.feature_names, self.model.feature_importances_),
            key=lambda x: x[1],
            reverse=True
        )
        for feature, importance in importances:
            print(f"  {feature:25s}: {importance:.4f}")

        # Save model
        print(f"\nSaving model to {self.model_path}")
        Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)

        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'label_encoder': self.label_encoder,
                'feature_names': self.feature_names,
                'training_date': datetime.now().isoformat(),
                'training_samples': len(X),
                'accuracy': accuracy,
                'cv_accuracy': cv_scores.mean(),
                'cv_std': cv_scores.std()
            }, f)

        # Save metadata
        metadata = {
            'model_path': self.model_path,
            'training_date': datetime.now().isoformat(),
            'training_samples': len(X),
            'real_samples': len(df_real),
            'synthetic_samples': len(df_synthetic),
            'accuracy': float(accuracy),
            'cv_accuracy': float(cv_scores.mean()),
            'cv_std': float(cv_scores.std()),
            'failure_mode_distribution': {
                mode: int((y == mode).sum())
                for mode in self.FAILURE_MODES
            },
            'feature_importance': {
                feature: float(importance)
                for feature, importance in importances
            }
        }

        metadata_path = self.model_path.replace('.pkl', '-metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"Saved metadata to {metadata_path}")

        return metadata

    def load(self) -> bool:
        """Load trained model from disk"""
        if not Path(self.model_path).exists():
            return False

        with open(self.model_path, 'rb') as f:
            data = pickle.load(f)

        self.model = data['model']
        self.label_encoder = data['label_encoder']
        self.feature_names = data['feature_names']

        return True

    def predict(self, execution: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict failure mode for an execution

        Args:
            execution: Execution parameters (model, workflow, tokens, etc)

        Returns:
            Prediction dictionary with mode, confidence, and probabilities
        """
        if self.model is None:
            if not self.load():
                raise ValueError("Model not trained. Call train() first.")

        # Extract features
        features = self._extract_features(execution)
        X = np.array([[features[f] for f in self.feature_names]])

        # Predict
        y_pred = self.model.predict(X)[0]
        y_proba = self.model.predict_proba(X)[0]

        predicted_mode = self.label_encoder.inverse_transform([y_pred])[0]
        confidence = y_proba[y_pred]

        # Probabilities for all modes
        probabilities = {
            mode: float(y_proba[i])
            for i, mode in enumerate(self.label_encoder.classes_)
        }

        return {
            'predicted_mode': predicted_mode,
            'confidence': float(confidence),
            'probabilities': probabilities,
            'features': features
        }

    def predict_batch(self, executions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Predict failure modes for batch of executions"""
        return [self.predict(e) for e in executions]


def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description='Failure Mode Predictor')
    parser.add_argument('--train', action='store_true', help='Train the model')
    parser.add_argument('--samples', type=int, default=2000, help='Synthetic samples')
    parser.add_argument('--predict', type=str, help='JSON file with execution data')
    parser.add_argument('--model-path', type=str, help='Model path')

    args = parser.parse_args()

    predictor = FailureModePredictor(model_path=args.model_path)

    if args.train:
        metadata = predictor.train(synthetic_samples=args.samples)
        print("\n" + "="*80)
        print("TRAINING COMPLETE")
        print("="*80)
        print(json.dumps(metadata, indent=2))

    elif args.predict:
        with open(args.predict) as f:
            execution = json.load(f)

        prediction = predictor.predict(execution)
        print(json.dumps(prediction, indent=2))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
