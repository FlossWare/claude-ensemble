#!/usr/bin/env python3
"""
Fleet Genetic Algorithm Engine
Evolves optimal fleet orchestration strategies via genetic algorithm.
Integrates with Thompson Sampling and PostgreSQL continual learning.
"""

import random
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

# PostgreSQL integration with fallback
try:
    from postgres_adapter import get_db, OUTCOMES
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
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
# All available models (27 local + 5 cloud placeholders)
VALID_ARBITERS = [
    # Local ollama models (actually available)
    'phi3.5:latest', 'qwen2.5-coder:7b', 'gemma3:4b', 'mistral:latest',
    'llama3.3:latest', 'phi4:latest', 'granite3.3:latest', 'qwen2.5:latest',
    'gemma2:latest', 'codellama:latest', 'codegemma:latest', 'nous-hermes2:latest',
    'dolphin-llama3:latest', 'magicoder:latest', 'starcoder:latest', 'codegeex4:latest',
    'exaone-deep:latest', 'qwen2-math:latest', 'mathstral:latest', 'granite3.1-moe:latest',
    'granite3-moe:latest', 'falcon3:latest', 'medgemma:latest', 'sqlcoder:latest',
    'llama2-uncensored:latest', 'medllama2:latest', 'meditron:latest',
    # Cloud API placeholders (for future use)
    'opus', 'sonnet', 'haiku', 'gpt4o', 'gemini'
]


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
    Integrates with PostgreSQL continual learning and Thompson Sampling.
    """

    def __init__(self, population_size: int = 20, mutation_rate: float = 0.1):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.population: List[FleetChromosome] = []
        self.generation = 0
        self.best_chromosome: Optional[FleetChromosome] = None
        self.best_fitness = 0.0

        # PostgreSQL connection
        self.db = get_db() if POSTGRES_AVAILABLE else None

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
            if gen % 10 == 0 and self.db:
                self.store_lineage()

        # Final lineage storage
        if self.db:
            self.store_lineage()

        return self.best_chromosome

    def store_lineage(self):
        """Store generation lineage to PostgreSQL ga.strategies and ga.lineage tables."""
        if not self.db:
            return

        try:
            cursor = self.db.cursor()

            # Ensure schema exists
            cursor.execute("""
                CREATE SCHEMA IF NOT EXISTS ga;

                CREATE TABLE IF NOT EXISTS ga.strategies (
                    id SERIAL PRIMARY KEY,
                    generation INT NOT NULL,
                    workers INT NOT NULL,
                    arbiter TEXT NOT NULL,
                    timeout INT NOT NULL,
                    consensus_type TEXT NOT NULL,
                    retry_limit INT NOT NULL,
                    diversity_weight FLOAT NOT NULL,
                    fitness FLOAT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS ga.lineage (
                    id SERIAL PRIMARY KEY,
                    generation INT NOT NULL,
                    parent1_id INT,
                    parent2_id INT,
                    child_id INT REFERENCES ga.strategies(id),
                    mutation_applied BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_generation ON ga.strategies(generation);
                CREATE INDEX IF NOT EXISTS idx_fitness ON ga.strategies(fitness DESC);
            """)

            # Store current population
            for chromosome in self.population:
                cursor.execute("""
                    INSERT INTO ga.strategies
                    (generation, workers, arbiter, timeout, consensus_type, retry_limit, diversity_weight, fitness)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.generation,
                    chromosome.workers,
                    chromosome.arbiter,
                    chromosome.timeout,
                    chromosome.consensus_type,
                    chromosome.retry_limit,
                    chromosome.diversity_weight,
                    chromosome.fitness
                ))

            self.db.commit()
            cursor.close()
        except Exception as e:
            print(f"Error storing lineage: {e}")

    def integrate_with_thompson_sampling(self) -> Dict:
        """
        Update Thompson Sampling bandit state with GA-discovered strategies.

        Returns:
            Integration stats
        """
        if not self.db or not self.best_chromosome:
            return {'status': 'skipped', 'reason': 'no_db_or_best'}

        try:
            cursor = self.db.cursor()

            # Convert best chromosome to strategy name
            strategy_name = f"ga_gen{self.generation}_{self.best_chromosome.arbiter}"

            # Check if strategy exists in Thompson Sampling
            cursor.execute("""
                SELECT strategy, alpha, beta FROM learning.strategy_performance
                WHERE strategy = %s
            """, (strategy_name,))

            result = cursor.fetchone()

            if result:
                # Update existing strategy
                alpha, beta = result[1], result[2]
                # Bias toward success based on GA fitness
                success_weight = int(self.best_fitness * 10)
                cursor.execute("""
                    UPDATE learning.strategy_performance
                    SET alpha = alpha + %s,
                        total_reward = total_reward + %s,
                        avg_reward = total_reward / (alpha + beta),
                        last_updated = NOW()
                    WHERE strategy = %s
                """, (success_weight, self.best_fitness, strategy_name))
            else:
                # Insert new strategy
                success_weight = int(self.best_fitness * 10)
                cursor.execute("""
                    INSERT INTO learning.strategy_performance
                    (strategy, successes, failures, alpha, beta, total_reward, avg_reward)
                    VALUES (%s, %s, 0, %s, 1, %s, %s)
                """, (strategy_name, success_weight, success_weight + 1, self.best_fitness, self.best_fitness))

            self.db.commit()
            cursor.close()

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
    if POSTGRES_AVAILABLE:
        print("\nIntegrating with Thompson Sampling...")
        result = optimizer.integrate_with_thompson_sampling()
        print(f"  Status: {result['status']}")
        if result['status'] == 'success':
            print(f"  Strategy: {result['strategy']}")
