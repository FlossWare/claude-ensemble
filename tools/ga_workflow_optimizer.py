#!/usr/bin/env python3
"""GA Workflow Configuration Optimizer

Evolves optimal configurations for multi-AI workflows: number of workers,
model diversity settings, timeout/retry policies, consensus thresholds,
and phase-level parameters. Works offline with synthetic fitness or online
with real execution data from workflow.executions via REST API.

Each chromosome encodes a workflow configuration template that can be
applied to different workflow types (research, review, implementation).

Usage:
    python3 ga_workflow_optimizer.py                 # offline (50 gens)
    python3 ga_workflow_optimizer.py --generations 200
"""

import argparse
import json
import math
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')

WORKFLOW_TYPES = ['research', 'code_review', 'implementation', 'consensus', 'analysis']

CONSENSUS_METHODS = ['majority', 'weighted', 'unanimous', 'ranked', 'threshold']
ROUTING_STRATEGIES = ['round_robin', 'capability_match', 'thompson_sampling', 'random']

FREE_MODELS = [
    'meta-llama/llama-3.3-70b-instruct:free',
    'qwen/qwen3-235b-a22b:free',
    'qwen/qwen3-coder:free',
    'deepseek/deepseek-chat-v3-0324:free',
    'google/gemini-2.5-flash-preview-05-20',
    'nvidia/llama-3.1-nemotron-70b-instruct:free',
    'nousresearch/hermes-3-llama-3.1-405b:free',
    'mistralai/mistral-small-3.1-24b-instruct:free',
    'microsoft/phi-4-reasoning-plus:free',
    'nvidia/nemotron-3-ultra-550b-a55b:free',
]

ARBITER_MODELS = ['opus', 'sonnet', 'fable', 'haiku']


@dataclass
class WorkflowConfig:
    workflow_type: str = 'research'
    num_workers: int = 4
    worker_model_count: int = 4    # distinct models for workers
    arbiter_model: str = 'fable'
    consensus_method: str = 'weighted'
    consensus_threshold: float = 0.6
    routing_strategy: str = 'capability_match'
    timeout_seconds: int = 120
    retry_limit: int = 2
    diversity_weight: float = 0.5
    max_parallel: int = 3
    review_depth: int = 2          # 1=shallow, 2=standard, 3=deep
    use_external_models: bool = True
    external_model_count: int = 3
    phase_timeout_multiplier: float = 1.5


@dataclass
class WorkflowChromosome:
    configs: Dict[str, WorkflowConfig] = field(default_factory=dict)
    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        return {name: asdict(cfg) for name, cfg in self.configs.items()}


class WorkflowGA:
    def __init__(self, population_size=30, mutation_rate=0.20, seed=None):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.convergence_history = []
        self.best_fitness = 0.0
        self.best_chromosome = None
        self.stagnation = 0

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def create_random(self) -> WorkflowChromosome:
        configs = {}
        for wf_type in WORKFLOW_TYPES:
            configs[wf_type] = WorkflowConfig(
                workflow_type=wf_type,
                num_workers=random.randint(2, 8),
                worker_model_count=random.randint(2, min(8, len(FREE_MODELS))),
                arbiter_model=random.choice(ARBITER_MODELS),
                consensus_method=random.choice(CONSENSUS_METHODS),
                consensus_threshold=round(random.uniform(0.4, 0.9), 2),
                routing_strategy=random.choice(ROUTING_STRATEGIES),
                timeout_seconds=random.choice([60, 90, 120, 180, 300]),
                retry_limit=random.randint(0, 4),
                diversity_weight=round(random.uniform(0.0, 1.0), 2),
                max_parallel=random.randint(1, 6),
                review_depth=random.randint(1, 3),
                use_external_models=random.random() > 0.3,
                external_model_count=random.randint(1, 5),
                phase_timeout_multiplier=round(random.uniform(1.0, 3.0), 1),
            )
        return WorkflowChromosome(configs=configs)

    def create_seeded(self) -> List[WorkflowChromosome]:
        seeds = []

        # Seed 1: Quality-first (many workers, deep review, strong arbiter)
        c1 = {}
        for wf_type in WORKFLOW_TYPES:
            c1[wf_type] = WorkflowConfig(
                workflow_type=wf_type, num_workers=6, worker_model_count=6,
                arbiter_model='opus', consensus_method='weighted',
                consensus_threshold=0.7, routing_strategy='capability_match',
                timeout_seconds=180, retry_limit=3, diversity_weight=0.8,
                max_parallel=4, review_depth=3, use_external_models=True,
                external_model_count=4, phase_timeout_multiplier=2.0)
        seeds.append(WorkflowChromosome(configs=c1))

        # Seed 2: Speed-first (few workers, shallow, fast timeout)
        c2 = {}
        for wf_type in WORKFLOW_TYPES:
            c2[wf_type] = WorkflowConfig(
                workflow_type=wf_type, num_workers=3, worker_model_count=3,
                arbiter_model='haiku', consensus_method='majority',
                consensus_threshold=0.5, routing_strategy='round_robin',
                timeout_seconds=60, retry_limit=1, diversity_weight=0.2,
                max_parallel=3, review_depth=1, use_external_models=False,
                external_model_count=0, phase_timeout_multiplier=1.0)
        seeds.append(WorkflowChromosome(configs=c2))

        # Seed 3: Balanced (tuned per workflow type)
        c3 = {}
        type_params = {
            'research': (5, 5, 'sonnet', 'weighted', 0.6, 180, 3),
            'code_review': (4, 4, 'fable', 'threshold', 0.7, 120, 2),
            'implementation': (3, 3, 'opus', 'majority', 0.5, 300, 2),
            'consensus': (6, 6, 'sonnet', 'unanimous', 0.8, 120, 1),
            'analysis': (4, 4, 'fable', 'weighted', 0.6, 180, 2),
        }
        for wf_type in WORKFLOW_TYPES:
            nw, mc, arb, con, thr, to, rd = type_params[wf_type]
            c3[wf_type] = WorkflowConfig(
                workflow_type=wf_type, num_workers=nw, worker_model_count=mc,
                arbiter_model=arb, consensus_method=con,
                consensus_threshold=thr, routing_strategy='thompson_sampling',
                timeout_seconds=to, retry_limit=2, diversity_weight=0.5,
                max_parallel=3, review_depth=rd, use_external_models=True,
                external_model_count=3, phase_timeout_multiplier=1.5)
        seeds.append(WorkflowChromosome(configs=c3))

        return seeds

    def calculate_fitness(self, chromosome: WorkflowChromosome) -> float:
        """
        Fitness = quality * 0.30 + speed * 0.20 + diversity * 0.20
                + reliability * 0.15 + cost_efficiency * 0.15
        """
        quality_scores = []
        speed_scores = []
        diversity_scores = []
        reliability_scores = []
        cost_scores = []

        for wf_type, cfg in chromosome.configs.items():
            q, s, d, r, c = self._evaluate_config(wf_type, cfg)
            quality_scores.append(q)
            speed_scores.append(s)
            diversity_scores.append(d)
            reliability_scores.append(r)
            cost_scores.append(c)

        quality = float(np.mean(quality_scores))
        speed = float(np.mean(speed_scores))
        diversity = float(np.mean(diversity_scores))
        reliability = float(np.mean(reliability_scores))
        cost_eff = float(np.mean(cost_scores))

        fitness = (
            quality * 0.30 + speed * 0.20 + diversity * 0.20 +
            reliability * 0.15 + cost_eff * 0.15
        )

        chromosome.fitness = round(fitness, 5)
        chromosome.fitness_details = {
            'quality': round(quality, 4), 'speed': round(speed, 4),
            'diversity': round(diversity, 4), 'reliability': round(reliability, 4),
            'cost_efficiency': round(cost_eff, 4),
        }
        return fitness

    def _evaluate_config(self, wf_type, cfg) -> Tuple[float, float, float, float, float]:
        # Quality: more workers + stronger arbiter + deeper review = better
        arbiter_q = {'opus': 0.95, 'fable': 0.90, 'sonnet': 0.88, 'haiku': 0.75}
        base_quality = arbiter_q.get(cfg.arbiter_model, 0.8)

        worker_bonus = min(0.15, cfg.num_workers * 0.025)
        review_bonus = cfg.review_depth * 0.05
        consensus_bonus = {'weighted': 0.08, 'unanimous': 0.1, 'threshold': 0.06,
                          'majority': 0.04, 'ranked': 0.05}.get(cfg.consensus_method, 0.04)
        external_bonus = 0.08 if cfg.use_external_models else 0.0

        quality = min(1.0, base_quality + worker_bonus + review_bonus +
                     consensus_bonus + external_bonus)

        # Quality expectations per type
        type_quality_weight = {'code_review': 1.2, 'consensus': 1.1,
                              'research': 1.0, 'implementation': 0.9, 'analysis': 1.0}
        quality *= type_quality_weight.get(wf_type, 1.0)
        quality = min(1.0, quality)

        # Speed: fewer workers, shorter timeout, less retry = faster
        time_budget = cfg.timeout_seconds * cfg.phase_timeout_multiplier
        if cfg.retry_limit > 0:
            time_budget *= (1 + cfg.retry_limit * 0.3)
        ideal_time = {'research': 120, 'code_review': 90, 'implementation': 180,
                     'consensus': 60, 'analysis': 120}.get(wf_type, 120)
        speed = max(0.0, 1.0 - abs(time_budget - ideal_time) / (ideal_time * 3))
        speed += min(0.15, cfg.max_parallel * 0.03)
        speed = min(1.0, speed)

        # Diversity: distinct models, external models, routing strategy
        model_diversity = min(1.0, cfg.worker_model_count / 6.0)
        external_diversity = min(0.3, cfg.external_model_count * 0.06) if cfg.use_external_models else 0
        routing_diversity = {'thompson_sampling': 0.15, 'capability_match': 0.12,
                           'random': 0.05, 'round_robin': 0.08}.get(cfg.routing_strategy, 0.08)
        diversity = min(1.0, model_diversity * 0.5 + cfg.diversity_weight * 0.2 +
                       external_diversity + routing_diversity)

        # Reliability: retries, timeout slack, consensus threshold
        retry_reliability = min(0.3, cfg.retry_limit * 0.1)
        timeout_reliability = min(0.3, cfg.timeout_seconds / 300.0 * 0.3)
        threshold_reliability = cfg.consensus_threshold * 0.3
        reliability = min(1.0, 0.3 + retry_reliability + timeout_reliability + threshold_reliability)

        # Cost efficiency: fewer workers, no external, fast arbiter = cheaper
        worker_cost = cfg.num_workers / 8.0
        external_cost = cfg.external_model_count * 0.05 if cfg.use_external_models else 0
        arbiter_cost = {'haiku': 0.05, 'sonnet': 0.15, 'fable': 0.12, 'opus': 0.25}.get(cfg.arbiter_model, 0.15)
        total_cost = worker_cost * 0.5 + external_cost + arbiter_cost
        cost_eff = max(0.0, 1.0 - total_cost)

        return quality, speed, diversity, reliability, cost_eff

    def crossover(self, p1: WorkflowChromosome, p2: WorkflowChromosome) -> WorkflowChromosome:
        configs = {}
        for wf_type in WORKFLOW_TYPES:
            c1 = p1.configs.get(wf_type)
            c2 = p2.configs.get(wf_type)
            if c1 and c2:
                d1, d2 = asdict(c1), asdict(c2)
                child = {}
                for key in d1:
                    child[key] = d1[key] if random.random() < 0.5 else d2[key]
                configs[wf_type] = WorkflowConfig(**child)
            elif c1:
                configs[wf_type] = WorkflowConfig(**asdict(c1))
            elif c2:
                configs[wf_type] = WorkflowConfig(**asdict(c2))
        return WorkflowChromosome(configs=configs)

    def mutate(self, chromosome: WorkflowChromosome):
        for wf_type, cfg in chromosome.configs.items():
            if random.random() < self.mutation_rate:
                gene = random.choice([
                    'num_workers', 'worker_model_count', 'arbiter_model',
                    'consensus_method', 'consensus_threshold', 'routing_strategy',
                    'timeout_seconds', 'retry_limit', 'diversity_weight',
                    'max_parallel', 'review_depth', 'use_external_models',
                    'external_model_count', 'phase_timeout_multiplier'])

                if gene == 'num_workers':
                    cfg.num_workers = max(2, min(8, cfg.num_workers + random.randint(-1, 1)))
                elif gene == 'worker_model_count':
                    cfg.worker_model_count = max(2, min(8, cfg.worker_model_count + random.randint(-1, 1)))
                elif gene == 'arbiter_model':
                    cfg.arbiter_model = random.choice(ARBITER_MODELS)
                elif gene == 'consensus_method':
                    cfg.consensus_method = random.choice(CONSENSUS_METHODS)
                elif gene == 'consensus_threshold':
                    cfg.consensus_threshold = round(max(0.4, min(0.9, cfg.consensus_threshold + random.uniform(-0.1, 0.1))), 2)
                elif gene == 'routing_strategy':
                    cfg.routing_strategy = random.choice(ROUTING_STRATEGIES)
                elif gene == 'timeout_seconds':
                    cfg.timeout_seconds = random.choice([60, 90, 120, 180, 300])
                elif gene == 'retry_limit':
                    cfg.retry_limit = max(0, min(4, cfg.retry_limit + random.randint(-1, 1)))
                elif gene == 'diversity_weight':
                    cfg.diversity_weight = round(max(0, min(1, cfg.diversity_weight + random.uniform(-0.2, 0.2))), 2)
                elif gene == 'max_parallel':
                    cfg.max_parallel = max(1, min(6, cfg.max_parallel + random.randint(-1, 1)))
                elif gene == 'review_depth':
                    cfg.review_depth = max(1, min(3, cfg.review_depth + random.choice([-1, 0, 1])))
                elif gene == 'use_external_models':
                    cfg.use_external_models = not cfg.use_external_models
                elif gene == 'external_model_count':
                    cfg.external_model_count = max(0, min(5, cfg.external_model_count + random.randint(-1, 1)))
                elif gene == 'phase_timeout_multiplier':
                    cfg.phase_timeout_multiplier = round(max(1.0, min(3.0, cfg.phase_timeout_multiplier + random.uniform(-0.3, 0.3))), 1)

    def tournament_select(self, population):
        candidates = random.sample(population, min(4, len(population)))
        return max(candidates, key=lambda c: c.fitness or 0)

    def run(self, generations=50):
        print("=" * 70)
        print("  GA Workflow Configuration Optimizer")
        print("=" * 70)
        print(f"Workflow types: {len(WORKFLOW_TYPES)}")
        print(f"Free models: {len(FREE_MODELS)}")
        print(f"Arbiter models: {len(ARBITER_MODELS)}")
        print(f"Genes per type: 15, Total genes: {15 * len(WORKFLOW_TYPES)}")
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
            if self.stagnation > 5:
                self.mutation_rate = min(0.5, 0.20 + 0.03 * self.stagnation)
            else:
                self.mutation_rate = 0.20

            population.sort(key=lambda c: c.fitness or 0, reverse=True)
            elite_size = max(2, self.population_size // 5)
            new_pop = []
            for c in population[:elite_size]:
                new_c = WorkflowChromosome(
                    configs={n: WorkflowConfig(**asdict(cfg)) for n, cfg in c.configs.items()})
                new_pop.append(new_c)

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
                      f"Q={d['quality']:.3f} S={d['speed']:.3f} "
                      f"D={d['diversity']:.3f} R={d['reliability']:.3f} "
                      f"C={d['cost_efficiency']:.3f}")
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
        print("  BEST WORKFLOW CONFIGURATIONS")
        print("=" * 70)
        print(f"  Overall Fitness: {best.fitness:.5f}")
        if best.fitness_details:
            for k, v in best.fitness_details.items():
                print(f"    {k:20s}: {v}")

        for wf_type in WORKFLOW_TYPES:
            cfg = best.configs.get(wf_type)
            if cfg:
                print(f"\n  [{wf_type.upper()}]")
                print(f"    Workers:    {cfg.num_workers} ({cfg.worker_model_count} distinct models)")
                print(f"    Arbiter:    {cfg.arbiter_model}")
                print(f"    Consensus:  {cfg.consensus_method} (threshold={cfg.consensus_threshold})")
                print(f"    Routing:    {cfg.routing_strategy}")
                print(f"    Timeout:    {cfg.timeout_seconds}s (phase mult={cfg.phase_timeout_multiplier}x)")
                print(f"    Retries:    {cfg.retry_limit}")
                print(f"    Diversity:  {cfg.diversity_weight}")
                print(f"    Review:     depth={cfg.review_depth}")
                print(f"    External:   {'Yes' if cfg.use_external_models else 'No'}"
                      f" ({cfg.external_model_count} models)")
                print(f"    Parallel:   {cfg.max_parallel}")
        print("=" * 70)

    def _store_results(self):
        best = self.best_chromosome
        if not best:
            return

        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, 'best_workflow_config.json')

        with open(output_path, 'w') as f:
            json.dump({
                'configs': best.to_dict(),
                'fitness': best.fitness,
                'fitness_details': best.fitness_details,
                'metadata': {'created_at': time.strftime('%Y-%m-%dT%H:%M:%S')},
            }, f, indent=2)
        print(f"\nConfig saved to: {output_path}")

        try:
            requests.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': 'workflow-optimizer',
                'chromosome': json.dumps(best.to_dict()),
                'fitness': float(best.fitness or 0),
                'fitness_details': json.dumps(best.fitness_details or {}),
                'generation_found': len(self.convergence_history),
            }, timeout=5)
            print("Stored in ga.best_solutions via REST API")
        except Exception:
            print("API unavailable — stored locally only")


def main():
    parser = argparse.ArgumentParser(description='GA Workflow Config Optimizer')
    parser.add_argument('--generations', type=int, default=50)
    parser.add_argument('--population', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    ga = WorkflowGA(population_size=args.population, seed=args.seed)
    ga.run(generations=args.generations)


if __name__ == '__main__':
    main()
