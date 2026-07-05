#!/usr/bin/env python3
"""
Test script for resource usage predictor.

Validates predictions against held-out test data and generates accuracy report.
"""

import sys
import json
from pathlib import Path
import numpy as np
from datetime import datetime

sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))
from postgres_adapter import get_db

sys.path.insert(0, str(Path.home() / 'Development' / 'redhat' / 'scm' / 'gitlab' / 'cee' / 'sfloess' / 'claude-global-skills' / 'tools'))
from resource_usage_predictor import ResourceUsagePredictor


def test_predictor():
    """Test predictor on recent data."""
    print("=" * 80)
    print("RESOURCE USAGE PREDICTOR - TEST REPORT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Load trained model
    model_path = Path.home() / '.claude' / 'learning' / 'resource_usage_predictor.pkl'
    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}")
        print("Run: python3 tools/resource_usage_predictor.py --retrain")
        return

    predictor = ResourceUsagePredictor.load(model_path)
    print(f"✓ Model loaded from: {model_path}")

    # Get recent test data (last 50 successful executions)
    db = get_db()
    rows = db.query("""
        SELECT model, workflow, task_type,
               input_tokens, output_tokens, duration_ms, cost_usd
        FROM monitoring.execution_summary
        WHERE outcome = 'success'
        ORDER BY id DESC
        LIMIT 50
    """)

    if len(rows) == 0:
        print("ERROR: No test data available")
        return

    print(f"✓ Loaded {len(rows)} test samples\n")

    # Make predictions
    predictions = []
    actuals = []

    for row in rows:
        # Predict
        pred = predictor.predict(
            model=row['model'],
            workflow=row['workflow'] or 'unknown',
            task_type=row['task_type'] or 'unknown',
            task_description=None
        )

        # Actual
        actual = {
            'input_tokens': row['input_tokens'] or 0,
            'output_tokens': row['output_tokens'] or 0,
            'duration_ms': row['duration_ms'] or 0,
            'cost_usd': row['cost_usd'] or 0.0
        }

        predictions.append(pred)
        actuals.append(actual)

    # Calculate errors
    errors = {
        'input_tokens': [],
        'output_tokens': [],
        'duration_ms': [],
        'cost_usd': []
    }

    for pred, actual in zip(predictions, actuals):
        for key in errors.keys():
            if actual[key] > 0:
                error = abs(pred[key] - actual[key]) / actual[key] * 100
                errors[key].append(error)

    # Print results
    print("PREDICTION ACCURACY:")
    print("-" * 80)
    print(f"{'Metric':<20} {'Mean Error':<15} {'Median Error':<15} {'90th %ile':<15}")
    print("-" * 80)

    for key in ['input_tokens', 'output_tokens', 'duration_ms', 'cost_usd']:
        if len(errors[key]) > 0:
            mean_err = np.mean(errors[key])
            median_err = np.median(errors[key])
            p90_err = np.percentile(errors[key], 90)

            print(f"{key:<20} {mean_err:>12.1f}%  {median_err:>12.1f}%  {p90_err:>12.1f}%")

    print("-" * 80)

    # Show a few examples
    print("\nEXAMPLE PREDICTIONS (first 5):")
    print("-" * 80)

    for i in range(min(5, len(predictions))):
        row = rows[i]
        pred = predictions[i]
        actual = actuals[i]

        print(f"\n{i+1}. {row['model']} / {row['workflow']} / {row['task_type']}")
        print(f"   Input tokens:   Pred {pred['input_tokens']:>6}  Actual {actual['input_tokens']:>6}  Error {abs(pred['input_tokens']-actual['input_tokens'])/max(actual['input_tokens'],1)*100:>5.1f}%")
        print(f"   Output tokens:  Pred {pred['output_tokens']:>6}  Actual {actual['output_tokens']:>6}  Error {abs(pred['output_tokens']-actual['output_tokens'])/max(actual['output_tokens'],1)*100:>5.1f}%")
        print(f"   Duration (ms):  Pred {pred['duration_ms']:>6}  Actual {actual['duration_ms']:>6}  Error {abs(pred['duration_ms']-actual['duration_ms'])/max(actual['duration_ms'],1)*100:>5.1f}%")
        print(f"   Cost (USD):     Pred ${pred['cost_usd']:.4f}  Actual ${actual['cost_usd']:.4f}  Error {abs(pred['cost_usd']-actual['cost_usd'])/max(actual['cost_usd'],0.0001)*100:>5.1f}%")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    test_predictor()
