#!/usr/bin/env python3
"""
Build Time Predictor - ML model to predict Maven build times

Features extracted:
- Number of source files
- Lines of code (LOC)
- Number of dependencies
- Test file count
- Module count
- Packaging type
- Historical build times

Model: Gradient Boosting Regressor (handles non-linear relationships)
"""

import os
import json
import pickle
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET

try:
    import numpy as np
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
except ImportError:
    print("Installing required packages...")
    subprocess.run(["pip3", "install", "--user", "scikit-learn", "numpy"], check=True)
    import numpy as np
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score


class BuildTimePredictor:
    """Predict Maven build times based on project features"""

    def __init__(self, model_path: str = None):
        self.model_path = model_path or str(Path.home() / '.claude' / 'learning' / 'build_time_predictor.pkl')
        self.stats_path = str(Path.home() / '.claude' / 'learning' / 'build_time_predictor_stats.json')
        self.model = None
        self.feature_names = [
            'num_java_files',
            'total_loc',
            'num_dependencies',
            'num_test_files',
            'num_modules',
            'is_jar',
            'is_war',
            'is_pom',
            'has_tests',
            'avg_file_size'
        ]

    def extract_features(self, pom_path: str) -> Dict:
        """Extract features from a Maven project"""
        pom_dir = os.path.dirname(os.path.abspath(pom_path))

        # Parse POM
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()
            ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}

            # Packaging type
            packaging = root.find('.//maven:packaging', ns)
            packaging_type = packaging.text if packaging is not None else 'jar'

            # Count dependencies
            dependencies = root.findall('.//maven:dependency', ns)
            num_dependencies = len(dependencies)

            # Count modules
            modules = root.findall('.//maven:module', ns)
            num_modules = len(modules)

        except Exception as e:
            print(f"Warning: Could not parse POM: {e}")
            packaging_type = 'jar'
            num_dependencies = 0
            num_modules = 0

        # Count Java files
        java_files = list(Path(pom_dir).rglob('*.java'))
        num_java_files = len(java_files)

        # Count test files
        test_files = [f for f in java_files if '/test/' in str(f) or 'Test.java' in str(f)]
        num_test_files = len(test_files)

        # Calculate total LOC
        total_loc = 0
        file_sizes = []
        for java_file in java_files:
            try:
                with open(java_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = len(f.readlines())
                    total_loc += lines
                    file_sizes.append(lines)
            except:
                pass

        avg_file_size = np.mean(file_sizes) if file_sizes else 0

        # Build feature dict
        features = {
            'num_java_files': num_java_files,
            'total_loc': total_loc,
            'num_dependencies': num_dependencies,
            'num_test_files': num_test_files,
            'num_modules': num_modules,
            'is_jar': 1 if packaging_type == 'jar' else 0,
            'is_war': 1 if packaging_type == 'war' else 0,
            'is_pom': 1 if packaging_type == 'pom' else 0,
            'has_tests': 1 if num_test_files > 0 else 0,
            'avg_file_size': avg_file_size,
            'project_path': pom_path
        }

        return features

    def measure_build_time(self, pom_path: str, clean: bool = True) -> float:
        """Measure actual build time for a Maven project"""
        pom_dir = os.path.dirname(os.path.abspath(pom_path))

        cmd = ['mvn', 'clean', 'install'] if clean else ['mvn', 'install']
        cmd.extend(['-DskipTests', '-q'])

        print(f"Building {pom_dir}...")
        start = datetime.now()

        try:
            result = subprocess.run(
                cmd,
                cwd=pom_dir,
                capture_output=True,
                text=True,
                timeout=600  # 10 min timeout
            )

            duration = (datetime.now() - start).total_seconds()

            if result.returncode != 0:
                print(f"Build failed: {result.stderr[:200]}")
                return -1

            return duration

        except subprocess.TimeoutExpired:
            print(f"Build timed out after 10 minutes")
            return -1
        except Exception as e:
            print(f"Build error: {e}")
            return -1

    def collect_training_data(self, project_roots: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """Collect training data from multiple Maven projects"""
        X_data = []
        y_data = []

        for root in project_roots:
            pom_files = list(Path(root).rglob('pom.xml'))
            print(f"\nFound {len(pom_files)} POM files in {root}")

            for pom_path in pom_files:
                print(f"\nProcessing {pom_path}...")

                # Extract features
                features = self.extract_features(str(pom_path))

                # Skip if no Java files
                if features['num_java_files'] == 0:
                    print("  Skipping (no Java files)")
                    continue

                # Measure build time
                build_time = self.measure_build_time(str(pom_path))

                if build_time > 0:
                    feature_vector = [features[name] for name in self.feature_names]
                    X_data.append(feature_vector)
                    y_data.append(build_time)

                    print(f"  Features: {features['num_java_files']} files, {features['total_loc']} LOC, {features['num_dependencies']} deps")
                    print(f"  Build time: {build_time:.2f}s")

        return np.array(X_data), np.array(y_data)

    def train(self, X: np.ndarray, y: np.ndarray):
        """Train the build time predictor"""
        if len(X) < 2:
            raise ValueError(f"Need at least 2 samples, got {len(X)}")

        # If we have limited data, use a simpler model and no test split
        if len(X) < 5:
            print(f"WARNING: Only {len(X)} samples - using simplified model")
            self.model = GradientBoostingRegressor(
                n_estimators=50,
                learning_rate=0.1,
                max_depth=3,
                random_state=42
            )
            self.model.fit(X, y)

            # No test set - report training stats only
            y_pred = self.model.predict(X)
            mae = mean_absolute_error(y, y_pred)
            r2 = r2_score(y, y_pred)
            train_size = len(X)
            test_size = 0

        else:
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Train model
            self.model = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )

            self.model.fit(X_train, y_train)

            # Evaluate
            y_pred = self.model.predict(X_test)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            train_size = len(X_train)
            test_size = len(X_test)

        # Feature importance
        importances = dict(zip(self.feature_names, self.model.feature_importances_))

        stats = {
            'trained_at': datetime.now().isoformat(),
            'num_samples': len(X),
            'train_size': train_size,
            'test_size': test_size,
            'mae_seconds': float(mae),
            'r2_score': float(r2),
            'feature_importance': {k: float(v) for k, v in importances.items()},
            'mean_build_time': float(np.mean(y)),
            'std_build_time': float(np.std(y)),
            'warning': 'Limited training data' if len(X) < 5 else None
        }

        # Save model
        with open(self.model_path, 'wb') as f:
            pickle.dump(self.model, f)

        with open(self.stats_path, 'w') as f:
            json.dump(stats, f, indent=2)

        print(f"\nModel trained:")
        print(f"  MAE: {mae:.2f} seconds")
        print(f"  R² score: {r2:.3f}")
        print(f"  Top features: {sorted(importances.items(), key=lambda x: x[1], reverse=True)[:3]}")
        print(f"  Saved to: {self.model_path}")

        return stats

    def load(self):
        """Load trained model"""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        with open(self.model_path, 'rb') as f:
            self.model = pickle.load(f)

    def heuristic_predict(self, features: Dict) -> float:
        """Heuristic-based prediction when no model is available"""
        # Base time (Maven overhead)
        base_time = 5.0

        # Per-file compilation time (roughly 0.5s per file)
        compilation_time = features['num_java_files'] * 0.5

        # Dependency resolution (0.3s per dependency)
        dependency_time = features['num_dependencies'] * 0.3

        # Test overhead (if tests exist)
        test_time = features['num_test_files'] * 0.2 if features['has_tests'] else 0

        # Module overhead (multi-module builds slower)
        module_time = features['num_modules'] * 2.0

        # Large file penalty (complex files take longer)
        if features['avg_file_size'] > 200:
            complexity_penalty = (features['avg_file_size'] - 200) * 0.01
        else:
            complexity_penalty = 0

        # WAR/EAR packaging takes longer
        packaging_time = 5.0 if features['is_war'] else 0

        total_time = (
            base_time +
            compilation_time +
            dependency_time +
            test_time +
            module_time +
            complexity_penalty +
            packaging_time
        )

        return total_time

    def predict(self, pom_path: str, use_heuristic: bool = False) -> Dict:
        """Predict build time for a Maven project"""
        # Extract features
        features = self.extract_features(pom_path)

        # Try to load model
        model_available = os.path.exists(self.model_path)

        if not model_available or use_heuristic:
            # Use heuristic prediction
            predicted_time = self.heuristic_predict(features)
            method = 'heuristic'
            model_mae = 'N/A (heuristic)'
            trained_at = 'N/A (heuristic)'
        else:
            # Use ML model
            if self.model is None:
                self.load()

            feature_vector = np.array([[features[name] for name in self.feature_names]])
            predicted_time = self.model.predict(feature_vector)[0]
            method = 'ml_model'

            # Load stats for context
            if os.path.exists(self.stats_path):
                with open(self.stats_path, 'r') as f:
                    stats = json.load(f)
                model_mae = stats.get('mae_seconds', 'unknown')
                trained_at = stats.get('trained_at', 'unknown')
            else:
                model_mae = 'unknown'
                trained_at = 'unknown'

        result = {
            'project': pom_path,
            'predicted_build_time_seconds': float(predicted_time),
            'predicted_build_time_formatted': f"{int(predicted_time // 60)}m {int(predicted_time % 60)}s",
            'prediction_method': method,
            'features': features,
            'model_mae': model_mae,
            'trained_at': trained_at
        }

        return result


def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description='Build Time Predictor for Maven projects')
    parser.add_argument('--train', nargs='+', help='Train on Maven projects (space-separated paths)')
    parser.add_argument('--predict', help='Predict build time for a POM file')
    parser.add_argument('--batch-predict', help='Predict for all POMs in directory')

    args = parser.parse_args()

    predictor = BuildTimePredictor()

    if args.train:
        print("Collecting training data...")
        X, y = predictor.collect_training_data(args.train)

        if len(X) > 0:
            print(f"\nCollected {len(X)} samples")
            stats = predictor.train(X, y)
            print("\nTraining complete!")
        else:
            print("No valid training data collected")

    elif args.predict:
        result = predictor.predict(args.predict)
        print(json.dumps(result, indent=2))

    elif args.batch_predict:
        pom_files = list(Path(args.batch_predict).rglob('pom.xml'))
        print(f"Found {len(pom_files)} POM files\n")

        predictions = []
        for pom_path in pom_files:
            try:
                result = predictor.predict(str(pom_path))
                predictions.append(result)
                print(f"{result['project']}: {result['predicted_build_time_formatted']}")
            except Exception as e:
                print(f"Error predicting {pom_path}: {e}")

        # Sort by predicted time
        predictions.sort(key=lambda x: x['predicted_build_time_seconds'], reverse=True)

        print("\n--- Top 5 Longest Builds ---")
        for p in predictions[:5]:
            print(f"{p['predicted_build_time_formatted']}: {p['project']}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
