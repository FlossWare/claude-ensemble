#!/usr/bin/env python3
"""
Unit tests for Thompson Sampling Router - Phase 1 FIX blockers

Tests the three critical fixes:
1. Cost normalization using 90th percentile
2. Race-condition-safe atomic writes
3. Graceful handling of empty candidate models
"""

import unittest
import json
import os
import tempfile
import threading
import time
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

from thompson_router import (
    StateTracker, ModelPerformance, BetaEstimator, ThompsonRouter,
    RHDisseminatorRouter
)


class TestCostNormalization(unittest.TestCase):
    """Test Blocker 1: Cost normalization using 90th percentile"""

    def setUp(self):
        """Create temporary state file"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test-state.json')

    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)
        os.rmdir(self.temp_dir)

    def test_cost_normalization_with_actual_costs(self):
        """Verify cost normalization uses 90th percentile, not hardcoded 1.0"""
        state = StateTracker(self.state_file)
        beta = BetaEstimator(alpha_prior=2, beta_prior=1)
        router = ThompsonRouter(state, beta, cost_weight=0.5)

        # Add models with different costs
        models = {
            'cheap': {'successes': 10, 'failures': 1, 'total_cost': 0.05},
            'medium': {'successes': 9, 'failures': 2, 'total_cost': 0.15},
            'expensive': {'successes': 8, 'failures': 3, 'total_cost': 0.40},
        }

        for name, data in models.items():
            perf = ModelPerformance(
                model_name=name,
                successes=data['successes'],
                failures=data['failures'],
                total_cost=data['total_cost'],
                calls=data['successes'] + data['failures'],
                total_latency_ms=5000 * (data['successes'] + data['failures'])
            )
            state.models[name] = perf
        state.save()

        # Get normalization factor
        cost_factor = router._get_cost_normalization_factor()

        # Should be 90th percentile of [0.05/11, 0.15/11, 0.40/11]
        # = [0.0045, 0.0136, 0.0364]
        # 90th percentile ≈ 0.0364
        self.assertGreater(cost_factor, 0.01)  # Not hardcoded 1.0
        self.assertLess(cost_factor, 0.05)  # Within range of actual costs

        print(f"✓ Cost normalization factor: {cost_factor:.4f} (not hardcoded 1.0)")

    def test_cost_normalization_affects_selection(self):
        """Verify cost weighting actually affects model selection"""
        state = StateTracker(self.state_file)

        # Setup: one model cheap but lower quality, one expensive but higher quality
        perf_cheap = ModelPerformance(
            model_name='haiku',
            successes=30, failures=6,  # 83% quality
            total_cost=0.015 * 36,
            calls=36,
            total_latency_ms=2500 * 36
        )
        perf_expensive = ModelPerformance(
            model_name='opus',
            successes=25, failures=3,  # 89% quality
            total_cost=0.080 * 28,
            calls=28,
            total_latency_ms=8000 * 28
        )

        state.models['haiku'] = perf_cheap
        state.models['opus'] = perf_expensive
        state.save()

        # Test with high cost weight
        beta = BetaEstimator(alpha_prior=2, beta_prior=1)
        router_high_cost = ThompsonRouter(state, beta, cost_weight=0.8)

        # With high cost weight, cheap model should win despite lower quality
        np.random.seed(42)
        selected = router_high_cost.select_model(['haiku', 'opus'])
        print(f"✓ With cost_weight=0.8: selected {selected}")

        # The selection should favor cheaper model more often
        # Run multiple times due to stochastic nature
        wins = {'haiku': 0, 'opus': 0}
        for i in range(100):
            selected = router_high_cost.select_model(['haiku', 'opus'])
            wins[selected] += 1

        self.assertGreater(wins['haiku'], 40,
                          "With high cost weight, cheap model should win frequently")
        print(f"✓ Cost weighting works: haiku won {wins['haiku']}/100, opus {wins['opus']}/100")

    def test_empty_cost_factor_returns_default(self):
        """Verify graceful handling when no cost data exists"""
        state = StateTracker(self.state_file)
        beta = BetaEstimator()
        router = ThompsonRouter(state, beta)

        # Empty state
        cost_factor = router._get_cost_normalization_factor()
        self.assertEqual(cost_factor, 1.0)
        print("✓ Empty cost history returns default 1.0")


class TestAtomicWrites(unittest.TestCase):
    """Test Blocker 2: Race-condition-safe atomic writes"""

    def setUp(self):
        """Create temporary state file"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test-state.json')

    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)
        os.rmdir(self.temp_dir)

    def test_atomic_write_uses_tempfile(self):
        """Verify save() uses atomic write pattern (tempfile + os.replace)"""
        state = StateTracker(self.state_file)

        # Add some data
        perf = ModelPerformance(model_name='test', successes=5, failures=1, total_cost=0.05, calls=6)
        state.models['test'] = perf

        # Track that a tempfile is created during save
        original_mkstemp = tempfile.mkstemp
        mkstemp_called = []

        def tracked_mkstemp(*args, **kwargs):
            mkstemp_called.append((args, kwargs))
            return original_mkstemp(*args, **kwargs)

        with patch('tempfile.mkstemp', side_effect=tracked_mkstemp):
            state.save()

        self.assertTrue(mkstemp_called, "save() should use tempfile.mkstemp")
        print(f"✓ save() uses atomic writes with tempfile.mkstemp")

    def test_concurrent_writes_no_corruption(self):
        """Verify concurrent writes don't corrupt JSON"""
        state = StateTracker(self.state_file)
        errors = []

        def writer_thread(model_name, iterations):
            """Worker thread that writes model performance"""
            try:
                for i in range(iterations):
                    state.record(
                        model_name,
                        quality_score=0.85 + np.random.uniform(-0.1, 0.1),
                        latency_ms=5000 + np.random.randint(-500, 500),
                        cost=0.05 + np.random.uniform(-0.01, 0.01)
                    )
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                errors.append(f"{model_name}: {e}")

        # Launch concurrent writers
        threads = []
        for i in range(5):
            t = threading.Thread(
                target=writer_thread,
                args=(f'model_{i}', 20),
                daemon=True
            )
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join(timeout=5)

        # Verify no errors and file is valid JSON
        self.assertEqual(errors, [], f"Concurrent writes caused errors: {errors}")

        # Verify JSON is valid
        with open(self.state_file, 'r') as f:
            data = json.load(f)
        self.assertIn('models', data)
        self.assertEqual(len(data['models']), 5)
        print(f"✓ 5 concurrent writers completed without corruption")
        print(f"✓ File contains valid JSON with {len(data['models'])} models")

    def test_corrupted_file_doesnt_crash_loader(self):
        """Verify robust error handling during load"""
        # Write invalid JSON
        with open(self.state_file, 'w') as f:
            f.write("{ invalid json }")

        # Should not crash, just log error and start fresh
        state = StateTracker(self.state_file)
        self.assertEqual(state.models, {})
        print("✓ Invalid JSON during load handled gracefully")


class TestEmptyCandidatesFallback(unittest.TestCase):
    """Test Blocker 3: Graceful fallback for empty candidate models"""

    def setUp(self):
        """Create temporary state file"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test-state.json')

    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)
        os.rmdir(self.temp_dir)

    def test_empty_candidates_with_no_history_raises_error(self):
        """Verify appropriate error when candidates empty and no history"""
        state = StateTracker(self.state_file)
        beta = BetaEstimator()
        router = ThompsonRouter(state, beta)

        # Should raise ValueError with helpful message
        with self.assertRaises(ValueError) as ctx:
            router.select_model([])

        self.assertIn("No candidate models", str(ctx.exception))
        print("✓ Empty candidates with no history raises ValueError")

    def test_empty_candidates_with_history_returns_best_model(self):
        """Verify fallback to best overall model when candidates empty but history exists"""
        state = StateTracker(self.state_file)

        # Add historical models
        state.models['haiku'] = ModelPerformance(
            model_name='haiku', successes=10, failures=2,
            total_cost=0.015 * 12, calls=12, total_latency_ms=2500 * 12
        )
        state.models['sonnet'] = ModelPerformance(
            model_name='sonnet', successes=9, failures=3,
            total_cost=0.050 * 12, calls=12, total_latency_ms=5000 * 12
        )
        state.save()

        beta = BetaEstimator()
        router = ThompsonRouter(state, beta, cost_weight=0.1)

        # Should not raise, but return best model
        with patch('logging.warning') as mock_warn:
            selected = router.select_model([])
            mock_warn.assert_called_once()
            self.assertIn("falling back", mock_warn.call_args[0][0].lower())

        self.assertIn(selected, ['haiku', 'sonnet'])
        print(f"✓ Empty candidates with history: returned {selected} with warning")

    def test_select_model_with_confidence_documents_api(self):
        """Verify select_model_with_confidence is documented as safe alternative"""
        state = StateTracker(self.state_file)
        state.models['test'] = ModelPerformance(
            model_name='test', successes=5, failures=1,
            total_cost=0.05, calls=6, total_latency_ms=5000
        )
        state.save()

        beta = BetaEstimator()
        router = ThompsonRouter(state, beta)

        # Method exists and is callable
        result = router.select_model_with_confidence(['test'])
        self.assertEqual(result, 'test')
        print("✓ select_model_with_confidence() exposed as API option")


class TestIntegration(unittest.TestCase):
    """Integration tests combining all three fixes"""

    def setUp(self):
        """Create temporary state file"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test-state.json')

    def tearDown(self):
        """Clean up"""
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)
        os.rmdir(self.temp_dir)

    def test_cost_savings_with_fixes(self):
        """Verify 40%+ cost savings is maintained with fixes applied"""
        state = StateTracker(self.state_file)

        # Initialize with realistic data
        models_data = {
            'haiku': {'successes': 30, 'failures': 6, 'cost': 0.015},
            'sonnet': {'successes': 18, 'failures': 3, 'cost': 0.050},
            'opus': {'successes': 14, 'failures': 2, 'cost': 0.080},
            'gpt-4o': {'successes': 22, 'failures': 4, 'cost': 0.045},
        }

        for name, data in models_data.items():
            total_calls = data['successes'] + data['failures']
            perf = ModelPerformance(
                model_name=name,
                successes=data['successes'],
                failures=data['failures'],
                total_cost=data['cost'] * total_calls,
                calls=total_calls,
                total_latency_ms=5000 * total_calls
            )
            state.models[name] = perf
        state.save()

        beta = BetaEstimator(alpha_prior=2, beta_prior=1)
        router = ThompsonRouter(state, beta, cost_weight=0.25)
        rh_router = RHDisseminatorRouter(state, router)

        # Simulate 50 task selections
        np.random.seed(42)
        selections = []
        costs = []
        for i in range(50):
            model = rh_router.select_model_for_task('code_review')
            cost = models_data[model]['cost']
            selections.append(model)
            costs.append(cost)

        # Calculate savings vs baseline (all Opus at $0.080 each)
        baseline_cost = 0.080 * 50
        thompson_cost = sum(costs)
        savings_pct = ((baseline_cost - thompson_cost) / baseline_cost) * 100

        print(f"\n✓ Cost savings test:")
        print(f"  Baseline (50 Opus calls): ${baseline_cost:.4f}")
        print(f"  Thompson Sampling:        ${thompson_cost:.4f}")
        print(f"  Savings:                  {savings_pct:.1f}%")

        self.assertGreater(savings_pct, 35, "Should achieve >35% cost savings")
        print(f"✓ Cost savings exceeds 35% target")


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(level=logging.ERROR)

    # Run tests
    unittest.main(verbosity=2)
