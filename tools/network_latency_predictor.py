#!/usr/bin/env python3
"""
Network Latency Predictor for Distributed Fleet

Trains ML models to predict network latency between orchestrator (aio-01) and fleet nodes.
Uses historical health check data + real-time measurements.

Features:
- Multi-model ensemble (Random Forest, Gradient Boosting, Neural Network)
- Time-series feature engineering (hour of day, day of week, workload patterns)
- Node characteristics (CPU cores, RAM, network type)
- Active data collection via ping/SSH latency measurement
- PostgreSQL integration for storage and historical analysis
- Model persistence for fleet routing decisions

Usage:
    # Collect current network measurements
    python3 network_latency_predictor.py --collect

    # Train models on historical data
    python3 network_latency_predictor.py --train

    # Predict latency for a node
    python3 network_latency_predictor.py --predict server-01

    # Continuous monitoring mode
    python3 network_latency_predictor.py --monitor --interval 300

Output:
    - Trained models: learning/network_latency_models.pkl
    - Feature stats: learning/network_latency_stats.json
    - Predictions: PostgreSQL monitoring.network_predictions table
"""

import argparse
import json
import pickle
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip3 install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
except ImportError:
    print("ERROR: scikit-learn not installed. Run: pip3 install scikit-learn", file=sys.stderr)
    sys.exit(1)


class NetworkLatencyPredictor:
    """Train and use ML models to predict network latency"""

    def __init__(self, db_host='aio-01', db_port=5433, db_name='learning', db_user='sfloess'):
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.conn = None

        # Fleet configuration
        self.fleet_nodes = {
            'aio-01': {'cores': 8, 'ram_gb': 16, 'network': 'gigabit'},
            'server-01': {'cores': 10, 'ram_gb': 24, 'network': 'gigabit'},
            'server-02': {'cores': 10, 'ram_gb': 24, 'network': 'gigabit'},
            'server-03': {'cores': 10, 'ram_gb': 24, 'network': 'gigabit'},
            'laptop-01': {'cores': 8, 'ram_gb': 16, 'network': 'wifi'},
            'pi-02': {'cores': 4, 'ram_gb': 8, 'network': 'gigabit'},
            'desktop-ap': {'cores': 8, 'ram_gb': 16, 'network': 'gigabit'},
            'server-ap': {'cores': 4, 'ram_gb': 8, 'network': 'gigabit'},
        }

        # Models
        self.models = {}
        self.scaler = StandardScaler()
        self.feature_stats = {}

        # Paths
        self.learning_dir = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning'
        self.model_path = self.learning_dir / 'network_latency_models.pkl'
        self.stats_path = self.learning_dir / 'network_latency_stats.json'

    def connect_db(self):
        """Connect to PostgreSQL"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user
            )
        return self.conn

    def create_tables(self):
        """Create network monitoring tables if they don't exist"""
        conn = self.connect_db()
        cursor = conn.cursor()

        # Network measurements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitoring.network_measurements (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                source_node TEXT NOT NULL,
                target_node TEXT NOT NULL,
                ping_latency_ms REAL,
                ssh_latency_ms REAL,
                packet_loss_percent REAL,
                hour_of_day INTEGER,
                day_of_week INTEGER,
                cpu_load NUMERIC,
                ram_used_percent REAL,
                concurrent_tasks INTEGER,
                metadata JSONB
            )
        """)

        # Network predictions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitoring.network_predictions (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                target_node TEXT NOT NULL,
                predicted_latency_ms REAL NOT NULL,
                confidence_score REAL,
                model_used TEXT,
                features JSONB,
                actual_latency_ms REAL,
                prediction_error_ms REAL
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_network_measurements_timestamp
            ON monitoring.network_measurements(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_network_measurements_target
            ON monitoring.network_measurements(target_node)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_network_predictions_timestamp
            ON monitoring.network_predictions(timestamp)
        """)

        conn.commit()
        cursor.close()
        print("✓ Database tables created/verified")

    def measure_latency(self, target_node: str, source_node: str = 'aio-01') -> Dict:
        """Measure current network latency to a node"""
        measurement = {
            'timestamp': datetime.now().isoformat(),
            'source_node': source_node,
            'target_node': target_node,
            'ping_latency_ms': None,
            'ssh_latency_ms': None,
            'packet_loss_percent': None,
            'hour_of_day': datetime.now().hour,
            'day_of_week': datetime.now().weekday(),
        }

        # Ping measurement (3 packets, 1s timeout)
        try:
            result = subprocess.run(
                ['ping', '-c', '3', '-W', '1', target_node],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Parse ping output: "rtt min/avg/max/mdev = 0.123/0.456/0.789/0.012 ms"
                for line in result.stdout.split('\n'):
                    if 'rtt min/avg/max' in line:
                        parts = line.split('=')[1].strip().split('/')
                        measurement['ping_latency_ms'] = float(parts[1])  # avg
                        break
                    elif '% packet loss' in line:
                        loss = line.split('%')[0].split()[-1]
                        measurement['packet_loss_percent'] = float(loss)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError) as e:
            print(f"  Warning: Ping to {target_node} failed: {e}")

        # SSH latency measurement (time to establish connection)
        try:
            start = time.time()
            result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=2', '-o', 'BatchMode=yes',
                 f'claude@{target_node}', 'echo ok'],
                capture_output=True,
                text=True,
                timeout=5
            )
            elapsed_ms = (time.time() - start) * 1000

            if result.returncode == 0:
                measurement['ssh_latency_ms'] = elapsed_ms
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"  Warning: SSH to {target_node} failed: {e}")

        # Get system load from fleet_health if available
        try:
            conn = self.connect_db()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT cpu_load, ram_used_mb, ram_total_mb
                FROM monitoring.fleet_health
                WHERE hostname = %s
                ORDER BY last_seen DESC
                LIMIT 1
            """, (target_node,))

            row = cursor.fetchone()
            if row:
                measurement['cpu_load'] = float(row['cpu_load']) if row['cpu_load'] else None
                if row['ram_used_mb'] and row['ram_total_mb']:
                    measurement['ram_used_percent'] = (row['ram_used_mb'] / row['ram_total_mb']) * 100
            cursor.close()
        except Exception as e:
            print(f"  Warning: Could not fetch system load: {e}")

        return measurement

    def collect_measurements(self, nodes: Optional[List[str]] = None):
        """Collect network measurements for all fleet nodes"""
        if nodes is None:
            nodes = [n for n in self.fleet_nodes.keys() if n != 'aio-01']

        conn = self.connect_db()
        cursor = conn.cursor()

        print(f"Collecting network measurements for {len(nodes)} nodes...")
        measurements = []

        for node in nodes:
            print(f"  Measuring {node}...")
            m = self.measure_latency(node)
            measurements.append(m)

            # Store in database
            cursor.execute("""
                INSERT INTO monitoring.network_measurements
                (timestamp, source_node, target_node, ping_latency_ms, ssh_latency_ms,
                 packet_loss_percent, hour_of_day, day_of_week, cpu_load, ram_used_percent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                m['timestamp'], m['source_node'], m['target_node'],
                m.get('ping_latency_ms'), m.get('ssh_latency_ms'),
                m.get('packet_loss_percent'), m['hour_of_day'], m['day_of_week'],
                m.get('cpu_load'), m.get('ram_used_percent')
            ))

        conn.commit()
        cursor.close()

        print(f"✓ Collected {len(measurements)} measurements")
        return measurements

    def extract_features(self, measurement: Dict) -> np.ndarray:
        """Extract feature vector from measurement"""
        node = measurement['target_node']
        node_config = self.fleet_nodes.get(node, {})

        features = [
            # Node characteristics
            node_config.get('cores', 4),
            node_config.get('ram_gb', 8),
            1 if node_config.get('network') == 'wifi' else 0,
            1 if node_config.get('network') == 'gigabit' else 0,

            # Time features
            measurement.get('hour_of_day', 12),
            measurement.get('day_of_week', 0),
            1 if measurement.get('hour_of_day', 12) in range(9, 17) else 0,  # Business hours

            # System load
            measurement.get('cpu_load', 0.5) or 0.5,
            measurement.get('ram_used_percent', 50.0) or 50.0,
            measurement.get('concurrent_tasks', 0) or 0,

            # Network quality
            measurement.get('packet_loss_percent', 0.0) or 0.0,
        ]

        return np.array(features, dtype=np.float32)

    def load_training_data(self, days: int = 30) -> Tuple[np.ndarray, np.ndarray]:
        """Load historical measurements from database"""
        conn = self.connect_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        since = datetime.now() - timedelta(days=days)

        # Get measurements with valid latency
        cursor.execute("""
            SELECT * FROM monitoring.network_measurements
            WHERE timestamp > %s
            AND (ping_latency_ms IS NOT NULL OR ssh_latency_ms IS NOT NULL)
            ORDER BY timestamp DESC
        """, (since,))

        rows = cursor.fetchall()
        cursor.close()

        if len(rows) < 10:
            print(f"Warning: Only {len(rows)} measurements found. Need at least 10 for training.")
            print("Run with --collect to gather more data.")
            return None, None

        print(f"Loaded {len(rows)} measurements from last {days} days")

        # Extract features and targets
        X = []
        y = []

        for row in rows:
            features = self.extract_features(dict(row))
            # Use ping latency if available, otherwise SSH latency
            latency = row['ping_latency_ms'] if row['ping_latency_ms'] else row['ssh_latency_ms']

            if latency and not np.isnan(latency) and latency > 0:
                X.append(features)
                y.append(latency)

        if len(X) < 10:
            print(f"Warning: Only {len(X)} valid samples after filtering")
            return None, None

        return np.array(X), np.array(y)

    def train_models(self, days: int = 30):
        """Train ensemble of ML models"""
        X, y = self.load_training_data(days)

        if X is None or len(X) < 10:
            print("ERROR: Insufficient training data")
            return False

        print(f"\nTraining on {len(X)} samples...")
        print(f"  Latency range: {y.min():.2f} - {y.max():.2f} ms")
        print(f"  Mean: {y.mean():.2f} ms, Std: {y.std():.2f} ms")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Normalize features
        self.scaler.fit(X_train)
        X_train_scaled = self.scaler.transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train multiple models
        print("\nTraining models:")

        # Random Forest
        print("  Training Random Forest...")
        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        rf.fit(X_train_scaled, y_train)
        self.models['random_forest'] = rf

        # Gradient Boosting
        print("  Training Gradient Boosting...")
        gb = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        gb.fit(X_train_scaled, y_train)
        self.models['gradient_boosting'] = gb

        # Neural Network
        print("  Training Neural Network...")
        nn = MLPRegressor(
            hidden_layer_sizes=(64, 32, 16),
            activation='relu',
            solver='adam',
            max_iter=500,
            random_state=42,
            early_stopping=True
        )
        nn.fit(X_train_scaled, y_train)
        self.models['neural_network'] = nn

        # Evaluate models
        print("\nModel Performance:")
        print("=" * 60)

        results = {}
        for name, model in self.models.items():
            y_pred = model.predict(X_test_scaled)

            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)

            results[name] = {'mae': mae, 'rmse': rmse, 'r2': r2}

            print(f"{name:20s} | MAE: {mae:6.2f} ms | RMSE: {rmse:6.2f} ms | R²: {r2:6.3f}")

        # Create ensemble (weighted average based on R² scores)
        weights = {}
        total_r2 = sum(r['r2'] for r in results.values() if r['r2'] > 0)

        if total_r2 > 0:
            for name, r in results.items():
                weights[name] = max(0, r['r2']) / total_r2
        else:
            # Equal weights if all R² negative
            weights = {name: 1.0/len(results) for name in results}

        print("\nEnsemble Weights:")
        for name, weight in weights.items():
            print(f"  {name:20s}: {weight:.3f}")

        # Store stats
        self.feature_stats = {
            'training_samples': len(X),
            'feature_count': X.shape[1],
            'latency_mean': float(y.mean()),
            'latency_std': float(y.std()),
            'latency_min': float(y.min()),
            'latency_max': float(y.max()),
            'ensemble_weights': weights,
            'model_performance': {
                name: {k: float(v) for k, v in perf.items()}
                for name, perf in results.items()
            },
            'trained_at': datetime.now().isoformat()
        }

        # Save models
        self.save_models()

        print(f"\n✓ Models trained and saved to {self.model_path}")
        return True

    def save_models(self):
        """Save trained models to disk"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'models': self.models,
                'scaler': self.scaler,
                'stats': self.feature_stats
            }, f)

        with open(self.stats_path, 'w') as f:
            json.dump(self.feature_stats, f, indent=2)

    def load_models(self):
        """Load trained models from disk"""
        if not self.model_path.exists():
            print(f"ERROR: No trained models found at {self.model_path}")
            print("Run with --train first")
            return False

        with open(self.model_path, 'rb') as f:
            data = pickle.load(f)
            self.models = data['models']
            self.scaler = data['scaler']
            self.feature_stats = data['stats']

        print(f"✓ Loaded {len(self.models)} models (trained {self.feature_stats.get('trained_at')})")
        return True

    def predict_latency(self, target_node: str, current_measurement: Optional[Dict] = None) -> Dict:
        """Predict network latency for a node"""
        if not self.models:
            if not self.load_models():
                return None

        # Get current measurement if not provided
        if current_measurement is None:
            current_measurement = self.measure_latency(target_node)

        # Extract features
        X = self.extract_features(current_measurement).reshape(1, -1)
        X_scaled = self.scaler.transform(X)

        # Ensemble prediction
        predictions = {}
        weights = self.feature_stats.get('ensemble_weights', {})

        for name, model in self.models.items():
            pred = model.predict(X_scaled)[0]
            predictions[name] = float(pred)

        # Weighted average
        if weights:
            ensemble_pred = sum(predictions[name] * weights.get(name, 0) for name in predictions)
        else:
            ensemble_pred = np.mean(list(predictions.values()))

        # Confidence score (inverse of prediction variance)
        pred_std = np.std(list(predictions.values()))
        confidence = 1.0 / (1.0 + pred_std / ensemble_pred) if ensemble_pred > 0 else 0.5

        result = {
            'target_node': target_node,
            'predicted_latency_ms': float(ensemble_pred),
            'confidence_score': float(confidence),
            'model_predictions': predictions,
            'actual_latency_ms': current_measurement.get('ping_latency_ms') or current_measurement.get('ssh_latency_ms'),
            'timestamp': datetime.now().isoformat()
        }

        # Store prediction in database
        try:
            conn = self.connect_db()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO monitoring.network_predictions
                (timestamp, target_node, predicted_latency_ms, confidence_score,
                 model_used, features, actual_latency_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                result['timestamp'], target_node, result['predicted_latency_ms'],
                result['confidence_score'], 'ensemble',
                json.dumps(result['model_predictions']), result['actual_latency_ms']
            ))

            result['prediction_id'] = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Warning: Could not store prediction: {e}")

        return result

    def monitor_continuous(self, interval: int = 300):
        """Continuously monitor and predict network latency"""
        print(f"Starting continuous monitoring (interval: {interval}s)")
        print("Press Ctrl+C to stop")

        try:
            while True:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Collecting measurements...")

                # Collect measurements
                measurements = self.collect_measurements()

                # Predict for each node
                for m in measurements:
                    if m.get('ping_latency_ms') or m.get('ssh_latency_ms'):
                        result = self.predict_latency(m['target_node'], m)

                        actual = result.get('actual_latency_ms')
                        predicted = result['predicted_latency_ms']
                        error = abs(actual - predicted) if actual else None

                        print(f"  {m['target_node']:12s} | "
                              f"Actual: {actual:6.2f} ms | "
                              f"Predicted: {predicted:6.2f} ms | "
                              f"Error: {error:6.2f} ms | "
                              f"Confidence: {result['confidence_score']:.3f}" if actual else
                              f"  {m['target_node']:12s} | Predicted: {predicted:6.2f} ms")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped")


def main():
    parser = argparse.ArgumentParser(
        description='Network Latency Predictor for Distributed Fleet',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--collect', action='store_true',
                        help='Collect current network measurements')
    parser.add_argument('--train', action='store_true',
                        help='Train ML models on historical data')
    parser.add_argument('--predict', metavar='NODE',
                        help='Predict latency for a specific node')
    parser.add_argument('--monitor', action='store_true',
                        help='Continuous monitoring mode')
    parser.add_argument('--interval', type=int, default=300,
                        help='Monitoring interval in seconds (default: 300)')
    parser.add_argument('--days', type=int, default=30,
                        help='Days of historical data for training (default: 30)')

    args = parser.parse_args()

    predictor = NetworkLatencyPredictor()

    # Create tables
    predictor.create_tables()

    if args.collect:
        predictor.collect_measurements()

    elif args.train:
        predictor.train_models(days=args.days)

    elif args.predict:
        result = predictor.predict_latency(args.predict)
        if result:
            print(json.dumps(result, indent=2))

    elif args.monitor:
        predictor.monitor_continuous(interval=args.interval)

    else:
        parser.print_help()
        print("\nExample usage:")
        print("  # Collect current measurements")
        print("  python3 network_latency_predictor.py --collect")
        print()
        print("  # Train models")
        print("  python3 network_latency_predictor.py --train")
        print()
        print("  # Predict latency")
        print("  python3 network_latency_predictor.py --predict server-01")
        print()
        print("  # Continuous monitoring")
        print("  python3 network_latency_predictor.py --monitor --interval 60")


if __name__ == '__main__':
    main()
