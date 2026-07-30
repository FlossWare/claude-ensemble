"""
Flask Blueprint for Mixture of Agents (MoA) API.

Endpoints
---------
POST /moa/query     Run a MoA query with optional custom proposers/aggregators.
GET  /moa/models    List available free models suitable for MoA.
GET  /moa/health    Health check for the MoA subsystem.

Registration:
    from tools.moa_blueprint import moa_bp
    app.register_blueprint(moa_bp)

Created: 2026-07-26
"""

import logging
from flask import Blueprint, request, jsonify

from tools.mixture_of_agents import (
    MixtureOfAgents,
    list_available_free_models,
    DEFAULT_PROPOSERS,
    DEFAULT_AGGREGATORS,
    DEFAULT_ARBITER,
    _fetch_api_key,
)

logger = logging.getLogger(__name__)

moa_bp = Blueprint('moa', __name__, url_prefix='/moa')

# ---------------------------------------------------------------------------
# Request validation helpers
# ---------------------------------------------------------------------------

_MAX_PROMPT_LENGTH = 50_000  # characters
_MAX_MODELS = 10  # per role


def _validate_model_list(models, role_name: str) -> tuple:
    """Validate a list of model identifiers.

    Returns (validated_list, error_message).  error_message is None on success.
    """
    if models is None:
        return None, None

    if not isinstance(models, list):
        return None, f'{role_name} must be a list of model identifiers'

    if len(models) > _MAX_MODELS:
        return None, f'{role_name} exceeds maximum of {_MAX_MODELS} models'

    if len(models) == 0:
        return None, f'{role_name} must not be empty'

    for m in models:
        if not isinstance(m, str) or not m.strip():
            return None, f'{role_name} contains invalid entry: {m!r}'

    return [m.strip() for m in models], None


# ---------------------------------------------------------------------------
# POST /moa/query
# ---------------------------------------------------------------------------

@moa_bp.route('/query', methods=['POST'])
def moa_query():
    """Run a Mixture-of-Agents query.

    Request body (JSON):
        prompt       (str, required):  The question or task.
        system       (str, optional):  System prompt for all models.
        proposers    (list, optional): Layer 1 model identifiers.
        aggregators  (list, optional): Layer 2 model identifiers.
        arbiter      (str, optional):  Final synthesis model.
        max_tokens   (int, optional):  Max tokens per response (default 4096).
        temperature  (float, optional): Sampling temperature (default 0.7).
        num_layers   (int, optional):  Aggregation layers 2-4 (default 2).

    Response (JSON):
        answer           (str):   The final synthesised answer.
        models_used      (int):   Total models invoked.
        total_duration_ms (int):  Wall-clock time in milliseconds.
        layer1           (list):  Per-model Layer 1 outputs.
        layer2           (list):  Per-model Layer 2 outputs.
        synthesis        (dict):  Arbiter output details.
        error            (str|null): Error message if partial failure.

    Status codes:
        200  Success (answer may still note partial failures in error field).
        400  Bad request (missing/invalid parameters).
        500  Internal server error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({'error': 'prompt is required and must be non-empty'}), 400

    if len(prompt) > _MAX_PROMPT_LENGTH:
        return jsonify({
            'error': f'prompt exceeds maximum length of {_MAX_PROMPT_LENGTH} characters',
        }), 400

    # Validate optional model lists
    proposers, err = _validate_model_list(data.get('proposers'), 'proposers')
    if err:
        return jsonify({'error': err}), 400

    aggregators, err = _validate_model_list(data.get('aggregators'), 'aggregators')
    if err:
        return jsonify({'error': err}), 400

    arbiter = data.get('arbiter')
    if arbiter is not None:
        if not isinstance(arbiter, str) or not arbiter.strip():
            return jsonify({'error': 'arbiter must be a non-empty string'}), 400
        arbiter = arbiter.strip()

    max_tokens = data.get('max_tokens', 4096)
    if not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 32768:
        return jsonify({
            'error': 'max_tokens must be an integer between 1 and 32768',
        }), 400

    temperature = data.get('temperature', 0.7)
    if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2.0:
        return jsonify({
            'error': 'temperature must be a number between 0.0 and 2.0',
        }), 400

    num_layers = data.get('num_layers', 2)
    if not isinstance(num_layers, int) or num_layers < 2 or num_layers > 4:
        return jsonify({
            'error': 'num_layers must be an integer between 2 and 4',
        }), 400

    system = data.get('system')
    if system is not None and not isinstance(system, str):
        return jsonify({'error': 'system must be a string'}), 400

    try:
        moa = MixtureOfAgents(
            proposers=proposers,
            aggregators=aggregators,
            arbiter=arbiter,
            max_tokens=max_tokens,
            temperature=float(temperature),
            system=system,
            num_layers=num_layers,
        )
        result = moa.query(prompt)

        status = 200 if result.answer else 502
        return jsonify(result.to_dict()), status

    except RuntimeError as exc:
        logger.error('MoA query failed (RuntimeError): %s', exc)
        return jsonify({'error': 'Configuration error. Check server logs for details.'}), 500
    except Exception as exc:
        logger.exception('MoA query failed unexpectedly')
        return jsonify({'error': 'Internal server error. Check server logs for details.'}), 500


# ---------------------------------------------------------------------------
# GET /moa/models
# ---------------------------------------------------------------------------

@moa_bp.route('/models', methods=['GET'])
def moa_models():
    """List available free models for MoA.

    Response (JSON):
        models (list): Each entry has model, params, strength.
        defaults (dict): Current default proposers, aggregators, arbiter.
    """
    return jsonify({
        'models': list_available_free_models(),
        'defaults': {
            'proposers': list(DEFAULT_PROPOSERS),
            'aggregators': list(DEFAULT_AGGREGATORS),
            'arbiter': DEFAULT_ARBITER,
        },
    })


# ---------------------------------------------------------------------------
# GET /moa/health
# ---------------------------------------------------------------------------

@moa_bp.route('/health', methods=['GET'])
def moa_health():
    """Health check for the MoA subsystem.

    Verifies that the API key can be fetched.  Does NOT make a live model
    call (use /moa/query for that).

    Response (JSON):
        status   (str): "healthy" or "degraded".
        api_key  (bool): Whether the API key is available.
        defaults (dict): Current default configuration.
    """
    api_key_ok = False
    try:
        key = _fetch_api_key()
        api_key_ok = bool(key)
    except Exception as exc:
        logger.warning('Health check: API key fetch failed: %s', exc)

    status = 'healthy' if api_key_ok else 'degraded'

    return jsonify({
        'status': status,
        'api_key': api_key_ok,
        'defaults': {
            'proposers': list(DEFAULT_PROPOSERS),
            'aggregators': list(DEFAULT_AGGREGATORS),
            'arbiter': DEFAULT_ARBITER,
            'num_layers': 2,
        },
    })
