#!/usr/bin/env python3
"""GA Unified Runner - Run all GA tools and compare results.

Executes each GA optimizer, collects fitness scores, convergence rates,
and generates a comparison report. Use for benchmarking GA performance
across all optimization domains.

Usage:
    python3 ga_run_all.py                    # run all GAs (20 generations each)
    python3 ga_run_all.py --generations 50   # longer runs
    python3 ga_run_all.py --only routing,consensus  # subset
"""

import argparse
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

TOOLS_DIR = Path(__file__).parent

GA_REGISTRY = {
    'workflow': {
        'module': 'ga_workflow_optimizer',
        'class': 'WorkflowGA',
        'description': 'Workflow configuration (workers, models, consensus)',
        'genes': 75,
    },
    'routing': {
        'module': 'ga_routing_weights',
        'class': 'RoutingGA',
        'description': 'Thompson Sampling priors for model routing',
        'genes': 160,
    },
    'consensus': {
        'module': 'ga_consensus_optimizer',
        'class': 'ConsensusGA',
        'description': 'Multi-AI voting thresholds and strategies',
        'genes': 66,
    },
    'scraper': {
        'module': 'ga_scraper_scheduler',
        'class': 'ScraperSchedulerGA',
        'description': 'Scraper scheduling across fleet workers',
        'genes': 210,
    },
    'prompt': {
        'module': 'ga_prompt_evolution_fixed',
        'class': 'PromptEvolutionGA',
        'description': 'Code review prompt check selection',
        'genes': 12,
    },
    'team': {
        'module': 'ga_team_selection_fixed',
        'class': None,  # Uses main() directly
        'description': 'Team composition from 445+ free models',
        'genes': 25,
    },
    'model': {
        'module': 'genetic_model_optimizer',
        'class': None,
        'description': 'Model-task type mapping optimization',
        'genes': 42,
    },
    'pipeline': {
        'module': 'ga_pipeline_optimizer',
        'class': None,
        'description': 'Meta-optimizer with MAP-Elites archive',
        'genes': 65,
    },
    'retry': {
        'module': 'ga_retry_policy',
        'class': 'RetryGA',
        'description': 'API retry policies per provider',
        'genes': 80,
    },
    'adversarial': {
        'module': 'ga_adversarial_verification_fixed',
        'class': 'AdversarialGA',
        'description': 'Adversarial code mutation evasion',
        'genes': 8,
    },
    'embedding': {
        'module': 'ga_embedding_optimizer',
        'class': 'EmbeddingGA',
        'description': 'Embedding/chunking params for retrieval',
        'genes': 54,
    },
    'meta': {
        'module': 'ga_meta_optimizer',
        'class': 'MetaGA',
        'description': 'GA hyperparameter self-optimization',
        'genes': 8,
    },
    'intelligence': {
        'module': 'ga_continuous_intelligence',
        'class': None,
        'description': 'Continuous intelligence evolution (run separately)',
        'genes': 15,
    },
}


def load_module(module_name):
    """Dynamically load a GA module."""
    module_path = TOOLS_DIR / f"{module_name}.py"
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_ga(name, info, generations, seed):
    """Run a single GA and return results."""
    print(f"\n{'='*70}")
    print(f"  Running: {name} ({info['description']})")
    print(f"  Genes: {info['genes']}, Generations: {generations}")
    print(f"{'='*70}")

    start = time.time()

    try:
        module = load_module(info['module'])
        if module is None:
            return {'name': name, 'status': 'not_found', 'error': f"Module {info['module']} not found"}

        if info['class'] and hasattr(module, info['class']):
            ga_class = getattr(module, info['class'])

            if name == 'prompt':
                ga = ga_class(population_size=20, seed=seed)
                best, stats = ga.run(generations=min(generations, 10))
                fitness = best.f1_score if best else 0
            elif name == 'adversarial':
                ga = ga_class(population_size=20, seed=seed)
                best, stats = ga.run(generations=min(generations, 15))
                fitness = best.fitness if best else 0
            else:
                ga = ga_class(population_size=20, seed=seed)
                best = ga.run(generations=generations)
                fitness = best.fitness if best else 0
        elif hasattr(module, 'main'):
            # For modules that use main() directly, just import and note
            return {
                'name': name, 'status': 'skipped',
                'reason': 'Uses main() with different interface',
                'duration': 0,
            }
        else:
            return {'name': name, 'status': 'no_entry_point'}

        duration = time.time() - start

        result = {
            'name': name,
            'status': 'success',
            'fitness': float(fitness) if fitness else 0,
            'duration': round(duration, 2),
            'generations': generations,
            'genes': info['genes'],
        }

        if hasattr(best, 'fitness_details') and best.fitness_details:
            result['details'] = {k: float(v) for k, v in best.fitness_details.items()}

        if hasattr(ga, 'convergence_history') and ga.convergence_history:
            result['convergence'] = {
                'initial': ga.convergence_history[0]['best'] if ga.convergence_history else 0,
                'final': ga.convergence_history[-1]['best'] if ga.convergence_history else 0,
                'improvement': round(
                    (ga.convergence_history[-1]['best'] - ga.convergence_history[0]['best'])
                    / max(0.001, ga.convergence_history[0]['best']) * 100, 1
                ) if ga.convergence_history else 0,
            }

        return result

    except Exception as e:
        duration = time.time() - start
        return {
            'name': name, 'status': 'error',
            'error': str(e), 'traceback': traceback.format_exc()[-500:],
            'duration': round(duration, 2),
        }


def print_report(results):
    """Print comparison report."""
    print("\n" + "=" * 70)
    print("  GA UNIFIED RESULTS REPORT")
    print("=" * 70)

    successes = [r for r in results if r['status'] == 'success']
    errors = [r for r in results if r['status'] == 'error']
    skipped = [r for r in results if r['status'] in ('skipped', 'not_found')]

    if successes:
        print(f"\n  {'GA Tool':<20} {'Fitness':>10} {'Duration':>10} {'Genes':>8} {'Improvement':>12}")
        print(f"  {'-'*18:<20} {'-'*8:>10} {'-'*8:>10} {'-'*6:>8} {'-'*10:>12}")

        for r in sorted(successes, key=lambda x: x.get('fitness', 0), reverse=True):
            imp = f"{r.get('convergence', {}).get('improvement', 0):+.1f}%" if 'convergence' in r else 'N/A'
            print(f"  {r['name']:<20} {r['fitness']:>10.5f} {r['duration']:>9.1f}s {r['genes']:>8} {imp:>12}")

        if len(successes) > 1:
            avg_fitness = sum(r['fitness'] for r in successes) / len(successes)
            total_time = sum(r['duration'] for r in successes)
            print(f"\n  Average fitness: {avg_fitness:.5f}")
            print(f"  Total runtime: {total_time:.1f}s")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for r in errors:
            print(f"    {r['name']}: {r.get('error', 'unknown')[:80]}")

    if skipped:
        print(f"\n  SKIPPED ({len(skipped)}):")
        for r in skipped:
            print(f"    {r['name']}: {r.get('reason', r.get('status', 'unknown'))}")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='GA Unified Runner')
    parser.add_argument('--generations', type=int, default=20)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--only', type=str, default=None, help='Comma-separated list of GA names')
    args = parser.parse_args()

    if args.only:
        names = [n.strip() for n in args.only.split(',')]
        registry = {k: v for k, v in GA_REGISTRY.items() if k in names}
    else:
        registry = GA_REGISTRY

    print(f"Running {len(registry)} GA tools, {args.generations} generations each, seed={args.seed}")

    results = []
    for name, info in registry.items():
        result = run_ga(name, info, args.generations, args.seed)
        results.append(result)

    print_report(results)

    output_path = TOOLS_DIR / 'ga_unified_results.json'
    with open(output_path, 'w') as f:
        json.dump({
            'results': results,
            'config': {'generations': args.generations, 'seed': args.seed},
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == '__main__':
    main()
