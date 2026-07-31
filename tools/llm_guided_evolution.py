#!/usr/bin/env python3
"""
LLM-Guided Evolution (EvoPrompt / Evolution of Heuristics pattern)

Replaces random crossover and mutation in the GA with LLM-generated rewrites.
LLMs understand prompt semantics, so they produce dramatically better offspring
than random string operations.

Architecture:
- Crossover: Given two parent prompts + fitness scores, an LLM combines their
  best aspects into a child prompt.
- Mutation: Given a prompt + fitness + known weaknesses, an LLM creates an
  improved variant.
- Population management: Tournament selection (from ga_engine.py pattern),
  elitism, lineage tracking.
- Model selection: Rotates through free OpenRouter models to maintain diversity.
- Storage: Results persisted via REST API at aio-01:5000.

DATABASE: Uses REST API at aio-01:5000 (not direct psycopg2)
"""

import argparse
import hashlib
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_BASE = 'http://aio-01:5000'
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Free models suitable for prompt generation (not hard reasoning).
# Rotated to maintain diversity and avoid single-model bias.
EVOLUTION_MODELS = [
    'qwen/qwen3-235b-a22b:free',
    'deepseek/deepseek-chat-v3-0324:free',
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-4-maverick:free',
    'nvidia/llama-3.1-nemotron-70b-instruct:free',
    'microsoft/phi-4-reasoning-plus:free',
    'mistralai/mistral-small-3.1-24b-instruct:free',
    'google/gemma-3-27b-it:free',
]

# Lineage file (local JSON, same pattern as ga_engine.py)
LINEAGE_PATH = Path(__file__).parent / 'llm_evolution_lineage.json'

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)


# ---------------------------------------------------------------------------
# Prompt templates for LLM-guided operators
# ---------------------------------------------------------------------------

CROSSOVER_PROMPT = """You are an expert prompt engineer performing genetic crossover.
Given two parent prompts that have been evaluated, create a child prompt that combines the best aspects of both.

Parent 1 (fitness={p1_fitness:.3f}):
{parent1}

Parent 2 (fitness={p2_fitness:.3f}):
{parent2}

Create a new prompt that:
- Preserves the strongest elements from the higher-fitness parent
- Incorporates complementary strengths from the other parent
- Is roughly the same length as the parents
- Does not simply concatenate the parents

Respond with ONLY the child prompt, no explanation or commentary."""

MUTATION_PROMPT = """You are an expert prompt engineer performing genetic mutation.
Given this prompt and its fitness score, create an improved variant.

Original prompt (fitness={fitness:.3f}):
{prompt}

Known weaknesses: {weaknesses}

Create a mutated version that:
- Addresses the known weaknesses
- Maintains the core instruction structure
- Makes one significant change (not just rewording)
- Could potentially improve the fitness score

Respond with ONLY the mutated prompt, no explanation or commentary."""

SEED_PROMPT = """You are an expert prompt engineer. Generate a high-quality prompt for the following task type.

Task type: {task_type}
Task description: {task_description}

Requirements:
- The prompt should be clear, specific, and actionable
- Include relevant constraints and quality criteria
- Be between 100-400 words
- Use structured formatting (bullet points, numbered steps) where appropriate

Respond with ONLY the prompt, no explanation or commentary."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PromptIndividual:
    """An individual in the prompt evolution population."""

    prompt_text: str
    fitness: float = 0.0
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    operator: str = 'seed'  # seed, crossover, mutation, elite
    model_used: str = ''
    individual_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    weaknesses: str = ''
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'PromptIndividual':
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})

    def prompt_hash(self) -> str:
        """Deterministic hash for deduplication."""
        return hashlib.sha256(self.prompt_text.strip().encode()).hexdigest()[:16]

    def __repr__(self) -> str:
        snippet = self.prompt_text[:60].replace('\n', ' ')
        return (f"Individual(id={self.individual_id}, fitness={self.fitness:.3f}, "
                f"gen={self.generation}, op={self.operator}, "
                f"prompt=\"{snippet}...\")")


# ---------------------------------------------------------------------------
# OpenRouter LLM client
# ---------------------------------------------------------------------------

class LLMClient:
    """Calls free OpenRouter models for evolution operators."""

    def __init__(self):
        self._api_key: Optional[str] = None
        self._model_index = 0
        self._call_count = 0
        self._error_count = 0

    def _get_api_key(self) -> str:
        """Fetch OpenRouter API key from REST API (cached)."""
        if self._api_key:
            return self._api_key
        try:
            resp = requests.get(
                f'{API_BASE}/secrets/PERSONAL_OPENROUTER_API_KEY', timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            self._api_key = data.get('value', data.get('secret', ''))
            if not self._api_key:
                raise ValueError('Empty API key returned from secrets endpoint')
            return self._api_key
        except Exception as e:
            logger.error('Failed to fetch OpenRouter API key: %s', e)
            raise

    def _next_model(self) -> str:
        """Rotate through models for diversity."""
        model = EVOLUTION_MODELS[self._model_index % len(EVOLUTION_MODELS)]
        self._model_index += 1
        return model

    def call(self, prompt: str, model: Optional[str] = None,
             max_tokens: int = 1024, temperature: float = 0.8) -> Tuple[str, str]:
        """Call an LLM and return (response_text, model_used).

        Retries once with a different model on failure.
        """
        chosen_model = model or self._next_model()

        for attempt in range(2):
            try:
                api_key = self._get_api_key()
                resp = requests.post(
                    OPENROUTER_URL,
                    headers={
                        'Authorization': f'Bearer {api_key}',
                        'Content-Type': 'application/json',
                        'HTTP-Referer': 'https://claude-global-skills.local',
                    },
                    json={
                        'model': chosen_model,
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': max_tokens,
                        'temperature': temperature,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()

                content = ''
                choices = data.get('choices', [])
                if choices:
                    message = choices[0].get('message', {})
                    content = message.get('content', '')

                if not content.strip():
                    raise ValueError(f'Empty response from {chosen_model}')

                self._call_count += 1
                return content.strip(), chosen_model

            except Exception as e:
                self._error_count += 1
                logger.warning(
                    'LLM call failed (attempt %d, model=%s): %s',
                    attempt + 1, chosen_model, e,
                )
                if attempt == 0:
                    chosen_model = self._next_model()
                    time.sleep(1)
                else:
                    raise

        # Unreachable, but satisfies type checker
        raise RuntimeError('LLM call exhausted retries')

    @property
    def stats(self) -> Dict:
        return {
            'total_calls': self._call_count,
            'total_errors': self._error_count,
            'error_rate': (self._error_count / max(1, self._call_count + self._error_count)),
        }


# ---------------------------------------------------------------------------
# Fitness evaluation
# ---------------------------------------------------------------------------

class FitnessEvaluator:
    """Evaluate prompt fitness for a given task type.

    This is a pluggable evaluator. For now it uses a heuristic scoring
    function that measures structural quality indicators. In production,
    this would be replaced by actual task execution (e.g., running the
    prompt against a test set and measuring output quality).
    """

    # Structural quality indicators and their weights
    QUALITY_SIGNALS = {
        'has_clear_role': {
            'keywords': ['you are', 'act as', 'your role', 'as an expert',
                         'as a specialist'],
            'weight': 0.10,
        },
        'has_constraints': {
            'keywords': ['must', 'should', 'do not', 'avoid', 'never',
                         'always', 'ensure', 'make sure'],
            'weight': 0.10,
        },
        'has_structure': {
            'keywords': ['1.', '2.', '- ', '* ', 'step ', 'first,',
                         'then,', 'finally,'],
            'weight': 0.10,
        },
        'has_output_format': {
            'keywords': ['format', 'output', 'respond with', 'return',
                         'provide', 'list', 'report'],
            'weight': 0.10,
        },
        'has_examples': {
            'keywords': ['example', 'e.g.', 'for instance', 'such as',
                         'like this'],
            'weight': 0.08,
        },
        'has_quality_criteria': {
            'keywords': ['quality', 'accurate', 'thorough', 'comprehensive',
                         'precise', 'detailed', 'specific'],
            'weight': 0.08,
        },
        'has_edge_cases': {
            'keywords': ['edge case', 'corner case', 'exception', 'error',
                         'fallback', 'handle', 'boundary'],
            'weight': 0.07,
        },
        'has_context': {
            'keywords': ['context', 'background', 'given', 'considering',
                         'based on', 'taking into account'],
            'weight': 0.07,
        },
    }

    # Task-specific bonus keywords
    TASK_KEYWORDS = {
        'code review': [
            'security', 'performance', 'maintainability', 'bug', 'vulnerability',
            'pattern', 'anti-pattern', 'best practice', 'code smell',
            'error handling', 'edge case', 'race condition', 'injection',
        ],
        'research': [
            'source', 'citation', 'evidence', 'finding', 'methodology',
            'analysis', 'comparison', 'synthesis', 'conclusion', 'hypothesis',
            'data', 'primary source', 'peer-reviewed',
        ],
        'summarization': [
            'key points', 'main ideas', 'concise', 'brief', 'overview',
            'highlight', 'essential', 'core', 'summary', 'takeaway',
        ],
        'generation': [
            'creative', 'original', 'unique', 'coherent', 'consistent',
            'tone', 'style', 'audience', 'engaging', 'clear',
        ],
    }

    def __init__(self, task_type: str = 'code review'):
        self.task_type = task_type.lower()

    def evaluate(self, individual: PromptIndividual) -> float:
        """Evaluate fitness of a prompt individual.

        Returns a score between 0.0 and 1.0.
        """
        text = individual.prompt_text.lower()
        score = 0.0
        weaknesses = []

        # 1. Structural quality signals (0.0 - 0.70)
        for signal_name, config in self.QUALITY_SIGNALS.items():
            matches = sum(1 for kw in config['keywords'] if kw in text)
            if matches > 0:
                # Diminishing returns: more matches help but cap at 1.0
                signal_score = min(1.0, matches / 2.0) * config['weight']
                score += signal_score
            else:
                weaknesses.append(signal_name.replace('has_', 'missing '))

        # 2. Task-specific keyword bonus (0.0 - 0.15)
        task_keywords = self.TASK_KEYWORDS.get(self.task_type, [])
        if task_keywords:
            task_matches = sum(1 for kw in task_keywords if kw in text)
            task_score = min(1.0, task_matches / 4.0) * 0.15
            score += task_score
            if task_matches < 2:
                weaknesses.append(f'few task-specific keywords for {self.task_type}')

        # 3. Length penalty/bonus (0.0 - 0.10)
        word_count = len(text.split())
        if 50 <= word_count <= 500:
            length_score = 0.10
            if 100 <= word_count <= 300:
                length_score = 0.10  # sweet spot
            elif word_count < 100:
                length_score = 0.05
                weaknesses.append('prompt too short')
        else:
            length_score = 0.02
            if word_count < 50:
                weaknesses.append('prompt far too short')
            else:
                weaknesses.append('prompt too long')
        score += length_score

        # 4. Specificity bonus (0.0 - 0.05)
        # Reward prompts that have numbers, specific quantities, thresholds
        specificity_markers = [
            char for char in text if char.isdigit()
        ]
        if len(specificity_markers) >= 2:
            score += 0.05
        elif len(specificity_markers) >= 1:
            score += 0.02
        else:
            weaknesses.append('lacks specific numbers/thresholds')

        # Store weaknesses for mutation operator
        individual.weaknesses = '; '.join(weaknesses) if weaknesses else 'none identified'

        # Clamp to [0, 1]
        fitness = max(0.0, min(1.0, score))
        individual.fitness = round(fitness, 4)

        return fitness


# ---------------------------------------------------------------------------
# LLM-Guided Evolution Engine
# ---------------------------------------------------------------------------

class LLMGuidedEvolution:
    """Population manager using LLM-guided crossover and mutation.

    Maintains a population of prompts, applies tournament selection,
    LLM crossover, and LLM mutation, and tracks full lineage.
    """

    def __init__(
        self,
        task_type: str = 'code review',
        task_description: str = '',
        population_size: int = 20,
        mutation_rate: float = 0.3,
        elite_fraction: float = 0.2,
        tournament_size: int = 3,
    ):
        self.task_type = task_type
        self.task_description = task_description or f'Prompt for {task_type}'
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.elite_fraction = elite_fraction
        self.tournament_size = tournament_size

        self.llm = LLMClient()
        self.evaluator = FitnessEvaluator(task_type)
        self.population: List[PromptIndividual] = []
        self.generation = 0
        self.best_ever: Optional[PromptIndividual] = None
        self.generation_stats: List[Dict] = []
        self.all_individuals: List[PromptIndividual] = []

        # Deduplication: track prompt hashes to avoid clones
        self._seen_hashes: set = set()

        # Evolution run ID for storage
        self.run_id = f'evo-{datetime.now().strftime("%Y%m%dT%H%M%S")}-{uuid.uuid4().hex[:6]}'

        # Stop flag for external control
        self.stopped = False

    # -- Seed population ----------------------------------------------------

    def seed_population(self) -> List[PromptIndividual]:
        """Generate initial population using LLM calls."""
        logger.info(
            'Seeding population of %d for task: %s',
            self.population_size, self.task_type,
        )

        population = []
        attempts = 0
        max_attempts = self.population_size * 3  # allow retries for dedup

        while len(population) < self.population_size and attempts < max_attempts:
            attempts += 1
            try:
                prompt = SEED_PROMPT.format(
                    task_type=self.task_type,
                    task_description=self.task_description,
                )
                text, model = self.llm.call(prompt, temperature=1.0)

                individual = PromptIndividual(
                    prompt_text=text,
                    generation=0,
                    operator='seed',
                    model_used=model,
                )

                # Deduplication check
                h = individual.prompt_hash()
                if h in self._seen_hashes:
                    logger.debug('Duplicate seed prompt, retrying')
                    continue
                self._seen_hashes.add(h)

                # Evaluate fitness
                self.evaluator.evaluate(individual)
                population.append(individual)
                self.all_individuals.append(individual)

                logger.info(
                    'Seed %d/%d: fitness=%.3f model=%s',
                    len(population), self.population_size,
                    individual.fitness, model,
                )

            except Exception as e:
                logger.warning('Seed generation failed: %s', e)
                time.sleep(2)

        if len(population) < 2:
            raise RuntimeError(
                f'Could only seed {len(population)} individuals, need at least 2'
            )

        self.population = population
        self._update_best()
        self._record_generation_stats()

        logger.info(
            'Seeded %d individuals, best fitness=%.3f',
            len(population), self.best_ever.fitness if self.best_ever else 0,
        )

        return population

    # -- Selection ----------------------------------------------------------

    def tournament_select(self) -> PromptIndividual:
        """Select an individual via tournament selection."""
        k = min(self.tournament_size, len(self.population))
        tournament = random.sample(self.population, k)
        return max(tournament, key=lambda ind: ind.fitness)

    # -- LLM Crossover ------------------------------------------------------

    def llm_crossover(
        self, parent1: PromptIndividual, parent2: PromptIndividual
    ) -> Optional[PromptIndividual]:
        """Use an LLM to combine the best aspects of two parents."""
        try:
            prompt = CROSSOVER_PROMPT.format(
                p1_fitness=parent1.fitness,
                parent1=parent1.prompt_text,
                p2_fitness=parent2.fitness,
                parent2=parent2.prompt_text,
            )
            text, model = self.llm.call(prompt, temperature=0.7)

            child = PromptIndividual(
                prompt_text=text,
                generation=self.generation + 1,
                parent_ids=[parent1.individual_id, parent2.individual_id],
                operator='crossover',
                model_used=model,
            )

            # Dedup
            h = child.prompt_hash()
            if h in self._seen_hashes:
                return None
            self._seen_hashes.add(h)

            return child

        except Exception as e:
            logger.warning('LLM crossover failed: %s', e)
            return None

    # -- LLM Mutation -------------------------------------------------------

    def llm_mutate(
        self, individual: PromptIndividual
    ) -> Optional[PromptIndividual]:
        """Use an LLM to create an improved variant of a prompt."""
        try:
            weaknesses = individual.weaknesses or 'none specifically identified'
            prompt = MUTATION_PROMPT.format(
                fitness=individual.fitness,
                prompt=individual.prompt_text,
                weaknesses=weaknesses,
            )
            text, model = self.llm.call(prompt, temperature=0.9)

            mutant = PromptIndividual(
                prompt_text=text,
                generation=self.generation + 1,
                parent_ids=[individual.individual_id],
                operator='mutation',
                model_used=model,
            )

            # Dedup
            h = mutant.prompt_hash()
            if h in self._seen_hashes:
                return None
            self._seen_hashes.add(h)

            return mutant

        except Exception as e:
            logger.warning('LLM mutation failed: %s', e)
            return None

    # -- Fallback mutation (no LLM) ----------------------------------------

    def _fallback_mutate(
        self, individual: PromptIndividual
    ) -> Optional[PromptIndividual]:
        """Simple text-level mutation fallback when LLM calls fail.

        Swaps two random lines to produce a novel individual without
        requiring an LLM call, preventing population shrinkage.
        """
        lines = individual.prompt_text.strip().split('\n')
        if len(lines) > 2:
            i, j = random.sample(range(len(lines)), 2)
            lines[i], lines[j] = lines[j], lines[i]
        elif len(lines) == 2:
            lines[0], lines[1] = lines[1], lines[0]
        else:
            # Single line: shuffle two words
            words = lines[0].split()
            if len(words) > 3:
                i, j = random.sample(range(len(words)), 2)
                words[i], words[j] = words[j], words[i]
                lines[0] = ' '.join(words)
            else:
                return None  # Cannot meaningfully mutate

        text = '\n'.join(lines)
        mutant = PromptIndividual(
            prompt_text=text,
            generation=self.generation + 1,
            parent_ids=[individual.individual_id],
            operator='mutation',
            model_used='fallback-text-swap',
        )

        h = mutant.prompt_hash()
        if h in self._seen_hashes:
            return None
        self._seen_hashes.add(h)
        return mutant

    # -- Evolution loop -----------------------------------------------------

    def evolve_one_generation(self) -> Dict:
        """Produce the next generation via selection, crossover, and mutation."""
        if self.stopped:
            return {'stopped': True}

        # Sort population by fitness
        self.population.sort(key=lambda ind: ind.fitness, reverse=True)

        # Bug fix #4: Reset dedup set to current population only.
        # Prevents the set from growing monotonically across generations,
        # which would reject an increasing fraction of novel prompts.
        self._seen_hashes = {ind.prompt_hash() for ind in self.population}

        # Elitism: keep top fraction (do NOT mutate the operator field --
        # it records how the individual was *created*, not its current role)
        elite_count = max(1, int(self.population_size * self.elite_fraction))
        new_population = list(self.population[:elite_count])
        crossover_count = 0
        mutation_count = 0
        failed_count = 0

        # Fill remaining slots
        max_fill_attempts = (self.population_size - elite_count) * 3
        fill_attempts = 0

        while len(new_population) < self.population_size and fill_attempts < max_fill_attempts:
            if self.stopped:
                break

            fill_attempts += 1

            # Decide operator: crossover or mutation
            if random.random() < self.mutation_rate:
                # Mutation: select one parent, mutate it
                parent = self.tournament_select()
                child = self.llm_mutate(parent)
                if child:
                    self.evaluator.evaluate(child)
                    new_population.append(child)
                    self.all_individuals.append(child)
                    mutation_count += 1
                else:
                    failed_count += 1
            else:
                # Crossover: select two parents, combine
                parent1 = self.tournament_select()
                parent2 = self.tournament_select()

                # Avoid selfing: reselect if same individual
                retries = 0
                while parent2.individual_id == parent1.individual_id and retries < 3:
                    parent2 = self.tournament_select()
                    retries += 1

                # Bug fix #2: If still identical after retries, fall back
                # to mutation instead of feeding the LLM a trivial
                # self-crossover that produces a copy, not a real child.
                if parent2.individual_id == parent1.individual_id:
                    child = self.llm_mutate(parent1)
                    if child:
                        self.evaluator.evaluate(child)
                        new_population.append(child)
                        self.all_individuals.append(child)
                        mutation_count += 1
                    else:
                        failed_count += 1
                    time.sleep(0.5)
                    continue

                child = self.llm_crossover(parent1, parent2)
                if child:
                    self.evaluator.evaluate(child)
                    new_population.append(child)
                    self.all_individuals.append(child)
                    crossover_count += 1
                else:
                    failed_count += 1

            # Rate limiting: brief pause between LLM calls
            time.sleep(0.5)

        # Bug fix #3: Guarantee population size.  If LLM failures left
        # us short, fill remaining slots via text-level mutation of elites.
        while len(new_population) < self.population_size and new_population:
            donor = random.choice(new_population[:elite_count])
            fallback = self._fallback_mutate(donor)
            if fallback:
                self.evaluator.evaluate(fallback)
                new_population.append(fallback)
                self.all_individuals.append(fallback)
            else:
                # Even fallback produced a duplicate; clone donor to
                # maintain population size (will be deduplicated next gen)
                clone = PromptIndividual(
                    prompt_text=donor.prompt_text,
                    generation=self.generation + 1,
                    parent_ids=[donor.individual_id],
                    operator='elite',
                    model_used='population-fill',
                )
                new_population.append(clone)
                self.all_individuals.append(clone)

        self.generation += 1
        self.population = new_population[:self.population_size]
        self._update_best()
        stats = self._record_generation_stats()
        stats['crossover_count'] = crossover_count
        stats['mutation_count'] = mutation_count
        stats['failed_count'] = failed_count

        return stats

    def evolve(self, generations: int) -> PromptIndividual:
        """Run evolution for N generations.

        Returns the best individual found across all generations.
        """
        logger.info(
            'Starting LLM-guided evolution: %d generations, pop=%d, task=%s',
            generations, self.population_size, self.task_type,
        )

        # Seed if needed
        if not self.population:
            self.seed_population()

        for gen in range(generations):
            if self.stopped:
                logger.info('Evolution stopped at generation %d', gen)
                break

            stats = self.evolve_one_generation()

            logger.info(
                'Gen %d: best=%.3f avg=%.3f '
                '(crossover=%d mutation=%d failed=%d)',
                self.generation,
                stats.get('best_fitness', 0),
                stats.get('avg_fitness', 0),
                stats.get('crossover_count', 0),
                stats.get('mutation_count', 0),
                stats.get('failed_count', 0),
            )

            # Store lineage periodically
            if gen % 3 == 0 or gen == generations - 1:
                self._store_lineage()

        # Final storage
        self._store_lineage()
        self._store_results_via_api()

        logger.info(
            'Evolution complete: %d generations, best fitness=%.3f',
            self.generation,
            self.best_ever.fitness if self.best_ever else 0,
        )

        return self.best_ever

    # -- Internal helpers ---------------------------------------------------

    def _update_best(self):
        """Update best-ever individual."""
        if not self.population:
            return
        current_best = max(self.population, key=lambda ind: ind.fitness)
        if self.best_ever is None or current_best.fitness > self.best_ever.fitness:
            self.best_ever = current_best

    def _record_generation_stats(self) -> Dict:
        """Record statistics for the current generation."""
        fitnesses = [ind.fitness for ind in self.population]

        # Count operators; the first elite_count individuals are carried
        # forward as elites, but their .operator still records their origin
        elite_count = max(1, int(self.population_size * self.elite_fraction))
        operators = {'elite': min(elite_count, len(self.population))}
        for ind in self.population[elite_count:]:
            operators[ind.operator] = operators.get(ind.operator, 0) + 1

        avg_fit = sum(fitnesses) / len(fitnesses) if fitnesses else 0
        std_fit = (
            (sum((f - avg_fit) ** 2 for f in fitnesses) / len(fitnesses)) ** 0.5
            if len(fitnesses) > 1 else 0
        )
        stats = {
            'generation': self.generation,
            'best_fitness': max(fitnesses) if fitnesses else 0,
            'avg_fitness': avg_fit,
            'min_fitness': min(fitnesses) if fitnesses else 0,
            'std_fitness': std_fit,
            'population_size': len(self.population),
            'unique_hashes': len(self._seen_hashes),
            'operator_counts': operators,
            'timestamp': datetime.now().isoformat(),
        }
        self.generation_stats.append(stats)
        return stats

    def _store_lineage(self):
        """Store lineage to local JSON and POST convergence to REST API."""
        try:
            lineage_data = {}
            if LINEAGE_PATH.exists():
                try:
                    with open(LINEAGE_PATH, 'r') as f:
                        lineage_data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    lineage_data = {}

            if 'runs' not in lineage_data:
                lineage_data['runs'] = {}

            run_data = lineage_data['runs'].setdefault(self.run_id, {
                'task_type': self.task_type,
                'started_at': datetime.now().isoformat(),
                'generations': {},
            })

            gen_key = str(self.generation)
            run_data['generations'][gen_key] = {
                'timestamp': datetime.now().isoformat(),
                'population': [ind.to_dict() for ind in self.population],
                'stats': self.generation_stats[-1] if self.generation_stats else {},
            }
            run_data['best_ever'] = (
                self.best_ever.to_dict() if self.best_ever else None
            )
            run_data['llm_stats'] = self.llm.stats

            with open(LINEAGE_PATH, 'w') as f:
                json.dump(lineage_data, f, indent=2)

            # REST API convergence tracking
            if self.generation_stats:
                latest = self.generation_stats[-1]
                diversity = (
                    latest['avg_fitness'] / latest['best_fitness']
                    if latest['best_fitness'] > 0 else 0
                )
                try:
                    requests.post(f'{API_BASE}/ga/convergence', json={
                        'use_case': f'llm-evolution-{self.task_type}',
                        'generation': self.generation,
                        'best_fitness': latest['best_fitness'],
                        'avg_fitness': latest['avg_fitness'],
                        'island_id': 0,
                        'diversity': round(diversity, 4),
                    }, timeout=10)
                except requests.exceptions.RequestException as e:
                    logger.debug('Convergence POST failed: %s', e)

        except Exception as e:
            logger.warning('Failed to store lineage: %s', e)

    def _store_results_via_api(self):
        """Store final results via REST API."""
        if not self.best_ever:
            return

        stored_count = 0
        error_count = 0

        # Store best solution
        try:
            resp = requests.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': f'llm-evolution-{self.task_type}',
                'chromosome': json.dumps({
                    'prompt_text': self.best_ever.prompt_text,
                    'operator': self.best_ever.operator,
                    'model_used': self.best_ever.model_used,
                    'parent_ids': self.best_ever.parent_ids,
                }),
                'fitness': float(self.best_ever.fitness),
                'fitness_details': json.dumps({
                    'best_fitness': float(self.best_ever.fitness),
                    'final_avg_fitness': float(
                        self.generation_stats[-1]['avg_fitness']
                        if self.generation_stats else 0
                    ),
                    'total_generations': self.generation,
                    'total_individuals': len(self.all_individuals),
                    'llm_calls': self.llm.stats['total_calls'],
                    'llm_errors': self.llm.stats['total_errors'],
                }),
                'generation_found': self.best_ever.generation,
                'notes': (
                    f'LLM-guided evolution ({self.task_type}): '
                    f'{self.generation} generations, '
                    f'fitness={self.best_ever.fitness:.3f}, '
                    f'{self.llm.stats["total_calls"]} LLM calls'
                ),
            }, timeout=10)
            if resp.status_code < 300:
                stored_count += 1
                logger.info('Stored best solution via API (status %d)', resp.status_code)
            else:
                error_count += 1
                logger.warning('best-solutions POST returned %d', resp.status_code)
        except requests.exceptions.RequestException as e:
            error_count += 1
            logger.warning('best-solutions POST failed: %s', e)

        # Store strategy performance
        try:
            resp = requests.post(f'{API_BASE}/ga/strategies', json={
                'use_case': f'llm-evolution-{self.task_type}',
                'strategy': 'llm_guided_crossover_mutation',
                'avg_reward': float(self.best_ever.fitness),
                'total_reward': float(
                    sum(s['best_fitness'] for s in self.generation_stats)
                ),
                'successes': self.generation,
                'failures': self.llm.stats['total_errors'],
                'alpha': 1.0,
                'beta': 1.0,
            }, timeout=10)
            if resp.status_code < 300:
                stored_count += 1
                logger.info('Stored strategy performance via API')
            else:
                error_count += 1
        except requests.exceptions.RequestException as e:
            error_count += 1
            logger.warning('strategies POST failed: %s', e)

        logger.info(
            'API storage: %d stored, %d errors', stored_count, error_count
        )

    # -- Public accessors ---------------------------------------------------

    def get_best(self) -> Optional[Dict]:
        """Return the best individual as a dict."""
        if self.best_ever:
            return self.best_ever.to_dict()
        return None

    def get_status(self) -> Dict:
        """Return current evolution status."""
        return {
            'run_id': self.run_id,
            'task_type': self.task_type,
            'generation': self.generation,
            'population_size': len(self.population),
            'best_fitness': self.best_ever.fitness if self.best_ever else 0,
            'avg_fitness': (
                sum(ind.fitness for ind in self.population) / len(self.population)
                if self.population else 0
            ),
            'total_individuals': len(self.all_individuals),
            'unique_prompts': len(self._seen_hashes),
            'llm_stats': self.llm.stats,
            'stopped': self.stopped,
            'generation_stats': self.generation_stats,
        }

    def get_lineage(self, individual_id: str) -> List[Dict]:
        """Trace the lineage of an individual back to its ancestors.

        Bug fix #5: Falls back to the lineage JSON file so lineage
        queries work for completed runs, not only the active one.
        """
        # Build index from in-memory individuals
        index: Dict[str, dict] = {
            ind.individual_id: ind.to_dict() for ind in self.all_individuals
        }

        # Merge file-based index for completed runs
        file_index = _load_lineage_index_from_file()
        for iid, ind_dict in file_index.items():
            if iid not in index:
                index[iid] = ind_dict

        lineage: List[Dict] = []
        queue = [individual_id]
        visited: set = set()

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            ind = index.get(current_id)
            if ind:
                lineage.append(ind)
                for pid in ind.get('parent_ids', []):
                    if pid not in visited:
                        queue.append(pid)

        return lineage


# ---------------------------------------------------------------------------
# Standalone lineage helpers (usable without an active engine instance)
# ---------------------------------------------------------------------------

def _load_lineage_index_from_file() -> Dict[str, Dict]:
    """Build an individual index from the lineage JSON file."""
    index: Dict[str, Dict] = {}
    if not LINEAGE_PATH.exists():
        return index
    try:
        with open(LINEAGE_PATH, 'r') as f:
            data = json.load(f)
        for _run_id, run_data in data.get('runs', {}).items():
            for _gen_key, gen_data in run_data.get('generations', {}).items():
                for ind_dict in gen_data.get('population', []):
                    iid = ind_dict.get('individual_id', '')
                    if iid:
                        index[iid] = ind_dict
    except (json.JSONDecodeError, IOError):
        pass
    return index


def load_lineage_from_file(individual_id: str) -> List[Dict]:
    """Load lineage for an individual from the JSON file.

    Works without an active LLMGuidedEvolution instance, enabling
    lineage queries for completed runs.
    """
    index = _load_lineage_index_from_file()

    lineage: List[Dict] = []
    queue = [individual_id]
    visited: set = set()

    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)

        ind = index.get(current_id)
        if ind:
            lineage.append(ind)
            for pid in ind.get('parent_ids', []):
                if pid not in visited:
                    queue.append(pid)

    return lineage


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='LLM-Guided Prompt Evolution (EvoPrompt pattern)',
    )
    parser.add_argument(
        '--task', type=str, default='code review',
        help='Task type to evolve prompts for (default: "code review")',
    )
    parser.add_argument(
        '--description', type=str, default='',
        help='Detailed task description',
    )
    parser.add_argument(
        '--population', type=int, default=20,
        help='Population size (default: 20)',
    )
    parser.add_argument(
        '--generations', type=int, default=10,
        help='Number of generations (default: 10)',
    )
    parser.add_argument(
        '--mutation-rate', type=float, default=0.3,
        help='Mutation rate 0.0-1.0 (default: 0.3)',
    )
    parser.add_argument(
        '--elite-fraction', type=float, default=0.2,
        help='Fraction of population to keep as elites (default: 0.2)',
    )
    parser.add_argument(
        '--tournament-size', type=int, default=3,
        help='Tournament selection size (default: 3)',
    )
    parser.add_argument(
        '--output', type=str, default='',
        help='Output file for results JSON (default: auto-generated)',
    )
    args = parser.parse_args()

    print('=' * 70)
    print('LLM-GUIDED PROMPT EVOLUTION')
    print('=' * 70)
    print(f'Task:        {args.task}')
    print(f'Population:  {args.population}')
    print(f'Generations: {args.generations}')
    print(f'Mutation:    {args.mutation_rate}')
    print(f'Elite:       {args.elite_fraction}')
    print(f'Tournament:  {args.tournament_size}')
    print('=' * 70)

    evo = LLMGuidedEvolution(
        task_type=args.task,
        task_description=args.description,
        population_size=args.population,
        mutation_rate=args.mutation_rate,
        elite_fraction=args.elite_fraction,
        tournament_size=args.tournament_size,
    )

    start_time = time.time()
    best = evo.evolve(args.generations)
    elapsed = time.time() - start_time

    print('\n' + '=' * 70)
    print('RESULTS')
    print('=' * 70)

    if best:
        print(f'\nBest Prompt (fitness={best.fitness:.3f}, gen={best.generation}):')
        print('-' * 50)
        print(best.prompt_text)
        print('-' * 50)
        print(f'\nOperator:   {best.operator}')
        print(f'Model:      {best.model_used}')
        print(f'Parents:    {best.parent_ids}')
        print(f'Weaknesses: {best.weaknesses}')

    status = evo.get_status()
    print(f'\nEvolution Stats:')
    print(f'  Run ID:          {status["run_id"]}')
    print(f'  Generations:     {status["generation"]}')
    print(f'  Total prompts:   {status["total_individuals"]}')
    print(f'  Unique prompts:  {status["unique_prompts"]}')
    print(f'  LLM calls:       {status["llm_stats"]["total_calls"]}')
    print(f'  LLM errors:      {status["llm_stats"]["total_errors"]}')
    print(f'  Elapsed:         {elapsed:.1f}s')

    # Convergence summary
    if evo.generation_stats:
        print(f'\nConvergence:')
        for s in evo.generation_stats:
            print(
                f'  Gen {s["generation"]:3d}: '
                f'best={s["best_fitness"]:.3f} '
                f'avg={s["avg_fitness"]:.3f} '
                f'min={s["min_fitness"]:.3f}'
            )

    # Save results
    output_file = args.output or (
        f'{Path(__file__).parent}/'
        f'llm_evolution_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )
    results = {
        'run_id': status['run_id'],
        'task_type': args.task,
        'best_prompt': best.prompt_text if best else '',
        'best_fitness': best.fitness if best else 0,
        'generation_stats': evo.generation_stats,
        'llm_stats': status['llm_stats'],
        'elapsed_seconds': elapsed,
        'timestamp': datetime.now().isoformat(),
        'config': {
            'population_size': args.population,
            'generations': args.generations,
            'mutation_rate': args.mutation_rate,
            'elite_fraction': args.elite_fraction,
            'tournament_size': args.tournament_size,
        },
    }
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'\nResults saved to: {output_file}')

    return results


if __name__ == '__main__':
    main()
