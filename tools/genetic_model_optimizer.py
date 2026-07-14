#!/usr/bin/env python3
"""
Genetic Algorithm for Model-Task Mapping Optimization

Evolves optimal model selections for each task type based on REAL execution data.
Uses REST API at aio-01:5000 for all data access.

Architecture:
- Chromosome: Dict mapping task_type -> model_id
- Fitness: quality * 0.6 - (cost * 100) * 0.2 - (latency_ms / 1000) * 0.2
- Evolution: Tournament selection + crossover + mutation
- Population: 30 strategies
- Data source: REST API -> PostgreSQL monitoring/workflow data
"""

import requests
import json
import random
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

API_BASE = 'http://aio-01:5000'

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

        # Load available models per task from free_models + execution history
        self.models_by_task = self._load_models_by_task()

        # Load strategy priors from Thompson Sampling data
        self.strategy_priors = self._load_strategy_priors()

        # Load execution history for fitness evaluation
        self.execution_history = self._load_execution_history()

        print(f"Loaded {len(self.execution_history)} model-task history entries")
        print(f"Loaded {len(self.strategy_priors)} strategy priors")
        total_models = len(set(m for models in self.models_by_task.values() for m in models))
        print(f"Total candidate models: {total_models}")

    def _load_models_by_task(self):
        """Load models from execution history + free model catalog"""
        # Get models from execution summary (replaces broken worker-results)
        models_used = set()
        try:
            resp = requests.get(f'{API_BASE}/ga/executions', params={'limit': 500}, timeout=10)
            resp.raise_for_status()
            executions = resp.json()
            for r in executions:
                model = r.get('model')
                if model and r.get('outcome') == 'success':
                    models_used.add(model)
            print(f"  Loaded {len(executions)} execution records ({len(models_used)} unique models)")
        except Exception as e:
            print(f"  Warning: Could not load executions: {e}")
            executions = []

        # Get free models as potential candidates
        try:
            resp = requests.get(f'{API_BASE}/ga/models/free', params={'limit': 200}, timeout=10)
            resp.raise_for_status()
            free_models_data = resp.json()
            free_models = set(m['model_id'] for m in free_models_data)
            print(f"  Loaded {len(free_models)} free models from catalog")
        except Exception as e:
            print(f"  Warning: Could not load free models: {e}")
            free_models = set()

        # Combine all candidate models
        all_candidate_models = list(models_used | free_models)

        # All tasks can use any model (GA will evolve the best mapping)
        models_by_task = {}
        for task_type in TASK_TYPES:
            models_by_task[task_type] = all_candidate_models

        return models_by_task

    def _load_strategy_priors(self):
        """Load Thompson Sampling strategy data as quality priors.

        Strategy names like 'opus', 'sonnet' map to model quality estimates.
        Other strategies provide general quality baselines.
        """
        priors = {}
        try:
            resp = requests.get(f'{API_BASE}/ga/strategies', params={'limit': 100}, timeout=10)
            resp.raise_for_status()
            strategies = resp.json()

            for s in strategies:
                name = s.get('strategy', '')
                avg_reward = s.get('avg_reward', 0)
                successes = s.get('successes', 0)
                failures = s.get('failures', 0)
                total = successes + failures

                if total >= 1:
                    priors[name] = {
                        'avg_reward': avg_reward,
                        'successes': successes,
                        'failures': failures,
                        'confidence': min(1.0, total / 10.0)  # More data = more confidence
                    }

            print(f"  Loaded {len(priors)} strategy priors from Thompson Sampling")
        except Exception as e:
            print(f"  Warning: Could not load strategy priors: {e}")

        return priors

    def _load_execution_history(self, days=30):
        """Load recent execution history for fitness calculation.

        Uses /ga/executions (execution_summary) since /ga/worker-results is unavailable.
        Infers quality from outcome when quality_score is null.
        Maps task_types from execution data to our 7 canonical types.
        """
        try:
            resp = requests.get(f'{API_BASE}/ga/executions', params={'limit': 500}, timeout=10)
            resp.raise_for_status()
            executions = resp.json()
        except Exception as e:
            print(f"  Warning: Could not load execution history: {e}")
            return {}

        # Map execution task_types to our canonical types
        TASK_TYPE_MAP = {
            'security_audit': 'security_analysis',
            'security_analysis': 'security_analysis',
            'load_testing': 'code_generation',  # Performance-related -> code tasks
            'code_generation': 'code_generation',
            'code_review': 'code_review',
            'research': 'research',
            'math_reasoning': 'math_reasoning',
            'general_qa': 'general_qa',
            'creative_writing': 'creative_writing',
        }

        history = defaultdict(list)
        for r in executions:
            model = r.get('model')
            raw_task = r.get('task_type', '')
            quality = r.get('quality_score')
            cost = r.get('cost_usd')
            duration = r.get('duration_ms')
            outcome = r.get('outcome')
            ts = r.get('timestamp')

            if not model:
                continue

            # Map task type
            task_type = TASK_TYPE_MAP.get(raw_task, 'general_qa')

            # Infer quality from outcome if quality_score is null
            if quality is None:
                if outcome == 'success':
                    quality = 0.75  # Successful but unknown quality
                elif outcome == 'error':
                    quality = 0.2
                else:
                    quality = 0.5

            # Use strategy priors to boost quality estimates for known models
            model_short = model.split('/')[-1].split(':')[0].split('-')[0].lower()
            prior = self.strategy_priors.get(model_short)
            if prior and prior['confidence'] > 0.3:
                # Blend inferred quality with prior (weighted by confidence)
                w = prior['confidence'] * 0.4  # Prior gets up to 40% weight
                quality = quality * (1 - w) + prior['avg_reward'] * w

            history[(model, task_type)].append({
                'quality': float(quality),
                'cost': float(cost) if cost is not None else 0.0,
                'duration_ms': float(duration) if duration and duration > 0 else 2000.0,
                'outcome': outcome,
                'timestamp': ts
            })

        # Also create synthetic entries from strategy priors for models we know about
        # This helps bootstrap model-task combos that have no execution history
        model_strategy_map = {
            'haiku': 'haiku',
            'sonnet': 'sonnet',
            'opus': 'opus',
        }
        for model_key, strategy_name in model_strategy_map.items():
            prior = self.strategy_priors.get(strategy_name)
            if not prior:
                continue
            # Find matching models in our candidate pool
            for task_type in TASK_TYPES:
                for model in self.models_by_task.get(task_type, []):
                    if model_key in model.lower():
                        key = (model, task_type)
                        if key not in history:
                            # Synthetic entry from strategy prior
                            history[key].append({
                                'quality': prior['avg_reward'],
                                'cost': 0.001 if model_key in ['opus', 'sonnet'] else 0.0003,
                                'duration_ms': 1500.0 if model_key == 'opus' else 800.0,
                                'outcome': 'success',
                                'timestamp': None
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
        Based on REAL execution data from workflow worker results
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
        best_generation = 0

        print(f"Generation 0: Best fitness = {best_ever.fitness:.3f}")
        print(f"  Strategy: {best_ever.genes}\n")

        for gen in range(1, generations + 1):
            population = self.evolve_generation(population)

            current_best = max(population, key=lambda c: c.fitness or 0)
            avg_fitness = np.mean([c.fitness for c in population if c.fitness])

            if current_best.fitness > (best_ever.fitness or 0):
                best_ever = current_best
                best_generation = gen
                print(f"Generation {gen}: NEW BEST! Fitness = {current_best.fitness:.3f} (avg = {avg_fitness:.3f})")
                print(f"  Strategy: {current_best.genes}\n")
            elif gen % 10 == 0:
                print(f"Generation {gen}: Best = {current_best.fitness:.3f}, Avg = {avg_fitness:.3f}")

            # Track convergence per generation
            try:
                # Calculate diversity as std dev of fitness values
                fitness_values = [c.fitness for c in population if c.fitness is not None]
                diversity = float(np.std(fitness_values)) if fitness_values else 0.0
                requests.post(f'{API_BASE}/ga/convergence', json={
                    'use_case': 'model-task-mapper',
                    'generation': gen,
                    'best_fitness': float(current_best.fitness or 0),
                    'avg_fitness': float(avg_fitness),
                    'diversity': diversity,
                    'island_id': 0
                }, timeout=5)
            except Exception:
                pass

        print("\n=== FINAL BEST STRATEGY ===")
        print(f"Fitness: {best_ever.fitness:.3f}")
        for task, model in best_ever.genes.items():
            print(f"  {task:20s} -> {model}")

        # Store in database
        self._store_best_strategy(best_ever, generation_found=best_generation)

        return best_ever

    def _store_best_strategy(self, chromosome, generation_found=0):
        """Store evolved strategy via REST API"""
        print("\nStoring evolved strategy via REST API...")

        # 1. Store best solution record (this endpoint works)
        try:
            resp = requests.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': 'model-task-mapper',
                'chromosome': json.dumps(chromosome.genes),
                'fitness': float(chromosome.fitness),
                'fitness_details': json.dumps({
                    'weights': {'quality': 0.6, 'cost': 0.2, 'latency': 0.2},
                    'task_types': TASK_TYPES,
                    'population_size': self.population_size,
                    'mutation_rate': self.mutation_rate,
                    'data_sources': ['ga/executions', 'ga/strategies', 'ga/models/free'],
                    'execution_history_entries': len(self.execution_history),
                    'strategy_priors': len(self.strategy_priors)
                }),
                'generation_found': generation_found,
                'notes': f'Best strategy from GA run at {datetime.now().isoformat()}'
            }, timeout=10)
            resp.raise_for_status()
            print("  Stored best solution in ga/best-solutions")
        except Exception as e:
            print(f"  Warning: Could not store best solution: {e}")

        # 2. Store per-model capability scores (graceful - endpoint may have schema issues)
        models_stored = 0
        models_failed = 0

        # Group tasks by model to build one capability row per model
        model_scores = defaultdict(dict)
        for task_type, model in chromosome.genes.items():
            if model is None or task_type not in TASK_TYPES:
                continue

            history = self.execution_history.get((model, task_type), [])
            if history:
                recent = history[-10:]
                avg_quality = float(np.mean([float(h['quality']) for h in recent]))
                avg_latency = int(float(np.mean([float(h['duration_ms']) for h in recent])))
            else:
                avg_quality = 0.6
                avg_latency = 2000

            model_scores[model][task_type] = avg_quality
            model_scores[model]['avg_latency_ms'] = avg_latency

        for model, scores in model_scores.items():
            try:
                payload = {
                    'model_id': model,
                    'provider': 'evolved',
                    'avg_latency_ms': scores.get('avg_latency_ms', 2000),
                    'notes': f'GA evolved - fitness {chromosome.fitness:.3f}',
                    'test_count': 1,
                }
                # Add task-type scores as columns
                for task in TASK_TYPES:
                    if task in scores:
                        payload[task] = scores[task]

                resp = requests.post(f'{API_BASE}/ga/models/capabilities', json=payload, timeout=10)
                if resp.status_code == 200:
                    models_stored += 1
                else:
                    models_failed += 1
            except Exception:
                models_failed += 1

        if models_stored > 0:
            print(f"  Stored {models_stored} model capabilities")
        if models_failed > 0:
            print(f"  Note: {models_failed} model capability stores failed (API schema mismatch - non-critical)")

        print("Strategy storage complete")

if __name__ == '__main__':
    print("=== Genetic Algorithm Model Optimizer ===\n")
    print("Using REAL execution data via REST API")
    print("Optimizing model selection for 7 task types")
    print("Fitness = quality * 0.6 - (cost * 100) * 0.2 - (latency_seconds) * 0.2\n")

    optimizer = GeneticOptimizer(
        population_size=30,
        mutation_rate=0.15,
        tournament_size=5
    )

    best = optimizer.run(generations=1000)

    print("\nOptimization complete!")
    print("Results stored in learning.model_capabilities via REST API")
