#!/usr/bin/env python3
"""
Predict Team Velocity - CLI Interface

Takes a workflow configuration file (JSON) and returns velocity predictions.
Used by JavaScript adapter for workflow integration.
"""

import json
import sys
from pathlib import Path
from team_velocity_predictor import TeamVelocityPredictor


def main():
    if len(sys.argv) != 2:
        print(json.dumps({
            'error': 'Usage: predict_team_velocity.py <config.json>',
            'success': False
        }))
        sys.exit(1)

    config_file = sys.argv[1]

    # Load configuration
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(json.dumps({
            'error': f'Failed to load config: {e}',
            'success': False
        }))
        sys.exit(1)

    # Load model
    model_path = Path.home() / ".claude" / "learning" / "team_velocity_predictor.pkl"
    if not model_path.exists():
        print(json.dumps({
            'error': f'Model not found at {model_path}. Run: python3 tools/team_velocity_predictor.py',
            'success': False
        }))
        sys.exit(1)

    try:
        predictor = TeamVelocityPredictor()
        # Suppress stdout during load
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            predictor.load(model_path)
    except Exception as e:
        print(json.dumps({
            'error': f'Failed to load model: {e}',
            'success': False
        }))
        sys.exit(1)

    # Make prediction
    try:
        result = predictor.predict(config)
        result['success'] = True
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({
            'error': f'Prediction failed: {e}',
            'success': False
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
