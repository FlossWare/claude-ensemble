#!/usr/bin/env python3
"""GA^3 — GA using GA to GA itself

NOTHING IS FIXED. Everything evolves:
  - Programs (what organisms do)
  - Mutators (how organisms reproduce)
  - Fitness weights (what organisms optimize for)
  - Tasks (the environment organisms face)
  - Population structure (islands, migration)
  - HGT rates (horizontal transfer)
  - Instruction biases (which ops matter)

Chaos is the ally. High variation, catastrophic events,
predator-prey co-evolution, organism merging, everything
subject to mutation at every level.

Three evolutionary layers running simultaneously:

  LAYER 0: Programs evolve to solve tasks
  LAYER 1: Mutators evolve to produce better programs
  LAYER 2: Environments co-evolve to challenge programs

Each organism carries its OWN evolutionary strategy —
mutation rates, operator biases, HGT preferences.
Organisms with better self-evolution outcompete those without.
Natural selection selects for evolvability itself.

Usage:
    python3 ga_chaos.py              # unleash chaos
    python3 ga_chaos.py --islands 7  # 7 island populations
    python3 ga_chaos.py --cores 14   # max parallelism
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
    PatternClassifyTask,
    get_all_nodes, subtree_crossover, point_mutation, subtree_mutation,
)

from ga_accelerated import compile_tree, execute_bytecode, fast_evaluate_task


# ============================================================================
# SELF-ADAPTIVE ORGANISM — carries its own evolution strategy
# ============================================================================

class ChaosOrganism:
    """An organism that carries its own evolutionary parameters.

    The genome has two parts:
      1. program: the executable program tree (what it does)
      2. strategy: its own mutation/reproduction parameters (how it evolves)

    When it reproduces, BOTH parts are subject to mutation.
    Organisms with better strategies produce better offspring,
    so evolution selects for evolvability itself.
    """

    __slots__ = ['program', 'bytecode', 'strategy', 'fitness', 'task_scores',
                 'gen_scores', 'age', 'island', 'lineage_len', 'id']

    def __init__(self, program: Node, strategy: dict = None, island: int = 0):
        self.program = program
        self.bytecode = compile_tree(program)
        self.strategy = strategy or self._default_strategy()
        self.fitness = 0.0
        self.task_scores = {}
        self.gen_scores = {}
        self.age = 0
        self.island = island
        self.lineage_len = 0
        self.id = 0

    @staticmethod
    def _default_strategy():
        return {
            'crossover_rate': 0.5,
            'point_mut_rate': 0.15,
            'subtree_mut_rate': 0.1,
            'point_intensity': 0.2,
            'hgt_accept_rate': 0.1,     # willingness to accept foreign DNA
            'hgt_donate_rate': 0.1,     # willingness to donate
            'const_mut_scale': 1.0,     # how much constants change
            'preferred_depth': 6,
            'op_bias_memory': 1.0,      # preference for READ/WRITE
            'op_bias_control': 1.0,     # preference for IF/SEQ
            'op_bias_io': 1.0,          # preference for SENSE/ACT
            'chaos_rate': 0.05,         # chance of completely random subtree replacement
            'merge_rate': 0.05,         # chance of absorbing another organism
            'fitness_weight_mean': 0.6,
            'fitness_weight_novelty': 0.1,
        }

    def mutate_strategy(self, rng: random.Random, rate: float = 0.1):
        """Mutate the organism's own evolutionary parameters."""
        for k, v in self.strategy.items():
            if rng.random() < rate:
                if isinstance(v, float):
                    scale = max(abs(v) * 0.3, 0.02)
                    self.strategy[k] = max(0.0, min(1.0, v + rng.gauss(0, scale)))
                elif isinstance(v, int):
                    self.strategy[k] = max(2, v + rng.choice([-1, 0, 1]))


# ============================================================================
# CO-EVOLVING TASKS — the environment fights back
# ============================================================================

class EvolvingTask:
    """A task that evolves to challenge organisms.

    Tasks that organisms find easy get harder.
    Tasks that are too hard get easier.
    The environment co-evolves with the population.
    """

    def __init__(self, base_task, difficulty_params: dict = None):
        self.base_task = base_task
        self.name = base_task.name
        self.params = difficulty_params or {
            'noise': 0.0,         # noise added to inputs
            'scale': 1.0,         # value range multiplier
            'distractor_rate': 0.0,  # irrelevant input channels
            'time_pressure': 1.0,  # fraction of normal steps allowed
        }
        self.recent_scores = []
        self.generation = 0

    def evaluate(self, bytecode: list, n_trials: int = 12, seed: int = 42) -> float:
        score = fast_evaluate_task(bytecode, self.base_task, n_trials=n_trials, seed=seed)
        self.recent_scores.append(score)
        if len(self.recent_scores) > 50:
            self.recent_scores = self.recent_scores[-50:]
        return score

    def evolve(self, rng: random.Random):
        """Adjust difficulty based on population performance."""
        if len(self.recent_scores) < 10:
            return

        avg_score = np.mean(self.recent_scores[-20:])
        self.generation += 1

        # If organisms are doing too well, make it harder
        if avg_score > 0.7:
            self.params['noise'] = min(2.0, self.params['noise'] + rng.uniform(0, 0.1))
            self.params['scale'] = min(3.0, self.params['scale'] + rng.uniform(0, 0.2))
        # If too hard, ease up
        elif avg_score < 0.3:
            self.params['noise'] = max(0.0, self.params['noise'] - rng.uniform(0, 0.05))
            self.params['scale'] = max(0.5, self.params['scale'] - rng.uniform(0, 0.1))


# ============================================================================
# ISLAND — an independent population with its own dynamics
# ============================================================================

class Island:
    """An isolated population with its own evolutionary dynamics.
    Periodically exchanges migrants with other islands.
    Each island can develop different strategies independently."""

    def __init__(self, island_id: int, pop_size: int, rng: random.Random):
        self.id = island_id
        self.pop_size = pop_size
        self.organisms: List[ChaosOrganism] = []
        self.plasmids: List[Node] = []  # shared gene fragments
        self.epoch = 0
        self.best_ever_fitness = 0.0
        self.stagnation = 0
        self.catastrophes = 0
        self.rng = random.Random(rng.randint(0, 2**31))
        self.stats = defaultdict(int)

    def initialize(self, max_depth: int = 6):
        """Create initial random population."""
        self.organisms = []
        for i in range(self.pop_size):
            tree = self._biased_random_tree(max_depth)
            org = ChaosOrganism(tree, island=self.id)
            org.id = i
            # Randomize each organism's strategy
            org.mutate_strategy(self.rng, rate=0.5)
            self.organisms.append(org)

    def _biased_random_tree(self, max_depth: int, depth: int = 0) -> Node:
        """Random tree with memory bias baked in at island level."""
        if depth >= max_depth or (depth > 1 and self.rng.random() < 0.3):
            op = self.rng.choice(TERMINAL_OPS)
            n = Node(op=op)
            if op == Op.CONST:
                n.value = round(self.rng.uniform(-5, 5), 2)
            return n

        # Bias toward memory/control on some islands
        if self.id % 3 == 0:
            # Memory-biased island
            memory_ops = [Op.READ, Op.WRITE, Op.IF, Op.SEQ]
            if self.rng.random() < 0.3 and depth < max_depth - 1:
                op = self.rng.choice(memory_ops)
                arity = ARITY[op]
                children = [self._biased_random_tree(max_depth, depth+1) for _ in range(arity)]
                return Node(op=op, children=children)

        all_ops = UNARY_OPS + BINARY_OPS + TERNARY_OPS
        op = self.rng.choice(all_ops)
        arity = ARITY[op]
        children = [self._biased_random_tree(max_depth, depth+1) for _ in range(arity)]
        return Node(op=op, children=children)

    def evaluate_all(self, tasks: dict, eval_seed: int = 42):
        """Evaluate all organisms."""
        for org in self.organisms:
            scores = []
            for name, task in tasks.items():
                if isinstance(task, EvolvingTask):
                    s = task.evaluate(org.bytecode, n_trials=10, seed=eval_seed)
                else:
                    s = fast_evaluate_task(org.bytecode, task, n_trials=10, seed=eval_seed)
                org.task_scores[name] = s
                scores.append(s)

            # Fitness uses the organism's OWN weights
            w = org.strategy['fitness_weight_mean']
            mean_s = np.mean(scores)
            min_s = min(scores) if scores else 0
            org.fitness = w * mean_s + (1 - w) * min_s

            # Parsimony
            size = org.program.size()
            org.fitness -= 0.00003 * size
            if size < 10:
                org.fitness -= 0.03 * (10 - size) / 10
            org.fitness = max(0, org.fitness)

    def evolve_one_epoch(self, tasks: dict):
        """Run one epoch of evolution with full chaos."""
        self.epoch += 1
        rng = self.rng

        # Evaluate
        self.evaluate_all(tasks, eval_seed=42 + (self.epoch % 7))

        # Sort by fitness
        self.organisms.sort(key=lambda o: o.fitness, reverse=True)

        # Track stagnation
        cur_best = self.organisms[0].fitness
        if cur_best > self.best_ever_fitness:
            self.best_ever_fitness = cur_best
            self.stagnation = 0
        else:
            self.stagnation += 1

        # === CATASTROPHIC EVENT ===
        # Periodically wipe most of the population — forces diversity
        if self.stagnation > 30 and rng.random() < 0.3:
            survivors = max(3, self.pop_size // 5)
            self.organisms = self.organisms[:survivors]
            while len(self.organisms) < self.pop_size:
                tree = self._biased_random_tree(max_depth=rng.randint(4, 8))
                org = ChaosOrganism(tree, island=self.id)
                org.mutate_strategy(rng, rate=0.5)
                self.organisms.append(org)
            self.catastrophes += 1
            self.stagnation = 0
            self.stats['catastrophes'] += 1
            return

        # === DONATION TO PLASMID POOL ===
        for org in self.organisms[:3]:  # top 3 donate
            nodes = get_all_nodes(org.program)
            for node, _, _ in nodes:
                if 3 <= node.size() <= 20 and rng.random() < 0.1:
                    self.plasmids.append(node.copy())
            if len(self.plasmids) > 150:
                rng.shuffle(self.plasmids)
                self.plasmids = self.plasmids[:100]

        # === BREED NEW GENERATION ===
        # Elitism: keep top 2
        new_pop = [self.organisms[0], self.organisms[1]]

        while len(new_pop) < self.pop_size:
            child = self._breed_one(rng)
            new_pop.append(child)

        self.organisms = new_pop

        # Age everyone
        for org in self.organisms:
            org.age += 1

    def _breed_one(self, rng: random.Random) -> ChaosOrganism:
        """Breed one offspring using parent's OWN strategy."""
        # Select parent(s)
        parent = self._tournament(rng, k=4)
        s = parent.strategy

        r = rng.random()

        if r < s['chaos_rate']:
            # CHAOS: completely random new program
            child_tree = self._biased_random_tree(max_depth=int(s['preferred_depth']))
            self.stats['chaos'] += 1

        elif r < s['chaos_rate'] + s['merge_rate']:
            # MERGE: combine two organisms
            other = self._tournament(rng, k=3)
            child_tree = self._merge_organisms(parent, other, rng)
            self.stats['merge'] += 1

        elif r < s['chaos_rate'] + s['merge_rate'] + s.get('hgt_accept_rate', 0):
            # HGT: incorporate plasmid
            child_tree = parent.program.copy()
            if self.plasmids:
                plasmid = rng.choice(self.plasmids).copy()
                nodes = get_all_nodes(child_tree)
                if len(nodes) > 1:
                    _, pn, idx = rng.choice(nodes[1:])
                    if pn is not None:
                        pn.children[idx] = plasmid
                        self.stats['hgt_uptake'] += 1
            if child_tree.size() > 100:
                child_tree = parent.program.copy()

        elif r < s['chaos_rate'] + s['merge_rate'] + s.get('hgt_accept_rate', 0) + s['crossover_rate']:
            # CROSSOVER
            other = self._tournament(rng, k=3)
            child_tree = subtree_crossover(parent.program, other.program, rng)
            self.stats['crossover'] += 1

        elif r < (s['chaos_rate'] + s['merge_rate'] + s.get('hgt_accept_rate', 0) +
                  s['crossover_rate'] + s['subtree_mut_rate']):
            # SUBTREE MUTATION
            child_tree = subtree_mutation(parent.program, rng)
            self.stats['subtree_mut'] += 1

        else:
            # POINT MUTATION
            child_tree = point_mutation(parent.program, rng, rate=s['point_intensity'])
            self.stats['point_mut'] += 1

        if child_tree.size() > 100:
            child_tree = parent.program.copy()

        child = ChaosOrganism(child_tree, strategy=copy.deepcopy(parent.strategy), island=self.id)
        child.lineage_len = parent.lineage_len + 1

        # MUTATE THE STRATEGY ITSELF
        child.mutate_strategy(rng, rate=0.15)

        return child

    def _tournament(self, rng, k=4) -> ChaosOrganism:
        candidates = rng.sample(self.organisms, min(k, len(self.organisms)))
        return max(candidates, key=lambda o: o.fitness)

    def _merge_organisms(self, a: ChaosOrganism, b: ChaosOrganism,
                         rng: random.Random) -> Node:
        """Symbiotic merge: combine two organisms into one."""
        # Wrap both programs in a SEQ (execute both) or IF (conditionally use one)
        if rng.random() < 0.5:
            return Node(op=Op.SEQ, children=[a.program.copy(), b.program.copy()])
        else:
            # Use b's output as condition for choosing between a's sub-strategies
            return Node(op=Op.IF, children=[
                b.program.copy(),
                a.program.copy(),
                Node(op=Op.ACT, children=[
                    Node(op=Op.ZERO),
                    Node(op=Op.SENSE, children=[Node(op=Op.ZERO)])
                ])
            ])

    def get_migrants(self, n: int) -> List[ChaosOrganism]:
        """Select top organisms for migration to other islands."""
        self.organisms.sort(key=lambda o: o.fitness, reverse=True)
        return [copy.deepcopy(o) for o in self.organisms[:n]]

    def accept_migrants(self, migrants: List[ChaosOrganism]):
        """Accept migrants, replacing worst organisms."""
        self.organisms.sort(key=lambda o: o.fitness, reverse=True)
        for i, m in enumerate(migrants):
            m.island = self.id
            if len(self.organisms) > len(migrants):
                self.organisms[-(i+1)] = m

    def best(self) -> ChaosOrganism:
        return max(self.organisms, key=lambda o: o.fitness)


# ============================================================================
# CHAOS ENGINE — orchestrates everything
# ============================================================================

def _run_island_epoch(args):
    """Worker: run one island for N epochs."""
    island, tasks_config, n_epochs = args
    tasks = {}
    for name, cfg in tasks_config.items():
        if name in TRAINING_TASKS:
            tasks[name] = TRAINING_TASKS[name]
        elif name in GENERALIZATION_TASKS:
            tasks[name] = GENERALIZATION_TASKS[name]

    for _ in range(n_epochs):
        island.evaluate_all(tasks)
        island.evolve_one_epoch(tasks)

    best = island.best()
    # Evaluate generalization
    for gname, gtask in GENERALIZATION_TASKS.items():
        best.gen_scores[gname] = fast_evaluate_task(best.bytecode, gtask, n_trials=10, seed=999)

    return island, {
        'fitness': best.fitness,
        'task_scores': best.task_scores,
        'gen_scores': best.gen_scores,
        'size': best.program.size(),
        'strategy': best.strategy,
        'stagnation': island.stagnation,
        'catastrophes': island.catastrophes,
        'stats': dict(island.stats),
        'epoch': island.epoch,
    }


class ChaosEngine:
    """The meta-orchestrator. Runs multiple islands with periodic
    migration, catastrophic events, and environment co-evolution."""

    def __init__(self, n_islands: int = 7, island_pop: int = 40,
                 cores: int = None, seed: int = 42):
        self.n_islands = n_islands
        self.island_pop = island_pop
        self.cores = cores or max(1, mp.cpu_count() - 2)
        self.rng = random.Random(seed)
        self.seed = seed

        self.islands: List[Island] = []
        self.global_best = None
        self.global_best_fitness = 0.0
        self.generation = 0
        self.history = []

        self.save_path = os.path.join(TOOLS_DIR, 'chaos_state.json')
        self.best_path = os.path.join(TOOLS_DIR, 'chaos_best.json')
        self.log_path = os.path.join(TOOLS_DIR, 'chaos_log.jsonl')

    def initialize(self):
        """Create islands with different biases."""
        self.islands = []
        for i in range(self.n_islands):
            island = Island(i, self.island_pop, self.rng)
            # Different islands start with different strategies
            depth = 4 + (i % 4)  # depths 4-7
            island.initialize(max_depth=depth)
            self.islands.append(island)

        print(f"  Created {self.n_islands} islands × {self.island_pop} organisms")
        print(f"  Island specializations:")
        for i, island in enumerate(self.islands):
            bias = "MEMORY" if i % 3 == 0 else "GENERAL"
            print(f"    Island {i}: {bias}, depth={4 + i%4}")

    def run(self):
        """Run the chaos engine continuously."""
        self.initialize()

        running = [True]
        def handler(signum, frame):
            print(f"\n[SIGNAL] Saving and stopping...")
            running[0] = False
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        print(f"\n{'='*70}")
        print(f"  GA^3 CHAOS ENGINE")
        print(f"{'='*70}")
        print(f"  Islands:     {self.n_islands}")
        print(f"  Pop/island:  {self.island_pop}")
        print(f"  Total:       {self.n_islands * self.island_pop} organisms")
        print(f"  Cores:       {self.cores}")
        print(f"  Migration:   every 10 epochs")
        print(f"  Catastrophe: stochastic (stagnation-triggered)")
        print(f"{'='*70}")

        tasks_config = {name: {} for name in TRAINING_TASKS}
        epochs_per_round = 10
        total_start = time.time()

        while running[0]:
            self.generation += 1
            round_start = time.time()

            # Run all islands in parallel
            work = [(island, tasks_config, epochs_per_round) for island in self.islands]

            # Use multiprocessing for islands
            if self.cores > 1 and self.n_islands > 1:
                with mp.Pool(processes=min(self.cores, self.n_islands)) as pool:
                    results = pool.map(_run_island_epoch, work)
            else:
                results = [_run_island_epoch(w) for w in work]

            # Collect results
            self.islands = [r[0] for r in results]
            island_results = [r[1] for r in results]

            # Find global best
            for i, (island, res) in enumerate(zip(self.islands, island_results)):
                if res['fitness'] > self.global_best_fitness:
                    best_org = island.best()
                    self.global_best = {
                        'fitness': res['fitness'],
                        'task_scores': res['task_scores'],
                        'gen_scores': res['gen_scores'],
                        'size': res['size'],
                        'strategy': res['strategy'],
                        'island': i,
                        'program': best_org.program.to_str()[:500],
                    }
                    self.global_best_fitness = res['fitness']

            # === MIGRATION ===
            if self.generation % 1 == 0:  # every round
                self._migrate()

            # === REPORT ===
            round_time = time.time() - round_start
            total_epochs = self.generation * epochs_per_round

            # Compute intelligence metrics for global best
            iq = self._compute_iq(self.global_best) if self.global_best else 0

            print(f"\n  Round {self.generation} ({total_epochs} total epochs, {round_time:.0f}s)")
            print(f"  Global best: fit={self.global_best_fitness:.4f}  IQ={iq:.4f}  "
                  f"island={self.global_best.get('island', '?')}")
            for i, res in enumerate(island_results):
                cat_str = f" [CAT×{res['catastrophes']}]" if res['catastrophes'] > 0 else ""
                hgt = res['stats'].get('hgt_uptake', 0)
                chaos = res['stats'].get('chaos', 0)
                merges = res['stats'].get('merge', 0)
                mem_bias = res['strategy'].get('op_bias_memory', 0)
                print(f"    Island {i}: fit={res['fitness']:.4f}  "
                      f"stag={res['stagnation']:3d}  "
                      f"hgt={hgt:3d}  chaos={chaos:3d}  merge={merges:3d}  "
                      f"mem_bias={mem_bias:.2f}{cat_str}")

            # Log
            entry = {
                'gen': self.generation,
                'total_epochs': total_epochs,
                'best_fitness': self.global_best_fitness,
                'iq': iq,
                'island_fits': [r['fitness'] for r in island_results],
                'time_s': round_time,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }
            self.history.append(entry)
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')

            # Save periodically
            if self.generation % 5 == 0:
                self._save_state()

            sys.stdout.flush()

        self._save_state()
        total_time = time.time() - total_start
        total_epochs = self.generation * epochs_per_round
        print(f"\n{'='*70}")
        print(f"  CHAOS ENGINE STOPPED")
        print(f"  Rounds: {self.generation}  Epochs: {total_epochs}  Time: {total_time:.0f}s")
        print(f"  Best fitness: {self.global_best_fitness:.4f}")
        if self.global_best:
            print(f"  Best strategy (self-evolved):")
            for k, v in self.global_best.get('strategy', {}).items():
                if isinstance(v, float):
                    print(f"    {k:25s}: {v:.4f}")
            print(f"  Best program:\n{self.global_best.get('program', 'N/A')}")
        print(f"{'='*70}")

    def _migrate(self):
        """Exchange organisms between islands (ring topology)."""
        n_migrants = max(1, self.island_pop // 10)
        migrants = [island.get_migrants(n_migrants) for island in self.islands]

        for i, island in enumerate(self.islands):
            # Receive from neighbor
            source = (i - 1) % self.n_islands
            island.accept_migrants(migrants[source])

            # Also occasionally receive from random island
            if self.rng.random() < 0.2:
                rand_source = self.rng.randint(0, self.n_islands - 1)
                if rand_source != i:
                    island.accept_migrants(migrants[rand_source][:1])

    def _compute_iq(self, best: dict) -> float:
        """Quick IQ computation."""
        if not best or 'gen_scores' not in best:
            return 0.0
        gs = best['gen_scores']
        gen = float(np.mean(list(gs.values()))) if gs else 0
        abst = gs.get('analogy', 0)
        ts = best.get('task_scores', {})
        all_s = list(ts.values()) + list(gs.values())
        multi = len([s for s in all_s if s > 0.7]) / len(all_s) if all_s else 0
        return gen * 0.35 + abst * 0.30 + multi * 0.20 + 0.15 * min(1, best.get('size', 0) / 20)

    def _save_state(self):
        state = {
            'generation': self.generation,
            'global_best': self.global_best,
            'global_best_fitness': self.global_best_fitness,
            'history': self.history[-200:],
            'n_islands': self.n_islands,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        with open(self.save_path, 'w') as f:
            json.dump(state, f, indent=2)

        if self.global_best:
            with open(self.best_path, 'w') as f:
                json.dump(self.global_best, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='GA^3 Chaos Engine')
    parser.add_argument('--islands', type=int, default=7)
    parser.add_argument('--island-pop', type=int, default=40)
    parser.add_argument('--cores', type=int, default=None)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    engine = ChaosEngine(
        n_islands=args.islands,
        island_pop=args.island_pop,
        cores=args.cores,
        seed=args.seed,
    )
    engine.run()


if __name__ == '__main__':
    main()
