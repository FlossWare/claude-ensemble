#!/usr/bin/env python3
"""
GA RAG Retrieval Optimizer

Evolves optimal chunking and retrieval configuration for RAG over 120K+ scraped
documents across 130+ categories. Uses a genetic algorithm to find the best
combination of chunk size, overlap, embedding model, top_k, reranking, and
per-category boosting weights.

Architecture:
- Genome: RAG retrieval config (chunk params, embedding, retrieval params, category boosts)
- Fitness: Weighted combination of relevance, coverage, efficiency, diversity, latency
- Evolution: Tournament selection, uniform crossover, adaptive mutation
- Data: 167 categories, 120K+ documents via REST API

DATABASE: Uses REST API at aio-01:5000 (not direct psycopg2)
"""

import argparse
import json
import math
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

API_BASE = 'http://aio-01:5000'

# --- Valid parameter spaces ---

EMBEDDING_MODELS = [
    'text-embedding-3-small',
    'text-embedding-3-large',
    'voyage-2',
    'voyage-3',
    'jina-embeddings-v3',
    'nomic-embed-text',
    'bge-large-en-v1.5',
    'gte-large',
]

EMBEDDING_DIMS = [128, 256, 384, 512, 768, 1024, 1536]

# Model-specific default/max dims (for latency and compatibility estimation)
MODEL_DIM_DEFAULTS = {
    'text-embedding-3-small': 1536,
    'text-embedding-3-large': 3072,
    'voyage-2': 1024,
    'voyage-3': 1024,
    'jina-embeddings-v3': 1024,
    'nomic-embed-text': 768,
    'bge-large-en-v1.5': 1024,
    'gte-large': 1024,
}

# Relative speed factors (lower = faster). Based on known benchmarks.
MODEL_SPEED_FACTORS = {
    'text-embedding-3-small': 0.6,
    'text-embedding-3-large': 1.2,
    'voyage-2': 1.0,
    'voyage-3': 0.9,
    'jina-embeddings-v3': 0.85,
    'nomic-embed-text': 0.5,
    'bge-large-en-v1.5': 0.8,
    'gte-large': 0.75,
}

# --- Synthetic test queries spanning the corpus ---

TEST_QUERIES = [
    # Technical - networking / DD-WRT
    {"query": "How to configure QoS in DD-WRT for VoIP traffic prioritization",
     "relevant_categories": ["ddwrt", "openwrt", "freshtomato"],
     "domain": "networking"},
    {"query": "Setting up a DD-WRT wireless bridge between two buildings",
     "relevant_categories": ["ddwrt", "openwrt"],
     "domain": "networking"},
    {"query": "DD-WRT VLAN configuration for guest network isolation",
     "relevant_categories": ["ddwrt", "openwrt", "freshtomato"],
     "domain": "networking"},

    # Technical - RFCs and standards
    {"query": "What is RFC 9110 about and how does it update HTTP semantics",
     "relevant_categories": ["rfc"],
     "domain": "standards"},
    {"query": "TLS 1.3 handshake improvements over TLS 1.2 per RFC 8446",
     "relevant_categories": ["rfc"],
     "domain": "standards"},
    {"query": "DNS over HTTPS protocol specification and privacy implications",
     "relevant_categories": ["rfc"],
     "domain": "standards"},

    # AI / ML
    {"query": "How does multi-head attention work in transformer architectures",
     "relevant_categories": ["ai", "arxiv-ai", "arxiv-neural", "ml", "arxiv-ml"],
     "domain": "ai"},
    {"query": "Comparison of LoRA vs QLoRA for parameter-efficient fine-tuning",
     "relevant_categories": ["ai", "arxiv-ai", "ml", "arxiv-ml", "huggingface"],
     "domain": "ai"},
    {"query": "Retrieval augmented generation architectures and vector database selection",
     "relevant_categories": ["ai", "arxiv-ai", "ml", "arxiv-ml"],
     "domain": "ai"},
    {"query": "Reinforcement learning from human feedback for language model alignment",
     "relevant_categories": ["ai", "arxiv-ai", "arxiv-ml", "ml"],
     "domain": "ai"},

    # Medical / epidemiology
    {"query": "Latest treatments for pancreatic cancer including immunotherapy approaches",
     "relevant_categories": ["pubmed", "genetic and genomic medicine"],
     "domain": "medical"},
    {"query": "Epidemiology of COVID-19 variants and vaccine effectiveness data",
     "relevant_categories": ["epidemiology", "infectious diseases", "public and global health"],
     "domain": "medical"},
    {"query": "CRISPR gene therapy clinical trial results for sickle cell disease",
     "relevant_categories": ["genetic and genomic medicine", "pubmed"],
     "domain": "medical"},
    {"query": "Neurological effects of long COVID on cognitive function",
     "relevant_categories": ["neurology", "infectious diseases", "pubmed"],
     "domain": "medical"},

    # Code / software engineering
    {"query": "Java thread pool best practices for high-throughput server applications",
     "relevant_categories": ["github", "java", "performance"],
     "domain": "code"},
    {"query": "Python asyncio patterns for concurrent web scraping pipelines",
     "relevant_categories": ["github", "python", "performance"],
     "domain": "code"},
    {"query": "Kubernetes horizontal pod autoscaler configuration and tuning",
     "relevant_categories": ["github", "linux"],
     "domain": "code"},
    {"query": "Git rebase vs merge strategies for large team collaboration",
     "relevant_categories": ["github"],
     "domain": "code"},

    # Cross-domain
    {"query": "Machine learning for network traffic optimization and anomaly detection",
     "relevant_categories": ["ai", "arxiv-ai", "ml", "ddwrt", "performance"],
     "domain": "cross-domain"},
    {"query": "Genetic algorithms applied to drug discovery and molecular optimization",
     "relevant_categories": ["ga", "pubmed", "genetic and genomic medicine", "ai"],
     "domain": "cross-domain"},
    {"query": "Natural language processing for clinical note extraction in healthcare",
     "relevant_categories": ["arxiv-cl", "pubmed", "ai"],
     "domain": "cross-domain"},
    {"query": "Computer vision for medical image analysis and tumor detection",
     "relevant_categories": ["arxiv-cv", "pubmed", "ai"],
     "domain": "cross-domain"},
    {"query": "Robotic surgery systems and reinforcement learning control policies",
     "relevant_categories": ["arxiv-robotics", "pubmed", "ai"],
     "domain": "cross-domain"},

    # Algorithms and theory
    {"query": "Approximate nearest neighbor search algorithms for high-dimensional vectors",
     "relevant_categories": ["algorithms", "ai", "arxiv-ai", "performance"],
     "domain": "algorithms"},
    {"query": "Graph neural networks for knowledge graph completion",
     "relevant_categories": ["arxiv-ai", "arxiv-neural", "algorithms", "ai"],
     "domain": "algorithms"},

    # Research
    {"query": "Recent advances in protein structure prediction beyond AlphaFold",
     "relevant_categories": ["arxiv-ai", "pubmed", "research_paper"],
     "domain": "research"},
    {"query": "Psychiatric applications of large language models for therapy assistance",
     "relevant_categories": ["psychiatry and clinical psychology", "ai", "arxiv-cl"],
     "domain": "research"},
]


@dataclass
class RAGConfig:
    """A chromosome representing a RAG retrieval configuration"""
    chunk_size: int = 1024                        # 256-4096 tokens
    chunk_overlap: int = 128                      # 0-512 tokens
    embedding_model: str = 'text-embedding-3-small'
    embedding_dim: int = 768                      # 128-1536
    top_k: int = 10                               # 3-20
    similarity_threshold: float = 0.5             # 0.0-1.0
    reranking_enabled: bool = True
    category_boost: Dict[str, float] = field(default_factory=dict)  # per-category weights
    max_context_tokens: int = 8192                # 2048-16384
    dedup_threshold: float = 0.9                  # 0.8-1.0

    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        d = asdict(self)
        # Remove internal fitness tracking from serialization
        d.pop('fitness', None)
        d.pop('fitness_details', None)
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class RAGRetrievalOptimizer:
    """GA that evolves optimal RAG retrieval configurations"""

    def __init__(self, population_size: int = 40, mutation_rate: float = 0.25,
                 tournament_size: int = 4, generations: int = 50,
                 seed: Optional[int] = None):
        self.population_size = population_size
        self.initial_mutation_rate = mutation_rate
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.max_generations = generations
        self.generation = 0
        self.convergence_history: List[Dict] = []
        self.stagnation_counter = 0
        self.best_fitness_seen = 0.0

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # Load corpus metadata
        self.category_stats = self._load_category_stats()
        self.available_categories = [
            c['category'] for c in self.category_stats if c.get('stored', 0) > 10
        ]
        self.total_docs = sum(c.get('stored', 0) for c in self.category_stats)

        # Build category-to-doc-count map
        self._cat_counts = {}
        for s in self.category_stats:
            self._cat_counts[s['category']] = s.get('stored', 0)

    def _load_category_stats(self) -> List[Dict]:
        """Fetch category statistics from the REST API"""
        try:
            resp = requests.get(f'{API_BASE}/ga/training-data/stats', timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"WARNING: Could not load category stats: {e}")
            print("Using fallback minimal stats")
            return []

    def _cat_doc_count(self, category: str) -> int:
        return self._cat_counts.get(category, 0)

    # ------------------------------------------------------------------
    # Population initialization
    # ------------------------------------------------------------------

    def create_random_config(self) -> RAGConfig:
        """Generate a random RAG configuration"""
        chunk_size = random.choice([256, 384, 512, 768, 1024, 1536, 2048, 3072, 4096])
        max_overlap = min(512, chunk_size // 2)
        chunk_overlap = random.randint(0, max_overlap)

        embedding_model = random.choice(EMBEDDING_MODELS)
        max_dim = MODEL_DIM_DEFAULTS.get(embedding_model, 1536)
        valid_dims = [d for d in EMBEDDING_DIMS if d <= max_dim]
        embedding_dim = random.choice(valid_dims) if valid_dims else 768

        top_k = random.randint(3, 20)
        similarity_threshold = round(random.uniform(0.15, 0.85), 3)
        reranking_enabled = random.random() < 0.6  # 60% chance of reranking
        max_context_tokens = random.choice([2048, 4096, 6144, 8192, 10240, 12288, 16384])
        dedup_threshold = round(random.uniform(0.80, 0.99), 3)

        # Random category boosts (select 5-25 categories)
        n_boost = random.randint(5, min(25, len(self.available_categories)))
        boosted = random.sample(self.available_categories, n_boost)
        category_boost = {}
        for cat in boosted:
            category_boost[cat] = round(random.uniform(0.5, 3.0), 3)

        return RAGConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            reranking_enabled=reranking_enabled,
            category_boost=category_boost,
            max_context_tokens=max_context_tokens,
            dedup_threshold=dedup_threshold,
        )

    def create_seeded_configs(self) -> List[RAGConfig]:
        """Create domain-expert seed configurations"""
        seeds = []

        # Seed 1: Small-chunk, high-precision config (good for code)
        seeds.append(RAGConfig(
            chunk_size=512,
            chunk_overlap=64,
            embedding_model='text-embedding-3-small',
            embedding_dim=512,
            top_k=5,
            similarity_threshold=0.65,
            reranking_enabled=True,
            category_boost={'github': 2.0, 'java': 1.5, 'python': 1.5,
                            'performance': 1.2, 'algorithms': 1.3},
            max_context_tokens=4096,
            dedup_threshold=0.92,
        ))

        # Seed 2: Large-chunk, broad-retrieval config (good for research)
        seeds.append(RAGConfig(
            chunk_size=2048,
            chunk_overlap=256,
            embedding_model='voyage-3',
            embedding_dim=1024,
            top_k=15,
            similarity_threshold=0.35,
            reranking_enabled=True,
            category_boost={'arxiv-ai': 2.0, 'arxiv-ml': 1.8, 'arxiv-neural': 1.5,
                            'pubmed': 1.5, 'research_paper': 1.5, 'ai': 1.3, 'ml': 1.3},
            max_context_tokens=12288,
            dedup_threshold=0.88,
        ))

        # Seed 3: Medium config balanced for DD-WRT/networking
        seeds.append(RAGConfig(
            chunk_size=1024,
            chunk_overlap=128,
            embedding_model='jina-embeddings-v3',
            embedding_dim=768,
            top_k=10,
            similarity_threshold=0.50,
            reranking_enabled=True,
            category_boost={'ddwrt': 2.5, 'openwrt': 2.0, 'freshtomato': 1.8,
                            'rfc': 1.5, 'linux': 1.3},
            max_context_tokens=8192,
            dedup_threshold=0.90,
        ))

        # Seed 4: Fast/efficient config (low latency)
        seeds.append(RAGConfig(
            chunk_size=768,
            chunk_overlap=64,
            embedding_model='nomic-embed-text',
            embedding_dim=384,
            top_k=5,
            similarity_threshold=0.55,
            reranking_enabled=False,
            category_boost={},
            max_context_tokens=4096,
            dedup_threshold=0.95,
        ))

        # Seed 5: High-coverage medical config
        seeds.append(RAGConfig(
            chunk_size=1536,
            chunk_overlap=192,
            embedding_model='text-embedding-3-large',
            embedding_dim=1024,
            top_k=12,
            similarity_threshold=0.40,
            reranking_enabled=True,
            category_boost={'pubmed': 2.5, 'infectious diseases': 2.0,
                            'epidemiology': 2.0, 'neurology': 1.8,
                            'genetic and genomic medicine': 1.8,
                            'public and global health': 1.5,
                            'psychiatry and clinical psychology': 1.5},
            max_context_tokens=10240,
            dedup_threshold=0.87,
        ))

        return seeds

    # ------------------------------------------------------------------
    # Fitness evaluation (5-component weighted score)
    # ------------------------------------------------------------------

    def calculate_fitness(self, config: RAGConfig) -> float:
        """
        Evaluate a RAG config against synthetic test queries.

        Components (weights):
        1. Retrieval Relevance (0.30): Simulated relevance of top_k results
        2. Coverage (0.20): Fraction of relevant info captured
        3. Efficiency (0.20): Tokens used vs information gained
        4. Diversity (0.15): Chunks cover multiple aspects
        5. Latency Score (0.15): Estimated retrieval speed
        """
        relevance_scores = []
        coverage_scores = []
        efficiency_scores = []
        diversity_scores = []

        for tq in TEST_QUERIES:
            rel, cov, eff, div = self._evaluate_query(config, tq)
            relevance_scores.append(rel)
            coverage_scores.append(cov)
            efficiency_scores.append(eff)
            diversity_scores.append(div)

        relevance = float(np.mean(relevance_scores))
        coverage = float(np.mean(coverage_scores))
        efficiency = float(np.mean(efficiency_scores))
        diversity = float(np.mean(diversity_scores))
        latency = self._estimate_latency_score(config)

        fitness = (
            relevance * 0.30 +
            coverage * 0.20 +
            efficiency * 0.20 +
            diversity * 0.15 +
            latency * 0.15
        )

        config.fitness = round(fitness, 5)
        config.fitness_details = {
            'relevance': round(relevance, 4),
            'coverage': round(coverage, 4),
            'efficiency': round(efficiency, 4),
            'diversity': round(diversity, 4),
            'latency': round(latency, 4),
            'weighted_fitness': round(fitness, 5),
        }

        return fitness

    def _evaluate_query(self, config: RAGConfig, test_query: Dict) -> Tuple[float, float, float, float]:
        """Evaluate a single test query against the config. Returns (relevance, coverage, efficiency, diversity)."""

        query_text = test_query['query']
        relevant_cats = test_query['relevant_categories']
        domain = test_query['domain']

        # --- Relevance ---
        # Simulate retrieval relevance based on how well the config parameters
        # match the query's domain characteristics.

        # Chunk size appropriateness: code queries prefer smaller chunks, research larger
        ideal_chunk = self._ideal_chunk_for_domain(domain)
        chunk_ratio = min(config.chunk_size, ideal_chunk) / max(config.chunk_size, ideal_chunk)
        chunk_fit = 0.6 + 0.4 * chunk_ratio  # 0.6..1.0

        # Category boost relevance: does the config boost the right categories?
        boost_overlap = 0.0
        if config.category_boost:
            boosted_cats = set(config.category_boost.keys())
            relevant_set = set(relevant_cats)
            overlap = boosted_cats & relevant_set
            if overlap:
                boost_values = [config.category_boost[c] for c in overlap]
                avg_boost = np.mean(boost_values)
                boost_overlap = (len(overlap) / len(relevant_set)) * min(1.0, avg_boost / 2.0)
            # Penalize over-boosting irrelevant categories
            irrelevant_boosts = boosted_cats - relevant_set
            if irrelevant_boosts and len(boosted_cats) > 0:
                noise_ratio = len(irrelevant_boosts) / len(boosted_cats)
                boost_overlap *= (1.0 - 0.3 * noise_ratio)

        # Embedding model quality factor (some models encode semantics better)
        model_quality = self._model_quality_factor(config.embedding_model)

        # Embedding dimension: higher dims capture more but with diminishing returns
        dim_factor = min(1.0, np.log2(config.embedding_dim) / np.log2(1536))

        # Similarity threshold: too high misses relevant chunks, too low adds noise
        threshold_penalty = 0.0
        if config.similarity_threshold > 0.75:
            threshold_penalty = (config.similarity_threshold - 0.75) * 2.0
        elif config.similarity_threshold < 0.25:
            threshold_penalty = (0.25 - config.similarity_threshold) * 1.5

        relevance = (
            chunk_fit * 0.25 +
            boost_overlap * 0.25 +
            model_quality * 0.25 +
            dim_factor * 0.15 +
            (1.0 - threshold_penalty) * 0.10
        )
        relevance = max(0.0, min(1.0, relevance))

        # --- Coverage ---
        # How much of the relevant information space is captured

        # More top_k = more coverage, but diminishing returns
        topk_coverage = 1.0 - math.exp(-config.top_k / 8.0)

        # Larger chunks = more context per retrieval
        chunk_coverage = 1.0 - math.exp(-config.chunk_size / 1500.0)

        # Overlap prevents info loss at chunk boundaries
        if config.chunk_size > 0:
            overlap_ratio = config.chunk_overlap / config.chunk_size
        else:
            overlap_ratio = 0
        overlap_benefit = min(1.0, overlap_ratio * 3.0)  # up to ~33% overlap is helpful

        # Max context tokens determines total retrievable info
        context_coverage = min(1.0, config.max_context_tokens / 8192.0)

        # Category boost coverage: are all relevant categories boosted?
        cat_coverage = 0.5  # base
        if config.category_boost and relevant_cats:
            covered = sum(1 for c in relevant_cats if c in config.category_boost)
            cat_coverage = 0.3 + 0.7 * (covered / len(relevant_cats))

        coverage = (
            topk_coverage * 0.25 +
            chunk_coverage * 0.20 +
            overlap_benefit * 0.15 +
            context_coverage * 0.20 +
            cat_coverage * 0.20
        )
        coverage = max(0.0, min(1.0, coverage))

        # --- Efficiency ---
        # Tokens used per unit of information gained

        # Total tokens consumed = top_k * chunk_size (approximate)
        tokens_consumed = config.top_k * config.chunk_size
        # Overlap adds redundant tokens
        if config.chunk_overlap > 0:
            overlap_waste = (config.chunk_overlap / config.chunk_size) * tokens_consumed
            tokens_consumed += overlap_waste * 0.5  # partial waste

        # Ideal is max_context_tokens worth of useful info
        # Penalize if tokens_consumed >> max_context_tokens (wasted computation)
        if tokens_consumed > config.max_context_tokens:
            waste_ratio = tokens_consumed / config.max_context_tokens
            eff_penalty = min(0.5, (waste_ratio - 1.0) * 0.3)
        else:
            eff_penalty = 0.0

        # Reranking costs compute but improves precision -> net positive for moderate top_k
        rerank_bonus = 0.0
        if config.reranking_enabled:
            if config.top_k > 8:
                rerank_bonus = 0.15  # reranking helps more with many candidates
            else:
                rerank_bonus = 0.05

        # Dedup threshold: aggressive dedup (lower threshold) saves tokens
        dedup_savings = (1.0 - config.dedup_threshold) * 2.0  # 0-0.4

        # Information density: smaller dims are cheaper to compute
        dim_efficiency = 1.0 - (config.embedding_dim / 2048.0) * 0.3

        efficiency = 0.7 - eff_penalty + rerank_bonus + dedup_savings * 0.1 + dim_efficiency * 0.15
        efficiency = max(0.0, min(1.0, efficiency))

        # --- Diversity ---
        # Retrieved chunks should cover multiple aspects

        # Higher top_k with dedup -> more diverse results
        diversity_base = min(1.0, config.top_k / 12.0)

        # Dedup removes near-duplicates, increasing diversity
        dedup_diversity = 1.0 - config.dedup_threshold  # lower threshold = more aggressive dedup
        dedup_factor = 0.5 + dedup_diversity * 2.5

        # Category boosts spread across multiple categories help diversity
        n_boosted = len(config.category_boost)
        boost_diversity = min(1.0, n_boosted / 10.0)

        # Similarity threshold too high limits diversity
        threshold_diversity = 1.0
        if config.similarity_threshold > 0.70:
            threshold_diversity = 1.0 - (config.similarity_threshold - 0.70) * 2.0

        # Chunk overlap too high means adjacent chunks are similar
        overlap_diversity = 1.0
        if config.chunk_size > 0:
            ov_ratio = config.chunk_overlap / config.chunk_size
            if ov_ratio > 0.4:
                overlap_diversity = 1.0 - (ov_ratio - 0.4) * 1.5

        diversity = (
            diversity_base * 0.30 +
            dedup_factor * 0.25 +
            boost_diversity * 0.20 +
            threshold_diversity * 0.15 +
            overlap_diversity * 0.10
        )
        diversity = max(0.0, min(1.0, diversity))

        return relevance, coverage, efficiency, diversity

    def _ideal_chunk_for_domain(self, domain: str) -> int:
        """Return ideal chunk size for a domain"""
        ideal = {
            'code': 512,
            'networking': 1024,
            'standards': 1536,
            'ai': 1024,
            'medical': 1536,
            'cross-domain': 1024,
            'algorithms': 768,
            'research': 2048,
        }
        return ideal.get(domain, 1024)

    def _model_quality_factor(self, model: str) -> float:
        """Estimated embedding quality (0-1) based on MTEB benchmarks"""
        quality = {
            'text-embedding-3-small': 0.78,
            'text-embedding-3-large': 0.92,
            'voyage-2': 0.88,
            'voyage-3': 0.91,
            'jina-embeddings-v3': 0.87,
            'nomic-embed-text': 0.76,
            'bge-large-en-v1.5': 0.84,
            'gte-large': 0.83,
        }
        return quality.get(model, 0.75)

    def _estimate_latency_score(self, config: RAGConfig) -> float:
        """
        Estimate retrieval latency score (higher = faster).
        Based on embedding dim, top_k, model speed, and reranking overhead.
        """
        # Base speed from model
        speed_factor = MODEL_SPEED_FACTORS.get(config.embedding_model, 1.0)

        # Dimension impact: higher dims = slower vector search
        dim_cost = config.embedding_dim / 1536.0  # normalized

        # top_k: scanning more candidates is slower
        topk_cost = config.top_k / 20.0

        # Reranking adds a secondary pass
        rerank_cost = 0.15 if config.reranking_enabled else 0.0

        # Chunk size affects indexing overhead
        chunk_cost = config.chunk_size / 4096.0

        total_cost = (
            speed_factor * 0.30 +
            dim_cost * 0.25 +
            topk_cost * 0.20 +
            rerank_cost * 0.10 +
            chunk_cost * 0.15
        )

        # Invert: lower cost = higher score
        latency_score = 1.0 - min(1.0, total_cost)
        return max(0.0, latency_score)

    # ------------------------------------------------------------------
    # Genetic operators
    # ------------------------------------------------------------------

    def tournament_selection(self, population: List[RAGConfig]) -> RAGConfig:
        """Select parent via tournament"""
        tournament = random.sample(population, min(self.tournament_size, len(population)))
        return max(tournament, key=lambda c: c.fitness or 0)

    def crossover(self, parent1: RAGConfig, parent2: RAGConfig) -> RAGConfig:
        """Uniform crossover between two parents"""
        child = RAGConfig(
            chunk_size=random.choice([parent1.chunk_size, parent2.chunk_size]),
            chunk_overlap=random.choice([parent1.chunk_overlap, parent2.chunk_overlap]),
            embedding_model=random.choice([parent1.embedding_model, parent2.embedding_model]),
            embedding_dim=random.choice([parent1.embedding_dim, parent2.embedding_dim]),
            top_k=random.choice([parent1.top_k, parent2.top_k]),
            similarity_threshold=random.choice([parent1.similarity_threshold,
                                                 parent2.similarity_threshold]),
            reranking_enabled=random.choice([parent1.reranking_enabled,
                                              parent2.reranking_enabled]),
            max_context_tokens=random.choice([parent1.max_context_tokens,
                                               parent2.max_context_tokens]),
            dedup_threshold=random.choice([parent1.dedup_threshold,
                                            parent2.dedup_threshold]),
        )

        # Merge category boosts: blend from both parents
        all_cats = set(list(parent1.category_boost.keys()) +
                       list(parent2.category_boost.keys()))
        child_boost = {}
        for cat in all_cats:
            w1 = parent1.category_boost.get(cat, 0)
            w2 = parent2.category_boost.get(cat, 0)
            if random.random() < 0.5:
                chosen = w1 if w1 > 0 else w2
            else:
                chosen = w2 if w2 > 0 else w1
            if chosen > 0:
                child_boost[cat] = chosen
        child.category_boost = child_boost

        # Validate constraints
        child = self._validate_config(child)
        return child

    def mutate(self, config: RAGConfig) -> None:
        """Apply adaptive mutation to a config"""
        if random.random() >= self.mutation_rate:
            return

        n_mutations = random.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]

        mutations = random.sample([
            'chunk_size', 'chunk_overlap', 'embedding_model', 'embedding_dim',
            'top_k', 'similarity_threshold', 'reranking', 'category_boost',
            'max_context_tokens', 'dedup_threshold'
        ], min(n_mutations, 10))

        for mutation in mutations:
            if mutation == 'chunk_size':
                delta = random.choice([-512, -256, -128, 128, 256, 512])
                config.chunk_size = max(256, min(4096, config.chunk_size + delta))

            elif mutation == 'chunk_overlap':
                delta = random.randint(-64, 64)
                max_overlap = min(512, config.chunk_size // 2)
                config.chunk_overlap = max(0, min(max_overlap, config.chunk_overlap + delta))

            elif mutation == 'embedding_model':
                config.embedding_model = random.choice(EMBEDDING_MODELS)
                # Adjust dim to be valid for new model
                max_dim = MODEL_DIM_DEFAULTS.get(config.embedding_model, 1536)
                if config.embedding_dim > max_dim:
                    valid = [d for d in EMBEDDING_DIMS if d <= max_dim]
                    config.embedding_dim = random.choice(valid) if valid else max_dim

            elif mutation == 'embedding_dim':
                max_dim = MODEL_DIM_DEFAULTS.get(config.embedding_model, 1536)
                valid = [d for d in EMBEDDING_DIMS if d <= max_dim]
                if valid:
                    config.embedding_dim = random.choice(valid)

            elif mutation == 'top_k':
                delta = random.randint(-3, 3)
                config.top_k = max(3, min(20, config.top_k + delta))

            elif mutation == 'similarity_threshold':
                delta = random.uniform(-0.15, 0.15)
                config.similarity_threshold = round(
                    max(0.0, min(1.0, config.similarity_threshold + delta)), 3)

            elif mutation == 'reranking':
                config.reranking_enabled = not config.reranking_enabled

            elif mutation == 'category_boost':
                action = random.choice(['add', 'remove', 'adjust'])
                if action == 'add' and len(config.category_boost) < 30:
                    unused = [c for c in self.available_categories
                              if c not in config.category_boost]
                    if unused:
                        cat = random.choice(unused)
                        config.category_boost[cat] = round(random.uniform(0.5, 2.5), 3)
                elif action == 'remove' and len(config.category_boost) > 2:
                    cat = random.choice(list(config.category_boost.keys()))
                    del config.category_boost[cat]
                elif action == 'adjust' and config.category_boost:
                    cat = random.choice(list(config.category_boost.keys()))
                    factor = random.uniform(0.5, 2.0)
                    config.category_boost[cat] = round(
                        max(0.1, min(5.0, config.category_boost[cat] * factor)), 3)

            elif mutation == 'max_context_tokens':
                delta = random.choice([-2048, -1024, 1024, 2048])
                config.max_context_tokens = max(2048, min(16384,
                                                          config.max_context_tokens + delta))

            elif mutation == 'dedup_threshold':
                delta = random.uniform(-0.05, 0.05)
                config.dedup_threshold = round(
                    max(0.80, min(1.0, config.dedup_threshold + delta)), 3)

        config = self._validate_config(config)

    def _validate_config(self, config: RAGConfig) -> RAGConfig:
        """Ensure config respects all constraints"""
        config.chunk_size = max(256, min(4096, config.chunk_size))
        config.chunk_overlap = max(0, min(min(512, config.chunk_size // 2),
                                          config.chunk_overlap))
        config.top_k = max(3, min(20, config.top_k))
        config.similarity_threshold = max(0.0, min(1.0, config.similarity_threshold))
        config.max_context_tokens = max(2048, min(16384, config.max_context_tokens))
        config.dedup_threshold = max(0.80, min(1.0, config.dedup_threshold))

        max_dim = MODEL_DIM_DEFAULTS.get(config.embedding_model, 1536)
        if config.embedding_dim > max_dim:
            valid = [d for d in EMBEDDING_DIMS if d <= max_dim]
            config.embedding_dim = max(valid) if valid else 768

        if config.embedding_dim not in EMBEDDING_DIMS:
            closest = min(EMBEDDING_DIMS, key=lambda d: abs(d - config.embedding_dim))
            config.embedding_dim = closest

        return config

    def _adapt_mutation_rate(self) -> None:
        """Increase mutation rate during stagnation, decrease during improvement"""
        if self.stagnation_counter > 5:
            self.mutation_rate = min(0.6, self.initial_mutation_rate * (1 + self.stagnation_counter * 0.1))
        else:
            self.mutation_rate = max(0.10, self.initial_mutation_rate * 0.9)

    # ------------------------------------------------------------------
    # Evolution loop
    # ------------------------------------------------------------------

    def evolve_generation(self, population: List[RAGConfig]) -> List[RAGConfig]:
        """Produce next generation"""
        population.sort(key=lambda c: c.fitness or 0, reverse=True)

        # Elitism: keep top 20%
        elite_size = max(2, self.population_size // 5)
        new_population = list(population[:elite_size])

        # Fill rest via crossover + mutation
        while len(new_population) < self.population_size:
            parent1 = self.tournament_selection(population)
            parent2 = self.tournament_selection(population)
            child = self.crossover(parent1, parent2)
            self.mutate(child)
            child.fitness = self.calculate_fitness(child)
            new_population.append(child)

        return new_population

    def run(self, generations: Optional[int] = None) -> RAGConfig:
        """Run the genetic algorithm"""
        if generations is None:
            generations = self.max_generations

        print("=" * 70)
        print("  GA RAG Retrieval Optimizer")
        print("=" * 70)
        print(f"Categories available:   {len(self.available_categories)}")
        print(f"Total documents:        {self.total_docs:,}")
        print(f"Test queries:           {len(TEST_QUERIES)}")
        print(f"Population size:        {self.population_size}")
        print(f"Generations:            {generations}")
        print(f"Tournament size:        {self.tournament_size}")
        print(f"Initial mutation rate:  {self.initial_mutation_rate}")
        print("=" * 70)
        print()

        # Initialize population: seeds + random
        population = self.create_seeded_configs()
        while len(population) < self.population_size:
            population.append(self.create_random_config())

        # Evaluate initial population
        for config in population:
            config.fitness = self.calculate_fitness(config)

        best_ever = max(population, key=lambda c: c.fitness or 0)
        self.best_fitness_seen = best_ever.fitness or 0

        avg_fitness = float(np.mean([c.fitness for c in population if c.fitness is not None]))
        print(f"Gen  0: Best={best_ever.fitness:.5f}  Avg={avg_fitness:.5f}  "
              f"Model={best_ever.embedding_model}  Chunk={best_ever.chunk_size}  "
              f"TopK={best_ever.top_k}")
        self._print_fitness_details(best_ever)

        self._record_convergence(0, population, best_ever)

        # Evolution loop
        for gen in range(1, generations + 1):
            self.generation = gen
            self._adapt_mutation_rate()

            population = self.evolve_generation(population)
            current_best = max(population, key=lambda c: c.fitness or 0)
            avg_fitness = float(np.mean([c.fitness for c in population if c.fitness is not None]))
            worst_fitness = float(min(c.fitness for c in population if c.fitness is not None))

            improved = False
            if (current_best.fitness or 0) > self.best_fitness_seen:
                best_ever = current_best
                self.best_fitness_seen = best_ever.fitness or 0
                self.stagnation_counter = 0
                improved = True
                print(f"Gen {gen:2d}: NEW BEST={current_best.fitness:.5f}  "
                      f"Avg={avg_fitness:.5f}  "
                      f"Model={current_best.embedding_model}  "
                      f"Chunk={current_best.chunk_size}  "
                      f"TopK={current_best.top_k}  "
                      f"MutRate={self.mutation_rate:.3f}")
                self._print_fitness_details(current_best)
            else:
                self.stagnation_counter += 1
                if gen % 5 == 0 or gen == generations:
                    print(f"Gen {gen:2d}: Best={current_best.fitness:.5f}  "
                          f"Avg={avg_fitness:.5f}  "
                          f"Worst={worst_fitness:.5f}  "
                          f"Stagnation={self.stagnation_counter}  "
                          f"MutRate={self.mutation_rate:.3f}")

            self._record_convergence(gen, population, current_best)

        # Final report
        self._print_final_report(best_ever)
        self._store_best(best_ever)

        return best_ever

    def _print_fitness_details(self, config: RAGConfig) -> None:
        """Print fitness component breakdown"""
        if config.fitness_details:
            d = config.fitness_details
            print(f"       Rel={d['relevance']:.4f}  Cov={d['coverage']:.4f}  "
                  f"Eff={d['efficiency']:.4f}  Div={d['diversity']:.4f}  "
                  f"Lat={d['latency']:.4f}")

    def _print_final_report(self, best: RAGConfig) -> None:
        """Print detailed final report"""
        print()
        print("=" * 70)
        print("  BEST RAG CONFIGURATION FOUND")
        print("=" * 70)
        print(f"  Fitness Score:        {best.fitness:.5f}")
        print()
        print("  --- Retrieval Parameters ---")
        print(f"  Chunk Size:           {best.chunk_size} tokens")
        print(f"  Chunk Overlap:        {best.chunk_overlap} tokens")
        print(f"  Embedding Model:      {best.embedding_model}")
        print(f"  Embedding Dimension:  {best.embedding_dim}")
        print(f"  Top K:                {best.top_k}")
        print(f"  Similarity Threshold: {best.similarity_threshold}")
        print(f"  Reranking Enabled:    {best.reranking_enabled}")
        print(f"  Max Context Tokens:   {best.max_context_tokens}")
        print(f"  Dedup Threshold:      {best.dedup_threshold}")
        print()
        print("  --- Fitness Components ---")
        if best.fitness_details:
            for k, v in best.fitness_details.items():
                print(f"  {k:24s} {v}")
        print()
        if best.category_boost:
            print("  --- Category Boosts (sorted by weight) ---")
            sorted_boosts = sorted(best.category_boost.items(), key=lambda x: -x[1])
            for cat, weight in sorted_boosts:
                doc_count = self._cat_doc_count(cat)
                print(f"  {cat:40s} boost={weight:.3f}  (docs={doc_count:,})")
        print()
        print("  --- Convergence ---")
        if self.convergence_history:
            first = self.convergence_history[0]
            last = self.convergence_history[-1]
            improvement = (last['best_fitness'] - first['best_fitness'])
            print(f"  Initial best:  {first['best_fitness']:.5f}")
            print(f"  Final best:    {last['best_fitness']:.5f}")
            print(f"  Improvement:   {improvement:+.5f}")
            print(f"  Generations:   {len(self.convergence_history)}")
        print("=" * 70)

    def _record_convergence(self, gen: int, population: List[RAGConfig],
                             best: RAGConfig) -> None:
        """Record convergence data and post to API"""
        fitnesses = [c.fitness for c in population if c.fitness is not None]
        if not fitnesses:
            return

        # Measure population diversity via unique embedding model + chunk combos
        unique_configs = set()
        for c in population:
            key = (c.embedding_model, c.chunk_size, c.top_k,
                   c.reranking_enabled, len(c.category_boost))
            unique_configs.add(key)
        diversity = len(unique_configs) / len(population)

        record = {
            'generation': gen,
            'best_fitness': float(best.fitness or 0),
            'avg_fitness': float(np.mean(fitnesses)),
            'worst_fitness': float(min(fitnesses)),
            'std_fitness': float(np.std(fitnesses)),
            'diversity': float(diversity),
            'mutation_rate': float(self.mutation_rate),
        }
        self.convergence_history.append(record)

        # Post to API
        try:
            requests.post(f'{API_BASE}/ga/convergence', json={
                'use_case': 'rag-retrieval-optimizer',
                'generation': gen,
                'island_id': 0,
                'best_fitness': record['best_fitness'],
                'avg_fitness': record['avg_fitness'],
                'diversity': record['diversity'],
            }, timeout=5)
        except Exception:
            pass  # Non-critical

    def _store_best(self, config: RAGConfig) -> None:
        """Store best solution via REST API"""
        try:
            payload = {
                'use_case': 'rag-retrieval-optimizer',
                'chromosome': json.dumps(config.to_dict()),
                'fitness': float(config.fitness or 0),
                'fitness_details': json.dumps(config.fitness_details or {}),
                'generation_found': self.generation,
                'notes': (
                    f'Best RAG config: {config.embedding_model} '
                    f'dim={config.embedding_dim} chunk={config.chunk_size} '
                    f'topk={config.top_k} rerank={config.reranking_enabled} '
                    f'threshold={config.similarity_threshold} '
                    f'cats={len(config.category_boost)}'
                ),
            }
            resp = requests.post(f'{API_BASE}/ga/best-solutions', json=payload, timeout=10)
            if resp.ok:
                print("Stored best config in ga.best_solutions via REST API")
            else:
                print(f"API returned {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"Failed to store best config: {e}")

    def export_config(self, config: RAGConfig, output_path: str) -> None:
        """Export best config as JSON for use by RAG pipeline"""
        export = {
            'rag_config': config.to_dict(),
            'fitness': {
                'score': config.fitness,
                'components': config.fitness_details,
            },
            'convergence': {
                'generations_run': len(self.convergence_history),
                'initial_fitness': (self.convergence_history[0]['best_fitness']
                                    if self.convergence_history else None),
                'final_fitness': (self.convergence_history[-1]['best_fitness']
                                  if self.convergence_history else None),
                'stagnation_at_end': self.stagnation_counter,
            },
            'test_queries_count': len(TEST_QUERIES),
            'corpus_stats': {
                'total_documents': self.total_docs,
                'categories': len(self.available_categories),
            },
            'metadata': {
                'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'population_size': self.population_size,
                'mutation_rate_initial': self.initial_mutation_rate,
                'tournament_size': self.tournament_size,
            },
        }

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(export, f, indent=2)
        print(f"Exported best RAG config to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='GA RAG Retrieval Optimizer - Evolve optimal chunking/retrieval config '
                    'for RAG over 120K+ documents'
    )
    parser.add_argument('--population', type=int, default=40,
                        help='Population size (default: 40)')
    parser.add_argument('--generations', type=int, default=50,
                        help='Number of generations (default: 50)')
    parser.add_argument('--mutation-rate', type=float, default=0.25,
                        help='Initial mutation rate (default: 0.25)')
    parser.add_argument('--tournament-size', type=int, default=4,
                        help='Tournament size for selection (default: 4)')
    parser.add_argument('--seed', type=int, default=None,
                        help='Random seed for reproducibility')
    parser.add_argument('--output', type=str, default=None,
                        help='Output path for best config JSON '
                             '(default: tools/best_rag_config.json)')
    args = parser.parse_args()

    optimizer = RAGRetrievalOptimizer(
        population_size=args.population,
        mutation_rate=args.mutation_rate,
        tournament_size=args.tournament_size,
        generations=args.generations,
        seed=args.seed,
    )

    best = optimizer.run(generations=args.generations)

    # Export config
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'best_rag_config.json'
        )
    optimizer.export_config(best, output_path)

    print("\nDone! Use best_rag_config.json with your RAG pipeline.")


if __name__ == '__main__':
    main()
