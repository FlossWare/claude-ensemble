#!/usr/bin/env python3
"""
Team Velocity Predictor - Gradient Boosting Regression

Predicts team performance metrics before workflow execution:
- Total workflow duration
- Parallel efficiency (speedup factor)
- Resource utilization
- Success probability

Features:
- Number of workers available
- Task complexity distribution
- Historical team performance
- Worker model diversity
- Task dependencies

Algorithm: XGBoost Gradient Boosting
Training data: Workflow execution history from PostgreSQL + synthetic patterns
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import pickle

# Try to import psycopg2 for database access
try:
    import psycopg2
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("⚠ psycopg2 not available - using synthetic training data")


class TeamVelocityPredictor:
    """Predicts team performance metrics for workflow execution"""

    def __init__(self):
        self.duration_model = None
        self.efficiency_model = None
        self.utilization_model = None
        self.success_model = None
        self.training_stats = {}

    def extract_features(self, workflow_config):
        """Extract features from workflow configuration

        Expected config:
        {
            'num_workers': int,
            'task_complexity': 'simple' | 'medium' | 'complex' | 'very_complex',
            'num_tasks': int,
            'has_dependencies': bool,
            'model_diversity': int (number of unique models),
            'parallel_ratio': float (0-1, how many tasks can run parallel),
            'historical_success_rate': float (0-1),
            'avg_worker_latency_ms': int
        }
        """

        # Complexity encoding
        complexity_map = {
            'simple': 1,
            'medium': 2,
            'complex': 3,
            'very_complex': 4
        }

        complexity = workflow_config.get('task_complexity', 'medium')

        features = {
            'num_workers': workflow_config.get('num_workers', 6),
            'num_tasks': workflow_config.get('num_tasks', 10),
            'complexity_score': complexity_map.get(complexity, 2),
            'has_dependencies': 1 if workflow_config.get('has_dependencies', False) else 0,
            'model_diversity': workflow_config.get('model_diversity', 4),
            'parallel_ratio': workflow_config.get('parallel_ratio', 0.7),
            'historical_success_rate': workflow_config.get('historical_success_rate', 0.85),
            'avg_worker_latency_ms': workflow_config.get('avg_worker_latency_ms', 2000),
            'worker_task_ratio': workflow_config.get('num_tasks', 10) / max(1, workflow_config.get('num_workers', 6)),
            'diversity_ratio': workflow_config.get('model_diversity', 4) / max(1, workflow_config.get('num_workers', 6)),
        }

        return features

    def generate_synthetic_training_data(self, n_samples=1000):
        """Generate synthetic training data based on team execution patterns"""
        print(f"Generating {n_samples} synthetic training examples...")

        training_data = []

        for _ in range(n_samples):
            # Random workflow configuration
            num_workers = np.random.randint(1, 9)  # 1-8 workers
            num_tasks = np.random.randint(5, 51)  # 5-50 tasks
            complexity_idx = np.random.randint(0, 4)
            complexity = ['simple', 'medium', 'complex', 'very_complex'][complexity_idx]
            has_dependencies = np.random.random() < 0.4
            model_diversity = min(num_workers, np.random.randint(2, 7))
            parallel_ratio = np.random.uniform(0.4, 0.95)
            historical_success = np.random.uniform(0.6, 0.95)
            avg_latency = np.random.randint(1000, 5000)

            config = {
                'num_workers': num_workers,
                'num_tasks': num_tasks,
                'task_complexity': complexity,
                'has_dependencies': has_dependencies,
                'model_diversity': model_diversity,
                'parallel_ratio': parallel_ratio,
                'historical_success_rate': historical_success,
                'avg_worker_latency_ms': avg_latency,
            }

            features = self.extract_features(config)

            # Simulate realistic outcomes

            # Base duration: task complexity * num_tasks * base_time
            complexity_time = [2000, 8000, 25000, 60000][complexity_idx]
            serial_duration = complexity_time * num_tasks

            # Parallel speedup (Amdahl's law approximation)
            if has_dependencies:
                parallel_speedup = 1 + (num_workers - 1) * parallel_ratio * 0.6
            else:
                parallel_speedup = min(num_workers, num_tasks) * parallel_ratio

            total_duration_ms = int(serial_duration / parallel_speedup + avg_latency * 2)

            # Parallel efficiency: actual_speedup / theoretical_speedup
            theoretical_speedup = min(num_workers, num_tasks)
            parallel_efficiency = min(1.0, parallel_speedup / max(1, theoretical_speedup))

            # Resource utilization: how much of available worker time is used
            total_available_time = num_workers * total_duration_ms
            total_work_time = serial_duration
            resource_utilization = min(1.0, total_work_time / max(1, total_available_time))

            # Success probability influenced by complexity, historical rate, dependencies
            base_success = historical_success
            if complexity == 'very_complex':
                base_success *= 0.8
            elif complexity == 'complex':
                base_success *= 0.9
            if has_dependencies:
                base_success *= 0.95
            success_probability = min(1.0, max(0.3, base_success + np.random.uniform(-0.1, 0.1)))

            # Add noise
            total_duration_ms = int(total_duration_ms * np.random.uniform(0.8, 1.2))
            parallel_efficiency = min(1.0, max(0.1, parallel_efficiency + np.random.uniform(-0.1, 0.1)))
            resource_utilization = min(1.0, max(0.1, resource_utilization + np.random.uniform(-0.05, 0.05)))

            training_data.append({
                'config': config,
                'features': features,
                'total_duration_ms': total_duration_ms,
                'parallel_efficiency': parallel_efficiency,
                'resource_utilization': resource_utilization,
                'success_probability': success_probability
            })

        return training_data

    def load_database_training_data(self):
        """Load real training data from PostgreSQL workflow executions"""
        if not DB_AVAILABLE:
            return None

        try:
            conn = psycopg2.connect(
                host="laptop-01",
                database="learning",
                user="sfloess",
                connect_timeout=5
            )

            cursor = conn.cursor()

            # Get workflow executions with aggregated worker metrics
            cursor.execute("""
                SELECT
                    e.workflow_id,
                    e.workflow_name,
                    e.task_description,
                    e.total_workers,
                    e.total_duration_ms,
                    e.outcome,
                    COUNT(DISTINCT w.model) as model_diversity,
                    COUNT(w.id) as num_tasks,
                    AVG(w.duration_ms) as avg_task_duration,
                    AVG(w.confidence) as avg_confidence,
                    SUM(CASE WHEN w.outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(w.id) as success_rate
                FROM workflow.executions e
                LEFT JOIN workflow.worker_results w ON e.id = w.workflow_execution_id
                WHERE e.total_duration_ms IS NOT NULL
                  AND e.total_workers > 0
                GROUP BY e.id, e.workflow_id, e.workflow_name, e.task_description,
                         e.total_workers, e.total_duration_ms, e.outcome
                HAVING COUNT(w.id) >= 3
                LIMIT 500
            """)

            rows = cursor.fetchall()
            conn.close()

            if len(rows) < 10:
                return None

            training_data = []
            for row in rows:
                (workflow_id, workflow_name, task_desc, total_workers, total_duration,
                 outcome, model_diversity, num_tasks, avg_task_dur, avg_conf, success_rate) = row

                # Estimate complexity from avg task duration
                if avg_task_dur < 5000:
                    complexity = 'simple'
                elif avg_task_dur < 20000:
                    complexity = 'medium'
                elif avg_task_dur < 60000:
                    complexity = 'complex'
                else:
                    complexity = 'very_complex'

                # Estimate parallel ratio from actual vs theoretical time
                theoretical_serial = avg_task_dur * num_tasks
                parallel_ratio = min(1.0, max(0.1, 1 - (total_duration / max(1, theoretical_serial))))

                config = {
                    'num_workers': total_workers,
                    'num_tasks': num_tasks,
                    'task_complexity': complexity,
                    'has_dependencies': False,  # Unknown from data
                    'model_diversity': model_diversity,
                    'parallel_ratio': parallel_ratio,
                    'historical_success_rate': success_rate or 0.8,
                    'avg_worker_latency_ms': int(avg_task_dur or 2000),
                }

                features = self.extract_features(config)

                # Calculate metrics
                theoretical_speedup = min(total_workers, num_tasks)
                actual_speedup = theoretical_serial / max(1, total_duration)
                parallel_efficiency = min(1.0, actual_speedup / max(1, theoretical_speedup))

                total_available = total_workers * total_duration
                total_work = theoretical_serial
                resource_utilization = min(1.0, total_work / max(1, total_available))

                training_data.append({
                    'config': config,
                    'features': features,
                    'total_duration_ms': total_duration,
                    'parallel_efficiency': parallel_efficiency,
                    'resource_utilization': resource_utilization,
                    'success_probability': 1.0 if outcome == 'success' else 0.0
                })

            print(f"✅ Loaded {len(training_data)} real workflow executions from database")
            return training_data

        except Exception as e:
            print(f"⚠ Database unavailable: {e}")
            return None

    def train(self, training_data=None):
        """Train Gradient Boosting models for team velocity prediction"""

        # Load data
        if training_data is None:
            # Try database first
            training_data = self.load_database_training_data()

            # Fall back to synthetic
            if training_data is None:
                training_data = self.generate_synthetic_training_data()

        # Extract features and targets
        feature_names = list(training_data[0]['features'].keys())
        X = np.array([[sample['features'][f] for f in feature_names]
                      for sample in training_data])
        y_duration = np.array([sample['total_duration_ms'] for sample in training_data])
        y_efficiency = np.array([sample['parallel_efficiency'] for sample in training_data])
        y_utilization = np.array([sample['resource_utilization'] for sample in training_data])
        y_success = np.array([sample['success_probability'] for sample in training_data])

        # Split data
        split_result = train_test_split(
            X, y_duration, y_efficiency, y_utilization, y_success,
            test_size=0.2, random_state=42
        )
        X_train, X_test, y_dur_train, y_dur_test, y_eff_train, y_eff_test, \
            y_util_train, y_util_test, y_succ_train, y_succ_test = split_result

        print(f"\n📊 Training on {len(X_train)} samples, testing on {len(X_test)} samples")
        print(f"Features: {len(feature_names)}")

        # Common model params
        model_params = {
            'n_estimators': 100,
            'max_depth': 5,
            'min_samples_split': 10,
            'min_samples_leaf': 4,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'random_state': 42
        }

        # Train duration model
        print("\n🌲 Training duration predictor (Gradient Boosting)...")
        self.duration_model = GradientBoostingRegressor(**model_params)
        self.duration_model.fit(X_train, y_dur_train)

        dur_pred_test = self.duration_model.predict(X_test)
        dur_r2 = r2_score(y_dur_test, dur_pred_test)
        dur_mae = mean_absolute_error(y_dur_test, dur_pred_test)
        dur_cv = cross_val_score(self.duration_model, X_train, y_dur_train, cv=5, scoring='r2')

        # Train efficiency model
        print("🌲 Training parallel efficiency predictor...")
        self.efficiency_model = GradientBoostingRegressor(**model_params)
        self.efficiency_model.fit(X_train, y_eff_train)

        eff_pred_test = self.efficiency_model.predict(X_test)
        eff_r2 = r2_score(y_eff_test, eff_pred_test)
        eff_mae = mean_absolute_error(y_eff_test, eff_pred_test)
        eff_cv = cross_val_score(self.efficiency_model, X_train, y_eff_train, cv=5, scoring='r2')

        # Train utilization model
        print("🌲 Training resource utilization predictor...")
        self.utilization_model = GradientBoostingRegressor(**model_params)
        self.utilization_model.fit(X_train, y_util_train)

        util_pred_test = self.utilization_model.predict(X_test)
        util_r2 = r2_score(y_util_test, util_pred_test)
        util_mae = mean_absolute_error(y_util_test, util_pred_test)
        util_cv = cross_val_score(self.utilization_model, X_train, y_util_train, cv=5, scoring='r2')

        # Train success model
        print("🌲 Training success probability predictor...")
        self.success_model = GradientBoostingRegressor(**model_params)
        self.success_model.fit(X_train, y_succ_train)

        succ_pred_test = self.success_model.predict(X_test)
        succ_r2 = r2_score(y_succ_test, succ_pred_test)
        succ_mae = mean_absolute_error(y_succ_test, succ_pred_test)
        succ_cv = cross_val_score(self.success_model, X_train, y_succ_train, cv=5, scoring='r2')

        # Store stats
        self.training_stats = {
            'n_train': len(X_train),
            'n_test': len(X_test),
            'n_features': len(feature_names),
            'feature_names': feature_names,
            'duration': {
                'test_r2': float(dur_r2),
                'mae_ms': float(dur_mae),
                'cv_r2_mean': float(dur_cv.mean()),
                'cv_r2_std': float(dur_cv.std()),
            },
            'efficiency': {
                'test_r2': float(eff_r2),
                'mae': float(eff_mae),
                'cv_r2_mean': float(eff_cv.mean()),
                'cv_r2_std': float(eff_cv.std()),
            },
            'utilization': {
                'test_r2': float(util_r2),
                'mae': float(util_mae),
                'cv_r2_mean': float(util_cv.mean()),
                'cv_r2_std': float(util_cv.std()),
            },
            'success': {
                'test_r2': float(succ_r2),
                'mae': float(succ_mae),
                'cv_r2_mean': float(succ_cv.mean()),
                'cv_r2_std': float(succ_cv.std()),
            }
        }

        # Feature importance
        self.training_stats['feature_importance'] = {
            'duration': dict(zip(feature_names, self.duration_model.feature_importances_)),
            'efficiency': dict(zip(feature_names, self.efficiency_model.feature_importances_)),
            'utilization': dict(zip(feature_names, self.utilization_model.feature_importances_)),
            'success': dict(zip(feature_names, self.success_model.feature_importances_)),
        }

        # Print results
        print("\n" + "="*70)
        print("📊 TRAINING RESULTS - TEAM VELOCITY PREDICTOR")
        print("="*70)

        print(f"\n⏱️  DURATION PREDICTOR:")
        print(f"  Test R²:  {dur_r2:.4f}")
        print(f"  MAE:      {dur_mae:.0f} ms ({dur_mae/1000:.1f}s)")
        print(f"  CV R²:    {dur_cv.mean():.4f} ± {dur_cv.std():.4f}")

        print(f"\n⚡ PARALLEL EFFICIENCY PREDICTOR:")
        print(f"  Test R²:  {eff_r2:.4f}")
        print(f"  MAE:      {eff_mae:.4f}")
        print(f"  CV R²:    {eff_cv.mean():.4f} ± {eff_cv.std():.4f}")

        print(f"\n📈 RESOURCE UTILIZATION PREDICTOR:")
        print(f"  Test R²:  {util_r2:.4f}")
        print(f"  MAE:      {util_mae:.4f}")
        print(f"  CV R²:    {util_cv.mean():.4f} ± {util_cv.std():.4f}")

        print(f"\n🎯 SUCCESS PROBABILITY PREDICTOR:")
        print(f"  Test R²:  {succ_r2:.4f}")
        print(f"  MAE:      {succ_mae:.4f}")
        print(f"  CV R²:    {succ_cv.mean():.4f} ± {succ_cv.std():.4f}")

        print("\n🔝 TOP FEATURES (Duration):")
        sorted_dur = sorted(self.training_stats['feature_importance']['duration'].items(),
                           key=lambda x: x[1], reverse=True)
        for feat, imp in sorted_dur[:5]:
            print(f"  {feat:25s} {imp:.4f}")

        return self.training_stats

    def predict(self, workflow_config):
        """Predict team velocity metrics for a workflow"""
        if self.duration_model is None:
            raise RuntimeError("Models not trained yet - call train() first")

        features = self.extract_features(workflow_config)
        feature_names = self.training_stats['feature_names']
        X = np.array([[features[f] for f in feature_names]])

        duration = self.duration_model.predict(X)[0]
        efficiency = self.efficiency_model.predict(X)[0]
        utilization = self.utilization_model.predict(X)[0]
        success_prob = self.success_model.predict(X)[0]

        # Clamp values
        efficiency = min(1.0, max(0.0, efficiency))
        utilization = min(1.0, max(0.0, utilization))
        success_prob = min(1.0, max(0.0, success_prob))

        # Calculate derived metrics
        num_workers = workflow_config.get('num_workers', 6)
        theoretical_speedup = min(num_workers, workflow_config.get('num_tasks', 10))
        actual_speedup = efficiency * theoretical_speedup

        return {
            'predicted_duration_ms': int(duration),
            'predicted_duration_minutes': round(duration / 60000, 2),
            'parallel_efficiency': round(efficiency, 3),
            'resource_utilization': round(utilization, 3),
            'success_probability': round(success_prob, 3),
            'theoretical_speedup': round(theoretical_speedup, 2),
            'actual_speedup': round(actual_speedup, 2),
            'efficiency_percent': round(efficiency * 100, 1),
            'features': features
        }

    def save(self, filepath):
        """Save trained models to disk"""
        data = {
            'duration_model': self.duration_model,
            'efficiency_model': self.efficiency_model,
            'utilization_model': self.utilization_model,
            'success_model': self.success_model,
            'training_stats': self.training_stats,
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Models saved to {filepath}")

    def load(self, filepath):
        """Load trained models from disk"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.duration_model = data['duration_model']
        self.efficiency_model = data['efficiency_model']
        self.utilization_model = data['utilization_model']
        self.success_model = data['success_model']
        self.training_stats = data['training_stats']
        print(f"✅ Models loaded from {filepath}")


def main():
    """Train and evaluate the team velocity predictor"""

    print("=" * 70)
    print("TEAM VELOCITY PREDICTOR - TRAINING")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize predictor
    predictor = TeamVelocityPredictor()

    # Train
    stats = predictor.train()

    # Save models
    model_path = Path.home() / ".claude" / "learning" / "team_velocity_predictor.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    predictor.save(model_path)

    # Save stats
    stats_path = Path.home() / ".claude" / "learning" / "team_velocity_predictor_stats.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✅ Stats saved to {stats_path}")

    # Test predictions
    print("\n" + "="*70)
    print("🧪 TESTING PREDICTIONS")
    print("="*70)

    test_configs = [
        {
            'name': 'Small team, simple tasks',
            'num_workers': 3,
            'num_tasks': 10,
            'task_complexity': 'simple',
            'has_dependencies': False,
            'model_diversity': 3,
            'parallel_ratio': 0.9,
            'historical_success_rate': 0.92,
            'avg_worker_latency_ms': 1500,
        },
        {
            'name': 'Large team, medium tasks',
            'num_workers': 8,
            'num_tasks': 40,
            'task_complexity': 'medium',
            'has_dependencies': True,
            'model_diversity': 6,
            'parallel_ratio': 0.7,
            'historical_success_rate': 0.85,
            'avg_worker_latency_ms': 3000,
        },
        {
            'name': 'Medium team, complex tasks',
            'num_workers': 6,
            'num_tasks': 15,
            'task_complexity': 'complex',
            'has_dependencies': True,
            'model_diversity': 5,
            'parallel_ratio': 0.6,
            'historical_success_rate': 0.75,
            'avg_worker_latency_ms': 5000,
        },
        {
            'name': 'Full fleet, very complex workflow',
            'num_workers': 8,
            'num_tasks': 25,
            'task_complexity': 'very_complex',
            'has_dependencies': True,
            'model_diversity': 6,
            'parallel_ratio': 0.5,
            'historical_success_rate': 0.70,
            'avg_worker_latency_ms': 8000,
        },
    ]

    for config in test_configs:
        name = config.pop('name')
        result = predictor.predict(config)

        print(f"\n{name}:")
        print(f"  Workers: {config['num_workers']}, Tasks: {config['num_tasks']}, "
              f"Complexity: {config['task_complexity']}")
        print(f"  Duration:    {result['predicted_duration_minutes']:.1f} min "
              f"({result['predicted_duration_ms']:,} ms)")
        print(f"  Efficiency:  {result['efficiency_percent']:.1f}% "
              f"(speedup: {result['actual_speedup']:.1f}x)")
        print(f"  Utilization: {result['resource_utilization']:.1%}")
        print(f"  Success:     {result['success_probability']:.1%}")

    print("\n" + "="*70)
    print("✅ TRAINING COMPLETE")
    print("="*70)
    print(f"Models saved to: {model_path}")
    print(f"Stats saved to:  {stats_path}")

    # Return summary for orchestration
    summary = {
        'status': 'SUCCESS',
        'duration_r2': stats['duration']['test_r2'],
        'efficiency_r2': stats['efficiency']['test_r2'],
        'utilization_r2': stats['utilization']['test_r2'],
        'success_r2': stats['success']['test_r2'],
        'n_train': stats['n_train'],
        'n_test': stats['n_test'],
        'model_path': str(model_path),
        'stats_path': str(stats_path),
    }

    return summary


if __name__ == "__main__":
    try:
        result = main()
        print(f"\n📊 Final Results: {json.dumps(result, indent=2)}")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
