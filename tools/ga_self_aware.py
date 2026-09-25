#!/usr/bin/env python3
from __future__ import annotations
"""GA Evolution with Self-Referential Awareness Pressure (v3)

Builds on v2's memory-mandatory landscape by adding instruction set
extensions that enable recursive self-reference — organisms that can
monitor their own outputs, predict future inputs, and detect surprise.

New ops (4):
  STEP       - returns current step number / 10 (temporal self-awareness)
  LAST_OUT   - returns organism's own last output on channel arg0
  PREDICT    - stores a prediction: prediction_reg[arg0] = arg1
  SURPRISE   - returns |prediction[arg0] - input[arg0]| (prediction error)

New tasks (selecting for self-reference):
  SequencePrediction   - predict next value in repeating pattern
  ErrorCorrection      - use error feedback + LAST_OUT to converge on target
  NoveltyDetection     - detect oddball in regular pattern using SURPRISE

All v2 memory tasks retained as baseline.

Usage:
    python3 ga_self_aware.py              # run
    python3 ga_self_aware.py --cores 14   # max parallelism
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

from ga_result_reporter import report_generation


# ============================================================================
# EXTENDED OP SET — original 28 + 4 self-referential
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

# Subset: only the original ops (for compatibility with v2 tasks)
MEMORY_OPS = {Op.READ, Op.WRITE}
SELF_REF_OPS = {Op.STEP, Op.LAST_OUT, Op.PREDICT, Op.SURPRISE}
LEARNING_OPS = {Op.LEARN, Op.RECALL, Op.STRENGTHEN, Op.WEAKEN, Op.DEFINE, Op.INVOKE}

OP_NAMES = {op.name: op for op in Op}


# ============================================================================
# PROGRAM PARSER — reconstruct trees from text representation
# ============================================================================

def parse_program(text: str) -> Optional[Node]:
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


def _parse_node(tokens: List[str], pos: int) -> Tuple[Node, int]:
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
        self.step_number = 0  # global step (preserved across advance_step)
        self.halted = False
        # Lifetime learning state (v4)
        self.learn_regs = [0.0] * self.NUM_LEARN_REGS
        self.hebbian_weights = {}
        self.closures = [None] * self.NUM_CLOSURES
        self.invoke_depth = 0

    def advance_step(self):
        """Between task steps: save outputs, increment global step, reset exec budget."""
        self.last_outputs = self.outputs.copy()
        self.step_number += 1
        self.steps = 0
        self.outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        for k in self.hebbian_weights:
            self.hebbian_weights[k] *= 0.99

    def reset_for_trial(self):
        """Full reset between trials."""
        self.registers = [0.0] * self.NUM_REGISTERS
        self.inputs = [0.0] * self.NUM_INPUT_CHANNELS
        self.outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.predictions = [0.0] * self.NUM_PREDICTIONS
        self.last_outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.steps = 0
        self.step_number = 0
        self.halted = False
        self.learn_regs = [0.0] * self.NUM_LEARN_REGS
        self.hebbian_weights = {}
        self.closures = [None] * self.NUM_CLOSURES
        self.invoke_depth = 0


# ============================================================================
# EXECUTE — handles all ops including self-referential
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
    """Generate random program tree with self-aware op bias."""
    if max_depth <= 1:
        if rng.random() < self_aware_bias and rng.random() < 0.5:
            return Node(op=Op.STEP)
        op = rng.choice(TERMINAL_OPS)
        if op == Op.CONST:
            return Node(op=op, value=rng.uniform(-5, 5))
        return Node(op=op)

    # Bias toward self-referential and learning ops
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
    """Get all nodes as (node, parent, child_index) tuples."""
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
# V2 MEMORY TASKS (baseline — must still solve these)
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

        # Step 0: present target
        ctx.inputs = [target, 1.0, 0.0, float(delay), 0, 0, 0, 0]
        execute(tree, ctx)

        # Noise steps
        noise_outputs = []
        for i, n_val in enumerate(noise):
            ctx.advance_step()
            ctx.inputs = [n_val, 0.0, float(i + 1), float(delay), 0, 0, 0, 0]
            execute(tree, ctx)
            noise_outputs.append(ctx.outputs[0])

        # Recall step
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
# NEW SELF-REFERENTIAL TASKS
# ============================================================================

class SequencePredictionTask:
    """Predict the next value in a repeating pattern.

    A short pattern (length 2-4) repeats. The organism must learn
    the pattern and predict what comes next.

    Each step: input ch0 = current value in pattern
    Expected: output ch0 = NEXT value in pattern

    Requires: memory (store pattern), prediction (anticipate next),
              temporal awareness (know position in cycle)

    IMPOSSIBLE without memory + self-referential ops.
    A pure reactive program can't predict what hasn't been seen yet.
    """
    name = "sequence_prediction"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            pattern_len = rng.randint(2, 4)
            pattern = [round(rng.uniform(-3, 3), 1) for _ in range(pattern_len)]
            n_cycles = rng.randint(2, 4)
            sequence = pattern * n_cycles
            # Expected prediction at each step: the NEXT value
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
        # Skip first cycle (organism hasn't seen pattern yet)
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
    """Converge on a hidden target using error feedback.

    Step 0: organism outputs initial guess (no information given)
    Step 1+: input ch0 = error = target - last_output (with noise)
             input ch1 = 1.0 (feedback available signal)

    The perfect strategy: new_output = LAST_OUT(0) + SENSE(0)
    This equals: last_output + (target - last_output) = target

    But error has noise (±0.3), so the organism must iteratively refine.
    Organisms with LAST_OUT can implement: output = last_output + error
    Organisms without LAST_OUT must somehow remember their own output.

    Score: 1.0 - (final_error / initial_distance), averaged over later steps
    """
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

        # Step 0: blind guess
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
    """Detect an oddball in a regular pattern.

    Regular pattern plays for N steps. At one random step, an oddball
    breaks the pattern. The organism must output:
      ch0 = 0.0 for regular steps
      ch0 = 1.0 when oddball detected

    The ideal strategy:
      1. PREDICT what the next input should be
      2. Check SURPRISE — if high, output 1.0
      3. Otherwise output 0.0

    Score: 2 * sensitivity * specificity / (sensitivity + specificity)
           (F1 of detection)

    IMPOSSIBLE without prediction + surprise detection.
    A reactive program can't know if the current value is "unusual"
    without a model of what's "usual."
    """
    name = "novelty_detection"

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            # Regular pattern: alternating or constant
            if rng.random() < 0.5:
                base_val = round(rng.uniform(-3, 3), 1)
                pattern = [base_val]
            else:
                v1, v2 = round(rng.uniform(-3, 3), 1), round(rng.uniform(-3, 3), 1)
                pattern = [v1, v2]

            n_total = rng.randint(8, 15)
            sequence = [pattern[i % len(pattern)] for i in range(n_total)]

            # Insert oddball after warmup
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
                continue  # skip warmup for scoring

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

ALL_TASKS = {**MEMORY_TASKS, **SELF_REF_TASKS, **REASONING_TASKS}


# ============================================================================
# EVALUATION
# ============================================================================

def evaluate_organism(tree: Node, tasks: dict, n_trials: int = 10,
                      seed: int = 42) -> dict:
    scores = {}
    for name, task in tasks.items():
        rng = random.Random(seed)
        trials = task.generate_trials(n_trials, rng)
        trial_scores = [task.evaluate(tree, trial) for trial in trials]
        scores[name] = float(np.mean(trial_scores))
    return scores


def compute_fitness(scores: dict) -> float:
    """Four-tier harmonic mean fitness.
    40% memory + 25% self-ref + 15% reasoning + 20% real data
    """
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

    fitness = 0.30 * mem_hmean + 0.10 * sr_hmean + 0.40 * rea_mean + 0.20 * rd_hmean
    rd_contrib = 0.20 * rd_hmean
    rd_pct = (rd_contrib / fitness * 100) if fitness > 0 else 0
    print(f"    [real_data] raw={rd_hmean:.4f}  contrib={rd_contrib:.4f}  pct={rd_pct:.1f}%")
    return fitness


# ============================================================================
# SELF-AWARE SEED PATTERNS
# ============================================================================

def self_aware_seed(rng: random.Random) -> Node:
    """Generate trees with self-referential and learning patterns baked in."""
    pattern = rng.randint(0, 19)

    if pattern == 0:
        # PREDICT-AND-CHECK: predict next input = current input, check surprise
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
                    Node(op=Op.ONE),   # surprise > 1 → novelty
                    Node(op=Op.ZERO)   # no surprise → normal
                ])
            ])
        ])

    elif pattern == 1:
        # ERROR CORRECTION: output = last_output + error_signal
        return Node(op=Op.ACT, children=[
            Node(op=Op.ZERO),
            Node(op=Op.ADD, children=[
                Node(op=Op.LAST_OUT, children=[Node(op=Op.ZERO)]),
                Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
            ])
        ])

    elif pattern == 2:
        # TEMPORAL MEMORY: store during early steps, recall later
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
        # SURPRISE-GATED STORAGE: only update model on surprising input
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
        # SIGNAL-GATED STORE (from v2 delayed echo)
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
        # RUNNING MAX (from v2)
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
        # COUNTER (from v2)
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
        # STATE MACHINE (from v2)
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
        # XOR MEMORY (from v2)
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
        # PREDICTIVE SEQUENCE LEARNER: store pattern, predict next
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
        # SELF-CORRECTING: use LAST_OUT and error signal
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

    # === COMPOSITE PATTERNS (v4 hybrid): memory + self-reference combined ===

    elif pattern == 11:
        # SURPRISE-GATED RUNNING MAX: predict max, update only when surprised
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
        # SELF-CORRECTING COUNTER: count + use LAST_OUT to detect errors
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
        # TEMPORAL NAVIGATOR: use STEP + LAST_OUT for path tracking
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
        # PREDICTIVE DELAYED ECHO: signal-gated store with PREDICT/SURPRISE
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

    elif pattern == 15:
        # LEARN-FROM-ERROR: observe surprise, store correction in learn register
        lr = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.LEARN, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.SURPRISE, children=[Node(op=Op.ZERO)]),
                    Node(op=Op.CONST, value=0.3)
                ]),
                lr,
                Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.ADD, children=[
                    Node(op=Op.RECALL, children=[lr.copy()]),
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ])
            ])
        ])

    elif pattern == 16:
        # ADAPTIVE LOOKUP TABLE: learn mapping from step to value
        return Node(op=Op.SEQ, children=[
            Node(op=Op.LEARN, children=[
                Node(op=Op.ONE),
                Node(op=Op.MOD, children=[
                    Node(op=Op.MUL, children=[
                        Node(op=Op.STEP),
                        Node(op=Op.CONST, value=10.0)
                    ]),
                    Node(op=Op.CONST, value=8.0)
                ]),
                Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.RECALL, children=[
                    Node(op=Op.MOD, children=[
                        Node(op=Op.MUL, children=[
                            Node(op=Op.ADD, children=[
                                Node(op=Op.STEP),
                                Node(op=Op.CONST, value=0.1)
                            ]),
                            Node(op=Op.CONST, value=10.0)
                        ]),
                        Node(op=Op.CONST, value=8.0)
                    ])
                ])
            ])
        ])

    elif pattern == 17:
        # HEBBIAN REINFORCEMENT: strengthen paths that reduce surprise
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.LT, children=[
                    Node(op=Op.SURPRISE, children=[Node(op=Op.ZERO)]),
                    Node(op=Op.CONST, value=0.5)
                ]),
                Node(op=Op.STRENGTHEN, children=[Node(op=Op.ONE)]),
                Node(op=Op.WEAKEN, children=[Node(op=Op.ONE)])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.PREDICT, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ])
            ])
        ])

    elif pattern == 18:
        # DEFINE-AND-INVOKE: define a prediction function, invoke it
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.LT, children=[
                    Node(op=Op.STEP),
                    Node(op=Op.CONST, value=0.1)
                ]),
                Node(op=Op.DEFINE, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.ADD, children=[
                        Node(op=Op.SENSE, children=[Node(op=Op.ZERO)]),
                        Node(op=Op.READ, children=[Node(op=Op.ZERO)])
                    ])
                ]),
                Node(op=Op.ZERO)
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.INVOKE, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ])
            ])
        ])

    else:
        # SURPRISE-GATED STATE MACHINE: state + novelty detection
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
# ISLAND
# ============================================================================

def load_transplants() -> List[Node]:
    """Load best organisms from any experiment's *_best.json files."""
    transplants = []
    import glob
    search_dirs = [TOOLS_DIR, os.getcwd()]
    seen = set()
    for d in search_dirs:
        for path in glob.glob(os.path.join(d, '*_best.json')):
            basename = os.path.basename(path)
            if basename in seen:
                continue
            seen.add(basename)
            try:
                with open(path) as f:
                    data = json.load(f)
                prog_text = data.get('program', '')
                if not prog_text:
                    continue
                tree = parse_program(prog_text)
                if tree and tree.size() > 3:
                    transplants.append(tree)
                    print(f"  Loaded transplant from {basename}:"
                          f" {tree.size()} nodes, fit={data.get('fitness', '?')}")
            except (FileNotFoundError, json.JSONDecodeError):
                pass
    return transplants


class SelfAwareIsland:
    def __init__(self, island_id: int, pop_size: int, seed: int):
        self.id = island_id
        self.pop_size = pop_size
        self.rng = random.Random(seed)
        self.organisms = []
        self.plasmids = []
        self.epoch = 0
        self.best_fitness = 0.0
        self.stagnation = 0
        self.catastrophes = 0

    def initialize(self, scaffold_rate: float = 0.5,
                   transplants: Optional[List[Node]] = None):
        self.organisms = []
        rng = self.rng

        # Inject transplants into first few islands
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
                    'tree': tree, 'fitness': 0.0, 'scores': {},
                    'strategy': strategy, 'age': 0,
                })
                # Also create mutated variants of each transplant
                for _ in range(2):
                    variant = point_mutation(tree, rng, rate=0.2)
                    self.organisms.append({
                        'tree': variant, 'fitness': 0.0, 'scores': {},
                        'strategy': copy.deepcopy(strategy), 'age': 0,
                    })

            # Cross transplants if we have at least 2
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
                        'tree': hybrid, 'fitness': 0.0, 'scores': {},
                        'strategy': strategy, 'age': 0,
                    })

        # Fill remaining with scaffolded + random
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
                'tree': tree, 'fitness': 0.0, 'scores': {},
                'strategy': strategy, 'age': 0,
            })

    def evaluate_all(self, seed: int = 42):
        for org in self.organisms:
            org['scores'] = evaluate_organism(
                org['tree'], ALL_TASKS, n_trials=8, seed=seed
            )
            org['fitness'] = compute_fitness(org['scores'])

    def evolve_one_epoch(self):
        self.epoch += 1
        rng = self.rng

        self.evaluate_all(seed=42 + (self.epoch % 5))
        self.organisms.sort(key=lambda o: o['fitness'], reverse=True)

        cur_best = self.organisms[0]['fitness']
        if cur_best > self.best_fitness:
            self.best_fitness = cur_best
            self.stagnation = 0
        else:
            self.stagnation += 1

        # Catastrophe
        if self.stagnation > 64:
            keep = max(3, self.pop_size // 5)
            self.organisms = self.organisms[:keep]
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
                    'tree': tree, 'fitness': 0.0, 'scores': {},
                    'strategy': strategy, 'age': 0
                })
            self.catastrophes += 1
            self.stagnation = 0
            return

        # Plasmid pool: prefer memory + self-ref subtrees
        for org in self.organisms[:3]:
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

        # Breed
        new_pop = [self.organisms[0], self.organisms[1]]

        while len(new_pop) < self.pop_size:
            child = self._breed(rng)
            new_pop.append(child)

        self.organisms = new_pop
        for org in self.organisms:
            org['age'] += 1

    def _breed(self, rng) -> dict:
        parent = self._tournament(rng, k=4)
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
                other = self._tournament(rng, k=3)
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
                    other = self._tournament(rng, k=3)
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
            'tree': tree, 'fitness': 0.0, 'scores': {},
            'strategy': new_strategy, 'age': 0,
        }

    def _tournament(self, rng, k=4):
        return max(rng.sample(self.organisms, min(k, len(self.organisms))),
                   key=lambda o: o['fitness'])

    def best(self):
        return max(self.organisms, key=lambda o: o['fitness'])

    def get_migrants(self, n):
        self.organisms.sort(key=lambda o: o['fitness'], reverse=True)
        return [copy.deepcopy(o) for o in self.organisms[:n]]

    def accept_migrants(self, migrants):
        self.organisms.sort(key=lambda o: o['fitness'], reverse=True)
        for i, m in enumerate(migrants):
            if len(self.organisms) > len(migrants):
                self.organisms[-(i + 1)] = m


# ============================================================================
# PARALLEL WORKER
# ============================================================================

def _run_island_batch(args):
    island, n_epochs = args
    for _ in range(n_epochs):
        island.evolve_one_epoch()
    best = island.best()
    return island, {
        'fitness': best['fitness'],
        'scores': best['scores'],
        'size': best['tree'].size(),
        'strategy': best['strategy'],
        'stagnation': island.stagnation,
        'catastrophes': island.catastrophes,
        'epoch': island.epoch,
    }


# ============================================================================
# SELF-AWARE ENGINE
# ============================================================================

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


class SelfAwareEngine:
    def __init__(self, n_islands=7, island_pop=50, cores=None, seed=42,
                 hybrid=False):
        self.n_islands = n_islands
        self.island_pop = island_pop
        self.cores = cores or max(1, mp.cpu_count() - 2)
        self.seed = seed
        self.rng = random.Random(seed)

        self.islands = []
        self.global_best = None
        self.global_best_fitness = 0.0
        self.generation = 0
        self.history = []

        self.hybrid = hybrid
        tag = 'hybrid' if hybrid else 'self_aware'
        self.save_path = os.path.join(TOOLS_DIR, f'{tag}_state.json')
        self.best_path = os.path.join(TOOLS_DIR, f'{tag}_best.json')
        self.log_path = os.path.join(TOOLS_DIR, f'{tag}_log.jsonl')

    def initialize(self):
        transplants = load_transplants() if self.hybrid else []

        self.islands = []
        for i in range(self.n_islands):
            island = SelfAwareIsland(i, self.island_pop,
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

        version = "HYBRID EVOLUTION (v4)" if self.hybrid else "SELF-AWARE EVOLUTION (v3)"
        print(f"\n{'=' * 70}")
        print(f"  {version}")
        print(f"{'=' * 70}")
        print(f"  Islands:     {self.n_islands}")
        print(f"  Pop/island:  {self.island_pop}")
        print(f"  Total:       {self.n_islands * self.island_pop} organisms")
        print(f"  Cores:       {self.cores}")
        print(f"  New ops:     STEP, LAST_OUT, PREDICT, SURPRISE")
        print(f"  Tasks:")
        print(f"    Memory:    {', '.join(MEMORY_TASKS.keys())}")
        print(f"    Self-ref:  {', '.join(SELF_REF_TASKS.keys())}")
        print(f"    Reasoning: {', '.join(REASONING_TASKS.keys())}")
        print(f"  Fitness:     50% hmean(memory) + 30% hmean(self-ref)"
              f" + 20% reasoning")
        n_seeds = 16
        print(f"  Size limit:  250 nodes  |  Seed patterns: {n_seeds}")
        if self.hybrid:
            print(f"  Mode:        HYBRID — v2 memory + v3 self-ref transplants")
        print(f"{'=' * 70}\n")

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

            for i, (island, res) in enumerate(zip(self.islands,
                                                   island_results)):
                if res['fitness'] > self.global_best_fitness:
                    best_org = island.best()
                    self.global_best = {
                        'fitness': res['fitness'],
                        'scores': res['scores'],
                        'size': res['size'],
                        'strategy': res['strategy'],
                        'island': i,
                        'program': best_org['tree'].to_str(),
                    }
                    self.global_best_fitness = res['fitness']

            # Migration (ring topology)
            n_mig = max(2, self.island_pop // 5)
            migrants = [isl.get_migrants(n_mig) for isl in self.islands]
            for i, isl in enumerate(self.islands):
                source = (i - 1) % self.n_islands
                isl.accept_migrants(migrants[source])

            # Report
            round_time = time.time() - round_start
            total_epochs = self.generation * epochs_per_round

            print(f"  Round {self.generation} ({total_epochs} epochs,"
                  f" {round_time:.0f}s)")

            if self.global_best:
                scores = self.global_best['scores']
                mem_names = ['delayed_echo', 'sequential_xor', 'running_max',
                             'accumulator', 'state_switcher']
                sr_names = ['sequence_prediction', 'error_correction',
                            'novelty_detection']
                mem_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                  for n in mem_names)
                sr_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                 for n in sr_names)
                nav = scores.get('persistent_nav', 0)
                print(f"  BEST: fit={self.global_best_fitness:.4f}"
                      f"  nav={nav:.2f}")
                print(f"    mem: {mem_str}")
                print(f"    self: {sr_str}")
                rd_names = ['real_line_length', 'real_indentation',
                            'real_nesting']
                rd_str = '  '.join(
                    f"{lbl}={scores.get(n, 0):.2f}"
                    for n, lbl in zip(rd_names,
                                      ['line', 'indent', 'nest']))
                print(f"    real: {rd_str}")

                # Count self-ref ops in best organism
                tree = island.best()['tree'] if res['fitness'] == self.global_best_fitness else None
                if tree:
                    sa_count = count_ops(tree, SELF_REF_OPS)
                    mem_count = count_ops(tree, MEMORY_OPS)
                    print(f"    ops: mem={mem_count} self_ref={sa_count}"
                          f" size={self.global_best['size']}")

            for i, res in enumerate(island_results):
                cat = (f" [CAT×{res['catastrophes']}]"
                       if res['catastrophes'] else "")
                print(f"    Isl {i}: fit={res['fitness']:.4f}"
                      f"  stag={res['stagnation']:3d}{cat}")

            # Log
            entry = {
                'gen': self.generation,
                'epochs': total_epochs,
                'best_fitness': self.global_best_fitness,
                'scores': (self.global_best.get('scores', {})
                           if self.global_best else {}),
                'best_strategy': (self.global_best.get('strategy', {})
                                  if self.global_best else {}),
                'time_s': round_time,
                'ts': time.strftime('%H:%M:%S'),
            }
            self.history.append(entry)
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')

            # Report to REST API
            exp_name = 'hybrid' if self.hybrid else 'self_aware'
            report_generation(
                experiment_name=exp_name,
                generation=self.generation,
                best_fitness=self.global_best_fitness,
                scores=self.global_best.get('scores', {}) if self.global_best else {},
                best_program_str=self.global_best.get('program') if self.global_best else None,
            )

            if self.generation % 5 == 0:
                self._save()

            sys.stdout.flush()

        self._save()
        elapsed = time.time() - total_start
        print(f"\n{'=' * 70}")
        print(f"  STOPPED — {self.generation} rounds,"
              f" {self.generation * epochs_per_round} epochs, {elapsed:.0f}s")
        print(f"  Best fitness: {self.global_best_fitness:.4f}")
        if self.global_best:
            print(f"  Scores:")
            for k, v in sorted(self.global_best['scores'].items()):
                print(f"    {k:25s}: {v:.4f}")
            print(f"  Strategy:")
            for k, v in sorted(self.global_best['strategy'].items()):
                print(f"    {k:25s}: {v:.4f}")
        print(f"{'=' * 70}")

    def _save(self):
        state = {
            'generation': self.generation,
            'global_best': self.global_best,
            'global_best_fitness': self.global_best_fitness,
            'history': self.history[-100:],
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        with open(self.save_path, 'w') as f:
            json.dump(state, f, indent=2)
        if self.global_best:
            with open(self.best_path, 'w') as f:
                json.dump(self.global_best, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='Self-Aware GA Evolution (v3/v4 hybrid)')
    parser.add_argument('--islands', type=int, default=7)
    parser.add_argument('--island-pop', type=int, default=50)
    parser.add_argument('--cores', type=int, default=None)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--hybrid', action='store_true',
                        help='Load v2/v3 best organisms as transplants')
    args = parser.parse_args()

    engine = SelfAwareEngine(
        n_islands=args.islands,
        island_pop=args.island_pop,
        cores=args.cores,
        seed=args.seed,
        hybrid=args.hybrid,
    )
    engine.run()


if __name__ == '__main__':
    main()
