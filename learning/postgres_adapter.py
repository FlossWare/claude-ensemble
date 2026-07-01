"""
PostgreSQL Adapter for Learning System (Python)
Drop-in replacement for SQLite database access

Usage:
    from postgres_adapter import get_db, get_strategy_performance, get_cost_tracker

    db = get_db()
    rows = db.query("SELECT * FROM learning.experiences LIMIT 10")
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

# Connection pool (reuse connections)
_connection_pool = None

def get_connection():
    """Get a database connection"""
    return psycopg2.connect(
        dbname='learning',
        user='sfloess',  # Database owner
        host='aio-01',  # PostgreSQL server
        port=5433,  # Non-standard port
        cursor_factory=RealDictCursor
    )

@contextmanager
def get_cursor():
    """Context manager for database cursor"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor, conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()

class LearningDB:
    """PostgreSQL database adapter"""

    def query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Execute a query and return all rows"""
        with get_cursor() as (cursor, conn):
            cursor.execute(sql, params)
            return cursor.fetchall() if cursor.description else []

    def get(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        """Execute a query and return first row"""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Execute INSERT/UPDATE/DELETE and return row count"""
        with get_cursor() as (cursor, conn):
            cursor.execute(sql, params)
            return cursor.rowcount

class StrategyPerformance:
    """Thompson Sampling Bandit state management"""

    def __init__(self, db: LearningDB = None):
        self.db = db or LearningDB()

    def get_strategy(self, strategy: str) -> Optional[Dict]:
        return self.db.get(
            "SELECT * FROM learning.strategy_performance WHERE strategy = %s",
            (strategy,)
        )

    def update_strategy(self, strategy: str, data: Dict):
        sql = """
            INSERT INTO learning.strategy_performance
            (strategy, successes, failures, alpha, beta, total_reward, avg_reward, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (strategy) DO UPDATE SET
                successes = EXCLUDED.successes,
                failures = EXCLUDED.failures,
                alpha = EXCLUDED.alpha,
                beta = EXCLUDED.beta,
                total_reward = EXCLUDED.total_reward,
                avg_reward = EXCLUDED.avg_reward,
                last_updated = NOW()
        """
        self.db.execute(sql, (
            strategy,
            data['successes'],
            data['failures'],
            data['alpha'],
            data['beta'],
            data['total_reward'],
            data['avg_reward']
        ))

    def get_all_strategies(self) -> List[Dict]:
        return self.db.query(
            "SELECT * FROM learning.strategy_performance ORDER BY avg_reward DESC"
        )

class ExecutionMonitor:
    """Model execution monitoring"""

    def __init__(self, db: LearningDB = None):
        self.db = db or LearningDB()

    def log_execution(self, data: Dict):
        sql = """
            INSERT INTO monitoring.execution_summary
            (timestamp, model, workflow, task_type, quality_score,
             input_tokens, output_tokens, cost_usd, duration_ms, outcome)
            VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        self.db.execute(sql, (
            data['model'],
            data.get('workflow'),
            data.get('task_type'),
            data.get('quality_score'),
            data.get('input_tokens', 0),
            data.get('output_tokens', 0),
            data.get('cost_usd', 0.0),
            data.get('duration_ms', 0),
            data.get('outcome', 'unknown')
        ))

    def get_recent(self, limit: int = 100) -> List[Dict]:
        return self.db.query(
            "SELECT * FROM monitoring.execution_summary ORDER BY timestamp DESC LIMIT %s",
            (limit,)
        )

class CostTracker:
    """Cost tracking and reporting"""

    def __init__(self, db: LearningDB = None):
        self.db = db or LearningDB()

    def log_cost(self, data: Dict):
        sql = """
            INSERT INTO costs.entries (timestamp, model, input_tokens, output_tokens, total_cost)
            VALUES (NOW(), %s, %s, %s, %s)
        """
        self.db.execute(sql, (
            data['model'],
            data.get('input_tokens', 0),
            data.get('output_tokens', 0),
            data.get('total_cost', 0.0)
        ))

    def get_daily_costs(self, days: int = 30) -> List[Dict]:
        sql = """
            SELECT DATE(timestamp) as date,
                   SUM(total_cost) as total_cost,
                   SUM(input_tokens) as input_tokens,
                   SUM(output_tokens) as output_tokens
            FROM costs.entries
            WHERE timestamp > NOW() - INTERVAL '%s days'
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """
        return self.db.query(sql, (days,))

    def get_total_cost(self, days: int = 30) -> float:
        result = self.db.get(
            "SELECT SUM(total_cost) as total FROM costs.entries WHERE timestamp > NOW() - INTERVAL '%s days'",
            (days,)
        )
        return result['total'] if result and result['total'] else 0.0

class ExperienceMemory:
    """Continual learning experience memory"""

    def __init__(self, db: LearningDB = None):
        self.db = db or LearningDB()

    def add_experience(self, data: Dict):
        sql = """
            INSERT INTO learning.experiences
            (problem_type, problem_hash, context, embedding, strategy, success, reward, novelty_score, importance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        self.db.execute(sql, (
            data['problem_type'],
            data['problem_hash'],
            json.dumps(data.get('context', {})),
            data['embedding'],
            data['strategy'],
            data['success'],
            data['reward'],
            data.get('novelty_score', 0.5),
            data.get('importance', 0.5)
        ))

    def find_similar(self, embedding: List[float], limit: int = 10, filters: Dict = None) -> List[Dict]:
        filters = filters or {}
        sql = "SELECT *, embedding <=> %s::vector as distance FROM learning.experiences WHERE 1=1"
        params = [embedding]

        if filters.get('success') is not None:
            sql += " AND success = %s"
            params.append(filters['success'])

        if filters.get('min_reward') is not None:
            sql += " AND reward >= %s"
            params.append(filters['min_reward'])

        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params.extend([embedding, limit])

        return self.db.query(sql, tuple(params))

    def get_recent(self, limit: int = 100) -> List[Dict]:
        return self.db.query(
            "SELECT * FROM learning.experiences ORDER BY timestamp DESC LIMIT %s",
            (limit,)
        )

# Singleton instances
_db = None
_strategy_perf = None
_exec_monitor = None
_cost_tracker = None
_experience_memory = None

def get_db() -> LearningDB:
    global _db
    if _db is None:
        _db = LearningDB()
    return _db

def get_strategy_performance() -> StrategyPerformance:
    global _strategy_perf
    if _strategy_perf is None:
        _strategy_perf = StrategyPerformance()
    return _strategy_perf

def get_execution_monitor() -> ExecutionMonitor:
    global _exec_monitor
    if _exec_monitor is None:
        _exec_monitor = ExecutionMonitor()
    return _exec_monitor

def get_cost_tracker() -> CostTracker:
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker

def get_experience_memory() -> ExperienceMemory:
    global _experience_memory
    if _experience_memory is None:
        _experience_memory = ExperienceMemory()
    return _experience_memory
