#!/usr/bin/env python3
"""
Simple CLI wrapper for complexity predictions

Usage:
  python3 predict_complexity.py "Task description here"

Returns JSON with prediction
"""

import sys
import json
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent))
from complexity_estimator import ComplexityEstimator

def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'No task description provided'}))
        sys.exit(1)

    task = ' '.join(sys.argv[1:])

    # Load model
    model_path = Path.home() / ".claude" / "learning" / "complexity_estimator.pkl"
    estimator = ComplexityEstimator()
    estimator.load(model_path)

    # Predict
    result = estimator.predict(task)

    # Output JSON
    print(json.dumps(result))

if __name__ == "__main__":
    main()
