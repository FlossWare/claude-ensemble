#!/usr/bin/env python3
"""
Comprehensive test for Security Policy Learner

Tests:
1. Policy creation with embeddings
2. Violation recording
3. Thompson Sampling updates (true/false positives)
4. Similarity search
5. Policy recommendations
6. Export and statistics
"""

import sys
from pathlib import Path

# Add learning directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'learning'))

from security_policy_learner import SecurityPolicyLearner
import json


def test_full_workflow():
    """Test complete security policy learning workflow."""

    learner = SecurityPolicyLearner()

    print("\n" + "="*80)
    print("SECURITY POLICY LEARNER - FULL WORKFLOW TEST")
    print("="*80)

    # Test 1: Add more comprehensive policies
    print("\n[Test 1] Adding Comprehensive Security Policies...")

    policies_added = []

    # XSS policies
    p1 = learner.add_policy(
        policy_name="XSS - innerHTML Assignment",
        pattern=r"\.innerHTML\s*=",
        owasp_category="A03",
        severity="HIGH",
        description="Direct innerHTML assignment can lead to XSS attacks"
    )
    policies_added.append(p1)

    # Path Traversal
    p2 = learner.add_policy(
        policy_name="Path Traversal - Directory Traversal",
        pattern=r"\.\./",
        owasp_category="A01",
        severity="HIGH",
        description="Directory traversal attempts using ../"
    )
    policies_added.append(p2)

    # Insecure Deserialization
    p3 = learner.add_policy(
        policy_name="Insecure Deserialization - Pickle",
        pattern=r"pickle\.loads\s*\(",
        owasp_category="A08",
        severity="CRITICAL",
        description="Pickle deserialization can execute arbitrary code"
    )
    policies_added.append(p3)

    # SSRF
    p4 = learner.add_policy(
        policy_name="SSRF - User-Controlled URL",
        pattern=r"requests\.(get|post)\s*\([^)]*user",
        owasp_category="A10",
        severity="HIGH",
        description="User-controlled URLs in HTTP requests can lead to SSRF"
    )
    policies_added.append(p4)

    print(f"✓ Added {len(policies_added)} new policies")

    # Test 2: Record multiple violations
    print("\n[Test 2] Recording Security Violations...")

    violations = []

    # XSS violation
    v1 = learner.record_violation(
        policy_id=p1,
        file_path="/app/frontend/dashboard.js",
        code_snippet='element.innerHTML = userInput;',
        severity="HIGH",
        line_number=127,
        metadata={'component': 'dashboard', 'risk': 'high'}
    )
    violations.append((v1, True))  # True = will be marked as true positive

    # Path traversal violation
    v2 = learner.record_violation(
        policy_id=p2,
        file_path="/app/api/fileserver.py",
        code_snippet='file_path = base_path + "../" + user_file',
        severity="HIGH",
        line_number=89,
        metadata={'component': 'file-server', 'risk': 'critical'}
    )
    violations.append((v2, True))

    # Pickle violation
    v3 = learner.record_violation(
        policy_id=p3,
        file_path="/app/api/cache.py",
        code_snippet='data = pickle.loads(cached_value)',
        severity="CRITICAL",
        line_number=45,
        metadata={'component': 'cache', 'risk': 'critical'}
    )
    violations.append((v3, True))

    # False positive (benign use of requests)
    v4 = learner.record_violation(
        policy_id=p4,
        file_path="/app/tests/test_api.py",
        code_snippet='response = requests.get(test_user_url)',
        severity="HIGH",
        line_number=23,
        metadata={'component': 'tests', 'risk': 'low', 'is_test': True}
    )
    violations.append((v4, False))  # False = false positive

    print(f"✓ Recorded {len(violations)} violations")

    # Test 3: Mark violations as fixed and update Thompson Sampling
    print("\n[Test 3] Marking Violations as Fixed (Thompson Sampling Updates)...")

    for violation_id, is_true_positive in violations:
        fix_desc = "Sanitized input" if is_true_positive else "False positive - test code"
        learner.mark_violation_fixed(violation_id, fix_desc, is_true_positive)
        status = "TRUE POSITIVE" if is_true_positive else "FALSE POSITIVE"
        print(f"  ✓ Marked {violation_id[:8]} as fixed ({status})")

    # Test 4: Get policy statistics with Thompson Sampling state
    print("\n[Test 4] Policy Performance Statistics...")

    stats = learner.get_policy_stats()
    print(f"  Total Policies: {stats['total_policies']}")
    print(f"  Active Policies: {stats['active_policies']}")
    print(f"  Total Triggers: {stats['total_triggers']}")
    print(f"  True Positives: {stats['total_true_positives']}")
    print(f"  False Positives: {stats['total_false_positives']}")
    print(f"  Average Precision: {stats['avg_precision']:.2%}")
    print(f"  Total Violations: {stats['total_violations']}")
    print(f"  Fixed Violations: {stats['fixed_violations']}")

    # Test 5: Find similar violations
    print("\n[Test 5] Finding Similar Violations (Vector Similarity)...")

    test_code = "document.getElementById('output').innerHTML = data;"
    similar = learner.find_similar_violations(test_code, limit=3)

    if similar:
        print(f"  Found {len(similar)} similar violations:")
        for i, v in enumerate(similar, 1):
            print(f"\n  {i}. Policy: {v['policy_name']}")
            print(f"     Similarity: {v['similarity']:.2%}")
            print(f"     File: {v['file_path']}")
            print(f"     Fixed: {v['fixed']}")
            if v['fix_applied']:
                print(f"     Fix: {v['fix_applied']}")
    else:
        print("  (No similar violations found - embeddings may not be available)")

    # Test 6: Get policy recommendations
    print("\n[Test 6] Policy Recommendations (Thompson Sampling)...")

    test_code2 = "user_data = yaml.load(file_contents)"
    recommendations = learner.recommend_policies(test_code2, limit=3)

    print(f"  Recommended policies for code: '{test_code2[:50]}...'")
    for i, rec in enumerate(recommendations, 1):
        print(f"\n  {i}. {rec['policy_name']}")
        print(f"     OWASP: {rec['owasp_category']} | Severity: {rec['severity']}")
        print(f"     Precision: {rec['precision']:.2%}")
        print(f"     Avg Reward: {rec['avg_reward']:.3f}")
        print(f"     Thompson Score: {rec['thompson_score']:.3f}")
        if rec['similarity'] > 0:
            print(f"     Similarity: {rec['similarity']:.2%}")

    # Test 7: Get top policies by performance
    print("\n[Test 7] Top Policies by Thompson Sampling Performance...")

    learner.cursor.execute("""
        SELECT
            p.policy_name,
            p.severity,
            p.precision,
            perf.successes,
            perf.failures,
            perf.avg_reward,
            perf.alpha,
            perf.beta
        FROM learning.security_policies p
        JOIN learning.policy_performance perf ON p.policy_id = perf.policy_id
        WHERE p.active = TRUE AND (perf.successes + perf.failures) > 0
        ORDER BY perf.avg_reward DESC, p.severity DESC
        LIMIT 5
    """)

    top_policies = learner.cursor.fetchall()
    if top_policies:
        print("\n  Top performing policies:")
        for i, policy in enumerate(top_policies, 1):
            print(f"\n  {i}. {policy[0]}")
            print(f"     Severity: {policy[1]}")
            print(f"     Precision: {policy[2]:.2%}" if policy[2] else "     Precision: N/A")
            print(f"     Successes: {policy[3]} | Failures: {policy[4]}")
            print(f"     Avg Reward: {policy[5]:.3f}" if policy[5] is not None else "     Avg Reward: 0.000")
            print(f"     Thompson Sampling: Alpha={policy[6]:.1f}, Beta={policy[7]:.1f}")

    # Test 8: Export policies
    print("\n[Test 8] Exporting Policies...")

    export_path = Path(__file__).parent.parent / 'learning' / 'security_policies_complete.json'
    learner.export_policies(str(export_path))

    # Load and display summary
    with open(export_path) as f:
        exported = json.load(f)

    print(f"\n  Exported {len(exported)} policies to {export_path.name}")
    print("\n  Summary by OWASP category:")

    owasp_counts = {}
    for policy in exported:
        cat = policy['owasp_category']
        if cat not in owasp_counts:
            owasp_counts[cat] = 0
        owasp_counts[cat] += 1

    for cat in sorted(owasp_counts.keys()):
        print(f"    {cat}: {owasp_counts[cat]} policies")

    # Final summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✓ Policies Created: {stats['total_policies']}")
    print(f"✓ Violations Recorded: {stats['total_violations']}")
    print(f"✓ Violations Fixed: {stats['fixed_violations']}")
    print(f"✓ True Positives: {stats['total_true_positives']}")
    print(f"✓ False Positives: {stats['total_false_positives']}")
    print(f"✓ Overall Precision: {stats['avg_precision']:.2%}")
    print(f"✓ Thompson Sampling: Active (Beta distributions updated)")
    print(f"✓ Vector Similarity: {'Active' if similar else 'Inactive (embeddings unavailable)'}")
    print(f"✓ Exported Policies: {export_path}")

    learner.close()
    print("\n✓ All tests completed successfully!")

    return True


if __name__ == '__main__':
    try:
        success = test_full_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
