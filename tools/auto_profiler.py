#!/usr/bin/env python3
"""
Auto-Profiler for Free Models

Profiles models by assigning them REAL tasks (not synthetic benchmarks).
Uses multi-armed bandit with exploration bonus to ensure all models get tried.

Runs continuously in background, profiling unprofiled models during normal usage.
"""

import psycopg2
from psycopg2 import sql
import random
import json
import re
from datetime import datetime

def get_db():
    return psycopg2.connect(
        host='aio-01',
        port=5433,
        user='sfloess',
        database='learning'
    )

class AutoProfiler:
    """Continuous model profiler using real task execution"""

    def __init__(self, exploration_rate=0.15, adaptive=True):
        """
        exploration_rate: Base probability of selecting unprofiled model (epsilon-greedy)
        adaptive: If True, adjust exploration rate based on coverage
                 - High exploration (30%) when coverage < 20%
                 - Medium exploration (15%) when coverage 20-80%
                 - Low exploration (5%) when coverage > 80%
        """
        self.base_exploration_rate = exploration_rate
        self.adaptive = adaptive
        self.db = get_db()
        self.cursor = self.db.cursor()

    @property
    def exploration_rate(self):
        """Get current exploration rate (adaptive or fixed)"""
        if not self.adaptive:
            return self.base_exploration_rate

        # Calculate current coverage
        stats = self.get_profiled_count()
        if stats['total'] == 0:
            return 0.30  # High exploration if no models

        coverage = stats['profiled'] / stats['total']

        # Adaptive exploration based on coverage
        if coverage < 0.20:
            # Low coverage: explore heavily (30%)
            return 0.30
        elif coverage < 0.80:
            # Medium coverage: balanced (15%)
            return 0.15
        else:
            # High coverage: mostly exploit (5%)
            return 0.05

    def get_unprofiled_models(self, limit=20):
        """Get models without capability data"""
        self.cursor.execute("""
            SELECT fm.model_id, fm.provider, fm.context_length
            FROM learning.free_models fm
            LEFT JOIN learning.model_capabilities mc ON fm.model_id = mc.model_id
            WHERE mc.model_id IS NULL
            ORDER BY fm.context_length DESC NULLS LAST
            LIMIT %s
        """, (limit,))

        return [{'model_id': row[0], 'provider': row[1], 'context_length': row[2]}
                for row in self.cursor.fetchall()]

    def get_profiled_count(self):
        """Get count of profiled vs total models"""
        self.cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM learning.model_capabilities) as profiled,
                (SELECT COUNT(*) FROM learning.free_models) as total
        """)
        row = self.cursor.fetchone()
        return {'profiled': row[0], 'total': row[1]}

    def should_explore(self):
        """Decide whether to use unprofiled model (exploration)"""
        return random.random() < self.exploration_rate

    def select_model_for_task(self, task_type='general_qa'):
        """
        Select model for task (with exploration bonus for unprofiled models)

        Returns: (model_id, is_exploration_pick)
        """
        # Validate task_type (whitelist allowed column names)
        ALLOWED_TASK_TYPES = [
            'general_qa', 'code_gen', 'analysis', 'research',
            'reasoning', 'creative', 'summarization'
        ]
        if task_type not in ALLOWED_TASK_TYPES:
            raise ValueError(f"Invalid task_type: {task_type}. Allowed: {ALLOWED_TASK_TYPES}")

        stats = self.get_profiled_count()

        # If no models profiled yet, must explore
        if stats['profiled'] == 0:
            unprofiled = self.get_unprofiled_models(limit=5)
            if unprofiled:
                return unprofiled[0]['model_id'], True

        # Epsilon-greedy: explore unprofiled models sometimes
        if self.should_explore():
            unprofiled = self.get_unprofiled_models(limit=5)
            if unprofiled:
                # Pick from top 5 unprofiled (by context length)
                model = random.choice(unprofiled[:3])
                print(f"🔍 EXPLORATION: Trying unprofiled model {model['model_id']}")
                return model['model_id'], True

        # Exploit: Use best known model for task type (safe - validated above)
        query = sql.SQL("""
            SELECT model_id
            FROM learning.model_capabilities
            WHERE {task_col} IS NOT NULL
            ORDER BY {task_col} DESC
            LIMIT 1
        """).format(task_col=sql.Identifier(task_type))

        self.cursor.execute(query)

        row = self.cursor.fetchone()
        if row:
            return row[0], False

        # Fallback: Random unprofiled
        unprofiled = self.get_unprofiled_models(limit=10)
        if unprofiled:
            return unprofiled[0]['model_id'], True

        return None, False

    def record_result(self, model_id, task_type, confidence, latency_ms):
        """Record profiling result"""

        # Validate task_type (whitelist allowed column names)
        ALLOWED_TASK_TYPES = [
            'general_qa', 'code_gen', 'analysis', 'research',
            'reasoning', 'creative', 'summarization'
        ]
        if task_type not in ALLOWED_TASK_TYPES:
            raise ValueError(f"Invalid task_type: {task_type}. Allowed: {ALLOWED_TASK_TYPES}")

        # Update or insert capability (safe - task_type validated above)
        task_col = sql.Identifier(task_type)

        query = sql.SQL("""
            INSERT INTO learning.model_capabilities
            (model_id, provider, {task_col}, avg_latency_ms, test_count, notes, last_tested)
            VALUES (%s, 'auto-profiled', %s, %s, 1, 'Auto-profiled via real tasks', NOW())
            ON CONFLICT (model_id) DO UPDATE SET
                {task_col} = CASE
                    WHEN learning.model_capabilities.{task_col} IS NULL
                    THEN EXCLUDED.{task_col}
                    ELSE (learning.model_capabilities.{task_col} * learning.model_capabilities.test_count + EXCLUDED.{task_col}) / (learning.model_capabilities.test_count + 1)
                END,
                avg_latency_ms = (learning.model_capabilities.avg_latency_ms * learning.model_capabilities.test_count + EXCLUDED.avg_latency_ms) / (learning.model_capabilities.test_count + 1),
                test_count = learning.model_capabilities.test_count + 1,
                last_tested = NOW()
        """, (model_id, float(confidence), int(latency_ms)))

        self.db.commit()

        # Log progress
        stats = self.get_profiled_count()
        coverage = (stats['profiled'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"✅ Profiled {model_id} for {task_type}: {confidence:.2f} confidence, {latency_ms}ms")
        print(f"   Coverage: {stats['profiled']}/{stats['total']} ({coverage:.1f}%)")

    def get_status(self):
        """Get profiling status summary"""
        stats = self.get_profiled_count()

        self.cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE code_generation IS NOT NULL) as has_code,
                COUNT(*) FILTER (WHERE code_review IS NOT NULL) as has_review,
                COUNT(*) FILTER (WHERE research IS NOT NULL) as has_research,
                COUNT(*) FILTER (WHERE math_reasoning IS NOT NULL) as has_math,
                COUNT(*) FILTER (WHERE general_qa IS NOT NULL) as has_qa,
                AVG(test_count) as avg_tests_per_model
            FROM learning.model_capabilities
        """)

        row = self.cursor.fetchone()

        return {
            'total_models': stats['total'],
            'profiled_models': stats['profiled'],
            'coverage_pct': (stats['profiled'] / stats['total'] * 100) if stats['total'] > 0 else 0,
            'by_task': {
                'code_generation': row[0],
                'code_review': row[1],
                'research': row[2],
                'math_reasoning': row[3],
                'general_qa': row[4]
            },
            'avg_tests_per_model': float(row[5]) if row[5] else 0
        }

    def close(self):
        self.cursor.close()
        self.db.close()

def run_profiling_demo():
    """Demo: Profile a few models with simulated tasks"""
    print("=== Auto-Profiler Demo ===\n")

    profiler = AutoProfiler(exploration_rate=0.3)  # 30% exploration

    # Show initial status
    status = profiler.get_status()
    print(f"Initial coverage: {status['profiled_models']}/{status['total_models']} ({status['coverage_pct']:.1f}%)")
    print(f"By task type:")
    for task, count in status['by_task'].items():
        print(f"  {task}: {count} models")
    print()

    # Simulate profiling some tasks
    task_types = ['code_generation', 'code_review', 'research', 'math_reasoning', 'general_qa']

    print("Simulating 20 task executions with exploration...\n")

    for i in range(20):
        task_type = random.choice(task_types)
        model, is_exploration = profiler.select_model_for_task(task_type)

        if model:
            # Simulate execution
            confidence = random.uniform(0.5, 0.95)
            latency = random.randint(800, 3000)

            profiler.record_result(model, task_type, confidence, latency)

    # Show final status
    print("\n" + "="*60)
    status = profiler.get_status()
    print(f"\nFinal coverage: {status['profiled_models']}/{status['total_models']} ({status['coverage_pct']:.1f}%)")
    print(f"Average tests per model: {status['avg_tests_per_model']:.1f}")
    print(f"\nBy task type:")
    for task, count in status['by_task'].items():
        print(f"  {task}: {count} models")

    profiler.close()

    print("\n✅ Auto-profiler demo complete!")
    print("\nTo integrate with orchestrator:")
    print("  profiler = AutoProfiler(exploration_rate=0.15)")
    print("  model, is_exploration = profiler.select_model_for_task('code_generation')")
    print("  # ... execute task ...")
    print("  profiler.record_result(model, 'code_generation', confidence, latency)")

if __name__ == '__main__':
    run_profiling_demo()
