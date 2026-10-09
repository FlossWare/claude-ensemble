#!/usr/bin/env python3
"""
Genetic Algorithm Tuning System for 5 RH Fixed Tools

Evolves parameters for:
1. Compression GA - compression_level, target_reduction
2. Thompson Router GA - alpha_prior, beta_prior, cost_weight
3. Caching GA - ttl_seconds, cache_threshold
4. Capability Matrix GA - ScoringWeights (domain, complexity, task)
5. Dashboard GA - learning_rate, exploration_decay, alert_threshold

Local evaluation only (no API calls). Uses parallel fitness evaluation.
"""

import json
import os
import sys
import time
import logging
import random
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import yaml

# Add evaluators to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'evaluators'))

from compression_evaluator import CompressionEvaluator
from thompson_evaluator import ThompsonEvaluator
from caching_evaluator import CachingEvaluator
from matrix_evaluator import MatrixEvaluator
from dashboard_evaluator import DashboardEvaluator
from parameter_schema import bounds_for_system

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# GENETIC ALGORITHM FRAMEWORK
# ============================================================================

@dataclass
class GAConfig:
    """GA configuration"""
    population_size: int = 50
    generations: int = 25
    crossover_rate: float = 0.8
    mutation_rate: float = 0.1
    tournament_k: int = 3
    seed: int = 42
    max_workers: int = 4
    output_dir: str = './results'


@dataclass
class Individual:
    """Single individual (parameter set)"""
    system_name: str
    parameters: Dict[str, float]
    fitness: Optional[float] = None
    generation: int = 0


class GeneticAlgorithm:
    """Main GA loop for parameter optimization"""

    def __init__(self, config: GAConfig):
        self.config = config
        self.population: List[Individual] = []
        self.best_overall: Optional[Individual] = None
        self.fitness_history: List[Dict[str, Any]] = []
        self.evaluators: Dict[str, Any] = {}

        # Create output directory
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)

        random.seed(config.seed)
        np.random.seed(config.seed)

    def initialize_evaluators(self):
        """Initialize all 5 evaluators"""
        logger.info("Initializing evaluators...")
        rh_memory_dir = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/memory'

        self.evaluators['compression'] = CompressionEvaluator(rh_memory_dir)
        self.evaluators['thompson'] = ThompsonEvaluator()
        self.evaluators['caching'] = CachingEvaluator()
        self.evaluators['matrix'] = MatrixEvaluator(rh_memory_dir)
        self.evaluators['dashboard'] = DashboardEvaluator()

        logger.info(f"Initialized {len(self.evaluators)} evaluators")

    def get_parameter_bounds(self, system_name: str) -> Dict[str, Tuple[float, float]]:
        """Get optimizer bounds from the shared parameter schema."""
        return bounds_for_system(system_name)

    def create_random_individual(self, system_name: str, generation: int = 0) -> Individual:
        """Create individual with random parameters"""
        bounds = self.get_parameter_bounds(system_name)
        parameters = {}

        for param_name, (lower, upper) in bounds.items():
            parameters[param_name] = random.uniform(lower, upper)

        return Individual(system_name=system_name, parameters=parameters, generation=generation)

    def initialize_population(self):
        """Create initial population for all 5 systems"""
        logger.info(f"Creating initial population of {self.config.population_size}")
        self.population = []
        systems = ['compression', 'thompson', 'caching', 'matrix', 'dashboard']

        per_system = self.config.population_size // len(systems)

        for system in systems:
            for _ in range(per_system):
                individual = self.create_random_individual(system)
                self.population.append(individual)

        logger.info(f"Created {len(self.population)} individuals")

    def evaluate_individual(self, individual: Individual) -> float:
        """Evaluate fitness of an individual"""
        try:
            evaluator = self.evaluators[individual.system_name]
            fitness = evaluator.evaluate(individual.parameters)
            return fitness
        except Exception as e:
            logger.error(f"Error evaluating {individual.system_name}: {e}")
            return 0.0

    def evaluate_population(self):
        """Evaluate entire population in parallel"""
        logger.info(f"Evaluating {len(self.population)} individuals...")

        # Sequential evaluation for now (can be parallelized)
        for i, individual in enumerate(self.population):
            if individual.fitness is None:
                fitness = self.evaluate_individual(individual)
                individual.fitness = fitness
                if (i + 1) % 10 == 0:
                    logger.info(f"  Evaluated {i+1}/{len(self.population)}")

        # Track best overall
        best_in_pop = max(self.population, key=lambda x: x.fitness)
        if self.best_overall is None or best_in_pop.fitness > self.best_overall.fitness:
            self.best_overall = best_in_pop
            logger.info(f"New best: {best_in_pop.system_name} fitness={best_in_pop.fitness:.6f}")

    def tournament_selection(self, k: int = 3) -> Individual:
        """Select individual via tournament selection"""
        tournament = random.sample(self.population, k)
        return max(tournament, key=lambda x: x.fitness)

    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Single-point crossover"""
        if parent1.system_name != parent2.system_name:
            # Can't crossover different systems
            return parent1, parent2

        if random.random() > self.config.crossover_rate:
            return parent1, parent2

        param_names = list(parent1.parameters.keys())
        crossover_point = random.randint(0, len(param_names) - 1)

        child1_params = {}
        child2_params = {}

        for i, param in enumerate(param_names):
            if i < crossover_point:
                child1_params[param] = parent1.parameters[param]
                child2_params[param] = parent2.parameters[param]
            else:
                child1_params[param] = parent2.parameters[param]
                child2_params[param] = parent1.parameters[param]

        child1 = Individual(system_name=parent1.system_name, parameters=child1_params)
        child2 = Individual(system_name=parent1.system_name, parameters=child2_params)

        return child1, child2

    def mutate(self, individual: Individual):
        """Gaussian mutation of parameters"""
        bounds = self.get_parameter_bounds(individual.system_name)

        for param_name in individual.parameters.keys():
            if random.random() < self.config.mutation_rate:
                lower, upper = bounds[param_name]
                current = individual.parameters[param_name]

                # Gaussian mutation with 10% std of range
                mutation_std = (upper - lower) * 0.1
                new_value = np.random.normal(current, mutation_std)

                # Clamp to bounds
                individual.parameters[param_name] = np.clip(new_value, lower, upper)

    def evolve(self, generation: int):
        """Perform one generation of evolution"""
        logger.info(f"\n=== Generation {generation + 1}/{self.config.generations} ===")

        # Evaluate current population
        self.evaluate_population()

        # Record statistics
        fitness_scores = [ind.fitness for ind in self.population]
        self.fitness_history.append({
            'generation': generation,
            'best': max(fitness_scores),
            'mean': np.mean(fitness_scores),
            'std': np.std(fitness_scores),
            'worst': min(fitness_scores),
            'best_individual': asdict(self.best_overall),
        })

        logger.info(f"  Best fitness: {max(fitness_scores):.6f}")
        logger.info(f"  Mean fitness: {np.mean(fitness_scores):.6f}")
        logger.info(f"  Std fitness: {np.std(fitness_scores):.6f}")

        # Create new population
        new_population = []

        # Elitism: keep best individual
        new_population.append(self.best_overall)

        # Generate offspring via selection, crossover, mutation
        while len(new_population) < len(self.population):
            parent1 = self.tournament_selection(self.config.tournament_k)
            parent2 = self.tournament_selection(self.config.tournament_k)

            child1, child2 = self.crossover(parent1, parent2)

            self.mutate(child1)
            self.mutate(child2)

            child1.generation = generation + 1
            child2.generation = generation + 1

            new_population.append(child1)
            if len(new_population) < len(self.population):
                new_population.append(child2)

        self.population = new_population[:len(self.population)]

    def run(self):
        """Run complete GA"""
        logger.info("=" * 80)
        logger.info("GENETIC ALGORITHM TUNING SYSTEM FOR 5 RH TOOLS")
        logger.info("=" * 80)
        logger.info(f"Configuration: {self.config}")

        self.initialize_evaluators()
        self.initialize_population()

        start_time = time.time()

        for generation in range(self.config.generations):
            self.evolve(generation)

        elapsed = time.time() - start_time

        logger.info("\n" + "=" * 80)
        logger.info("OPTIMIZATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Elapsed time: {elapsed:.2f} seconds")
        logger.info(f"Best fitness: {self.best_overall.fitness:.6f}")
        logger.info(f"Best system: {self.best_overall.system_name}")
        logger.info(f"Best parameters: {self.best_overall.parameters}")

        return self.save_results()

    def save_results(self) -> Dict[str, Any]:
        """Save results to JSON files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save best parameters for each system
        results_by_system = {}
        for ind in self.population:
            if ind.fitness is None:
                continue  # Skip individuals without fitness
            if ind.system_name not in results_by_system:
                results_by_system[ind.system_name] = []
            results_by_system[ind.system_name].append({
                'parameters': {k: float(v) for k, v in ind.parameters.items()},
                'fitness': float(ind.fitness),
            })

        # Keep best 3 for each system
        best_params = {}
        for system, individuals in results_by_system.items():
            if not individuals:
                continue
            sorted_inds = sorted(individuals, key=lambda x: x['fitness'], reverse=True)
            best_params[system] = sorted_inds[0:3]

        # Save best parameters
        best_file = os.path.join(self.config.output_dir, f'ga_best_parameters_{timestamp}.json')
        with open(best_file, 'w') as f:
            json.dump(best_params, f, indent=2)
        logger.info(f"Saved best parameters to {best_file}")

        # Save fitness history
        history_file = os.path.join(self.config.output_dir, f'ga_fitness_history_{timestamp}.json')
        with open(history_file, 'w') as f:
            json.dump(self.fitness_history, f, indent=2)
        logger.info(f"Saved fitness history to {history_file}")

        # Save summary report
        summary = {
            'timestamp': timestamp,
            'total_evaluations': len(self.population) * self.config.generations,
            'best_overall_fitness': float(self.best_overall.fitness) if self.best_overall.fitness else 0.0,
            'best_overall_system': self.best_overall.system_name,
            'best_overall_parameters': {k: float(v) for k, v in self.best_overall.parameters.items()},
            'generations': self.config.generations,
            'population_size': self.config.population_size,
            'best_by_system': best_params,
        }

        summary_file = os.path.join(self.config.output_dir, f'ga_summary_{timestamp}.json')
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Saved summary to {summary_file}")

        return summary


def main():
    """Main entry point"""
    # Load config if available, otherwise use defaults
    config_file = './ga_config.yaml'
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config_dict = yaml.safe_load(f)
        config = GAConfig(**config_dict)
    else:
        config = GAConfig()

    ga = GeneticAlgorithm(config)
    summary = ga.run()

    print("\n" + "=" * 80)
    print("BEST PARAMETERS BY SYSTEM")
    print("=" * 80)
    for system, individuals in summary['best_by_system'].items():
        print(f"\n{system.upper()}:")
        for i, ind in enumerate(individuals, 1):
            print(f"  Rank {i} (fitness={ind['fitness']:.6f}):")
            for param, value in ind['parameters'].items():
                print(f"    {param}: {value:.4f}")


if __name__ == '__main__':
    main()
