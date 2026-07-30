#!/usr/bin/env python3
"""GA Meta-Optimizer: Evolve pipeline configurations across all 9 techniques.

A single PipelineChromosome encodes ~65 genes controlling which techniques are
active, their parameters, routing strategy, and model pool preferences. The GA
discovers interaction effects between techniques that manual tuning cannot find.

MAP-Elites maintains a quality-diversity archive across cost/latency/technique
niches. Best evolved configs become Thompson Sampling strategies for online routing.

Usage:
    # Quick validation (10 generations, 10 benchmarks)
    python3 ga_pipeline_optimizer.py --quick

    # Full run (100 generations, all 30 benchmarks)
    python3 ga_pipeline_optimizer.py

    # Resume from checkpoint
    python3 ga_pipeline_optimizer.py --resume checkpoints/gen_050.json
"""
import argparse
import copy
import json
import logging
import math
import os
import random
import statistics
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('meta_optimizer')

API_BASE = os.environ.get('API_BASE', 'http://aio-01:5000')
CHECKPOINT_DIR = Path(__file__).parent / 'checkpoints'
RESULTS_DIR = Path(__file__).parent / 'ga_results'


# ─── Pipeline Chromosome ─────────────────────────────────────────────────────

ROUTING_STRATEGIES = ['cascade_first', 'bandit_first', 'complexity_route']
CASCADE_TIERS = ['free_small', 'free_large', 'paid']
CRAG_MODES = ['hybrid', 'fulltext', 'vector']


@dataclass
class PipelineChromosome:
    """~65-gene chromosome encoding a complete pipeline configuration."""

    # Activation flags (9 booleans)
    use_thompson: bool = True
    use_contextual_bandits: bool = True
    use_cascade: bool = True
    use_moa: bool = False
    use_crag: bool = True
    use_graph_rag: bool = False
    use_contextual_retrieval: bool = False
    use_evoprompt: bool = False
    use_map_elites: bool = False

    # Thompson Sampling params (3)
    ts_decay_factor: float = 0.995
    ts_window_size: int = 100
    ts_round_hours: float = 6.0

    # LinUCB params (2)
    linucb_alpha: float = 1.0
    linucb_regularisation: float = 1.0

    # Cascade params (4)
    cascade_threshold: float = 0.7
    cascade_max_tier: str = 'free_large'
    cascade_max_tokens: int = 2048
    cascade_timeout: int = 60

    # MoA params (5)
    moa_num_proposers: int = 3
    moa_num_aggregators: int = 1
    moa_num_layers: int = 2
    moa_temperature: float = 0.7
    moa_max_tokens: int = 4096

    # CRAG params (3)
    crag_limit: int = 5
    crag_mode: str = 'hybrid'
    crag_max_fallback_rounds: int = 2

    # Graph RAG params (3)
    graph_max_hops: int = 2
    graph_expansion: bool = True
    graph_excerpt_len: int = 1500

    # Pipeline routing (1)
    routing_strategy: str = 'cascade_first'

    # Model pool params (3)
    proposer_pool_size: int = 4
    free_model_preference: float = 0.8
    diversity_weight: float = 0.5

    # Fitness (set after evaluation)
    fitness: Optional[Dict] = field(default=None, repr=False)

    def active_techniques(self) -> Dict[str, bool]:
        return {
            'thompson': self.use_thompson,
            'contextual_bandits': self.use_contextual_bandits,
            'cascade': self.use_cascade,
            'moa': self.use_moa,
            'crag': self.use_crag,
            'graph_rag': self.use_graph_rag,
            'contextual_retrieval': self.use_contextual_retrieval,
            'evoprompt': self.use_evoprompt,
            'map_elites': self.use_map_elites,
        }

    def active_count(self) -> int:
        return sum(self.active_techniques().values())

    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop('fitness', None)
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> 'PipelineChromosome':
        data = {k: v for k, v in data.items() if k != 'fitness'}
        return cls(**data)

    @classmethod
    def random(cls) -> 'PipelineChromosome':
        return cls(
            use_thompson=random.random() > 0.3,
            use_contextual_bandits=random.random() > 0.5,
            use_cascade=random.random() > 0.2,
            use_moa=random.random() > 0.6,
            use_crag=random.random() > 0.3,
            use_graph_rag=random.random() > 0.6,
            use_contextual_retrieval=random.random() > 0.7,
            use_evoprompt=random.random() > 0.8,
            use_map_elites=random.random() > 0.8,
            ts_decay_factor=round(random.uniform(0.9, 0.999), 4),
            ts_window_size=random.randint(10, 500),
            ts_round_hours=round(random.uniform(1.0, 24.0), 1),
            linucb_alpha=round(random.uniform(0.1, 5.0), 2),
            linucb_regularisation=round(random.uniform(0.1, 10.0), 2),
            cascade_threshold=round(random.uniform(0.3, 0.95), 2),
            cascade_max_tier=random.choice(CASCADE_TIERS),
            cascade_max_tokens=random.choice([256, 512, 1024, 2048, 4096, 8192]),
            cascade_timeout=random.randint(10, 120),
            moa_num_proposers=random.randint(2, 6),
            moa_num_aggregators=random.randint(1, 3),
            moa_num_layers=random.randint(2, 4),
            moa_temperature=round(random.uniform(0.1, 1.5), 2),
            moa_max_tokens=random.choice([1024, 2048, 4096, 8192]),
            crag_limit=random.randint(3, 20),
            crag_mode=random.choice(CRAG_MODES),
            crag_max_fallback_rounds=random.randint(1, 4),
            graph_max_hops=random.randint(1, 3),
            graph_expansion=random.random() > 0.3,
            graph_excerpt_len=random.choice([500, 1000, 1500, 2000, 3000]),
            routing_strategy=random.choice(ROUTING_STRATEGIES),
            proposer_pool_size=random.randint(2, 8),
            free_model_preference=round(random.uniform(0.0, 1.0), 2),
            diversity_weight=round(random.uniform(0.0, 1.0), 2),
        )

    # --- Seeded starting points ---

    @classmethod
    def minimal(cls) -> 'PipelineChromosome':
        """Baseline: cascade only."""
        return cls(
            use_thompson=False, use_contextual_bandits=False,
            use_cascade=True, use_moa=False, use_crag=False,
            use_graph_rag=False, use_contextual_retrieval=False,
            use_evoprompt=False, use_map_elites=False,
            cascade_threshold=0.5, cascade_max_tier='free_large',
            routing_strategy='cascade_first',
        )

    @classmethod
    def full_pipeline(cls) -> 'PipelineChromosome':
        """Kitchen sink: everything on, default params."""
        return cls(
            use_thompson=True, use_contextual_bandits=True,
            use_cascade=True, use_moa=True, use_crag=True,
            use_graph_rag=True, use_contextual_retrieval=True,
            use_evoprompt=True, use_map_elites=True,
        )

    @classmethod
    def cost_optimized(cls) -> 'PipelineChromosome':
        """Cheap and fast: cascade + bandits, free only."""
        return cls(
            use_thompson=True, use_contextual_bandits=True,
            use_cascade=True, use_moa=False, use_crag=False,
            use_graph_rag=False, use_contextual_retrieval=False,
            use_evoprompt=False, use_map_elites=False,
            cascade_threshold=0.4, cascade_max_tier='free_small',
            cascade_max_tokens=1024, cascade_timeout=30,
            free_model_preference=1.0,
            routing_strategy='bandit_first',
        )

    @classmethod
    def quality_optimized(cls) -> 'PipelineChromosome':
        """Maximum quality: MoA + CRAG + Graph RAG, paid tier."""
        return cls(
            use_thompson=True, use_contextual_bandits=True,
            use_cascade=True, use_moa=True, use_crag=True,
            use_graph_rag=True, use_contextual_retrieval=True,
            use_evoprompt=False, use_map_elites=False,
            cascade_threshold=0.85, cascade_max_tier='paid',
            cascade_max_tokens=4096,
            moa_num_proposers=5, moa_num_layers=3,
            crag_limit=10, graph_max_hops=3,
            routing_strategy='complexity_route',
            free_model_preference=0.3,
        )

    @classmethod
    def balanced(cls) -> 'PipelineChromosome':
        """Balanced: cascade + CRAG + Thompson Sampling."""
        return cls(
            use_thompson=True, use_contextual_bandits=False,
            use_cascade=True, use_moa=False, use_crag=True,
            use_graph_rag=False, use_contextual_retrieval=False,
            use_evoprompt=False, use_map_elites=False,
            cascade_threshold=0.7, cascade_max_tier='free_large',
            crag_limit=5, crag_mode='hybrid',
            routing_strategy='cascade_first',
        )


# ─── Genetic Operators ───────────────────────────────────────────────────────

BOOL_GENES = [
    'use_thompson', 'use_contextual_bandits', 'use_cascade', 'use_moa',
    'use_crag', 'use_graph_rag', 'use_contextual_retrieval',
    'use_evoprompt', 'use_map_elites', 'graph_expansion',
]

FLOAT_GENES = {
    'ts_decay_factor': (0.9, 0.999),
    'ts_round_hours': (1.0, 24.0),
    'linucb_alpha': (0.1, 5.0),
    'linucb_regularisation': (0.1, 10.0),
    'cascade_threshold': (0.3, 0.95),
    'moa_temperature': (0.1, 1.5),
    'free_model_preference': (0.0, 1.0),
    'diversity_weight': (0.0, 1.0),
}

INT_GENES = {
    'ts_window_size': (10, 500),
    'cascade_max_tokens': [256, 512, 1024, 2048, 4096, 8192],
    'cascade_timeout': (10, 120),
    'moa_num_proposers': (2, 6),
    'moa_num_aggregators': (1, 3),
    'moa_num_layers': (2, 4),
    'moa_max_tokens': [1024, 2048, 4096, 8192],
    'crag_limit': (3, 20),
    'crag_max_fallback_rounds': (1, 4),
    'graph_max_hops': (1, 3),
    'graph_excerpt_len': [500, 1000, 1500, 2000, 3000],
    'proposer_pool_size': (2, 8),
}

CHOICE_GENES = {
    'cascade_max_tier': CASCADE_TIERS,
    'crag_mode': CRAG_MODES,
    'routing_strategy': ROUTING_STRATEGIES,
}


def uniform_crossover(p1: PipelineChromosome, p2: PipelineChromosome) -> Tuple[PipelineChromosome, PipelineChromosome]:
    """Per-gene uniform crossover with technique-group awareness."""
    d1, d2 = p1.to_dict(), p2.to_dict()
    c1, c2 = {}, {}

    for gene in d1:
        if random.random() < 0.5:
            c1[gene] = d1[gene]
            c2[gene] = d2[gene]
        else:
            c1[gene] = d2[gene]
            c2[gene] = d1[gene]

    return PipelineChromosome.from_dict(c1), PipelineChromosome.from_dict(c2)


def mutate(chromosome: PipelineChromosome, rate: float = 0.15) -> PipelineChromosome:
    """Mutate with adaptive per-gene probability."""
    d = chromosome.to_dict()

    for gene in BOOL_GENES:
        if gene in d and random.random() < rate:
            d[gene] = not d[gene]

    for gene, (lo, hi) in FLOAT_GENES.items():
        if gene in d and random.random() < rate:
            delta = (hi - lo) * random.gauss(0, 0.2)
            d[gene] = round(max(lo, min(hi, d[gene] + delta)), 4)

    for gene, spec in INT_GENES.items():
        if gene in d and random.random() < rate:
            if isinstance(spec, list):
                d[gene] = random.choice(spec)
            else:
                lo, hi = spec
                delta = random.randint(-2, 2)
                d[gene] = max(lo, min(hi, d[gene] + delta))

    for gene, choices in CHOICE_GENES.items():
        if gene in d and random.random() < rate:
            d[gene] = random.choice(choices)

    return PipelineChromosome.from_dict(d)


def tournament_select(population: List[PipelineChromosome], k: int = 5) -> PipelineChromosome:
    """Tournament selection: pick best of k random individuals."""
    candidates = random.sample(population, min(k, len(population)))
    return max(candidates, key=lambda c: (c.fitness or {}).get('total', 0))


# ─── MAP-Elites ──────────────────────────────────────────────────────────────

@dataclass
class MapElitesArchive:
    """Quality-diversity archive across cost/latency/technique-count niches."""

    # 3D grid: cost_bin × latency_bin × technique_bin
    cost_bins: int = 4       # free-only, mostly-free, mixed, paid-heavy
    latency_bins: int = 3    # fast (<5s), medium (5-15s), slow (>15s)
    technique_bins: int = 3  # minimal (1-2), moderate (3-5), full (6-9)

    archive: Dict[str, Dict] = field(default_factory=dict)

    def _niche_key(self, chromosome: PipelineChromosome) -> str:
        fitness = chromosome.fitness or {}

        cost = fitness.get('total_cost', 0)
        if cost <= 0.001:
            cost_bin = 0
        elif cost <= 0.01:
            cost_bin = 1
        elif cost <= 0.05:
            cost_bin = 2
        else:
            cost_bin = 3

        latency = fitness.get('avg_latency_ms', 5000)
        if latency < 5000:
            latency_bin = 0
        elif latency < 15000:
            latency_bin = 1
        else:
            latency_bin = 2

        tc = chromosome.active_count()
        if tc <= 2:
            technique_bin = 0
        elif tc <= 5:
            technique_bin = 1
        else:
            technique_bin = 2

        return f'{cost_bin}_{latency_bin}_{technique_bin}'

    def try_insert(self, chromosome: PipelineChromosome) -> bool:
        """Insert into archive if niche is empty or this is better."""
        if not chromosome.fitness:
            return False

        key = self._niche_key(chromosome)
        total = chromosome.fitness.get('total', 0)

        if key not in self.archive or total > self.archive[key].get('total_fitness', 0):
            self.archive[key] = {
                'chromosome': chromosome.to_dict(),
                'total_fitness': total,
                'fitness': chromosome.fitness,
                'niche': key,
            }
            return True
        return False

    def best_per_niche(self) -> List[Dict]:
        return list(self.archive.values())

    def summary(self) -> Dict:
        if not self.archive:
            return {'niches_filled': 0, 'total_niches': self.cost_bins * self.latency_bins * self.technique_bins}
        fitnesses = [v['total_fitness'] for v in self.archive.values()]
        return {
            'niches_filled': len(self.archive),
            'total_niches': self.cost_bins * self.latency_bins * self.technique_bins,
            'best_fitness': max(fitnesses),
            'avg_fitness': round(statistics.mean(fitnesses), 4),
            'niches': list(self.archive.keys()),
        }

    def to_dict(self) -> Dict:
        return {'archive': self.archive, 'summary': self.summary()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'MapElitesArchive':
        me = cls()
        me.archive = data.get('archive', {})
        return me


# ─── Meta-Optimizer ──────────────────────────────────────────────────────────

class PipelineMetaOptimizer:
    """GA meta-optimizer with MAP-Elites and Thompson Sampling bridge."""

    def __init__(
        self,
        population_size: int = 30,
        mutation_rate: float = 0.15,
        elite_fraction: float = 0.2,
        tournament_k: int = 5,
        stagnation_threshold: int = 10,
    ):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.elite_fraction = elite_fraction
        self.tournament_k = tournament_k
        self.stagnation_threshold = stagnation_threshold

        self.population: List[PipelineChromosome] = []
        self.generation = 0
        self.best_chromosome: Optional[PipelineChromosome] = None
        self.best_fitness = 0.0
        self.generations_without_improvement = 0
        self.convergence_history: List[Dict] = []
        self.map_elites = MapElitesArchive()

    def initialize_population(self) -> None:
        """Create initial population with 5 seeded + rest random."""
        seeded = [
            PipelineChromosome.minimal(),
            PipelineChromosome.full_pipeline(),
            PipelineChromosome.cost_optimized(),
            PipelineChromosome.quality_optimized(),
            PipelineChromosome.balanced(),
        ]
        randoms = [PipelineChromosome.random() for _ in range(self.population_size - len(seeded))]
        self.population = seeded + randoms
        logger.info(f'Population initialized: {len(seeded)} seeded + {len(randoms)} random = {len(self.population)}')

    def evaluate_population(self, benchmark_fn) -> None:
        """Evaluate all chromosomes via the benchmark function."""
        for i, chromosome in enumerate(self.population):
            if chromosome.fitness is not None:
                continue
            logger.info(f'Evaluating {i+1}/{len(self.population)} (gen {self.generation}): '
                        f'{chromosome.active_count()} techniques, {chromosome.routing_strategy}')
            fitness = benchmark_fn(chromosome)
            chromosome.fitness = fitness
            self.map_elites.try_insert(chromosome)
            logger.info(f'  Fitness: {fitness.get("total", 0):.4f} '
                        f'(Q={fitness.get("quality", 0):.3f} C={fitness.get("cost_efficiency", 0):.3f} '
                        f'L={fitness.get("latency", 0):.3f} R={fitness.get("reliability", 0):.3f})')

    def evolve_one_generation(self, benchmark_fn) -> Dict:
        """Execute one generation: evaluate, select, crossover, mutate."""
        self.evaluate_population(benchmark_fn)

        self.population.sort(key=lambda c: (c.fitness or {}).get('total', 0), reverse=True)
        gen_best = (self.population[0].fitness or {}).get('total', 0)

        if gen_best > self.best_fitness:
            self.best_fitness = gen_best
            self.best_chromosome = copy.deepcopy(self.population[0])
            self.generations_without_improvement = 0
        else:
            self.generations_without_improvement += 1

        # Adaptive mutation: increase when stagnating
        effective_rate = self.mutation_rate
        if self.generations_without_improvement > 5:
            effective_rate = min(0.4, self.mutation_rate + 0.05 * (self.generations_without_improvement - 5))

        # Elitism
        elite_count = max(1, int(len(self.population) * self.elite_fraction))
        elites = self.population[:elite_count]

        # Breed offspring
        offspring = []
        while len(offspring) < self.population_size - elite_count:
            p1 = tournament_select(self.population, self.tournament_k)
            p2 = tournament_select(self.population, self.tournament_k)
            c1, c2 = uniform_crossover(p1, p2)
            c1 = mutate(c1, effective_rate)
            c2 = mutate(c2, effective_rate)
            offspring.append(c1)
            if len(offspring) < self.population_size - elite_count:
                offspring.append(c2)

        # Inject MAP-Elites champions periodically to maintain diversity
        if self.generation % 10 == 0 and self.map_elites.archive:
            champ = random.choice(list(self.map_elites.archive.values()))
            injected = PipelineChromosome.from_dict(champ['chromosome'])
            injected = mutate(injected, effective_rate)
            if offspring:
                offspring[-1] = injected

        self.population = [copy.deepcopy(e) for e in elites] + offspring
        for c in self.population[elite_count:]:
            c.fitness = None

        self.generation += 1

        fitnesses = [(c.fitness or {}).get('total', 0) for c in elites]
        stats = {
            'generation': self.generation,
            'best_fitness': self.best_fitness,
            'gen_best': gen_best,
            'avg_fitness': round(statistics.mean(fitnesses), 4) if fitnesses else 0,
            'mutation_rate': round(effective_rate, 3),
            'stagnation': self.generations_without_improvement,
            'map_elites_niches': len(self.map_elites.archive),
            'best_techniques': list(k for k, v in (self.best_chromosome.active_techniques() if self.best_chromosome else {}).items() if v),
        }
        self.convergence_history.append(stats)
        return stats

    def evolve(self, generations: int, benchmark_fn, checkpoint_every: int = 10) -> PipelineChromosome:
        """Run full evolution."""
        if not self.population:
            self.initialize_population()

        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        for gen in range(generations):
            stats = self.evolve_one_generation(benchmark_fn)
            logger.info(
                f'Gen {stats["generation"]}: best={stats["best_fitness"]:.4f} '
                f'gen_best={stats["gen_best"]:.4f} avg={stats["avg_fitness"]:.4f} '
                f'stagnation={stats["stagnation"]} niches={stats["map_elites_niches"]} '
                f'mutation={stats["mutation_rate"]:.3f}'
            )

            if (gen + 1) % checkpoint_every == 0:
                self.save_checkpoint()
                self._post_convergence(stats)

            # Early termination if fully converged
            if self.generations_without_improvement >= self.stagnation_threshold * 2:
                logger.info(f'Early termination: {self.generations_without_improvement} generations without improvement')
                break

        self.save_checkpoint()
        self.save_results()
        self.integrate_with_thompson_sampling()

        return self.best_chromosome

    def save_checkpoint(self) -> None:
        path = CHECKPOINT_DIR / f'gen_{self.generation:04d}.json'
        data = {
            'generation': self.generation,
            'best_fitness': self.best_fitness,
            'best_chromosome': self.best_chromosome.to_dict() if self.best_chromosome else None,
            'population': [c.to_dict() for c in self.population],
            'convergence_history': self.convergence_history,
            'map_elites': self.map_elites.to_dict(),
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f'Checkpoint saved: {path}')

    def load_checkpoint(self, path: str) -> None:
        with open(path) as f:
            data = json.load(f)
        self.generation = data['generation']
        self.best_fitness = data['best_fitness']
        if data.get('best_chromosome'):
            self.best_chromosome = PipelineChromosome.from_dict(data['best_chromosome'])
        self.population = [PipelineChromosome.from_dict(d) for d in data.get('population', [])]
        self.convergence_history = data.get('convergence_history', [])
        if data.get('map_elites'):
            self.map_elites = MapElitesArchive.from_dict(data['map_elites'])
        logger.info(f'Checkpoint loaded: gen {self.generation}, best {self.best_fitness:.4f}')

    def save_results(self) -> None:
        path = RESULTS_DIR / f'results_gen{self.generation:04d}.json'
        results = {
            'final_generation': self.generation,
            'best_fitness': self.best_fitness,
            'best_chromosome': self.best_chromosome.to_dict() if self.best_chromosome else None,
            'best_techniques': list(
                k for k, v in (self.best_chromosome.active_techniques() if self.best_chromosome else {}).items() if v
            ),
            'convergence_history': self.convergence_history,
            'map_elites': self.map_elites.to_dict(),
            'map_elites_champions': self.map_elites.best_per_niche(),
        }
        with open(path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f'Results saved: {path}')

    def _post_convergence(self, stats: Dict) -> None:
        try:
            requests.post(f'{API_BASE}/ga/convergence', json={
                'generation': stats['generation'],
                'best_fitness': stats['best_fitness'],
                'avg_fitness': stats['avg_fitness'],
                'min_fitness': 0,
                'population_size': self.population_size,
                'use_case': 'pipeline-meta-optimizer',
                'metadata': {
                    'stagnation': stats['stagnation'],
                    'mutation_rate': stats['mutation_rate'],
                    'niches': stats['map_elites_niches'],
                },
            }, timeout=5)
        except Exception:
            pass

    def integrate_with_thompson_sampling(self) -> Dict:
        """Register best evolved configs as Thompson Sampling strategies."""
        if not self.best_chromosome:
            return {'status': 'no_best'}

        strategies = {}

        # Overall best
        strategies['evolved_best'] = {
            'chromosome': self.best_chromosome.to_dict(),
            'fitness': self.best_fitness,
        }

        # Per-niche champions from MAP-Elites
        for niche_key, entry in self.map_elites.archive.items():
            cost_bin, lat_bin, tech_bin = niche_key.split('_')
            labels = {
                '0': 'free', '1': 'cheap', '2': 'mixed', '3': 'paid',
            }
            lat_labels = {'0': 'fast', '1': 'medium', '2': 'slow'}
            tech_labels = {'0': 'minimal', '1': 'moderate', '2': 'full'}

            name = f"evolved_{labels.get(cost_bin, 'x')}_{lat_labels.get(lat_bin, 'x')}_{tech_labels.get(tech_bin, 'x')}"
            strategies[name] = {
                'chromosome': entry['chromosome'],
                'fitness': entry['total_fitness'],
                'niche': niche_key,
            }

        # Post to Thompson Sampling via REST API
        registered = 0
        for strategy_name, info in strategies.items():
            try:
                success_weight = max(1, int(info['fitness'] * 10))
                resp = requests.post(f'{API_BASE}/ga/strategies', json={
                    'strategy': strategy_name,
                    'successes': success_weight,
                    'failures': 0,
                    'alpha': success_weight + 1,
                    'beta': 1,
                    'total_reward': info['fitness'],
                    'avg_reward': info['fitness'],
                    'metadata': {
                        'source': 'ga_pipeline_optimizer',
                        'generation': self.generation,
                        'chromosome': info['chromosome'],
                    },
                }, timeout=5)
                if resp.ok:
                    registered += 1
            except Exception:
                pass

        logger.info(f'Thompson Sampling integration: {registered}/{len(strategies)} strategies registered')
        return {'registered': registered, 'strategies': list(strategies.keys())}


# ─── Main Entry Point ────────────────────────────────────────────────────────

def create_benchmark_fn(tasks=None, task_limit: Optional[int] = None):
    """Create a benchmark function that evaluates a chromosome."""
    from ga_benchmark_suite import BENCHMARKS, run_benchmarks, compute_fitness
    from ga_pipeline_runner import configure_and_run

    benchmark_tasks = tasks or BENCHMARKS
    if task_limit:
        benchmark_tasks = benchmark_tasks[:task_limit]

    def benchmark_fn(chromosome: PipelineChromosome) -> Dict:
        pipeline_fn = lambda query: configure_and_run(query, chromosome)
        results = run_benchmarks(pipeline_fn, benchmark_tasks)
        return compute_fitness(results)

    return benchmark_fn


def main():
    parser = argparse.ArgumentParser(description='GA Pipeline Meta-Optimizer')
    parser.add_argument('--quick', action='store_true', help='Quick validation: 10 gens, 10 benchmarks')
    parser.add_argument('--generations', type=int, default=100, help='Number of generations')
    parser.add_argument('--population', type=int, default=30, help='Population size')
    parser.add_argument('--benchmarks', type=int, default=None, help='Limit number of benchmark tasks')
    parser.add_argument('--resume', type=str, default=None, help='Resume from checkpoint file')
    parser.add_argument('--mutation-rate', type=float, default=0.15, help='Base mutation rate')
    args = parser.parse_args()

    if args.quick:
        args.generations = 10
        args.population = 10
        args.benchmarks = 10

    logger.info(f'Meta-Optimizer: {args.generations} generations, pop={args.population}, '
                f'benchmarks={args.benchmarks or 30}')

    optimizer = PipelineMetaOptimizer(
        population_size=args.population,
        mutation_rate=args.mutation_rate,
    )

    if args.resume:
        optimizer.load_checkpoint(args.resume)

    benchmark_fn = create_benchmark_fn(task_limit=args.benchmarks)
    best = optimizer.evolve(args.generations, benchmark_fn)

    if best:
        print('\n' + '=' * 60)
        print('BEST PIPELINE CONFIGURATION')
        print('=' * 60)
        active = [k for k, v in best.active_techniques().items() if v]
        print(f'Active techniques ({len(active)}): {", ".join(active)}')
        print(f'Routing: {best.routing_strategy}')
        print(f'Fitness: {optimizer.best_fitness:.4f}')
        print(f'Generation: {optimizer.generation}')
        print(f'\nMAP-Elites Archive:')
        for entry in optimizer.map_elites.best_per_niche():
            chrom = PipelineChromosome.from_dict(entry['chromosome'])
            active_list = [k for k, v in chrom.active_techniques().items() if v]
            print(f'  Niche {entry["niche"]}: fitness={entry["total_fitness"]:.4f}, '
                  f'techniques={", ".join(active_list)}')
        print(f'\nCheckpoints: {CHECKPOINT_DIR}')
        print(f'Results: {RESULTS_DIR}')


if __name__ == '__main__':
    main()
