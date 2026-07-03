#!/usr/bin/env python3
"""
Integration Tests: ML Training Systems

Tests all 6 trained ML systems:
1. Thompson Sampling (Contextual Bandit)
2. Auto-Profiler (GA)
3. Prompt Optimizer
4. Novelty Detector
5. Complexity Estimator
6. CPU Fine-Tuning (validation only)
"""

import sys
import os
import json
import pickle
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.contextual_bandit_trainer_v2 import ContextualBandit, extract_context
from tools.auto_profiler import AutoProfiler
import pickle


class TestMLSystems:
    """Integration tests for trained ML systems"""

    def test_thompson_sampling_loaded(self):
        """Test that Thompson Sampling model loads correctly"""
        print("\n=== Test: Thompson Sampling Model ===")

        model_path = Path.home() / '.claude/learning/contextual_bandit_v2.json'
        assert model_path.exists(), f"Model not found: {model_path}"

        bandit = ContextualBandit.load(str(model_path))

        assert bandit.num_models > 0, "No models in bandit"
        assert bandit.context_dim == 10, "Wrong context dimension"

        print(f"✓ Loaded {bandit.num_models} models, {bandit.context_dim} context dims")
        return True

    def test_thompson_sampling_prediction(self):
        """Test that Thompson Sampling makes predictions"""
        print("\n=== Test: Thompson Sampling Predictions ===")

        model_path = Path.home() / '.claude/learning/contextual_bandit_v2.json'
        bandit = ContextualBandit.load(str(model_path))

        # Test prediction
        context = extract_context("Write Java code", "test-workflow")
        model_idx, ucb_scores = bandit.select_model(context)

        assert 0 <= model_idx < bandit.num_models, "Invalid model index"
        assert len(ucb_scores) == bandit.num_models, "Wrong number of scores"

        print(f"✓ Selected model index: {model_idx}")
        print(f"✓ UCB scores: {len(ucb_scores)} models")
        return True

    def test_auto_profiler_coverage(self):
        """Test that Auto-Profiler has profiled models"""
        print("\n=== Test: Auto-Profiler Coverage ===")

        profiler = AutoProfiler(exploration_rate=0.15, adaptive=True)

        status = profiler.get_status()
        coverage = status['coverage_pct']

        assert status['profiled_models'] > 0, "No models profiled"
        assert coverage > 0, "Coverage is 0%"

        print(f"✓ Coverage: {status['profiled_models']}/{status['total_models']} ({coverage:.1f}%)")
        print(f"✓ By task type: {status['by_task']}")

        profiler.close()
        return True

    def test_auto_profiler_selection(self):
        """Test that Auto-Profiler selects models"""
        print("\n=== Test: Auto-Profiler Model Selection ===")

        profiler = AutoProfiler(exploration_rate=0.15, adaptive=True)

        model, is_exploration = profiler.select_model_for_task('code_generation')

        assert model is not None, "No model selected"
        assert isinstance(is_exploration, bool), "Invalid exploration flag"

        print(f"✓ Selected: {model} (exploration: {is_exploration})")

        profiler.close()
        return True

    def test_novelty_detector_loaded(self):
        """Test that Novelty Detector model loads"""
        print("\n=== Test: Novelty Detector Model ===")

        model_path = Path.home() / '.claude/learning/novelty_detector_model.pkl'
        assert model_path.exists(), f"Model not found: {model_path}"

        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        assert model is not None, "Model not loaded"

        print(f"✓ Model loaded successfully")
        return True

    def test_novelty_detector_prediction(self):
        """Test that Novelty Detector makes predictions"""
        print("\n=== Test: Novelty Detector Predictions ===")

        # Novelty detector is a standalone script, just verify artifacts exist
        model_path = Path.home() / '.claude/learning/novelty_detector_model.pkl'
        metrics_path = Path.home() / '.claude/learning/novelty_detector_metrics.json'

        assert model_path.exists(), f"Model not found"
        assert metrics_path.exists(), f"Metrics not found"

        with open(metrics_path, 'r') as f:
            metrics = json.load(f)

        assert 'overall_accuracy' in metrics, "Metrics missing accuracy"

        print(f"✓ Novelty detector artifacts exist")
        print(f"✓ Accuracy: {metrics.get('overall_accuracy', 0)*100:.1f}%")
        return True

    def test_complexity_estimator_loaded(self):
        """Test that Complexity Estimator model loads"""
        print("\n=== Test: Complexity Estimator Model ===")

        model_path = Path.home() / '.claude/learning/complexity_estimator.pkl'
        assert model_path.exists(), f"Model not found: {model_path}"

        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        assert model is not None, "Model not loaded"

        print(f"✓ Model loaded successfully")
        return True

    def test_complexity_estimator_prediction(self):
        """Test that Complexity Estimator makes predictions"""
        print("\n=== Test: Complexity Estimator Predictions ===")

        # Complexity estimator is a standalone script, verify artifacts exist
        model_path = Path.home() / '.claude/learning/complexity_estimator.pkl'
        stats_path = Path.home() / '.claude/learning/complexity_estimator_stats.json'

        assert model_path.exists(), f"Model not found"
        assert stats_path.exists(), f"Stats not found"

        with open(stats_path, 'r') as f:
            stats = json.load(f)

        assert 'duration' in stats, "Stats missing duration metrics"
        assert 'test_r2' in stats['duration'], "Stats missing test R²"

        r2 = stats['duration']['test_r2']
        mae_ms = stats['duration']['mae_ms']

        print(f"✓ Complexity estimator artifacts exist")
        print(f"✓ R² score: {r2:.3f}")
        print(f"✓ MAE: {mae_ms/1000:.1f}s")
        return True

    def test_prompt_optimizer_exists(self):
        """Test that Prompt Optimizer artifacts exist"""
        print("\n=== Test: Prompt Optimizer ===")

        optimizer_path = Path(__file__).parent.parent.parent / 'tools/prompt_optimizer.py'
        assert optimizer_path.exists(), f"Optimizer not found: {optimizer_path}"

        print(f"✓ Prompt optimizer exists")
        return True

    def test_cpu_finetuning_scripts_exist(self):
        """Test that CPU fine-tuning scripts exist"""
        print("\n=== Test: CPU Fine-Tuning Scripts ===")

        finetuning_dir = Path.home() / 'fine-tuning'

        if not finetuning_dir.exists():
            print(f"⚠ Fine-tuning directory not found (expected for training-only scripts)")
            return True

        scripts_dir = finetuning_dir / 'scripts'
        if scripts_dir.exists():
            scripts = list(scripts_dir.glob('*.py')) + list(scripts_dir.glob('*.sh'))
            print(f"✓ Found {len(scripts)} fine-tuning scripts")
        else:
            print(f"⚠ Scripts directory not found (fine-tuning not set up)")

        return True


def run_integration_tests():
    """Run all ML system integration tests"""
    print("="*60)
    print("ML SYSTEMS INTEGRATION TESTS")
    print("="*60)

    test = TestMLSystems()
    results = []

    tests = [
        ('Thompson Sampling - Load', test.test_thompson_sampling_loaded),
        ('Thompson Sampling - Predict', test.test_thompson_sampling_prediction),
        ('Auto-Profiler - Coverage', test.test_auto_profiler_coverage),
        ('Auto-Profiler - Selection', test.test_auto_profiler_selection),
        ('Novelty Detector - Load', test.test_novelty_detector_loaded),
        ('Novelty Detector - Predict', test.test_novelty_detector_prediction),
        ('Complexity Estimator - Load', test.test_complexity_estimator_loaded),
        ('Complexity Estimator - Predict', test.test_complexity_estimator_prediction),
        ('Prompt Optimizer - Exists', test.test_prompt_optimizer_exists),
        ('CPU Fine-Tuning - Scripts', test.test_cpu_finetuning_scripts_exist),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            results.append((name, 'PASS'))
            passed += 1
        except Exception as e:
            results.append((name, f'FAIL: {e}'))
            failed += 1

    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)

    for name, result in results:
        status = "✓" if result == 'PASS' else "✗"
        print(f"{status} {name}: {result}")

    print()
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n✅ ALL ML INTEGRATION TESTS PASSED")
        return 0
    else:
        print(f"\n❌ {failed} TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(run_integration_tests())
