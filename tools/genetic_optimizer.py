#!/usr/bin/env python3
"""
Genetic Algorithm Optimizer for Workflow Parameters

Evolves optimal workflow configurations using data from PostgreSQL.
Fitness functions: cost, quality, duration, success rate.

Usage:
    python3 genetic_optimizer.py --task embed-conversations --generations 20
"""

import random
import json
import argparse
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import psycopg2

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
        self.db = psycopg2.connect('dbname=learning host=aio-01 port=5433 user=postgres')

    def evaluate_fitness(self, chromosome: WorkflowChromosome) -> FitnessScore:
        """
        Evaluate fitness by querying historical data from PostgreSQL

        Instead of running actual workflows (expensive), we predict performance
        using past similar executions.
        """
        cur = self.db.cursor()

        # Find similar past executions
        cur.execute("""
            SELECT
                AVG(cost_usd) as avg_cost,
                AVG(quality_score) as avg_quality,
                AVG(duration_ms) as avg_duration,
                SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
                COUNT(*) as sample_count
            FROM monitoring.execution_summary
            WHERE
                model = %s
                AND task_type = %s
                AND ABS(input_tokens + output_tokens - %s) < 1000
            LIMIT 100
        """, (chromosome.model, self.task_type, chromosome.batch_size * 50))

        result = cur.fetchone()

        if result and result[4] > 0:  # Has samples
            avg_cost, avg_quality, avg_duration, success_rate, _ = result

            # Adjust based on chromosome parameters
            # More workers = faster but same cost
            duration_factor = 1.0 / (chromosome.workers / 4.0)

            # Pipeline pattern is generally faster
            if chromosome.pattern == 'pipeline':
                duration_factor *= 0.8

            return FitnessScore(
                cost=avg_cost or 0.01,
                quality=avg_quality or 0.5,
                duration_ms=int((avg_duration or 60000) * duration_factor),
                success_rate=success_rate or 0.5,
            )
        else:
            # No historical data - use defaults
            return FitnessScore(cost=0.1, quality=0.5, duration_ms=120000, success_rate=0.5)

    def evolve(self, generations: int = 20, mutation_rate: float = 0.1) -> WorkflowChromosome:
        """Run genetic algorithm"""
        # Initialize population
        population = [WorkflowChromosome.random() for _ in range(self.population_size)]

        best_individual = None
        best_fitness = None

        for gen in range(generations):
            # Evaluate fitness
            fitness_scores = [(ind, self.evaluate_fitness(ind)) for ind in population]

            # Sort by combined fitness (descending)
            fitness_scores.sort(key=lambda x: x[1].combined_score(), reverse=True)

            # Track best
            if best_fitness is None or fitness_scores[0][1].combined_score() > best_fitness.combined_score():
                best_individual = fitness_scores[0][0]
                best_fitness = fitness_scores[0][1]

            print(f"Generation {gen+1}/{generations}: Best fitness = {best_fitness.combined_score():.4f}")
            print(f"  Cost: ${best_fitness.cost:.4f}, Quality: {best_fitness.quality:.2f}, "
                  f"Duration: {best_fitness.duration_ms/1000:.1f}s, Success: {best_fitness.success_rate:.1%}")

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
