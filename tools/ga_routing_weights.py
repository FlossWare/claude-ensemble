#!/usr/bin/env python3
"""GA Routing Weight Optimizer

Evolves optimal Thompson Sampling priors (alpha, beta) for model routing
across different task types. Instead of starting from uninformative
Beta(1,1) priors, the GA discovers priors that encode domain knowledge
about which models excel at which tasks.

The chromosome encodes alpha/beta pairs for each (model, task_type) combination.
Fitness measures how quickly the evolved priors converge to optimal model
selection compared to uniform priors.

Usage:
    python3 ga_routing_weights.py                    # 50 generations
    python3 ga_routing_weights.py --generations 200
"""

import argparse
import json
import math
import os
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')

TASK_TYPES = [
    'code_review', 'bug_fix', 'research', 'summarization',
    'code_generation', 'analysis', 'creative_writing', 'reasoning',
]

MODELS = [
    'opus', 'sonnet', 'haiku', 'fable',
    'deepseek-chat', 'llama-3.3-70b',
    'qwen3-235b', 'mistral-small-3.1',
    'gemini-2.5-flash', 'nemotron-70b',
]

# Ground truth: simulated quality scores per (model, task)
# These represent what the routing system should converge to
GROUND_TRUTH_QUALITY = {}
_gt_seed = np.random.RandomState(12345)
for model in MODELS:
    for task in TASK_TYPES:
        base = {
            'opus': 0.92, 'sonnet': 0.88, 'fable': 0.90, 'haiku': 0.75,
            'deepseek-chat': 0.84, 'llama-3.3-70b': 0.82,
            'qwen3-235b': 0.86, 'mistral-small-3.1': 0.78,
            'gemini-2.5-flash': 0.80, 'nemotron-70b': 0.81,
        }.get(model, 0.75)

        task_affinity = {
            'code_review': {'opus': 0.08, 'fable': 0.06, 'deepseek-chat': 0.07, 'qwen3-235b': 0.05},
            'bug_fix': {'opus': 0.07, 'sonnet': 0.06, 'deepseek-chat': 0.08},
            'research': {'fable': 0.08, 'gemini-2.5-flash': 0.09, 'opus': 0.05},
            'summarization': {'haiku': 0.10, 'sonnet': 0.06, 'gemini-2.5-flash': 0.07},
            'code_generation': {'deepseek-chat': 0.09, 'qwen3-235b': 0.08, 'opus': 0.05},
            'analysis': {'opus': 0.07, 'fable': 0.06, 'sonnet': 0.05},
            'creative_writing': {'fable': 0.10, 'opus': 0.06, 'nemotron-70b': 0.05},
            'reasoning': {'opus': 0.09, 'qwen3-235b': 0.07, 'deepseek-chat': 0.06},
        }

        affinity = task_affinity.get(task, {}).get(model, 0.0)
        noise = _gt_seed.normal(0, 0.02)
        GROUND_TRUTH_QUALITY[(model, task)] = min(1.0, max(0.1, base + affinity + noise))


@dataclass
class RoutingChromosome:
    # priors[model][task] = (alpha, beta)
    priors: Dict[str, Dict[str, Tuple[float, float]]] = field(default_factory=dict)
    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        return {m: {t: list(ab) for t, ab in tasks.items()} for m, tasks in self.priors.items()}


class ThompsonSimulator:
    """Simulates Thompson Sampling model selection over N rounds."""

    def __init__(self, rounds=100, noise_std=0.08):
        self.rounds = rounds
        self.noise_std = noise_std

    def simulate(self, priors: Dict, seed=42) -> Dict:
        """
        Run Thompson Sampling with given priors and measure:
        1. Cumulative regret (lower = better priors)
        2. Convergence speed (rounds to find best model per task)
        3. Selection accuracy in final 20 rounds
        """
        rng = np.random.RandomState(seed)
        total_regret = 0.0
        convergence_rounds = {}
        final_accuracy = {task: 0 for task in TASK_TYPES}
        final_count = {task: 0 for task in TASK_TYPES}

        # Initialize bandit state from priors
        state = {}
        for model in MODELS:
            state[model] = {}
            for task in TASK_TYPES:
                a, b = priors.get(model, {}).get(task, (1.0, 1.0))
                state[model][task] = {'alpha': a, 'beta': b}

        # Find optimal model per task
        optimal = {}
        for task in TASK_TYPES:
            best_model = max(MODELS, key=lambda m: GROUND_TRUTH_QUALITY.get((m, task), 0.5))
            optimal[task] = (best_model, GROUND_TRUTH_QUALITY[(best_model, task)])

        for round_num in range(self.rounds):
            task = TASK_TYPES[round_num % len(TASK_TYPES)]

            # Thompson Sampling: draw from Beta posteriors
            samples = {}
            for model in MODELS:
                s = state[model][task]
                samples[model] = rng.beta(s['alpha'], s['beta'])

            selected = max(samples, key=samples.get)

            # Get reward (noisy observation of true quality)
            true_q = GROUND_TRUTH_QUALITY.get((selected, task), 0.5)
            reward = min(1.0, max(0.0, true_q + rng.normal(0, self.noise_std)))
            success = reward > 0.5

            # Update posterior
            if success:
                state[selected][task]['alpha'] += 1
            else:
                state[selected][task]['beta'] += 1

            # Regret: difference from optimal
            opt_q = optimal[task][1]
            regret = opt_q - true_q
            total_regret += max(0, regret)

            # Track convergence
            if task not in convergence_rounds and selected == optimal[task][0]:
                convergence_rounds[task] = round_num

            # Final accuracy (last 20 rounds)
            if round_num >= self.rounds - 20:
                final_count[task] += 1
                if selected == optimal[task][0]:
                    final_accuracy[task] += 1

        avg_convergence = np.mean(list(convergence_rounds.values())) if convergence_rounds else self.rounds
        tasks_converged = len(convergence_rounds)

        acc_scores = []
        for task in TASK_TYPES:
            if final_count[task] > 0:
                acc_scores.append(final_accuracy[task] / final_count[task])
        avg_final_accuracy = np.mean(acc_scores) if acc_scores else 0.0

        return {
            'total_regret': total_regret,
            'avg_convergence': avg_convergence,
            'tasks_converged': tasks_converged,
            'avg_final_accuracy': avg_final_accuracy,
        }


class RoutingGA:
    def __init__(self, population_size=30, mutation_rate=0.20, seed=None):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.simulator = ThompsonSimulator(rounds=200)
        self.convergence_history = []
        self.best_fitness = 0.0
        self.best_chromosome = None
        self.stagnation = 0

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def create_random(self) -> RoutingChromosome:
        priors = {}
        for model in MODELS:
            priors[model] = {}
            for task in TASK_TYPES:
                alpha = round(random.uniform(0.5, 10.0), 2)
                beta = round(random.uniform(0.5, 10.0), 2)
                priors[model][task] = (alpha, beta)
        return RoutingChromosome(priors=priors)

    def create_seeded(self) -> List[RoutingChromosome]:
        seeds = []

        # Seed 1: Uniform uninformative Beta(1,1)
        p1 = {}
        for model in MODELS:
            p1[model] = {task: (1.0, 1.0) for task in TASK_TYPES}
        seeds.append(RoutingChromosome(priors=p1))

        # Seed 2: Quality-biased (higher alpha for known-good models)
        p2 = {}
        base_alpha = {'opus': 8, 'fable': 7, 'sonnet': 6, 'deepseek-chat': 5,
                     'qwen3-235b': 5, 'llama-3.3-70b': 4, 'nemotron-70b': 4,
                     'gemini-2.5-flash': 4, 'mistral-small-3.1': 3, 'haiku': 3}
        for model in MODELS:
            p2[model] = {}
            for task in TASK_TYPES:
                a = base_alpha.get(model, 3)
                p2[model][task] = (float(a), 2.0)
        seeds.append(RoutingChromosome(priors=p2))

        # Seed 3: Task-specialized (biases toward known task affinities)
        p3 = {}
        specializations = {
            'code_review': ['opus', 'deepseek-chat'],
            'bug_fix': ['deepseek-chat', 'opus'],
            'research': ['fable', 'gemini-2.5-flash'],
            'summarization': ['haiku', 'sonnet'],
            'code_generation': ['deepseek-chat', 'qwen3-235b'],
            'analysis': ['opus', 'fable'],
            'creative_writing': ['fable', 'opus'],
            'reasoning': ['opus', 'qwen3-235b'],
        }
        for model in MODELS:
            p3[model] = {}
            for task in TASK_TYPES:
                if model in specializations.get(task, []):
                    p3[model][task] = (8.0, 2.0)
                else:
                    p3[model][task] = (2.0, 3.0)
        seeds.append(RoutingChromosome(priors=p3))

        return seeds

    def calculate_fitness(self, chromosome: RoutingChromosome) -> float:
        """
        Fitness = convergence_speed * 0.35 + final_accuracy * 0.30
                + low_regret * 0.25 + coverage * 0.10

        Evaluated across 5 seeds for robustness.
        """
        results = []
        for s in [42, 123, 456, 789, 1011]:
            r = self.simulator.simulate(chromosome.priors, seed=s)
            results.append(r)

        avg_regret = np.mean([r['total_regret'] for r in results])
        avg_convergence = np.mean([r['avg_convergence'] for r in results])
        avg_accuracy = np.mean([r['avg_final_accuracy'] for r in results])
        avg_coverage = np.mean([r['tasks_converged'] for r in results])

        # Normalize
        regret_score = max(0, 1.0 - avg_regret / 20.0)  # lower regret = better
        convergence_score = max(0, 1.0 - avg_convergence / 200.0)  # faster = better
        accuracy_score = avg_accuracy  # higher = better
        coverage_score = avg_coverage / len(TASK_TYPES)  # fraction converged

        fitness = (
            convergence_score * 0.35 +
            accuracy_score * 0.30 +
            regret_score * 0.25 +
            coverage_score * 0.10
        )

        chromosome.fitness = round(fitness, 5)
        chromosome.fitness_details = {
            'convergence': round(convergence_score, 4),
            'accuracy': round(accuracy_score, 4),
            'regret': round(regret_score, 4),
            'coverage': round(coverage_score, 4),
            'raw_regret': round(avg_regret, 3),
            'raw_convergence': round(avg_convergence, 1),
        }
        return fitness

    def crossover(self, p1: RoutingChromosome, p2: RoutingChromosome) -> RoutingChromosome:
        priors = {}
        for model in MODELS:
            priors[model] = {}
            for task in TASK_TYPES:
                if random.random() < 0.5:
                    priors[model][task] = p1.priors[model][task]
                else:
                    priors[model][task] = p2.priors[model][task]
        return RoutingChromosome(priors=priors)

    def mutate(self, chromosome: RoutingChromosome):
        for model in MODELS:
            for task in TASK_TYPES:
                if random.random() < self.mutation_rate / (len(MODELS) * len(TASK_TYPES) / 4):
                    a, b = chromosome.priors[model][task]
                    gene = random.choice(['alpha', 'beta', 'swap', 'reset'])
                    if gene == 'alpha':
                        a = max(0.5, a + random.gauss(0, 1.5))
                    elif gene == 'beta':
                        b = max(0.5, b + random.gauss(0, 1.5))
                    elif gene == 'swap':
                        a, b = b, a
                    elif gene == 'reset':
                        a = round(random.uniform(0.5, 10.0), 2)
                        b = round(random.uniform(0.5, 10.0), 2)
                    chromosome.priors[model][task] = (round(a, 2), round(b, 2))

    def tournament_select(self, population):
        candidates = random.sample(population, min(4, len(population)))
        return max(candidates, key=lambda c: c.fitness or 0)

    def run(self, generations=50):
        print("=" * 70)
        print("  GA Routing Weight Optimizer")
        print("=" * 70)
        print(f"Models: {len(MODELS)}, Task types: {len(TASK_TYPES)}")
        print(f"Genes: {len(MODELS) * len(TASK_TYPES) * 2} (alpha+beta per model/task)")
        print(f"Thompson Sampling rounds per eval: {self.simulator.rounds}")
        print("=" * 70)

        population = self.create_seeded()
        while len(population) < self.population_size:
            population.append(self.create_random())

        for c in population:
            c.fitness = self.calculate_fitness(c)

        best_ever = max(population, key=lambda c: c.fitness or 0)
        self.best_fitness = best_ever.fitness or 0
        self.best_chromosome = best_ever

        print(f"Gen  0: Best={best_ever.fitness:.5f}  {best_ever.fitness_details}")

        for gen in range(1, generations + 1):
            if self.stagnation > 8:
                self.mutation_rate = min(0.5, 0.20 + 0.02 * self.stagnation)
            else:
                self.mutation_rate = 0.20

            population.sort(key=lambda c: c.fitness or 0, reverse=True)
            elite_size = max(2, self.population_size // 5)
            new_pop = list(population[:elite_size])

            while len(new_pop) < self.population_size:
                p1 = self.tournament_select(population)
                p2 = self.tournament_select(population)
                child = self.crossover(p1, p2)
                self.mutate(child)
                child.fitness = self.calculate_fitness(child)
                new_pop.append(child)
            population = new_pop

            current_best = max(population, key=lambda c: c.fitness or 0)
            if (current_best.fitness or 0) > self.best_fitness:
                self.best_fitness = current_best.fitness
                self.best_chromosome = current_best
                self.stagnation = 0
                d = current_best.fitness_details
                print(f"Gen {gen:2d}: NEW BEST={current_best.fitness:.5f}  "
                      f"Conv={d['convergence']:.3f} Acc={d['accuracy']:.3f} "
                      f"Reg={d['regret']:.3f} Cov={d['coverage']:.3f}")
            else:
                self.stagnation += 1
                if gen % 10 == 0:
                    avg = np.mean([c.fitness for c in population if c.fitness])
                    print(f"Gen {gen:2d}: Best={current_best.fitness:.5f}  "
                          f"Avg={avg:.5f}  Stag={self.stagnation}")

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
        print("  BEST ROUTING PRIORS")
        print("=" * 70)
        print(f"  Overall Fitness: {best.fitness:.5f}")
        if best.fitness_details:
            for k, v in best.fitness_details.items():
                print(f"    {k:20s}: {v}")

        print(f"\n  Top models per task (by alpha/(alpha+beta) = prior mean):")
        for task in TASK_TYPES:
            rankings = []
            for model in MODELS:
                a, b = best.priors[model][task]
                prior_mean = a / (a + b)
                rankings.append((model, prior_mean, a, b))
            rankings.sort(key=lambda x: x[1], reverse=True)
            top3 = rankings[:3]
            line = ", ".join(f"{m}={pm:.2f}(a={a:.1f},b={b:.1f})" for m, pm, a, b in top3)
            print(f"    {task:20s}: {line}")

        # Compare vs uniform priors
        print("\n  Comparison vs uniform Beta(1,1) priors:")
        uniform = {m: {t: (1.0, 1.0) for t in TASK_TYPES} for m in MODELS}
        uniform_results = []
        for s in [42, 123, 456, 789, 1011]:
            r = self.simulator.simulate(uniform, seed=s)
            uniform_results.append(r)

        evolved_results = []
        for s in [42, 123, 456, 789, 1011]:
            r = self.simulator.simulate(best.priors, seed=s)
            evolved_results.append(r)

        u_regret = np.mean([r['total_regret'] for r in uniform_results])
        e_regret = np.mean([r['total_regret'] for r in evolved_results])
        u_conv = np.mean([r['avg_convergence'] for r in uniform_results])
        e_conv = np.mean([r['avg_convergence'] for r in evolved_results])
        u_acc = np.mean([r['avg_final_accuracy'] for r in uniform_results])
        e_acc = np.mean([r['avg_final_accuracy'] for r in evolved_results])

        print(f"    Regret:      Uniform={u_regret:.3f}  Evolved={e_regret:.3f}  "
              f"({(1-e_regret/u_regret)*100:+.1f}%)")
        print(f"    Convergence: Uniform={u_conv:.1f}  Evolved={e_conv:.1f}  "
              f"({(1-e_conv/u_conv)*100:+.1f}% faster)")
        print(f"    Accuracy:    Uniform={u_acc:.3f}  Evolved={e_acc:.3f}  "
              f"({(e_acc/u_acc-1)*100:+.1f}%)")

        print("=" * 70)

    def _store_results(self):
        best = self.best_chromosome
        if not best:
            return

        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, 'best_routing_weights.json')

        with open(output_path, 'w') as f:
            json.dump({
                'priors': best.to_dict(),
                'fitness': best.fitness,
                'fitness_details': best.fitness_details,
                'metadata': {'created_at': time.strftime('%Y-%m-%dT%H:%M:%S')},
            }, f, indent=2)
        print(f"\nPriors saved to: {output_path}")

        try:
            requests.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': 'routing-weights',
                'chromosome': json.dumps(best.to_dict()),
                'fitness': float(best.fitness or 0),
                'fitness_details': json.dumps(best.fitness_details or {}),
                'generation_found': len(self.convergence_history),
            }, timeout=5)
            print("Stored in ga.best_solutions via REST API")
        except Exception:
            print("API unavailable — stored locally only")


def main():
    parser = argparse.ArgumentParser(description='GA Routing Weight Optimizer')
    parser.add_argument('--generations', type=int, default=50)
    parser.add_argument('--population', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    ga = RoutingGA(population_size=args.population, seed=args.seed)
    ga.run(generations=args.generations)


if __name__ == '__main__':
    main()
