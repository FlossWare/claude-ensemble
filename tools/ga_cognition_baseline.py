#!/usr/bin/env python3
"""Cognitive Evolution Baseline Analysis

Generate and evaluate random programs to establish statistical baselines
for every task and intelligence metric. Without this, we can't distinguish
evolved intelligence from lucky random programs.

Measures:
  - Mean, std, max, min for each task score across random programs
  - Distribution of program sizes and depths
  - Baseline intelligence metrics
  - What fraction of random programs beat the evolved best
  - Statistical significance thresholds (mean + 2σ, mean + 3σ)

Usage:
    python3 ga_cognition_baseline.py                    # full baseline (1000 programs)
    python3 ga_cognition_baseline.py --samples 500      # faster
    python3 ga_cognition_baseline.py --compare latest   # compare evolved vs baseline
"""

import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

import numpy as np

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

from ga_cognition_engine import (
    random_tree, execute, ExecutionContext, Node, Op, ARITY,
    TRAINING_TASKS, GENERALIZATION_TASKS, ALL_TASKS,
    IntelligenceReport, INTELLIGENCE_LEVELS,
    PatternClassifyTask,
)


def count_ops(node: Node, target_ops: set) -> int:
    count = 1 if node.op in target_ops else 0
    return count + sum(count_ops(c, target_ops) for c in node.children)


def measure_intelligence_for(program: Node, task_scores: dict, gen_scores: dict) -> dict:
    """Compute intelligence metrics for a single program."""
    metrics = {}

    # Generalization
    if gen_scores:
        metrics['generalization'] = float(np.mean(list(gen_scores.values())))
    else:
        metrics['generalization'] = 0.0

    # Abstraction (analogy score)
    metrics['abstraction'] = gen_scores.get('analogy', 0.0)

    # Memory use
    memory_ops = count_ops(program, {Op.READ, Op.WRITE})
    total_ops = program.size()
    memory_ratio = memory_ops / max(total_ops, 1)
    copy_score = task_scores.get('copy_recall', 0.0)
    metrics['memory_use'] = min(1.0, memory_ratio * 5) * copy_score if memory_ops > 0 else 0.0

    # Lifetime learning
    task = PatternClassifyTask()
    rng = random.Random(777)
    trials = task.generate_trials(10, rng)
    score_with = 0
    score_without = 0
    for trial in trials:
        ctx_bare = ExecutionContext()
        for i, v in enumerate(trial['test_input'][:4]):
            ctx_bare.inputs[i] = v
        ctx_bare.inputs[5] = 0.0
        execute(program, ctx_bare)
        score_without += (1.0 if (ctx_bare.outputs[0] > 0) == (trial['test_label'] > 0) else 0.0)

        ctx_trained = ExecutionContext()
        for ex_input, ex_label in trial['examples']:
            ctx_trained.steps = 0
            ctx_trained.outputs = [0.0] * ctx_trained.NUM_OUTPUT_CHANNELS
            for i, v in enumerate(ex_input[:4]):
                ctx_trained.inputs[i] = v
            ctx_trained.inputs[4] = ex_label
            ctx_trained.inputs[5] = 1.0
            execute(program, ctx_trained)
        ctx_trained.steps = 0
        ctx_trained.outputs = [0.0] * ctx_trained.NUM_OUTPUT_CHANNELS
        for i, v in enumerate(trial['test_input'][:4]):
            ctx_trained.inputs[i] = v
        ctx_trained.inputs[4] = 0.0
        ctx_trained.inputs[5] = 0.0
        execute(program, ctx_trained)
        score_with += (1.0 if (ctx_trained.outputs[0] > 0) == (trial['test_label'] > 0) else 0.0)

    score_with /= len(trials)
    score_without /= len(trials)
    if score_with > score_without and score_with > 0.6:
        metrics['lifetime_learning'] = min(1.0, (score_with - score_without) * 3)
    else:
        metrics['lifetime_learning'] = 0.0

    # Behavioral complexity
    has_cond = count_ops(program, {Op.IF}) > 0
    has_mem = memory_ops > 0
    has_io = count_ops(program, {Op.SENSE, Op.ACT}) > 0
    has_arith = count_ops(program, {Op.ADD, Op.SUB, Op.MUL, Op.DIV}) > 0
    has_cmp = count_ops(program, {Op.GT, Op.LT, Op.EQ}) > 0
    complexity_count = sum([has_cond, has_mem, has_io, has_arith, has_cmp])
    size_factor = min(1.0, program.size() / 20)
    metrics['behavioral_complexity'] = (complexity_count / 5) * size_factor

    # Multi-task
    all_scores = list(task_scores.values()) + list(gen_scores.values())
    above_competent = [s for s in all_scores if s > 0.7]
    metrics['multi_task'] = len(above_competent) / len(all_scores) if all_scores else 0

    # IQ
    metrics['intelligence_score'] = (
        metrics['generalization'] * 0.30 +
        metrics['abstraction'] * 0.25 +
        metrics['memory_use'] * 0.10 +
        metrics['lifetime_learning'] * 0.15 +
        metrics['behavioral_complexity'] * 0.05 +
        metrics['multi_task'] * 0.15
    )

    return metrics


def run_baseline(n_samples: int = 1000, max_depths: list = None, seed: int = 42):
    if max_depths is None:
        max_depths = [3, 4, 5, 6, 7, 8]

    rng = random.Random(seed)
    print("=" * 70)
    print("  COGNITIVE BASELINE ANALYSIS")
    print("=" * 70)
    print(f"  Samples: {n_samples}")
    print(f"  Tree depths: {max_depths}")
    print(f"  Training tasks: {list(TRAINING_TASKS.keys())}")
    print(f"  Held-out tasks: {list(GENERALIZATION_TASKS.keys())}")
    print("=" * 70)

    all_results = []
    start = time.time()

    for i in range(n_samples):
        depth = rng.choice(max_depths)
        program = random_tree(rng, max_depth=depth)

        task_scores = {}
        for name, task in TRAINING_TASKS.items():
            task_scores[name] = task.evaluate(program, n_trials=15, seed=42)

        gen_scores = {}
        for name, task in GENERALIZATION_TASKS.items():
            gen_scores[name] = task.evaluate(program, n_trials=15, seed=999)

        metrics = measure_intelligence_for(program, task_scores, gen_scores)

        # Fitness (same formula as engine)
        scores = list(task_scores.values())
        mean_score = sum(scores) / len(scores)
        min_score = min(scores)
        fitness = 0.6 * mean_score + 0.4 * min_score

        all_results.append({
            'fitness': fitness,
            'size': program.size(),
            'depth': program.depth(),
            'task_scores': task_scores,
            'gen_scores': gen_scores,
            'metrics': metrics,
        })

        if (i + 1) % 100 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            print(f"  {i+1}/{n_samples} ({rate:.1f}/s)")
            sys.stdout.flush()

    elapsed = time.time() - start
    print(f"\n  Completed in {elapsed:.1f}s ({n_samples/elapsed:.1f} programs/s)")

    # === ANALYSIS ===
    print("\n" + "=" * 70)
    print("  BASELINE STATISTICS")
    print("=" * 70)

    # Fitness
    fitnesses = [r['fitness'] for r in all_results]
    print(f"\n  Overall Fitness:")
    print(f"    Mean:   {np.mean(fitnesses):.6f}")
    print(f"    Std:    {np.std(fitnesses):.6f}")
    print(f"    Median: {np.median(fitnesses):.6f}")
    print(f"    Max:    {np.max(fitnesses):.6f}")
    print(f"    Min:    {np.min(fitnesses):.6f}")
    print(f"    2σ:     {np.mean(fitnesses) + 2*np.std(fitnesses):.6f}  (top ~2.5%)")
    print(f"    3σ:     {np.mean(fitnesses) + 3*np.std(fitnesses):.6f}  (top ~0.15%)")

    # Per-task
    print(f"\n  Per-Task Baselines:")
    print(f"    {'Task':<25s} {'Mean':>8s} {'Std':>8s} {'Max':>8s} {'2σ':>8s} {'3σ':>8s}")
    print(f"    {'-'*23:<25s} {'-'*6:>8s} {'-'*6:>8s} {'-'*6:>8s} {'-'*6:>8s} {'-'*6:>8s}")
    all_task_names = list(TRAINING_TASKS.keys()) + list(GENERALIZATION_TASKS.keys())
    task_baselines = {}
    for task_name in all_task_names:
        if task_name in TRAINING_TASKS:
            scores = [r['task_scores'][task_name] for r in all_results]
        else:
            scores = [r['gen_scores'][task_name] for r in all_results]
        m, s = np.mean(scores), np.std(scores)
        task_baselines[task_name] = {'mean': m, 'std': s, 'max': np.max(scores)}
        label = f"  * {task_name}" if task_name in GENERALIZATION_TASKS else f"    {task_name}"
        print(f"  {label:<25s} {m:8.4f} {s:8.4f} {np.max(scores):8.4f} {m+2*s:8.4f} {m+3*s:8.4f}")

    # Intelligence metrics
    print(f"\n  Intelligence Metric Baselines:")
    metric_names = ['intelligence_score', 'generalization', 'abstraction', 'memory_use',
                    'lifetime_learning', 'behavioral_complexity', 'multi_task']
    metric_baselines = {}
    print(f"    {'Metric':<25s} {'Mean':>8s} {'Std':>8s} {'Max':>8s} {'2σ':>8s} {'3σ':>8s}")
    print(f"    {'-'*23:<25s} {'-'*6:>8s} {'-'*6:>8s} {'-'*6:>8s} {'-'*6:>8s} {'-'*6:>8s}")
    for mn in metric_names:
        vals = [r['metrics'][mn] for r in all_results]
        m, s = np.mean(vals), np.std(vals)
        metric_baselines[mn] = {'mean': m, 'std': s, 'max': np.max(vals)}
        print(f"    {mn:<25s} {m:8.4f} {s:8.4f} {np.max(vals):8.4f} {m+2*s:8.4f} {m+3*s:8.4f}")

    # Program structure
    sizes = [r['size'] for r in all_results]
    depths = [r['depth'] for r in all_results]
    print(f"\n  Program Structure:")
    print(f"    Size:  mean={np.mean(sizes):.1f}, std={np.std(sizes):.1f}, range=[{np.min(sizes)}, {np.max(sizes)}]")
    print(f"    Depth: mean={np.mean(depths):.1f}, std={np.std(depths):.1f}, range=[{np.min(depths)}, {np.max(depths)}]")

    # How many random programs have lifetime learning > 0?
    learners = sum(1 for r in all_results if r['metrics']['lifetime_learning'] > 0)
    print(f"\n  Lifetime learning > 0: {learners}/{n_samples} ({100*learners/n_samples:.1f}%)")

    # How many have memory use > 0?
    mem_users = sum(1 for r in all_results if r['metrics']['memory_use'] > 0)
    print(f"  Memory use > 0:       {mem_users}/{n_samples} ({100*mem_users/n_samples:.1f}%)")

    # Save results
    output = {
        'n_samples': n_samples,
        'seed': seed,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'fitness': {
            'mean': float(np.mean(fitnesses)),
            'std': float(np.std(fitnesses)),
            'median': float(np.median(fitnesses)),
            'max': float(np.max(fitnesses)),
            'sigma2': float(np.mean(fitnesses) + 2 * np.std(fitnesses)),
            'sigma3': float(np.mean(fitnesses) + 3 * np.std(fitnesses)),
        },
        'task_baselines': {k: {kk: float(vv) for kk, vv in v.items()} for k, v in task_baselines.items()},
        'metric_baselines': {k: {kk: float(vv) for kk, vv in v.items()} for k, v in metric_baselines.items()},
        'lifetime_learners_pct': 100 * learners / n_samples,
        'memory_users_pct': 100 * mem_users / n_samples,
    }

    output_path = os.path.join(TOOLS_DIR, 'cognition_baseline.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n  Saved to: {output_path}")

    print("=" * 70)
    return output


def compare_with_evolved(baseline_path: str, checkpoint_path: str):
    """Compare evolved best with baseline statistics."""
    with open(baseline_path) as f:
        baseline = json.load(f)
    with open(checkpoint_path) as f:
        checkpoint = json.load(f)

    be = checkpoint['best_ever']
    bl = baseline

    print("=" * 70)
    print("  EVOLVED vs BASELINE COMPARISON")
    print("=" * 70)

    # Fitness
    fit = be['fitness']
    bl_mean = bl['fitness']['mean']
    bl_std = bl['fitness']['std']
    sigma = (fit - bl_mean) / bl_std if bl_std > 0 else 0
    print(f"\n  Fitness: {fit:.6f}  (baseline: {bl_mean:.6f} ± {bl_std:.6f})  → {sigma:.1f}σ above random")

    # Per-task comparison
    print(f"\n  Task Performance vs Baseline:")
    print(f"    {'Task':<25s} {'Evolved':>8s} {'Baseline':>8s} {'σ above':>8s} {'Verdict':>12s}")
    print(f"    {'-'*23:<25s} {'-'*6:>8s} {'-'*6:>8s} {'-'*6:>8s} {'-'*10:>12s}")

    all_scores = {}
    all_scores.update(be.get('task_scores', {}))
    all_scores.update(be.get('generalization_scores', {}))

    for task_name, evolved_score in all_scores.items():
        if task_name in bl['task_baselines']:
            tb = bl['task_baselines'][task_name]
            sig = (evolved_score - tb['mean']) / tb['std'] if tb['std'] > 0 else 0
            if sig >= 3:
                verdict = "*** STRONG"
            elif sig >= 2:
                verdict = "** GOOD"
            elif sig >= 1:
                verdict = "* ABOVE"
            elif sig >= 0:
                verdict = "~ RANDOM"
            else:
                verdict = "BELOW"
            prefix = "* " if task_name in GENERALIZATION_TASKS else "  "
            print(f"  {prefix}{task_name:<23s} {evolved_score:8.4f} {tb['mean']:8.4f} {sig:+7.1f}σ {verdict:>12s}")

    # Intelligence metrics
    m = checkpoint['metrics_history'][-1]
    print(f"\n  Intelligence Metrics vs Baseline:")
    print(f"    {'Metric':<25s} {'Evolved':>8s} {'Baseline':>8s} {'σ above':>8s}")
    print(f"    {'-'*23:<25s} {'-'*6:>8s} {'-'*6:>8s} {'-'*6:>8s}")
    for mn in ['intelligence_score', 'generalization', 'abstraction', 'memory_use',
                'lifetime_learning', 'behavioral_complexity', 'multi_task']:
        evolved_val = m.get(mn, 0)
        if mn in bl['metric_baselines']:
            mb = bl['metric_baselines'][mn]
            sig = (evolved_val - mb['mean']) / mb['std'] if mb['std'] > 0 else 0
            print(f"    {mn:<25s} {evolved_val:8.4f} {mb['mean']:8.4f} {sig:+7.1f}σ")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Cognitive Evolution Baseline')
    parser.add_argument('--samples', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--compare', type=str, default=None,
                        help='"latest" or path to checkpoint')
    args = parser.parse_args()

    baseline_path = os.path.join(TOOLS_DIR, 'cognition_baseline.json')

    if args.compare:
        if not os.path.exists(baseline_path):
            print("No baseline found, running baseline first...")
            run_baseline(n_samples=args.samples, seed=args.seed)

        if args.compare == 'latest':
            ckpt = os.path.join(TOOLS_DIR, 'cognition_checkpoints', 'latest.json')
        else:
            ckpt = args.compare

        compare_with_evolved(baseline_path, ckpt)
    else:
        run_baseline(n_samples=args.samples, seed=args.seed)


if __name__ == '__main__':
    main()
