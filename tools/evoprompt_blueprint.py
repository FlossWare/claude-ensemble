"""
EvoPrompt Flask Blueprint - REST API for LLM-Guided Prompt Evolution

Endpoints:
  POST /evolution/start   -- Start a new LLM-guided evolution run
  GET  /evolution/status   -- Check progress of the active evolution run
  GET  /evolution/best     -- Get the best evolved prompt
  POST /evolution/stop     -- Stop the active evolution run
  GET  /evolution/history  -- List past evolution runs (from lineage file)
  GET  /evolution/lineage/<individual_id> -- Trace an individual's ancestry

All heavy computation runs in a background thread so the API stays responsive.
Only one evolution run is active at a time.
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from flask import Blueprint, request, jsonify

from llm_guided_evolution import (
    LLMGuidedEvolution, LINEAGE_PATH, load_lineage_from_file,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
evolution_bp = Blueprint('evolution', __name__, url_prefix='/evolution')

# ---------------------------------------------------------------------------
# Singleton state: one active evolution run at a time
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_active_engine: LLMGuidedEvolution = None
_active_thread: threading.Thread = None
_last_error: str = ''


def _is_running() -> bool:
    """Check if an evolution run is currently active (thread-safe)."""
    with _lock:
        thread = _active_thread
    return thread is not None and thread.is_alive()


def _run_evolution(engine: LLMGuidedEvolution, generations: int):
    """Background thread target: run evolution to completion."""
    global _last_error
    try:
        engine.evolve(generations)
        with _lock:
            _last_error = ''
    except Exception as e:
        with _lock:
            _last_error = str(e)
        logger.error('Evolution run failed: %s', e, exc_info=True)


# ===================================================================
# POST /evolution/start
# ===================================================================
@evolution_bp.route('/start', methods=['POST'])
def start_evolution():
    """Start a new LLM-guided evolution run.

    Request body::

        {
            "task":            "code review",   # task type
            "description":     "...",           # optional detailed description
            "population":      20,             # population size (default 20)
            "generations":     10,             # number of generations (default 10)
            "mutation_rate":   0.3,            # 0.0-1.0 (default 0.3)
            "elite_fraction":  0.2,            # 0.0-0.5 (default 0.2)
            "tournament_size": 3               # default 3
        }

    Returns 202 Accepted with the run_id, or 409 if a run is already active.
    """
    global _active_engine, _active_thread, _last_error

    body = request.get_json(force=True) or {}

    task = body.get('task', 'code review')
    description = body.get('description', '')
    population = max(4, min(100, int(body.get('population', 20))))
    generations = max(1, min(100, int(body.get('generations', 10))))
    mutation_rate = max(0.0, min(1.0, float(body.get('mutation_rate', 0.3))))
    elite_fraction = max(0.05, min(0.5, float(body.get('elite_fraction', 0.2))))
    tournament_size = max(2, min(10, int(body.get('tournament_size', 3))))

    # Bug fix #1: All shared-state reads and writes under a single lock
    # acquisition to eliminate TOCTOU races between the running check
    # and the engine/thread assignment.
    with _lock:
        if _active_thread is not None and _active_thread.is_alive():
            return jsonify({
                'error': 'An evolution run is already active',
                'run_id': _active_engine.run_id if _active_engine else None,
                'generation': _active_engine.generation if _active_engine else 0,
            }), 409

        _last_error = ''
        _active_engine = LLMGuidedEvolution(
            task_type=task,
            task_description=description,
            population_size=population,
            mutation_rate=mutation_rate,
            elite_fraction=elite_fraction,
            tournament_size=tournament_size,
        )

        _active_thread = threading.Thread(
            target=_run_evolution,
            args=(_active_engine, generations),
            daemon=True,
            name=f'evo-{_active_engine.run_id}',
        )
        _active_thread.start()

        run_id = _active_engine.run_id

    logger.info(
        'Started evolution run %s: task=%s pop=%d gen=%d',
        run_id, task, population, generations,
    )

    return jsonify({
        'run_id': run_id,
        'task': task,
        'population': population,
        'generations': generations,
        'mutation_rate': mutation_rate,
        'status': 'started',
    }), 202


# ===================================================================
# GET /evolution/status
# ===================================================================
@evolution_bp.route('/status', methods=['GET'])
def evolution_status():
    """Check progress of the active or most recent evolution run.

    Returns generation stats, population info, and LLM call metrics.
    """
    # Bug fix #1: snapshot shared state under lock, then release
    with _lock:
        engine = _active_engine
        thread = _active_thread
        error = _last_error

    if engine is None:
        return jsonify({
            'status': 'no_run',
            'message': 'No evolution run has been started',
        })

    running = thread is not None and thread.is_alive()
    status = engine.get_status()
    status['running'] = running
    status['status'] = 'running' if running else ('completed' if not error else 'failed')
    if error:
        status['error'] = error

    return jsonify(status)


# ===================================================================
# GET /evolution/best
# ===================================================================
@evolution_bp.route('/best', methods=['GET'])
def evolution_best():
    """Get the best evolved prompt found so far.

    Works during and after a run.
    """
    with _lock:
        engine = _active_engine
        thread = _active_thread

    if engine is None:
        return jsonify({
            'error': 'No evolution run has been started',
        }), 404

    best = engine.get_best()
    if best is None:
        return jsonify({
            'error': 'No best individual yet (population not seeded)',
        }), 404

    return jsonify({
        'run_id': engine.run_id,
        'task_type': engine.task_type,
        'generation': engine.generation,
        'running': thread is not None and thread.is_alive(),
        'best': best,
    })


# ===================================================================
# POST /evolution/stop
# ===================================================================
@evolution_bp.route('/stop', methods=['POST'])
def stop_evolution():
    """Stop the active evolution run gracefully.

    The current generation will complete, then the run stops.
    Results are preserved.
    """
    with _lock:
        engine = _active_engine
        thread = _active_thread

    if engine is None:
        return jsonify({'error': 'No evolution run to stop'}), 404

    if thread is None or not thread.is_alive():
        return jsonify({
            'message': 'Evolution run already finished',
            'run_id': engine.run_id,
            'generation': engine.generation,
        })

    engine.stopped = True
    logger.info('Stopping evolution run %s', engine.run_id)

    return jsonify({
        'message': 'Stop signal sent; current generation will complete',
        'run_id': engine.run_id,
        'generation': engine.generation,
    })


# ===================================================================
# GET /evolution/history
# ===================================================================
@evolution_bp.route('/history', methods=['GET'])
def evolution_history():
    """List past evolution runs from the lineage file."""
    if not LINEAGE_PATH.exists():
        return jsonify({'runs': [], 'count': 0})

    try:
        with open(LINEAGE_PATH, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return jsonify({'runs': [], 'count': 0})

    runs = data.get('runs', {})
    summaries = []

    for run_id, run_data in runs.items():
        best = run_data.get('best_ever', {})
        gens = run_data.get('generations', {})
        summaries.append({
            'run_id': run_id,
            'task_type': run_data.get('task_type', 'unknown'),
            'started_at': run_data.get('started_at', ''),
            'total_generations': len(gens),
            'best_fitness': best.get('fitness', 0) if best else 0,
            'llm_stats': run_data.get('llm_stats', {}),
        })

    # Sort by start time descending
    summaries.sort(key=lambda s: s.get('started_at', ''), reverse=True)

    return jsonify({
        'runs': summaries,
        'count': len(summaries),
    })


# ===================================================================
# GET /evolution/lineage/<individual_id>
# ===================================================================
@evolution_bp.route('/lineage/<individual_id>', methods=['GET'])
def evolution_lineage(individual_id):
    """Trace the lineage (ancestry) of a specific individual.

    Bug fix #5: Works for active runs (in-memory) and completed runs
    (lineage JSON file).
    """
    with _lock:
        engine = _active_engine

    # Try active engine first (includes file fallback via get_lineage)
    if engine is not None:
        lineage = engine.get_lineage(individual_id)
        if lineage:
            return jsonify({
                'individual_id': individual_id,
                'lineage': lineage,
                'depth': len(lineage),
            })

    # Fall back to file-only lookup for completed runs
    lineage = load_lineage_from_file(individual_id)
    if not lineage:
        return jsonify({
            'error': f'Individual {individual_id} not found',
        }), 404

    return jsonify({
        'individual_id': individual_id,
        'lineage': lineage,
        'depth': len(lineage),
        'source': 'history',
    })
