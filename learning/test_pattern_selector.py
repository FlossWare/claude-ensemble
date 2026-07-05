#!/usr/bin/env python3
"""
Pattern Selector Model - Usage Example

Demonstrates how to load and use the trained pattern selector model.
"""

import pickle
import json
import numpy as np
from pathlib import Path


def load_model():
    """Load trained pattern selector model."""
    model_path = Path.home() / '.claude' / 'learning' / 'predictors' / 'pattern-selector.pkl'
    metadata_path = Path.home() / '.claude' / 'learning' / 'predictors' / 'pattern-selector-metadata.json'

    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    return model, metadata


def extract_features(worker_count, phase_count, task_description, total_duration_ms):
    """
    Extract feature vector for prediction.

    Args:
        worker_count: Number of parallel workers
        phase_count: Number of sequential phases
        task_description: Task description text
        total_duration_ms: Total workflow duration (milliseconds)

    Returns:
        Feature vector [7 features]
    """
    # Task complexity from description length (log scale)
    task_complexity = min(np.log1p(len(task_description)), 10.0)

    # Average worker duration
    avg_worker_duration = total_duration_ms / max(worker_count, 1)

    # Interdependence score
    interdependence_score = phase_count / max(worker_count, 1)

    # Parallelism potential
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


def predict_pattern(model, metadata, worker_count, phase_count, task_description, total_duration_ms):
    """
    Predict optimal workflow pattern.

    Returns:
        pattern_name: 'parallel', 'sequential', 'pipeline', or 'nested'
        confidence: Probability of predicted class
    """
    features = extract_features(worker_count, phase_count, task_description, total_duration_ms)
    features_array = np.array([features])

    prediction = model.predict(features_array)[0]
    probabilities = model.predict_proba(features_array)[0]

    pattern_name = metadata['patterns'][str(prediction)]
    confidence = probabilities[prediction]

    return pattern_name, confidence, probabilities


def main():
    """Test pattern selector with example scenarios."""
    print("=" * 80)
    print("PATTERN SELECTOR - USAGE EXAMPLE")
    print("=" * 80)

    # Load model
    print("\nLoading model...")
    model, metadata = load_model()
    print(f"Model loaded: {metadata['model_name']}")
    print(f"Accuracy: {metadata['accuracy']:.3f}")
    print(f"Training samples: {metadata['training_samples']}")

    # Test scenarios
    scenarios = [
        {
            'name': 'Large parallel research task',
            'worker_count': 8,
            'phase_count': 1,
            'task_description': 'Deep research on firmware reverse engineering with multiple sources',
            'total_duration_ms': 45000
        },
        {
            'name': 'Simple single-worker task',
            'worker_count': 1,
            'phase_count': 1,
            'task_description': 'Read file',
            'total_duration_ms': 500
        },
        {
            'name': 'Multi-phase pipeline',
            'worker_count': 3,
            'phase_count': 4,
            'task_description': 'Search, analyze, verify, synthesize results',
            'total_duration_ms': 30000
        },
        {
            'name': 'Complex nested workflow',
            'worker_count': 6,
            'phase_count': 5,
            'task_description': 'Multi-stage analysis with parallel verification and synthesis',
            'total_duration_ms': 60000
        }
    ]

    print("\n" + "=" * 80)
    print("PREDICTIONS")
    print("=" * 80)

    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        print(f"  Workers: {scenario['worker_count']}, Phases: {scenario['phase_count']}")
        print(f"  Duration: {scenario['total_duration_ms']}ms")

        pattern, confidence, probabilities = predict_pattern(
            model, metadata,
            scenario['worker_count'],
            scenario['phase_count'],
            scenario['task_description'],
            scenario['total_duration_ms']
        )

        print(f"  Predicted pattern: {pattern} (confidence: {confidence:.3f})")

        # Build probability string dynamically (handle variable number of classes)
        prob_strs = []
        pattern_names = ['parallel', 'sequential', 'pipeline', 'nested']
        for i, prob in enumerate(probabilities):
            prob_strs.append(f"{pattern_names[i]}={prob:.3f}")
        print(f"  Probabilities: {', '.join(prob_strs)}")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
