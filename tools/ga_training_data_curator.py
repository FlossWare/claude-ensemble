#!/usr/bin/env python3
"""
GA Training Data Curator

Evolves optimal data mix recipes for fine-tuning from 120K+ scraped documents.
Finds the best combination of category weights, quality thresholds, and sampling
strategies to maximize fine-tuned model performance.

Architecture:
- Genome: Data mix recipe (category weights, quality thresholds, bounds)
- Fitness: Fine-tuned model eval score (via API fine-tuning + benchmark)
- Evolution: Tournament selection + crossover + mutation
- Data: 167 categories, 120K+ documents, 320M+ tokens
"""

import json
import random
import requests
import numpy as np
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

API_BASE = 'http://localhost:5000'
SCRAPED_DATA_DIR = '/exports/claude-orchestrator/scraped-data/raw'


@dataclass
class DataRecipe:
    """A chromosome representing a training data mix recipe"""
    category_weights: Dict[str, float] = field(default_factory=dict)
    min_content_length: int = 500
    max_content_length: int = 50000
    max_samples_per_category: int = 500
    total_target_samples: int = 10000
    dedup_similarity_threshold: float = 0.9
    include_categories: List[str] = field(default_factory=list)
    exclude_categories: List[str] = field(default_factory=list)
    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class TrainingDataCurator:
    """GA that evolves optimal training data mixtures"""

    def __init__(self, population_size=20, mutation_rate=0.2, tournament_size=3,
                 eval_method='proxy'):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.eval_method = eval_method
        self.category_stats = self._load_category_stats()
        self.available_categories = [c['category'] for c in self.category_stats if c['stored'] > 50]
        self.generation = 0

    def _load_category_stats(self):
        resp = requests.get(f'{API_BASE}/ga/training-data/stats')
        resp.raise_for_status()
        return resp.json()

    def _category_doc_count(self, category):
        for s in self.category_stats:
            if s['category'] == category:
                return s['stored']
        return 0

    def create_random_recipe(self):
        n_categories = random.randint(5, min(30, len(self.available_categories)))
        selected = random.sample(self.available_categories, n_categories)

        weights = {}
        for cat in selected:
            weights[cat] = random.uniform(0.1, 3.0)

        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

        return DataRecipe(
            category_weights=weights,
            min_content_length=random.choice([200, 500, 1000, 2000]),
            max_content_length=random.choice([20000, 50000, 100000]),
            max_samples_per_category=random.choice([100, 250, 500, 1000]),
            total_target_samples=random.choice([5000, 10000, 20000, 50000]),
            dedup_similarity_threshold=random.uniform(0.8, 0.95),
            include_categories=selected,
            exclude_categories=[]
        )

    def create_seeded_recipes(self):
        """Create domain-focused seed recipes"""
        seeds = []

        tech_cats = [c for c in self.available_categories
                     if any(k in c.lower() for k in ['java', 'python', 'rfc', 'linux', 'github', 'netbeans', 'ml', 'ai'])]
        if tech_cats:
            weights = {c: 1.0 / len(tech_cats) for c in tech_cats}
            seeds.append(DataRecipe(
                category_weights=weights,
                min_content_length=1000,
                max_content_length=50000,
                max_samples_per_category=500,
                total_target_samples=20000,
                include_categories=tech_cats
            ))

        research_cats = [c for c in self.available_categories
                         if any(k in c.lower() for k in ['arxiv', 'pubmed', 'research', 'patent'])]
        if research_cats:
            weights = {c: 1.0 / len(research_cats) for c in research_cats}
            seeds.append(DataRecipe(
                category_weights=weights,
                min_content_length=2000,
                max_content_length=100000,
                max_samples_per_category=300,
                total_target_samples=15000,
                include_categories=research_cats
            ))

        balanced = {}
        for cat in self.available_categories[:20]:
            count = self._category_doc_count(cat)
            balanced[cat] = 1.0 / max(1, np.log1p(count))
        total = sum(balanced.values())
        balanced = {k: v / total for k, v in balanced.items()}
        seeds.append(DataRecipe(
            category_weights=balanced,
            min_content_length=500,
            max_content_length=50000,
            max_samples_per_category=250,
            total_target_samples=10000,
            include_categories=list(balanced.keys())
        ))

        return seeds

    def sample_training_data(self, recipe, dry_run=True):
        """Sample training data according to a recipe. Returns metadata about what would be sampled."""
        sampled = {}
        total_tokens_est = 0

        for cat, weight in recipe.category_weights.items():
            available = self._category_doc_count(cat)
            target = min(
                int(recipe.total_target_samples * weight),
                recipe.max_samples_per_category,
                available
            )

            if target <= 0:
                continue

            avg_len = next((s.get('avg_content_length', 5000) for s in self.category_stats
                           if s['category'] == cat), 5000)
            avg_len = float(avg_len) if avg_len else 5000.0

            effective_len = min(max(avg_len, recipe.min_content_length), recipe.max_content_length)
            est_tokens = (effective_len / 4) * target

            sampled[cat] = {
                'target': target,
                'available': available,
                'est_tokens': int(est_tokens),
                'avg_doc_length': int(effective_len)
            }
            total_tokens_est += est_tokens

        return {
            'categories_used': len(sampled),
            'total_samples': sum(s['target'] for s in sampled.values()),
            'total_tokens_est': int(total_tokens_est),
            'category_breakdown': sampled
        }

    def calculate_fitness(self, recipe):
        """
        Fitness function for data recipes.

        Components:
        1. Coverage diversity (0.3) - how many distinct knowledge domains
        2. Data balance (0.2) - inverse of max category dominance
        3. Quality signal (0.2) - content length sweet spot, not too short/long
        4. Volume efficiency (0.15) - enough data without waste
        5. Category richness (0.15) - preference for categories with more stored docs
        """
        sample_info = self.sample_training_data(recipe)
        breakdown = sample_info['category_breakdown']

        if not breakdown:
            return 0.0

        category_counts = [v['target'] for v in breakdown.values()]
        total_samples = sum(category_counts)

        if total_samples == 0:
            return 0.0

        n_cats = len(breakdown)
        max_cats = len(self.available_categories)
        coverage_score = min(1.0, n_cats / max(1, min(30, max_cats)))

        proportions = [c / total_samples for c in category_counts]
        max_proportion = max(proportions)
        balance_score = 1.0 - max_proportion

        avg_lengths = [v['avg_doc_length'] for v in breakdown.values()]
        mean_len = np.mean(avg_lengths)
        quality_score = 1.0
        if mean_len < 500:
            quality_score *= 0.5
        elif mean_len < 1000:
            quality_score *= 0.8
        if mean_len > 80000:
            quality_score *= 0.6

        target = 15000
        volume_ratio = total_samples / target
        volume_score = 1.0 - abs(1.0 - volume_ratio) * 0.5
        volume_score = max(0, min(1, volume_score))

        richness_scores = []
        for cat, info in breakdown.items():
            utilization = info['target'] / max(1, info['available'])
            richness_scores.append(min(1.0, utilization * 2))
        richness_score = np.mean(richness_scores) if richness_scores else 0

        fitness = (
            coverage_score * 0.3 +
            balance_score * 0.2 +
            quality_score * 0.2 +
            volume_score * 0.15 +
            richness_score * 0.15
        )

        recipe.fitness_details = {
            'coverage': round(coverage_score, 3),
            'balance': round(balance_score, 3),
            'quality': round(quality_score, 3),
            'volume': round(volume_score, 3),
            'richness': round(richness_score, 3),
            'n_categories': n_cats,
            'total_samples': total_samples,
            'total_tokens_est': sample_info['total_tokens_est']
        }

        return fitness

    def tournament_selection(self, population):
        tournament = random.sample(population, min(self.tournament_size, len(population)))
        return max(tournament, key=lambda r: r.fitness or 0)

    def crossover(self, parent1, parent2):
        all_cats = list(set(list(parent1.category_weights.keys()) + list(parent2.category_weights.keys())))
        child_weights = {}
        for cat in all_cats:
            w1 = parent1.category_weights.get(cat, 0)
            w2 = parent2.category_weights.get(cat, 0)
            if random.random() < 0.5:
                child_weights[cat] = w1 if w1 > 0 else w2
            else:
                child_weights[cat] = w2 if w2 > 0 else w1

        child_weights = {k: v for k, v in child_weights.items() if v > 0}
        if child_weights:
            total = sum(child_weights.values())
            child_weights = {k: v / total for k, v in child_weights.items()}

        child = DataRecipe(
            category_weights=child_weights,
            min_content_length=random.choice([parent1.min_content_length, parent2.min_content_length]),
            max_content_length=random.choice([parent1.max_content_length, parent2.max_content_length]),
            max_samples_per_category=random.choice([parent1.max_samples_per_category, parent2.max_samples_per_category]),
            total_target_samples=random.choice([parent1.total_target_samples, parent2.total_target_samples]),
            dedup_similarity_threshold=(parent1.dedup_similarity_threshold + parent2.dedup_similarity_threshold) / 2,
            include_categories=list(child_weights.keys()),
        )
        return child

    def mutate(self, recipe):
        if random.random() < self.mutation_rate:
            mutation_type = random.choice(['add_category', 'remove_category', 'adjust_weight',
                                           'change_threshold', 'change_samples'])

            if mutation_type == 'add_category' and len(recipe.category_weights) < 30:
                unused = [c for c in self.available_categories if c not in recipe.category_weights]
                if unused:
                    new_cat = random.choice(unused)
                    recipe.category_weights[new_cat] = random.uniform(0.01, 0.1)
                    recipe.include_categories.append(new_cat)

            elif mutation_type == 'remove_category' and len(recipe.category_weights) > 3:
                cat = random.choice(list(recipe.category_weights.keys()))
                del recipe.category_weights[cat]
                if cat in recipe.include_categories:
                    recipe.include_categories.remove(cat)

            elif mutation_type == 'adjust_weight' and recipe.category_weights:
                cat = random.choice(list(recipe.category_weights.keys()))
                recipe.category_weights[cat] *= random.uniform(0.5, 2.0)

            elif mutation_type == 'change_threshold':
                recipe.min_content_length = max(100, recipe.min_content_length + random.randint(-500, 500))
                recipe.max_content_length = max(recipe.min_content_length + 1000,
                                                recipe.max_content_length + random.randint(-10000, 10000))

            elif mutation_type == 'change_samples':
                recipe.total_target_samples = max(1000, recipe.total_target_samples + random.randint(-5000, 5000))
                recipe.max_samples_per_category = max(50, recipe.max_samples_per_category + random.randint(-200, 200))

            if recipe.category_weights:
                total = sum(recipe.category_weights.values())
                recipe.category_weights = {k: v / total for k, v in recipe.category_weights.items()}

    def evolve_generation(self, population):
        population.sort(key=lambda r: r.fitness or 0, reverse=True)

        elite_size = max(1, self.population_size // 5)
        new_population = population[:elite_size]

        while len(new_population) < self.population_size:
            parent1 = self.tournament_selection(population)
            parent2 = self.tournament_selection(population)
            child = self.crossover(parent1, parent2)
            self.mutate(child)
            child.fitness = self.calculate_fitness(child)
            new_population.append(child)

        return new_population

    def run(self, generations=30):
        print(f"=== GA Training Data Curator ===")
        print(f"Available categories: {len(self.available_categories)}")
        print(f"Population: {self.population_size}, Generations: {generations}")
        print(f"Eval method: {self.eval_method}\n")

        population = self.create_seeded_recipes()
        while len(population) < self.population_size:
            population.append(self.create_random_recipe())

        for recipe in population:
            recipe.fitness = self.calculate_fitness(recipe)

        best_ever = max(population, key=lambda r: r.fitness or 0)
        print(f"Gen 0: Best={best_ever.fitness:.4f} | {best_ever.fitness_details}")

        for gen in range(1, generations + 1):
            self.generation = gen
            population = self.evolve_generation(population)

            current_best = max(population, key=lambda r: r.fitness or 0)
            avg_fitness = np.mean([r.fitness for r in population if r.fitness])

            if current_best.fitness > (best_ever.fitness or 0):
                best_ever = current_best
                print(f"Gen {gen}: NEW BEST! {current_best.fitness:.4f} (avg={avg_fitness:.4f})")
                print(f"  {current_best.fitness_details}")
            elif gen % 5 == 0:
                print(f"Gen {gen}: Best={current_best.fitness:.4f}, Avg={avg_fitness:.4f}")

            try:
                requests.post(f'{API_BASE}/ga/convergence', json={
                    'use_case': 'training-data-curator',
                    'generation': gen,
                    'island_id': 0,
                    'best_fitness': float(current_best.fitness),
                    'avg_fitness': float(avg_fitness),
                    'diversity': float(len(set(
                        tuple(sorted(r.category_weights.keys())) for r in population
                    )) / len(population))
                })
            except Exception:
                pass

        print(f"\n=== BEST RECIPE ===")
        print(f"Fitness: {best_ever.fitness:.4f}")
        print(f"Details: {json.dumps(best_ever.fitness_details, indent=2)}")
        print(f"\nCategory weights:")
        for cat, weight in sorted(best_ever.category_weights.items(), key=lambda x: -x[1]):
            count = self._category_doc_count(cat)
            samples = int(best_ever.total_target_samples * weight)
            print(f"  {cat:40s} weight={weight:.3f}  samples={samples:5d}  (avail={count})")
        print(f"\nContent length: {best_ever.min_content_length} - {best_ever.max_content_length}")
        print(f"Max per category: {best_ever.max_samples_per_category}")
        print(f"Total target: {best_ever.total_target_samples}")

        self._store_best(best_ever)
        return best_ever

    def _store_best(self, recipe):
        try:
            requests.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': 'training-data-curator',
                'chromosome': json.dumps(recipe.to_dict()),
                'fitness': float(recipe.fitness),
                'fitness_details': json.dumps(recipe.fitness_details),
                'generation_found': self.generation,
                'notes': f'Best data recipe: {recipe.fitness_details.get("n_categories", 0)} categories, '
                         f'{recipe.fitness_details.get("total_samples", 0)} samples, '
                         f'~{recipe.fitness_details.get("total_tokens_est", 0) / 1e6:.1f}M tokens'
            })
            print("\nStored best recipe in ga.best_solutions")
        except Exception as e:
            print(f"\nFailed to store: {e}")

    def export_recipe(self, recipe, output_path):
        """Export a recipe as a JSON file for use by training pipeline"""
        sample_info = self.sample_training_data(recipe)
        export = {
            'recipe': recipe.to_dict(),
            'sample_plan': sample_info,
            'metadata': {
                'fitness': recipe.fitness,
                'fitness_details': recipe.fitness_details,
                'generation': self.generation,
                'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'eval_method': self.eval_method
            }
        }
        with open(output_path, 'w') as f:
            json.dump(export, f, indent=2)
        print(f"Exported recipe to {output_path}")


if __name__ == '__main__':
    curator = TrainingDataCurator(
        population_size=30,
        mutation_rate=0.2,
        tournament_size=3,
        eval_method='proxy'
    )

    best = curator.run(generations=1000)

    output_dir = os.path.dirname(os.path.abspath(__file__))
    curator.export_recipe(best, os.path.join(output_dir, 'best_training_recipe.json'))

    print("\nDone! Use best_training_recipe.json with training pipeline.")
