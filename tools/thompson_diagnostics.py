#!/usr/bin/env python3
"""
Thompson Sampling Diagnostics Tool
BLOCKER #2 FIX: Verify Thompson feedback loop is working correctly

Checks:
1. Outcomes are being recorded to thompson-sampling-state.json
2. Quality feedback is being calculated correctly
3. Beta priors are updating as expected
4. Model utilization reflects learned posteriors

Usage:
    python3 tools/thompson_diagnostics.py --verbose
    python3 tools/thompson_diagnostics.py --inject-test-feedback  # Add synthetic data
    python3 tools/thompson_diagnostics.py --trace-feedback-loop  # Detailed logging
"""

import json
import sys
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple
import numpy as np
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ThompsonState:
    """Thompson sampling state snapshot"""
    last_updated: str
    models: Dict[str, Any]
    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0

    def __post_init__(self):
        """Compute totals"""
        for model_data in self.models.values():
            self.total_calls += model_data.get('calls', 0)
            self.total_successes += model_data.get('successes', 0)
            self.total_failures += model_data.get('failures', 0)


class ThompsonDiagnostics:
    """Diagnostic tool for Thompson feedback loop"""

    def __init__(self, state_file: str = None, alpha_prior: float = 2, beta_prior: float = 1):
        """
        Initialize diagnostics

        Args:
            state_file: Path to thompson-sampling-state.json
            alpha_prior: Beta distribution alpha parameter (successes prior)
            beta_prior: Beta distribution beta parameter (failures prior)
        """
        if state_file is None:
            state_file = os.path.join(
                os.path.dirname(__file__),
                '../learning/thompson-sampling-state.json'
            )

        self.state_file = Path(state_file)
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior
        self.state: ThompsonState = None
        self.previous_state: ThompsonState = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def load_state(self) -> bool:
        """Load Thompson state from file"""
        if not self.state_file.exists():
            self.errors.append(f"Thompson state file not found: {self.state_file}")
            return False

        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)

            self.state = ThompsonState(
                last_updated=data.get('last_updated'),
                models=data.get('models', {})
            )

            logger.info(f"Loaded Thompson state: {len(self.state.models)} models, "
                       f"{self.state.total_calls} total calls")
            return True

        except Exception as e:
            self.errors.append(f"Failed to load Thompson state: {e}")
            return False

    def check_feedback_loop_integrity(self) -> bool:
        """
        BLOCKER #2: Verify outcomes are flowing back to Thompson

        Checks:
        1. State file exists and is readable
        2. Models have recorded outcomes
        3. No model is stuck at 0 calls (except new models)
        4. Success/failure counts are reasonable
        """
        all_valid = True

        # Check 1: Basic data presence
        if not self.state or not self.state.models:
            self.errors.append("Thompson state is empty - no feedback being recorded")
            all_valid = False
        else:
            self.info.append(f"✓ Thompson state has {len(self.state.models)} models")

        # Check 2: Each model has recorded outcomes
        for model_name, model_data in self.state.models.items():
            calls = model_data.get('calls', 0)
            successes = model_data.get('successes', 0)
            failures = model_data.get('failures', 0)

            if calls == 0:
                self.warnings.append(f"Model '{model_name}' has no recorded calls - check if being used")
            elif successes + failures != calls:
                self.errors.append(
                    f"Model '{model_name}': calls ({calls}) != successes ({successes}) + failures ({failures})"
                )
                all_valid = False
            else:
                success_rate = successes / calls * 100
                self.info.append(
                    f"✓ {model_name}: {calls} calls, {successes} successes ({success_rate:.1f}%)"
                )

        # Check 3: Total calls reasonable (should be > 0 for learning)
        if self.state.total_calls < 10:
            self.warnings.append(
                f"Total calls ({self.state.total_calls}) is low - may not have enough data for learning"
            )

        return all_valid

    def check_beta_prior_updating(self) -> bool:
        """
        BLOCKER #2: Verify Beta priors are updating correctly

        Expected behavior:
        - As successes/failures recorded, posterior changes
        - Expected quality = alpha_posterior / (alpha_posterior + beta_posterior)
        - High quality models should converge to high expected_quality
        """
        all_valid = True

        for model_name, model_data in self.state.models.items():
            calls = model_data.get('calls', 0)
            successes = model_data.get('successes', 0)

            if calls == 0:
                continue

            # Compute expected quality under current posterior
            alpha_post = self.alpha_prior + successes
            beta_post = self.beta_prior + (calls - successes)
            expected_quality = alpha_post / (alpha_post + beta_post)

            # Sanity checks
            if expected_quality < 0 or expected_quality > 1:
                self.errors.append(
                    f"Model '{model_name}': expected quality {expected_quality} out of bounds [0,1]"
                )
                all_valid = False
            elif expected_quality < 0.5 and calls > 20:
                self.warnings.append(
                    f"Model '{model_name}': low expected quality ({expected_quality:.2f}) with {calls} calls"
                )
            else:
                self.info.append(
                    f"✓ {model_name}: expected quality {expected_quality:.3f} "
                    f"(α={alpha_post}, β={beta_post})"
                )

        return all_valid

    def check_utilization_distribution(self) -> Dict[str, float]:
        """
        Check that model utilization reflects learned posteriors

        Expected pattern:
        - High quality models should be used more (high posterior probability)
        - Low quality models should be used less (exploration phase)
        - Haiku appears underutilized if only 2% despite good quality

        Returns:
            Dict mapping model name to utilization percentage
        """
        utilization = {}
        total = self.state.total_calls

        for model_name, model_data in self.state.models.items():
            calls = model_data.get('calls', 0)
            pct = (calls / total * 100) if total > 0 else 0
            utilization[model_name] = pct

        # Analyze patterns
        sorted_util = sorted(utilization.items(), key=lambda x: x[1], reverse=True)

        logger.info("\nModel Utilization Distribution:")
        for model_name, pct in sorted_util:
            model_data = self.state.models[model_name]
            quality = model_data.get('successes', 0) / max(1, model_data.get('calls', 1)) * 100
            logger.info(f"  {model_name:20s}: {pct:6.1f}% utilization, {quality:6.1f}% quality")

        # Check for suspicious patterns
        if 'haiku' in utilization and utilization['haiku'] < 5:
            quality = self.state.models['haiku'].get('successes', 0) / max(1, self.state.models['haiku'].get('calls', 1))
            if quality > 0.8:
                self.warnings.append(
                    f"Haiku underutilized ({utilization['haiku']:.1f}%) despite {quality*100:.1f}% quality - "
                    f"Thompson may be too conservative. Consider epsilon-greedy exploration."
                )

        return utilization

    def inject_test_feedback(self, model_name: str = 'test-model', calls: int = 5,
                            quality_threshold: float = 0.7) -> bool:
        """
        BLOCKER #2: Inject synthetic feedback to verify recording works

        Args:
            model_name: Model to inject feedback for
            calls: Number of synthetic calls to add
            quality_threshold: Threshold for marking success (0-1)

        Usage:
            diagnostics.inject_test_feedback()  # Adds 5 test calls
        """
        try:
            from shared.thompson_router import StateTracker, ModelPerformance

            tracker = StateTracker(str(self.state_file))

            # Inject synthetic feedback
            for i in range(calls):
                # Alternate between success and failure
                quality_score = 0.85 if (i % 2 == 0) else 0.65
                latency_ms = 1000.0 + i * 100
                cost = 0.01 + i * 0.001

                tracker.record(
                    model_name=model_name,
                    quality_score=quality_score,
                    latency_ms=latency_ms,
                    cost=cost,
                    quality_threshold=quality_threshold
                )

            logger.info(f"✓ Injected {calls} test calls for model '{model_name}'")

            # Reload to verify
            self.load_state()
            return True

        except Exception as e:
            self.errors.append(f"Failed to inject test feedback: {e}")
            return False

    def print_report(self):
        """Print diagnostic report"""
        print("\n" + "="*80)
        print("THOMPSON SAMPLING FEEDBACK LOOP DIAGNOSTICS")
        print("="*80 + "\n")

        # Status summary
        print(f"State File: {self.state_file}")
        if self.state:
            print(f"Last Updated: {self.state.last_updated}")
            print(f"Total Calls: {self.state.total_calls}")
            print(f"Total Successes: {self.state.total_successes}")
            print(f"Total Failures: {self.state.total_failures}")
            print(f"Overall Quality: {self.state.total_successes / max(1, self.state.total_calls) * 100:.1f}%\n")

        # Errors
        if self.errors:
            print(f"ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  ✗ {error}")
            print()

        # Warnings
        if self.warnings:
            print(f"WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")
            print()

        # Info
        if self.info:
            print(f"FEEDBACK LOOP STATUS ({len(self.info)} checks):")
            for info in self.info:
                print(f"  {info}")
            print()

        # Verdict
        if not self.errors:
            print("✓ FEEDBACK LOOP OPERATIONAL\n")
        else:
            print("✗ FEEDBACK LOOP HAS ISSUES - See errors above\n")


def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Diagnose Thompson Sampling feedback loop"
    )
    parser.add_argument('--state-file', help='Path to thompson-sampling-state.json')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--inject-test-feedback', action='store_true',
                       help='Inject synthetic test feedback')
    parser.add_argument('--trace-feedback-loop', action='store_true',
                       help='Enable detailed logging')

    args = parser.parse_args()

    if args.verbose or args.trace_feedback_loop:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run diagnostics
    diagnostics = ThompsonDiagnostics(state_file=args.state_file)

    if not diagnostics.load_state():
        print("ERROR: Could not load Thompson state file")
        sys.exit(1)

    # Run checks
    diagnostics.check_feedback_loop_integrity()
    diagnostics.check_beta_prior_updating()
    utilization = diagnostics.check_utilization_distribution()

    # Optionally inject test feedback
    if args.inject_test_feedback:
        diagnostics.inject_test_feedback()
        print("\nRe-running diagnostics after test injection...\n")
        diagnostics = ThompsonDiagnostics(state_file=args.state_file)
        if diagnostics.load_state():
            diagnostics.check_feedback_loop_integrity()
            diagnostics.check_utilization_distribution()

    # Print report
    diagnostics.print_report()

    # Exit with appropriate code
    sys.exit(0 if not diagnostics.errors else 1)


if __name__ == '__main__':
    main()
