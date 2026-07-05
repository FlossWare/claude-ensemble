#!/usr/bin/env python3
"""
Pattern Selector Reliability Test

Tests the retrained pattern selector model for:
1. Prediction accuracy (10 diverse scenarios)
2. Confidence levels (>80% target)
3. Retry failure rate (<5% target)
4. Edge case handling

Success criteria:
- Accuracy: >90%
- Avg confidence: >80%
- Retry failures: <5%
"""

import pickle
import json
import numpy as np
import time
import sys
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


def extract_features(worker_count, phase_count, task_complexity, avg_worker_duration,
                     total_duration_ms, interdependence_score, parallelism_potential):
    """Extract feature vector for prediction."""
    return np.array([[
        worker_count,
        phase_count,
        task_complexity,
        avg_worker_duration,
        total_duration_ms,
        interdependence_score,
        parallelism_potential
    ]])


def predict_with_validation(model, metadata, features, min_confidence=0.5):
    """
    Predict pattern with validation layer.

    Returns:
        pattern_name: Predicted pattern
        confidence: Prediction confidence
        validation_passed: True if confidence >= threshold
        fallback_used: True if fell back to default
    """
    try:
        prediction = model.predict(features)[0]
        probabilities = model.predict_proba(features)[0]

        pattern_name = metadata['patterns'][str(prediction)]
        confidence = probabilities[prediction]

        # Validation: if confidence too low, fall back to safe default
        validation_passed = confidence >= min_confidence
        fallback_used = False

        if not validation_passed:
            # Fallback to most common pattern (parallel)
            pattern_name = 'parallel'
            fallback_used = True

        return pattern_name, confidence, validation_passed, fallback_used

    except Exception as e:
        # Hard failure - return safe default
        return 'parallel', 0.0, False, True


def run_test_scenarios():
    """Run 10 diverse test scenarios."""
    scenarios = [
        {
            'name': 'Large parallel research (8 workers, 1 phase)',
            'expected': 'parallel',
            'features': {
                'worker_count': 8,
                'phase_count': 1,
                'task_complexity': 4.5,
                'avg_worker_duration': 5000,
                'total_duration_ms': 40000,
                'interdependence_score': 0.125,  # 1/8
                'parallelism_potential': 0.2     # 8*1000/40000
            }
        },
        {
            'name': 'Single worker task',
            'expected': 'sequential',
            'features': {
                'worker_count': 1,
                'phase_count': 1,
                'task_complexity': 2.0,
                'avg_worker_duration': 500,
                'total_duration_ms': 500,
                'interdependence_score': 1.0,    # 1/1
                'parallelism_potential': 2.0     # 1*1000/500
            }
        },
        {
            'name': 'Multi-phase pipeline (3 workers, 4 phases)',
            'expected': 'pipeline',
            'features': {
                'worker_count': 3,
                'phase_count': 4,
                'task_complexity': 3.5,
                'avg_worker_duration': 10000,
                'total_duration_ms': 30000,
                'interdependence_score': 1.33,   # 4/3
                'parallelism_potential': 0.1     # 3*1000/30000
            }
        },
        {
            'name': 'Complex nested workflow (6 workers, 5 phases)',
            'expected': 'pipeline',  # Now maps to pipeline (not nested)
            'features': {
                'worker_count': 6,
                'phase_count': 5,
                'task_complexity': 5.0,
                'avg_worker_duration': 10000,
                'total_duration_ms': 60000,
                'interdependence_score': 0.83,   # 5/6
                'parallelism_potential': 0.1     # 6*1000/60000
            }
        },
        {
            'name': 'Small parallel (2 workers, 1 phase)',
            'expected': 'parallel',
            'features': {
                'worker_count': 2,
                'phase_count': 1,
                'task_complexity': 3.0,
                'avg_worker_duration': 2000,
                'total_duration_ms': 4000,
                'interdependence_score': 0.5,    # 1/2
                'parallelism_potential': 0.5     # 2*1000/4000
            }
        },
        {
            'name': 'High interdependence (4 workers, 8 phases)',
            'expected': 'pipeline',
            'features': {
                'worker_count': 4,
                'phase_count': 8,
                'task_complexity': 4.0,
                'avg_worker_duration': 8750,
                'total_duration_ms': 35000,
                'interdependence_score': 2.0,    # 8/4
                'parallelism_potential': 0.11    # 4*1000/35000
            }
        },
        {
            'name': 'Low interdependence (8 workers, 2 phases)',
            'expected': 'pipeline',  # 2 phases = pipeline
            'features': {
                'worker_count': 8,
                'phase_count': 2,
                'task_complexity': 3.0,
                'avg_worker_duration': 625,
                'total_duration_ms': 5000,
                'interdependence_score': 0.25,   # 2/8
                'parallelism_potential': 1.6     # 8*1000/5000
            }
        },
        {
            'name': 'Very high parallelism (16 workers, 1 phase)',
            'expected': 'parallel',
            'features': {
                'worker_count': 16,
                'phase_count': 1,
                'task_complexity': 5.0,
                'avg_worker_duration': 1563,
                'total_duration_ms': 25000,
                'interdependence_score': 0.0625, # 1/16
                'parallelism_potential': 0.64    # 16*1000/25000
            }
        },
        {
            'name': 'Medium pipeline (4 workers, 3 phases)',
            'expected': 'pipeline',
            'features': {
                'worker_count': 4,
                'phase_count': 3,
                'task_complexity': 3.5,
                'avg_worker_duration': 5000,
                'total_duration_ms': 20000,
                'interdependence_score': 0.75,   # 3/4
                'parallelism_potential': 0.2     # 4*1000/20000
            }
        },
        {
            'name': 'Edge case: 1 worker, 0 phases',
            'expected': 'sequential',
            'features': {
                'worker_count': 1,
                'phase_count': 0,
                'task_complexity': 1.0,
                'avg_worker_duration': 100,
                'total_duration_ms': 100,
                'interdependence_score': 0.0,
                'parallelism_potential': 10.0
            }
        }
    ]

    return scenarios


def main():
    """Main test harness."""
    print("=" * 80)
    print("PATTERN SELECTOR RELIABILITY TEST")
    print("=" * 80)

    # Load model
    print("\nLoading model...")
    start_time = time.time()
    model, metadata = load_model()
    load_time = (time.time() - start_time) * 1000

    print(f"Model loaded: {metadata['model_name']} v{metadata.get('model_version', '1.0')}")
    print(f"Training accuracy: {metadata['accuracy']:.3f}")
    print(f"OOB score: {metadata.get('oob_score', 'N/A')}")
    print(f"Load time: {load_time:.1f}ms")
    print(f"Classes: {', '.join(metadata['class_names'])}")

    # Run test scenarios
    scenarios = run_test_scenarios()

    print("\n" + "=" * 80)
    print("TEST SCENARIOS")
    print("=" * 80)

    results = []
    total_correct = 0
    total_high_confidence = 0
    total_retry_failures = 0
    confidences = []

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/10] {scenario['name']}")
        print(f"  Expected: {scenario['expected']}")

        features = extract_features(**scenario['features'])

        start_time = time.time()
        pattern, confidence, validation_passed, fallback_used = predict_with_validation(
            model, metadata, features, min_confidence=0.5
        )
        prediction_time = (time.time() - start_time) * 1000

        correct = (pattern == scenario['expected'])
        high_confidence = confidence >= 0.8
        retry_failure = confidence < 0.5  # Would trigger retry in production

        if correct:
            total_correct += 1
        if high_confidence:
            total_high_confidence += 1
        if retry_failure:
            total_retry_failures += 1

        confidences.append(confidence)

        status = "✓ PASS" if correct else "✗ FAIL"
        retry_status = " (RETRY RISK)" if retry_failure else ""
        fallback_status = " (FALLBACK)" if fallback_used else ""

        print(f"  Predicted: {pattern} (confidence: {confidence:.3f}) {status}{retry_status}{fallback_status}")
        print(f"  Prediction time: {prediction_time:.1f}ms")

        results.append({
            'scenario': scenario['name'],
            'expected': scenario['expected'],
            'predicted': pattern,
            'confidence': float(confidence),
            'correct': bool(correct),
            'high_confidence': bool(high_confidence),
            'retry_failure': bool(retry_failure),
            'fallback_used': bool(fallback_used),
            'prediction_time_ms': float(prediction_time)
        })

    # Summary statistics
    accuracy = (total_correct / len(scenarios)) * 100
    avg_confidence = np.mean(confidences)
    min_confidence = np.min(confidences)
    max_confidence = np.max(confidences)
    retry_failure_rate = (total_retry_failures / len(scenarios)) * 100
    high_confidence_rate = (total_high_confidence / len(scenarios)) * 100
    avg_prediction_time = np.mean([r['prediction_time_ms'] for r in results])

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\nAccuracy:")
    print(f"  Correct predictions: {total_correct}/{len(scenarios)} ({accuracy:.1f}%)")
    print(f"  Target: >90%")
    print(f"  Status: {'✓ PASS' if accuracy >= 90 else '✗ FAIL'}")

    print(f"\nConfidence:")
    print(f"  Average: {avg_confidence:.3f}")
    print(f"  Minimum: {min_confidence:.3f}")
    print(f"  Maximum: {max_confidence:.3f}")
    print(f"  High confidence (>0.8): {total_high_confidence}/{len(scenarios)} ({high_confidence_rate:.1f}%)")
    print(f"  Target: avg >0.80")
    print(f"  Status: {'✓ PASS' if avg_confidence >= 0.80 else '✗ FAIL'}")

    print(f"\nRetry Failures:")
    print(f"  Low confidence (<0.5): {total_retry_failures}/{len(scenarios)} ({retry_failure_rate:.1f}%)")
    print(f"  Target: <5%")
    print(f"  Status: {'✓ PASS' if retry_failure_rate < 5 else '✗ FAIL'}")

    print(f"\nPerformance:")
    print(f"  Average prediction time: {avg_prediction_time:.1f}ms")
    print(f"  Model load time: {load_time:.1f}ms")

    # Overall verdict
    all_passed = (accuracy >= 90) and (avg_confidence >= 0.80) and (retry_failure_rate < 5)

    print("\n" + "=" * 80)
    print("OVERALL VERDICT")
    print("=" * 80)
    if all_passed:
        print("\n✓ ALL TESTS PASSED - Model ready for production")
    else:
        print("\n✗ SOME TESTS FAILED - Review results above")

    # Calculate improvement metrics
    print("\n" + "=" * 80)
    print("IMPROVEMENT ANALYSIS")
    print("=" * 80)
    print("\nBefore retraining:")
    print("  - Class imbalance: 57% sequential, 41% parallel, 3% pipeline, 0% nested")
    print("  - Retry failures: >5% (exceeded retry cap)")
    print("  - Confidence: Unknown (not measured)")
    print("\nAfter retraining:")
    print(f"  - Class balance: {100.0/3:.1f}% per class (35-38% actual)")
    print(f"  - Retry failures: {retry_failure_rate:.1f}%")
    print(f"  - Confidence: {avg_confidence:.3f} average")
    print(f"  - Classes: 3 (merged nested → pipeline)")
    print(f"  - Accuracy improvement: {accuracy - 96.7:.1f}% (from 96.7% to {accuracy:.1f}%)")
    print(f"\nReliability improvement: {100 - retry_failure_rate:.0f}% (from <95% to {100 - retry_failure_rate:.0f}%)")

    # Save results
    results_file = Path.home() / 'Development' / 'redhat' / 'scm' / 'gitlab' / 'cee' / 'sfloess' / 'claude-global-skills' / 'learning' / 'predictors' / 'pattern-selector-reliability-test.json'
    results_data = {
        'test_timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'model_version': metadata.get('model_version', '1.0'),
        'accuracy': float(accuracy),
        'avg_confidence': float(avg_confidence),
        'min_confidence': float(min_confidence),
        'max_confidence': float(max_confidence),
        'retry_failure_rate': float(retry_failure_rate),
        'high_confidence_rate': float(high_confidence_rate),
        'avg_prediction_time_ms': float(avg_prediction_time),
        'all_tests_passed': bool(all_passed),
        'scenarios': results
    }

    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)

    print(f"\nResults saved to: {results_file}")

    return results_data


if __name__ == '__main__':
    try:
        results = main()
        print("\n" + "=" * 80)
        sys.exit(0 if results['all_tests_passed'] else 1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
