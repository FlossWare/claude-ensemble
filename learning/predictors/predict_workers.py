#!/usr/bin/env python3
"""
Simple worker allocation prediction helper

Usage:
    from predictors.predict_workers import predict_worker_count

    workers = predict_worker_count(
        total_tokens=10000,
        unique_models=3,
        workflow_complexity=60,
        has_complex_task=True
    )
"""

import pickle
import numpy as np
from pathlib import Path


def predict_worker_count(
    total_tokens=1000,
    avg_tokens_per_worker=None,
    avg_output_input_ratio=1.0,
    unique_models=1,
    workflow_complexity=50,
    success_rate=0.9,
    avg_quality=0.85,
    has_complex_task=False,
    avg_duration_ms=3000,
):
    """
    Predict optimal worker count for a task

    Args:
        total_tokens: Total input + output tokens (default: 1000)
        avg_tokens_per_worker: Tokens per worker (default: total_tokens / unique_models)
        avg_output_input_ratio: Output/input token ratio (default: 1.0)
        unique_models: Number of different AI models (default: 1) - MOST IMPORTANT
        workflow_complexity: Task complexity 0-100 (default: 50)
        success_rate: Historical success rate 0-1 (default: 0.9)
        avg_quality: Expected quality score 0-1 (default: 0.85)
        has_complex_task: Whether task is complex (default: False)
        avg_duration_ms: Expected duration per worker (default: 3000)

    Returns:
        int: Recommended worker count (1-8+)
    """

    # Load model
    model_path = Path.home() / '.claude' / 'learning' / 'predictors' / 'worker-allocation-optimizer.pkl'
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)

    # Default avg_tokens_per_worker
    if avg_tokens_per_worker is None:
        avg_tokens_per_worker = total_tokens / max(unique_models, 1)

    # Build feature dict
    features = {
        'total_tokens': total_tokens,
        'avg_tokens_per_worker': avg_tokens_per_worker,
        'avg_output_input_ratio': avg_output_input_ratio,
        'unique_models': unique_models,
        'workflow_complexity': workflow_complexity,
        'success_rate': success_rate,
        'avg_quality': avg_quality,
        'has_complex_task': 1 if has_complex_task else 0,
        'avg_duration_ms': avg_duration_ms,
    }

    # Create feature vector
    X = np.array([[features[col] for col in model_data['feature_cols']]])

    # Scale and predict
    X_scaled = model_data['scaler'].transform(X)
    prediction = model_data['model'].predict(X_scaled)[0]

    # Return rounded prediction (min 1 worker)
    return max(1, round(prediction))


def get_model_info():
    """Get model metadata and performance metrics"""
    model_path = Path.home() / '.claude' / 'learning' / 'predictors' / 'worker-allocation-optimizer.pkl'
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)

    return {
        'model_name': model_data['model_name'],
        'metrics': model_data['metrics'],
        'feature_importances': model_data['feature_importances'],
        'feature_cols': model_data['feature_cols'],
    }


if __name__ == '__main__':
    # CLI usage
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: predict_workers.py <total_tokens> [unique_models] [complexity]")
        print("   or: predict_workers.py --info")
        print("\nExample:")
        print("  predict_workers.py 10000 3 60")
        print("  → Predicts worker count for 10K tokens, 3 models, complexity 60")
        sys.exit(1)

    if sys.argv[1] == '--info':
        info = get_model_info()
        print(json.dumps(info, indent=2))
        sys.exit(0)

    total_tokens = int(sys.argv[1])
    unique_models = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    complexity = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    workers = predict_worker_count(
        total_tokens=total_tokens,
        unique_models=unique_models,
        workflow_complexity=complexity,
        has_complex_task=(complexity > 60)
    )

    print(f"{workers}")
