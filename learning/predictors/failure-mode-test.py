#!/usr/bin/env python3
"""
Test harness for Failure Mode Predictor
Validates predictions across different scenarios
"""

import sys
from pathlib import Path
import importlib.util

# Load module directly from file
module_path = Path(__file__).parent / 'failure-mode-predictor.py'
spec = importlib.util.spec_from_file_location("failure_mode_predictor", module_path)
fmp_module = importlib.util.module_from_spec(spec)
sys.modules["failure_mode_predictor"] = fmp_module
spec.loader.exec_module(fmp_module)

FailureModePredictor = fmp_module.FailureModePredictor
import json

def test_predictor():
    """Run comprehensive tests"""

    predictor = FailureModePredictor()
    predictor.load()

    print("="*80)
    print("FAILURE MODE PREDICTOR - VALIDATION TESTS")
    print("="*80)

    test_cases = [
        {
            "name": "1. Fast successful search (Haiku)",
            "execution": {
                "model": "haiku",
                "workflow": "search",
                "input_tokens": 5000,
                "output_tokens": 1500,
                "duration_ms": 8000
            },
            "expected": "success"
        },
        {
            "name": "2. Normal code review (Sonnet)",
            "execution": {
                "model": "sonnet",
                "workflow": "code-review",
                "input_tokens": 12000,
                "output_tokens": 3000,
                "duration_ms": 25000
            },
            "expected": "success"
        },
        {
            "name": "3. Complex deep research - TIMEOUT risk (Phi)",
            "execution": {
                "model": "phi",
                "workflow": "deep-research",
                "input_tokens": 45000,
                "output_tokens": 12000,
                "duration_ms": 250000  # 4+ minutes
            },
            "expected": "timeout"
        },
        {
            "name": "4. High memory pressure - OOM risk (80K tokens)",
            "execution": {
                "model": "sonnet",
                "workflow": "synthesis",
                "input_tokens": 80000,
                "output_tokens": 25000,
                "duration_ms": 60000
            },
            "expected": "oom"
        },
        {
            "name": "5. Very high memory - OOM certain (100K tokens)",
            "execution": {
                "model": "opus",
                "workflow": "deep-research",
                "input_tokens": 100000,
                "output_tokens": 30000,
                "duration_ms": 80000
            },
            "expected": "oom"
        },
        {
            "name": "6. API rate limit scenario (Opus, fast)",
            "execution": {
                "model": "opus",
                "workflow": "analysis",
                "input_tokens": 15000,
                "output_tokens": 5000,
                "duration_ms": 2000  # Very fast = likely API error
            },
            "expected": "api_error"
        },
        {
            "name": "7. Successful synthesis (Opus, normal speed)",
            "execution": {
                "model": "opus",
                "workflow": "synthesis",
                "input_tokens": 18000,
                "output_tokens": 6000,
                "duration_ms": 35000
            },
            "expected": "success"
        },
        {
            "name": "8. AutoML timeout (low reliability + long duration)",
            "execution": {
                "model": "automl",
                "workflow": "deep-research",
                "input_tokens": 35000,
                "output_tokens": 10000,
                "duration_ms": 180000  # 3 minutes
            },
            "expected": "timeout"
        },
        {
            "name": "9. Fast API error (GPT4o rate limit)",
            "execution": {
                "model": "gpt4o",
                "workflow": "search",
                "input_tokens": 8000,
                "output_tokens": 2000,
                "duration_ms": 1500
            },
            "expected": "api_error"
        },
        {
            "name": "10. Successful analysis (Gemini)",
            "execution": {
                "model": "gemini",
                "workflow": "analysis",
                "input_tokens": 10000,
                "output_tokens": 3500,
                "duration_ms": 20000
            },
            "expected": "success"
        }
    ]

    results = []
    correct = 0
    total = len(test_cases)

    for i, test_case in enumerate(test_cases):
        print(f"\n{test_case['name']}")
        print("-" * 80)

        execution = test_case['execution']
        expected = test_case['expected']

        print(f"Model: {execution['model']:10s} | Workflow: {execution['workflow']}")
        print(f"Tokens: {execution['input_tokens']:6d} in / {execution['output_tokens']:5d} out")
        print(f"Duration: {execution['duration_ms']:6d} ms")
        print(f"Expected: {expected.upper()}")

        prediction = predictor.predict(execution)
        predicted = prediction['predicted_mode']
        confidence = prediction['confidence']

        # Check if prediction matches expected
        match = predicted == expected
        if match:
            correct += 1
            status = "CORRECT"
        else:
            status = "MISMATCH"

        print(f"\nPredicted: {predicted.upper()} (confidence: {confidence:.1%}) - {status}")

        # Show top 3 probabilities
        print("\nTop probabilities:")
        sorted_probs = sorted(
            prediction['probabilities'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        for mode, prob in sorted_probs[:3]:
            marker = " <-- " if mode == expected else ""
            bar = "#" * int(prob * 40)
            print(f"  {mode:12s}: {prob:6.1%} {bar}{marker}")

        results.append({
            'test_name': test_case['name'],
            'expected': expected,
            'predicted': predicted,
            'confidence': confidence,
            'match': match,
            'execution': execution
        })

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total tests: {total}")
    print(f"Correct predictions: {correct}")
    print(f"Accuracy: {correct/total:.1%}")

    print("\n" + "="*80)
    print("FAILURE MODE DISTRIBUTION (Expected vs Predicted)")
    print("="*80)

    # Count expected vs predicted per mode
    modes = ['success', 'timeout', 'oom', 'api_error', 'unknown']
    print(f"{'Mode':<12s} | {'Expected':<8s} | {'Predicted':<8s}")
    print("-" * 40)

    for mode in modes:
        expected_count = sum(1 for r in results if r['expected'] == mode)
        predicted_count = sum(1 for r in results if r['predicted'] == mode)
        print(f"{mode:<12s} | {expected_count:<8d} | {predicted_count:<8d}")

    # Mismatches
    mismatches = [r for r in results if not r['match']]
    if mismatches:
        print("\n" + "="*80)
        print("MISMATCHES")
        print("="*80)
        for r in mismatches:
            print(f"\n{r['test_name']}")
            print(f"  Expected: {r['expected']}, Predicted: {r['predicted']} ({r['confidence']:.1%})")

    return results


if __name__ == '__main__':
    results = test_predictor()

    # Save results
    output_file = Path(__file__).parent / 'failure-mode-test-results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_file}")
