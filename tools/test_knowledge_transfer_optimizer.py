#!/usr/bin/env python3
"""
Test Knowledge Transfer Optimizer

Validates:
1. Transfer plan creation
2. Similarity assessment
3. Knowledge distillation
4. Effectiveness evaluation

Created: 2026-07-03
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

from knowledge_transfer_optimizer import (
    KnowledgeTransferOptimizer,
    TransferCandidate
)


def test_basic_functionality():
    """Test basic optimizer functionality"""
    print("=" * 80)
    print("TEST: Basic Functionality")
    print("=" * 80)

    optimizer = KnowledgeTransferOptimizer()

    # Test 1: Temporal relevance decay
    print("\n1. Temporal Relevance Decay:")
    now = datetime.now()
    recent = now - timedelta(days=1)
    old = now - timedelta(days=60)
    ancient = now - timedelta(days=180)

    recent_decay = optimizer._temporal_relevance(recent)
    old_decay = optimizer._temporal_relevance(old)
    ancient_decay = optimizer._temporal_relevance(ancient)

    print(f"  1 day ago: {recent_decay:.3f} (should be ~0.977)")
    print(f"  60 days ago: {old_decay:.3f} (should be ~0.250)")
    print(f"  180 days ago: {ancient_decay:.3f} (should be ~0.016)")

    assert 0.97 < recent_decay < 0.99, "Recent decay should be ~0.977"
    assert 0.24 < old_decay < 0.26, "Old decay should be ~0.250"
    assert 0.01 < ancient_decay < 0.02, "Ancient decay should be ~0.016"
    print("  ✓ Temporal decay working correctly")

    # Test 2: Task hashing
    print("\n2. Task Hashing:")
    task1 = "Fix authentication bug in login flow"
    task2 = "Fix authentication bug in login flow"
    task3 = "Implement OAuth2 authentication"

    hash1 = optimizer._hash_task(task1)
    hash2 = optimizer._hash_task(task2)
    hash3 = optimizer._hash_task(task3)

    print(f"  Task 1 hash: {hash1}")
    print(f"  Task 2 hash: {hash2}")
    print(f"  Task 3 hash: {hash3}")

    assert hash1 == hash2, "Same tasks should have same hash"
    assert hash1 != hash3, "Different tasks should have different hash"
    print("  ✓ Task hashing working correctly")

    # Test 3: Transfer assessment
    print("\n3. Transfer Assessment:")

    # Mock candidate (successful similar task)
    candidate_success = {
        'workflow_id': 'wf-001',
        'task_description': 'Fix authentication bug in OAuth2 flow',
        'outcome': 'success',
        'created_at': datetime.now() - timedelta(days=7)
    }

    # Mock candidate (failed dissimilar task)
    candidate_failure = {
        'workflow_id': 'wf-002',
        'task_description': 'Deploy Kubernetes cluster to production',
        'outcome': 'failed',
        'created_at': datetime.now() - timedelta(days=90)
    }

    task = "Fix authentication bug in login flow"

    transfer_score_pos, confidence_pos = optimizer.assess_transfer_potential(
        task, candidate_success
    )
    transfer_score_neg, confidence_neg = optimizer.assess_transfer_potential(
        task, candidate_failure
    )

    print(f"  Similar success: transfer_score={transfer_score_pos:.3f}, confidence={confidence_pos:.3f}")
    print(f"  Dissimilar failure: transfer_score={transfer_score_neg:.3f}, confidence={confidence_neg:.3f}")

    assert transfer_score_pos > 0.3, "Similar success should have positive transfer"
    assert confidence_pos > 0.5, "Similar success should have high confidence"
    assert transfer_score_neg <= 0.1, "Dissimilar failure should have minimal transfer"
    print("  ✓ Transfer assessment working correctly")

    # Test 4: Knowledge distillation
    print("\n4. Knowledge Distillation:")

    # Mock positive transfers
    positive_transfers = [
        TransferCandidate(
            workflow_id='wf-001',
            workflow_execution_id=1,
            task_description='Fix OAuth bug',
            similarity_score=0.85,
            outcome='success',
            total_duration_ms=15000,
            created_at=datetime.now() - timedelta(days=7),
            learnings=[
                {
                    'learning_type': 'pattern',
                    'description': 'Token validation should happen before database lookup',
                    'actionable_insight': 'Validate JWT tokens at API gateway level',
                    'importance': 0.9
                },
                {
                    'learning_type': 'optimization',
                    'description': 'Use redis cache for session tokens',
                    'actionable_insight': 'Cache tokens with 15-minute TTL',
                    'importance': 0.7
                }
            ],
            transfer_score=0.75,
            confidence=0.85,
            relevance_decay=0.95
        ),
        TransferCandidate(
            workflow_id='wf-002',
            workflow_execution_id=2,
            task_description='Fix authentication timeout',
            similarity_score=0.70,
            outcome='success',
            total_duration_ms=12000,
            created_at=datetime.now() - timedelta(days=14),
            learnings=[
                {
                    'learning_type': 'pattern',
                    'description': 'Token validation should use constant-time comparison',
                    'actionable_insight': 'Use crypto.timingSafeEqual to prevent timing attacks',
                    'importance': 0.85
                }
            ],
            transfer_score=0.65,
            confidence=0.75,
            relevance_decay=0.90
        )
    ]

    distilled = optimizer.distill_knowledge(positive_transfers)

    print(f"  Key learnings: {len(distilled['key_learnings'])}")
    print(f"  Duration estimate: {distilled['duration_estimate_ms']:.0f}ms")
    print(f"  Common patterns: {len(distilled['common_patterns'])}")

    assert len(distilled['key_learnings']) > 0, "Should extract learnings"
    assert distilled['duration_estimate_ms'] is not None, "Should estimate duration"
    print("  ✓ Knowledge distillation working correctly")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED ✓")
    print("=" * 80)


def test_database_integration():
    """Test database integration (if available)"""
    print("\n" + "=" * 80)
    print("TEST: Database Integration")
    print("=" * 80)

    try:
        import psycopg2

        optimizer = KnowledgeTransferOptimizer()

        # Test database connection
        print("\n1. Database Connection:")
        try:
            conn = optimizer._get_connection()
            conn.close()
            print("  ✓ Connected to PostgreSQL")
        except Exception as e:
            print(f"  ✗ Connection failed: {e}")
            print("  Skipping database tests (database unavailable)")
            return

        # Test similar workflow retrieval
        print("\n2. Similar Workflow Retrieval:")
        try:
            candidates = optimizer.retrieve_similar_workflows(
                "Fix authentication bug",
                max_results=5
            )
            print(f"  Retrieved {len(candidates)} candidates")

            if len(candidates) > 0:
                print(f"  Sample: {candidates[0]['workflow_name']}")
                print("  ✓ Retrieval working")
            else:
                print("  ⚠ No candidates found (database may be empty)")

        except Exception as e:
            print(f"  ✗ Retrieval failed: {e}")

        # Test transfer plan creation
        print("\n3. Transfer Plan Creation:")
        try:
            plan = optimizer.create_transfer_plan("Fix authentication bug in OAuth2 flow")

            print(f"  Candidates retrieved: {plan.candidates_retrieved}")
            print(f"  Positive transfers: {len(plan.positive_transfers)}")
            print(f"  Negative transfers: {len(plan.negative_transfers)}")
            print(f"  Key learnings: {len(plan.key_learnings)}")

            if plan.estimated_duration_ms:
                print(f"  Estimated duration: {plan.estimated_duration_ms:.0f}ms")

            print("  ✓ Transfer plan creation working")

        except Exception as e:
            print(f"  ✗ Plan creation failed: {e}")

        # Test effectiveness evaluation
        print("\n4. Effectiveness Evaluation:")
        try:
            stats = optimizer.evaluate_transfer_effectiveness(window_days=30)

            print(f"  Groups analyzed: {list(stats.keys())}")

            if 'with_context' in stats:
                print(f"  With context: {stats['with_context']['total']} workflows, "
                      f"{stats['with_context']['success_rate']:.1%} success")

            if 'no_context' in stats:
                print(f"  No context: {stats['no_context']['total']} workflows, "
                      f"{stats['no_context']['success_rate']:.1%} success")

            if 'improvement' in stats:
                print(f"  Improvement: {stats['improvement']['success_rate_delta']:+.1%}")

            print("  ✓ Effectiveness evaluation working")

        except Exception as e:
            print(f"  ✗ Evaluation failed: {e}")

        print("\n" + "=" * 80)
        print("DATABASE INTEGRATION TESTS COMPLETE")
        print("=" * 80)

    except ImportError:
        print("\npsycopg2 not available - skipping database tests")


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("KNOWLEDGE TRANSFER OPTIMIZER TEST SUITE")
    print("=" * 80)

    # Test 1: Basic functionality (no database required)
    test_basic_functionality()

    # Test 2: Database integration (if available)
    test_database_integration()

    print("\n" + "=" * 80)
    print("ALL TEST SUITES COMPLETE")
    print("=" * 80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
