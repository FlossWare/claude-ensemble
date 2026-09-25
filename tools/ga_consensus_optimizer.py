#!/usr/bin/env python3
"""GA Consensus Threshold Optimizer

Evolves optimal consensus parameters for multi-AI voting across different
decision types. Parameters include: vote threshold, tie-breaking strategy,
confidence weighting, diversity requirements, and escalation rules.

The fitness function balances decision accuracy against decision speed
(fewer re-votes needed) and robustness (correct under adversarial conditions).

Usage:
    python3 ga_consensus_optimizer.py                    # 50 gens
    python3 ga_consensus_optimizer.py --generations 200
"""

import argparse
import json
import math
import os
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')

DECISION_TYPES = [
    'code_approval',     # approve/reject code changes
    'bug_triage',        # severity classification
    'model_selection',   # which model for a task
    'design_review',     # architectural decisions
    'security_audit',    # security finding validation
    'merge_decision',    # merge or block PR
]

TIEBREAK_STRATEGIES = ['strongest_model', 'most_confident', 'random', 'escalate', 'abstain']
ESCALATION_TARGETS = ['human', 'stronger_model', 'larger_panel', 'defer']


@dataclass
class ConsensusConfig:
    decision_type: str = 'code_approval'
    min_voters: int = 3
    vote_threshold: float = 0.6       # fraction needed to pass
    confidence_weight: bool = True     # weight votes by model confidence
    min_confidence: float = 0.3       # minimum confidence to count a vote
    diversity_required: int = 2        # min distinct model families
    tiebreak: str = 'strongest_model'
    escalation_trigger: float = 0.1    # margin below threshold to escalate
    escalation_target: str = 'stronger_model'
    max_rounds: int = 2                # max re-vote rounds
    require_reasoning: bool = True     # require models to explain vote
    adversarial_veto: bool = False     # single strong disagreement blocks


@dataclass
class ConsensusChromosome:
    configs: Dict[str, ConsensusConfig] = field(default_factory=dict)
    fitness: Optional[float] = None
    fitness_details: Optional[Dict] = None

    def to_dict(self):
        return {name: asdict(cfg) for name, cfg in self.configs.items()}


# Simulated model voting behavior
MODEL_FAMILIES = {
    'anthropic': ['opus', 'sonnet', 'haiku', 'fable'],
    'openai': ['gpt4o'],
    'google': ['gemini'],
    'meta': ['llama-3.3-70b'],
    'deepseek': ['deepseek-chat'],
    'qwen': ['qwen3-235b'],
    'mistral': ['mistral-small'],
}

ALL_MODELS = [m for fam in MODEL_FAMILIES.values() for m in fam]

MODEL_ACCURACY = {
    'opus': 0.93, 'sonnet': 0.88, 'haiku': 0.72, 'fable': 0.90,
    'gpt4o': 0.91, 'gemini': 0.85, 'llama-3.3-70b': 0.82,
    'deepseek-chat': 0.84, 'qwen3-235b': 0.86, 'mistral-small': 0.78,
}

TASK_DIFFICULTY = {
    'code_approval': 0.7, 'bug_triage': 0.6, 'model_selection': 0.5,
    'design_review': 0.8, 'security_audit': 0.85, 'merge_decision': 0.65,
}


class VotingSimulator:
    """Simulates multi-AI consensus voting."""

    def __init__(self, num_scenarios=50, noise_std=0.1):
        self.num_scenarios = num_scenarios
        self.noise_std = noise_std

    def simulate(self, config: ConsensusConfig, seed=42) -> Dict:
        rng = np.random.RandomState(seed)
        correct_decisions = 0
        total_rounds = 0
        escalations = 0
        false_accepts = 0
        false_rejects = 0
        difficulty = TASK_DIFFICULTY.get(config.decision_type, 0.7)

        for scenario in range(self.num_scenarios):
            ground_truth = rng.random() > 0.4  # 60% should pass
            voters = rng.choice(ALL_MODELS, size=min(config.min_voters, len(ALL_MODELS)), replace=False)

            # Check diversity requirement
            families_present = set()
            for v in voters:
                for fam, members in MODEL_FAMILIES.items():
                    if v in members:
                        families_present.add(fam)
            if len(families_present) < config.diversity_required:
                extra_needed = config.diversity_required - len(families_present)
                for fam, members in MODEL_FAMILIES.items():
                    if fam not in families_present and extra_needed > 0:
                        voters = np.append(voters, rng.choice(members))
                        families_present.add(fam)
                        extra_needed -= 1

            made_decision = False
            decision = None
            for round_num in range(config.max_rounds):
                total_rounds += 1
                votes = []
                confidences = []

                for voter in voters:
                    accuracy = MODEL_ACCURACY.get(voter, 0.75)
                    effective_acc = accuracy * (1 - difficulty * 0.3) + rng.normal(0, self.noise_std)
                    effective_acc = max(0.1, min(0.99, effective_acc))

                    correct_vote = rng.random() < effective_acc
                    vote = ground_truth if correct_vote else (not ground_truth)
                    confidence = abs(effective_acc - 0.5) * 2 + rng.normal(0, 0.1)
                    confidence = max(0.0, min(1.0, confidence))

                    if confidence >= config.min_confidence:
                        votes.append(vote)
                        confidences.append(confidence)

                if not votes:
                    escalations += 1
                    decision = rng.random() > 0.5
                    made_decision = True
                    break

                if config.confidence_weight and confidences:
                    total_weight = sum(confidences)
                    weighted_yes = sum(c for v, c in zip(votes, confidences) if v)
                    vote_fraction = weighted_yes / total_weight if total_weight > 0 else 0.5
                else:
                    vote_fraction = sum(votes) / len(votes)

                if vote_fraction >= config.vote_threshold:
                    decision = True
                    made_decision = True
                elif vote_fraction <= (1 - config.vote_threshold):
                    decision = False
                    made_decision = True
                elif abs(vote_fraction - config.vote_threshold) < config.escalation_trigger:
                    escalations += 1
                    if config.escalation_target == 'larger_panel':
                        extra = rng.choice([m for m in ALL_MODELS if m not in voters],
                                          size=min(2, len(ALL_MODELS) - len(voters)), replace=False)
                        voters = np.append(voters, extra)
                    continue
                else:
                    # Tiebreak
                    if config.tiebreak == 'strongest_model':
                        best_voter_idx = np.argmax([MODEL_ACCURACY.get(v, 0.5) for v in voters])
                        decision = votes[best_voter_idx] if best_voter_idx < len(votes) else True
                    elif config.tiebreak == 'most_confident':
                        best_conf_idx = np.argmax(confidences)
                        decision = votes[best_conf_idx]
                    elif config.tiebreak == 'escalate':
                        escalations += 1
                        decision = ground_truth  # human gets it right
                    elif config.tiebreak == 'abstain':
                        continue
                    else:
                        decision = rng.random() > 0.5
                    made_decision = True

                if config.adversarial_veto and made_decision:
                    strong_disagreers = [v for v, c, vote in zip(voters, confidences, votes)
                                        if not vote == decision and c > 0.8
                                        and MODEL_ACCURACY.get(v, 0.5) > 0.88]
                    if strong_disagreers:
                        escalations += 1
                        decision = ground_truth

                if made_decision:
                    break

            if not made_decision:
                decision = rng.random() > 0.5

            if decision == ground_truth:
                correct_decisions += 1
            elif decision and not ground_truth:
                false_accepts += 1
            elif not decision and ground_truth:
                false_rejects += 1

        accuracy = correct_decisions / self.num_scenarios
        avg_rounds = total_rounds / self.num_scenarios
        escalation_rate = escalations / self.num_scenarios

        return {
            'accuracy': accuracy,
            'avg_rounds': avg_rounds,
            'escalation_rate': escalation_rate,
            'false_accept_rate': false_accepts / self.num_scenarios,
            'false_reject_rate': false_rejects / self.num_scenarios,
        }


class ConsensusGA:
    def __init__(self, population_size=30, mutation_rate=0.20, seed=None):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.simulator = VotingSimulator(num_scenarios=80)
        self.convergence_history = []
        self.best_fitness = 0.0
        self.best_chromosome = None
        self.stagnation = 0

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def create_random(self) -> ConsensusChromosome:
        configs = {}
        for dt in DECISION_TYPES:
            configs[dt] = ConsensusConfig(
                decision_type=dt,
                min_voters=random.randint(3, 8),
                vote_threshold=round(random.uniform(0.5, 0.9), 2),
                confidence_weight=random.random() > 0.3,
                min_confidence=round(random.uniform(0.1, 0.6), 2),
                diversity_required=random.randint(1, 4),
                tiebreak=random.choice(TIEBREAK_STRATEGIES),
                escalation_trigger=round(random.uniform(0.05, 0.3), 2),
                escalation_target=random.choice(ESCALATION_TARGETS),
                max_rounds=random.randint(1, 3),
                require_reasoning=random.random() > 0.4,
                adversarial_veto=random.random() > 0.7,
            )
        return ConsensusChromosome(configs=configs)

    def create_seeded(self) -> List[ConsensusChromosome]:
        seeds = []

        # Seed 1: Conservative (high threshold, veto power)
        c1 = {}
        for dt in DECISION_TYPES:
            c1[dt] = ConsensusConfig(
                decision_type=dt, min_voters=6, vote_threshold=0.8,
                confidence_weight=True, min_confidence=0.4,
                diversity_required=3, tiebreak='escalate',
                escalation_trigger=0.15, escalation_target='human',
                max_rounds=3, require_reasoning=True, adversarial_veto=True)
        seeds.append(ConsensusChromosome(configs=c1))

        # Seed 2: Fast (low threshold, minimal voters)
        c2 = {}
        for dt in DECISION_TYPES:
            c2[dt] = ConsensusConfig(
                decision_type=dt, min_voters=3, vote_threshold=0.55,
                confidence_weight=False, min_confidence=0.1,
                diversity_required=1, tiebreak='strongest_model',
                escalation_trigger=0.05, escalation_target='defer',
                max_rounds=1, require_reasoning=False, adversarial_veto=False)
        seeds.append(ConsensusChromosome(configs=c2))

        # Seed 3: Balanced (per-type tuning)
        c3 = {}
        type_params = {
            'code_approval': (5, 0.65, True, 3, 'strongest_model', False),
            'bug_triage': (4, 0.6, True, 2, 'most_confident', False),
            'model_selection': (3, 0.55, False, 2, 'random', False),
            'design_review': (6, 0.75, True, 3, 'escalate', True),
            'security_audit': (7, 0.8, True, 4, 'escalate', True),
            'merge_decision': (5, 0.7, True, 3, 'strongest_model', False),
        }
        for dt in DECISION_TYPES:
            nv, thr, cw, div, tb, veto = type_params[dt]
            c3[dt] = ConsensusConfig(
                decision_type=dt, min_voters=nv, vote_threshold=thr,
                confidence_weight=cw, min_confidence=0.3,
                diversity_required=div, tiebreak=tb,
                escalation_trigger=0.1, escalation_target='stronger_model',
                max_rounds=2, require_reasoning=True, adversarial_veto=veto)
        seeds.append(ConsensusChromosome(configs=c3))

        return seeds

    def calculate_fitness(self, chromosome: ConsensusChromosome) -> float:
        """
        Fitness = accuracy * 0.40 + speed * 0.20 + robustness * 0.20
                + safety * 0.20

        Evaluated across 3 seeds.
        """
        accuracy_scores = []
        speed_scores = []
        safety_scores = []

        for dt, cfg in chromosome.configs.items():
            results = []
            for s in [42, 123, 456]:
                r = self.simulator.simulate(cfg, seed=s + hash(dt) % 1000)
                results.append(r)

            avg_acc = np.mean([r['accuracy'] for r in results])
            avg_rounds = np.mean([r['avg_rounds'] for r in results])
            avg_fa = np.mean([r['false_accept_rate'] for r in results])
            avg_fr = np.mean([r['false_reject_rate'] for r in results])

            accuracy_scores.append(avg_acc)

            speed = max(0, 1.0 - (avg_rounds - 1.0) / 3.0)
            speed_scores.append(speed)

            # Safety: penalize false accepts more for security, false rejects more for merge
            if dt in ('security_audit', 'design_review'):
                safety = max(0, 1.0 - avg_fa * 5)
            elif dt in ('merge_decision', 'code_approval'):
                safety = max(0, 1.0 - avg_fr * 3 - avg_fa * 2)
            else:
                safety = max(0, 1.0 - avg_fa * 2 - avg_fr * 2)
            safety_scores.append(safety)

        accuracy = float(np.mean(accuracy_scores))
        speed = float(np.mean(speed_scores))
        safety = float(np.mean(safety_scores))
        robustness = float(np.std(accuracy_scores))
        robustness_score = max(0, 1.0 - robustness * 5)

        fitness = accuracy * 0.40 + speed * 0.20 + robustness_score * 0.20 + safety * 0.20

        chromosome.fitness = round(fitness, 5)
        chromosome.fitness_details = {
            'accuracy': round(accuracy, 4),
            'speed': round(speed, 4),
            'robustness': round(robustness_score, 4),
            'safety': round(safety, 4),
        }
        return fitness

    def crossover(self, p1: ConsensusChromosome, p2: ConsensusChromosome) -> ConsensusChromosome:
        configs = {}
        for dt in DECISION_TYPES:
            c1 = p1.configs.get(dt)
            c2 = p2.configs.get(dt)
            if c1 and c2:
                d1, d2 = asdict(c1), asdict(c2)
                child = {}
                for key in d1:
                    child[key] = d1[key] if random.random() < 0.5 else d2[key]
                configs[dt] = ConsensusConfig(**child)
            elif c1:
                configs[dt] = ConsensusConfig(**asdict(c1))
            elif c2:
                configs[dt] = ConsensusConfig(**asdict(c2))
        return ConsensusChromosome(configs=configs)

    def mutate(self, chromosome: ConsensusChromosome):
        for dt, cfg in chromosome.configs.items():
            if random.random() < self.mutation_rate:
                gene = random.choice([
                    'min_voters', 'vote_threshold', 'confidence_weight',
                    'min_confidence', 'diversity_required', 'tiebreak',
                    'escalation_trigger', 'escalation_target', 'max_rounds',
                    'adversarial_veto'])

                if gene == 'min_voters':
                    cfg.min_voters = max(3, min(8, cfg.min_voters + random.randint(-1, 1)))
                elif gene == 'vote_threshold':
                    cfg.vote_threshold = round(max(0.5, min(0.9, cfg.vote_threshold + random.uniform(-0.08, 0.08))), 2)
                elif gene == 'confidence_weight':
                    cfg.confidence_weight = not cfg.confidence_weight
                elif gene == 'min_confidence':
                    cfg.min_confidence = round(max(0.1, min(0.6, cfg.min_confidence + random.uniform(-0.1, 0.1))), 2)
                elif gene == 'diversity_required':
                    cfg.diversity_required = max(1, min(4, cfg.diversity_required + random.randint(-1, 1)))
                elif gene == 'tiebreak':
                    cfg.tiebreak = random.choice(TIEBREAK_STRATEGIES)
                elif gene == 'escalation_trigger':
                    cfg.escalation_trigger = round(max(0.05, min(0.3, cfg.escalation_trigger + random.uniform(-0.05, 0.05))), 2)
                elif gene == 'escalation_target':
                    cfg.escalation_target = random.choice(ESCALATION_TARGETS)
                elif gene == 'max_rounds':
                    cfg.max_rounds = max(1, min(3, cfg.max_rounds + random.choice([-1, 0, 1])))
                elif gene == 'adversarial_veto':
                    cfg.adversarial_veto = not cfg.adversarial_veto

    def tournament_select(self, population):
        candidates = random.sample(population, min(4, len(population)))
        return max(candidates, key=lambda c: c.fitness or 0)

    def run(self, generations=50):
        print("=" * 70)
        print("  GA Consensus Threshold Optimizer")
        print("=" * 70)
        print(f"Decision types: {len(DECISION_TYPES)}")
        print(f"Genes per type: 11, Total genes: {11 * len(DECISION_TYPES)}")
        print(f"Models: {len(ALL_MODELS)} across {len(MODEL_FAMILIES)} families")
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
                      f"Acc={d['accuracy']:.3f} Spd={d['speed']:.3f} "
                      f"Rob={d['robustness']:.3f} Saf={d['safety']:.3f}")
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
        print("  BEST CONSENSUS CONFIGURATIONS")
        print("=" * 70)
        print(f"  Overall Fitness: {best.fitness:.5f}")
        if best.fitness_details:
            for k, v in best.fitness_details.items():
                print(f"    {k:20s}: {v}")

        for dt in DECISION_TYPES:
            cfg = best.configs.get(dt)
            if cfg:
                print(f"\n  [{dt.upper()}]")
                print(f"    Voters:     {cfg.min_voters} (diversity={cfg.diversity_required} families)")
                print(f"    Threshold:  {cfg.vote_threshold} ({cfg.consensus_method if hasattr(cfg, 'consensus_method') else 'vote'})")
                print(f"    Confidence: weighted={cfg.confidence_weight}, min={cfg.min_confidence}")
                print(f"    Tiebreak:   {cfg.tiebreak}")
                print(f"    Escalation: trigger={cfg.escalation_trigger}, target={cfg.escalation_target}")
                print(f"    Rounds:     max={cfg.max_rounds}")
                print(f"    Veto:       {cfg.adversarial_veto}")
        print("=" * 70)

    def _store_results(self):
        best = self.best_chromosome
        if not best:
            return

        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(output_dir, 'best_consensus_config.json')

        with open(output_path, 'w') as f:
            json.dump({
                'configs': best.to_dict(),
                'fitness': best.fitness,
                'fitness_details': best.fitness_details,
                'metadata': {'created_at': time.strftime('%Y-%m-%dT%H:%M:%S')},
            }, f, indent=2)
        print(f"\nConfig saved to: {output_path}")

        try:
            requests.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': 'consensus-optimizer',
                'chromosome': json.dumps(best.to_dict()),
                'fitness': float(best.fitness or 0),
                'fitness_details': json.dumps(best.fitness_details or {}),
                'generation_found': len(self.convergence_history),
            }, timeout=5)
            print("Stored in ga.best_solutions via REST API")
        except Exception:
            print("API unavailable — stored locally only")


def main():
    parser = argparse.ArgumentParser(description='GA Consensus Optimizer')
    parser.add_argument('--generations', type=int, default=50)
    parser.add_argument('--population', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    ga = ConsensusGA(population_size=args.population, seed=args.seed)
    ga.run(generations=args.generations)


if __name__ == '__main__':
    main()
