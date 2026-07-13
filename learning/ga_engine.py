#!/usr/bin/env python3
"""
Fleet Genetic Algorithm Engine
Evolves optimal fleet orchestration strategies via genetic algorithm.
Integrates with Thompson Sampling via REST API (aio-01:5000).

Refactored: Uses REST API instead of direct PostgreSQL (psycopg2).
use_case: fleet-orchestration
"""

import random
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

API_BASE = 'http://aio-01:5000'

# REST API integration with fallback
try:
    import requests
    REST_AVAILABLE = True
except ImportError:
    REST_AVAILABLE = False

OUTCOMES = type('OUTCOMES', (), {
    'SUCCESS': 'SUCCESS',
    'FAILED': 'FAILED',
    'ERROR': 'ERROR'
})()


# Fleet constraints (from validated orchestration)
WORKERS_MIN = 1
WORKERS_MAX = 6
TIMEOUT_MIN = 30
TIMEOUT_MAX = 600
VALID_CONSENSUS = ['majority', 'unanimous', 'weighted', 'ranked']
# All available models (3 local + 5 cloud placeholders)
VALID_ARBITERS = [
    # Local ollama models (actually available on laptop-01)
    'gemma2:2b', 'phi3.5:latest', 'qwen2.5:7b',
    # Cloud API placeholders (for future use)
    'opus', 'sonnet', 'haiku', 'gpt4o', 'gemini'
]

# Local lineage storage path (replaces ga.strategies / ga.lineage PostgreSQL tables)
LINEAGE_PATH = Path(__file__).parent / 'ga_fleet_lineage.json'


@dataclass
class FleetChromosome:
    """Represents a fleet orchestration strategy as genes."""

    # Genes (strategy parameters)
    workers: int  # 1-6 parallel workers
    arbiter: str  # consensus model
    timeout: int  # seconds
    consensus_type: str  # majority/unanimous/weighted/ranked
    retry_limit: int  # max retries
    diversity_weight: float  # 0.0-1.0

    # Fitness (calculated after evaluation)
    fitness: Optional[float] = None

    def __post_init__(self):
        """Validate genes on initialization."""
        if not WORKERS_MIN <= self.workers <= WORKERS_MAX:
            raise ValueError(f"workers must be {WORKERS_MIN}-{WORKERS_MAX}")
        if self.arbiter not in VALID_ARBITERS:
            raise ValueError(f"arbiter must be one of {VALID_ARBITERS}")
        if not TIMEOUT_MIN <= self.timeout <= TIMEOUT_MAX:
            raise ValueError(f"timeout must be {TIMEOUT_MIN}-{TIMEOUT_MAX}")
        if self.consensus_type not in VALID_CONSENSUS:
            raise ValueError(f"consensus_type must be one of {VALID_CONSENSUS}")
        if not 1 <= self.retry_limit <= 5:
            raise ValueError("retry_limit must be 1-5")
        if not 0.0 <= self.diversity_weight <= 1.0:
            raise ValueError("diversity_weight must be 0.0-1.0")

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'FleetChromosome':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k != 'fitness'})

    def validate(self) -> Dict[str, bool]:
        """Validate chromosome integrity."""
        return {
            'workers_valid': WORKERS_MIN <= self.workers <= WORKERS_MAX,
            'arbiter_valid': self.arbiter in VALID_ARBITERS,
            'timeout_valid': TIMEOUT_MIN <= self.timeout <= TIMEOUT_MAX,
            'consensus_valid': self.consensus_type in VALID_CONSENSUS,
            'retry_valid': 1 <= self.retry_limit <= 5,
            'diversity_valid': 0.0 <= self.diversity_weight <= 1.0
        }


def crossover(parent1: FleetChromosome, parent2: FleetChromosome) -> Tuple[FleetChromosome, FleetChromosome]:
    """
    Two-point crossover with validation.
    Returns two offspring chromosomes.
    """
    # Choose two random crossover points
    genes = ['workers', 'arbiter', 'timeout', 'consensus_type', 'retry_limit', 'diversity_weight']
    point1, point2 = sorted(random.sample(range(1, len(genes)), 2))

    # Create offspring gene sets
    child1_genes = {}
    child2_genes = {}

    for i, gene in enumerate(genes):
        if i < point1 or i >= point2:
            child1_genes[gene] = getattr(parent1, gene)
            child2_genes[gene] = getattr(parent2, gene)
        else:
            child1_genes[gene] = getattr(parent2, gene)
            child2_genes[gene] = getattr(parent1, gene)

    # Validate offspring (retry if invalid)
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            child1 = FleetChromosome(**child1_genes)
            child2 = FleetChromosome(**child2_genes)

            # Validate integrity
            if all(child1.validate().values()) and all(child2.validate().values()):
                return child1, child2
        except ValueError:
            pass

        # Retry with different crossover points
        point1, point2 = sorted(random.sample(range(1, len(genes)), 2))
        child1_genes = {}
        child2_genes = {}
        for i, gene in enumerate(genes):
            if i < point1 or i >= point2:
                child1_genes[gene] = getattr(parent1, gene)
                child2_genes[gene] = getattr(parent2, gene)
            else:
                child1_genes[gene] = getattr(parent2, gene)
                child2_genes[gene] = getattr(parent1, gene)

    # Fallback: return parents if crossover fails
    return parent1, parent2


def mutate(chromosome: FleetChromosome, mutation_rate: float = 0.1) -> FleetChromosome:
    """
    Mutate chromosome genes with given probability.
    Returns new mutated chromosome.
    """
    genes = chromosome.to_dict()
    del genes['fitness']  # Remove fitness before mutation

    # Mutate each gene independently
    if random.random() < mutation_rate:
        genes['workers'] = random.randint(WORKERS_MIN, WORKERS_MAX)

    if random.random() < mutation_rate:
        genes['arbiter'] = random.choice(VALID_ARBITERS)

    if random.random() < mutation_rate:
        genes['timeout'] = random.randint(TIMEOUT_MIN, TIMEOUT_MAX)

    if random.random() < mutation_rate:
        genes['consensus_type'] = random.choice(VALID_CONSENSUS)

    if random.random() < mutation_rate:
        genes['retry_limit'] = random.randint(1, 5)

    if random.random() < mutation_rate:
        genes['diversity_weight'] = round(random.uniform(0.0, 1.0), 2)

    # Validate mutated chromosome (retry if invalid)
    max_attempts = 10
    for _ in range(max_attempts):
        try:
            mutated = FleetChromosome(**genes)
            if all(mutated.validate().values()):
                return mutated
        except ValueError:
            # Retry with fresh random values
            if random.random() < mutation_rate:
                genes['workers'] = random.randint(WORKERS_MIN, WORKERS_MAX)
            if random.random() < mutation_rate:
                genes['arbiter'] = random.choice(VALID_ARBITERS)
            if random.random() < mutation_rate:
                genes['timeout'] = random.randint(TIMEOUT_MIN, TIMEOUT_MAX)
            if random.random() < mutation_rate:
                genes['consensus_type'] = random.choice(VALID_CONSENSUS)
            if random.random() < mutation_rate:
                genes['retry_limit'] = random.randint(1, 5)
            if random.random() < mutation_rate:
                genes['diversity_weight'] = round(random.uniform(0.0, 1.0), 2)

    # Fallback: return original if mutation fails
    return chromosome


def calculate_fitness(chromosome: FleetChromosome, tasks: List[Dict]) -> float:
    """
    Calculate fitness by executing tasks with chromosome's strategy.

    Fitness = (success_rate * 0.4) + (avg_quality * 0.3) + (efficiency * 0.2) + (diversity * 0.1)

    Args:
        chromosome: Strategy to evaluate
        tasks: List of test tasks with expected outputs

    Returns:
        Fitness score (0.0-1.0, higher is better)
    """
    if not tasks:
        return 0.0

    # Simulate task execution with chromosome's strategy
    # In production, this would call actual fleet orchestration
    successes = 0
    total_quality = 0.0
    total_time = 0.0
    model_usage = {}

    for task in tasks:
        # Simulate execution based on genes
        base_success_rate = 0.7

        # Workers: more workers = higher parallelism but coordination overhead
        worker_factor = min(1.0, chromosome.workers / 4.0)

        # Arbiter quality (from historical data)
        arbiter_quality = {
            'opus': 0.9,
            'sonnet': 0.85,
            'haiku': 0.75,
            'gpt4o': 0.88,
            'gemini': 0.82
        }.get(chromosome.arbiter, 0.8)

        # Consensus type impact
        consensus_factor = {
            'unanimous': 0.95,
            'majority': 0.85,
            'weighted': 0.90,
            'ranked': 0.88
        }.get(chromosome.consensus_type, 0.85)

        # Timeout: too short = failures, too long = wasted time
        optimal_timeout = 120
        timeout_factor = 1.0 - abs(chromosome.timeout - optimal_timeout) / optimal_timeout * 0.3

        # Retry limit: more retries = higher success but slower
        retry_factor = min(1.0, chromosome.retry_limit / 3.0)

        # Calculate success probability
        success_prob = base_success_rate * worker_factor * arbiter_quality * consensus_factor * timeout_factor * retry_factor

        if random.random() < success_prob:
            successes += 1
            quality = arbiter_quality * consensus_factor
            total_quality += quality

            # Track model usage for diversity
            model_usage[chromosome.arbiter] = model_usage.get(chromosome.arbiter, 0) + 1

        # Simulate execution time
        base_time = 30
        time = base_time / chromosome.workers + (chromosome.retry_limit - 1) * 10
        total_time += min(time, chromosome.timeout)

    # Calculate metrics
    success_rate = successes / len(tasks)
    avg_quality = total_quality / len(tasks) if successes > 0 else 0.0

    # Efficiency: inverse of average time (normalized)
    avg_time = total_time / len(tasks)
    max_time = TIMEOUT_MAX
    efficiency = 1.0 - (avg_time / max_time)

    # Diversity: penalize if only using one model
    diversity_score = len(model_usage) / len(VALID_ARBITERS)
    diversity = chromosome.diversity_weight * diversity_score

    # Weighted fitness
    fitness = (success_rate * 0.4) + (avg_quality * 0.3) + (efficiency * 0.2) + (diversity * 0.1)

    return round(fitness, 4)


class FleetGeneticOptimizer:
    """
    Orchestrates genetic evolution of fleet strategies.
    Integrates with REST API for Thompson Sampling and convergence tracking.
    use_case: fleet-orchestration
    """

    def __init__(self, population_size: int = 20, mutation_rate: float = 0.1):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.population: List[FleetChromosome] = []
        self.generation = 0
        self.best_chromosome: Optional[FleetChromosome] = None
        self.best_fitness = 0.0

    def create_random_population(self, size: int) -> List[FleetChromosome]:
        """Generate initial random population."""
        population = []
        for _ in range(size):
            chromosome = FleetChromosome(
                workers=random.randint(WORKERS_MIN, WORKERS_MAX),
                arbiter=random.choice(VALID_ARBITERS),
                timeout=random.randint(TIMEOUT_MIN, TIMEOUT_MAX),
                consensus_type=random.choice(VALID_CONSENSUS),
                retry_limit=random.randint(1, 5),
                diversity_weight=round(random.uniform(0.0, 1.0), 2)
            )
            population.append(chromosome)
        self.population = population  # Fix: assign to self.population
        return population

    def evolve_one_generation(self, tasks: List[Dict]) -> Dict:
        """
        Execute one generation of evolution.

        Returns:
            Stats about the generation
        """
        # Evaluate fitness
        for chromosome in self.population:
            chromosome.fitness = calculate_fitness(chromosome, tasks)

        # Sort by fitness
        self.population.sort(key=lambda c: c.fitness or 0.0, reverse=True)

        # Track best
        if self.population[0].fitness and self.population[0].fitness > self.best_fitness:
            self.best_fitness = self.population[0].fitness
            self.best_chromosome = self.population[0]

        # Selection (top 50%)
        elite_size = self.population_size // 2
        elite = self.population[:elite_size]

        # Crossover + Mutation to create new generation
        offspring = []
        while len(offspring) < self.population_size - elite_size:
            # Tournament selection
            parent1 = max(random.sample(elite, min(3, len(elite))), key=lambda c: c.fitness or 0.0)
            parent2 = max(random.sample(elite, min(3, len(elite))), key=lambda c: c.fitness or 0.0)

            # Crossover
            child1, child2 = crossover(parent1, parent2)

            # Mutation
            child1 = mutate(child1, self.mutation_rate)
            child2 = mutate(child2, self.mutation_rate)

            offspring.extend([child1, child2])

        # New population = elite + offspring
        self.population = elite + offspring[:self.population_size - elite_size]
        self.generation += 1

        # Stats
        fitnesses = [c.fitness for c in self.population if c.fitness is not None]
        return {
            'generation': self.generation,
            'best_fitness': self.best_fitness,
            'avg_fitness': sum(fitnesses) / len(fitnesses) if fitnesses else 0.0,
            'min_fitness': min(fitnesses) if fitnesses else 0.0,
            'population_size': len(self.population)
        }

    def evolve(self, generations: int, tasks_per_eval: List[Dict]) -> FleetChromosome:
        """
        Run evolution for N generations.

        Args:
            generations: Number of generations to evolve
            tasks_per_eval: Test tasks for fitness evaluation

        Returns:
            Best chromosome found
        """
        # Initialize population if empty
        if not self.population:
            self.population = self.create_random_population(self.population_size)

        # Evolve
        for gen in range(generations):
            stats = self.evolve_one_generation(tasks_per_eval)
            print(f"Generation {stats['generation']}: "
                  f"best={stats['best_fitness']:.4f}, "
                  f"avg={stats['avg_fitness']:.4f}, "
                  f"min={stats['min_fitness']:.4f}")

            # Store lineage every 10 generations
            if gen % 10 == 0 and REST_AVAILABLE:
                self.store_lineage()

        # Final lineage storage
        if REST_AVAILABLE:
            self.store_lineage()

        return self.best_chromosome

    def store_lineage(self):
        """Store generation lineage to local JSON and POST convergence to REST API.

        Replaces direct PostgreSQL INSERT into ga.strategies / ga.lineage tables.
        - Population snapshots are saved to local JSON (ga_fleet_lineage.json).
        - Generation-level summary is POSTed to /ga/convergence for central tracking.
        """
        try:
            from datetime import datetime

            # --- Local JSON storage (replaces ga.strategies table) ---
            lineage_data = {}
            if LINEAGE_PATH.exists():
                try:
                    with open(LINEAGE_PATH, 'r') as f:
                        lineage_data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    lineage_data = {}

            if 'generations' not in lineage_data:
                lineage_data['generations'] = {}

            gen_key = str(self.generation)
            lineage_data['generations'][gen_key] = {
                'timestamp': datetime.now().isoformat(),
                'chromosomes': [c.to_dict() for c in self.population]
            }

            with open(LINEAGE_PATH, 'w') as f:
                json.dump(lineage_data, f, indent=2)

            # --- REST API convergence tracking ---
            fitnesses = [c.fitness for c in self.population if c.fitness is not None]
            if fitnesses:
                requests.post(f'{API_BASE}/ga/convergence', json={
                    'generation': self.generation,
                    'best_fitness': max(fitnesses),
                    'avg_fitness': sum(fitnesses) / len(fitnesses),
                    'min_fitness': min(fitnesses),
                    'population_size': len(self.population),
                    'use_case': 'fleet-orchestration'
                })

        except Exception as e:
            print(f"Error storing lineage: {e}")

    def integrate_with_thompson_sampling(self) -> Dict:
        """
        Update Thompson Sampling bandit state with GA-discovered strategies
        via REST API.

        Returns:
            Integration stats
        """
        if not REST_AVAILABLE or not self.best_chromosome:
            return {'status': 'skipped', 'reason': 'no_rest_or_best'}

        try:
            # Convert best chromosome to strategy name
            strategy_name = f"ga_gen{self.generation}_{self.best_chromosome.arbiter}"

            # Check if strategy exists via REST API
            resp = requests.get(f'{API_BASE}/ga/strategies')
            resp.raise_for_status()
            all_strategies = resp.json()
            if isinstance(all_strategies, dict):
                all_strategies = all_strategies.get('strategies', all_strategies.get('rows', []))

            existing = None
            for s in all_strategies:
                if isinstance(s, dict) and s.get('strategy') == strategy_name:
                    existing = s
                    break

            success_weight = int(self.best_fitness * 10)

            if existing:
                # Update existing strategy: increment alpha and total_reward
                new_alpha = existing.get('alpha', 1) + success_weight
                new_beta = existing.get('beta', 1)
                new_total_reward = existing.get('total_reward', 0) + self.best_fitness
                new_avg_reward = new_total_reward / (new_alpha + new_beta) if (new_alpha + new_beta) > 0 else 0

                resp = requests.post(f'{API_BASE}/ga/strategies', json={
                    'strategy': strategy_name,
                    'successes': existing.get('successes', 0),
                    'failures': existing.get('failures', 0),
                    'alpha': new_alpha,
                    'beta': new_beta,
                    'total_reward': new_total_reward,
                    'avg_reward': new_avg_reward
                })
                resp.raise_for_status()
            else:
                # Insert new strategy
                resp = requests.post(f'{API_BASE}/ga/strategies', json={
                    'strategy': strategy_name,
                    'successes': success_weight,
                    'failures': 0,
                    'alpha': success_weight + 1,
                    'beta': 1,
                    'total_reward': self.best_fitness,
                    'avg_reward': self.best_fitness
                })
                resp.raise_for_status()

            return {
                'status': 'success',
                'strategy': strategy_name,
                'fitness': self.best_fitness,
                'generation': self.generation
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}


if __name__ == '__main__':
    # Demo usage
    print("Fleet Genetic Algorithm Engine")
    print("=" * 50)

    # Create optimizer
    optimizer = FleetGeneticOptimizer(population_size=20, mutation_rate=0.15)

    # Sample test tasks
    test_tasks = [
        {'type': 'code_review', 'complexity': 'medium'},
        {'type': 'code_generation', 'complexity': 'high'},
        {'type': 'consensus', 'complexity': 'low'},
    ] * 10

    # Evolve for 50 generations
    print("\nEvolving fleet strategies...")
    best = optimizer.evolve(generations=50, tasks_per_eval=test_tasks)

    print("\nBest Strategy Found:")
    print(f"  Workers: {best.workers}")
    print(f"  Arbiter: {best.arbiter}")
    print(f"  Timeout: {best.timeout}s")
    print(f"  Consensus: {best.consensus_type}")
    print(f"  Retry Limit: {best.retry_limit}")
    print(f"  Diversity Weight: {best.diversity_weight}")
    print(f"  Fitness: {best.fitness:.4f}")

    # Integrate with Thompson Sampling
    if REST_AVAILABLE:
        print("\nIntegrating with Thompson Sampling...")
        result = optimizer.integrate_with_thompson_sampling()
        print(f"  Status: {result['status']}")
        if result['status'] == 'success':
            print(f"  Strategy: {result['strategy']}")
