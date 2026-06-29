#!/usr/bin/env python3
"""
Genetic Algorithm Evolution Loop for Multi-Model Routing Optimization

FIX 2 APPLIED: _chromosome_to_strategy() now walks the decision tree
to extract task_type_rules instead of leaving them as {}.

Implements:
1. Population initialization (25 random routing strategies)
2. Fitness evaluation via 10-fold cross-validation
3. NSGA-II multi-objective selection
4. Crossover (70% rate) + Mutation (20% rate)
5. Elitism (preserve top 20%)
6. Diversity filtering (reject >70% single vendor)
7. PostgreSQL logging (learning.ga_evolution)
8. Abort conditions (convergence, diversity violations, timeout)
9. Pareto frontier extraction and persistence

Usage:
    python3 ~/ga-routing/evolve_fixed.py --generations 50 --population 25
"""

import sys
import os
import argparse
import json
import time
import random
import numpy as np
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# Add ga-routing to path
sys.path.insert(0, str(Path.home() / 'ga-routing'))

from fitness_evaluator import FitnessEvaluator, FitnessMetrics, PostgreSQLConnection
from ga_operators import (
    Chromosome, crossover_routing, mutate_routing,
    select_nsga2, diversity_filter, create_toolbox
)


@dataclass
class GenerationStats:
    """Statistics for a single generation"""
    generation: int
    best_fitness: float
    avg_fitness: float
    diversity_score: float
    diversity_violations: int
    elapsed_time: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GAEvolutionHarness:
    """Main evolution harness with PostgreSQL logging and abort conditions"""

    def __init__(self,
                 population_size: int = 25,
                 num_generations: int = 50,
                 crossover_rate: float = 0.7,
                 mutation_rate: float = 0.2,
                 elitism_rate: float = 0.2,
                 db_host: str = "laptop-01",
                 log_table: str = "learning.ga_evolution"):

        self.population_size = population_size
        self.num_generations = num_generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elitism_rate = elitism_rate
        self.db_host = db_host
        self.log_table = log_table

        # Initialize components
        self.evaluator = FitnessEvaluator(db_host=db_host)
        self.db = PostgreSQLConnection(host=db_host)
        self.toolbox = create_toolbox(
            population_size=population_size,
            elitism_rate=elitism_rate
        )

        # Evolution state
        self.population: List[Chromosome] = []
        self.stats: List[GenerationStats] = []
        self.pareto_frontier: List[Tuple[Chromosome, FitnessMetrics]] = []

        # Abort conditions
        self.start_time = None
        self.last_improvement = 0
        self.best_fitness_history = []
        self.diversity_violation_count = 0

        # Constants
        self.MAX_RUNTIME_HOURS = 8
        self.MIN_IMPROVEMENT_THRESHOLD = 0.02  # 2% improvement
        self.MAX_STAGNATION_GENERATIONS = 10
        self.MAX_DIVERSITY_VIOLATION_RATE = 0.30  # 30%

        # Known task types from execution logs, mapped to numeric bins.
        # The decision tree splits on 'task_type' using a numeric threshold
        # in [0, 1].  We partition that range into bins so each known task
        # type occupies a slice.  When a tree path narrows a task_type range
        # to fall within a bin, we emit a task_type_rules entry for that
        # category.
        self.TASK_TYPE_BINS = {
            'code_generation':   (0.00, 0.20),
            'consensus':         (0.20, 0.40),
            'routing_decision':  (0.40, 0.60),
            'code_review':       (0.60, 0.80),
            'general':           (0.80, 1.00),
        }

    def initialize_database(self):
        """Create ga_evolution table if not exists"""
        self.db.connect()

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS learning.ga_evolution (
            id SERIAL PRIMARY KEY,
            generation INT NOT NULL,
            best_fitness FLOAT NOT NULL,
            avg_fitness FLOAT NOT NULL,
            diversity_score FLOAT NOT NULL,
            diversity_violations INT DEFAULT 0,
            elapsed_time FLOAT NOT NULL,
            timestamp TIMESTAMPTZ DEFAULT NOW(),
            metadata JSONB
        );

        CREATE INDEX IF NOT EXISTS idx_ga_evolution_generation
        ON learning.ga_evolution(generation);
        """

        with self.db.conn.cursor() as cursor:
            cursor.execute(create_table_sql)
            self.db.conn.commit()

        print(f"Database table {self.log_table} initialized")

    def initialize_population(self) -> List[Chromosome]:
        """Generate initial population of 25 random routing strategies"""
        print(f"Initializing population of {self.population_size} chromosomes...")

        population = []

        # Load execution logs for reference
        num_logs = self.evaluator.load_execution_logs(limit=1000)
        print(f"  Loaded {num_logs} execution logs for fitness evaluation")

        # Extract available models from logs
        available_models = set(log.model for log in self.evaluator.execution_logs)
        available_vendors = ['anthropic', 'openai', 'google', 'local']

        for i in range(self.population_size):
            chromosome = Chromosome()

            # Randomize permutation (vendor priorities)
            chromosome.permutation = random.sample(available_vendors, len(available_vendors))

            # Randomize thresholds
            chromosome.thresholds = {
                'quality_min': random.uniform(0.5, 0.9),
                'cost_max': random.uniform(0.001, 0.02),
                'latency_max': random.uniform(1.0, 10.0),
                'diversity_min': random.uniform(0.2, 0.5)
            }

            # Randomize decision tree depth (2-4 levels)
            chromosome.decision_tree = self._random_decision_tree(depth=random.randint(2, 4))

            population.append(chromosome)

        print(f"  Generated {len(population)} chromosomes")
        return population

    def _random_decision_tree(self, depth: int):
        """Generate random decision tree for routing"""
        from ga_operators import DecisionNode

        features = ['task_type', 'quality_threshold', 'cost_budget', 'latency_requirement']
        models = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'deepseek-coder', 'phi-4-mini']

        if depth == 0:
            # Leaf node
            return DecisionNode(model=random.choice(models))

        # Internal node
        node = DecisionNode(
            feature=random.choice(features),
            threshold=random.uniform(0.3, 0.7)
        )

        node.left = self._random_decision_tree(depth - 1)
        node.right = self._random_decision_tree(depth - 1)

        return node

    def evaluate_fitness(self, chromosome: Chromosome) -> FitnessMetrics:
        """
        Evaluate chromosome fitness using 10-fold cross-validation

        Returns: FitnessMetrics with multi-objective scores
        """
        # Convert chromosome to routing strategy dict
        strategy = self._chromosome_to_strategy(chromosome)

        # Run 10-fold cross-validation
        avg_metrics, fold_metrics = self.evaluator.cross_validate(strategy, k_folds=10)

        return avg_metrics

    # ------------------------------------------------------------------
    # FIX 2: Extract task_type_rules from chromosome.decision_tree
    # ------------------------------------------------------------------
    def _chromosome_to_strategy(self, chromosome: Chromosome) -> Dict[str, Any]:
        """Convert Chromosome to strategy dict for FitnessEvaluator.

        Walks the decision tree to extract concrete task_type routing
        rules.  Each root-to-leaf path that branches on 'task_type'
        constrains a numeric range; when that range overlaps a known
        task-type bin we emit a rule mapping that task type to the
        leaf's model.
        """
        # Map short model names used in decision-tree leaves to the
        # full model identifiers expected by the fitness evaluator.
        leaf_model_map = {
            'opus':           'claude-opus-4',
            'sonnet':         'claude-sonnet-4.5',
            'haiku':          'claude-haiku-3.5',
            'gpt-4o':         'gpt-4o',
            'gemini':         'gemini-pro',
            'deepseek-coder': 'deepseek-coder-java:finetuned',
            'phi-4-mini':     'phi-4-mini-routing:finetuned',
        }

        # Traverse the decision tree; collect routing rules by walking
        # all root-to-leaf paths and tracking the task_type interval.
        task_type_rules: Dict[str, str] = {}
        self._extract_rules_from_tree(
            chromosome.decision_tree,
            task_type_lo=0.0,
            task_type_hi=1.0,
            rules_out=task_type_rules,
            leaf_model_map=leaf_model_map,
        )

        # Vendor-to-model mapping for fallback from permutation
        vendor_to_model = {
            'anthropic': 'claude-sonnet-4.5',
            'openai': 'gpt-4o',
            'google': 'gemini-pro',
            'local': 'deepseek-coder-java:finetuned'
        }

        fallback_vendor = chromosome.permutation[0]

        strategy = {
            'task_type_rules': task_type_rules,
            'quality_threshold': chromosome.thresholds.get('quality_min', 0.7),
            'cost_limit': chromosome.thresholds.get('cost_max', 0.01),
            'fallback_model': vendor_to_model.get(fallback_vendor, 'claude-sonnet-4.5')
        }

        return strategy

    def _extract_rules_from_tree(
        self,
        node,
        task_type_lo: float,
        task_type_hi: float,
        rules_out: Dict[str, str],
        leaf_model_map: Dict[str, str],
    ) -> None:
        """Recursively walk the decision tree and populate *rules_out*.

        We track the cumulative task_type interval [lo, hi) along the
        current path.  When we reach a leaf, we check which known task-
        type bins overlap that interval and emit a rule for each.

        For non-task_type splits (cost_budget, quality_threshold, etc.)
        both children inherit the same task_type interval, so the leaf
        model is still associated with the correct task types.

        When multiple leaves map to the same task type, the last one
        written wins -- this is intentional: deeper / more-specific
        paths override shallower ones.
        """
        if node is None:
            return

        if node.is_leaf():
            # Resolve full model name
            model = leaf_model_map.get(node.model, node.model)

            # Check which task-type bins overlap [task_type_lo, task_type_hi)
            for task_name, (bin_lo, bin_hi) in self.TASK_TYPE_BINS.items():
                # Overlap exists when lo < bin_hi AND hi > bin_lo
                if task_type_lo < bin_hi and task_type_hi > bin_lo:
                    rules_out[task_name] = model
            return

        threshold = node.threshold if node.threshold is not None else 0.5

        if node.feature == 'task_type':
            # Left child: task_type < threshold  => narrow hi
            # Right child: task_type >= threshold => narrow lo
            self._extract_rules_from_tree(
                node.left,
                task_type_lo=task_type_lo,
                task_type_hi=min(task_type_hi, threshold),
                rules_out=rules_out,
                leaf_model_map=leaf_model_map,
            )
            self._extract_rules_from_tree(
                node.right,
                task_type_lo=max(task_type_lo, threshold),
                task_type_hi=task_type_hi,
                rules_out=rules_out,
                leaf_model_map=leaf_model_map,
            )
        else:
            # Non-task_type feature -- both branches keep the same
            # task_type interval.
            self._extract_rules_from_tree(
                node.left,
                task_type_lo=task_type_lo,
                task_type_hi=task_type_hi,
                rules_out=rules_out,
                leaf_model_map=leaf_model_map,
            )
            self._extract_rules_from_tree(
                node.right,
                task_type_lo=task_type_lo,
                task_type_hi=task_type_hi,
                rules_out=rules_out,
                leaf_model_map=leaf_model_map,
            )

    def check_abort_conditions(self, generation: int) -> Tuple[bool, str]:
        """
        Check if evolution should abort

        Returns: (should_abort, reason)
        """
        # Condition 1: Runtime timeout (8 hours)
        elapsed = time.time() - self.start_time
        if elapsed > self.MAX_RUNTIME_HOURS * 3600:
            return True, f"Runtime timeout ({self.MAX_RUNTIME_HOURS}h exceeded)"

        # Condition 2: No improvement >2% for 10 generations
        if len(self.best_fitness_history) >= self.MAX_STAGNATION_GENERATIONS:
            recent_best = max(self.best_fitness_history[-self.MAX_STAGNATION_GENERATIONS:])
            overall_best = max(self.best_fitness_history)

            if overall_best > 0 and (recent_best - overall_best) / overall_best < self.MIN_IMPROVEMENT_THRESHOLD:
                return True, f"Stagnation detected (no >2% improvement for {self.MAX_STAGNATION_GENERATIONS} generations)"

        # Condition 3: Diversity violations >30%
        total_offspring = generation * self.population_size
        if total_offspring > 0:
            violation_rate = self.diversity_violation_count / total_offspring
            if violation_rate > self.MAX_DIVERSITY_VIOLATION_RATE:
                return True, f"Diversity violations exceed 30% ({violation_rate:.1%})"

        return False, ""

    def log_generation(self, gen_stats: GenerationStats):
        """Log generation statistics to PostgreSQL"""
        self.db.connect()

        insert_sql = """
        INSERT INTO learning.ga_evolution
        (generation, best_fitness, avg_fitness, diversity_score,
         diversity_violations, elapsed_time, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        metadata = {
            'population_size': self.population_size,
            'crossover_rate': self.crossover_rate,
            'mutation_rate': self.mutation_rate,
            'elitism_rate': self.elitism_rate
        }

        with self.db.conn.cursor() as cursor:
            cursor.execute(insert_sql, (
                gen_stats.generation,
                gen_stats.best_fitness,
                gen_stats.avg_fitness,
                gen_stats.diversity_score,
                gen_stats.diversity_violations,
                gen_stats.elapsed_time,
                json.dumps(metadata)
            ))
            self.db.conn.commit()

    def extract_pareto_frontier(self) -> List[Tuple[Chromosome, FitnessMetrics]]:
        """
        Extract Pareto frontier from final population

        Returns: List of (chromosome, fitness_metrics) on Pareto front
        """
        from ga_operators import _fast_non_dominated_sort

        # Evaluate all individuals
        population_with_fitness = []
        for chromosome in self.population:
            fitness = self.evaluate_fitness(chromosome)
            population_with_fitness.append((chromosome, fitness))

        # Convert to fitness tuples for Pareto sorting
        fitnesses = [fit.to_tuple() for _, fit in population_with_fitness]

        # Get first Pareto front
        fronts = _fast_non_dominated_sort(
            [chrom for chrom, _ in population_with_fitness],
            fitnesses
        )

        # Extract first front with fitness metrics
        pareto_frontier = []
        for chromosome in fronts[0]:
            # Find corresponding fitness
            idx = [c for c, _ in population_with_fitness].index(chromosome)
            fitness = population_with_fitness[idx][1]
            pareto_frontier.append((chromosome, fitness))

        return pareto_frontier

    def save_pareto_frontier(self, output_path: str):
        """Save Pareto frontier to JSON"""
        frontier_data = []

        for chromosome, fitness in self.pareto_frontier:
            frontier_data.append({
                'chromosome': {
                    'permutation': chromosome.permutation,
                    'thresholds': chromosome.thresholds,
                    'decision_tree': self._serialize_tree(chromosome.decision_tree)
                },
                'fitness': {
                    'success_rate': fitness.success_rate,
                    'latency_p95': fitness.latency_p95,
                    'avg_cost': fitness.avg_cost,
                    'diversity_score': fitness.diversity_score,
                    'weighted_fitness': fitness.weighted_fitness()
                }
            })

        with open(output_path, 'w') as f:
            json.dump({
                'pareto_frontier': frontier_data,
                'num_solutions': len(frontier_data),
                'timestamp': datetime.now().isoformat(),
                'config': {
                    'population_size': self.population_size,
                    'num_generations': len(self.stats),
                    'crossover_rate': self.crossover_rate,
                    'mutation_rate': self.mutation_rate,
                    'elitism_rate': self.elitism_rate
                }
            }, f, indent=2)

        print(f"Pareto frontier saved to {output_path} ({len(frontier_data)} solutions)")

    def _serialize_tree(self, node):
        """Serialize decision tree node to JSON-compatible dict"""
        from ga_operators import DecisionNode

        if node.is_leaf():
            return {'model': node.model}

        return {
            'feature': node.feature,
            'threshold': node.threshold,
            'left': self._serialize_tree(node.left),
            'right': self._serialize_tree(node.right)
        }

    def run_evolution(self):
        """Main evolution loop with logging and abort conditions"""
        print("=" * 80)
        print("GENETIC ALGORITHM EVOLUTION - Multi-Model Routing Optimization")
        print("=" * 80)
        print(f"Population size: {self.population_size}")
        print(f"Generations: {self.num_generations}")
        print(f"Crossover rate: {self.crossover_rate:.1%}")
        print(f"Mutation rate: {self.mutation_rate:.1%}")
        print(f"Elitism rate: {self.elitism_rate:.1%}")
        print("=" * 80)
        print()

        # Initialize database
        self.initialize_database()

        # Initialize population
        self.population = self.initialize_population()
        self.start_time = time.time()

        # Evolution loop
        for generation in range(self.num_generations):
            gen_start = time.time()

            print(f"\n--- Generation {generation + 1}/{self.num_generations} ---")

            # Step 1: Evaluate fitness for all individuals
            print(f"  Evaluating fitness (10-fold CV)...")
            population_fitness = []
            for i, chromosome in enumerate(self.population):
                fitness = self.evaluate_fitness(chromosome)
                population_fitness.append((chromosome, fitness))

                if (i + 1) % 5 == 0:
                    print(f"    {i + 1}/{len(self.population)} evaluated")

            # Sort by weighted fitness
            population_fitness.sort(key=lambda x: x[1].weighted_fitness(), reverse=True)

            # Extract statistics
            best_fitness = population_fitness[0][1].weighted_fitness()
            avg_fitness = np.mean([f.weighted_fitness() for _, f in population_fitness])
            avg_diversity = np.mean([f.diversity_score for _, f in population_fitness])

            self.best_fitness_history.append(best_fitness)

            # Step 2: Check abort conditions
            should_abort, abort_reason = self.check_abort_conditions(generation)

            if should_abort:
                print(f"\nABORT: {abort_reason}")
                break

            # Step 3: Selection (NSGA-II)
            print(f"  Selection (NSGA-II)...")

            # Preserve elite
            num_elite = int(self.population_size * self.elitism_rate)
            elite = [chrom for chrom, _ in population_fitness[:num_elite]]

            # Select remaining via NSGA-II
            num_offspring = self.population_size - num_elite

            # Multi-objective fitness function for NSGA-II
            def fitness_func(chromosome: Chromosome) -> Tuple[float, float, float]:
                fitness = self.evaluate_fitness(chromosome)
                return fitness.to_tuple()

            selected = select_nsga2(
                [chrom for chrom, _ in population_fitness],
                k=num_offspring,
                fitness_func=fitness_func
            )

            # Step 4: Crossover (70% rate)
            print(f"  Crossover (rate={self.crossover_rate:.1%})...")
            offspring = []

            for i in range(0, len(selected), 2):
                if i + 1 < len(selected):
                    parent1 = selected[i]
                    parent2 = selected[i + 1]

                    if random.random() < self.crossover_rate:
                        child1, child2 = crossover_routing(parent1, parent2)
                        offspring.extend([child1, child2])
                    else:
                        offspring.extend([parent1.copy(), parent2.copy()])
                else:
                    offspring.append(selected[i].copy())

            # Step 5: Mutation (20% rate)
            print(f"  Mutation (rate={self.mutation_rate:.1%})...")
            for i, individual in enumerate(offspring):
                if random.random() < self.mutation_rate:
                    mutated, = mutate_routing(individual, indpb=0.2)
                    offspring[i] = mutated

            # Step 6: Diversity filtering
            print(f"  Diversity filtering (>70% vendor rejection)...")
            filtered_offspring = []
            diversity_violations = 0

            # Use execution logs for diversity check
            execution_history = [
                {
                    'task_type': random.random(),
                    'cost_budget': random.uniform(0.001, 0.01),
                    'quality_requirement': random.uniform(0.6, 0.9)
                }
                for _ in range(100)
            ]

            for individual in offspring:
                if diversity_filter(individual, execution_history):
                    filtered_offspring.append(individual)
                else:
                    diversity_violations += 1
                    self.diversity_violation_count += 1

            # Step 7: Replace population (elite + filtered offspring)
            self.population = elite + filtered_offspring

            # Pad if needed (diversity filter removed too many)
            while len(self.population) < self.population_size:
                self.population.append(Chromosome())

            # Step 8: Log generation stats
            gen_elapsed = time.time() - gen_start
            total_elapsed = time.time() - self.start_time

            gen_stats = GenerationStats(
                generation=generation + 1,
                best_fitness=best_fitness,
                avg_fitness=avg_fitness,
                diversity_score=avg_diversity,
                diversity_violations=diversity_violations,
                elapsed_time=total_elapsed,
                timestamp=datetime.now().isoformat()
            )

            self.stats.append(gen_stats)
            self.log_generation(gen_stats)

            # Print summary
            print(f"\n  Summary:")
            print(f"    Best fitness:  {best_fitness:.6f}")
            print(f"    Avg fitness:   {avg_fitness:.6f}")
            print(f"    Diversity:     {avg_diversity:.3f}")
            print(f"    Violations:    {diversity_violations}/{len(offspring)} ({diversity_violations/max(len(offspring),1):.1%})")
            print(f"    Gen time:      {gen_elapsed:.1f}s")
            print(f"    Total time:    {total_elapsed/60:.1f}min")

        # Step 9: Extract Pareto frontier
        print(f"\n--- Evolution Complete ---")
        print(f"Extracting Pareto frontier...")
        self.pareto_frontier = self.extract_pareto_frontier()

        print(f"\nFinal Results:")
        print(f"  Generations completed: {len(self.stats)}")
        print(f"  Best fitness: {max(self.best_fitness_history):.6f}")
        print(f"  Pareto frontier size: {len(self.pareto_frontier)}")
        print(f"  Total runtime: {(time.time() - self.start_time)/60:.1f}min")

        # Save Pareto frontier
        output_path = Path.home() / 'ga-routing' / 'pareto_frontier.json'
        self.save_pareto_frontier(str(output_path))

        # Close database
        self.evaluator.close()
        self.db.close()

        print("\nEvolution complete")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description='GA Routing Evolution')
    parser.add_argument('--population', type=int, default=25, help='Population size')
    parser.add_argument('--generations', type=int, default=50, help='Number of generations')
    parser.add_argument('--crossover-rate', type=float, default=0.7, help='Crossover rate')
    parser.add_argument('--mutation-rate', type=float, default=0.2, help='Mutation rate')
    parser.add_argument('--elitism-rate', type=float, default=0.2, help='Elitism rate')
    parser.add_argument('--db-host', type=str, default='laptop-01', help='PostgreSQL host')

    args = parser.parse_args()

    # Create harness
    harness = GAEvolutionHarness(
        population_size=args.population,
        num_generations=args.generations,
        crossover_rate=args.crossover_rate,
        mutation_rate=args.mutation_rate,
        elitism_rate=args.elitism_rate,
        db_host=args.db_host
    )

    # Run evolution
    harness.run_evolution()


if __name__ == '__main__':
    main()
