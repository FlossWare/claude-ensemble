#!/usr/bin/env python3
"""GA Experiment 8: Automatically Defined Functions (ADFs)

Fork of ga_self_aware.py. Adds three ADF subroutine slots per organism.
Each organism has a main program tree plus 3 reusable ADF trees that
the main tree can call via CALL_ADF0/1/2 ops.

Hypothesis: All 9 tasks share common subproblems (store-recall,
conditional-increment, compare-with-threshold). Monolithic trees can't
factor these out. ADFs let organisms evolve reusable subroutines.

New ops (5):
  CALL_ADF0  - 2 args: call ADF 0 with (arg0, arg1)
  CALL_ADF1  - 2 args: call ADF 1 with (arg0, arg1)
  CALL_ADF2  - 2 args: call ADF 2 with (arg0, arg1)
  ADF_ARG0   - 0 args: returns current ADF argument 0
  ADF_ARG1   - 0 args: returns current ADF argument 1

Recursion guard: max ADF call depth = 1 (ADFs cannot call other ADFs).

ADF workspace: registers 12-15 are saved/restored around ADF calls.

Usage:
    python3 ga_exp8_adf.py              # run with defaults
    python3 ga_exp8_adf.py --cores 3    # explicit core count
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


# ============================================================================
# EXTENDED OP SET -- original 32 + 5 ADF ops
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

    # Self-referential (from v3)
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

    # === ADF OPS (new in exp8) ===
    CALL_ADF0 = auto()  # 2 args: call ADF 0 with (arg0, arg1)
    CALL_ADF1 = auto()  # 2 args: call ADF 1 with (arg0, arg1)
    CALL_ADF2 = auto()  # 2 args: call ADF 2 with (arg0, arg1)
    ADF_ARG0 = auto()   # 0 args: returns current ADF argument 0
    ADF_ARG1 = auto()   # 0 args: returns current ADF argument 1


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
    # ADF
    Op.CALL_ADF0: 2, Op.CALL_ADF1: 2, Op.CALL_ADF2: 2,
    Op.ADF_ARG0: 0, Op.ADF_ARG1: 0,
}

# Full op lists (all ops)
TERMINAL_OPS = [op for op, a in ARITY.items() if a == 0]
UNARY_OPS = [op for op, a in ARITY.items() if a == 1]
BINARY_OPS = [op for op, a in ARITY.items() if a == 2]
TERNARY_OPS = [op for op, a in ARITY.items() if a == 3]

# ADF op sets
ADF_CALL_OPS = {Op.CALL_ADF0, Op.CALL_ADF1, Op.CALL_ADF2}
ADF_ARG_OPS = {Op.ADF_ARG0, Op.ADF_ARG1}

# Ops for MAIN tree generation (no ADF_ARG*)
MAIN_TERMINALS = [op for op in TERMINAL_OPS if op not in ADF_ARG_OPS]
MAIN_UNARY = UNARY_OPS[:]
MAIN_BINARY = BINARY_OPS[:]  # includes CALL_ADF*
MAIN_TERNARY = TERNARY_OPS[:]

# Ops for ADF tree generation (no CALL_ADF*)
ADF_TERMINALS = [op for op in TERMINAL_OPS if op not in ADF_CALL_OPS]
ADF_UNARY = UNARY_OPS[:]
ADF_BINARY = [op for op in BINARY_OPS if op not in ADF_CALL_OPS]
ADF_TERNARY = TERNARY_OPS[:]

# Ops-by-arity for point mutation in main vs ADF context
MAIN_OPS_BY_ARITY = defaultdict(list)
for _op, _a in ARITY.items():
    if _op not in ADF_ARG_OPS:
        MAIN_OPS_BY_ARITY[_a].append(_op)

ADF_OPS_BY_ARITY = defaultdict(list)
for _op, _a in ARITY.items():
    if _op not in ADF_CALL_OPS:
        ADF_OPS_BY_ARITY[_a].append(_op)

# Subsets for analysis
MEMORY_OPS = {Op.READ, Op.WRITE}
SELF_REF_OPS = {Op.STEP, Op.LAST_OUT, Op.PREDICT, Op.SURPRISE}

OP_NAMES = {op.name: op for op in Op}


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
# PROGRAM PARSER -- reconstruct trees from text representation
# ============================================================================

def parse_program(text: str) -> Optional[Node]:
    """Parse S-expression program text back into a Node tree.
    Handles truncated programs gracefully (fills missing children with ZERO)."""
    if not text or not text.strip():
        return None
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
# SELF-AWARE EXECUTION CONTEXT (extended with ADF support)
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

        # ADF state
        self.adfs = []              # List of 3 ADF Node trees
        self.adf_args = [0.0, 0.0]  # Current ADF arguments
        self.adf_call_depth = 0     # Recursion guard
        self.adf_calls = [0, 0, 0]  # Dynamic call counts per ADF

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
        self.adf_args = [0.0, 0.0]
        self.adf_call_depth = 0
        self.adf_calls = [0, 0, 0]


# ============================================================================
# ADF CALL HELPER
# ============================================================================

def _call_adf(ctx: SelfAwareContext, adf_idx: int,
              arg0: float, arg1: float) -> float:
    """Execute an ADF with the given arguments.

    Recursion guard: max call depth = 1 (ADFs cannot call other ADFs).
    Registers 12-15 are saved and restored (ADF workspace).
    """
    if ctx.adf_call_depth >= 1:
        return 0.0
    if adf_idx >= len(ctx.adfs) or ctx.adfs[adf_idx] is None:
        return 0.0

    # Save workspace registers (12-15) and current ADF args
    saved_regs = ctx.registers[12:16][:]
    saved_args = ctx.adf_args[:]

    # Set ADF arguments and increment depth
    ctx.adf_args = [arg0, arg1]
    ctx.adf_call_depth += 1
    ctx.adf_calls[adf_idx] += 1

    # Execute the ADF tree
    result = execute(ctx.adfs[adf_idx], ctx)

    # Restore state
    ctx.adf_call_depth -= 1
    ctx.adf_args = saved_args
    ctx.registers[12:16] = saved_regs

    return result


# ============================================================================
# EXECUTE -- handles all ops including self-referential and ADF
# ============================================================================

def execute(node: Node, ctx: SelfAwareContext) -> float:
    if ctx.steps >= ctx.MAX_STEPS or ctx.halted:
        return 0.0
    ctx.steps += 1

    op = node.op

    # Terminals (arity 0)
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
    if op == Op.ADF_ARG0:
        return ctx.adf_args[0]
    if op == Op.ADF_ARG1:
        return ctx.adf_args[1]

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

    # ADF calls
    if op == Op.CALL_ADF0:
        return _call_adf(ctx, 0, args[0], args[1])
    if op == Op.CALL_ADF1:
        return _call_adf(ctx, 1, args[0], args[1])
    if op == Op.CALL_ADF2:
        return _call_adf(ctx, 2, args[0], args[1])

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
    """Generate random MAIN program tree (no ADF_ARG ops, includes CALL_ADF)."""
    if max_depth <= 1:
        if rng.random() < self_aware_bias and rng.random() < 0.5:
            return Node(op=Op.STEP)
        op = rng.choice(MAIN_TERMINALS)
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
        op = rng.choice(MAIN_TERMINALS)
    elif rng.random() < 0.4:
        op = rng.choice(MAIN_UNARY)
    elif rng.random() < 0.7:
        op = rng.choice(MAIN_BINARY)  # includes CALL_ADF*
    else:
        op = rng.choice(MAIN_TERNARY)

    arity = ARITY[op]
    if arity == 0:
        if op == Op.CONST:
            return Node(op=op, value=rng.uniform(-5, 5))
        return Node(op=op)

    children = [random_tree(rng, max_depth - 1, self_aware_bias)
                for _ in range(arity)]
    return Node(op=op, children=children)


def random_adf_tree(rng: random.Random, max_depth: int = 4) -> Node:
    """Generate random ADF tree (no CALL_ADF ops, 20% ADF_ARG terminals)."""
    if max_depth <= 1:
        # 20% chance of ADF_ARG0 or ADF_ARG1
        if rng.random() < 0.20:
            return Node(op=rng.choice([Op.ADF_ARG0, Op.ADF_ARG1]))
        # Non-ADF-ARG terminals (also exclude CALL_ADF which are arity 2)
        base_terminals = [op for op in TERMINAL_OPS
                          if op not in ADF_ARG_OPS and op not in ADF_CALL_OPS]
        op = rng.choice(base_terminals)
        if op == Op.CONST:
            return Node(op=op, value=rng.uniform(-5, 5))
        return Node(op=op)

    if rng.random() < 0.3:
        # Terminal with 20% ADF_ARG chance
        if rng.random() < 0.20:
            return Node(op=rng.choice([Op.ADF_ARG0, Op.ADF_ARG1]))
        base_terminals = [op for op in ADF_TERMINALS
                          if op not in ADF_ARG_OPS]
        op = rng.choice(base_terminals)
        if op == Op.CONST:
            return Node(op=op, value=rng.uniform(-5, 5))
        return Node(op=op)
    elif rng.random() < 0.4:
        op = rng.choice(ADF_UNARY)
    elif rng.random() < 0.8:
        op = rng.choice(ADF_BINARY)
    else:
        op = rng.choice(ADF_TERNARY)

    arity = ARITY[op]
    if arity == 0:
        if op == Op.CONST:
            return Node(op=op, value=rng.uniform(-5, 5))
        return Node(op=op)

    children = [random_adf_tree(rng, max_depth - 1) for _ in range(arity)]
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
    """Swap a random subtree between two trees."""
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
                   rate: float = 0.15,
                   ops_by_arity: dict = None) -> Node:
    """Mutate individual ops to same-arity alternatives."""
    if ops_by_arity is None:
        ops_by_arity = MAIN_OPS_BY_ARITY
    child = tree.copy()
    nodes = get_all_nodes(child)
    for node, _, _ in nodes:
        if rng.random() < rate:
            arity = ARITY[node.op]
            candidates = ops_by_arity.get(arity, [])
            if candidates:
                node.op = rng.choice(candidates)
                if node.op == Op.CONST:
                    node.value = rng.uniform(-5, 5)
    return child


def subtree_mutation(tree: Node, rng: random.Random,
                     subtree_gen=None) -> Node:
    """Replace a random subtree with a freshly generated one."""
    if subtree_gen is None:
        subtree_gen = lambda: random_tree(rng, max_depth=3)
    child = tree.copy()
    nodes = get_all_nodes(child)
    if len(nodes) > 1:
        _, p, i = rng.choice(nodes[1:])
        if p is not None:
            p.children[i] = subtree_gen()
    return child


def organism_size(organism: dict) -> int:
    """Total node count across main tree and all ADFs."""
    total = organism['main'].size()
    for adf in organism['adfs']:
        total += adf.size()
    return total


# ============================================================================
# V2 MEMORY TASKS (baseline -- must still solve these)
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

    def evaluate(self, tree, trial, adfs=None):
        ctx = SelfAwareContext()
        ctx.adfs = adfs or []
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

    def evaluate(self, tree, trial, adfs=None):
        ctx = SelfAwareContext()
        ctx.adfs = adfs or []
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

    def evaluate(self, tree, trial, adfs=None):
        ctx = SelfAwareContext()
        ctx.adfs = adfs or []
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

    def evaluate(self, tree, trial, adfs=None):
        ctx = SelfAwareContext()
        ctx.adfs = adfs or []
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

    def evaluate(self, tree, trial, adfs=None):
        ctx = SelfAwareContext()
        ctx.adfs = adfs or []
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

    def evaluate(self, tree, trial, adfs=None):
        ctx = SelfAwareContext()
        ctx.adfs = adfs or []
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

    def evaluate(self, tree, trial, adfs=None):
        ctx = SelfAwareContext()
        ctx.adfs = adfs or []
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

    def evaluate(self, tree, trial, adfs=None):
        ctx = SelfAwareContext()
        ctx.adfs = adfs or []
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
    """Detect an oddball in a regular pattern using SURPRISE."""
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

    def evaluate(self, tree, trial, adfs=None):
        ctx = SelfAwareContext()
        ctx.adfs = adfs or []
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
                continue  # skip warmup

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

def evaluate_organism(organism: dict, tasks: dict, n_trials: int = 10,
                      seed: int = 42) -> dict:
    """Evaluate an organism (main + ADFs) against all tasks."""
    main = organism['main']
    adfs = organism['adfs']
    scores = {}
    for name, task in tasks.items():
        rng = random.Random(seed)
        trials = task.generate_trials(n_trials, rng)
        trial_scores = [task.evaluate(main, trial, adfs=adfs)
                        for trial in trials]
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
# SEED PATTERNS
# ============================================================================

def self_aware_seed(rng: random.Random) -> Node:
    """Generate MAIN trees with self-referential patterns baked in.
    Same 16 patterns as ga_self_aware.py."""
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


def adf_seed(rng: random.Random, adf_idx: int) -> Node:
    """Generate seed ADF trees for the 3 ADF slots."""
    if adf_idx == 0:
        # ADF0: store-recall pattern
        # WRITE(reg12, ADF_ARG0) then READ(reg12)
        return Node(op=Op.SEQ, children=[
            Node(op=Op.WRITE, children=[
                Node(op=Op.CONST, value=12.0),
                Node(op=Op.ADF_ARG0)
            ]),
            Node(op=Op.READ, children=[
                Node(op=Op.CONST, value=12.0)
            ])
        ])
    elif adf_idx == 1:
        # ADF1: conditional pattern
        # IF_POS(ADF_ARG0, ADF_ARG1, ZERO)
        return Node(op=Op.IF, children=[
            Node(op=Op.GT, children=[
                Node(op=Op.ADF_ARG0),
                Node(op=Op.ZERO)
            ]),
            Node(op=Op.ADF_ARG1),
            Node(op=Op.ZERO)
        ])
    else:
        # ADF2: comparison pattern
        # SUB(ADF_ARG0, ADF_ARG1)
        return Node(op=Op.SUB, children=[
            Node(op=Op.ADF_ARG0),
            Node(op=Op.ADF_ARG1)
        ])


# ============================================================================
# ORGANISM HELPERS
# ============================================================================

def make_organism(rng: random.Random, main: Node = None,
                  adfs: List[Node] = None, scaffold_rate: float = 0.5,
                  strategy: dict = None, max_depth: int = 5) -> dict:
    """Create a complete organism with main tree + 3 ADFs."""
    if main is None:
        if rng.random() < scaffold_rate:
            main = self_aware_seed(rng)
        else:
            main = random_tree(rng, max_depth=max_depth)

    if adfs is None:
        adfs = []
        for i in range(3):
            if rng.random() < 0.5:
                adfs.append(adf_seed(rng, i))
            else:
                adfs.append(random_adf_tree(rng))

    if strategy is None:
        strategy = {
            'crossover_rate': rng.uniform(0.3, 0.7),
            'point_mut_rate': rng.uniform(0.05, 0.3),
            'subtree_mut_rate': rng.uniform(0.05, 0.2),
            'chaos_rate': rng.uniform(0.0, 0.1),
            'merge_rate': rng.uniform(0.0, 0.2),
        }

    return {
        'main': main,
        'adfs': adfs,
        'fitness': 0.0,
        'scores': {},
        'strategy': strategy,
        'age': 0,
    }


def organism_to_str(organism: dict) -> str:
    """Serialize organism (main + ADFs) to text."""
    parts = ['MAIN:', organism['main'].to_str()]
    for i, adf in enumerate(organism['adfs']):
        parts.append(f'ADF{i}:')
        parts.append(adf.to_str())
    return '\n'.join(parts)


def parse_organism_str(text: str) -> Optional[dict]:
    """Parse serialized organism text back into main + ADFs.
    Handles both ADF format and legacy single-tree format."""
    if not text:
        return None

    if 'MAIN:' in text:
        # ADF format: split on MAIN: / ADF0: / ADF1: / ADF2:
        sections = {}
        current_key = None
        current_lines = []

        for line in text.split('\n'):
            stripped = line.strip()
            if stripped in ('MAIN:', 'ADF0:', 'ADF1:', 'ADF2:'):
                if current_key is not None:
                    sections[current_key] = '\n'.join(current_lines)
                current_key = stripped.rstrip(':')
                current_lines = []
            else:
                current_lines.append(line)

        if current_key is not None:
            sections[current_key] = '\n'.join(current_lines)

        main = parse_program(sections.get('MAIN', ''))
        adfs = [
            parse_program(sections.get(f'ADF{i}', '')) or Node(op=Op.ZERO)
            for i in range(3)
        ]
        if main is None:
            return None
        return {'main': main, 'adfs': adfs}
    else:
        # Legacy single-tree format
        main = parse_program(text)
        if main is None:
            return None
        return {
            'main': main,
            'adfs': [Node(op=Op.ZERO), Node(op=Op.ZERO), Node(op=Op.ZERO)]
        }


# ============================================================================
# ISLAND
# ============================================================================

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_transplants() -> list:
    """Load best organisms from previous runs for cross-pollination.
    Returns list of (main_tree, adfs_or_None) tuples."""
    transplants = []
    for path in [
        os.path.join(TOOLS_DIR, 'exp8_adf_best.json'),
        os.path.join(TOOLS_DIR, 'self_aware_best.json'),
        os.path.join(TOOLS_DIR, 'memory_pressure_v2_best.json'),
    ]:
        try:
            with open(path) as f:
                data = json.load(f)

            if 'program_main' in data:
                # ADF format
                main = parse_program(data['program_main'])
                adfs = [
                    parse_program(data.get(f'program_adf{i}', ''))
                    or Node(op=Op.ZERO)
                    for i in range(3)
                ]
            else:
                # Legacy single-tree format
                main = parse_program(data.get('program', ''))
                adfs = None  # will be filled with random ADFs

            if main and main.size() > 3:
                transplants.append((main, adfs))
                print(f"  Loaded transplant from {os.path.basename(path)}:"
                      f" {main.size()} nodes")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return transplants


class ADFIsland:
    MAX_MAIN_SIZE = 250
    MAX_ADF_SIZE = 80
    MAX_TOTAL_SIZE = 400

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
                   transplants: Optional[list] = None):
        self.organisms = []
        rng = self.rng

        # Inject transplants into first few islands
        if transplants and self.id < len(transplants) * 3:
            for main_tree, adfs in transplants:
                main = main_tree.copy()
                if adfs is not None:
                    adf_copies = [adf.copy() for adf in adfs]
                else:
                    adf_copies = [adf_seed(rng, i) for i in range(3)]

                org = make_organism(rng, main=main, adfs=adf_copies)
                self.organisms.append(org)

                # Create mutated variants
                for _ in range(2):
                    variant_main = point_mutation(main, rng, rate=0.2,
                                                 ops_by_arity=MAIN_OPS_BY_ARITY)
                    variant_adfs = [
                        point_mutation(adf, rng, rate=0.15,
                                       ops_by_arity=ADF_OPS_BY_ARITY)
                        for adf in adf_copies
                    ]
                    self.organisms.append(
                        make_organism(rng, main=variant_main,
                                      adfs=variant_adfs))

            # Cross transplants if we have at least 2
            if len(transplants) >= 2:
                for _ in range(3):
                    hybrid_main = subtree_crossover(
                        transplants[0][0], transplants[1][0], rng)
                    # Mix ADFs from both parents
                    hybrid_adfs = []
                    for i in range(3):
                        parent_idx = rng.choice([0, 1])
                        src_adfs = transplants[parent_idx][1]
                        if src_adfs is not None:
                            hybrid_adfs.append(src_adfs[i].copy())
                        else:
                            hybrid_adfs.append(adf_seed(rng, i))
                    self.organisms.append(
                        make_organism(rng, main=hybrid_main,
                                      adfs=hybrid_adfs))

        # Fill remaining with scaffolded + random
        while len(self.organisms) < self.pop_size:
            depth = 5 + (self.id % 3)
            org = make_organism(rng, scaffold_rate=scaffold_rate,
                                max_depth=depth)
            self.organisms.append(org)

    def evaluate_all(self, seed: int = 42):
        for org in self.organisms:
            org['scores'] = evaluate_organism(
                org, ALL_TASKS, n_trials=8, seed=seed
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
        if self.stagnation > 40 and rng.random() < 0.3:
            keep = max(3, self.pop_size // 5)
            self.organisms = self.organisms[:keep]
            while len(self.organisms) < self.pop_size:
                depth = rng.randint(4, 7)
                org = make_organism(rng, scaffold_rate=0.6,
                                    max_depth=depth)
                self.organisms.append(org)
            self.catastrophes += 1
            self.stagnation = 0
            return

        # Plasmid pool: prefer memory + self-ref subtrees from main trees
        for org in self.organisms[:3]:
            nodes = get_all_nodes(org['main'])
            for node, _, _ in nodes:
                has_relevant = any(
                    n.op in (Op.READ, Op.WRITE, Op.PREDICT, Op.SURPRISE,
                             Op.LAST_OUT, Op.CALL_ADF0, Op.CALL_ADF1,
                             Op.CALL_ADF2)
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

        child_main = None
        child_adfs = None

        cumulative = s.get('chaos_rate', 0)
        if r < cumulative:
            # Chaos: generate entirely new organism
            if rng.random() < 0.6:
                child_main = self_aware_seed(rng)
            else:
                child_main = random_tree(rng, max_depth=6)
            child_adfs = [
                adf_seed(rng, i) if rng.random() < 0.5
                else random_adf_tree(rng)
                for i in range(3)
            ]
        else:
            cumulative += s.get('merge_rate', 0)
            if r < cumulative and len(self.organisms) > 2:
                # Merge (HGT): graft memory subtree from another organism
                other = self._tournament(rng, k=3)
                child_main = parent['main'].copy()
                child_adfs = [adf.copy() for adf in parent['adfs']]
                donor_nodes = get_all_nodes(other['main'])
                mem_subtrees = [
                    (n, p, i) for n, p, i in donor_nodes
                    if any(nn.op in (Op.READ, Op.WRITE, Op.IF, Op.PREDICT,
                                     Op.SURPRISE, Op.LAST_OUT,
                                     Op.CALL_ADF0, Op.CALL_ADF1,
                                     Op.CALL_ADF2)
                           for nn, _, _ in get_all_nodes(n))
                    and 3 <= n.size() <= 30
                ]
                if not mem_subtrees:
                    mem_subtrees = [(n, p, i) for n, p, i in donor_nodes
                                   if 3 <= n.size() <= 20]
                if mem_subtrees:
                    graft = rng.choice(mem_subtrees)[0].copy()
                    host_nodes = get_all_nodes(child_main)
                    if len(host_nodes) > 1:
                        _, hp, hi = rng.choice(host_nodes[1:])
                        if hp is not None:
                            hp.children[hi] = graft
                if child_main.size() > self.MAX_MAIN_SIZE:
                    child_main = parent['main'].copy()
            else:
                cumulative += s['crossover_rate']
                if r < cumulative:
                    # Crossover: 3 types
                    child_main, child_adfs = self._crossover(parent, rng)
                else:
                    # Mutation: target main (60%) or ADF (40%)
                    child_main, child_adfs = self._mutate(parent, rng)

        # Defaults from parent if not set
        if child_main is None:
            child_main = parent['main'].copy()
        if child_adfs is None:
            child_adfs = [adf.copy() for adf in parent['adfs']]

        # HGT from plasmid pool (main tree only)
        if self.plasmids and rng.random() < 0.1:
            plasmid = rng.choice(self.plasmids).copy()
            nodes = get_all_nodes(child_main)
            if len(nodes) > 1:
                _, pn, idx = rng.choice(nodes[1:])
                if pn is not None:
                    pn.children[idx] = plasmid

        # Size limit enforcement
        if child_main.size() > self.MAX_MAIN_SIZE:
            child_main = parent['main'].copy()
        for i in range(3):
            if child_adfs[i].size() > self.MAX_ADF_SIZE:
                child_adfs[i] = parent['adfs'][i].copy()

        # Mutate strategy
        new_strategy = copy.deepcopy(parent['strategy'])
        for k, v in new_strategy.items():
            if rng.random() < 0.15:
                scale = max(abs(v) * 0.3, 0.02)
                new_strategy[k] = max(0.0, min(1.0, v + rng.gauss(0, scale)))

        return {
            'main': child_main,
            'adfs': child_adfs,
            'fitness': 0.0,
            'scores': {},
            'strategy': new_strategy,
            'age': 0,
        }

    def _crossover(self, parent, rng) -> Tuple[Node, List[Node]]:
        """Three crossover types: main-main (60%), ADF swap (30%),
        main-ADF (10%)."""
        other = self._tournament(rng, k=3)
        roll = rng.random()

        if roll < 0.60:
            # Main-main crossover
            child_main = subtree_crossover(parent['main'], other['main'], rng)
            child_adfs = [adf.copy() for adf in parent['adfs']]

        elif roll < 0.90:
            # ADF crossover: swap an entire ADF between parents
            child_main = parent['main'].copy()
            child_adfs = [adf.copy() for adf in parent['adfs']]
            adf_idx = rng.randint(0, 2)
            child_adfs[adf_idx] = other['adfs'][adf_idx].copy()

        else:
            # Main-ADF crossover: graft a subtree from other's main
            # into this organism's ADF
            child_main = parent['main'].copy()
            child_adfs = [adf.copy() for adf in parent['adfs']]
            adf_idx = rng.randint(0, 2)

            donor_nodes = get_all_nodes(other['main'])
            adf_nodes = get_all_nodes(child_adfs[adf_idx])
            if len(donor_nodes) > 1 and len(adf_nodes) > 1:
                donor, _, _ = rng.choice(donor_nodes[1:])
                _, p, i = rng.choice(adf_nodes[1:])
                if p is not None:
                    p.children[i] = donor.copy()

        return child_main, child_adfs

    def _mutate(self, parent, rng) -> Tuple[Node, List[Node]]:
        """Mutation: 60% targets main, 40% targets a random ADF.
        Same mutation types as original: point, subtree, chaos."""
        if rng.random() < 0.60:
            # Mutate main tree
            child_adfs = [adf.copy() for adf in parent['adfs']]
            if rng.random() < 0.5:
                child_main = subtree_mutation(parent['main'], rng,
                    subtree_gen=lambda: random_tree(rng, max_depth=3))
            else:
                child_main = point_mutation(parent['main'], rng,
                    rate=parent['strategy'].get('point_mut_rate', 0.15),
                    ops_by_arity=MAIN_OPS_BY_ARITY)
        else:
            # Mutate a random ADF
            child_main = parent['main'].copy()
            child_adfs = [adf.copy() for adf in parent['adfs']]
            adf_idx = rng.randint(0, 2)
            if rng.random() < 0.5:
                child_adfs[adf_idx] = subtree_mutation(
                    child_adfs[adf_idx], rng,
                    subtree_gen=lambda: random_adf_tree(rng, max_depth=3))
            else:
                child_adfs[adf_idx] = point_mutation(
                    child_adfs[adf_idx], rng,
                    rate=parent['strategy'].get('point_mut_rate', 0.15),
                    ops_by_arity=ADF_OPS_BY_ARITY)

        return child_main, child_adfs

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

    # Count static ADF usage across all organisms
    adf_counts = [0, 0, 0]
    for org in island.organisms:
        adf_counts[0] += count_ops(org['main'], {Op.CALL_ADF0})
        adf_counts[1] += count_ops(org['main'], {Op.CALL_ADF1})
        adf_counts[2] += count_ops(org['main'], {Op.CALL_ADF2})

    main_size = best['main'].size()
    adf_sizes = [adf.size() for adf in best['adfs']]
    total_size = main_size + sum(adf_sizes)

    return island, {
        'fitness': best['fitness'],
        'scores': best['scores'],
        'size': total_size,
        'main_size': main_size,
        'adf_sizes': adf_sizes,
        'strategy': best['strategy'],
        'stagnation': island.stagnation,
        'catastrophes': island.catastrophes,
        'epoch': island.epoch,
        'adf_counts': adf_counts,
    }


# ============================================================================
# ADF ENGINE
# ============================================================================

class ADFEngine:
    def __init__(self, n_islands=5, island_pop=30, cores=None, seed=333):
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

        self.save_path = os.path.join(TOOLS_DIR, 'exp8_adf_state.json')
        self.best_path = os.path.join(TOOLS_DIR, 'exp8_adf_best.json')
        self.log_path = os.path.join(TOOLS_DIR, 'exp8_adf_log.jsonl')

    def initialize(self):
        transplants = load_transplants()

        self.islands = []
        for i in range(self.n_islands):
            island = ADFIsland(i, self.island_pop,
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

        print(f"\n{'=' * 70}")
        print(f"  EXP8: AUTOMATICALLY DEFINED FUNCTIONS (ADFs)")
        print(f"{'=' * 70}")
        print(f"  Islands:     {self.n_islands}")
        print(f"  Pop/island:  {self.island_pop}")
        print(f"  Total:       {self.n_islands * self.island_pop} organisms")
        print(f"  Cores:       {self.cores}")
        print(f"  Seed:        {self.seed}")
        print(f"  New ops:     CALL_ADF0/1/2, ADF_ARG0, ADF_ARG1")
        print(f"  ADF slots:   3 per organism (max depth 4, max 80 nodes)")
        print(f"  Recursion:   max depth 1 (ADFs cannot call ADFs)")
        print(f"  Workspace:   registers 12-15 (saved/restored)")
        print(f"  Tasks:")
        print(f"    Memory:    {', '.join(MEMORY_TASKS.keys())}")
        print(f"    Self-ref:  {', '.join(SELF_REF_TASKS.keys())}")
        print(f"    Reasoning: {', '.join(REASONING_TASKS.keys())}")
        print(f"  Fitness:     50% hmean(memory) + 30% hmean(self-ref)"
              f" + 20% reasoning")
        print(f"  Size limit:  main={ADFIsland.MAX_MAIN_SIZE}"
              f"  adf={ADFIsland.MAX_ADF_SIZE}"
              f"  total={ADFIsland.MAX_TOTAL_SIZE}")
        print(f"  Hypothesis:  ADFs let organisms factor out reusable")
        print(f"               subroutines (store-recall, conditional-inc,")
        print(f"               compare-threshold) shared across 9 tasks.")
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

            # Track global best
            for i, (island, res) in enumerate(zip(self.islands,
                                                   island_results)):
                if res['fitness'] > self.global_best_fitness:
                    best_org = island.best()
                    self.global_best = {
                        'fitness': res['fitness'],
                        'scores': res['scores'],
                        'size': res['size'],
                        'main_size': res['main_size'],
                        'adf_sizes': res['adf_sizes'],
                        'strategy': res['strategy'],
                        'island': i,
                        'program_main': best_org['main'].to_str(),
                        'program_adf0': best_org['adfs'][0].to_str(),
                        'program_adf1': best_org['adfs'][1].to_str(),
                        'program_adf2': best_org['adfs'][2].to_str(),
                    }
                    self.global_best_fitness = res['fitness']

            # Migration (ring topology)
            n_mig = max(1, self.island_pop // 10)
            migrants = [isl.get_migrants(n_mig) for isl in self.islands]
            for i, isl in enumerate(self.islands):
                source = (i - 1) % self.n_islands
                isl.accept_migrants(migrants[source])

            # Aggregate ADF usage across all islands
            total_adf_counts = [0, 0, 0]
            for res in island_results:
                for j in range(3):
                    total_adf_counts[j] += res['adf_counts'][j]

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

                # Op counts for best organism
                best_tree = None
                for isl, res in zip(self.islands, island_results):
                    if res['fitness'] == self.global_best_fitness:
                        best_tree = isl.best()
                        break
                if best_tree:
                    sa_count = count_ops(best_tree['main'], SELF_REF_OPS)
                    mem_count = count_ops(best_tree['main'], MEMORY_OPS)
                    adf_call_count = count_ops(best_tree['main'],
                                               ADF_CALL_OPS)
                    ms = self.global_best['main_size']
                    asizes = self.global_best['adf_sizes']
                    print(f"    ops: mem={mem_count} self_ref={sa_count}"
                          f" adf_calls={adf_call_count}"
                          f"  main={ms} adfs={asizes}")

            # ADF usage across population
            print(f"    ADF usage (nodes across all organisms):"
                  f" adf0={total_adf_counts[0]}"
                  f" adf1={total_adf_counts[1]}"
                  f" adf2={total_adf_counts[2]}")

            for i, res in enumerate(island_results):
                cat = (f" [CAT x{res['catastrophes']}]"
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
                'adf_counts': total_adf_counts,
                'time_s': round_time,
                'ts': time.strftime('%H:%M:%S'),
            }
            self.history.append(entry)
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')

            if self.generation % 5 == 0:
                self._save()

            sys.stdout.flush()

        self._save()
        elapsed = time.time() - total_start
        print(f"\n{'=' * 70}")
        print(f"  STOPPED -- {self.generation} rounds,"
              f" {self.generation * epochs_per_round} epochs, {elapsed:.0f}s")
        print(f"  Best fitness: {self.global_best_fitness:.4f}")
        if self.global_best:
            print(f"  Scores:")
            for k, v in sorted(self.global_best['scores'].items()):
                print(f"    {k:25s}: {v:.4f}")
            print(f"  Strategy:")
            for k, v in sorted(self.global_best['strategy'].items()):
                print(f"    {k:25s}: {v:.4f}")
            print(f"  Size: main={self.global_best['main_size']}"
                  f"  adfs={self.global_best['adf_sizes']}")
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
        description='GA Experiment 8: Automatically Defined Functions')
    parser.add_argument('--islands', type=int, default=5)
    parser.add_argument('--island-pop', type=int, default=30)
    parser.add_argument('--cores', type=int, default=3)
    parser.add_argument('--seed', type=int, default=333)
    args = parser.parse_args()

    engine = ADFEngine(
        n_islands=args.islands,
        island_pop=args.island_pop,
        cores=args.cores,
        seed=args.seed,
    )
    engine.run()


if __name__ == '__main__':
    main()
