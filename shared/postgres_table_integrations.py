#!/usr/bin/env python3
"""
PostgreSQL Table Integration Wrappers (Python)

Wires unused PostgreSQL tables into the appropriate integration points:
- learning.diversity_violations: Model selection diversity enforcement
- learning.procedural_rules: Pattern/rule extraction from executions
- monitoring.execution_log: Detailed task execution tracking
- monitoring.model_tuning: Model parameter tuning history

Created: 2026-07-01 (Issue #251-254)
"""

import os
import json
import hashlib
import math
from datetime import datetime
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection
DB_CONFIG = {
    'host': os.getenv('PGHOST', 'aio-01'),
    'port': int(os.getenv('PGPORT', '5433')),
    'database': os.getenv('PGDATABASE', 'learning'),
    'user': os.getenv('PGUSER', os.getenv('USER')),
    'password': os.getenv('PGPASSWORD')
}

def get_connection():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)

# ============================================================================
# DIVERSITY VIOLATIONS
# ============================================================================

def record_diversity_violation(violation: Dict[str, Any]) -> None:
    """
    Record diversity violation when model usage exceeds quotas

    Args:
        violation: {
            'violation_type': 'floor_breach' | 'ceiling_breach' | 'entropy_collapse',
            'model': Model name,
            'current_usage_pct': Current usage percentage (0-100),
            'quota_limit_pct': Quota limit that was breached (0-100),
            'diversity_entropy': Shannon entropy of distribution (optional),
            'action_taken': 'forced_rotation' | 'banned_temporarily' | 'warning_only'
        }

    Example:
        record_diversity_violation({
            'violation_type': 'ceiling_breach',
            'model': 'opus',
            'current_usage_pct': 72,
            'quota_limit_pct': 70,
            'diversity_entropy': 0.45,
            'action_taken': 'forced_rotation'
        })
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO learning.diversity_violations
            (violation_type, model, current_usage_pct, quota_limit_pct, diversity_entropy, action_taken)
            VALUES (%(violation_type)s, %(model)s, %(current_usage_pct)s, %(quota_limit_pct)s,
                    %(diversity_entropy)s, %(action_taken)s)
        """, violation)
        conn.commit()
    except Exception as e:
        print(f"Failed to record diversity violation: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def query_diversity_violations(filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Query recent diversity violations

    Args:
        filters: {
            'model': Filter by model (optional),
            'violation_type': Filter by violation type (optional),
            'limit': Max results (default: 20)
        }

    Returns:
        List of violation records
    """
    if filters is None:
        filters = {}

    model = filters.get('model')
    violation_type = filters.get('violation_type')
    limit = filters.get('limit', 20)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    query = "SELECT * FROM learning.diversity_violations WHERE 1=1"
    params = []

    if model:
        params.append(model)
        query += f" AND model = ${len(params)}"

    if violation_type:
        params.append(violation_type)
        query += f" AND violation_type = ${len(params)}"

    params.append(limit)
    query += f" ORDER BY timestamp DESC LIMIT ${len(params)}"

    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        return [dict(row) for row in results]
    except Exception as e:
        print(f"Failed to query diversity violations: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def calculate_diversity_entropy(distribution: Dict[str, int]) -> float:
    """
    Calculate diversity entropy from model usage distribution
    Returns Shannon entropy (higher = more diverse)

    Args:
        distribution: Model usage counts {'opus': 50, 'sonnet': 30, 'haiku': 20}

    Returns:
        Entropy value (0 = all one model, higher = more diverse)

    Example:
        entropy = calculate_diversity_entropy({'opus': 70, 'sonnet': 20, 'haiku': 10})
        # entropy ~= 0.96 (low diversity)

        better_entropy = calculate_diversity_entropy({'opus': 33, 'sonnet': 33, 'haiku': 34})
        # better_entropy ~= 1.58 (high diversity)
    """
    total = sum(distribution.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in distribution.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)

    return entropy

# ============================================================================
# PROCEDURAL RULES
# ============================================================================

def record_procedural_rule(rule: Dict[str, Any]) -> None:
    """
    Extract and store procedural rule from successful execution

    Args:
        rule: {
            'condition': Condition dict (JSONB),
            'action': Action to take when condition matches,
            'confidence': Confidence score (0-1),
            'evidence_count': Number of observations (default: 1)
        }

    Example:
        record_procedural_rule({
            'condition': {
                'task_type': 'code_generation',
                'language': 'java',
                'framework': 'maven'
            },
            'action': 'use_deepseek_coder',
            'confidence': 0.92,
            'evidence_count': 5
        })
    """
    condition = rule['condition']
    action = rule['action']
    confidence = rule['confidence']
    evidence_count = rule.get('evidence_count', 1)

    # Create deterministic hash
    condition_hash = hashlib.sha256(
        json.dumps(condition, sort_keys=True).encode()
    ).hexdigest()[:16]

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO learning.procedural_rules
            (condition_hash, condition, action, confidence, evidence_count)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (condition_hash, action) DO UPDATE SET
                confidence = GREATEST(procedural_rules.confidence, EXCLUDED.confidence),
                evidence_count = procedural_rules.evidence_count + EXCLUDED.evidence_count,
                last_updated = NOW()
        """, [condition_hash, json.dumps(condition), action, confidence, evidence_count])
        conn.commit()
    except Exception as e:
        print(f"Failed to record procedural rule: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def query_procedural_rules(condition: Dict[str, Any], min_confidence: float = 0.7) -> List[Dict]:
    """
    Query procedural rules matching condition

    Args:
        condition: Condition to match
        min_confidence: Minimum confidence threshold

    Returns:
        List of matching rules sorted by confidence
    """
    condition_hash = hashlib.sha256(
        json.dumps(condition, sort_keys=True).encode()
    ).hexdigest()[:16]

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Try exact match first
        cursor.execute("""
            SELECT condition, action, confidence, evidence_count, last_updated
            FROM learning.procedural_rules
            WHERE condition_hash = %s AND confidence >= %s
            ORDER BY confidence DESC, evidence_count DESC
        """, [condition_hash, min_confidence])

        results = cursor.fetchall()
        if results:
            return [dict(row) for row in results]

        # Fallback: JSONB containment
        cursor.execute("""
            SELECT condition, action, confidence, evidence_count, last_updated
            FROM learning.procedural_rules
            WHERE condition @> %s::jsonb AND confidence >= %s
            ORDER BY confidence DESC, evidence_count DESC
            LIMIT 10
        """, [json.dumps(condition), min_confidence])

        return [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        print(f"Failed to query procedural rules: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# EXECUTION LOG
# ============================================================================

def log_execution(execution: Dict[str, Any]) -> None:
    """
    Log detailed task execution

    Args:
        execution: {
            'model': Model used,
            'model_role': 'worker' | 'arbiter' | 'verifier' (default: 'worker'),
            'workflow': Workflow name (optional),
            'task_type': Task category (optional),
            'phase': Execution phase (optional),
            'label': Task label (optional),
            'parameters': Task parameters dict (optional),
            'quality_score': Quality score 0-1 (optional),
            'confidence': Confidence 0-1 (optional),
            'consensus_score': Consensus 0-1 (optional),
            'was_selected': Was selected? (default: False),
            'input_tokens': Input tokens (default: 0),
            'output_tokens': Output tokens (default: 0),
            'cost_usd': Cost in USD (default: 0.0),
            'duration_ms': Duration in ms (default: 0),
            'outcome': 'SUCCESS' | 'FAILURE' | 'PARTIAL' | 'unknown' (default: 'unknown'),
            'outcome_notes': Notes (optional),
            'request_hash': Request hash (optional),
            'response_hash': Response hash (optional),
            'error': Error message (optional),
            'run_id': Run ID (optional),
            'execution_id': Execution ID (optional),
            ... and more fields from monitoring.execution_log schema
        }
    """
    defaults = {
        'model_role': 'worker',
        'parameters': {},
        'was_selected': False,
        'input_tokens': 0,
        'output_tokens': 0,
        'cost_usd': 0.0,
        'duration_ms': 0,
        'outcome': 'unknown',
        'model_count': 1,
        'selection_method': 'static'
    }

    execution = {**defaults, **execution}

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO monitoring.execution_log
            (model, model_role, workflow, task_type, phase, label, parameters,
             quality_score, confidence, consensus_score, was_selected,
             input_tokens, output_tokens, cost_usd, duration_ms, outcome, outcome_notes,
             request_hash, response_hash, error, run_id, execution_id,
             task_description, worker_models, arbiter_model, model_count,
             strategy, diversity_score, total_input_tokens, total_output_tokens,
             total_cost_usd, per_model_costs, per_model_durations, selected_model,
             session_id, parent_execution_id, counterfactual_scores, selection_method)
            VALUES (
                %(model)s, %(model_role)s, %(workflow)s, %(task_type)s, %(phase)s, %(label)s, %(parameters)s,
                %(quality_score)s, %(confidence)s, %(consensus_score)s, %(was_selected)s,
                %(input_tokens)s, %(output_tokens)s, %(cost_usd)s, %(duration_ms)s, %(outcome)s, %(outcome_notes)s,
                %(request_hash)s, %(response_hash)s, %(error)s, %(run_id)s, %(execution_id)s,
                %(task_description)s, %(worker_models)s, %(arbiter_model)s, %(model_count)s,
                %(strategy)s, %(diversity_score)s, %(total_input_tokens)s, %(total_output_tokens)s,
                %(total_cost_usd)s, %(per_model_costs)s, %(per_model_durations)s, %(selected_model)s,
                %(session_id)s, %(parent_execution_id)s, %(counterfactual_scores)s, %(selection_method)s
            )
        """, {
            **execution,
            'parameters': json.dumps(execution.get('parameters', {})),
            'worker_models': json.dumps(execution.get('worker_models')) if execution.get('worker_models') else None,
            'per_model_costs': json.dumps(execution.get('per_model_costs')) if execution.get('per_model_costs') else None,
            'per_model_durations': json.dumps(execution.get('per_model_durations')) if execution.get('per_model_durations') else None,
            'counterfactual_scores': json.dumps(execution.get('counterfactual_scores')) if execution.get('counterfactual_scores') else None
        })
        conn.commit()
    except Exception as e:
        print(f"Failed to log execution: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def query_execution_log(filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Query execution log with filters

    Args:
        filters: {
            'model': Filter by model (optional),
            'workflow': Filter by workflow (optional),
            'outcome': Filter by outcome (optional),
            'limit': Max results (default: 100)
        }

    Returns:
        List of execution records
    """
    if filters is None:
        filters = {}

    model = filters.get('model')
    workflow = filters.get('workflow')
    outcome = filters.get('outcome')
    limit = filters.get('limit', 100)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    query = "SELECT * FROM monitoring.execution_log WHERE 1=1"
    params = []

    if model:
        params.append(model)
        query += f" AND model = ${len(params)}"

    if workflow:
        params.append(workflow)
        query += f" AND workflow = ${len(params)}"

    if outcome:
        params.append(outcome)
        query += f" AND outcome = ${len(params)}"

    params.append(limit)
    query += f" ORDER BY timestamp DESC LIMIT ${len(params)}"

    try:
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Failed to query execution log: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# MODEL TUNING
# ============================================================================

def record_model_tuning(tuning: Dict[str, Any]) -> None:
    """
    Record model tuning parameters and performance

    Args:
        tuning: {
            'model': Model name,
            'task_type': Task type,
            'optimal_params': Optimal parameters dict,
            'avg_quality': Average quality (default: 0.0),
            'avg_confidence': Average confidence (default: 0.0),
            'avg_cost_usd': Average cost (default: 0.0),
            'avg_duration_ms': Average duration (default: 0.0),
            'sample_count': Sample count (default: 0),
            'success_rate': Success rate 0-1 (default: 0.0),
            'selection_rate': Selection rate 0-1 (default: 0.0),
            'quality_trend': Quality trend list (default: []),
            'cost_trend': Cost trend list (default: [])
        }

    Example:
        record_model_tuning({
            'model': 'opus',
            'task_type': 'security_review',
            'optimal_params': {'temperature': 0.3, 'top_p': 0.9},
            'avg_quality': 0.92,
            'sample_count': 50,
            'success_rate': 0.94,
            'quality_trend': [0.85, 0.87, 0.90, 0.92]
        })
    """
    defaults = {
        'avg_quality': 0.0,
        'avg_confidence': 0.0,
        'avg_cost_usd': 0.0,
        'avg_duration_ms': 0.0,
        'sample_count': 0,
        'success_rate': 0.0,
        'selection_rate': 0.0,
        'quality_trend': [],
        'cost_trend': []
    }

    tuning = {**defaults, **tuning}

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO monitoring.model_tuning
            (model, task_type, optimal_params, avg_quality, avg_confidence,
             avg_cost_usd, avg_duration_ms, sample_count, success_rate,
             selection_rate, quality_trend, cost_trend)
            VALUES (%(model)s, %(task_type)s, %(optimal_params)s, %(avg_quality)s, %(avg_confidence)s,
                    %(avg_cost_usd)s, %(avg_duration_ms)s, %(sample_count)s, %(success_rate)s,
                    %(selection_rate)s, %(quality_trend)s, %(cost_trend)s)
            ON CONFLICT (model, task_type) DO UPDATE SET
                optimal_params = EXCLUDED.optimal_params,
                avg_quality = EXCLUDED.avg_quality,
                avg_confidence = EXCLUDED.avg_confidence,
                avg_cost_usd = EXCLUDED.avg_cost_usd,
                avg_duration_ms = EXCLUDED.avg_duration_ms,
                sample_count = EXCLUDED.sample_count,
                success_rate = EXCLUDED.success_rate,
                selection_rate = EXCLUDED.selection_rate,
                quality_trend = EXCLUDED.quality_trend,
                cost_trend = EXCLUDED.cost_trend,
                updated_at = NOW()
        """, {
            **tuning,
            'optimal_params': json.dumps(tuning['optimal_params']),
            'quality_trend': json.dumps(tuning['quality_trend']),
            'cost_trend': json.dumps(tuning['cost_trend'])
        })
        conn.commit()
    except Exception as e:
        print(f"Failed to record model tuning: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def query_model_tuning(filters: Optional[Dict[str, str]] = None) -> List[Dict]:
    """
    Query model tuning history

    Args:
        filters: {
            'model': Filter by model (optional),
            'task_type': Filter by task type (optional)
        }

    Returns:
        List of tuning records
    """
    if filters is None:
        filters = {}

    model = filters.get('model')
    task_type = filters.get('task_type')

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    query = "SELECT * FROM monitoring.model_tuning WHERE 1=1"
    params = []

    if model:
        params.append(model)
        query += f" AND model = ${len(params)}"

    if task_type:
        params.append(task_type)
        query += f" AND task_type = ${len(params)}"

    query += " ORDER BY updated_at DESC"

    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        return [dict(row) for row in results]
    except Exception as e:
        print(f"Failed to query model tuning: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    print("PostgreSQL Table Integration Wrappers")
    print("Usage:")
    print("  from postgres_table_integrations import *")
    print("\nFunctions:")
    print("  - record_diversity_violation(violation)")
    print("  - query_diversity_violations(filters)")
    print("  - calculate_diversity_entropy(distribution)")
    print("  - record_procedural_rule(rule)")
    print("  - query_procedural_rules(condition, min_confidence)")
    print("  - log_execution(execution)")
    print("  - query_execution_log(filters)")
    print("  - record_model_tuning(tuning)")
    print("  - query_model_tuning(filters)")
