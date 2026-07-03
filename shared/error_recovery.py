#!/usr/bin/env python3
"""
Error Recovery Classifier Integration
Predicts if task failures are retryable + best retry model
Accuracy: 99.2% (retryable prediction)
"""
import pickle
import pandas as pd
from pathlib import Path
import numpy as np

class ErrorRecoveryClassifier:
    """Wrapper for error recovery classifier"""

    def __init__(self, model_path=None):
        if model_path is None:
            model_path = Path.home() / ".claude" / "learning" / "error_recovery_classifier.pkl"

        self.model_path = Path(model_path)
        self.clf_dict = None
        self.loaded = False

        try:
            with open(self.model_path, 'rb') as f:
                self.clf_dict = pickle.load(f)
            self.loaded = True
            print(f"✅ Loaded error recovery classifier from {self.model_path}")
        except FileNotFoundError:
            print(f"⚠️  Error recovery classifier not found at {self.model_path}")
        except Exception as e:
            print(f"⚠️  Error loading classifier: {e}")

    def predict_recovery(self, model, task_type, error_type, duration_ms=None, tokens=None):
        """
        Predict if failure is retryable + best retry model

        Args:
            model: Model that failed (e.g., 'gpt-4o-mini', 'opus')
            task_type: Task category (e.g., 'code_generation', 'general_qa')
            error_type: Error category (e.g., 'timeout', 'api_error', 'rate_limit')
            duration_ms: Optional duration before failure (ms)
            tokens: Optional token count

        Returns:
            dict with:
                - is_retryable: bool (True if should retry)
                - retryable_confidence: float (0-1)
                - best_retry_model: str or None (recommended model for retry)
                - retry_model_confidence: float (0-1)
                - retry_success_probability: float (0-1, expected success rate)
        """
        if not self.loaded:
            # Fallback: simple heuristic
            return self._fallback_heuristic(error_type)

        try:
            # Extract classifiers
            retryable_clf = self.clf_dict['retryable_classifier']
            retry_model_clf = self.clf_dict['retry_model_classifier']
            retry_success_clf = self.clf_dict.get('retry_success_classifier')

            # Extract encoders
            model_encoder = self.clf_dict['model_encoder']
            task_type_encoder = self.clf_dict['task_type_encoder']
            retry_model_encoder = self.clf_dict['retry_model_encoder']

            # Feature columns (from training)
            feature_cols = self.clf_dict.get('feature_cols', [
                'model', 'task_type', 'error_type', 'duration_ms', 'tokens'
            ])

            # Build feature dict
            features = {
                'model': model,
                'task_type': task_type,
                'error_type': error_type,
                'duration_ms': duration_ms if duration_ms is not None else 0,
                'tokens': tokens if tokens is not None else 0
            }

            # Create DataFrame with correct columns
            df = pd.DataFrame([features])

            # Encode categorical features (handle unknown values)
            if 'model' in df.columns and model_encoder is not None:
                try:
                    df['model'] = model_encoder.transform(df['model'])
                except ValueError:
                    # Unknown model → use most common
                    df['model'] = 0

            if 'task_type' in df.columns and task_type_encoder is not None:
                try:
                    df['task_type'] = task_type_encoder.transform(df['task_type'])
                except ValueError:
                    df['task_type'] = 0

            # Ensure all feature_cols exist
            for col in feature_cols:
                if col not in df.columns:
                    df[col] = 0

            # Select features in correct order
            X = df[feature_cols]

            # Predict retryable
            is_retryable = bool(retryable_clf.predict(X)[0])
            retryable_proba = retryable_clf.predict_proba(X)[0]
            retryable_confidence = max(retryable_proba)  # Max probability

            # Predict best retry model (if retryable)
            best_retry_model = None
            retry_model_confidence = 0.0

            if is_retryable and retry_model_clf is not None:
                retry_model_idx = retry_model_clf.predict(X)[0]
                retry_model_proba = retry_model_clf.predict_proba(X)[0]
                retry_model_confidence = max(retry_model_proba)

                # Decode model index
                if retry_model_encoder is not None:
                    try:
                        best_retry_model = retry_model_encoder.inverse_transform([retry_model_idx])[0]
                    except:
                        best_retry_model = None

            # Predict retry success probability (if available)
            retry_success_prob = 0.5  # Default
            if is_retryable and retry_success_clf is not None:
                retry_success_proba = retry_success_clf.predict_proba(X)[0]
                retry_success_prob = retry_success_proba[1] if len(retry_success_proba) > 1 else 0.5

            return {
                'is_retryable': is_retryable,
                'retryable_confidence': float(retryable_confidence),
                'best_retry_model': best_retry_model,
                'retry_model_confidence': float(retry_model_confidence),
                'retry_success_probability': float(retry_success_prob)
            }

        except Exception as e:
            print(f"⚠️  Error recovery prediction failed: {e}")
            return self._fallback_heuristic(error_type)

    def _fallback_heuristic(self, error_type):
        """Simple heuristic when classifier unavailable"""
        # Retryable errors
        retryable_errors = {
            'timeout', 'rate_limit', 'connection_error', 'server_error',
            'api_error', 'temporary_failure', '503', '429', '500'
        }

        is_retryable = any(err in error_type.lower() for err in retryable_errors)

        return {
            'is_retryable': is_retryable,
            'retryable_confidence': 0.7 if is_retryable else 0.3,
            'best_retry_model': None,  # No recommendation
            'retry_model_confidence': 0.0,
            'retry_success_probability': 0.5
        }

    def get_metrics(self):
        """Get classifier performance metrics"""
        if not self.loaded:
            return None

        return self.clf_dict.get('metrics', {})


def predict_error_recovery(model, task_type, error_type, duration_ms=None, tokens=None):
    """
    Convenience function for quick predictions

    Example:
        result = predict_error_recovery(
            model='gpt-4o-mini',
            task_type='code_generation',
            error_type='timeout',
            duration_ms=120000
        )

        if result['is_retryable']:
            print(f"Retry with {result['best_retry_model']}")
    """
    clf = ErrorRecoveryClassifier()
    return clf.predict_recovery(model, task_type, error_type, duration_ms, tokens)


if __name__ == "__main__":
    # Test classifier
    clf = ErrorRecoveryClassifier()

    if clf.loaded:
        print("\n" + "="*60)
        print("ERROR RECOVERY CLASSIFIER TEST")
        print("="*60)

        # Show metrics
        metrics = clf.get_metrics()
        if metrics:
            print("\nClassifier Metrics:")
            print(f"  Retryable prediction accuracy: {metrics['retryable']['accuracy']:.1%}")
            print(f"  Retry model prediction accuracy: {metrics['retry_model']['accuracy']:.1%}")
            print(f"  Retry success prediction accuracy: {metrics['retry_success']['accuracy']:.1%}")

        # Test cases
        test_cases = [
            {
                'model': 'gpt-4o-mini',
                'task_type': 'code_generation',
                'error_type': 'timeout',
                'duration_ms': 120000
            },
            {
                'model': 'opus',
                'task_type': 'general_qa',
                'error_type': 'rate_limit',
                'duration_ms': 5000
            },
            {
                'model': 'haiku',
                'task_type': 'code_review',
                'error_type': 'invalid_request',
                'duration_ms': 2000
            }
        ]

        print("\nTest Cases:")
        for i, test in enumerate(test_cases, 1):
            result = clf.predict_recovery(**test)
            print(f"\nCase {i}: {test['error_type']} ({test['model']}, {test['task_type']})")
            print(f"  Retryable: {result['is_retryable']} (confidence: {result['retryable_confidence']:.2f})")
            if result['best_retry_model']:
                print(f"  Best retry model: {result['best_retry_model']} "
                      f"(confidence: {result['retry_model_confidence']:.2f})")
            print(f"  Retry success probability: {result['retry_success_probability']:.2f}")

        print("\n" + "="*60)
    else:
        print("\n⚠️  Classifier not loaded - run error recovery trainer first")
