"""
MAP-Elites Flask Blueprint - REST API for Quality-Diversity Prompt Evolution

Endpoints:
  POST /evolution/map-elites/start    -- Start a new MAP-Elites run
  GET  /evolution/map-elites/status   -- Check progress + coverage percentage
  GET  /evolution/map-elites/archive  -- Full archive with behavior descriptors
  GET  /evolution/map-elites/best     -- Best per dimension + overall best
  POST /evolution/map-elites/stop     -- Stop the active run
  GET  /evolution/map-elites/history  -- List past MAP-Elites runs

All heavy computation runs in a background thread so the API stays responsive.
Only one MAP-Elites run is active at a time.
"""

import json
import logging
import threading
from pathlib import Path

from flask import Blueprint, request, jsonify

from map_elites import MAPElitesEngine, LINEAGE_PATH

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
map_elites_bp = Blueprint('map_elites', __name__, url_prefix='/evolution/map-elites')

# ---------------------------------------------------------------------------
# Singleton state: one active MAP-Elites run at a time
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_active_engine: MAPElitesEngine = None
_active_thread: threading.Thread = None
_last_error: str = ''


def _is_running() -> bool:
    """Check if a MAP-Elites run is currently active."""
    return _active_thread is not None and _active_thread.is_alive()


def _run_map_elites(engine: MAPElitesEngine, iterations: int, batch_size: int):
    """Background thread target: run MAP-Elites to completion."""
    global _last_error
    try:
        engine.evolve(iterations, batch_size)
        _last_error = ''
    except Exception as e:
        _last_error = str(e)
        logger.error('MAP-Elites run failed: %s', e, exc_info=True)


# ===================================================================
# POST /evolution/map-elites/start
# ===================================================================
@map_elites_bp.route('/start', methods=['POST'])
def start_map_elites():
    """Start a new MAP-Elites quality-diversity evolution run.

    Request body::

        {
            "task":                "code review",   # task type
            "description":         "...",           # optional detailed description
            "iterations":          20,             # number of iterations (default 20)
            "batch_size":          10,             # variants per iteration (default 10)
            "initial_population":  50,             # seed population (default 50)
            "dimensions":          ["length", "style", "specificity"],  # behavior dims
            "seed":                42              # random seed for reproducibility (optional)
        }

    Returns 202 Accepted with the run_id, or 409 if a run is already active.
    """
    global _active_engine, _active_thread, _last_error

    if _is_running():
        return jsonify({
            'error': 'A MAP-Elites run is already active',
            'run_id': _active_engine.run_id if _active_engine else None,
            'iteration': _active_engine.iteration if _active_engine else 0,
        }), 409

    body = request.get_json(force=True) or {}

    task = body.get('task', 'code review')
    description = body.get('description', '')
    iterations = max(1, min(500, int(body.get('iterations', 20))))
    batch_size = max(1, min(50, int(body.get('batch_size', 10))))
    initial_population = max(5, min(200, int(body.get('initial_population', 50))))
    dimensions = body.get('dimensions', ['length', 'style', 'specificity'])
    seed = body.get('seed', None)
    if seed is not None:
        seed = int(seed)

    # Validate dimensions
    valid_dims = {'length', 'style', 'specificity'}
    dimensions = [d for d in dimensions if d in valid_dims]
    if not dimensions:
        dimensions = ['length', 'style', 'specificity']

    with _lock:
        _last_error = ''
        _active_engine = MAPElitesEngine(
            task_type=task,
            task_description=description,
            initial_population=initial_population,
            dimensions=dimensions,
            seed=seed,
        )

        _active_thread = threading.Thread(
            target=_run_map_elites,
            args=(_active_engine, iterations, batch_size),
            daemon=True,
            name=f'me-{_active_engine.run_id}',
        )
        _active_thread.start()

    logger.info(
        'Started MAP-Elites run %s: task=%s pop=%d iter=%d batch=%d',
        _active_engine.run_id, task, initial_population, iterations, batch_size,
    )

    return jsonify({
        'run_id': _active_engine.run_id,
        'task': task,
        'dimensions': dimensions,
        'initial_population': initial_population,
        'iterations': iterations,
        'batch_size': batch_size,
        'status': 'started',
    }), 202


# ===================================================================
# GET /evolution/map-elites/status
# ===================================================================
@map_elites_bp.route('/status', methods=['GET'])
def map_elites_status():
    """Check progress of the active or most recent MAP-Elites run.

    Returns iteration count, coverage percentage, archive stats, LLM metrics.
    """
    if _active_engine is None:
        return jsonify({
            'status': 'no_run',
            'message': 'No MAP-Elites run has been started',
        })

    running = _is_running()
    status = _active_engine.get_status()
    status['running'] = running
    status['status'] = (
        'running' if running
        else ('completed' if not _last_error else 'failed')
    )
    if _last_error:
        status['error'] = _last_error

    return jsonify(status)


# ===================================================================
# GET /evolution/map-elites/archive
# ===================================================================
@map_elites_bp.route('/archive', methods=['GET'])
def map_elites_archive():
    """Get the full archive with all behavior descriptors.

    Returns the complete grid with each cell's individual, fitness,
    and behavior coordinates.
    """
    if _active_engine is None:
        return jsonify({
            'error': 'No MAP-Elites run has been started',
        }), 404

    archive = _active_engine.get_archive()
    archive['run_id'] = _active_engine.run_id
    archive['iteration'] = _active_engine.iteration
    archive['running'] = _is_running()

    return jsonify(archive)


# ===================================================================
# GET /evolution/map-elites/best
# ===================================================================
@map_elites_bp.route('/best', methods=['GET'])
def map_elites_best():
    """Get the best individual overall and best per behavior dimension.

    Works during and after a run.
    """
    if _active_engine is None:
        return jsonify({
            'error': 'No MAP-Elites run has been started',
        }), 404

    best = _active_engine.get_best()
    if best is None:
        return jsonify({
            'error': 'Archive is empty (not yet initialized)',
        }), 404

    per_dimension = _active_engine.get_best_per_dimension()

    return jsonify({
        'run_id': _active_engine.run_id,
        'task_type': _active_engine.task_type,
        'iteration': _active_engine.iteration,
        'running': _is_running(),
        'overall_best': best,
        'best_per_dimension': per_dimension,
        'archive_stats': _active_engine.archive.stats,
    })


# ===================================================================
# POST /evolution/map-elites/stop
# ===================================================================
@map_elites_bp.route('/stop', methods=['POST'])
def stop_map_elites():
    """Stop the active MAP-Elites run gracefully.

    The current batch will complete, then the run stops.
    The archive is preserved.
    """
    if _active_engine is None:
        return jsonify({'error': 'No MAP-Elites run to stop'}), 404

    if not _is_running():
        return jsonify({
            'message': 'MAP-Elites run already finished',
            'run_id': _active_engine.run_id,
            'iteration': _active_engine.iteration,
            'coverage': _active_engine.archive.coverage,
        })

    _active_engine.stopped = True
    logger.info('Stopping MAP-Elites run %s', _active_engine.run_id)

    return jsonify({
        'message': 'Stop signal sent; current batch will complete',
        'run_id': _active_engine.run_id,
        'iteration': _active_engine.iteration,
        'coverage': _active_engine.archive.coverage,
    })


# ===================================================================
# GET /evolution/map-elites/history
# ===================================================================
@map_elites_bp.route('/history', methods=['GET'])
def map_elites_history():
    """List past MAP-Elites runs from the lineage file."""
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
        archive = run_data.get('archive', {})
        archive_stats = archive.get('stats', {})
        summaries.append({
            'run_id': run_id,
            'task_type': run_data.get('task_type', 'unknown'),
            'started_at': run_data.get('started_at', ''),
            'dimensions': run_data.get('dimensions', []),
            'coverage': archive_stats.get('coverage', 0),
            'filled_cells': archive_stats.get('filled_cells', 0),
            'total_cells': archive_stats.get('total_cells', 0),
            'qd_score': archive_stats.get('qd_score', 0),
            'best_fitness': archive_stats.get('best_fitness', 0),
            'avg_fitness': archive_stats.get('avg_fitness', 0),
            'llm_stats': run_data.get('llm_stats', {}),
        })

    summaries.sort(key=lambda s: s.get('started_at', ''), reverse=True)

    return jsonify({
        'runs': summaries,
        'count': len(summaries),
    })
