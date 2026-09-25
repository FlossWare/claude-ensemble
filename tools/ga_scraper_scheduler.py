#!/usr/bin/env python3
"""GA Scraper Schedule Optimizer

Evolves optimal scheduling configurations for 60+ scrapers across the fleet.
Each chromosome encodes per-scraper parameters: frequency, time window,
batch size, concurrency, priority, and worker assignment.

Fitness balances freshness (how often data is updated), efficiency (minimal
rate-limiting/failures), fleet utilization (spread across workers), and
cost (API calls, bandwidth).

Can run offline with synthetic fitness or online with real execution data
from monitoring.execution_summary via REST API.

Usage:
    python3 ga_scraper_scheduler.py                    # offline mode
    python3 ga_scraper_scheduler.py --online            # fetch real data
    python3 ga_scraper_scheduler.py --generations 100   # longer evolution
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

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')

FLEET_WORKERS = [
    'server-01', 'server-02', 'server-03',
    'pi-01', 'pi-02', 'desktop-ap', 'server-ap', 'aio-01',
]

WORKER_CAPACITY = {
    'server-01': 4, 'server-02': 4, 'server-03': 4,
    'aio-01': 2,
    'pi-01': 1, 'pi-02': 1, 'desktop-ap': 1, 'server-ap': 1,
}

SCRAPERS = [
    {'name': 'arxiv_paper_scraper', 'category': 'research', 'rate_limit': 3.0, 'avg_docs_per_run': 50},
    {'name': 'arxiv_scraper_with_storage', 'category': 'research', 'rate_limit': 3.0, 'avg_docs_per_run': 100},
    {'name': 'pubmed_scraper', 'category': 'medical', 'rate_limit': 3.0, 'avg_docs_per_run': 80},
    {'name': 'semantic_scholar_scraper', 'category': 'research', 'rate_limit': 1.0, 'avg_docs_per_run': 40},
    {'name': 'github_scraper', 'category': 'code', 'rate_limit': 5.0, 'avg_docs_per_run': 30},
    {'name': 'github_code_scraper', 'category': 'code', 'rate_limit': 5.0, 'avg_docs_per_run': 25},
    {'name': 'stackoverflow_scraper', 'category': 'code', 'rate_limit': 1.0, 'avg_docs_per_run': 60},
    {'name': 'stackexchange_scraper', 'category': 'code', 'rate_limit': 1.0, 'avg_docs_per_run': 40},
    {'name': 'hackernews_scraper', 'category': 'news', 'rate_limit': 10.0, 'avg_docs_per_run': 30},
    {'name': 'reddit_scraper', 'category': 'social', 'rate_limit': 1.0, 'avg_docs_per_run': 50},
    {'name': 'devto_scraper', 'category': 'code', 'rate_limit': 5.0, 'avg_docs_per_run': 20},
    {'name': 'rfc_scraper', 'category': 'standards', 'rate_limit': 10.0, 'avg_docs_per_run': 5},
    {'name': 'w3c_scraper', 'category': 'standards', 'rate_limit': 10.0, 'avg_docs_per_run': 10},
    {'name': 'mdn_scraper', 'category': 'docs', 'rate_limit': 5.0, 'avg_docs_per_run': 30},
    {'name': 'wikipedia_scraper', 'category': 'reference', 'rate_limit': 5.0, 'avg_docs_per_run': 50},
    {'name': 'wikisource_scraper', 'category': 'reference', 'rate_limit': 5.0, 'avg_docs_per_run': 15},
    {'name': 'gutenberg_scraper', 'category': 'literature', 'rate_limit': 10.0, 'avg_docs_per_run': 10},
    {'name': 'official_docs_scraper', 'category': 'docs', 'rate_limit': 5.0, 'avg_docs_per_run': 20},
    {'name': 'newsapi_scraper', 'category': 'news', 'rate_limit': 2.0, 'avg_docs_per_run': 40},
    {'name': 'guardian_scraper', 'category': 'news', 'rate_limit': 2.0, 'avg_docs_per_run': 25},
    {'name': 'mit_ocw_scraper', 'category': 'education', 'rate_limit': 5.0, 'avg_docs_per_run': 15},
    {'name': 'rosetta_code_scraper', 'category': 'code', 'rate_limit': 5.0, 'avg_docs_per_run': 30},
    {'name': 'internet_archive_scraper', 'category': 'reference', 'rate_limit': 1.0, 'avg_docs_per_run': 20},
    {'name': 'pypi_npm_scraper', 'category': 'code', 'rate_limit': 5.0, 'avg_docs_per_run': 25},
    {'name': 'quora_scraper', 'category': 'social', 'rate_limit': 0.5, 'avg_docs_per_run': 15},
    {'name': 'phd_thesis_scraper', 'category': 'research', 'rate_limit': 2.0, 'avg_docs_per_run': 5},
    {'name': 'chip_design_hardware_scraper', 'category': 'hardware', 'rate_limit': 5.0, 'avg_docs_per_run': 10},
    {'name': 'consciousness_neuroscience_scraper', 'category': 'research', 'rate_limit': 3.0, 'avg_docs_per_run': 15},
    {'name': 'firmware_code_scraper', 'category': 'code', 'rate_limit': 5.0, 'avg_docs_per_run': 20},
    {'name': 'electronics_ee_scraper', 'category': 'hardware', 'rate_limit': 5.0, 'avg_docs_per_run': 15},
]

FREQUENCY_OPTIONS = [1, 2, 4, 6, 8, 12, 24, 48, 72, 168]  # hours between runs
TIME_WINDOWS = ['night', 'morning', 'afternoon', 'evening', 'any']
BATCH_SIZES = [10, 25, 50, 100, 200, 500]


@dataclass
class ScraperGene:
    frequency_hours: int = 24
    time_window: str = 'any'
    batch_size: int = 50
    concurrency: int = 2
    priority: int = 5           # 1-10
    worker: str = 'server-01'
    enabled: bool = True


@dataclass
class ScheduleChromosome:
    genes: Dict[str, ScraperGene] = field(default_factory=dict)
    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        return {name: asdict(gene) for name, gene in self.genes.items()}

    @classmethod
    def from_dict(cls, d):
        genes = {name: ScraperGene(**params) for name, params in d.items()}
        return cls(genes=genes)


class ScraperScheduleGA:
    def __init__(self, population_size=30, mutation_rate=0.20,
                 tournament_size=4, seed=None):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.convergence_history = []
        self.best_fitness = 0.0
        self.best_chromosome = None
        self.stagnation = 0

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def create_random(self) -> ScheduleChromosome:
        genes = {}
        for scraper in SCRAPERS:
            genes[scraper['name']] = ScraperGene(
                frequency_hours=random.choice(FREQUENCY_OPTIONS),
                time_window=random.choice(TIME_WINDOWS),
                batch_size=random.choice(BATCH_SIZES),
                concurrency=random.randint(1, 4),
                priority=random.randint(1, 10),
                worker=random.choice(FLEET_WORKERS),
                enabled=random.random() > 0.1,
            )
        return ScheduleChromosome(genes=genes)

    def create_seeded(self) -> List[ScheduleChromosome]:
        seeds = []

        # Seed 1: Conservative (all daily, low concurrency)
        g1 = {}
        for s in SCRAPERS:
            g1[s['name']] = ScraperGene(
                frequency_hours=24, time_window='night', batch_size=50,
                concurrency=1, priority=5, worker='server-01', enabled=True)
        seeds.append(ScheduleChromosome(genes=g1))

        # Seed 2: Aggressive (frequent, high concurrency)
        g2 = {}
        for s in SCRAPERS:
            freq = 4 if s['category'] in ('news', 'social') else 12
            g2[s['name']] = ScraperGene(
                frequency_hours=freq, time_window='any',
                batch_size=min(200, int(s['avg_docs_per_run'] * 2)),
                concurrency=3, priority=7, worker='server-02', enabled=True)
        seeds.append(ScheduleChromosome(genes=g2))

        # Seed 3: Category-optimized
        g3 = {}
        worker_map = {
            'research': 'server-03', 'medical': 'server-03',
            'code': 'server-01', 'news': 'server-02',
            'social': 'pi-02', 'standards': 'pi-01',
            'docs': 'desktop-ap', 'reference': 'server-ap',
            'education': 'aio-01', 'literature': 'pi-01',
            'hardware': 'server-02',
        }
        for s in SCRAPERS:
            g3[s['name']] = ScraperGene(
                frequency_hours=8 if s['category'] in ('news', 'code') else 24,
                time_window='night' if s['rate_limit'] < 3 else 'any',
                batch_size=s['avg_docs_per_run'],
                concurrency=2, priority=5,
                worker=worker_map.get(s['category'], 'server-01'),
                enabled=True)
        seeds.append(ScheduleChromosome(genes=g3))

        return seeds

    def calculate_fitness(self, chromosome: ScheduleChromosome) -> float:
        """
        Fitness = freshness * 0.30 + efficiency * 0.25 + fleet_balance * 0.20
                + throughput * 0.15 + cost_efficiency * 0.10
        """
        enabled_genes = {n: g for n, g in chromosome.genes.items() if g.enabled}
        if not enabled_genes:
            return 0.0

        scrapers_by_name = {s['name']: s for s in SCRAPERS}

        # 1. Freshness: how often data is updated (lower frequency_hours = fresher)
        freshness_scores = []
        for name, gene in enabled_genes.items():
            s = scrapers_by_name.get(name, {})
            cat = s.get('category', 'other')
            ideal_freq = {'news': 4, 'social': 6, 'code': 12,
                          'research': 24, 'medical': 24, 'standards': 168,
                          'docs': 48, 'reference': 72, 'education': 168,
                          'literature': 168, 'hardware': 48}.get(cat, 24)
            ratio = min(gene.frequency_hours, ideal_freq) / max(gene.frequency_hours, ideal_freq)
            freshness_scores.append(ratio)
        freshness = float(np.mean(freshness_scores))

        # 2. Efficiency: respect rate limits, avoid over-concurrency
        efficiency_scores = []
        for name, gene in enabled_genes.items():
            s = scrapers_by_name.get(name, {})
            rate_limit = s.get('rate_limit', 5.0)
            effective_rps = gene.concurrency * (gene.batch_size / max(1, gene.frequency_hours * 3600))
            if effective_rps > rate_limit:
                penalty = min(0.5, (effective_rps - rate_limit) / rate_limit)
                efficiency_scores.append(1.0 - penalty)
            else:
                efficiency_scores.append(1.0)
            if gene.time_window == 'night' and rate_limit < 3:
                efficiency_scores[-1] = min(1.0, efficiency_scores[-1] + 0.1)
        efficiency = float(np.mean(efficiency_scores))

        # 3. Fleet balance: even distribution across workers
        worker_load = defaultdict(float)
        for name, gene in enabled_genes.items():
            s = scrapers_by_name.get(name, {})
            load = gene.concurrency * (s.get('avg_docs_per_run', 30) / gene.frequency_hours)
            worker_load[gene.worker] += load

        if worker_load:
            loads = list(worker_load.values())
            max_load = max(loads)
            # Check against worker capacity
            over_capacity = 0
            for worker, load in worker_load.items():
                cap = WORKER_CAPACITY.get(worker, 2)
                if load > cap * 10:
                    over_capacity += 1

            load_std = float(np.std(loads))
            load_mean = float(np.mean(loads))
            cv = load_std / load_mean if load_mean > 0 else 1.0
            balance = max(0.0, 1.0 - cv * 0.5)
            workers_used = len(worker_load) / len(FLEET_WORKERS)
            fleet_balance = balance * 0.6 + workers_used * 0.4
            fleet_balance -= over_capacity * 0.1
            fleet_balance = max(0.0, min(1.0, fleet_balance))
        else:
            fleet_balance = 0.0

        # 4. Throughput: total docs per day
        total_docs_per_day = 0
        for name, gene in enabled_genes.items():
            s = scrapers_by_name.get(name, {})
            runs_per_day = 24.0 / gene.frequency_hours
            total_docs_per_day += runs_per_day * s.get('avg_docs_per_run', 30) * min(gene.batch_size / s.get('avg_docs_per_run', 30), 2.0)
        max_theoretical = sum(s['avg_docs_per_run'] * 24 for s in SCRAPERS)
        throughput = min(1.0, total_docs_per_day / (max_theoretical * 0.1))

        # 5. Cost efficiency: prefer fewer high-concurrency runs over many small ones
        total_runs_per_day = sum(24.0 / g.frequency_hours for g in enabled_genes.values())
        run_overhead = min(1.0, total_runs_per_day / 200.0)
        cost_efficiency = 1.0 - run_overhead * 0.5
        disabled_count = len(chromosome.genes) - len(enabled_genes)
        cost_efficiency += disabled_count * 0.01
        cost_efficiency = max(0.0, min(1.0, cost_efficiency))

        fitness = (
            freshness * 0.30 +
            efficiency * 0.25 +
            fleet_balance * 0.20 +
            throughput * 0.15 +
            cost_efficiency * 0.10
        )
        fitness = max(0.0, min(1.0, fitness))

        chromosome.fitness = round(fitness, 5)
        chromosome.fitness_details = {
            'freshness': round(freshness, 4),
            'efficiency': round(efficiency, 4),
            'fleet_balance': round(fleet_balance, 4),
            'throughput': round(throughput, 4),
            'cost_efficiency': round(cost_efficiency, 4),
            'enabled_scrapers': len(enabled_genes),
            'total_docs_per_day': round(total_docs_per_day, 0),
            'workers_used': len(worker_load),
        }
        return fitness

    def crossover(self, p1: ScheduleChromosome, p2: ScheduleChromosome) -> ScheduleChromosome:
        child_genes = {}
        for name in p1.genes:
            if random.random() < 0.5:
                child_genes[name] = ScraperGene(**asdict(p1.genes[name]))
            else:
                child_genes[name] = ScraperGene(**asdict(p2.genes[name]))
        return ScheduleChromosome(genes=child_genes)

    def mutate(self, chromosome: ScheduleChromosome):
        for name, gene in chromosome.genes.items():
            if random.random() < self.mutation_rate:
                mutation = random.choice([
                    'frequency', 'time_window', 'batch_size',
                    'concurrency', 'priority', 'worker', 'enabled'])
                if mutation == 'frequency':
                    gene.frequency_hours = random.choice(FREQUENCY_OPTIONS)
                elif mutation == 'time_window':
                    gene.time_window = random.choice(TIME_WINDOWS)
                elif mutation == 'batch_size':
                    gene.batch_size = random.choice(BATCH_SIZES)
                elif mutation == 'concurrency':
                    gene.concurrency = random.randint(1, 4)
                elif mutation == 'priority':
                    gene.priority = max(1, min(10, gene.priority + random.randint(-2, 2)))
                elif mutation == 'worker':
                    gene.worker = random.choice(FLEET_WORKERS)
                elif mutation == 'enabled':
                    gene.enabled = not gene.enabled

    def tournament_select(self, population):
        candidates = random.sample(population, min(self.tournament_size, len(population)))
        return max(candidates, key=lambda c: c.fitness or 0)

    def evolve_generation(self, population):
        population.sort(key=lambda c: c.fitness or 0, reverse=True)
        elite_size = max(2, self.population_size // 5)
        new_pop = [ScheduleChromosome(
            genes={n: ScraperGene(**asdict(g)) for n, g in c.genes.items()})
            for c in population[:elite_size]]

        while len(new_pop) < self.population_size:
            p1 = self.tournament_select(population)
            p2 = self.tournament_select(population)
            child = self.crossover(p1, p2)
            self.mutate(child)
            child.fitness = self.calculate_fitness(child)
            new_pop.append(child)

        return new_pop

    def run(self, generations=50):
        print("=" * 70)
        print("  GA Scraper Schedule Optimizer")
        print("=" * 70)
        print(f"Scrapers: {len(SCRAPERS)}")
        print(f"Fleet workers: {len(FLEET_WORKERS)}")
        print(f"Population: {self.population_size}")
        print(f"Generations: {generations}")
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
            # Adaptive mutation
            if self.stagnation > 5:
                self.mutation_rate = min(0.5, 0.20 + 0.03 * self.stagnation)
            else:
                self.mutation_rate = 0.20

            population = self.evolve_generation(population)
            current_best = max(population, key=lambda c: c.fitness or 0)

            if (current_best.fitness or 0) > self.best_fitness:
                self.best_fitness = current_best.fitness
                self.best_chromosome = current_best
                self.stagnation = 0
                print(f"Gen {gen:2d}: NEW BEST={current_best.fitness:.5f}  "
                      f"Fresh={current_best.fitness_details['freshness']:.3f} "
                      f"Eff={current_best.fitness_details['efficiency']:.3f} "
                      f"Bal={current_best.fitness_details['fleet_balance']:.3f} "
                      f"Docs/day={current_best.fitness_details['total_docs_per_day']:.0f}")
            else:
                self.stagnation += 1
                if gen % 10 == 0:
                    avg_fit = np.mean([c.fitness for c in population if c.fitness])
                    print(f"Gen {gen:2d}: Best={current_best.fitness:.5f}  "
                          f"Avg={avg_fit:.5f}  Stagnation={self.stagnation}")

            self.convergence_history.append({
                'generation': gen,
                'best_fitness': float(current_best.fitness or 0),
                'avg_fitness': float(np.mean([c.fitness for c in population if c.fitness])),
            })

        self._print_report()
        self._store_results()
        return self.best_chromosome

    def _print_report(self):
        best = self.best_chromosome
        if not best:
            return

        print("\n" + "=" * 70)
        print("  BEST SCRAPER SCHEDULE")
        print("=" * 70)
        print(f"  Fitness: {best.fitness:.5f}")
        if best.fitness_details:
            for k, v in best.fitness_details.items():
                print(f"  {k:20s}: {v}")

        print("\n  --- Per-Scraper Schedule ---")
        by_worker = defaultdict(list)
        for name, gene in sorted(best.genes.items()):
            if gene.enabled:
                by_worker[gene.worker].append((name, gene))

        for worker in FLEET_WORKERS:
            scrapers = by_worker.get(worker, [])
            if scrapers:
                cap = WORKER_CAPACITY.get(worker, 2)
                print(f"\n  [{worker}] (capacity={cap}, assigned={len(scrapers)})")
                for name, gene in scrapers:
                    print(f"    {name:40s} every {gene.frequency_hours:3d}h  "
                          f"batch={gene.batch_size:3d}  conc={gene.concurrency}  "
                          f"pri={gene.priority:2d}  window={gene.time_window}")

        disabled = [n for n, g in best.genes.items() if not g.enabled]
        if disabled:
            print(f"\n  Disabled scrapers ({len(disabled)}): {', '.join(disabled)}")
        print("=" * 70)

    def _store_results(self):
        best = self.best_chromosome
        if not best:
            return

        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, 'best_scraper_schedule.json')

        export = {
            'schedule': best.to_dict(),
            'fitness': best.fitness,
            'fitness_details': best.fitness_details,
            'convergence': self.convergence_history[-5:] if self.convergence_history else [],
            'metadata': {
                'scrapers': len(SCRAPERS),
                'workers': len(FLEET_WORKERS),
                'generations': len(self.convergence_history),
                'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }
        }

        with open(output_path, 'w') as f:
            json.dump(export, f, indent=2)
        print(f"\nSchedule saved to: {output_path}")

        try:
            requests.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': 'scraper-schedule',
                'chromosome': json.dumps(best.to_dict()),
                'fitness': float(best.fitness or 0),
                'fitness_details': json.dumps(best.fitness_details or {}),
                'generation_found': len(self.convergence_history),
                'notes': f'Evolved schedule for {len(SCRAPERS)} scrapers across {len(FLEET_WORKERS)} workers',
            }, timeout=5)
            print("Stored in ga.best_solutions via REST API")
        except Exception:
            print("API unavailable — stored locally only")


def main():
    parser = argparse.ArgumentParser(description='GA Scraper Schedule Optimizer')
    parser.add_argument('--generations', type=int, default=50)
    parser.add_argument('--population', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    optimizer = ScraperScheduleGA(
        population_size=args.population,
        seed=args.seed,
    )
    optimizer.run(generations=args.generations)


if __name__ == '__main__':
    main()
