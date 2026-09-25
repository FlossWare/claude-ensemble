#!/usr/bin/env python3
"""Continuous Intelligence Evolution Engine

GA that runs indefinitely, evolving populations of cognitive strategies
across diverse problem domains, measuring and detecting emergent intelligence.

Intelligence Detection Metrics:
  1. Generalization: performance on unseen problems
  2. Transfer: skills from one domain improving another
  3. Compositional: combining sub-strategies in novel ways
  4. Novelty: behavioral diversity increasing over time
  5. Meta-optimization: strategies that optimize strategies
  6. Robustness: performance under perturbation

The system runs until intelligence indicators cross defined thresholds,
then checkpoints the state so results can be reproduced and studied.

Usage:
    python3 ga_continuous_intelligence.py                    # run forever
    python3 ga_continuous_intelligence.py --max-epochs 100   # limited run
    python3 ga_continuous_intelligence.py --resume state.json # resume from checkpoint
    python3 ga_continuous_intelligence.py --report            # show latest findings
"""

import argparse
import json
import math
import os
import signal
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

# ============================================================================
# PROBLEM DOMAINS
# ============================================================================
# Each domain tests a different cognitive capability. Intelligence is measured
# by how well evolved strategies generalize ACROSS domains, not just within.

def _clamp01(x):
    return max(0.0, min(1.0, x))


class ProblemDomain:
    """Base class for problem domains."""
    name: str = "base"
    dimension: int = 10

    def evaluate(self, strategy: np.ndarray, seed: int = 42) -> float:
        raise NotImplementedError

    def perturbed_evaluate(self, strategy: np.ndarray, perturbation: float = 0.05, seed: int = 42) -> float:
        rng = np.random.RandomState(seed)
        perturbed = strategy + rng.normal(0, perturbation, len(strategy))
        return self.evaluate(perturbed, seed)


class OptimizationDomain(ProblemDomain):
    """Evolve strategies for continuous optimization.
    Strategy encodes: step sizes, momentum terms, exploration rates.
    """
    name = "optimization"
    dimension = 12

    TARGET_FUNCTIONS = {
        'rastrigin': lambda x: 10*len(x) + sum(xi**2 - 10*math.cos(2*math.pi*xi) for xi in x),
        'sphere': lambda x: sum(xi**2 for xi in x),
        'ackley': lambda x: -20*math.exp(-0.2*math.sqrt(sum(xi**2 for xi in x)/len(x)))
                            - math.exp(sum(math.cos(2*math.pi*xi) for xi in x)/len(x)) + 20 + math.e,
        'griewank': lambda x: sum(xi**2 for xi in x)/4000
                              - np.prod([math.cos(x[i]/math.sqrt(i+1)) for i in range(len(x))]) + 1,
    }

    def evaluate(self, strategy: np.ndarray, seed: int = 42) -> float:
        rng = np.random.RandomState(seed)
        s = strategy[:self.dimension]

        step_scale = abs(s[0]) * 2 + 0.01
        momentum = _clamp01(abs(s[1]))
        explore_rate = _clamp01(abs(s[2]))
        adapt_speed = _clamp01(abs(s[3]))
        dims = 5

        scores = []
        for fn_name, fn in self.TARGET_FUNCTIONS.items():
            x = rng.uniform(-5, 5, dims)
            velocity = np.zeros(dims)
            best_val = fn(x.tolist())

            for step in range(50):
                grad_est = np.zeros(dims)
                eps = 0.01 * step_scale
                for d in range(dims):
                    x_plus = x.copy(); x_plus[d] += eps
                    x_minus = x.copy(); x_minus[d] -= eps
                    grad_est[d] = (fn(x_plus.tolist()) - fn(x_minus.tolist())) / (2 * eps)

                if rng.random() < explore_rate * max(0, 1 - step/50):
                    grad_est += rng.normal(0, 0.5, dims)

                velocity = momentum * velocity - step_scale * adapt_speed * grad_est
                x = x + velocity
                x = np.clip(x, -5, 5)
                val = fn(x.tolist())
                best_val = min(best_val, val)

            max_val = fn([5]*dims)
            scores.append(_clamp01(1.0 - best_val / max(max_val, 1)))

        return float(np.mean(scores))


class SequencePredictionDomain(ProblemDomain):
    """Evolve strategies for sequence prediction.
    Strategy encodes: window sizes, weighting schemes, memory parameters.
    """
    name = "sequence_prediction"
    dimension = 10

    def _generate_sequence(self, seq_type: str, length: int, rng) -> List[float]:
        if seq_type == 'linear':
            slope = rng.uniform(0.5, 2.0)
            return [slope * i + rng.normal(0, 0.1) for i in range(length)]
        elif seq_type == 'sinusoidal':
            freq = rng.uniform(0.1, 0.5)
            return [math.sin(freq * i) + rng.normal(0, 0.05) for i in range(length)]
        elif seq_type == 'exponential':
            base = rng.uniform(0.9, 1.1)
            return [base**i + rng.normal(0, 0.1) for i in range(length)]
        elif seq_type == 'logistic':
            r = rng.uniform(2.5, 3.8)
            x = 0.5
            seq = []
            for _ in range(length):
                x = r * x * (1 - x)
                seq.append(x + rng.normal(0, 0.02))
            return seq
        elif seq_type == 'fibonacci':
            a, b = 1, 1
            seq = []
            for _ in range(length):
                seq.append(a / (1 + a) + rng.normal(0, 0.01))
                a, b = b, a + b
            return seq
        return [rng.random() for _ in range(length)]

    def evaluate(self, strategy: np.ndarray, seed: int = 42) -> float:
        rng = np.random.RandomState(seed)
        s = strategy[:self.dimension]

        window = max(2, int(abs(s[0]) * 10) + 1)
        decay = _clamp01(abs(s[1]) * 0.5 + 0.5)
        trend_weight = abs(s[2])
        ema_alpha = _clamp01(abs(s[3]) * 0.3 + 0.1)

        errors = []
        for seq_type in ['linear', 'sinusoidal', 'exponential', 'logistic', 'fibonacci']:
            seq = self._generate_sequence(seq_type, 30, rng)
            predictions = []

            for t in range(window, len(seq)):
                recent = seq[max(0, t-window):t]
                weights = np.array([decay**(len(recent)-1-i) for i in range(len(recent))])
                weights /= weights.sum()
                weighted_avg = np.dot(weights, recent)

                if len(recent) >= 2:
                    trend = (recent[-1] - recent[0]) / len(recent) * trend_weight
                else:
                    trend = 0

                pred = weighted_avg + trend
                ema = ema_alpha * seq[t-1] + (1-ema_alpha) * (weighted_avg if t == window else predictions[-1] if predictions else seq[t-1])
                final_pred = 0.5 * pred + 0.5 * ema

                predictions.append(final_pred)
                errors.append(abs(final_pred - seq[t]))

        if not errors:
            return 0.0
        return _clamp01(1.0 - float(np.mean(errors)))


class ClassificationDomain(ProblemDomain):
    """Evolve strategies for boundary-based classification.
    Strategy encodes: distance metrics, thresholds, feature weights.
    """
    name = "classification"
    dimension = 10

    def _generate_dataset(self, problem: str, n: int, rng):
        if problem == 'linear':
            X = rng.uniform(-2, 2, (n, 2))
            y = (X[:, 0] + X[:, 1] > 0).astype(float)
        elif problem == 'circular':
            X = rng.uniform(-2, 2, (n, 2))
            y = (X[:, 0]**2 + X[:, 1]**2 < 1.5).astype(float)
        elif problem == 'xor':
            X = rng.uniform(-2, 2, (n, 2))
            y = ((X[:, 0] > 0) ^ (X[:, 1] > 0)).astype(float)
        elif problem == 'spiral':
            t = np.linspace(0, 4*math.pi, n//2)
            r = t / (4*math.pi)
            X1 = np.column_stack([r*np.cos(t), r*np.sin(t)]) + rng.normal(0, 0.05, (n//2, 2))
            X2 = np.column_stack([-r*np.cos(t), -r*np.sin(t)]) + rng.normal(0, 0.05, (n//2, 2))
            X = np.vstack([X1, X2])
            y = np.array([0]*(n//2) + [1]*(n//2), dtype=float)
        else:
            X = rng.uniform(-2, 2, (n, 2))
            y = rng.randint(0, 2, n).astype(float)
        return X, y

    def evaluate(self, strategy: np.ndarray, seed: int = 42) -> float:
        rng = np.random.RandomState(seed)
        s = strategy[:self.dimension]

        feature_w = s[:2]
        bias = s[2]
        threshold = s[3]
        kernel_scale = abs(s[4]) + 0.1
        k_neighbors = max(1, int(abs(s[5]) * 5) + 1)

        accuracies = []
        for problem in ['linear', 'circular', 'xor', 'spiral']:
            X, y = self._generate_dataset(problem, 80, rng)
            X_train, y_train = X[:60], y[:60]
            X_test, y_test = X[60:], y[60:]

            correct = 0
            for i in range(len(X_test)):
                dists = np.sqrt(np.sum((X_train - X_test[i])**2 * abs(feature_w), axis=1))
                k = min(k_neighbors, len(X_train))
                nearest = np.argsort(dists)[:k]
                vote = np.mean(y_train[nearest])

                linear_score = np.dot(X_test[i], feature_w) + bias
                combined = 0.5 * vote + 0.5 * (1 / (1 + math.exp(-linear_score)))
                pred = 1.0 if combined > _clamp01(threshold * 0.5 + 0.5) else 0.0

                if pred == y_test[i]:
                    correct += 1

            accuracies.append(correct / len(X_test))

        return float(np.mean(accuracies))


class PlanningDomain(ProblemDomain):
    """Evolve strategies for sequential decision making.
    Strategy encodes: exploration-exploitation balance, lookahead, discounting.
    """
    name = "planning"
    dimension = 8

    def evaluate(self, strategy: np.ndarray, seed: int = 42) -> float:
        rng = np.random.RandomState(seed)
        s = strategy[:self.dimension]

        epsilon = _clamp01(abs(s[0]) * 0.5)
        discount = _clamp01(abs(s[1]) * 0.3 + 0.7)
        lr = _clamp01(abs(s[2]) * 0.3 + 0.05)
        init_optimism = abs(s[3])

        scores = []
        for n_arms in [5, 10, 20]:
            true_means = rng.normal(0, 1, n_arms)
            q_est = np.ones(n_arms) * init_optimism
            counts = np.zeros(n_arms)
            total_reward = 0

            for t in range(200):
                if rng.random() < epsilon * max(0, 1 - t/200):
                    action = rng.randint(0, n_arms)
                else:
                    ucb_bonus = np.sqrt(2 * math.log(t+1) / (counts + 1))
                    action = np.argmax(q_est + ucb_bonus * abs(s[4]))

                reward = rng.normal(true_means[action], 1)
                counts[action] += 1
                q_est[action] += lr * (reward - q_est[action])
                total_reward += reward * (discount ** t)

            best_possible = true_means.max() * sum(discount**t for t in range(200))
            scores.append(_clamp01(total_reward / max(best_possible, 1)))

        return float(np.mean(scores))


class MemoryDomain(ProblemDomain):
    """Evolve strategies for memory-based tasks.
    Strategy encodes: memory capacity, retrieval weights, forgetting curves.
    """
    name = "memory"
    dimension = 8

    def evaluate(self, strategy: np.ndarray, seed: int = 42) -> float:
        rng = np.random.RandomState(seed)
        s = strategy[:self.dimension]

        capacity = max(3, int(abs(s[0]) * 20) + 2)
        decay = _clamp01(abs(s[1]) * 0.3 + 0.7)
        relevance_weight = abs(s[2]) + 0.1
        recency_weight = abs(s[3]) + 0.1

        scores = []
        for n_items, n_queries in [(20, 10), (50, 20), (100, 30)]:
            items = rng.uniform(-1, 1, (n_items, 4))
            memory = []
            timestamps = []
            correct = 0

            for q in range(n_queries):
                query_idx = rng.randint(0, n_items)
                query = items[query_idx]

                if rng.random() < 0.7:
                    store_idx = rng.randint(0, n_items)
                    memory.append(items[store_idx].copy())
                    timestamps.append(q)
                    if len(memory) > capacity:
                        ages = [q - t for t in timestamps]
                        oldest = np.argmax(ages)
                        memory.pop(oldest)
                        timestamps.pop(oldest)

                if memory:
                    sims = []
                    for i, m in enumerate(memory):
                        sim = np.dot(query, m) / (np.linalg.norm(query) * np.linalg.norm(m) + 1e-8)
                        age = q - timestamps[i]
                        recency = decay ** age
                        score = relevance_weight * sim + recency_weight * recency
                        sims.append(score)

                    best_idx = np.argmax(sims)
                    retrieved = memory[best_idx]
                    dist = np.linalg.norm(retrieved - query)
                    if dist < 0.5:
                        correct += 1

            scores.append(correct / max(n_queries, 1))

        return float(np.mean(scores))


ALL_DOMAINS = {
    'optimization': OptimizationDomain(),
    'sequence': SequencePredictionDomain(),
    'classification': ClassificationDomain(),
    'planning': PlanningDomain(),
    'memory': MemoryDomain(),
}


# ============================================================================
# INTELLIGENCE DETECTION
# ============================================================================

@dataclass
class IntelligenceMetrics:
    """Measurable proxies for emergent intelligence."""
    epoch: int = 0

    # Core metrics (0-1, higher = more intelligent)
    generalization: float = 0.0     # performance on unseen domains
    transfer: float = 0.0          # cross-domain skill transfer
    novelty: float = 0.0           # behavioral diversity vs history
    robustness: float = 0.0        # stability under perturbation
    compositional: float = 0.0     # using multiple sub-strategies
    meta_improvement: float = 0.0  # rate of improvement accelerating

    # Derived
    intelligence_score: float = 0.0  # weighted aggregate

    # Tracking
    improvements_per_epoch: float = 0.0
    population_diversity: float = 0.0
    best_fitness: float = 0.0
    mean_fitness: float = 0.0

    def compute_intelligence_score(self):
        self.intelligence_score = (
            self.generalization * 0.25 +
            self.transfer * 0.20 +
            self.novelty * 0.15 +
            self.robustness * 0.15 +
            self.compositional * 0.10 +
            self.meta_improvement * 0.15
        )
        return self.intelligence_score

    def to_dict(self):
        return {k: round(v, 6) if isinstance(v, float) else v for k, v in self.__dict__.items()}

    def summary_line(self) -> str:
        return (f"IQ={self.intelligence_score:.4f} "
                f"[gen={self.generalization:.3f} xfer={self.transfer:.3f} "
                f"nov={self.novelty:.3f} rob={self.robustness:.3f} "
                f"comp={self.compositional:.3f} meta={self.meta_improvement:.3f}]")


INTELLIGENCE_THRESHOLDS = {
    'spark':        0.35,  # first signs of cross-domain capability
    'emerging':     0.50,  # consistent generalization + transfer
    'notable':      0.65,  # robust, novel, compositional strategies
    'significant':  0.80,  # approaching theoretical limits
    'breakthrough': 0.90,  # would be genuinely remarkable
}


# ============================================================================
# CONTINUOUS EVOLUTION ENGINE
# ============================================================================

@dataclass
class Organism:
    """An evolved cognitive strategy."""
    genome: np.ndarray = field(default_factory=lambda: np.array([]))
    fitness_per_domain: Dict[str, float] = field(default_factory=dict)
    overall_fitness: float = 0.0
    generation_born: int = 0
    lineage: List[int] = field(default_factory=list)
    behavior_hash: str = ""
    id: int = 0

    def to_dict(self):
        return {
            'genome': self.genome.tolist(),
            'fitness_per_domain': self.fitness_per_domain,
            'overall_fitness': self.overall_fitness,
            'generation_born': self.generation_born,
            'lineage': self.lineage[-10:],
            'id': self.id,
        }


class ContinuousIntelligenceEngine:
    """GA that runs continuously, evolving toward intelligence."""

    MAX_DIMENSION = 15  # genome covers all domains

    def __init__(
        self,
        population_size: int = 40,
        domains: List[str] = None,
        train_domains: List[str] = None,
        test_domains: List[str] = None,
        seed: int = 42,
        checkpoint_dir: str = None,
    ):
        self.population_size = population_size
        self.rng = np.random.RandomState(seed)
        self.seed = seed

        all_domain_names = list(ALL_DOMAINS.keys())
        self.domains = {n: ALL_DOMAINS[n] for n in (domains or all_domain_names)}

        if train_domains and test_domains:
            self.train_domains = train_domains
            self.test_domains = test_domains
        else:
            names = list(self.domains.keys())
            self.rng.shuffle(names)
            split = max(2, len(names) - 1)
            self.train_domains = names[:split]
            self.test_domains = names[split:]
            if not self.test_domains:
                self.test_domains = [names[-1]]

        self.checkpoint_dir = checkpoint_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'intelligence_checkpoints'
        )
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        self.population: List[Organism] = []
        self.epoch = 0
        self.next_id = 0
        self.metrics_history: List[Dict] = []
        self.behavior_archive: List[Tuple[str, float]] = []
        self.best_ever: Optional[Organism] = None
        self.improvement_history: List[float] = []
        self.intelligence_detected: Dict[str, int] = {}
        self.running = True
        self.fitness_stagnation = 0

        # GA hyperparams — try to load meta-GA evolved params, else use defaults
        evolved = self._load_evolved_params()
        self.mutation_rate = evolved.get('mutation_rate', 0.25)
        self.crossover_rate = evolved.get('crossover_rate', 0.7)
        self.tournament_size = evolved.get('tournament_size', 4)
        self.elitism_ratio = evolved.get('elitism_ratio', 0.15)
        self.mutation_scale = evolved.get('mutation_step_scale', 0.15)

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _load_evolved_params(self) -> dict:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'best_ga_hyperparams.json')
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                return data.get('hyperparams', {})
            except Exception:
                pass
        return {}

    def _handle_signal(self, signum, frame):
        print(f"\n[SIGNAL] Received signal {signum}, checkpointing and stopping...")
        self.running = False

    def _new_id(self) -> int:
        self.next_id += 1
        return self.next_id

    def _random_organism(self) -> Organism:
        return Organism(
            genome=self.rng.uniform(-1, 1, self.MAX_DIMENSION),
            id=self._new_id(),
            generation_born=self.epoch,
        )

    def _evaluate_organism(self, org: Organism, domain_names: List[str] = None, seeds: List[int] = None):
        if domain_names is None:
            domain_names = self.train_domains
        if seeds is None:
            seeds = [42, 123]

        for dname in domain_names:
            domain = self.domains[dname]
            scores = []
            for s in seeds:
                scores.append(domain.evaluate(org.genome, seed=s))
            org.fitness_per_domain[dname] = float(np.mean(scores))

        evaluated_domains = [d for d in domain_names if d in org.fitness_per_domain]
        if evaluated_domains:
            org.overall_fitness = float(np.mean([org.fitness_per_domain[d] for d in evaluated_domains]))

        org.behavior_hash = self._behavior_hash(org)

    def _behavior_hash(self, org: Organism) -> str:
        parts = []
        for d in sorted(org.fitness_per_domain.keys()):
            parts.append(f"{d}:{org.fitness_per_domain[d]:.2f}")
        return "|".join(parts)

    def _crossover(self, p1: Organism, p2: Organism) -> Organism:
        if self.rng.random() < self.crossover_rate:
            # Uniform crossover with blending
            mask = self.rng.random(self.MAX_DIMENSION) < 0.5
            child_genome = np.where(mask, p1.genome, p2.genome)
            # Blend at crossover points
            blend_mask = self.rng.random(self.MAX_DIMENSION) < 0.3
            alpha = self.rng.uniform(0.2, 0.8)
            blended = alpha * p1.genome + (1 - alpha) * p2.genome
            child_genome = np.where(blend_mask & mask, blended, child_genome)
        else:
            child_genome = p1.genome.copy()

        child = Organism(
            genome=child_genome,
            id=self._new_id(),
            generation_born=self.epoch,
            lineage=(p1.lineage + [p1.id])[-10:],
        )
        return child

    def _mutate(self, org: Organism):
        for i in range(self.MAX_DIMENSION):
            if self.rng.random() < self.mutation_rate:
                org.genome[i] += self.rng.normal(0, self.mutation_scale)
                org.genome[i] = np.clip(org.genome[i], -3, 3)

        # Rare large mutation (exploration)
        if self.rng.random() < 0.05:
            idx = self.rng.randint(0, self.MAX_DIMENSION)
            org.genome[idx] = self.rng.uniform(-2, 2)

    def _tournament_select(self) -> Organism:
        candidates = [self.population[i] for i in
                      self.rng.choice(len(self.population), min(self.tournament_size, len(self.population)), replace=False)]
        return max(candidates, key=lambda o: o.overall_fitness)

    def _novelty_score(self, org: Organism) -> float:
        if not self.behavior_archive:
            return 1.0
        bh = org.behavior_hash
        min_dist = float('inf')
        for archived_bh, _ in self.behavior_archive[-500:]:
            dist = sum(1 for a, b in zip(bh.split('|'), archived_bh.split('|')) if a != b) / max(len(bh.split('|')), 1)
            min_dist = min(min_dist, dist)
        return min(1.0, min_dist)

    def _measure_intelligence(self) -> IntelligenceMetrics:
        metrics = IntelligenceMetrics(epoch=self.epoch)

        # 1. GENERALIZATION: test on held-out domains
        if self.test_domains and self.best_ever:
            test_scores = []
            for dname in self.test_domains:
                domain = self.domains[dname]
                score = domain.evaluate(self.best_ever.genome, seed=999)
                test_scores.append(score)
            train_mean = np.mean([self.best_ever.fitness_per_domain.get(d, 0) for d in self.train_domains])
            test_mean = np.mean(test_scores) if test_scores else 0

            generalization_gap = max(0, test_mean / max(train_mean, 0.001))
            metrics.generalization = _clamp01(min(1.0, generalization_gap))

        # 2. TRANSFER: does training on A help with B?
        if len(self.domains) >= 3:
            specialist_scores = {}
            for dname in list(self.domains.keys())[:3]:
                specialist = self._random_organism()
                specialist.genome = self.rng.uniform(-1, 1, self.MAX_DIMENSION)
                domain = self.domains[dname]
                specialist_scores[dname] = domain.evaluate(specialist.genome, seed=42)

            generalist = self.best_ever
            if generalist:
                transfer_ratios = []
                for dname in specialist_scores:
                    gen_score = generalist.fitness_per_domain.get(dname,
                        self.domains[dname].evaluate(generalist.genome, seed=42))
                    spec_score = specialist_scores[dname]
                    if spec_score > 0:
                        transfer_ratios.append(min(2.0, gen_score / max(spec_score, 0.001)))
                if transfer_ratios:
                    metrics.transfer = _clamp01(float(np.mean(transfer_ratios)) - 0.5)

        # 3. NOVELTY: population behavioral diversity
        if self.population:
            hashes = set(o.behavior_hash for o in self.population)
            metrics.novelty = len(hashes) / len(self.population)

        # 4. ROBUSTNESS: performance under perturbation
        if self.best_ever:
            perturbation_scores = []
            for seed in [1, 2, 3]:
                for dname in self.train_domains[:2]:
                    domain = self.domains[dname]
                    normal = domain.evaluate(self.best_ever.genome, seed=42)
                    perturbed = domain.perturbed_evaluate(self.best_ever.genome, 0.1, seed)
                    if normal > 0:
                        perturbation_scores.append(min(1.0, perturbed / max(normal, 0.001)))
            if perturbation_scores:
                metrics.robustness = float(np.mean(perturbation_scores))

        # 5. COMPOSITIONAL: genome uses multiple non-zero dimensions
        if self.best_ever is not None:
            active_dims = np.sum(np.abs(self.best_ever.genome) > 0.1)
            metrics.compositional = _clamp01(active_dims / self.MAX_DIMENSION)

        # 6. META-IMPROVEMENT: is the rate of improvement accelerating?
        if len(self.improvement_history) >= 10:
            recent = self.improvement_history[-5:]
            older = self.improvement_history[-10:-5]
            recent_rate = np.mean(recent)
            older_rate = np.mean(older)
            if older_rate > 0:
                metrics.meta_improvement = _clamp01((recent_rate / max(older_rate, 0.001)) - 0.5)
            elif recent_rate > 0:
                metrics.meta_improvement = 0.5

        # Tracking
        metrics.best_fitness = self.best_ever.overall_fitness if self.best_ever else 0
        metrics.mean_fitness = float(np.mean([o.overall_fitness for o in self.population])) if self.population else 0
        metrics.population_diversity = metrics.novelty

        if self.improvement_history:
            metrics.improvements_per_epoch = float(np.mean(self.improvement_history[-10:]))

        metrics.compute_intelligence_score()
        return metrics

    def _check_intelligence_thresholds(self, metrics: IntelligenceMetrics):
        for level, threshold in INTELLIGENCE_THRESHOLDS.items():
            if metrics.intelligence_score >= threshold and level not in self.intelligence_detected:
                self.intelligence_detected[level] = self.epoch
                print(f"\n{'='*70}")
                print(f"  *** INTELLIGENCE LEVEL DETECTED: {level.upper()} ***")
                print(f"  Epoch: {self.epoch}")
                print(f"  Score: {metrics.intelligence_score:.6f} (threshold: {threshold})")
                print(f"  {metrics.summary_line()}")
                print(f"{'='*70}\n")
                self._checkpoint(f"intelligence_{level}")

    def _checkpoint(self, tag: str = "periodic"):
        path = os.path.join(self.checkpoint_dir, f"checkpoint_epoch{self.epoch}_{tag}.json")
        state = {
            'epoch': self.epoch,
            'tag': tag,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'seed': self.seed,
            'population_size': self.population_size,
            'train_domains': self.train_domains,
            'test_domains': self.test_domains,
            'ga_hyperparams': {
                'mutation_rate': self.mutation_rate,
                'crossover_rate': self.crossover_rate,
                'tournament_size': self.tournament_size,
                'elitism_ratio': self.elitism_ratio,
                'mutation_scale': self.mutation_scale,
            },
            'best_ever': self.best_ever.to_dict() if self.best_ever else None,
            'top_5': [o.to_dict() for o in sorted(self.population, key=lambda o: o.overall_fitness, reverse=True)[:5]],
            'intelligence_detected': self.intelligence_detected,
            'metrics_history': self.metrics_history[-100:],
        }

        with open(path, 'w') as f:
            json.dump(state, f, indent=2)

        latest_path = os.path.join(self.checkpoint_dir, 'latest.json')
        with open(latest_path, 'w') as f:
            json.dump(state, f, indent=2)

        return path

    def _adaptive_mutation(self):
        if self.fitness_stagnation > 10:
            self.mutation_rate = min(0.5, 0.25 + 0.02 * self.fitness_stagnation)
            self.mutation_scale = min(0.4, 0.15 + 0.02 * self.fitness_stagnation)
        elif self.fitness_stagnation > 5:
            self.mutation_rate = min(0.4, 0.25 + 0.01 * self.fitness_stagnation)
        else:
            self.mutation_rate = 0.25
            self.mutation_scale = 0.15

    def initialize(self):
        print("=" * 70)
        print("  CONTINUOUS INTELLIGENCE EVOLUTION ENGINE")
        print("=" * 70)
        print(f"  Population: {self.population_size}")
        print(f"  Genome dimensions: {self.MAX_DIMENSION}")
        print(f"  Train domains: {self.train_domains}")
        print(f"  Test domains: {self.test_domains}")
        print(f"  Checkpoint dir: {self.checkpoint_dir}")
        print(f"  Intelligence thresholds: {INTELLIGENCE_THRESHOLDS}")
        print("=" * 70)

        self.population = [self._random_organism() for _ in range(self.population_size)]
        for org in self.population:
            self._evaluate_organism(org)

        self.best_ever = max(self.population, key=lambda o: o.overall_fitness)
        print(f"\nInitial best fitness: {self.best_ever.overall_fitness:.6f}")
        print(f"  Per-domain: {self.best_ever.fitness_per_domain}")

    def run_epoch(self) -> IntelligenceMetrics:
        self.epoch += 1
        self._adaptive_mutation()

        # Selection + reproduction
        elite_count = max(2, int(self.population_size * self.elitism_ratio))
        self.population.sort(key=lambda o: o.overall_fitness, reverse=True)
        new_pop = list(self.population[:elite_count])

        while len(new_pop) < self.population_size:
            p1 = self._tournament_select()
            p2 = self._tournament_select()
            child = self._crossover(p1, p2)
            self._mutate(child)
            self._evaluate_organism(child)

            # Novelty bonus: slight fitness boost for novel behaviors
            novelty = self._novelty_score(child)
            child.overall_fitness = child.overall_fitness * 0.85 + novelty * 0.15

            new_pop.append(child)

        self.population = new_pop[:self.population_size]

        # Update best
        current_best = max(self.population, key=lambda o: o.overall_fitness)
        improved = False
        if self.best_ever is None or current_best.overall_fitness > self.best_ever.overall_fitness:
            improvement = current_best.overall_fitness - (self.best_ever.overall_fitness if self.best_ever else 0)
            self.best_ever = current_best
            improved = True
            self.fitness_stagnation = 0
            self.improvement_history.append(improvement)
        else:
            self.fitness_stagnation += 1
            self.improvement_history.append(0.0)

        # Archive behaviors
        for org in self.population[:3]:
            self.behavior_archive.append((org.behavior_hash, org.overall_fitness))
        if len(self.behavior_archive) > 1000:
            self.behavior_archive = self.behavior_archive[-500:]

        # Periodically re-evaluate best on test domains
        if self.epoch % 5 == 0 and self.best_ever:
            self._evaluate_organism(self.best_ever, domain_names=self.test_domains, seeds=[42, 999])

        # Measure intelligence
        metrics = self._measure_intelligence()
        self.metrics_history.append(metrics.to_dict())
        self._check_intelligence_thresholds(metrics)

        return metrics

    def run(self, max_epochs: int = None):
        self.initialize()
        start_time = time.time()
        last_report_epoch = 0

        print(f"\n{'Epoch':>6} | {'Best':>8} | {'Mean':>8} | {'Stag':>4} | Intelligence")
        print("-" * 80)

        while self.running:
            metrics = self.run_epoch()

            # Print progress
            if self.epoch % 5 == 0 or self.epoch <= 3:
                print(f"{self.epoch:6d} | {metrics.best_fitness:8.5f} | {metrics.mean_fitness:8.5f} | "
                      f"{self.fitness_stagnation:4d} | {metrics.summary_line()}")

            # Detailed report every 50 epochs
            if self.epoch % 50 == 0:
                elapsed = time.time() - start_time
                eps = self.epoch / max(elapsed, 1)
                print(f"\n--- Epoch {self.epoch} Report (elapsed: {elapsed:.0f}s, {eps:.1f} epochs/s) ---")
                print(f"  Intelligence Score: {metrics.intelligence_score:.6f}")
                print(f"  Best genome (top 5): {self.best_ever.genome[:5].round(3).tolist()}")
                print(f"  Domain scores: {self.best_ever.fitness_per_domain}")
                if self.intelligence_detected:
                    print(f"  Milestones reached: {self.intelligence_detected}")
                print(f"  Mutation rate: {self.mutation_rate:.3f} (stagnation: {self.fitness_stagnation})")
                print()

            # Checkpoint every 100 epochs
            if self.epoch % 100 == 0:
                path = self._checkpoint("periodic")
                print(f"  [checkpoint saved: {path}]")

            if max_epochs and self.epoch >= max_epochs:
                break

        # Final checkpoint
        print(f"\n{'='*70}")
        print(f"  EVOLUTION COMPLETE - Epoch {self.epoch}")
        print(f"{'='*70}")
        final_metrics = self._measure_intelligence()
        print(f"  Final Intelligence Score: {final_metrics.intelligence_score:.6f}")
        print(f"  {final_metrics.summary_line()}")
        if self.intelligence_detected:
            print(f"  Milestones: {self.intelligence_detected}")
        else:
            print(f"  No intelligence thresholds crossed yet.")
        print(f"  Best fitness: {self.best_ever.overall_fitness:.6f}")
        print(f"  Domain scores: {self.best_ever.fitness_per_domain}")
        self._checkpoint("final")
        print(f"{'='*70}")

        return final_metrics

    @classmethod
    def from_checkpoint(cls, checkpoint_path: str) -> 'ContinuousIntelligenceEngine':
        with open(checkpoint_path) as f:
            state = json.load(f)

        engine = cls(
            population_size=state.get('population_size', 40),
            train_domains=state.get('train_domains'),
            test_domains=state.get('test_domains'),
            seed=state.get('seed', 42),
        )

        if state.get('ga_hyperparams'):
            hp = state['ga_hyperparams']
            engine.mutation_rate = hp.get('mutation_rate', 0.25)
            engine.crossover_rate = hp.get('crossover_rate', 0.7)
            engine.tournament_size = hp.get('tournament_size', 4)
            engine.elitism_ratio = hp.get('elitism_ratio', 0.15)
            engine.mutation_scale = hp.get('mutation_scale', 0.15)

        engine.epoch = state.get('epoch', 0)
        engine.intelligence_detected = state.get('intelligence_detected', {})
        engine.metrics_history = state.get('metrics_history', [])

        # Reconstruct population from top-5
        engine.population = []
        for org_dict in state.get('top_5', []):
            org = Organism(
                genome=np.array(org_dict['genome']),
                fitness_per_domain=org_dict.get('fitness_per_domain', {}),
                overall_fitness=org_dict.get('overall_fitness', 0),
                generation_born=org_dict.get('generation_born', 0),
                id=org_dict.get('id', engine._new_id()),
            )
            engine.population.append(org)

        while len(engine.population) < engine.population_size:
            engine.population.append(engine._random_organism())

        if state.get('best_ever'):
            be = state['best_ever']
            engine.best_ever = Organism(
                genome=np.array(be['genome']),
                fitness_per_domain=be.get('fitness_per_domain', {}),
                overall_fitness=be.get('overall_fitness', 0),
                generation_born=be.get('generation_born', 0),
                id=be.get('id', 0),
            )

        return engine


def show_report(checkpoint_dir: str):
    latest = os.path.join(checkpoint_dir, 'latest.json')
    if not os.path.exists(latest):
        print("No checkpoint found.")
        return

    with open(latest) as f:
        state = json.load(f)

    print("=" * 70)
    print("  INTELLIGENCE EVOLUTION REPORT")
    print("=" * 70)
    print(f"  Epoch: {state['epoch']}")
    print(f"  Timestamp: {state['timestamp']}")
    print(f"  Train domains: {state['train_domains']}")
    print(f"  Test domains: {state['test_domains']}")

    if state.get('best_ever'):
        be = state['best_ever']
        print(f"\n  Best Organism:")
        print(f"    Fitness: {be['overall_fitness']:.6f}")
        print(f"    Born: epoch {be['generation_born']}")
        print(f"    Domain scores:")
        for d, s in be.get('fitness_per_domain', {}).items():
            print(f"      {d:25s}: {s:.4f}")

    if state.get('intelligence_detected'):
        print(f"\n  Intelligence Milestones:")
        for level, epoch in state['intelligence_detected'].items():
            print(f"    {level:15s}: epoch {epoch}")
    else:
        print(f"\n  No intelligence milestones reached yet.")

    if state.get('metrics_history'):
        last = state['metrics_history'][-1]
        print(f"\n  Latest Metrics:")
        for k, v in last.items():
            if isinstance(v, float):
                print(f"    {k:25s}: {v:.6f}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Continuous Intelligence Evolution')
    parser.add_argument('--max-epochs', type=int, default=None, help='Max epochs (default: infinite)')
    parser.add_argument('--population', type=int, default=40)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--resume', type=str, default=None, help='Resume from checkpoint JSON')
    parser.add_argument('--report', action='store_true', help='Show latest report')
    parser.add_argument('--checkpoint-dir', type=str, default=None)
    args = parser.parse_args()

    if args.report:
        checkpoint_dir = args.checkpoint_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'intelligence_checkpoints'
        )
        show_report(checkpoint_dir)
        return

    if args.resume:
        engine = ContinuousIntelligenceEngine.from_checkpoint(args.resume)
        print(f"Resuming from epoch {engine.epoch}")
    else:
        engine = ContinuousIntelligenceEngine(
            population_size=args.population,
            seed=args.seed,
            checkpoint_dir=args.checkpoint_dir,
        )

    engine.run(max_epochs=args.max_epochs)


if __name__ == '__main__':
    main()
