#!/usr/bin/env python3
"""GA Experiment 15: Cooperative Coevolution with Problem Decomposition

Decomposes the problem into 3 specialist subpopulations that cooperate:

  SubPop A: "Memory Specialists"    — MEMORY_TASKS
  SubPop B: "Reasoning Specialists" — REASONING_TASKS + REAL_DATA_TASKS
  SubPop C: "Self-Ref Specialists"  — SELF_REF_TASKS

Each subpopulation evolves independently, then best specialists combine
into "teams" evaluated on ALL tasks. Team fitness feeds back as a bonus
to individual specialist fitness, creating pressure for compatibility.

Key features:
  - Specialist fitness = 0.7 * specialist_score + 0.3 * last_team_score
  - Tree merging: SEQ(A_best, SEQ(B_best, C_best))
  - Each subpop has its own islands with tournament selection + elitism
  - Migration within subpops only (not between subpops)
  - Draft phase every 5 rounds: top organisms form team combos

Hypothesis: Decomposing into specialist subpopulations allows each to
optimize independently while collaboration pressure prevents incompatible
specialization.

IMPORTANT: When --cores 1, uses sequential loop (no multiprocessing.Pool).

Usage:
    python3 ga_exp15_cooperative.py                        # defaults
    python3 ga_exp15_cooperative.py --cores 2              # limit parallelism
    python3 ga_exp15_cooperative.py --islands-per-subpop 3 --island-pop 30
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
# EXTENDED OP SET -- original 28 + 4 self-referential + lifetime learning
# ============================================================================

class Op(Enum):
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    GT = auto()
    LT = auto()
    EQ = auto()
    NEQ = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IF = auto()
    SEQ = auto()
    READ = auto()
    WRITE = auto()
    SENSE = auto()
    ACT = auto()
    CONST = auto()
    ZERO = auto()
    ONE = auto()
    NEG1 = auto()
    INC = auto()
    DEC = auto()
    ABS = auto()
    SIGN = auto()
    MAX2 = auto()
    MIN2 = auto()
    STEP = auto()
    LAST_OUT = auto()
    PREDICT = auto()
    SURPRISE = auto()
    LEARN = auto()
    RECALL = auto()
    STRENGTHEN = auto()
    WEAKEN = auto()
    DEFINE = auto()
    INVOKE = auto()


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
# PROGRAM PARSER
# ============================================================================

def parse_program(text: str) -> Optional['Node']:
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
# EXECUTE
# ============================================================================

def execute(node: Node, ctx: SelfAwareContext) -> float:
    if ctx.steps >= ctx.MAX_STEPS or ctx.halted:
        return 0.0
    ctx.steps += 1

    op = node.op

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

    args = [execute(c, ctx) for c in node.children]

    def clamp(v):
        return max(-1e6, min(1e6, v))

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

    if op == Op.GT:
        return 1.0 if args[0] > args[1] else 0.0
    if op == Op.LT:
        return 1.0 if args[0] < args[1] else 0.0
    if op == Op.EQ:
        return 1.0 if abs(args[0] - args[1]) < 0.1 else 0.0
    if op == Op.NEQ:
        return 1.0 if abs(args[0] - args[1]) >= 0.1 else 0.0

    if op == Op.AND:
        return 1.0 if args[0] > 0 and args[1] > 0 else 0.0
    if op == Op.OR:
        return 1.0 if args[0] > 0 or args[1] > 0 else 0.0
    if op == Op.NOT:
        return 0.0 if args[0] > 0 else 1.0

    if op == Op.IF:
        return args[1] if args[0] > 0 else args[2]
    if op == Op.SEQ:
        return args[1]

    if op == Op.READ:
        idx = int(args[0]) % ctx.NUM_REGISTERS
        return ctx.registers[idx]
    if op == Op.WRITE:
        idx = int(args[0]) % ctx.NUM_REGISTERS
        ctx.registers[idx] = clamp(args[1])
        return args[1]

    if op == Op.SENSE:
        idx = int(args[0]) % ctx.NUM_INPUT_CHANNELS
        return ctx.inputs[idx]
    if op == Op.ACT:
        idx = int(args[0]) % ctx.NUM_OUTPUT_CHANNELS
        ctx.outputs[idx] = clamp(args[1])
        return args[1]

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
# TASKS
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
                'sequence': sequence, 'expected': expected,
                'pattern': pattern, 'pattern_len': pattern_len,
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
                'target': target, 'n_steps': n_steps, 'noise': noise,
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
                'sequence': sequence, 'expected': expected,
                'oddball_pos': oddball_pos, 'pattern': pattern,
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
# EVALUATION
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
    clamped = [max(v, 0.01) for v in values]
    return len(clamped) / sum(1.0 / s for s in clamped)


def compute_objectives(scores: dict) -> List[float]:
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
    return (0.30 * objectives[0] + 0.10 * objectives[1] +
            0.40 * objectives[2] + 0.20 * objectives[3])


# ============================================================================
# SELF-AWARE SEED PATTERNS (all 16)
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
# SPECIALIST ISLAND — standard tournament + elitism
# ============================================================================

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_transplants() -> List[Node]:
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


def tournament_select(pop: List[dict], rng: random.Random, k: int = 4) -> dict:
    candidates = rng.sample(pop, min(k, len(pop)))
    return max(candidates, key=lambda o: o['adjusted_fitness'])


class SpecialistIsland:
    """Island evolving specialists for a specific task domain."""

    def __init__(self, island_id: int, pop_size: int, seed: int,
                 domain_name: str, domain_tasks: dict):
        self.id = island_id
        self.pop_size = pop_size
        self.rng = random.Random(seed)
        self.domain_name = domain_name
        self.domain_tasks = domain_tasks
        self.organisms = []
        self.plasmids = []
        self.epoch = 0
        self.best_fitness = 0.0
        self.stagnation = 0
        self.catastrophes = 0
        self.last_team_bonus = 0.0

    def initialize(self, scaffold_rate: float = 0.5,
                   transplants: Optional[List[Node]] = None):
        self.organisms = []
        rng = self.rng

        if transplants and self.id < len(transplants) * 2:
            for t_tree in transplants:
                tree = t_tree.copy()
                strategy = {
                    'crossover_rate': rng.uniform(0.3, 0.7),
                    'point_mut_rate': rng.uniform(0.05, 0.3),
                    'subtree_mut_rate': rng.uniform(0.05, 0.2),
                    'chaos_rate': rng.uniform(0.0, 0.05),
                }
                self.organisms.append({
                    'tree': tree, 'domain_fitness': 0.0,
                    'adjusted_fitness': 0.0, 'scores': {},
                    'strategy': strategy, 'age': 0,
                })

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
            }

            self.organisms.append({
                'tree': tree, 'domain_fitness': 0.0,
                'adjusted_fitness': 0.0, 'scores': {},
                'strategy': strategy, 'age': 0,
            })

    def evaluate_all(self, seed: int = 42):
        for org in self.organisms:
            org['scores'] = evaluate_organism(
                org['tree'], self.domain_tasks, n_trials=8, seed=seed
            )
            domain_scores = list(org['scores'].values())
            org['domain_fitness'] = float(np.mean(domain_scores)) if domain_scores else 0.0
            org['adjusted_fitness'] = (
                0.7 * org['domain_fitness'] + 0.3 * self.last_team_bonus
            )

    def evolve_one_epoch(self):
        self.epoch += 1
        rng = self.rng

        self.evaluate_all(seed=42 + (self.epoch % 5))

        best = max(self.organisms, key=lambda o: o['adjusted_fitness'])
        best_fit = best['adjusted_fitness']

        if best_fit > self.best_fitness:
            self.best_fitness = best_fit
            self.stagnation = 0
        else:
            self.stagnation += 1

        if self.stagnation > 40 and rng.random() < 0.3:
            kept = [max(self.organisms, key=lambda o: o['adjusted_fitness'])]
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
                }
                self.organisms.append({
                    'tree': tree, 'domain_fitness': 0.0,
                    'adjusted_fitness': 0.0, 'scores': {},
                    'strategy': strategy, 'age': 0,
                })
            self.catastrophes += 1
            self.stagnation = 0
            return

        # Elitism: keep top 10%
        sorted_pop = sorted(self.organisms,
                            key=lambda o: o['adjusted_fitness'], reverse=True)
        elite_count = max(2, self.pop_size // 10)
        elites = [copy.deepcopy(o) for o in sorted_pop[:elite_count]]

        # Build plasmid pool from best
        for org in sorted_pop[:3]:
            nodes = get_all_nodes(org['tree'])
            for node, _, _ in nodes:
                has_relevant = any(
                    n.op in (Op.READ, Op.WRITE, Op.PREDICT, Op.SURPRISE,
                             Op.LAST_OUT)
                    for n, _, _ in get_all_nodes(node)
                )
                if has_relevant and 3 <= node.size() <= 30 and rng.random() < 0.15:
                    self.plasmids.append(node.copy())
        if len(self.plasmids) > 80:
            rng.shuffle(self.plasmids)
            self.plasmids = self.plasmids[:50]

        offspring = list(elites)
        while len(offspring) < self.pop_size:
            offspring.append(self._breed(rng))

        self.organisms = offspring
        for org in self.organisms:
            org['age'] += 1

    def _breed(self, rng) -> dict:
        parent = tournament_select(self.organisms, rng, k=4)
        s = parent['strategy']
        r = rng.random()

        cumulative = s.get('chaos_rate', 0)
        if r < cumulative:
            if rng.random() < 0.6:
                tree = self_aware_seed(rng)
            else:
                tree = random_tree(rng, max_depth=6)
        else:
            cumulative += s['crossover_rate']
            if r < cumulative:
                other = tournament_select(self.organisms, rng, k=3)
                tree = subtree_crossover(parent['tree'], other['tree'], rng)
            elif rng.random() < 0.5:
                tree = subtree_mutation(parent['tree'], rng)
            else:
                tree = point_mutation(parent['tree'], rng,
                                      rate=s.get('point_mut_rate', 0.15))

        if self.plasmids and rng.random() < 0.1:
            plasmid = rng.choice(self.plasmids).copy()
            nodes = get_all_nodes(tree)
            if len(nodes) > 1:
                _, pn, idx = rng.choice(nodes[1:])
                if pn is not None:
                    pn.children[idx] = plasmid

        if tree.size() > 250:
            tree = parent['tree'].copy()

        new_strategy = copy.deepcopy(parent['strategy'])
        for k, v in new_strategy.items():
            if rng.random() < 0.15:
                scale = max(abs(v) * 0.3, 0.02)
                new_strategy[k] = max(0.0, min(1.0, v + rng.gauss(0, scale)))

        return {
            'tree': tree, 'domain_fitness': 0.0,
            'adjusted_fitness': 0.0, 'scores': {},
            'strategy': new_strategy, 'age': 0,
        }

    def best_organism(self) -> dict:
        return max(self.organisms, key=lambda o: o['adjusted_fitness'])

    def get_migrants(self, n):
        sorted_pop = sorted(self.organisms,
                            key=lambda o: o['adjusted_fitness'], reverse=True)
        return [copy.deepcopy(o) for o in sorted_pop[:n]]

    def accept_migrants(self, migrants):
        sorted_pop = sorted(
            range(len(self.organisms)),
            key=lambda i: self.organisms[i]['adjusted_fitness']
        )
        for i, m in enumerate(migrants):
            if len(sorted_pop) > len(migrants):
                replace_idx = sorted_pop[i]
                self.organisms[replace_idx] = m


# ============================================================================
# PARALLEL WORKER
# ============================================================================

def _run_subpop_batch(args):
    islands, n_epochs = args
    for island in islands:
        for _ in range(n_epochs):
            island.evolve_one_epoch()

    results = []
    for island in islands:
        island.evaluate_all(seed=42 + (island.epoch % 5))
        best = island.best_organism()
        results.append({
            'best_fitness': best['adjusted_fitness'],
            'domain_fitness': best['domain_fitness'],
            'scores': best['scores'],
            'size': best['tree'].size(),
            'stagnation': island.stagnation,
            'catastrophes': island.catastrophes,
            'epoch': island.epoch,
        })

    return islands, results


# ============================================================================
# TEAM COMPOSITION
# ============================================================================

def compose_team(mem_tree: Node, rea_tree: Node, sr_tree: Node,
                 max_size: int = 500) -> Node:
    """Merge specialist trees: SEQ(mem, SEQ(rea, sr))."""
    mt = mem_tree.copy()
    rt = rea_tree.copy()
    st = sr_tree.copy()

    # Trim if too large
    while mt.size() > max_size // 3:
        nodes = get_all_nodes(mt)
        if len(nodes) > 3:
            _, p, i = nodes[-1]
            if p is not None:
                p.children[i] = Node(op=Op.ZERO)
            else:
                break
        else:
            break

    while rt.size() > max_size // 3:
        nodes = get_all_nodes(rt)
        if len(nodes) > 3:
            _, p, i = nodes[-1]
            if p is not None:
                p.children[i] = Node(op=Op.ZERO)
            else:
                break
        else:
            break

    while st.size() > max_size // 3:
        nodes = get_all_nodes(st)
        if len(nodes) > 3:
            _, p, i = nodes[-1]
            if p is not None:
                p.children[i] = Node(op=Op.ZERO)
            else:
                break
        else:
            break

    return Node(op=Op.SEQ, children=[mt, Node(op=Op.SEQ, children=[rt, st])])


# ============================================================================
# COOPERATIVE ENGINE
# ============================================================================

# Define specialist task sets
SPECIALIST_TASKS = {
    'memory': MEMORY_TASKS,
    'reasoning': {**REASONING_TASKS, **{k: v for k, v in REAL_DATA_TASKS.items()}},
    'selfref': SELF_REF_TASKS,
}


class CooperativeEngine:
    def __init__(self, islands_per_subpop=2, island_pop=40,
                 cores=None, seed=555):
        self.islands_per_subpop = islands_per_subpop
        self.island_pop = island_pop
        self.cores = cores or max(1, mp.cpu_count() - 2)
        self.seed = seed
        self.rng = random.Random(seed)

        self.subpops = {}  # domain_name -> list of SpecialistIsland
        self.generation = 0
        self.best_team = None
        self.best_team_scalar = 0.0
        self.history = []

        self.save_path = os.path.join(TOOLS_DIR, 'exp15_cooperative_state.json')
        self.best_path = os.path.join(TOOLS_DIR, 'exp15_cooperative_best.json')
        self.teams_path = os.path.join(TOOLS_DIR, 'exp15_cooperative_teams.json')
        self.log_path = os.path.join(TOOLS_DIR, 'exp15_cooperative_log.jsonl')

    def initialize(self):
        transplants = load_transplants()

        for i, (domain, tasks) in enumerate(SPECIALIST_TASKS.items()):
            islands = []
            for j in range(self.islands_per_subpop):
                island = SpecialistIsland(
                    island_id=i * self.islands_per_subpop + j,
                    pop_size=self.island_pop,
                    seed=self.seed + i * 10000 + j * 1000,
                    domain_name=domain,
                    domain_tasks=tasks,
                )
                scaffold_rate = 0.4 + (j % 3) * 0.1
                island.initialize(scaffold_rate=scaffold_rate,
                                  transplants=transplants)
                islands.append(island)
            self.subpops[domain] = islands

    def run(self):
        self.initialize()

        running = [True]

        def handler(sig, frame):
            print(f"\n[SIGNAL] Saving and stopping...")
            running[0] = False

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        total_islands = self.islands_per_subpop * len(SPECIALIST_TASKS)
        total_orgs = total_islands * self.island_pop

        print(f"\n{'=' * 74}")
        print(f"  COOPERATIVE COEVOLUTION (exp15)")
        print(f"{'=' * 74}")
        print(f"  Subpopulations: {len(SPECIALIST_TASKS)}"
              f" (memory, reasoning, selfref)")
        print(f"  Islands/subpop: {self.islands_per_subpop}")
        print(f"  Pop/island:     {self.island_pop}")
        print(f"  Total:          {total_orgs} organisms across"
              f" {total_islands} islands")
        print(f"  Cores:          {self.cores}")
        print(f"  Specialist fitness = 0.7*domain + 0.3*team_bonus")
        print(f"  Team composition: SEQ(mem, SEQ(rea, sr))")
        print(f"  Hypothesis: Problem decomposition + cooperation pressure")
        print(f"              enables deeper specialization")
        for domain, tasks in SPECIALIST_TASKS.items():
            print(f"    {domain:10s}: {', '.join(tasks.keys())}")
        print(f"{'=' * 74}\n")

        epochs_per_round = 10
        total_start = time.time()

        while running[0]:
            self.generation += 1
            round_start = time.time()

            # Evolve each subpopulation
            all_subpop_results = {}
            for domain, islands in self.subpops.items():
                if self.cores > 1:
                    work = (islands, epochs_per_round)
                    updated_islands, results = _run_subpop_batch(work)
                    self.subpops[domain] = updated_islands
                else:
                    for island in islands:
                        for _ in range(epochs_per_round):
                            island.evolve_one_epoch()
                    results = []
                    for island in islands:
                        island.evaluate_all(seed=42 + (island.epoch % 5))
                        best = island.best_organism()
                        results.append({
                            'best_fitness': best['adjusted_fitness'],
                            'domain_fitness': best['domain_fitness'],
                            'scores': best['scores'],
                            'size': best['tree'].size(),
                            'stagnation': island.stagnation,
                            'catastrophes': island.catastrophes,
                            'epoch': island.epoch,
                        })
                all_subpop_results[domain] = results

            # Migration within each subpop (ring topology)
            for domain, islands in self.subpops.items():
                if len(islands) > 1:
                    n_mig = max(1, self.island_pop // 10)
                    migrants = [isl.get_migrants(n_mig) for isl in islands]
                    for i, isl in enumerate(islands):
                        source = (i - 1) % len(islands)
                        isl.accept_migrants(migrants[source])

            # COLLABORATION PHASE: form teams from best specialists
            mem_best = []
            rea_best = []
            sr_best = []

            for island in self.subpops['memory']:
                b = island.best_organism()
                mem_best.append((b['adjusted_fitness'], b['tree'], island))
            for island in self.subpops['reasoning']:
                b = island.best_organism()
                rea_best.append((b['adjusted_fitness'], b['tree'], island))
            for island in self.subpops['selfref']:
                b = island.best_organism()
                sr_best.append((b['adjusted_fitness'], b['tree'], island))

            mem_best.sort(key=lambda x: x[0], reverse=True)
            rea_best.sort(key=lambda x: x[0], reverse=True)
            sr_best.sort(key=lambda x: x[0], reverse=True)

            # Try multiple team combinations (draft phase every 5 rounds)
            n_combos = min(4, len(mem_best) * len(rea_best) * len(sr_best))
            if self.generation % 5 == 0:
                n_combos = min(8, n_combos * 2)

            best_team_scalar = 0.0
            best_team_info = None

            combo_idx = 0
            for mi in range(min(2, len(mem_best))):
                for ri in range(min(2, len(rea_best))):
                    for si in range(min(2, len(sr_best))):
                        if combo_idx >= n_combos:
                            break

                        team_tree = compose_team(
                            mem_best[mi][1], rea_best[ri][1], sr_best[si][1]
                        )

                        team_scores = evaluate_organism(
                            team_tree, ALL_TASKS, n_trials=6,
                            seed=42 + (self.generation % 5)
                        )
                        team_obj = compute_objectives(team_scores)
                        team_scalar = scalar_fitness(team_obj)

                        if team_scalar > best_team_scalar:
                            best_team_scalar = team_scalar
                            best_team_info = {
                                'scalar_fitness': team_scalar,
                                'objectives': team_obj,
                                'scores': team_scores,
                                'size': team_tree.size(),
                                'program': team_tree.to_str(),
                                'mem_island': mi,
                                'rea_island': ri,
                                'sr_island': si,
                            }

                        combo_idx += 1
                    if combo_idx >= n_combos:
                        break
                if combo_idx >= n_combos:
                    break

            # Feed team bonus back to specialists
            for domain, islands in self.subpops.items():
                for island in islands:
                    island.last_team_bonus = best_team_scalar

            # Update global best
            if best_team_scalar > self.best_team_scalar:
                self.best_team = best_team_info
                self.best_team_scalar = best_team_scalar

            # Report
            round_time = time.time() - round_start
            total_epochs = self.generation * epochs_per_round

            print(f"  Round {self.generation} ({total_epochs} epochs,"
                  f" {round_time:.0f}s)")

            if self.best_team:
                obj = self.best_team['objectives']
                scores = self.best_team['scores']
                print(f"  BEST TEAM: scalar={self.best_team_scalar:.4f}"
                      f"  obj=[{obj[0]:.3f}, {obj[1]:.3f},"
                      f" {obj[2]:.3f}, {obj[3]:.3f}]")

                mem_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                  for n in MEMORY_NAMES)
                sr_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                 for n in SELF_REF_NAMES)
                rd_str = '  '.join(
                    f"{lbl}={scores.get(n, 0):.2f}"
                    for n, lbl in zip(REAL_DATA_NAMES,
                                      ['line', 'indent', 'nest']))
                nav = scores.get('persistent_nav', 0)
                print(f"    mem: {mem_str}")
                print(f"    self: {sr_str}")
                print(f"    real: {rd_str}")
                print(f"    nav={nav:.2f}  size={self.best_team['size']}")

            # Per-subpop stats
            for domain, results in all_subpop_results.items():
                best_r = max(results, key=lambda r: r['domain_fitness'])
                avg_fit = np.mean([r['domain_fitness'] for r in results])
                cat_total = sum(r['catastrophes'] for r in results)
                cat_str = f" [CAT x{cat_total}]" if cat_total else ""
                print(f"    {domain:10s}: best={best_r['domain_fitness']:.4f}"
                      f"  avg={avg_fit:.4f}"
                      f"  stag={max(r['stagnation'] for r in results):3d}"
                      f"{cat_str}")

            print(f"    team_bonus={best_team_scalar:.4f}"
                  f"  (fed back as 0.3 weight)")

            # Log
            entry = {
                'gen': self.generation,
                'epochs': total_epochs,
                'team_scalar': best_team_scalar,
                'global_best_scalar': self.best_team_scalar,
                'team_objectives': (best_team_info['objectives']
                                    if best_team_info else []),
                'team_scores': (best_team_info['scores']
                                if best_team_info else {}),
                'subpop_stats': {
                    domain: {
                        'best_domain': max(r['domain_fitness'] for r in results),
                        'avg_domain': float(np.mean([r['domain_fitness']
                                                     for r in results])),
                    }
                    for domain, results in all_subpop_results.items()
                },
                'time_s': round_time,
                'ts': time.strftime('%H:%M:%S'),
            }
            self.history.append(entry)
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')

            report_generation(
                experiment_name='exp15_cooperative',
                generation=self.generation,
                best_fitness=self.best_team_scalar,
                scores=self.best_team.get('scores', {}) if self.best_team else {},
                best_program_str=(self.best_team.get('program')
                                  if self.best_team else None),
                metadata={
                    'objectives': (self.best_team.get('objectives', [])
                                   if self.best_team else []),
                    'subpop_stats': entry.get('subpop_stats', {}),
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
        print(f"  Best team scalar: {self.best_team_scalar:.4f}")
        if self.best_team:
            obj = self.best_team['objectives']
            print(f"  Objectives: mem={obj[0]:.4f} sr={obj[1]:.4f}"
                  f" rea={obj[2]:.4f} rd={obj[3]:.4f}")
            print(f"  Scores:")
            for k, v in sorted(self.best_team['scores'].items()):
                print(f"    {k:25s}: {v:.4f}")
        print(f"{'=' * 74}")

    def _save(self):
        state = {
            'generation': self.generation,
            'best_team': self.best_team,
            'best_team_scalar': self.best_team_scalar,
            'history': self.history[-100:],
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        with open(self.save_path, 'w') as f:
            json.dump(state, f, indent=2)

        if self.best_team:
            with open(self.best_path, 'w') as f:
                json.dump(self.best_team, f, indent=2)

        # Save team compositions
        teams = []
        for domain, islands in self.subpops.items():
            for island in islands:
                best = island.best_organism()
                teams.append({
                    'domain': domain,
                    'island_id': island.id,
                    'fitness': best['adjusted_fitness'],
                    'domain_fitness': best['domain_fitness'],
                    'scores': best['scores'],
                    'size': best['tree'].size(),
                    'program': best['tree'].to_str(),
                })
        with open(self.teams_path, 'w') as f:
            json.dump({
                'generation': self.generation,
                'specialists': teams,
                'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='GA Experiment 15: Cooperative Coevolution')
    parser.add_argument('--islands-per-subpop', type=int, default=2)
    parser.add_argument('--island-pop', type=int, default=40)
    parser.add_argument('--cores', type=int, default=2)
    parser.add_argument('--seed', type=int, default=555)
    args = parser.parse_args()

    engine = CooperativeEngine(
        islands_per_subpop=args.islands_per_subpop,
        island_pop=args.island_pop,
        cores=args.cores,
        seed=args.seed,
    )
    engine.run()


if __name__ == '__main__':
    main()
