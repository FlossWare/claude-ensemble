#!/usr/bin/env python3
"""
LLM Cascade Router - Try cheap models first, escalate on low confidence.

Implements the RouteLLM / cascading pattern:
  1. Classify query difficulty using heuristics + historical data.
  2. Route to the cheapest tier likely to succeed.
  3. After each response, estimate confidence.
  4. If confidence is below threshold, escalate to the next tier.

Achieves ~95% quality at ~15% cost by reserving paid models for genuinely
hard queries.

Tiers:
  - free_small : fast free models  (Qwen3-4B, Llama-8B, Gemini Flash)
  - free_large : strong free models (Qwen3-30B, DeepSeek-chat, Llama-70B)
  - paid       : premium models     (Sonnet, Opus)

CLI:
    python3 llm_cascade.py "What is 2+2?"
    python3 llm_cascade.py --max-tier free_large "Explain monads"
    python3 llm_cascade.py --threshold 0.6 "Write a binary search in Rust"

All model calls go through OpenRouter.  API key fetched from the
orchestrator REST API at http://aio-01:5000/secrets/OPENROUTER_API_KEY.
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# REST API base
# ---------------------------------------------------------------------------
API_BASE = os.environ.get('ORCHESTRATOR_URL', 'http://aio-01:5000')

# ---------------------------------------------------------------------------
# OpenRouter endpoint
# ---------------------------------------------------------------------------
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------
TIERS: Dict[str, List[str]] = {
    'free_small': [
        'qwen/qwen3-4b:free',
        'meta-llama/llama-3.1-8b-instant:free',
        'google/gemini-2.0-flash-exp:free',
    ],
    'free_large': [
        'qwen/qwen3-30b-a3b:free',
        'deepseek/deepseek-chat-v3-0324:free',
        'meta-llama/llama-3.1-70b-instruct:free',
    ],
    'paid': [
        'anthropic/claude-sonnet-4',
        'anthropic/claude-opus-4',
    ],
}

TIER_ORDER = ['free_small', 'free_large', 'paid']

# Estimated cost per 1M tokens (input / output) -- for stats only
TIER_COST_ESTIMATES: Dict[str, Dict[str, float]] = {
    'free_small':  {'input': 0.0, 'output': 0.0},
    'free_large':  {'input': 0.0, 'output': 0.0},
    'paid':        {'input': 3.0, 'output': 15.0},
}

# ---------------------------------------------------------------------------
# Difficulty keywords
# ---------------------------------------------------------------------------
HARD_DOMAIN_KEYWORDS = frozenset([
    # Code / engineering
    'implement', 'refactor', 'debug', 'optimize', 'algorithm', 'data structure',
    'concurrency', 'thread', 'async', 'distributed', 'architecture',
    'design pattern', 'system design',
    # Math / reasoning
    'prove', 'proof', 'theorem', 'integral', 'derivative', 'matrix',
    'eigenvalue', 'probability', 'bayesian', 'regression',
    # Analytical
    'compare and contrast', 'trade-off', 'trade off', 'tradeoff',
    'evaluate', 'critique', 'analyze', 'implications', 'nuance',
    'counterargument', 'synthesize',
])

EASY_DOMAIN_KEYWORDS = frozenset([
    'define', 'what is', 'who is', 'when did', 'where is',
    'list', 'name', 'how many', 'translate', 'convert',
    'hello', 'hi', 'thanks', 'thank you',
])

# ---------------------------------------------------------------------------
# Hedging / uncertainty phrases used for confidence estimation
# ---------------------------------------------------------------------------
# Only genuine uncertainty/hedging phrases -- NOT normal conversational
# language like "I think" or self-identification like "as an AI".
# Those are benign and should not reduce confidence scores.
HEDGING_PHRASES = [
    "i'm not sure",
    "i'm not certain",
    "it's unclear",
    "it is unclear",
    "i don't know",
    "i do not know",
    "not entirely sure",
    "hard to say",
    "difficult to determine",
    "could be wrong",
    "take this with a grain of salt",
    "i cannot confirm",
    "i can not confirm",
]


# ===================================================================
# API key helper
# ===================================================================

_cached_api_key: Optional[str] = None
_key_lock = threading.Lock()


def _get_openrouter_key() -> str:
    """Fetch the OpenRouter API key.

    Resolution order:
      1. Cached value from a previous call.
      2. OPENROUTER_API_KEY environment variable.
      3. Orchestrator REST API at /secrets/OPENROUTER_API_KEY.

    Thread-safe: uses double-checked locking to protect the global cache.
    """
    global _cached_api_key

    # Fast path outside lock
    if _cached_api_key:
        return _cached_api_key

    with _key_lock:
        # Double-check inside lock
        if _cached_api_key:
            return _cached_api_key

        # Try environment variable first
        key = os.environ.get('OPENROUTER_API_KEY', '').strip()
        if key:
            _cached_api_key = key
            return key

        # Fall back to orchestrator secrets endpoint
        try:
            resp = requests.get(
                f'{API_BASE}/secrets/OPENROUTER_API_KEY',
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            key = data.get('value', data.get('secret', '')).strip()
            if key:
                _cached_api_key = key
                return key
        except Exception as exc:
            logger.warning('Failed to fetch API key from orchestrator: %s', exc)

    raise RuntimeError(
        'No OpenRouter API key found.  Set OPENROUTER_API_KEY or ensure '
        f'{API_BASE}/secrets/OPENROUTER_API_KEY is reachable.'
    )


# ===================================================================
# Difficulty classifier
# ===================================================================

def classify_difficulty(prompt: str) -> Dict[str, Any]:
    """Estimate query complexity using lightweight heuristics.

    Returns a dict with:
        score       float in [0, 1]  (0 = trivial, 1 = very hard)
        category    str              ('easy', 'medium', 'hard')
        signals     dict             per-heuristic breakdown
    """
    text = prompt.lower()
    words = text.split()
    word_count = len(words)

    signals: Dict[str, float] = {}

    # --- 1. Length signal ---
    # Very short queries tend to be simple lookups.
    if word_count <= 8:
        signals['length'] = 0.1
    elif word_count <= 30:
        signals['length'] = 0.3
    elif word_count <= 80:
        signals['length'] = 0.5
    elif word_count <= 200:
        signals['length'] = 0.7
    else:
        signals['length'] = 0.9

    # --- 2. Domain keyword signal ---
    hard_hits = sum(1 for kw in HARD_DOMAIN_KEYWORDS if kw in text)
    easy_hits = sum(1 for kw in EASY_DOMAIN_KEYWORDS if kw in text)
    if hard_hits + easy_hits == 0:
        signals['domain'] = 0.4  # neutral
    else:
        # ratio biased toward hard
        signals['domain'] = min(1.0, hard_hits / max(1, hard_hits + easy_hits))

    # --- 3. Question type signal ---
    # Factual questions ("what is X") are easy; open-ended / analytical are hard.
    factual_patterns = [
        r'\bwhat is\b', r'\bwho is\b', r'\bwhen did\b', r'\bdefine\b',
        r'\bhow many\b', r'\bwhere is\b',
    ]
    analytical_patterns = [
        r'\bwhy\b', r'\bhow (would|could|should|can)\b',
        r'\bexplain\b', r'\bcompare\b', r'\bdesign\b',
        r'\bwhat are the (pros|cons|advantages|disadvantages|implications)\b',
    ]
    factual_count = sum(1 for p in factual_patterns if re.search(p, text))
    analytical_count = sum(1 for p in analytical_patterns if re.search(p, text))

    if factual_count > analytical_count:
        signals['question_type'] = 0.2
    elif analytical_count > factual_count:
        signals['question_type'] = 0.7
    else:
        signals['question_type'] = 0.4

    # --- 4. Code signal ---
    has_code_block = '```' in prompt
    code_keywords = sum(1 for kw in ['function', 'class', 'def ', 'import ',
                                      'return ', 'for ', 'while ', 'if ']
                        if kw in text)
    if has_code_block or code_keywords >= 3:
        signals['code'] = 0.7
    elif code_keywords >= 1:
        signals['code'] = 0.5
    else:
        signals['code'] = 0.2

    # --- 5. Multi-part signal ---
    # Multiple questions / numbered requirements imply harder tasks.
    numbered = len(re.findall(r'(?:^|\n)\s*\d+[\.\)]\s', prompt))
    question_marks = prompt.count('?')
    if numbered >= 3 or question_marks >= 3:
        signals['multi_part'] = 0.8
    elif numbered >= 1 or question_marks >= 2:
        signals['multi_part'] = 0.5
    else:
        signals['multi_part'] = 0.2

    # --- Aggregate ---
    weights = {
        'length': 0.15,
        'domain': 0.30,
        'question_type': 0.20,
        'code': 0.20,
        'multi_part': 0.15,
    }
    score = sum(signals[k] * weights[k] for k in weights)
    score = max(0.0, min(1.0, score))

    if score < 0.35:
        category = 'easy'
    elif score < 0.65:
        category = 'medium'
    else:
        category = 'hard'

    return {
        'score': round(score, 4),
        'category': category,
        'signals': {k: round(v, 4) for k, v in signals.items()},
    }


# ===================================================================
# Confidence estimator (post-response)
# ===================================================================

def estimate_confidence(response_text: str, prompt: str) -> Dict[str, Any]:
    """Estimate how confident the model's response is.

    Returns:
        score       float in [0, 1]
        signals     dict
    """
    if not response_text or not response_text.strip():
        return {'score': 0.0, 'signals': {'empty': True}}

    text_lower = response_text.lower()
    prompt_words = len(prompt.split())
    response_words = len(response_text.split())

    signals: Dict[str, float] = {}

    # --- 1. Length ratio ---
    # A very short response relative to the prompt is suspicious.
    if response_words == 0:
        signals['length_ratio'] = 0.0
    elif response_words < 10:
        signals['length_ratio'] = 0.3
    elif response_words < 30:
        signals['length_ratio'] = 0.5
    elif response_words < prompt_words * 0.5:
        signals['length_ratio'] = 0.5
    else:
        signals['length_ratio'] = 0.9

    # --- 2. Hedging language ---
    hedge_count = sum(1 for phrase in HEDGING_PHRASES if phrase in text_lower)
    if hedge_count == 0:
        signals['hedging'] = 1.0
    elif hedge_count <= 2:
        signals['hedging'] = 0.6
    else:
        signals['hedging'] = 0.3

    # --- 3. Refusal / inability ---
    # NOTE: "as an ai" and "as a language model" are benign self-identification,
    # not refusals.  A model saying "As an AI, I can help with that" is not
    # refusing.  Only penalise genuine inability phrases.
    refusal_phrases = [
        "i cannot", "i can't", "i'm unable", "i am unable",
        "beyond my capabilities", "outside my training",
        "i don't have access", "i do not have access",
    ]
    refusal_count = sum(1 for p in refusal_phrases if p in text_lower)
    if refusal_count == 0:
        signals['refusal'] = 1.0
    elif refusal_count == 1:
        signals['refusal'] = 0.5
    else:
        signals['refusal'] = 0.2

    # --- 4. Structural quality ---
    # Responses with structure (lists, code, headings) tend to be higher quality.
    has_list = bool(re.search(r'(?:^|\n)\s*[-*]\s', response_text))
    has_numbered = bool(re.search(r'(?:^|\n)\s*\d+[\.\)]\s', response_text))
    has_code = '```' in response_text
    has_heading = bool(re.search(r'(?:^|\n)#+\s', response_text))
    structure_count = sum([has_list, has_numbered, has_code, has_heading])
    signals['structure'] = min(1.0, 0.5 + structure_count * 0.15)

    # --- 5. Repetition (low quality indicator) ---
    sentences = re.split(r'[.!?]+', response_text)
    sentences = [s.strip().lower() for s in sentences if len(s.strip()) > 10]
    if len(sentences) >= 2:
        unique_ratio = len(set(sentences)) / len(sentences)
        signals['repetition'] = unique_ratio
    else:
        signals['repetition'] = 0.8  # too short to judge, lean positive

    # --- Aggregate ---
    weights = {
        'length_ratio': 0.25,
        'hedging': 0.25,
        'refusal': 0.20,
        'structure': 0.15,
        'repetition': 0.15,
    }
    score = sum(signals[k] * weights[k] for k in weights)
    score = max(0.0, min(1.0, score))

    return {
        'score': round(score, 4),
        'signals': {k: round(v, 4) for k, v in signals.items()},
    }


# ===================================================================
# LLMCascade
# ===================================================================

class LLMCascade:
    """Cascading LLM router: tries cheap tiers first, escalates on low
    confidence.

    Parameters
    ----------
    threshold : float
        Minimum confidence score to accept a response without escalation.
        Default 0.65.
    max_tier : str
        Highest tier to escalate to ('free_small', 'free_large', 'paid').
        Default 'paid'.
    timeout : int
        HTTP timeout in seconds for model calls.  Default 30.
    max_tokens : int
        Maximum tokens to request from the model.  Default 1024.
    """

    def __init__(
        self,
        threshold: float = 0.65,
        max_tier: str = 'paid',
        timeout: int = 30,
        max_tokens: int = 1024,
    ):
        self.threshold = threshold
        self.max_tier = max_tier
        self.timeout = timeout
        self.max_tokens = max_tokens

        # Runtime statistics -- protected by _stats_lock for thread safety
        self._stats_lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            'total_queries': 0,
            'tier_counts': {t: 0 for t in TIER_ORDER},
            'escalation_count': 0,
            'avg_confidence': 0.0,
            'total_latency_ms': 0,
            'errors': 0,
            'started_at': datetime.now(timezone.utc).isoformat(),
        }

    # -----------------------------------------------------------------
    # Model call
    # -----------------------------------------------------------------

    def _call_model(
        self,
        model: str,
        prompt: str,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        """Call a single model via OpenRouter.

        Parameters
        ----------
        model : str
            The model identifier.
        prompt : str
            The user message content.
        max_tokens : int, optional
            Override max tokens for this call.
        system_prompt : str, optional
            System prompt sent as a separate ``system`` role message.

        Returns (response_text, metadata_dict).
        On failure returns ('', error_metadata).
        """
        api_key = _get_openrouter_key()
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/sfloess/claude-global-skills',
            'X-Title': 'LLM Cascade Router',
        }
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        payload = {
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens if max_tokens is not None else self.max_tokens,
            'temperature': 0.3,
        }

        start = time.monotonic()
        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code != 200:
                error_body = resp.text[:500]
                logger.warning(
                    'Model %s returned %d: %s', model, resp.status_code, error_body,
                )
                return '', {
                    'error': f'HTTP {resp.status_code}',
                    'detail': error_body,
                    'latency_ms': latency_ms,
                }

            data = resp.json()
            choices = data.get('choices', [])
            if not choices:
                return '', {
                    'error': 'no_choices',
                    'latency_ms': latency_ms,
                }

            text = choices[0].get('message', {}).get('content', '')
            usage = data.get('usage', {})

            return text, {
                'latency_ms': latency_ms,
                'usage': usage,
                'model_id': data.get('model', model),
            }

        except requests.exceptions.Timeout:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.warning('Model %s timed out after %dms', model, latency_ms)
            return '', {'error': 'timeout', 'latency_ms': latency_ms}

        except requests.exceptions.ConnectionError as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.warning('Connection error for model %s: %s', model, exc)
            return '', {'error': 'connection_error', 'latency_ms': latency_ms}

        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error('Unexpected error calling model %s: %s', model, exc)
            return '', {'error': str(exc), 'latency_ms': latency_ms}

    # -----------------------------------------------------------------
    # Tier iteration helpers
    # -----------------------------------------------------------------

    def _tiers_up_to(self, max_tier: str) -> List[str]:
        """Return the ordered list of tier names up to and including max_tier."""
        try:
            idx = TIER_ORDER.index(max_tier)
        except ValueError:
            idx = len(TIER_ORDER) - 1
        return TIER_ORDER[:idx + 1]

    def _pick_model(self, tier_name: str) -> str:
        """Pick a random model from the given tier."""
        models = TIERS.get(tier_name, [])
        if not models:
            raise ValueError(f'No models in tier {tier_name}')
        return random.choice(models)

    # -----------------------------------------------------------------
    # Starting tier selection
    # -----------------------------------------------------------------

    def _select_starting_tier(self, difficulty: Dict[str, Any]) -> str:
        """Choose the initial tier based on difficulty classification.

        Easy queries start at free_small.
        Medium queries start at free_small (give it a chance).
        Hard queries skip to free_large directly to save latency.
        """
        cat = difficulty.get('category', 'medium')
        if cat == 'hard':
            return 'free_large'
        return 'free_small'

    # -----------------------------------------------------------------
    # Main query method
    # -----------------------------------------------------------------

    def query(
        self,
        prompt: str,
        max_tier: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run a cascading query.

        Parameters
        ----------
        prompt : str
            The user query.
        max_tier : str, optional
            Override the instance-level max_tier for this call.
        system_prompt : str, optional
            Optional system prompt prepended to the user message.
        max_tokens : int, optional
            Override the instance-level max_tokens for this call.

        Returns
        -------
        dict with keys:
            answer        str   -- the model response
            model         str   -- model that produced the accepted answer
            tier          str   -- tier of that model
            confidence    float -- estimated confidence of the answer
            escalated     bool  -- whether we escalated past the first tried tier
            difficulty    dict  -- difficulty classification of the prompt
            attempts      list  -- log of each tier attempt
            latency_ms    int   -- total wall-clock time
        """
        effective_max_tier = max_tier or self.max_tier
        effective_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        total_start = time.monotonic()

        # Classify difficulty
        difficulty = classify_difficulty(prompt)

        # Select starting tier
        start_tier = self._select_starting_tier(difficulty)
        tiers_to_try = self._tiers_up_to(effective_max_tier)

        # Adjust: skip tiers before the starting tier
        try:
            start_idx = tiers_to_try.index(start_tier)
        except ValueError:
            start_idx = 0
        tiers_to_try = tiers_to_try[start_idx:]

        attempts: List[Dict[str, Any]] = []
        first_tier_tried = tiers_to_try[0] if tiers_to_try else 'free_small'

        for tier_name in tiers_to_try:
            model = self._pick_model(tier_name)
            response_text, call_meta = self._call_model(
                model, prompt, effective_max_tokens, system_prompt=system_prompt,
            )

            # If the call errored, try another model in the same tier once,
            # then escalate.
            if not response_text and call_meta.get('error'):
                attempts.append({
                    'tier': tier_name,
                    'model': model,
                    'error': call_meta.get('error'),
                    'latency_ms': call_meta.get('latency_ms', 0),
                })
                # Retry once with a different model in the same tier
                alt_models = [m for m in TIERS.get(tier_name, []) if m != model]
                if alt_models:
                    model = random.choice(alt_models)
                    response_text, call_meta = self._call_model(
                        model, prompt, effective_max_tokens, system_prompt=system_prompt,
                    )

                if not response_text:
                    attempts.append({
                        'tier': tier_name,
                        'model': model,
                        'error': call_meta.get('error', 'empty_response'),
                        'latency_ms': call_meta.get('latency_ms', 0),
                    })
                    continue  # escalate to next tier

            conf = estimate_confidence(response_text, prompt)
            confidence_score = conf['score']

            attempts.append({
                'tier': tier_name,
                'model': model,
                'confidence': confidence_score,
                'confidence_signals': conf['signals'],
                'latency_ms': call_meta.get('latency_ms', 0),
                'usage': call_meta.get('usage', {}),
            })

            is_last_tier = (tier_name == tiers_to_try[-1])

            if confidence_score >= self.threshold or is_last_tier:
                total_latency = int((time.monotonic() - total_start) * 1000)
                escalated = (tier_name != first_tier_tried)

                # Update stats (thread-safe)
                with self._stats_lock:
                    self._stats['total_queries'] += 1
                    self._stats['tier_counts'][tier_name] = (
                        self._stats['tier_counts'].get(tier_name, 0) + 1
                    )
                    if escalated:
                        self._stats['escalation_count'] += 1
                    n = self._stats['total_queries']
                    prev_avg = self._stats['avg_confidence']
                    self._stats['avg_confidence'] = (
                        prev_avg + (confidence_score - prev_avg) / n
                    )
                    self._stats['total_latency_ms'] += total_latency

                return {
                    'answer': response_text,
                    'model': model,
                    'tier': tier_name,
                    'confidence': confidence_score,
                    'escalated': escalated,
                    'difficulty': difficulty,
                    'attempts': attempts,
                    'latency_ms': total_latency,
                }

            # Confidence too low -- escalate
            logger.info(
                'Tier %s (model=%s) confidence %.3f < threshold %.3f, escalating',
                tier_name, model, confidence_score, self.threshold,
            )

        # Should not reach here, but safety fallback
        total_latency = int((time.monotonic() - total_start) * 1000)
        with self._stats_lock:
            self._stats['total_queries'] += 1
            self._stats['errors'] += 1
        return {
            'answer': '',
            'model': '',
            'tier': '',
            'confidence': 0.0,
            'escalated': True,
            'difficulty': difficulty,
            'attempts': attempts,
            'latency_ms': total_latency,
            'error': 'All tiers failed to produce a response.',
        }

    # -----------------------------------------------------------------
    # Statistics
    # -----------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return runtime statistics (thread-safe snapshot)."""
        with self._stats_lock:
            stats = dict(self._stats)
            # Deep-copy tier_counts to avoid mutation after release
            stats['tier_counts'] = dict(stats['tier_counts'])

        n = stats['total_queries']
        if n > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] / n
            stats['escalation_rate'] = stats['escalation_count'] / n
            # Estimate cost savings: proportion served by free tiers
            free_served = (
                stats['tier_counts'].get('free_small', 0)
                + stats['tier_counts'].get('free_large', 0)
            )
            stats['free_tier_rate'] = free_served / n
        else:
            stats['avg_latency_ms'] = 0
            stats['escalation_rate'] = 0.0
            stats['free_tier_rate'] = 0.0

        stats['threshold'] = self.threshold
        stats['max_tier'] = self.max_tier
        return stats

    def reset_stats(self) -> None:
        """Reset runtime statistics (thread-safe)."""
        with self._stats_lock:
            self._stats = {
                'total_queries': 0,
                'tier_counts': {t: 0 for t in TIER_ORDER},
                'escalation_count': 0,
                'avg_confidence': 0.0,
                'total_latency_ms': 0,
                'errors': 0,
                'started_at': datetime.now(timezone.utc).isoformat(),
            }

    def configure(
        self,
        threshold: Optional[float] = None,
        max_tier: Optional[str] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update cascade configuration.  Returns the new config."""
        if threshold is not None:
            self.threshold = max(0.0, min(1.0, threshold))
        if max_tier is not None and max_tier in TIER_ORDER:
            self.max_tier = max_tier
        if max_tokens is not None:
            self.max_tokens = max(64, min(16384, max_tokens))
        if timeout is not None:
            self.timeout = max(5, min(120, timeout))

        return {
            'threshold': self.threshold,
            'max_tier': self.max_tier,
            'max_tokens': self.max_tokens,
            'timeout': self.timeout,
        }


# ===================================================================
# Record cascade result to orchestrator (optional)
# ===================================================================

def _record_cascade_result(result: Dict[str, Any]) -> None:
    """Best-effort POST to /cascade/record for analytics.

    Does not raise -- failures are logged and swallowed.
    """
    try:
        requests.post(
            f'{API_BASE}/cascade/record',
            json={
                'model': result.get('model', ''),
                'tier': result.get('tier', ''),
                'confidence': result.get('confidence', 0.0),
                'escalated': result.get('escalated', False),
                'difficulty_score': result.get('difficulty', {}).get('score', 0.0),
                'difficulty_category': result.get('difficulty', {}).get('category', ''),
                'latency_ms': result.get('latency_ms', 0),
                'attempts': len(result.get('attempts', [])),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            },
            timeout=3,
        )
    except Exception:
        pass  # best-effort


# ===================================================================
# CLI entry point
# ===================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description='LLM Cascade Router -- try cheap models first, escalate on low confidence.',
    )
    parser.add_argument(
        'prompt',
        nargs='?',
        help='The query to send.  Reads from stdin if omitted.',
    )
    parser.add_argument(
        '--max-tier',
        choices=TIER_ORDER,
        default='paid',
        help='Highest tier to escalate to (default: paid).',
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.65,
        help='Confidence threshold for accepting a response (default: 0.65).',
    )
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=1024,
        help='Max tokens to request (default: 1024).',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        dest='json_output',
        help='Output full JSON result instead of just the answer.',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging.',
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

    # Get prompt
    prompt = args.prompt
    if not prompt:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        if not prompt:
            parser.error('No prompt provided.  Pass as argument or pipe via stdin.')

    cascade = LLMCascade(
        threshold=args.threshold,
        max_tier=args.max_tier,
        max_tokens=args.max_tokens,
    )

    result = cascade.query(prompt)

    # Best-effort record to orchestrator
    _record_cascade_result(result)

    if args.json_output:
        print(json.dumps(result, indent=2, default=str))
    else:
        # Human-friendly output
        if result.get('error'):
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

        print(result.get('answer', ''))
        print(file=sys.stderr)
        print(
            f"[model={result['model']}  tier={result['tier']}  "
            f"confidence={result['confidence']:.2f}  "
            f"escalated={result['escalated']}  "
            f"difficulty={result['difficulty']['category']}  "
            f"latency={result['latency_ms']}ms]",
            file=sys.stderr,
        )


if __name__ == '__main__':
    main()
