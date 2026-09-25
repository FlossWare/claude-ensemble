#!/usr/bin/env python3
"""Experiment 1: Ablation test on best v4 hybrid organism.

Replaces all SURPRISE nodes with (a) ABS, (b) ZERO, (c) random subtrees
to determine if SURPRISE is load-bearing or exploited as abs(input).
"""

import copy
import json
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ga_self_aware import (
    Op, ARITY, Node, SelfAwareContext, execute,
    evaluate_organism, compute_fitness, parse_program,
    random_tree,
    DelayedEchoTask, SequentialXORTask, RunningMaxTask,
    AccumulatorTask, StateSwitcherTask,
    SequencePredictionTask, ErrorCorrectionTask, NoveltyDetectionTask,
    PersistentNavigationTask,
)
from ga_sequence_data import REAL_DATA_TASKS, prefetch_sequences

ALL_TASKS = {
    'delayed_echo': DelayedEchoTask(),
    'sequential_xor': SequentialXORTask(),
    'running_max': RunningMaxTask(),
    'accumulator': AccumulatorTask(),
    'state_switcher': StateSwitcherTask(),
    'sequence_prediction': SequencePredictionTask(),
    'error_correction': ErrorCorrectionTask(),
    'novelty_detection': NoveltyDetectionTask(),
    'persistent_nav': PersistentNavigationTask(),
    **REAL_DATA_TASKS,
}


def count_op(node, target_op):
    c = 1 if node.op == target_op else 0
    return c + sum(count_op(ch, target_op) for ch in node.children)


def replace_all(node, target_op, replacement_fn, rng):
    node = copy.deepcopy(node)
    return _replace(node, target_op, replacement_fn, rng)


def _replace(node, target_op, replacement_fn, rng):
    if node.op == target_op:
        return replacement_fn(node, rng)
    node.children = [_replace(ch, target_op, replacement_fn, rng)
                     for ch in node.children]
    return node


def replace_with_abs(node, rng):
    return Node(op=Op.ABS, children=node.children[:1])


def replace_with_zero(node, rng):
    return Node(op=Op.ZERO, children=[])


def replace_with_random(node, rng):
    return random_tree(rng, max_depth=2)


def replace_with_sense(node, rng):
    return Node(op=Op.SENSE, children=node.children[:1])


def evaluate(label, tree):
    scores = evaluate_organism(tree, ALL_TASKS, n_trials=20, seed=42)
    fitness = compute_fitness(scores)
    return label, fitness, scores


def main():
    best_path = os.path.join(os.path.dirname(__file__), 'hybrid_best.json')
    with open(best_path) as f:
        best = json.load(f)

    tree = parse_program(best['program'])
    n_surprise = count_op(tree, Op.SURPRISE)
    n_predict = count_op(tree, Op.PREDICT)
    n_step = count_op(tree, Op.STEP)
    n_last_out = count_op(tree, Op.LAST_OUT)

    print(f"Best organism: {tree.size()} nodes, fitness={best['fitness']:.4f}")
    print(f"Self-ref ops: SURPRISE={n_surprise} STEP={n_step} PREDICT={n_predict} LAST_OUT={n_last_out}")
    print()

    rng = random.Random(42)

    variants = [
        ("CONTROL (original)", tree),
        ("SURPRISE -> ABS", replace_all(tree, Op.SURPRISE, replace_with_abs, rng)),
        ("SURPRISE -> ZERO", replace_all(tree, Op.SURPRISE, replace_with_zero, rng)),
        ("SURPRISE -> SENSE", replace_all(tree, Op.SURPRISE, replace_with_sense, rng)),
        ("SURPRISE -> random(depth=2)", replace_all(tree, Op.SURPRISE, replace_with_random, rng)),
    ]

    results = []
    for label, variant_tree in variants:
        label, fitness, scores = evaluate(label, variant_tree)
        results.append({
            'variant': label,
            'fitness': fitness,
            'size': variant_tree.size(),
            'scores': scores,
        })

        print(f"=== {label} ===")
        print(f"  Fitness: {fitness:.4f}  (size: {variant_tree.size()})")
        for task, score in sorted(scores.items()):
            ctrl_score = results[0]['scores'].get(task, 0)
            delta = score - ctrl_score
            marker = '  ' if abs(delta) < 0.01 else ('+' if delta > 0 else '-')
            print(f"    {task:25s}: {score:.4f}  ({marker}{delta:+.4f})")
        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    ctrl_fit = results[0]['fitness']
    for r in results:
        delta = r['fitness'] - ctrl_fit
        pct = 100 * delta / ctrl_fit if ctrl_fit > 0 else 0
        print(f"  {r['variant']:35s}  fit={r['fitness']:.4f}  delta={delta:+.4f} ({pct:+.1f}%)")

    print()
    abs_fit = results[1]['fitness']
    if abs(abs_fit - ctrl_fit) < 0.01:
        print("VERDICT: SURPRISE = ABS confirmed. SURPRISE is NOT used for prediction error.")
        print("         The organism hacked SURPRISE as abs(input).")
    elif abs_fit < ctrl_fit * 0.8:
        print("VERDICT: SURPRISE is LOAD-BEARING and NOT just abs().")
        print("         The organism uses SURPRISE beyond simple abs(input).")
    else:
        print("VERDICT: Partial dependence. SURPRISE contributes but partially replaceable by ABS.")

    out_path = os.path.join(os.path.dirname(__file__), 'exp1_ablation_results.json')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
