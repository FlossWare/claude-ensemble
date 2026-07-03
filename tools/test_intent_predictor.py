#!/usr/bin/env python3
"""
Intent Predictor Integration Test Suite

Validates intent prediction accuracy on known test cases.
"""

import sys
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent))

from predict_intent import load_model, predict_intent


# Test cases with expected intents
TEST_CASES = [
    # Code Generation
    ("Write a Python script to parse JSON logs", "code_generation"),
    ("Create a function to sort a list", "code_generation"),
    ("Generate boilerplate for a REST API", "code_generation"),

    # Code Review
    ("Review this code for bugs", "code_review"),
    ("Analyze this implementation for improvements", "code_review"),
    ("Audit the security of this function", "code_review"),

    # Research
    ("Research the latest Kubernetes features", "research"),
    ("What is the Free Energy Principle?", "research"),
    ("Summarize this PDF about machine learning", "research"),

    # System Operations
    ("Deploy the application to production", "system_ops"),
    ("Install Docker on the server", "system_ops"),
    ("Configure SSH keys for the fleet", "system_ops"),

    # Debugging
    ("Debug this segmentation fault", "debugging"),
    ("Why is this code throwing a NullPointerException?", "debugging"),
    ("Fix this memory leak", "debugging"),

    # Data Analysis
    ("Analyze the PostgreSQL query performance", "data_analysis"),
    ("Parse these access logs and extract IPs", "data_analysis"),
    ("Generate a dashboard showing metrics", "data_analysis"),

    # Documentation
    ("Write a README for this project", "documentation"),
    ("Document the API endpoints", "documentation"),
    ("Explain how this algorithm works", "documentation"),

    # Workflow Automation
    ("Create a workflow to process files in parallel", "workflow_automation"),
    ("Automate the deployment pipeline", "workflow_automation"),
    ("Set up a cron job to backup the database", "workflow_automation"),

    # Learning
    ("Train a classifier on this dataset", "learning"),
    ("Fine-tune the model on Java code", "learning"),
    ("Generate embeddings for these documents", "learning"),
]


def run_tests():
    """Run test suite and report results."""
    print("Intent Predictor Test Suite")
    print("=" * 70)

    # Load model
    try:
        model = load_model()
        print(f"✓ Model loaded successfully")
        print(f"  Training samples: {model['training_samples']}")
        print(f"  Intent classes: {', '.join(model['intent_classes'])}")
        print()
    except FileNotFoundError as e:
        print(f"✗ Model not found: {e}")
        print(f"  Run: python3 tools/train_intent_predictor.py")
        sys.exit(1)

    # Run test cases
    results = {
        'total': 0,
        'correct': 0,
        'incorrect': 0,
        'multi_intent': 0,
    }

    failures = []

    for text, expected_intent in TEST_CASES:
        results['total'] += 1

        intents = predict_intent(model, text, threshold=0.3)
        predicted_intent = intents[0][0] if intents else 'other'

        # Check if expected intent is in predictions
        predicted_intents = [intent for intent, conf in intents]
        is_correct = expected_intent in predicted_intents

        if is_correct:
            results['correct'] += 1
            status = '✓'
        else:
            results['incorrect'] += 1
            status = '✗'
            failures.append({
                'text': text,
                'expected': expected_intent,
                'predicted': predicted_intent,
                'all_intents': intents,
            })

        if len(intents) > 1:
            results['multi_intent'] += 1

        # Print compact result
        intent_str = ', '.join([f"{intent}:{conf:.2f}" for intent, conf in intents[:3]])
        print(f"{status} {predicted_intent:20s} | {text[:45]:45s}")

    # Print summary
    print()
    print("=" * 70)
    print("Test Results:")
    print(f"  Total: {results['total']}")
    print(f"  Correct: {results['correct']} ({results['correct']/results['total']*100:.1f}%)")
    print(f"  Incorrect: {results['incorrect']} ({results['incorrect']/results['total']*100:.1f}%)")
    print(f"  Multi-intent: {results['multi_intent']} ({results['multi_intent']/results['total']*100:.1f}%)")

    # Print failures
    if failures:
        print()
        print("Failures:")
        for failure in failures:
            print(f"  Text: {failure['text']}")
            print(f"    Expected: {failure['expected']}")
            print(f"    Predicted: {failure['predicted']}")
            print(f"    All intents: {failure['all_intents']}")
            print()

    # Return exit code
    accuracy = results['correct'] / results['total']
    if accuracy >= 0.75:
        print("✓ Test suite PASSED (>75% accuracy)")
        return 0
    else:
        print(f"✗ Test suite FAILED ({accuracy*100:.1f}% < 75% threshold)")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
