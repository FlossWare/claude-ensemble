#!/usr/bin/env python3
"""
Agent Personality Matcher - Usage Example

Demonstrates how to use the trained classifier to predict
which model/agent is best suited for a given task.
"""

import pickle
from pathlib import Path
import numpy as np

def extract_features_from_task(task_text, estimated_tokens=None):
    """Extract features from task description"""
    if not task_text:
        return [0] * 10

    task_lower = task_text.lower()

    # Same feature extraction as training
    features = [
        len(task_text),  # task_length
        int(any(kw in task_lower for kw in ['code', 'implement', 'debug', 'fix'])),  # has_code
        int(any(kw in task_lower for kw in ['analyze', 'analysis', 'examine', 'investigate'])),  # has_analysis
        int(any(kw in task_lower for kw in ['research', 'search', 'find', 'gather'])),  # has_research
        int(any(kw in task_lower for kw in ['review', 'evaluate', 'assess', 'verify'])),  # has_review
        int(any(kw in task_lower for kw in ['test', 'validate', 'check'])),  # has_test
        estimated_tokens or len(task_text) * 0.4,  # input_tokens (rough estimate)
        estimated_tokens or len(task_text) * 0.4,  # output_tokens (rough estimate)
        5000,  # duration_ms (median value)
        0.7   # confidence (median value)
    ]

    return features

def load_matcher():
    """Load trained agent-personality-matcher model"""
    model_path = Path.home() / '.claude' / 'learning' / 'predictors' / 'agent-personality-matcher.pkl'

    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)

    return model_data

def predict_best_agent(task_description, top_k=3):
    """Predict best agent for given task"""
    model_data = load_matcher()
    clf = model_data['classifier']

    # Extract features
    features = extract_features_from_task(task_description)
    X = np.array([features])

    # Get predictions with probabilities
    prediction = clf.predict(X)[0]
    probabilities = clf.predict_proba(X)[0]

    # Get top-k models
    top_indices = np.argsort(probabilities)[::-1][:top_k]
    top_models = [(clf.classes_[i], probabilities[i]) for i in top_indices]

    return {
        'best_model': prediction,
        'confidence': probabilities[clf.classes_.tolist().index(prediction)],
        'top_k_models': top_models,
        'model_accuracy': model_data['accuracy']
    }

if __name__ == '__main__':
    # Example usage
    examples = [
        "Analyze the firmware binary and identify security vulnerabilities",
        "Implement a Python script to train a machine learning classifier",
        "Review the code changes for potential bugs and edge cases",
        "Research the latest advances in transformer architectures",
        "Debug the connection timeout issue in the PostgreSQL adapter",
        "Test the new API endpoint for edge cases and error handling"
    ]

    print("Agent Personality Matcher - Predictions")
    print("=" * 80)

    model_data = load_matcher()
    print(f"Model Accuracy: {model_data['accuracy']:.4f}")
    print(f"Trained: {model_data['trained_at']}")
    print()

    for task in examples:
        result = predict_best_agent(task, top_k=3)

        print(f"Task: {task}")
        print(f"Best Model: {result['best_model']} (confidence: {result['confidence']:.4f})")
        print("Top 3:")
        for model, prob in result['top_k_models']:
            print(f"  {model:40s} {prob:.4f}")
        print()
