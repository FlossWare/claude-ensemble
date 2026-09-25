"""
Unit tests for metrics system (Phase 1 Framework)

Tests the core functionality of each worker:
- WORKER 1: Classifier workflow type detection
- WORKER 2: Logger metrics capture
- WORKER 3: Analyzer pattern detection
- WORKER 4: Tuner config generation

Run with: python3 test_metrics.py
"""

import tempfile
from pathlib import Path

from classifier import WorkflowClassifier, WorkflowType
from logger import PerformanceLogger
from analyzer import PerformanceAnalyzer
from tuner import ConfigTuner


def test_classifier():
    """Test WORKER 1: Workflow classification."""
    print("\n[TEST 1] WORKER 1: Workflow Classifier")
    print("-" * 60)

    classifier = WorkflowClassifier()

    test_cases = [
        ("Code review for PR #123", WorkflowType.CODE_REVIEW.value),
        ("Deploy to production", WorkflowType.DEPLOYMENT.value),
        ("Security vulnerability analysis", WorkflowType.SECURITY_REVIEW.value),
        ("Bi-weekly release notes", WorkflowType.RELEASE_NOTES.value),
        ("Debug database connection issue", WorkflowType.BUG_DIAGNOSIS.value),
    ]

    passed = 0
    for task, expected_type in test_cases:
        classification = classifier.classify(task)
        match = classification.workflow_type == expected_type
        passed += match
        status = "✓" if match else "✗"
        print(f"{status} {task:40} → {classification.workflow_type:20} "
              f"(confidence: {classification.confidence:.0%})")

    print(f"\nResult: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_logger():
    """Test WORKER 2: Performance logging."""
    print("\n[TEST 2] WORKER 2: Performance Logger")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test_performance.jsonl"
        logger = PerformanceLogger(log_file=log_file)

        test_data = [
            {
                "workflow_type": "code_review",
                "model": "opus",
                "original_tokens": 12500,
                "compressed_tokens": 7300,
                "semantic_similarity": 0.94,
                "output_tokens": 1200,
                "cost_usd": 0.067,
            },
            {
                "workflow_type": "deployment",
                "model": "haiku",
                "original_tokens": 8000,
                "compressed_tokens": 6400,
                "cache_hit": True,
                "semantic_similarity": 0.98,
            },
            {
                "workflow_type": "release_notes",
                "model": "sonnet",
                "original_tokens": 15000,
                "compressed_tokens": 7800,
                "test_pass_rate": 1.0,
                "semantic_similarity": 0.92,
            },
        ]

        # Log calls
        entries = []
        for i, data in enumerate(test_data):
            entry = logger.log_call(**data)
            entries.append(entry)
            print(f"✓ Logged {data['workflow_type']:20} | "
                  f"{data['model']:8} | "
                  f"Compression: {entry.compression.reduction_percent:5.1f}%")

        # Verify logs were saved
        logs = logger.read_logs()
        logs_ok = len(logs) == len(test_data)
        print(f"\n✓ All {len(logs)} entries logged successfully")

        # Get stats
        stats = logger.get_stats()
        print(f"✓ Total tokens original: {stats['total_tokens_original']}")
        print(f"✓ Total tokens compressed: {stats['total_tokens_compressed']}")

        stats_ok = (
            stats["total_calls"] == len(test_data) and
            stats["total_tokens_original"] > 0
        )
        print(f"\nResult: {'PASS' if logs_ok and stats_ok else 'FAIL'}")
        return logs_ok and stats_ok


def test_analyzer():
    """Test WORKER 3: Performance analysis."""
    print("\n[TEST 3] WORKER 3: Correlation Analyzer")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test_performance.jsonl"

        # Generate sample data
        logger = PerformanceLogger(log_file=log_file)

        workflows = [
            ("code_review", 38.2, 0.94),
            ("deployment", 45.0, 0.98),
            ("release_notes", 48.1, 0.92),
            ("security_review", 22.3, 0.85),
        ]

        for workflow, reduction_pct, similarity in workflows:
            for i in range(10):  # 10 calls per workflow
                original = 12000 + i * 100
                compressed = int(original * (1 - reduction_pct / 100))
                logger.log_call(
                    workflow_type=workflow,
                    model="opus",
                    original_tokens=original,
                    compressed_tokens=compressed,
                    semantic_similarity=similarity,
                )

        # Analyze
        analyzer = PerformanceAnalyzer(log_file=log_file)
        report = analyzer.analyze_all()

        if report:
            print(f"✓ Analyzed {report.workflows_analyzed} workflows")
            print(f"✓ Found compression patterns:")

            for workflow, stats in report.compression_analysis.items():
                rec = stats.get("recommendation", "unknown")
                conf = stats.get("confidence", 0)
                print(f"  {workflow:20} → {rec:25} (confidence: {conf:.0%})")

            result = report.workflows_analyzed > 0
            print(f"\nResult: {'PASS' if result else 'FAIL'}")
            return result

    return False


def test_tuner():
    """Test WORKER 4: Configuration tuning."""
    print("\n[TEST 4] WORKER 4: Auto-Tuner")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        tuner = ConfigTuner(config_dir=Path(tmpdir))

        # Sample analysis report
        sample_analysis = {
            "compression_analysis": {
                "code_review": {
                    "avg_reduction_percent": 38.2,
                    "quality_impact": 0.08,
                    "recommendation": "light_compression",
                    "confidence": 0.91,
                },
                "release_notes": {
                    "avg_reduction_percent": 48.1,
                    "quality_impact": 0.04,
                    "recommendation": "aggressive_compression",
                    "confidence": 0.87,
                },
                "security_review": {
                    "avg_reduction_percent": 22.3,
                    "quality_impact": 0.15,
                    "recommendation": "none",
                    "confidence": 0.94,
                },
            },
            "cache_analysis": {
                "deployment": {
                    "cache_hit_rate": 0.72,
                    "avg_tokens_saved_per_hit": 8400,
                    "recommendation": "aggressive_caching",
                    "confidence": 0.89,
                },
            },
            "latency_impact": {
                "compression_avg_ms": 42,
            },
        }

        # Generate config
        recommended = tuner.generate_config(sample_analysis)
        print(f"✓ Generated recommended config")

        # Save config
        config_path = tuner.save_config(recommended)
        print(f"✓ Saved to {config_path}")

        # Load and verify
        loaded = tuner.load_config("recommended_config.yaml")
        has_compression = "compression" in loaded
        has_cache = "cache" in loaded

        print(f"✓ Config has compression rules: {has_compression}")
        print(f"✓ Config has cache rules: {has_cache}")

        # Generate A/B test plan
        changes = []
        plan = tuner.generate_ab_test_plan(recommended, changes)
        print(f"✓ Generated A/B test plan: {plan['test_id']}")

        result = has_compression and has_cache and "test_id" in plan
        print(f"\nResult: {'PASS' if result else 'FAIL'}")
        return result


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("METRICS SYSTEM PHASE 1 - TEST SUITE")
    print("=" * 70)

    results = {
        "Classifier (Worker 1)": test_classifier(),
        "Logger (Worker 2)": test_logger(),
        "Analyzer (Worker 3)": test_analyzer(),
        "Tuner (Worker 4)": test_tuner(),
    }

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} test groups passed")

    if passed == total:
        print("\n✓ ALL TESTS PASSED - Phase 1 Framework Ready")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
