#!/usr/bin/env python3
"""Meta-GA: GA That Discovers Optimal GA Hyperparameters

An outer GA evolves the configuration of an inner GA. The inner GA
solves a benchmark problem; the outer GA's fitness is how well the
inner GA performs (fitness achieved, convergence speed, robustness).

Evolved hyperparameters:
    - population_size (10-100)
    - mutation_rate (0.01-0.50)
    - crossover_rate (0.3-1.0)
    - tournament_size (2-10)
    - elitism_ratio (0.0-0.4)
    - mutation_step_scale (0.05-0.5)
    - eval_seeds_count (1-5) - how many seeds to average over
    - stagnation_threshold (3-15) - when to boost mutation
    - adaptive_mutation_boost (0.01-0.10) - how much to boost per stagnation gen

The inner GA runs a configurable benchmark problem. Multiple benchmarks
available to prevent overfitting to one landscape.

Usage:
    python3 ga_meta_optimizer.py                     # defaults
    python3 ga_meta_optimizer.py --outer-gens 30     # more outer generations
    python3 ga_meta_optimizer.py --benchmark all     # test all benchmarks
"""

import argparse
import json
import math
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


# ---- Benchmark Problems (inner GA targets) ----

def rastrigin(x: List[float]) -> float:
    """Rastrigin function: many local minima, global minimum at origin.
    Classic test for GA's ability to escape local optima.
    Minimization → we negate for maximization fitness.
    """
    n = len(x)
    val = 10 * n + sum(xi**2 - 10 * math.cos(2 * math.pi * xi) for xi in x)
    return max(0, 1.0 - val / (10 * n + n * 25))  # normalize to 0-1


def rosenbrock(x: List[float]) -> float:
    """Rosenbrock function: narrow curved valley, global min at (1,1,...,1).
    Tests GA's ability to follow a gradient-like structure.
    """
    val = sum(100 * (x[i+1] - x[i]**2)**2 + (1 - x[i])**2 for i in range(len(x)-1))
    return max(0, 1.0 - val / (len(x) * 500))


def schwefel(x: List[float]) -> float:
    """Schwefel function: deceptive — global min far from next-best local min.
    Tests GA's exploration capability.
    """
    n = len(x)
    val = 418.9829 * n - sum(xi * math.sin(math.sqrt(abs(xi))) for xi in x)
    return max(0, 1.0 - val / (2 * 418.9829 * n))


def step_function(x: List[float]) -> float:
    """Step function: flat plateaus with sharp drops.
    Tests GA's ability to work without gradient signal.
    """
    val = sum(math.floor(abs(xi)) for xi in x)
    return max(0, 1.0 - val / (len(x) * 5))


BENCHMARKS = {
    'rastrigin': {'fn': rastrigin, 'dims': 5, 'range': (-5.12, 5.12)},
    'rosenbrock': {'fn': rosenbrock, 'dims': 5, 'range': (-5, 10)},
    'schwefel': {'fn': schwefel, 'dims': 5, 'range': (-500, 500)},
    'step': {'fn': step_function, 'dims': 5, 'range': (-5, 5)},
}


# ---- Inner GA (runs with evolved hyperparameters) ----

def run_inner_ga(
    hyperparams: Dict,
    benchmark_name: str,
    max_generations: int = 30,
    seed: int = 42,
) -> Dict:
    """Run an inner GA with the given hyperparameters on a benchmark.

    Returns metrics: best_fitness, convergence_speed, final_diversity.
    """
    rng = random.Random(seed)
    np_rng = np.random.RandomState(seed)

    bm = BENCHMARKS[benchmark_name]
    fn = bm['fn']
    dims = bm['dims']
    lo, hi = bm['range']

    pop_size = max(4, int(hyperparams.get('population_size', 30)))
    mut_rate = float(hyperparams.get('mutation_rate', 0.2))
    cross_rate = float(hyperparams.get('crossover_rate', 0.7))
    tourn_size = max(2, int(hyperparams.get('tournament_size', 4)))
    elitism = float(hyperparams.get('elitism_ratio', 0.1))
    mut_step = float(hyperparams.get('mutation_step_scale', 0.1))
    stag_thresh = max(1, int(hyperparams.get('stagnation_threshold', 6)))
    adapt_boost = float(hyperparams.get('adaptive_mutation_boost', 0.03))

    # Initialize population
    population = []
    for _ in range(pop_size):
        individual = [rng.uniform(lo, hi) for _ in range(dims)]
        population.append(individual)

    fitnesses = [fn(ind) for ind in population]
    best_fitness = max(fitnesses)
    best_gen = 0
    stagnation = 0
    current_mut_rate = mut_rate

    for gen in range(1, max_generations + 1):
        # Adaptive mutation
        if stagnation > stag_thresh:
            current_mut_rate = min(0.5, mut_rate + adapt_boost * stagnation)
        else:
            current_mut_rate = mut_rate

        # Elitism
        elite_count = max(1, int(pop_size * elitism))
        sorted_indices = sorted(range(pop_size), key=lambda i: fitnesses[i], reverse=True)
        new_pop = [list(population[i]) for i in sorted_indices[:elite_count]]

        # Breed
        while len(new_pop) < pop_size:
            # Tournament selection
            t1 = [rng.randint(0, pop_size-1) for _ in range(min(tourn_size, pop_size))]
            t2 = [rng.randint(0, pop_size-1) for _ in range(min(tourn_size, pop_size))]
            p1 = population[max(t1, key=lambda i: fitnesses[i])]
            p2 = population[max(t2, key=lambda i: fitnesses[i])]

            # Crossover
            child = list(p1)
            if rng.random() < cross_rate:
                point = rng.randint(1, dims - 1)
                child = p1[:point] + p2[point:]

            # Mutation
            for i in range(dims):
                if rng.random() < current_mut_rate:
                    delta = np_rng.normal(0, mut_step * (hi - lo))
                    child[i] = max(lo, min(hi, child[i] + delta))

            new_pop.append(child)

        population = new_pop[:pop_size]
        fitnesses = [fn(ind) for ind in population]
        gen_best = max(fitnesses)

        if gen_best > best_fitness:
            best_fitness = gen_best
            best_gen = gen
            stagnation = 0
        else:
            stagnation += 1

    # Diversity: average pairwise distance
    if pop_size > 1:
        sample_size = min(20, pop_size)
        sample_idx = rng.sample(range(pop_size), sample_size)
        distances = []
        for i in range(len(sample_idx)):
            for j in range(i+1, len(sample_idx)):
                a, b = population[sample_idx[i]], population[sample_idx[j]]
                d = math.sqrt(sum((a[k]-b[k])**2 for k in range(dims)))
                distances.append(d)
        diversity = np.mean(distances) / (hi - lo) if distances else 0
    else:
        diversity = 0

    convergence_speed = 1.0 - best_gen / max_generations if best_gen > 0 else 1.0

    return {
        'best_fitness': best_fitness,
        'convergence_speed': convergence_speed,
        'diversity': min(1.0, diversity),
        'best_gen': best_gen,
        'evaluations': pop_size * max_generations,
    }


# ---- Outer GA (evolves inner GA hyperparameters) ----

@dataclass
class MetaChromosome:
    hyperparams: Dict[str, Any] = field(default_factory=dict)
    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        return {
            'hyperparams': self.hyperparams,
            'fitness': self.fitness,
            'fitness_details': self.fitness_details,
        }


HYPERPARAM_RANGES = {
    'population_size': ('int', 10, 100),
    'mutation_rate': ('float', 0.01, 0.50),
    'crossover_rate': ('float', 0.3, 1.0),
    'tournament_size': ('int', 2, 10),
    'elitism_ratio': ('float', 0.0, 0.4),
    'mutation_step_scale': ('float', 0.02, 0.5),
    'stagnation_threshold': ('int', 2, 15),
    'adaptive_mutation_boost': ('float', 0.005, 0.10),
}


class MetaGA:
    """Outer GA that evolves inner GA hyperparameters."""

    def __init__(
        self,
        benchmarks: List[str] = None,
        inner_generations: int = 30,
        outer_population: int = 20,
        outer_mutation_rate: float = 0.25,
        seed: int = 42,
    ):
        self.benchmarks = benchmarks or ['rastrigin', 'rosenbrock', 'schwefel']
        self.inner_generations = inner_generations
        self.outer_population = outer_population
        self.outer_mutation_rate = outer_mutation_rate
        self.convergence_history = []
        self.best_fitness = 0.0
        self.best_chromosome = None
        self.stagnation = 0

        random.seed(seed)
        np.random.seed(seed)

    def random_hyperparams(self) -> Dict:
        hp = {}
        for name, (dtype, lo, hi) in HYPERPARAM_RANGES.items():
            if dtype == 'int':
                hp[name] = random.randint(lo, hi)
            else:
                hp[name] = round(random.uniform(lo, hi), 4)
        return hp

    def evaluate(self, chromosome: MetaChromosome) -> float:
        """Run inner GA on multiple benchmarks with multiple seeds.

        Fitness = mean(best_fitness * 0.5 + convergence * 0.3 + diversity * 0.2)
        across all benchmarks and seeds, penalized by evaluation cost.
        """
        scores = []
        per_benchmark = {}

        for bm_name in self.benchmarks:
            bm_scores = []
            for seed in [42, 123, 456]:
                result = run_inner_ga(
                    chromosome.hyperparams, bm_name,
                    max_generations=self.inner_generations, seed=seed,
                )
                score = (
                    result['best_fitness'] * 0.50 +
                    result['convergence_speed'] * 0.30 +
                    result['diversity'] * 0.20
                )
                # Penalize very large populations (evaluation cost)
                cost_penalty = max(0, (chromosome.hyperparams.get('population_size', 30) - 50) * 0.002)
                score = max(0, score - cost_penalty)
                bm_scores.append(score)

            per_benchmark[bm_name] = round(float(np.mean(bm_scores)), 4)
            scores.extend(bm_scores)

        fitness = float(np.mean(scores))
        chromosome.fitness = round(fitness, 6)
        chromosome.fitness_details = per_benchmark
        return fitness

    def crossover(self, p1: MetaChromosome, p2: MetaChromosome) -> MetaChromosome:
        hp = {}
        for name in HYPERPARAM_RANGES:
            hp[name] = p1.hyperparams[name] if random.random() < 0.5 else p2.hyperparams[name]
        return MetaChromosome(hyperparams=hp)

    def mutate(self, chromosome: MetaChromosome):
        for name, (dtype, lo, hi) in HYPERPARAM_RANGES.items():
            if random.random() < self.outer_mutation_rate:
                if dtype == 'int':
                    step = max(1, int((hi - lo) * 0.15))
                    new_val = chromosome.hyperparams[name] + random.randint(-step, step)
                    chromosome.hyperparams[name] = max(lo, min(hi, new_val))
                else:
                    step = (hi - lo) * 0.15
                    new_val = chromosome.hyperparams[name] + random.gauss(0, step)
                    chromosome.hyperparams[name] = round(max(lo, min(hi, new_val)), 4)

    def tournament_select(self, population):
        candidates = random.sample(population, min(4, len(population)))
        return max(candidates, key=lambda c: c.fitness or 0)

    def run(self, outer_generations: int = 20) -> MetaChromosome:
        print("=" * 70)
        print("  META-GA: Evolving GA Hyperparameters")
        print("=" * 70)
        print(f"  Outer: pop={self.outer_population}, gens={outer_generations}")
        print(f"  Inner: gens={self.inner_generations}, benchmarks={self.benchmarks}")
        print(f"  Hyperparams: {len(HYPERPARAM_RANGES)}")
        print("=" * 70)

        # Seed with standard configs
        population = [
            MetaChromosome(hyperparams={
                'population_size': 30, 'mutation_rate': 0.20,
                'crossover_rate': 0.70, 'tournament_size': 4,
                'elitism_ratio': 0.10, 'mutation_step_scale': 0.10,
                'stagnation_threshold': 6, 'adaptive_mutation_boost': 0.03,
            }),
            MetaChromosome(hyperparams={
                'population_size': 50, 'mutation_rate': 0.10,
                'crossover_rate': 0.90, 'tournament_size': 3,
                'elitism_ratio': 0.20, 'mutation_step_scale': 0.05,
                'stagnation_threshold': 10, 'adaptive_mutation_boost': 0.02,
            }),
        ]
        while len(population) < self.outer_population:
            population.append(MetaChromosome(hyperparams=self.random_hyperparams()))

        for c in population:
            self.evaluate(c)

        best_ever = max(population, key=lambda c: c.fitness or 0)
        self.best_fitness = best_ever.fitness
        self.best_chromosome = best_ever

        print(f"Gen  0: Best={best_ever.fitness:.6f}  {best_ever.fitness_details}")

        for gen in range(1, outer_generations + 1):
            if self.stagnation > 4:
                self.outer_mutation_rate = min(0.5, 0.25 + 0.04 * self.stagnation)
            else:
                self.outer_mutation_rate = 0.25

            population.sort(key=lambda c: c.fitness or 0, reverse=True)
            elite_size = max(2, self.outer_population // 5)
            new_pop = list(population[:elite_size])

            while len(new_pop) < self.outer_population:
                p1 = self.tournament_select(population)
                p2 = self.tournament_select(population)
                child = self.crossover(p1, p2)
                self.mutate(child)
                self.evaluate(child)
                new_pop.append(child)

            population = new_pop
            current_best = max(population, key=lambda c: c.fitness or 0)

            if (current_best.fitness or 0) > self.best_fitness:
                self.best_fitness = current_best.fitness
                self.best_chromosome = current_best
                self.stagnation = 0
                print(f"Gen {gen:2d}: NEW BEST={current_best.fitness:.6f}  {current_best.fitness_details}")
            else:
                self.stagnation += 1
                if gen % 5 == 0:
                    avg = np.mean([c.fitness for c in population if c.fitness])
                    print(f"Gen {gen:2d}: Best={self.best_fitness:.6f}  Avg={avg:.6f}  Stag={self.stagnation}")

            self.convergence_history.append({
                'generation': gen,
                'best': float(current_best.fitness or 0),
                'avg': float(np.mean([c.fitness for c in population if c.fitness])),
            })

        self._print_report()
        self._store_results()
        return self.best_chromosome

    def _print_report(self):
        best = self.best_chromosome
        if not best:
            return

        print("\n" + "=" * 70)
        print("  EVOLVED GA HYPERPARAMETERS")
        print("=" * 70)
        print(f"  Meta-Fitness: {best.fitness:.6f}")

        if best.fitness_details:
            print("\n  Per-benchmark scores:")
            for bm, score in best.fitness_details.items():
                print(f"    {bm:20s}: {score:.4f}")

        print("\n  Optimal GA configuration:")
        for name, val in best.hyperparams.items():
            default = {
                'population_size': 30, 'mutation_rate': 0.20,
                'crossover_rate': 0.70, 'tournament_size': 4,
                'elitism_ratio': 0.10, 'mutation_step_scale': 0.10,
                'stagnation_threshold': 6, 'adaptive_mutation_boost': 0.03,
            }.get(name)
            diff = ""
            if default is not None and isinstance(val, (int, float)):
                pct = ((val - default) / max(abs(default), 0.001)) * 100
                diff = f"  ({pct:+.0f}% vs default)"
            print(f"    {name:30s}: {val}{diff}")

        print("=" * 70)

    def _store_results(self):
        best = self.best_chromosome
        if not best:
            return

        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, 'best_ga_hyperparams.json')

        with open(output_path, 'w') as f:
            json.dump({
                'hyperparams': best.hyperparams,
                'fitness': best.fitness,
                'fitness_details': best.fitness_details,
                'convergence': self.convergence_history,
                'benchmarks': self.benchmarks,
                'metadata': {'created_at': time.strftime('%Y-%m-%dT%H:%M:%S')},
            }, f, indent=2)
        print(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Meta-GA: GA discovers optimal GA')
    parser.add_argument('--outer-gens', type=int, default=20)
    parser.add_argument('--inner-gens', type=int, default=30)
    parser.add_argument('--outer-pop', type=int, default=20)
    parser.add_argument('--benchmark', type=str, default='rastrigin,rosenbrock,schwefel',
                       help='Comma-separated benchmarks or "all"')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    if args.benchmark == 'all':
        benchmarks = list(BENCHMARKS.keys())
    else:
        benchmarks = [b.strip() for b in args.benchmark.split(',')]

    meta = MetaGA(
        benchmarks=benchmarks,
        inner_generations=args.inner_gens,
        outer_population=args.outer_pop,
        seed=args.seed,
    )
    meta.run(outer_generations=args.outer_gens)


if __name__ == '__main__':
    main()
