#!/usr/bin/env python3
"""GA Experiment 10: Bytecode-Compiled Self-Aware Evolution (exp10)

Fork of ga_self_aware.py (v3/v4) with bytecode compilation for 10-50x speedup.

Two-phase execution:
  1. compile_tree(node) -> flat instruction list (done once per organism)
  2. execute_bytecode(instructions, ctx) -> stack-based interpreter (per step)

Trees remain the genotype (used for crossover/mutation).
Bytecode is the phenotype (used for evaluation only, cached per organism).

Hypothesis: 10-50x speedup means 500+ rounds in the time v4 does 50.
            More generations = more search = breaking through fitness plateaus.

Ops: 28 base + 4 self-referential (STEP, LAST_OUT, PREDICT, SURPRISE)
Tasks: 9 (5 memory + 3 self-referential + 1 reasoning)
Fitness: 50% hmean(memory) + 30% hmean(self-ref) + 20% reasoning

Save files:
    exp10_bytecode_state.json  — checkpoint (resume not implemented)
    exp10_bytecode_best.json   — best organism
    exp10_bytecode_log.jsonl   — per-round log

Usage:
    python3 ga_exp10_bytecode.py                         # run
    python3 ga_exp10_bytecode.py --cores 14              # parallelism
    python3 ga_exp10_bytecode.py --benchmark             # tree vs bytecode timing
    python3 ga_exp10_bytecode.py --islands 10 --seed 999 # custom config
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
from enum import Enum, IntEnum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ga_sequence_data import REAL_DATA_TASKS, prefetch_sequences, set_context


# ============================================================================
# OP SET — 28 base + 4 self-referential = 32 ops
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

    # Self-referential ops (v3)
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
# PROGRAM PARSER — reconstruct trees from text representation
# ============================================================================

def parse_program(text: str) -> Optional[Node]:
    """Parse S-expression program text back into a Node tree."""
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
        """Between task steps: save outputs, increment global step, reset budget."""
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
# TREE INTERPRETER — kept for verification and benchmark comparison
# ============================================================================

def execute_tree(node: Node, ctx: SelfAwareContext) -> float:
    """Recursive tree interpreter. Identical semantics to ga_self_aware.py."""
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

    # Evaluate children (eager — all children evaluated for every op)
    args = [execute_tree(c, ctx) for c in node.children]

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
# BYTECODE COMPILER + STACK MACHINE
# ============================================================================

# Integer opcodes for the stack machine (faster than enum comparison)
class BC(IntEnum):
    # Arithmetic
    ADD = 0; SUB = 1; MUL = 2; DIV = 3; MOD = 4
    # Comparison
    GT = 5; LT = 6; EQ = 7; NEQ = 8
    # Logic
    AND = 9; OR = 10; NOT = 11
    # Control
    IF = 12; SEQ = 13
    # Memory
    READ = 14; WRITE = 15
    # I/O
    SENSE = 16; ACT = 17
    # Constants
    CONST = 18; ZERO = 19; ONE = 20; NEG1 = 21
    # Accumulation
    INC = 22; DEC = 23; ABS = 24; SIGN = 25; MAX2 = 26; MIN2 = 27
    # Self-referential
    STEP = 28; LAST_OUT = 29; PREDICT = 30; SURPRISE = 31
    # Lifetime learning
    LEARN = 32; RECALL = 33; STRENGTHEN = 34; WEAKEN = 35; DEFINE = 36; INVOKE = 37


# Map tree ops to bytecode ops
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
    Op.STEP: BC.STEP, Op.LAST_OUT: BC.LAST_OUT,
    Op.PREDICT: BC.PREDICT, Op.SURPRISE: BC.SURPRISE,
    # Lifetime learning
    Op.LEARN: BC.LEARN, Op.RECALL: BC.RECALL,
    Op.STRENGTHEN: BC.STRENGTHEN, Op.WEAKEN: BC.WEAKEN,
    Op.DEFINE: BC.DEFINE, Op.INVOKE: BC.INVOKE,
}


def compile_tree(node: Node) -> list:
    """Compile a program tree into a flat postfix instruction list.

    Post-order traversal: children first, then operation.
    All children are evaluated eagerly (matching tree interpreter semantics).
    Each instruction is a (bc_op, value) tuple.
    """
    instructions = []
    _compile_node(node, instructions)
    return instructions


def _compile_node(node: Node, out: list):
    """Recursive compilation to postfix bytecode."""
    op = node.op
    bc = OP_TO_BC[op]

    # Terminals (no children)
    if bc == BC.CONST:
        out.append((BC.CONST, node.value))
        return
    if ARITY[op] == 0:
        out.append((bc, 0.0))
        return

    # Non-terminals: compile all children first (postfix), then emit op
    # IF: compile condition, true_branch, false_branch, then IF
    # (eager evaluation — both branches always executed, matching tree semantics)
    for child in node.children:
        _compile_node(child, out)
    out.append((bc, 0.0))


def execute(program, ctx):
    """Auto-dispatch: bytecode (list) → execute_bytecode, Node → execute_tree."""
    if isinstance(program, list):
        return execute_bytecode(program, ctx)
    return execute_tree(program, ctx)


def execute_bytecode(instructions: list, ctx: SelfAwareContext) -> float:
    """Execute compiled bytecode using a stack machine.

    Eliminates recursive Python function call overhead from tree interpretation.
    Handles all 32 ops including the 4 self-referential ops (STEP, LAST_OUT,
    PREDICT, SURPRISE) which interact with SelfAwareContext.

    Returns the top-of-stack value (or 0.0 if stack empty).
    Side effects: modifies ctx.registers, ctx.outputs, ctx.predictions via
    WRITE, ACT, PREDICT instructions.
    """
    stack = []
    max_steps = ctx.MAX_STEPS
    steps = 0

    for bc_op, val in instructions:
        steps += 1
        if steps >= max_steps:
            break

        # --- Constants ---
        if bc_op == BC.CONST:
            stack.append(val)
        elif bc_op == BC.ZERO:
            stack.append(0.0)
        elif bc_op == BC.ONE:
            stack.append(1.0)
        elif bc_op == BC.NEG1:
            stack.append(-1.0)
        elif bc_op == BC.STEP:
            stack.append(ctx.step_number / 10.0)

        # --- Arithmetic ---
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

        # --- Comparison ---
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

        # --- Logic ---
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

        # --- Control ---
        elif bc_op == BC.IF:
            # All 3 children already evaluated (eager, matching tree semantics)
            if len(stack) < 3: stack.append(0.0); continue
            false_val = stack.pop()
            true_val = stack.pop()
            cond = stack.pop()
            stack.append(true_val if cond > 0 else false_val)
        elif bc_op == BC.SEQ:
            if len(stack) < 2: stack.append(0.0); continue
            b = stack.pop(); stack.pop()
            stack.append(b)

        # --- Memory ---
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

        # --- I/O ---
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

        # --- Accumulation ---
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

        # --- Self-referential ---
        elif bc_op == BC.LAST_OUT:
            if len(stack) < 1: stack.append(0.0); continue
            a = stack.pop()
            idx = int(a) % ctx.NUM_OUTPUT_CHANNELS
            stack.append(ctx.last_outputs[idx])
        elif bc_op == BC.PREDICT:
            if len(stack) < 2: stack.append(0.0); continue
            val_p = stack.pop(); idx_p = stack.pop()
            idx = int(idx_p) % ctx.NUM_PREDICTIONS
            ctx.predictions[idx] = max(-1e6, min(1e6, val_p))
            stack.append(val_p)
        elif bc_op == BC.SURPRISE:
            if len(stack) < 1: stack.append(0.0); continue
            a = stack.pop()
            idx = int(a) % ctx.NUM_PREDICTIONS
            input_idx = idx % ctx.NUM_INPUT_CHANNELS
            stack.append(abs(ctx.predictions[idx] - ctx.inputs[input_idx]))

        # --- Lifetime Learning ---
        elif bc_op == BC.LEARN:
            if len(stack) < 3: stack.append(0.0); continue
            val_l = stack.pop(); idx_l = stack.pop(); cond = stack.pop()
            if cond > 0:
                ctx.learn_regs[int(idx_l) % ctx.NUM_LEARN_REGS] = max(-1e6, min(1e6, val_l))
            stack.append(val_l)
        elif bc_op == BC.RECALL:
            if len(stack) < 1: stack.append(0.0); continue
            a = stack.pop()
            stack.append(ctx.learn_regs[int(a) % ctx.NUM_LEARN_REGS])
        elif bc_op == BC.STRENGTHEN:
            if len(stack) < 1: stack.append(0.0); continue
            a = stack.pop()
            key = ('bc', steps)
            w = ctx.hebbian_weights.get(key, 1.0)
            w = min(3.0, max(0.1, w + math.tanh(a) * 0.1))
            ctx.hebbian_weights[key] = w
            stack.append(w)
        elif bc_op == BC.WEAKEN:
            if len(stack) < 1: stack.append(0.0); continue
            a = stack.pop()
            key = ('bc', steps)
            w = ctx.hebbian_weights.get(key, 1.0)
            w = min(3.0, max(0.1, w - math.tanh(a) * 0.1))
            ctx.hebbian_weights[key] = w
            stack.append(w)
        elif bc_op == BC.DEFINE:
            if len(stack) < 2: stack.append(0.0); continue
            stack.pop(); idx_d = stack.pop()
            stack.append(1.0)
        elif bc_op == BC.INVOKE:
            if len(stack) < 2: stack.append(0.0); continue
            stack.pop(); stack.pop()
            stack.append(0.0)

    ctx.steps = steps
    return stack[-1] if stack else 0.0


# ============================================================================
# EXECUTION DISPATCHER
# ============================================================================

def _run(program, ctx: SelfAwareContext, is_bytecode: bool):
    """Execute program on context using either tree or bytecode engine."""
    if is_bytecode:
        execute_bytecode(program, ctx)
    else:
        execute_tree(program, ctx)


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
# TASKS — all 9 (5 memory + 3 self-ref + 1 reasoning)
# Each evaluate() supports both tree and bytecode execution via is_bytecode.
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

    def evaluate(self, program, trial, is_bytecode=False):
        ctx = SelfAwareContext()
        target = trial['target']
        delay = trial['delay']
        noise = trial['noise']

        # Step 0: present target
        ctx.inputs = [target, 1.0, 0.0, float(delay), 0, 0, 0, 0]
        _run(program, ctx, is_bytecode)

        # Noise steps
        noise_outputs = []
        for i, n_val in enumerate(noise):
            ctx.advance_step()
            ctx.inputs = [n_val, 0.0, float(i + 1), float(delay), 0, 0, 0, 0]
            _run(program, ctx, is_bytecode)
            noise_outputs.append(ctx.outputs[0])

        # Recall step
        ctx.advance_step()
        ctx.inputs = [0.0, -1.0, float(delay), float(delay), 0, 0, 0, 0]
        _run(program, ctx, is_bytecode)

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

    def evaluate(self, program, trial, is_bytecode=False):
        ctx = SelfAwareContext()
        correct = 0
        total = len(trial['sequence'])

        for i, val in enumerate(trial['sequence']):
            if i > 0:
                ctx.advance_step()
            ctx.inputs = [val, float(i), float(total), 0, 0, 0, 0, 0]
            _run(program, ctx, is_bytecode)

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

    def evaluate(self, program, trial, is_bytecode=False):
        ctx = SelfAwareContext()
        total_score = 0.0
        values = trial['values']
        expected = trial['running_max']

        for i, val in enumerate(values):
            if i > 0:
                ctx.advance_step()
            ctx.inputs = [val, float(i), float(len(values)), 0, 0, 0, 0, 0]
            _run(program, ctx, is_bytecode)

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

    def evaluate(self, program, trial, is_bytecode=False):
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
            _run(program, ctx, is_bytecode)

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

    def evaluate(self, program, trial, is_bytecode=False):
        ctx = SelfAwareContext()
        correct = 0
        query_count = 0

        for i in range(len(trial['signals'])):
            if i > 0:
                ctx.advance_step()
            ctx.inputs = [trial['signals'][i], trial['queries'][i],
                          float(i), 0, 0, 0, 0, 0]
            _run(program, ctx, is_bytecode)

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

    def evaluate(self, program, trial, is_bytecode=False):
        ctx = SelfAwareContext()
        pos = trial['start']
        goal = trial['goal']
        best_dist = abs(pos - goal)

        for step in range(20):
            if step > 0:
                ctx.advance_step()
            ctx.inputs = [pos, goal, float(step), best_dist, 0, 0, 0, 0]
            _run(program, ctx, is_bytecode)

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
                'sequence': sequence,
                'expected': expected,
                'pattern': pattern,
                'pattern_len': pattern_len,
            })
        return trials

    def evaluate(self, program, trial, is_bytecode=False):
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
            _run(program, ctx, is_bytecode)

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

    def evaluate(self, program, trial, is_bytecode=False):
        ctx = SelfAwareContext()
        target = trial['target']
        n_steps = trial['n_steps']
        noise = trial['noise']

        # Step 0: blind guess
        ctx.inputs = [0.0, 0.0, float(n_steps), 0, 0, 0, 0, 0]
        _run(program, ctx, is_bytecode)
        last_output = ctx.outputs[0]
        initial_error = abs(target - last_output)

        total_score = 0.0
        for step in range(1, n_steps):
            ctx.advance_step()
            error_signal = (target - last_output) + noise[step]
            ctx.inputs = [error_signal, 1.0, float(n_steps),
                          float(step), abs(target - last_output), 0, 0, 0]
            _run(program, ctx, is_bytecode)
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

    def evaluate(self, program, trial, is_bytecode=False):
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
            _run(program, ctx, is_bytecode)

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

set_context(SelfAwareContext, execute)

import ga_sequence_data as _gsd
_gsd._context_class = SelfAwareContext
_gsd._execute_fn = execute


# ============================================================================
# EVALUATION
# ============================================================================

def evaluate_organism(program, tasks: dict, n_trials: int = 10,
                      seed: int = 42, is_bytecode: bool = False) -> dict:
    """Evaluate program (tree or bytecode) on all tasks."""
    scores = {}
    for name, task in tasks.items():
        rng = random.Random(seed)
        trials = task.generate_trials(n_trials, rng)
        trial_scores = [task.evaluate(program, trial, is_bytecode)
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
# SELF-AWARE SEED PATTERNS
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
        # TEMPORAL MEMORY: store early, recall later
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
# TRANSPLANT LOADER
# ============================================================================

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_transplants() -> List[Node]:
    """Load best organisms from prior runs for cross-pollination."""
    transplants = []
    for path in [
        os.path.join(TOOLS_DIR, 'memory_pressure_v2_best.json'),
        os.path.join(TOOLS_DIR, 'self_aware_best.json'),
        os.path.join(TOOLS_DIR, 'exp10_bytecode_best.json'),
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
# ISLAND MODEL — with bytecode caching
# ============================================================================

class BytecodeIsland:
    """Island with bytecode-cached organisms.

    Each organism is a dict:
        tree:     Node        — genotype (used for mutation/crossover)
        bytecode: list        — phenotype (compiled from tree, used for eval)
        fitness:  float
        scores:   dict
        strategy: dict        — self-adaptive mutation rates
        age:      int
    """

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

    def _make_organism(self, tree: Node, strategy: dict = None) -> dict:
        """Create an organism dict with compiled bytecode."""
        if strategy is None:
            strategy = {
                'crossover_rate': self.rng.uniform(0.3, 0.7),
                'point_mut_rate': self.rng.uniform(0.05, 0.3),
                'subtree_mut_rate': self.rng.uniform(0.05, 0.2),
                'chaos_rate': self.rng.uniform(0.0, 0.1),
                'merge_rate': self.rng.uniform(0.0, 0.2),
            }
        return {
            'tree': tree,
            'bytecode': compile_tree(tree),
            'fitness': 0.0,
            'scores': {},
            'strategy': strategy,
            'age': 0,
        }

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
                self.organisms.append(self._make_organism(tree, strategy))
                for _ in range(2):
                    variant = point_mutation(tree, rng, rate=0.2)
                    self.organisms.append(
                        self._make_organism(variant, copy.deepcopy(strategy)))

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
                    self.organisms.append(self._make_organism(hybrid, strategy))

        # Fill with scaffolded + random
        while len(self.organisms) < self.pop_size:
            if rng.random() < scaffold_rate:
                tree = self_aware_seed(rng)
            else:
                tree = random_tree(rng, max_depth=5 + (self.id % 3))
            self.organisms.append(self._make_organism(tree))

    def evaluate_all(self, seed: int = 42):
        """Evaluate all organisms using bytecode (fast path)."""
        for org in self.organisms:
            org['scores'] = evaluate_organism(
                org['bytecode'], ALL_TASKS, n_trials=8, seed=seed,
                is_bytecode=True
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
                if rng.random() < 0.6:
                    tree = self_aware_seed(rng)
                else:
                    tree = random_tree(rng, max_depth=rng.randint(4, 7))
                self.organisms.append(self._make_organism(tree))
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

        return self._make_organism(tree, new_strategy)

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
# SELF-TEST — verify bytecode matches tree interpreter
# ============================================================================

def run_self_test(verbose: bool = False) -> bool:
    """Generate 10 random organisms, evaluate with both engines, compare.

    Returns True if all match within 1e-6. Prints failing organism and
    halts if any mismatch found.
    """
    print("  Self-test: verifying bytecode matches tree interpreter...")
    rng = random.Random(12345)
    n_organisms = 10
    max_diff = 0.0
    all_pass = True

    for i in range(n_organisms):
        # Mix of random and seeded organisms
        if i < 5:
            tree = random_tree(rng, max_depth=4 + (i % 3))
        else:
            tree = self_aware_seed(rng)

        bytecode = compile_tree(tree)

        # Evaluate with tree engine
        tree_scores = evaluate_organism(
            tree, ALL_TASKS, n_trials=5, seed=77, is_bytecode=False)
        tree_fitness = compute_fitness(tree_scores)

        # Evaluate with bytecode engine
        bc_scores = evaluate_organism(
            bytecode, ALL_TASKS, n_trials=5, seed=77, is_bytecode=True)
        bc_fitness = compute_fitness(bc_scores)

        diff = abs(tree_fitness - bc_fitness)
        max_diff = max(max_diff, diff)

        if verbose:
            status = "OK" if diff < 1e-6 else "FAIL"
            print(f"    Organism {i}: tree={tree_fitness:.6f}"
                  f" bc={bc_fitness:.6f} diff={diff:.2e} [{status}]"
                  f" size={tree.size()}")

        if diff >= 1e-6:
            print(f"\n  SELF-TEST FAILED for organism {i}!")
            print(f"    Tree fitness:     {tree_fitness:.10f}")
            print(f"    Bytecode fitness: {bc_fitness:.10f}")
            print(f"    Difference:       {diff:.2e}")
            print(f"    Tree size:        {tree.size()}")
            print(f"\n  Per-task comparison:")
            for task_name in sorted(ALL_TASKS.keys()):
                ts = tree_scores.get(task_name, 0)
                bs = bc_scores.get(task_name, 0)
                td = abs(ts - bs)
                flag = " ***" if td >= 1e-6 else ""
                print(f"    {task_name:25s}: tree={ts:.6f} bc={bs:.6f}"
                      f" diff={td:.2e}{flag}")
            print(f"\n  Failing program:\n{tree.to_str(indent=2)}")
            all_pass = False
            break

    if all_pass:
        print(f"  Self-test PASSED: {n_organisms} organisms,"
              f" max diff = {max_diff:.2e}")
    return all_pass


# ============================================================================
# BENCHMARK — compare tree vs bytecode timing
# ============================================================================

def run_benchmark():
    """Run identical evaluations with tree and bytecode, print timing."""
    print("=" * 70)
    print("  BENCHMARK: Tree Interpreter vs Bytecode Compiler")
    print("=" * 70)

    rng = random.Random(42)
    organisms = []

    # Generate organisms at various sizes representative of GA evolution
    # Small: depth 3-4, Medium: depth 5-6, Large: depth 7-8
    for depth in [4, 5, 6, 7, 8]:
        # Generate several and pick ones that are reasonably sized
        for attempt in range(20):
            tree = random_tree(rng, max_depth=depth, self_aware_bias=0.15)
            if tree.size() >= max(3, depth):
                organisms.append(('random_d%d' % depth, tree))
                break
    # Seeded patterns (typically 12-25 nodes)
    for i in range(5):
        tree = self_aware_seed(rng)
        organisms.append(('seed_%d' % i, tree))
    # Build large organisms by composing seeded ones (simulate evolved organisms)
    for i in range(3):
        base = self_aware_seed(rng)
        for _ in range(5 + i * 3):
            donor = self_aware_seed(rng)
            base = subtree_crossover(base, donor, rng)
            if base.size() > 200:
                break
        organisms.append(('composed_%d(%d)' % (i, base.size()), base))

    print(f"\n  {'Name':20s} {'Size':>5s} {'Tree(ms)':>10s}"
          f" {'BC(ms)':>10s} {'Speedup':>8s}")
    print("  " + "-" * 57)

    total_tree_ms = 0
    total_bc_ms = 0

    for name, tree in organisms:
        bytecode = compile_tree(tree)
        size = tree.size()

        # Time tree execution
        t0 = time.perf_counter()
        for _ in range(3):
            evaluate_organism(tree, ALL_TASKS, n_trials=8, seed=42,
                              is_bytecode=False)
        tree_ms = (time.perf_counter() - t0) / 3 * 1000

        # Time bytecode execution
        t0 = time.perf_counter()
        for _ in range(3):
            evaluate_organism(bytecode, ALL_TASKS, n_trials=8, seed=42,
                              is_bytecode=True)
        bc_ms = (time.perf_counter() - t0) / 3 * 1000

        speedup = tree_ms / bc_ms if bc_ms > 0 else float('inf')
        total_tree_ms += tree_ms
        total_bc_ms += bc_ms

        print(f"  {name:20s} {size:5d} {tree_ms:10.1f} {bc_ms:10.1f}"
              f" {speedup:7.1f}x")

    overall_speedup = total_tree_ms / total_bc_ms if total_bc_ms > 0 else 0
    print("  " + "-" * 57)
    print(f"  {'TOTAL':20s} {'':5s} {total_tree_ms:10.1f}"
          f" {total_bc_ms:10.1f} {overall_speedup:7.1f}x")
    print(f"\n  Average speedup: {overall_speedup:.1f}x")

    # Estimate round projections
    # A round = 10 epochs, each epoch = pop_size evaluations
    # Default: 7 islands * 50 organisms = 350 evaluations per epoch
    evals_per_round = 7 * 50 * 10
    avg_bc_per_eval = total_bc_ms / (10 * 3)  # per single evaluation
    avg_tree_per_eval = total_tree_ms / (10 * 3)

    bc_round_s = evals_per_round * avg_bc_per_eval / 1000
    tree_round_s = evals_per_round * avg_tree_per_eval / 1000

    print(f"\n  Projected round times ({evals_per_round} evals/round):")
    print(f"    Tree:     {tree_round_s:8.1f}s/round"
          f" ({3600/tree_round_s:.0f} rounds/hr)")
    print(f"    Bytecode: {bc_round_s:8.1f}s/round"
          f" ({3600/bc_round_s:.0f} rounds/hr)")
    print("=" * 70)


# ============================================================================
# MAIN ENGINE — bytecode-accelerated evolution
# ============================================================================

class BytecodeEngine:
    def __init__(self, n_islands=7, island_pop=50, cores=None, seed=555):
        self.n_islands = n_islands
        self.island_pop = island_pop
        self.cores = cores or 1
        self.seed = seed
        self.rng = random.Random(seed)

        self.islands = []
        self.global_best = None
        self.global_best_fitness = 0.0
        self.generation = 0
        self.history = []

        self.save_path = os.path.join(TOOLS_DIR, 'exp10_bytecode_state.json')
        self.best_path = os.path.join(TOOLS_DIR, 'exp10_bytecode_best.json')
        self.log_path = os.path.join(TOOLS_DIR, 'exp10_bytecode_log.jsonl')

    def initialize(self):
        transplants = load_transplants()

        self.islands = []
        for i in range(self.n_islands):
            island = BytecodeIsland(i, self.island_pop,
                                    seed=self.seed + i * 1000)
            scaffold_rate = 0.4 + (i % 4) * 0.1
            island.initialize(scaffold_rate=scaffold_rate,
                              transplants=transplants)
            self.islands.append(island)

    def _estimate_tree_time(self) -> float:
        """Measure tree execution time for a sample organism (seconds/eval)."""
        rng = random.Random(999)
        tree = self_aware_seed(rng)
        t0 = time.perf_counter()
        for _ in range(5):
            evaluate_organism(tree, ALL_TASKS, n_trials=8, seed=42,
                              is_bytecode=False)
        return (time.perf_counter() - t0) / 5

    def run(self):
        self.initialize()

        running = [True]

        def handler(sig, frame):
            print(f"\n[SIGNAL] Saving and stopping...")
            running[0] = False

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        # Measure baseline tree speed for speedup reporting
        print("  Measuring tree interpreter baseline...")
        tree_time_per_eval = self._estimate_tree_time()
        evals_per_round = self.n_islands * self.island_pop * 10
        estimated_tree_round_s = tree_time_per_eval * evals_per_round
        print(f"  Tree baseline: {tree_time_per_eval*1000:.1f}ms/eval,"
              f" ~{estimated_tree_round_s:.0f}s/round (estimated)")

        print(f"\n{'=' * 70}")
        print(f"  BYTECODE-ACCELERATED SELF-AWARE EVOLUTION (exp10)")
        print(f"{'=' * 70}")
        print(f"  Islands:     {self.n_islands}")
        print(f"  Pop/island:  {self.island_pop}")
        print(f"  Total:       {self.n_islands * self.island_pop} organisms")
        print(f"  Cores:       {self.cores}")
        print(f"  Seed:        {self.seed}")
        print(f"  Execution:   BYTECODE (stack machine, {len(BC)} opcodes)")
        print(f"  Ops:         28 base + 4 self-ref (STEP, LAST_OUT,"
              f" PREDICT, SURPRISE)")
        print(f"  Tasks:")
        print(f"    Memory:    {', '.join(MEMORY_TASKS.keys())}")
        print(f"    Self-ref:  {', '.join(SELF_REF_TASKS.keys())}")
        print(f"    Reasoning: {', '.join(REASONING_TASKS.keys())}")
        print(f"  Fitness:     50% hmean(memory) + 30% hmean(self-ref)"
              f" + 20% reasoning")
        n_seeds = 16
        print(f"  Size limit:  250 nodes  |  Seed patterns: {n_seeds}")
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
            n_mig = max(1, self.island_pop // 10)
            migrants = [isl.get_migrants(n_mig) for isl in self.islands]
            for i, isl in enumerate(self.islands):
                source = (i - 1) % self.n_islands
                isl.accept_migrants(migrants[source])

            # Report
            round_time = time.time() - round_start
            total_epochs = self.generation * epochs_per_round
            total_elapsed = time.time() - total_start
            rounds_per_sec = self.generation / total_elapsed if total_elapsed > 0 else 0

            # Speedup vs estimated tree time
            if estimated_tree_round_s > 0:
                speedup = estimated_tree_round_s / round_time if round_time > 0 else 0
            else:
                speedup = 0

            print(f"  Round {self.generation} ({total_epochs} epochs,"
                  f" {round_time:.1f}s, {rounds_per_sec:.2f} rnd/s,"
                  f" {speedup:.1f}x vs tree)")

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

                # Count self-ref ops in best organism
                for island, res in zip(self.islands, island_results):
                    if res['fitness'] == self.global_best_fitness:
                        tree = island.best()['tree']
                        sa_count = count_ops(tree, SELF_REF_OPS)
                        mem_count = count_ops(tree, MEMORY_OPS)
                        print(f"    ops: mem={mem_count} self_ref={sa_count}"
                              f" size={self.global_best['size']}")
                        break

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
                'time_s': round_time,
                'rounds_per_sec': rounds_per_sec,
                'speedup_vs_tree': speedup,
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
        avg_speedup = (np.mean([h['speedup_vs_tree'] for h in self.history])
                       if self.history else 0)
        print(f"  Average speedup vs tree: {avg_speedup:.1f}x")
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


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='GA Experiment 10: Bytecode-Compiled Self-Aware Evolution')
    parser.add_argument('--islands', type=int, default=7)
    parser.add_argument('--island-pop', type=int, default=50)
    parser.add_argument('--cores', type=int, default=1)
    parser.add_argument('--seed', type=int, default=555)
    parser.add_argument('--benchmark', action='store_true',
                        help='Run timing comparison: tree vs bytecode')
    args = parser.parse_args()

    if args.benchmark:
        # Self-test first, then benchmark
        if not run_self_test(verbose=True):
            print("\nSelf-test failed! Bytecode does not match tree.")
            sys.exit(1)
        print()
        run_benchmark()
        return

    # Normal run: self-test at startup
    if not run_self_test(verbose=False):
        print("\nSelf-test failed! Bytecode does not match tree interpreter.")
        print("Halting. Fix the bytecode compiler before running evolution.")
        sys.exit(1)

    print()
    engine = BytecodeEngine(
        n_islands=args.islands,
        island_pop=args.island_pop,
        cores=args.cores,
        seed=args.seed,
    )
    engine.run()


if __name__ == '__main__':
    main()
