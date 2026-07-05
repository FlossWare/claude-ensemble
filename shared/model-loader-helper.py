#!/usr/bin/env python3
"""
Model Loader Helper - Python subprocess interface for loading sklearn .pkl models
Used by shared/model-loader.js to predict with trained models

CACHING IMPLEMENTATION:
- Models cached in-memory for 30 minutes (CACHE_TTL_MS)
- Persistent process mode: run as daemon, process requests via stdin/stdout
- Supports both CLI mode (one-shot) and daemon mode (persistent)
"""
import sys
import json
import pickle
import numpy as np
from pathlib import Path
import re
import warnings
import time
warnings.filterwarnings('ignore')

MODEL_DIR = Path.home() / '.claude' / 'learning'

# In-memory model cache
# Structure: {model_name: {'model': <loaded_model>, 'expires_at': <timestamp>}}
MODEL_CACHE = {}
CACHE_TTL_MS = 30 * 60 * 1000  # 30 minutes in milliseconds

def load_model(model_name, use_cache=True):
    """Load a pickled model from ~/.claude/learning/ (with caching)"""
    # Check cache first
    if use_cache and model_name in MODEL_CACHE:
        cached = MODEL_CACHE[model_name]
        if time.time() * 1000 < cached['expires_at']:
            # Cache hit - return cached model
            return cached['model']
        else:
            # Cache expired - remove from cache
            del MODEL_CACHE[model_name]

    # Validate model_name to prevent path traversal attacks
    # Only allow alphanumeric, underscores, and hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', model_name):
        print(json.dumps({'error': f'Invalid model name: {model_name}. Only alphanumeric, underscore, and hyphen characters allowed.'}), file=sys.stderr)
        return None

    model_path = MODEL_DIR / f"{model_name}.pkl"

    # Verify the resolved path is actually inside MODEL_DIR
    try:
        resolved_path = model_path.resolve()
        resolved_model_dir = MODEL_DIR.resolve()
        # Check if resolved path starts with resolved model dir (handles symlinks)
        if not str(resolved_path).startswith(str(resolved_model_dir)):
            print(json.dumps({'error': f'Path traversal attempt detected: {model_name}'}), file=sys.stderr)
            return None
    except Exception as e:
        print(json.dumps({'error': f'Path validation failed: {str(e)}'}), file=sys.stderr)
        return None

    if not model_path.exists():
        return None
    try:
        # Load model from disk
        load_start = time.time()
        with open(model_path, 'rb') as f:
            loaded_model = pickle.load(f)
        load_time_ms = (time.time() - load_start) * 1000

        # Cache the loaded model
        if use_cache:
            MODEL_CACHE[model_name] = {
                'model': loaded_model,
                'expires_at': time.time() * 1000 + CACHE_TTL_MS,
                'loaded_at': time.time() * 1000,
                'load_time_ms': load_time_ms
            }

        return loaded_model
    except Exception as e:
        print(json.dumps({'error': f'Failed to load {model_name}: {str(e)}'}), file=sys.stderr)
        return None

def predict(model_name, features):
    """
    Load model and predict
    features: dict or list depending on model type
    """
    loaded = load_model(model_name)
    if loaded is None:
        return {'error': f'Model {model_name} not found'}

    try:
        # Handle dict-based model containers (e.g., {'duration_model': ..., 'confidence_model': ...})
        if isinstance(loaded, dict):
            # Check if it has training_stats to determine structure
            if 'training_stats' in loaded:
                # Multi-model structure - look for main 'model' key first
                if 'model' in loaded and hasattr(loaded['model'], 'predict'):
                    feature_array = prepare_features(model_name, features, loaded['model'])
                    return predict_with_model(loaded['model'], feature_array)

                # Fallback: predict with all sub-models that have predict
                results = {}
                for key, model in loaded.items():
                    if key in ['training_stats', 'class_weights', 'training_date', 'accuracy', 'precision', 'recall', 'f1', 'feature_importances', 'training_samples', 'test_samples']:
                        continue
                    if not hasattr(model, 'predict'):
                        continue
                    feature_array = prepare_features(model_name, features, model)
                    pred = model.predict(feature_array)[0]
                    results[key.replace('_model', '')] = float(pred) if isinstance(pred, (np.floating, float)) else int(pred)

                if results:
                    return {'predictions': results}
                else:
                    return {'error': 'No predictive models found in dict'}
            else:
                # Simple dict - try to find a model
                for key, model in loaded.items():
                    # Skip non-model entries
                    if not hasattr(model, 'predict'):
                        continue
                    feature_array = prepare_features(model_name, features, model)
                    return predict_with_model(model, feature_array)
                return {'error': 'No predictive model found in dict'}

        # Direct model object
        elif hasattr(loaded, 'predict'):
            feature_array = prepare_features(model_name, features, loaded)
            return predict_with_model(loaded, feature_array)

        else:
            return {'error': f'Unknown model structure: {type(loaded).__name__}'}

    except Exception as e:
        return {'error': f'Prediction failed: {str(e)}'}

def predict_with_model(model, feature_array):
    """Helper to predict with a single model"""
    if hasattr(model, 'predict_proba'):
        # Classifier with probabilities
        prediction = model.predict(feature_array)[0]
        probabilities = model.predict_proba(feature_array)[0]
        return {
            'prediction': int(prediction) if isinstance(prediction, np.integer) else prediction,
            'probabilities': probabilities.tolist(),
            'confidence': float(max(probabilities))
        }
    elif hasattr(model, 'predict'):
        # Regressor or classifier without probabilities
        prediction = model.predict(feature_array)[0]
        return {
            'prediction': float(prediction) if isinstance(prediction, (np.floating, float)) else int(prediction)
        }
    else:
        return {'error': 'Model has no predict method'}

def prepare_features(model_name, features_dict, model=None):
    """
    Convert feature dict to numpy array in expected order for each model
    This is model-specific and may need updates as models are retrained
    """
    # If model has feature_names_in_, use that (ALWAYS prefer model metadata)
    if model and hasattr(model, 'feature_names_in_'):
        order = model.feature_names_in_.tolist()
        return np.array([[features_dict.get(k, 0) for k in order]])

    # Common feature orderings (can be extended) - ONLY used if model lacks feature_names_in_
    feature_orders = {
        'complexity_estimator': ['prompt_length', 'word_count', 'num_implement', 'num_fix', 'num_review',
                                'num_create', 'num_update', 'num_analyze', 'num_test', 'num_refactor',
                                'file_mentions', 'code_blocks', 'has_java', 'has_python', 'has_javascript',
                                'has_bug', 'has_error', 'has_performance', 'has_security', 'num_questions',
                                'num_exclamations'],
        'bug_predictor': ['message_length', 'has_bugfix_keywords', 'has_wip_keywords', 'has_tmp_keywords', 'hour_of_day', 'day_of_week', 'files_changed', 'has_tests', 'message_capitalized', 'has_issue_reference'],
        'cost_optimizer': ['input_tokens', 'output_tokens', 'model_tier', 'duration_ms'],
        'performance_optimizer': ['cpu_usage', 'memory_mb', 'io_operations', 'network_calls'],
        'worker_predictor': ['task_complexity', 'task_duration_estimate', 'available_workers'],
        'team_velocity_predictor': ['sprint_points', 'team_size', 'completed_stories', 'carry_over'],
        'tech_debt_quantifier': ['code_smells', 'duplications', 'complexity', 'coverage'],
        'dependency_risk_analyzer': ['num_dependencies', 'outdated_count', 'vulnerability_count', 'license_risk'],
        'merge_conflict_predictor': ['lines_changed', 'files_touched', 'num_authors', 'branch_age_days'],
        'resource_usage_predictor': ['concurrent_tasks', 'avg_task_complexity', 'worker_count'],
        'intent_predictor': ['query_length', 'num_technical_terms', 'num_questions', 'sentiment'],
    }

    if model_name in feature_orders:
        order = feature_orders[model_name]
        return np.array([[features_dict.get(k, 0) for k in order]])
    else:
        # Fallback: alphabetical order
        keys = sorted(features_dict.keys())
        return np.array([[features_dict[k] for k in keys]])

def list_models():
    """List all available .pkl models"""
    models = [f.stem for f in MODEL_DIR.glob('*.pkl')]
    return {'models': sorted(models), 'count': len(models)}

def model_info(model_name):
    """Get information about a model"""
    model = load_model(model_name)
    if model is None:
        return {'error': f'Model {model_name} not found'}

    info = {
        'name': model_name,
        'type': type(model).__name__,
        'module': type(model).__module__,
    }

    # Try to get model-specific info
    if hasattr(model, 'n_features_in_'):
        info['n_features'] = model.n_features_in_
    if hasattr(model, 'classes_'):
        info['classes'] = model.classes_.tolist() if hasattr(model.classes_, 'tolist') else list(model.classes_)
    if hasattr(model, 'feature_names_in_'):
        info['feature_names'] = model.feature_names_in_.tolist()
    if hasattr(model, 'coef_'):
        info['has_coefficients'] = True
    if hasattr(model, 'feature_importances_'):
        info['has_feature_importances'] = True
        info['feature_importances'] = model.feature_importances_.tolist()

    return info

def cache_stats():
    """Get cache statistics"""
    now = time.time() * 1000
    cached_models = []

    for model_name, cached in MODEL_CACHE.items():
        cached_models.append({
            'name': model_name,
            'loaded_at': cached['loaded_at'],
            'expires_at': cached['expires_at'],
            'ttl_remaining_ms': max(0, cached['expires_at'] - now),
            'load_time_ms': cached.get('load_time_ms', 0)
        })

    return {
        'cached_models': len(MODEL_CACHE),
        'cache_ttl_ms': CACHE_TTL_MS,
        'models': cached_models
    }

def clear_cache():
    """Clear all cached models"""
    count = len(MODEL_CACHE)
    MODEL_CACHE.clear()
    return {'cleared': count, 'message': f'Cleared {count} cached models'}

def main():
    """CLI interface for model operations"""
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: model-loader-helper.py <command> [args...]'}))
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == 'list':
            result = list_models()
        elif command == 'info':
            if len(sys.argv) < 3:
                result = {'error': 'Usage: model-loader-helper.py info <model_name>'}
            else:
                result = model_info(sys.argv[2])
        elif command == 'predict':
            if len(sys.argv) < 4:
                result = {'error': 'Usage: model-loader-helper.py predict <model_name> <features_json>'}
            else:
                model_name = sys.argv[2]
                features = json.loads(sys.argv[3])
                result = predict(model_name, features)
        elif command == 'cache-stats':
            result = cache_stats()
        elif command == 'clear-cache':
            result = clear_cache()
        elif command == 'daemon':
            # Persistent mode - process requests from stdin
            run_daemon()
            return
        else:
            result = {'error': f'Unknown command: {command}'}

        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)

def run_daemon():
    """Run in daemon mode - process requests from stdin"""
    # Send ready signal
    print(json.dumps({'status': 'ready'}))
    sys.stdout.flush()

    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            command = request.get('command')

            if command == 'predict':
                model_name = request.get('model_name')
                features = request.get('features')
                result = predict(model_name, features)
            elif command == 'list':
                result = list_models()
            elif command == 'info':
                model_name = request.get('model_name')
                result = model_info(model_name)
            elif command == 'cache-stats':
                result = cache_stats()
            elif command == 'clear-cache':
                result = clear_cache()
            elif command == 'shutdown':
                result = {'status': 'shutdown'}
                print(json.dumps(result))
                sys.stdout.flush()
                break
            else:
                result = {'error': f'Unknown command: {command}'}

            print(json.dumps(result))
            sys.stdout.flush()

        except Exception as e:
            print(json.dumps({'error': str(e)}))
            sys.stdout.flush()

if __name__ == '__main__':
    main()
