#!/usr/bin/env python3
"""GA Experiment 7: NSGA-II Multi-Objective Selection

Fork of ga_self_aware.py (v3/v4) replacing single-scalar fitness with
NSGA-II multi-objective optimization over 3 objectives:

  Objective 0: memory_hmean   -- harmonic mean of memory tasks
  Objective 1: selfref_hmean  -- harmonic mean of self-referential tasks
  Objective 2: reasoning_mean -- arithmetic mean of reasoning tasks

Hypothesis: Harmonic mean aggregation severely punishes specialists.
An organism with memory_hmean=0.85, selfref_hmean=0.15 gets scalar
fitness ~0.30 and dies. NSGA-II preserves it on the Pareto front,
maintaining specialists that can later cross to produce generalists.

Key changes from ga_self_aware.py:
  - 3-objective fitness stored per organism
  - Non-dominated sorting (NSGA-II) partitions into Pareto fronts
  - Crowding distance preserves diversity within fronts
  - Tournament selection compares (front_rank, crowding_distance)
  - Elitism: merge 2N -> sort -> fill N from fronts
  - Knee point detection on F0 for "best balanced" organism
  - Scalar fitness still computed for logging/comparison with v4

Usage:
    python3 ga_exp7_nsga2.py              # run with defaults
    python3 ga_exp7_nsga2.py --cores 3    # limit parallelism
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
from collections import defaultdict
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ga_sequence_data import REAL_DATA_TASKS, prefetch_sequences
from ga_result_reporter import report_generation


# ============================================================================
# EXTENDED OP SET -- original 28 + 4 self-referential
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

    # === SELF-REFERENTIAL OPS (new in v3) ===
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
    # Self-referential
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

OP_NAMES = {op.name: op for op in Op}


# ============================================================================
# PROGRAM PARSER -- reconstruct trees from text representation
# ============================================================================

def parse_program(text: str) -> Optional['Node']:
    """Parse S-expression program text back into a Node tree.
    Handles truncated programs gracefully (fills missing children with ZERO)."""
    tokens = _tokenize(text)
    if not tokens:
        return None
    try:
        node, _ = _parse_node(tokens, 0)
        return node
    except (IndexError, ValueError):
        return None


def _tokenize(text: str) -> List[str]:
    text = text.replace('(', ' ( ').replace(')', ' ) ')
    return [t for t in text.split() if t]


def _parse_node(tokens: List[str], pos: int) -> Tuple['Node', int]:
    if pos >= len(tokens):
        return Node(op=Op.ZERO), pos

    token = tokens[pos]

    if token == '(':
        pos += 1
        if pos >= len(tokens):
            return Node(op=Op.ZERO), pos

        op_name = tokens[pos]
        pos += 1

        if op_name not in OP_NAMES:
            return Node(op=Op.ZERO), pos

        op = OP_NAMES[op_name]
        arity = ARITY[op]
        children = []

        for _ in range(arity):
            if pos >= len(tokens) or tokens[pos] == ')':
                children.append(Node(op=Op.ZERO))
            else:
                child, pos = _parse_node(tokens, pos)
                children.append(child)

        if pos < len(tokens) and tokens[pos] == ')':
            pos += 1

        return Node(op=op, children=children), pos

    elif token == ')':
        return Node(op=Op.ZERO), pos + 1

    elif token in OP_NAMES:
        op = OP_NAMES[token]
        if ARITY[op] == 0:
            return Node(op=op), pos + 1
        return Node(op=op, children=[Node(op=Op.ZERO)] * ARITY[op]), pos + 1

    else:
        try:
            val = float(token)
            return Node(op=Op.CONST, value=val), pos + 1
        except ValueError:
            return Node(op=Op.ZERO), pos + 1


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

    def to_str(self, indent=0) -> str:
        prefix = "  " * indent
        if self.op == Op.CONST:
            return f"{prefix}{self.value:.2f}"
        if not self.children:
            return f"{prefix}{self.op.name}"
        child_strs = "\n".join(c.to_str(indent + 1) for c in self.children)
        return f"{prefix}({self.op.name}\n{child_strs})"


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
# EXECUTE -- handles all ops including self-referential
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

    # === SELF-REFERENTIAL ===
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


def count_ops(tree: Node, op_set: set) -> int:
    count = 1 if tree.op in op_set else 0
    return count + sum(count_ops(c, op_set) for c in tree.children)


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


def subtree_mutation(tree: Node, rng: random.Random) -> Node:
    child = tree.copy()
    nodes = get_all_nodes(child)
    if len(nodes) > 1:
        _, p, i = rng.choice(nodes[1:])
        if p is not None:
            new_sub = random_tree(rng, max_depth=3)
            p.children[i] = new_sub
    return child


# ============================================================================
# V2 MEMORY TASKS (baseline)
# ============================================================================

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


# ============================================================================
# SELF-REFERENTIAL TASKS
# ============================================================================

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
                v1, v2 = round(rng.uniform(-3, 3), 1), round(rng.uniform(-3, 3), 1)
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
# EVALUATION -- 3-objective + scalar
# ============================================================================

MEMORY_NAMES = ['delayed_echo', 'sequential_xor', 'running_max',
                'accumulator', 'state_switcher']
SELF_REF_NAMES = ['sequence_prediction', 'error_correction',
                  'novelty_detection']
REASONING_NAMES = ['persistent_nav']
REAL_DATA_NAMES = ['real_line_length', 'real_indentation', 'real_nesting']


def evaluate_organism(tree: Node, tasks: dict, n_trials: int = 10,
                      seed: int = 42) -> dict:
    scores = {}
    for name, task in tasks.items():
        rng = random.Random(seed)
        trials = task.generate_trials(n_trials, rng)
        trial_scores = [task.evaluate(tree, trial) for trial in trials]
        scores[name] = float(np.mean(trial_scores))
    return scores


def _harmonic_mean(values: List[float]) -> float:
    """Harmonic mean with floor at 0.01 to avoid division by zero."""
    clamped = [max(v, 0.01) for v in values]
    return len(clamped) / sum(1.0 / s for s in clamped)


def compute_objectives(scores: dict) -> List[float]:
    """Compute 4 objectives from task scores.
    Returns [memory_hmean, selfref_hmean, reasoning_mean, realdata_hmean].
    """
    mem_scores = [scores.get(n, 0) for n in MEMORY_NAMES]
    sr_scores = [scores.get(n, 0) for n in SELF_REF_NAMES]
    rea_scores = [scores.get(n, 0) for n in REASONING_NAMES]
    rd_scores = [scores.get(n, 0) for n in REAL_DATA_NAMES]

    mem_hmean = _harmonic_mean(mem_scores)
    sr_hmean = _harmonic_mean(sr_scores)
    rea_mean = float(np.mean(rea_scores)) if rea_scores else 0.0
    rd_hmean = _harmonic_mean(rd_scores)

    return [mem_hmean, sr_hmean, rea_mean, rd_hmean]


def scalar_fitness(objectives: List[float]) -> float:
    """Scalar fitness for comparison:
    0.30 * memory + 0.10 * selfref + 0.40 * reasoning + 0.20 * realdata
    """
    return (0.30 * objectives[0] + 0.10 * objectives[1] +
            0.40 * objectives[2] + 0.20 * objectives[3])


# ============================================================================
# NSGA-II FUNCTIONS
# ============================================================================

def dominates(a: List[float], b: List[float]) -> bool:
    """Return True if a dominates b (a >= b on all, a > b on at least one)."""
    at_least_one_better = False
    for ai, bi in zip(a, b):
        if ai < bi:
            return False
        if ai > bi:
            at_least_one_better = True
    return at_least_one_better


def fast_non_dominated_sort(population: List[dict]) -> List[List[int]]:
    """NSGA-II fast non-dominated sort.
    Returns list of fronts, each front is a list of indices into population.
    F[0] = non-dominated (Pareto front), F[1] = next layer, etc.
    """
    n = len(population)
    S = [[] for _ in range(n)]     # S[p] = set of solutions dominated by p
    n_dom = [0] * n                # n_dom[p] = number of solutions dominating p
    fronts = [[]]                  # fronts[0] = first front

    for p in range(n):
        obj_p = population[p]['objectives']
        for q in range(n):
            if p == q:
                continue
            obj_q = population[q]['objectives']
            if dominates(obj_p, obj_q):
                S[p].append(q)
            elif dominates(obj_q, obj_p):
                n_dom[p] += 1

        if n_dom[p] == 0:
            population[p]['front_rank'] = 0
            fronts[0].append(p)

    i = 0
    while fronts[i]:
        next_front = []
        for p in fronts[i]:
            for q in S[p]:
                n_dom[q] -= 1
                if n_dom[q] == 0:
                    population[q]['front_rank'] = i + 1
                    next_front.append(q)
        i += 1
        fronts.append(next_front)

    # Remove trailing empty front
    if not fronts[-1]:
        fronts.pop()

    return fronts


def crowding_distance(population: List[dict], front: List[int]) -> None:
    """Compute crowding distance for organisms in a front.
    Sets population[idx]['crowding_distance'] for each idx in front.
    """
    n = len(front)
    if n == 0:
        return

    for idx in front:
        population[idx]['crowding_distance'] = 0.0

    if n <= 2:
        for idx in front:
            population[idx]['crowding_distance'] = float('inf')
        return

    n_obj = len(population[front[0]]['objectives'])

    for m in range(n_obj):
        # Sort front by objective m
        sorted_front = sorted(front, key=lambda idx: population[idx]['objectives'][m])

        # Boundary points get infinite distance
        population[sorted_front[0]]['crowding_distance'] = float('inf')
        population[sorted_front[-1]]['crowding_distance'] = float('inf')

        obj_min = population[sorted_front[0]]['objectives'][m]
        obj_max = population[sorted_front[-1]]['objectives'][m]
        obj_range = obj_max - obj_min

        if obj_range < 1e-12:
            continue

        for k in range(1, n - 1):
            idx = sorted_front[k]
            prev_val = population[sorted_front[k - 1]]['objectives'][m]
            next_val = population[sorted_front[k + 1]]['objectives'][m]
            population[idx]['crowding_distance'] += (next_val - prev_val) / obj_range


def nsga2_tournament(pop: List[dict], rng: random.Random, k: int = 4) -> dict:
    """Tournament selection using NSGA-II criteria.
    Lower front_rank wins. If same front, higher crowding distance wins.
    """
    candidates = rng.sample(pop, min(k, len(pop)))
    return min(candidates, key=lambda o: (
        o.get('front_rank', 999),
        -o.get('crowding_distance', 0.0)
    ))


def find_knee_point(population: List[dict], front: List[int]) -> int:
    """Find the knee point on Pareto front F0.
    The knee point is the organism closest to the ideal point
    (max of each objective across the front).
    Uses normalized Euclidean distance.
    """
    if not front:
        return 0

    if len(front) == 1:
        return front[0]

    n_obj = len(population[front[0]]['objectives'])

    # Ideal point: max of each objective across the front
    ideal = [max(population[idx]['objectives'][m] for idx in front)
             for m in range(n_obj)]

    # Ranges for normalization
    mins = [min(population[idx]['objectives'][m] for idx in front)
            for m in range(n_obj)]
    ranges = [ideal[m] - mins[m] if ideal[m] - mins[m] > 1e-12 else 1.0
              for m in range(n_obj)]

    # Find organism closest to ideal in normalized space
    best_idx = front[0]
    best_dist = float('inf')
    for idx in front:
        dist = 0.0
        for m in range(n_obj):
            norm = (ideal[m] - population[idx]['objectives'][m]) / ranges[m]
            dist += norm * norm
        dist = math.sqrt(dist)
        if dist < best_dist:
            best_dist = dist
            best_idx = idx

    return best_idx


# ============================================================================
# SELF-AWARE SEED PATTERNS (identical to ga_self_aware.py)
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
# ISLAND -- NSGA-II variant
# ============================================================================

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_transplants() -> List[Node]:
    """Load best organisms from v2, v3, and v4 runs for cross-pollination."""
    transplants = []
    for path in [
        os.path.join(TOOLS_DIR, 'memory_pressure_v2_best.json'),
        os.path.join(TOOLS_DIR, 'self_aware_best.json'),
        os.path.join(TOOLS_DIR, 'hybrid_best.json'),
    ]:
        try:
            with open(path) as f:
                data = json.load(f)
            prog_text = data.get('program', '')
            tree = parse_program(prog_text)
            if tree and tree.size() > 3:
                transplants.append(tree)
                print(f"  Loaded transplant from {os.path.basename(path)}:"
                      f" {tree.size()} nodes")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return transplants


class NSGA2Island:
    """Island running NSGA-II multi-objective evolution."""

    def __init__(self, island_id: int, pop_size: int, seed: int):
        self.id = island_id
        self.pop_size = pop_size
        self.rng = random.Random(seed)
        self.organisms = []
        self.plasmids = []
        self.epoch = 0
        self.best_scalar = 0.0
        self.stagnation = 0
        self.catastrophes = 0

    def initialize(self, scaffold_rate: float = 0.5,
                   transplants: Optional[List[Node]] = None):
        self.organisms = []
        rng = self.rng

        # Inject transplants
        if transplants and self.id < len(transplants) * 3:
            for t_tree in transplants:
                tree = t_tree.copy()
                strategy = {
                    'crossover_rate': rng.uniform(0.3, 0.7),
                    'point_mut_rate': rng.uniform(0.05, 0.3),
                    'subtree_mut_rate': rng.uniform(0.05, 0.2),
                    'chaos_rate': rng.uniform(0.0, 0.05),
                    'merge_rate': rng.uniform(0.1, 0.4),
                }
                self.organisms.append({
                    'tree': tree, 'objectives': [0.0, 0.0, 0.0],
                    'scalar_fitness': 0.0, 'scores': {},
                    'strategy': strategy, 'age': 0,
                    'front_rank': 999, 'crowding_distance': 0.0,
                })
                for _ in range(2):
                    variant = point_mutation(tree, rng, rate=0.2)
                    self.organisms.append({
                        'tree': variant, 'objectives': [0.0, 0.0, 0.0],
                        'scalar_fitness': 0.0, 'scores': {},
                        'strategy': copy.deepcopy(strategy), 'age': 0,
                        'front_rank': 999, 'crowding_distance': 0.0,
                    })

            if len(transplants) >= 2:
                for _ in range(3):
                    hybrid = subtree_crossover(
                        transplants[0], transplants[1], rng)
                    strategy = {
                        'crossover_rate': rng.uniform(0.4, 0.8),
                        'point_mut_rate': rng.uniform(0.05, 0.2),
                        'subtree_mut_rate': rng.uniform(0.05, 0.15),
                        'chaos_rate': rng.uniform(0.0, 0.05),
                        'merge_rate': rng.uniform(0.2, 0.5),
                    }
                    self.organisms.append({
                        'tree': hybrid, 'objectives': [0.0, 0.0, 0.0],
                        'scalar_fitness': 0.0, 'scores': {},
                        'strategy': strategy, 'age': 0,
                        'front_rank': 999, 'crowding_distance': 0.0,
                    })

        # Fill remaining
        while len(self.organisms) < self.pop_size:
            if rng.random() < scaffold_rate:
                tree = self_aware_seed(rng)
            else:
                tree = random_tree(rng, max_depth=5 + (self.id % 3))

            strategy = {
                'crossover_rate': rng.uniform(0.3, 0.7),
                'point_mut_rate': rng.uniform(0.05, 0.3),
                'subtree_mut_rate': rng.uniform(0.05, 0.2),
                'chaos_rate': rng.uniform(0.0, 0.1),
                'merge_rate': rng.uniform(0.0, 0.2),
            }

            self.organisms.append({
                'tree': tree, 'objectives': [0.0, 0.0, 0.0],
                'scalar_fitness': 0.0, 'scores': {},
                'strategy': strategy, 'age': 0,
                'front_rank': 999, 'crowding_distance': 0.0,
            })

    def evaluate_all(self, seed: int = 42):
        """Evaluate all organisms and compute 3 objectives + scalar."""
        for org in self.organisms:
            org['scores'] = evaluate_organism(
                org['tree'], ALL_TASKS, n_trials=8, seed=seed
            )
            org['objectives'] = compute_objectives(org['scores'])
            org['scalar_fitness'] = scalar_fitness(org['objectives'])

    def _nsga2_sort_and_assign(self):
        """Run NSGA-II non-dominated sort and crowding distance on current pop."""
        fronts = fast_non_dominated_sort(self.organisms)
        for front in fronts:
            crowding_distance(self.organisms, front)
        return fronts

    def evolve_one_epoch(self):
        self.epoch += 1
        rng = self.rng

        # Evaluate current population
        self.evaluate_all(seed=42 + (self.epoch % 5))

        # NSGA-II sort current population
        fronts = self._nsga2_sort_and_assign()

        # Track stagnation via knee point scalar fitness
        knee_idx = find_knee_point(self.organisms, fronts[0]) if fronts else 0
        knee_scalar = self.organisms[knee_idx]['scalar_fitness']

        if knee_scalar > self.best_scalar:
            self.best_scalar = knee_scalar
            self.stagnation = 0
        else:
            self.stagnation += 1

        # Catastrophe check
        if self.stagnation > 40 and rng.random() < 0.3:
            # Keep knee point and a few top-front organisms
            keep_indices = set()
            keep_indices.add(knee_idx)
            for idx in fronts[0][:max(2, self.pop_size // 5 - 1)]:
                keep_indices.add(idx)
            kept = [self.organisms[i] for i in keep_indices]

            self.organisms = kept
            while len(self.organisms) < self.pop_size:
                if rng.random() < 0.6:
                    tree = self_aware_seed(rng)
                else:
                    tree = random_tree(rng, max_depth=rng.randint(4, 7))
                strategy = {
                    'crossover_rate': rng.uniform(0.3, 0.7),
                    'point_mut_rate': rng.uniform(0.05, 0.3),
                    'subtree_mut_rate': rng.uniform(0.05, 0.2),
                    'chaos_rate': rng.uniform(0.0, 0.1),
                    'merge_rate': rng.uniform(0.0, 0.2),
                }
                self.organisms.append({
                    'tree': tree, 'objectives': [0.0, 0.0, 0.0],
                    'scalar_fitness': 0.0, 'scores': {},
                    'strategy': strategy, 'age': 0,
                    'front_rank': 999, 'crowding_distance': 0.0,
                })
            self.catastrophes += 1
            self.stagnation = 0
            return

        # Update plasmid pool from front-0 organisms
        for idx in fronts[0][:5]:
            org = self.organisms[idx]
            nodes = get_all_nodes(org['tree'])
            for node, _, _ in nodes:
                has_relevant = any(
                    n.op in (Op.READ, Op.WRITE, Op.PREDICT, Op.SURPRISE,
                             Op.LAST_OUT)
                    for n, _, _ in get_all_nodes(node)
                )
                if has_relevant and 3 <= node.size() <= 30 and rng.random() < 0.15:
                    self.plasmids.append(node.copy())
        if len(self.plasmids) > 100:
            rng.shuffle(self.plasmids)
            self.plasmids = self.plasmids[:60]

        # Generate offspring population (same size as parent)
        offspring = []
        while len(offspring) < self.pop_size:
            child = self._breed(rng)
            offspring.append(child)

        # NSGA-II elitism: merge parent + offspring (2N)
        merged = self.organisms + offspring

        # Evaluate offspring
        for org in offspring:
            org['scores'] = evaluate_organism(
                org['tree'], ALL_TASKS, n_trials=8,
                seed=42 + (self.epoch % 5)
            )
            org['objectives'] = compute_objectives(org['scores'])
            org['scalar_fitness'] = scalar_fitness(org['objectives'])

        # Non-dominated sort on merged population
        merged_fronts = fast_non_dominated_sort(merged)
        for front in merged_fronts:
            crowding_distance(merged, front)

        # Fill next generation from fronts until we reach pop_size
        next_gen = []
        for front in merged_fronts:
            if len(next_gen) + len(front) <= self.pop_size:
                # Entire front fits
                for idx in front:
                    next_gen.append(merged[idx])
            else:
                # Partial front: sort by crowding distance (descending)
                remaining = self.pop_size - len(next_gen)
                sorted_front = sorted(
                    front,
                    key=lambda idx: merged[idx].get('crowding_distance', 0.0),
                    reverse=True
                )
                for idx in sorted_front[:remaining]:
                    next_gen.append(merged[idx])
                break

        self.organisms = next_gen
        for org in self.organisms:
            org['age'] += 1

    def _breed(self, rng) -> dict:
        """Create one offspring using NSGA-II tournament selection."""
        parent = nsga2_tournament(self.organisms, rng, k=4)
        s = parent['strategy']
        r = rng.random()

        cumulative = s.get('chaos_rate', 0)
        if r < cumulative:
            if rng.random() < 0.6:
                tree = self_aware_seed(rng)
            else:
                tree = random_tree(rng, max_depth=6)
        else:
            cumulative += s.get('merge_rate', 0)
            if r < cumulative and len(self.organisms) > 2:
                other = nsga2_tournament(self.organisms, rng, k=3)
                tree = parent['tree'].copy()
                donor_nodes = get_all_nodes(other['tree'])
                mem_subtrees = [
                    (n, p, i) for n, p, i in donor_nodes
                    if any(nn.op in (Op.READ, Op.WRITE, Op.IF, Op.PREDICT,
                                     Op.SURPRISE, Op.LAST_OUT)
                           for nn, _, _ in get_all_nodes(n))
                    and 3 <= n.size() <= 30
                ]
                if not mem_subtrees:
                    mem_subtrees = [(n, p, i) for n, p, i in donor_nodes
                                   if 3 <= n.size() <= 20]
                if mem_subtrees:
                    graft = rng.choice(mem_subtrees)[0].copy()
                    host_nodes = get_all_nodes(tree)
                    if len(host_nodes) > 1:
                        _, hp, hi = rng.choice(host_nodes[1:])
                        if hp is not None:
                            hp.children[hi] = graft
                if tree.size() > 250:
                    tree = parent['tree'].copy()
            else:
                cumulative += s['crossover_rate']
                if r < cumulative:
                    other = nsga2_tournament(self.organisms, rng, k=3)
                    tree = subtree_crossover(parent['tree'], other['tree'],
                                             rng)
                elif rng.random() < 0.5:
                    tree = subtree_mutation(parent['tree'], rng)
                else:
                    tree = point_mutation(parent['tree'], rng,
                                         rate=s.get('point_mut_rate', 0.15))

        # HGT from plasmid pool
        if self.plasmids and rng.random() < 0.1:
            plasmid = rng.choice(self.plasmids).copy()
            nodes = get_all_nodes(tree)
            if len(nodes) > 1:
                _, pn, idx = rng.choice(nodes[1:])
                if pn is not None:
                    pn.children[idx] = plasmid

        if tree.size() > 250:
            tree = parent['tree'].copy()

        # Mutate strategy
        new_strategy = copy.deepcopy(parent['strategy'])
        for k, v in new_strategy.items():
            if rng.random() < 0.15:
                scale = max(abs(v) * 0.3, 0.02)
                new_strategy[k] = max(0.0, min(1.0, v + rng.gauss(0, scale)))

        return {
            'tree': tree, 'objectives': [0.0, 0.0, 0.0],
            'scalar_fitness': 0.0, 'scores': {},
            'strategy': new_strategy, 'age': 0,
            'front_rank': 999, 'crowding_distance': 0.0,
        }

    def knee_point(self) -> dict:
        """Return the knee point organism (best balanced on Pareto front)."""
        fronts = self._nsga2_sort_and_assign()
        if not fronts or not fronts[0]:
            return max(self.organisms, key=lambda o: o['scalar_fitness'])
        idx = find_knee_point(self.organisms, fronts[0])
        return self.organisms[idx]

    def pareto_front(self) -> List[dict]:
        """Return all organisms on F0."""
        fronts = self._nsga2_sort_and_assign()
        if not fronts or not fronts[0]:
            return []
        return [self.organisms[idx] for idx in fronts[0]]

    def get_migrants(self, n):
        """Send knee point and top-front organisms as migrants."""
        fronts = self._nsga2_sort_and_assign()
        if not fronts or not fronts[0]:
            sorted_pop = sorted(self.organisms,
                                key=lambda o: o['scalar_fitness'], reverse=True)
            return [copy.deepcopy(o) for o in sorted_pop[:n]]

        # Knee point first, then others from F0 by crowding distance
        knee_idx = find_knee_point(self.organisms, fronts[0])
        migrants = [copy.deepcopy(self.organisms[knee_idx])]

        other_f0 = sorted(
            [i for i in fronts[0] if i != knee_idx],
            key=lambda i: self.organisms[i].get('crowding_distance', 0.0),
            reverse=True
        )
        for idx in other_f0[:n - 1]:
            migrants.append(copy.deepcopy(self.organisms[idx]))

        return migrants

    def accept_migrants(self, migrants):
        """Replace worst-ranked organisms with migrants."""
        # Sort by (front_rank ASC, crowding_distance DESC)
        sorted_indices = sorted(
            range(len(self.organisms)),
            key=lambda i: (
                self.organisms[i].get('front_rank', 999),
                -self.organisms[i].get('crowding_distance', 0.0)
            )
        )
        # Replace from the end (worst organisms)
        for i, m in enumerate(migrants):
            if len(sorted_indices) > len(migrants):
                replace_idx = sorted_indices[-(i + 1)]
                self.organisms[replace_idx] = m


# ============================================================================
# PARALLEL WORKER
# ============================================================================

def _run_island_batch(args):
    island, n_epochs = args
    for _ in range(n_epochs):
        island.evolve_one_epoch()

    # Compute final state
    island.evaluate_all(seed=42 + (island.epoch % 5))
    fronts = fast_non_dominated_sort(island.organisms)
    for front in fronts:
        crowding_distance(island.organisms, front)

    knee_idx = find_knee_point(island.organisms, fronts[0]) if fronts else 0
    knee = island.organisms[knee_idx]
    f0_size = len(fronts[0]) if fronts else 0

    # Best per objective
    best_per_obj = []
    for m in range(3):
        best_idx = max(range(len(island.organisms)),
                       key=lambda i: island.organisms[i]['objectives'][m])
        best_per_obj.append(island.organisms[best_idx]['objectives'][m])

    return island, {
        'knee_scalar': knee['scalar_fitness'],
        'knee_objectives': knee['objectives'],
        'knee_scores': knee['scores'],
        'knee_size': knee['tree'].size(),
        'knee_strategy': knee['strategy'],
        'f0_size': f0_size,
        'best_per_obj': best_per_obj,
        'stagnation': island.stagnation,
        'catastrophes': island.catastrophes,
        'epoch': island.epoch,
    }


# ============================================================================
# NSGA-II ENGINE
# ============================================================================

class NSGA2Engine:
    def __init__(self, n_islands=5, island_pop=40, cores=None, seed=222):
        self.n_islands = n_islands
        self.island_pop = island_pop
        self.cores = cores or max(1, mp.cpu_count() - 2)
        self.seed = seed
        self.rng = random.Random(seed)

        self.islands = []
        self.global_knee = None
        self.global_knee_scalar = 0.0
        self.generation = 0
        self.history = []

        self.save_path = os.path.join(TOOLS_DIR, 'exp7_nsga2_state.json')
        self.best_path = os.path.join(TOOLS_DIR, 'exp7_nsga2_best.json')
        self.front_path = os.path.join(TOOLS_DIR, 'exp7_nsga2_front.json')
        self.log_path = os.path.join(TOOLS_DIR, 'exp7_nsga2_log.jsonl')

    def initialize(self):
        transplants = load_transplants()

        self.islands = []
        for i in range(self.n_islands):
            island = NSGA2Island(i, self.island_pop,
                                  seed=self.seed + i * 1000)
            scaffold_rate = 0.4 + (i % 4) * 0.1
            island.initialize(scaffold_rate=scaffold_rate,
                              transplants=transplants)
            self.islands.append(island)

    def run(self):
        self.initialize()

        running = [True]

        def handler(sig, frame):
            print(f"\n[SIGNAL] Saving and stopping...")
            running[0] = False

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        OBJ_NAMES = ['mem_hmean', 'sr_hmean', 'rea_mean']

        print(f"\n{'=' * 74}")
        print(f"  NSGA-II MULTI-OBJECTIVE EVOLUTION (exp7)")
        print(f"{'=' * 74}")
        print(f"  Islands:     {self.n_islands}")
        print(f"  Pop/island:  {self.island_pop}")
        print(f"  Total:       {self.n_islands * self.island_pop} organisms")
        print(f"  Cores:       {self.cores}")
        print(f"  Objectives:  3 (memory_hmean, selfref_hmean, reasoning_mean)")
        print(f"  Selection:   NSGA-II (non-dominated sort + crowding)")
        print(f"  Tasks:")
        print(f"    Memory:    {', '.join(MEMORY_TASKS.keys())}")
        print(f"    Self-ref:  {', '.join(SELF_REF_TASKS.keys())}")
        print(f"    Reasoning: {', '.join(REASONING_TASKS.keys())}")
        print(f"  Scalar:      0.50*mem + 0.30*sr + 0.20*rea (for comparison)")
        print(f"  Hypothesis:  NSGA-II preserves specialists that harmonic")
        print(f"               mean aggregation would kill")
        print(f"{'=' * 74}\n")

        epochs_per_round = 10
        total_start = time.time()

        while running[0]:
            self.generation += 1
            round_start = time.time()

            work = [(island, epochs_per_round) for island in self.islands]

            if self.cores > 1 and self.n_islands > 1:
                with mp.Pool(processes=min(self.cores, self.n_islands)) as pool:
                    results = pool.map(_run_island_batch, work)
            else:
                results = [_run_island_batch(w) for w in work]

            self.islands = [r[0] for r in results]
            island_results = [r[1] for r in results]

            # Update global knee point
            for i, (island, res) in enumerate(zip(self.islands,
                                                   island_results)):
                if res['knee_scalar'] > self.global_knee_scalar:
                    knee_org = island.knee_point()
                    self.global_knee = {
                        'scalar_fitness': res['knee_scalar'],
                        'objectives': res['knee_objectives'],
                        'scores': res['knee_scores'],
                        'size': res['knee_size'],
                        'strategy': res['knee_strategy'],
                        'island': i,
                        'program': knee_org['tree'].to_str(),
                    }
                    self.global_knee_scalar = res['knee_scalar']

            # Migration (ring topology) -- sends knee point
            n_mig = max(1, self.island_pop // 10)
            migrants = [isl.get_migrants(n_mig) for isl in self.islands]
            for i, isl in enumerate(self.islands):
                source = (i - 1) % self.n_islands
                isl.accept_migrants(migrants[source])

            # Report
            round_time = time.time() - round_start
            total_epochs = self.generation * epochs_per_round

            print(f"  Round {self.generation} ({total_epochs} epochs,"
                  f" {round_time:.0f}s)")

            if self.global_knee:
                obj = self.global_knee['objectives']
                scores = self.global_knee['scores']
                print(f"  KNEE: scalar={self.global_knee_scalar:.4f}"
                      f"  obj=[{obj[0]:.3f}, {obj[1]:.3f}, {obj[2]:.3f}]")

                # Per-task breakdown of knee point
                mem_names = ['delayed_echo', 'sequential_xor', 'running_max',
                             'accumulator', 'state_switcher']
                sr_names = ['sequence_prediction', 'error_correction',
                            'novelty_detection']
                mem_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                  for n in mem_names)
                sr_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                 for n in sr_names)
                nav = scores.get('persistent_nav', 0)
                print(f"    mem: {mem_str}")
                print(f"    self: {sr_str}")
                rd_names = ['real_line_length', 'real_indentation',
                            'real_nesting']
                rd_str = '  '.join(
                    f"{lbl}={scores.get(n, 0):.2f}"
                    for n, lbl in zip(rd_names,
                                      ['line', 'indent', 'nest']))
                print(f"    real: {rd_str}")
                print(f"    nav={nav:.2f}  size={self.global_knee['size']}")

            # Per-island stats
            total_f0 = 0
            for i, res in enumerate(island_results):
                total_f0 += res['f0_size']
                cat = (f" [CAT x{res['catastrophes']}]"
                       if res['catastrophes'] else "")
                bpo = res['best_per_obj']
                print(f"    Isl {i}: knee={res['knee_scalar']:.4f}"
                      f"  |F0|={res['f0_size']:3d}"
                      f"  best=[{bpo[0]:.2f},{bpo[1]:.2f},{bpo[2]:.2f}]"
                      f"  stag={res['stagnation']:3d}{cat}")

            # Log
            entry = {
                'gen': self.generation,
                'epochs': total_epochs,
                'knee_scalar': self.global_knee_scalar,
                'knee_objectives': (self.global_knee.get('objectives', [])
                                    if self.global_knee else []),
                'knee_scores': (self.global_knee.get('scores', {})
                                if self.global_knee else {}),
                'total_f0': total_f0,
                'island_f0': [r['f0_size'] for r in island_results],
                'best_per_obj_per_island': [r['best_per_obj']
                                            for r in island_results],
                'time_s': round_time,
                'ts': time.strftime('%H:%M:%S'),
            }
            self.history.append(entry)
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')

            # Report to REST API
            report_generation(
                experiment_name='exp7_nsga2',
                generation=self.generation,
                best_fitness=self.global_knee_scalar,
                scores=self.global_knee.get('scores', {}) if self.global_knee else {},
                best_program_str=self.global_knee.get('program') if self.global_knee else None,
                metadata={
                    'objectives': self.global_knee.get('objectives', []) if self.global_knee else [],
                },
            )

            if self.generation % 5 == 0:
                self._save()

            sys.stdout.flush()

        self._save()
        elapsed = time.time() - total_start
        print(f"\n{'=' * 74}")
        print(f"  STOPPED -- {self.generation} rounds,"
              f" {self.generation * epochs_per_round} epochs, {elapsed:.0f}s")
        print(f"  Knee scalar: {self.global_knee_scalar:.4f}")
        if self.global_knee:
            obj = self.global_knee['objectives']
            print(f"  Objectives: mem={obj[0]:.4f} sr={obj[1]:.4f}"
                  f" rea={obj[2]:.4f}")
            print(f"  Scores:")
            for k, v in sorted(self.global_knee['scores'].items()):
                print(f"    {k:25s}: {v:.4f}")
            print(f"  Strategy:")
            for k, v in sorted(self.global_knee['strategy'].items()):
                print(f"    {k:25s}: {v:.4f}")
        print(f"{'=' * 74}")

    def _save(self):
        state = {
            'generation': self.generation,
            'global_knee': self.global_knee,
            'global_knee_scalar': self.global_knee_scalar,
            'history': self.history[-100:],
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        with open(self.save_path, 'w') as f:
            json.dump(state, f, indent=2)

        if self.global_knee:
            with open(self.best_path, 'w') as f:
                json.dump(self.global_knee, f, indent=2)

        # Save full Pareto front from all islands
        all_front = []
        for island in self.islands:
            pf = island.pareto_front()
            for org in pf:
                all_front.append({
                    'objectives': org['objectives'],
                    'scalar_fitness': org['scalar_fitness'],
                    'scores': org['scores'],
                    'size': org['tree'].size(),
                    'program': org['tree'].to_str(),
                })
        with open(self.front_path, 'w') as f:
            json.dump({
                'generation': self.generation,
                'front_size': len(all_front),
                'organisms': all_front,
                'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='GA Experiment 7: NSGA-II Multi-Objective Evolution')
    parser.add_argument('--islands', type=int, default=5)
    parser.add_argument('--island-pop', type=int, default=40)
    parser.add_argument('--cores', type=int, default=3)
    parser.add_argument('--seed', type=int, default=222)
    args = parser.parse_args()

    engine = NSGA2Engine(
        n_islands=args.islands,
        island_pop=args.island_pop,
        cores=args.cores,
        seed=args.seed,
    )
    engine.run()


if __name__ == '__main__':
    main()
