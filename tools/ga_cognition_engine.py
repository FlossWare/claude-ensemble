#!/usr/bin/env python3
"""Cognitive Evolution Engine — Evolving Programs, Not Parameters

Genetic programming system that evolves actual executable programs
with memory, perception, conditionals, and loops. Organisms are
program trees that run against cognitive tasks and get selected
for genuine reasoning ability.

This is NOT parameter optimization. Organisms are programs that:
  - Perceive inputs through sensory channels
  - Maintain working memory (read/write registers)
  - Make decisions via evolved conditionals
  - Produce outputs through actions
  - Get tested on tasks they've NEVER seen during evolution

Intelligence is detected when evolved programs exhibit:
  1. Zero-shot generalization — solve novel problem structures
  2. Abstraction — discover general rules from examples
  3. Composition — combine learned skills for new tasks
  4. Lifetime learning — improve within a single evaluation
  5. Communication — coordinate between organisms

Unlike current AI (gradient descent on data), this explores whether
selection pressure alone can produce cognitive structures.

Usage:
    python3 ga_cognition_engine.py                    # run forever
    python3 ga_cognition_engine.py --max-epochs 1000  # bounded
    python3 ga_cognition_engine.py --report           # latest findings
    python3 ga_cognition_engine.py --resume           # from checkpoint
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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np


# ============================================================================
# INSTRUCTION SET — the primitives organisms can evolve
# ============================================================================

class Op(Enum):
    # Arithmetic (2 args)
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()      # protected: div by 0 → 0
    MOD = auto()      # protected

    # Comparison (2 args → 0 or 1)
    GT = auto()
    LT = auto()
    EQ = auto()        # approximate equality (|a-b| < 0.1)
    NEQ = auto()

    # Logic (2 args)
    AND = auto()
    OR = auto()
    NOT = auto()       # 1 arg

    # Control (3 args for IF, 2 for WHILE)
    IF = auto()        # if arg0 > 0 then arg1 else arg2
    SEQ = auto()       # execute arg0 then arg1, return arg1

    # Memory (variable args)
    READ = auto()      # read register[int(arg0) % N]
    WRITE = auto()     # write arg1 to register[int(arg0) % N], return arg1

    # Input/Output
    SENSE = auto()     # read input channel int(arg0)
    ACT = auto()       # write arg1 to output channel int(arg0)

    # Constants
    CONST = auto()     # literal float value
    ZERO = auto()
    ONE = auto()
    NEG1 = auto()

    # Accumulation
    INC = auto()       # arg0 + 1
    DEC = auto()       # arg0 - 1
    ABS = auto()       # |arg0|
    SIGN = auto()      # sign(arg0)
    MAX2 = auto()      # max(arg0, arg1)
    MIN2 = auto()      # min(arg0, arg1)


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
}

TERMINAL_OPS = [op for op, a in ARITY.items() if a == 0]
UNARY_OPS = [op for op, a in ARITY.items() if a == 1]
BINARY_OPS = [op for op, a in ARITY.items() if a == 2]
TERNARY_OPS = [op for op, a in ARITY.items() if a == 3]


# ============================================================================
# PROGRAM TREE — the genome of each organism
# ============================================================================

@dataclass
class Node:
    op: Op
    children: List['Node'] = field(default_factory=list)
    value: float = 0.0  # for CONST nodes

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
        child_strs = "\n".join(c.to_str(indent+1) for c in self.children)
        return f"{prefix}({self.op.name}\n{child_strs})"


# ============================================================================
# PROGRAM EXECUTION — virtual machine with safety limits
# ============================================================================

class ExecutionContext:
    MAX_STEPS = 500
    NUM_REGISTERS = 16
    NUM_INPUT_CHANNELS = 8
    NUM_OUTPUT_CHANNELS = 4

    def __init__(self):
        self.registers = [0.0] * self.NUM_REGISTERS
        self.inputs = [0.0] * self.NUM_INPUT_CHANNELS
        self.outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.steps = 0
        self.halted = False

    def reset(self):
        self.registers = [0.0] * self.NUM_REGISTERS
        self.outputs = [0.0] * self.NUM_OUTPUT_CHANNELS
        self.steps = 0
        self.halted = False

    def set_inputs(self, values: List[float]):
        for i, v in enumerate(values[:self.NUM_INPUT_CHANNELS]):
            self.inputs[i] = v


def execute(node: Node, ctx: ExecutionContext) -> float:
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

    # Evaluate children
    args = [execute(c, ctx) for c in node.children]

    # Clamp to prevent overflow
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
        return args[1]  # both evaluated already, return second

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

    return 0.0


# ============================================================================
# COGNITIVE TASKS — what organisms must solve
# ============================================================================

class CognitiveTask:
    """Base class for tasks that test cognitive ability."""
    name: str = "base"
    description: str = ""
    difficulty: int = 1  # 1-5

    def generate_trials(self, n: int, rng: random.Random) -> List[dict]:
        raise NotImplementedError

    def evaluate_trial(self, program: Node, trial: dict) -> float:
        raise NotImplementedError

    def evaluate(self, program: Node, n_trials: int = 20, seed: int = 42) -> float:
        rng = random.Random(seed)
        trials = self.generate_trials(n_trials, rng)
        scores = []
        for trial in trials:
            score = self.evaluate_trial(program, trial)
            scores.append(score)
        return float(np.mean(scores)) if scores else 0.0


class NumberSequenceTask(CognitiveTask):
    """Given a sequence of numbers via input channels, predict the next one.

    Inputs: channel 0-5 = sequence values, channel 6 = position, channel 7 = length
    Output: channel 0 = predicted next value
    """
    name = "sequence_next"
    description = "Predict the next number in a sequence"
    difficulty = 2

    PATTERNS = {
        'constant': lambda i, p: p[0],
        'linear': lambda i, p: p[0] + p[1] * i,
        'quadratic': lambda i, p: p[0] + p[1] * i + p[2] * i * i,
        'geometric': lambda i, p: p[0] * (p[1] ** i),
        'alternating': lambda i, p: p[0] if i % 2 == 0 else p[1],
        'fibonacci_like': None,  # special handling
        'modular': lambda i, p: (p[0] * i + p[1]) % p[2] if p[2] != 0 else 0,
    }

    def generate_trials(self, n, rng):
        trials = []
        pattern_names = list(self.PATTERNS.keys())
        for _ in range(n):
            pattern = rng.choice(pattern_names)
            if pattern == 'fibonacci_like':
                a, b = rng.randint(1, 5), rng.randint(1, 5)
                seq = [a, b]
                for i in range(5):
                    seq.append(seq[-1] + seq[-2])
                target = seq[-1]
                seq = seq[:-1]
            elif pattern == 'constant':
                c = rng.uniform(-5, 5)
                seq = [c] * 6
                target = c
            elif pattern == 'linear':
                a, b = rng.uniform(-3, 3), rng.uniform(-2, 2)
                seq = [a + b * i for i in range(6)]
                target = a + b * 6
            elif pattern == 'quadratic':
                a, b, c = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.3)
                seq = [a + b*i + c*i*i for i in range(6)]
                target = a + b*6 + c*36
            elif pattern == 'geometric':
                a = rng.uniform(0.5, 3)
                r = rng.choice([0.5, 2, -1, 1.5])
                seq = [a * (r**i) for i in range(6)]
                target = a * (r**6)
            elif pattern == 'alternating':
                a, b = rng.uniform(-5, 5), rng.uniform(-5, 5)
                seq = [a if i%2==0 else b for i in range(6)]
                target = a  # position 6 is even
            else:  # modular
                a, b = rng.randint(1, 5), rng.randint(0, 3)
                m = rng.randint(3, 8)
                seq = [(a*i + b) % m for i in range(6)]
                target = (a*6 + b) % m

            # Normalize to reasonable range
            max_abs = max(abs(x) for x in seq + [target]) or 1
            if max_abs > 100:
                seq = [x/max_abs*10 for x in seq]
                target = target/max_abs*10

            trials.append({'sequence': seq, 'target': target, 'pattern': pattern})
        return trials

    def evaluate_trial(self, program, trial):
        ctx = ExecutionContext()
        seq = trial['sequence']
        target = trial['target']

        # Run program multiple times, feeding sequence values
        # Each call: inputs are the last 6 values + position + count
        for step in range(len(seq)):
            ctx.reset()
            for i, v in enumerate(seq[:step+1]):
                if i < 6:
                    ctx.inputs[i] = v
            ctx.inputs[6] = step
            ctx.inputs[7] = len(seq)
            execute(program, ctx)

        prediction = ctx.outputs[0]
        error = abs(prediction - target)
        max_error = max(abs(target), 1.0) * 2
        return max(0.0, 1.0 - error / max_error)


class PatternClassifyTask(CognitiveTask):
    """Classify inputs based on a hidden rule.

    Given examples (input→label pairs), classify a new input.
    Inputs: ch0-3 = test input features, ch4 = example label hint, ch5-7 = context
    Output: ch0 = classification (>0 = class A, ≤0 = class B)
    """
    name = "pattern_classify"
    description = "Learn a classification rule from examples"
    difficulty = 3

    RULES = [
        ('sum_positive', lambda x: sum(x) > 0),
        ('first_gt_last', lambda x: x[0] > x[-1]),
        ('max_gt_2', lambda x: max(x) > 2),
        ('even_count', lambda x: sum(1 for v in x if int(v) % 2 == 0) > len(x)//2),
        ('range_small', lambda x: (max(x) - min(x)) < 3),
        ('ascending', lambda x: all(x[i] <= x[i+1] for i in range(len(x)-1))),
    ]

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            rule_name, rule_fn = rng.choice(self.RULES)

            # Generate training examples
            examples = []
            for _ in range(5):
                x = [rng.uniform(-5, 5) for _ in range(4)]
                label = 1.0 if rule_fn(x) else -1.0
                examples.append((x, label))

            # Generate test case
            test_x = [rng.uniform(-5, 5) for _ in range(4)]
            test_label = 1.0 if rule_fn(test_x) else -1.0

            trials.append({
                'examples': examples,
                'test_input': test_x,
                'test_label': test_label,
                'rule': rule_name,
            })
        return trials

    def evaluate_trial(self, program, trial):
        ctx = ExecutionContext()

        # Feed examples into program to build internal representation
        for ex_input, ex_label in trial['examples']:
            ctx.reset()
            for i, v in enumerate(ex_input[:4]):
                ctx.inputs[i] = v
            ctx.inputs[4] = ex_label  # tell it the answer for training
            ctx.inputs[5] = 1.0       # flag: this is a training example
            execute(program, ctx)
            # Don't reset registers — let it accumulate knowledge

        # Now test
        ctx.steps = 0  # reset step counter but keep registers
        ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
        for i, v in enumerate(trial['test_input'][:4]):
            ctx.inputs[i] = v
        ctx.inputs[4] = 0.0  # no label hint
        ctx.inputs[5] = 0.0  # flag: this is a test
        execute(program, ctx)

        prediction = ctx.outputs[0]
        correct = (prediction > 0) == (trial['test_label'] > 0)
        return 1.0 if correct else 0.0


class CopyTask(CognitiveTask):
    """Read a sequence of values, then reproduce them from memory.

    Phase 1: values presented one at a time (input ch0, ch1=position, ch2=1.0 for "read")
    Phase 2: position given, organism must output the value (ch2=0.0 for "recall")
    """
    name = "copy_recall"
    description = "Memorize and recall a sequence"
    difficulty = 2

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            length = rng.randint(3, 6)
            values = [rng.uniform(-5, 5) for _ in range(length)]
            query_idx = rng.randint(0, length - 1)
            trials.append({'values': values, 'query_idx': query_idx})
        return trials

    def evaluate_trial(self, program, trial):
        ctx = ExecutionContext()
        values = trial['values']

        # Phase 1: present values
        for i, v in enumerate(values):
            ctx.steps = 0
            ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
            ctx.inputs = [v, float(i), 1.0, float(len(values)), 0, 0, 0, 0]
            execute(program, ctx)

        # Phase 2: query
        ctx.steps = 0
        ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
        qi = trial['query_idx']
        ctx.inputs = [0.0, float(qi), 0.0, float(len(values)), 0, 0, 0, 0]
        execute(program, ctx)

        recalled = ctx.outputs[0]
        target = values[qi]
        error = abs(recalled - target)
        return max(0.0, 1.0 - error / max(abs(target) + 1, 1.0))


class ComparisonTask(CognitiveTask):
    """Compare two values and output which relationship holds.

    Input ch0 = a, ch1 = b, ch2 = operation code
    Operation: 0 = is a > b?, 1 = is a == b?, 2 = what is max?, 3 = what is a - b?
    Output ch0 = answer
    """
    name = "comparison"
    description = "Compare values under different operations"
    difficulty = 1

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            a = rng.uniform(-10, 10)
            b = rng.uniform(-10, 10)
            op_code = rng.randint(0, 3)
            if op_code == 0:
                answer = 1.0 if a > b else 0.0
            elif op_code == 1:
                answer = 1.0 if abs(a - b) < 0.5 else 0.0
            elif op_code == 2:
                answer = max(a, b)
            else:
                answer = a - b
            trials.append({'a': a, 'b': b, 'op': op_code, 'answer': answer})
        return trials

    def evaluate_trial(self, program, trial):
        ctx = ExecutionContext()
        ctx.inputs = [trial['a'], trial['b'], float(trial['op']), 0, 0, 0, 0, 0]
        execute(program, ctx)
        prediction = ctx.outputs[0]
        error = abs(prediction - trial['answer'])
        scale = max(abs(trial['answer']), 1.0)
        return max(0.0, 1.0 - error / scale)


class ArithmeticTask(CognitiveTask):
    """Perform arithmetic operations based on an operation code.

    Input ch0 = a, ch1 = b, ch2 = op (0=add, 1=sub, 2=mul, 3=div)
    Output ch0 = result
    """
    name = "arithmetic"
    description = "Perform specified arithmetic operations"
    difficulty = 1

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            a = rng.uniform(-10, 10)
            b = rng.uniform(-10, 10)
            if abs(b) < 0.1:
                b = 1.0
            op = rng.randint(0, 3)
            if op == 0: ans = a + b
            elif op == 1: ans = a - b
            elif op == 2: ans = a * b
            else: ans = a / b
            trials.append({'a': a, 'b': b, 'op': op, 'answer': ans})
        return trials

    def evaluate_trial(self, program, trial):
        ctx = ExecutionContext()
        ctx.inputs = [trial['a'], trial['b'], float(trial['op']), 0, 0, 0, 0, 0]
        execute(program, ctx)
        prediction = ctx.outputs[0]
        error = abs(prediction - trial['answer'])
        scale = max(abs(trial['answer']), 1.0)
        return max(0.0, 1.0 - error / scale)


class NavigationTask(CognitiveTask):
    """Navigate a 1D environment to reach a goal.

    Input ch0 = current position, ch1 = goal position, ch2 = step number
    Output ch0 = movement direction (-1 = left, +1 = right, 0 = stay)

    The program is called repeatedly; position updates based on its output.
    """
    name = "navigation"
    description = "Navigate to a goal position"
    difficulty = 2

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            start = rng.uniform(-10, 10)
            goal = rng.uniform(-10, 10)
            while abs(goal - start) < 1:
                goal = rng.uniform(-10, 10)
            trials.append({'start': start, 'goal': goal})
        return trials

    def evaluate_trial(self, program, trial):
        pos = trial['start']
        goal = trial['goal']
        best_dist = abs(pos - goal)

        for step in range(20):
            ctx = ExecutionContext()
            ctx.inputs = [pos, goal, float(step), best_dist, 0, 0, 0, 0]
            execute(program, ctx)

            move = max(-1, min(1, ctx.outputs[0]))
            pos += move
            dist = abs(pos - goal)
            best_dist = min(best_dist, dist)

            if dist < 0.5:
                return 1.0

        initial_dist = abs(trial['start'] - trial['goal'])
        return max(0.0, 1.0 - best_dist / max(initial_dist, 0.1))


class AnalogicalReasoningTask(CognitiveTask):
    """A is to B as C is to ?

    Given a transformation from A→B, apply the same transformation to C.
    Input ch0 = A, ch1 = B, ch2 = C
    Output ch0 = D (where A:B :: C:D)

    Transformations: add constant, multiply, negate, square, etc.
    """
    name = "analogy"
    description = "A:B :: C:? — find the analogical transformation"
    difficulty = 4

    TRANSFORMS = [
        ('add', lambda x, k: x + k),
        ('mul', lambda x, k: x * k),
        ('negate', lambda x, k: -x),
        ('square', lambda x, k: x * x),
        ('double_add', lambda x, k: 2 * x + k),
        ('abs', lambda x, k: abs(x)),
    ]

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            transform_name, transform_fn = rng.choice(self.TRANSFORMS)
            k = rng.uniform(-3, 3)
            a = rng.uniform(-5, 5)
            b = transform_fn(a, k)
            c = rng.uniform(-5, 5)
            d = transform_fn(c, k)
            trials.append({'a': a, 'b': b, 'c': c, 'd': d, 'transform': transform_name})
        return trials

    def evaluate_trial(self, program, trial):
        ctx = ExecutionContext()
        ctx.inputs = [trial['a'], trial['b'], trial['c'], 0, 0, 0, 0, 0]
        execute(program, ctx)
        prediction = ctx.outputs[0]
        error = abs(prediction - trial['d'])
        scale = max(abs(trial['d']), 1.0)
        return max(0.0, 1.0 - error / scale)


# Registry of all tasks, split into training and held-out
TRAINING_TASKS = {
    'comparison': ComparisonTask(),
    'arithmetic': ArithmeticTask(),
    'navigation': NavigationTask(),
    'copy_recall': CopyTask(),
}

GENERALIZATION_TASKS = {
    'sequence_next': NumberSequenceTask(),
    'pattern_classify': PatternClassifyTask(),
    'analogy': AnalogicalReasoningTask(),
}

ALL_TASKS = {**TRAINING_TASKS, **GENERALIZATION_TASKS}


# ============================================================================
# GENETIC PROGRAMMING OPERATORS
# ============================================================================

def random_tree(rng: random.Random, max_depth: int = 4, current_depth: int = 0) -> Node:
    if current_depth >= max_depth or (current_depth > 1 and rng.random() < 0.3):
        # Terminal
        op = rng.choice(TERMINAL_OPS)
        node = Node(op=op)
        if op == Op.CONST:
            node.value = round(rng.uniform(-5, 5), 2)
        return node

    # Non-terminal
    all_ops = UNARY_OPS + BINARY_OPS + TERNARY_OPS
    op = rng.choice(all_ops)
    arity = ARITY[op]
    children = [random_tree(rng, max_depth, current_depth + 1) for _ in range(arity)]
    return Node(op=op, children=children)


def get_all_nodes(tree: Node) -> List[Tuple[Node, Optional[Node], int]]:
    """Return all nodes with their parent and child index."""
    result = [(tree, None, 0)]
    stack = [(tree, None, 0)]
    while stack:
        node, parent, idx = stack.pop()
        for i, child in enumerate(node.children):
            result.append((child, node, i))
            stack.append((child, node, i))
    return result


def subtree_crossover(p1: Node, p2: Node, rng: random.Random) -> Node:
    child = p1.copy()
    donor = p2.copy()

    child_nodes = get_all_nodes(child)
    donor_nodes = get_all_nodes(donor)

    if len(child_nodes) < 2 or len(donor_nodes) < 1:
        return child

    # Pick a crossover point in child (not root)
    _, cx_parent, cx_idx = rng.choice(child_nodes[1:])

    # Pick a subtree from donor
    donor_node, _, _ = rng.choice(donor_nodes)
    donor_subtree = donor_node.copy()

    # Limit transplanted subtree depth
    if donor_subtree.depth() > 6:
        donor_subtree = random_tree(rng, max_depth=3)

    if cx_parent is not None:
        cx_parent.children[cx_idx] = donor_subtree

    # Size limit
    if child.size() > 100:
        return p1.copy()

    return child


def point_mutation(tree: Node, rng: random.Random, rate: float = 0.1) -> Node:
    mutant = tree.copy()
    nodes = get_all_nodes(mutant)

    for node, parent, idx in nodes:
        if rng.random() >= rate:
            continue

        if node.op == Op.CONST:
            # Perturb constant
            node.value = round(node.value + rng.gauss(0, 1), 2)
            node.value = max(-10, min(10, node.value))
        elif ARITY[node.op] == 0:
            # Replace terminal
            new_op = rng.choice(TERMINAL_OPS)
            node.op = new_op
            if new_op == Op.CONST:
                node.value = round(rng.uniform(-5, 5), 2)
        else:
            # Replace with same-arity op
            arity = ARITY[node.op]
            same_arity = [op for op, a in ARITY.items() if a == arity]
            node.op = rng.choice(same_arity)

    return mutant


def subtree_mutation(tree: Node, rng: random.Random) -> Node:
    mutant = tree.copy()
    nodes = get_all_nodes(mutant)

    if len(nodes) < 2:
        return mutant

    _, mut_parent, mut_idx = rng.choice(nodes[1:])
    new_subtree = random_tree(rng, max_depth=3)

    if mut_parent is not None:
        mut_parent.children[mut_idx] = new_subtree

    if mutant.size() > 100:
        return tree.copy()

    return mutant


# ============================================================================
# ORGANISM — a program with its evaluation history
# ============================================================================

@dataclass
class Organism:
    program: Node
    id: int = 0
    generation: int = 0
    fitness: float = 0.0
    task_scores: Dict[str, float] = field(default_factory=dict)
    generalization_scores: Dict[str, float] = field(default_factory=dict)
    lineage: List[int] = field(default_factory=list)
    program_size: int = 0
    program_depth: int = 0

    def update_stats(self):
        self.program_size = self.program.size()
        self.program_depth = self.program.depth()

    def to_dict(self):
        return {
            'id': self.id,
            'generation': self.generation,
            'fitness': self.fitness,
            'task_scores': self.task_scores,
            'generalization_scores': self.generalization_scores,
            'program_size': self.program_size,
            'program_depth': self.program_depth,
            'lineage': self.lineage[-10:],
            'program': self.program.to_str(),
        }


# ============================================================================
# INTELLIGENCE METRICS — genuinely hard to satisfy
# ============================================================================

@dataclass
class IntelligenceReport:
    epoch: int = 0
    timestamp: str = ""

    # Core metrics — each 0-1, genuinely hard to achieve
    # These are NOT population statistics — they measure what the BEST organism can do
    generalization: float = 0.0     # performance on HELD-OUT tasks never seen during evolution
    abstraction: float = 0.0       # can it solve analogical reasoning?
    memory_use: float = 0.0        # does it use registers meaningfully?
    lifetime_learning: float = 0.0 # does it improve across trials within one evaluation?
    behavioral_complexity: float = 0.0  # is the program non-trivial?
    multi_task: float = 0.0        # can one program solve multiple task types?

    # Aggregate
    intelligence_score: float = 0.0

    # Context
    best_fitness: float = 0.0
    best_size: int = 0
    population_diversity: float = 0.0

    def compute(self):
        self.intelligence_score = (
            self.generalization * 0.30 +       # most important: can it do what it wasn't trained for?
            self.abstraction * 0.25 +           # analogy is a hallmark of intelligence
            self.memory_use * 0.10 +            # using internal state, not just reactive
            self.lifetime_learning * 0.15 +     # adapting within its lifetime
            self.behavioral_complexity * 0.05 + # not just a trivial program
            self.multi_task * 0.15              # genuine generality
        )
        return self.intelligence_score

    def summary(self) -> str:
        return (f"IQ={self.intelligence_score:.4f} "
                f"[gen={self.generalization:.3f} abs={self.abstraction:.3f} "
                f"mem={self.memory_use:.3f} learn={self.lifetime_learning:.3f} "
                f"complex={self.behavioral_complexity:.3f} multi={self.multi_task:.3f}]")

    def to_dict(self):
        return {k: round(v, 6) if isinstance(v, float) else v for k, v in self.__dict__.items()}


# Thresholds — these should be HARD to reach
INTELLIGENCE_LEVELS = {
    'reactive':     0.10,  # better than random on training tasks
    'adaptive':     0.20,  # uses memory, handles multiple tasks
    'cognitive':    0.35,  # generalizes to held-out tasks
    'reasoning':    0.50,  # analogical reasoning + generalization
    'intelligent':  0.70,  # all metrics above 0.5
    'breakthrough': 0.85,  # would be genuinely remarkable
}


# ============================================================================
# EVOLUTION ENGINE
# ============================================================================

class CognitionEngine:
    """Evolves programs toward genuine cognition."""

    def __init__(
        self,
        population_size: int = 60,
        max_depth: int = 6,
        seed: int = 42,
        checkpoint_dir: str = None,
    ):
        self.population_size = population_size
        self.max_depth = max_depth
        self.rng = random.Random(seed)
        self.seed = seed

        self.checkpoint_dir = checkpoint_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'cognition_checkpoints'
        )
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        self.population: List[Organism] = []
        self.epoch = 0
        self.next_id = 0
        self.best_ever: Optional[Organism] = None
        self.metrics_history: List[dict] = []
        self.milestones: Dict[str, int] = {}
        self.stagnation = 0
        self.running = True

        # GP parameters (from meta-GA findings: aggressive exploration works)
        self.crossover_rate = 0.85
        self.point_mutation_rate = 0.15
        self.subtree_mutation_rate = 0.10
        self.reproduction_rate = 0.05  # copy unchanged
        self.tournament_size = 5
        self.elitism = 3
        self.parsimony_coeff = 0.00005  # very light bloat penalty — let complexity emerge

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        print(f"\n[SIGNAL] Checkpointing and stopping...")
        self.running = False

    def _new_id(self):
        self.next_id += 1
        return self.next_id

    def _evaluate_organism(self, org: Organism, tasks: Dict[str, CognitiveTask] = None,
                           n_trials: int = 15, seed: int = 42):
        if tasks is None:
            tasks = TRAINING_TASKS

        scores = []
        for name, task in tasks.items():
            score = task.evaluate(org.program, n_trials=n_trials, seed=seed)
            org.task_scores[name] = score
            scores.append(score)

        mean_score = sum(scores) / len(scores) if scores else 0
        min_score = min(scores) if scores else 0
        # Blend: rewards generalists (min matters) over specialists
        base_fitness = 0.6 * mean_score + 0.4 * min_score

        size = org.program.size()
        # Light bloat penalty
        size_penalty = self.parsimony_coeff * size
        # Complexity floor: programs under 15 nodes are penalized
        # (prevents collapse to trivial constant-output programs)
        complexity_bonus = 0.0 if size >= 15 else -0.05 * (15 - size) / 15

        org.fitness = max(0, base_fitness - size_penalty + complexity_bonus)
        org.update_stats()

    def _evaluate_generalization(self, org: Organism, seed: int = 999):
        for name, task in GENERALIZATION_TASKS.items():
            score = task.evaluate(org.program, n_trials=15, seed=seed)
            org.generalization_scores[name] = score

    def _measure_intelligence(self, org: Organism) -> IntelligenceReport:
        report = IntelligenceReport(
            epoch=self.epoch,
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),
        )

        # 1. GENERALIZATION: how well does it do on held-out tasks?
        if org.generalization_scores:
            report.generalization = float(np.mean(list(org.generalization_scores.values())))

        # 2. ABSTRACTION: specifically the analogy task
        report.abstraction = org.generalization_scores.get('analogy', 0.0)

        # 3. MEMORY USE: does the program actually use READ/WRITE?
        def count_ops(node: Node, target_ops: set) -> int:
            count = 1 if node.op in target_ops else 0
            return count + sum(count_ops(c, target_ops) for c in node.children)

        memory_ops = count_ops(org.program, {Op.READ, Op.WRITE})
        total_ops = org.program.size()
        if total_ops > 0 and memory_ops > 0:
            memory_ratio = memory_ops / total_ops
            memory_score = org.task_scores.get('copy_recall', 0.0)
            report.memory_use = min(1.0, memory_ratio * 5) * memory_score
        else:
            report.memory_use = 0.0

        # 4. LIFETIME LEARNING: does the program perform BETTER after seeing
        #    training examples than without them? This requires it to actually
        #    USE registers to store knowledge from the examples.
        task = PatternClassifyTask()
        rng = random.Random(777)
        trials = task.generate_trials(10, rng)
        score_with_training = 0
        score_without_training = 0
        for trial in trials:
            # WITHOUT training: just test directly (no examples shown)
            ctx_bare = ExecutionContext()
            for i, v in enumerate(trial['test_input'][:4]):
                ctx_bare.inputs[i] = v
            ctx_bare.inputs[5] = 0.0  # test mode
            execute(org.program, ctx_bare)
            pred_bare = ctx_bare.outputs[0]
            score_without_training += (1.0 if (pred_bare > 0) == (trial['test_label'] > 0) else 0.0)

            # WITH training: feed examples first, then test
            ctx_trained = ExecutionContext()
            for ex_input, ex_label in trial['examples']:
                ctx_trained.steps = 0
                ctx_trained.outputs = [0.0] * ctx_trained.NUM_OUTPUT_CHANNELS
                for i, v in enumerate(ex_input[:4]):
                    ctx_trained.inputs[i] = v
                ctx_trained.inputs[4] = ex_label
                ctx_trained.inputs[5] = 1.0
                execute(org.program, ctx_trained)
            ctx_trained.steps = 0
            ctx_trained.outputs = [0.0] * ctx_trained.NUM_OUTPUT_CHANNELS
            for i, v in enumerate(trial['test_input'][:4]):
                ctx_trained.inputs[i] = v
            ctx_trained.inputs[4] = 0.0
            ctx_trained.inputs[5] = 0.0
            execute(org.program, ctx_trained)
            pred_trained = ctx_trained.outputs[0]
            score_with_training += (1.0 if (pred_trained > 0) == (trial['test_label'] > 0) else 0.0)

        score_with_training /= len(trials)
        score_without_training /= len(trials)
        # Only counts if training HELPS and exceeds chance
        if score_with_training > score_without_training and score_with_training > 0.6:
            report.lifetime_learning = min(1.0, (score_with_training - score_without_training) * 3)

        # 5. BEHAVIORAL COMPLEXITY: non-trivial program structure
        has_conditionals = count_ops(org.program, {Op.IF}) > 0
        has_memory = memory_ops > 0
        has_io = count_ops(org.program, {Op.SENSE, Op.ACT}) > 0
        has_arithmetic = count_ops(org.program, {Op.ADD, Op.SUB, Op.MUL, Op.DIV}) > 0
        has_comparison = count_ops(org.program, {Op.GT, Op.LT, Op.EQ}) > 0

        complexity_indicators = sum([has_conditionals, has_memory, has_io, has_arithmetic, has_comparison])
        size_factor = min(1.0, org.program_size / 20)
        report.behavioral_complexity = (complexity_indicators / 5) * size_factor

        # 6. MULTI-TASK: can one program solve multiple task types well?
        # Requires genuinely good performance, not just above random chance
        all_scores = list(org.task_scores.values()) + list(org.generalization_scores.values())
        if all_scores:
            above_competent = [s for s in all_scores if s > 0.7]  # genuinely good, not random
            report.multi_task = len(above_competent) / len(all_scores)

        # Context
        report.best_fitness = org.fitness
        report.best_size = org.program_size
        if self.population:
            sizes = [o.program.size() for o in self.population]
            report.population_diversity = np.std(sizes) / max(np.mean(sizes), 1)

        report.compute()
        return report

    def _behavior_signature(self, org: Organism) -> tuple:
        """Behavioral fingerprint based on task scores, not program structure."""
        return tuple(round(org.task_scores.get(t, 0), 1) for t in sorted(TRAINING_TASKS.keys()))

    def _tournament_select(self) -> Organism:
        candidates = self.rng.sample(self.population, min(self.tournament_size, len(self.population)))
        # 80% fitness-based, 20% novelty-based (pick most behaviorally unique)
        if self.rng.random() < 0.2:
            sigs = [self._behavior_signature(c) for c in candidates]
            pop_sigs = [self._behavior_signature(o) for o in self.population]
            # Score by how rare this behavior is in the population
            novelty_scores = []
            for sig in sigs:
                same = sum(1 for ps in pop_sigs if ps == sig)
                novelty_scores.append(1.0 / same)
            best_idx = novelty_scores.index(max(novelty_scores))
            return candidates[best_idx]
        return max(candidates, key=lambda o: o.fitness)

    def _breed(self) -> Organism:
        r = self.rng.random()
        if r < self.crossover_rate:
            p1 = self._tournament_select()
            p2 = self._tournament_select()
            child_prog = subtree_crossover(p1.program, p2.program, self.rng)
            lineage = p1.lineage + [p1.id]
        elif r < self.crossover_rate + self.point_mutation_rate:
            parent = self._tournament_select()
            child_prog = point_mutation(parent.program, self.rng, rate=0.2)
            lineage = parent.lineage + [parent.id]
        elif r < self.crossover_rate + self.point_mutation_rate + self.subtree_mutation_rate:
            parent = self._tournament_select()
            child_prog = subtree_mutation(parent.program, self.rng)
            lineage = parent.lineage + [parent.id]
        else:
            parent = self._tournament_select()
            child_prog = parent.program.copy()
            lineage = parent.lineage + [parent.id]

        return Organism(
            program=child_prog,
            id=self._new_id(),
            generation=self.epoch,
            lineage=lineage[-10:],
        )

    def _check_milestones(self, report: IntelligenceReport):
        for level, threshold in INTELLIGENCE_LEVELS.items():
            if report.intelligence_score >= threshold and level not in self.milestones:
                # Gate: must actually perform on tasks, not just inflate metrics
                if level in ('reactive',) and report.best_fitness < 0.2:
                    continue  # can't be reactive if training fitness is trivial
                if level in ('adaptive',) and (report.memory_use < 0.05 or report.multi_task < 0.15):
                    continue  # adaptive requires memory use and multi-task
                if level in ('cognitive',) and report.generalization < 0.25:
                    continue  # cognitive requires actual generalization
                if level in ('reasoning',) and report.abstraction < 0.3:
                    continue  # reasoning requires analogical ability
                if level in ('intelligent',) and (report.generalization < 0.5 or report.abstraction < 0.4):
                    continue
                if level in ('breakthrough',) and report.lifetime_learning < 0.3:
                    continue  # breakthrough requires actual lifetime learning
                self.milestones[level] = self.epoch
                print(f"\n{'='*70}")
                print(f"  *** COGNITION LEVEL: {level.upper()} ***")
                print(f"  Epoch {self.epoch}  |  Score: {report.intelligence_score:.6f}  (threshold: {threshold})")
                print(f"  {report.summary()}")
                print(f"  Program size: {report.best_size} nodes")
                if self.best_ever:
                    print(f"  Training scores: {self.best_ever.task_scores}")
                    print(f"  Generalization:  {self.best_ever.generalization_scores}")
                print(f"{'='*70}\n")
                self._checkpoint(f"milestone_{level}")

    def _checkpoint(self, tag: str = "periodic"):
        path = os.path.join(self.checkpoint_dir, f"epoch{self.epoch}_{tag}.json")

        state = {
            'epoch': self.epoch,
            'tag': tag,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'seed': self.seed,
            'milestones': self.milestones,
            'best_ever': self.best_ever.to_dict() if self.best_ever else None,
            'top_5': [o.to_dict() for o in sorted(self.population, key=lambda o: o.fitness, reverse=True)[:5]],
            'metrics_history': self.metrics_history[-200:],
            'gp_params': {
                'crossover_rate': self.crossover_rate,
                'point_mutation_rate': self.point_mutation_rate,
                'subtree_mutation_rate': self.subtree_mutation_rate,
                'tournament_size': self.tournament_size,
                'parsimony_coeff': self.parsimony_coeff,
            },
        }

        with open(path, 'w') as f:
            json.dump(state, f, indent=2)

        latest = os.path.join(self.checkpoint_dir, 'latest.json')
        with open(latest, 'w') as f:
            json.dump(state, f, indent=2)

        return path

    def initialize(self):
        print("=" * 70)
        print("  COGNITIVE EVOLUTION ENGINE")
        print("  Evolving programs, not parameters")
        print("=" * 70)
        print(f"  Population:       {self.population_size} programs")
        print(f"  Max tree depth:   {self.max_depth}")
        print(f"  Training tasks:   {list(TRAINING_TASKS.keys())}")
        print(f"  Held-out tasks:   {list(GENERALIZATION_TASKS.keys())}")
        print(f"  Instruction set:  {len(Op)} operations")
        print(f"  Registers:        {ExecutionContext.NUM_REGISTERS}")
        print(f"  Max steps/exec:   {ExecutionContext.MAX_STEPS}")
        print(f"  Checkpoint dir:   {self.checkpoint_dir}")
        print(f"  Cognition levels: {INTELLIGENCE_LEVELS}")
        print("=" * 70)

        # Random initial population
        self.population = []
        for _ in range(self.population_size):
            org = Organism(
                program=random_tree(self.rng, max_depth=self.max_depth),
                id=self._new_id(),
                generation=0,
            )
            self._evaluate_organism(org)
            self.population.append(org)

        self.best_ever = max(self.population, key=lambda o: o.fitness)
        self._evaluate_generalization(self.best_ever)

        print(f"\nInitial best fitness: {self.best_ever.fitness:.6f}")
        print(f"  Size: {self.best_ever.program_size} nodes, Depth: {self.best_ever.program_depth}")
        print(f"  Training:       {self.best_ever.task_scores}")
        print(f"  Generalization: {self.best_ever.generalization_scores}")

    def run_epoch(self) -> IntelligenceReport:
        self.epoch += 1

        # Adaptive mutation when stagnating
        if self.stagnation > 20:
            self.subtree_mutation_rate = min(0.3, 0.10 + 0.005 * self.stagnation)
            self.point_mutation_rate = min(0.3, 0.15 + 0.005 * self.stagnation)
        else:
            self.subtree_mutation_rate = 0.10
            self.point_mutation_rate = 0.15

        # Elitism
        self.population.sort(key=lambda o: o.fitness, reverse=True)
        new_pop = [Organism(
            program=o.program.copy(),
            id=o.id,
            generation=o.generation,
            fitness=o.fitness,
            task_scores=dict(o.task_scores),
            generalization_scores=dict(o.generalization_scores),
            lineage=list(o.lineage),
        ) for o in self.population[:self.elitism]]

        # Breed
        while len(new_pop) < self.population_size:
            child = self._breed()
            # Vary evaluation seed slightly for robustness
            eval_seed = 42 + (self.epoch % 5)
            self._evaluate_organism(child, seed=eval_seed)
            new_pop.append(child)

        self.population = new_pop

        # Update best
        current_best = max(self.population, key=lambda o: o.fitness)
        improved = False
        if current_best.fitness > (self.best_ever.fitness if self.best_ever else 0):
            self.best_ever = current_best
            self.stagnation = 0
            improved = True
        else:
            self.stagnation += 1

        # Periodically evaluate generalization (expensive)
        if self.epoch % 10 == 0 or improved:
            self._evaluate_generalization(self.best_ever)

        # Measure intelligence
        report = self._measure_intelligence(self.best_ever)
        self.metrics_history.append(report.to_dict())
        self._check_milestones(report)

        return report

    def run(self, max_epochs: int = None):
        self.initialize()
        start_time = time.time()

        print(f"\n{'Epoch':>6} | {'Fit':>7} | {'Size':>5} | {'Stag':>4} | Intelligence")
        print("-" * 90)

        while self.running:
            report = self.run_epoch()

            if self.epoch <= 5 or self.epoch % 10 == 0:
                print(f"{self.epoch:6d} | {report.best_fitness:7.4f} | "
                      f"{report.best_size:5d} | {self.stagnation:4d} | {report.summary()}")
                sys.stdout.flush()

            if self.epoch % 100 == 0:
                elapsed = time.time() - start_time
                eps = self.epoch / max(elapsed, 1)
                print(f"\n--- Epoch {self.epoch} ({elapsed:.0f}s, {eps:.1f} ep/s) ---")
                print(f"  Training:       {self.best_ever.task_scores}")
                print(f"  Generalization: {self.best_ever.generalization_scores}")
                print(f"  Milestones:     {self.milestones}")
                print(f"  Mutation rates: point={self.point_mutation_rate:.3f} subtree={self.subtree_mutation_rate:.3f}")
                print(f"  Best program:\n{self.best_ever.program.to_str(indent=2)[:500]}")
                path = self._checkpoint("periodic")
                print(f"  [checkpoint: {path}]")
                print()
                sys.stdout.flush()

            if max_epochs and self.epoch >= max_epochs:
                break

        # Final report
        print(f"\n{'='*70}")
        print(f"  EVOLUTION COMPLETE — {self.epoch} epochs")
        print(f"{'='*70}")
        final = self._measure_intelligence(self.best_ever)
        print(f"  Intelligence: {final.summary()}")
        print(f"  Training:     {self.best_ever.task_scores}")
        print(f"  Generalize:   {self.best_ever.generalization_scores}")
        print(f"  Program:      {self.best_ever.program_size} nodes, depth {self.best_ever.program_depth}")
        if self.milestones:
            print(f"  Milestones:   {self.milestones}")
        else:
            print(f"  No cognition milestones reached.")
        print(f"\n  Best program:")
        print(self.best_ever.program.to_str(indent=2)[:1000])
        self._checkpoint("final")
        print(f"{'='*70}")
        sys.stdout.flush()

        return final


def show_report(checkpoint_dir):
    latest = os.path.join(checkpoint_dir, 'latest.json')
    if not os.path.exists(latest):
        print("No checkpoint found.")
        return
    with open(latest) as f:
        state = json.load(f)
    print("=" * 70)
    print("  COGNITIVE EVOLUTION REPORT")
    print("=" * 70)
    print(f"  Epoch:      {state['epoch']}")
    print(f"  Timestamp:  {state['timestamp']}")
    if state.get('best_ever'):
        be = state['best_ever']
        print(f"  Best fitness:  {be['fitness']:.6f}")
        print(f"  Program size:  {be['program_size']} nodes")
        print(f"  Training:      {be['task_scores']}")
        print(f"  Generalize:    {be['generalization_scores']}")
        print(f"\n  Program:")
        print(be.get('program', 'N/A')[:500])
    if state.get('milestones'):
        print(f"\n  Milestones: {state['milestones']}")
    if state.get('metrics_history'):
        last = state['metrics_history'][-1]
        print(f"\n  Latest metrics:")
        for k, v in sorted(last.items()):
            if isinstance(v, float):
                print(f"    {k:25s}: {v:.6f}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Cognitive Evolution Engine')
    parser.add_argument('--max-epochs', type=int, default=None)
    parser.add_argument('--population', type=int, default=60)
    parser.add_argument('--max-depth', type=int, default=6)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--report', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--checkpoint-dir', type=str, default=None)
    args = parser.parse_args()

    ckpt_dir = args.checkpoint_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'cognition_checkpoints'
    )

    if args.report:
        show_report(ckpt_dir)
        return

    engine = CognitionEngine(
        population_size=args.population,
        max_depth=args.max_depth,
        seed=args.seed,
        checkpoint_dir=ckpt_dir,
    )
    engine.run(max_epochs=args.max_epochs)


if __name__ == '__main__':
    main()
