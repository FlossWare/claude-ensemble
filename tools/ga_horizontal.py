#!/usr/bin/env python3
"""Horizontal Gene Transfer for Cognitive Evolution

Biology's secret weapon: lateral genetic transfer between organisms.
Instead of only inheriting from parents, organisms can acquire
functional genetic material from anywhere in the population.

Four mechanisms from microbiology:

1. CONJUGATION — Direct transfer between organisms. A high-fitness
   organism donates a functional subtree to a lower-fitness one.
   Like bacterial pili exchanging plasmids.

2. TRANSDUCTION — Virus-mediated transfer. "Phage" particles carry
   subtrees from dead/replaced organisms and inject them into random
   living ones. Genetic material persists beyond organism death.

3. TRANSFORMATION — Free DNA uptake. Organisms absorb functional
   subtrees from the environment (a shared gene pool). Any organism
   can pick up any proven pattern.

4. GENE LIBRARY (Plasmid Pool) — Proven functional subtrees are
   extracted and stored. Tagged with fitness contribution. Available
   to all organisms during breeding and mutation.

Why this matters for intelligence evolution:
  - Memory (READ/WRITE/IF) only needs to evolve ONCE, then spreads
  - Specialized task solutions can combine across lineages
  - Population can share innovations laterally, not just vertically
  - Massively accelerates discovery of coordinated structures

Usage:
    python3 ga_horizontal.py                    # run with HGT
    python3 ga_horizontal.py --continuous       # run forever
    python3 ga_horizontal.py --no-hgt           # control (vertical only)
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
    TRAINING_TASKS, GENERALIZATION_TASKS,
    TERMINAL_OPS, UNARY_OPS, BINARY_OPS, TERNARY_OPS,
    PatternClassifyTask, IntelligenceReport, INTELLIGENCE_LEVELS,
    get_all_nodes, subtree_crossover, point_mutation, subtree_mutation,
    random_tree,
)

from ga_accelerated import (
    compile_tree, execute_bytecode, fast_evaluate_task,
    FastCognitionEngine,
)


# ============================================================================
# PLASMID POOL — shared gene library
# ============================================================================

class PlasmidPool:
    """Shared library of functional subtrees (plasmids).

    Extracts and stores proven subtrees from high-performing organisms.
    Tags each with fitness contribution and operational signature.
    Organisms can incorporate plasmids during breeding (transformation).
    """

    def __init__(self, max_size: int = 200):
        self.max_size = max_size
        # Each entry: (subtree_node, fitness_contribution, op_signature, source_gen, uses)
        self.plasmids: List[dict] = []
        self.total_donated = 0
        self.total_uptakes = 0

    def donate(self, organism_tree: Node, organism_fitness: float,
               task_scores: dict, generation: int, rng: random.Random):
        """Extract functional subtrees from a high-performing organism."""
        all_nodes = get_all_nodes(organism_tree)
        if len(all_nodes) < 3:
            return

        for node, parent, idx in all_nodes:
            size = node.size()
            if size < 3 or size > 30:
                continue

            # Score this subtree by what operations it contains
            ops_present = set()
            self._collect_ops(node, ops_present)

            # Interesting subtrees: those with memory, control flow, or I/O
            has_memory = bool(ops_present & {Op.READ, Op.WRITE})
            has_control = bool(ops_present & {Op.IF, Op.SEQ})
            has_io = bool(ops_present & {Op.SENSE, Op.ACT})
            has_compute = bool(ops_present & {Op.ADD, Op.SUB, Op.MUL, Op.DIV})
            has_compare = bool(ops_present & {Op.GT, Op.LT, Op.EQ})

            # Only keep subtrees with at least 2 different functional categories
            categories = sum([has_memory, has_control, has_io, has_compute, has_compare])
            if categories < 2:
                continue

            # Priority: memory-containing subtrees are most valuable
            priority = categories
            if has_memory and has_control:
                priority += 3  # memory+control is the holy grail
            if has_memory and has_io:
                priority += 2  # memory+io is useful

            sig = self._op_signature(node)

            # Check for duplicates (same signature)
            if any(p['signature'] == sig for p in self.plasmids):
                continue

            self.plasmids.append({
                'tree': node.copy(),
                'fitness': organism_fitness,
                'priority': priority,
                'signature': sig,
                'generation': generation,
                'uses': 0,
                'has_memory': has_memory,
                'has_control': has_control,
                'size': size,
            })
            self.total_donated += 1

        # Prune: keep highest priority
        if len(self.plasmids) > self.max_size:
            self.plasmids.sort(key=lambda p: (p['priority'], p['fitness']), reverse=True)
            self.plasmids = self.plasmids[:self.max_size]

    def uptake(self, rng: random.Random, prefer_memory: bool = False) -> Optional[Node]:
        """Select a plasmid for incorporation (transformation)."""
        if not self.plasmids:
            return None

        if prefer_memory:
            memory_plasmids = [p for p in self.plasmids if p['has_memory']]
            if memory_plasmids:
                chosen = rng.choice(memory_plasmids)
                chosen['uses'] += 1
                self.total_uptakes += 1
                return chosen['tree'].copy()

        # Weighted by priority
        weights = [p['priority'] + 1 for p in self.plasmids]
        total = sum(weights)
        r = rng.random() * total
        cum = 0
        for p, w in zip(self.plasmids, weights):
            cum += w
            if r <= cum:
                p['uses'] += 1
                self.total_uptakes += 1
                return p['tree'].copy()

        chosen = self.plasmids[-1]
        chosen['uses'] += 1
        self.total_uptakes += 1
        return chosen['tree'].copy()

    def _collect_ops(self, node: Node, ops: set):
        ops.add(node.op)
        for c in node.children:
            self._collect_ops(c, ops)

    def _op_signature(self, node: Node) -> str:
        """Structural signature for deduplication."""
        if not node.children:
            return node.op.name
        child_sigs = ','.join(self._op_signature(c) for c in node.children)
        return f"{node.op.name}({child_sigs})"

    def stats(self) -> dict:
        memory_count = sum(1 for p in self.plasmids if p['has_memory'])
        return {
            'pool_size': len(self.plasmids),
            'memory_plasmids': memory_count,
            'total_donated': self.total_donated,
            'total_uptakes': self.total_uptakes,
            'avg_priority': float(np.mean([p['priority'] for p in self.plasmids])) if self.plasmids else 0,
        }


# ============================================================================
# PHAGE POOL — viral transfer vectors
# ============================================================================

class PhagePool:
    """Transduction: subtrees from dead/replaced organisms persist as
    'phage particles' that can inject into living organisms."""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.phages: List[Node] = []
        self.infections = 0

    def harvest(self, dead_tree: Node, rng: random.Random):
        """Extract subtrees from a dying organism."""
        nodes = get_all_nodes(dead_tree)
        for node, _, _ in nodes:
            size = node.size()
            if 3 <= size <= 20:
                if rng.random() < 0.3:  # only some fragments survive
                    self.phages.append(node.copy())

        if len(self.phages) > self.max_size:
            # Keep random subset (phages don't have fitness, they're fragments)
            rng.shuffle(self.phages)
            self.phages = self.phages[:self.max_size]

    def infect(self, tree: Node, rng: random.Random) -> Node:
        """Inject a phage subtree into a living organism."""
        if not self.phages:
            return tree

        mutant = tree.copy()
        nodes = get_all_nodes(mutant)
        if len(nodes) < 2:
            return mutant

        # Pick injection point
        _, parent, idx = rng.choice(nodes[1:])
        if parent is None:
            return mutant

        # Pick phage
        phage = rng.choice(self.phages).copy()
        parent.children[idx] = phage
        self.infections += 1

        if mutant.size() > 100:
            return tree.copy()

        return mutant


# ============================================================================
# HGT-ENABLED COGNITION ENGINE
# ============================================================================

class HGTCognitionEngine(FastCognitionEngine):
    """Cognition engine with horizontal gene transfer mechanisms."""

    def __init__(self, strategy: dict, seed: int = 42,
                 conjugation_rate: float = 0.1,
                 transduction_rate: float = 0.05,
                 transformation_rate: float = 0.15,
                 donation_threshold: float = 0.7):  # top 30% donate
        super().__init__(strategy, seed)

        self.conjugation_rate = conjugation_rate
        self.transduction_rate = transduction_rate
        self.transformation_rate = transformation_rate
        self.donation_threshold = donation_threshold

        self.plasmid_pool = PlasmidPool(max_size=200)
        self.phage_pool = PhagePool(max_size=100)
        self.hgt_stats = defaultdict(int)

    def run(self, epochs: int) -> dict:
        """Run with HGT mechanisms active."""
        # Initialize population
        self.population = []
        for _ in range(self.pop_size):
            if self.rng.random() < self.mem_scaffold:
                tree = self._memory_scaffold()
            else:
                tree = self._random_tree()
            bc = compile_tree(tree)
            fitness, scores = self._evaluate(tree, bc)
            self.population.append((tree, bc, fitness, scores, {}))

        self.best_ever = max(self.population, key=lambda o: o[2])
        gen_s = self._evaluate_gen(self.best_ever[0], self.best_ever[1])
        self.best_ever = (*self.best_ever[:4], gen_s)

        # Evolve with HGT
        for ep in range(1, epochs + 1):
            self.epoch = ep
            self.population.sort(key=lambda o: o[2], reverse=True)

            # --- DONATION: top organisms donate to plasmid pool ---
            top_n = max(1, int(len(self.population) * (1 - self.donation_threshold)))
            for org in self.population[:top_n]:
                self.plasmid_pool.donate(
                    org[0], org[2], org[3], self.epoch, self.rng
                )

            # --- TRANSDUCTION: harvest from organisms about to be replaced ---
            for org in self.population[self.elitism:]:
                if self.rng.random() < 0.2:
                    self.phage_pool.harvest(org[0], self.rng)

            # --- BREED with HGT ---
            new_pop = list(self.population[:self.elitism])

            while len(new_pop) < self.pop_size:
                r = self.rng.random()

                if r < self.transformation_rate:
                    # TRANSFORMATION: parent + plasmid from pool
                    parent = self._tournament_select()
                    child = parent[0].copy()
                    plasmid = self.plasmid_pool.uptake(self.rng, prefer_memory=True)
                    if plasmid:
                        nodes = get_all_nodes(child)
                        if len(nodes) > 1:
                            _, pn, idx = self.rng.choice(nodes[1:])
                            if pn is not None:
                                pn.children[idx] = plasmid
                                self.hgt_stats['transformation'] += 1
                    if child.size() > 100:
                        child = parent[0].copy()

                elif r < self.transformation_rate + self.conjugation_rate:
                    # CONJUGATION: direct transfer from high-fit to low-fit
                    donor = self.population[self.rng.randint(0, top_n - 1)]
                    recipient = self._tournament_select()
                    child = recipient[0].copy()
                    donor_nodes = get_all_nodes(donor[0])
                    if len(donor_nodes) > 1:
                        donor_sub, _, _ = self.rng.choice(donor_nodes[1:])
                        if donor_sub.size() <= 25:
                            recipient_nodes = get_all_nodes(child)
                            if len(recipient_nodes) > 1:
                                _, pn, idx = self.rng.choice(recipient_nodes[1:])
                                if pn is not None:
                                    pn.children[idx] = donor_sub.copy()
                                    self.hgt_stats['conjugation'] += 1
                    if child.size() > 100:
                        child = recipient[0].copy()

                elif r < self.transformation_rate + self.conjugation_rate + self.transduction_rate:
                    # TRANSDUCTION: phage infection
                    parent = self._tournament_select()
                    child = self.phage_pool.infect(parent[0], self.rng)
                    self.hgt_stats['transduction'] += 1

                else:
                    # Standard breeding (crossover/mutation)
                    child = self._breed()

                bc = compile_tree(child)
                fitness, scores = self._evaluate(child, bc)
                new_pop.append((child, bc, fitness, scores, {}))

            self.population = new_pop

            # Update best
            cur_best = max(self.population, key=lambda o: o[2])
            if cur_best[2] > self.best_ever[2]:
                gen_s = self._evaluate_gen(cur_best[0], cur_best[1])
                self.best_ever = (*cur_best[:4], gen_s)
                self.stagnation = 0
            else:
                self.stagnation += 1

            if self.stagnation > self.epoch * 0.6:
                break

        # Final measurement
        if self.epoch % 10 != 0:
            gen_scores = self._evaluate_gen(self.best_ever[0], self.best_ever[1])
            self.best_ever = (*self.best_ever[:4], gen_scores)

        metrics = self._measure_intelligence()
        metrics['hgt_stats'] = dict(self.hgt_stats)
        metrics['plasmid_stats'] = self.plasmid_pool.stats()
        return metrics


# ============================================================================
# WORKER FUNCTION FOR MULTIPROCESSING
# ============================================================================

def _eval_hgt_worker(args):
    """Evaluate a strategy with HGT enabled."""
    strategy_dict, seed, epochs, hgt_params = args
    try:
        engine = HGTCognitionEngine(
            strategy_dict, seed=seed,
            conjugation_rate=hgt_params.get('conjugation_rate', 0.1),
            transduction_rate=hgt_params.get('transduction_rate', 0.05),
            transformation_rate=hgt_params.get('transformation_rate', 0.15),
            donation_threshold=hgt_params.get('donation_threshold', 0.7),
        )
        metrics = engine.run(epochs)
        score = (metrics['intelligence_score'] +
                 0.1 * metrics['memory_use'] +
                 0.15 * metrics['lifetime_learning'])
        return score, metrics
    except Exception as e:
        return 0.0, {'error': str(e)}


def _eval_no_hgt_worker(args):
    """Evaluate without HGT (control group)."""
    strategy_dict, seed, epochs = args
    try:
        engine = FastCognitionEngine(strategy_dict, seed=seed)
        metrics = engine.run(epochs)
        score = (metrics['intelligence_score'] +
                 0.1 * metrics['memory_use'] +
                 0.15 * metrics['lifetime_learning'])
        return score, metrics
    except Exception as e:
        return 0.0, {'error': str(e)}


# ============================================================================
# CONTINUOUS EVOLUTION WITH HGT
# ============================================================================

def run_hgt_continuous(cores=None, seed=42, no_hgt=False):
    """Run continuous evolution with horizontal gene transfer.

    Also evolves the HGT rates themselves — conjugation, transduction,
    transformation rates are part of the strategy genome.
    """
    cores = cores or max(1, mp.cpu_count() - 2)
    save_path = os.path.join(TOOLS_DIR, 'hgt_meta_state.json')
    best_path = os.path.join(TOOLS_DIR, 'best_hgt_strategy.json')
    log_path = os.path.join(TOOLS_DIR, 'hgt_evolution_log.jsonl')

    rng = random.Random(seed)
    outer_pop = 24
    next_id = [0]

    def new_id():
        next_id[0] += 1
        return next_id[0]

    def random_strategy():
        r = rng
        s = {
            'crossover_rate': r.uniform(0.3, 0.8),
            'point_mutation_rate': r.uniform(0.05, 0.3),
            'subtree_mutation_rate': r.uniform(0.05, 0.25),
            'point_mutation_intensity': r.uniform(0.05, 0.35),
            'tournament_size': r.randint(2, 8),
            'elitism': r.randint(1, 5),
            'novelty_ratio': r.uniform(0.0, 0.4),
            'mean_weight': r.uniform(0.4, 0.8),
            'parsimony_coeff': r.uniform(0.0, 0.0003),
            'complexity_floor': r.randint(5, 20),
            'complexity_penalty_scale': r.uniform(0.02, 0.12),
            'bias_arithmetic': r.uniform(0.3, 2.5),
            'bias_comparison': r.uniform(0.3, 2.5),
            'bias_logic': r.uniform(0.3, 2.5),
            'bias_control': r.uniform(0.5, 3.0),
            'bias_memory': r.uniform(0.5, 4.0),
            'bias_io': r.uniform(0.3, 2.5),
            'bias_accumulation': r.uniform(0.3, 2.0),
            'memory_scaffold_prob': r.uniform(0.0, 0.5),
            'memory_mutation_prob': r.uniform(0.0, 0.3),
            'weight_comparison': r.uniform(0.3, 2.0),
            'weight_arithmetic': r.uniform(0.3, 2.0),
            'weight_navigation': r.uniform(0.3, 2.0),
            'weight_copy_recall': r.uniform(0.5, 3.0),
            'stagnation_threshold': r.randint(8, 35),
            'stagnation_mutation_boost': r.uniform(0.002, 0.012),
            'stagnation_mutation_cap': r.uniform(0.2, 0.4),
            'max_depth': r.randint(4, 8),
            'terminal_prob': r.uniform(0.15, 0.45),
            'population_size': r.choice([40, 50, 60, 80]),
            # HGT rates — these get evolved too
            'conjugation_rate': r.uniform(0.02, 0.2),
            'transduction_rate': r.uniform(0.01, 0.15),
            'transformation_rate': r.uniform(0.05, 0.3),
            'donation_threshold': r.uniform(0.6, 0.9),
            '_id': new_id(),
            '_fitness': 0.0,
        }
        total = s['crossover_rate'] + s['point_mutation_rate'] + s['subtree_mutation_rate']
        hgt_total = s['conjugation_rate'] + s['transduction_rate'] + s['transformation_rate']
        # Ensure vertical + horizontal breeding rates don't exceed 1
        grand_total = total + hgt_total
        if grand_total > 0.95:
            scale = 0.95 / grand_total
            s['crossover_rate'] *= scale
            s['point_mutation_rate'] *= scale
            s['subtree_mutation_rate'] *= scale
            s['conjugation_rate'] *= scale
            s['transduction_rate'] *= scale
            s['transformation_rate'] *= scale
        return s

    def crossover(p1, p2):
        child = {}
        for k in p1:
            if k.startswith('_'):
                continue
            child[k] = p1[k] if rng.random() < 0.5 else p2[k]
        child['_id'] = new_id()
        child['_fitness'] = 0.0
        return child

    def mutate(s, rate=0.15):
        child = dict(s)
        for k, v in child.items():
            if k.startswith('_'):
                continue
            if isinstance(v, float) and rng.random() < rate:
                scale = max(abs(v) * 0.2, 0.01)
                child[k] = v + rng.gauss(0, scale)
            elif isinstance(v, int) and rng.random() < rate:
                child[k] = v + rng.choice([-2, -1, 1, 2])
        # Clamp critical values
        for k in ['crossover_rate', 'point_mutation_rate', 'subtree_mutation_rate']:
            child[k] = np.clip(child.get(k, 0.1), 0.01, 0.5)
        for k in ['conjugation_rate', 'transduction_rate', 'transformation_rate']:
            child[k] = np.clip(child.get(k, 0.1), 0.0, 0.3)
        child['donation_threshold'] = np.clip(child.get('donation_threshold', 0.7), 0.5, 0.95)
        child['tournament_size'] = int(np.clip(child.get('tournament_size', 5), 2, 10))
        child['elitism'] = int(np.clip(child.get('elitism', 3), 0, 8))
        child['max_depth'] = int(np.clip(child.get('max_depth', 6), 4, 10))
        child['population_size'] = int(np.clip(child.get('population_size', 60), 30, 120))
        child['memory_scaffold_prob'] = np.clip(child.get('memory_scaffold_prob', 0.1), 0.0, 0.7)
        child['memory_mutation_prob'] = np.clip(child.get('memory_mutation_prob', 0.1), 0.0, 0.4)
        for k in ['bias_arithmetic', 'bias_comparison', 'bias_logic', 'bias_control',
                   'bias_memory', 'bias_io', 'bias_accumulation']:
            child[k] = np.clip(child.get(k, 1.0), 0.1, 5.0)
        child['_id'] = new_id()
        child['_fitness'] = 0.0
        return child

    def tournament(pop, k=3):
        candidates = rng.sample(pop, min(k, len(pop)))
        return max(candidates, key=lambda s: s['_fitness'])

    def eval_batch(strategies, epochs, seeds):
        work = []
        for s in strategies:
            hgt_params = {
                'conjugation_rate': s.get('conjugation_rate', 0.1),
                'transduction_rate': s.get('transduction_rate', 0.05),
                'transformation_rate': s.get('transformation_rate', 0.15),
                'donation_threshold': s.get('donation_threshold', 0.7),
            }
            for sd in seeds:
                if no_hgt:
                    work.append((s, sd, epochs))
                else:
                    work.append((s, sd, epochs, hgt_params))

        worker = _eval_no_hgt_worker if no_hgt else _eval_hgt_worker
        with mp.Pool(processes=cores) as pool:
            results = pool.map(worker, work)

        n_seeds = len(seeds)
        fitnesses = []
        all_metrics = []
        for i in range(len(strategies)):
            chunk = results[i*n_seeds:(i+1)*n_seeds]
            scores = [r[0] for r in chunk]
            fitnesses.append(float(np.mean(scores)))
            all_metrics.append(chunk[-1][1])  # last seed's metrics
        return fitnesses, all_metrics

    # Resume or initialize
    population = []
    best_ever = None
    best_fitness = 0.0
    history = []
    start_gen = 0

    if os.path.exists(save_path):
        with open(save_path) as f:
            state = json.load(f)
        population = state['population']
        best_ever = state['best_ever']
        best_fitness = state['best_fitness']
        history = state.get('history', [])
        start_gen = state.get('generation', 0)
        next_id[0] = state.get('next_id', 100)
        print(f"  RESUMED from generation {start_gen}, best={best_fitness:.4f}")
    else:
        population = [random_strategy() for _ in range(outer_pop)]

        # Seed configurations
        # 1. No HGT baseline
        population[0].update({
            'memory_scaffold_prob': 0.0, 'memory_mutation_prob': 0.0,
            'conjugation_rate': 0.0, 'transduction_rate': 0.0,
            'transformation_rate': 0.0,
        })
        # 2. Heavy HGT
        population[1].update({
            'conjugation_rate': 0.15, 'transduction_rate': 0.1,
            'transformation_rate': 0.25, 'donation_threshold': 0.7,
            'memory_scaffold_prob': 0.2, 'bias_memory': 2.5,
        })
        # 3. Scaffold + moderate HGT
        population[2].update({
            'memory_scaffold_prob': 0.35, 'memory_mutation_prob': 0.15,
            'conjugation_rate': 0.1, 'transduction_rate': 0.05,
            'transformation_rate': 0.15, 'bias_memory': 2.0, 'bias_control': 2.0,
        })
        # 4. Heavy transformation (plasmid focus)
        population[3].update({
            'transformation_rate': 0.3, 'conjugation_rate': 0.05,
            'transduction_rate': 0.02, 'donation_threshold': 0.6,
            'memory_scaffold_prob': 0.15, 'bias_memory': 3.0,
        })

    running = [True]
    def handler(signum, frame):
        print(f"\n[SIGNAL] Saving and stopping...")
        running[0] = False
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    mode = "VERTICAL ONLY (control)" if no_hgt else "HORIZONTAL GENE TRANSFER"
    print("=" * 70)
    print(f"  CONTINUOUS EVOLUTION — {mode}")
    print("=" * 70)
    print(f"  Population:    {outer_pop} strategies")
    print(f"  Cores:         {cores}")
    print(f"  HGT:           {'DISABLED' if no_hgt else 'ENABLED (conjugation + transduction + transformation)'}")
    print(f"  Resume from:   gen {start_gen}")
    print(f"  Best so far:   {best_fitness:.4f}")
    print("=" * 70)

    PHASES = [
        {'gens': (1, 15),     'inner': 80,  'seeds': [42, 123, 777]},
        {'gens': (16, 40),    'inner': 150, 'seeds': [42, 123, 777, 500, 900]},
        {'gens': (41, 80),    'inner': 250, 'seeds': [42, 123, 777, 500, 900, 1111, 2222]},
        {'gens': (81, 999999),'inner': 400, 'seeds': [42, 123, 777, 500, 900, 1111, 2222, 3333, 4444]},
    ]

    def get_phase(gen):
        for p in PHASES:
            if p['gens'][0] <= gen <= p['gens'][1]:
                return p
        return PHASES[-1]

    total_start = time.time()
    gen = start_gen

    while running[0]:
        gen += 1
        phase = get_phase(gen)
        phase_num = next(i+1 for i, p in enumerate(PHASES) if p['gens'][0] <= gen <= p['gens'][1])
        gen_start = time.time()

        if gen == 1:
            print(f"\n  Phase {phase_num} — Evaluating {outer_pop} strategies "
                  f"(inner={phase['inner']}ep, {len(phase['seeds'])} seeds, HGT={'off' if no_hgt else 'on'})...")
            fits, mets = eval_batch(population, phase['inner'], phase['seeds'])
            for i, (fit, met) in enumerate(zip(fits, mets)):
                population[i]['_fitness'] = fit
                tag = ""
                if i == 0: tag = " [no-hgt]"
                elif i == 1: tag = " [heavy-hgt]"
                elif i == 2: tag = " [scaffold+hgt]"
                elif i == 3: tag = " [plasmid-focus]"
                hgt_info = ""
                if not no_hgt and isinstance(met, dict) and 'hgt_stats' in met:
                    hs = met['hgt_stats']
                    hgt_info = f"  conj={hs.get('conjugation',0)} trans={hs.get('transduction',0)} xform={hs.get('transformation',0)}"
                print(f"    [{i+1:2d}] {fit:.4f}  mem={met.get('memory_use',0):.3f}  "
                      f"learn={met.get('lifetime_learning',0):.3f}{hgt_info}{tag}")

            best_ever = max(population, key=lambda s: s['_fitness'])
            best_fitness = best_ever['_fitness']
        else:
            population.sort(key=lambda s: s['_fitness'], reverse=True)
            new_pop = [copy.deepcopy(population[0]), copy.deepcopy(population[1]),
                       copy.deepcopy(population[2])]

            while len(new_pop) < outer_pop:
                if rng.random() < 0.65:
                    p1 = tournament(population, k=4)
                    p2 = tournament(population, k=4)
                    child = crossover(p1, p2)
                else:
                    parent = tournament(population, k=3)
                    child = mutate(parent, rate=0.2)
                if rng.random() < 0.35:
                    child = mutate(child, rate=0.1)
                new_pop.append(child)

            population = new_pop

            to_eval = population[3:]
            if to_eval:
                screen_epochs = max(40, phase['inner'] // 2)
                fits, _ = eval_batch(to_eval, screen_epochs, phase['seeds'][:2])
                for i, fit in enumerate(fits):
                    to_eval[i]['_fitness'] = fit

            all_sorted = sorted(population, key=lambda s: s['_fitness'], reverse=True)
            top_n = max(4, outer_pop // 3)
            top = all_sorted[:top_n]
            fits, mets = eval_batch(top, phase['inner'], phase['seeds'])
            for i, (fit, met) in enumerate(zip(fits, mets)):
                top[i]['_fitness'] = fit

        gen_best = max(population, key=lambda s: s['_fitness'])
        gen_elapsed = time.time() - gen_start
        improved = gen_best['_fitness'] > best_fitness

        if improved:
            best_ever = copy.deepcopy(gen_best)
            best_fitness = gen_best['_fitness']
            print(f"\n  Gen {gen:4d} [P{phase_num}] *** NEW BEST: {best_fitness:.4f} *** ({gen_elapsed:.0f}s)")
            print(f"    scaffold={best_ever['memory_scaffold_prob']:.3f}  "
                  f"mem_bias={best_ever['bias_memory']:.3f}  "
                  f"conj={best_ever['conjugation_rate']:.3f}  "
                  f"trans={best_ever['transduction_rate']:.3f}  "
                  f"xform={best_ever['transformation_rate']:.3f}")
        else:
            mean_fit = float(np.mean([s['_fitness'] for s in population]))
            print(f"  Gen {gen:4d} [P{phase_num}] best={best_fitness:.4f}  "
                  f"gen_best={gen_best['_fitness']:.4f}  mean={mean_fit:.4f}  ({gen_elapsed:.0f}s)")

        entry = {
            'gen': gen, 'phase': phase_num,
            'best': best_fitness, 'gen_best': gen_best['_fitness'],
            'mean': float(np.mean([s['_fitness'] for s in population])),
            'inner_epochs': phase['inner'], 'time_s': gen_elapsed,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'improved': improved, 'hgt': not no_hgt,
        }
        history.append(entry)
        with open(log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        state = {
            'generation': gen, 'best_ever': best_ever,
            'best_fitness': best_fitness, 'population': population,
            'history': history[-500:], 'next_id': next_id[0],
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        with open(save_path, 'w') as f:
            json.dump(state, f, indent=2)

        if improved:
            out = {
                'best_strategy': {k: v for k, v in best_ever.items() if not k.startswith('_')},
                'best_fitness': best_fitness,
                'generation': gen, 'phase': phase_num,
                'hgt_enabled': not no_hgt,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }
            with open(best_path, 'w') as f:
                json.dump(out, f, indent=2)

        sys.stdout.flush()

    total_time = time.time() - total_start
    print(f"\n{'='*70}")
    print(f"  STOPPED at generation {gen} ({total_time:.0f}s)")
    print(f"{'='*70}")
    print(f"  Best fitness: {best_fitness:.6f}")
    print(f"  HGT rates evolved to:")
    print(f"    conjugation:     {best_ever.get('conjugation_rate', 0):.4f}")
    print(f"    transduction:    {best_ever.get('transduction_rate', 0):.4f}")
    print(f"    transformation:  {best_ever.get('transformation_rate', 0):.4f}")
    print(f"    donation thresh: {best_ever.get('donation_threshold', 0):.4f}")
    print(f"  Memory params:")
    print(f"    scaffold prob:   {best_ever.get('memory_scaffold_prob', 0):.4f}")
    print(f"    memory bias:     {best_ever.get('bias_memory', 0):.4f}")
    print(f"    memory mutation: {best_ever.get('memory_mutation_prob', 0):.4f}")
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(description='Horizontal Gene Transfer Evolution')
    parser.add_argument('--continuous', action='store_true',
                        help='Run continuously with HGT')
    parser.add_argument('--no-hgt', action='store_true',
                        help='Control group: vertical inheritance only')
    parser.add_argument('--cores', type=int, default=None)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    if args.continuous or True:  # always continuous for now
        run_hgt_continuous(cores=args.cores, seed=args.seed, no_hgt=args.no_hgt)


if __name__ == '__main__':
    main()
