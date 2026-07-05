#!/usr/bin/env python3
"""
Test Causal Inference Expert

Demonstrates the trained causal inference classifier on various examples.
"""

import pickle
import numpy as np
from pathlib import Path
import sys

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from causal_inference_expert_trainer import extract_features

def load_models():
    """Load trained models"""
    base_path = Path('/home/sfloess/.claude/learning')

    with open(base_path / 'causal_inference_expert_category.pkl', 'rb') as f:
        clf_category = pickle.load(f)
    with open(base_path / 'causal_inference_expert_severity.pkl', 'rb') as f:
        clf_severity = pickle.load(f)
    with open(base_path / 'causal_inference_expert_vectorizer.pkl', 'rb') as f:
        vectorizer = pickle.load(f)

    return clf_category, clf_severity, vectorizer

def analyze_text(text, clf_category, clf_severity, vectorizer):
    """Analyze text for causal inference issues"""
    # Vectorize text
    X = vectorizer.transform([text])

    # Extract custom features
    custom_feat = extract_features(text)
    X_custom = np.array([list(custom_feat.values())])
    X_combined = np.hstack([X.toarray(), X_custom])

    # Predict
    category = clf_category.predict(X_combined)[0]
    severity = clf_severity.predict(X_combined)[0]
    confidence = clf_category.predict_proba(X_combined).max()

    # Get top probabilities for category
    proba = clf_category.predict_proba(X_combined)[0]
    classes = clf_category.classes_
    top_indices = np.argsort(proba)[::-1][:3]

    return {
        'category': category,
        'severity': severity,
        'confidence': confidence,
        'top_categories': [(classes[i], proba[i]) for i in top_indices]
    }

def main():
    print("=== Causal Inference Expert Test ===\n")

    # Load models
    print("Loading models...")
    clf_category, clf_severity, vectorizer = load_models()
    print("✅ Models loaded\n")

    # Test cases
    test_cases = [
        {
            'name': 'Correlation-Causation Confusion',
            'text': 'Ice cream sales and drowning deaths are correlated, therefore ice cream causes drowning.'
        },
        {
            'name': 'Reverse Causation',
            'text': 'Students who study more get better grades. Analysis shows higher GPA predicts more study time.'
        },
        {
            'name': 'Confounding Ignored',
            'text': 'Drug shows efficacy in observational study. No adjustment for confounding. Claim causal effect.'
        },
        {
            'name': 'Selection Bias',
            'text': 'Hospital quality measured by patient outcomes. Sicker patients go to better hospitals.'
        },
        {
            'name': 'Valid RCT',
            'text': 'RCT with random assignment, double-blind, intention-to-treat analysis, and pre-registered protocol.'
        },
        {
            'name': 'Valid DiD',
            'text': 'Difference-in-differences with parallel pre-trends shown, event study, and multiple robustness checks.'
        },
        {
            'name': 'Weak Instrument',
            'text': 'Instrumental variable analysis with weak instrument (F-statistic = 5).'
        },
        {
            'name': 'Parallel Trends Violation',
            'text': 'Difference-in-differences analysis assumes parallel trends but no evidence provided.'
        },
        {
            'name': 'Observational with Controls',
            'text': 'Education and income are correlated. Controlling for family background, ability, and region.'
        },
        {
            'name': 'No Control Group',
            'text': 'Claim policy reduced crime by comparing before/after trends, but no control group.'
        }
    ]

    # Analyze each test case
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. {test_case['name']}")
        print(f"   Text: {test_case['text'][:80]}...")

        result = analyze_text(test_case['text'], clf_category, clf_severity, vectorizer)

        print(f"   ✓ Category: {result['category']}")
        print(f"   ✓ Severity: {result['severity']}")
        print(f"   ✓ Confidence: {result['confidence']:.1%}")

        if len(result['top_categories']) > 1:
            print(f"   Alternative categories:")
            for cat, prob in result['top_categories'][1:]:
                if prob > 0.1:
                    print(f"     - {cat}: {prob:.1%}")

        print()

    # Interactive mode
    print("\n=== Interactive Mode ===")
    print("Enter text to analyze (or 'quit' to exit):\n")

    while True:
        try:
            text = input("> ")
            if text.lower() in ['quit', 'exit', 'q']:
                break

            if not text.strip():
                continue

            result = analyze_text(text, clf_category, clf_severity, vectorizer)

            print(f"\n📊 Analysis Results:")
            print(f"   Category: {result['category']}")
            print(f"   Severity: {result['severity']}")
            print(f"   Confidence: {result['confidence']:.1%}")

            if result['confidence'] < 0.5:
                print("   ⚠️  Low confidence - consider multiple interpretations")

            print(f"\n   Top predictions:")
            for cat, prob in result['top_categories']:
                print(f"     {cat:40s} {prob:.1%}")
            print()

        except EOFError:
            break
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break

    print("\n✅ Test complete!")

if __name__ == '__main__':
    main()
