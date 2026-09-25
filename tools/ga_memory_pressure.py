#!/usr/bin/env python3
"""GA Evolution with Memory-Mandatory Fitness Landscape

The previous engines stagnated at IQ ~0.47-0.54 because the task
environment didn't REQUIRE memory. Reactive strategies scored 0.48
with zero memory use, so evolution had no pressure to develop it.

Root causes identified:
  - NavigationTask created new ExecutionContext per step (registers wiped)
  - Comparison/Arithmetic are single-call (no temporal state needed)
  - CopyTask scoring was lenient enough for partial credit without memory

This engine fixes the landscape:
  - ALL tasks require multi-step execution with PERSISTENT context
  - Reactive strategies score 0.0 on memory tasks (not 0.3, not 0.1 — ZERO)
  - Fitness is 70% memory-mandatory tasks, 30% reasoning tasks
  - Memory use is directly measured and rewarded

New tasks (all require WRITE→READ to score above zero):
  - DelayedEcho: hear value at step 0, output it at step N
  - SequentialXOR: output XOR(current, previous) — must store last input
  - RunningMax: output the maximum value seen so far
  - Accumulator: count inputs exceeding a threshold
  - StateSwitcher: maintain internal state machine based on input signals

Usage:
    python3 ga_memory_pressure.py              # run
    python3 ga_memory_pressure.py --cores 14   # max parallelism
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
from typing import Dict, List, Optional, Tuple

import numpy as np

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

from ga_cognition_engine import (
    Op, ARITY, Node, ExecutionContext,
    TERMINAL_OPS, UNARY_OPS, BINARY_OPS, TERNARY_OPS,
    CognitiveTask,
    get_all_nodes, subtree_crossover, point_mutation, subtree_mutation,
    random_tree,
)

from ga_accelerated import compile_tree, execute_bytecode


# ============================================================================
# MEMORY-MANDATORY TASKS
# ============================================================================

class DelayedEchoTask(CognitiveTask):
    """Hear a value, wait N steps of noise, then output it.

    Step 0: input ch0 = target value, ch1 = 1.0 (store signal)
    Steps 1..N-1: input ch0 = random noise, ch1 = 0.0 (wait)
    Step N: input ch0 = 0, ch1 = -1.0 (recall signal)
    Expected: output ch0 = target value from step 0

    IMPOSSIBLE without memory. A reactive program sees random noise
    at recall time and has no access to the original value.
    """
    name = "delayed_echo"
    description = "Store a value, recall it after delay"
    difficulty = 3

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            target = rng.uniform(-5, 5)
            delay = rng.randint(2, 6)
            noise = [rng.uniform(-5, 5) for _ in range(delay - 1)]
            trials.append({'target': target, 'delay': delay, 'noise': noise})
        return trials

    def evaluate_trial(self, program, trial):
        return self._evaluate_bytecode(compile_tree(program), trial)

    def _evaluate_bytecode(self, bytecode, trial):
        ctx = ExecutionContext()
        target = trial['target']
        delay = trial['delay']
        noise = trial['noise']

        # Step 0: present target
        ctx.steps = 0
        ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
        ctx.inputs = [target, 1.0, 0.0, float(delay), 0, 0, 0, 0]
        execute_bytecode(bytecode, ctx)

        # Steps 1..N-1: noise (registers PRESERVED)
        noise_outputs = []
        for i, n_val in enumerate(noise):
            ctx.steps = 0
            ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
            ctx.inputs = [n_val, 0.0, float(i + 1), float(delay), 0, 0, 0, 0]
            execute_bytecode(bytecode, ctx)
            noise_outputs.append(ctx.outputs[0])

        # Step N: recall
        ctx.steps = 0
        ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
        ctx.inputs = [0.0, -1.0, float(delay), float(delay), 0, 0, 0, 0]
        execute_bytecode(bytecode, ctx)

        recalled = ctx.outputs[0]
        error = abs(recalled - target)

        # Primary: did it recall correctly?
        if error < 0.5:
            recall_score = 1.0
        elif error < 1.0:
            recall_score = 0.5
        elif error < 2.0:
            recall_score = 0.2
        else:
            recall_score = 0.0

        # Bonus: noise resistance — did it output the stored value
        # consistently during noise steps? (trains "don't overwrite")
        if noise_outputs:
            # Check how many noise-step outputs were close to target
            stable_count = sum(1 for o in noise_outputs
                               if abs(o - target) < 1.0)
            stability = stable_count / len(noise_outputs)
            return 0.7 * recall_score + 0.3 * stability

        return recall_score


class SequentialXORTask(CognitiveTask):
    """Output the XOR of current and previous input.

    Each step: input ch0 = current value (0 or 1)
    Expected: output ch0 = XOR(current, previous)
    First step: output = current (no previous)

    IMPOSSIBLE without memory. Must store the previous input
    to compute XOR with current.
    """
    name = "sequential_xor"
    description = "Output XOR of current and previous input"
    difficulty = 2

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            length = rng.randint(4, 8)
            sequence = [rng.choice([0.0, 1.0]) for _ in range(length)]
            expected = [sequence[0]]  # first step = identity
            for i in range(1, length):
                xor = 1.0 if (sequence[i] > 0.5) != (sequence[i-1] > 0.5) else 0.0
                expected.append(xor)
            trials.append({'sequence': sequence, 'expected': expected})
        return trials

    def evaluate_trial(self, program, trial):
        return self._evaluate_bytecode(compile_tree(program), trial)

    def _evaluate_bytecode(self, bytecode, trial):
        ctx = ExecutionContext()
        correct = 0
        total = len(trial['sequence'])

        for i, val in enumerate(trial['sequence']):
            ctx.steps = 0
            ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
            ctx.inputs = [val, float(i), float(total), 0, 0, 0, 0, 0]
            execute_bytecode(bytecode, ctx)

            output = ctx.outputs[0]
            expected = trial['expected'][i]
            # Binary: check if output matches expected (threshold 0.5)
            predicted = 1.0 if output > 0.5 else 0.0
            if abs(predicted - expected) < 0.1:
                correct += 1

        return correct / total


class RunningMaxTask(CognitiveTask):
    """Output the maximum value seen so far across all steps.

    Each step: input ch0 = new value
    Expected: output ch0 = max(all values seen up to this step)

    IMPOSSIBLE without memory. Must track running maximum.
    """
    name = "running_max"
    description = "Output maximum value seen so far"
    difficulty = 2

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

    def evaluate_trial(self, program, trial):
        return self._evaluate_bytecode(compile_tree(program), trial)

    def _evaluate_bytecode(self, bytecode, trial):
        ctx = ExecutionContext()
        total_score = 0.0
        values = trial['values']
        expected = trial['running_max']

        for i, val in enumerate(values):
            ctx.steps = 0
            ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
            ctx.inputs = [val, float(i), float(len(values)), 0, 0, 0, 0, 0]
            execute_bytecode(bytecode, ctx)

            output = ctx.outputs[0]
            error = abs(output - expected[i])
            scale = max(abs(expected[i]), 1.0)
            step_score = max(0.0, 1.0 - error / scale)
            total_score += step_score

        return total_score / len(values)


class AccumulatorTask(CognitiveTask):
    """Count how many inputs exceed a threshold.

    Each step: input ch0 = value, ch1 = threshold
    Expected: output ch0 = count of values > threshold seen so far

    IMPOSSIBLE without memory. Must maintain a counter.
    """
    name = "accumulator"
    description = "Count inputs exceeding threshold"
    difficulty = 3

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
                'values': values,
                'threshold': threshold,
                'expected_counts': counts
            })
        return trials

    def evaluate_trial(self, program, trial):
        return self._evaluate_bytecode(compile_tree(program), trial)

    def _evaluate_bytecode(self, bytecode, trial):
        ctx = ExecutionContext()
        total_score = 0.0
        values = trial['values']
        threshold = trial['threshold']
        expected = trial['expected_counts']

        for i, val in enumerate(values):
            ctx.steps = 0
            ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
            ctx.inputs = [val, threshold, float(i), float(len(values)), 0, 0, 0, 0]
            execute_bytecode(bytecode, ctx)

            output = ctx.outputs[0]
            error = abs(output - expected[i])
            # Counting is discrete — be strict
            if error < 0.5:
                total_score += 1.0
            elif error < 1.5:
                total_score += 0.3

        return total_score / len(values)


class StateSwitcherTask(CognitiveTask):
    """Maintain a state machine: toggle between states based on signals.

    Input ch0 = signal (positive = switch to state A, negative = switch to state B)
    Input ch1 = query (1.0 = "what state am I in?")
    Expected: output ch0 = current state (1.0 for A, -1.0 for B)

    IMPOSSIBLE without memory. Must remember which state was last set.
    """
    name = "state_switcher"
    description = "Maintain and report internal state"
    difficulty = 3

    def generate_trials(self, n, rng):
        trials = []
        for _ in range(n):
            length = rng.randint(5, 10)
            signals = []
            queries = []
            states = []
            current_state = 1.0  # start in state A
            for _ in range(length):
                is_signal = rng.random() < 0.4
                is_query = rng.random() < 0.5
                if is_signal:
                    sig = rng.choice([3.0, -3.0])  # clear positive/negative
                    current_state = 1.0 if sig > 0 else -1.0
                else:
                    sig = 0.0
                signals.append(sig)
                queries.append(1.0 if is_query else 0.0)
                states.append(current_state)
            trials.append({
                'signals': signals,
                'queries': queries,
                'expected_states': states,
            })
        return trials

    def evaluate_trial(self, program, trial):
        return self._evaluate_bytecode(compile_tree(program), trial)

    def _evaluate_bytecode(self, bytecode, trial):
        ctx = ExecutionContext()
        correct = 0
        query_count = 0
        signals = trial['signals']
        queries = trial['queries']
        expected = trial['expected_states']

        for i in range(len(signals)):
            ctx.steps = 0
            ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
            ctx.inputs = [signals[i], queries[i], float(i), 0, 0, 0, 0, 0]
            execute_bytecode(bytecode, ctx)

            if queries[i] > 0.5:
                query_count += 1
                output = ctx.outputs[0]
                # Check if output matches expected state direction
                if (output > 0) == (expected[i] > 0):
                    correct += 1

        return correct / max(query_count, 1)


class PersistentNavigationTask(CognitiveTask):
    """Navigate to goal WITH persistent memory across steps.

    Fixes the original NavigationTask bug where ExecutionContext
    was reset every step, making memory impossible.
    """
    name = "persistent_nav"
    description = "Navigate to goal with persistent memory"
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
        return self._evaluate_bytecode(compile_tree(program), trial)

    def _evaluate_bytecode(self, bytecode, trial):
        ctx = ExecutionContext()  # ONE context for ALL steps
        pos = trial['start']
        goal = trial['goal']
        best_dist = abs(pos - goal)

        for step in range(20):
            ctx.steps = 0  # reset step counter but KEEP registers
            ctx.outputs = [0.0] * ctx.NUM_OUTPUT_CHANNELS
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

REASONING_TASKS = {
    'persistent_nav': PersistentNavigationTask(),
}

ALL_PRESSURE_TASKS = {**MEMORY_TASKS, **REASONING_TASKS}


# ============================================================================
# FAST EVALUATION — bytecode path for all new tasks
# ============================================================================

def evaluate_organism(bytecode: list, tasks: dict, n_trials: int = 12,
                      seed: int = 42) -> dict:
    """Evaluate bytecode on all tasks, return per-task scores."""
    scores = {}
    for name, task in tasks.items():
        rng = random.Random(seed)
        trials = task.generate_trials(n_trials, rng)
        trial_scores = []
        for trial in trials:
            s = task._evaluate_bytecode(bytecode, trial)
            trial_scores.append(s)
        scores[name] = float(np.mean(trial_scores))
    return scores


def compute_fitness(scores: dict) -> float:
    """Fitness that HEAVILY weights memory tasks.
    Uses harmonic mean for memory tasks — forces ALL tasks to improve.
    Harmonic mean of [0.82, 0.80, 0.72, 0.43, 0.42] = 0.58
    vs arithmetic mean = 0.64. Weak tasks drag harder."""
    memory_names = ['delayed_echo', 'sequential_xor', 'running_max',
                    'accumulator', 'state_switcher']
    reasoning_names = ['persistent_nav']

    mem_scores = [max(scores.get(n, 0), 0.01) for n in memory_names]
    rea_scores = [scores.get(n, 0) for n in reasoning_names]

    # Harmonic mean punishes weak links harder than arithmetic mean
    mem_hmean = len(mem_scores) / sum(1.0 / s for s in mem_scores)
    rea_mean = np.mean(rea_scores) if rea_scores else 0

    # 75% memory (harmonic), 25% reasoning
    return 0.75 * mem_hmean + 0.25 * rea_mean


# ============================================================================
# MEMORY-SEEDED TREE GENERATION
# ============================================================================

def memory_seed_tree(rng: random.Random) -> Node:
    """Generate a tree with working memory patterns baked in.
    These are functional READ→WRITE→IF patterns, not dead code."""

    # Pick a memory pattern
    pattern = rng.randint(0, 6)

    if pattern == 0:
        # STORE AND RECALL: write input to register, read back later
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.WRITE, children=[
                reg,
                Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.IF, children=[
                    Node(op=Op.SENSE, children=[Node(op=Op.ONE)]),  # check signal
                    Node(op=Op.READ, children=[reg.copy()]),  # recall
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])  # pass-through
                ])
            ])
        ])

    elif pattern == 1:
        # RUNNING MAX: compare input with stored max, update if greater
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

    elif pattern == 2:
        # COUNTER: increment register when condition met
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
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

    elif pattern == 3:
        # STATE MACHINE: write state based on signal, read on query
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

    elif pattern == 4:
        # SIGNAL-GATED STORE: only write when signal says to, otherwise hold
        # This is the exact pattern delayed_echo needs — store on signal=1,
        # ignore noise when signal=0, recall on signal=-1
        reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.SENSE, children=[Node(op=Op.ONE)]),  # ch1 = signal
                    Node(op=Op.ZERO)
                ]),
                # Signal > 0: STORE the input
                Node(op=Op.WRITE, children=[
                    reg,
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ]),
                # Signal <= 0: DON'T overwrite (just read existing value)
                Node(op=Op.READ, children=[reg.copy()])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg.copy()])
            ])
        ])

    elif pattern == 5:
        # PRECISE ACCUMULATOR: IF(input > threshold, counter++, counter)
        # Uses separate register for counter to avoid interference
        reg_count = Node(op=Op.CONST, value=float(rng.randint(8, 12)))
        return Node(op=Op.SEQ, children=[
            Node(op=Op.IF, children=[
                Node(op=Op.GT, children=[
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)]),  # ch0 = value
                    Node(op=Op.SENSE, children=[Node(op=Op.ONE)])    # ch1 = threshold
                ]),
                # value > threshold: increment counter
                Node(op=Op.WRITE, children=[
                    reg_count,
                    Node(op=Op.ADD, children=[
                        Node(op=Op.READ, children=[reg_count.copy()]),
                        Node(op=Op.ONE)
                    ])
                ]),
                # value <= threshold: keep counter unchanged
                Node(op=Op.READ, children=[reg_count.copy()])
            ]),
            Node(op=Op.ACT, children=[
                Node(op=Op.ZERO),
                Node(op=Op.READ, children=[reg_count.copy()])
            ])
        ])

    else:
        # XOR MEMORY: store previous, compare with current
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


# ============================================================================
# ISLAND WITH MEMORY PRESSURE
# ============================================================================

class MemoryIsland:
    """Island where fitness landscape demands memory."""

    def __init__(self, island_id: int, pop_size: int, seed: int):
        self.id = island_id
        self.pop_size = pop_size
        self.rng = random.Random(seed)
        self.organisms = []  # list of (tree, bytecode, fitness, scores, strategy)
        self.plasmids = []
        self.epoch = 0
        self.best_fitness = 0.0
        self.stagnation = 0
        self.catastrophes = 0

    def initialize(self, scaffold_rate: float = 0.5):
        """Create initial population with memory scaffolding."""
        self.organisms = []
        for i in range(self.pop_size):
            if self.rng.random() < scaffold_rate:
                tree = memory_seed_tree(self.rng)
            else:
                tree = random_tree(self.rng, max_depth=5 + (self.id % 3))

            # Each organism has self-evolving strategy
            strategy = {
                'crossover_rate': self.rng.uniform(0.3, 0.7),
                'point_mut_rate': self.rng.uniform(0.05, 0.3),
                'subtree_mut_rate': self.rng.uniform(0.05, 0.2),
                'chaos_rate': self.rng.uniform(0.0, 0.1),
                'merge_rate': self.rng.uniform(0.0, 0.2),
            }

            bytecode = compile_tree(tree)
            self.organisms.append({
                'tree': tree,
                'bytecode': bytecode,
                'fitness': 0.0,
                'scores': {},
                'strategy': strategy,
                'age': 0,
            })

    def evaluate_all(self, seed: int = 42):
        """Evaluate all organisms on memory tasks."""
        for org in self.organisms:
            org['scores'] = evaluate_organism(
                org['bytecode'], ALL_PRESSURE_TASKS,
                n_trials=10, seed=seed
            )
            org['fitness'] = compute_fitness(org['scores'])

    def evolve_one_epoch(self):
        self.epoch += 1
        rng = self.rng

        # Evaluate
        self.evaluate_all(seed=42 + (self.epoch % 5))

        # Sort
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
                    tree = memory_seed_tree(rng)
                else:
                    tree = random_tree(rng, max_depth=rng.randint(4, 7))
                strategy = {
                    'crossover_rate': rng.uniform(0.3, 0.7),
                    'point_mut_rate': rng.uniform(0.05, 0.3),
                    'subtree_mut_rate': rng.uniform(0.05, 0.2),
                    'chaos_rate': rng.uniform(0.0, 0.1),
                    'merge_rate': rng.uniform(0.0, 0.2),
                }
                bytecode = compile_tree(tree)
                self.organisms.append({
                    'tree': tree, 'bytecode': bytecode,
                    'fitness': 0.0, 'scores': {}, 'strategy': strategy, 'age': 0
                })
            self.catastrophes += 1
            self.stagnation = 0
            return

        # Donate to plasmid pool
        for org in self.organisms[:3]:
            nodes = get_all_nodes(org['tree'])
            for node, _, _ in nodes:
                has_mem = any(n.op in (Op.READ, Op.WRITE)
                             for n, _, _ in get_all_nodes(node))
                if has_mem and 3 <= node.size() <= 25 and rng.random() < 0.15:
                    self.plasmids.append(node.copy())
        if len(self.plasmids) > 100:
            rng.shuffle(self.plasmids)
            self.plasmids = self.plasmids[:60]

        # Breed
        new_pop = [self.organisms[0], self.organisms[1]]  # elitism

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

        cumulative = 0
        cumulative += s.get('chaos_rate', 0)
        if r < cumulative:
            if rng.random() < 0.6:
                tree = memory_seed_tree(rng)
            else:
                tree = random_tree(rng, max_depth=6)
        else:
            cumulative += s.get('merge_rate', 0)
            if r < cumulative and len(self.organisms) > 2:
                other = self._tournament(rng, k=3)
                # Smart merge: graft a functional subtree from other into parent
                tree = parent['tree'].copy()
                donor_nodes = get_all_nodes(other['tree'])
                # Prefer subtrees with memory ops
                mem_subtrees = [(n, p, i) for n, p, i in donor_nodes
                                if any(nn.op in (Op.READ, Op.WRITE, Op.IF)
                                       for nn, _, _ in get_all_nodes(n))
                                and 3 <= n.size() <= 30]
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
                if tree.size() > 200:
                    tree = parent['tree'].copy()
            else:
                cumulative += s['crossover_rate']
                if r < cumulative:
                    other = self._tournament(rng, k=3)
                    tree = subtree_crossover(parent['tree'], other['tree'], rng)
                elif rng.random() < 0.5:
                    tree = subtree_mutation(parent['tree'], rng)
                else:
                    tree = point_mutation(parent['tree'], rng,
                                         rate=s.get('point_mut_rate', 0.15))

        # HGT from plasmid pool (prefer memory-containing plasmids)
        if self.plasmids and rng.random() < 0.1:
            plasmid = rng.choice(self.plasmids).copy()
            nodes = get_all_nodes(tree)
            if len(nodes) > 1:
                _, pn, idx = rng.choice(nodes[1:])
                if pn is not None:
                    pn.children[idx] = plasmid

        if tree.size() > 200:
            tree = parent['tree'].copy()

        # Mutate strategy
        new_strategy = copy.deepcopy(parent['strategy'])
        for k, v in new_strategy.items():
            if rng.random() < 0.15:
                scale = max(abs(v) * 0.3, 0.02)
                new_strategy[k] = max(0.0, min(1.0, v + rng.gauss(0, scale)))

        return {
            'tree': tree,
            'bytecode': compile_tree(tree),
            'fitness': 0.0,
            'scores': {},
            'strategy': new_strategy,
            'age': 0,
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
                self.organisms[-(i+1)] = m


# ============================================================================
# PARALLEL WORKER
# ============================================================================

def _run_island_batch(args):
    """Worker: run island for N epochs."""
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
# MEMORY PRESSURE ENGINE
# ============================================================================

class MemoryPressureEngine:
    def __init__(self, n_islands=7, island_pop=50, cores=None, seed=42):
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

        self.save_path = os.path.join(TOOLS_DIR, 'memory_pressure_v2_state.json')
        self.best_path = os.path.join(TOOLS_DIR, 'memory_pressure_v2_best.json')
        self.log_path = os.path.join(TOOLS_DIR, 'memory_pressure_v2_log.jsonl')

    def initialize(self):
        self.islands = []
        for i in range(self.n_islands):
            island = MemoryIsland(i, self.island_pop,
                                  seed=self.seed + i * 1000)
            scaffold_rate = 0.3 + (i % 4) * 0.15  # 0.3 to 0.75
            island.initialize(scaffold_rate=scaffold_rate)
            self.islands.append(island)

        print(f"  {self.n_islands} islands × {self.island_pop} organisms")
        print(f"  Scaffold rates: {[f'{0.3 + (i%4)*0.15:.0%}' for i in range(self.n_islands)]}")

    def run(self):
        self.initialize()

        running = [True]
        def handler(sig, frame):
            print(f"\n[SIGNAL] Saving and stopping...")
            running[0] = False
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        print(f"\n{'='*70}")
        print(f"  MEMORY PRESSURE EVOLUTION")
        print(f"{'='*70}")
        print(f"  Islands:     {self.n_islands}")
        print(f"  Pop/island:  {self.island_pop}")
        print(f"  Total:       {self.n_islands * self.island_pop} organisms")
        print(f"  Cores:       {self.cores}")
        print(f"  Tasks:       {', '.join(ALL_PRESSURE_TASKS.keys())}")
        print(f"  Fitness:     75% harmonic-mean(memory) + 25% reasoning")
        print(f"  Size limit:  200 nodes  |  Seed patterns: 7  |  Smart merge")
        print(f"{'='*70}\n")

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
            for i, (island, res) in enumerate(zip(self.islands, island_results)):
                if res['fitness'] > self.global_best_fitness:
                    best_org = island.best()
                    self.global_best = {
                        'fitness': res['fitness'],
                        'scores': res['scores'],
                        'size': res['size'],
                        'strategy': res['strategy'],
                        'island': i,
                        'program': best_org['tree'].to_str()[:500],
                    }
                    self.global_best_fitness = res['fitness']

            # Migration
            if self.generation % 1 == 0:
                n_mig = max(1, self.island_pop // 10)
                migrants = [isl.get_migrants(n_mig) for isl in self.islands]
                for i, isl in enumerate(self.islands):
                    source = (i - 1) % self.n_islands
                    isl.accept_migrants(migrants[source])

            # Report
            round_time = time.time() - round_start
            total_epochs = self.generation * epochs_per_round

            print(f"  Round {self.generation} ({total_epochs} epochs, {round_time:.0f}s)")
            if self.global_best:
                scores = self.global_best['scores']
                mem_tasks = ['delayed_echo', 'sequential_xor', 'running_max',
                             'accumulator', 'state_switcher']
                mem_str = '  '.join(f"{n[:5]}={scores.get(n,0):.2f}" for n in mem_tasks)
                nav_s = scores.get('persistent_nav', 0)
                print(f"  BEST: fit={self.global_best_fitness:.4f}  "
                      f"nav={nav_s:.2f}  {mem_str}")

            for i, res in enumerate(island_results):
                cat = f" [CAT×{res['catastrophes']}]" if res['catastrophes'] else ""
                print(f"    Isl {i}: fit={res['fitness']:.4f}  "
                      f"stag={res['stagnation']:3d}{cat}")

            # Log
            entry = {
                'gen': self.generation,
                'epochs': total_epochs,
                'best_fitness': self.global_best_fitness,
                'scores': self.global_best.get('scores', {}) if self.global_best else {},
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
        print(f"\n{'='*70}")
        print(f"  STOPPED — {self.generation} rounds, "
              f"{self.generation * epochs_per_round} epochs, {elapsed:.0f}s")
        print(f"  Best fitness: {self.global_best_fitness:.4f}")
        if self.global_best:
            print(f"  Scores:")
            for k, v in sorted(self.global_best['scores'].items()):
                print(f"    {k:20s}: {v:.4f}")
            print(f"  Strategy:")
            for k, v in sorted(self.global_best['strategy'].items()):
                print(f"    {k:25s}: {v:.4f}")
        print(f"{'='*70}")

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
    parser = argparse.ArgumentParser()
    parser.add_argument('--islands', type=int, default=7)
    parser.add_argument('--island-pop', type=int, default=50)
    parser.add_argument('--cores', type=int, default=None)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    engine = MemoryPressureEngine(
        n_islands=args.islands,
        island_pop=args.island_pop,
        cores=args.cores,
        seed=args.seed,
    )
    engine.run()


if __name__ == '__main__':
    main()
