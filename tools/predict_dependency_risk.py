#!/usr/bin/env python3
"""
Dependency Risk Prediction Script

Loads trained dependency risk analyzer and predicts risk for given dependencies.

Usage:
  python3 predict_dependency_risk.py --name lodash --ecosystem npm
  python3 predict_dependency_risk.py --json dependency.json
  python3 predict_dependency_risk.py --scan package.json
"""

import json
import sys
import argparse
from pathlib import Path
import pickle


def load_model():
    """Load trained dependency risk analyzer"""
    model_path = Path.home() / "Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning" / "dependency_risk_analyzer.pkl"

    if not model_path.exists():
        print(f"❌ Model not found at {model_path}", file=sys.stderr)
        print("Run dependency_risk_analyzer_trainer.py first to train the model", file=sys.stderr)
        sys.exit(1)

    with open(model_path, 'rb') as f:
        data = pickle.load(f)

    return data


def predict_risk(model_data, dependency_info):
    """Predict risk for a dependency"""
    model = model_data['model']
    label_encoder = model_data['label_encoder']
    feature_names = model_data['feature_names']

    # Extract features (using same logic as trainer)
    from dependency_risk_analyzer_trainer import DependencyRiskAnalyzer
    analyzer = DependencyRiskAnalyzer()
    features = analyzer.extract_features(dependency_info)

    # Predict
    X = [[features[f] for f in feature_names]]
    prediction_idx = model.predict(X)[0]
    risk_level = label_encoder.inverse_transform([prediction_idx])[0]

    # Get probabilities
    if hasattr(model, 'predict_proba'):
        probs = model.predict_proba(X)[0]
        risk_probabilities = {
            label: float(prob)
            for label, prob in zip(label_encoder.classes_, probs)
        }
    else:
        risk_probabilities = {}

    return {
        'dependency_name': dependency_info.get('name', 'unknown'),
        'risk_level': risk_level,
        'risk_probabilities': risk_probabilities,
        'features_used': features
    }


def scan_package_json(package_json_path):
    """Scan package.json and analyze all dependencies"""
    with open(package_json_path) as f:
        package_data = json.load(f)

    dependencies = {}

    # Collect all dependencies
    for dep_type in ['dependencies', 'devDependencies', 'optionalDependencies']:
        if dep_type in package_data:
            for name, version in package_data[dep_type].items():
                dependencies[name] = {
                    'name': name,
                    'version': version,
                    'is_dev_dependency': dep_type == 'devDependencies',
                    'is_optional': dep_type == 'optionalDependencies',
                    'ecosystem': 'npm',
                    # Set defaults (in production, fetch from npm registry)
                    'version_age_days': 90,  # Default assumption
                    'commits_last_year': 50,
                    'open_issues': 10,
                    'open_prs': 5,
                    'closed_issues_last_month': 10,
                    'known_vulnerabilities': 0,
                    'has_security_policy': True,
                    'cve_count': 0,
                    'downloads_per_month': 10000,
                    'github_stars': 1000,
                    'num_dependents': 100,
                    'major_versions_behind': 0,
                    'minor_versions_behind': 0,
                    'breaking_changes_in_latest': 0,
                    'license': 'MIT',
                    'transitive_depth': 2,
                    'total_transitive_deps': 20,
                    'is_core_dependency': False,
                    'num_reverse_deps': 50,
                }

    return dependencies


def main():
    parser = argparse.ArgumentParser(description='Predict dependency risk levels')
    parser.add_argument('--name', help='Dependency name')
    parser.add_argument('--ecosystem', default='npm', help='Ecosystem (npm, pypi, maven)')
    parser.add_argument('--json', help='JSON file with dependency info')
    parser.add_argument('--scan', help='Scan package.json file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Load model
    print("Loading model...")
    model_data = load_model()
    print(f"✅ Model loaded (trained on {model_data['training_stats']['n_train']} samples)")

    # Process based on input type
    if args.scan:
        # Scan package.json
        print(f"\n📦 Scanning {args.scan}...")
        dependencies = scan_package_json(args.scan)

        results = []
        for name, dep_info in dependencies.items():
            result = predict_risk(model_data, dep_info)
            results.append(result)

        # Sort by risk level
        risk_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        results.sort(key=lambda x: risk_order.get(x['risk_level'], 4))

        # Print summary
        print(f"\n{'='*70}")
        print(f"{'DEPENDENCY RISK ANALYSIS':<70}")
        print(f"{'='*70}")
        print(f"{'Package':<30} {'Risk Level':<12} {'Confidence':<15}")
        print(f"{'-'*70}")

        for result in results:
            name = result['dependency_name'][:28]
            risk = result['risk_level']
            conf = result['risk_probabilities'].get(risk, 0.0) if result['risk_probabilities'] else 0.0

            # Color coding
            risk_emoji = {
                'CRITICAL': '🔴',
                'HIGH': '🟠',
                'MEDIUM': '🟡',
                'LOW': '🟢'
            }.get(risk, '⚪')

            print(f"{name:<30} {risk_emoji} {risk:<10} {conf:>6.1%}")

        # Risk summary
        risk_counts = {}
        for result in results:
            risk = result['risk_level']
            risk_counts[risk] = risk_counts.get(risk, 0) + 1

        print(f"\n{'='*70}")
        print("SUMMARY:")
        for risk in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            count = risk_counts.get(risk, 0)
            if count > 0:
                print(f"  {risk:10s}: {count:3d} packages")

    elif args.json:
        # Load from JSON
        with open(args.json) as f:
            dependency_info = json.load(f)

        result = predict_risk(model_data, dependency_info)

        print(f"\n{'='*60}")
        print(f"Dependency: {result['dependency_name']}")
        print(f"Risk Level: {result['risk_level']}")

        if result['risk_probabilities']:
            print("\nRisk Probabilities:")
            for level, prob in sorted(result['risk_probabilities'].items(),
                                     key=lambda x: x[1], reverse=True):
                bar = '█' * int(prob * 40)
                print(f"  {level:10s}: {prob:6.1%} {bar}")

        if args.verbose:
            print("\nFeatures Used:")
            for feat, val in sorted(result['features_used'].items()):
                print(f"  {feat:30s}: {val}")

    elif args.name:
        # Predict for single dependency (with defaults)
        dependency_info = {
            'name': args.name,
            'ecosystem': args.ecosystem,
            # Defaults (in production, fetch from registry)
            'version_age_days': 90,
            'commits_last_year': 50,
            'open_issues': 10,
            'open_prs': 5,
            'closed_issues_last_month': 10,
            'known_vulnerabilities': 0,
            'has_security_policy': True,
            'cve_count': 0,
            'downloads_per_month': 10000,
            'github_stars': 1000,
            'num_dependents': 100,
            'major_versions_behind': 0,
            'minor_versions_behind': 0,
            'breaking_changes_in_latest': 0,
            'license': 'MIT',
            'transitive_depth': 2,
            'total_transitive_deps': 20,
            'is_dev_dependency': False,
            'is_optional': False,
            'is_core_dependency': False,
            'num_reverse_deps': 50,
        }

        result = predict_risk(model_data, dependency_info)

        print(f"\n{'='*60}")
        print(f"Dependency: {result['dependency_name']}")
        print(f"Ecosystem:  {args.ecosystem}")
        print(f"Risk Level: {result['risk_level']}")

        if result['risk_probabilities']:
            print("\nRisk Probabilities:")
            for level, prob in sorted(result['risk_probabilities'].items(),
                                     key=lambda x: x[1], reverse=True):
                bar = '█' * int(prob * 40)
                print(f"  {level:10s}: {prob:6.1%} {bar}")

        print("\n⚠ Note: Using default values. For accurate analysis,")
        print("   provide full dependency info via --json or --scan")

    else:
        parser.print_help()
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
