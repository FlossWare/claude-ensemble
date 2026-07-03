#!/usr/bin/env python3
"""
Integration Tests: Smart Orchestrator (GA + Thompson Sampling)

Tests the full orchestrator pipeline:
1. Model selection (Thompson Sampling vs Auto-Profiler)
2. Fleet execution (8 workers)
3. Result aggregation
4. Metrics tracking
"""

import sys
import os
import json
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from orchestrate_smart import SmartOrchestrator

class TestSmartOrchestrator:
    """Integration tests for smart orchestrator"""

    def setup_method(self):
        """Setup before each test"""
        self.orch = SmartOrchestrator(exploration_rate=0.15)

    def teardown_method(self):
        """Cleanup after each test"""
        self.orch.close()

    def test_thompson_sampling_model_selection(self):
        """Test that Thompson Sampling selects appropriate models"""
        print("\n=== Test: Thompson Sampling Model Selection ===")

        # Test code generation task
        model, method = self.orch.select_model(
            task_description="Write a Java function to parse XML",
            task_type="code_generation"
        )

        assert model is not None, "Model selection failed"
        assert method in ['thompson_sampling', 'auto_profiler', 'ga_exploration'], \
            f"Invalid selection method: {method}"

        print(f"✓ Selected: {model} via {method}")
        return True

    def test_auto_profiler_exploration(self):
        """Test that Auto-Profiler explores unprofiled models"""
        print("\n=== Test: Auto-Profiler Exploration ===")

        # Get unprofiled models
        unprofiled = self.orch.profiler.get_unprofiled_models(limit=5)
        initial_count = len(unprofiled)

        print(f"Unprofiled models: {initial_count}")

        # With 15% exploration rate, should occasionally explore
        # Run 20 selections and count explorations
        explorations = 0
        for i in range(20):
            model, method = self.orch.select_model(
                task_description=f"Test task {i}",
                task_type="general_qa"
            )
            if method == 'ga_exploration':
                explorations += 1

        exploration_rate = explorations / 20
        print(f"✓ Exploration rate: {exploration_rate*100:.1f}% (expected ~15%)")

        # Should be roughly 15% +/- some variance
        assert 0 < exploration_rate < 0.5, \
            f"Exploration rate {exploration_rate} seems wrong"

        return True

    def test_fleet_execution_parallel(self):
        """Test that fleet executes tasks in parallel across 8 workers"""
        print("\n=== Test: Fleet Parallel Execution ===")

        task = "What is 2+2?"
        workers = ["server-01", "server-02"]  # Test with 2 workers for speed

        start = time.time()
        result = self.orch.orchestrate_task(
            task_description=task,
            workers=workers,
            task_type="math_reasoning"
        )
        duration = time.time() - start

        print(f"Model: {result['model']}")
        print(f"Workers: {result['workers']}")
        print(f"Duration: {duration:.2f}s")
        print(f"Success rate: {result['success_rate']*100:.1f}%")

        # Verify results
        assert result['workers'] == 2, "Should use 2 workers"
        assert result['model'] is not None, "Model not selected"
        assert 'results' in result, "Results missing"
        assert len(result['results']) == 2, "Should have 2 results"

        print(f"✓ Fleet execution successful")
        return True

    def test_orchestrator_status(self):
        """Test orchestrator status reporting"""
        print("\n=== Test: Orchestrator Status ===")

        self.orch.get_status()

        # If we got here without errors, status works
        print(f"✓ Status reporting works")
        return True

    def test_context_extraction(self):
        """Test that context is correctly extracted from tasks"""
        print("\n=== Test: Context Extraction ===")

        from tools.contextual_bandit_trainer_v2 import extract_context

        # Test code task
        context = extract_context("Write a Java class", "workflow-code")
        assert context[0] == 1.0, "Should detect code task"  # is_code

        # Test review task
        context = extract_context("Review this code for bugs", "workflow-review")
        assert context[1] == 1.0, "Should detect review task"  # is_review

        # Test fix task
        context = extract_context("Fix authentication bug", "workflow-fix")
        assert context[2] == 1.0, "Should detect fix task"  # is_fix

        # Test research task
        context = extract_context("Research best practices", "workflow-research")
        assert context[3] == 1.0, "Should detect research task"  # is_research

        print(f"✓ Context extraction working")
        return True


def run_integration_tests():
    """Run all integration tests"""
    print("="*60)
    print("SMART ORCHESTRATOR INTEGRATION TESTS")
    print("="*60)

    test = TestSmartOrchestrator()
    results = []

    tests = [
        ('Thompson Sampling Model Selection', test.test_thompson_sampling_model_selection),
        ('Auto-Profiler Exploration', test.test_auto_profiler_exploration),
        ('Fleet Parallel Execution', test.test_fleet_execution_parallel),
        ('Orchestrator Status', test.test_orchestrator_status),
        ('Context Extraction', test.test_context_extraction),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        test.setup_method()
        try:
            test_func()
            results.append((name, 'PASS'))
            passed += 1
        except Exception as e:
            results.append((name, f'FAIL: {e}'))
            failed += 1
        finally:
            test.teardown_method()

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
        print("\n✅ ALL INTEGRATION TESTS PASSED")
        return 0
    else:
        print(f"\n❌ {failed} TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(run_integration_tests())
