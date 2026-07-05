#!/usr/bin/env python3
"""
Check Breaking Changes - CLI Tool

Uses the trained breaking change detector to analyze git diffs
and identify potentially breaking changes.

Usage:
    # Check current working directory changes
    python3 check_breaking_changes.py

    # Check specific commit
    python3 check_breaking_changes.py --commit abc123

    # Check PR/branch
    python3 check_breaking_changes.py --branch feature-branch

    # Check specific diff file
    python3 check_breaking_changes.py --diff-file changes.diff

    # JSON output
    python3 check_breaking_changes.py --json
"""

import sys
import json
import argparse
import subprocess
from pathlib import Path
from breaking_change_detector import BreakingChangeDetector


def get_git_diff(commit=None, branch=None):
    """Get git diff from various sources"""
    try:
        if commit:
            # Diff for specific commit
            cmd = ['git', 'show', commit, '--unified=3']
        elif branch:
            # Diff between current branch and target branch
            cmd = ['git', 'diff', f'{branch}...HEAD', '--unified=3']
        else:
            # Diff of working directory
            cmd = ['git', 'diff', 'HEAD', '--unified=3']

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout

    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e}", file=sys.stderr)
        return None


def get_commit_message(commit='HEAD'):
    """Get commit message"""
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--pretty=%s', commit],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def analyze_changes(detector, diff, description=None, output_json=False):
    """Analyze changes and report findings"""

    if not diff or not diff.strip():
        if output_json:
            print(json.dumps({'error': 'No changes detected'}))
        else:
            print("No changes detected")
        return 0

    # Predict
    result = detector.predict(diff=diff, description=description)

    if output_json:
        # JSON output for CI/CD integration
        output = {
            'is_breaking': result['is_breaking'],
            'confidence': result['confidence'],
            'risk_level': result['risk_level'],
            'recommendation': get_recommendation(result),
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-friendly output
        print("=" * 60)
        print("BREAKING CHANGE ANALYSIS")
        print("=" * 60)

        if description:
            print(f"\nChange: {description}")

        print(f"\nBreaking Change: {'YES' if result['is_breaking'] else 'NO'}")
        print(f"Confidence: {result['confidence']:.1%}")
        print(f"Risk Level: {result['risk_level']}")

        print(f"\n{get_recommendation(result)}")

        # Show top contributing features
        features = result['features']
        important_features = {k: v for k, v in features.items() if v > 0}

        if important_features:
            print("\nDetected Patterns:")
            for feat, val in sorted(important_features.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  - {feat.replace('_', ' ').title()}: {val}")

        print("\n" + "=" * 60)

    # Exit code: 1 if high/critical risk, 0 otherwise
    return 1 if result['risk_level'] in ['HIGH', 'CRITICAL'] else 0


def get_recommendation(result):
    """Get recommendation based on analysis"""
    risk = result['risk_level']
    confidence = result['confidence']

    if risk == 'CRITICAL' and confidence >= 0.9:
        return (
            "⚠️  CRITICAL: This change is highly likely to break compatibility.\n"
            "   Recommendation: BLOCK merge until:\n"
            "   1. Version bump (major version)\n"
            "   2. Update CHANGELOG with breaking changes\n"
            "   3. Manual review by senior developer\n"
            "   4. Update migration guide"
        )
    elif risk == 'HIGH':
        return (
            "⚠️  HIGH RISK: This change may break compatibility.\n"
            "   Recommendation:\n"
            "   1. Add deprecation warnings before removing\n"
            "   2. Update documentation\n"
            "   3. Manual code review required"
        )
    elif risk == 'MEDIUM':
        return (
            "⚠️  MEDIUM RISK: Review recommended.\n"
            "   Recommendation:\n"
            "   1. Check if changes are backward compatible\n"
            "   2. Update relevant tests\n"
            "   3. Update API documentation if needed"
        )
    else:
        return (
            "✅ LOW RISK: Change appears safe.\n"
            "   Recommendation: Standard code review process"
        )


def main():
    """Main CLI entry point"""

    parser = argparse.ArgumentParser(
        description='Detect breaking changes in code modifications'
    )
    parser.add_argument(
        '--commit',
        help='Analyze specific commit (e.g., abc123 or HEAD~1)'
    )
    parser.add_argument(
        '--branch',
        help='Compare current branch with target branch (e.g., main)'
    )
    parser.add_argument(
        '--diff-file',
        help='Path to diff file to analyze'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output JSON for CI/CD integration'
    )
    parser.add_argument(
        '--model',
        default=str(Path.home() / '.claude' / 'learning' / 'breaking_change_detector.pkl'),
        help='Path to trained model (default: ~/.claude/learning/breaking_change_detector.pkl)'
    )

    args = parser.parse_args()

    # Load model
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Error: Model not found at {model_path}", file=sys.stderr)
        print("Run: python3 tools/breaking_change_detector.py", file=sys.stderr)
        return 1

    detector = BreakingChangeDetector()
    detector.load(model_path)

    # Get diff
    if args.diff_file:
        with open(args.diff_file) as f:
            diff = f.read()
        description = f"Changes in {args.diff_file}"

    else:
        diff = get_git_diff(commit=args.commit, branch=args.branch)
        if diff is None:
            return 1

        # Get commit message for context
        commit_ref = args.commit or 'HEAD'
        description = get_commit_message(commit_ref)

    # Analyze
    exit_code = analyze_changes(detector, diff, description, args.json)

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
