#!/usr/bin/env python3
"""Experiment 2: Meta-GA for Hyperparameter Evolution

An outer GA evolves a chromosome of 12 hyperparameters that control the
inner GP engine (from ga_self_aware.py). Each meta-individual runs a SHORT
inner evolution (default 5 rounds, 1 island) and is scored by the best
fitness achieved. The outer GA uses standard tournament selection.

Hypothesis: hand-tuned defaults may be suboptimal. Meta-evolution can find
configurations that reach higher fitness in fewer rounds.

COMPLETELY SELF-CONTAINED. Does not import from ga_self_aware.py or
ga_engine.py. Designed to run on remote node (cabin-laptop-01, 8 cores).

Usage:
    python3 ga_exp2_meta_ga.py
    python3 ga_exp2_meta_ga.py --cores 3
    python3 ga_exp2_meta_ga.py --outer-pop 10 --outer-gens 20 --inner-rounds 5
"""

import argparse
import copy
import json
import math
import os
import random
import signal
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import numpy as np

from ga_sequence_data import REAL_DATA_TASKS, prefetch_sequences
from ga_result_reporter import report_generation


# ============================================================================
# OP SET -- all 32 ops from ga_self_aware.py (28 base + 4 self-referential)
# ============================================================================

class Op(Enum):
    # Arithmetic (2 args)
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()

    # Comparison (2 args -> 0 or 1)
    GT = auto()
    LT = auto()
    EQ = auto()
    NEQ = auto()

    # Logic (2 args, NOT is 1)
    AND = auto()
    OR = auto()
    NOT = auto()

    # Control
    IF = auto()       # 3 args: if arg0 > 0 then arg1 else arg2
    SEQ = auto()      # 2 args: execute both, return arg1

    # Memory
    READ = auto()     # 1 arg: read register[int(arg0) % N]
    WRITE = auto()    # 2 args: write arg1 to register[int(arg0) % N]

    # Input/Output
    SENSE = auto()    # 1 arg: read input channel
    ACT = auto()      # 2 args: write arg1 to output channel arg0

    # Constants
    CONST = auto()    # literal float
    ZERO = auto()
    ONE = auto()
    NEG1 = auto()

    # Accumulation
    INC = auto()      # arg0 + 1
    DEC = auto()      # arg0 - 1
    ABS = auto()      # |arg0|
    SIGN = auto()     # sign(arg0)
    MAX2 = auto()     # max(arg0, arg1)
    MIN2 = auto()     # min(arg0, arg1)

    # Self-referential (v3)
    STEP = auto()      # 0 args: returns step_number / 10.0
    LAST_OUT = auto()  # 1 arg: returns last output on channel arg0
    PREDICT = auto()   # 2 args: prediction_reg[arg0] = arg1, returns arg1
    SURPRISE = auto()  # 1 arg: |prediction[arg0] - input[arg0]|
    # === LIFETIME LEARNING OPS (v4) ===
    LEARN = auto()      # 3 args: if arg0>0, learn_regs[arg1%8]=arg2; returns arg2
    RECALL = auto()     # 1 arg: returns learn_regs[arg0%8]
    STRENGTHEN = auto() # 1 arg: boost hebbian weight of parent node; returns weight
    WEAKEN = auto()     # 1 arg: reduce hebbian weight of parent node; returns weight
    DEFINE = auto()     # 2 args: store child[1] subtree at closures[arg0%4]; returns 1
    INVOKE = auto()     # 2 args: execute closure[arg0%4] with arg1 as input; returns result


ARITY = {
    Op.ADD: 2, Op.SUB: 2, Op.MUL: 2, Op.DIV: 2, Op.MOD: 2,
    Op.GT: 2, Op.LT: 2, Op.EQ: 2, Op.NEQ: 2,
    Op.AND: 2, Op.OR: 2, Op.NOT: 1,
    Op.IF: 3, Op.SEQ: 2,
    Op.READ: 1, Op.WRITE: 2,
    Op.SENSE: 1, Op.ACT: 2,
    Op.CONST: 0, Op.ZERO: 0, Op.ONE: 0, Op.NEG1: 0,
    Op.INC: 1, Op.DEC: 1, Op.ABS: 1, Op.SIGN: 1,
    Op.MAX2: 2, Op.MIN2: 2,
    Op.STEP: 0, Op.LAST_OUT: 1, Op.PREDICT: 2, Op.SURPRISE: 1,
    # Lifetime learning
    Op.LEARN: 3, Op.RECALL: 1, Op.STRENGTHEN: 1, Op.WEAKEN: 1,
    Op.DEFINE: 2, Op.INVOKE: 2,
}

TERMINAL_OPS = [op for op, a in ARITY.items() if a == 0]
UNARY_OPS = [op for op, a in ARITY.items() if a == 1]
BINARY_OPS = [op for op, a in ARITY.items() if a == 2]
TERNARY_OPS = [op for op, a in ARITY.items() if a == 3]

MEMORY_OPS = {Op.READ, Op.WRITE}
SELF_REF_OPS = {Op.STEP, Op.LAST_OUT, Op.PREDICT, Op.SURPRISE}


# ============================================================================
# PROGRAM TREE
# ============================================================================

@dataclass
class Node:
    op: Op
    children: List['Node'] = field(default_factory=list)
    value: float = 0.0

    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(c.depth() for c in self.children)

    def size(self) -> int:
        return 1 + sum(c.size() for c in self.children)

    def copy(self) -> 'Node':
        return Node(
            op=self.op,
            children=[c.copy() for c in self.children],
            value=self.value,
        )


# ============================================================================
# SELF-AWARE EXECUTION CONTEXT
# ============================================================================

class SelfAwareContext:
    MAX_STEPS = 500
    NUM_REGISTERS = 16
    NUM_INPUT_CHANNELS = 8
    NUM_OUTPUT_CHANNELS = 4
    NUM_PREDICTIONS = 8
    NUM_LEARN_REGS = 8
    NUM_CLOSURES = 4

    def __init__(self):
        self.registers = [0.0] * self.NUM_REGISTERS
        self.inputs = [0.0] * self.NUM_INPUT_CHANNELS
        self.outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.predictions = [0.0] * self.NUM_PREDICTIONS
        self.last_outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.steps = 0
        self.step_number = 0
        self.halted = False
        # Lifetime learning state (v4)
        self.learn_regs = [0.0] * self.NUM_LEARN_REGS
        self.hebbian_weights = {}
        self.closures = [None] * self.NUM_CLOSURES
        self.invoke_depth = 0

    def advance_step(self):
        self.last_outputs = self.outputs.copy()
        self.step_number += 1
        self.steps = 0
        self.outputs = [0.0] * self.NUM_OUTPUT_CHANNELS

    def reset_for_trial(self):
        self.registers = [0.0] * self.NUM_REGISTERS
        self.inputs = [0.0] * self.NUM_INPUT_CHANNELS
        self.outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.predictions = [0.0] * self.NUM_PREDICTIONS
        self.last_outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.steps = 0
        self.step_number = 0
        self.halted = False


# ============================================================================
# EXECUTE -- handles all 32 ops
# ============================================================================

def execute(node: Node, ctx: SelfAwareContext) -> float:
    if ctx.steps >= ctx.MAX_STEPS or ctx.halted:
        return 0.0
    ctx.steps += 1

    op = node.op

    # Terminals
    if op == Op.CONST:
        return node.value
    if op == Op.ZERO:
        return 0.0
    if op == Op.ONE:
        return 1.0
    if op == Op.NEG1:
        return -1.0
    if op == Op.STEP:
        return ctx.step_number / 10.0

    # Evaluate children
    args = [execute(c, ctx) for c in node.children]

    def clamp(v):
        return max(-1e6, min(1e6, v))

    # Arithmetic
    if op == Op.ADD:
        return clamp(args[0] + args[1])
    if op == Op.SUB:
        return clamp(args[0] - args[1])
    if op == Op.MUL:
        return clamp(args[0] * args[1])
    if op == Op.DIV:
        return clamp(args[0] / args[1]) if abs(args[1]) > 1e-10 else 0.0
    if op == Op.MOD:
        return clamp(args[0] % args[1]) if abs(args[1]) > 1e-10 else 0.0

    # Comparison
    if op == Op.GT:
        return 1.0 if args[0] > args[1] else 0.0
    if op == Op.LT:
        return 1.0 if args[0] < args[1] else 0.0
    if op == Op.EQ:
        return 1.0 if abs(args[0] - args[1]) < 0.1 else 0.0
    if op == Op.NEQ:
        return 1.0 if abs(args[0] - args[1]) >= 0.1 else 0.0

    # Logic
    if op == Op.AND:
        return 1.0 if args[0] > 0 and args[1] > 0 else 0.0
    if op == Op.OR:
        return 1.0 if args[0] > 0 or args[1] > 0 else 0.0
    if op == Op.NOT:
        return 0.0 if args[0] > 0 else 1.0

    # Control
    if op == Op.IF:
        return args[1] if args[0] > 0 else args[2]
    if op == Op.SEQ:
        return args[1]

    # Memory
    if op == Op.READ:
        idx = int(args[0]) % ctx.NUM_REGISTERS
        return ctx.registers[idx]
    if op == Op.WRITE:
        idx = int(args[0]) % ctx.NUM_REGISTERS
        ctx.registers[idx] = clamp(args[1])
        return args[1]

    # I/O
    if op == Op.SENSE:
        idx = int(args[0]) % ctx.NUM_INPUT_CHANNELS
        return ctx.inputs[idx]
    if op == Op.ACT:
        idx = int(args[0]) % ctx.NUM_OUTPUT_CHANNELS
        ctx.outputs[idx] = clamp(args[1])
        return args[1]

    # Accumulation
    if op == Op.INC:
        return clamp(args[0] + 1)
    if op == Op.DEC:
        return clamp(args[0] - 1)
    if op == Op.ABS:
        return abs(args[0])
    if op == Op.SIGN:
        return 1.0 if args[0] > 0 else (-1.0 if args[0] < 0 else 0.0)
    if op == Op.MAX2:
        return max(args[0], args[1])
    if op == Op.MIN2:
        return min(args[0], args[1])

    # Self-referential
    if op == Op.LAST_OUT:
        idx = int(args[0]) % ctx.NUM_OUTPUT_CHANNELS
        return ctx.last_outputs[idx]
    if op == Op.PREDICT:
        idx = int(args[0]) % ctx.NUM_PREDICTIONS
        ctx.predictions[idx] = clamp(args[1])
        return args[1]
    if op == Op.SURPRISE:
        idx = int(args[0]) % ctx.NUM_PREDICTIONS
        input_idx = idx % ctx.NUM_INPUT_CHANNELS
        return abs(ctx.predictions[idx] - ctx.inputs[input_idx])

    # === LIFETIME LEARNING ===
    if op == Op.LEARN:
        if args[0] > 0:
            idx = int(args[1]) % ctx.NUM_LEARN_REGS
            ctx.learn_regs[idx] = clamp(args[2])
        return args[2] if len(args) > 2 else 0.0
    if op == Op.RECALL:
        idx = int(args[0]) % ctx.NUM_LEARN_REGS
        return ctx.learn_regs[idx]
    if op == Op.STRENGTHEN:
        nid = id(node)
        w = ctx.hebbian_weights.get(nid, 1.0)
        w += math.tanh(args[0]) * 0.1
        w = max(0.1, min(3.0, w))
        ctx.hebbian_weights[nid] = w
        return w
    if op == Op.WEAKEN:
        nid = id(node)
        w = ctx.hebbian_weights.get(nid, 1.0)
        w -= math.tanh(args[0]) * 0.1
        w = max(0.1, min(3.0, w))
        ctx.hebbian_weights[nid] = w
        return w
    if op == Op.DEFINE:
        idx = int(args[0]) % ctx.NUM_CLOSURES
        if len(node.children) > 1:
            ctx.closures[idx] = node.children[1]
        return 1.0
    if op == Op.INVOKE:
        idx = int(args[0]) % ctx.NUM_CLOSURES
        body = ctx.closures[idx]
        if body is None or ctx.invoke_depth >= 3:
            return 0.0
        ctx.invoke_depth += 1
        saved_input = ctx.inputs[0]
        ctx.inputs[0] = clamp(args[1])
        result = execute(body, ctx)
        ctx.inputs[0] = saved_input
        ctx.invoke_depth -= 1
        return result

    return 0.0


# ============================================================================
# TREE UTILITIES
# ============================================================================

def random_tree(rng: random.Random, max_depth: int = 5,
                self_aware_bias: float = 0.15) -> Node:
    if max_depth <= 1:
        if rng.random() < self_aware_bias and rng.random() < 0.5:
            return Node(op=Op.STEP)
        op = rng.choice(TERMINAL_OPS)
        if op == Op.CONST:
            return Node(op=op, value=rng.uniform(-5, 5))
        return Node(op=op)

    if rng.random() < self_aware_bias:
        sa_ops = [Op.LAST_OUT, Op.PREDICT, Op.SURPRISE, Op.STEP,
                  Op.LEARN, Op.RECALL, Op.STRENGTHEN, Op.WEAKEN,
                  Op.DEFINE, Op.INVOKE]
        op = rng.choice(sa_ops)
    elif rng.random() < 0.3:
        op = rng.choice(TERMINAL_OPS)
    elif rng.random() < 0.4:
        op = rng.choice(UNARY_OPS)
    elif rng.random() < 0.7:
        op = rng.choice(BINARY_OPS)
    else:
        op = rng.choice(TERNARY_OPS)

    arity = ARITY[op]
    if arity == 0:
        if op == Op.CONST:
            return Node(op=op, value=rng.uniform(-5, 5))
        return Node(op=op)

    children = [random_tree(rng, max_depth - 1, self_aware_bias)
                for _ in range(arity)]
    return Node(op=op, children=children)


def get_all_nodes(node: Node, parent=None, idx=0) -> List:
    result = [(node, parent, idx)]
    for i, child in enumerate(node.children):
        result.extend(get_all_nodes(child, node, i))
    return result


def subtree_crossover(parent1: Node, parent2: Node,
                      rng: random.Random) -> Node:
    child = parent1.copy()
    nodes1 = get_all_nodes(child)
    nodes2 = get_all_nodes(parent2)
    if len(nodes1) > 1 and len(nodes2) > 1:
        _, p, i = rng.choice(nodes1[1:])
        donor, _, _ = rng.choice(nodes2[1:])
        if p is not None:
            p.children[i] = donor.copy()
    return child


def point_mutation(tree: Node, rng: random.Random,
                   rate: float = 0.15) -> Node:
    child = tree.copy()
    nodes = get_all_nodes(child)
    for node, _, _ in nodes:
        if rng.random() < rate:
            arity = ARITY[node.op]
            candidates = [op for op, a in ARITY.items() if a == arity]
            if candidates:
                node.op = rng.choice(candidates)
                if node.op == Op.CONST:
                    node.value = rng.uniform(-5, 5)
    return child


def subtree_mutation(tree: Node, rng: random.Random,
                     max_depth: int = 3,
                     self_aware_bias: float = 0.15) -> Node:
    child = tree.copy()
    nodes = get_all_nodes(child)
    if len(nodes) > 1:
        _, p, i = rng.choice(nodes[1:])
        if p is not None:
            new_sub = random_tree(rng, max_depth=max_depth,
                                  self_aware_bias=self_aware_bias)
            p.children[i] = new_sub
    return child


# ============================================================================
# ALL 9 TASKS (identical to ga_self_aware.py)
# ============================================================================

# --- Memory tasks (5) ---

class DelayedEchoTask:
    name = "delayed_echo"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            target = rng.uniform(-5, 5)
            delay = rng.randint(2, 6)
            noise = [rng.uniform(-5, 5) for _ in range(delay - 1)]
            trials.append({'target': target, 'delay': delay, 'noise': noise})
        return trials

    def evaluate(self, tree, trial):
        ctx = SelfAwareContext()
        target = trial['target']
        delay = trial['delay']
        noise = trial['noise']

        ctx.inputs = [target, 1.0, 0.0, float(delay), 0, 0, 0, 0]
        execute(tree, ctx)

        noise_outputs = []
        for i, n_val in enumerate(noise):
            ctx.advance_step()
            ctx.inputs = [n_val, 0.0, float(i + 1), float(delay), 0, 0, 0, 0]
            execute(tree, ctx)
            noise_outputs.append(ctx.outputs[0])

        ctx.advance_step()
        ctx.inputs = [0.0, -1.0, float(delay), float(delay), 0, 0, 0, 0]
        execute(tree, ctx)

        recalled = ctx.outputs[0]
        error = abs(recalled - target)

        if error < 0.5:
            recall_score = 1.0
        elif error < 1.0:
            recall_score = 0.5
        elif error < 2.0:
            recall_score = 0.2
        else:
            recall_score = 0.0

        if noise_outputs:
            stable_count = sum(1 for o in noise_outputs
                               if abs(o - target) < 1.0)
            stability = stable_count / len(noise_outputs)
            return 0.7 * recall_score + 0.3 * stability
        return recall_score


class SequentialXORTask:
    name = "sequential_xor"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            length = rng.randint(4, 8)
            sequence = [rng.choice([0.0, 1.0]) for _ in range(length)]
            expected = [sequence[0]]
            for i in range(1, length):
                xor = 1.0 if (sequence[i] > 0.5) != (sequence[i - 1] > 0.5) else 0.0
                expected.append(xor)
            trials.append({'sequence': sequence, 'expected': expected})
        return trials

    def evaluate(self, tree, trial):
        ctx = SelfAwareContext()
        correct = 0
        total = len(trial['sequence'])

        for i, val in enumerate(trial['sequence']):
            if i > 0:
                ctx.advance_step()
            ctx.inputs = [val, float(i), float(total), 0, 0, 0, 0, 0]
            execute(tree, ctx)

            predicted = 1.0 if ctx.outputs[0] > 0.5 else 0.0
            if abs(predicted - trial['expected'][i]) < 0.1:
                correct += 1

        return correct / total


class RunningMaxTask:
    name = "running_max"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            length = rng.randint(4, 8)
            values = [rng.uniform(-5, 5) for _ in range(length)]
            running_max = []
            cur_max = float('-inf')
            for v in values:
                cur_max = max(cur_max, v)
                running_max.append(cur_max)
            trials.append({'values': values, 'running_max': running_max})
        return trials

    def evaluate(self, tree, trial):
        ctx = SelfAwareContext()
        total_score = 0.0
        values = trial['values']
        expected = trial['running_max']

        for i, val in enumerate(values):
            if i > 0:
                ctx.advance_step()
            ctx.inputs = [val, float(i), float(len(values)), 0, 0, 0, 0, 0]
            execute(tree, ctx)

            error = abs(ctx.outputs[0] - expected[i])
            scale = max(abs(expected[i]), 1.0)
            total_score += max(0.0, 1.0 - error / scale)

        return total_score / len(values)


class AccumulatorTask:
    name = "accumulator"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            length = rng.randint(4, 8)
            threshold = rng.uniform(-2, 2)
            values = [rng.uniform(-5, 5) for _ in range(length)]
            counts = []
            c = 0
            for v in values:
                if v > threshold:
                    c += 1
                counts.append(float(c))
            trials.append({
                'values': values, 'threshold': threshold,
                'expected_counts': counts
            })
        return trials

    def evaluate(self, tree, trial):
        ctx = SelfAwareContext()
        total_score = 0.0
        values = trial['values']
        threshold = trial['threshold']
        expected = trial['expected_counts']

        for i, val in enumerate(values):
            if i > 0:
                ctx.advance_step()
            ctx.inputs = [val, threshold, float(i), float(len(values)),
                          0, 0, 0, 0]
            execute(tree, ctx)

            error = abs(ctx.outputs[0] - expected[i])
            if error < 0.5:
                total_score += 1.0
            elif error < 1.5:
                total_score += 0.3

        return total_score / len(values)


class StateSwitcherTask:
    name = "state_switcher"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            length = rng.randint(5, 10)
            signals, queries, states = [], [], []
            current_state = 1.0
            for _ in range(length):
                is_signal = rng.random() < 0.4
                is_query = rng.random() < 0.5
                sig = rng.choice([3.0, -3.0]) if is_signal else 0.0
                if is_signal:
                    current_state = 1.0 if sig > 0 else -1.0
                signals.append(sig)
                queries.append(1.0 if is_query else 0.0)
                states.append(current_state)
            trials.append({
                'signals': signals, 'queries': queries,
                'expected_states': states
            })
        return trials

    def evaluate(self, tree, trial):
        ctx = SelfAwareContext()
        correct = 0
        query_count = 0

        for i in range(len(trial['signals'])):
            if i > 0:
                ctx.advance_step()
            ctx.inputs = [trial['signals'][i], trial['queries'][i],
                          float(i), 0, 0, 0, 0, 0]
            execute(tree, ctx)

            if trial['queries'][i] > 0.5:
                query_count += 1
                if (ctx.outputs[0] > 0) == (trial['expected_states'][i] > 0):
                    correct += 1

        return correct / max(query_count, 1)


class PersistentNavigationTask:
    name = "persistent_nav"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            start = rng.uniform(-10, 10)
            goal = rng.uniform(-10, 10)
            while abs(goal - start) < 1:
                goal = rng.uniform(-10, 10)
            trials.append({'start': start, 'goal': goal})
        return trials

    def evaluate(self, tree, trial):
        ctx = SelfAwareContext()
        pos = trial['start']
        goal = trial['goal']
        best_dist = abs(pos - goal)

        for step in range(20):
            if step > 0:
                ctx.advance_step()
            ctx.inputs = [pos, goal, float(step), best_dist, 0, 0, 0, 0]
            execute(tree, ctx)

            move = max(-1, min(1, ctx.outputs[0]))
            pos += move
            dist = abs(pos - goal)
            best_dist = min(best_dist, dist)

            if dist < 0.5:
                return 1.0

        initial_dist = abs(trial['start'] - trial['goal'])
        return max(0.0, 1.0 - best_dist / max(initial_dist, 0.1))


# --- Self-referential tasks (3) ---

class SequencePredictionTask:
    name = "sequence_prediction"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            pattern_len = rng.randint(2, 4)
            pattern = [round(rng.uniform(-3, 3), 1) for _ in range(pattern_len)]
            n_cycles = rng.randint(2, 4)
            sequence = pattern * n_cycles
            expected = []
            for i in range(len(sequence)):
                next_idx = (i + 1) % len(sequence)
                expected.append(sequence[next_idx])
            trials.append({
                'sequence': sequence,
                'expected': expected,
                'pattern': pattern,
                'pattern_len': pattern_len,
            })
        return trials

    def evaluate(self, tree, trial):
        ctx = SelfAwareContext()
        sequence = trial['sequence']
        expected = trial['expected']
        total_score = 0.0
        score_start = trial['pattern_len']

        for i, val in enumerate(sequence):
            if i > 0:
                ctx.advance_step()
            ctx.inputs = [val, float(i), float(len(sequence)),
                          float(trial['pattern_len']), 0, 0, 0, 0]
            execute(tree, ctx)

            if i >= score_start:
                output = ctx.outputs[0]
                error = abs(output - expected[i])
                scale = max(abs(expected[i]), 1.0)
                step_score = max(0.0, 1.0 - error / scale)
                total_score += step_score

        scored_steps = len(sequence) - score_start
        return total_score / max(scored_steps, 1)


class ErrorCorrectionTask:
    name = "error_correction"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            target = rng.uniform(-5, 5)
            n_steps = rng.randint(5, 10)
            noise = [rng.uniform(-0.3, 0.3) for _ in range(n_steps)]
            trials.append({
                'target': target,
                'n_steps': n_steps,
                'noise': noise,
            })
        return trials

    def evaluate(self, tree, trial):
        ctx = SelfAwareContext()
        target = trial['target']
        n_steps = trial['n_steps']
        noise = trial['noise']

        ctx.inputs = [0.0, 0.0, float(n_steps), 0, 0, 0, 0, 0]
        execute(tree, ctx)
        last_output = ctx.outputs[0]
        initial_error = abs(target - last_output)

        total_score = 0.0
        for step in range(1, n_steps):
            ctx.advance_step()
            error_signal = (target - last_output) + noise[step]
            ctx.inputs = [error_signal, 1.0, float(n_steps),
                          float(step), abs(target - last_output), 0, 0, 0]
            execute(tree, ctx)
            last_output = ctx.outputs[0]

            step_error = abs(target - last_output)
            if initial_error > 0.1:
                step_score = max(0.0, 1.0 - step_error / initial_error)
            else:
                step_score = 1.0 if step_error < 0.5 else 0.0
            total_score += step_score

        return total_score / max(n_steps - 1, 1)


class NoveltyDetectionTask:
    name = "novelty_detection"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            if rng.random() < 0.5:
                base_val = round(rng.uniform(-3, 3), 1)
                pattern = [base_val]
            else:
                v1 = round(rng.uniform(-3, 3), 1)
                v2 = round(rng.uniform(-3, 3), 1)
                pattern = [v1, v2]

            n_total = rng.randint(8, 15)
            sequence = [pattern[i % len(pattern)] for i in range(n_total)]

            oddball_pos = rng.randint(len(pattern) + 1, n_total - 2)
            oddball_val = round(rng.uniform(-5, 5), 1)
            while abs(oddball_val - sequence[oddball_pos]) < 2.0:
                oddball_val = round(rng.uniform(-5, 5), 1)
            sequence[oddball_pos] = oddball_val

            expected = [0.0] * n_total
            expected[oddball_pos] = 1.0

            trials.append({
                'sequence': sequence,
                'expected': expected,
                'oddball_pos': oddball_pos,
                'pattern': pattern,
            })
        return trials

    def evaluate(self, tree, trial):
        ctx = SelfAwareContext()
        sequence = trial['sequence']
        expected = trial['expected']

        true_pos = 0
        false_pos = 0
        true_neg = 0
        false_neg = 0

        for i, val in enumerate(sequence):
            if i > 0:
                ctx.advance_step()
            ctx.inputs = [val, float(i), float(len(sequence)),
                          float(len(trial['pattern'])), 0, 0, 0, 0]
            execute(tree, ctx)

            detected = ctx.outputs[0] > 0.5
            is_oddball = expected[i] > 0.5

            if i < len(trial['pattern']):
                continue

            if detected and is_oddball:
                true_pos += 1
            elif detected and not is_oddball:
                false_pos += 1
            elif not detected and not is_oddball:
                true_neg += 1
            elif not detected and is_oddball:
                false_neg += 1

        sensitivity = true_pos / max(true_pos + false_neg, 1)
        specificity = true_neg / max(true_neg + false_pos, 1)

        if sensitivity + specificity == 0:
            return 0.0
        return 2 * sensitivity * specificity / (sensitivity + specificity)


# ============================================================================
# TASK REGISTRIES
# ============================================================================

MEMORY_TASKS = {
    'delayed_echo': DelayedEchoTask(),
    'sequential_xor': SequentialXORTask(),
    'running_max': RunningMaxTask(),
    'accumulator': AccumulatorTask(),
    'state_switcher': StateSwitcherTask(),
}

SELF_REF_TASKS = {
    'sequence_prediction': SequencePredictionTask(),
    'error_correction': ErrorCorrectionTask(),
    'novelty_detection': NoveltyDetectionTask(),
}

REASONING_TASKS = {
    'persistent_nav': PersistentNavigationTask(),
}

ALL_TASKS = {**MEMORY_TASKS, **SELF_REF_TASKS, **REASONING_TASKS, **REAL_DATA_TASKS}


# ============================================================================
# EVALUATION (with configurable weights)
# ============================================================================

def evaluate_organism(tree: Node, tasks: dict, n_trials: int = 8,
                      seed: int = 42) -> dict:
    scores = {}
    for name, task in tasks.items():
        rng = random.Random(seed)
        trials = task.generate_trials(n_trials, rng)
        trial_scores = [task.evaluate(tree, trial) for trial in trials]
        scores[name] = float(np.mean(trial_scores))
    return scores


def compute_fitness(scores: dict,
                    mem_weight: float = 0.40,
                    selfref_weight: float = 0.25,
                    reasoning_weight: float = 0.15,
                    realdata_weight: float = 0.20) -> float:
    """Four-tier harmonic mean fitness with configurable weights."""
    memory_names = ['delayed_echo', 'sequential_xor', 'running_max',
                    'accumulator', 'state_switcher']
    self_ref_names = ['sequence_prediction', 'error_correction',
                      'novelty_detection']
    reasoning_names = ['persistent_nav']
    real_data_names = ['real_line_length', 'real_indentation', 'real_nesting']

    mem_scores = [max(scores.get(n, 0), 0.01) for n in memory_names]
    sr_scores = [max(scores.get(n, 0), 0.01) for n in self_ref_names]
    rea_scores = [scores.get(n, 0) for n in reasoning_names]
    rd_scores = [max(scores.get(n, 0), 0.01) for n in real_data_names]

    mem_hmean = len(mem_scores) / sum(1.0 / s for s in mem_scores)
    sr_hmean = len(sr_scores) / sum(1.0 / s for s in sr_scores)
    rea_mean = np.mean(rea_scores) if rea_scores else 0
    rd_hmean = len(rd_scores) / sum(1.0 / s for s in rd_scores)

    return (mem_weight * mem_hmean + selfref_weight * sr_hmean +
            reasoning_weight * rea_mean + realdata_weight * rd_hmean)


# ============================================================================
# SELF-AWARE SEED PATTERNS (16 patterns, identical to ga_self_aware.py)
# ============================================================================

def self_aware_seed(rng: random.Random) -> Node:
    pattern = rng.randint(0, 15)

    if pattern == 0:
        return Node(op=Op.SEQ, children=[
            Node(op=Op.PREDICT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.IF, children=[
                    Node(op=Op.GT, children=[
                        Node(op=Op.SURPRISE, children=[Node(op=Op.ZERO)]),
                        Node(op=Op.ONE)
                    ]),
                    Node(op=Op.ONE),
                    Node(op=Op.ZERO)
                ])
            ])
        ])

    elif pattern == 1:
        return Node(op=Op.ACT, children=[
            Node(op=Op.ZERO),
            Node(op=Op.ADD, children=[
                Node(op=Op.LAST_OUT, children=[Node(op=Op.ZERO)]),
                Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
            ])
        ])

    elif pattern == 2:
        return Node(op=Op.IF, children=[
            Node(op=Op.GT, children=[
                Node(op=Op.STEP),
                Node(op=Op.CONST, value=0.2)
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[Node(op=Op.ZERO)])
            ]),
            Node(op=Op.SEQ, children=[
                Node(op=Op.WRITE, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ]),
                Node(op=Op.ACT, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ])
            ])
        ])

    elif pattern == 3:
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.SURPRISE, children=[Node(op=Op.ZERO)]),
                    Node(op=Op.CONST, value=0.5)
                ]),
                Node(op=Op.WRITE, children=[
                    reg,
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ]),
                Node(op=Op.READ, children=[reg.copy()])
            ]),
            Node(op=Op.PREDICT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ])
        ])

    elif pattern == 4:
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.SENSE, children=[Node(op=Op.ONE)]),
                    Node(op=Op.ZERO)
                ]),
                Node(op=Op.WRITE, children=[
                    reg,
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ]),
                Node(op=Op.READ, children=[reg.copy()])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ])
        ])

    elif pattern == 5:
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.WRITE, children=[
                reg,
                Node(op=Op.MAX2, children=[
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)]),
                    Node(op=Op.READ, children=[reg.copy()])
                ])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ])
        ])

    elif pattern == 6:
        reg = Node(op=Op.CONST, value=float(rng.randint(8, 12)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)]),
                    Node(op=Op.SENSE, children=[Node(op=Op.ONE)])
                ]),
                Node(op=Op.WRITE, children=[
                    reg,
                    Node(op=Op.INC, children=[
                        Node(op=Op.READ, children=[reg.copy()])
                    ])
                ]),
                Node(op=Op.READ, children=[reg.copy()])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ])
        ])

    elif pattern == 7:
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.ABS, children=[
                        Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                    ]),
                    Node(op=Op.ONE)
                ]),
                Node(op=Op.WRITE, children=[
                    reg,
                    Node(op=Op.SIGN, children=[
                        Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                    ])
                ]),
                Node(op=Op.READ, children=[reg.copy()])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ])
        ])

    elif pattern == 8:
        reg_prev = Node(op=Op.CONST, value=float(rng.randint(0, 3)))
        reg_cur = Node(op=Op.CONST, value=float(rng.randint(4, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.SEQ, children=[
                Node(op=Op.WRITE, children=[
                    reg_prev,
                    Node(op=Op.READ, children=[reg_cur.copy()])
                ]),
                Node(op=Op.WRITE, children=[
                    reg_cur,
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ]),
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.NEQ, children=[
                    Node(op=Op.READ, children=[reg_cur.copy()]),
                    Node(op=Op.READ, children=[reg_prev.copy()])
                ])
            ])
        ])

    elif pattern == 9:
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.SEQ, children=[
                Node(op=Op.WRITE, children=[
                    reg,
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ]),
                Node(op=Op.PREDICT, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ])
        ])

    elif pattern == 10:
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.SENSE, children=[Node(op=Op.ONE)]),
                    Node(op=Op.ZERO)
                ]),
                Node(op=Op.ACT, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.ADD, children=[
                        Node(op=Op.LAST_OUT, children=[Node(op=Op.ZERO)]),
                        Node(op=Op.MUL, children=[
                            Node(op=Op.SENSE, children=[Node(op=Op.ZERO)]),
                            Node(op=Op.CONST, value=0.7)
                        ])
                    ])
                ]),
                Node(op=Op.ACT, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.LAST_OUT, children=[Node(op=Op.ZERO)])
                ])
            ]),
            Node(op=Op.PREDICT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.LAST_OUT, children=[Node(op=Op.ZERO)])
            ])
        ])

    elif pattern == 11:
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.PREDICT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ]),
            Node(op=Op.SEQ, children=[
                Node(op=Op.IF, children=[
                    Node(op=Op.GT, children=[
                        Node(op=Op.SENSE, children=[Node(op=Op.ZERO)]),
                        Node(op=Op.READ, children=[reg.copy()])
                    ]),
                    Node(op=Op.WRITE, children=[
                        reg,
                        Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                    ]),
                    Node(op=Op.READ, children=[reg.copy()])
                ]),
                Node(op=Op.ACT, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.READ, children=[reg.copy()])
                ])
            ])
        ])

    elif pattern == 12:
        reg = Node(op=Op.CONST, value=float(rng.randint(8, 12)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)]),
                    Node(op=Op.SENSE, children=[Node(op=Op.ONE)])
                ]),
                Node(op=Op.WRITE, children=[
                    reg,
                    Node(op=Op.INC, children=[
                        Node(op=Op.READ, children=[reg.copy()])
                    ])
                ]),
                Node(op=Op.READ, children=[reg.copy()])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.MAX2, children=[
                    Node(op=Op.READ, children=[reg.copy()]),
                    Node(op=Op.LAST_OUT, children=[Node(op=Op.ZERO)])
                ])
            ])
        ])

    elif pattern == 13:
        return Node(op=Op.SEQ, children=[
            Node(op=Op.PREDICT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.SENSE, children=[Node(op=Op.ONE)])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.IF, children=[
                    Node(op=Op.GT, children=[
                        Node(op=Op.STEP),
                        Node(op=Op.ZERO)
                    ]),
                    Node(op=Op.ADD, children=[
                        Node(op=Op.LAST_OUT, children=[Node(op=Op.ZERO)]),
                        Node(op=Op.SIGN, children=[
                            Node(op=Op.SUB, children=[
                                Node(op=Op.SENSE, children=[Node(op=Op.ONE)]),
                                Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                            ])
                        ])
                    ]),
                    Node(op=Op.SIGN, children=[
                        Node(op=Op.SUB, children=[
                            Node(op=Op.SENSE, children=[Node(op=Op.ONE)]),
                            Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                        ])
                    ])
                ])
            ])
        ])

    elif pattern == 14:
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.SENSE, children=[Node(op=Op.ONE)]),
                    Node(op=Op.ZERO)
                ]),
                Node(op=Op.SEQ, children=[
                    Node(op=Op.WRITE, children=[
                        reg,
                        Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                    ]),
                    Node(op=Op.PREDICT, children=[
                        Node(op=Op.ZERO),
                        Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                    ])
                ]),
                Node(op=Op.IF, children=[
                    Node(op=Op.GT, children=[
                        Node(op=Op.SURPRISE, children=[Node(op=Op.ZERO)]),
                        Node(op=Op.ONE)
                    ]),
                    Node(op=Op.READ, children=[reg.copy()]),
                    Node(op=Op.READ, children=[reg.copy()])
                ])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ])
        ])

    else:
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.ABS, children=[
                        Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                    ]),
                    Node(op=Op.ONE)
                ]),
                Node(op=Op.SEQ, children=[
                    Node(op=Op.WRITE, children=[
                        reg,
                        Node(op=Op.SIGN, children=[
                            Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                        ])
                    ]),
                    Node(op=Op.PREDICT, children=[
                        Node(op=Op.ZERO),
                        Node(op=Op.SIGN, children=[
                            Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                        ])
                    ])
                ]),
                Node(op=Op.READ, children=[reg.copy()])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ])
        ])


# ============================================================================
# META-CHROMOSOME: 12 hyperparameter genes
# ============================================================================

# Gene definitions: (name, type, min, max, default)
GENE_DEFS = [
    ('island_pop',              'int',   20,   80,  50),
    ('tournament_k',            'int',    2,    7,   3),
    ('mutation_rate',           'float', 0.05, 0.50, 0.15),
    ('crossover_rate',          'float', 0.30, 0.90, 0.70),
    ('catastrophe_threshold',   'int',   20,   80,  40),
    ('fitness_memory_weight',   'float', 0.30, 0.70, 0.50),
    ('fitness_selfref_weight',  'float', 0.10, 0.50, 0.30),
    ('max_tree_depth',          'int',    4,   12,   8),
    ('elitism_count',           'int',    1,   10,   2),
    ('self_aware_bias',         'float', 0.05, 0.40, 0.15),
    ('scaffold_rounds',         'int',    0,   20,  10),
    ('merge_rate',              'float', 0.00, 0.50, 0.10),
]


class MetaChromosome:
    """Holds 12 hyperparameter genes with bounds checking."""

    def __init__(self, genes: Optional[Dict] = None):
        if genes is None:
            # Use defaults
            self.genes = {name: default for name, _, _, _, default in GENE_DEFS}
        else:
            self.genes = dict(genes)
        self._clamp_all()

    def _clamp_all(self):
        """Enforce bounds on all genes."""
        for name, gtype, lo, hi, _ in GENE_DEFS:
            val = self.genes.get(name)
            if val is None:
                self.genes[name] = _  # use default
                continue
            if gtype == 'int':
                self.genes[name] = int(max(lo, min(hi, round(val))))
            else:
                self.genes[name] = float(max(lo, min(hi, val)))

    @property
    def fitness_reasoning_weight(self) -> float:
        """Derived: 1.0 - mem - selfref, clamped to min 0.05."""
        remainder = 1.0 - self.genes['fitness_memory_weight'] - self.genes['fitness_selfref_weight']
        return max(0.05, remainder)

    def mutate(self, rng: random.Random) -> 'MetaChromosome':
        """Gaussian perturbation: sigma = 10% of range for floats, +/-1 for ints."""
        new_genes = dict(self.genes)
        for name, gtype, lo, hi, _ in GENE_DEFS:
            if rng.random() < 0.3:  # mutate ~30% of genes per mutation
                if gtype == 'int':
                    delta = rng.choice([-1, 0, 1])
                    new_genes[name] = int(max(lo, min(hi, new_genes[name] + delta)))
                else:
                    sigma = 0.10 * (hi - lo)
                    new_genes[name] = max(lo, min(hi, new_genes[name] + rng.gauss(0, sigma)))
        return MetaChromosome(new_genes)

    def crossover(self, other: 'MetaChromosome',
                  rng: random.Random) -> 'MetaChromosome':
        """Uniform crossover: 50/50 each gene from self or other."""
        new_genes = {}
        for name, _, _, _, _ in GENE_DEFS:
            if rng.random() < 0.5:
                new_genes[name] = self.genes[name]
            else:
                new_genes[name] = other.genes[name]
        return MetaChromosome(new_genes)

    def to_dict(self) -> Dict:
        d = dict(self.genes)
        d['fitness_reasoning_weight'] = self.fitness_reasoning_weight
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> 'MetaChromosome':
        genes = {name: d[name] for name, _, _, _, _ in GENE_DEFS if name in d}
        return cls(genes)

    @classmethod
    def random(cls, rng: random.Random) -> 'MetaChromosome':
        """Generate a random chromosome within bounds."""
        genes = {}
        for name, gtype, lo, hi, _ in GENE_DEFS:
            if gtype == 'int':
                genes[name] = rng.randint(lo, hi)
            else:
                genes[name] = rng.uniform(lo, hi)
        return cls(genes)

    def summary(self) -> str:
        """Short one-line summary of key genes."""
        g = self.genes
        return (f"pop={g['island_pop']} tk={g['tournament_k']} "
                f"mut={g['mutation_rate']:.2f} cx={g['crossover_rate']:.2f} "
                f"depth={g['max_tree_depth']} elite={g['elitism_count']} "
                f"sa={g['self_aware_bias']:.2f} "
                f"w={g['fitness_memory_weight']:.2f}/"
                f"{g['fitness_selfref_weight']:.2f}/"
                f"{self.fitness_reasoning_weight:.2f}")


# ============================================================================
# INNER EVOLUTION: mini ga_self_aware.py run
# ============================================================================

class InnerEvolution:
    """Runs a short inner GP evolution with given hyperparameters.

    1 island, configurable population size, configurable number of rounds.
    Uses same 32 ops, 9 tasks, and fitness function from ga_self_aware.py
    but with hyperparameters from the MetaChromosome.
    """

    def __init__(self, meta: MetaChromosome, n_rounds: int = 5, seed: int = 42):
        self.meta = meta
        self.n_rounds = n_rounds
        self.seed = seed
        self.rng = random.Random(seed)

        g = meta.genes
        self.pop_size = g['island_pop']
        self.tournament_k = g['tournament_k']
        self.mutation_rate = g['mutation_rate']
        self.crossover_rate = g['crossover_rate']
        self.catastrophe_threshold = g['catastrophe_threshold']
        self.max_tree_depth = g['max_tree_depth']
        self.elitism_count = min(g['elitism_count'], self.pop_size - 1)
        self.self_aware_bias = g['self_aware_bias']
        self.scaffold_rounds = g['scaffold_rounds']
        self.merge_rate = g['merge_rate']

        self.mem_weight = g['fitness_memory_weight']
        self.selfref_weight = g['fitness_selfref_weight']
        self.reasoning_weight = meta.fitness_reasoning_weight

        self.organisms: List[dict] = []
        self.best_fitness = 0.0
        self.stagnation = 0

    def initialize(self):
        """Create initial population with scaffolded seeds + random trees."""
        self.organisms = []
        rng = self.rng
        scaffold_rate = 0.5

        while len(self.organisms) < self.pop_size:
            if rng.random() < scaffold_rate:
                tree = self_aware_seed(rng)
            else:
                tree = random_tree(rng, max_depth=self.max_tree_depth,
                                   self_aware_bias=self.self_aware_bias)
            self.organisms.append({
                'tree': tree,
                'fitness': 0.0,
                'scores': {},
                'age': 0,
            })

    def evaluate_all(self, eval_seed: int = 42):
        """Evaluate all organisms using all 9 tasks."""
        for org in self.organisms:
            org['scores'] = evaluate_organism(
                org['tree'], ALL_TASKS, n_trials=6, seed=eval_seed
            )
            org['fitness'] = compute_fitness(
                org['scores'],
                mem_weight=self.mem_weight,
                selfref_weight=self.selfref_weight,
                reasoning_weight=self.reasoning_weight,
            )

    def evolve_one_round(self, round_num: int):
        """One round: evaluate, select, breed."""
        eval_seed = 42 + (round_num % 5)
        self.evaluate_all(eval_seed)
        self.organisms.sort(key=lambda o: o['fitness'], reverse=True)

        cur_best = self.organisms[0]['fitness']
        if cur_best > self.best_fitness:
            self.best_fitness = cur_best
            self.stagnation = 0
        else:
            self.stagnation += 1

        # Catastrophe check
        if self.stagnation >= self.catastrophe_threshold:
            keep = max(2, self.pop_size // 5)
            self.organisms = self.organisms[:keep]
            while len(self.organisms) < self.pop_size:
                if self.rng.random() < 0.6:
                    tree = self_aware_seed(self.rng)
                else:
                    tree = random_tree(self.rng,
                                       max_depth=self.max_tree_depth,
                                       self_aware_bias=self.self_aware_bias)
                self.organisms.append({
                    'tree': tree, 'fitness': 0.0,
                    'scores': {}, 'age': 0,
                })
            self.stagnation = 0
            return

        # Elitism
        new_pop = self.organisms[:self.elitism_count]

        # Scaffolded vs normal breeding
        use_scaffold = round_num < self.scaffold_rounds

        while len(new_pop) < self.pop_size:
            child = self._breed(use_scaffold)
            new_pop.append(child)

        self.organisms = new_pop
        for org in self.organisms:
            org['age'] += 1

    def _breed(self, use_scaffold: bool) -> dict:
        """Produce one offspring via selection + variation."""
        rng = self.rng

        # During scaffold rounds, 40% chance of scaffolded seed instead of breeding
        if use_scaffold and rng.random() < 0.40:
            tree = self_aware_seed(rng)
            return {'tree': tree, 'fitness': 0.0, 'scores': {}, 'age': 0}

        parent = self._tournament()
        r = rng.random()

        if r < self.merge_rate and len(self.organisms) > 2:
            # Merge/fusion: graft relevant subtree from another individual
            other = self._tournament()
            tree = parent['tree'].copy()
            donor_nodes = get_all_nodes(other['tree'])
            relevant = [
                (n, p, i) for n, p, i in donor_nodes
                if any(nn.op in (Op.READ, Op.WRITE, Op.IF, Op.PREDICT,
                                 Op.SURPRISE, Op.LAST_OUT)
                       for nn, _, _ in get_all_nodes(n))
                and 3 <= n.size() <= 30
            ]
            if not relevant:
                relevant = [(n, p, i) for n, p, i in donor_nodes
                            if 3 <= n.size() <= 20]
            if relevant:
                graft = rng.choice(relevant)[0].copy()
                host_nodes = get_all_nodes(tree)
                if len(host_nodes) > 1:
                    _, hp, hi = rng.choice(host_nodes[1:])
                    if hp is not None:
                        hp.children[hi] = graft
            if tree.size() > 250:
                tree = parent['tree'].copy()

        elif r < self.merge_rate + self.crossover_rate:
            # Subtree crossover
            other = self._tournament()
            tree = subtree_crossover(parent['tree'], other['tree'], rng)

        elif rng.random() < 0.5:
            # Subtree mutation
            tree = subtree_mutation(parent['tree'], rng,
                                    max_depth=min(4, self.max_tree_depth),
                                    self_aware_bias=self.self_aware_bias)
        else:
            # Point mutation
            tree = point_mutation(parent['tree'], rng,
                                  rate=self.mutation_rate)

        # Size cap
        if tree.size() > 250:
            tree = parent['tree'].copy()

        return {'tree': tree, 'fitness': 0.0, 'scores': {}, 'age': 0}

    def _tournament(self) -> dict:
        k = min(self.tournament_k, len(self.organisms))
        return max(self.rng.sample(self.organisms, k),
                   key=lambda o: o['fitness'])

    def run(self) -> float:
        """Run the full inner evolution and return best fitness achieved."""
        self.initialize()
        for r in range(self.n_rounds):
            self.evolve_one_round(r)
        # Final evaluation to get accurate fitness
        self.evaluate_all(eval_seed=99)
        self.organisms.sort(key=lambda o: o['fitness'], reverse=True)
        return self.organisms[0]['fitness']


# ============================================================================
# OUTER META-GA
# ============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class MetaGA:
    """Outer GA that evolves hyperparameters of the inner GP engine."""

    def __init__(self, outer_pop: int = 10, outer_gens: int = 20,
                 inner_rounds: int = 5, cores: int = 3, seed: int = 66):
        self.outer_pop = outer_pop
        self.outer_gens = outer_gens
        self.inner_rounds = inner_rounds
        self.cores = cores  # reserved for future parallel inner evals
        self.seed = seed
        self.rng = random.Random(seed)

        self.population: List[Tuple[MetaChromosome, float]] = []
        self.generation = 0
        self.global_best_chromo: Optional[MetaChromosome] = None
        self.global_best_fitness = 0.0
        self.history: List[dict] = []

        self.best_path = os.path.join(SCRIPT_DIR, 'exp2_meta_ga_best.json')
        self.log_path = os.path.join(SCRIPT_DIR, 'exp2_meta_ga_log.jsonl')

    def evaluate_individual(self, chromo: MetaChromosome,
                            individual_seed: int) -> float:
        """Run a short inner evolution with the given hyperparameters.
        Returns best fitness achieved."""
        inner = InnerEvolution(
            meta=chromo,
            n_rounds=self.inner_rounds,
            seed=individual_seed,
        )
        return inner.run()

    def initialize_population(self):
        """Create initial outer population: default + random."""
        self.population = []
        # Individual 0: the defaults (our baseline to beat)
        self.population.append((MetaChromosome(), 0.0))

        # Remaining: random
        for _ in range(self.outer_pop - 1):
            chromo = MetaChromosome.random(self.rng)
            self.population.append((chromo, 0.0))

    def tournament_select(self, k: int = 3) -> MetaChromosome:
        """Tournament selection from current population."""
        candidates = self.rng.sample(self.population, min(k, len(self.population)))
        winner = max(candidates, key=lambda x: x[1])
        return winner[0]

    def run(self):
        """Run the full meta-GA."""
        self.initialize_population()

        running = [True]

        def handler(sig, frame):
            print(f"\n[SIGNAL] Saving best and stopping...")
            running[0] = False

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        print()
        print("=" * 72)
        print("  EXPERIMENT 2: META-GA FOR HYPERPARAMETER EVOLUTION")
        print("=" * 72)
        print(f"  Outer population:  {self.outer_pop}")
        print(f"  Outer generations: {self.outer_gens}")
        print(f"  Inner rounds/eval: {self.inner_rounds}")
        print(f"  Cores (reserved):  {self.cores}")
        print(f"  Seed:              {self.seed}")
        print(f"  Chromosome:        12 genes (pop, tournament, mutation, ...")
        print(f"  Inner engine:      1 island, 9 tasks, 32 ops")
        print(f"  Elitism:           2 meta-individuals")
        print(f"  Selection:         Tournament k=3")
        print(f"  Output:            {os.path.basename(self.best_path)}")
        print("=" * 72)
        print()

        total_start = time.time()

        for gen in range(self.outer_gens):
            if not running[0]:
                break

            self.generation = gen + 1
            gen_start = time.time()

            # -- Evaluate all individuals --
            evaluated = []
            for i, (chromo, _) in enumerate(self.population):
                if not running[0]:
                    break
                ind_seed = self.seed * 1000 + gen * 100 + i
                fitness = self.evaluate_individual(chromo, ind_seed)
                evaluated.append((chromo, fitness))

                # Progress indicator for long evaluations
                if (i + 1) % 5 == 0 or i == len(self.population) - 1:
                    elapsed = time.time() - gen_start
                    print(f"    [gen {self.generation}] evaluated {i + 1}/{len(self.population)}"
                          f"  ({elapsed:.0f}s)", end='\r')

            if not running[0] and len(evaluated) < len(self.population):
                # Partial evaluation on interrupt -- keep what we have
                self.population = evaluated
                break

            self.population = evaluated
            print()  # clear progress line

            # -- Sort by fitness --
            self.population.sort(key=lambda x: x[1], reverse=True)

            best_chromo, best_fit = self.population[0]

            # Update global best
            if best_fit > self.global_best_fitness:
                self.global_best_fitness = best_fit
                self.global_best_chromo = MetaChromosome(dict(best_chromo.genes))

            # -- Stats --
            fitnesses = [f for _, f in self.population]
            avg_fit = np.mean(fitnesses)
            std_fit = np.std(fitnesses)
            worst_fit = fitnesses[-1]
            gen_time = time.time() - gen_start

            print(f"  Gen {self.generation:3d}/{self.outer_gens}"
                  f"  best={best_fit:.4f}  avg={avg_fit:.4f}"
                  f"  std={std_fit:.4f}  worst={worst_fit:.4f}"
                  f"  ({gen_time:.0f}s)")
            print(f"         {best_chromo.summary()}")

            if self.global_best_fitness > best_fit:
                print(f"         (global best: {self.global_best_fitness:.4f})")

            # -- Log --
            entry = {
                'gen': self.generation,
                'best_fitness': best_fit,
                'avg_fitness': float(avg_fit),
                'std_fitness': float(std_fit),
                'worst_fitness': worst_fit,
                'global_best': self.global_best_fitness,
                'best_chromosome': best_chromo.to_dict(),
                'time_s': round(gen_time, 1),
                'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }
            self.history.append(entry)
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')

            # Report to REST API
            report_generation(
                experiment_name='exp2_meta_ga',
                generation=self.generation,
                best_fitness=self.global_best_fitness,
                scores=best_chromo.to_dict(),
                metadata={'avg_fitness': float(avg_fit), 'std_fitness': float(std_fit)},
            )

            # -- Breed next generation (unless final) --
            if self.generation < self.outer_gens and running[0]:
                new_pop = []

                # Elitism: keep top 2
                for i in range(min(2, len(self.population))):
                    new_pop.append((MetaChromosome(dict(self.population[i][0].genes)), 0.0))

                # Breed offspring
                while len(new_pop) < self.outer_pop:
                    parent1 = self.tournament_select(k=3)
                    parent2 = self.tournament_select(k=3)
                    child = parent1.crossover(parent2, self.rng)
                    child = child.mutate(self.rng)
                    new_pop.append((child, 0.0))

                self.population = new_pop

            # Save periodically
            if self.generation % 5 == 0 or self.generation == self.outer_gens:
                self._save_best()

            sys.stdout.flush()

        # Final save
        self._save_best()

        total_time = time.time() - total_start
        print()
        print("=" * 72)
        print(f"  META-GA COMPLETE")
        print(f"  Generations:    {self.generation}")
        print(f"  Total time:     {total_time:.0f}s ({total_time / 60:.1f} min)")
        print(f"  Best fitness:   {self.global_best_fitness:.4f}")
        print("=" * 72)

        if self.global_best_chromo:
            print()
            print("  BEST HYPERPARAMETERS FOUND:")
            print("  " + "-" * 40)
            d = self.global_best_chromo.to_dict()
            for name, _, _, _, default in GENE_DEFS:
                val = d[name]
                if isinstance(val, float):
                    delta = val - default
                    print(f"    {name:28s} = {val:.4f}  (default: {default}, delta: {delta:+.4f})")
                else:
                    delta = val - default
                    print(f"    {name:28s} = {val}  (default: {default}, delta: {delta:+d})")
            rw = d.get('fitness_reasoning_weight', 0)
            print(f"    {'fitness_reasoning_weight':28s} = {rw:.4f}  (derived)")
            print()
            print(f"  Saved to: {self.best_path}")

        # Comparison with defaults
        print()
        print("  DEFAULT vs BEST comparison:")
        default_entry = None
        best_entry = None
        for entry in self.history:
            if entry['gen'] == 1:
                # In gen 1, the first individual is the default
                default_entry = entry
            if entry['best_fitness'] == self.global_best_fitness:
                best_entry = entry
        if default_entry and best_entry:
            improvement = self.global_best_fitness - default_entry.get('worst_fitness', 0)
            print(f"    Gen 1 best:  {default_entry['best_fitness']:.4f}")
            print(f"    Final best:  {self.global_best_fitness:.4f}")

        print("=" * 72)

    def _save_best(self):
        """Save best chromosome to JSON."""
        if self.global_best_chromo is None:
            return
        data = {
            'generation': self.generation,
            'fitness': self.global_best_fitness,
            'chromosome': self.global_best_chromo.to_dict(),
            'inner_rounds': self.inner_rounds,
            'outer_pop': self.outer_pop,
            'outer_gens': self.outer_gens,
            'seed': self.seed,
            'history_summary': {
                'total_generations': len(self.history),
                'fitness_trajectory': [h['best_fitness'] for h in self.history],
            },
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        with open(self.best_path, 'w') as f:
            json.dump(data, f, indent=2)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Experiment 2: Meta-GA for Hyperparameter Evolution')
    parser.add_argument('--outer-pop', type=int, default=10,
                        help='Outer GA population size (default: 10)')
    parser.add_argument('--outer-gens', type=int, default=20,
                        help='Outer GA generations (default: 20)')
    parser.add_argument('--inner-rounds', type=int, default=5,
                        help='Inner evolution rounds per evaluation (default: 5)')
    parser.add_argument('--cores', type=int, default=3,
                        help='Reserved cores (default: 3, inner evals are serial)')
    parser.add_argument('--seed', type=int, default=66,
                        help='Random seed (default: 66)')
    args = parser.parse_args()

    meta_ga = MetaGA(
        outer_pop=args.outer_pop,
        outer_gens=args.outer_gens,
        inner_rounds=args.inner_rounds,
        cores=args.cores,
        seed=args.seed,
    )
    meta_ga.run()


if __name__ == '__main__':
    main()
