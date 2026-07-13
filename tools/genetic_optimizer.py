#!/usr/bin/env python3
"""
Genetic Algorithm Optimizer for Workflow Parameters

Evolves optimal workflow configurations using execution history from the
REST API at aio-01:5000.
Fitness functions: cost, quality, duration, success rate.

Usage:
    python3 genetic_optimizer.py --task embed-conversations --generations 20
"""

import random
import json
import argparse
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import requests

API_BASE = 'http://aio-01:5000'


@dataclass
class WorkflowChromosome:
    """Represents a workflow configuration (individual in population)"""
    pattern: str  # 'pipeline', 'parallel', 'nested', 'sequential'
    batch_size: int  # 100-1000
    workers: int  # 2-16
    model: str  # 'opus', 'sonnet', 'haiku', 'automl', 'fable'
    timeout_ms: int  # 30000-600000
    retry_strategy: str  # 'none', 'linear', 'exponential'

    def to_dict(self) -> Dict:
        return {
            'pattern': self.pattern,
            'batch_size': self.batch_size,
            'workers': self.workers,
            'model': self.model,
            'timeout_ms': self.timeout_ms,
            'retry_strategy': self.retry_strategy,
        }

    @staticmethod
    def random() -> 'WorkflowChromosome':
        """Generate random chromosome"""
        return WorkflowChromosome(
            pattern=random.choice(['pipeline', 'parallel', 'nested', 'sequential']),
            batch_size=random.randint(10, 100) * 10,  # 100-1000 in steps of 10
            workers=random.randint(2, 16),
            model=random.choice(['opus', 'sonnet', 'haiku', 'automl', 'fable']),
            timeout_ms=random.randint(30, 600) * 1000,
            retry_strategy=random.choice(['none', 'linear', 'exponential']),
        )

    def mutate(self, mutation_rate: float = 0.1) -> 'WorkflowChromosome':
        """Mutate chromosome with given probability"""
        if random.random() < mutation_rate:
            gene = random.choice(['pattern', 'batch_size', 'workers', 'model', 'timeout_ms', 'retry_strategy'])
            if gene == 'pattern':
                self.pattern = random.choice(['pipeline', 'parallel', 'nested', 'sequential'])
            elif gene == 'batch_size':
                self.batch_size = random.randint(10, 100) * 10
            elif gene == 'workers':
                self.workers = random.randint(2, 16)
            elif gene == 'model':
                self.model = random.choice(['opus', 'sonnet', 'haiku', 'automl', 'fable'])
            elif gene == 'timeout_ms':
                self.timeout_ms = random.randint(30, 600) * 1000
            elif gene == 'retry_strategy':
                self.retry_strategy = random.choice(['none', 'linear', 'exponential'])
        return self

    @staticmethod
    def crossover(parent1: 'WorkflowChromosome', parent2: 'WorkflowChromosome') -> Tuple['WorkflowChromosome', 'WorkflowChromosome']:
        """Single-point crossover"""
        genes = ['pattern', 'batch_size', 'workers', 'model', 'timeout_ms', 'retry_strategy']
        crossover_point = random.randint(1, len(genes) - 1)

        child1_genes = {g: getattr(parent1, g) for g in genes[:crossover_point]}
        child1_genes.update({g: getattr(parent2, g) for g in genes[crossover_point:]})

        child2_genes = {g: getattr(parent2, g) for g in genes[:crossover_point]}
        child2_genes.update({g: getattr(parent1, g) for g in genes[crossover_point:]})

        return WorkflowChromosome(**child1_genes), WorkflowChromosome(**child2_genes)


@dataclass
class FitnessScore:
    """Multi-objective fitness score"""
    cost: float  # Lower is better
    quality: float  # Higher is better (0-1)
    duration_ms: int  # Lower is better
    success_rate: float  # Higher is better (0-1)

    def combined_score(self, weights: Dict[str, float] = None) -> float:
        """Weighted combination of objectives"""
        if weights is None:
            weights = {'cost': 0.3, 'quality': 0.4, 'duration': 0.2, 'success': 0.1}

        # Normalize (lower cost/duration is better)
        normalized = {
            'cost': 1.0 / (1.0 + self.cost),
            'quality': self.quality,
            'duration': 1.0 / (1.0 + self.duration_ms / 60000),  # Normalize to minutes
            'success': self.success_rate,
        }

        return sum(normalized[k] * weights[k] for k in weights)


class GeneticOptimizer:
    """Genetic algorithm for workflow optimization"""

    def __init__(self, task_type: str, population_size: int = 50):
        self.task_type = task_type
        self.population_size = population_size
        self.use_case = 'workflow-optimizer'
        # Reuse TCP connections for speed (connection pooling)
        self._session = requests.Session()
        # Cache fitness results for identical (model, task_type) lookups within a run
        self._fitness_cache: Dict[str, Dict] = {}

    def _fetch_baseline(self, model: str) -> Dict:
        """
        Fetch historical baseline for a model+task_type combo, with caching.

        Two-stage lookup:
          1. Exact match on model + task_type (best signal)
          2. Fallback to task_type only (cross-model baseline)

        Returns dict with avg_cost, avg_quality, avg_duration, success_rate or None.
        """
        cache_key = f"{model}|{self.task_type}"
        if cache_key in self._fitness_cache:
            return self._fitness_cache[cache_key]

        # Stage 1: exact model + task_type match
        resp = self._session.post(f'{API_BASE}/ga/query', json={
            'query': """
                SELECT
                    AVG(cost_usd) as avg_cost,
                    AVG(quality_score) as avg_quality,
                    AVG(duration_ms) as avg_duration,
                    SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float
                        / NULLIF(COUNT(*), 0) as success_rate,
                    COUNT(*) as sample_count
                FROM monitoring.execution_summary
                WHERE model = %(model)s
                  AND task_type = %(task_type)s
            """,
            'params': {
                'model': model,
                'task_type': self.task_type,
            }
        }, timeout=10)
        resp.raise_for_status()
        rows = resp.json()

        row = None
        if rows and rows[0].get('sample_count', 0) and rows[0]['sample_count'] > 0:
            row = rows[0]
        else:
            # Stage 2: fallback to task_type only (cross-model)
            fallback_key = f"__fallback__|{self.task_type}"
            if fallback_key in self._fitness_cache:
                row = self._fitness_cache[fallback_key]
            else:
                resp2 = self._session.post(f'{API_BASE}/ga/query', json={
                    'query': """
                        SELECT
                            AVG(cost_usd) as avg_cost,
                            AVG(quality_score) as avg_quality,
                            AVG(duration_ms) as avg_duration,
                            SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float
                                / NULLIF(COUNT(*), 0) as success_rate,
                            COUNT(*) as sample_count
                        FROM monitoring.execution_summary
                        WHERE task_type = %(task_type)s
                    """,
                    'params': {'task_type': self.task_type}
                }, timeout=10)
                resp2.raise_for_status()
                rows2 = resp2.json()
                if rows2 and rows2[0].get('sample_count', 0) and rows2[0]['sample_count'] > 0:
                    row = rows2[0]
                self._fitness_cache[fallback_key] = row

        self._fitness_cache[cache_key] = row
        return row

    def evaluate_fitness(self, chromosome: WorkflowChromosome) -> FitnessScore:
        """
        Evaluate fitness by querying historical data from the REST API.

        Instead of running actual workflows (expensive), we predict performance
        using past similar executions. Chromosome parameters (workers, pattern,
        batch_size, retry_strategy) modulate the historical averages.
        """
        row = self._fetch_baseline(chromosome.model)

        if row is None:
            # No historical data at all - use defaults
            return FitnessScore(cost=0.1, quality=0.5, duration_ms=120000, success_rate=0.5)

        avg_cost = float(row.get('avg_cost') or 0.01)
        avg_quality = float(row.get('avg_quality') or 0.5)
        avg_duration = float(row.get('avg_duration') or 60000)
        success_rate = float(row.get('success_rate') or 0.5)

        # --- Modulate by chromosome parameters ---

        # More workers = faster execution (diminishing returns)
        duration_factor = 1.0 / (chromosome.workers / 4.0) ** 0.7

        # Pattern effects
        pattern_speed = {'pipeline': 0.80, 'parallel': 0.85, 'nested': 1.0, 'sequential': 1.15}
        duration_factor *= pattern_speed.get(chromosome.pattern, 1.0)

        # Batch size scales cost linearly, quality slightly degrades at high batch
        batch_ratio = chromosome.batch_size / 500.0  # 500 = midpoint
        cost_factor = batch_ratio

        # Quality degrades slightly at extremes (too small = underfit, too large = noisy)
        quality_factor = 1.0 - 0.05 * abs(batch_ratio - 1.0)

        # Retry strategy affects success rate and duration
        retry_effects = {
            'none':        {'success': 1.0,  'duration': 1.0},
            'linear':      {'success': 1.05, 'duration': 1.15},
            'exponential': {'success': 1.10, 'duration': 1.25},
        }
        retry = retry_effects.get(chromosome.retry_strategy, retry_effects['none'])

        return FitnessScore(
            cost=avg_cost * cost_factor,
            quality=min(1.0, avg_quality * quality_factor),
            duration_ms=int(avg_duration * duration_factor * retry['duration']),
            success_rate=min(1.0, success_rate * retry['success']),
        )

    def _store_convergence(self, generation: int, best_fitness: float, avg_fitness: float, diversity: float):
        """Store convergence metrics via REST API"""
        try:
            self._session.post(f'{API_BASE}/ga/convergence', json={
                'use_case': self.use_case,
                'generation': generation,
                'island_id': 0,
                'best_fitness': best_fitness,
                'avg_fitness': avg_fitness,
                'diversity': diversity,
            }, timeout=5)
        except requests.RequestException:
            pass  # Non-critical, don't interrupt evolution

    def _store_best_solution(self, chromosome: WorkflowChromosome, fitness: FitnessScore, generation: int):
        """Store the best solution found via REST API"""
        try:
            resp = self._session.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': self.use_case,
                'chromosome': json.dumps(chromosome.to_dict()),
                'fitness': fitness.combined_score(),
                'fitness_details': json.dumps({
                    'cost': fitness.cost,
                    'quality': fitness.quality,
                    'duration_ms': fitness.duration_ms,
                    'success_rate': fitness.success_rate,
                }),
                'generation_found': generation,
                'notes': f'Task: {self.task_type}, Pop: {self.population_size}',
            }, timeout=10)
            if resp.status_code >= 300:
                print(f"Warning: best-solutions POST returned {resp.status_code}")
        except requests.RequestException as e:
            print(f"Warning: failed to store best solution: {e}")

    def _store_population(self, generation: int, population: List[WorkflowChromosome],
                          fitness_scores: List[Tuple[WorkflowChromosome, FitnessScore]]):
        """Store current population state via REST API (top 10 only to limit volume)"""
        try:
            for chromosome, fitness in fitness_scores[:10]:
                self._session.post(f'{API_BASE}/ga/populations', json={
                    'use_case': self.use_case,
                    'generation': generation,
                    'island_id': 0,
                    'chromosome': json.dumps(chromosome.to_dict()),
                    'fitness': fitness.combined_score(),
                    'fitness_details': json.dumps({
                        'cost': fitness.cost,
                        'quality': fitness.quality,
                        'duration_ms': fitness.duration_ms,
                        'success_rate': fitness.success_rate,
                    }),
                }, timeout=5)
        except requests.RequestException:
            pass  # Non-critical

    @staticmethod
    def _population_diversity(fitness_scores: List[Tuple[WorkflowChromosome, FitnessScore]]) -> float:
        """Measure population diversity as ratio of unique models and patterns"""
        if not fitness_scores:
            return 0.0
        models = set()
        patterns = set()
        for chrom, _ in fitness_scores:
            models.add(chrom.model)
            patterns.add(chrom.pattern)
        # Diversity = average of unique-model ratio and unique-pattern ratio
        return (len(models) / 5.0 + len(patterns) / 4.0) / 2.0

    def _preflight_check(self):
        """Show data availability before running GA"""
        try:
            resp = self._session.post(f'{API_BASE}/ga/query', json={
                'query': """
                    SELECT model, COUNT(*) as cnt,
                           AVG(quality_score) as avg_q,
                           AVG(cost_usd) as avg_c
                    FROM monitoring.execution_summary
                    WHERE task_type = %(task_type)s
                    GROUP BY model
                    ORDER BY cnt DESC
                    LIMIT 15
                """,
                'params': {'task_type': self.task_type}
            }, timeout=10)
            resp.raise_for_status()
            rows = resp.json()
            total = sum(r['cnt'] for r in rows)
            print(f"Data availability for task_type='{self.task_type}':")
            print(f"  Total records: {total}")
            for r in rows[:8]:
                q = f"{r['avg_q']:.3f}" if r.get('avg_q') is not None else 'N/A'
                c = f"${r['avg_c']:.4f}" if r.get('avg_c') is not None else 'N/A'
                print(f"  {r['model']:20s}  n={r['cnt']:>5d}  quality={q}  cost={c}")
            print()
        except Exception as e:
            print(f"Warning: preflight check failed: {e}\n")

    def evolve(self, generations: int = 20, mutation_rate: float = 0.1) -> WorkflowChromosome:
        """Run genetic algorithm"""
        self._preflight_check()

        # Initialize population
        population = [WorkflowChromosome.random() for _ in range(self.population_size)]

        best_individual = None
        best_fitness = None
        best_generation = 0

        for gen in range(generations):
            # Evaluate fitness
            fitness_scores = [(ind, self.evaluate_fitness(ind)) for ind in population]

            # Sort by combined fitness (descending)
            fitness_scores.sort(key=lambda x: x[1].combined_score(), reverse=True)

            # Track best
            if best_fitness is None or fitness_scores[0][1].combined_score() > best_fitness.combined_score():
                best_individual = fitness_scores[0][0]
                best_fitness = fitness_scores[0][1]
                best_generation = gen + 1

            print(f"Generation {gen+1}/{generations}: Best fitness = {best_fitness.combined_score():.4f}")
            print(f"  Cost: ${best_fitness.cost:.4f}, Quality: {best_fitness.quality:.2f}, "
                  f"Duration: {best_fitness.duration_ms/1000:.1f}s, Success: {best_fitness.success_rate:.1%}")

            # Store convergence and population tracking
            avg_fitness = sum(fs.combined_score() for _, fs in fitness_scores) / len(fitness_scores)
            diversity = self._population_diversity(fitness_scores)
            self._store_convergence(gen + 1, best_fitness.combined_score(), avg_fitness, diversity)
            self._store_population(gen + 1, population, fitness_scores)

            # Selection (top 50%)
            selected = [ind for ind, _ in fitness_scores[:self.population_size // 2]]

            # Crossover
            offspring = []
            while len(offspring) < self.population_size // 2:
                parent1, parent2 = random.sample(selected, 2)
                child1, child2 = WorkflowChromosome.crossover(parent1, parent2)
                offspring.extend([child1, child2])

            # Mutation
            offspring = [child.mutate(mutation_rate) for child in offspring]

            # New population
            population = selected + offspring[:self.population_size - len(selected)]

        # Store the best solution found
        self._store_best_solution(best_individual, best_fitness, best_generation)

        print("\n" + "="*60)
        print("EVOLUTION COMPLETE")
        print("="*60)
        print(f"Best configuration: {json.dumps(best_individual.to_dict(), indent=2)}")
        print(f"Predicted performance:")
        print(f"  Cost: ${best_fitness.cost:.4f}")
        print(f"  Quality: {best_fitness.quality:.2f}")
        print(f"  Duration: {best_fitness.duration_ms/1000:.1f}s")
        print(f"  Success rate: {best_fitness.success_rate:.1%}")

        return best_individual


def main():
    parser = argparse.ArgumentParser(description='Genetic algorithm for workflow optimization')
    parser.add_argument('--task', required=True, help='Task type to optimize for')
    parser.add_argument('--generations', type=int, default=20, help='Number of generations')
    parser.add_argument('--population', type=int, default=50, help='Population size')
    parser.add_argument('--mutation-rate', type=float, default=0.1, help='Mutation rate (0-1)')
    parser.add_argument('--output', help='Output file for best configuration')

    args = parser.parse_args()

    optimizer = GeneticOptimizer(task_type=args.task, population_size=args.population)
    best = optimizer.evolve(generations=args.generations, mutation_rate=args.mutation_rate)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(best.to_dict(), f, indent=2)
        print(f"\nBest configuration saved to: {args.output}")


if __name__ == '__main__':
    main()
