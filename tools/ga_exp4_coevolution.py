#!/usr/bin/env python3
"""GA Coevolution Experiment (exp4) — Competitive Coevolution with Two Populations

Fork of ga_self_aware.py (v3/v4) that adds competitive coevolution:
- Solvers (3 islands, 30 pop each): same 32-op organisms evaluated on BOTH
  static tasks AND generator-produced challenges.
- Generators (2 islands, 20 pop each): produce adversarial input sequences
  that exploit solver weaknesses. Rewarded when solvers FAIL.

Arms race dynamics push solvers toward robust, general solutions while
generators discover novel failure modes.

Hypothesis: adversarial coevolution discovers more general solutions than
the static-task-only fitness landscape.

Three dynamic challenge modes generators can create:
  echo_challenge       — solver must echo a sequence after variable delay
  accumulate_challenge  — solver must track running sum with noise/resets
  change_detect         — solver must detect change points in a signal

Solver fitness:  0.40 * static_fitness + 0.60 * coevolution_score
Generator fitness: 1.0 - avg_solver_score + diversity_bonus

Save files:
  exp4_coev_state.json         — checkpoint
  exp4_coev_solver_best.json   — best solver organism
  exp4_coev_generator_best.json — best generator organism
  exp4_coev_log.jsonl           — per-round metrics

Usage:
    python3 ga_exp4_coevolution.py --cores 8
    python3 ga_exp4_coevolution.py --islands 7 --island-pop 40 --cores 16
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
# EXTENDED OP SET — original 28 + 4 self-referential (32 total)
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

    # === SELF-REFERENTIAL OPS (v3) ===
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
# PROGRAM PARSER — reconstruct trees from text representation
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
# SELF-AWARE EXECUTION CONTEXT (used by solvers)
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
        """Between task steps: save outputs, increment global step, reset exec budget."""
        self.last_outputs = self.outputs.copy()
        self.step_number += 1
        self.steps = 0
        self.outputs = [0.0] * self.NUM_OUTPUT_CHANNELS

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


# ============================================================================
# EXECUTE — handles all 32 ops including self-referential
# ============================================================================

def execute(node: Node, ctx) -> float:
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

    # Bias toward self-referential ops
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
# V2 MEMORY TASKS (baseline — solvers must still solve these)
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
# SELF-REFERENTIAL TASKS
# ============================================================================

class SequencePredictionTask:
    """Predict the next value in a repeating pattern."""
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
    """Converge on a hidden target using error feedback."""
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
    """Detect an oddball in a regular pattern."""
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
# STATIC EVALUATION
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
    """Three-tier harmonic mean fitness.
    50% memory (harmonic) + 30% self-reference (harmonic) + 20% reasoning
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

    return 0.30 * mem_hmean + 0.10 * sr_hmean + 0.40 * rea_mean + 0.20 * rd_hmean


# ============================================================================
# SELF-AWARE SEED PATTERNS (for solvers)
# ============================================================================

def self_aware_seed(rng: random.Random) -> Node:
    """Generate trees with self-referential patterns baked in."""
    pattern = rng.randint(0, 15)

    if pattern == 0:
        # PREDICT-AND-CHECK
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
        # ERROR CORRECTION: output = last_output + error_signal
        return Node(op=Op.ACT, children=[
            Node(op=Op.ZERO),
            Node(op=Op.ADD, children=[
                Node(op=Op.LAST_OUT, children=[Node(op=Op.ZERO)]),
                Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
            ])
        ])

    elif pattern == 2:
        # TEMPORAL MEMORY
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
        # SURPRISE-GATED STORAGE
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
        # SIGNAL-GATED STORE
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
        # RUNNING MAX
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
        # COUNTER
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
        # STATE MACHINE
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
        # XOR MEMORY
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
        # PREDICTIVE SEQUENCE LEARNER
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
        # SELF-CORRECTING
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
        # SURPRISE-GATED RUNNING MAX
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
        # SELF-CORRECTING COUNTER
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
        # TEMPORAL NAVIGATOR
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
        # PREDICTIVE DELAYED ECHO
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
        # SURPRISE-GATED STATE MACHINE
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
# LOAD TRANSPLANTS FROM PREVIOUS RUNS
# ============================================================================

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_transplants() -> List[Node]:
    """Load best organisms from v2/v3/v4 runs for cross-pollination."""
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


# ============================================================================
# GENERATOR CONTEXT — simplified execution context for generators
# ============================================================================

class GeneratorContext:
    """Simplified context for generator organisms.
    4 registers (vs 16 for solvers), no prediction system.
    Generators produce challenge parameters through return values and
    register side-effects.
    """
    MAX_STEPS = 300
    NUM_REGISTERS = 4
    NUM_INPUT_CHANNELS = 4
    NUM_OUTPUT_CHANNELS = 4
    NUM_PREDICTIONS = 4

    def __init__(self):
        self.registers = [0.0] * self.NUM_REGISTERS
        self.inputs = [0.0] * self.NUM_INPUT_CHANNELS
        self.outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.predictions = [0.0] * self.NUM_PREDICTIONS
        self.last_outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.steps = 0
        self.step_number = 0
        self.halted = False

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
# GENERATOR OP SUBSET — restricted to 14 ops
# ============================================================================

GENERATOR_OPS_SET = {
    Op.ADD, Op.SUB, Op.MUL, Op.DIV,     # arithmetic (4)
    Op.CONST, Op.ZERO, Op.ONE, Op.NEG1,  # constants (4)
    Op.ABS,                               # unary (1)
    Op.SENSE,                             # input (1)
    Op.READ, Op.WRITE,                    # memory (2)
    Op.IF,                                # control (1)
    Op.STEP,                              # temporal (1)
}  # 14 ops total

GENERATOR_TERMINAL_OPS = [op for op in GENERATOR_OPS_SET if ARITY[op] == 0]
GENERATOR_UNARY_OPS = [op for op in GENERATOR_OPS_SET if ARITY[op] == 1]
GENERATOR_BINARY_OPS = [op for op in GENERATOR_OPS_SET if ARITY[op] == 2]
GENERATOR_TERNARY_OPS = [op for op in GENERATOR_OPS_SET if ARITY[op] == 3]


# ============================================================================
# GENERATOR TREE UTILITIES
# ============================================================================

def random_generator_tree(rng: random.Random, max_depth: int = 4) -> Node:
    """Generate random tree using only generator ops."""
    if max_depth <= 1:
        op = rng.choice(GENERATOR_TERMINAL_OPS)
        if op == Op.CONST:
            return Node(op=op, value=rng.uniform(-5, 5))
        return Node(op=op)

    r = rng.random()
    if r < 0.25:
        op = rng.choice(GENERATOR_TERMINAL_OPS)
    elif r < 0.45:
        op = rng.choice(GENERATOR_UNARY_OPS) if GENERATOR_UNARY_OPS else rng.choice(GENERATOR_TERMINAL_OPS)
    elif r < 0.80:
        op = rng.choice(GENERATOR_BINARY_OPS) if GENERATOR_BINARY_OPS else rng.choice(GENERATOR_TERMINAL_OPS)
    else:
        op = rng.choice(GENERATOR_TERNARY_OPS) if GENERATOR_TERNARY_OPS else rng.choice(GENERATOR_BINARY_OPS)

    arity = ARITY[op]
    if arity == 0:
        if op == Op.CONST:
            return Node(op=op, value=rng.uniform(-5, 5))
        return Node(op=op)

    children = [random_generator_tree(rng, max_depth - 1) for _ in range(arity)]
    return Node(op=op, children=children)


def point_mutation_generator(tree: Node, rng: random.Random,
                             rate: float = 0.15) -> Node:
    """Point mutation restricted to generator ops."""
    child = tree.copy()
    nodes = get_all_nodes(child)
    for node, _, _ in nodes:
        if rng.random() < rate:
            arity = ARITY[node.op]
            candidates = [op for op in GENERATOR_OPS_SET if ARITY[op] == arity]
            if candidates:
                node.op = rng.choice(candidates)
                if node.op == Op.CONST:
                    node.value = rng.uniform(-5, 5)
    return child


def subtree_mutation_generator(tree: Node, rng: random.Random) -> Node:
    """Subtree mutation using generator-only trees."""
    child = tree.copy()
    nodes = get_all_nodes(child)
    if len(nodes) > 1:
        _, p, i = rng.choice(nodes[1:])
        if p is not None:
            new_sub = random_generator_tree(rng, max_depth=3)
            p.children[i] = new_sub
    return child


# ============================================================================
# GENERATOR SEED PATTERNS
# ============================================================================

def generator_seed(rng: random.Random) -> Node:
    """Hand-crafted generator patterns that produce interesting challenges."""
    pattern = rng.randint(0, 7)

    if pattern == 0:
        # RAMP: output increases linearly with step
        # Returns STEP * scale_factor
        scale = rng.uniform(2.0, 8.0)
        return Node(op=Op.MUL, children=[
            Node(op=Op.STEP),
            Node(op=Op.CONST, value=scale)
        ])

    elif pattern == 1:
        # ALTERNATING: flip sign each step using register toggle
        # reg0 = -reg0 each step, output reg0
        reg = Node(op=Op.ZERO)
        amplitude = rng.uniform(1.0, 5.0)
        return Node(op=Op.WRITE, children=[
            reg,
            Node(op=Op.MUL, children=[
                Node(op=Op.SUB, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.IF, children=[
                        Node(op=Op.READ, children=[reg.copy()]),
                        Node(op=Op.CONST, value=amplitude),
                        Node(op=Op.CONST, value=-amplitude)
                    ])
                ]),
                Node(op=Op.ONE)
            ])
        ])

    elif pattern == 2:
        # NOISE WRITER: stores noise flag in register 0 based on step
        # Writes 1.0 to reg0 every 3rd step (noise marker)
        reg_noise = Node(op=Op.ZERO)
        reg_val = Node(op=Op.ONE)
        return Node(op=Op.IF, children=[
            Node(op=Op.ABS, children=[
                Node(op=Op.SUB, children=[
                    Node(op=Op.MUL, children=[
                        Node(op=Op.STEP),
                        Node(op=Op.CONST, value=10.0)
                    ]),
                    Node(op=Op.CONST, value=rng.uniform(2.0, 4.0))
                ])
            ]),
            Node(op=Op.WRITE, children=[
                reg_noise,
                Node(op=Op.CONST, value=1.0)
            ]),
            Node(op=Op.WRITE, children=[
                reg_noise,
                Node(op=Op.CONST, value=-1.0)
            ])
        ])

    elif pattern == 3:
        # SAWTOOTH: increases then resets (via modular arithmetic)
        period = rng.uniform(3.0, 6.0)
        return Node(op=Op.SUB, children=[
            Node(op=Op.MUL, children=[
                Node(op=Op.STEP),
                Node(op=Op.CONST, value=10.0 / period)
            ]),
            Node(op=Op.MUL, children=[
                Node(op=Op.CONST, value=period),
                Node(op=Op.DIV, children=[
                    Node(op=Op.MUL, children=[
                        Node(op=Op.STEP),
                        Node(op=Op.CONST, value=10.0)
                    ]),
                    Node(op=Op.CONST, value=period)
                ])
            ])
        ])

    elif pattern == 4:
        # STEP FUNCTION: constant then sudden change
        # Output = val1 if step < threshold else val2
        threshold = rng.uniform(0.3, 0.7)
        val1 = rng.uniform(-3.0, 3.0)
        val2 = rng.uniform(-3.0, 3.0)
        while abs(val2 - val1) < 2.0:
            val2 = rng.uniform(-5.0, 5.0)
        return Node(op=Op.IF, children=[
            Node(op=Op.SUB, children=[
                Node(op=Op.CONST, value=threshold),
                Node(op=Op.STEP)
            ]),
            Node(op=Op.CONST, value=val1),
            Node(op=Op.CONST, value=val2)
        ])

    elif pattern == 5:
        # ACCUMULATOR GENERATOR: builds value in register over time
        reg = Node(op=Op.ZERO)
        increment = rng.uniform(0.3, 1.5)
        return Node(op=Op.WRITE, children=[
            reg,
            Node(op=Op.ADD, children=[
                Node(op=Op.READ, children=[reg.copy()]),
                Node(op=Op.CONST, value=increment)
            ])
        ])

    elif pattern == 6:
        # INPUT-REACTIVE: uses input channel to vary output
        scale = rng.uniform(1.0, 4.0)
        return Node(op=Op.ADD, children=[
            Node(op=Op.MUL, children=[
                Node(op=Op.SENSE, children=[Node(op=Op.ZERO)]),
                Node(op=Op.CONST, value=scale)
            ]),
            Node(op=Op.MUL, children=[
                Node(op=Op.STEP),
                Node(op=Op.CONST, value=rng.uniform(-2.0, 2.0))
            ])
        ])

    else:
        # DELAY CONTROLLER: writes varying delays to register 1
        reg_delay = Node(op=Op.ONE)
        return Node(op=Op.IF, children=[
            Node(op=Op.SUB, children=[
                Node(op=Op.STEP),
                Node(op=Op.CONST, value=rng.uniform(0.3, 0.6))
            ]),
            Node(op=Op.WRITE, children=[
                reg_delay,
                Node(op=Op.CONST, value=rng.uniform(3.0, 6.0))
            ]),
            Node(op=Op.WRITE, children=[
                reg_delay,
                Node(op=Op.CONST, value=rng.uniform(1.0, 2.0))
            ])
        ])


# ============================================================================
# CHALLENGE GENERATION — run generator to produce challenge parameters
# ============================================================================

ECHO_CHALLENGE = 'echo_challenge'
ACCUMULATE_CHALLENGE = 'accumulate_challenge'
CHANGE_DETECT = 'change_detect'
CHALLENGE_TYPES = [ECHO_CHALLENGE, ACCUMULATE_CHALLENGE, CHANGE_DETECT]


def generate_challenges(gen_tree: Node, gen_seed: int) -> List[dict]:
    """Run generator tree to produce challenge parameters for all 3 types.

    Generator output is interpreted as:
      - Tree return value: challenge input value (clamped to [-10, 10])
      - Register 0: noise flag (>0 means noise at this step)
      - Register 1: delay parameter (clamped to [1, 6])
    """
    gen_rng = random.Random(gen_seed)
    challenges = []

    for ctype_idx, ctype in enumerate(CHALLENGE_TYPES):
        ctx = GeneratorContext()
        seq_length = 10 + gen_rng.randint(0, 5)

        values = []
        noise_flags = []
        delays = []

        for step in range(seq_length):
            if step > 0:
                ctx.advance_step()
            ctx.inputs = [
                float(step) / 10.0,
                float(seq_length) / 10.0,
                float(ctype_idx),
                gen_rng.uniform(-1.0, 1.0),
            ]
            result = execute(gen_tree, ctx)

            values.append(max(-10.0, min(10.0, result)))
            noise_flags.append(ctx.registers[0 % ctx.NUM_REGISTERS] > 0.0)
            raw_delay = ctx.registers[1 % ctx.NUM_REGISTERS]
            delays.append(max(1, min(6, int(abs(raw_delay)) + 1)))

        challenges.append({
            'type': ctype,
            'values': values,
            'noise_flags': noise_flags,
            'delays': delays,
            'seq_length': seq_length,
        })

    return challenges


# ============================================================================
# COEVOLUTION TASK — evaluate solvers on generator-produced challenges
# ============================================================================

def evaluate_on_challenge(solver_tree: Node, challenge: dict) -> float:
    """Evaluate a solver on a single generator-produced challenge."""
    ctype = challenge['type']
    if ctype == ECHO_CHALLENGE:
        return _eval_echo_challenge(solver_tree, challenge)
    elif ctype == ACCUMULATE_CHALLENGE:
        return _eval_accumulate_challenge(solver_tree, challenge)
    elif ctype == CHANGE_DETECT:
        return _eval_change_detect(solver_tree, challenge)
    return 0.0


def _eval_echo_challenge(solver_tree: Node, challenge: dict) -> float:
    """Echo challenge: solver must remember values and echo them after delay.

    Protocol:
      Phase 1 (store):  Present values with ch1=1.0 (store signal)
      Phase 2 (delay):  Noise steps with ch1=0.0
      Phase 3 (recall): ch1=-1.0, solver must output stored values
    """
    ctx = SelfAwareContext()
    values = challenge['values'][:5]  # max 5 values to echo
    if not values:
        return 0.0

    delay = max(2, min(6, challenge['delays'][0] if challenge['delays'] else 3))

    # Phase 1: Store each value
    for i, val in enumerate(values):
        if ctx.step_number > 0:
            ctx.advance_step()
        ctx.inputs = [val, 1.0, float(i) / max(len(values), 1),
                      float(len(values)), 0.0, 0.0, 0.0, 0.0]
        execute(solver_tree, ctx)

    # Phase 2: Delay with noise
    all_vals = challenge['values']
    for d in range(delay):
        ctx.advance_step()
        noise_idx = (len(values) + d) % len(all_vals)
        noise_val = all_vals[noise_idx] * 0.5
        ctx.inputs = [noise_val, 0.0, float(d) / max(delay, 1),
                      float(len(values)), 0.0, 0.0, 0.0, 0.0]
        execute(solver_tree, ctx)

    # Phase 3: Recall
    total_score = 0.0
    for i in range(len(values)):
        ctx.advance_step()
        ctx.inputs = [0.0, -1.0, float(i) / max(len(values), 1),
                      float(i), 0.0, 0.0, 0.0, 0.0]
        execute(solver_tree, ctx)

        recalled = ctx.outputs[0]
        error = abs(recalled - values[i])
        if error < 0.5:
            total_score += 1.0
        elif error < 1.0:
            total_score += 0.5
        elif error < 2.0:
            total_score += 0.2

    return total_score / max(len(values), 1)


def _eval_accumulate_challenge(solver_tree: Node, challenge: dict) -> float:
    """Accumulate challenge: solver must track running sum, ignore noise.

    At each step:
      ch0 = value
      ch1 = 1.0 if noise (ignore), 0.0 if real (add to sum)
    Solver output ch0 should match running sum of real values.
    """
    ctx = SelfAwareContext()
    values = challenge['values'][:12]
    noise_flags = challenge['noise_flags'][:12]

    # Pad noise_flags if needed
    while len(noise_flags) < len(values):
        noise_flags.append(False)

    running_sum = 0.0
    total_score = 0.0

    for i in range(len(values)):
        if i > 0:
            ctx.advance_step()

        val = values[i]
        is_noise = noise_flags[i]

        ctx.inputs = [val, 1.0 if is_noise else 0.0,
                      float(i), float(len(values)),
                      0.0, 0.0, 0.0, 0.0]
        execute(solver_tree, ctx)

        if not is_noise:
            running_sum += val

        output = ctx.outputs[0]
        error = abs(output - running_sum)
        scale = max(abs(running_sum), 1.0)
        step_score = max(0.0, 1.0 - error / scale)
        total_score += step_score

    return total_score / max(len(values), 1)


def _eval_change_detect(solver_tree: Node, challenge: dict) -> float:
    """Change detection: solver must detect significant changes in signal.

    Change point: |value[i] - value[i-1]| > 1.5
    Solver output ch0 > 0.5 means "change detected."
    Score: F1 of detection (skipping first step).
    """
    ctx = SelfAwareContext()
    values = challenge['values'][:15]
    if len(values) < 2:
        return 0.0

    true_pos = 0
    false_pos = 0
    true_neg = 0
    false_neg = 0

    for i, val in enumerate(values):
        if i > 0:
            ctx.advance_step()

        ctx.inputs = [val, float(i), float(len(values)), 0.0,
                      0.0, 0.0, 0.0, 0.0]
        execute(solver_tree, ctx)

        if i == 0:
            continue  # no previous value

        is_change = abs(values[i] - values[i - 1]) > 1.5
        detected = ctx.outputs[0] > 0.5

        if detected and is_change:
            true_pos += 1
        elif detected and not is_change:
            false_pos += 1
        elif not detected and not is_change:
            true_neg += 1
        elif not detected and is_change:
            false_neg += 1

    # F1 score
    if true_pos + false_pos + false_neg == 0:
        # No changes to detect and none false-detected
        return 0.5 if true_neg > 0 else 0.0

    precision = true_pos / max(true_pos + false_pos, 1)
    recall = true_pos / max(true_pos + false_neg, 1)

    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall)


# ============================================================================
# GENERATOR DIVERSITY BONUS
# ============================================================================

def compute_diversity_bonus(gen_challenges: List[dict],
                            top3_challenges: List[List[dict]]) -> float:
    """Add +0.1 if generator's pattern differs from top 3 generators.

    Compare value sequences using normalized euclidean distance.
    """
    if not top3_challenges:
        return 0.1  # all get bonus if no top 3 yet

    # Flatten this generator's values
    gen_vals = []
    for c in gen_challenges:
        gen_vals.extend(c['values'][:10])
    if not gen_vals:
        return 0.1

    distances = []
    for top_c_list in top3_challenges:
        top_vals = []
        for c in top_c_list:
            top_vals.extend(c['values'][:10])
        if not top_vals:
            continue

        min_len = min(len(gen_vals), len(top_vals))
        if min_len == 0:
            continue

        sq_dist = sum((a - b) ** 2
                      for a, b in zip(gen_vals[:min_len], top_vals[:min_len]))
        distances.append(math.sqrt(sq_dist / min_len))

    if distances and (sum(distances) / len(distances)) > 1.0:
        return 0.1
    return 0.0


# ============================================================================
# SOLVER ISLAND — island of solver organisms with external fitness
# ============================================================================

class SolverIsland:
    MAX_TREE_SIZE = 250

    def __init__(self, island_id: int, pop_size: int, seed: int):
        self.id = island_id
        self.pop_size = pop_size
        self.rng = random.Random(seed)
        self.organisms: List[dict] = []
        self.plasmids: List[Node] = []
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
                    'static_fitness': 0.0, 'coev_fitness': 0.0,
                })
                # Mutated variants
                for _ in range(2):
                    variant = point_mutation(tree, rng, rate=0.2)
                    self.organisms.append({
                        'tree': variant, 'fitness': 0.0, 'scores': {},
                        'strategy': copy.deepcopy(strategy), 'age': 0,
                        'static_fitness': 0.0, 'coev_fitness': 0.0,
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
                        'tree': hybrid, 'fitness': 0.0, 'scores': {},
                        'strategy': strategy, 'age': 0,
                        'static_fitness': 0.0, 'coev_fitness': 0.0,
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
                'tree': tree, 'fitness': 0.0, 'scores': {},
                'strategy': strategy, 'age': 0,
                'static_fitness': 0.0, 'coev_fitness': 0.0,
            })

    def evolve(self):
        """Evolve population using pre-set fitness values (no internal eval)."""
        self.epoch += 1
        rng = self.rng

        self.organisms.sort(key=lambda o: o['fitness'], reverse=True)

        cur_best = self.organisms[0]['fitness']
        if cur_best > self.best_fitness + 0.001:
            self.best_fitness = cur_best
            self.stagnation = 0
        else:
            self.stagnation += 1

        # Catastrophe
        if self.stagnation > 40 and rng.random() < 0.3:
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
                    'strategy': strategy, 'age': 0,
                    'static_fitness': 0.0, 'coev_fitness': 0.0,
                })
            self.catastrophes += 1
            self.stagnation = 0
            return

        # Plasmid pool
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
                if tree.size() > self.MAX_TREE_SIZE:
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

        if tree.size() > self.MAX_TREE_SIZE:
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
            'static_fitness': 0.0, 'coev_fitness': 0.0,
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
# GENERATOR ISLAND — island of generator organisms with external fitness
# ============================================================================

class GeneratorIsland:
    MAX_TREE_SIZE = 150

    def __init__(self, island_id: int, pop_size: int, seed: int):
        self.id = island_id
        self.pop_size = pop_size
        self.rng = random.Random(seed)
        self.organisms: List[dict] = []
        self.epoch = 0
        self.best_fitness = 0.0
        self.stagnation = 0
        self.catastrophes = 0

    def initialize(self, scaffold_rate: float = 0.5):
        self.organisms = []
        rng = self.rng

        while len(self.organisms) < self.pop_size:
            if rng.random() < scaffold_rate:
                tree = generator_seed(rng)
            else:
                tree = random_generator_tree(rng, max_depth=4 + (self.id % 2))

            strategy = {
                'crossover_rate': rng.uniform(0.3, 0.7),
                'point_mut_rate': rng.uniform(0.05, 0.3),
                'subtree_mut_rate': rng.uniform(0.05, 0.2),
                'chaos_rate': rng.uniform(0.0, 0.1),
            }

            self.organisms.append({
                'tree': tree, 'fitness': 0.5,  # neutral initial fitness
                'strategy': strategy, 'age': 0,
                'challenges': None,
                'avg_solver_score': 0.5,
            })

    def evolve(self):
        """Evolve generator population using pre-set fitness values."""
        self.epoch += 1
        rng = self.rng

        self.organisms.sort(key=lambda o: o['fitness'], reverse=True)

        cur_best = self.organisms[0]['fitness']
        if cur_best > self.best_fitness + 0.001:
            self.best_fitness = cur_best
            self.stagnation = 0
        else:
            self.stagnation += 1

        # Catastrophe (generators stagnate faster threshold = 30)
        if self.stagnation > 30 and rng.random() < 0.4:
            keep = max(2, self.pop_size // 5)
            self.organisms = self.organisms[:keep]
            while len(self.organisms) < self.pop_size:
                if rng.random() < 0.6:
                    tree = generator_seed(rng)
                else:
                    tree = random_generator_tree(rng, max_depth=rng.randint(3, 5))
                strategy = {
                    'crossover_rate': rng.uniform(0.3, 0.7),
                    'point_mut_rate': rng.uniform(0.05, 0.3),
                    'subtree_mut_rate': rng.uniform(0.05, 0.2),
                    'chaos_rate': rng.uniform(0.0, 0.1),
                }
                self.organisms.append({
                    'tree': tree, 'fitness': 0.5,
                    'strategy': strategy, 'age': 0,
                    'challenges': None,
                    'avg_solver_score': 0.5,
                })
            self.catastrophes += 1
            self.stagnation = 0
            return

        # Breed new population (elitism: keep top 2)
        new_pop = [self.organisms[0], self.organisms[1]]

        while len(new_pop) < self.pop_size:
            child = self._breed(rng)
            new_pop.append(child)

        self.organisms = new_pop
        for org in self.organisms:
            org['age'] += 1

    def _breed(self, rng) -> dict:
        parent = self._tournament(rng, k=3)
        s = parent['strategy']
        r = rng.random()

        cumulative = s.get('chaos_rate', 0)
        if r < cumulative:
            # Chaos: random new generator
            tree = generator_seed(rng) if rng.random() < 0.5 else \
                random_generator_tree(rng, max_depth=5)
        else:
            cumulative += s['crossover_rate']
            if r < cumulative and len(self.organisms) > 2:
                other = self._tournament(rng, k=3)
                tree = subtree_crossover(parent['tree'], other['tree'], rng)
                # Ensure all ops are in generator set
                self._sanitize_tree(tree, rng)
            elif rng.random() < 0.5:
                tree = subtree_mutation_generator(parent['tree'], rng)
            else:
                tree = point_mutation_generator(parent['tree'], rng,
                                                rate=s.get('point_mut_rate', 0.15))

        if tree.size() > self.MAX_TREE_SIZE:
            tree = parent['tree'].copy()

        # Mutate strategy
        new_strategy = copy.deepcopy(parent['strategy'])
        for k, v in new_strategy.items():
            if rng.random() < 0.15:
                scale = max(abs(v) * 0.3, 0.02)
                new_strategy[k] = max(0.0, min(1.0, v + rng.gauss(0, scale)))

        return {
            'tree': tree, 'fitness': 0.5,
            'strategy': new_strategy, 'age': 0,
            'challenges': None,
            'avg_solver_score': 0.5,
        }

    def _sanitize_tree(self, tree: Node, rng: random.Random):
        """Replace non-generator ops introduced by crossover with solver trees."""
        nodes = get_all_nodes(tree)
        for node, _, _ in nodes:
            if node.op not in GENERATOR_OPS_SET:
                arity = ARITY[node.op]
                candidates = [op for op in GENERATOR_OPS_SET
                              if ARITY[op] == arity]
                if candidates:
                    node.op = rng.choice(candidates)
                    if node.op == Op.CONST:
                        node.value = rng.uniform(-5, 5)
                else:
                    # Replace with terminal
                    node.op = rng.choice(GENERATOR_TERMINAL_OPS)
                    if node.op == Op.CONST:
                        node.value = rng.uniform(-5, 5)
                    node.children = []

    def _tournament(self, rng, k=3):
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
# PARALLEL WORKER — evaluate one solver on static tasks + challenges
# ============================================================================

def _eval_solver_worker(args):
    """Worker: evaluate a single solver on static tasks and generator challenges."""
    tree, challenges, eval_seed = args

    # Static evaluation on all 9 tasks
    static_scores = evaluate_organism(tree, ALL_TASKS, n_trials=8,
                                      seed=eval_seed)
    static_fitness = compute_fitness(static_scores)

    # Coevolution evaluation on generator challenges
    coev_scores = []
    for challenge in challenges:
        score = evaluate_on_challenge(tree, challenge)
        coev_scores.append(score)
    coev_fitness = (sum(coev_scores) / len(coev_scores)) if coev_scores else 0.0

    combined = 0.40 * static_fitness + 0.60 * coev_fitness

    return {
        'static_scores': static_scores,
        'static_fitness': static_fitness,
        'coev_fitness': coev_fitness,
        'combined_fitness': combined,
    }


# ============================================================================
# COEVOLUTION ENGINE
# ============================================================================

class CoevolutionEngine:
    def __init__(self, n_solver_islands: int = 3,
                 n_generator_islands: int = 2,
                 solver_pop: int = 30,
                 generator_pop: int = 20,
                 cores: int = 8,
                 seed: int = 88):
        self.n_solver_islands = n_solver_islands
        self.n_generator_islands = n_generator_islands
        self.solver_pop = solver_pop
        self.generator_pop = generator_pop
        self.cores = cores
        self.seed = seed
        self.rng = random.Random(seed)

        self.solver_islands: List[SolverIsland] = []
        self.generator_islands: List[GeneratorIsland] = []

        self.global_best_solver = None
        self.global_best_solver_fitness = 0.0
        self.global_best_generator = None
        self.global_best_generator_fitness = 0.0

        self.generation = 0
        self.history = []

        self.state_path = os.path.join(TOOLS_DIR, 'exp4_coev_state.json')
        self.solver_best_path = os.path.join(TOOLS_DIR,
                                              'exp4_coev_solver_best.json')
        self.generator_best_path = os.path.join(TOOLS_DIR,
                                                 'exp4_coev_generator_best.json')
        self.log_path = os.path.join(TOOLS_DIR, 'exp4_coev_log.jsonl')

    def initialize(self):
        transplants = load_transplants()

        # Create solver islands
        self.solver_islands = []
        for i in range(self.n_solver_islands):
            island = SolverIsland(i, self.solver_pop,
                                  seed=self.seed + i * 1000)
            scaffold_rate = 0.4 + (i % 3) * 0.1
            island.initialize(scaffold_rate=scaffold_rate,
                              transplants=transplants)
            self.solver_islands.append(island)

        # Create generator islands
        self.generator_islands = []
        for i in range(self.n_generator_islands):
            island = GeneratorIsland(
                self.n_solver_islands + i,  # unique id
                self.generator_pop,
                seed=self.seed + (self.n_solver_islands + i) * 1000
            )
            scaffold_rate = 0.5 + (i % 2) * 0.1
            island.initialize(scaffold_rate=scaffold_rate)
            self.generator_islands.append(island)

    def run(self):
        self.initialize()

        running = [True]

        def handler(sig, frame):
            print(f"\n[SIGNAL] Saving and stopping...")
            running[0] = False

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        total_solvers = self.n_solver_islands * self.solver_pop
        total_generators = self.n_generator_islands * self.generator_pop

        print(f"\n{'=' * 72}")
        print(f"  COEVOLUTION EXPERIMENT (exp4)")
        print(f"{'=' * 72}")
        print(f"  Solver islands:     {self.n_solver_islands}"
              f"  ({self.solver_pop} pop each,"
              f" {total_solvers} total)")
        print(f"  Generator islands:  {self.n_generator_islands}"
              f"  ({self.generator_pop} pop each,"
              f" {total_generators} total)")
        print(f"  Cores:              {self.cores}")
        print(f"  Seed:               {self.seed}")
        print(f"  Solver ops:         32 (full set incl. self-referential)")
        print(f"  Generator ops:      {len(GENERATOR_OPS_SET)}"
              f" (restricted subset)")
        print(f"  Challenge types:    {', '.join(CHALLENGE_TYPES)}")
        print(f"  Solver fitness:     0.40 * static + 0.60 * coevolution")
        print(f"  Generator fitness:  1.0 - avg_solver_score + diversity")
        print(f"  Static tasks:       {', '.join(ALL_TASKS.keys())}")
        print(f"  Size limits:        solver={SolverIsland.MAX_TREE_SIZE}"
              f"  gen={GeneratorIsland.MAX_TREE_SIZE}")
        print(f"{'=' * 72}\n")

        epochs_per_round = 10
        total_start = time.time()

        while running[0]:
            self.generation += 1
            round_start = time.time()

            self._run_round()

            round_time = time.time() - round_start
            total_epochs = self.generation * epochs_per_round

            # ---- Report ----
            print(f"  Round {self.generation}"
                  f" ({round_time:.1f}s)")

            if self.global_best_solver:
                scores = self.global_best_solver.get('scores', {})
                mem_names = ['delayed_echo', 'sequential_xor', 'running_max',
                             'accumulator', 'state_switcher']
                sr_names = ['sequence_prediction', 'error_correction',
                            'novelty_detection']

                static_f = self.global_best_solver.get('static_fitness', 0)
                coev_f = self.global_best_solver.get('coev_fitness', 0)
                comb_f = self.global_best_solver_fitness

                print(f"  SOLVER  static={static_f:.4f}"
                      f"  coev={coev_f:.4f}"
                      f"  combined={comb_f:.4f}"
                      f"  size={self.global_best_solver.get('size', '?')}")

                mem_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                  for n in mem_names)
                sr_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                 for n in sr_names)
                nav = scores.get('persistent_nav', 0)
                print(f"    mem:  {mem_str}")
                print(f"    self: {sr_str}  nav={nav:.2f}")
                rd_names = ['real_line_length', 'real_indentation',
                            'real_nesting']
                rd_str = '  '.join(
                    f"{lbl}={scores.get(n, 0):.2f}"
                    for n, lbl in zip(rd_names,
                                      ['line', 'indent', 'nest']))
                print(f"    real: {rd_str}")

            if self.global_best_generator:
                gen_f = self.global_best_generator_fitness
                avg_s = self.global_best_generator.get('avg_solver_score', 0)
                print(f"  GENRTR  fitness={gen_f:.4f}"
                      f"  difficulty={1.0 - avg_s:.4f}"
                      f"  size={self.global_best_generator.get('size', '?')}")

            # Per-island summary
            for i, isl in enumerate(self.solver_islands):
                b = isl.best()
                cat = (f" [CAT x{isl.catastrophes}]"
                       if isl.catastrophes else "")
                print(f"    Solv {i}: fit={b['fitness']:.4f}"
                      f"  stag={isl.stagnation:3d}{cat}")
            for i, isl in enumerate(self.generator_islands):
                b = isl.best()
                cat = (f" [CAT x{isl.catastrophes}]"
                       if isl.catastrophes else "")
                print(f"    Gen  {i}: fit={b['fitness']:.4f}"
                      f"  stag={isl.stagnation:3d}{cat}")

            # ---- Log ----
            entry = {
                'gen': self.generation,
                'best_solver_fitness': self.global_best_solver_fitness,
                'best_solver_static': (
                    self.global_best_solver.get('static_fitness', 0)
                    if self.global_best_solver else 0),
                'best_solver_coev': (
                    self.global_best_solver.get('coev_fitness', 0)
                    if self.global_best_solver else 0),
                'best_generator_fitness': self.global_best_generator_fitness,
                'best_generator_difficulty': (
                    1.0 - self.global_best_generator.get('avg_solver_score', 0.5)
                    if self.global_best_generator else 0.5),
                'scores': (self.global_best_solver.get('scores', {})
                           if self.global_best_solver else {}),
                'time_s': round_time,
                'ts': time.strftime('%H:%M:%S'),
            }
            self.history.append(entry)
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')

            # Report to REST API
            report_generation(
                experiment_name='exp4_coevolution',
                generation=self.generation,
                best_fitness=self.global_best_solver_fitness,
                scores=self.global_best_solver.get('scores', {}) if self.global_best_solver else {},
                best_program_str=self.global_best_solver.get('program') if self.global_best_solver else None,
                metadata={
                    'static_fitness': self.global_best_solver.get('static_fitness', 0) if self.global_best_solver else 0,
                    'coev_fitness': self.global_best_solver.get('coev_fitness', 0) if self.global_best_solver else 0,
                    'generator_fitness': self.global_best_generator_fitness,
                },
            )

            if self.generation % 5 == 0:
                self._save()

            sys.stdout.flush()

        self._save()
        elapsed = time.time() - total_start
        print(f"\n{'=' * 72}")
        print(f"  STOPPED -- {self.generation} rounds, {elapsed:.0f}s")
        print(f"  Best solver fitness:    {self.global_best_solver_fitness:.4f}")
        print(f"  Best generator fitness: {self.global_best_generator_fitness:.4f}")
        if self.global_best_solver:
            print(f"  Solver scores:")
            for k, v in sorted(
                    self.global_best_solver.get('scores', {}).items()):
                print(f"    {k:25s}: {v:.4f}")
        print(f"{'=' * 72}")

    def _run_round(self):
        """Execute one coevolution round:
        1. Generate challenges from all generators
        2. Select top 5 generators
        3. Evaluate all solvers (static + coev) in parallel
        4. Evaluate all generators against top solvers
        5. Evolve both populations
        6. Migration within each population type
        """

        # ---- Step 1: Generate challenges from ALL generators ----
        all_gen_data = []  # list of (island_idx, org_idx, organism)
        for isl_idx, isl in enumerate(self.generator_islands):
            for org_idx, org in enumerate(isl.organisms):
                all_gen_data.append((isl_idx, org_idx, org))

        gen_challenges = {}  # (isl_idx, org_idx) -> list of 3 challenges
        for isl_idx, org_idx, org in all_gen_data:
            key = (isl_idx, org_idx)
            gen_seed = (self.seed + self.generation * 10000
                        + isl_idx * 1000 + org_idx)
            gen_challenges[key] = generate_challenges(org['tree'], gen_seed)

        # ---- Step 2: Select top 5 generators (by previous fitness) ----
        sorted_gen_data = sorted(all_gen_data,
                                 key=lambda x: x[2]['fitness'],
                                 reverse=True)
        top5_gen_keys = [(d[0], d[1]) for d in sorted_gen_data[:5]]

        # Flatten top 5 challenges for solver evaluation
        top5_flat_challenges = []
        for key in top5_gen_keys:
            top5_flat_challenges.extend(gen_challenges[key])

        # ---- Step 3: Evaluate all solvers in parallel ----
        all_solver_data = []  # list of (island_idx, org_idx, organism)
        for isl_idx, isl in enumerate(self.solver_islands):
            for org_idx, org in enumerate(isl.organisms):
                all_solver_data.append((isl_idx, org_idx, org))

        eval_seed = 42 + (self.generation % 5)
        work = [(org['tree'], top5_flat_challenges, eval_seed)
                for _, _, org in all_solver_data]

        if self.cores > 1 and len(work) > 1:
            with mp.Pool(processes=min(self.cores, len(work))) as pool:
                solver_results = pool.map(_eval_solver_worker, work)
        else:
            solver_results = [_eval_solver_worker(w) for w in work]

        # Set solver fitness
        for (isl_idx, org_idx, org), result in zip(all_solver_data,
                                                    solver_results):
            org['fitness'] = result['combined_fitness']
            org['scores'] = result['static_scores']
            org['static_fitness'] = result['static_fitness']
            org['coev_fitness'] = result['coev_fitness']

        # Track global best solver
        for isl_idx, org_idx, org in all_solver_data:
            if org['fitness'] > self.global_best_solver_fitness:
                self.global_best_solver_fitness = org['fitness']
                self.global_best_solver = {
                    'fitness': org['fitness'],
                    'static_fitness': org.get('static_fitness', 0),
                    'coev_fitness': org.get('coev_fitness', 0),
                    'scores': org.get('scores', {}),
                    'size': org['tree'].size(),
                    'strategy': org['strategy'],
                    'island': isl_idx,
                    'program': org['tree'].to_str(),
                }

        # ---- Step 4: Evaluate all generators ----
        # Get top N solver trees for generator evaluation
        sorted_solver_data = sorted(all_solver_data,
                                    key=lambda x: x[2]['fitness'],
                                    reverse=True)
        top_n = min(10, max(3, len(all_solver_data) // 3))
        top_solver_trees = [d[2]['tree'] for d in sorted_solver_data[:top_n]]

        # Compute top 3 generator challenge patterns for diversity
        top3_gen_challenge_lists = [gen_challenges[k]
                                    for k in top5_gen_keys[:3]]

        for isl_idx, org_idx, org in all_gen_data:
            key = (isl_idx, org_idx)
            challenges = gen_challenges[key]
            org['challenges'] = challenges

            # Evaluate top solvers on this generator's challenges
            solver_scores = []
            for s_tree in top_solver_trees:
                scores = [evaluate_on_challenge(s_tree, c)
                          for c in challenges]
                solver_scores.append(sum(scores) / len(scores))

            avg_solver_score = (sum(solver_scores) / len(solver_scores)
                                if solver_scores else 0.5)
            org['avg_solver_score'] = avg_solver_score

            gen_fitness = 1.0 - avg_solver_score

            # Diversity bonus (skip for top 3 who define the baseline)
            if key not in top5_gen_keys[:3]:
                bonus = compute_diversity_bonus(challenges,
                                                top3_gen_challenge_lists)
                gen_fitness += bonus

            org['fitness'] = max(0.0, min(2.0, gen_fitness))

        # Track global best generator
        for isl_idx, org_idx, org in all_gen_data:
            if org['fitness'] > self.global_best_generator_fitness:
                self.global_best_generator_fitness = org['fitness']
                self.global_best_generator = {
                    'fitness': org['fitness'],
                    'avg_solver_score': org.get('avg_solver_score', 0.5),
                    'size': org['tree'].size(),
                    'strategy': org['strategy'],
                    'island': isl_idx,
                    'program': org['tree'].to_str(),
                }

        # ---- Step 5: Evolve both populations ----
        for isl in self.solver_islands:
            isl.evolve()
        for isl in self.generator_islands:
            isl.evolve()

        # ---- Step 6: Migration within each population type ----
        # Solver migration (ring topology)
        if len(self.solver_islands) > 1:
            n_mig = max(1, self.solver_pop // 10)
            migrants = [isl.get_migrants(n_mig)
                        for isl in self.solver_islands]
            for i, isl in enumerate(self.solver_islands):
                source = (i - 1) % len(self.solver_islands)
                isl.accept_migrants(migrants[source])

        # Generator migration (ring topology)
        if len(self.generator_islands) > 1:
            n_mig = max(1, self.generator_pop // 10)
            migrants = [isl.get_migrants(n_mig)
                        for isl in self.generator_islands]
            for i, isl in enumerate(self.generator_islands):
                source = (i - 1) % len(self.generator_islands)
                isl.accept_migrants(migrants[source])

    def _save(self):
        state = {
            'generation': self.generation,
            'global_best_solver': self.global_best_solver,
            'global_best_solver_fitness': self.global_best_solver_fitness,
            'global_best_generator': self.global_best_generator,
            'global_best_generator_fitness': self.global_best_generator_fitness,
            'history': self.history[-100:],
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        with open(self.state_path, 'w') as f:
            json.dump(state, f, indent=2)

        if self.global_best_solver:
            with open(self.solver_best_path, 'w') as f:
                json.dump(self.global_best_solver, f, indent=2)

        if self.global_best_generator:
            with open(self.generator_best_path, 'w') as f:
                json.dump(self.global_best_generator, f, indent=2)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='GA Coevolution Experiment (exp4) — '
                    'Competitive coevolution with solver and generator populations')
    parser.add_argument('--islands', type=int, default=5,
                        help='Total islands (last 2 are generators, rest are '
                             'solvers). Default: 5 = 3 solver + 2 generator')
    parser.add_argument('--island-pop', type=int, default=30,
                        help='Solver island population (generator pop = '
                             '2/3 of this). Default: 30')
    parser.add_argument('--cores', type=int, default=8,
                        help='Parallel worker cores. Default: 8')
    parser.add_argument('--seed', type=int, default=88,
                        help='Random seed. Default: 88')
    args = parser.parse_args()

    n_solver_islands = max(1, args.islands - 2)
    n_generator_islands = min(args.islands, 2)
    generator_pop = max(10, args.island_pop * 2 // 3)

    engine = CoevolutionEngine(
        n_solver_islands=n_solver_islands,
        n_generator_islands=n_generator_islands,
        solver_pop=args.island_pop,
        generator_pop=generator_pop,
        cores=args.cores,
        seed=args.seed,
    )
    engine.run()


if __name__ == '__main__':
    main()
