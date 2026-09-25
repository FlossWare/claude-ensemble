#!/usr/bin/env python3
"""GA Embedding & Chunking Optimizer

Evolves optimal embedding/chunking parameters for different retrieval tasks.
Parameters: chunk_size, chunk_overlap, embedding_model, similarity_metric,
top_k, reranking_strategy, context_window, metadata_weight.

Fitness measures retrieval quality (precision@k, recall@k, MRR) against
a synthetic corpus with known-relevant documents.

Usage:
    python3 ga_embedding_optimizer.py                    # 50 generations
    python3 ga_embedding_optimizer.py --generations 100
"""

import argparse
import json
import math
import os
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np

RETRIEVAL_TASKS = [
    'code_search',
    'documentation_lookup',
    'bug_report_match',
    'api_reference',
    'conversation_history',
    'error_log_analysis',
]

EMBEDDING_MODELS = [
    'all-MiniLM-L6-v2',       # 384-dim, fast
    'all-mpnet-base-v2',       # 768-dim, balanced
    'bge-large-en-v1.5',      # 1024-dim, quality
    'e5-large-v2',            # 1024-dim, quality
    'gte-base',               # 768-dim, fast
    'nomic-embed-text-v1.5',  # 768-dim, balanced
]

EMBEDDING_DIMS = {
    'all-MiniLM-L6-v2': 384,
    'all-mpnet-base-v2': 768,
    'bge-large-en-v1.5': 1024,
    'e5-large-v2': 1024,
    'gte-base': 768,
    'nomic-embed-text-v1.5': 768,
}

SIMILARITY_METRICS = ['cosine', 'dot_product', 'euclidean']
RERANKING_STRATEGIES = ['none', 'cross_encoder', 'llm_rerank', 'reciprocal_rank_fusion']


@dataclass
class EmbeddingConfig:
    task: str = 'code_search'
    chunk_size: int = 512          # tokens
    chunk_overlap: int = 64        # tokens
    embedding_model: str = 'all-MiniLM-L6-v2'
    similarity_metric: str = 'cosine'
    top_k: int = 5
    reranking: str = 'none'
    context_window: int = 3        # chunks around match
    metadata_weight: float = 0.1   # 0-1, weight of metadata in scoring
    min_score_threshold: float = 0.5


@dataclass
class EmbeddingChromosome:
    configs: Dict[str, EmbeddingConfig] = field(default_factory=dict)
    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        return {name: asdict(cfg) for name, cfg in self.configs.items()}


class RetrievalSimulator:
    """Simulates retrieval quality with realistic document/query embeddings.

    Models the interplay between:
    - Chunk size vs information density (too small = no context, too big = noise)
    - Embedding model quality vs latency (bigger = better recall, slower)
    - Overlap vs redundancy (some overlap helps boundaries, too much wastes space)
    - Reranking vs latency (cross-encoder is best but 10x slower)
    - top_k vs precision (more results = higher recall but lower precision)
    """

    # How well each embedding model handles each task type (quality 0-1)
    MODEL_TASK_AFFINITY = {
        'all-MiniLM-L6-v2': {
            'code_search': 0.55, 'documentation_lookup': 0.70, 'bug_report_match': 0.60,
            'api_reference': 0.65, 'conversation_history': 0.72, 'error_log_analysis': 0.50,
        },
        'all-mpnet-base-v2': {
            'code_search': 0.72, 'documentation_lookup': 0.78, 'bug_report_match': 0.75,
            'api_reference': 0.74, 'conversation_history': 0.80, 'error_log_analysis': 0.68,
        },
        'bge-large-en-v1.5': {
            'code_search': 0.82, 'documentation_lookup': 0.85, 'bug_report_match': 0.80,
            'api_reference': 0.83, 'conversation_history': 0.78, 'error_log_analysis': 0.76,
        },
        'e5-large-v2': {
            'code_search': 0.80, 'documentation_lookup': 0.82, 'bug_report_match': 0.78,
            'api_reference': 0.85, 'conversation_history': 0.76, 'error_log_analysis': 0.74,
        },
        'gte-base': {
            'code_search': 0.68, 'documentation_lookup': 0.74, 'bug_report_match': 0.70,
            'api_reference': 0.72, 'conversation_history': 0.76, 'error_log_analysis': 0.65,
        },
        'nomic-embed-text-v1.5': {
            'code_search': 0.75, 'documentation_lookup': 0.80, 'bug_report_match': 0.73,
            'api_reference': 0.77, 'conversation_history': 0.82, 'error_log_analysis': 0.71,
        },
    }

    # Optimal chunk size ranges per task (outside this range, quality drops)
    OPTIMAL_CHUNK_RANGES = {
        'code_search': (128, 384),
        'documentation_lookup': (384, 768),
        'bug_report_match': (256, 512),
        'api_reference': (192, 512),
        'conversation_history': (128, 256),
        'error_log_analysis': (256, 512),
    }

    # Similarity metric effectiveness per task
    METRIC_AFFINITY = {
        'code_search': {'cosine': 0.85, 'dot_product': 0.70, 'euclidean': 0.60},
        'documentation_lookup': {'cosine': 0.90, 'dot_product': 0.80, 'euclidean': 0.70},
        'bug_report_match': {'cosine': 0.80, 'dot_product': 0.75, 'euclidean': 0.65},
        'api_reference': {'cosine': 0.85, 'dot_product': 0.82, 'euclidean': 0.68},
        'conversation_history': {'cosine': 0.88, 'dot_product': 0.78, 'euclidean': 0.62},
        'error_log_analysis': {'cosine': 0.75, 'dot_product': 0.80, 'euclidean': 0.72},
    }

    # Reranking quality boost and latency cost
    RERANKING_PROFILES = {
        'none': {'quality_boost': 0.0, 'latency_cost': 0.0},
        'cross_encoder': {'quality_boost': 0.15, 'latency_cost': 0.40},
        'llm_rerank': {'quality_boost': 0.12, 'latency_cost': 0.55},
        'reciprocal_rank_fusion': {'quality_boost': 0.08, 'latency_cost': 0.10},
    }

    def __init__(self, num_queries=100, corpus_size=5000):
        self.num_queries = num_queries
        self.corpus_size = corpus_size

    def simulate(self, config: EmbeddingConfig, seed: int = 42) -> Dict:
        rng = np.random.RandomState(seed)
        task = config.task

        # Base quality from model-task affinity
        model_quality = self.MODEL_TASK_AFFINITY.get(
            config.embedding_model, {}
        ).get(task, 0.50)

        # Chunk size quality curve (gaussian centered on optimal range)
        opt_min, opt_max = self.OPTIMAL_CHUNK_RANGES.get(task, (256, 512))
        opt_center = (opt_min + opt_max) / 2
        opt_width = (opt_max - opt_min) / 2
        chunk_distance = abs(config.chunk_size - opt_center) / (opt_width + 1)
        chunk_quality = math.exp(-0.5 * chunk_distance ** 2)

        # Overlap quality: sweet spot at 10-20% of chunk_size
        overlap_ratio = config.chunk_overlap / max(config.chunk_size, 1)
        optimal_overlap = 0.15
        overlap_quality = max(0.5, 1.0 - abs(overlap_ratio - optimal_overlap) * 3)

        # Metric quality
        metric_quality = self.METRIC_AFFINITY.get(task, {}).get(config.similarity_metric, 0.70)

        # Reranking effect
        rerank = self.RERANKING_PROFILES.get(config.reranking, self.RERANKING_PROFILES['none'])

        # Combined base retrieval quality
        base_quality = (model_quality * 0.40 + chunk_quality * 0.25 +
                       metric_quality * 0.20 + overlap_quality * 0.15)

        # Apply reranking boost (multiplicative)
        retrieval_quality = min(1.0, base_quality * (1 + rerank['quality_boost']))

        # Precision@K: higher K = more results but lower precision
        k_penalty = 1.0 / (1 + 0.08 * max(0, config.top_k - 3))
        precision_at_k = retrieval_quality * k_penalty + rng.normal(0, 0.03)
        precision_at_k = max(0, min(1, precision_at_k))

        # Recall@K: higher K = better recall
        recall_base = retrieval_quality * (1 - math.exp(-0.3 * config.top_k))
        recall_at_k = recall_base + rng.normal(0, 0.03)
        recall_at_k = max(0, min(1, recall_at_k))

        # MRR (mean reciprocal rank)
        mrr = retrieval_quality * 0.9 + rng.normal(0, 0.02)
        mrr = max(0, min(1, mrr))

        # Latency score (lower is better → inverted for fitness)
        dim = EMBEDDING_DIMS.get(config.embedding_model, 768)
        embed_latency = dim / 1024 * 0.3  # normalized
        rerank_latency = rerank['latency_cost']
        search_latency = 0.05 * config.top_k / 5
        total_latency = embed_latency + rerank_latency + search_latency
        speed_score = max(0, 1.0 - total_latency)

        # Context window: more context = better answer quality but more tokens
        context_boost = min(0.1, 0.02 * config.context_window)
        context_cost = 0.01 * config.context_window

        # Metadata weight impact
        meta_bonus = config.metadata_weight * 0.05 if task in ('bug_report_match', 'error_log_analysis') else 0

        return {
            'precision_at_k': round(precision_at_k + meta_bonus, 4),
            'recall_at_k': round(recall_at_k, 4),
            'mrr': round(mrr + context_boost, 4),
            'speed': round(speed_score - context_cost, 4),
            'retrieval_quality': round(retrieval_quality, 4),
        }


class EmbeddingGA:
    def __init__(self, population_size=30, mutation_rate=0.20, seed=None):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.simulator = RetrievalSimulator()
        self.convergence_history = []
        self.best_fitness = 0.0
        self.best_chromosome = None
        self.stagnation = 0

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def create_random(self) -> EmbeddingChromosome:
        configs = {}
        for task in RETRIEVAL_TASKS:
            configs[task] = EmbeddingConfig(
                task=task,
                chunk_size=random.choice([64, 128, 192, 256, 384, 512, 768, 1024]),
                chunk_overlap=random.choice([0, 16, 32, 64, 96, 128]),
                embedding_model=random.choice(EMBEDDING_MODELS),
                similarity_metric=random.choice(SIMILARITY_METRICS),
                top_k=random.randint(1, 15),
                reranking=random.choice(RERANKING_STRATEGIES),
                context_window=random.randint(0, 5),
                metadata_weight=round(random.uniform(0, 0.5), 2),
                min_score_threshold=round(random.uniform(0.3, 0.8), 2),
            )
        return EmbeddingChromosome(configs=configs)

    def create_seeded(self) -> List[EmbeddingChromosome]:
        seeds = []

        # Seed 1: Quality-first (large model, cross-encoder reranking)
        c1 = {}
        for task in RETRIEVAL_TASKS:
            c1[task] = EmbeddingConfig(
                task=task, chunk_size=512, chunk_overlap=64,
                embedding_model='bge-large-en-v1.5', similarity_metric='cosine',
                top_k=10, reranking='cross_encoder', context_window=3,
                metadata_weight=0.1, min_score_threshold=0.5,
            )
        seeds.append(EmbeddingChromosome(configs=c1))

        # Seed 2: Speed-first (small model, no reranking)
        c2 = {}
        for task in RETRIEVAL_TASKS:
            c2[task] = EmbeddingConfig(
                task=task, chunk_size=256, chunk_overlap=32,
                embedding_model='all-MiniLM-L6-v2', similarity_metric='dot_product',
                top_k=3, reranking='none', context_window=1,
                metadata_weight=0.0, min_score_threshold=0.6,
            )
        seeds.append(EmbeddingChromosome(configs=c2))

        return seeds

    def calculate_fitness(self, chromosome: EmbeddingChromosome) -> float:
        precisions = []
        recalls = []
        mrrs = []
        speeds = []

        for task, cfg in chromosome.configs.items():
            results = []
            for s in [42, 123, 456]:
                r = self.simulator.simulate(cfg, seed=s + hash(task) % 1000)
                results.append(r)

            precisions.append(np.mean([r['precision_at_k'] for r in results]))
            recalls.append(np.mean([r['recall_at_k'] for r in results]))
            mrrs.append(np.mean([r['mrr'] for r in results]))
            speeds.append(np.mean([r['speed'] for r in results]))

        precision = float(np.mean(precisions))
        recall = float(np.mean(recalls))
        mrr = float(np.mean(mrrs))
        speed = float(np.mean(speeds))

        fitness = precision * 0.25 + recall * 0.25 + mrr * 0.30 + speed * 0.20

        chromosome.fitness = round(fitness, 5)
        chromosome.fitness_details = {
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'mrr': round(mrr, 4),
            'speed': round(speed, 4),
        }
        return fitness

    def crossover(self, p1: EmbeddingChromosome, p2: EmbeddingChromosome) -> EmbeddingChromosome:
        configs = {}
        for task in RETRIEVAL_TASKS:
            c1, c2 = p1.configs.get(task), p2.configs.get(task)
            if c1 and c2:
                d1, d2 = asdict(c1), asdict(c2)
                child = {}
                for key in d1:
                    child[key] = d1[key] if random.random() < 0.5 else d2[key]
                configs[task] = EmbeddingConfig(**child)
            elif c1:
                configs[task] = EmbeddingConfig(**asdict(c1))
            elif c2:
                configs[task] = EmbeddingConfig(**asdict(c2))
        return EmbeddingChromosome(configs=configs)

    def mutate(self, chromosome: EmbeddingChromosome):
        for task, cfg in chromosome.configs.items():
            if random.random() < self.mutation_rate:
                gene = random.choice([
                    'chunk_size', 'chunk_overlap', 'embedding_model',
                    'similarity_metric', 'top_k', 'reranking',
                    'context_window', 'metadata_weight',
                ])

                if gene == 'chunk_size':
                    cfg.chunk_size = random.choice([64, 128, 192, 256, 384, 512, 768, 1024])
                elif gene == 'chunk_overlap':
                    cfg.chunk_overlap = max(0, min(cfg.chunk_size // 2,
                                                   cfg.chunk_overlap + random.choice([-16, -8, 8, 16, 32])))
                elif gene == 'embedding_model':
                    cfg.embedding_model = random.choice(EMBEDDING_MODELS)
                elif gene == 'similarity_metric':
                    cfg.similarity_metric = random.choice(SIMILARITY_METRICS)
                elif gene == 'top_k':
                    cfg.top_k = max(1, min(15, cfg.top_k + random.randint(-2, 2)))
                elif gene == 'reranking':
                    cfg.reranking = random.choice(RERANKING_STRATEGIES)
                elif gene == 'context_window':
                    cfg.context_window = max(0, min(5, cfg.context_window + random.randint(-1, 1)))
                elif gene == 'metadata_weight':
                    cfg.metadata_weight = round(max(0, min(0.5, cfg.metadata_weight + random.uniform(-0.1, 0.1))), 2)

    def tournament_select(self, population):
        candidates = random.sample(population, min(4, len(population)))
        return max(candidates, key=lambda c: c.fitness or 0)

    def run(self, generations=50):
        print("=" * 70)
        print("  GA Embedding & Chunking Optimizer")
        print("=" * 70)
        print(f"Tasks: {len(RETRIEVAL_TASKS)}")
        print(f"Genes per task: 9, Total genes: {9 * len(RETRIEVAL_TASKS)}")
        print("=" * 70)

        population = self.create_seeded()
        while len(population) < self.population_size:
            population.append(self.create_random())

        for c in population:
            c.fitness = self.calculate_fitness(c)

        best_ever = max(population, key=lambda c: c.fitness or 0)
        self.best_fitness = best_ever.fitness or 0
        self.best_chromosome = best_ever

        print(f"Gen  0: Best={best_ever.fitness:.5f}  {best_ever.fitness_details}")

        for gen in range(1, generations + 1):
            if self.stagnation > 6:
                self.mutation_rate = min(0.5, 0.20 + 0.03 * self.stagnation)
            else:
                self.mutation_rate = 0.20

            population.sort(key=lambda c: c.fitness or 0, reverse=True)
            elite_size = max(2, self.population_size // 5)
            new_pop = list(population[:elite_size])

            while len(new_pop) < self.population_size:
                p1 = self.tournament_select(population)
                p2 = self.tournament_select(population)
                child = self.crossover(p1, p2)
                self.mutate(child)
                child.fitness = self.calculate_fitness(child)
                new_pop.append(child)
            population = new_pop

            current_best = max(population, key=lambda c: c.fitness or 0)
            if (current_best.fitness or 0) > self.best_fitness:
                self.best_fitness = current_best.fitness
                self.best_chromosome = current_best
                self.stagnation = 0
                d = current_best.fitness_details
                print(f"Gen {gen:2d}: NEW BEST={current_best.fitness:.5f}  "
                      f"P={d['precision']:.3f} R={d['recall']:.3f} MRR={d['mrr']:.3f} Spd={d['speed']:.3f}")
            else:
                self.stagnation += 1
                if gen % 10 == 0:
                    avg = np.mean([c.fitness for c in population if c.fitness])
                    print(f"Gen {gen:2d}: Best={current_best.fitness:.5f}  "
                          f"Avg={avg:.5f}  Stag={self.stagnation}")

            self.convergence_history.append({
                'generation': gen,
                'best': float(current_best.fitness or 0),
                'avg': float(np.mean([c.fitness for c in population if c.fitness])),
            })

        self._print_report()
        self._store_results()
        return self.best_chromosome

    def _print_report(self):
        best = self.best_chromosome
        if not best:
            return

        print("\n" + "=" * 70)
        print("  BEST EMBEDDING/CHUNKING CONFIGS")
        print("=" * 70)
        print(f"  Overall Fitness: {best.fitness:.5f}")
        if best.fitness_details:
            for k, v in best.fitness_details.items():
                print(f"    {k:20s}: {v}")

        for task in RETRIEVAL_TASKS:
            cfg = best.configs.get(task)
            if cfg:
                dim = EMBEDDING_DIMS.get(cfg.embedding_model, '?')
                print(f"\n  [{task.upper()}]")
                print(f"    Model:      {cfg.embedding_model} ({dim}-dim)")
                print(f"    Chunk:      {cfg.chunk_size} tokens, {cfg.chunk_overlap} overlap ({cfg.chunk_overlap/max(cfg.chunk_size,1)*100:.0f}%)")
                print(f"    Metric:     {cfg.similarity_metric}")
                print(f"    top_k:      {cfg.top_k}")
                print(f"    Reranking:  {cfg.reranking}")
                print(f"    Context:    {cfg.context_window} surrounding chunks")
                print(f"    Metadata:   {cfg.metadata_weight:.0%} weight")
        print("=" * 70)

    def _store_results(self):
        best = self.best_chromosome
        if not best:
            return

        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, 'best_embedding_config.json')

        with open(output_path, 'w') as f:
            json.dump({
                'configs': best.to_dict(),
                'fitness': best.fitness,
                'fitness_details': best.fitness_details,
                'metadata': {'created_at': time.strftime('%Y-%m-%dT%H:%M:%S')},
            }, f, indent=2)
        print(f"\nConfig saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='GA Embedding & Chunking Optimizer')
    parser.add_argument('--generations', type=int, default=50)
    parser.add_argument('--population', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    ga = EmbeddingGA(population_size=args.population, seed=args.seed)
    ga.run(generations=args.generations)


if __name__ == '__main__':
    main()
