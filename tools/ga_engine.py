#!/usr/bin/env python3
"""General-Purpose GA Engine

A reusable genetic algorithm framework. Define a parameter schema and
fitness function, point the engine at it, and evolve.

Usage:
    # Python API
    from ga_engine import GAEngine, ParamSpec

    schema = [
        ParamSpec('learning_rate', 'float', 0.0001, 0.1),
        ParamSpec('batch_size', 'int', 8, 128),
        ParamSpec('optimizer', 'choice', choices=['adam', 'sgd', 'rmsprop']),
        ParamSpec('use_dropout', 'bool'),
    ]

    def fitness(params, seed):
        # evaluate params, return float 0-1
        return score

    engine = GAEngine(schema, fitness)
    best = engine.run(generations=50)
    print(best.params, best.fitness)

    # CLI (with JSON schema file)
    python3 ga_engine.py --schema schema.json --fitness my_module:my_fitness --generations 50

Features:
    - Declarative parameter schemas (float, int, choice, bool)
    - Multi-seed evaluation for robustness
    - Adaptive mutation rate (increases on stagnation)
    - Elitism + tournament selection
    - Convergence tracking
    - JSON import/export of schemas and results
    - Pluggable fitness functions (Python callables or module:function strings)
    - Per-parameter mutation bounds
    - Resume from previous population
"""

import argparse
import importlib
import json
import math
import os
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np


@dataclass
class ParamSpec:
    """Defines one evolvable parameter.

    Types:
        float: continuous in [low, high]
        int:   discrete integer in [low, high]
        choice: one of a fixed set of values
        bool:  True/False
    """
    name: str
    type: str  # 'float', 'int', 'choice', 'bool'
    low: Optional[float] = None
    high: Optional[float] = None
    choices: Optional[List[Any]] = None
    step: Optional[float] = None  # for int/float, mutation step size
    default: Optional[Any] = None

    def random_value(self, rng=None):
        r = rng or random
        if self.type == 'float':
            return round(r.uniform(self.low, self.high), 6)
        elif self.type == 'int':
            return r.randint(int(self.low), int(self.high))
        elif self.type == 'choice':
            return r.choice(self.choices)
        elif self.type == 'bool':
            return r.random() > 0.5
        raise ValueError(f"Unknown type: {self.type}")

    def mutate(self, value, rng=None):
        r = rng or random
        if self.type == 'float':
            step = self.step or (self.high - self.low) * 0.1
            new_val = value + r.gauss(0, step)
            return round(max(self.low, min(self.high, new_val)), 6)
        elif self.type == 'int':
            step = self.step or max(1, int((self.high - self.low) * 0.1))
            new_val = value + r.randint(-step, step)
            return max(int(self.low), min(int(self.high), new_val))
        elif self.type == 'choice':
            return r.choice(self.choices)
        elif self.type == 'bool':
            return not value
        return value

    def to_dict(self):
        d = {'name': self.name, 'type': self.type}
        if self.low is not None: d['low'] = self.low
        if self.high is not None: d['high'] = self.high
        if self.choices is not None: d['choices'] = self.choices
        if self.step is not None: d['step'] = self.step
        if self.default is not None: d['default'] = self.default
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> 'ParamSpec':
        return cls(**d)


@dataclass
class Individual:
    params: Dict[str, Any] = field(default_factory=dict)
    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        return {
            'params': self.params,
            'fitness': self.fitness,
            'fitness_details': self.fitness_details,
        }


class GAEngine:
    """General-purpose genetic algorithm engine.

    Args:
        schema: List of ParamSpec defining the search space
        fitness_fn: Callable(params_dict, seed) -> float or (float, dict)
        population_size: Number of individuals
        mutation_rate: Base mutation probability per gene
        eval_seeds: Seeds for multi-seed evaluation (robustness)
        seed: Random seed for reproducibility
        seeded_configs: Optional list of dicts to seed the initial population
    """

    def __init__(
        self,
        schema: List[ParamSpec],
        fitness_fn: Callable,
        population_size: int = 30,
        mutation_rate: float = 0.20,
        eval_seeds: Optional[List[int]] = None,
        seed: Optional[int] = None,
        seeded_configs: Optional[List[Dict]] = None,
    ):
        self.schema = schema
        self.fitness_fn = fitness_fn
        self.population_size = population_size
        self.base_mutation_rate = mutation_rate
        self.mutation_rate = mutation_rate
        self.eval_seeds = eval_seeds or [42, 123, 456]
        self.seeded_configs = seeded_configs or []
        self.convergence_history = []
        self.best_fitness = -float('inf')
        self.best_individual = None
        self.stagnation = 0

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def _random_individual(self) -> Individual:
        params = {}
        for spec in self.schema:
            params[spec.name] = spec.random_value()
        return Individual(params=params)

    def _seeded_individual(self, config: Dict) -> Individual:
        params = {}
        for spec in self.schema:
            if spec.name in config:
                params[spec.name] = config[spec.name]
            elif spec.default is not None:
                params[spec.name] = spec.default
            else:
                params[spec.name] = spec.random_value()
        return Individual(params=params)

    def evaluate(self, individual: Individual) -> float:
        scores = []
        details_list = []

        for s in self.eval_seeds:
            result = self.fitness_fn(individual.params, s)
            if isinstance(result, tuple):
                score, details = result
                scores.append(score)
                details_list.append(details)
            else:
                scores.append(result)

        fitness = float(np.mean(scores))
        individual.fitness = round(fitness, 6)

        if details_list:
            merged = {}
            for key in details_list[0]:
                vals = [d.get(key, 0) for d in details_list if isinstance(d.get(key), (int, float))]
                if vals:
                    merged[key] = round(float(np.mean(vals)), 4)
            individual.fitness_details = merged

        return fitness

    def crossover(self, p1: Individual, p2: Individual) -> Individual:
        params = {}
        for spec in self.schema:
            params[spec.name] = p1.params[spec.name] if random.random() < 0.5 else p2.params[spec.name]
        return Individual(params=params)

    def mutate(self, individual: Individual):
        for spec in self.schema:
            if random.random() < self.mutation_rate:
                individual.params[spec.name] = spec.mutate(individual.params[spec.name])

    def tournament_select(self, population: List[Individual], k: int = 4) -> Individual:
        candidates = random.sample(population, min(k, len(population)))
        return max(candidates, key=lambda c: c.fitness or -float('inf'))

    def run(self, generations: int = 50, verbose: bool = True) -> Individual:
        if verbose:
            print(f"GA Engine: {len(self.schema)} params, pop={self.population_size}, gens={generations}")

        # Initialize population
        population = []
        for cfg in self.seeded_configs:
            population.append(self._seeded_individual(cfg))
        while len(population) < self.population_size:
            population.append(self._random_individual())

        for ind in population:
            self.evaluate(ind)

        best_ever = max(population, key=lambda c: c.fitness or -float('inf'))
        self.best_fitness = best_ever.fitness
        self.best_individual = Individual(
            params=dict(best_ever.params),
            fitness=best_ever.fitness,
            fitness_details=best_ever.fitness_details,
        )

        if verbose:
            print(f"Gen  0: Best={best_ever.fitness:.6f}")

        for gen in range(1, generations + 1):
            # Adaptive mutation
            if self.stagnation > 6:
                self.mutation_rate = min(0.5, self.base_mutation_rate + 0.03 * self.stagnation)
            else:
                self.mutation_rate = self.base_mutation_rate

            population.sort(key=lambda c: c.fitness or -float('inf'), reverse=True)
            elite_size = max(2, self.population_size // 5)
            new_pop = list(population[:elite_size])

            while len(new_pop) < self.population_size:
                p1 = self.tournament_select(population)
                p2 = self.tournament_select(population)
                child = self.crossover(p1, p2)
                self.mutate(child)
                self.evaluate(child)
                new_pop.append(child)

            population = new_pop
            current_best = max(population, key=lambda c: c.fitness or -float('inf'))

            if (current_best.fitness or 0) > self.best_fitness:
                self.best_fitness = current_best.fitness
                self.best_individual = Individual(
                    params=dict(current_best.params),
                    fitness=current_best.fitness,
                    fitness_details=current_best.fitness_details,
                )
                self.stagnation = 0
                if verbose:
                    print(f"Gen {gen:3d}: NEW BEST={current_best.fitness:.6f}  {current_best.fitness_details or ''}")
            else:
                self.stagnation += 1
                if verbose and gen % 10 == 0:
                    avg = np.mean([c.fitness for c in population if c.fitness is not None])
                    print(f"Gen {gen:3d}: Best={self.best_fitness:.6f}  Avg={avg:.6f}  Stag={self.stagnation}")

            self.convergence_history.append({
                'generation': gen,
                'best': float(current_best.fitness or 0),
                'avg': float(np.mean([c.fitness for c in population if c.fitness is not None])),
            })

        if verbose:
            print(f"\nFinal: fitness={self.best_fitness:.6f}")
            print(f"Params: {json.dumps(self.best_individual.params, indent=2, default=str)}")

        return self.best_individual

    def save_results(self, path: str):
        with open(path, 'w') as f:
            json.dump({
                'best': self.best_individual.to_dict() if self.best_individual else None,
                'schema': [s.to_dict() for s in self.schema],
                'convergence': self.convergence_history,
                'config': {
                    'population_size': self.population_size,
                    'mutation_rate': self.base_mutation_rate,
                    'eval_seeds': self.eval_seeds,
                },
                'metadata': {'created_at': time.strftime('%Y-%m-%dT%H:%M:%S')},
            }, f, indent=2, default=str)

    @classmethod
    def from_schema_file(cls, schema_path: str, fitness_fn: Callable, **kwargs) -> 'GAEngine':
        with open(schema_path) as f:
            schema_data = json.load(f)
        schema = [ParamSpec.from_dict(s) for s in schema_data.get('params', schema_data)]
        seeded = schema_data.get('seeded_configs', [])
        return cls(schema, fitness_fn, seeded_configs=seeded, **kwargs)


def load_fitness_fn(spec: str) -> Callable:
    """Load a fitness function from a 'module:function' string."""
    if ':' not in spec:
        raise ValueError(f"Fitness spec must be 'module:function', got '{spec}'")
    mod_name, fn_name = spec.rsplit(':', 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, fn_name)


# --- Built-in fitness targets for common optimization tasks ---

def thompson_sampling_fitness(params: Dict, seed: int) -> Tuple[float, Dict]:
    """Fitness function for Thompson Sampling prior optimization.

    Evaluates how fast the bandit converges to the best arm given
    the evolved (alpha, beta) priors.
    """
    rng = np.random.RandomState(seed)
    n_arms = int(params.get('n_arms', 5))
    n_rounds = int(params.get('n_rounds', 200))

    true_means = rng.uniform(0.2, 0.9, n_arms)
    best_arm = np.argmax(true_means)

    alphas = [params.get(f'alpha_{i}', 1.0) for i in range(n_arms)]
    betas = [params.get(f'beta_{i}', 1.0) for i in range(n_arms)]

    correct = 0
    total_regret = 0.0

    for t in range(n_rounds):
        samples = [rng.beta(alphas[i], betas[i]) for i in range(n_arms)]
        chosen = int(np.argmax(samples))

        reward = 1 if rng.random() < true_means[chosen] else 0
        regret = true_means[best_arm] - true_means[chosen]
        total_regret += regret

        if chosen == best_arm:
            correct += 1

        if reward:
            alphas[chosen] += 1
        else:
            betas[chosen] += 1

    accuracy = correct / n_rounds
    normalized_regret = 1.0 - total_regret / (n_rounds * 0.7)

    fitness = accuracy * 0.5 + max(0, normalized_regret) * 0.5
    return fitness, {'accuracy': accuracy, 'regret': round(total_regret, 2)}


def retry_policy_fitness(params: Dict, seed: int) -> Tuple[float, Dict]:
    """Fitness function for retry policy optimization."""
    rng = np.random.RandomState(seed)
    n_calls = 200
    failure_rate = params.get('simulated_failure_rate', 0.15)

    successes = 0
    total_latency = 0.0
    total_attempts = 0

    max_retries = int(params.get('max_retries', 3))
    backoff_base = float(params.get('backoff_base', 1.0))
    backoff_mult = float(params.get('backoff_multiplier', 2.0))

    for _ in range(n_calls):
        for attempt in range(max_retries + 1):
            total_attempts += 1
            if rng.random() > failure_rate:
                successes += 1
                total_latency += rng.exponential(1.5)
                break
            else:
                delay = min(backoff_base * (backoff_mult ** attempt), 30)
                total_latency += delay + rng.uniform(0.1, 0.5)

    success_rate = successes / n_calls
    avg_latency = total_latency / n_calls
    efficiency = max(0, 1.0 - (total_attempts / n_calls - 1.0) / 5.0)

    fitness = success_rate * 0.5 + max(0, 1 - avg_latency / 20) * 0.25 + efficiency * 0.25
    return fitness, {'success_rate': round(success_rate, 4), 'avg_latency': round(avg_latency, 2)}


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description='General-Purpose GA Engine')
    parser.add_argument('--schema', type=str, help='JSON schema file path')
    parser.add_argument('--fitness', type=str, help='module:function for fitness')
    parser.add_argument('--builtin', type=str, choices=['thompson', 'retry'],
                       help='Use a built-in fitness target')
    parser.add_argument('--generations', type=int, default=50)
    parser.add_argument('--population', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=str, default=None)
    args = parser.parse_args()

    if args.builtin == 'thompson':
        schema = [
            ParamSpec('n_arms', 'int', 3, 10),
            ParamSpec('n_rounds', 'int', 50, 500),
        ] + [
            ParamSpec(f'alpha_{i}', 'float', 0.1, 10.0, step=0.5) for i in range(10)
        ] + [
            ParamSpec(f'beta_{i}', 'float', 0.1, 10.0, step=0.5) for i in range(10)
        ]
        fitness_fn = thompson_sampling_fitness
    elif args.builtin == 'retry':
        schema = [
            ParamSpec('max_retries', 'int', 1, 6),
            ParamSpec('backoff_base', 'float', 0.1, 5.0),
            ParamSpec('backoff_multiplier', 'float', 1.1, 4.0),
            ParamSpec('simulated_failure_rate', 'float', 0.05, 0.30),
        ]
        fitness_fn = retry_policy_fitness
    elif args.schema and args.fitness:
        fitness_fn = load_fitness_fn(args.fitness)
        engine = GAEngine.from_schema_file(
            args.schema, fitness_fn,
            population_size=args.population, seed=args.seed,
        )
        best = engine.run(generations=args.generations)
        if args.output:
            engine.save_results(args.output)
        return
    else:
        parser.error("Specify --builtin or both --schema and --fitness")
        return

    engine = GAEngine(
        schema, fitness_fn,
        population_size=args.population, seed=args.seed,
    )
    best = engine.run(generations=args.generations)

    output = args.output or f'ga_engine_results_{args.builtin}.json'
    engine.save_results(output)
    print(f"Results saved to: {output}")


if __name__ == '__main__':
    main()
