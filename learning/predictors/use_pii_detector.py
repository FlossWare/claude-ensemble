#!/usr/bin/env python3
"""
Usage script for trained PII detector.

Example:
    python3 use_pii_detector.py "Email me at test@example.com"
    python3 use_pii_detector.py --batch file.txt
"""

import pickle
import re
import sys
import numpy as np
from pathlib import Path

# Load model and vectorizer
model_dir = Path(__file__).parent
with open(model_dir / 'pii-detector.pkl', 'rb') as f:
    clf = pickle.load(f)
with open(model_dir / 'pii-detector-vectorizer.pkl', 'rb') as f:
    vectorizer = pickle.load(f)

# PII patterns (must match training)
PII_PATTERNS = {
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'phone': r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b',
    'credit_card': r'\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b',
    'ip_address': r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
    'api_key': r'(?i)(?:api[_-]?key|token|secret)["\']?\s*[=:]\s*["\']?[a-zA-Z0-9_\-]{20,}',
    'password_field': r'(?i)password\s*[=:]\s*\S{3,}',
    'auth_bearer': r'(?i)authorization\s*:\s*bearer\s+[a-zA-Z0-9+/=\-_]+',
}

def extract_features(text):
    """Extract pattern-based features"""
    return {name: (1 if re.search(pattern, text, re.IGNORECASE) else 0) 
            for name, pattern in PII_PATTERNS.items()}

def predict(text):
    """Predict if text contains PII"""
    features = extract_features(text)
    X_text = vectorizer.transform([text]).toarray()
    X = np.hstack([X_text, [list(features.values())]])
    pred = clf.predict(X)[0]
    prob = clf.predict_proba(X)[0]
    return {
        'has_pii': bool(pred),
        'confidence': float(prob[pred]),
        'patterns_detected': [k for k, v in features.items() if v == 1]
    }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 use_pii_detector.py <text>")
        print("       python3 use_pii_detector.py --batch <file>")
        sys.exit(1)
    
    if sys.argv[1] == '--batch':
        with open(sys.argv[2]) as f:
            for line in f:
                line = line.strip()
                if line:
                    result = predict(line)
                    status = "⚠️  PII" if result['has_pii'] else "✓  Clean"
                    print(f"{status} [{result['confidence']:.2f}] {line}")
                    if result['patterns_detected']:
                        print(f"   Patterns: {', '.join(result['patterns_detected'])}")
    else:
        text = ' '.join(sys.argv[1:])
        result = predict(text)
        print(f"Text: {text}")
        print(f"Has PII: {result['has_pii']}")
        print(f"Confidence: {result['confidence']:.4f}")
        if result['patterns_detected']:
            print(f"Patterns detected: {', '.join(result['patterns_detected'])}")
