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

import copy
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
        # Fitness is only comparable within a single target system/evaluator.
        self.best_by_system: Dict[str, Individual] = {}
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
        """Get parameter bounds for each system"""
        bounds = {
            'compression': {
                'compression_level': (0.0, 5.0),
                'target_reduction': (0.2, 0.7),
            },
            'thompson': {
                'alpha_prior': (0.5, 3.0),
                'beta_prior': (0.5, 3.0),
                'cost_weight': (0.1, 0.5),
            },
            'caching': {
                'ttl_seconds': (60.0, 600.0),
                'cache_threshold': (0.1, 0.9),
            },
            'matrix': {
                'domain_weight': (0.1, 0.5),
                'complexity_weight': (0.2, 0.6),
                'task_weight': (0.1, 0.5),
            },
            'dashboard': {
                'learning_rate': (0.01, 0.2),
                'exploration_decay': (0.85, 0.99),
                'alert_threshold': (0.3, 0.9),
            },
        }
        return bounds.get(system_name, {})

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

        per_system, remainder = divmod(self.config.population_size, len(systems))

        for index, system in enumerate(systems):
            count = per_system + (1 if index < remainder else 0)
            for _ in range(count):
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

        # Track best candidates only within their own evaluator/system.
        self.best_by_system = {}
        for system in self.evaluators:
            candidates = [
                individual for individual in self.population
                if individual.system_name == system and individual.fitness is not None
            ]
            if candidates:
                best = max(candidates, key=lambda x: x.fitness)
                self.best_by_system[system] = best
                logger.info(f"Best {system}: fitness={best.fitness:.6f}")

    def tournament_selection(self, system_name: str, k: int = 3) -> Individual:
        """Select an individual via tournament selection within one system."""
        candidates = [
            individual for individual in self.population
            if individual.system_name == system_name
        ]
        if len(candidates) < k:
            raise ValueError(
                f"Cannot run tournament for {system_name}: "
                f"need {k} candidates, have {len(candidates)}"
            )
        tournament = random.sample(candidates, k)
        return max(tournament, key=lambda x: x.fitness)

    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Single-point crossover"""
        if parent1.system_name != parent2.system_name:
            raise ValueError(
                f"Cannot crossover different systems: "
                f"{parent1.system_name} vs {parent2.system_name}"
            )

        # Never return references to the current population when crossover
        # is skipped, because mutation must not mutate parents in place.
        if random.random() > self.config.crossover_rate:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

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
        """Gaussian mutation of parameters.

        Any parameter mutation invalidates the individual's cached fitness.
        Unchanged individuals may retain their existing fitness.
        """
        bounds = self.get_parameter_bounds(individual.system_name)
        mutated = False

        for param_name in individual.parameters.keys():
            if random.random() < self.config.mutation_rate:
                lower, upper = bounds[param_name]
                current = individual.parameters[param_name]

                # Gaussian mutation with 10% std of range
                mutation_std = (upper - lower) * 0.1
                new_value = np.random.normal(current, mutation_std)

                # Clamp to bounds
                individual.parameters[param_name] = np.clip(new_value, lower, upper)
                mutated = True

        if mutated:
            individual.fitness = None

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
            'best_by_system': {
                system: asdict(individual)
                for system, individual in self.best_by_system.items()
            },
        })

        logger.info(f"  Best fitness: {max(fitness_scores):.6f}")
        logger.info(f"  Mean fitness: {np.mean(fitness_scores):.6f}")
        logger.info(f"  Std fitness: {np.std(fitness_scores):.6f}")

        # Evolve each target system independently. Fitness scores are only
        # meaningful relative to the evaluator that produced them.
        new_population = []

        for system_name in sorted({ind.system_name for ind in self.population}):
            current_population = [
                ind for ind in self.population if ind.system_name == system_name
            ]
            elite = self.best_by_system.get(system_name)
            if elite is None:
                raise RuntimeError(f"No elite available for {system_name}")

            # Strict elitism: copy the elite unchanged into the next generation.
            elite_copy = copy.deepcopy(elite)
            elite_copy.generation = generation + 1
            new_population.append(elite_copy)

            system_count = 1
            while system_count < len(current_population):
                parent1 = self.tournament_selection(system_name, self.config.tournament_k)
                parent2 = self.tournament_selection(system_name, self.config.tournament_k)
                child1, child2 = self.crossover(parent1, parent2)

                self.mutate(child1)
                self.mutate(child2)
                child1.generation = generation + 1
                child2.generation = generation + 1

                new_population.append(child1)
                system_count += 1
                if system_count < len(current_population):
                    new_population.append(child2)
                    system_count += 1

        self.population = new_population

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

        # Evaluate the final generation before persisting results so offspring
        # with invalidated fitness are represented in the saved output.
        self.evaluate_population()

        elapsed = time.time() - start_time

        logger.info("\n" + "=" * 80)
        logger.info("OPTIMIZATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Elapsed time: {elapsed:.2f} seconds")
        logger.info("Best fitness by system:")
        for system, individual in sorted(self.best_by_system.items()):
            logger.info(f"  {system}: {individual.fitness:.6f} {individual.parameters}")

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
            'total_evaluations': len(self.population) * (self.config.generations + 1),
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
