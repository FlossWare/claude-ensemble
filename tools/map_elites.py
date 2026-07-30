#!/usr/bin/env python3
"""
MAP-Elites: Quality-Diversity Algorithm for Prompt Evolution

Maintains an archive of diverse, high-quality prompts across a behavior space
instead of converging to a single best. Each cell in the behavior grid holds the
best-performing prompt for that behavioral niche (length x style x specificity).

Architecture:
- Behavior characterization: 3 dimensions (length, style, specificity)
- Archive: Sparse grid mapping behavior bins to best individuals
- Evolution: Sample from archive, mutate via LLM, evaluate, place in archive
- LLM-guided variation: Targeted rewrites toward specific behavior cells
- Fitness evaluation: Reuses FitnessEvaluator from llm_guided_evolution.py
- Storage: Lineage and convergence via REST API at aio-01:5000

DATABASE: Uses REST API at aio-01:5000 (not direct psycopg2)
"""

import argparse
import ast
import hashlib
import json
import logging
import random
import re
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_BASE = 'http://aio-01:5000'
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Free models for generating prompt variants (rotated for diversity)
VARIATION_MODELS = [
    'qwen/qwen3-235b-a22b:free',
    'deepseek/deepseek-chat-v3-0324:free',
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-4-maverick:free',
    'nvidia/llama-3.1-nemotron-70b-instruct:free',
    'microsoft/phi-4-reasoning-plus:free',
    'mistralai/mistral-small-3.1-24b-instruct:free',
    'google/gemma-3-27b-it:free',
]

# Style classification model (needs to be good at analysis)
STYLE_CLASSIFIER_MODEL = 'qwen/qwen3-235b-a22b:free'

# Lineage file (local JSON, same pattern as ga_engine.py)
LINEAGE_PATH = Path(__file__).parent / 'map_elites_lineage.json'

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)


# ---------------------------------------------------------------------------
# Behavior Dimensions
# ---------------------------------------------------------------------------

# Dimension 1: Length bins (word count thresholds)
LENGTH_BINS = ['very-short', 'short', 'medium', 'long', 'very-long']
LENGTH_THRESHOLDS = [50, 100, 200, 400]  # words: <50, 50-99, 100-199, 200-399, 400+

# Dimension 2: Style bins (classified by LLM)
STYLE_BINS = ['directive', 'structured', 'neutral', 'conversational', 'collaborative']

# Dimension 3: Specificity bins (keyword density)
SPECIFICITY_BINS = ['very-general', 'general', 'moderate', 'specific', 'very-specific']
SPECIFICITY_THRESHOLDS = [0.02, 0.04, 0.07, 0.12]  # domain keyword density

# Domain keywords for specificity measurement
DOMAIN_KEYWORDS = {
    'code review': [
        'security', 'performance', 'bug', 'vulnerability', 'pattern', 'injection',
        'XSS', 'CSRF', 'race condition', 'null', 'memory', 'leak', 'overflow',
        'authentication', 'authorization', 'sanitize', 'validate', 'boundary',
        'error handling', 'exception', 'stack trace', 'deadlock', 'thread',
        'SQL', 'API', 'endpoint', 'input validation', 'output encoding',
    ],
    'research': [
        'source', 'citation', 'evidence', 'methodology', 'analysis', 'synthesis',
        'hypothesis', 'data', 'peer-reviewed', 'primary', 'secondary', 'bias',
        'statistical', 'sample', 'control', 'variable', 'correlation', 'causation',
    ],
    'summarization': [
        'key points', 'main ideas', 'concise', 'overview', 'highlight', 'essential',
        'core', 'takeaway', 'abstract', 'distill', 'compress', 'salient',
    ],
    'generation': [
        'creative', 'original', 'coherent', 'consistent', 'tone', 'style',
        'audience', 'engaging', 'narrative', 'structure', 'voice', 'persona',
    ],
}

# LLM prompt templates for targeted variation
VARIATION_CONCISE = """Rewrite this prompt to be MORE CONCISE while maintaining its quality and intent.
Target: under 50 words. Cut verbose phrases, merge redundant instructions.

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

VARIATION_DETAILED = """Rewrite this prompt to be MORE DETAILED and comprehensive.
Target: 300+ words. Add specific criteria, examples, edge cases, output format.

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

VARIATION_DIRECTIVE = """Rewrite this prompt in a DIRECTIVE style. Use imperative verbs,
clear commands, numbered steps. Remove hedging language ("could", "might", "consider").

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

VARIATION_COLLABORATIVE = """Rewrite this prompt in a COLLABORATIVE style. Use inclusive
language ("let's", "we should", "together"), ask guiding questions, suggest options.

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

VARIATION_SPECIFIC = """Rewrite this prompt to be MORE DOMAIN-SPECIFIC. Add technical
terminology, specific tool names, concrete thresholds, exact metrics to check.

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

VARIATION_GENERAL = """Rewrite this prompt to be MORE GENERAL and broadly applicable.
Remove domain jargon, use universal language, make it work for any codebase/context.

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

VARIATION_STRUCTURED = """Rewrite this prompt in a STRUCTURED style. Use markdown headings,
numbered steps, bullet points, and clear sections. Organize into: Context, Instructions, Output Format.

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

VARIATION_NEUTRAL = """Rewrite this prompt in a NEUTRAL, balanced style. Avoid both
commanding language and overly collaborative phrasing. Use declarative statements.

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

VARIATION_CONVERSATIONAL = """Rewrite this prompt in a CONVERSATIONAL style. Use natural
language, explain the reasoning, add context for why each instruction matters.

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

VARIATION_RANDOM = """Create an improved variant of this prompt. Make one significant
structural change (reorder sections, add a new constraint, change the framing).

Original prompt:
{prompt}

Respond with ONLY the rewritten prompt, no explanation."""

STYLE_CLASSIFICATION_PROMPT = """Classify the communication style of this prompt into
exactly ONE of these categories:

- directive: Uses imperative commands, numbered steps, clear mandates
- structured: Uses bullet points, sections, formal organization
- neutral: Balanced, neither commanding nor collaborative
- conversational: Uses natural language, informal tone, explanations
- collaborative: Uses inclusive language ("let's", "we"), asks questions, suggests options

Prompt to classify:
{prompt}

Respond with ONLY the category name (one word), nothing else."""

SEED_PROMPT = """You are an expert prompt engineer. Generate a high-quality prompt for
the following task.

Task type: {task_type}
Task description: {task_description}
Style hint: {style_hint}
Target length: {length_hint}

Requirements:
- Clear, specific, and actionable
- Include relevant constraints and quality criteria
- Use formatting appropriate to the requested style
- Match the target length approximately

Respond with ONLY the prompt, no explanation or commentary."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BehaviorDescriptor:
    """Describes where an individual sits in the behavior space."""
    length_bin: str       # e.g. 'short', 'medium'
    style_bin: str        # e.g. 'directive', 'collaborative'
    specificity_bin: str  # e.g. 'general', 'specific'

    # Raw values for more detail
    word_count: int = 0
    keyword_density: float = 0.0

    def cell_key(self) -> Tuple[str, str, str]:
        """Return the grid cell coordinates as a tuple."""
        return (self.length_bin, self.style_bin, self.specificity_bin)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'BehaviorDescriptor':
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class MAPElitesIndividual:
    """An individual in the MAP-Elites archive."""
    prompt_text: str
    fitness: float = 0.0
    behavior: Optional[BehaviorDescriptor] = None
    generation: int = 0
    parent_id: str = ''
    operator: str = 'seed'
    model_used: str = ''
    individual_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    weaknesses: str = ''
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        d = asdict(self)
        if self.behavior:
            d['behavior'] = self.behavior.to_dict()
        d['cell_key'] = list(self.behavior.cell_key()) if self.behavior else None
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> 'MAPElitesIndividual':
        behavior_data = data.pop('behavior', None)
        data.pop('cell_key', None)
        ind = cls(**{k: v for k, v in data.items()
                     if k in cls.__dataclass_fields__})
        if behavior_data and isinstance(behavior_data, dict):
            ind.behavior = BehaviorDescriptor.from_dict(behavior_data)
        return ind

    def prompt_hash(self) -> str:
        return hashlib.sha256(self.prompt_text.strip().encode()).hexdigest()[:16]

    def __repr__(self) -> str:
        cell = self.behavior.cell_key() if self.behavior else ('?', '?', '?')
        snippet = self.prompt_text[:50].replace('\n', ' ')
        return (f"Individual(id={self.individual_id}, fitness={self.fitness:.3f}, "
                f"cell={cell}, op={self.operator}, "
                f"prompt=\"{snippet}...\")")


# ---------------------------------------------------------------------------
# OpenRouter LLM client (reuses pattern from llm_guided_evolution.py)
# ---------------------------------------------------------------------------

class LLMClient:
    """Calls free OpenRouter models for variation operators."""

    def __init__(self):
        self._api_key: Optional[str] = None
        self._model_index = 0
        self._call_count = 0
        self._error_count = 0

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        try:
            resp = requests.get(
                f'{API_BASE}/secrets/OPENROUTER_API_KEY', timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            self._api_key = data.get('value', data.get('secret', ''))
            if not self._api_key:
                raise ValueError('Empty API key from secrets endpoint')
            return self._api_key
        except Exception as e:
            logger.error('Failed to fetch OpenRouter API key: %s', e)
            raise

    def _next_model(self) -> str:
        model = VARIATION_MODELS[self._model_index % len(VARIATION_MODELS)]
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

        raise RuntimeError('LLM call exhausted retries')

    @property
    def stats(self) -> Dict:
        return {
            'total_calls': self._call_count,
            'total_errors': self._error_count,
            'error_rate': (self._error_count / max(1, self._call_count + self._error_count)),
        }


# ---------------------------------------------------------------------------
# Behavior Characterization
# ---------------------------------------------------------------------------

class BehaviorCharacterizer:
    """Measures behavioral dimensions of a prompt."""

    def __init__(self, task_type: str = 'code review', llm: Optional[LLMClient] = None):
        self.task_type = task_type.lower()
        self.llm = llm
        self._style_cache: Dict[str, str] = {}
        self._keywords = DOMAIN_KEYWORDS.get(self.task_type, [])
        # Fallback: merge all domain keywords if task type not recognized
        if not self._keywords:
            for kws in DOMAIN_KEYWORDS.values():
                self._keywords.extend(kws)
            self._keywords = list(set(self._keywords))

    def characterize(self, prompt_text: str) -> BehaviorDescriptor:
        """Compute all behavior dimensions for a prompt."""
        length_bin, word_count = self._classify_length(prompt_text)
        style_bin = self._classify_style(prompt_text)
        specificity_bin, keyword_density = self._classify_specificity(prompt_text)

        return BehaviorDescriptor(
            length_bin=length_bin,
            style_bin=style_bin,
            specificity_bin=specificity_bin,
            word_count=word_count,
            keyword_density=round(keyword_density, 4),
        )

    def _classify_length(self, text: str) -> Tuple[str, int]:
        """Classify prompt length into bins."""
        word_count = len(text.split())
        for i, threshold in enumerate(LENGTH_THRESHOLDS):
            if word_count < threshold:
                return LENGTH_BINS[i], word_count
        return LENGTH_BINS[-1], word_count

    def _classify_style(self, text: str) -> str:
        """Classify prompt style via heuristics (with optional LLM fallback)."""
        text_lower = text.lower()

        # Heuristic scoring for each style
        scores = {style: 0.0 for style in STYLE_BINS}

        # Directive indicators
        imperative_patterns = [
            r'\b(do|check|verify|ensure|find|list|report|analyze|review|identify)\b',
            r'\b(must|shall|required)\b',
            r'^\d+\.', r'^- ',
        ]
        for p in imperative_patterns:
            scores['directive'] += len(re.findall(p, text_lower, re.MULTILINE)) * 0.3

        # Structured indicators
        structured_patterns = [
            r'^\s*[-*]\s', r'^\s*\d+[.)]\s', r'^#{1,3}\s',
            r'\b(section|phase|step|stage|part)\b',
        ]
        for p in structured_patterns:
            scores['structured'] += len(re.findall(p, text_lower, re.MULTILINE)) * 0.4

        # Collaborative indicators
        collaborative_patterns = [
            r"\b(let's|let us|we should|we can|together|consider)\b",
            r'\b(could you|would you|please|might we)\b',
            r'\b(what do you think|your thoughts|suggestions)\b',
        ]
        for p in collaborative_patterns:
            scores['collaborative'] += len(re.findall(p, text_lower)) * 0.5

        # Conversational indicators
        conversational_patterns = [
            r'\b(you know|basically|essentially|think of it|imagine)\b',
            r'\b(right\?|okay|so,|well,|honestly)\b',
            r"[!]{2,}",
        ]
        for p in conversational_patterns:
            scores['conversational'] += len(re.findall(p, text_lower)) * 0.4

        # Neutral baseline
        scores['neutral'] = 1.0

        best_style = max(scores, key=scores.get)

        # If heuristics are inconclusive (top two within 0.5) and LLM available, ask LLM
        sorted_scores = sorted(scores.values(), reverse=True)
        if (sorted_scores[0] - sorted_scores[1] < 0.5 and
                self.llm and best_style == 'neutral'):
            llm_style = self._classify_style_llm(text)
            if llm_style in STYLE_BINS:
                return llm_style

        return best_style

    def _classify_style_llm(self, text: str) -> str:
        """Classify style using LLM (slow, used as fallback)."""
        h = hashlib.md5(text[:200].encode()).hexdigest()[:12]
        if h in self._style_cache:
            return self._style_cache[h]

        try:
            prompt = STYLE_CLASSIFICATION_PROMPT.format(prompt=text[:500])
            response, _ = self.llm.call(
                prompt, model=STYLE_CLASSIFIER_MODEL,
                max_tokens=20, temperature=0.1
            )
            style = response.strip().lower().split()[0] if response.strip() else 'neutral'
            # Validate
            if style not in STYLE_BINS:
                # Fuzzy match
                for bin_name in STYLE_BINS:
                    if bin_name in style or style in bin_name:
                        style = bin_name
                        break
                else:
                    style = 'neutral'
            self._style_cache[h] = style
            return style
        except Exception as e:
            logger.debug('LLM style classification failed: %s', e)
            return 'neutral'

    def _classify_specificity(self, text: str) -> Tuple[str, float]:
        """Classify specificity via domain keyword density."""
        text_lower = text.lower()
        words = text_lower.split()
        if not words:
            return SPECIFICITY_BINS[0], 0.0

        keyword_hits = sum(
            1 for kw in self._keywords if kw.lower() in text_lower
        )
        density = keyword_hits / len(words)

        for i, threshold in enumerate(SPECIFICITY_THRESHOLDS):
            if density < threshold:
                return SPECIFICITY_BINS[i], density
        return SPECIFICITY_BINS[-1], density


# ---------------------------------------------------------------------------
# Fitness Evaluation (reuses pattern from llm_guided_evolution.py)
# ---------------------------------------------------------------------------

class FitnessEvaluator:
    """Evaluate prompt fitness via structural quality heuristics."""

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

    TASK_KEYWORDS = {
        'code review': [
            'security', 'performance', 'maintainability', 'bug', 'vulnerability',
            'pattern', 'anti-pattern', 'best practice', 'code smell',
            'error handling', 'edge case', 'race condition', 'injection',
        ],
        'research': [
            'source', 'citation', 'evidence', 'finding', 'methodology',
            'analysis', 'comparison', 'synthesis', 'conclusion', 'hypothesis',
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

    def evaluate(self, individual: MAPElitesIndividual) -> float:
        text = individual.prompt_text.lower()
        score = 0.0
        weaknesses = []

        # 1. Structural quality signals (0.0 - 0.70)
        for signal_name, config in self.QUALITY_SIGNALS.items():
            matches = sum(1 for kw in config['keywords'] if kw in text)
            if matches > 0:
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
            if 100 <= word_count <= 300:
                length_score = 0.10
            elif word_count < 100:
                length_score = 0.05
                weaknesses.append('prompt too short')
            else:
                length_score = 0.10
        else:
            length_score = 0.02
            if word_count < 50:
                weaknesses.append('prompt far too short')
            else:
                weaknesses.append('prompt too long')
        score += length_score

        # 4. Specificity bonus (0.0 - 0.05)
        digit_count = sum(1 for c in text if c.isdigit())
        if digit_count >= 2:
            score += 0.05
        elif digit_count >= 1:
            score += 0.02
        else:
            weaknesses.append('lacks specific numbers/thresholds')

        individual.weaknesses = '; '.join(weaknesses) if weaknesses else 'none identified'
        fitness = max(0.0, min(1.0, score))
        individual.fitness = round(fitness, 4)
        return fitness


# ---------------------------------------------------------------------------
# MAP-Elites Archive
# ---------------------------------------------------------------------------

class MAPElitesArchive:
    """Thread-safe sparse grid archive indexed by behavior cell coordinates.

    Each cell holds the single best-performing individual for that behavior
    niche. New individuals replace existing ones if they have higher or equal
    fitness (equal-fitness replacement preserves diversity by allowing newer
    variants to enter).
    """

    def __init__(self, dimension_names: List[str]):
        self.dimension_names = dimension_names
        self.grid: Dict[Tuple, MAPElitesIndividual] = {}
        self._lock = threading.Lock()
        self._additions = 0
        self._replacements = 0
        self._rejections = 0

    def add(self, individual: MAPElitesIndividual) -> bool:
        """Try to place an individual in the archive (thread-safe).

        Returns True if the individual was added (new cell or >= fitness).
        Equal-fitness individuals replace existing ones to encourage diversity.
        """
        if individual.behavior is None:
            return False

        cell = individual.behavior.cell_key()

        with self._lock:
            if cell not in self.grid:
                self.grid[cell] = individual
                self._additions += 1
                return True
            elif individual.fitness >= self.grid[cell].fitness:
                self.grid[cell] = individual
                self._replacements += 1
                return True
            else:
                self._rejections += 1
                return False

    def sample_random(self) -> Optional[MAPElitesIndividual]:
        """Select a random individual from the archive (thread-safe)."""
        with self._lock:
            if not self.grid:
                return None
            return random.choice(list(self.grid.values()))

    def sample_uniform_random(self, n: int = 1) -> List[MAPElitesIndividual]:
        """Sample n random individuals (with replacement if n > archive size)."""
        with self._lock:
            if not self.grid:
                return []
            values = list(self.grid.values())
        return [random.choice(values) for _ in range(n)]

    def get_cell(self, cell_key: Tuple) -> Optional[MAPElitesIndividual]:
        """Get the individual in a specific cell."""
        with self._lock:
            return self.grid.get(cell_key)

    def get_empty_cells(self) -> List[Tuple]:
        """Return all possible cell keys that are currently empty."""
        with self._lock:
            occupied = set(self.grid.keys())
        return [
            (lb, sb, sp)
            for lb in LENGTH_BINS
            for sb in STYLE_BINS
            for sp in SPECIFICITY_BINS
            if (lb, sb, sp) not in occupied
        ]

    @property
    def total_cells(self) -> int:
        return len(LENGTH_BINS) * len(STYLE_BINS) * len(SPECIFICITY_BINS)

    @property
    def filled_cells(self) -> int:
        with self._lock:
            return len(self.grid)

    @property
    def coverage(self) -> float:
        """Fraction of behavior space that has been explored."""
        return self.filled_cells / self.total_cells if self.total_cells > 0 else 0.0

    @property
    def qd_score(self) -> float:
        """Quality-Diversity score: sum of all elite fitnesses in the archive.

        Standard MAP-Elites metric that captures both quality and coverage.
        Higher QD-score = more cells filled with higher-fitness individuals.
        """
        with self._lock:
            return sum(ind.fitness for ind in self.grid.values())

    @property
    def stats(self) -> Dict:
        with self._lock:
            fitnesses = [ind.fitness for ind in self.grid.values()]
            filled = len(self.grid)
        total = self.total_cells
        coverage = filled / total if total > 0 else 0.0
        return {
            'total_cells': total,
            'filled_cells': filled,
            'coverage': round(coverage, 4),
            'qd_score': round(sum(fitnesses), 4) if fitnesses else 0.0,
            'additions': self._additions,
            'replacements': self._replacements,
            'rejections': self._rejections,
            'best_fitness': max(fitnesses) if fitnesses else 0.0,
            'avg_fitness': sum(fitnesses) / len(fitnesses) if fitnesses else 0.0,
            'min_fitness': min(fitnesses) if fitnesses else 0.0,
        }

    def to_dict(self) -> Dict:
        """Serialize the full archive (thread-safe)."""
        with self._lock:
            cells = {
                str(k): v.to_dict() for k, v in self.grid.items()
            }
        return {
            'dimension_names': self.dimension_names,
            'cells': cells,
            'stats': self.stats,
        }

    def get_best_per_dimension(self) -> Dict[str, List[Dict]]:
        """Get the best individual along each dimension (thread-safe)."""
        with self._lock:
            grid_snapshot = dict(self.grid)

        result = {}

        # Best per length bin
        result['length'] = []
        for lb in LENGTH_BINS:
            candidates = [
                (k, v) for k, v in grid_snapshot.items() if k[0] == lb
            ]
            if candidates:
                best_key, best_ind = max(candidates, key=lambda x: x[1].fitness)
                result['length'].append({
                    'bin': lb,
                    'fitness': best_ind.fitness,
                    'cell_key': list(best_key),
                    'individual_id': best_ind.individual_id,
                })

        # Best per style bin
        result['style'] = []
        for sb in STYLE_BINS:
            candidates = [
                (k, v) for k, v in grid_snapshot.items() if k[1] == sb
            ]
            if candidates:
                best_key, best_ind = max(candidates, key=lambda x: x[1].fitness)
                result['style'].append({
                    'bin': sb,
                    'fitness': best_ind.fitness,
                    'cell_key': list(best_key),
                    'individual_id': best_ind.individual_id,
                })

        # Best per specificity bin
        result['specificity'] = []
        for sp in SPECIFICITY_BINS:
            candidates = [
                (k, v) for k, v in grid_snapshot.items() if k[2] == sp
            ]
            if candidates:
                best_key, best_ind = max(candidates, key=lambda x: x[1].fitness)
                result['specificity'].append({
                    'bin': sp,
                    'fitness': best_ind.fitness,
                    'cell_key': list(best_key),
                    'individual_id': best_ind.individual_id,
                })

        return result


# ---------------------------------------------------------------------------
# MAP-Elites Engine
# ---------------------------------------------------------------------------

class MAPElitesEngine:
    """Quality-diversity optimization via the MAP-Elites algorithm.

    Instead of converging to a single best prompt, maintains an archive of
    diverse high-quality prompts across the behavior space.
    """

    def __init__(
        self,
        task_type: str = 'code review',
        task_description: str = '',
        initial_population: int = 50,
        dimensions: Optional[List[str]] = None,
        seed: Optional[int] = None,
    ):
        self.task_type = task_type
        self.task_description = task_description or f'Prompt for {task_type}'
        self.initial_population = initial_population
        self.dimensions = dimensions or ['length', 'style', 'specificity']

        # Reproducibility: set random seed if provided
        self.seed = seed
        if seed is not None:
            random.seed(seed)

        self.llm = LLMClient()
        self.evaluator = FitnessEvaluator(task_type)
        self.characterizer = BehaviorCharacterizer(task_type, self.llm)
        self.archive = MAPElitesArchive(self.dimensions)

        self.iteration = 0
        self.total_evaluations = 0
        self.iteration_stats: List[Dict] = []
        self._seen_hashes: set = set()

        self.run_id = f'me-{datetime.now().strftime("%Y%m%dT%H%M%S")}-{uuid.uuid4().hex[:6]}'
        self._stopped = threading.Event()
        self.started_at = datetime.now().isoformat()

    @property
    def stopped(self) -> bool:
        """Thread-safe check of stop flag."""
        return self._stopped.is_set()

    @stopped.setter
    def stopped(self, value: bool):
        """Thread-safe set of stop flag."""
        if value:
            self._stopped.set()
        else:
            self._stopped.clear()

    # -- Initialization ----------------------------------------------------

    def initialize(self) -> int:
        """Generate initial random prompts to seed the archive.

        Returns the number of individuals placed in the archive.
        """
        logger.info(
            'Initializing MAP-Elites: %d initial prompts for task: %s',
            self.initial_population, self.task_type,
        )

        placed = 0
        attempts = 0
        max_attempts = self.initial_population * 3

        # Generate diverse seeds by varying style/length hints
        style_hints = STYLE_BINS
        length_hints = [
            'very short (under 50 words)',
            'short (50-100 words)',
            'medium (100-200 words)',
            'long (200-400 words)',
            'very long (400+ words)',
        ]

        while placed < self.initial_population and attempts < max_attempts:
            if self.stopped:
                break

            attempts += 1
            style_hint = random.choice(style_hints)
            length_hint = random.choice(length_hints)

            try:
                prompt = SEED_PROMPT.format(
                    task_type=self.task_type,
                    task_description=self.task_description,
                    style_hint=style_hint,
                    length_hint=length_hint,
                )
                text, model = self.llm.call(prompt, temperature=1.0)

                individual = MAPElitesIndividual(
                    prompt_text=text,
                    generation=0,
                    operator='seed',
                    model_used=model,
                )

                # Dedup check
                h = individual.prompt_hash()
                if h in self._seen_hashes:
                    continue
                self._seen_hashes.add(h)

                # Evaluate fitness and characterize behavior
                self.evaluator.evaluate(individual)
                individual.behavior = self.characterizer.characterize(text)
                self.total_evaluations += 1

                # Try to place in archive
                if self.archive.add(individual):
                    placed += 1
                    logger.info(
                        'Seed %d/%d: fitness=%.3f cell=%s model=%s',
                        placed, self.initial_population,
                        individual.fitness,
                        individual.behavior.cell_key(),
                        model,
                    )

            except Exception as e:
                logger.warning('Seed generation failed: %s', e)
                time.sleep(2)

        self._record_iteration_stats()
        logger.info(
            'Initialization complete: %d placed, coverage=%.1f%%',
            placed, self.archive.coverage * 100,
        )
        return placed

    # -- Variation operators -----------------------------------------------

    def _select_variation_prompt(self, parent: MAPElitesIndividual) -> Tuple[str, str]:
        """Choose a variation operator based on archive coverage gaps.

        Returns (variation_prompt, operator_name).
        Prioritizes variation toward empty cells to improve coverage.
        """
        empty_cells = self.archive.get_empty_cells()

        if empty_cells and random.random() < 0.6:
            # Target a random empty cell
            target = random.choice(empty_cells)
            target_length, target_style, target_specificity = target

            # Choose the variation that best targets this cell
            # Map target dimensions to variation templates
            style_templates = {
                'directive': (VARIATION_DIRECTIVE, 'targeted-directive'),
                'structured': (VARIATION_STRUCTURED, 'targeted-structured'),
                'neutral': (VARIATION_NEUTRAL, 'targeted-neutral'),
                'conversational': (VARIATION_CONVERSATIONAL, 'targeted-conversational'),
                'collaborative': (VARIATION_COLLABORATIVE, 'targeted-collaborative'),
            }
            specificity_templates = {
                'very-specific': (VARIATION_SPECIFIC, 'targeted-specific'),
                'specific': (VARIATION_SPECIFIC, 'targeted-specific'),
                'moderate': (VARIATION_RANDOM, 'targeted-moderate'),
                'general': (VARIATION_GENERAL, 'targeted-general'),
                'very-general': (VARIATION_GENERAL, 'targeted-general'),
            }

            # Prioritize the dimension that differs most from parent
            if target_length in ('very-short', 'short') and parent.behavior and \
               parent.behavior.length_bin in ('long', 'very-long', 'medium'):
                return VARIATION_CONCISE.format(prompt=parent.prompt_text), 'targeted-concise'
            elif target_length in ('long', 'very-long') and parent.behavior and \
                 parent.behavior.length_bin in ('very-short', 'short', 'medium'):
                return VARIATION_DETAILED.format(prompt=parent.prompt_text), 'targeted-detailed'
            elif target_style in style_templates and parent.behavior and \
                 parent.behavior.style_bin != target_style:
                tmpl, name = style_templates[target_style]
                return tmpl.format(prompt=parent.prompt_text), name
            elif target_specificity in specificity_templates:
                tmpl, name = specificity_templates[target_specificity]
                return tmpl.format(prompt=parent.prompt_text), name

        # Random variation (exploration)
        variations = [
            (VARIATION_CONCISE, 'random-concise'),
            (VARIATION_DETAILED, 'random-detailed'),
            (VARIATION_DIRECTIVE, 'random-directive'),
            (VARIATION_STRUCTURED, 'random-structured'),
            (VARIATION_NEUTRAL, 'random-neutral'),
            (VARIATION_CONVERSATIONAL, 'random-conversational'),
            (VARIATION_COLLABORATIVE, 'random-collaborative'),
            (VARIATION_SPECIFIC, 'random-specific'),
            (VARIATION_GENERAL, 'random-general'),
            (VARIATION_RANDOM, 'random-structural'),
        ]
        template, op_name = random.choice(variations)
        return template.format(prompt=parent.prompt_text), op_name

    def _create_variant(self, parent: MAPElitesIndividual) -> Optional[MAPElitesIndividual]:
        """Generate a variant of a parent via LLM-guided variation."""
        try:
            variation_prompt, op_name = self._select_variation_prompt(parent)
            text, model = self.llm.call(variation_prompt, temperature=0.8)

            child = MAPElitesIndividual(
                prompt_text=text,
                generation=self.iteration + 1,
                parent_id=parent.individual_id,
                operator=op_name,
                model_used=model,
            )

            # Dedup check
            h = child.prompt_hash()
            if h in self._seen_hashes:
                return None
            self._seen_hashes.add(h)

            # Evaluate and characterize
            self.evaluator.evaluate(child)
            child.behavior = self.characterizer.characterize(text)
            self.total_evaluations += 1

            return child

        except Exception as e:
            logger.warning('Variant generation failed: %s', e)
            return None

    # -- Evolution loop ----------------------------------------------------

    def run_iteration(self, batch_size: int = 10) -> Dict:
        """Run one MAP-Elites iteration: sample, vary, evaluate, archive.

        Args:
            batch_size: Number of variants to generate per iteration.

        Returns:
            Iteration statistics.
        """
        if self.stopped:
            return {'stopped': True}

        placed = 0
        improved = 0
        failed = 0
        operators_used = {}

        for _ in range(batch_size):
            if self.stopped:
                break

            # Sample parent from archive
            parent = self.archive.sample_random()
            if parent is None:
                logger.warning('Archive is empty, cannot sample parent')
                break

            # Generate variant
            child = self._create_variant(parent)
            if child is None:
                failed += 1
                continue

            operators_used[child.operator] = operators_used.get(child.operator, 0) + 1

            # Try to place in archive
            cell_key = child.behavior.cell_key()
            was_occupied = cell_key in self.archive.grid
            if self.archive.add(child):
                placed += 1
                if was_occupied:
                    improved += 1

            # Rate limiting
            time.sleep(0.5)

        self.iteration += 1
        stats = self._record_iteration_stats()
        stats['placed'] = placed
        stats['improved'] = improved
        stats['failed'] = failed
        stats['operators'] = operators_used

        return stats

    def evolve(self, iterations: int, batch_size: int = 10) -> Dict:
        """Run MAP-Elites for N iterations.

        Args:
            iterations: Number of iterations.
            batch_size: Variants per iteration.

        Returns:
            Final archive stats.
        """
        logger.info(
            'Starting MAP-Elites: %d iterations, batch=%d, task=%s',
            iterations, batch_size, self.task_type,
        )

        # Initialize if archive is empty
        if self.archive.filled_cells == 0:
            self.initialize()

        for i in range(iterations):
            if self.stopped:
                logger.info('MAP-Elites stopped at iteration %d', i)
                break

            stats = self.run_iteration(batch_size)

            logger.info(
                'Iter %d: coverage=%.1f%% (%d/%d) '
                'best=%.3f avg=%.3f placed=%d improved=%d failed=%d',
                self.iteration,
                self.archive.coverage * 100,
                self.archive.filled_cells,
                self.archive.total_cells,
                stats.get('best_fitness', 0),
                stats.get('avg_fitness', 0),
                stats.get('placed', 0),
                stats.get('improved', 0),
                stats.get('failed', 0),
            )

            # Store lineage periodically
            if i % 5 == 0 or i == iterations - 1:
                self._store_lineage()

        # Final storage
        self._store_lineage()
        self._store_results_via_api()

        final_stats = self.archive.stats
        logger.info(
            'MAP-Elites complete: %d iterations, coverage=%.1f%%, best=%.3f',
            self.iteration, self.archive.coverage * 100,
            final_stats['best_fitness'],
        )

        return final_stats

    # -- Internal helpers --------------------------------------------------

    def _record_iteration_stats(self) -> Dict:
        archive_stats = self.archive.stats

        stats = {
            'iteration': self.iteration,
            'coverage': archive_stats['coverage'],
            'filled_cells': archive_stats['filled_cells'],
            'total_cells': archive_stats['total_cells'],
            'qd_score': archive_stats['qd_score'],
            'best_fitness': archive_stats['best_fitness'],
            'avg_fitness': archive_stats['avg_fitness'],
            'min_fitness': archive_stats['min_fitness'],
            'total_evaluations': self.total_evaluations,
            'timestamp': datetime.now().isoformat(),
        }
        self.iteration_stats.append(stats)
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
                'started_at': self.started_at,
                'dimensions': self.dimensions,
                'iterations': {},
            })

            iter_key = str(self.iteration)
            run_data['iterations'][iter_key] = {
                'timestamp': datetime.now().isoformat(),
                'archive_stats': self.archive.stats,
                'iteration_stats': self.iteration_stats[-1] if self.iteration_stats else {},
            }
            run_data['archive'] = self.archive.to_dict()
            run_data['llm_stats'] = self.llm.stats

            with open(LINEAGE_PATH, 'w') as f:
                json.dump(lineage_data, f, indent=2)

            # REST API convergence tracking
            if self.iteration_stats:
                latest = self.iteration_stats[-1]
                try:
                    requests.post(f'{API_BASE}/ga/convergence', json={
                        'use_case': f'map-elites-{self.task_type}',
                        'generation': self.iteration,
                        'best_fitness': latest['best_fitness'],
                        'avg_fitness': latest['avg_fitness'],
                        'island_id': 0,
                        'diversity': latest['coverage'],
                    }, timeout=10)
                except requests.exceptions.RequestException as e:
                    logger.debug('Convergence POST failed: %s', e)

        except Exception as e:
            logger.warning('Failed to store lineage: %s', e)

    def _store_results_via_api(self):
        """Store final results via REST API."""
        archive_stats = self.archive.stats
        if archive_stats['filled_cells'] == 0:
            return

        # Find overall best
        best = max(self.archive.grid.values(), key=lambda ind: ind.fitness)

        stored_count = 0
        error_count = 0

        # Store best solution
        try:
            resp = requests.post(f'{API_BASE}/ga/best-solutions', json={
                'use_case': f'map-elites-{self.task_type}',
                'chromosome': json.dumps({
                    'prompt_text': best.prompt_text,
                    'operator': best.operator,
                    'model_used': best.model_used,
                    'behavior': best.behavior.to_dict() if best.behavior else {},
                    'cell_key': list(best.behavior.cell_key()) if best.behavior else [],
                }),
                'fitness': float(best.fitness),
                'fitness_details': json.dumps({
                    'best_fitness': float(best.fitness),
                    'avg_fitness': float(archive_stats['avg_fitness']),
                    'coverage': float(archive_stats['coverage']),
                    'filled_cells': archive_stats['filled_cells'],
                    'total_cells': archive_stats['total_cells'],
                    'total_iterations': self.iteration,
                    'total_evaluations': self.total_evaluations,
                    'llm_calls': self.llm.stats['total_calls'],
                    'llm_errors': self.llm.stats['total_errors'],
                }),
                'generation_found': best.generation,
                'notes': (
                    f'MAP-Elites ({self.task_type}): '
                    f'{self.iteration} iterations, '
                    f'coverage={archive_stats["coverage"]:.1%}, '
                    f'fitness={best.fitness:.3f}, '
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
                'use_case': f'map-elites-{self.task_type}',
                'strategy': 'map_elites_quality_diversity',
                'avg_reward': float(archive_stats['avg_fitness']),
                'total_reward': float(archive_stats['avg_fitness'] * archive_stats['filled_cells']),
                'successes': archive_stats['filled_cells'],
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

        logger.info('API storage: %d stored, %d errors', stored_count, error_count)

    # -- Public accessors --------------------------------------------------

    def get_status(self) -> Dict:
        return {
            'run_id': self.run_id,
            'task_type': self.task_type,
            'dimensions': self.dimensions,
            'iteration': self.iteration,
            'total_evaluations': self.total_evaluations,
            'seed': self.seed,
            'archive': self.archive.stats,
            'llm_stats': self.llm.stats,
            'stopped': self.stopped,
            'started_at': self.started_at,
        }

    def get_archive(self) -> Dict:
        return self.archive.to_dict()

    def get_best(self) -> Optional[Dict]:
        with self.archive._lock:
            if not self.archive.grid:
                return None
            best = max(self.archive.grid.values(), key=lambda ind: ind.fitness)
            return best.to_dict()

    def get_best_per_dimension(self) -> Dict:
        return self.archive.get_best_per_dimension()


# ---------------------------------------------------------------------------
# Archive visualization (text-based)
# ---------------------------------------------------------------------------

def visualize_archive(archive: MAPElitesArchive, dims: List[str] = None):
    """Print a text-based heatmap of the archive.

    Shows a 2D slice (length x style) for each specificity bin.
    """
    dims = dims or ['length', 'style', 'specificity']

    print('\nMAP-Elites Archive Heatmap')
    print('=' * 60)
    print(f'Coverage: {archive.filled_cells}/{archive.total_cells} '
          f'({archive.coverage:.1%})')
    print(f'QD-Score:     {archive.qd_score:.3f}')
    print(f'Best fitness: {archive.stats["best_fitness"]:.3f}')
    print(f'Avg fitness:  {archive.stats["avg_fitness"]:.3f}')
    print()

    for sp_bin in SPECIFICITY_BINS:
        print(f'--- Specificity: {sp_bin} ---')
        # Header
        header = f'{"Length":<12}'
        for s_bin in STYLE_BINS:
            header += f'{s_bin:>14}'
        print(header)

        for l_bin in LENGTH_BINS:
            row = f'{l_bin:<12}'
            for s_bin in STYLE_BINS:
                cell_key = (l_bin, s_bin, sp_bin)
                ind = archive.get_cell(cell_key)
                if ind:
                    row += f'{ind.fitness:>13.3f} '
                else:
                    row += f'{"---":>14}'
            print(row)
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='MAP-Elites Quality-Diversity Prompt Evolution',
    )
    parser.add_argument(
        '--task', type=str, default='code review',
        help='Task type (default: "code review")',
    )
    parser.add_argument(
        '--description', type=str, default='',
        help='Detailed task description',
    )
    parser.add_argument(
        '--iterations', type=int, default=20,
        help='Number of MAP-Elites iterations (default: 20)',
    )
    parser.add_argument(
        '--batch-size', type=int, default=10,
        help='Variants per iteration (default: 10)',
    )
    parser.add_argument(
        '--initial-population', type=int, default=50,
        help='Initial seed population size (default: 50)',
    )
    parser.add_argument(
        '--dims', type=str, default='length,style,specificity',
        help='Behavior dimensions (comma-separated, default: length,style,specificity)',
    )
    parser.add_argument(
        '--seed', type=int, default=None,
        help='Random seed for reproducibility (default: none)',
    )
    parser.add_argument(
        '--show-archive', action='store_true',
        help='Show archive heatmap only (load from lineage file)',
    )
    parser.add_argument(
        '--output', type=str, default='',
        help='Output file for results JSON',
    )
    args = parser.parse_args()

    dimensions = [d.strip() for d in args.dims.split(',')]

    # Show archive mode
    if args.show_archive:
        if not LINEAGE_PATH.exists():
            print('No lineage file found. Run MAP-Elites first.')
            return

        with open(LINEAGE_PATH, 'r') as f:
            data = json.load(f)

        runs = data.get('runs', {})
        if not runs:
            print('No runs found in lineage file.')
            return

        # Show the most recent run
        latest_run_id = max(runs.keys(), key=lambda k: runs[k].get('started_at', ''))
        run_data = runs[latest_run_id]
        archive_data = run_data.get('archive', {})

        print(f'Run: {latest_run_id}')
        print(f'Task: {run_data.get("task_type", "unknown")}')
        print(f'Started: {run_data.get("started_at", "unknown")}')

        # Reconstruct archive for visualization
        archive = MAPElitesArchive(dimensions)
        cells = archive_data.get('cells', {})
        for cell_str, ind_data in cells.items():
            ind = MAPElitesIndividual.from_dict(ind_data)
            archive.grid[tuple(ast.literal_eval(cell_str))] = ind

        visualize_archive(archive, dimensions)
        return

    # Evolution mode
    print('=' * 70)
    print('MAP-ELITES: Quality-Diversity Prompt Evolution')
    print('=' * 70)
    print(f'Task:              {args.task}')
    print(f'Dimensions:        {dimensions}')
    print(f'Initial pop:       {args.initial_population}')
    print(f'Iterations:        {args.iterations}')
    print(f'Batch size:        {args.batch_size}')
    print(f'Total cells:       {len(LENGTH_BINS) * len(STYLE_BINS) * len(SPECIFICITY_BINS)}')
    print('=' * 70)

    engine = MAPElitesEngine(
        task_type=args.task,
        task_description=args.description,
        initial_population=args.initial_population,
        dimensions=dimensions,
        seed=args.seed,
    )

    start_time = time.time()
    final_stats = engine.evolve(args.iterations, args.batch_size)
    elapsed = time.time() - start_time

    # Results
    print('\n' + '=' * 70)
    print('RESULTS')
    print('=' * 70)

    print(f'\nArchive Coverage: {final_stats["filled_cells"]}/{final_stats["total_cells"]} '
          f'({final_stats["coverage"]:.1%})')
    print(f'QD-Score:         {final_stats["qd_score"]:.3f}')
    print(f'Best Fitness:     {final_stats["best_fitness"]:.3f}')
    print(f'Avg Fitness:      {final_stats["avg_fitness"]:.3f}')
    print(f'Min Fitness:      {final_stats["min_fitness"]:.3f}')

    best = engine.get_best()
    if best:
        print(f'\nBest Prompt (fitness={best["fitness"]:.3f}):')
        print('-' * 50)
        print(best['prompt_text'][:500])
        if len(best['prompt_text']) > 500:
            print('... (truncated)')
        print('-' * 50)
        print(f'Cell:     {best.get("cell_key", "unknown")}')
        print(f'Operator: {best["operator"]}')
        print(f'Model:    {best["model_used"]}')

    # Best per dimension
    per_dim = engine.get_best_per_dimension()
    print('\nBest per dimension:')
    for dim_name, entries in per_dim.items():
        print(f'\n  {dim_name}:')
        for entry in entries:
            print(f'    {entry["bin"]:<16} fitness={entry["fitness"]:.3f} '
                  f'cell={entry["cell_key"]}')

    # Visualize
    visualize_archive(engine.archive, dimensions)

    status = engine.get_status()
    print(f'\nRun Stats:')
    print(f'  Run ID:          {status["run_id"]}')
    print(f'  Iterations:      {status["iteration"]}')
    print(f'  Evaluations:     {status["total_evaluations"]}')
    print(f'  LLM calls:       {status["llm_stats"]["total_calls"]}')
    print(f'  LLM errors:      {status["llm_stats"]["total_errors"]}')
    print(f'  Elapsed:         {elapsed:.1f}s')

    # Convergence
    if engine.iteration_stats:
        print(f'\nConvergence:')
        for s in engine.iteration_stats:
            print(
                f'  Iter {s["iteration"]:3d}: '
                f'coverage={s["coverage"]:.3f} '
                f'qd={s.get("qd_score", 0):.3f} '
                f'best={s["best_fitness"]:.3f} '
                f'avg={s["avg_fitness"]:.3f} '
                f'filled={s["filled_cells"]}/{s["total_cells"]}'
            )

    # Save results
    output_file = args.output or (
        f'{Path(__file__).parent}/'
        f'map_elites_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )
    results = {
        'run_id': status['run_id'],
        'task_type': args.task,
        'dimensions': dimensions,
        'archive_stats': final_stats,
        'best_per_dimension': per_dim,
        'iteration_stats': engine.iteration_stats,
        'llm_stats': status['llm_stats'],
        'elapsed_seconds': elapsed,
        'timestamp': datetime.now().isoformat(),
        'config': {
            'initial_population': args.initial_population,
            'iterations': args.iterations,
            'batch_size': args.batch_size,
            'dimensions': dimensions,
        },
    }
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'\nResults saved to: {output_file}')

    return results


if __name__ == '__main__':
    main()
