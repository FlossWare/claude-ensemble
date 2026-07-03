#!/usr/bin/env python3
"""
Novelty Detector Integration Module
Easy-to-use wrapper for trained Isolation Forest novelty detector

Usage:
    from shared.novelty_detector import NoveltyDetector

    detector = NoveltyDetector()
    is_novel = detector.predict(task_features)

    if is_novel:
        use_exploration_strategy()
    else:
        use_exploitation_strategy()
"""

import pickle
import numpy as np
from pathlib import Path

class NoveltyDetector:
    """Wrapper for trained novelty detection model"""

    def __init__(self, model_path=None):
        """
        Load trained novelty detector model

        Args:
            model_path: Path to .pkl model file (defaults to learning dir)
        """
        if model_path is None:
            model_path = Path.home() / '.claude' / 'learning' / 'novelty_detector_model.pkl'

        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        with open(self.model_path, 'rb') as f:
            self.model = pickle.load(f)

        self.feature_names = [
            'prompt_length', 'file_count', 'code_blocks',
            'complexity', 'success', 'reward', 'importance'
        ]

    def extract_features(self, task):
        """
        Extract feature vector from task description

        Args:
            task: dict with keys:
                - prompt_length (int)
                - file_count (int)
                - code_blocks (int)
                - complexity (str: 'simple', 'medium', 'complex')
                - success (bool, optional)
                - reward (float, optional)
                - importance (float, optional)

        Returns:
            numpy array of features
        """
        complexity_map = {'simple': 0, 'medium': 1, 'complex': 2}
        complexity_val = complexity_map.get(task.get('complexity', 'medium'), 1)

        features = [
            task.get('prompt_length', 0),
            task.get('file_count', 0),
            task.get('code_blocks', 0),
            complexity_val,
            1.0 if task.get('success', False) else 0.0,
            task.get('reward', 0.5),
            task.get('importance', 0.5)
        ]

        return np.array(features).reshape(1, -1)

    def predict(self, task_or_features):
        """
        Predict if task is novel (requires exploration) or familiar (can exploit)

        Args:
            task_or_features: dict (task) or numpy array (features)

        Returns:
            bool: True if novel (explore), False if familiar (exploit)
        """
        if isinstance(task_or_features, dict):
            features = self.extract_features(task_or_features)
        else:
            features = task_or_features.reshape(1, -1)

        prediction = self.model.predict(features)[0]
        return prediction == -1  # -1 = outlier/novel, 1 = inlier/familiar

    def get_score(self, task_or_features):
        """
        Get anomaly score (lower = more novel)

        Args:
            task_or_features: dict (task) or numpy array (features)

        Returns:
            float: anomaly score (negative = novel, positive = familiar)
        """
        if isinstance(task_or_features, dict):
            features = self.extract_features(task_or_features)
        else:
            features = task_or_features.reshape(1, -1)

        return self.model.decision_function(features)[0]

    def predict_with_confidence(self, task_or_features):
        """
        Predict novelty with confidence score

        Args:
            task_or_features: dict (task) or numpy array (features)

        Returns:
            tuple: (is_novel: bool, confidence: float)
        """
        score = self.get_score(task_or_features)
        is_novel = score < 0

        # Normalize score to [0, 1] confidence
        # Higher magnitude = higher confidence
        confidence = min(1.0, abs(score) / 0.5)

        return is_novel, confidence


# Convenience functions for quick usage
def load_model(model_path=None):
    """Load novelty detector model"""
    return NoveltyDetector(model_path)

def predict_novelty(task):
    """
    Quick prediction: Is this task novel?

    Args:
        task: dict with task features

    Returns:
        bool: True if novel (explore), False if familiar (exploit)
    """
    detector = NoveltyDetector()
    return detector.predict(task)

def get_exploration_strategy(task):
    """
    Recommend exploration vs exploitation strategy

    Args:
        task: dict with task features

    Returns:
        str: 'explore' or 'exploit'
    """
    detector = NoveltyDetector()
    is_novel, confidence = detector.predict_with_confidence(task)

    return 'explore' if is_novel else 'exploit'


# Example usage
if __name__ == '__main__':
    print("Novelty Detector Integration Module\n")

    detector = NoveltyDetector()
    print(f"Model loaded: {detector.model_path}\n")

    # Test cases
    test_cases = [
        {
            'name': 'Simple code search',
            'task': {
                'prompt_length': 50,
                'file_count': 2,
                'code_blocks': 1,
                'complexity': 'simple'
            }
        },
        {
            'name': 'Complex feature implementation',
            'task': {
                'prompt_length': 500,
                'file_count': 15,
                'code_blocks': 8,
                'complexity': 'complex'
            }
        },
        {
            'name': 'Medium bug fix',
            'task': {
                'prompt_length': 150,
                'file_count': 3,
                'code_blocks': 2,
                'complexity': 'medium'
            }
        }
    ]

    for case in test_cases:
        task = case['task']
        is_novel, confidence = detector.predict_with_confidence(task)
        strategy = 'EXPLORE' if is_novel else 'EXPLOIT'

        print(f"{case['name']}:")
        print(f"  Strategy: {strategy}")
        print(f"  Confidence: {confidence:.1%}")
        print(f"  Score: {detector.get_score(task):.4f}")
        print()
