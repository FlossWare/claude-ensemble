#!/usr/bin/env python3
"""
CLI tool to analyze technical debt using the trained quantifier
"""

import sys
import json
from pathlib import Path
import argparse
from tech_debt_quantifier import TechDebtQuantifier


def main():
    parser = argparse.ArgumentParser(
        description='Analyze technical debt in code files or directories'
    )
    parser.add_argument(
        'path',
        help='File or directory path to analyze'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=60.0,
        help='Debt score threshold for flagging files (default: 60)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=10,
        help='Show top N files by priority (default: 10)'
    )

    args = parser.parse_args()

    # Load trained model
    model_path = Path.home() / '.claude' / 'learning' / 'tech_debt_quantifier.pkl'
    if not model_path.exists():
        print("❌ Model not found. Run tech_debt_quantifier.py first to train the model.", file=sys.stderr)
        sys.exit(1)

    quantifier = TechDebtQuantifier()
    quantifier.load(model_path)

    path = Path(args.path)

    if path.is_file():
        # Analyze single file
        result = quantifier.predict(path)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"TECH DEBT ANALYSIS: {path.name}")
            print(f"{'='*60}")
            print(f"\n📊 Debt Score:      {result['debt_score']:.1f}/100")
            print(f"🎯 Priority Score:  {result['priority_score']:.1f}/100")
            print(f"📈 Debt Level:      {result['debt_level']}")
            print(f"⏱️  Fix Estimate:    {result['estimated_fix_hours']:.1f} hours")
            print(f"\n💡 Recommendation: {result['recommendation']}")

            print(f"\n📋 Metrics:")
            print(f"  Maintainability Index: {result['maintainability_index']:.1f}")
            print(f"  Code Smell Score:      {result['smell_score']:.1f}")
            print(f"  Debt Indicators:       {result['debt_indicators']}")

            if result['debt_score'] >= args.threshold:
                print(f"\n⚠️  WARNING: Debt score exceeds threshold ({args.threshold})")

    elif path.is_dir():
        # Analyze directory
        print(f"\n🔍 Analyzing directory: {path}")
        print("This may take a moment...\n")

        summary = quantifier.analyze_directory(path)

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"{'='*60}")
            print("TECH DEBT SUMMARY")
            print(f"{'='*60}")
            print(f"\n📊 Total Files:          {summary['total_files']}")
            print(f"💳 Average Debt Score:   {summary['avg_debt_score']:.1f}/100")
            print(f"⏱️  Total Fix Estimate:   {summary['total_estimated_fix_hours']:.1f} hours")
            print(f"🚨 Critical Files:       {summary['critical_files']}")

            if summary['top_priority_files']:
                print(f"\n🔝 TOP {min(args.top, len(summary['top_priority_files']))} PRIORITY FILES:")
                print(f"{'─'*60}")

                for i, result in enumerate(summary['top_priority_files'][:args.top], 1):
                    file_name = Path(result['file_path']).name
                    print(f"\n{i}. {file_name}")
                    print(f"   Debt:     {result['debt_score']:.1f}/100 ({result['debt_level']})")
                    print(f"   Priority: {result['priority_score']:.1f}/100")
                    print(f"   Fix Time: {result['estimated_fix_hours']:.1f}h")
                    print(f"   → {result['recommendation']}")

            # Show files above threshold
            high_debt_files = [r for r in summary['top_priority_files'] if r['debt_score'] >= args.threshold]
            if high_debt_files:
                print(f"\n⚠️  {len(high_debt_files)} files exceed debt threshold ({args.threshold})")

    else:
        print(f"❌ Path not found: {path}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
