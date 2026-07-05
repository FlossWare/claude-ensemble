#!/usr/bin/env python3
"""
Use Formal Verification Expert

Demo script showing how to use the trained formal verification expert
to analyze verification tasks and get recommendations.
"""

import pickle
import numpy as np
from pathlib import Path

def extract_features_from_task(task_text):
    """Extract verification-specific features from task description"""
    task_lower = task_text.lower() if task_text else ""

    features = {}

    # Verification keywords
    features['has_verify'] = 1.0 if any(kw in task_lower for kw in ['verify', 'prove', 'check', 'formal']) else 0.0
    features['has_correctness'] = 1.0 if any(kw in task_lower for kw in ['correct', 'specification', 'invariant']) else 0.0
    features['has_safety'] = 1.0 if any(kw in task_lower for kw in ['safety', 'memory', 'null', 'bounds']) else 0.0
    features['has_termination'] = 1.0 if any(kw in task_lower for kw in ['terminat', 'halting', 'loop', 'recursive']) else 0.0
    features['has_concurrency'] = 1.0 if any(kw in task_lower for kw in ['concurrent', 'thread', 'lock', 'race', 'deadlock']) else 0.0

    # Code patterns
    features['has_array'] = 1.0 if any(kw in task_lower for kw in ['array', 'list', 'buffer']) else 0.0
    features['has_pointer'] = 1.0 if any(kw in task_lower for kw in ['pointer', 'reference', 'dereference']) else 0.0
    features['has_sorting'] = 1.0 if any(kw in task_lower for kw in ['sort', 'search', 'binary search']) else 0.0
    features['has_tree'] = 1.0 if any(kw in task_lower for kw in ['tree', 'graph', 'linked list']) else 0.0

    # Tools mentioned
    features['mentions_dafny'] = 1.0 if 'dafny' in task_lower else 0.0
    features['mentions_coq'] = 1.0 if 'coq' in task_lower else 0.0
    features['mentions_z3'] = 1.0 if 'z3' in task_lower else 0.0
    features['mentions_tla'] = 1.0 if 'tla' in task_lower else 0.0

    # Complexity indicators
    features['task_length'] = min(len(task_text) / 1000.0, 1.0) if task_text else 0.0
    features['has_code'] = 1.0 if '```' in task_text else 0.0

    return list(features.values())

def analyze_verification_task(task_description):
    """Analyze a verification task and provide recommendations"""

    # Load model
    model_path = Path.home() / '.claude' / 'learning' / 'formal_verification_expert.pkl'
    if not model_path.exists():
        print(f"Error: Model not found at {model_path}")
        print("Run formal_verification_expert_trainer.py first")
        return None

    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    # Vectorize task
    X_tfidf = model['vectorizer'].transform([task_description]).toarray()
    X_manual = extract_features_from_task(task_description)
    X = np.hstack([X_tfidf, [X_manual]])

    # Get predictions with probabilities
    pattern = model['pattern_classifier'].predict(X)[0]
    pattern_probs = model['pattern_classifier'].predict_proba(X)[0]
    pattern_classes = model['pattern_classifier'].classes_

    tool = model['tool_classifier'].predict(X)[0]
    tool_probs = model['tool_classifier'].predict_proba(X)[0]
    tool_classes = model['tool_classifier'].classes_

    technique = model['technique_classifier'].predict(X)[0]
    technique_probs = model['technique_classifier'].predict_proba(X)[0]
    technique_classes = model['technique_classifier'].classes_

    # Get top 3 recommendations for each category
    top_patterns = sorted(zip(pattern_classes, pattern_probs), key=lambda x: x[1], reverse=True)[:3]
    top_tools = sorted(zip(tool_classes, tool_probs), key=lambda x: x[1], reverse=True)[:3]
    top_techniques = sorted(zip(technique_classes, technique_probs), key=lambda x: x[1], reverse=True)[:3]

    # Access knowledge base
    kb = model['knowledge_base']

    # Format results
    result = {
        'task': task_description,
        'recommendations': {
            'pattern': pattern,
            'tool': tool,
            'technique': technique
        },
        'top_patterns': [{'name': p, 'confidence': float(c)} for p, c in top_patterns],
        'top_tools': [{'name': t, 'confidence': float(c)} for t, c in top_tools],
        'top_techniques': [{'name': t, 'confidence': float(c)} for t, c in top_techniques],
        'guidance': {}
    }

    # Add knowledge base guidance
    if pattern in kb['common_patterns']:
        result['guidance']['pattern'] = kb['common_patterns'][pattern]

    if tool in kb['tool_selection']:
        result['guidance']['tool'] = kb['tool_selection'][tool]

    if technique in kb['proof_techniques']:
        result['guidance']['technique'] = kb['proof_techniques'][technique]

    return result

def print_analysis(result):
    """Pretty print analysis results"""
    if not result:
        return

    print("=" * 80)
    print("FORMAL VERIFICATION ANALYSIS")
    print("=" * 80)
    print(f"\nTask: {result['task']}")
    print("\n" + "-" * 80)
    print("PRIMARY RECOMMENDATIONS:")
    print("-" * 80)
    print(f"  Pattern: {result['recommendations']['pattern']}")
    print(f"  Tool:    {result['recommendations']['tool']}")
    print(f"  Technique: {result['recommendations']['technique']}")

    print("\n" + "-" * 80)
    print("TOP PATTERNS (by confidence):")
    print("-" * 80)
    for p in result['top_patterns']:
        print(f"  {p['name']:30s} {p['confidence']:.1%}")

    print("\n" + "-" * 80)
    print("TOP TOOLS (by confidence):")
    print("-" * 80)
    for t in result['top_tools']:
        print(f"  {t['name']:30s} {t['confidence']:.1%}")

    print("\n" + "-" * 80)
    print("TOP TECHNIQUES (by confidence):")
    print("-" * 80)
    for t in result['top_techniques']:
        print(f"  {t['name']:30s} {t['confidence']:.1%}")

    if result['guidance']:
        print("\n" + "=" * 80)
        print("DETAILED GUIDANCE:")
        print("=" * 80)

        if 'pattern' in result['guidance']:
            print(f"\nPattern Guidance ({result['recommendations']['pattern']}):")
            for key, value in result['guidance']['pattern'].items():
                print(f"  {key}: {value}")

        if 'tool' in result['guidance']:
            print(f"\nTool Guidance ({result['recommendations']['tool']}):")
            for key, value in result['guidance']['tool'].items():
                print(f"  {key}: {value}")

        if 'technique' in result['guidance']:
            print(f"\nTechnique Guidance ({result['recommendations']['technique']}):")
            for key, value in result['guidance']['technique'].items():
                print(f"  {key}: {value}")

    print("\n" + "=" * 80)

def main():
    """Demo with example verification tasks"""

    examples = [
        "Prove binary search correctness with loop invariants",
        "Verify no null pointer dereferences in linked list traversal",
        "Check for data races in concurrent hash table implementation",
        "Model AWS distributed consensus protocol with TLA+",
        "Verify sorting algorithm maintains permutation of input",
        "Prove recursive function terminates using well-founded induction",
        "Check buffer overflow in C string manipulation functions",
        "Verify smart contract functional correctness using formal methods"
    ]

    print("FORMAL VERIFICATION EXPERT - DEMO\n")
    print("Analyzing example verification tasks...\n")

    for i, task in enumerate(examples, 1):
        print(f"\n{'='*80}")
        print(f"EXAMPLE {i}/{len(examples)}")
        result = analyze_verification_task(task)
        print_analysis(result)
        print()

    # Interactive mode
    print("\n" + "="*80)
    print("INTERACTIVE MODE")
    print("="*80)
    print("Enter verification tasks (empty line to quit):\n")

    while True:
        try:
            task = input("Task: ").strip()
            if not task:
                break

            result = analyze_verification_task(task)
            print_analysis(result)
            print()
        except (KeyboardInterrupt, EOFError):
            break

    print("\nDone!")

if __name__ == '__main__':
    main()
