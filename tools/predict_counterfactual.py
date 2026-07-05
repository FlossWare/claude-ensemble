#!/usr/bin/env python3
"""
Counterfactual Scenario Predictor

Uses trained Random Forest models to predict outcomes of what-if scenarios.

Usage:
    python3 predict_counterfactual.py "What if we increase timeout from 30s to 120s?"
    python3 predict_counterfactual.py "What if we remove this deprecated API?"
    echo "What if we upgrade Python 3.9 to 3.12?" | python3 predict_counterfactual.py

Output: JSON with impact severity, success probability, rollback difficulty, and recommendation
"""

import sys
import json
from pathlib import Path

# Import the reasoner
sys.path.insert(0, str(Path(__file__).parent))
from counterfactual_reasoning_trainer import CounterfactualReasoner


def main():
    # Load trained model
    model_path = Path.home() / "Development" / "redhat" / "scm" / "gitlab" / "cee" / "sfloess" / "claude-global-skills" / "learning" / "counterfactual_reasoner.pkl"

    if not model_path.exists():
        print("❌ Model not found. Train it first:", file=sys.stderr)
        print("   python3 counterfactual_reasoning_trainer.py", file=sys.stderr)
        sys.exit(1)

    reasoner = CounterfactualReasoner()
    reasoner.load(model_path)

    # Get scenario from stdin or argv
    if len(sys.argv) > 1:
        scenario = " ".join(sys.argv[1:])
    else:
        scenario = sys.stdin.read().strip()

    if not scenario:
        print("Usage: predict_counterfactual.py <scenario>", file=sys.stderr)
        print("   or: echo 'scenario' | predict_counterfactual.py", file=sys.stderr)
        sys.exit(1)

    # Predict
    result = reasoner.predict(scenario)

    # Pretty print
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
