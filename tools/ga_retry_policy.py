#!/usr/bin/env python3
"""GA Retry Policy Optimizer

Evolves optimal retry configurations per API provider. Parameters include
max retries, backoff base/multiplier, jitter range, timeout per attempt,
circuit breaker threshold, and cooldown period.

Fitness balances success rate, latency overhead, and resource efficiency
against a simulated API failure model (transient errors, rate limits,
server overload, network timeouts).

Usage:
    python3 ga_retry_policy.py                    # 50 generations
    python3 ga_retry_policy.py --generations 200
"""

import argparse
import json
import math
import os
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')

PROVIDERS = [
    'openrouter', 'anthropic', 'google', 'groq',
    'cerebras', 'deepseek', 'openai', 'mistral',
]

# Simulated failure profiles per provider
FAILURE_PROFILES = {
    'openrouter': {'transient_rate': 0.08, 'rate_limit_rate': 0.12, 'overload_rate': 0.05, 'timeout_rate': 0.03},
    'anthropic':  {'transient_rate': 0.03, 'rate_limit_rate': 0.05, 'overload_rate': 0.02, 'timeout_rate': 0.01},
    'google':     {'transient_rate': 0.04, 'rate_limit_rate': 0.08, 'overload_rate': 0.03, 'timeout_rate': 0.02},
    'groq':       {'transient_rate': 0.06, 'rate_limit_rate': 0.15, 'overload_rate': 0.08, 'timeout_rate': 0.02},
    'cerebras':   {'transient_rate': 0.10, 'rate_limit_rate': 0.10, 'overload_rate': 0.06, 'timeout_rate': 0.04},
    'deepseek':   {'transient_rate': 0.07, 'rate_limit_rate': 0.09, 'overload_rate': 0.04, 'timeout_rate': 0.05},
    'openai':     {'transient_rate': 0.03, 'rate_limit_rate': 0.06, 'overload_rate': 0.02, 'timeout_rate': 0.01},
    'mistral':    {'transient_rate': 0.05, 'rate_limit_rate': 0.07, 'overload_rate': 0.04, 'timeout_rate': 0.03},
}


@dataclass
class RetryConfig:
    provider: str = 'openrouter'
    max_retries: int = 3
    backoff_base: float = 1.0       # seconds
    backoff_multiplier: float = 2.0  # exponential factor
    backoff_max: float = 30.0       # cap
    jitter_fraction: float = 0.2    # 0-1, fraction of delay added as jitter
    timeout_per_attempt: float = 30.0  # seconds
    circuit_breaker_threshold: int = 5  # consecutive failures to open
    circuit_breaker_cooldown: float = 60.0  # seconds before half-open
    rate_limit_backoff: float = 5.0  # extra delay on 429
    adaptive_timeout: bool = True    # increase timeout on slow responses


@dataclass
class RetryChromosome:
    configs: Dict[str, RetryConfig] = field(default_factory=dict)
    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        return {name: asdict(cfg) for name, cfg in self.configs.items()}


class APISimulator:
    """Simulates API call patterns with realistic failure modes."""

    def __init__(self, num_calls=200, seed=42):
        self.num_calls = num_calls
        self.seed = seed

    def simulate(self, config: RetryConfig, seed=None) -> Dict:
        rng = np.random.RandomState(seed or self.seed)
        profile = FAILURE_PROFILES.get(config.provider, FAILURE_PROFILES['openrouter'])

        successful_calls = 0
        total_latency = 0.0
        total_attempts = 0
        circuit_open_time = 0.0
        consecutive_failures = 0
        circuit_open = False
        wasted_retries = 0

        for call_num in range(self.num_calls):
            if circuit_open:
                circuit_open_time += config.circuit_breaker_cooldown
                circuit_open = False
                consecutive_failures = 0

            call_succeeded = False
            call_latency = 0.0

            for attempt in range(config.max_retries + 1):
                total_attempts += 1

                # Determine failure type
                r = rng.random()
                failure_type = None
                cumulative = 0
                for ftype, frate in profile.items():
                    cumulative += frate
                    if r < cumulative:
                        failure_type = ftype.replace('_rate', '')
                        break

                if failure_type is None:
                    # Success
                    base_latency = rng.exponential(2.0)
                    call_latency += min(base_latency, config.timeout_per_attempt)
                    call_succeeded = True
                    consecutive_failures = 0
                    break
                else:
                    # Failure — add attempt latency
                    if failure_type == 'timeout':
                        call_latency += config.timeout_per_attempt
                    elif failure_type == 'rate_limit':
                        call_latency += config.rate_limit_backoff
                    else:
                        call_latency += rng.uniform(0.1, 1.0)

                    consecutive_failures += 1

                    if consecutive_failures >= config.circuit_breaker_threshold:
                        circuit_open = True
                        wasted_retries += config.max_retries - attempt
                        break

                    # Backoff before retry
                    if attempt < config.max_retries:
                        delay = min(
                            config.backoff_base * (config.backoff_multiplier ** attempt),
                            config.backoff_max
                        )
                        jitter = delay * config.jitter_fraction * rng.random()
                        call_latency += delay + jitter

            if call_succeeded:
                successful_calls += 1

            total_latency += call_latency

        success_rate = successful_calls / self.num_calls
        avg_latency = total_latency / self.num_calls
        attempts_per_call = total_attempts / self.num_calls
        circuit_downtime = circuit_open_time / (total_latency + circuit_open_time + 1e-9)

        return {
            'success_rate': success_rate,
            'avg_latency': avg_latency,
            'attempts_per_call': attempts_per_call,
            'circuit_downtime': circuit_downtime,
            'wasted_retries': wasted_retries,
        }


class RetryGA:
    def __init__(self, population_size=30, mutation_rate=0.20, seed=None):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.simulator = APISimulator(num_calls=300)
        self.convergence_history = []
        self.best_fitness = 0.0
        self.best_chromosome = None
        self.stagnation = 0

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def create_random(self) -> RetryChromosome:
        configs = {}
        for provider in PROVIDERS:
            configs[provider] = RetryConfig(
                provider=provider,
                max_retries=random.randint(1, 6),
                backoff_base=round(random.uniform(0.3, 3.0), 2),
                backoff_multiplier=round(random.uniform(1.2, 4.0), 1),
                backoff_max=round(random.uniform(10, 60), 0),
                jitter_fraction=round(random.uniform(0.0, 0.5), 2),
                timeout_per_attempt=round(random.uniform(10, 60), 0),
                circuit_breaker_threshold=random.randint(3, 10),
                circuit_breaker_cooldown=round(random.uniform(20, 120), 0),
                rate_limit_backoff=round(random.uniform(1, 15), 1),
                adaptive_timeout=random.random() > 0.4,
            )
        return RetryChromosome(configs=configs)

    def create_seeded(self) -> List[RetryChromosome]:
        seeds = []

        # Seed 1: Conservative (many retries, long backoff)
        c1 = {}
        for p in PROVIDERS:
            c1[p] = RetryConfig(provider=p, max_retries=5, backoff_base=2.0,
                               backoff_multiplier=3.0, backoff_max=45, jitter_fraction=0.3,
                               timeout_per_attempt=45, circuit_breaker_threshold=8,
                               circuit_breaker_cooldown=90, rate_limit_backoff=10, adaptive_timeout=True)
        seeds.append(RetryChromosome(configs=c1))

        # Seed 2: Aggressive (few retries, fast fail)
        c2 = {}
        for p in PROVIDERS:
            c2[p] = RetryConfig(provider=p, max_retries=2, backoff_base=0.5,
                               backoff_multiplier=1.5, backoff_max=10, jitter_fraction=0.1,
                               timeout_per_attempt=15, circuit_breaker_threshold=3,
                               circuit_breaker_cooldown=30, rate_limit_backoff=3, adaptive_timeout=False)
        seeds.append(RetryChromosome(configs=c2))

        # Seed 3: Standard (the typical 3-retry with exponential backoff)
        c3 = {}
        for p in PROVIDERS:
            c3[p] = RetryConfig(provider=p, max_retries=3, backoff_base=1.0,
                               backoff_multiplier=2.0, backoff_max=30, jitter_fraction=0.2,
                               timeout_per_attempt=30, circuit_breaker_threshold=5,
                               circuit_breaker_cooldown=60, rate_limit_backoff=5, adaptive_timeout=True)
        seeds.append(RetryChromosome(configs=c3))

        return seeds

    def calculate_fitness(self, chromosome: RetryChromosome) -> float:
        success_scores = []
        latency_scores = []
        efficiency_scores = []

        for provider, cfg in chromosome.configs.items():
            results = []
            for s in [42, 123, 456]:
                r = self.simulator.simulate(cfg, seed=s + hash(provider) % 1000)
                results.append(r)

            avg_success = np.mean([r['success_rate'] for r in results])
            avg_latency = np.mean([r['avg_latency'] for r in results])
            avg_attempts = np.mean([r['attempts_per_call'] for r in results])
            avg_downtime = np.mean([r['circuit_downtime'] for r in results])

            success_scores.append(avg_success)
            latency_score = max(0, 1.0 - avg_latency / 30.0)
            latency_scores.append(latency_score)
            efficiency = max(0, 1.0 - (avg_attempts - 1.0) / 5.0 - avg_downtime * 2)
            efficiency_scores.append(efficiency)

        success = float(np.mean(success_scores))
        latency = float(np.mean(latency_scores))
        efficiency = float(np.mean(efficiency_scores))

        fitness = success * 0.50 + latency * 0.25 + efficiency * 0.25

        chromosome.fitness = round(fitness, 5)
        chromosome.fitness_details = {
            'success_rate': round(success, 4),
            'latency': round(latency, 4),
            'efficiency': round(efficiency, 4),
        }
        return fitness

    def crossover(self, p1: RetryChromosome, p2: RetryChromosome) -> RetryChromosome:
        configs = {}
        for provider in PROVIDERS:
            c1 = p1.configs.get(provider)
            c2 = p2.configs.get(provider)
            if c1 and c2:
                d1, d2 = asdict(c1), asdict(c2)
                child = {}
                for key in d1:
                    child[key] = d1[key] if random.random() < 0.5 else d2[key]
                configs[provider] = RetryConfig(**child)
            elif c1:
                configs[provider] = RetryConfig(**asdict(c1))
            elif c2:
                configs[provider] = RetryConfig(**asdict(c2))
        return RetryChromosome(configs=configs)

    def mutate(self, chromosome: RetryChromosome):
        for provider, cfg in chromosome.configs.items():
            if random.random() < self.mutation_rate:
                gene = random.choice([
                    'max_retries', 'backoff_base', 'backoff_multiplier', 'backoff_max',
                    'jitter_fraction', 'timeout_per_attempt', 'circuit_breaker_threshold',
                    'circuit_breaker_cooldown', 'rate_limit_backoff', 'adaptive_timeout'])

                if gene == 'max_retries':
                    cfg.max_retries = max(1, min(6, cfg.max_retries + random.randint(-1, 1)))
                elif gene == 'backoff_base':
                    cfg.backoff_base = round(max(0.1, min(5.0, cfg.backoff_base + random.uniform(-0.5, 0.5))), 2)
                elif gene == 'backoff_multiplier':
                    cfg.backoff_multiplier = round(max(1.1, min(4.0, cfg.backoff_multiplier + random.uniform(-0.3, 0.3))), 1)
                elif gene == 'backoff_max':
                    cfg.backoff_max = round(max(5, min(60, cfg.backoff_max + random.uniform(-5, 5))), 0)
                elif gene == 'jitter_fraction':
                    cfg.jitter_fraction = round(max(0, min(0.5, cfg.jitter_fraction + random.uniform(-0.1, 0.1))), 2)
                elif gene == 'timeout_per_attempt':
                    cfg.timeout_per_attempt = round(max(5, min(60, cfg.timeout_per_attempt + random.uniform(-5, 5))), 0)
                elif gene == 'circuit_breaker_threshold':
                    cfg.circuit_breaker_threshold = max(2, min(10, cfg.circuit_breaker_threshold + random.randint(-1, 1)))
                elif gene == 'circuit_breaker_cooldown':
                    cfg.circuit_breaker_cooldown = round(max(10, min(120, cfg.circuit_breaker_cooldown + random.uniform(-10, 10))), 0)
                elif gene == 'rate_limit_backoff':
                    cfg.rate_limit_backoff = round(max(1, min(20, cfg.rate_limit_backoff + random.uniform(-2, 2))), 1)
                elif gene == 'adaptive_timeout':
                    cfg.adaptive_timeout = not cfg.adaptive_timeout

    def tournament_select(self, population):
        candidates = random.sample(population, min(4, len(population)))
        return max(candidates, key=lambda c: c.fitness or 0)

    def run(self, generations=50):
        print("=" * 70)
        print("  GA Retry Policy Optimizer")
        print("=" * 70)
        print(f"Providers: {len(PROVIDERS)}")
        print(f"Genes per provider: 10, Total genes: {10 * len(PROVIDERS)}")
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
            if self.stagnation > 6:
                self.mutation_rate = min(0.5, 0.20 + 0.03 * self.stagnation)
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
                      f"Suc={d['success_rate']:.3f} Lat={d['latency']:.3f} Eff={d['efficiency']:.3f}")
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
        print("  BEST RETRY POLICIES")
        print("=" * 70)
        print(f"  Overall Fitness: {best.fitness:.5f}")
        if best.fitness_details:
            for k, v in best.fitness_details.items():
                print(f"    {k:20s}: {v}")

        for provider in PROVIDERS:
            cfg = best.configs.get(provider)
            if cfg:
                print(f"\n  [{provider.upper()}]")
                print(f"    Retries:    {cfg.max_retries}")
                print(f"    Backoff:    {cfg.backoff_base}s × {cfg.backoff_multiplier}x (max {cfg.backoff_max}s)")
                print(f"    Jitter:     {cfg.jitter_fraction * 100:.0f}%")
                print(f"    Timeout:    {cfg.timeout_per_attempt}s")
                print(f"    Circuit:    threshold={cfg.circuit_breaker_threshold}, cooldown={cfg.circuit_breaker_cooldown}s")
                print(f"    Rate limit: +{cfg.rate_limit_backoff}s backoff")
                print(f"    Adaptive:   {cfg.adaptive_timeout}")
        print("=" * 70)

    def _store_results(self):
        best = self.best_chromosome
        if not best:
            return

        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, 'best_retry_policy.json')

        with open(output_path, 'w') as f:
            json.dump({
                'configs': best.to_dict(),
                'fitness': best.fitness,
                'fitness_details': best.fitness_details,
                'metadata': {'created_at': time.strftime('%Y-%m-%dT%H:%M:%S')},
            }, f, indent=2)
        print(f"\nPolicy saved to: {output_path}")

        try:
            requests.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': 'retry-policy',
                'chromosome': json.dumps(best.to_dict()),
                'fitness': float(best.fitness or 0),
                'fitness_details': json.dumps(best.fitness_details or {}),
                'generation_found': len(self.convergence_history),
            }, timeout=5)
            print("Stored in ga.best_solutions via REST API")
        except Exception:
            print("API unavailable — stored locally only")


def main():
    parser = argparse.ArgumentParser(description='GA Retry Policy Optimizer')
    parser.add_argument('--generations', type=int, default=50)
    parser.add_argument('--population', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    ga = RetryGA(population_size=args.population, seed=args.seed)
    ga.run(generations=args.generations)


if __name__ == '__main__':
    main()
