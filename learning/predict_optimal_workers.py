#!/usr/bin/env python3
"""
Predict optimal worker count for a given task
Uses trained Random Forest model

Usage:
    python3 predict_optimal_workers.py --complexity 50000 --duration 30000 --budget 0.05
    python3 predict_optimal_workers.py --task-type fleet-orchestrator
"""

import pickle
import argparse
import json

MODEL_PATH = '/home/sfloess/.claude/learning/worker_count_optimizer.pkl'

def load_model():
    """Load trained model"""
    with open(MODEL_PATH, 'rb') as f:
        return pickle.load(f)

def predict_workers(complexity, duration_ms, budget_usd):
    """
    Predict optimal worker count

    Args:
        complexity: Task complexity (proxy: total tokens, e.g., 10000-100000)
        duration_ms: Expected duration in milliseconds
        budget_usd: Budget in USD

    Returns:
        int: Recommended worker count
    """
    model_data = load_model()
    model = model_data['model']

    # Normalize features (same as training)
    X = [[
        complexity / 100000,     # Normalize tokens
        duration_ms / 60000,     # Normalize duration (ms to minutes)
        budget_usd * 10          # Normalize cost
    ]]

    prediction = model.predict(X)[0]

    # Round to nearest integer, min 1
    return max(1, round(prediction))

def get_optimal_for_task_type(task_type):
    """
    Get optimal worker count for known task type

    Args:
        task_type: Workflow name (e.g., 'fleet-orchestrator')

    Returns:
        int: Optimal worker count
    """
    model_data = load_model()
    optimal_counts = model_data['optimal_counts']

    return optimal_counts.get(task_type, None)

def main():
    parser = argparse.ArgumentParser(description='Predict optimal worker count')
    parser.add_argument('--complexity', type=float, help='Task complexity (tokens)')
    parser.add_argument('--duration', type=float, help='Expected duration (ms)')
    parser.add_argument('--budget', type=float, help='Budget (USD)')
    parser.add_argument('--task-type', type=str, help='Known task type')

    args = parser.parse_args()

    if args.task_type:
        # Lookup optimal count for known task type
        optimal = get_optimal_for_task_type(args.task_type)
        if optimal:
            print(json.dumps({
                'task_type': args.task_type,
                'optimal_workers': optimal,
                'method': 'lookup'
            }, indent=2))
        else:
            print(json.dumps({
                'error': f'Unknown task type: {args.task_type}',
                'available_types': list(load_model()['optimal_counts'].keys())
            }, indent=2))

    elif args.complexity and args.duration and args.budget:
        # Predict using model
        optimal = predict_workers(args.complexity, args.duration, args.budget)

        print(json.dumps({
            'complexity': args.complexity,
            'duration_ms': args.duration,
            'budget_usd': args.budget,
            'optimal_workers': optimal,
            'method': 'regression'
        }, indent=2))

    else:
        parser.print_help()
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
