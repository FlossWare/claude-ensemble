#!/usr/bin/env python3
"""
Counterfactual Reasoning System - Random Forest Multi-Output Classifier

Predicts outcomes of hypothetical "what-if" scenarios before execution:
- Impact severity (low/medium/high/critical)
- Success probability
- Affected components
- Rollback difficulty
- Side effects likelihood

Algorithm: Random Forest Multi-Output Classifier (sklearn)
Training data: Synthetic what-if scenarios + real change impact data from database

Example scenarios:
- "What if we increase timeout from 30s to 120s?"
- "What if we remove this deprecated API endpoint?"
- "What if we upgrade Python from 3.9 to 3.12?"
- "What if we switch from REST to gRPC?"
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder
import pickle

# Try to import psycopg2 for database access
try:
    import psycopg2
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("⚠ psycopg2 not available - using synthetic training data")


class CounterfactualReasoner:
    """Predicts outcomes of hypothetical changes before execution"""

    def __init__(self):
        self.impact_model = None  # Classifier for impact severity
        self.success_model = None  # Regressor for success probability
        self.rollback_model = None  # Regressor for rollback difficulty
        self.side_effects_model = None  # Regressor for side effects likelihood
        self.feature_names = []
        self.training_stats = {}
        self.impact_encoder = LabelEncoder()
        self.impact_labels = ['low', 'medium', 'high', 'critical']

    def extract_features(self, scenario_description):
        """Extract features from what-if scenario description"""
        text = scenario_description.lower()

        # Change type detection
        is_config_change = any(word in text for word in ['config', 'timeout', 'limit', 'threshold', 'setting'])
        is_code_change = any(word in text for word in ['implement', 'add', 'remove', 'refactor', 'function'])
        is_version_change = any(word in text for word in ['upgrade', 'downgrade', 'version', 'migrate'])
        is_architecture_change = any(word in text for word in ['switch', 'replace', 'architecture', 'framework'])
        is_data_change = any(word in text for word in ['database', 'schema', 'migration', 'data'])
        is_api_change = any(word in text for word in ['api', 'endpoint', 'interface', 'contract'])

        # Risk indicators
        has_breaking_keywords = any(word in text for word in ['remove', 'delete', 'deprecate', 'breaking'])
        has_critical_systems = any(word in text for word in ['auth', 'payment', 'security', 'production'])
        has_data_risk = any(word in text for word in ['database', 'data', 'migration', 'schema'])
        has_user_impact = any(word in text for word in ['user', 'customer', 'client', 'frontend'])
        has_dependency = any(word in text for word in ['dependency', 'library', 'package', 'module'])

        # Numeric change detection
        numeric_changes = re.findall(r'(\d+(?:\.\d+)?)\s*(?:to|->)\s*(\d+(?:\.\d+)?)', text)
        has_numeric_change = len(numeric_changes) > 0

        # Calculate magnitude of change if numeric
        change_magnitude = 0.0
        if has_numeric_change:
            try:
                before, after = float(numeric_changes[0][0]), float(numeric_changes[0][1])
                if before > 0:
                    change_magnitude = abs(after - before) / before
            except:
                pass

        # Version change detection
        version_pattern = r'(\d+\.\d+(?:\.\d+)?)\s*(?:to|->)\s*(\d+\.\d+(?:\.\d+)?)'
        version_matches = re.findall(version_pattern, text)
        is_major_version_change = False
        if version_matches:
            try:
                before_ver = version_matches[0][0].split('.')
                after_ver = version_matches[0][1].split('.')
                is_major_version_change = before_ver[0] != after_ver[0]
            except:
                pass

        features = {
            'scenario_length': len(scenario_description),
            'word_count': len(scenario_description.split()),

            # Change type (one-hot)
            'is_config_change': int(is_config_change),
            'is_code_change': int(is_code_change),
            'is_version_change': int(is_version_change),
            'is_architecture_change': int(is_architecture_change),
            'is_data_change': int(is_data_change),
            'is_api_change': int(is_api_change),

            # Risk indicators
            'has_breaking_keywords': int(has_breaking_keywords),
            'has_critical_systems': int(has_critical_systems),
            'has_data_risk': int(has_data_risk),
            'has_user_impact': int(has_user_impact),
            'has_dependency': int(has_dependency),

            # Change magnitude
            'has_numeric_change': int(has_numeric_change),
            'change_magnitude': float(change_magnitude),
            'is_major_version_change': int(is_major_version_change),

            # Action keywords
            'num_increase': text.count('increase') + text.count('raise') + text.count('grow'),
            'num_decrease': text.count('decrease') + text.count('reduce') + text.count('lower'),
            'num_add': text.count('add') + text.count('create') + text.count('new'),
            'num_remove': text.count('remove') + text.count('delete') + text.count('deprecate'),
            'num_replace': text.count('replace') + text.count('switch') + text.count('migrate'),

            # Question marks (uncertainty)
            'num_questions': text.count('?'),
        }

        return features

    def generate_synthetic_training_data(self, n_samples=800):
        """Generate synthetic what-if scenarios with expected outcomes"""
        print(f"Generating {n_samples} synthetic what-if scenarios...")

        # Scenario templates: (description, impact, success_prob, rollback_difficulty, side_effects_likelihood)
        # impact: low/medium/high/critical
        # scores: 0.0-1.0

        scenario_templates = [
            # Low impact - configuration tweaks
            ("What if we increase API timeout from 30s to 60s?", "low", 0.90, 0.15, 0.20),
            ("What if we change log level from INFO to DEBUG?", "low", 0.95, 0.10, 0.15),
            ("What if we increase connection pool size from 10 to 20?", "low", 0.85, 0.20, 0.25),
            ("What if we enable caching for static assets?", "low", 0.88, 0.18, 0.22),
            ("What if we reduce session timeout from 60min to 30min?", "low", 0.82, 0.25, 0.30),

            # Medium impact - code changes
            ("What if we refactor authentication module to use OAuth2?", "medium", 0.70, 0.45, 0.55),
            ("What if we add rate limiting to public API endpoints?", "medium", 0.75, 0.35, 0.40),
            ("What if we switch from sync to async database queries?", "medium", 0.65, 0.50, 0.60),
            ("What if we implement request batching for microservices?", "medium", 0.72, 0.40, 0.48),
            ("What if we add input validation to all API endpoints?", "medium", 0.80, 0.30, 0.35),

            # High impact - architecture changes
            ("What if we migrate from REST to gRPC?", "high", 0.55, 0.70, 0.75),
            ("What if we switch from PostgreSQL to MongoDB?", "high", 0.45, 0.85, 0.90),
            ("What if we upgrade Python from 3.9 to 3.12?", "high", 0.60, 0.65, 0.70),
            ("What if we replace Redis with Memcached?", "high", 0.58, 0.68, 0.72),
            ("What if we move from monolith to microservices?", "high", 0.50, 0.75, 0.80),

            # Critical impact - breaking changes
            ("What if we remove deprecated API endpoint used by 50% of clients?", "critical", 0.30, 0.90, 0.95),
            ("What if we change database schema without migration path?", "critical", 0.25, 0.95, 0.98),
            ("What if we disable backward compatibility in authentication?", "critical", 0.35, 0.88, 0.92),
            ("What if we upgrade database from version 10 to 15 in production?", "critical", 0.40, 0.82, 0.85),
            ("What if we change payment API contract without versioning?", "critical", 0.28, 0.92, 0.96),

            # Data changes
            ("What if we add new index to users table with 10M rows?", "medium", 0.68, 0.42, 0.50),
            ("What if we delete unused columns from production database?", "high", 0.52, 0.72, 0.78),
            ("What if we change primary key type from int to UUID?", "critical", 0.32, 0.89, 0.93),

            # Version upgrades
            ("What if we upgrade Node.js from 16 to 20?", "medium", 0.73, 0.38, 0.45),
            ("What if we upgrade React from 17 to 18?", "medium", 0.76, 0.35, 0.42),
            ("What if we upgrade Django from 3.2 to 5.0?", "high", 0.56, 0.66, 0.71),

            # Security changes
            ("What if we enforce HTTPS everywhere?", "medium", 0.78, 0.33, 0.38),
            ("What if we require MFA for all admin users?", "medium", 0.81, 0.28, 0.32),
            ("What if we rotate all API keys in production?", "high", 0.54, 0.69, 0.74),
        ]

        training_data = []

        for _ in range(n_samples):
            # Pick random template
            template, impact, success_prob, rollback_diff, side_effects = scenario_templates[
                np.random.randint(len(scenario_templates))
            ]

            # Add random variation
            success_prob = min(1.0, max(0.1, success_prob + np.random.uniform(-0.1, 0.1)))
            rollback_diff = min(1.0, max(0.0, rollback_diff + np.random.uniform(-0.08, 0.08)))
            side_effects = min(1.0, max(0.0, side_effects + np.random.uniform(-0.08, 0.08)))

            # Optionally add complexity
            if np.random.random() < 0.25:
                template += " without downtime"
                rollback_diff = min(1.0, rollback_diff * 1.2)
                side_effects = min(1.0, side_effects * 1.15)
                success_prob *= 0.92

            if np.random.random() < 0.20:
                template += " in production"
                rollback_diff = min(1.0, rollback_diff * 1.15)
                side_effects = min(1.0, side_effects * 1.1)
                success_prob *= 0.95

            features = self.extract_features(template)
            training_data.append({
                'scenario': template,
                'features': features,
                'impact': impact,
                'success_probability': success_prob,
                'rollback_difficulty': rollback_diff,
                'side_effects_likelihood': side_effects
            })

        return training_data

    def load_database_training_data(self):
        """Load real what-if scenario data from PostgreSQL if available"""
        if not DB_AVAILABLE:
            return None

        try:
            conn = psycopg2.connect(
                host="aio-01",
                port=5433,
                database="learning",
                user="claude",
                connect_timeout=5
            )

            cursor = conn.cursor()

            # Try to get change impact data from workflow results
            cursor.execute("""
                SELECT
                    task_assigned,
                    CASE
                        WHEN confidence > 0.8 THEN 'low'
                        WHEN confidence > 0.6 THEN 'medium'
                        WHEN confidence > 0.4 THEN 'high'
                        ELSE 'critical'
                    END as impact,
                    confidence as success_prob,
                    CASE WHEN outcome = 'success' THEN 0.2 ELSE 0.8 END as rollback_diff
                FROM workflow.worker_results
                WHERE task_assigned LIKE '%what if%'
                   OR task_assigned LIKE '%if we%'
                   OR task_assigned LIKE '%change%'
                LIMIT 500
            """)

            rows = cursor.fetchall()
            conn.close()

            if len(rows) < 5:
                return None

            training_data = []
            for task, impact, success_prob, rollback_diff in rows:
                features = self.extract_features(task)
                training_data.append({
                    'scenario': task,
                    'features': features,
                    'impact': impact,
                    'success_probability': success_prob,
                    'rollback_difficulty': rollback_diff,
                    'side_effects_likelihood': 1.0 - success_prob
                })

            print(f"✅ Loaded {len(training_data)} real scenarios from database")
            return training_data

        except Exception as e:
            print(f"⚠ Database unavailable: {e}")
            return None

    def train(self, training_data=None):
        """Train Random Forest models for counterfactual reasoning"""

        # Load data
        if training_data is None:
            # Try database first
            training_data = self.load_database_training_data()

            # Fall back to synthetic
            if training_data is None:
                training_data = self.generate_synthetic_training_data()

        # Encode impact labels
        self.impact_encoder.fit(self.impact_labels)

        # Extract features and targets
        self.feature_names = list(training_data[0]['features'].keys())
        X = np.array([[sample['features'][f] for f in self.feature_names]
                      for sample in training_data])

        y_impact = self.impact_encoder.transform([sample['impact'] for sample in training_data])
        y_success = np.array([sample['success_probability'] for sample in training_data])
        y_rollback = np.array([sample['rollback_difficulty'] for sample in training_data])
        y_side_effects = np.array([sample['side_effects_likelihood'] for sample in training_data])

        # Split data
        indices = np.arange(len(X))
        X_train, X_test, y_imp_train, y_imp_test, y_succ_train, y_succ_test, \
        y_roll_train, y_roll_test, y_side_train, y_side_test, idx_train, idx_test = train_test_split(
            X, y_impact, y_success, y_rollback, y_side_effects, indices,
            test_size=0.2, random_state=42, stratify=y_impact
        )

        print(f"\n📊 Training on {len(X_train)} scenarios, testing on {len(X_test)} scenarios")
        print(f"Features: {len(self.feature_names)}")

        # Train impact classifier
        print("\n🌲 Training impact severity classifier (Random Forest)...")
        self.impact_model = RandomForestClassifier(
            n_estimators=150,
            max_depth=12,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        )
        self.impact_model.fit(X_train, y_imp_train)

        imp_pred_train = self.impact_model.predict(X_train)
        imp_pred_test = self.impact_model.predict(X_test)

        imp_train_acc = accuracy_score(y_imp_train, imp_pred_train)
        imp_test_acc = accuracy_score(y_imp_test, imp_pred_test)

        # Train success probability regressor
        print("🌲 Training success probability regressor...")
        self.success_model = RandomForestRegressor(
            n_estimators=120,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        self.success_model.fit(X_train, y_succ_train)

        succ_pred_test = self.success_model.predict(X_test)
        succ_r2 = r2_score(y_succ_test, succ_pred_test)
        succ_mae = mean_absolute_error(y_succ_test, succ_pred_test)

        # Train rollback difficulty regressor
        print("🌲 Training rollback difficulty regressor...")
        self.rollback_model = RandomForestRegressor(
            n_estimators=120,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        self.rollback_model.fit(X_train, y_roll_train)

        roll_pred_test = self.rollback_model.predict(X_test)
        roll_r2 = r2_score(y_roll_test, roll_pred_test)
        roll_mae = mean_absolute_error(y_roll_test, roll_pred_test)

        # Train side effects regressor
        print("🌲 Training side effects likelihood regressor...")
        self.side_effects_model = RandomForestRegressor(
            n_estimators=120,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        self.side_effects_model.fit(X_train, y_side_train)

        side_pred_test = self.side_effects_model.predict(X_test)
        side_r2 = r2_score(y_side_test, side_pred_test)
        side_mae = mean_absolute_error(y_side_test, side_pred_test)

        # Store stats
        self.training_stats = {
            'n_train': len(X_train),
            'n_test': len(X_test),
            'n_features': len(self.feature_names),
            'feature_names': self.feature_names,
            'impact': {
                'train_accuracy': float(imp_train_acc),
                'test_accuracy': float(imp_test_acc),
                'labels': self.impact_labels,
            },
            'success_probability': {
                'r2': float(succ_r2),
                'mae': float(succ_mae),
            },
            'rollback_difficulty': {
                'r2': float(roll_r2),
                'mae': float(roll_mae),
            },
            'side_effects': {
                'r2': float(side_r2),
                'mae': float(side_mae),
            }
        }

        # Feature importance
        imp_importance = dict(zip(self.feature_names, self.impact_model.feature_importances_))
        succ_importance = dict(zip(self.feature_names, self.success_model.feature_importances_))

        self.training_stats['feature_importance'] = {
            'impact': {k: float(v) for k, v in sorted(imp_importance.items(),
                                                      key=lambda x: x[1], reverse=True)},
            'success': {k: float(v) for k, v in sorted(succ_importance.items(),
                                                       key=lambda x: x[1], reverse=True)}
        }

        # Print results
        print("\n" + "="*70)
        print("📊 TRAINING RESULTS - COUNTERFACTUAL REASONING")
        print("="*70)
        print(f"\n🎯 IMPACT SEVERITY CLASSIFIER:")
        print(f"  Train Accuracy: {imp_train_acc:.4f}")
        print(f"  Test Accuracy:  {imp_test_acc:.4f}")

        print(f"\n✅ SUCCESS PROBABILITY REGRESSOR:")
        print(f"  R²:   {succ_r2:.4f}")
        print(f"  MAE:  {succ_mae:.4f}")

        print(f"\n🔄 ROLLBACK DIFFICULTY REGRESSOR:")
        print(f"  R²:   {roll_r2:.4f}")
        print(f"  MAE:  {roll_mae:.4f}")

        print(f"\n⚠️  SIDE EFFECTS REGRESSOR:")
        print(f"  R²:   {side_r2:.4f}")
        print(f"  MAE:  {side_mae:.4f}")

        print("\n🔝 TOP FEATURES (Impact):")
        for feat, imp in list(self.training_stats['feature_importance']['impact'].items())[:5]:
            print(f"  {feat:30s} {imp:.4f}")

        return self.training_stats

    def predict(self, scenario_description):
        """Predict outcome of a what-if scenario"""
        if self.impact_model is None:
            raise RuntimeError("Models not trained yet - call train() first")

        features = self.extract_features(scenario_description)
        X = np.array([[features[f] for f in self.feature_names]])

        # Predictions
        impact_encoded = self.impact_model.predict(X)[0]
        impact = self.impact_encoder.inverse_transform([impact_encoded])[0]
        impact_proba = self.impact_model.predict_proba(X)[0]

        success_prob = float(np.clip(self.success_model.predict(X)[0], 0.0, 1.0))
        rollback_diff = float(np.clip(self.rollback_model.predict(X)[0], 0.0, 1.0))
        side_effects = float(np.clip(self.side_effects_model.predict(X)[0], 0.0, 1.0))

        # Risk score (0-1, higher = riskier)
        risk_score = (
            0.3 * (self.impact_labels.index(impact) / len(self.impact_labels)) +
            0.25 * (1.0 - success_prob) +
            0.25 * rollback_diff +
            0.20 * side_effects
        )

        # Recommendation
        if risk_score < 0.3:
            recommendation = "PROCEED - Low risk, high confidence"
        elif risk_score < 0.5:
            recommendation = "PROCEED WITH CAUTION - Medium risk, test thoroughly"
        elif risk_score < 0.7:
            recommendation = "RISKY - High impact, consider alternatives"
        else:
            recommendation = "DO NOT PROCEED - Critical risk, requires extensive planning"

        return {
            'scenario': scenario_description,
            'impact_severity': impact,
            'impact_probabilities': {
                label: float(prob)
                for label, prob in zip(self.impact_labels, impact_proba)
            },
            'success_probability': success_prob,
            'rollback_difficulty': rollback_diff,
            'side_effects_likelihood': side_effects,
            'risk_score': float(risk_score),
            'recommendation': recommendation,
            'features': features
        }

    def save(self, filepath):
        """Save trained models to disk"""
        data = {
            'impact_model': self.impact_model,
            'success_model': self.success_model,
            'rollback_model': self.rollback_model,
            'side_effects_model': self.side_effects_model,
            'impact_encoder': self.impact_encoder,
            'impact_labels': self.impact_labels,
            'feature_names': self.feature_names,
            'training_stats': self.training_stats,
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Models saved to {filepath}")

    def load(self, filepath):
        """Load trained models from disk"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.impact_model = data['impact_model']
        self.success_model = data['success_model']
        self.rollback_model = data['rollback_model']
        self.side_effects_model = data['side_effects_model']
        self.impact_encoder = data['impact_encoder']
        self.impact_labels = data['impact_labels']
        self.feature_names = data['feature_names']
        self.training_stats = data['training_stats']
        print(f"✅ Models loaded from {filepath}")


def main():
    """Train and evaluate the counterfactual reasoning system"""

    print("=" * 70)
    print("COUNTERFACTUAL REASONING SYSTEM - TRAINING")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize reasoner
    reasoner = CounterfactualReasoner()

    # Train
    stats = reasoner.train()

    # Save models
    model_dir = Path.home() / "Development" / "redhat" / "scm" / "gitlab" / "cee" / "sfloess" / "claude-global-skills" / "learning"
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / "counterfactual_reasoner.pkl"
    reasoner.save(model_path)

    # Save stats
    stats_path = model_dir / "counterfactual_reasoner_stats.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✅ Stats saved to {stats_path}")

    # Test predictions
    print("\n" + "="*70)
    print("🧪 TESTING WHAT-IF SCENARIOS")
    print("="*70)

    test_scenarios = [
        "What if we increase API timeout from 30s to 90s?",
        "What if we migrate from REST to gRPC?",
        "What if we remove deprecated endpoint used by 30% of clients?",
        "What if we upgrade Python from 3.9 to 3.12?",
        "What if we enable caching for database queries?",
        "What if we change database schema without migration path?",
        "What if we switch from PostgreSQL to MongoDB in production?",
    ]

    for scenario in test_scenarios:
        result = reasoner.predict(scenario)
        print(f"\n{'='*70}")
        print(f"Scenario: {scenario}")
        print(f"{'='*70}")
        print(f"Impact Severity:       {result['impact_severity'].upper()}")
        print(f"Success Probability:   {result['success_probability']:.2%}")
        print(f"Rollback Difficulty:   {result['rollback_difficulty']:.2%}")
        print(f"Side Effects Risk:     {result['side_effects_likelihood']:.2%}")
        print(f"Overall Risk Score:    {result['risk_score']:.2%}")
        print(f"\n💡 Recommendation: {result['recommendation']}")

    print("\n" + "="*70)
    print("✅ TRAINING COMPLETE")
    print("="*70)
    print(f"Models saved to: {model_path}")
    print(f"Stats saved to:  {stats_path}")

    # Return summary
    return {
        'status': 'SUCCESS',
        'impact_accuracy': stats['impact']['test_accuracy'],
        'success_r2': stats['success_probability']['r2'],
        'n_train': stats['n_train'],
        'n_test': stats['n_test'],
        'model_path': str(model_path),
        'stats_path': str(stats_path),
    }


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
