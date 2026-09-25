#!/usr/bin/env python3
"""GA Self-Improvement — GA Evolving GA

The outer GA evolves the inner GA's evolutionary strategy. Instead of
hand-tuning mutation rates, operator biases, fitness weights, and
scaffolding — let evolution discover what works for evolving intelligence.

Each outer individual is a CONFIGURATION for the cognition engine:
  - Mutation rates and modes
  - Operator probability biases (which ops appear more often)
  - Fitness function weights
  - Selection strategy parameters
  - Memory scaffolding probability (critical for crossing the fitness valley)
  - Task emphasis weights

The inner GA runs for N epochs with that configuration. Outer fitness =
the intelligence score the inner GA achieves.

This is recursive self-improvement: evolution optimizing evolution.

Usage:
    python3 ga_self_improving.py                         # run meta-evolution
    python3 ga_self_improving.py --outer-gens 30         # outer generations
    python3 ga_self_improving.py --inner-epochs 80       # inner run length
    python3 ga_self_improving.py --deploy                # apply best config
"""

import argparse
import copy
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

from ga_cognition_engine import (
    CognitionEngine, Op, ARITY, Node, random_tree,
    TERMINAL_OPS, UNARY_OPS, BINARY_OPS, TERNARY_OPS,
    TRAINING_TASKS, GENERALIZATION_TASKS,
    IntelligenceReport, INTELLIGENCE_LEVELS,
    subtree_crossover, point_mutation, subtree_mutation,
    get_all_nodes, execute, ExecutionContext,
)


# ============================================================================
# EVOLUTION STRATEGY GENOME — what the outer GA evolves
# ============================================================================

@dataclass
class EvolutionStrategy:
    """A complete configuration for the inner GA.
    This IS the genome of the outer GA."""

    # --- Mutation rates ---
    crossover_rate: float = 0.85
    point_mutation_rate: float = 0.15
    subtree_mutation_rate: float = 0.10
    point_mutation_intensity: float = 0.2       # per-node rate within point mutation

    # --- Selection ---
    tournament_size: int = 5
    elitism: int = 3
    novelty_ratio: float = 0.2                  # fraction of selections by novelty

    # --- Fitness function ---
    mean_weight: float = 0.6                    # weight on mean(task_scores) vs min
    parsimony_coeff: float = 0.00005
    complexity_floor: int = 15                  # min nodes before penalty
    complexity_penalty_scale: float = 0.05

    # --- Operator biases (probability weights for random tree generation) ---
    # Higher = more likely to appear. Normalized to sum to 1.
    bias_arithmetic: float = 1.0    # ADD, SUB, MUL, DIV, MOD
    bias_comparison: float = 1.0    # GT, LT, EQ, NEQ
    bias_logic: float = 1.0        # AND, OR, NOT
    bias_control: float = 1.0      # IF, SEQ
    bias_memory: float = 1.0       # READ, WRITE
    bias_io: float = 1.0           # SENSE, ACT
    bias_accumulation: float = 1.0  # INC, DEC, ABS, SIGN, MAX2, MIN2

    # --- Memory scaffolding ---
    # Probability that a new random tree includes a READ-WRITE-IF scaffold
    memory_scaffold_prob: float = 0.0
    # Probability that mutation inserts a memory-using subtree
    memory_mutation_prob: float = 0.0

    # --- Task emphasis (relative weights for fitness) ---
    weight_comparison: float = 1.0
    weight_arithmetic: float = 1.0
    weight_navigation: float = 1.0
    weight_copy_recall: float = 1.0

    # --- Adaptive mutation ---
    stagnation_threshold: int = 20              # epochs before mutation boost
    stagnation_mutation_boost: float = 0.005    # per-epoch boost
    stagnation_mutation_cap: float = 0.3

    # --- Tree generation ---
    max_depth: int = 6
    terminal_prob: float = 0.3                  # chance of terminal at depth > 1

    # --- Population ---
    population_size: int = 60

    # --- Outer GA metadata (not evolved) ---
    outer_fitness: float = 0.0
    outer_id: int = 0

    def to_vector(self) -> List[float]:
        """Encode as float vector for crossover/mutation."""
        return [
            self.crossover_rate,
            self.point_mutation_rate,
            self.subtree_mutation_rate,
            self.point_mutation_intensity,
            float(self.tournament_size),
            float(self.elitism),
            self.novelty_ratio,
            self.mean_weight,
            self.parsimony_coeff,
            float(self.complexity_floor),
            self.complexity_penalty_scale,
            self.bias_arithmetic,
            self.bias_comparison,
            self.bias_logic,
            self.bias_control,
            self.bias_memory,
            self.bias_io,
            self.bias_accumulation,
            self.memory_scaffold_prob,
            self.memory_mutation_prob,
            self.weight_comparison,
            self.weight_arithmetic,
            self.weight_navigation,
            self.weight_copy_recall,
            float(self.stagnation_threshold),
            self.stagnation_mutation_boost,
            self.stagnation_mutation_cap,
            float(self.max_depth),
            self.terminal_prob,
            float(self.population_size),
        ]

    @classmethod
    def from_vector(cls, v: List[float]) -> 'EvolutionStrategy':
        s = cls()
        s.crossover_rate           = np.clip(v[0], 0.3, 0.95)
        s.point_mutation_rate      = np.clip(v[1], 0.01, 0.5)
        s.subtree_mutation_rate    = np.clip(v[2], 0.01, 0.5)
        s.point_mutation_intensity = np.clip(v[3], 0.05, 0.5)
        s.tournament_size          = int(np.clip(v[4], 2, 10))
        s.elitism                  = int(np.clip(v[5], 0, 10))
        s.novelty_ratio            = np.clip(v[6], 0.0, 0.5)
        s.mean_weight              = np.clip(v[7], 0.3, 0.9)
        s.parsimony_coeff          = np.clip(v[8], 0.0, 0.001)
        s.complexity_floor         = int(np.clip(v[9], 5, 30))
        s.complexity_penalty_scale = np.clip(v[10], 0.01, 0.2)
        s.bias_arithmetic          = np.clip(v[11], 0.1, 5.0)
        s.bias_comparison          = np.clip(v[12], 0.1, 5.0)
        s.bias_logic               = np.clip(v[13], 0.1, 5.0)
        s.bias_control             = np.clip(v[14], 0.1, 5.0)
        s.bias_memory              = np.clip(v[15], 0.1, 5.0)
        s.bias_io                  = np.clip(v[16], 0.1, 5.0)
        s.bias_accumulation        = np.clip(v[17], 0.1, 5.0)
        s.memory_scaffold_prob     = np.clip(v[18], 0.0, 0.8)
        s.memory_mutation_prob     = np.clip(v[19], 0.0, 0.5)
        s.weight_comparison        = np.clip(v[20], 0.1, 3.0)
        s.weight_arithmetic        = np.clip(v[21], 0.1, 3.0)
        s.weight_navigation        = np.clip(v[22], 0.1, 3.0)
        s.weight_copy_recall       = np.clip(v[23], 0.1, 3.0)
        s.stagnation_threshold     = int(np.clip(v[24], 5, 50))
        s.stagnation_mutation_boost = np.clip(v[25], 0.001, 0.02)
        s.stagnation_mutation_cap  = np.clip(v[26], 0.15, 0.5)
        s.max_depth                = int(np.clip(v[27], 4, 10))
        s.terminal_prob            = np.clip(v[28], 0.1, 0.6)
        s.population_size          = int(np.clip(v[29], 30, 120))
        # Normalize rates so they sum <= 1
        total_rate = s.crossover_rate + s.point_mutation_rate + s.subtree_mutation_rate
        if total_rate > 0.95:
            scale = 0.95 / total_rate
            s.crossover_rate *= scale
            s.point_mutation_rate *= scale
            s.subtree_mutation_rate *= scale
        return s

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if k.startswith('outer_'):
                continue
            d[k] = v
        d['outer_fitness'] = self.outer_fitness
        return d


# ============================================================================
# MODIFIED COGNITION ENGINE — accepts strategy configuration
# ============================================================================

def build_biased_op_weights(strategy: EvolutionStrategy) -> Dict[str, float]:
    """Map operator categories to probability weights."""
    OP_CATEGORIES = {
        'arithmetic': [Op.ADD, Op.SUB, Op.MUL, Op.DIV, Op.MOD],
        'comparison': [Op.GT, Op.LT, Op.EQ, Op.NEQ],
        'logic': [Op.AND, Op.OR, Op.NOT],
        'control': [Op.IF, Op.SEQ],
        'memory': [Op.READ, Op.WRITE],
        'io': [Op.SENSE, Op.ACT],
        'accumulation': [Op.INC, Op.DEC, Op.ABS, Op.SIGN, Op.MAX2, Op.MIN2],
    }
    biases = {
        'arithmetic': strategy.bias_arithmetic,
        'comparison': strategy.bias_comparison,
        'logic': strategy.bias_logic,
        'control': strategy.bias_control,
        'memory': strategy.bias_memory,
        'io': strategy.bias_io,
        'accumulation': strategy.bias_accumulation,
    }
    weights = {}
    for cat, ops in OP_CATEGORIES.items():
        w = biases[cat] / len(ops)
        for op in ops:
            weights[op] = w
    return weights


def biased_random_tree(rng: random.Random, strategy: EvolutionStrategy,
                       max_depth: int = None, current_depth: int = 0) -> Node:
    """Random tree generator with operator biases from the strategy."""
    if max_depth is None:
        max_depth = strategy.max_depth

    if current_depth >= max_depth or (current_depth > 1 and rng.random() < strategy.terminal_prob):
        op = rng.choice(TERMINAL_OPS)
        node = Node(op=op)
        if op == Op.CONST:
            node.value = round(rng.uniform(-5, 5), 2)
        return node

    # Build weighted non-terminal op list
    op_weights = build_biased_op_weights(strategy)
    non_terminal_ops = [op for op in op_weights if ARITY[op] > 0]
    non_terminal_weights = [op_weights[op] for op in non_terminal_ops]
    total_w = sum(non_terminal_weights)
    non_terminal_weights = [w / total_w for w in non_terminal_weights]

    # Weighted choice
    r = rng.random()
    cumulative = 0.0
    chosen = non_terminal_ops[-1]
    for op, w in zip(non_terminal_ops, non_terminal_weights):
        cumulative += w
        if r <= cumulative:
            chosen = op
            break

    arity = ARITY[chosen]
    children = [biased_random_tree(rng, strategy, max_depth, current_depth + 1) for _ in range(arity)]
    return Node(op=chosen, children=children)


def memory_scaffold(rng: random.Random, strategy: EvolutionStrategy) -> Node:
    """Create a program subtree that uses READ/WRITE/IF together.
    This is the key innovation — seeding coordinated memory usage
    so evolution doesn't have to discover it from scratch."""

    # Pattern: SEQ(WRITE(register, SENSE(input)), IF(GT(READ(register), threshold), action_a, action_b))
    reg = Node(op=Op.CONST, value=float(rng.randint(0, 7)))
    input_ch = Node(op=Op.CONST, value=float(rng.randint(0, 5)))

    # Write sensed value to register
    write_node = Node(op=Op.WRITE, children=[
        reg.copy(),
        Node(op=Op.SENSE, children=[input_ch.copy()])
    ])

    # Read it back and use it in a conditional
    threshold = Node(op=Op.CONST, value=round(rng.uniform(-2, 2), 2))
    read_node = Node(op=Op.READ, children=[reg.copy()])

    condition = Node(op=Op.GT, children=[read_node, threshold])

    # Two different actions
    action_a = Node(op=Op.ACT, children=[
        Node(op=Op.ZERO),
        Node(op=Op.ONE),
    ])
    action_b = Node(op=Op.ACT, children=[
        Node(op=Op.ZERO),
        Node(op=Op.NEG1),
    ])

    if_node = Node(op=Op.IF, children=[condition, action_a, action_b])

    return Node(op=Op.SEQ, children=[write_node, if_node])


def memory_mutation_subtree(rng: random.Random) -> Node:
    """Generate a small subtree that uses memory operations.
    Injected during mutation to help memory co-evolve."""
    patterns = [
        # Read-compare-act
        lambda: Node(op=Op.IF, children=[
            Node(op=Op.GT, children=[
                Node(op=Op.READ, children=[Node(op=Op.CONST, value=float(rng.randint(0, 7)))]),
                Node(op=Op.CONST, value=round(rng.uniform(-2, 2), 2)),
            ]),
            Node(op=Op.ACT, children=[Node(op=Op.ZERO), Node(op=Op.ONE)]),
            Node(op=Op.ACT, children=[Node(op=Op.ZERO), Node(op=Op.NEG1)]),
        ]),
        # Write-sense
        lambda: Node(op=Op.WRITE, children=[
            Node(op=Op.CONST, value=float(rng.randint(0, 7))),
            Node(op=Op.SENSE, children=[Node(op=Op.CONST, value=float(rng.randint(0, 5)))]),
        ]),
        # Accumulate in register
        lambda: Node(op=Op.WRITE, children=[
            Node(op=Op.CONST, value=float(rng.randint(0, 3))),
            Node(op=Op.ADD, children=[
                Node(op=Op.READ, children=[Node(op=Op.CONST, value=float(rng.randint(0, 3)))]),
                Node(op=Op.SENSE, children=[Node(op=Op.CONST, value=float(rng.randint(0, 5)))]),
            ]),
        ]),
    ]
    return rng.choice(patterns)()


class ConfigurableCognitionEngine(CognitionEngine):
    """Cognition engine that accepts an EvolutionStrategy configuration."""

    def __init__(self, strategy: EvolutionStrategy, seed: int = 42, quiet: bool = True):
        super().__init__(
            population_size=strategy.population_size,
            max_depth=strategy.max_depth,
            seed=seed,
            checkpoint_dir=None,
        )
        self.strategy = strategy
        self.quiet = quiet

        # Override GP parameters from strategy
        self.crossover_rate = strategy.crossover_rate
        self.point_mutation_rate = strategy.point_mutation_rate
        self.subtree_mutation_rate = strategy.subtree_mutation_rate
        self.tournament_size = strategy.tournament_size
        self.elitism = strategy.elitism
        self.parsimony_coeff = strategy.parsimony_coeff

        # Disable checkpointing and signals for inner runs
        self.checkpoint_dir = None
        import signal as sig
        sig.signal(sig.SIGINT, sig.SIG_DFL)
        sig.signal(sig.SIGTERM, sig.SIG_DFL)

    def _checkpoint(self, tag="periodic"):
        pass  # no checkpointing in inner runs

    def _evaluate_organism(self, org, tasks=None, n_trials=15, seed=42):
        """Evaluate with task weighting from strategy."""
        if tasks is None:
            tasks = TRAINING_TASKS

        task_weights = {
            'comparison': self.strategy.weight_comparison,
            'arithmetic': self.strategy.weight_arithmetic,
            'navigation': self.strategy.weight_navigation,
            'copy_recall': self.strategy.weight_copy_recall,
        }

        scores = []
        weighted_scores = []
        for name, task in tasks.items():
            score = task.evaluate(org.program, n_trials=n_trials, seed=seed)
            org.task_scores[name] = score
            scores.append(score)
            w = task_weights.get(name, 1.0)
            weighted_scores.append(score * w)

        total_weight = sum(task_weights.get(n, 1.0) for n in tasks.keys())
        mean_score = sum(weighted_scores) / total_weight if total_weight > 0 else 0
        min_score = min(scores) if scores else 0

        base_fitness = self.strategy.mean_weight * mean_score + (1 - self.strategy.mean_weight) * min_score

        size = org.program.size()
        size_penalty = self.strategy.parsimony_coeff * size

        floor = self.strategy.complexity_floor
        if size < floor:
            complexity_bonus = -self.strategy.complexity_penalty_scale * (floor - size) / floor
        else:
            complexity_bonus = 0.0

        org.fitness = max(0, base_fitness - size_penalty + complexity_bonus)
        org.update_stats()

    def _breed(self):
        """Breeding with memory scaffolding and biased operators."""
        r = self.rng.random()

        if r < self.strategy.crossover_rate:
            p1 = self._tournament_select()
            p2 = self._tournament_select()
            child_prog = subtree_crossover(p1.program, p2.program, self.rng)
            lineage = p1.lineage + [p1.id]
        elif r < self.strategy.crossover_rate + self.strategy.point_mutation_rate:
            parent = self._tournament_select()
            child_prog = point_mutation(parent.program, self.rng, rate=self.strategy.point_mutation_intensity)
            lineage = parent.lineage + [parent.id]
        elif r < self.strategy.crossover_rate + self.strategy.point_mutation_rate + self.strategy.subtree_mutation_rate:
            parent = self._tournament_select()
            child_prog = subtree_mutation(parent.program, self.rng)
            lineage = parent.lineage + [parent.id]
        else:
            parent = self._tournament_select()
            child_prog = parent.program.copy()
            lineage = parent.lineage + [parent.id]

        # Memory mutation injection
        if self.rng.random() < self.strategy.memory_mutation_prob:
            nodes = get_all_nodes(child_prog)
            if len(nodes) > 1:
                _, parent_node, idx = self.rng.choice(nodes[1:])
                if parent_node is not None:
                    mem_tree = memory_mutation_subtree(self.rng)
                    parent_node.children[idx] = mem_tree
                    if child_prog.size() > 100:
                        child_prog = child_prog.copy()  # fallback

        from ga_cognition_engine import Organism
        return Organism(
            program=child_prog,
            id=self._new_id(),
            generation=self.epoch,
            lineage=lineage[-10:],
        )

    def _tournament_select(self):
        """Tournament with configurable novelty ratio."""
        candidates = self.rng.sample(self.population, min(self.tournament_size, len(self.population)))
        if self.rng.random() < self.strategy.novelty_ratio:
            sigs = [self._behavior_signature(c) for c in candidates]
            pop_sigs = [self._behavior_signature(o) for o in self.population]
            novelty_scores = []
            for sig in sigs:
                same = sum(1 for ps in pop_sigs if ps == sig)
                novelty_scores.append(1.0 / same)
            best_idx = novelty_scores.index(max(novelty_scores))
            return candidates[best_idx]
        return max(candidates, key=lambda o: o.fitness)

    def initialize(self):
        """Initialize with biased random trees and optional memory scaffolds."""
        if not self.quiet:
            print(f"  Inner GA: pop={self.strategy.population_size}, depth={self.strategy.max_depth}")

        from ga_cognition_engine import Organism
        self.population = []
        for _ in range(self.population_size):
            if self.rng.random() < self.strategy.memory_scaffold_prob:
                prog = memory_scaffold(self.rng, self.strategy)
            else:
                prog = biased_random_tree(self.rng, self.strategy)
            org = Organism(
                program=prog,
                id=self._new_id(),
                generation=0,
            )
            self._evaluate_organism(org)
            self.population.append(org)

        self.best_ever = max(self.population, key=lambda o: o.fitness)
        self._evaluate_generalization(self.best_ever)

    def run_epoch(self):
        """Run one epoch with strategy-configured adaptive mutation."""
        self.epoch += 1

        if self.stagnation > self.strategy.stagnation_threshold:
            boost = self.strategy.stagnation_mutation_boost * (self.stagnation - self.strategy.stagnation_threshold)
            self.subtree_mutation_rate = min(self.strategy.stagnation_mutation_cap,
                                            self.strategy.subtree_mutation_rate + boost)
            self.point_mutation_rate = min(self.strategy.stagnation_mutation_cap,
                                          self.strategy.point_mutation_rate + boost)
        else:
            self.subtree_mutation_rate = self.strategy.subtree_mutation_rate
            self.point_mutation_rate = self.strategy.point_mutation_rate

        # Elitism
        self.population.sort(key=lambda o: o.fitness, reverse=True)
        from ga_cognition_engine import Organism
        new_pop = []
        for o in self.population[:self.strategy.elitism]:
            new_pop.append(Organism(
                program=o.program.copy(), id=o.id, generation=o.generation,
                fitness=o.fitness, task_scores=dict(o.task_scores),
                generalization_scores=dict(o.generalization_scores),
                lineage=list(o.lineage),
            ))

        while len(new_pop) < self.population_size:
            child = self._breed()
            eval_seed = 42 + (self.epoch % 5)
            self._evaluate_organism(child, seed=eval_seed)
            new_pop.append(child)

        self.population = new_pop

        current_best = max(self.population, key=lambda o: o.fitness)
        if current_best.fitness > (self.best_ever.fitness if self.best_ever else 0):
            self.best_ever = current_best
            self.stagnation = 0
        else:
            self.stagnation += 1

        if self.epoch % 10 == 0:
            self._evaluate_generalization(self.best_ever)

        report = self._measure_intelligence(self.best_ever)
        return report

    def run_short(self, epochs: int) -> IntelligenceReport:
        """Run for N epochs and return final intelligence report."""
        self.initialize()
        last_report = None
        for _ in range(epochs):
            last_report = self.run_epoch()
        if last_report is None:
            self._evaluate_generalization(self.best_ever)
            last_report = self._measure_intelligence(self.best_ever)
        return last_report


# ============================================================================
# OUTER GA — evolves evolution strategies
# ============================================================================

class MetaEvolutionGA:
    """Outer GA that evolves EvolutionStrategy configurations."""

    def __init__(
        self,
        outer_pop_size: int = 16,
        inner_epochs: int = 60,
        seed: int = 42,
    ):
        self.outer_pop_size = outer_pop_size
        self.inner_epochs = inner_epochs
        self.rng = random.Random(seed)
        self.seed = seed
        self.population: List[EvolutionStrategy] = []
        self.generation = 0
        self.best_ever: Optional[EvolutionStrategy] = None
        self.history: List[dict] = []
        self.next_id = 0

    def _new_id(self):
        self.next_id += 1
        return self.next_id

    def _random_strategy(self) -> EvolutionStrategy:
        """Generate a random evolution strategy."""
        s = EvolutionStrategy()
        s.crossover_rate = self.rng.uniform(0.4, 0.9)
        s.point_mutation_rate = self.rng.uniform(0.05, 0.35)
        s.subtree_mutation_rate = self.rng.uniform(0.05, 0.3)
        s.point_mutation_intensity = self.rng.uniform(0.05, 0.4)
        s.tournament_size = self.rng.randint(2, 8)
        s.elitism = self.rng.randint(0, 6)
        s.novelty_ratio = self.rng.uniform(0.0, 0.4)
        s.mean_weight = self.rng.uniform(0.4, 0.8)
        s.parsimony_coeff = self.rng.uniform(0.0, 0.0005)
        s.complexity_floor = self.rng.randint(5, 25)
        s.complexity_penalty_scale = self.rng.uniform(0.02, 0.15)
        s.bias_arithmetic = self.rng.uniform(0.3, 3.0)
        s.bias_comparison = self.rng.uniform(0.3, 3.0)
        s.bias_logic = self.rng.uniform(0.3, 3.0)
        s.bias_control = self.rng.uniform(0.3, 3.0)
        s.bias_memory = self.rng.uniform(0.3, 3.0)
        s.bias_io = self.rng.uniform(0.3, 3.0)
        s.bias_accumulation = self.rng.uniform(0.3, 3.0)
        s.memory_scaffold_prob = self.rng.uniform(0.0, 0.5)
        s.memory_mutation_prob = self.rng.uniform(0.0, 0.3)
        s.weight_comparison = self.rng.uniform(0.3, 2.0)
        s.weight_arithmetic = self.rng.uniform(0.3, 2.0)
        s.weight_navigation = self.rng.uniform(0.3, 2.0)
        s.weight_copy_recall = self.rng.uniform(0.3, 2.0)
        s.stagnation_threshold = self.rng.randint(8, 40)
        s.stagnation_mutation_boost = self.rng.uniform(0.002, 0.015)
        s.stagnation_mutation_cap = self.rng.uniform(0.2, 0.45)
        s.max_depth = self.rng.randint(4, 8)
        s.terminal_prob = self.rng.uniform(0.15, 0.5)
        s.population_size = self.rng.choice([30, 40, 50, 60, 80])
        # Normalize rates
        total_rate = s.crossover_rate + s.point_mutation_rate + s.subtree_mutation_rate
        if total_rate > 0.95:
            scale = 0.95 / total_rate
            s.crossover_rate *= scale
            s.point_mutation_rate *= scale
            s.subtree_mutation_rate *= scale
        s.outer_id = self._new_id()
        return s

    def _evaluate_strategy(self, strategy: EvolutionStrategy, trial_seeds: List[int]) -> float:
        """Run the inner GA with this strategy across multiple seeds.
        Returns average intelligence score."""
        scores = []
        for trial_seed in trial_seeds:
            engine = ConfigurableCognitionEngine(strategy, seed=trial_seed, quiet=True)
            try:
                report = engine.run_short(self.inner_epochs)
                # Composite score: IQ + bonus for memory use + bonus for lifetime learning
                score = report.intelligence_score
                score += 0.1 * report.memory_use      # extra reward for memory
                score += 0.15 * report.lifetime_learning  # extra reward for learning
                scores.append(score)
            except Exception as e:
                scores.append(0.0)
        return float(np.mean(scores))

    def _crossover(self, p1: EvolutionStrategy, p2: EvolutionStrategy) -> EvolutionStrategy:
        """Uniform crossover between two strategies."""
        v1 = p1.to_vector()
        v2 = p2.to_vector()
        child_v = []
        for a, b in zip(v1, v2):
            child_v.append(a if self.rng.random() < 0.5 else b)
        child = EvolutionStrategy.from_vector(child_v)
        child.outer_id = self._new_id()
        return child

    def _mutate(self, strategy: EvolutionStrategy, rate: float = 0.15) -> EvolutionStrategy:
        """Gaussian mutation on strategy vector."""
        v = strategy.to_vector()
        mutated = []
        for val in v:
            if self.rng.random() < rate:
                # Scale mutation to parameter magnitude
                scale = max(abs(val) * 0.2, 0.01)
                val += self.rng.gauss(0, scale)
            mutated.append(val)
        child = EvolutionStrategy.from_vector(mutated)
        child.outer_id = self._new_id()
        return child

    def _tournament_select(self, k: int = 3) -> EvolutionStrategy:
        candidates = self.rng.sample(self.population, min(k, len(self.population)))
        return max(candidates, key=lambda s: s.outer_fitness)

    def run(self, outer_generations: int = 20):
        print("=" * 70)
        print("  GA SELF-IMPROVEMENT — EVOLUTION EVOLVING EVOLUTION")
        print("=" * 70)
        print(f"  Outer population:  {self.outer_pop_size} strategies")
        print(f"  Outer generations: {outer_generations}")
        print(f"  Inner epochs/eval: {self.inner_epochs}")
        print(f"  Trial seeds:       3 (robustness)")
        print(f"  Total inner runs:  ~{self.outer_pop_size * outer_generations * 3}")
        print("=" * 70)

        trial_seeds = [42, 123, 777]

        # Initialize outer population
        print("\n  Initializing outer population...")
        self.population = [self._random_strategy() for _ in range(self.outer_pop_size)]

        # Also seed with the known good config from Run 1
        known_good = EvolutionStrategy()  # defaults match the engine that got IQ 0.31
        known_good.outer_id = self._new_id()
        self.population[0] = known_good

        # Evaluate initial population
        for i, strategy in enumerate(self.population):
            fitness = self._evaluate_strategy(strategy, trial_seeds)
            strategy.outer_fitness = fitness
            tag = " (Run1 config)" if i == 0 else ""
            print(f"    [{i+1}/{self.outer_pop_size}] fitness={fitness:.4f}  "
                  f"mem_scaffold={strategy.memory_scaffold_prob:.2f} "
                  f"mem_bias={strategy.bias_memory:.2f} "
                  f"mem_mut={strategy.memory_mutation_prob:.2f}{tag}")
            sys.stdout.flush()

        self.best_ever = max(self.population, key=lambda s: s.outer_fitness)
        print(f"\n  Initial best: {self.best_ever.outer_fitness:.4f}")

        # Evolve
        for gen in range(1, outer_generations + 1):
            self.generation = gen
            print(f"\n--- Outer Generation {gen}/{outer_generations} ---")

            # Sort by fitness
            self.population.sort(key=lambda s: s.outer_fitness, reverse=True)

            # Elitism: keep top 2
            new_pop = [copy.deepcopy(self.population[0]), copy.deepcopy(self.population[1])]

            # Breed rest
            while len(new_pop) < self.outer_pop_size:
                if self.rng.random() < 0.7:
                    p1 = self._tournament_select()
                    p2 = self._tournament_select()
                    child = self._crossover(p1, p2)
                else:
                    parent = self._tournament_select()
                    child = self._mutate(parent, rate=0.2)
                # Additional mutation
                if self.rng.random() < 0.3:
                    child = self._mutate(child, rate=0.1)
                new_pop.append(child)

            self.population = new_pop

            # Evaluate (skip elites)
            for i, strategy in enumerate(self.population):
                if i < 2 and strategy.outer_fitness > 0:
                    continue  # skip elites
                fitness = self._evaluate_strategy(strategy, trial_seeds)
                strategy.outer_fitness = fitness
                print(f"    [{i+1}/{self.outer_pop_size}] fitness={fitness:.4f}  "
                      f"scaffold={strategy.memory_scaffold_prob:.2f} "
                      f"bias_mem={strategy.bias_memory:.2f} "
                      f"novelty={strategy.novelty_ratio:.2f}")
                sys.stdout.flush()

            gen_best = max(self.population, key=lambda s: s.outer_fitness)
            if gen_best.outer_fitness > self.best_ever.outer_fitness:
                self.best_ever = copy.deepcopy(gen_best)
                print(f"  *** NEW BEST: {self.best_ever.outer_fitness:.4f} ***")
            else:
                print(f"  Best: {self.best_ever.outer_fitness:.4f} (no improvement)")

            self.history.append({
                'generation': gen,
                'best_fitness': self.best_ever.outer_fitness,
                'gen_best': gen_best.outer_fitness,
                'gen_mean': float(np.mean([s.outer_fitness for s in self.population])),
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            })

        # Final report
        print(f"\n{'='*70}")
        print(f"  META-EVOLUTION COMPLETE")
        print(f"{'='*70}")
        print(f"  Best meta-fitness: {self.best_ever.outer_fitness:.6f}")
        print(f"\n  Evolved Strategy:")
        for k, v in self.best_ever.to_dict().items():
            if isinstance(v, float):
                print(f"    {k:30s}: {v:.6f}")
            else:
                print(f"    {k:30s}: {v}")

        # Save
        output = {
            'best_strategy': self.best_ever.to_dict(),
            'history': self.history,
            'config': {
                'outer_pop_size': self.outer_pop_size,
                'outer_generations': outer_generations,
                'inner_epochs': self.inner_epochs,
                'trial_seeds': trial_seeds,
            },
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        output_path = os.path.join(TOOLS_DIR, 'best_evolution_strategy.json')
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n  Saved to: {output_path}")

        # Convergence
        print(f"\n  Convergence:")
        for h in self.history:
            print(f"    Gen {h['generation']:3d}: best={h['best_fitness']:.4f}  "
                  f"gen_best={h['gen_best']:.4f}  mean={h['gen_mean']:.4f}")

        print(f"{'='*70}")
        return self.best_ever


def deploy_best_strategy():
    """Load best evolved strategy and run a full cognition engine with it."""
    path = os.path.join(TOOLS_DIR, 'best_evolution_strategy.json')
    if not os.path.exists(path):
        print("No evolved strategy found. Run meta-evolution first.")
        return

    with open(path) as f:
        data = json.load(f)

    strategy_dict = data['best_strategy']
    v = EvolutionStrategy()
    for k, val in strategy_dict.items():
        if hasattr(v, k) and k != 'outer_fitness':
            setattr(v, k, val)

    print("=" * 70)
    print("  DEPLOYING EVOLVED STRATEGY")
    print("=" * 70)
    print(f"  Meta-fitness:         {strategy_dict.get('outer_fitness', 'N/A')}")
    print(f"  Memory scaffold prob: {v.memory_scaffold_prob:.4f}")
    print(f"  Memory mutation prob: {v.memory_mutation_prob:.4f}")
    print(f"  Memory op bias:       {v.bias_memory:.4f}")
    print(f"  Novelty ratio:        {v.novelty_ratio:.4f}")
    print(f"  Population:           {v.population_size}")
    print("=" * 70)

    engine = ConfigurableCognitionEngine(v, seed=42, quiet=False)
    engine.checkpoint_dir = os.path.join(TOOLS_DIR, 'cognition_checkpoints_evolved')
    os.makedirs(engine.checkpoint_dir, exist_ok=True)

    # Re-enable signals for full run
    import signal as sig
    def handler(signum, frame):
        print("\n[SIGNAL] Stopping...")
        engine.running = False
    sig.signal(sig.SIGINT, handler)
    sig.signal(sig.SIGTERM, handler)

    engine.initialize()
    start_time = time.time()

    print(f"\n{'Epoch':>6} | {'Fit':>7} | {'Size':>5} | {'Stag':>4} | Intelligence")
    print("-" * 90)

    while engine.running:
        report = engine.run_epoch()

        if engine.epoch <= 5 or engine.epoch % 10 == 0:
            print(f"{engine.epoch:6d} | {report.best_fitness:7.4f} | "
                  f"{report.best_size:5d} | {engine.stagnation:4d} | {report.summary()}")
            sys.stdout.flush()

        if engine.epoch % 100 == 0:
            elapsed = time.time() - start_time
            eps = engine.epoch / max(elapsed, 1)
            print(f"\n--- Epoch {engine.epoch} ({elapsed:.0f}s, {eps:.1f} ep/s) ---")
            print(f"  Training:       {engine.best_ever.task_scores}")
            print(f"  Generalization: {engine.best_ever.generalization_scores}")
            print(f"  Best program:\n{engine.best_ever.program.to_str(indent=2)[:500]}")

            # Save checkpoint
            state = {
                'epoch': engine.epoch,
                'best_ever': engine.best_ever.to_dict(),
                'metrics_history': engine.metrics_history[-200:],
                'milestones': engine.milestones,
                'strategy': v.to_dict(),
            }
            ckpt = os.path.join(engine.checkpoint_dir, 'latest.json')
            with open(ckpt, 'w') as f:
                json.dump(state, f, indent=2)
            print(f"  [checkpoint saved]")
            sys.stdout.flush()

    # Final
    final = engine._measure_intelligence(engine.best_ever)
    print(f"\n{'='*70}")
    print(f"  EVOLVED STRATEGY RUN COMPLETE — {engine.epoch} epochs")
    print(f"{'='*70}")
    print(f"  Intelligence: {final.summary()}")
    print(f"  Training:     {engine.best_ever.task_scores}")
    print(f"  Generalize:   {engine.best_ever.generalization_scores}")
    print(f"  Milestones:   {engine.milestones}")
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(description='GA Self-Improvement')
    parser.add_argument('--outer-pop', type=int, default=16)
    parser.add_argument('--outer-gens', type=int, default=20)
    parser.add_argument('--inner-epochs', type=int, default=60)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--deploy', action='store_true',
                        help='Run full evolution with best evolved strategy')
    args = parser.parse_args()

    if args.deploy:
        deploy_best_strategy()
    else:
        meta = MetaEvolutionGA(
            outer_pop_size=args.outer_pop,
            inner_epochs=args.inner_epochs,
            seed=args.seed,
        )
        meta.run(outer_generations=args.outer_gens)


if __name__ == '__main__':
    main()
