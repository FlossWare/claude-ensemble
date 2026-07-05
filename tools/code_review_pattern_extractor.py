#!/usr/bin/env python3
"""
Code Review Pattern Extractor

Analyzes workflow database to extract and learn code review patterns:
1. Common issue categories and severity distributions
2. Model performance on different review types
3. Arbiter consensus patterns (what gets validated vs rejected)
4. Task complexity indicators (files, duration, confidence)
5. Predictive model for issue detection likelihood

Uses PostgreSQL workflow.* tables for training data.
Saves trained model to learning/code_review_pattern_extractor.pkl
"""

import psycopg2
import psycopg2.extras
import json
import pickle
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
from typing import Dict, List, Tuple, Optional

# Scikit-learn imports
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix


class CodeReviewPatternExtractor:
    """Extract patterns from code review workflow data"""

    def __init__(self, db_host='aio-01', db_port=5433, db_name='learning', db_user='claude'):
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'dbname': db_name,
            'user': db_user
        }
        self.conn = None
        self.patterns = {
            'issue_categories': Counter(),
            'severity_distribution': Counter(),
            'model_performance': defaultdict(lambda: {'reviews': 0, 'success': 0, 'avg_confidence': 0.0}),
            'arbiter_consensus': {'validated': 0, 'rejected': 0, 'patterns': []},
            'task_complexity': {'simple': 0, 'medium': 0, 'complex': 0},
            'common_files': Counter(),
            'review_outcomes': Counter(),
            'time_to_resolution': []
        }

        # ML models
        self.issue_predictor = None  # Predict if task will find issues
        self.severity_classifier = None  # Classify issue severity
        self.tfidf_vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        self.scaler = StandardScaler()

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            return True
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def extract_review_tasks(self, window_days=90) -> List[Dict]:
        """Extract review tasks from workflow.worker_results"""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = f"""
            SELECT
                wr.id,
                wr.workflow_execution_id,
                wr.worker_id,
                wr.model,
                wr.task_assigned,
                wr.result,
                wr.confidence,
                wr.duration_ms,
                wr.input_tokens,
                wr.output_tokens,
                wr.cost_usd,
                wr.outcome,
                wr.metadata,
                wr.created_at,
                we.workflow_name,
                we.task_description,
                we.total_duration_ms,
                we.outcome as workflow_outcome
            FROM workflow.worker_results wr
            JOIN workflow.executions we ON wr.workflow_execution_id = we.id
            WHERE
                (wr.task_assigned ILIKE '%review%'
                 OR wr.task_assigned ILIKE '%bug%'
                 OR wr.task_assigned ILIKE '%fix%'
                 OR wr.task_assigned ILIKE '%issue%')
                AND wr.created_at > NOW() - INTERVAL '{window_days} days'
            ORDER BY wr.created_at DESC
        """

        cursor.execute(query)
        tasks = cursor.fetchall()
        cursor.close()

        return [dict(task) for task in tasks]

    def extract_arbiter_decisions(self, window_days=90) -> List[Dict]:
        """Extract arbiter consensus decisions"""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = f"""
            SELECT
                ad.id,
                ad.workflow_execution_id,
                ad.arbiter_model,
                ad.worker_result_ids,
                ad.decision,
                ad.reasoning,
                ad.confidence,
                ad.duration_ms,
                ad.metadata,
                ad.created_at
            FROM workflow.arbiter_decisions ad
            WHERE ad.created_at > NOW() - INTERVAL '{window_days} days'
            ORDER BY ad.created_at DESC
        """

        cursor.execute(query)
        decisions = cursor.fetchall()
        cursor.close()

        return [dict(decision) for decision in decisions]

    def parse_issue_data(self, result_text: str) -> Dict:
        """Parse issue information from result text"""
        issue_data = {
            'has_issues': False,
            'issue_count': 0,
            'categories': [],
            'severities': [],
            'files_mentioned': []
        }

        if not result_text:
            return issue_data

        # Detect if issues were found
        issue_keywords = ['bug', 'error', 'issue', 'problem', 'vulnerability', 'fix']
        text_lower = result_text.lower()

        for keyword in issue_keywords:
            if keyword in text_lower:
                issue_data['has_issues'] = True
                break

        # Extract categories
        categories = ['bug', 'security', 'performance', 'style', 'maintainability', 'documentation']
        for cat in categories:
            if cat in text_lower:
                issue_data['categories'].append(cat)

        # Extract severities
        severities = ['critical', 'high', 'medium', 'low']
        for sev in severities:
            if sev in text_lower:
                issue_data['severities'].append(sev)

        # Extract file mentions
        file_pattern = r'[\w\-]+\.(py|js|mjs|cjs|java|ts|tsx|jsx|go|rs|cpp|c|h)'
        files = re.findall(file_pattern, text_lower)
        issue_data['files_mentioned'] = files

        # Count issues (look for numbered lists or bullet points)
        issue_count_patterns = [
            r'(\d+)\s+issue',
            r'found\s+(\d+)',
            r'total:\s+(\d+)'
        ]
        for pattern in issue_count_patterns:
            match = re.search(pattern, text_lower)
            if match:
                issue_data['issue_count'] = int(match.group(1))
                break

        return issue_data

    def analyze_patterns(self, tasks: List[Dict], decisions: List[Dict]):
        """Analyze patterns from tasks and decisions"""
        print(f"\n📊 Analyzing {len(tasks)} review tasks and {len(decisions)} arbiter decisions...")

        for task in tasks:
            # Parse issue data
            issue_data = self.parse_issue_data(task['result'])

            # Update patterns
            for category in issue_data['categories']:
                self.patterns['issue_categories'][category] += 1

            for severity in issue_data['severities']:
                self.patterns['severity_distribution'][severity] += 1

            # Model performance
            model = task['model']
            self.patterns['model_performance'][model]['reviews'] += 1
            if task['outcome'] == 'success':
                self.patterns['model_performance'][model]['success'] += 1
            if task['confidence']:
                current_avg = self.patterns['model_performance'][model]['avg_confidence']
                current_count = self.patterns['model_performance'][model]['reviews']
                new_avg = (current_avg * (current_count - 1) + task['confidence']) / current_count
                self.patterns['model_performance'][model]['avg_confidence'] = new_avg

            # Task complexity (based on duration and token count)
            duration = task['duration_ms'] or 0
            tokens = task['input_tokens'] or 0

            if duration < 5000 and tokens < 1000:
                self.patterns['task_complexity']['simple'] += 1
            elif duration < 15000 and tokens < 5000:
                self.patterns['task_complexity']['medium'] += 1
            else:
                self.patterns['task_complexity']['complex'] += 1

            # Review outcomes
            self.patterns['review_outcomes'][task['outcome']] += 1

        # Arbiter consensus
        for decision in decisions:
            decision_lower = decision['decision'].lower()

            if 'reject' in decision_lower or 'false positive' in decision_lower:
                self.patterns['arbiter_consensus']['rejected'] += 1
            else:
                self.patterns['arbiter_consensus']['validated'] += 1

            # Store consensus pattern
            self.patterns['arbiter_consensus']['patterns'].append({
                'arbiter': decision['arbiter_model'],
                'confidence': decision['confidence'],
                'reasoning_length': len(decision['reasoning']) if decision['reasoning'] else 0
            })

    def build_ml_features(self, tasks: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """Build feature matrix for ML training"""
        X = []
        y = []

        for task in tasks:
            issue_data = self.parse_issue_data(task['result'])

            # Features
            features = [
                task['duration_ms'] or 0,
                task['input_tokens'] or 0,
                task['output_tokens'] or 0,
                task['confidence'] or 0.5,
                len(issue_data['files_mentioned']),
                len(issue_data['categories']),
                len(issue_data['severities']),
                1 if task['outcome'] == 'success' else 0,
                task['cost_usd'] or 0,
            ]

            X.append(features)

            # Target: Did the review find issues?
            y.append(1 if issue_data['has_issues'] else 0)

        return np.array(X), np.array(y)

    def train_issue_predictor(self, X: np.ndarray, y: np.ndarray):
        """Train model to predict if a review task will find issues"""
        if len(X) < 10:
            print("⚠️ Insufficient data for training (need at least 10 samples)")
            return

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train Random Forest
        self.issue_predictor = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight='balanced'
        )

        self.issue_predictor.fit(X_train_scaled, y_train)

        # Evaluate
        train_score = self.issue_predictor.score(X_train_scaled, y_train)
        test_score = self.issue_predictor.score(X_test_scaled, y_test)

        print(f"\n🤖 Issue Predictor Trained:")
        print(f"   Training accuracy: {train_score:.2%}")
        print(f"   Test accuracy: {test_score:.2%}")

        # Cross-validation
        cv_scores = cross_val_score(self.issue_predictor, X_train_scaled, y_train, cv=5)
        print(f"   Cross-validation: {cv_scores.mean():.2%} ± {cv_scores.std():.2%}")

        # Feature importance
        feature_names = [
            'duration_ms', 'input_tokens', 'output_tokens', 'confidence',
            'files_mentioned', 'categories', 'severities', 'success', 'cost_usd'
        ]

        importances = self.issue_predictor.feature_importances_
        sorted_idx = np.argsort(importances)[::-1]

        print("\n   Top 5 Features:")
        for i in sorted_idx[:5]:
            print(f"      {feature_names[i]}: {importances[i]:.3f}")

    def predict_issue_likelihood(self, task_features: Dict) -> Tuple[float, str]:
        """Predict likelihood of finding issues in a review task"""
        if not self.issue_predictor:
            return 0.5, "Model not trained"

        # Build feature vector
        features = [
            task_features.get('duration_ms', 0),
            task_features.get('input_tokens', 0),
            task_features.get('output_tokens', 0),
            task_features.get('confidence', 0.5),
            task_features.get('files_mentioned', 0),
            task_features.get('categories', 0),
            task_features.get('severities', 0),
            1 if task_features.get('outcome') == 'success' else 0,
            task_features.get('cost_usd', 0)
        ]

        X = np.array([features])
        X_scaled = self.scaler.transform(X)

        # Predict probability
        prob = self.issue_predictor.predict_proba(X_scaled)[0][1]

        # Generate confidence message
        if prob > 0.7:
            message = "High likelihood of finding issues"
        elif prob > 0.5:
            message = "Moderate likelihood of finding issues"
        else:
            message = "Low likelihood of finding issues"

        return prob, message

    def get_top_models(self, n=5) -> List[Tuple[str, Dict]]:
        """Get top N performing models for code review"""
        models = []

        for model, stats in self.patterns['model_performance'].items():
            if stats['reviews'] == 0:
                continue

            success_rate = stats['success'] / stats['reviews']
            score = success_rate * 0.7 + stats['avg_confidence'] * 0.3

            models.append((model, {
                'reviews': stats['reviews'],
                'success_rate': success_rate,
                'avg_confidence': stats['avg_confidence'],
                'score': score
            }))

        # Sort by score
        models.sort(key=lambda x: x[1]['score'], reverse=True)

        return models[:n]

    def get_recommendations(self) -> Dict:
        """Generate recommendations based on patterns"""
        recommendations = {
            'top_models': [],
            'common_issues': [],
            'optimization_tips': [],
            'risk_areas': []
        }

        # Top models
        top_models = self.get_top_models(5)
        for model, stats in top_models:
            recommendations['top_models'].append({
                'model': model,
                'success_rate': f"{stats['success_rate']:.1%}",
                'avg_confidence': f"{stats['avg_confidence']:.2f}",
                'reviews': stats['reviews']
            })

        # Common issues
        for category, count in self.patterns['issue_categories'].most_common(5):
            recommendations['common_issues'].append({
                'category': category,
                'count': count
            })

        # Optimization tips
        if self.patterns['task_complexity']['complex'] > self.patterns['task_complexity']['simple']:
            recommendations['optimization_tips'].append(
                "High complexity tasks detected - consider breaking down into smaller reviews"
            )

        success_rate = (
            self.patterns['review_outcomes'].get('success', 0) /
            max(sum(self.patterns['review_outcomes'].values()), 1)
        )

        if success_rate < 0.8:
            recommendations['optimization_tips'].append(
                f"Success rate {success_rate:.1%} - review task definitions for clarity"
            )

        # Risk areas
        if self.patterns['severity_distribution']['critical'] > 0:
            recommendations['risk_areas'].append({
                'area': 'Critical issues detected',
                'count': self.patterns['severity_distribution']['critical']
            })

        return recommendations

    def save_model(self, filepath: str):
        """Save trained model and patterns"""
        # Convert defaultdict to regular dict for pickling
        patterns_serializable = {
            'issue_categories': dict(self.patterns['issue_categories']),
            'severity_distribution': dict(self.patterns['severity_distribution']),
            'model_performance': dict(self.patterns['model_performance']),
            'arbiter_consensus': self.patterns['arbiter_consensus'],
            'task_complexity': self.patterns['task_complexity'],
            'common_files': dict(self.patterns['common_files']),
            'review_outcomes': dict(self.patterns['review_outcomes']),
            'time_to_resolution': self.patterns['time_to_resolution']
        }

        model_data = {
            'patterns': patterns_serializable,
            'issue_predictor': self.issue_predictor,
            'scaler': self.scaler,
            'tfidf_vectorizer': self.tfidf_vectorizer,
            'trained_at': datetime.now().isoformat(),
            'version': '1.0.0'
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"\n✅ Model saved to {filepath}")

    def load_model(self, filepath: str):
        """Load trained model and patterns"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        # Convert back to Counter objects for compatibility
        patterns = model_data['patterns']
        self.patterns = {
            'issue_categories': Counter(patterns['issue_categories']),
            'severity_distribution': Counter(patterns['severity_distribution']),
            'model_performance': defaultdict(lambda: {'reviews': 0, 'success': 0, 'avg_confidence': 0.0}, patterns['model_performance']),
            'arbiter_consensus': patterns['arbiter_consensus'],
            'task_complexity': patterns['task_complexity'],
            'common_files': Counter(patterns['common_files']),
            'review_outcomes': Counter(patterns['review_outcomes']),
            'time_to_resolution': patterns['time_to_resolution']
        }

        self.issue_predictor = model_data['issue_predictor']
        self.scaler = model_data['scaler']
        self.tfidf_vectorizer = model_data['tfidf_vectorizer']

        print(f"✅ Model loaded from {filepath}")
        print(f"   Trained at: {model_data['trained_at']}")
        print(f"   Version: {model_data['version']}")

    def print_report(self):
        """Print analysis report"""
        print("\n" + "="*80)
        print("CODE REVIEW PATTERN ANALYSIS REPORT")
        print("="*80)

        print("\n📋 ISSUE CATEGORIES:")
        for category, count in self.patterns['issue_categories'].most_common():
            print(f"   {category:20s}: {count:4d}")

        print("\n⚠️ SEVERITY DISTRIBUTION:")
        for severity, count in self.patterns['severity_distribution'].most_common():
            print(f"   {severity:20s}: {count:4d}")

        print("\n🤖 TOP PERFORMING MODELS:")
        top_models = self.get_top_models(5)
        for model, stats in top_models:
            print(f"   {model:30s}: {stats['reviews']:3d} reviews, "
                  f"{stats['success_rate']:5.1%} success, "
                  f"{stats['avg_confidence']:.2f} confidence")

        print("\n📊 TASK COMPLEXITY:")
        total = sum(self.patterns['task_complexity'].values())
        for level, count in self.patterns['task_complexity'].items():
            pct = count / total * 100 if total > 0 else 0
            print(f"   {level:20s}: {count:4d} ({pct:5.1f}%)")

        print("\n👨‍⚖️ ARBITER CONSENSUS:")
        total = (self.patterns['arbiter_consensus']['validated'] +
                self.patterns['arbiter_consensus']['rejected'])
        if total > 0:
            validated_pct = self.patterns['arbiter_consensus']['validated'] / total * 100
            print(f"   Validated: {self.patterns['arbiter_consensus']['validated']:4d} ({validated_pct:5.1f}%)")
            print(f"   Rejected:  {self.patterns['arbiter_consensus']['rejected']:4d} ({100-validated_pct:5.1f}%)")

        print("\n✅ REVIEW OUTCOMES:")
        for outcome, count in self.patterns['review_outcomes'].most_common():
            print(f"   {outcome:20s}: {count:4d}")

        print("\n💡 RECOMMENDATIONS:")
        recs = self.get_recommendations()

        if recs['top_models']:
            print("\n   Top Models for Code Review:")
            for model in recs['top_models'][:3]:
                print(f"      {model['model']:30s}: {model['success_rate']} success")

        if recs['optimization_tips']:
            print("\n   Optimization Tips:")
            for tip in recs['optimization_tips']:
                print(f"      • {tip}")

        if recs['risk_areas']:
            print("\n   Risk Areas:")
            for risk in recs['risk_areas']:
                print(f"      ⚠️ {risk['area']}: {risk['count']} instances")

        print("\n" + "="*80)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Extract code review patterns from workflow data')
    parser.add_argument('--window', type=int, default=90, help='Analysis window in days (default: 90)')
    parser.add_argument('--output', type=str, default='learning/code_review_pattern_extractor.pkl',
                       help='Output path for trained model')
    parser.add_argument('--load', type=str, help='Load existing model instead of training')
    parser.add_argument('--predict', action='store_true', help='Run predictions on sample data')

    args = parser.parse_args()

    # Initialize extractor
    extractor = CodeReviewPatternExtractor()

    if args.load:
        # Load existing model
        extractor.load_model(args.load)
        extractor.print_report()
        return

    # Connect to database
    if not extractor.connect():
        print("❌ Failed to connect to database")
        return

    try:
        # Extract data
        print(f"📥 Extracting review tasks from last {args.window} days...")
        tasks = extractor.extract_review_tasks(window_days=args.window)
        decisions = extractor.extract_arbiter_decisions(window_days=args.window)

        print(f"   Found {len(tasks)} review tasks")
        print(f"   Found {len(decisions)} arbiter decisions")

        if len(tasks) == 0:
            print("⚠️ No review tasks found - cannot train model")
            return

        # Analyze patterns
        extractor.analyze_patterns(tasks, decisions)

        # Build ML features
        print("\n🔨 Building ML features...")
        X, y = extractor.build_ml_features(tasks)

        print(f"   Feature matrix: {X.shape}")
        print(f"   Target distribution: {np.bincount(y)}")

        # Train predictor
        extractor.train_issue_predictor(X, y)

        # Print report
        extractor.print_report()

        # Save model
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        extractor.save_model(str(output_path))

        # Demonstrate prediction
        if args.predict and len(tasks) > 0:
            print("\n🔮 SAMPLE PREDICTIONS:")
            sample_task = tasks[0]
            task_features = {
                'duration_ms': sample_task['duration_ms'],
                'input_tokens': sample_task['input_tokens'],
                'output_tokens': sample_task['output_tokens'],
                'confidence': sample_task['confidence'],
                'files_mentioned': 5,
                'categories': 2,
                'severities': 1,
                'outcome': sample_task['outcome'],
                'cost_usd': sample_task['cost_usd']
            }

            prob, message = extractor.predict_issue_likelihood(task_features)
            print(f"   Probability of finding issues: {prob:.1%}")
            print(f"   Assessment: {message}")

    finally:
        extractor.close()


if __name__ == '__main__':
    main()
