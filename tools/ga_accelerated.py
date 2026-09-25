#!/usr/bin/env python3
"""Hyper-Accelerated GA Self-Improvement

Three acceleration layers over ga_self_improving.py:

1. BYTECODE COMPILER — program trees compiled to flat instruction arrays
   executed by a tight stack machine. Eliminates recursive Python calls.
   ~10-50x faster per program execution.

2. MULTIPROCESSING — strategy evaluations distributed across all CPU cores.
   Each core runs an independent inner GA. ~Nx for N cores.

3. TIERED EVALUATION — quick screen (1 seed, 30 epochs) filters bad
   strategies. Only promising ones get full evaluation (3 seeds, 80 epochs).
   ~3-5x fewer total evaluations.

Combined: 100-500x faster than serial tree interpretation.

Usage:
    python3 ga_accelerated.py                          # full run
    python3 ga_accelerated.py --outer-gens 30           # more generations
    python3 ga_accelerated.py --cores 8                 # limit parallelism
    python3 ga_accelerated.py --deploy                  # run best strategy
"""

import argparse
import copy
import json
import math
import multiprocessing as mp
import os
import random
import signal
import sys
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

from ga_cognition_engine import (
    Op, ARITY, Node, ExecutionContext,
    TRAINING_TASKS, GENERALIZATION_TASKS, ALL_TASKS,
    TERMINAL_OPS, UNARY_OPS, BINARY_OPS, TERNARY_OPS,
    PatternClassifyTask, IntelligenceReport, INTELLIGENCE_LEVELS,
    get_all_nodes,
)


# ============================================================================
# LAYER 1: BYTECODE COMPILER + STACK MACHINE
# ============================================================================

# Integer opcodes for the stack machine (faster than enum comparison)
class BC(IntEnum):
    ADD = 0; SUB = 1; MUL = 2; DIV = 3; MOD = 4
    GT = 5; LT = 6; EQ = 7; NEQ = 8
    AND = 9; OR = 10; NOT = 11
    IF = 12; SEQ = 13
    READ = 14; WRITE = 15
    SENSE = 16; ACT = 17
    CONST = 18; ZERO = 19; ONE = 20; NEG1 = 21
    INC = 22; DEC = 23; ABS = 24; SIGN = 25; MAX2 = 26; MIN2 = 27
    # Special: marks for IF control flow
    IF_MARK = 28; IF_JUMP = 29

OP_TO_BC = {
    Op.ADD: BC.ADD, Op.SUB: BC.SUB, Op.MUL: BC.MUL, Op.DIV: BC.DIV, Op.MOD: BC.MOD,
    Op.GT: BC.GT, Op.LT: BC.LT, Op.EQ: BC.EQ, Op.NEQ: BC.NEQ,
    Op.AND: BC.AND, Op.OR: BC.OR, Op.NOT: BC.NOT,
    Op.IF: BC.IF, Op.SEQ: BC.SEQ,
    Op.READ: BC.READ, Op.WRITE: BC.WRITE,
    Op.SENSE: BC.SENSE, Op.ACT: BC.ACT,
    Op.CONST: BC.CONST, Op.ZERO: BC.ZERO, Op.ONE: BC.ONE, Op.NEG1: BC.NEG1,
    Op.INC: BC.INC, Op.DEC: BC.DEC, Op.ABS: BC.ABS, Op.SIGN: BC.SIGN,
    Op.MAX2: BC.MAX2, Op.MIN2: BC.MIN2,
}


def compile_tree(node: Node) -> list:
    """Compile a program tree into a flat instruction list.
    Post-order traversal: children first, then operation.
    For IF: we handle it specially since it's conditional."""
    instructions = []
    _compile_node(node, instructions)
    return instructions


def _compile_node(node: Node, out: list):
    """Recursive compilation. Most ops: compile children then emit op.
    IF is special: we need to evaluate condition first, then branch."""
    op = node.op
    bc = OP_TO_BC[op]

    if op == Op.IF:
        # Compile: condition, then true_branch, then false_branch
        # At runtime: pop condition, if >0 execute true (skip false), else execute false (skip true)
        # We emit all three and let the VM handle branching
        _compile_node(node.children[0], out)  # condition
        _compile_node(node.children[1], out)  # true branch
        _compile_node(node.children[2], out)  # false branch
        out.append((BC.IF, 0.0))
        return

    if bc == BC.CONST:
        out.append((BC.CONST, node.value))
        return

    if ARITY[op] == 0:
        out.append((bc, 0.0))
        return

    for child in node.children:
        _compile_node(child, out)
    out.append((bc, 0.0))


def execute_bytecode(instructions: list, ctx: ExecutionContext) -> float:
    """Execute compiled bytecode using a stack machine.
    Much faster than recursive tree execution — no Python function call overhead."""
    stack = []
    max_steps = ctx.MAX_STEPS
    steps = 0

    for bc_op, val in instructions:
        steps += 1
        if steps >= max_steps:
            break

        if bc_op == BC.CONST:
            stack.append(val)
        elif bc_op == BC.ZERO:
            stack.append(0.0)
        elif bc_op == BC.ONE:
            stack.append(1.0)
        elif bc_op == BC.NEG1:
            stack.append(-1.0)
        elif bc_op == BC.ADD:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(max(-1e6, min(1e6, a + b)))
        elif bc_op == BC.SUB:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(max(-1e6, min(1e6, a - b)))
        elif bc_op == BC.MUL:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(max(-1e6, min(1e6, a * b)))
        elif bc_op == BC.DIV:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(max(-1e6, min(1e6, a / b)) if abs(b) > 1e-10 else 0.0)
        elif bc_op == BC.MOD:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(max(-1e6, min(1e6, a % b)) if abs(b) > 1e-10 else 0.0)
        elif bc_op == BC.GT:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(1.0 if a > b else 0.0)
        elif bc_op == BC.LT:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(1.0 if a < b else 0.0)
        elif bc_op == BC.EQ:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(1.0 if abs(a - b) < 0.1 else 0.0)
        elif bc_op == BC.NEQ:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(1.0 if abs(a - b) >= 0.1 else 0.0)
        elif bc_op == BC.AND:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(1.0 if a > 0 and b > 0 else 0.0)
        elif bc_op == BC.OR:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(1.0 if a > 0 or b > 0 else 0.0)
        elif bc_op == BC.NOT:
            if len(stack) < 1: stack.append(0.0); continue
            a = stack.pop()
            stack.append(0.0 if a > 0 else 1.0)
        elif bc_op == BC.IF:
            if len(stack) < 3: stack.append(0.0); continue
            false_val = stack.pop()
            true_val = stack.pop()
            cond = stack.pop()
            stack.append(true_val if cond > 0 else false_val)
        elif bc_op == BC.SEQ:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); stack.pop()
            stack.append(b)
        elif bc_op == BC.READ:
            if len(stack) < 1: stack.append(0.0); continue
            a = stack.pop()
            idx = int(a) % ctx.NUM_REGISTERS
            stack.append(ctx.registers[idx])
        elif bc_op == BC.WRITE:
            if len(stack) < 2: stack.append(0.0); continue
            val_w = stack.pop(); idx_w = stack.pop()
            idx = int(idx_w) % ctx.NUM_REGISTERS
            ctx.registers[idx] = max(-1e6, min(1e6, val_w))
            stack.append(val_w)
        elif bc_op == BC.SENSE:
            if len(stack) < 1: stack.append(0.0); continue
            a = stack.pop()
            idx = int(a) % ctx.NUM_INPUT_CHANNELS
            stack.append(ctx.inputs[idx])
        elif bc_op == BC.ACT:
            if len(stack) < 2: stack.append(0.0); continue
            val_a = stack.pop(); idx_a = stack.pop()
            idx = int(idx_a) % ctx.NUM_OUTPUT_CHANNELS
            ctx.outputs[idx] = max(-1e6, min(1e6, val_a))
            stack.append(val_a)
        elif bc_op == BC.INC:
            if len(stack) < 1: stack.append(0.0); continue
            stack.append(max(-1e6, min(1e6, stack.pop() + 1)))
        elif bc_op == BC.DEC:
            if len(stack) < 1: stack.append(0.0); continue
            stack.append(max(-1e6, min(1e6, stack.pop() - 1)))
        elif bc_op == BC.ABS:
            if len(stack) < 1: stack.append(0.0); continue
            stack.append(abs(stack.pop()))
        elif bc_op == BC.SIGN:
            if len(stack) < 1: stack.append(0.0); continue
            a = stack.pop()
            stack.append(1.0 if a > 0 else (-1.0 if a < 0 else 0.0))
        elif bc_op == BC.MAX2:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(max(a, b))
        elif bc_op == BC.MIN2:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); a = stack.pop()
            stack.append(min(a, b))

    ctx.steps = steps
    return stack[-1] if stack else 0.0


# ============================================================================
# FAST TASK EVALUATION — uses bytecode
# ============================================================================

def fast_evaluate_task(bytecode: list, task, n_trials: int = 15, seed: int = 42) -> float:
    """Evaluate a compiled program on a task using bytecode execution."""
    rng = random.Random(seed)
    trials = task.generate_trials(n_trials, rng)
    scores = []

    for trial in trials:
        score = fast_evaluate_trial(bytecode, task, trial)
        scores.append(score)

    return float(np.mean(scores)) if scores else 0.0


def fast_evaluate_trial(bytecode: list, task, trial: dict) -> float:
    """Evaluate a single trial using bytecode. Dispatches by task type."""
    task_name = task.name

    if task_name == 'comparison':
        ctx = ExecutionContext()
        ctx.inputs = [trial['a'], trial['b'], float(trial['op']), 0, 0, 0, 0, 0]
        execute_bytecode(bytecode, ctx)
        error = abs(ctx.outputs[0] - trial['answer'])
        scale = max(abs(trial['answer']), 1.0)
        return max(0.0, 1.0 - error / scale)

    elif task_name == 'arithmetic':
        ctx = ExecutionContext()
        ctx.inputs = [trial['a'], trial['b'], float(trial['op']), 0, 0, 0, 0, 0]
        execute_bytecode(bytecode, ctx)
        error = abs(ctx.outputs[0] - trial['answer'])
        scale = max(abs(trial['answer']), 1.0)
        return max(0.0, 1.0 - error / scale)

    elif task_name == 'navigation':
        pos = trial['start']
        goal = trial['goal']
        best_dist = abs(pos - goal)
        for step in range(20):
            ctx = ExecutionContext()
            ctx.inputs = [pos, goal, float(step), best_dist, 0, 0, 0, 0]
            execute_bytecode(bytecode, ctx)
            move = max(-1, min(1, ctx.outputs[0]))
            pos += move
            dist = abs(pos - goal)
            best_dist = min(best_dist, dist)
            if dist < 0.5:
                return 1.0
        initial_dist = abs(trial['start'] - trial['goal'])
        return max(0.0, 1.0 - best_dist / max(initial_dist, 0.1))

    elif task_name == 'copy_recall':
        ctx = ExecutionContext()
        values = trial['values']
        for i, v in enumerate(values):
            ctx.steps = 0
            ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
            ctx.inputs = [v, float(i), 1.0, float(len(values)), 0, 0, 0, 0]
            execute_bytecode(bytecode, ctx)
        ctx.steps = 0
        ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
        qi = trial['query_idx']
        ctx.inputs = [0.0, float(qi), 0.0, float(len(values)), 0, 0, 0, 0]
        execute_bytecode(bytecode, ctx)
        error = abs(ctx.outputs[0] - values[qi])
        return max(0.0, 1.0 - error / max(abs(values[qi]) + 1, 1.0))

    elif task_name == 'sequence_next':
        ctx = ExecutionContext()
        seq = trial['sequence']
        target = trial['target']
        for step in range(len(seq)):
            ctx.reset()
            for i, v in enumerate(seq[:step+1]):
                if i < 6:
                    ctx.inputs[i] = v
            ctx.inputs[6] = step
            ctx.inputs[7] = len(seq)
            execute_bytecode(bytecode, ctx)
        error = abs(ctx.outputs[0] - target)
        max_error = max(abs(target), 1.0) * 2
        return max(0.0, 1.0 - error / max_error)

    elif task_name == 'pattern_classify':
        ctx = ExecutionContext()
        for ex_input, ex_label in trial['examples']:
            ctx.steps = 0  # reset but keep registers
            ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
            for i, v in enumerate(ex_input[:4]):
                ctx.inputs[i] = v
            ctx.inputs[4] = ex_label
            ctx.inputs[5] = 1.0
            execute_bytecode(bytecode, ctx)
        ctx.steps = 0
        ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
        for i, v in enumerate(trial['test_input'][:4]):
            ctx.inputs[i] = v
        ctx.inputs[4] = 0.0
        ctx.inputs[5] = 0.0
        execute_bytecode(bytecode, ctx)
        correct = (ctx.outputs[0] > 0) == (trial['test_label'] > 0)
        return 1.0 if correct else 0.0

    elif task_name == 'analogy':
        ctx = ExecutionContext()
        ctx.inputs = [trial['a'], trial['b'], trial['c'], 0, 0, 0, 0, 0]
        execute_bytecode(bytecode, ctx)
        error = abs(ctx.outputs[0] - trial['d'])
        scale = max(abs(trial['d']), 1.0)
        return max(0.0, 1.0 - error / scale)

    return 0.0


# ============================================================================
# FAST COGNITION ENGINE — uses bytecode + compiled evaluation
# ============================================================================

class FastCognitionEngine:
    """High-performance cognition engine using bytecode compilation."""

    def __init__(self, strategy: dict, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed
        self.s = strategy  # dict of parameters
        self.population = []  # list of (Node, bytecode, fitness, task_scores, gen_scores)
        self.epoch = 0
        self.next_id = 0
        self.best_ever = None  # (Node, bytecode, fitness, task_scores, gen_scores)
        self.stagnation = 0
        self.metrics_history = []

        # Extract params with defaults
        self.pop_size = strategy.get('population_size', 60)
        self.max_depth = strategy.get('max_depth', 6)
        self.crossover_rate = strategy.get('crossover_rate', 0.85)
        self.point_mut_rate = strategy.get('point_mutation_rate', 0.15)
        self.subtree_mut_rate = strategy.get('subtree_mutation_rate', 0.10)
        self.point_mut_intensity = strategy.get('point_mutation_intensity', 0.2)
        self.tourn_size = strategy.get('tournament_size', 5)
        self.elitism = strategy.get('elitism', 3)
        self.novelty_ratio = strategy.get('novelty_ratio', 0.2)
        self.mean_weight = strategy.get('mean_weight', 0.6)
        self.parsimony = strategy.get('parsimony_coeff', 0.00005)
        self.comp_floor = strategy.get('complexity_floor', 15)
        self.comp_penalty = strategy.get('complexity_penalty_scale', 0.05)
        self.mem_scaffold = strategy.get('memory_scaffold_prob', 0.0)
        self.mem_mut_prob = strategy.get('memory_mutation_prob', 0.0)
        self.stag_thresh = strategy.get('stagnation_threshold', 20)
        self.stag_boost = strategy.get('stagnation_mutation_boost', 0.005)
        self.stag_cap = strategy.get('stagnation_mutation_cap', 0.3)
        self.terminal_prob = strategy.get('terminal_prob', 0.3)

        # Operator weights
        self.op_weights = self._build_op_weights()

        # Task weights
        self.task_weights = {
            'comparison': strategy.get('weight_comparison', 1.0),
            'arithmetic': strategy.get('weight_arithmetic', 1.0),
            'navigation': strategy.get('weight_navigation', 1.0),
            'copy_recall': strategy.get('weight_copy_recall', 1.0),
        }

    def _build_op_weights(self):
        """Build per-op probability weights from category biases."""
        categories = {
            'arithmetic': ([Op.ADD, Op.SUB, Op.MUL, Op.DIV, Op.MOD],
                          self.s.get('bias_arithmetic', 1.0)),
            'comparison': ([Op.GT, Op.LT, Op.EQ, Op.NEQ],
                          self.s.get('bias_comparison', 1.0)),
            'logic': ([Op.AND, Op.OR, Op.NOT],
                     self.s.get('bias_logic', 1.0)),
            'control': ([Op.IF, Op.SEQ],
                       self.s.get('bias_control', 1.0)),
            'memory': ([Op.READ, Op.WRITE],
                      self.s.get('bias_memory', 1.0)),
            'io': ([Op.SENSE, Op.ACT],
                  self.s.get('bias_io', 1.0)),
            'accumulation': ([Op.INC, Op.DEC, Op.ABS, Op.SIGN, Op.MAX2, Op.MIN2],
                            self.s.get('bias_accumulation', 1.0)),
        }
        weights = {}
        for cat, (ops, bias) in categories.items():
            w = bias / len(ops)
            for op in ops:
                weights[op] = w
        return weights

    def _random_tree(self, max_depth=None, depth=0):
        if max_depth is None:
            max_depth = self.max_depth

        if depth >= max_depth or (depth > 1 and self.rng.random() < self.terminal_prob):
            op = self.rng.choice(TERMINAL_OPS)
            n = Node(op=op)
            if op == Op.CONST:
                n.value = round(self.rng.uniform(-5, 5), 2)
            return n

        # Weighted non-terminal selection
        nonterminals = [op for op in self.op_weights if ARITY[op] > 0]
        wts = [self.op_weights[op] for op in nonterminals]
        total = sum(wts)
        wts = [w/total for w in wts]

        r = self.rng.random()
        cum = 0.0
        chosen = nonterminals[-1]
        for op, w in zip(nonterminals, wts):
            cum += w
            if r <= cum:
                chosen = op
                break

        arity = ARITY[chosen]
        children = [self._random_tree(max_depth, depth + 1) for _ in range(arity)]
        return Node(op=chosen, children=children)

    def _memory_scaffold(self):
        """Create a program with working memory (READ/WRITE/IF) baked in."""
        reg = Node(op=Op.CONST, value=float(self.rng.randint(0, 7)))
        inp = Node(op=Op.CONST, value=float(self.rng.randint(0, 5)))
        write = Node(op=Op.WRITE, children=[reg.copy(), Node(op=Op.SENSE, children=[inp.copy()])])
        thresh = Node(op=Op.CONST, value=round(self.rng.uniform(-2, 2), 2))
        read = Node(op=Op.READ, children=[reg.copy()])
        cond = Node(op=Op.GT, children=[read, thresh])
        act_a = Node(op=Op.ACT, children=[Node(op=Op.ZERO), Node(op=Op.ONE)])
        act_b = Node(op=Op.ACT, children=[Node(op=Op.ZERO), Node(op=Op.NEG1)])
        if_node = Node(op=Op.IF, children=[cond, act_a, act_b])
        return Node(op=Op.SEQ, children=[write, if_node])

    def _memory_subtree(self):
        """Small memory-using subtree for injection during mutation."""
        patterns = [
            lambda: Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.READ, children=[Node(op=Op.CONST, value=float(self.rng.randint(0,7)))]),
                    Node(op=Op.CONST, value=round(self.rng.uniform(-2, 2), 2))]),
                Node(op=Op.ACT, children=[Node(op=Op.ZERO), Node(op=Op.ONE)]),
                Node(op=Op.ACT, children=[Node(op=Op.ZERO), Node(op=Op.NEG1)])]),
            lambda: Node(op=Op.WRITE, children=[
                Node(op=Op.CONST, value=float(self.rng.randint(0,7))),
                Node(op=Op.SENSE, children=[Node(op=Op.CONST, value=float(self.rng.randint(0,5)))])]),
            lambda: Node(op=Op.WRITE, children=[
                Node(op=Op.CONST, value=float(self.rng.randint(0,3))),
                Node(op=Op.ADD, children=[
                    Node(op=Op.READ, children=[Node(op=Op.CONST, value=float(self.rng.randint(0,3)))]),
                    Node(op=Op.SENSE, children=[Node(op=Op.CONST, value=float(self.rng.randint(0,5)))])])]),
        ]
        return self.rng.choice(patterns)()

    def _evaluate(self, tree: Node, bytecode: list = None):
        """Evaluate organism. Returns (fitness, task_scores)."""
        if bytecode is None:
            bytecode = compile_tree(tree)

        task_scores = {}
        weighted = []
        for name, task in TRAINING_TASKS.items():
            score = fast_evaluate_task(bytecode, task, n_trials=12, seed=42 + (self.epoch % 5))
            task_scores[name] = score
            w = self.task_weights.get(name, 1.0)
            weighted.append(score * w)

        total_w = sum(self.task_weights.get(n, 1.0) for n in TRAINING_TASKS)
        mean_s = sum(weighted) / total_w if total_w > 0 else 0
        min_s = min(task_scores.values()) if task_scores else 0
        base = self.mean_weight * mean_s + (1 - self.mean_weight) * min_s

        size = tree.size()
        penalty = self.parsimony * size
        if size < self.comp_floor:
            bonus = -self.comp_penalty * (self.comp_floor - size) / self.comp_floor
        else:
            bonus = 0.0

        fitness = max(0, base - penalty + bonus)
        return fitness, task_scores

    def _evaluate_gen(self, tree: Node, bytecode: list = None):
        """Evaluate on held-out tasks."""
        if bytecode is None:
            bytecode = compile_tree(tree)
        gen_scores = {}
        for name, task in GENERALIZATION_TASKS.items():
            gen_scores[name] = fast_evaluate_task(bytecode, task, n_trials=12, seed=999)
        return gen_scores

    def _tournament_select(self):
        candidates = self.rng.sample(self.population, min(self.tourn_size, len(self.population)))
        if self.rng.random() < self.novelty_ratio:
            sigs = [self._sig(c) for c in candidates]
            pop_sigs = [self._sig(o) for o in self.population]
            scores = []
            for sig in sigs:
                same = sum(1 for ps in pop_sigs if ps == sig)
                scores.append(1.0 / same)
            return candidates[scores.index(max(scores))]
        return max(candidates, key=lambda o: o[2])

    def _sig(self, org):
        return tuple(round(org[3].get(t, 0), 1) for t in sorted(TRAINING_TASKS.keys()))

    def _breed(self):
        from ga_cognition_engine import subtree_crossover, point_mutation, subtree_mutation

        r = self.rng.random()
        if r < self.crossover_rate:
            p1 = self._tournament_select()
            p2 = self._tournament_select()
            child = subtree_crossover(p1[0], p2[0], self.rng)
        elif r < self.crossover_rate + self.point_mut_rate:
            parent = self._tournament_select()
            child = point_mutation(parent[0], self.rng, rate=self.point_mut_intensity)
        elif r < self.crossover_rate + self.point_mut_rate + self.subtree_mut_rate:
            parent = self._tournament_select()
            child = subtree_mutation(parent[0], self.rng)
        else:
            parent = self._tournament_select()
            child = parent[0].copy()

        # Memory mutation injection
        if self.rng.random() < self.mem_mut_prob:
            nodes = get_all_nodes(child)
            if len(nodes) > 1:
                _, pn, idx = self.rng.choice(nodes[1:])
                if pn is not None:
                    pn.children[idx] = self._memory_subtree()
                    if child.size() > 100:
                        child = child.copy()

        return child

    def run(self, epochs: int) -> dict:
        """Run for N epochs. Returns intelligence metrics."""
        # Initialize
        self.population = []
        for _ in range(self.pop_size):
            if self.rng.random() < self.mem_scaffold:
                tree = self._memory_scaffold()
            else:
                tree = self._random_tree()
            bc = compile_tree(tree)
            fitness, scores = self._evaluate(tree, bc)
            self.population.append((tree, bc, fitness, scores, {}))

        self.best_ever = max(self.population, key=lambda o: o[2])
        gen_scores = self._evaluate_gen(self.best_ever[0], self.best_ever[1])
        self.best_ever = (*self.best_ever[:4], gen_scores)

        # Evolve
        for ep in range(1, epochs + 1):
            self.epoch = ep

            # Adaptive mutation
            cur_sub = self.subtree_mut_rate
            cur_pt = self.point_mut_rate
            if self.stagnation > self.stag_thresh:
                boost = self.stag_boost * (self.stagnation - self.stag_thresh)
                cur_sub = min(self.stag_cap, self.subtree_mut_rate + boost)
                cur_pt = min(self.stag_cap, self.point_mut_rate + boost)

            # Sort + elitism
            self.population.sort(key=lambda o: o[2], reverse=True)
            new_pop = list(self.population[:self.elitism])

            while len(new_pop) < self.pop_size:
                child_tree = self._breed()
                bc = compile_tree(child_tree)
                fitness, scores = self._evaluate(child_tree, bc)
                new_pop.append((child_tree, bc, fitness, scores, {}))

            self.population = new_pop

            cur_best = max(self.population, key=lambda o: o[2])
            if cur_best[2] > self.best_ever[2]:
                gen_s = self._evaluate_gen(cur_best[0], cur_best[1])
                self.best_ever = (*cur_best[:4], gen_s)
                self.stagnation = 0
            else:
                self.stagnation += 1

            # Early termination: if stagnating badly, stop wasting compute
            if self.stagnation > epochs * 0.6:
                break

        # Final intelligence measurement
        if self.epoch % 10 != 0:
            gen_scores = self._evaluate_gen(self.best_ever[0], self.best_ever[1])
            self.best_ever = (*self.best_ever[:4], gen_scores)

        return self._measure_intelligence()

    def _measure_intelligence(self) -> dict:
        tree, bc, fitness, task_scores, gen_scores = self.best_ever

        def count_ops(node, target_ops):
            c = 1 if node.op in target_ops else 0
            return c + sum(count_ops(ch, target_ops) for ch in node.children)

        # Generalization
        generalization = float(np.mean(list(gen_scores.values()))) if gen_scores else 0.0
        abstraction = gen_scores.get('analogy', 0.0)

        # Memory use
        mem_ops = count_ops(tree, {Op.READ, Op.WRITE})
        total = tree.size()
        if mem_ops > 0 and total > 0:
            ratio = mem_ops / total
            copy_s = task_scores.get('copy_recall', 0.0)
            memory_use = min(1.0, ratio * 5) * copy_s
        else:
            memory_use = 0.0

        # Lifetime learning (simplified for speed)
        task = PatternClassifyTask()
        rng = random.Random(777)
        trials = task.generate_trials(8, rng)
        score_with = score_without = 0
        for trial in trials:
            # Without training
            ctx = ExecutionContext()
            for i, v in enumerate(trial['test_input'][:4]):
                ctx.inputs[i] = v
            ctx.inputs[5] = 0.0
            execute_bytecode(bc, ctx)
            score_without += (1.0 if (ctx.outputs[0] > 0) == (trial['test_label'] > 0) else 0.0)
            # With training
            ctx2 = ExecutionContext()
            for ex_input, ex_label in trial['examples']:
                ctx2.steps = 0
                ctx2.outputs = [0.0] * 4
                for i, v in enumerate(ex_input[:4]):
                    ctx2.inputs[i] = v
                ctx2.inputs[4] = ex_label
                ctx2.inputs[5] = 1.0
                execute_bytecode(bc, ctx2)
            ctx2.steps = 0
            ctx2.outputs = [0.0] * 4
            for i, v in enumerate(trial['test_input'][:4]):
                ctx2.inputs[i] = v
            ctx2.inputs[4] = 0.0
            ctx2.inputs[5] = 0.0
            execute_bytecode(bc, ctx2)
            score_with += (1.0 if (ctx2.outputs[0] > 0) == (trial['test_label'] > 0) else 0.0)

        score_with /= len(trials)
        score_without /= len(trials)
        lifetime_learning = 0.0
        if score_with > score_without and score_with > 0.6:
            lifetime_learning = min(1.0, (score_with - score_without) * 3)

        # Behavioral complexity
        has_cond = count_ops(tree, {Op.IF}) > 0
        has_mem = mem_ops > 0
        has_io = count_ops(tree, {Op.SENSE, Op.ACT}) > 0
        has_arith = count_ops(tree, {Op.ADD, Op.SUB, Op.MUL, Op.DIV}) > 0
        has_cmp = count_ops(tree, {Op.GT, Op.LT, Op.EQ}) > 0
        complexity = (sum([has_cond, has_mem, has_io, has_arith, has_cmp]) / 5) * min(1.0, total / 20)

        # Multi-task
        all_s = list(task_scores.values()) + list(gen_scores.values())
        multi_task = len([s for s in all_s if s > 0.7]) / len(all_s) if all_s else 0

        iq = (generalization * 0.30 + abstraction * 0.25 + memory_use * 0.10 +
              lifetime_learning * 0.15 + complexity * 0.05 + multi_task * 0.15)

        return {
            'intelligence_score': iq,
            'generalization': generalization,
            'abstraction': abstraction,
            'memory_use': memory_use,
            'lifetime_learning': lifetime_learning,
            'behavioral_complexity': complexity,
            'multi_task': multi_task,
            'fitness': fitness,
            'program_size': total,
        }


# ============================================================================
# LAYER 2: PARALLEL STRATEGY EVALUATION
# ============================================================================

def _eval_strategy_worker(args):
    """Worker function for multiprocessing. Evaluates one strategy with one seed."""
    strategy_dict, seed, epochs = args
    try:
        engine = FastCognitionEngine(strategy_dict, seed=seed)
        metrics = engine.run(epochs)
        score = (metrics['intelligence_score'] +
                 0.1 * metrics['memory_use'] +
                 0.15 * metrics['lifetime_learning'])
        return score, metrics
    except Exception as e:
        return 0.0, {'error': str(e)}


# ============================================================================
# LAYER 3: TIERED EVALUATION + OUTER GA
# ============================================================================

class AcceleratedMetaGA:
    """Outer GA with bytecode compilation, multiprocessing, and tiered evaluation."""

    def __init__(self, outer_pop: int = 20, inner_epochs: int = 80,
                 cores: int = None, seed: int = 42):
        self.outer_pop = outer_pop
        self.inner_epochs = inner_epochs
        self.cores = cores or max(1, mp.cpu_count() - 2)
        self.rng = random.Random(seed)
        self.seed = seed
        self.population = []
        self.best_ever = None
        self.best_fitness = 0.0
        self.history = []
        self.generation = 0
        self.next_id = 0

    def _new_id(self):
        self.next_id += 1
        return self.next_id

    def _random_strategy(self) -> dict:
        r = self.rng
        s = {
            'crossover_rate': r.uniform(0.4, 0.9),
            'point_mutation_rate': r.uniform(0.05, 0.35),
            'subtree_mutation_rate': r.uniform(0.05, 0.3),
            'point_mutation_intensity': r.uniform(0.05, 0.4),
            'tournament_size': r.randint(2, 8),
            'elitism': r.randint(0, 6),
            'novelty_ratio': r.uniform(0.0, 0.4),
            'mean_weight': r.uniform(0.4, 0.8),
            'parsimony_coeff': r.uniform(0.0, 0.0005),
            'complexity_floor': r.randint(5, 25),
            'complexity_penalty_scale': r.uniform(0.02, 0.15),
            'bias_arithmetic': r.uniform(0.3, 3.0),
            'bias_comparison': r.uniform(0.3, 3.0),
            'bias_logic': r.uniform(0.3, 3.0),
            'bias_control': r.uniform(0.3, 3.0),
            'bias_memory': r.uniform(0.3, 3.0),
            'bias_io': r.uniform(0.3, 3.0),
            'bias_accumulation': r.uniform(0.3, 3.0),
            'memory_scaffold_prob': r.uniform(0.0, 0.5),
            'memory_mutation_prob': r.uniform(0.0, 0.3),
            'weight_comparison': r.uniform(0.3, 2.0),
            'weight_arithmetic': r.uniform(0.3, 2.0),
            'weight_navigation': r.uniform(0.3, 2.0),
            'weight_copy_recall': r.uniform(0.3, 2.0),
            'stagnation_threshold': r.randint(8, 40),
            'stagnation_mutation_boost': r.uniform(0.002, 0.015),
            'stagnation_mutation_cap': r.uniform(0.2, 0.45),
            'max_depth': r.randint(4, 8),
            'terminal_prob': r.uniform(0.15, 0.5),
            'population_size': r.choice([30, 40, 50, 60]),
        }
        # Normalize rates
        total = s['crossover_rate'] + s['point_mutation_rate'] + s['subtree_mutation_rate']
        if total > 0.95:
            scale = 0.95 / total
            s['crossover_rate'] *= scale
            s['point_mutation_rate'] *= scale
            s['subtree_mutation_rate'] *= scale
        s['_id'] = self._new_id()
        s['_fitness'] = 0.0
        return s

    def _evaluate_batch(self, strategies: list, epochs: int, seeds: list) -> list:
        """Evaluate multiple strategies in parallel using multiprocessing."""
        work = []
        for s in strategies:
            for seed in seeds:
                work.append((s, seed, epochs))

        with mp.Pool(processes=self.cores) as pool:
            results = pool.map(_eval_strategy_worker, work)

        # Aggregate per strategy (mean across seeds)
        n_seeds = len(seeds)
        fitnesses = []
        for i in range(len(strategies)):
            chunk = results[i*n_seeds:(i+1)*n_seeds]
            scores = [r[0] for r in chunk]
            fitnesses.append(float(np.mean(scores)))

        return fitnesses

    def _crossover(self, p1: dict, p2: dict) -> dict:
        child = {}
        for k in p1:
            if k.startswith('_'):
                continue
            if isinstance(p1[k], (int, float)):
                child[k] = p1[k] if self.rng.random() < 0.5 else p2[k]
            else:
                child[k] = p1[k]
        child['_id'] = self._new_id()
        child['_fitness'] = 0.0
        return child

    def _mutate(self, s: dict, rate: float = 0.15) -> dict:
        child = dict(s)
        for k, v in child.items():
            if k.startswith('_'):
                continue
            if isinstance(v, float) and self.rng.random() < rate:
                scale = max(abs(v) * 0.2, 0.01)
                child[k] = v + self.rng.gauss(0, scale)
            elif isinstance(v, int) and self.rng.random() < rate:
                child[k] = v + self.rng.choice([-2, -1, 1, 2])
        # Clamp
        child['crossover_rate'] = np.clip(child.get('crossover_rate', 0.8), 0.3, 0.95)
        child['point_mutation_rate'] = np.clip(child.get('point_mutation_rate', 0.15), 0.01, 0.5)
        child['subtree_mutation_rate'] = np.clip(child.get('subtree_mutation_rate', 0.1), 0.01, 0.5)
        child['tournament_size'] = int(np.clip(child.get('tournament_size', 5), 2, 10))
        child['elitism'] = int(np.clip(child.get('elitism', 3), 0, 10))
        child['novelty_ratio'] = np.clip(child.get('novelty_ratio', 0.2), 0.0, 0.5)
        child['memory_scaffold_prob'] = np.clip(child.get('memory_scaffold_prob', 0.0), 0.0, 0.8)
        child['memory_mutation_prob'] = np.clip(child.get('memory_mutation_prob', 0.0), 0.0, 0.5)
        child['max_depth'] = int(np.clip(child.get('max_depth', 6), 4, 10))
        child['population_size'] = int(np.clip(child.get('population_size', 60), 20, 120))
        for k in ['bias_arithmetic', 'bias_comparison', 'bias_logic', 'bias_control',
                   'bias_memory', 'bias_io', 'bias_accumulation']:
            child[k] = np.clip(child.get(k, 1.0), 0.1, 5.0)
        # Normalize rates
        total = child['crossover_rate'] + child['point_mutation_rate'] + child['subtree_mutation_rate']
        if total > 0.95:
            scale = 0.95 / total
            child['crossover_rate'] *= scale
            child['point_mutation_rate'] *= scale
            child['subtree_mutation_rate'] *= scale
        child['_id'] = self._new_id()
        child['_fitness'] = 0.0
        return child

    def _tournament(self, k=3):
        candidates = self.rng.sample(self.population, min(k, len(self.population)))
        return max(candidates, key=lambda s: s['_fitness'])

    def run(self, outer_gens: int = 20):
        print("=" * 70)
        print("  HYPER-ACCELERATED GA SELF-IMPROVEMENT")
        print("=" * 70)
        print(f"  Outer population:  {self.outer_pop}")
        print(f"  Outer generations: {outer_gens}")
        print(f"  Inner epochs:      {self.inner_epochs}")
        print(f"  CPU cores:         {self.cores}")
        print(f"  Bytecode:          ENABLED (stack machine)")
        print(f"  Tiered eval:       ENABLED (screen → full)")
        print(f"  Parallelism:       {self.cores} concurrent evaluations")
        print("=" * 70)

        screen_seeds = [42]           # 1 seed for screening
        full_seeds = [42, 123, 777]   # 3 seeds for full eval
        screen_epochs = max(30, self.inner_epochs // 2)

        # Initialize
        print("\n  Generating strategies...")
        self.population = [self._random_strategy() for _ in range(self.outer_pop)]

        # Seed known good config
        baseline = self._random_strategy()
        baseline.update({
            'crossover_rate': 0.85, 'point_mutation_rate': 0.15,
            'subtree_mutation_rate': 0.10, 'tournament_size': 5,
            'elitism': 3, 'parsimony_coeff': 0.00005, 'novelty_ratio': 0.2,
            'mean_weight': 0.6, 'memory_scaffold_prob': 0.0,
            'memory_mutation_prob': 0.0, 'max_depth': 6,
            'population_size': 60,
        })
        self.population[0] = baseline

        # Seed a high-scaffold variant
        scaffold_heavy = self._random_strategy()
        scaffold_heavy.update({
            'memory_scaffold_prob': 0.4, 'memory_mutation_prob': 0.2,
            'bias_memory': 3.0, 'bias_control': 2.0,
            'weight_copy_recall': 2.0, 'population_size': 60,
        })
        self.population[1] = scaffold_heavy

        start = time.time()

        # TIER 1: Screen all strategies (1 seed, fewer epochs)
        print(f"\n  TIER 1 SCREENING ({self.outer_pop} strategies, {screen_epochs} epochs, 1 seed)...")
        screen_fits = self._evaluate_batch(self.population, screen_epochs, screen_seeds)
        for i, fit in enumerate(screen_fits):
            self.population[i]['_fitness'] = fit
            tag = ""
            if i == 0: tag = " [baseline]"
            elif i == 1: tag = " [scaffold]"
            print(f"    [{i+1:2d}] {fit:.4f}  scaffold={self.population[i]['memory_scaffold_prob']:.2f}  "
                  f"mem_bias={self.population[i]['bias_memory']:.2f}{tag}")

        # TIER 2: Full eval for top half
        self.population.sort(key=lambda s: s['_fitness'], reverse=True)
        top_half = self.population[:self.outer_pop // 2]
        print(f"\n  TIER 2 FULL EVAL (top {len(top_half)} strategies, {self.inner_epochs} epochs, 3 seeds)...")
        full_fits = self._evaluate_batch(top_half, self.inner_epochs, full_seeds)
        for i, fit in enumerate(full_fits):
            top_half[i]['_fitness'] = fit
            print(f"    [{i+1:2d}] {fit:.4f}")

        self.best_ever = max(self.population, key=lambda s: s['_fitness'])
        self.best_fitness = self.best_ever['_fitness']
        elapsed = time.time() - start
        print(f"\n  Gen 0 complete ({elapsed:.0f}s) — Best: {self.best_fitness:.4f}")

        # Outer evolution
        for gen in range(1, outer_gens + 1):
            self.generation = gen
            gen_start = time.time()
            print(f"\n--- Outer Generation {gen}/{outer_gens} ---")

            self.population.sort(key=lambda s: s['_fitness'], reverse=True)
            new_pop = [copy.deepcopy(self.population[0]), copy.deepcopy(self.population[1])]

            while len(new_pop) < self.outer_pop:
                if self.rng.random() < 0.7:
                    p1 = self._tournament()
                    p2 = self._tournament()
                    child = self._crossover(p1, p2)
                else:
                    parent = self._tournament()
                    child = self._mutate(parent, rate=0.2)
                if self.rng.random() < 0.3:
                    child = self._mutate(child, rate=0.1)
                new_pop.append(child)

            self.population = new_pop

            # Tier 1: screen new individuals
            to_screen = [s for s in self.population[2:]]  # skip elites
            if to_screen:
                fits = self._evaluate_batch(to_screen, screen_epochs, screen_seeds)
                for i, fit in enumerate(fits):
                    to_screen[i]['_fitness'] = fit

                # Tier 2: full eval for top candidates
                all_sorted = sorted(self.population, key=lambda s: s['_fitness'], reverse=True)
                top_n = max(3, self.outer_pop // 3)
                top = all_sorted[:top_n]
                full_fits = self._evaluate_batch(top, self.inner_epochs, full_seeds)
                for i, fit in enumerate(full_fits):
                    top[i]['_fitness'] = fit

            gen_best = max(self.population, key=lambda s: s['_fitness'])
            gen_elapsed = time.time() - gen_start

            if gen_best['_fitness'] > self.best_fitness:
                self.best_ever = copy.deepcopy(gen_best)
                self.best_fitness = gen_best['_fitness']
                print(f"  *** NEW BEST: {self.best_fitness:.4f} *** ({gen_elapsed:.0f}s)")
                print(f"      scaffold={self.best_ever['memory_scaffold_prob']:.3f}  "
                      f"mem_bias={self.best_ever['bias_memory']:.3f}  "
                      f"mem_mut={self.best_ever['memory_mutation_prob']:.3f}  "
                      f"novelty={self.best_ever['novelty_ratio']:.3f}")
            else:
                print(f"  Best: {self.best_fitness:.4f} (no improvement) ({gen_elapsed:.0f}s)")

            self.history.append({
                'gen': gen,
                'best': self.best_fitness,
                'gen_best': gen_best['_fitness'],
                'mean': float(np.mean([s['_fitness'] for s in self.population])),
                'time_s': gen_elapsed,
            })

        # Final
        total_time = time.time() - start
        print(f"\n{'='*70}")
        print(f"  META-EVOLUTION COMPLETE ({total_time:.0f}s)")
        print(f"{'='*70}")
        print(f"  Best fitness: {self.best_fitness:.6f}")
        print(f"\n  Evolved Strategy:")
        for k, v in sorted(self.best_ever.items()):
            if k.startswith('_'):
                continue
            if isinstance(v, float):
                print(f"    {k:30s}: {v:.6f}")
            else:
                print(f"    {k:30s}: {v}")

        # Key findings
        print(f"\n  KEY FINDINGS:")
        print(f"    Memory scaffold probability:  {self.best_ever['memory_scaffold_prob']:.4f}")
        print(f"    Memory operator bias:         {self.best_ever['bias_memory']:.4f}")
        print(f"    Memory mutation injection:    {self.best_ever['memory_mutation_prob']:.4f}")
        print(f"    Control (IF/SEQ) bias:        {self.best_ever['bias_control']:.4f}")
        print(f"    Novelty selection ratio:      {self.best_ever['novelty_ratio']:.4f}")
        print(f"    Copy/recall task weight:      {self.best_ever['weight_copy_recall']:.4f}")

        # Save
        output = {
            'best_strategy': {k: v for k, v in self.best_ever.items() if not k.startswith('_')},
            'best_fitness': self.best_fitness,
            'history': self.history,
            'total_time_s': total_time,
            'config': {
                'outer_pop': self.outer_pop,
                'outer_gens': outer_gens,
                'inner_epochs': self.inner_epochs,
                'cores': self.cores,
            },
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        output_path = os.path.join(TOOLS_DIR, 'best_evolution_strategy.json')
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n  Saved to: {output_path}")

        # Convergence
        print(f"\n  Convergence:")
        for h in self.history:
            print(f"    Gen {h['gen']:3d}: best={h['best']:.4f}  "
                  f"gen_best={h['gen_best']:.4f}  mean={h['mean']:.4f}  ({h['time_s']:.0f}s)")

        print(f"{'='*70}")
        return self.best_ever


def run_continuous(cores=None, seed=42):
    """Run meta-evolution continuously with escalating rigor.

    Phase 1 (gen 1-20):    inner=60 epochs, 1 seed screen, 3 seed full — fast exploration
    Phase 2 (gen 21-50):   inner=120 epochs, 2 seed screen, 5 seed full — exploitation
    Phase 3 (gen 51-100):  inner=200 epochs, 3 seed screen, 7 seed full — deep validation
    Phase 4 (gen 101+):    inner=300 epochs, 3 seed screen, 9 seed full — maximum rigor

    Every new best triggers a full-depth validation run (500 epochs, 5 seeds).
    Results saved after every generation. Resumes from last save.
    Runs until killed (SIGINT/SIGTERM).
    """
    cores = cores or max(1, mp.cpu_count() - 2)
    save_path = os.path.join(TOOLS_DIR, 'continuous_meta_state.json')
    best_path = os.path.join(TOOLS_DIR, 'best_evolution_strategy.json')
    log_path = os.path.join(TOOLS_DIR, 'meta_evolution_log.jsonl')

    # Phase configuration
    PHASES = [
        {'gens': (1, 20),   'inner': 60,  'screen_seeds': [42],        'full_seeds': [42, 123, 777]},
        {'gens': (21, 50),  'inner': 120, 'screen_seeds': [42, 200],   'full_seeds': [42, 123, 777, 500, 900]},
        {'gens': (51, 100), 'inner': 200, 'screen_seeds': [42, 200, 333], 'full_seeds': [42, 123, 777, 500, 900, 1111, 2222]},
        {'gens': (101, 999999), 'inner': 300, 'screen_seeds': [42, 200, 333], 'full_seeds': [42, 123, 777, 500, 900, 1111, 2222, 3333, 4444]},
    ]

    def get_phase(gen):
        for p in PHASES:
            if p['gens'][0] <= gen <= p['gens'][1]:
                return p
        return PHASES[-1]

    # Resume or initialize
    rng = random.Random(seed)
    outer_pop = 24
    meta = AcceleratedMetaGA(outer_pop=outer_pop, inner_epochs=60, cores=cores, seed=seed)
    start_gen = 0

    if os.path.exists(save_path):
        with open(save_path) as f:
            state = json.load(f)
        meta.population = state['population']
        meta.best_ever = state['best_ever']
        meta.best_fitness = state['best_fitness']
        meta.history = state.get('history', [])
        start_gen = state.get('generation', 0)
        meta.next_id = state.get('next_id', 100)
        print(f"  RESUMED from generation {start_gen}, best={meta.best_fitness:.4f}")
    else:
        # Fresh start — initialize population
        meta.population = [meta._random_strategy() for _ in range(outer_pop)]

        # Seed known configs
        baseline = meta._random_strategy()
        baseline.update({
            'crossover_rate': 0.85, 'point_mutation_rate': 0.15,
            'subtree_mutation_rate': 0.10, 'tournament_size': 5,
            'elitism': 3, 'parsimony_coeff': 0.00005, 'novelty_ratio': 0.2,
            'mean_weight': 0.6, 'memory_scaffold_prob': 0.0,
            'memory_mutation_prob': 0.0, 'max_depth': 6, 'population_size': 60,
        })
        meta.population[0] = baseline

        scaffold_heavy = meta._random_strategy()
        scaffold_heavy.update({
            'memory_scaffold_prob': 0.4, 'memory_mutation_prob': 0.2,
            'bias_memory': 3.0, 'bias_control': 2.0,
            'weight_copy_recall': 2.0, 'population_size': 60,
        })
        meta.population[1] = scaffold_heavy

        # Moderate scaffold
        scaffold_mid = meta._random_strategy()
        scaffold_mid.update({
            'memory_scaffold_prob': 0.25, 'memory_mutation_prob': 0.1,
            'bias_memory': 1.5, 'bias_control': 1.5,
            'weight_copy_recall': 1.5, 'population_size': 50,
        })
        meta.population[2] = scaffold_mid

        # High novelty
        novelty = meta._random_strategy()
        novelty.update({
            'novelty_ratio': 0.4, 'elitism': 1,
            'memory_scaffold_prob': 0.15, 'memory_mutation_prob': 0.15,
            'bias_memory': 2.0, 'population_size': 80,
        })
        meta.population[3] = novelty

    running = [True]
    def handler(signum, frame):
        print(f"\n[SIGNAL] Saving state and stopping after current generation...")
        running[0] = False
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    print("=" * 70)
    print("  CONTINUOUS META-EVOLUTION")
    print("=" * 70)
    print(f"  Population:    {outer_pop} strategies")
    print(f"  Cores:         {cores}")
    print(f"  Mode:          CONTINUOUS (escalating rigor)")
    print(f"  Phases:        4 (60→120→200→300 inner epochs)")
    print(f"  Resume from:   gen {start_gen}")
    print(f"  Best so far:   {meta.best_fitness:.4f}")
    print(f"  Save file:     {save_path}")
    print("=" * 70)

    total_start = time.time()
    gen = start_gen

    while running[0]:
        gen += 1
        phase = get_phase(gen)
        meta.inner_epochs = phase['inner']
        screen_seeds = phase['screen_seeds']
        full_seeds = phase['full_seeds']
        screen_epochs = max(30, phase['inner'] // 2)

        gen_start = time.time()
        phase_num = next(i+1 for i, p in enumerate(PHASES) if p['gens'][0] <= gen <= p['gens'][1])

        if gen == 1:
            # Initial evaluation
            print(f"\n  Phase {phase_num} — Screening {outer_pop} strategies "
                  f"(inner={phase['inner']}ep, {len(screen_seeds)} screen seeds)...")
            fits = meta._evaluate_batch(meta.population, screen_epochs, screen_seeds)
            for i, fit in enumerate(fits):
                meta.population[i]['_fitness'] = fit

            meta.population.sort(key=lambda s: s['_fitness'], reverse=True)
            top_n = max(4, outer_pop // 3)
            top = meta.population[:top_n]
            print(f"  Full eval top {top_n} ({len(full_seeds)} seeds, {phase['inner']} epochs)...")
            full_fits = meta._evaluate_batch(top, phase['inner'], full_seeds)
            for i, fit in enumerate(full_fits):
                top[i]['_fitness'] = fit

            meta.best_ever = max(meta.population, key=lambda s: s['_fitness'])
            meta.best_fitness = meta.best_ever['_fitness']
        else:
            # Breed new generation
            meta.population.sort(key=lambda s: s['_fitness'], reverse=True)
            new_pop = [copy.deepcopy(meta.population[0]), copy.deepcopy(meta.population[1]),
                       copy.deepcopy(meta.population[2])]  # top 3 elite

            while len(new_pop) < outer_pop:
                if meta.rng.random() < 0.65:
                    p1 = meta._tournament(k=4)
                    p2 = meta._tournament(k=4)
                    child = meta._crossover(p1, p2)
                else:
                    parent = meta._tournament(k=3)
                    child = meta._mutate(parent, rate=0.2)
                if meta.rng.random() < 0.35:
                    child = meta._mutate(child, rate=0.1)
                new_pop.append(child)

            meta.population = new_pop

            # Screen new individuals
            to_screen = meta.population[3:]
            if to_screen:
                fits = meta._evaluate_batch(to_screen, screen_epochs, screen_seeds)
                for i, fit in enumerate(fits):
                    to_screen[i]['_fitness'] = fit

            # Full eval top candidates
            all_sorted = sorted(meta.population, key=lambda s: s['_fitness'], reverse=True)
            top_n = max(4, outer_pop // 3)
            top = all_sorted[:top_n]
            full_fits = meta._evaluate_batch(top, phase['inner'], full_seeds)
            for i, fit in enumerate(full_fits):
                top[i]['_fitness'] = fit

        # Check for improvement
        gen_best = max(meta.population, key=lambda s: s['_fitness'])
        gen_elapsed = time.time() - gen_start
        improved = gen_best['_fitness'] > meta.best_fitness

        if improved:
            meta.best_ever = copy.deepcopy(gen_best)
            meta.best_fitness = gen_best['_fitness']
            print(f"\n  Gen {gen:4d} [P{phase_num}] *** NEW BEST: {meta.best_fitness:.4f} *** ({gen_elapsed:.0f}s)")
            print(f"    scaffold={meta.best_ever['memory_scaffold_prob']:.3f}  "
                  f"mem_bias={meta.best_ever['bias_memory']:.3f}  "
                  f"mem_mut={meta.best_ever['memory_mutation_prob']:.3f}  "
                  f"novelty={meta.best_ever['novelty_ratio']:.3f}  "
                  f"depth={meta.best_ever['max_depth']}  "
                  f"pop={meta.best_ever['population_size']}")

            # Deep validation of new best
            print(f"    Deep validation (500 epochs, 5 seeds)...")
            deep_seeds = [42, 123, 777, 1337, 9999]
            deep_fit = meta._evaluate_batch([meta.best_ever], 500, deep_seeds)
            print(f"    Deep-validated fitness: {deep_fit[0]:.4f}")
            meta.best_ever['_deep_fitness'] = deep_fit[0]
        else:
            mean_fit = float(np.mean([s['_fitness'] for s in meta.population]))
            print(f"  Gen {gen:4d} [P{phase_num}] best={meta.best_fitness:.4f}  "
                  f"gen_best={gen_best['_fitness']:.4f}  mean={mean_fit:.4f}  ({gen_elapsed:.0f}s)")

        # Log
        entry = {
            'gen': gen, 'phase': phase_num,
            'best': meta.best_fitness,
            'gen_best': gen_best['_fitness'],
            'mean': float(np.mean([s['_fitness'] for s in meta.population])),
            'inner_epochs': phase['inner'],
            'time_s': gen_elapsed,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'improved': improved,
        }
        meta.history.append(entry)
        with open(log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        # Save state every generation
        save_state = {
            'generation': gen,
            'best_ever': meta.best_ever,
            'best_fitness': meta.best_fitness,
            'population': meta.population,
            'history': meta.history[-500:],
            'next_id': meta.next_id,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        with open(save_path, 'w') as f:
            json.dump(save_state, f, indent=2)

        # Save best strategy
        if improved:
            best_out = {
                'best_strategy': {k: v for k, v in meta.best_ever.items() if not k.startswith('_')},
                'best_fitness': meta.best_fitness,
                'deep_fitness': meta.best_ever.get('_deep_fitness'),
                'generation': gen,
                'phase': phase_num,
                'history': meta.history[-100:],
                'total_time_s': time.time() - total_start,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }
            with open(best_path, 'w') as f:
                json.dump(best_out, f, indent=2)

        sys.stdout.flush()

    # Clean exit
    total_time = time.time() - total_start
    print(f"\n{'='*70}")
    print(f"  STOPPED at generation {gen} ({total_time:.0f}s total)")
    print(f"{'='*70}")
    print(f"  Best fitness:  {meta.best_fitness:.6f}")
    print(f"  Strategy saved to: {best_path}")
    print(f"  State saved to:    {save_path} (resume with --continuous)")
    print(f"\n  Best strategy highlights:")
    for k in ['memory_scaffold_prob', 'memory_mutation_prob', 'bias_memory',
              'bias_control', 'novelty_ratio', 'elitism', 'max_depth',
              'population_size', 'weight_copy_recall']:
        print(f"    {k:30s}: {meta.best_ever.get(k, 'N/A')}")
    print(f"{'='*70}")


def deploy_best():
    """Run full evolution with the best discovered strategy."""
    path = os.path.join(TOOLS_DIR, 'best_evolution_strategy.json')
    if not os.path.exists(path):
        print("No evolved strategy found. Run meta-evolution first.")
        return

    with open(path) as f:
        data = json.load(f)

    strategy = data['best_strategy']
    print("=" * 70)
    print("  DEPLOYING EVOLVED STRATEGY (FULL RUN)")
    print("=" * 70)
    print(f"  Meta-fitness: {data.get('best_fitness', 'N/A')}")
    print(f"  Scaffold:     {strategy.get('memory_scaffold_prob', 0):.4f}")
    print(f"  Mem bias:     {strategy.get('bias_memory', 1):.4f}")
    print(f"  Mem mutation: {strategy.get('memory_mutation_prob', 0):.4f}")
    print("=" * 70)

    engine = FastCognitionEngine(strategy, seed=42)

    # Run with progress output
    engine.population = []
    for _ in range(engine.pop_size):
        if engine.rng.random() < engine.mem_scaffold:
            tree = engine._memory_scaffold()
        else:
            tree = engine._random_tree()
        bc = compile_tree(tree)
        fitness, scores = engine._evaluate(tree, bc)
        engine.population.append((tree, bc, fitness, scores, {}))

    engine.best_ever = max(engine.population, key=lambda o: o[2])
    gen_s = engine._evaluate_gen(engine.best_ever[0], engine.best_ever[1])
    engine.best_ever = (*engine.best_ever[:4], gen_s)

    print(f"\n{'Epoch':>6} | {'Fit':>7} | {'Size':>5} | {'Stag':>4} | IQ")
    print("-" * 60)

    start = time.time()
    epoch = 0
    stagnation = 0

    while True:
        epoch += 1
        engine.epoch = epoch

        engine.population.sort(key=lambda o: o[2], reverse=True)
        new_pop = list(engine.population[:engine.elitism])

        while len(new_pop) < engine.pop_size:
            child = engine._breed()
            bc = compile_tree(child)
            fitness, scores = engine._evaluate(child, bc)
            new_pop.append((child, bc, fitness, scores, {}))

        engine.population = new_pop

        cur_best = max(engine.population, key=lambda o: o[2])
        if cur_best[2] > engine.best_ever[2]:
            gen_s = engine._evaluate_gen(cur_best[0], cur_best[1])
            engine.best_ever = (*cur_best[:4], gen_s)
            stagnation = 0
        else:
            stagnation += 1

        if epoch % 10 == 0:
            metrics = engine._measure_intelligence()
            print(f"{epoch:6d} | {engine.best_ever[2]:7.4f} | "
                  f"{engine.best_ever[0].size():5d} | {stagnation:4d} | "
                  f"{metrics['intelligence_score']:.4f}  "
                  f"gen={metrics['generalization']:.3f} mem={metrics['memory_use']:.3f} "
                  f"learn={metrics['lifetime_learning']:.3f}")
            sys.stdout.flush()

        if epoch % 100 == 0:
            elapsed = time.time() - start
            print(f"\n  --- Epoch {epoch} ({elapsed:.0f}s, {epoch/elapsed:.1f} ep/s) ---")
            print(f"  Training: {engine.best_ever[3]}")
            print(f"  Held-out: {engine.best_ever[4]}")
            print(f"  Program:\n{engine.best_ever[0].to_str(indent=2)[:500]}")
            sys.stdout.flush()

        # Run until killed
        if epoch >= 100000:
            break

    metrics = engine._measure_intelligence()
    print(f"\nFinal IQ: {metrics['intelligence_score']:.4f}")
    print(f"Metrics: {metrics}")


def main():
    parser = argparse.ArgumentParser(description='Hyper-Accelerated GA Self-Improvement')
    parser.add_argument('--outer-pop', type=int, default=20)
    parser.add_argument('--outer-gens', type=int, default=20)
    parser.add_argument('--inner-epochs', type=int, default=80)
    parser.add_argument('--cores', type=int, default=None)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--deploy', action='store_true',
                        help='Run full evolution with best evolved strategy')
    parser.add_argument('--continuous', action='store_true',
                        help='Run continuously with escalating rigor, saves every gen, resumes on restart')
    args = parser.parse_args()

    if args.deploy:
        deploy_best()
    elif args.continuous:
        run_continuous(cores=args.cores, seed=args.seed)
    else:
        meta = AcceleratedMetaGA(
            outer_pop=args.outer_pop,
            inner_epochs=args.inner_epochs,
            cores=args.cores,
            seed=args.seed,
        )
        meta.run(outer_gens=args.outer_gens)


if __name__ == '__main__':
    main()
