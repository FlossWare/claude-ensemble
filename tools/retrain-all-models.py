#!/usr/bin/env python3
"""
Retrain all ML models with latest data from PostgreSQL.

Discovers all .pkl files in ~/.claude/learning/predictors/, retrains them with
the latest data from the database, and only saves improvements (no regression).
Logs all results to monitoring.model_retraining table.

Usage:
    python3 tools/retrain-all-models.py                    # Retrain all models
    python3 tools/retrain-all-models.py --models model1,model2  # Retrain specific models
    python3 tools/retrain-all-models.py --force             # Save even if accuracy decreases
    python3 tools/retrain-all-models.py --predictor-dir /path  # Custom model directory
"""

import os
import sys
import glob
import pickle
import argparse
import logging
import json
import copy
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Any, Optional

import psycopg2
import psycopg2.extras
import numpy as np
from sklearn.metrics import accuracy_score, r2_score, mean_squared_error, mean_absolute_error
from sklearn.model_selection import train_test_split


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(log_file: Optional[str] = None) -> logging.Logger:
    """Setup logging configuration with both console and file output."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler
    if log_file is None:
        log_dir = Path.home() / '.claude' / 'logs' / 'model_retraining'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"retrain_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    else:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    logger.info(f"Logging to {log_file}")
    return logger


# ============================================================================
# Database Operations
# ============================================================================

def get_db_connection():
    """Connect to PostgreSQL learning database."""
    try:
        conn = psycopg2.connect(
            dbname='learning',
            user=os.environ.get('PGUSER', 'postgres'),
            password=os.environ.get('PGPASSWORD'),
            host=os.environ.get('PGHOST', 'localhost'),
            port=int(os.environ.get('PGPORT', 5432))
        )
        return conn
    except psycopg2.Error as e:
        raise RuntimeError(f"Database connection failed: {e}")


def ensure_retraining_table(conn) -> None:
    """Create monitoring.model_retraining table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS monitoring.model_retraining (
                id SERIAL PRIMARY KEY,
                model_name VARCHAR(255) NOT NULL,
                model_type VARCHAR(50),
                old_accuracy FLOAT,
                new_accuracy FLOAT,
                accuracy_metric VARCHAR(50),
                training_samples INTEGER,
                test_samples INTEGER,
                old_r2 FLOAT,
                new_r2 FLOAT,
                old_rmse FLOAT,
                new_rmse FLOAT,
                training_duration_seconds FLOAT,
                result VARCHAR(50),
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                created_by VARCHAR(255)
            );
        """)

        # Create indexes if they don't exist
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_retraining_model
            ON monitoring.model_retraining(model_name);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_retraining_created
            ON monitoring.model_retraining(created_at);
        """)

        conn.commit()


def log_retraining_result(
    conn,
    model_name: str,
    model_type: str,
    old_metrics: Dict[str, float],
    new_metrics: Dict[str, float],
    training_samples: int,
    test_samples: int,
    training_duration: float,
    result: str,
    notes: str = None,
    logger: logging.Logger = None
) -> None:
    """Log retraining results to database."""
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.model_retraining
                (model_name, model_type, old_accuracy, new_accuracy, accuracy_metric,
                 training_samples, test_samples, old_r2, new_r2, old_rmse, new_rmse,
                 training_duration_seconds, result, notes, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                model_name,
                model_type,
                old_metrics.get('accuracy'),
                new_metrics.get('accuracy'),
                new_metrics.get('metric_name'),
                training_samples,
                test_samples,
                old_metrics.get('r2'),
                new_metrics.get('r2'),
                old_metrics.get('rmse'),
                new_metrics.get('rmse'),
                training_duration,
                result,
                notes,
                os.environ.get('USER', 'unknown')
            ))
        conn.commit()
    except Exception as e:
        logger.warning(f"Failed to log results to database: {e}")


# ============================================================================
# Model Operations
# ============================================================================

def is_regression_model(model: Any) -> bool:
    """Determine if model is regression or classification based on type."""
    model_class_name = model.__class__.__name__.lower()

    regression_keywords = [
        'linearregression', 'ridge', 'lasso', 'elasticnet',
        'svr', 'kernelridge', 'huberregressor',
        'sgdregressor', 'ransacregressor', 'theilsenregressor',
        'tweedieregressor', 'poissonregressor'
    ]

    # Check if model class name contains regression keywords
    if any(keyword in model_class_name for keyword in regression_keywords):
        return True

    # Check for classification indicators
    if hasattr(model, 'classes_'):
        return False

    # Default to classification
    return False


def load_model(model_path: str, logger: logging.Logger = None) -> Tuple[Any, Optional[str]]:
    """Load model from pickle file.

    Returns:
        (model, error_message) - error_message is None if successful
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        return model, None
    except Exception as e:
        error_msg = f"Failed to load {model_path}: {e}"
        logger.error(error_msg)
        return None, error_msg


def extract_training_data(
    conn,
    model_name: str,
    logger: logging.Logger = None
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], int, Optional[str]]:
    """Extract training data from PostgreSQL experiences table.

    Returns:
        (X, y, num_samples, error_message)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Query experiences for data
            cur.execute("""
                SELECT
                    problem_type,
                    strategy,
                    success,
                    COALESCE(reward, 0.0) as reward,
                    COALESCE(novelty_score, 0.0) as novelty_score,
                    COALESCE(importance, 0.0) as importance
                FROM learning.experiences
                WHERE problem_type ILIKE %s OR %s = 'all'
                ORDER BY timestamp DESC NULLS LAST
                LIMIT 10000
            """, (f'%{model_name}%', model_name))

            rows = cur.fetchall()

            if not rows:
                return None, None, 0, f"No training data found for model '{model_name}'"

            # Build feature matrix and labels
            try:
                X = np.array([[
                    float(row.get('success', 0)),
                    float(row.get('reward', 0.0)),
                    float(row.get('novelty_score', 0.0)),
                    float(row.get('importance', 0.0))
                ] for row in rows], dtype=np.float32)

                # Binary classification: success
                y = np.array([int(bool(row.get('success', False))) for row in rows], dtype=np.int32)

                return X, y, len(rows), None

            except Exception as e:
                return None, None, 0, f"Error processing training data: {e}"

    except Exception as e:
        error_msg = f"Database query failed: {e}"
        logger.error(error_msg)
        return None, None, 0, error_msg


def evaluate_model(
    model: Any,
    X_test: np.ndarray,
    y_test: np.ndarray,
    is_regression: bool,
    logger: logging.Logger = None
) -> Dict[str, float]:
    """Evaluate model and return metrics dictionary.

    Returns:
        {accuracy, r2, rmse, mae, metric_name}
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        y_pred = model.predict(X_test)

        metrics = {
            'accuracy': None,
            'r2': None,
            'rmse': None,
            'mae': None,
            'metric_name': None
        }

        if is_regression:
            metrics['r2'] = r2_score(y_test, y_pred)
            metrics['rmse'] = np.sqrt(mean_squared_error(y_test, y_pred))
            metrics['mae'] = mean_absolute_error(y_test, y_pred)
            metrics['accuracy'] = metrics['r2']
            metrics['metric_name'] = 'r2'
        else:
            metrics['accuracy'] = accuracy_score(y_test, y_pred)
            metrics['metric_name'] = 'accuracy'

        return metrics

    except Exception as e:
        logger.error(f"Model evaluation failed: {e}")
        return {
            'accuracy': None,
            'r2': None,
            'rmse': None,
            'mae': None,
            'metric_name': None
        }


def atomic_save_model(
    model: Any,
    model_path: str,
    logger: logging.Logger = None
) -> Tuple[bool, str]:
    """Safely save model with atomic backup of old version.

    Returns:
        (success, message)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        model_path = Path(model_path)
        backup_path = model_path.with_suffix('.pkl.bak')

        # Backup existing model
        if model_path.exists():
            if backup_path.exists():
                backup_path.unlink()
            model_path.rename(backup_path)

        # Save new model
        with open(model_path, 'wb') as f:
            pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

        msg = f"Model saved to {model_path}"
        logger.info(msg)
        return True, msg

    except Exception as e:
        # Try to restore backup
        try:
            backup_path = Path(model_path).with_suffix('.pkl.bak')
            if backup_path.exists():
                backup_path.rename(model_path)
            error_msg = f"Save failed and restored backup: {e}"
        except:
            error_msg = f"Save failed, could not restore backup: {e}"

        logger.error(error_msg)
        return False, error_msg


# ============================================================================
# Main Retraining Logic
# ============================================================================

def retrain_model(
    model_path: str,
    force: bool = False,
    logger: logging.Logger = None
) -> Tuple[str, Dict[str, Any]]:
    """Retrain a single model with latest data.

    Args:
        model_path: Path to .pkl model file
        force: Save even if accuracy decreases
        logger: Logger instance

    Returns:
        (status, result_dict) where status is one of:
        - 'improved': New model is better
        - 'no_change': No difference in accuracy
        - 'regressed': New model is worse
        - 'no_data': No training data found
        - 'failed': Error occurred
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    result = {
        'model_path': str(model_path),
        'model_name': Path(model_path).stem,
        'status': 'unknown',
        'old_accuracy': None,
        'new_accuracy': None,
        'improvement': None,
        'error': None,
        'training_duration': 0,
        'training_samples': 0,
        'test_samples': 0
    }

    conn = None

    try:
        # Load existing model
        old_model, error = load_model(model_path, logger)
        if error:
            result['status'] = 'failed'
            result['error'] = error
            return 'failed', result

        # Determine model type
        is_regression = is_regression_model(old_model)
        model_type = 'regression' if is_regression else 'classification'
        logger.info(f"Loaded model, type: {model_type}")

        # Get database connection
        try:
            conn = get_db_connection()
            ensure_retraining_table(conn)
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = f"Database connection failed: {e}"
            logger.error(result['error'])
            return 'failed', result

        # Extract training data
        X, y, num_samples, error = extract_training_data(conn, result['model_name'], logger)
        if error:
            result['status'] = 'no_data'
            result['error'] = error
            logger.warning(error)
            return 'no_data', result

        logger.info(f"Extracted {num_samples} training samples")

        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if not is_regression else None
        )

        result['training_samples'] = len(X_train)
        result['test_samples'] = len(X_test)

        # Evaluate old model
        old_metrics = evaluate_model(old_model, X_test, y_test, is_regression, logger)
        if old_metrics['accuracy'] is None:
            result['status'] = 'failed'
            result['error'] = 'Failed to evaluate old model'
            return 'failed', result

        result['old_accuracy'] = old_metrics['accuracy']
        logger.info(f"Old model {old_metrics['metric_name']}: {old_metrics['accuracy']:.4f}")

        # Clone and retrain model
        new_model = copy.deepcopy(old_model)

        start_time = datetime.now()
        try:
            new_model.fit(X_train, y_train)
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = f"Training failed: {e}"
            logger.error(result['error'])
            return 'failed', result

        training_duration = (datetime.now() - start_time).total_seconds()
        result['training_duration'] = training_duration
        logger.info(f"Training completed in {training_duration:.2f} seconds")

        # Evaluate new model
        new_metrics = evaluate_model(new_model, X_test, y_test, is_regression, logger)
        if new_metrics['accuracy'] is None:
            result['status'] = 'failed'
            result['error'] = 'Failed to evaluate new model'
            return 'failed', result

        result['new_accuracy'] = new_metrics['accuracy']
        logger.info(f"New model {new_metrics['metric_name']}: {new_metrics['accuracy']:.4f}")

        # Calculate improvement
        improvement = new_metrics['accuracy'] - old_metrics['accuracy']
        result['improvement'] = improvement

        # Decide whether to save
        should_save = improvement >= 0 or force

        if should_save:
            success, message = atomic_save_model(new_model, model_path, logger)
            if success:
                if improvement > 0.0001:  # Account for floating point precision
                    result['status'] = 'improved'
                else:
                    result['status'] = 'no_change'
                logger.info(f"Model saved, improvement: {improvement:+.6f}")

                log_retraining_result(
                    conn, result['model_name'], model_type,
                    old_metrics, new_metrics,
                    len(X_train), len(X_test), training_duration,
                    result['status'],
                    f"Improvement: {improvement:+.6f}" + (" (force)" if force else ""),
                    logger
                )
            else:
                result['status'] = 'failed'
                result['error'] = message
                logger.error(f"Failed to save: {message}")
        else:
            result['status'] = 'regressed'
            result['error'] = f"Accuracy decreased by {abs(improvement):.6f}"
            logger.warning(f"Model regressed: {result['error']}")

            log_retraining_result(
                conn, result['model_name'], model_type,
                old_metrics, new_metrics,
                len(X_train), len(X_test), training_duration,
                'rejected',
                f"Regression: {improvement:.6f} (use --force to override)",
                logger
            )

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        logger.exception(f"Unexpected error: {e}")

    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

    return result['status'], result


# ============================================================================
# CLI and Main
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Retrain ML models with latest data from PostgreSQL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 tools/retrain-all-models.py
  python3 tools/retrain-all-models.py --models model1,model2
  python3 tools/retrain-all-models.py --force
  python3 tools/retrain-all-models.py --predictor-dir /custom/path
        """
    )

    parser.add_argument(
        '--models',
        help='Specific models to retrain (comma-separated, no .pkl extension)',
        default=None
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Save models even if accuracy decreases'
    )
    parser.add_argument(
        '--predictor-dir',
        default=str(Path.home() / '.claude' / 'learning' / 'predictors'),
        help='Directory containing .pkl model files'
    )
    parser.add_argument(
        '--log-file',
        help='Log file path (default: ~/.claude/logs/model_retraining/...)',
        default=None
    )

    args = parser.parse_args()

    logger = setup_logging(args.log_file)
    logger.info("Starting model retraining")
    logger.info(f"Predictor directory: {args.predictor_dir}")
    logger.info(f"Force mode: {args.force}")

    # Find model files
    predictor_dir = Path(args.predictor_dir)
    if not predictor_dir.exists():
        logger.error(f"Predictor directory not found: {predictor_dir}")
        return 1

    model_files = sorted(glob.glob(str(predictor_dir / '*.pkl')))

    # Filter by specific models if requested
    if args.models:
        selected_models = set(m.strip() for m in args.models.split(','))
        model_files = [f for f in model_files if Path(f).stem in selected_models]
        logger.info(f"Filtered to {len(model_files)} selected models")

    if not model_files:
        logger.warning("No model files found")
        return 0

    logger.info(f"Found {len(model_files)} models to retrain\n")

    # Retrain each model
    results = {}
    summary = {
        'total': len(model_files),
        'improved': 0,
        'no_change': 0,
        'regressed': 0,
        'no_data': 0,
        'failed': 0,
        'error': 0
    }

    for i, model_path in enumerate(model_files, 1):
        model_name = Path(model_path).stem
        logger.info(f"\n[{i}/{len(model_files)}] {model_name}")
        logger.info("-" * 60)

        status, result = retrain_model(model_path, force=args.force, logger=logger)
        results[model_name] = result

        if status in summary:
            summary[status] += 1

        logger.info(f"Result: {status.upper()}")

    # Print summary
    logger.info(f"\n{'='*70}")
    logger.info("RETRAINING SUMMARY")
    logger.info(f"{'='*70}")
    logger.info(f"Total models:     {summary['total']}")
    logger.info(f"  Improved:       {summary['improved']}")
    logger.info(f"  No change:      {summary['no_change']}")
    logger.info(f"  Regressed:      {summary['regressed']}")
    logger.info(f"  No data:        {summary['no_data']}")
    logger.info(f"  Failed:         {summary['failed']}")
    logger.info(f"  Error:          {summary['error']}")
    logger.info(f"{'='*70}\n")

    # Save results to JSON
    results_dir = Path.home() / '.claude' / 'logs' / 'model_retraining'
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = results_dir / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'summary': summary,
            'results': results
        }, f, indent=2)

    logger.info(f"Results saved to {results_file}")

    # Exit with error code if any failures
    return 0 if (summary['failed'] + summary['error']) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
