#!/usr/bin/env python3
"""GA Experiment 12: NEAT-Inspired Speciation

Fork of ga_self_aware.py (v3/v4) replacing single-population selection with
NEAT-style speciation via compatibility distance:

  - Compatibility distance between organisms based on tree structure
    (op-signature comparison at matching positions)
  - Species formed by clustering organisms within delta_t threshold
  - Fitness sharing within species (adjusted = raw / species_size)
  - Species-proportional reproduction (offspring slots ~ avg fitness)
  - Species champion protection (best survives regardless)
  - Dynamic delta_t adjustment (target 3-8 species per island)
  - Stagnation detection per species (removed after 20 epochs stagnant)

Hypothesis: Speciation maintains diversity by preventing cross-species
competition, allowing specialists to develop without being outcompeted
by generalists. Unlike NSGA-II which preserves via Pareto fronts,
speciation creates reproductive barriers that let niches stabilize.

IMPORTANT: When --cores 1, uses sequential loop (no multiprocessing.Pool)
to work on systems without /dev/shm.

Usage:
    python3 ga_exp12_speciation.py                   # default (1 core)
    python3 ga_exp12_speciation.py --cores 4          # parallel
    python3 ga_exp12_speciation.py --islands 8 --island-pop 40
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
# EXTENDED OP SET -- original 28 + 4 self-referential + 6 lifetime learning
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
# TASKS (identical to ga_self_aware / exp7)
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
# EVALUATION -- 4-objective + scalar
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
# COMPATIBILITY DISTANCE (NEAT-inspired)
# ============================================================================

def _tree_op_signature(tree: Node, max_depth: int = 6) -> List[Tuple[int, int]]:
    """Extract (depth, op_index) pairs from a tree via BFS up to max_depth.
    This creates a structural fingerprint for compatibility comparison."""
    signature = []
    queue = [(tree, 0)]
    while queue:
        node, depth = queue.pop(0)
        if depth > max_depth:
            break
        signature.append((depth, node.op.value))
        for child in node.children:
            queue.append((child, depth + 1))
    return signature


def compatibility_distance(tree_a: Node, tree_b: Node,
                           c_disjoint: float = 1.0,
                           c_size: float = 0.4) -> float:
    """Compute compatibility distance between two organisms' trees.

    Uses structural op-signature comparison:
    - Extract BFS traversal of ops with depth tags
    - Count matching vs disjoint positions
    - Normalize by the larger signature length
    - Add size difference penalty
    """
    sig_a = _tree_op_signature(tree_a)
    sig_b = _tree_op_signature(tree_b)

    len_a = len(sig_a)
    len_b = len(sig_b)
    max_len = max(len_a, len_b)
    min_len = min(len_a, len_b)

    if max_len == 0:
        return 0.0

    matching = 0
    for i in range(min_len):
        if sig_a[i] == sig_b[i]:
            matching += 1

    disjoint = max_len - matching

    size_a = tree_a.size()
    size_b = tree_b.size()
    size_diff = abs(size_a - size_b) / max(size_a, size_b, 1)

    normalizer = max(max_len, 1)
    dist = c_disjoint * (disjoint / normalizer) + c_size * size_diff

    return dist


# ============================================================================
# SPECIES
# ============================================================================

class Species:
    _next_id = 0

    def __init__(self, representative: dict):
        Species._next_id += 1
        self.id = Species._next_id
        self.representative = representative
        self.members: List[int] = []  # indices into island population
        self.best_fitness: float = 0.0
        self.avg_fitness: float = 0.0
        self.stagnation: int = 0
        self.age: int = 0

    def update_stats(self, population: List[dict]):
        if not self.members:
            return
        fitnesses = [population[i]['scalar_fitness'] for i in self.members]
        current_best = max(fitnesses)
        self.avg_fitness = sum(fitnesses) / len(fitnesses)

        if current_best > self.best_fitness + 1e-6:
            self.best_fitness = current_best
            self.stagnation = 0
        else:
            self.stagnation += 1

        self.age += 1


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
# SPECIATION ISLAND
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


class SpeciationIsland:
    """Island running NEAT-style speciation evolution."""

    TARGET_SPECIES_MIN = 3
    TARGET_SPECIES_MAX = 8
    STAGNATION_LIMIT = 20

    def __init__(self, island_id: int, pop_size: int, seed: int):
        self.id = island_id
        self.pop_size = pop_size
        self.rng = random.Random(seed)
        self.organisms: List[dict] = []
        self.species_list: List[Species] = []
        self.plasmids: List[Node] = []
        self.epoch = 0
        self.best_scalar = 0.0
        self.stagnation = 0
        self.catastrophes = 0
        self.delta_t = 6.0  # compatibility threshold
        self.species_created = 0

    def initialize(self, scaffold_rate: float = 0.5,
                   transplants: Optional[List[Node]] = None):
        self.organisms = []
        rng = self.rng

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
                    'tree': tree, 'objectives': [0.0, 0.0, 0.0, 0.0],
                    'scalar_fitness': 0.0, 'adjusted_fitness': 0.0,
                    'scores': {}, 'strategy': strategy, 'age': 0,
                    'species_id': -1,
                })
                for _ in range(2):
                    variant = point_mutation(tree, rng, rate=0.2)
                    self.organisms.append({
                        'tree': variant, 'objectives': [0.0, 0.0, 0.0, 0.0],
                        'scalar_fitness': 0.0, 'adjusted_fitness': 0.0,
                        'scores': {}, 'strategy': copy.deepcopy(strategy),
                        'age': 0, 'species_id': -1,
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
                        'tree': hybrid, 'objectives': [0.0, 0.0, 0.0, 0.0],
                        'scalar_fitness': 0.0, 'adjusted_fitness': 0.0,
                        'scores': {}, 'strategy': strategy, 'age': 0,
                        'species_id': -1,
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
                'merge_rate': rng.uniform(0.0, 0.2),
            }

            self.organisms.append({
                'tree': tree, 'objectives': [0.0, 0.0, 0.0, 0.0],
                'scalar_fitness': 0.0, 'adjusted_fitness': 0.0,
                'scores': {}, 'strategy': strategy, 'age': 0,
                'species_id': -1,
            })

    def evaluate_all(self, seed: int = 42):
        for org in self.organisms:
            org['scores'] = evaluate_organism(
                org['tree'], ALL_TASKS, n_trials=8, seed=seed
            )
            org['objectives'] = compute_objectives(org['scores'])
            org['scalar_fitness'] = scalar_fitness(org['objectives'])

    def _speciate(self):
        """Assign organisms to species using compatibility distance."""
        # Clear existing member lists
        for sp in self.species_list:
            sp.members = []

        for i, org in enumerate(self.organisms):
            placed = False
            for sp in self.species_list:
                dist = compatibility_distance(
                    org['tree'], sp.representative['tree'])
                if dist < self.delta_t:
                    sp.members.append(i)
                    org['species_id'] = sp.id
                    placed = True
                    break

            if not placed:
                new_sp = Species(copy.deepcopy(org))
                new_sp.members.append(i)
                org['species_id'] = new_sp.id
                self.species_list.append(new_sp)
                self.species_created += 1

        # Remove empty species
        self.species_list = [sp for sp in self.species_list if sp.members]

        # Update representatives: pick a random member from each species
        for sp in self.species_list:
            rep_idx = self.rng.choice(sp.members)
            sp.representative = copy.deepcopy(self.organisms[rep_idx])

        # Adjust delta_t to target species count
        n_species = len(self.species_list)
        if n_species < self.TARGET_SPECIES_MIN:
            self.delta_t *= 0.95  # tighten: more species
        elif n_species > self.TARGET_SPECIES_MAX:
            self.delta_t *= 1.05  # loosen: fewer species
        self.delta_t = max(1.0, min(20.0, self.delta_t))

    def _compute_adjusted_fitness(self):
        """Fitness sharing: adjusted = raw / species_size."""
        for sp in self.species_list:
            sp_size = len(sp.members)
            for idx in sp.members:
                self.organisms[idx]['adjusted_fitness'] = (
                    self.organisms[idx]['scalar_fitness'] / max(sp_size, 1)
                )
            sp.update_stats(self.organisms)

    def _remove_stagnant_species(self):
        """Remove species stagnant for too long (keep at least 2)."""
        if len(self.species_list) <= 2:
            return

        alive = []
        for sp in self.species_list:
            if sp.stagnation < self.STAGNATION_LIMIT or len(alive) < 2:
                alive.append(sp)

        self.species_list = alive

    def evolve_one_epoch(self):
        self.epoch += 1
        rng = self.rng

        # Evaluate
        self.evaluate_all(seed=42 + (self.epoch % 5))

        # Speciate
        self._speciate()
        self._compute_adjusted_fitness()
        self._remove_stagnant_species()

        # Track global best
        best_org = max(self.organisms, key=lambda o: o['scalar_fitness'])
        if best_org['scalar_fitness'] > self.best_scalar:
            self.best_scalar = best_org['scalar_fitness']
            self.stagnation = 0
        else:
            self.stagnation += 1

        # Catastrophe check
        if self.stagnation > 40 and rng.random() < 0.3:
            best_idx = max(range(len(self.organisms)),
                           key=lambda i: self.organisms[i]['scalar_fitness'])
            kept = [self.organisms[best_idx]]

            while len(kept) < self.pop_size:
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
                kept.append({
                    'tree': tree, 'objectives': [0.0, 0.0, 0.0, 0.0],
                    'scalar_fitness': 0.0, 'adjusted_fitness': 0.0,
                    'scores': {}, 'strategy': strategy, 'age': 0,
                    'species_id': -1,
                })
            self.organisms = kept
            self.species_list = []
            self.catastrophes += 1
            self.stagnation = 0
            return

        # Update plasmid pool from best organisms
        sorted_pop = sorted(self.organisms,
                            key=lambda o: o['scalar_fitness'], reverse=True)
        for org in sorted_pop[:5]:
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

        # Species-proportional reproduction
        total_adj = sum(sp.avg_fitness for sp in self.species_list)
        if total_adj < 1e-12:
            total_adj = 1.0

        offspring = []

        # Champion protection: best of each species survives
        for sp in self.species_list:
            if sp.members:
                champ_idx = max(sp.members,
                                key=lambda i: self.organisms[i]['scalar_fitness'])
                offspring.append(copy.deepcopy(self.organisms[champ_idx]))

        # Allocate remaining slots proportionally
        remaining_slots = self.pop_size - len(offspring)
        for sp in self.species_list:
            if not sp.members:
                continue
            proportion = sp.avg_fitness / total_adj
            n_offspring = max(0, int(round(proportion * remaining_slots)))
            for _ in range(n_offspring):
                if len(offspring) >= self.pop_size:
                    break
                child = self._breed_from_species(sp, rng)
                offspring.append(child)

        # Fill remaining (rounding errors)
        while len(offspring) < self.pop_size:
            sp = rng.choice(self.species_list) if self.species_list else None
            if sp and sp.members:
                child = self._breed_from_species(sp, rng)
            else:
                tree = self_aware_seed(rng) if rng.random() < 0.5 else random_tree(rng, max_depth=5)
                child = {
                    'tree': tree, 'objectives': [0.0, 0.0, 0.0, 0.0],
                    'scalar_fitness': 0.0, 'adjusted_fitness': 0.0,
                    'scores': {}, 'strategy': {
                        'crossover_rate': rng.uniform(0.3, 0.7),
                        'point_mut_rate': rng.uniform(0.1, 0.3),
                        'subtree_mut_rate': rng.uniform(0.05, 0.2),
                        'chaos_rate': rng.uniform(0.0, 0.1),
                        'merge_rate': rng.uniform(0.0, 0.2),
                    }, 'age': 0, 'species_id': -1,
                }
            offspring.append(child)

        # Trim if over
        self.organisms = offspring[:self.pop_size]
        for org in self.organisms:
            org['age'] += 1

    def _breed_from_species(self, sp: Species, rng: random.Random) -> dict:
        """Create one offspring from within a species."""
        parent_idx = self._tournament_within_species(sp, rng)
        parent = self.organisms[parent_idx]
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
            if r < cumulative and len(sp.members) > 2:
                other_idx = self._tournament_within_species(sp, rng)
                other = self.organisms[other_idx]
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
                if r < cumulative and len(sp.members) > 1:
                    # Intra-species crossover
                    other_idx = self._tournament_within_species(sp, rng)
                    other = self.organisms[other_idx]
                    tree = subtree_crossover(parent['tree'], other['tree'], rng)
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

        new_strategy = copy.deepcopy(parent['strategy'])
        for k, v in new_strategy.items():
            if rng.random() < 0.15:
                scale = max(abs(v) * 0.3, 0.02)
                new_strategy[k] = max(0.0, min(1.0, v + rng.gauss(0, scale)))

        return {
            'tree': tree, 'objectives': [0.0, 0.0, 0.0, 0.0],
            'scalar_fitness': 0.0, 'adjusted_fitness': 0.0,
            'scores': {}, 'strategy': new_strategy, 'age': 0,
            'species_id': sp.id,
        }

    def _tournament_within_species(self, sp: Species,
                                   rng: random.Random, k: int = 3) -> int:
        """Tournament selection within a species."""
        candidates = rng.sample(sp.members, min(k, len(sp.members)))
        return max(candidates,
                   key=lambda i: self.organisms[i]['scalar_fitness'])

    def get_best(self) -> dict:
        return max(self.organisms, key=lambda o: o['scalar_fitness'])

    def get_migrants(self, n: int) -> List[dict]:
        sorted_pop = sorted(self.organisms,
                            key=lambda o: o['scalar_fitness'], reverse=True)
        return [copy.deepcopy(o) for o in sorted_pop[:n]]

    def accept_migrants(self, migrants: List[dict]):
        sorted_indices = sorted(
            range(len(self.organisms)),
            key=lambda i: self.organisms[i]['scalar_fitness']
        )
        for i, m in enumerate(migrants):
            if len(sorted_indices) > len(migrants):
                replace_idx = sorted_indices[i]
                m['species_id'] = -1
                self.organisms[replace_idx] = m


# ============================================================================
# PARALLEL WORKER
# ============================================================================

def _run_island_batch(args):
    island, n_epochs = args
    for _ in range(n_epochs):
        island.evolve_one_epoch()

    island.evaluate_all(seed=42 + (island.epoch % 5))

    best = island.get_best()
    n_species = len(island.species_list)
    species_sizes = [len(sp.members) for sp in island.species_list]
    species_stagnation = [sp.stagnation for sp in island.species_list]

    return island, {
        'best_scalar': best['scalar_fitness'],
        'best_objectives': best['objectives'],
        'best_scores': best['scores'],
        'best_size': best['tree'].size(),
        'best_strategy': best['strategy'],
        'n_species': n_species,
        'species_sizes': species_sizes,
        'species_stagnation': species_stagnation,
        'delta_t': island.delta_t,
        'stagnation': island.stagnation,
        'catastrophes': island.catastrophes,
        'epoch': island.epoch,
    }


# ============================================================================
# SPECIATION ENGINE
# ============================================================================

class SpeciationEngine:
    def __init__(self, n_islands=5, island_pop=40, cores=None, seed=333):
        self.n_islands = n_islands
        self.island_pop = island_pop
        self.cores = cores or max(1, mp.cpu_count() - 2)
        self.seed = seed
        self.rng = random.Random(seed)

        self.islands: List[SpeciationIsland] = []
        self.global_best = None
        self.global_best_scalar = 0.0
        self.generation = 0
        self.history = []

        self.save_path = os.path.join(TOOLS_DIR, 'exp12_speciation_state.json')
        self.best_path = os.path.join(TOOLS_DIR, 'exp12_speciation_best.json')
        self.log_path = os.path.join(TOOLS_DIR, 'exp12_speciation_log.jsonl')

    def initialize(self):
        transplants = load_transplants()

        self.islands = []
        for i in range(self.n_islands):
            island = SpeciationIsland(i, self.island_pop,
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

        print(f"\n{'=' * 74}")
        print(f"  NEAT-STYLE SPECIATION EVOLUTION (exp12)")
        print(f"{'=' * 74}")
        print(f"  Islands:     {self.n_islands}")
        print(f"  Pop/island:  {self.island_pop}")
        print(f"  Total:       {self.n_islands * self.island_pop} organisms")
        print(f"  Cores:       {self.cores}")
        print(f"  Selection:   Speciation (compatibility distance)")
        print(f"  Delta_t:     {self.islands[0].delta_t:.1f} (initial)")
        print(f"  Target spp:  {SpeciationIsland.TARGET_SPECIES_MIN}-"
              f"{SpeciationIsland.TARGET_SPECIES_MAX} per island")
        print(f"  Stag limit:  {SpeciationIsland.STAGNATION_LIMIT} epochs/species")
        print(f"  Tasks:")
        print(f"    Memory:    {', '.join(MEMORY_TASKS.keys())}")
        print(f"    Self-ref:  {', '.join(SELF_REF_TASKS.keys())}")
        print(f"    Reasoning: {', '.join(REASONING_TASKS.keys())}")
        print(f"    Real data: {', '.join(REAL_DATA_NAMES)}")
        print(f"  Hypothesis:  Speciation maintains diversity by preventing")
        print(f"               cross-species competition")
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

            # Update global best
            for i, (island, res) in enumerate(zip(self.islands,
                                                   island_results)):
                if res['best_scalar'] > self.global_best_scalar:
                    best_org = island.get_best()
                    self.global_best = {
                        'scalar_fitness': res['best_scalar'],
                        'objectives': res['best_objectives'],
                        'scores': res['best_scores'],
                        'size': res['best_size'],
                        'strategy': res['best_strategy'],
                        'island': i,
                        'program': best_org['tree'].to_str(),
                    }
                    self.global_best_scalar = res['best_scalar']

            # Migration (ring topology)
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

            if self.global_best:
                obj = self.global_best['objectives']
                scores = self.global_best['scores']
                print(f"  BEST: scalar={self.global_best_scalar:.4f}"
                      f"  obj=[{obj[0]:.3f}, {obj[1]:.3f},"
                      f" {obj[2]:.3f}, {obj[3]:.3f}]")

                mem_names = ['delayed_echo', 'sequential_xor', 'running_max',
                             'accumulator', 'state_switcher']
                sr_names = ['sequence_prediction', 'error_correction',
                            'novelty_detection']
                mem_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                  for n in mem_names)
                sr_str = ' '.join(f"{n[:4]}={scores.get(n, 0):.2f}"
                                 for n in sr_names)
                nav = scores.get('persistent_nav', 0)
                rd_names = ['real_line_length', 'real_indentation',
                            'real_nesting']
                rd_str = '  '.join(
                    f"{lbl}={scores.get(n, 0):.2f}"
                    for n, lbl in zip(rd_names,
                                      ['line', 'indent', 'nest']))
                print(f"    mem: {mem_str}")
                print(f"    self: {sr_str}")
                print(f"    real: {rd_str}")
                print(f"    nav={nav:.2f}  size={self.global_best['size']}")

            # Per-island stats
            total_species = 0
            for i, res in enumerate(island_results):
                total_species += res['n_species']
                cat = (f" [CAT x{res['catastrophes']}]"
                       if res['catastrophes'] else "")
                sp_str = ','.join(str(s) for s in res['species_sizes'])
                print(f"    Isl {i}: best={res['best_scalar']:.4f}"
                      f"  spp={res['n_species']} [{sp_str}]"
                      f"  dt={res['delta_t']:.2f}"
                      f"  stag={res['stagnation']:3d}{cat}")

            # Log
            entry = {
                'gen': self.generation,
                'epochs': total_epochs,
                'best_scalar': self.global_best_scalar,
                'best_objectives': (self.global_best.get('objectives', [])
                                    if self.global_best else []),
                'best_scores': (self.global_best.get('scores', {})
                                if self.global_best else {}),
                'total_species': total_species,
                'island_species': [r['n_species'] for r in island_results],
                'island_delta_t': [r['delta_t'] for r in island_results],
                'time_s': round_time,
                'ts': time.strftime('%H:%M:%S'),
            }
            self.history.append(entry)
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')

            report_generation(
                experiment_name='exp12_speciation',
                generation=self.generation,
                best_fitness=self.global_best_scalar,
                scores=self.global_best.get('scores', {}) if self.global_best else {},
                best_program_str=self.global_best.get('program') if self.global_best else None,
                metadata={
                    'objectives': self.global_best.get('objectives', []) if self.global_best else [],
                    'total_species': total_species,
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
        print(f"  Best scalar: {self.global_best_scalar:.4f}")
        if self.global_best:
            obj = self.global_best['objectives']
            print(f"  Objectives: mem={obj[0]:.4f} sr={obj[1]:.4f}"
                  f" rea={obj[2]:.4f} rd={obj[3]:.4f}")
            print(f"  Scores:")
            for k, v in sorted(self.global_best['scores'].items()):
                print(f"    {k:25s}: {v:.4f}")
            print(f"  Strategy:")
            for k, v in sorted(self.global_best['strategy'].items()):
                print(f"    {k:25s}: {v:.4f}")
        print(f"{'=' * 74}")

    def _save(self):
        state = {
            'generation': self.generation,
            'global_best': self.global_best,
            'global_best_scalar': self.global_best_scalar,
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
        description='GA Experiment 12: NEAT-Inspired Speciation')
    parser.add_argument('--islands', type=int, default=5)
    parser.add_argument('--island-pop', type=int, default=40)
    parser.add_argument('--cores', type=int, default=3)
    parser.add_argument('--seed', type=int, default=333)
    args = parser.parse_args()

    engine = SpeciationEngine(
        n_islands=args.islands,
        island_pop=args.island_pop,
        cores=args.cores,
        seed=args.seed,
    )
    engine.run()


if __name__ == '__main__':
    main()
