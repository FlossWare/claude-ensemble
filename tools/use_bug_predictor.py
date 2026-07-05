#!/usr/bin/env python3
"""
Bug Predictor Usage Script

Quick script to predict bug likelihood for tasks.
Loads the trained model and provides predictions.

Usage:
    python3 use_bug_predictor.py "Fix authentication bug"
    python3 use_bug_predictor.py "Implement OAuth2 flow" --model haiku
"""

import sys
import json
from pathlib import Path
import argparse

# Import the predictor
sys.path.insert(0, str(Path(__file__).parent))
from bug_predictor import BugPredictor


def main():
    parser = argparse.ArgumentParser(description='Predict bug likelihood for a task')
    parser.add_argument('task', help='Task description')
    parser.add_argument('--model', help='Model to use (e.g., opus, sonnet, haiku)')
    parser.add_argument('--workflow', help='Workflow name (e.g., code-review)')
    parser.add_argument('--task-type', help='Task type (e.g., security, refactor)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    # Load model
    model_path = Path.home() / ".claude" / "learning" / "bug_predictor.pkl"

    if not model_path.exists():
        print(f"❌ Model not found at {model_path}")
        print("Run: python3 bug_predictor.py to train the model first")
        sys.exit(1)

    predictor = BugPredictor()
    predictor.load(model_path)

    # Predict
    result = predictor.predict(
        args.task,
        model=args.model,
        workflow=args.workflow,
        task_type=args.task_type
    )

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"TASK: {args.task}")
        if args.model:
            print(f"MODEL: {args.model}")
        print(f"{'='*60}")
        print(f"\n🎯 Bug Likelihood: {result['bug_probability']:.1%}")
        print(f"⚠️  Risk Category:  {result['risk_category']}")
        print(f"📊 Prediction:     {result['prediction']}")

        if result['top_risk_factors']:
            print(f"\n🔍 Top Risk Factors:")
            for i, factor in enumerate(result['top_risk_factors'][:5], 1):
                print(f"   {i}. {factor['feature']}: {factor['value']} (contribution: {factor['contribution']:.4f})")

        print(f"\n💡 Recommendation:")
        if result['bug_probability'] < 0.3:
            print("   Low risk - proceed normally")
        elif result['bug_probability'] < 0.5:
            print("   Medium risk - consider code review")
        elif result['bug_probability'] < 0.7:
            print("   High risk - require code review and tests")
        else:
            print("   Critical risk - use multi-model consensus and thorough testing")


if __name__ == "__main__":
    main()
