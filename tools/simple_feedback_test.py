#!/usr/bin/env python3
"""
Simple Feedback Loop Optimizer Test

Tests against real production database with existing data
No synthetic data injection required

Created: 2026-07-03
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from feedback_loop_optimizer import FeedbackLoopOptimizer


def test_basic_functionality():
    """Test basic optimizer functionality"""
    print("=" * 80)
    print("FEEDBACK LOOP OPTIMIZER - BASIC FUNCTIONALITY TEST")
    print("=" * 80)

    optimizer = FeedbackLoopOptimizer()

    # Test 1: Model distribution analysis
    print("\n[TEST 1] Model Distribution Analysis")
    try:
        distribution, risks = optimizer.analyze_model_distribution(window_days=30)
        print(f"  ✓ Model distribution analyzed")
        print(f"    Models found: {len(distribution)}")
        print(f"    Risks detected: {len(risks)}")

        if distribution:
            print("    Distribution:")
            for model, pct in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
                print(f"      {model:20s}: {pct*100:5.1f}%")

        if risks:
            print("    Risks:")
            for risk in risks:
                print(f"      [{risk.risk_type}] severity={risk.severity:.2f}: {risk.description}")

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

    # Test 2: Eval-generator coupling
    print("\n[TEST 2] Evaluator-Generator Coupling Analysis")
    try:
        risks = optimizer.analyze_eval_generator_coupling(window_days=30)
        print(f"  ✓ Coupling analysis completed")
        print(f"    Risks detected: {len(risks)}")

        if risks:
            for risk in risks:
                print(f"      [{risk.risk_type}] severity={risk.severity:.2f}: {risk.description}")
        else:
            print("    No coupling risks detected ✓")

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

    # Test 3: Reward hacking
    print("\n[TEST 3] Reward Hacking Analysis")
    try:
        risks = optimizer.analyze_reward_hacking(window_days=30)
        print(f"  ✓ Reward hacking analysis completed")
        print(f"    Risks detected: {len(risks)}")

        if risks:
            for risk in risks:
                print(f"      [{risk.risk_type}] severity={risk.severity:.2f}: {risk.description}")
        else:
            print("    No reward hacking detected ✓")

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

    # Test 4: Concept collapse
    print("\n[TEST 4] Concept Collapse Analysis")
    try:
        risks = optimizer.analyze_concept_collapse(limit=100)
        print(f"  ✓ Concept collapse analysis completed")
        print(f"    Risks detected: {len(risks)}")

        if risks:
            for risk in risks:
                print(f"      [{risk.risk_type}] severity={risk.severity:.2f}: {risk.description}")
                if 'mean_similarity' in risk.evidence:
                    print(f"        Mean similarity: {risk.evidence['mean_similarity']:.3f}")
        else:
            print("    No concept collapse detected ✓")

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

    # Test 5: Full analysis
    print("\n[TEST 5] Full Analysis")
    try:
        analysis = optimizer.run_full_analysis(window_days=30, save_to_db=True)
        print(f"  ✓ Full analysis completed")
        print(f"    Total risks: {analysis['summary']['total_risks']}")
        print(f"    Critical: {analysis['summary']['critical']}")
        print(f"    High: {analysis['summary']['high']}")
        print(f"    Medium: {analysis['summary']['medium']}")
        print(f"    Low: {analysis['summary']['low']}")

        print("\n  Recommendations:")
        for i, rec in enumerate(analysis['recommendations'], 1):
            print(f"    {i}. {rec}")

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 6: Mitigation actions
    print("\n[TEST 6] Mitigation Actions")
    try:
        for risk_type in ['model_dominance', 'eval_gen_coupling', 'reward_hacking', 'concept_collapse']:
            actions = optimizer.get_mitigation_actions(risk_type)
            print(f"  ✓ {risk_type}: {len(actions)} actions available")

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED ✓")
    print("=" * 80)

    return True


if __name__ == '__main__':
    success = test_basic_functionality()
    sys.exit(0 if success else 1)
