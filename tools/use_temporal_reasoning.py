#!/usr/bin/env python3
"""
Temporal Reasoning Model Usage Example

Demonstrates how to load and use the trained temporal reasoning model
for analyzing temporal logic, planning, and time-based reasoning tasks.
"""

import pickle
import sys
from pathlib import Path
import json

def load_temporal_reasoning_model(model_path='/home/sfloess/.claude/learning/temporal_reasoning_model.pkl'):
    """Load the trained temporal reasoning model"""
    with open(model_path, 'rb') as f:
        data = pickle.load(f)
    return data

def analyze_temporal_query(query, model_data):
    """Analyze a temporal reasoning query"""
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    model = model_data['model']
    vectorizer = model_data['vectorizer']
    feature_names = model_data['feature_names']
    patterns = model_data['patterns']

    # Vectorize query
    X_tfidf = vectorizer.transform([query])

    # Extract custom features (same as training)
    custom_features = extract_temporal_features(query, patterns)
    X_custom = np.zeros((1, len(feature_names)))
    for j, fname in enumerate(feature_names):
        X_custom[0, j] = custom_features.get(fname, 0)

    # Combine features
    X_combined = np.hstack([X_tfidf.toarray(), X_custom])

    # Predict
    prediction = model.predict(X_combined)[0]
    probabilities = model.predict_proba(X_combined)[0]
    confidence = max(probabilities)

    # Get top predictions
    top_indices = np.argsort(probabilities)[::-1][:5]
    top_classes = model.classes_[top_indices].tolist()
    top_probs = probabilities[top_indices].tolist()

    return {
        'query': query,
        'prediction': prediction,
        'confidence': confidence,
        'category': prediction.split('_')[0],
        'subcategory': '_'.join(prediction.split('_')[1:]),
        'top_predictions': [
            {'class': cls, 'probability': prob}
            for cls, prob in zip(top_classes, top_probs)
        ],
        'interpretation': interpret_prediction(prediction, patterns)
    }

def extract_temporal_features(text, patterns):
    """Extract temporal features from text"""
    features = {}
    text_lower = text.lower()

    # Temporal keywords
    temporal_keywords = [
        'before', 'after', 'during', 'while', 'when', 'until', 'since',
        'always', 'eventually', 'never', 'sometimes', 'often', 'rarely',
        'immediately', 'delayed', 'scheduled', 'periodic', 'continuous',
        'sequential', 'parallel', 'concurrent', 'simultaneous', 'overlapping',
        'deadline', 'timeout', 'duration', 'interval', 'period', 'phase',
        'start', 'end', 'begin', 'finish', 'complete', 'terminate',
        'wait', 'delay', 'lag', 'lead', 'gap', 'window', 'span',
        'early', 'late', 'on-time', 'overdue', 'ahead', 'behind'
    ]

    for keyword in temporal_keywords:
        features[f'temporal_{keyword}'] = text_lower.count(keyword)

    # Planning keywords
    planning_keywords = [
        'schedule', 'plan', 'allocate', 'assign', 'distribute', 'arrange',
        'optimize', 'minimize', 'maximize', 'balance', 'prioritize',
        'order', 'sequence', 'rank', 'sort', 'organize',
        'coordinate', 'synchronize', 'align', 'orchestrate',
        'resource', 'capacity', 'constraint', 'requirement', 'goal',
        'dependency', 'prerequisite', 'successor', 'predecessor',
        'critical-path', 'bottleneck', 'slack', 'float', 'buffer'
    ]

    for keyword in planning_keywords:
        features[f'planning_{keyword}'] = text_lower.count(keyword)

    # Constraint keywords
    constraint_keywords = [
        'must', 'cannot', 'required', 'forbidden', 'mandatory', 'optional',
        'minimum', 'maximum', 'exactly', 'at-most', 'at-least',
        'within', 'outside', 'between', 'range', 'limit', 'bound',
        'violate', 'satisfy', 'conflict', 'compatible', 'feasible',
        'impossible', 'possible', 'allowed', 'prohibited'
    ]

    for keyword in constraint_keywords:
        features[f'constraint_{keyword}'] = text_lower.count(keyword)

    # Causality keywords
    causality_keywords = [
        'cause', 'effect', 'result', 'consequence', 'impact', 'influence',
        'trigger', 'activate', 'enable', 'disable', 'block', 'prevent',
        'lead-to', 'result-in', 'due-to', 'because', 'therefore',
        'precondition', 'postcondition', 'invariant', 'assumption'
    ]

    for keyword in causality_keywords:
        features[f'causality_{keyword}'] = text_lower.count(keyword)

    # Complexity indicators
    features['has_multiple_timescales'] = int(
        sum(1 for t in ['second', 'minute', 'hour', 'day', 'week', 'month']
            if t in text_lower) > 1
    )
    features['has_dependencies'] = int(
        any(dep in text_lower for dep in ['depend', 'require', 'need', 'must'])
    )
    features['has_concurrency'] = int(
        any(conc in text_lower for conc in ['parallel', 'concurrent', 'simultaneous'])
    )
    features['has_deadlines'] = int(
        any(dl in text_lower for dl in ['deadline', 'due', 'by', 'before'])
    )

    # Interval algebra
    interval_relations = [
        'before', 'meets', 'overlaps', 'finished_by', 'contains',
        'starts', 'equals', 'started_by', 'during', 'finishes',
        'overlapped_by', 'met_by', 'after'
    ]
    features['interval_relation_count'] = sum(
        1 for rel in interval_relations
        if rel.replace('_', ' ') in text_lower
    )

    # Optimization
    features['has_optimization'] = int(
        any(opt in text_lower for opt in ['optimize', 'minimize', 'maximize', 'best'])
    )
    features['has_multi_objective'] = int(
        sum(1 for obj in ['time', 'cost', 'quality', 'resource']
            if obj in text_lower) > 1
    )

    return features

def interpret_prediction(prediction, patterns):
    """Interpret the prediction and provide recommendations"""
    parts = prediction.split('_')
    category = parts[0]

    interpretations = {
        'interval': {
            'description': 'Temporal interval relationship detected',
            'patterns': patterns['interval_relations'],
            'recommendation': 'Use Allen\'s Interval Algebra for formal reasoning'
        },
        'constraint': {
            'description': 'Temporal constraint satisfaction problem',
            'patterns': patterns['temporal_constraints'],
            'recommendation': 'Check feasibility using constraint propagation'
        },
        'planning': {
            'description': 'Planning or scheduling task detected',
            'patterns': patterns['planning_types'],
            'recommendation': 'Apply appropriate planning algorithm based on complexity'
        },
        'logic': {
            'description': 'Temporal logic query',
            'patterns': patterns['temporal_logic'],
            'recommendation': 'Use formal verification methods for critical properties'
        },
        'pattern': {
            'description': 'Temporal pattern detection',
            'patterns': patterns['temporal_patterns'],
            'recommendation': 'Analyze historical data for pattern validation'
        },
        'causal': {
            'description': 'Causal-temporal relationship',
            'recommendation': 'Verify temporal precedence and rule out confounders'
        }
    }

    return interpretations.get(category, {
        'description': 'Unknown temporal reasoning category',
        'recommendation': 'Review query for temporal keywords'
    })

def main():
    """Main demonstration"""
    print("=" * 80)
    print("TEMPORAL REASONING MODEL - USAGE DEMO")
    print("=" * 80)

    # Load model
    print("\nLoading temporal reasoning model...")
    model_data = load_temporal_reasoning_model()
    stats = model_data['training_stats']

    print(f"Model loaded successfully")
    print(f"Training accuracy: {stats['training_accuracy']:.3f}")
    print(f"Test accuracy: {stats['test_accuracy']:.3f}")
    print(f"F1 score: {stats['f1_score']:.3f}")
    print(f"Total patterns learned: {stats['total_examples']}")

    # Interactive mode or test examples
    if len(sys.argv) > 1:
        # Analyze command line query
        query = ' '.join(sys.argv[1:])
        result = analyze_temporal_query(query, model_data)
        print("\n" + "=" * 80)
        print("ANALYSIS RESULT")
        print("=" * 80)
        print(json.dumps(result, indent=2))
    else:
        # Run test examples
        test_queries = [
            "Task A must finish before Task B can start",
            "Schedule 10 parallel jobs with resource constraints",
            "Will the system eventually reach a stable state?",
            "Detect periodic failures occurring every Monday",
            "Optimize multi-objective planning with time and cost constraints",
            "Check if there is a circular dependency in the workflow",
            "Plan resource allocation for 5 concurrent tasks",
            "Analyze temporal causality between deployment and errors",
            "Find critical path in project schedule",
            "Does the schedule violate any deadline constraints?",
        ]

        print("\n" + "=" * 80)
        print("TEST QUERIES")
        print("=" * 80)

        for i, query in enumerate(test_queries, 1):
            result = analyze_temporal_query(query, model_data)
            print(f"\n{i}. QUERY: {query}")
            print(f"   Category: {result['category']}")
            print(f"   Prediction: {result['subcategory']}")
            print(f"   Confidence: {result['confidence']:.3f}")
            print(f"   Interpretation: {result['interpretation']['description']}")
            print(f"   Recommendation: {result['interpretation'].get('recommendation', 'N/A')}")

            # Show top 3 alternatives
            print(f"   Alternatives:")
            for j, pred in enumerate(result['top_predictions'][:3], 1):
                print(f"      {j}. {pred['class']} ({pred['probability']:.3f})")

    print("\n" + "=" * 80)
    print("USAGE INSTRUCTIONS")
    print("=" * 80)
    print("\nCommand line usage:")
    print("  python3 use_temporal_reasoning.py \"your temporal query here\"")
    print("\nPython API usage:")
    print("  from use_temporal_reasoning import load_temporal_reasoning_model, analyze_temporal_query")
    print("  model = load_temporal_reasoning_model()")
    print("  result = analyze_temporal_query('your query', model)")
    print("=" * 80)

if __name__ == '__main__':
    main()
