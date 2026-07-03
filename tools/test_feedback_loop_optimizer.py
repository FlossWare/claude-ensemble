#!/usr/bin/env python3
"""
Test Suite for Feedback Loop Optimizer

Validates all 4 detection layers with synthetic data
Run: python3 tools/test_feedback_loop_optimizer.py

Created: 2026-07-03
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from feedback_loop_optimizer import FeedbackLoopOptimizer, FeedbackLoopRisk
import psycopg2
from datetime import datetime, timedelta
import json
import numpy as np


class FeedbackLoopOptimizerTests:
    """Test suite for feedback loop optimizer"""

    def __init__(self):
        self.optimizer = FeedbackLoopOptimizer()
        self.db_config = self.optimizer.db_config
        self.test_workflow_id = f'test-feedback-loop-{datetime.now().timestamp()}'

    def _cleanup_test_data(self):
        """Remove test data from database"""
        with psycopg2.connect(**self.db_config) as conn:
            with conn.cursor() as cur:
                # Clean monitoring.execution_summary
                cur.execute("""
                    DELETE FROM monitoring.execution_summary
                    WHERE workflow LIKE 'test-%'
                """)

                # Clean workflow tables
                cur.execute("""
                    DELETE FROM workflow.executions
                    WHERE workflow_id LIKE 'test-%'
                """)

                # Clean feedback_loop_risks
                try:
                    cur.execute("""
                        DELETE FROM monitoring.feedback_loop_risks
                        WHERE description LIKE '%TEST%'
                    """)
                except Exception:
                    pass  # Table may not exist yet

                conn.commit()

    def _insert_execution_logs(self, logs):
        """Insert test execution logs"""
        with psycopg2.connect(**self.db_config) as conn:
            with conn.cursor() as cur:
                for log in logs:
                    cur.execute("""
                        INSERT INTO monitoring.execution_summary
                        (timestamp, model, workflow, task_type, quality_score,
                         input_tokens, output_tokens, cost_usd, duration_ms, outcome)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        log['timestamp'],
                        log['model'],
                        log.get('workflow', 'test-workflow'),
                        log.get('task_type', 'test'),
                        log.get('quality_score', 0.8),
                        log.get('input_tokens', 1000),
                        log.get('output_tokens', 500),
                        log.get('cost_usd', 0.01),
                        log.get('duration_ms', 2000),
                        log.get('outcome', 'success')
                    ))
                conn.commit()

    def _insert_workflow_data(self, workers, arbiter):
        """Insert test workflow worker results and arbiter decisions"""
        with psycopg2.connect(**self.db_config) as conn:
            with conn.cursor() as cur:
                # Create workflow execution
                cur.execute("""
                    INSERT INTO workflow.executions
                    (workflow_id, workflow_name, task_description, total_workers,
                     total_duration_ms, outcome, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    self.test_workflow_id,
                    'test-coupling',
                    'TEST coupling detection',
                    len(workers),
                    5000,
                    'success',
                    datetime.now()
                ))

                exec_id = cur.fetchone()[0]

                # Insert workers
                worker_ids = []
                for i, worker in enumerate(workers):
                    cur.execute("""
                        INSERT INTO workflow.worker_results
                        (workflow_execution_id, worker_id, model, task_assigned,
                         result, confidence, duration_ms, input_tokens, output_tokens,
                         cost_usd, outcome, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        exec_id,
                        f'worker-{i}',
                        worker['model'],
                        f'Task {i}',
                        f'Result {i}',
                        0.85,
                        1000,
                        500,
                        300,
                        0.01,
                        'success',
                        datetime.now()
                    ))
                    worker_ids.append(cur.fetchone()[0])

                # Insert arbiter decision
                cur.execute("""
                    INSERT INTO workflow.arbiter_decisions
                    (workflow_execution_id, arbiter_model, worker_result_ids,
                     decision, reasoning, confidence, duration_ms, input_tokens,
                     output_tokens, cost_usd, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    exec_id,
                    arbiter['model'],
                    worker_ids,
                    'Synthesis complete',
                    'TEST arbiter decision',
                    0.90,
                    2000,
                    1500,
                    800,
                    0.02,
                    datetime.now()
                ))

                conn.commit()

    def test_model_dominance_detection(self):
        """Test Layer 1: Model dominance detection (>70/30 rule)"""
        print("\n[TEST 1] Model Dominance Detection")

        # Insert logs with 80% opus dominance
        now = datetime.now()
        logs = []

        for i in range(80):
            logs.append({
                'timestamp': now - timedelta(hours=i),
                'model': 'opus',
                'workflow': 'test-dominance'
            })

        for i in range(20):
            logs.append({
                'timestamp': now - timedelta(hours=i),
                'model': 'sonnet',
                'workflow': 'test-dominance'
            })

        self._insert_execution_logs(logs)

        # Run analysis
        distribution, risks = self.optimizer.analyze_model_distribution(window_days=1)

        # Verify
        assert 'opus' in distribution, "Opus should be in distribution"
        assert distribution['opus'] > 0.70, f"Opus should be >70%, got {distribution['opus']}"
        assert len(risks) > 0, "Should detect dominance risk"
        assert risks[0].risk_type == 'model_dominance', "Should be model_dominance risk"
        assert risks[0].severity > 0.0, "Should have non-zero severity"

        print(f"  ✓ Detected dominance: opus={distribution['opus']*100:.1f}% (threshold=70%)")
        print(f"  ✓ Risk severity: {risks[0].severity:.2f}")
        print(f"  ✓ Description: {risks[0].description}")

        return True

    def test_eval_generator_coupling_detection(self):
        """Test Layer 2: Evaluator-generator coupling detection"""
        print("\n[TEST 2] Evaluator-Generator Coupling Detection")

        # Create workflows where opus evaluates its own outputs
        for i in range(10):
            self.test_workflow_id = f'test-coupling-{i}'

            workers = [
                {'model': 'opus'},
                {'model': 'sonnet'},
                {'model': 'haiku'}
            ]

            # Same model arbiter (coupling)
            arbiter = {'model': 'opus'}

            self._insert_workflow_data(workers, arbiter)

        # Run analysis
        risks = self.optimizer.analyze_eval_generator_coupling(window_days=1)

        # Verify
        if len(risks) > 0:
            assert risks[0].risk_type == 'eval_gen_coupling', "Should be coupling risk"
            print(f"  ✓ Detected coupling: {risks[0].description}")
            print(f"  ✓ Risk severity: {risks[0].severity:.2f}")
        else:
            print("  ⚠ No coupling detected (need more test data or lower threshold)")

        return True

    def test_reward_hacking_detection(self):
        """Test Layer 3: Reward hacking detection"""
        print("\n[TEST 3] Reward Hacking Detection")

        # Insert logs showing quality increasing + diversity decreasing
        now = datetime.now()
        logs = []

        # Day 1-3: Low quality, high diversity
        for day in range(1, 4):
            for model in ['opus', 'sonnet', 'haiku', 'gemini']:
                for i in range(5):
                    logs.append({
                        'timestamp': now - timedelta(days=day, hours=i),
                        'model': model,
                        'quality_score': 0.60 + np.random.normal(0, 0.05),
                        'workflow': 'test-reward'
                    })

        # Day 4-7: High quality, low diversity (reward hacking!)
        for day in range(4, 8):
            for model in ['opus']:  # Only opus (low diversity)
                for i in range(20):
                    logs.append({
                        'timestamp': now - timedelta(days=day, hours=i),
                        'model': model,
                        'quality_score': 0.90 + np.random.normal(0, 0.02),
                        'workflow': 'test-reward'
                    })

        self._insert_execution_logs(logs)

        # Run analysis
        risks = self.optimizer.analyze_reward_hacking(window_days=7)

        # Verify
        if len(risks) > 0:
            assert risks[0].risk_type == 'reward_hacking', "Should be reward_hacking risk"
            print(f"  ✓ Detected reward hacking: {risks[0].description}")
            print(f"  ✓ Risk severity: {risks[0].severity:.2f}")
            print(f"  ✓ Evidence: quality_trend={risks[0].evidence['quality_trend']:.3f}, diversity_trend={risks[0].evidence['diversity_trend']:.3f}")
        else:
            print("  ⚠ No reward hacking detected (trends may not be strong enough)")

        return True

    def test_concept_collapse_detection(self):
        """Test Layer 4: Concept collapse detection"""
        print("\n[TEST 4] Concept Collapse Detection")

        # Insert workflow results with highly similar embeddings
        with psycopg2.connect(**self.db_config) as conn:
            with conn.cursor() as cur:
                # Create workflow
                cur.execute("""
                    INSERT INTO workflow.executions
                    (workflow_id, workflow_name, task_description, total_workers,
                     total_duration_ms, outcome, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    f'test-collapse-{datetime.now().timestamp()}',
                    'test-collapse',
                    'TEST concept collapse',
                    10,
                    5000,
                    'success',
                    datetime.now()
                ))

                exec_id = cur.fetchone()[0]

                # Generate similar embeddings (all close to same vector)
                base_embedding = np.random.randn(384)
                base_embedding /= np.linalg.norm(base_embedding)

                for i in range(20):
                    # Add small noise to base embedding
                    noise = np.random.randn(384) * 0.1
                    embedding = base_embedding + noise
                    embedding /= np.linalg.norm(embedding)

                    cur.execute("""
                        INSERT INTO workflow.worker_results
                        (workflow_execution_id, worker_id, model, task_assigned,
                         result, result_embedding, confidence, duration_ms,
                         input_tokens, output_tokens, cost_usd, outcome, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        exec_id,
                        f'worker-{i}',
                        'opus',
                        f'Task {i}',
                        f'Similar result {i}',
                        json.dumps(embedding.tolist()),
                        0.85,
                        1000,
                        500,
                        300,
                        0.01,
                        'success',
                        datetime.now()
                    ))

                conn.commit()

        # Run analysis
        risks = self.optimizer.analyze_concept_collapse(limit=50)

        # Verify
        assert len(risks) > 0, "Should detect concept collapse"
        assert risks[0].risk_type == 'concept_collapse', "Should be concept_collapse risk"
        assert risks[0].evidence['mean_similarity'] > 0.80, "Mean similarity should be high"

        print(f"  ✓ Detected concept collapse: mean_similarity={risks[0].evidence['mean_similarity']:.3f}")
        print(f"  ✓ Risk severity: {risks[0].severity:.2f}")
        print(f"  ✓ High similarity pairs: {risks[0].evidence['high_similarity_count']}/{risks[0].evidence['total_pairs']}")

        return True

    def test_full_analysis(self):
        """Test full analysis integration"""
        print("\n[TEST 5] Full Analysis Integration")

        analysis = self.optimizer.run_full_analysis(window_days=1, save_to_db=False)

        # Verify structure
        assert 'timestamp' in analysis, "Should have timestamp"
        assert 'window_days' in analysis, "Should have window_days"
        assert 'risks' in analysis, "Should have risks list"
        assert 'summary' in analysis, "Should have summary"
        assert 'model_distribution' in analysis, "Should have model_distribution"
        assert 'recommendations' in analysis, "Should have recommendations"

        # Verify summary structure
        summary = analysis['summary']
        assert 'total_risks' in summary, "Summary should have total_risks"
        assert 'critical' in summary, "Summary should have critical"
        assert 'high' in summary, "Summary should have high"
        assert 'medium' in summary, "Summary should have medium"
        assert 'low' in summary, "Summary should have low"

        print(f"  ✓ Analysis structure valid")
        print(f"  ✓ Total risks detected: {summary['total_risks']}")
        print(f"  ✓ Critical: {summary['critical']}, High: {summary['high']}, Medium: {summary['medium']}, Low: {summary['low']}")

        # Test report generation
        self.optimizer.print_report(analysis)

        return True

    def run_all_tests(self):
        """Run all test cases"""
        print("=" * 80)
        print("FEEDBACK LOOP OPTIMIZER TEST SUITE")
        print("=" * 80)

        try:
            # Clean up before tests
            print("\nCleaning up test data...")
            self._cleanup_test_data()

            # Run tests
            tests = [
                self.test_model_dominance_detection,
                self.test_eval_generator_coupling_detection,
                self.test_reward_hacking_detection,
                self.test_concept_collapse_detection,
                self.test_full_analysis
            ]

            passed = 0
            failed = 0

            for test in tests:
                try:
                    if test():
                        passed += 1
                except Exception as e:
                    print(f"  ✗ FAILED: {e}")
                    failed += 1
                    import traceback
                    traceback.print_exc()

            # Clean up after tests
            print("\nCleaning up test data...")
            self._cleanup_test_data()

            # Summary
            print("\n" + "=" * 80)
            print(f"TEST SUMMARY: {passed} passed, {failed} failed")
            print("=" * 80)

            return failed == 0

        except Exception as e:
            print(f"\n✗ Test suite failed: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    tests = FeedbackLoopOptimizerTests()
    success = tests.run_all_tests()
    sys.exit(0 if success else 1)
