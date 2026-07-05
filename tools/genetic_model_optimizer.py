#!/usr/bin/env python3
"""
Genetic Algorithm for Model-Task Mapping Optimization

Evolves optimal model selections for each task type based on REAL execution data.
Uses existing monitoring.execution_summary as fitness feedback.

Architecture:
- Chromosome: Dict mapping task_type → model_id
- Fitness: quality * 0.6 - (cost * 100) * 0.2 - (latency_ms / 1000) * 0.2
- Evolution: Tournament selection + crossover + mutation
- Population: 30 strategies
- Data source: PostgreSQL monitoring.execution_summary (actual production results)
"""

import psycopg2
from psycopg2 import sql
import json
import random
import re
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

# Database connection
def get_db():
    return psycopg2.connect(
        host='aio-01',
        port=5433,
        user='sfloess',
        database='learning'
    )

# Task types we optimize for
TASK_TYPES = [
    'code_generation',
    'code_review',
    'research',
    'math_reasoning',
    'general_qa',
    'creative_writing',
    'security_analysis'
]

class Chromosome:
    """Represents one model selection strategy"""

    def __init__(self, genes=None, models_by_task=None):
        """
        genes: Dict[task_type] -> model_id
        models_by_task: Dict[task_type] -> List[model_id] (available models)
        """
        if genes:
            self.genes = genes
        else:
            # Random initialization
            self.genes = {}
            for task_type in TASK_TYPES:
                available = models_by_task.get(task_type, [])
                if available:
                    self.genes[task_type] = random.choice(available)
                else:
                    self.genes[task_type] = None

        self.fitness = None

    def __repr__(self):
        return f"Chromosome(fitness={self.fitness:.3f if self.fitness else 'None'}, genes={self.genes})"

class GeneticOptimizer:
    """Genetic algorithm for model-task optimization"""

    def __init__(self, population_size=30, mutation_rate=0.15, tournament_size=5):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.db = get_db()
        self.cursor = self.db.cursor()

        # Load available models per task from free_models + execution history
        self.models_by_task = self._load_models_by_task()

        # Load execution history for fitness evaluation
        self.execution_history = self._load_execution_history()

    def _load_models_by_task(self):
        """Load models that have been used for each task type"""
        # Use workflow.worker_results which has actual task data
        self.cursor.execute("""
            SELECT DISTINCT model
            FROM workflow.worker_results
            WHERE model IS NOT NULL
              AND outcome = 'success'
            ORDER BY model
        """)

        models_used = [row[0] for row in self.cursor.fetchall()]

        # Add free models as potential candidates
        self.cursor.execute("SELECT DISTINCT model_id FROM learning.free_models LIMIT 50")
        free_models = [row[0] for row in self.cursor.fetchall()]

        # Combine: models with history + free models
        all_candidate_models = list(set(models_used + free_models))

        # All tasks can use any model (we'll learn which is best)
        models_by_task = {}
        for task_type in TASK_TYPES:
            models_by_task[task_type] = all_candidate_models

        return models_by_task

    def _load_execution_history(self, days=30):
        """Load recent execution history for fitness calculation"""
        # Use workflow.worker_results which has real task data
        self.cursor.execute("""
            SELECT
                wr.model,
                wr.task_assigned,
                wr.confidence,
                wr.cost_usd,
                wr.duration_ms,
                wr.outcome,
                we.created_at
            FROM workflow.worker_results wr
            JOIN workflow.executions we ON wr.workflow_execution_id = we.id
            WHERE we.created_at > NOW() - INTERVAL '%s days'
              AND wr.outcome = 'success'
              AND wr.confidence IS NOT NULL
        """, (days,))

        history = defaultdict(list)
        for row in self.cursor.fetchall():
            model, task, confidence, cost, duration, outcome, ts = row

            # Classify task type by keywords
            task_lower = task.lower() if task else ""
            task_type = self._classify_task(task_lower)

            history[(model, task_type)].append({
                'quality': confidence or 0.5,
                'cost': cost or 0.0,
                'duration_ms': duration or 2000,
                'outcome': outcome,
                'timestamp': ts
            })

        return dict(history)

    def _classify_task(self, task_text):
        """Classify task into one of our task types based on keywords"""
        task_text = task_text.lower()

        if any(kw in task_text for kw in ['write', 'implement', 'create', 'code', 'function', 'class', 'script']):
            return 'code_generation'
        elif any(kw in task_text for kw in ['review', 'analyze', 'check', 'quality', 'rate', 'examine']):
            return 'code_review'
        elif any(kw in task_text for kw in ['research', 'find', 'search', 'investigate', 'discover']):
            return 'research'
        elif any(kw in task_text for kw in ['math', 'calculate', 'factorial', '+', '-', '*', '/', 'equation']):
            return 'math_reasoning'
        elif any(kw in task_text for kw in ['security', 'vulnerability', 'audit', 'attack', 'exploit']):
            return 'security_analysis'
        elif any(kw in task_text for kw in ['write', 'story', 'creative', 'poem', 'article']):
            return 'creative_writing'
        else:
            return 'general_qa'

    def calculate_fitness(self, chromosome):
        """
        Fitness = quality * 0.6 - (cost * 100) * 0.2 - (latency_seconds) * 0.2

        Higher fitness = better strategy
        Based on REAL execution data from monitoring.execution_summary
        """
        total_quality = 0
        total_cost = 0
        total_latency = 0
        tasks_evaluated = 0

        for task_type, model in chromosome.genes.items():
            if model is None:
                continue

            # Get execution history for this model+task combo
            history = self.execution_history.get((model, task_type), [])

            if history:
                # Use recent actual performance
                recent = history[-5:]  # Last 5 executions
                avg_quality = float(np.mean([float(h['quality']) for h in recent]))
                avg_cost = float(np.mean([float(h['cost']) for h in recent]))
                avg_latency = float(np.mean([float(h['duration_ms']) for h in recent])) / 1000.0  # ms -> seconds

                total_quality += avg_quality
                total_cost += avg_cost
                total_latency += avg_latency
                tasks_evaluated += 1
            else:
                # No history: Use conservative estimates
                # Free models: assume medium quality, zero cost, fast
                total_quality += 0.6
                total_cost += 0.0
                total_latency += 2.0
                tasks_evaluated += 1

        if tasks_evaluated == 0:
            return 0.0

        # Normalize by number of tasks
        avg_quality = total_quality / tasks_evaluated
        avg_cost = total_cost / tasks_evaluated
        avg_latency = total_latency / tasks_evaluated

        # Fitness function (higher = better)
        fitness = (avg_quality * 0.6) - (avg_cost * 100 * 0.2) - (avg_latency * 0.2)

        return fitness

    def create_initial_population(self):
        """Create initial population with mix of random + seeded strategies"""
        population = []

        # Seed 1: Use models that historically performed best
        best_per_task = {}
        for task_type in TASK_TYPES:
            candidates = []
            for model in self.models_by_task.get(task_type, []):
                history = self.execution_history.get((model, task_type), [])
                if history:
                    avg_quality = np.mean([h['quality'] for h in history])
                    candidates.append((model, avg_quality))

            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                best_per_task[task_type] = candidates[0][0]
            else:
                best_per_task[task_type] = None

        population.append(Chromosome(genes=best_per_task))

        # Seed 2-5: Hand-crafted strategies based on model names
        specialized_strategies = [
            # Code-focused strategy
            {task: model for task, model in {
                'code_generation': next((m for m in self.models_by_task.get('code_generation', []) if 'coder' in m.lower() or 'code' in m.lower()), None),
                'code_review': next((m for m in self.models_by_task.get('code_review', []) if 'llama' in m.lower() or 'qwen' in m.lower()), None),
            }.items()},

            # Reasoning-focused strategy
            {task: model for task, model in {
                'math_reasoning': next((m for m in self.models_by_task.get('math_reasoning', []) if 'deepseek' in m.lower() or 'llama-3.3' in m.lower()), None),
                'research': next((m for m in self.models_by_task.get('research', []) if 'gemini' in m.lower() or 'mistral' in m.lower()), None),
            }.items()},
        ]

        for strategy in specialized_strategies:
            # Fill in missing tasks with random models
            full_strategy = {}
            for task in TASK_TYPES:
                if task in strategy and strategy[task]:
                    full_strategy[task] = strategy[task]
                else:
                    available = self.models_by_task.get(task, [])
                    full_strategy[task] = random.choice(available) if available else None
            population.append(Chromosome(genes=full_strategy))

        # Rest: Random initialization
        while len(population) < self.population_size:
            population.append(Chromosome(models_by_task=self.models_by_task))

        # Calculate fitness for all
        for chromo in population:
            chromo.fitness = self.calculate_fitness(chromo)

        return population

    def tournament_selection(self, population):
        """Select one chromosome via tournament selection"""
        tournament = random.sample(population, self.tournament_size)
        return max(tournament, key=lambda c: c.fitness or 0)

    def crossover(self, parent1, parent2):
        """Single-point crossover"""
        child_genes = {}
        tasks = list(TASK_TYPES)
        crossover_point = random.randint(1, len(tasks) - 1)

        for i, task in enumerate(tasks):
            if i < crossover_point:
                child_genes[task] = parent1.genes.get(task)
            else:
                child_genes[task] = parent2.genes.get(task)

        return Chromosome(genes=child_genes)

    def mutate(self, chromosome):
        """Randomly change one task's model assignment"""
        if random.random() < self.mutation_rate:
            task_to_mutate = random.choice(TASK_TYPES)
            available = self.models_by_task.get(task_to_mutate, [])
            if available:
                chromosome.genes[task_to_mutate] = random.choice(available)

    def evolve_generation(self, population):
        """Create next generation via selection + crossover + mutation"""
        # Sort by fitness
        population.sort(key=lambda c: c.fitness or 0, reverse=True)

        # Elitism: Keep top 10%
        elite_size = max(1, self.population_size // 10)
        new_population = population[:elite_size]

        # Create rest via crossover + mutation
        while len(new_population) < self.population_size:
            parent1 = self.tournament_selection(population)
            parent2 = self.tournament_selection(population)
            child = self.crossover(parent1, parent2)
            self.mutate(child)
            child.fitness = self.calculate_fitness(child)
            new_population.append(child)

        return new_population

    def run(self, generations=50):
        """Run genetic algorithm for N generations"""
        print(f"Initializing population of {self.population_size} strategies...")
        population = self.create_initial_population()

        best_ever = max(population, key=lambda c: c.fitness or 0)

        print(f"Generation 0: Best fitness = {best_ever.fitness:.3f}")
        print(f"  Strategy: {best_ever.genes}\n")

        for gen in range(1, generations + 1):
            population = self.evolve_generation(population)

            current_best = max(population, key=lambda c: c.fitness or 0)
            avg_fitness = np.mean([c.fitness for c in population if c.fitness])

            if current_best.fitness > (best_ever.fitness or 0):
                best_ever = current_best
                print(f"Generation {gen}: NEW BEST! Fitness = {current_best.fitness:.3f} (avg = {avg_fitness:.3f})")
                print(f"  Strategy: {current_best.genes}\n")
            elif gen % 10 == 0:
                print(f"Generation {gen}: Best = {current_best.fitness:.3f}, Avg = {avg_fitness:.3f}")

        print("\n=== FINAL BEST STRATEGY ===")
        print(f"Fitness: {best_ever.fitness:.3f}")
        for task, model in best_ever.genes.items():
            print(f"  {task:20s} -> {model}")

        # Store in database
        self._store_best_strategy(best_ever)

        return best_ever

    def _store_best_strategy(self, chromosome):
        """Store evolved strategy in learning.model_capabilities"""
        print("\nStoring evolved strategy in database...")

        # Validate task types (whitelist allowed column names)
        ALLOWED_TASK_TYPES = [
            'general_qa', 'code_gen', 'analysis', 'research',
            'reasoning', 'creative', 'summarization'
        ]

        for task_type, model in chromosome.genes.items():
            if model is None:
                continue

            # Validate task_type
            if task_type not in ALLOWED_TASK_TYPES:
                print(f"⚠️  Skipping invalid task_type: {task_type}")
                continue

            # Get actual performance data
            history = self.execution_history.get((model, task_type), [])

            if history:
                recent = history[-10:]
                avg_quality = float(np.mean([float(h['quality']) for h in recent]))
                avg_latency = int(float(np.mean([float(h['duration_ms']) for h in recent])))
            else:
                avg_quality = 0.6  # Conservative estimate
                avg_latency = 2000

            # Update model_capabilities table (safe - task_type validated above)
            task_col = sql.Identifier(task_type)
            notes_value = f'GA evolved - fitness {chromosome.fitness:.3f}'

            query = sql.SQL("""
                INSERT INTO learning.model_capabilities
                (model_id, provider, {task_col}, avg_latency_ms, test_count, notes)
                VALUES (%s, 'evolved', %s, %s, 1, %s)
                ON CONFLICT (model_id) DO UPDATE SET
                  {task_col} = GREATEST(learning.model_capabilities.{task_col}, EXCLUDED.{task_col}),
                  avg_latency_ms = EXCLUDED.avg_latency_ms,
                  test_count = learning.model_capabilities.test_count + 1,
                  notes = EXCLUDED.notes,
                  last_tested = NOW()
            """).format(task_col=task_col)

            self.cursor.execute(query, (model, avg_quality, avg_latency, notes_value))

        self.db.commit()
        print("Strategy stored in learning.model_capabilities ✅")

if __name__ == '__main__':
    print("=== Genetic Algorithm Model Optimizer ===\n")
    print("Using REAL execution data from monitoring.execution_summary")
    print("Optimizing model selection for 7 task types")
    print("Fitness = quality * 0.6 - (cost * 100) * 0.2 - (latency_seconds) * 0.2\n")

    optimizer = GeneticOptimizer(
        population_size=30,
        mutation_rate=0.15,
        tournament_size=5
    )

    best = optimizer.run(generations=50)

    print("\n✅ Optimization complete!")
    print("Results stored in learning.model_capabilities")
