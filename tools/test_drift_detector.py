#!/usr/bin/env python3
"""
Drift Detector Validation Test

Tests all drift detection algorithms with synthetic data
to ensure proper functionality before production deployment.

Usage:
    python3 tools/test_drift_detector.py
"""

import sys
import numpy as np
from pathlib import Path

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import drift detector classes
from drift_detector import (
    CUSUMDetector,
    PageHinkleyDetector,
    ADWINDetector,
    DriftDetectionSystem
)


def test_cusum_detector():
    """Test CUSUM detector with synthetic drift"""
    print("\n=== Testing CUSUM Detector ===")

    detector = CUSUMDetector(threshold=3.0, drift_threshold=0.0)

    # Simulate quality scores with drift
    # Baseline: 0.85 for 20 samples
    # Drift: 0.70 for 20 samples (degradation)
    baseline = [0.85 + np.random.normal(0, 0.02) for _ in range(20)]
    degraded = [0.70 + np.random.normal(0, 0.02) for _ in range(20)]

    drift_detected = False
    drift_index = None

    for i, value in enumerate(baseline + degraded):
        detected, magnitude = detector.update(value)
        if detected and not drift_detected:
            drift_detected = True
            drift_index = i
            print(f"  ✓ Drift detected at sample {i+1}")
            print(f"    Magnitude: {magnitude:.3f}")
            break

    if drift_detected and drift_index >= 15:
        print("  ✓ CUSUM detector working correctly")
        return True
    else:
        print("  ✗ CUSUM detector failed to detect drift")
        return False


def test_page_hinkley_detector():
    """Test Page-Hinkley detector with abrupt change"""
    print("\n=== Testing Page-Hinkley Detector ===")

    detector = PageHinkleyDetector(threshold=5.0, delta=0.005)

    # Simulate abrupt quality drop
    stable = [0.85 + np.random.normal(0, 0.01) for _ in range(30)]
    sudden_drop = [0.65 + np.random.normal(0, 0.01) for _ in range(10)]

    drift_detected = False
    drift_index = None

    for i, value in enumerate(stable + sudden_drop):
        detected, magnitude = detector.update(value)
        if detected and not drift_detected:
            drift_detected = True
            drift_index = i
            print(f"  ✓ Drift detected at sample {i+1}")
            print(f"    Magnitude: {magnitude:.3f}")
            break

    if drift_detected and 25 <= drift_index <= 35:
        print("  ✓ Page-Hinkley detector working correctly")
        return True
    else:
        print("  ✗ Page-Hinkley detector failed to detect abrupt change")
        return False


def test_adwin_detector():
    """Test ADWIN detector with concept drift"""
    print("\n=== Testing ADWIN Detector ===")

    detector = ADWINDetector(delta=0.002)

    # Simulate concept drift (distribution change)
    dist1 = np.random.normal(0.80, 0.05, 50)
    dist2 = np.random.normal(0.65, 0.05, 50)

    drift_detected = False
    drift_index = None

    for i, value in enumerate(np.concatenate([dist1, dist2])):
        detected, magnitude = detector.update(value)
        if detected and not drift_detected:
            drift_detected = True
            drift_index = i
            print(f"  ✓ Drift detected at sample {i+1}")
            print(f"    Magnitude: {magnitude:.3f}")
            break

    if drift_detected and 30 <= drift_index <= 70:
        print("  ✓ ADWIN detector working correctly")
        return True
    else:
        print("  ✗ ADWIN detector failed to detect concept drift")
        return False


def test_integrated_system():
    """Test integrated drift detection system with mock data"""
    print("\n=== Testing Integrated System ===")

    # Create mock time-series data
    timeseries = []

    # Baseline period (30 samples)
    for i in range(30):
        timeseries.append({
            'timestamp': f'2026-07-{i+1:02d} 12:00:00',
            'quality': 0.85 + np.random.normal(0, 0.02),
            'confidence': 0.80 + np.random.normal(0, 0.03),
            'cost': 0.05 + np.random.normal(0, 0.005),
            'samples': 10
        })

    # Degraded period (20 samples)
    for i in range(20):
        timeseries.append({
            'timestamp': f'2026-07-{i+30:02d} 12:00:00',
            'quality': 0.70 + np.random.normal(0, 0.02),  # Quality drop
            'confidence': 0.75 + np.random.normal(0, 0.03),
            'cost': 0.06 + np.random.normal(0, 0.005),  # Cost increase
            'samples': 10
        })

    # NOTE: Cannot test full system without database connection
    # This validates data structure only

    print(f"  ✓ Generated {len(timeseries)} time buckets")
    print(f"    Baseline quality: {np.mean([t['quality'] for t in timeseries[:30]]):.3f}")
    print(f"    Degraded quality: {np.mean([t['quality'] for t in timeseries[30:]]):.3f}")
    print(f"    Expected drift: YES")

    # Manually run drift detection logic (without database)
    system = DriftDetectionSystem()
    result = system.detect_drift(timeseries, 'test-model')

    if result.get('drift_detected'):
        print(f"  ✓ Drift detected: {result.get('drift_type')}")
        print(f"    Severity: {result.get('severity')}")
        print(f"    Affected metrics: {result.get('affected_metrics')}")
        return True
    else:
        print(f"  ✗ Drift not detected (reason: {result.get('reason', 'unknown')})")
        return False


def main():
    """Run all validation tests"""
    print("=" * 60)
    print("DRIFT DETECTOR VALIDATION TESTS")
    print("=" * 60)

    results = {
        'CUSUM': test_cusum_detector(),
        'Page-Hinkley': test_page_hinkley_detector(),
        'ADWIN': test_adwin_detector(),
        'Integrated System': test_integrated_system()
    }

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    passed = sum(results.values())
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All drift detection algorithms validated successfully")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed - drift detector may need tuning")
        return 1


if __name__ == '__main__':
    sys.exit(main())
