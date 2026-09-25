"""GA Config Loader - Loads evolved configs into the orchestrator.

Reads best solutions from ga.best_solutions and applies them to:
1. Thompson Sampling priors (routing-weights → strategy_performance)
2. Consensus voting parameters (consensus-thresholds → app config)
3. Retry policies per provider (retry-policy → app config)

Called at API startup or on-demand via /ga/apply endpoint.

Designed to run ON aio-01 inside the orchestrator. For remote use,
call via REST: POST /ga/apply
"""

import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Task type mapping from GA gene names to DB strategy names
TASK_TYPE_MAP = {
    'code_review': 'code_review',
    'bug_fix': 'bug_fix',
    'research': 'research',
    'summarization': 'summarization',
    'code_generation': 'code_generation',
    'analysis': 'analysis',
    'creative_writing': 'creative_writing',
    'reasoning': 'reasoning',
}


def load_evolved_configs(conn) -> Dict:
    """Load all GA-evolved configs from ga.best_solutions.

    Returns dict of {use_case: {chromosome, fitness, fitness_details}}.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT use_case, chromosome, fitness, fitness_details
        FROM ga.best_solutions
        WHERE fitness > 0
        ORDER BY fitness DESC
    """)
    configs = {}
    for row in cursor.fetchall():
        configs[row[0]] = {
            'chromosome': row[1],
            'fitness': float(row[2]) if row[2] else 0,
            'fitness_details': row[3],
        }
    cursor.close()
    logger.info(f"Loaded {len(configs)} evolved GA configs")
    return configs


def apply_routing_priors(conn, routing_config: Dict) -> int:
    """Apply evolved Thompson Sampling priors to strategy_performance.

    The routing-weights GA evolves optimal (alpha, beta) per model per task.
    This updates the bandit state so Thompson Sampling starts from evolved
    priors instead of uniform Beta(1,1).

    Returns number of rows updated.
    """
    chromosome = routing_config.get('chromosome', {})
    if isinstance(chromosome, str):
        chromosome = json.loads(chromosome)

    updated = 0
    cursor = conn.cursor()

    for model_name, task_priors in chromosome.items():
        if not isinstance(task_priors, dict):
            continue
        for task_type, prior in task_priors.items():
            if not isinstance(prior, dict):
                continue
            alpha = prior.get('alpha', 1.0)
            beta_val = prior.get('beta', 1.0)

            strategy_key = f"{model_name}:{task_type}"

            cursor.execute("""
                INSERT INTO learning.strategy_performance
                    (strategy, alpha, beta, successes, failures, total_reward, avg_reward)
                VALUES (%s, %s, %s, 0, 0, 0, 0)
                ON CONFLICT (strategy) DO UPDATE SET
                    alpha = GREATEST(learning.strategy_performance.alpha, %s),
                    beta = LEAST(learning.strategy_performance.beta, %s),
                    last_updated = NOW()
            """, (strategy_key, alpha, beta_val, alpha, beta_val))
            updated += 1

    conn.commit()
    cursor.close()
    logger.info(f"Applied {updated} routing priors from GA evolution")
    return updated


def get_retry_config(conn, provider: str) -> Optional[Dict]:
    """Get evolved retry config for a specific provider.

    Returns None if no evolved config exists.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT chromosome FROM ga.best_solutions
        WHERE use_case = 'retry-policy' AND fitness > 0
    """)
    row = cursor.fetchone()
    cursor.close()

    if not row:
        return None

    chromosome = row[0]
    if isinstance(chromosome, str):
        chromosome = json.loads(chromosome)

    return chromosome.get(provider)


def get_consensus_config(conn, decision_type: str) -> Optional[Dict]:
    """Get evolved consensus config for a specific decision type.

    Returns None if no evolved config exists.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT chromosome FROM ga.best_solutions
        WHERE use_case = 'consensus-thresholds' AND fitness > 0
    """)
    row = cursor.fetchone()
    cursor.close()

    if not row:
        return None

    chromosome = row[0]
    if isinstance(chromosome, str):
        chromosome = json.loads(chromosome)

    return chromosome.get(decision_type)


def get_workflow_config(conn, workflow_type: str) -> Optional[Dict]:
    """Get evolved workflow config for a specific workflow type."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT chromosome FROM ga.best_solutions
        WHERE use_case = 'workflow-config' AND fitness > 0
    """)
    row = cursor.fetchone()
    cursor.close()

    if not row:
        return None

    chromosome = row[0]
    if isinstance(chromosome, str):
        chromosome = json.loads(chromosome)

    return chromosome.get(workflow_type)


def get_embedding_config(conn, task: str) -> Optional[Dict]:
    """Get evolved embedding/chunking config for a retrieval task."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT chromosome FROM ga.best_solutions
        WHERE use_case = 'embedding-chunking' AND fitness > 0
    """)
    row = cursor.fetchone()
    cursor.close()

    if not row:
        return None

    chromosome = row[0]
    if isinstance(chromosome, str):
        chromosome = json.loads(chromosome)

    return chromosome.get(task)


def apply_all(conn) -> Dict:
    """Apply all evolved configs at once. Call at API startup.

    Returns summary of what was applied.
    """
    configs = load_evolved_configs(conn)
    summary = {'loaded': len(configs), 'applied': {}}

    if 'routing-weights' in configs:
        count = apply_routing_priors(conn, configs['routing-weights'])
        summary['applied']['routing_priors'] = count

    for use_case in ['consensus-thresholds', 'retry-policy',
                     'workflow-config', 'embedding-chunking']:
        if use_case in configs:
            summary['applied'][use_case] = {
                'fitness': configs[use_case]['fitness'],
                'status': 'loaded_to_cache',
            }

    logger.info(f"GA config apply complete: {summary}")
    return summary
