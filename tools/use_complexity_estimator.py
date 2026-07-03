#!/usr/bin/env python3
"""
Example: Using the Complexity Estimator

Shows how to load and use the trained complexity estimator
to predict task duration and confidence before execution.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from complexity_estimator import ComplexityEstimator


def main():
    # Load trained model
    model_path = Path.home() / ".claude" / "learning" / "complexity_estimator.pkl"

    estimator = ComplexityEstimator()
    estimator.load(model_path)

    # Example tasks
    tasks = [
        "Fix typo in documentation",
        "Implement OAuth2 authentication flow",
        "Review code for security vulnerabilities across 10 files",
        "Create Java Maven project with Spring Boot",
        "Optimize database query performance",
        "Add unit tests for user service",
        "Refactor authentication module",
        "FIX critical bug in payment processing",
        "ANALYZE memory leak in production",
    ]

    print("=" * 70)
    print("COMPLEXITY ESTIMATOR - PREDICTIONS")
    print("=" * 70)

    for task in tasks:
        result = estimator.predict(task)
        print(f"\n📋 Task: {task}")
        print(f"   Category:   {result['complexity_category']:15s}")
        print(f"   Duration:   {result['predicted_duration_ms']:7,} ms ({result['predicted_duration_ms']/1000:5.1f}s)")
        print(f"   Confidence: {result['predicted_confidence']:5.2f}")

    print("\n" + "=" * 70)
    print("💡 USAGE TIPS:")
    print("=" * 70)
    print("- SIMPLE tasks (<5s): Use fast, cheap models")
    print("- MEDIUM tasks (5-20s): Use balanced models")
    print("- COMPLEX tasks (20-60s): Use higher-quality models")
    print("- VERY_COMPLEX tasks (>60s): Use top-tier models + retries")
    print("\n- Low confidence (<0.6): Add exploration bonus")
    print("- High confidence (>0.8): Exploit known strategies")


if __name__ == "__main__":
    main()
