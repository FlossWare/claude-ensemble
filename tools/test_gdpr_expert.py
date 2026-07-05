#!/usr/bin/env python3
"""
Test GDPR Expert Model

Demonstrates usage of the trained GDPR compliance classifier.
"""

import pickle
import numpy as np
import sys
from pathlib import Path

# Import feature extractor
sys.path.insert(0, str(Path(__file__).parent))
from gdpr_expert_trainer import extract_features

def load_gdpr_expert():
    """Load GDPR expert models"""
    base_path = Path.home() / '.claude' / 'learning'

    with open(base_path / 'gdpr_expert_category.pkl', 'rb') as f:
        clf_category = pickle.load(f)
    with open(base_path / 'gdpr_expert_severity.pkl', 'rb') as f:
        clf_severity = pickle.load(f)
    with open(base_path / 'gdpr_expert_vectorizer.pkl', 'rb') as f:
        vectorizer = pickle.load(f)

    return clf_category, clf_severity, vectorizer

def analyze_gdpr_issue(text, clf_category, clf_severity, vectorizer):
    """Analyze GDPR compliance issue"""
    # Vectorize text
    X_tfidf = vectorizer.transform([text])

    # Add custom GDPR features
    custom_feat = extract_features(text)
    X_custom = np.array([list(custom_feat.values())])

    # Combine features
    X_combined = np.hstack([X_tfidf.toarray(), X_custom])

    # Predict
    category = clf_category.predict(X_combined)[0]
    severity = clf_severity.predict(X_combined)[0]
    category_proba = clf_category.predict_proba(X_combined)[0]
    severity_proba = clf_severity.predict_proba(X_combined)[0]

    # Get confidence scores
    category_confidence = category_proba.max()
    severity_confidence = severity_proba.max()

    return {
        'category': category,
        'severity': severity,
        'category_confidence': category_confidence,
        'severity_confidence': severity_confidence,
        'custom_features': custom_feat
    }

def main():
    print("=== GDPR Expert Test Suite ===\n")

    # Load models
    print("Loading GDPR expert models...")
    clf_category, clf_severity, vectorizer = load_gdpr_expert()
    print("✅ Models loaded\n")

    # Test cases
    test_cases = [
        {
            'name': 'Deletion Request Ignored',
            'text': 'User requested data deletion 60 days ago. No response sent. Data still in database.'
        },
        {
            'name': 'Invalid Consent',
            'text': 'Consent obtained via pre-ticked checkbox. No granular options. Cannot withdraw consent.'
        },
        {
            'name': 'Unlawful Cross-Border Transfer',
            'text': 'Personal data transferred to USA without Standard Contractual Clauses. No Transfer Impact Assessment.'
        },
        {
            'name': 'Missing Encryption',
            'text': 'Personal data stored in plaintext. No encryption at rest. Access logs disabled.'
        },
        {
            'name': 'Excessive Data Collection',
            'text': 'Collecting phone number, address, and browsing history for newsletter signup. Data minimization violation.'
        },
        {
            'name': 'Child Data Without Parental Consent',
            'text': 'Child under 13 data collected without verifiable parental consent. Age verification missing.'
        },
        {
            'name': 'Valid Consent (Compliant)',
            'text': 'Consent obtained via clear checkbox. Granular options provided. Withdrawal link available. Records maintained.'
        },
        {
            'name': 'Proper Deletion Process',
            'text': 'Deletion request fulfilled within 14 days. All systems purged. Third parties notified. User confirmation sent.'
        }
    ]

    # Analyze each test case
    for i, test in enumerate(test_cases, 1):
        print(f"--- Test {i}: {test['name']} ---")
        print(f"Input: {test['text'][:80]}...")

        result = analyze_gdpr_issue(
            test['text'],
            clf_category,
            clf_severity,
            vectorizer
        )

        print(f"Category: {result['category']} (confidence: {result['category_confidence']:.1%})")
        print(f"Severity: {result['severity']} (confidence: {result['severity_confidence']:.1%})")

        # Show relevant features
        active_features = [k for k, v in result['custom_features'].items() if v]
        if active_features:
            print(f"Features detected: {', '.join(active_features[:5])}")
            if len(active_features) > 5:
                print(f"  ... and {len(active_features) - 5} more")

        print()

    print("=== Test Complete ===")

if __name__ == '__main__':
    main()
