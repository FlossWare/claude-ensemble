#!/usr/bin/env python3
"""
User Intent Prediction Script

Uses trained intent predictor to classify user queries.
"""

import sys
import json
import joblib
from pathlib import Path


def load_model(model_path: str = None):
    """Load trained intent predictor model."""
    if model_path is None:
        model_path = Path.home() / '.claude' / 'learning' / 'intent_predictor.pkl'

    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Model not found at {model_path}. "
            f"Run train_intent_predictor.py first."
        )

    return joblib.load(model_path)


def predict_intent(model: dict, text: str, threshold: float = 0.3) -> list[tuple[str, float]]:
    """Predict intents for text with confidence scores."""
    import scipy.special

    vectorizer = model['vectorizer']
    classifier = model['classifier']
    mlb = model['label_binarizer']

    # Vectorize
    X = vectorizer.transform([text])

    # Get decision scores for all classifiers
    decision_scores = []
    for estimator in classifier.estimators_:
        scores = estimator.decision_function(X)
        decision_scores.append(scores[0] if hasattr(scores, '__iter__') else scores)

    # Apply sigmoid to convert to probabilities
    probas = scipy.special.expit(decision_scores)

    # Get intents above threshold
    intents = []
    for idx, proba in enumerate(probas):
        if proba >= threshold:
            intent = mlb.classes_[idx]
            # Exclude 'other' unless it's the only high-confidence prediction
            if intent != 'other' or len(intents) == 0:
                intents.append((intent, float(proba)))

    # Sort by confidence
    intents.sort(key=lambda x: x[1], reverse=True)

    # If only 'other' is found, check if there are any predictions above a lower threshold
    if len(intents) == 1 and intents[0][0] == 'other':
        lower_threshold = threshold * 0.5
        for idx, proba in enumerate(probas):
            if proba >= lower_threshold and mlb.classes_[idx] != 'other':
                intents.insert(0, (mlb.classes_[idx], float(proba)))

    return intents if intents else [('other', 1.0)]


def main():
    """CLI interface for intent prediction."""
    if len(sys.argv) < 2:
        print("Usage: predict_intent.py '<text>' [--threshold 0.3] [--json]")
        print("\nExamples:")
        print("  predict_intent.py 'Write a Python script to process files'")
        print("  predict_intent.py 'Debug this error' --json")
        print("  predict_intent.py 'Research Kubernetes' --threshold 0.5")
        sys.exit(1)

    # Parse arguments
    text = sys.argv[1]
    threshold = 0.3
    json_output = False

    for i, arg in enumerate(sys.argv[2:]):
        if arg == '--threshold' and i + 3 < len(sys.argv):
            threshold = float(sys.argv[i + 3])
        elif arg == '--json':
            json_output = True

    # Load model
    model = load_model()

    # Predict
    intents = predict_intent(model, text, threshold=threshold)

    # Output
    if json_output:
        result = {
            'text': text,
            'intents': [{'name': intent, 'confidence': conf} for intent, conf in intents],
            'primary_intent': intents[0][0] if intents else 'other',
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"\nInput: {text}")
        print(f"\nPredicted intents:")
        for intent, confidence in intents:
            print(f"  - {intent}: {confidence:.2%}")
        print(f"\nPrimary intent: {intents[0][0] if intents else 'other'}")


if __name__ == '__main__':
    main()
