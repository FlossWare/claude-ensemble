#!/usr/bin/env python3
"""
Dependency Risk Analyzer - Gradient Boosting Classification

Predicts risk level for package dependencies based on:
- Version age and staleness
- Security vulnerability indicators
- Maintenance activity
- Breaking change history
- Ecosystem health metrics
- License compatibility
- Transitive dependency depth

Algorithm: XGBoost Gradient Boosting Classifier
Training data: Synthetic + real dependency audit data if available
Risk Categories: LOW, MEDIUM, HIGH, CRITICAL
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score
from sklearn.preprocessing import LabelEncoder
import pickle

# Try XGBoost first, fall back to Random Forest
try:
    from xgboost import XGBClassifier
    CLASSIFIER_TYPE = "XGBoost"
except ImportError:
    from sklearn.ensemble import RandomForestClassifier as XGBClassifier
    CLASSIFIER_TYPE = "RandomForest"
    print("⚠ XGBoost not available - using Random Forest")

# Try to import psycopg2 for database access
try:
    import psycopg2
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("⚠ psycopg2 not available - using synthetic training data")


class DependencyRiskAnalyzer:
    """Predicts risk level for package dependencies"""

    RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

    def __init__(self):
        self.model = None
        self.label_encoder = LabelEncoder()
        self.training_stats = {}
        self.feature_names = []

    def extract_features(self, dependency_info):
        """Extract features from dependency information"""

        # Version age (days since last update)
        version_age_days = dependency_info.get('version_age_days', 0)

        # Maintenance metrics
        commits_last_year = dependency_info.get('commits_last_year', 0)
        open_issues = dependency_info.get('open_issues', 0)
        open_prs = dependency_info.get('open_prs', 0)
        closed_issues_last_month = dependency_info.get('closed_issues_last_month', 0)

        # Security indicators
        known_vulnerabilities = dependency_info.get('known_vulnerabilities', 0)
        has_security_policy = 1 if dependency_info.get('has_security_policy', False) else 0
        cve_count = dependency_info.get('cve_count', 0)

        # Popularity and ecosystem health
        downloads_per_month = dependency_info.get('downloads_per_month', 0)
        github_stars = dependency_info.get('github_stars', 0)
        num_dependents = dependency_info.get('num_dependents', 0)

        # Version and compatibility
        is_major_version_behind = 1 if dependency_info.get('major_versions_behind', 0) > 0 else 0
        is_minor_version_behind = 1 if dependency_info.get('minor_versions_behind', 0) > 0 else 0
        breaking_changes_in_latest = dependency_info.get('breaking_changes_in_latest', 0)

        # License
        license_type = dependency_info.get('license', 'unknown').lower()
        is_permissive_license = 1 if any(lic in license_type for lic in ['mit', 'apache', 'bsd', 'isc']) else 0
        is_copyleft_license = 1 if any(lic in license_type for lic in ['gpl', 'agpl', 'lgpl']) else 0

        # Dependency depth
        transitive_depth = dependency_info.get('transitive_depth', 0)
        total_transitive_deps = dependency_info.get('total_transitive_deps', 0)

        # Package type indicators
        is_dev_dependency = 1 if dependency_info.get('is_dev_dependency', False) else 0
        is_optional = 1 if dependency_info.get('is_optional', False) else 0

        # Ecosystem-specific
        ecosystem = dependency_info.get('ecosystem', 'npm').lower()
        is_npm = 1 if ecosystem == 'npm' else 0
        is_pypi = 1 if ecosystem == 'pypi' else 0
        is_maven = 1 if ecosystem == 'maven' else 0

        # Critical infrastructure indicators
        is_core_dependency = 1 if dependency_info.get('is_core_dependency', False) else 0
        num_reverse_deps = dependency_info.get('num_reverse_deps', 0)

        features = {
            'version_age_days': min(version_age_days, 3650),  # Cap at 10 years
            'commits_last_year': min(commits_last_year, 1000),
            'open_issues': min(open_issues, 500),
            'open_prs': min(open_prs, 100),
            'closed_issues_last_month': min(closed_issues_last_month, 100),
            'known_vulnerabilities': known_vulnerabilities,
            'has_security_policy': has_security_policy,
            'cve_count': min(cve_count, 50),
            'log_downloads': np.log1p(downloads_per_month),
            'log_stars': np.log1p(github_stars),
            'log_dependents': np.log1p(num_dependents),
            'is_major_version_behind': is_major_version_behind,
            'is_minor_version_behind': is_minor_version_behind,
            'breaking_changes_in_latest': breaking_changes_in_latest,
            'is_permissive_license': is_permissive_license,
            'is_copyleft_license': is_copyleft_license,
            'transitive_depth': min(transitive_depth, 20),
            'total_transitive_deps': min(total_transitive_deps, 500),
            'is_dev_dependency': is_dev_dependency,
            'is_optional': is_optional,
            'is_npm': is_npm,
            'is_pypi': is_pypi,
            'is_maven': is_maven,
            'is_core_dependency': is_core_dependency,
            'log_reverse_deps': np.log1p(num_reverse_deps),
        }

        return features

    def compute_risk_score(self, dep):
        """Compute risk score to generate synthetic risk labels"""
        risk_score = 0.0

        # Age factor (older = higher risk)
        age_days = dep.get('version_age_days', 0)
        if age_days > 730:  # > 2 years
            risk_score += 0.3
        elif age_days > 365:  # > 1 year
            risk_score += 0.15

        # Security vulnerabilities (major risk factor)
        vuln_count = dep.get('known_vulnerabilities', 0)
        cve_count = dep.get('cve_count', 0)
        risk_score += min(vuln_count * 0.25, 0.5)
        risk_score += min(cve_count * 0.2, 0.4)

        # Maintenance activity (low activity = higher risk)
        commits = dep.get('commits_last_year', 0)
        if commits == 0:
            risk_score += 0.2
        elif commits < 10:
            risk_score += 0.1

        # Open issues vs closed (high open = higher risk)
        open_issues = dep.get('open_issues', 0)
        closed_recent = dep.get('closed_issues_last_month', 0)
        if open_issues > 50 and closed_recent < 5:
            risk_score += 0.15

        # Version behind (not keeping up = risk)
        if dep.get('major_versions_behind', 0) > 0:
            risk_score += 0.2
        if dep.get('minor_versions_behind', 0) > 2:
            risk_score += 0.1

        # Breaking changes (migration risk)
        breaking = dep.get('breaking_changes_in_latest', 0)
        if breaking > 0:
            risk_score += min(breaking * 0.1, 0.2)

        # Popularity (low popularity = higher risk)
        downloads = dep.get('downloads_per_month', 0)
        if downloads < 1000:
            risk_score += 0.1

        # Transitive depth (deep deps = higher risk)
        depth = dep.get('transitive_depth', 0)
        if depth > 5:
            risk_score += 0.1

        # Security policy (lack of = risk)
        if not dep.get('has_security_policy', False):
            risk_score += 0.05

        # Normalize to 0-1 range
        risk_score = min(risk_score, 1.0)

        # Map to risk categories
        if risk_score >= 0.75:
            return 'CRITICAL'
        elif risk_score >= 0.5:
            return 'HIGH'
        elif risk_score >= 0.25:
            return 'MEDIUM'
        else:
            return 'LOW'

    def generate_synthetic_training_data(self, n_samples=1000):
        """Generate synthetic dependency risk data"""
        print(f"Generating {n_samples} synthetic dependency examples...")

        np.random.seed(42)
        training_data = []

        ecosystems = ['npm', 'pypi', 'maven']
        licenses = ['MIT', 'Apache-2.0', 'BSD-3-Clause', 'GPL-3.0', 'ISC', 'unknown']

        for i in range(n_samples):
            # Simulate various dependency patterns

            # 20% critical risk (high vulnerabilities, abandoned)
            if i < n_samples * 0.2:
                dep = {
                    'name': f'abandoned-package-{i}',
                    'version_age_days': np.random.randint(730, 3650),
                    'commits_last_year': np.random.randint(0, 5),
                    'open_issues': np.random.randint(50, 300),
                    'open_prs': np.random.randint(10, 50),
                    'closed_issues_last_month': np.random.randint(0, 2),
                    'known_vulnerabilities': np.random.randint(2, 10),
                    'has_security_policy': False,
                    'cve_count': np.random.randint(1, 5),
                    'downloads_per_month': np.random.randint(100, 10000),
                    'github_stars': np.random.randint(10, 500),
                    'num_dependents': np.random.randint(5, 100),
                    'major_versions_behind': np.random.randint(1, 5),
                    'minor_versions_behind': np.random.randint(3, 20),
                    'breaking_changes_in_latest': np.random.randint(1, 5),
                    'license': np.random.choice(licenses),
                    'transitive_depth': np.random.randint(3, 10),
                    'total_transitive_deps': np.random.randint(50, 200),
                    'is_dev_dependency': np.random.choice([True, False]),
                    'is_optional': False,
                    'ecosystem': np.random.choice(ecosystems),
                    'is_core_dependency': np.random.choice([True, False]),
                    'num_reverse_deps': np.random.randint(0, 50),
                }

            # 25% high risk (some vulnerabilities, outdated)
            elif i < n_samples * 0.45:
                dep = {
                    'name': f'outdated-package-{i}',
                    'version_age_days': np.random.randint(365, 730),
                    'commits_last_year': np.random.randint(5, 30),
                    'open_issues': np.random.randint(20, 100),
                    'open_prs': np.random.randint(5, 20),
                    'closed_issues_last_month': np.random.randint(1, 10),
                    'known_vulnerabilities': np.random.randint(0, 3),
                    'has_security_policy': np.random.choice([True, False]),
                    'cve_count': np.random.randint(0, 2),
                    'downloads_per_month': np.random.randint(5000, 100000),
                    'github_stars': np.random.randint(100, 2000),
                    'num_dependents': np.random.randint(50, 500),
                    'major_versions_behind': np.random.randint(0, 2),
                    'minor_versions_behind': np.random.randint(1, 5),
                    'breaking_changes_in_latest': np.random.randint(0, 2),
                    'license': np.random.choice(licenses),
                    'transitive_depth': np.random.randint(2, 6),
                    'total_transitive_deps': np.random.randint(20, 100),
                    'is_dev_dependency': np.random.choice([True, False]),
                    'is_optional': np.random.choice([True, False]),
                    'ecosystem': np.random.choice(ecosystems),
                    'is_core_dependency': np.random.choice([True, False]),
                    'num_reverse_deps': np.random.randint(10, 500),
                }

            # 30% medium risk (somewhat outdated, minor issues)
            elif i < n_samples * 0.75:
                dep = {
                    'name': f'moderate-package-{i}',
                    'version_age_days': np.random.randint(90, 365),
                    'commits_last_year': np.random.randint(30, 100),
                    'open_issues': np.random.randint(5, 50),
                    'open_prs': np.random.randint(2, 15),
                    'closed_issues_last_month': np.random.randint(5, 30),
                    'known_vulnerabilities': 0,
                    'has_security_policy': np.random.choice([True, False]),
                    'cve_count': 0,
                    'downloads_per_month': np.random.randint(50000, 500000),
                    'github_stars': np.random.randint(500, 5000),
                    'num_dependents': np.random.randint(200, 2000),
                    'major_versions_behind': 0,
                    'minor_versions_behind': np.random.randint(0, 3),
                    'breaking_changes_in_latest': np.random.randint(0, 1),
                    'license': np.random.choice(licenses),
                    'transitive_depth': np.random.randint(1, 4),
                    'total_transitive_deps': np.random.randint(10, 50),
                    'is_dev_dependency': np.random.choice([True, False]),
                    'is_optional': np.random.choice([True, False]),
                    'ecosystem': np.random.choice(ecosystems),
                    'is_core_dependency': np.random.choice([True, False]),
                    'num_reverse_deps': np.random.randint(50, 2000),
                }

            # 25% low risk (actively maintained, up-to-date)
            else:
                dep = {
                    'name': f'healthy-package-{i}',
                    'version_age_days': np.random.randint(0, 90),
                    'commits_last_year': np.random.randint(100, 500),
                    'open_issues': np.random.randint(0, 20),
                    'open_prs': np.random.randint(0, 10),
                    'closed_issues_last_month': np.random.randint(10, 50),
                    'known_vulnerabilities': 0,
                    'has_security_policy': True,
                    'cve_count': 0,
                    'downloads_per_month': np.random.randint(500000, 5000000),
                    'github_stars': np.random.randint(2000, 50000),
                    'num_dependents': np.random.randint(1000, 10000),
                    'major_versions_behind': 0,
                    'minor_versions_behind': 0,
                    'breaking_changes_in_latest': 0,
                    'license': np.random.choice(['MIT', 'Apache-2.0', 'BSD-3-Clause']),
                    'transitive_depth': np.random.randint(0, 3),
                    'total_transitive_deps': np.random.randint(0, 30),
                    'is_dev_dependency': np.random.choice([True, False]),
                    'is_optional': np.random.choice([True, False]),
                    'ecosystem': np.random.choice(ecosystems),
                    'is_core_dependency': np.random.choice([True, False]),
                    'num_reverse_deps': np.random.randint(100, 10000),
                }

            # Compute risk level
            risk_level = self.compute_risk_score(dep)

            # Extract features
            features = self.extract_features(dep)

            training_data.append({
                'dependency': dep,
                'features': features,
                'risk_level': risk_level
            })

        return training_data

    def train(self, training_data=None):
        """Train XGBoost/RandomForest classifier for dependency risk prediction"""

        # Load data
        if training_data is None:
            training_data = self.generate_synthetic_training_data()

        # Extract features and labels
        feature_names = list(training_data[0]['features'].keys())
        self.feature_names = feature_names

        X = np.array([[sample['features'][f] for f in feature_names]
                      for sample in training_data])
        y_labels = np.array([sample['risk_level'] for sample in training_data])

        # Encode labels
        y = self.label_encoder.fit_transform(y_labels)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print(f"\n📊 Training on {len(X_train)} samples, testing on {len(X_test)} samples")
        print(f"Features: {len(feature_names)}")
        print(f"Risk levels: {self.RISK_LEVELS}")

        # Distribution
        unique, counts = np.unique(y_train, return_counts=True)
        print("\nTraining distribution:")
        for label_idx, count in zip(unique, counts):
            label = self.label_encoder.inverse_transform([label_idx])[0]
            print(f"  {label:10s}: {count:4d} ({100*count/len(y_train):5.1f}%)")

        # Train model
        print(f"\n🌲 Training {CLASSIFIER_TYPE} classifier...")

        if CLASSIFIER_TYPE == "XGBoost":
            self.model = XGBClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=-1,
                eval_metric='mlogloss'
            )
        else:
            self.model = XGBClassifier(
                n_estimators=200,
                max_depth=15,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )

        self.model.fit(X_train, y_train)

        # Predictions
        y_pred_train = self.model.predict(X_train)
        y_pred_test = self.model.predict(X_test)

        # Metrics
        train_acc = accuracy_score(y_train, y_pred_train)
        test_acc = accuracy_score(y_test, y_pred_test)
        test_f1_macro = f1_score(y_test, y_pred_test, average='macro')
        test_f1_weighted = f1_score(y_test, y_pred_test, average='weighted')

        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train, y_train, cv=5, scoring='f1_macro')

        # Classification report
        print("\n" + "="*60)
        print("📊 CLASSIFICATION REPORT (Test Set)")
        print("="*60)
        print(classification_report(
            y_test, y_pred_test,
            target_names=self.label_encoder.classes_.tolist(),
            digits=3
        ))

        # Confusion matrix
        print("="*60)
        print("📊 CONFUSION MATRIX (Test Set)")
        print("="*60)
        cm = confusion_matrix(y_test, y_pred_test)
        labels = self.label_encoder.classes_

        # Print header
        print(f"{'':12s}", end='')
        for label in labels:
            print(f"{label:>10s}", end='')
        print()

        # Print matrix
        for i, label in enumerate(labels):
            print(f"{label:12s}", end='')
            for j in range(len(labels)):
                print(f"{cm[i][j]:10d}", end='')
            print()

        # Feature importance
        if hasattr(self.model, 'feature_importances_'):
            importance_dict = dict(zip(feature_names, self.model.feature_importances_))
            sorted_importance = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        else:
            sorted_importance = []

        # Store stats
        self.training_stats = {
            'classifier': CLASSIFIER_TYPE,
            'n_train': len(X_train),
            'n_test': len(X_test),
            'n_features': len(feature_names),
            'feature_names': feature_names,
            'risk_levels': self.label_encoder.classes_.tolist(),
            'train_accuracy': float(train_acc),
            'test_accuracy': float(test_acc),
            'test_f1_macro': float(test_f1_macro),
            'test_f1_weighted': float(test_f1_weighted),
            'cv_f1_mean': float(cv_scores.mean()),
            'cv_f1_std': float(cv_scores.std()),
            'confusion_matrix': cm.tolist(),
            'feature_importance': {k: float(v) for k, v in sorted_importance}
        }

        # Print summary
        print("\n" + "="*60)
        print("📊 TRAINING SUMMARY")
        print("="*60)
        print(f"Classifier:        {CLASSIFIER_TYPE}")
        print(f"Train Accuracy:    {train_acc:.4f}")
        print(f"Test Accuracy:     {test_acc:.4f}")
        print(f"Test F1 (macro):   {test_f1_macro:.4f}")
        print(f"Test F1 (weighted):{test_f1_weighted:.4f}")
        print(f"CV F1 (5-fold):    {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

        print("\n🔝 TOP 10 FEATURES:")
        for feat, imp in sorted_importance[:10]:
            print(f"  {feat:30s} {imp:.4f}")

        return self.training_stats

    def predict(self, dependency_info):
        """Predict risk level for a dependency"""
        if self.model is None:
            raise RuntimeError("Model not trained yet - call train() first")

        features = self.extract_features(dependency_info)
        X = np.array([[features[f] for f in self.feature_names]])

        prediction_idx = self.model.predict(X)[0]
        risk_level = self.label_encoder.inverse_transform([prediction_idx])[0]

        # Get probability distribution if available
        if hasattr(self.model, 'predict_proba'):
            probs = self.model.predict_proba(X)[0]
            risk_probabilities = {
                label: float(prob)
                for label, prob in zip(self.label_encoder.classes_, probs)
            }
        else:
            risk_probabilities = {}

        return {
            'dependency_name': dependency_info.get('name', 'unknown'),
            'risk_level': risk_level,
            'risk_probabilities': risk_probabilities,
            'features': features
        }

    def save(self, filepath):
        """Save trained model to disk"""
        data = {
            'model': self.model,
            'label_encoder': self.label_encoder,
            'training_stats': self.training_stats,
            'feature_names': self.feature_names,
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Model saved to {filepath}")

    def load(self, filepath):
        """Load trained model from disk"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.model = data['model']
        self.label_encoder = data['label_encoder']
        self.training_stats = data['training_stats']
        self.feature_names = data['feature_names']
        print(f"✅ Model loaded from {filepath}")


def main():
    """Train and evaluate the dependency risk analyzer"""

    print("=" * 60)
    print("DEPENDENCY RISK ANALYZER - TRAINING")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Classifier: {CLASSIFIER_TYPE}")

    # Initialize analyzer
    analyzer = DependencyRiskAnalyzer()

    # Train
    stats = analyzer.train()

    # Save model
    model_path = Path.home() / "Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning" / "dependency_risk_analyzer.pkl"
    analyzer.save(model_path)

    # Save stats
    stats_path = model_path.parent / "dependency_risk_analyzer_stats.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✅ Stats saved to {stats_path}")

    # Test predictions
    print("\n" + "="*60)
    print("🧪 TESTING PREDICTIONS")
    print("="*60)

    test_cases = [
        {
            'name': 'lodash',
            'version_age_days': 30,
            'commits_last_year': 150,
            'open_issues': 50,
            'open_prs': 10,
            'closed_issues_last_month': 20,
            'known_vulnerabilities': 0,
            'has_security_policy': True,
            'cve_count': 0,
            'downloads_per_month': 50000000,
            'github_stars': 50000,
            'num_dependents': 100000,
            'major_versions_behind': 0,
            'minor_versions_behind': 0,
            'breaking_changes_in_latest': 0,
            'license': 'MIT',
            'transitive_depth': 1,
            'total_transitive_deps': 5,
            'is_dev_dependency': False,
            'is_optional': False,
            'ecosystem': 'npm',
            'is_core_dependency': True,
            'num_reverse_deps': 50000,
        },
        {
            'name': 'old-vulnerable-package',
            'version_age_days': 1825,
            'commits_last_year': 2,
            'open_issues': 150,
            'open_prs': 30,
            'closed_issues_last_month': 0,
            'known_vulnerabilities': 5,
            'has_security_policy': False,
            'cve_count': 3,
            'downloads_per_month': 5000,
            'github_stars': 200,
            'num_dependents': 50,
            'major_versions_behind': 3,
            'minor_versions_behind': 15,
            'breaking_changes_in_latest': 4,
            'license': 'unknown',
            'transitive_depth': 8,
            'total_transitive_deps': 150,
            'is_dev_dependency': False,
            'is_optional': False,
            'ecosystem': 'npm',
            'is_core_dependency': True,
            'num_reverse_deps': 10,
        },
        {
            'name': 'moderately-outdated',
            'version_age_days': 180,
            'commits_last_year': 40,
            'open_issues': 30,
            'open_prs': 8,
            'closed_issues_last_month': 5,
            'known_vulnerabilities': 1,
            'has_security_policy': True,
            'cve_count': 0,
            'downloads_per_month': 100000,
            'github_stars': 1500,
            'num_dependents': 500,
            'major_versions_behind': 0,
            'minor_versions_behind': 2,
            'breaking_changes_in_latest': 1,
            'license': 'Apache-2.0',
            'transitive_depth': 3,
            'total_transitive_deps': 30,
            'is_dev_dependency': True,
            'is_optional': False,
            'ecosystem': 'npm',
            'is_core_dependency': False,
            'num_reverse_deps': 200,
        }
    ]

    for dep in test_cases:
        result = analyzer.predict(dep)
        print(f"\nDependency: {result['dependency_name']}")
        print(f"  Risk Level: {result['risk_level']}")
        if result['risk_probabilities']:
            print("  Probabilities:")
            for level, prob in sorted(result['risk_probabilities'].items(),
                                     key=lambda x: x[1], reverse=True):
                print(f"    {level:10s}: {prob:.3f}")

    print("\n" + "="*60)
    print("✅ TRAINING COMPLETE")
    print("="*60)
    print(f"Models saved to: {model_path}")
    print(f"Stats saved to:  {stats_path}")

    # Return summary
    summary = {
        'status': 'SUCCESS',
        'classifier': CLASSIFIER_TYPE,
        'test_accuracy': stats['test_accuracy'],
        'test_f1_macro': stats['test_f1_macro'],
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
