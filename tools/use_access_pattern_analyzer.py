#!/usr/bin/env python3
"""
Use Access Pattern Analyzer

Load and use the trained access pattern analyzer to:
1. Predict best models for tasks
2. Estimate resource usage
3. Predict failure risks
4. Get model recommendations

Usage:
    python3 use_access_pattern_analyzer.py "Fix memory leak in cache"
    python3 use_access_pattern_analyzer.py --interactive
    python3 use_access_pattern_analyzer.py --stats
"""

import sys
import pickle
import json
from pathlib import Path
from typing import Optional

# Import the AccessPatternAnalyzer class so pickle can deserialize it
sys.path.insert(0, str(Path(__file__).parent))
from access_pattern_analyzer_trainer import AccessPatternAnalyzer


def load_analyzer(model_path: Optional[str] = None):
    """Load trained analyzer"""
    if model_path is None:
        model_path = str(Path.home() / '.claude' / 'learning' / 'access_pattern_analyzer.pkl')

    with open(model_path, 'rb') as f:
        return pickle.load(f)


def predict_for_task(analyzer, task_description: str, top_k: int = 5):
    """Get predictions for a task"""
    print(f"\nTask: {task_description}")
    print("=" * 80)

    # Get best models
    predictions = analyzer.predict_best_model(task_description, top_k=top_k)

    if not predictions:
        print("No predictions available (insufficient training data)")
        return

    print(f"\n{'Model':<45} {'Score':>8} {'Duration':>10} {'Cost':>8} {'Risk':>8}")
    print("-" * 80)

    for model, score in predictions:
        # Get resource predictions
        resources = analyzer.predict_resource_usage(model)
        duration = resources['expected_duration_ms']
        cost = resources['expected_cost_usd']

        # Get failure risk
        risk = analyzer.predict_failure_risk(model, task_description)

        print(f"{model:<45} {score:>8.3f} {duration:>9.0f}ms ${cost:>7.4f} {risk:>7.1%}")

    # Show task features
    features = analyzer.extract_task_features(task_description)
    print(f"\nTask Features:")
    print(f"  Type: ", end="")
    if features.get('has_fix'):
        print("Fix/Debug", end=" ")
    if features.get('has_review'):
        print("Review", end=" ")
    if features.get('has_test'):
        print("Test", end=" ")
    if features.get('has_code'):
        print("Code", end=" ")
    if features.get('has_question'):
        print("Question", end=" ")
    print()
    print(f"  Length: {features['length']} chars, {features['word_count']} words")


def show_stats(analyzer):
    """Show analyzer statistics"""
    stats = analyzer.get_stats()

    print("\n" + "=" * 80)
    print("ACCESS PATTERN ANALYZER STATISTICS")
    print("=" * 80)

    print(f"\nTraining Information:")
    print(f"  Trained at: {stats['trained_at']}")
    print(f"  Models tracked: {stats['models_tracked']}")
    print(f"  Unique tasks: {stats['unique_tasks']}")
    print(f"  Task clusters: {stats['task_clusters']}")
    print(f"  Cache entries: {stats['cache_entries']}")
    print(f"  Failure patterns: {stats['failure_patterns']}")

    # Model performance breakdown
    print(f"\nModel Performance Summary:")
    model_stats = []
    for model in list(analyzer.model_task_affinity.keys())[:10]:
        tasks = analyzer.model_task_affinity[model]
        total_executions = sum(len(results) for results in tasks.values())

        # Calculate success rate
        all_results = []
        for results in tasks.values():
            all_results.extend(results)

        if all_results:
            success_rate = sum(r['success'] for r in all_results) / len(all_results)
            avg_confidence = sum(r.get('confidence', 0.5) for r in all_results) / len(all_results)
            avg_duration = sum(r.get('duration_ms', 0) for r in all_results) / len(all_results)

            model_stats.append({
                'model': model,
                'executions': total_executions,
                'success_rate': success_rate,
                'avg_confidence': avg_confidence,
                'avg_duration': avg_duration
            })

    # Sort by executions
    model_stats.sort(key=lambda x: x['executions'], reverse=True)

    print(f"\n{'Model':<45} {'Execs':>6} {'Success':>8} {'Conf':>6} {'Dur(ms)':>9}")
    print("-" * 80)
    for ms in model_stats[:15]:
        print(f"{ms['model']:<45} {ms['executions']:>6} "
              f"{ms['success_rate']:>7.1%} {ms['avg_confidence']:>6.2f} "
              f"{ms['avg_duration']:>9.0f}")


def interactive_mode(analyzer):
    """Interactive query mode"""
    print("\n" + "=" * 80)
    print("ACCESS PATTERN ANALYZER - Interactive Mode")
    print("=" * 80)
    print("\nEnter task descriptions to get model recommendations.")
    print("Commands: 'stats' for statistics, 'quit' to exit")
    print("=" * 80)

    while True:
        try:
            task = input("\nTask> ").strip()

            if not task:
                continue

            if task.lower() in ['quit', 'exit', 'q']:
                break

            if task.lower() == 'stats':
                show_stats(analyzer)
                continue

            predict_for_task(analyzer, task, top_k=5)

        except EOFError:
            break
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Use Access Pattern Analyzer')
    parser.add_argument('task', nargs='?', help='Task description to predict')
    parser.add_argument('--model', type=str,
                       default=str(Path.home() / '.claude' / 'learning' / 'access_pattern_analyzer.pkl'),
                       help='Path to trained model pickle file')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Interactive mode')
    parser.add_argument('--stats', '-s', action='store_true',
                       help='Show statistics only')
    parser.add_argument('--top-k', type=int, default=5,
                       help='Number of top models to show (default: 5)')

    args = parser.parse_args()

    # Load analyzer
    try:
        print(f"Loading analyzer from {args.model}...")
        analyzer = load_analyzer(args.model)
        print("✓ Analyzer loaded")
    except FileNotFoundError:
        print(f"Error: Model file not found: {args.model}")
        print("Run access_pattern_analyzer_trainer.py first to train the model.")
        sys.exit(1)

    # Show stats if requested
    if args.stats:
        show_stats(analyzer)
        return

    # Interactive mode
    if args.interactive:
        interactive_mode(analyzer)
        return

    # Single task prediction
    if args.task:
        predict_for_task(analyzer, args.task, top_k=args.top_k)
        return

    # No arguments - show help
    parser.print_help()
    print("\nExamples:")
    print('  python3 use_access_pattern_analyzer.py "Fix memory leak"')
    print('  python3 use_access_pattern_analyzer.py --interactive')
    print('  python3 use_access_pattern_analyzer.py --stats')


if __name__ == '__main__':
    main()
