#!/usr/bin/env python3
"""
Mixture of Agents (MoA) - Multi-Layer LLM Aggregation

Implements the Mixture of Agents pattern where:
  Layer 1 (Proposers):   N models independently generate responses in parallel
  Layer 2 (Aggregators): 2-3 models receive ALL Layer 1 outputs and produce refined responses
  Final Synthesis:       One arbiter synthesizes Layer 2 outputs into the final answer

This has been shown to outperform single-model approaches (including GPT-4o)
by leveraging diverse model strengths and iterative refinement.

Architecture:
    User Query -> [Model A, Model B, Model C, Model D]  (Layer 1, parallel)
                              | all outputs
              [Aggregator 1, Aggregator 2]               (Layer 2, parallel)
                              | all outputs
                         [Final Arbiter]  ->  Answer

All model calls go through the fleet proxy at aio-01:8000 (OpenAI-compatible)
or directly to OpenRouter. API keys fetched via REST from aio-01:5000/secrets/.

Usage:
    # Python API
    from mixture_of_agents import MixtureOfAgents
    moa = MixtureOfAgents()
    result = moa.query("What is Thompson Sampling?")
    print(result.answer)

    # CLI
    python3 tools/mixture_of_agents.py "What is Thompson Sampling?"
    python3 tools/mixture_of_agents.py --layers 3 "Explain RLHF"

Created: 2026-07-26
"""

import random
import requests
import json
import sys
import os
import time
import argparse
import logging
import threading
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = os.getenv('API_BASE', 'http://aio-01:5000')
PROXY_URL = os.getenv('API_PROXY_URL', 'http://aio-01:8000/v1/chat/completions')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Per-call timeout (seconds).  Layer 2 and synthesis calls may take longer
# because prompts include all prior outputs.
DEFAULT_TIMEOUT = 90
SYNTHESIS_TIMEOUT = 120

# Maximum number of concurrent threads for any single layer.
MAX_LAYER_PARALLELISM = 8

# Retry configuration for transient failures (429, 5xx).
MAX_RETRIES = 2
RETRY_BACKOFF = 1.5  # seconds, doubles each retry

# Truncate individual model outputs to this many characters before feeding
# them into the next layer to avoid exceeding context windows.
MAX_OUTPUT_CHARS = 12_000

# HTTP status codes that warrant an automatic retry.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# ---------------------------------------------------------------------------
# Default model selections
# ---------------------------------------------------------------------------

# Layer 1 proposers: diverse, free-tier models from different providers/families
# to maximise viewpoint diversity.
DEFAULT_PROPOSERS = [
    'deepseek/deepseek-chat',
    'qwen/qwen3-30b-a3b:free',
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-3.3-70b-instruct:free',
]

# Layer 2 aggregators: strong models that can synthesise multiple viewpoints.
# ZERO overlap with proposers to avoid self-confirmation bias.
DEFAULT_AGGREGATORS = [
    'nvidia/nemotron-3-super-120b-a12b:free',
    'qwen/qwen3-235b-a22b:free',
]

# Final arbiter: high-capability model for the definitive synthesis.
DEFAULT_ARBITER = 'nousresearch/hermes-3-llama-3.1-405b:free'


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class ModelOutput:
    """Result from a single model call."""
    model: str
    content: str
    duration_ms: int = 0
    tokens_used: int = 0
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and bool(self.content)


@dataclass
class MoAResult:
    """Complete result from a Mixture-of-Agents run."""
    answer: str
    layer1: List[Dict[str, Any]] = field(default_factory=list)
    layer2: List[Dict[str, Any]] = field(default_factory=list)
    synthesis: Optional[Dict[str, Any]] = None
    models_used: int = 0
    total_duration_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# API Key Management
# ---------------------------------------------------------------------------

_cached_api_key: Optional[str] = None
_cache_expiry: float = 0.0
_KEY_CACHE_TTL = 300  # seconds
_key_lock = threading.Lock()


def _fetch_api_key(key_name: str = 'OPENROUTER_API_KEY') -> str:
    """Fetch an API key from the secrets REST endpoint.

    Tries (in order):
      1. Environment variable
      2. REST endpoint at aio-01:5000/secrets/<key_name>
    Caches the result for 5 minutes to avoid hammering the endpoint.

    Thread-safe: uses double-checked locking to protect the global cache.

    Raises RuntimeError if the key cannot be obtained.
    """
    global _cached_api_key, _cache_expiry

    # Fast path: cache hit (read outside lock for performance)
    if _cached_api_key and time.monotonic() < _cache_expiry:
        return _cached_api_key

    with _key_lock:
        # Double-check inside lock to avoid redundant fetches
        if _cached_api_key and time.monotonic() < _cache_expiry:
            return _cached_api_key

        # Try environment variable first
        env_val = os.environ.get(key_name)
        if env_val:
            _cached_api_key = env_val
            _cache_expiry = time.monotonic() + _KEY_CACHE_TTL
            return env_val

        # Fetch from secrets endpoint
        url = f'{API_BASE}/secrets/{key_name}'
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            value = data.get('value', '')
            if not value:
                raise RuntimeError(
                    f'Secrets endpoint returned empty value for {key_name}'
                )
            _cached_api_key = value
            _cache_expiry = time.monotonic() + _KEY_CACHE_TTL
            return value
        except requests.RequestException as exc:
            raise RuntimeError(
                f'Failed to fetch API key {key_name} from {url}: {exc}'
            ) from exc


# ---------------------------------------------------------------------------
# Low-level model calling
# ---------------------------------------------------------------------------

def _call_model(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    timeout: int = DEFAULT_TIMEOUT,
) -> ModelOutput:
    """Call a single model via the OpenRouter API (OpenAI-compatible).

    Uses the fleet proxy when a proxy URL is configured and the model string
    contains a ``/`` (indicating an OpenRouter model identifier).

    Retries on transient HTTP errors with exponential backoff.
    """
    api_key = _fetch_api_key()

    messages: List[Dict[str, str]] = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})

    payload = {
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com/sfloess/claude-global-skills',
        'X-Title': 'MoA-Orchestrator',
    }

    # Prefer proxy when available; fall back to OpenRouter direct.
    url = PROXY_URL if PROXY_URL else OPENROUTER_URL

    last_error: Optional[str] = None
    start = time.monotonic()

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=timeout,
            )

            if resp.status_code in _RETRYABLE_STATUS_CODES:
                last_error = f'HTTP {resp.status_code}: {resp.text[:300]}'
                if attempt < MAX_RETRIES:
                    delay = RETRY_BACKOFF * (2 ** attempt)
                    logger.warning(
                        'Retryable error from %s (attempt %d/%d): %s. '
                        'Sleeping %.1fs.',
                        model, attempt + 1, MAX_RETRIES + 1, last_error, delay,
                    )
                    time.sleep(delay)
                    continue

                # Final attempt exhausted
                return ModelOutput(
                    model=model,
                    content='',
                    duration_ms=int((time.monotonic() - start) * 1000),
                    error=f'Exhausted retries. Last: {last_error}',
                )

            if resp.status_code != 200:
                return ModelOutput(
                    model=model,
                    content='',
                    duration_ms=int((time.monotonic() - start) * 1000),
                    error=f'HTTP {resp.status_code}: {resp.text[:500]}',
                )

            data = resp.json()
            choices = data.get('choices', [])
            if not choices:
                return ModelOutput(
                    model=model,
                    content='',
                    duration_ms=int((time.monotonic() - start) * 1000),
                    error=f'No choices in response: {json.dumps(data)[:300]}',
                )

            content = choices[0].get('message', {}).get('content', '')
            usage = data.get('usage', {})
            total_tokens = (
                usage.get('total_tokens')
                or usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)
            )

            return ModelOutput(
                model=model,
                content=content,
                duration_ms=int((time.monotonic() - start) * 1000),
                tokens_used=total_tokens,
            )

        except requests.Timeout:
            last_error = f'Timeout after {timeout}s'
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * (2 ** attempt))
                continue
            return ModelOutput(
                model=model,
                content='',
                duration_ms=int((time.monotonic() - start) * 1000),
                error=last_error,
            )

        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * (2 ** attempt))
                continue
            return ModelOutput(
                model=model,
                content='',
                duration_ms=int((time.monotonic() - start) * 1000),
                error=f'Request failed: {last_error}',
            )

    # Should not reach here, but guard against it.
    return ModelOutput(
        model=model,
        content='',
        duration_ms=int((time.monotonic() - start) * 1000),
        error=f'Unexpected exit from retry loop: {last_error}',
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_aggregation_prompt(
    original_prompt: str,
    layer1_outputs: List[ModelOutput],
) -> str:
    """Build the prompt for Layer 2 aggregators.

    Presents all Layer 1 outputs in a numbered, neutral format.  Model names
    are replaced with generic labels (Response 1, 2, ...) to prevent
    brand-name bias in the aggregation.
    """
    # Shuffle the output order to prevent position bias -- LLMs tend to
    # give disproportionate attention to earlier responses.
    shuffled = list(layer1_outputs)
    random.shuffle(shuffled)

    sections: List[str] = []
    for i, output in enumerate(shuffled, 1):
        if output.succeeded:
            # Truncate very long outputs to stay within context limits
            text = output.content
            if len(text) > MAX_OUTPUT_CHARS:
                text = text[:MAX_OUTPUT_CHARS] + '\n... [truncated]'
            sections.append(f'--- Response {i} ---\n{text}')
        else:
            sections.append(
                f'--- Response {i} ---\n[This response was unavailable]'
            )

    all_responses = '\n\n'.join(sections)

    return (
        f'A user asked the following question:\n\n'
        f'"""\n{original_prompt}\n"""\n\n'
        f'Multiple independent AI models have answered this question.  '
        f'Their responses are shown below in randomised order.\n\n'
        f'{all_responses}\n\n'
        f'Your task:\n'
        f'1. Carefully read every response above.\n'
        f'2. Identify the strongest points, correct facts, and best '
        f'reasoning from each.\n'
        f'3. Note any contradictions, errors, or gaps.\n'
        f'4. Produce a single, comprehensive, refined answer to the '
        f'original question that is better than any individual response.\n\n'
        f'Do NOT simply concatenate the responses.  Synthesise them into a '
        f'coherent, accurate, well-structured answer.  Where responses '
        f'disagree, use your own reasoning to determine the correct position '
        f'and explain why.\n\n'
        f'IMPORTANT: Do not assume earlier-numbered responses are better.  '
        f'Evaluate each response on its merits regardless of its position.'
    )


def _build_synthesis_prompt(
    original_prompt: str,
    layer2_outputs: List[ModelOutput],
) -> str:
    """Build the prompt for the final arbiter synthesis.

    Similar to aggregation but emphasises producing the definitive answer.
    """
    # Shuffle to prevent position bias in synthesis.
    shuffled = list(layer2_outputs)
    random.shuffle(shuffled)

    sections: List[str] = []
    for i, output in enumerate(shuffled, 1):
        if output.succeeded:
            text = output.content
            if len(text) > MAX_OUTPUT_CHARS:
                text = text[:MAX_OUTPUT_CHARS] + '\n... [truncated]'
            sections.append(f'--- Refined Response {i} ---\n{text}')
        else:
            sections.append(
                f'--- Refined Response {i} ---\n'
                f'[This response was unavailable]'
            )

    all_responses = '\n\n'.join(sections)
    num_successful = sum(1 for o in layer2_outputs if o.succeeded)

    return (
        f'A user asked the following question:\n\n'
        f'"""\n{original_prompt}\n"""\n\n'
        f'{num_successful} expert AI system(s) have each synthesised multiple '
        f'independent answers into refined responses.  '
        f'Their refined outputs are below.\n\n'
        f'{all_responses}\n\n'
        f'You are the final arbiter.  Produce the definitive answer:\n'
        f'1. Take the best elements from each refined response.\n'
        f'2. Resolve any remaining contradictions with clear reasoning.\n'
        f'3. Ensure factual accuracy and completeness.\n'
        f'4. Present a clear, well-structured final answer.\n\n'
        f'This is the answer that will be delivered to the user.  '
        f'Make it excellent.'
    )


# ---------------------------------------------------------------------------
# Layer execution
# ---------------------------------------------------------------------------

def _run_layer(
    models: List[str],
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[ModelOutput]:
    """Run a set of models in parallel and collect their outputs.

    Failed models are included in the result list (with error fields set)
    so callers can inspect failures.  At least one model must succeed for
    the layer to be considered usable.
    """
    results: List[ModelOutput] = [None] * len(models)  # type: ignore[list-item]
    parallelism = min(len(models), MAX_LAYER_PARALLELISM)

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        future_to_idx = {}
        for idx, model in enumerate(models):
            future = executor.submit(
                _call_model, model, prompt, system, max_tokens, temperature,
                timeout,
            )
            future_to_idx[future] = idx

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = ModelOutput(
                    model=models[idx],
                    content='',
                    error=f'Thread exception: {exc}',
                )

    return results


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MixtureOfAgents:
    """Mixture-of-Agents orchestrator.

    Parameters
    ----------
    proposers : list[str], optional
        Models for Layer 1 (independent proposals).
    aggregators : list[str], optional
        Models for Layer 2 (cross-response refinement).
    arbiter : str, optional
        Model for the final synthesis.
    max_tokens : int
        Maximum tokens per model call.
    temperature : float
        Sampling temperature for all calls.
    system : str, optional
        System prompt prepended to all calls.
    num_layers : int
        Number of aggregation layers (default 2: proposers + aggregators).
        Set to 3 for an extra refinement pass.
    """

    def __init__(
        self,
        proposers: Optional[List[str]] = None,
        aggregators: Optional[List[str]] = None,
        arbiter: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system: Optional[str] = None,
        num_layers: int = 2,
    ):
        self.proposers = proposers or list(DEFAULT_PROPOSERS)
        self.aggregators = aggregators or list(DEFAULT_AGGREGATORS)
        self.arbiter = arbiter or DEFAULT_ARBITER
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system = system
        self.num_layers = max(2, min(num_layers, 4))  # clamp 2-4

        self._validate_no_overlap()

    def _validate_no_overlap(self) -> None:
        """Warn if proposers and aggregators share models (self-confirmation risk)."""
        overlap = set(self.proposers) & set(self.aggregators)
        if overlap:
            logger.warning(
                'Proposer/aggregator overlap detected (self-confirmation risk): %s. '
                'Consider using distinct model families.',
                overlap,
            )

    def query(
        self,
        prompt: str,
        system: Optional[str] = None,
    ) -> MoAResult:
        """Execute a full MoA pipeline.

        Parameters
        ----------
        prompt : str
            The user's question or task.
        system : str, optional
            Override the instance-level system prompt for this call.

        Returns
        -------
        MoAResult
            Contains the final answer plus per-layer details.
        """
        effective_system = system or self.system
        overall_start = time.monotonic()

        # ---- Layer 1: Independent proposals ----
        logger.info(
            'Layer 1: Running %d proposers in parallel...', len(self.proposers),
        )
        layer1_outputs = _run_layer(
            self.proposers, prompt, effective_system,
            self.max_tokens, self.temperature,
        )

        successful_l1 = [o for o in layer1_outputs if o.succeeded]
        if not successful_l1:
            return MoAResult(
                answer='',
                layer1=[asdict(o) for o in layer1_outputs],
                models_used=len(self.proposers),
                total_duration_ms=int((time.monotonic() - overall_start) * 1000),
                error='All Layer 1 proposers failed. No outputs to aggregate.',
            )

        logger.info(
            'Layer 1 complete: %d/%d succeeded.',
            len(successful_l1), len(self.proposers),
        )

        # ---- Layer 2+: Aggregation (may iterate for num_layers > 2) ----
        current_outputs = layer1_outputs
        all_layer2_outputs: List[List[ModelOutput]] = []

        for layer_num in range(2, self.num_layers + 1):
            is_final_agg = (layer_num == self.num_layers)
            agg_prompt = _build_aggregation_prompt(prompt, current_outputs)

            logger.info(
                'Layer %d: Running %d aggregators in parallel...',
                layer_num, len(self.aggregators),
            )
            layer_outputs = _run_layer(
                self.aggregators, agg_prompt, effective_system,
                self.max_tokens, self.temperature,
                timeout=SYNTHESIS_TIMEOUT if is_final_agg else DEFAULT_TIMEOUT,
            )
            all_layer2_outputs.append(layer_outputs)

            successful = [o for o in layer_outputs if o.succeeded]
            if not successful:
                # Fall back: use the last successful Layer 1 output
                # (arbitrary but deterministic -- length is a bad quality proxy
                # because verbose hallucinations would beat concise correct answers).
                best_l1 = successful_l1[-1]
                return MoAResult(
                    answer=best_l1.content,
                    layer1=[asdict(o) for o in layer1_outputs],
                    layer2=[
                        [asdict(o) for o in lo] for lo in all_layer2_outputs
                    ],
                    models_used=len(self.proposers) + len(self.aggregators),
                    total_duration_ms=int(
                        (time.monotonic() - overall_start) * 1000
                    ),
                    error=(
                        f'All Layer {layer_num} aggregators failed.  '
                        f'Returning best Layer 1 output as fallback.'
                    ),
                )

            logger.info(
                'Layer %d complete: %d/%d succeeded.',
                layer_num, len(successful), len(self.aggregators),
            )
            current_outputs = layer_outputs

        # ---- Final Synthesis ----
        logger.info('Synthesis: Running final arbiter (%s)...', self.arbiter)
        synthesis_prompt = _build_synthesis_prompt(prompt, current_outputs)
        synthesis_output = _call_model(
            self.arbiter, synthesis_prompt, effective_system,
            self.max_tokens, self.temperature, SYNTHESIS_TIMEOUT,
        )

        # If the arbiter fails, fall back to the best aggregator output
        if not synthesis_output.succeeded:
            last_agg = all_layer2_outputs[-1] if all_layer2_outputs else []
            successful_agg = [o for o in last_agg if o.succeeded]
            fallback_content = (
                successful_agg[0].content if successful_agg else
                successful_l1[0].content
            )
            logger.warning(
                'Arbiter failed (%s). Falling back to best aggregator output.',
                synthesis_output.error,
            )
            return MoAResult(
                answer=fallback_content,
                layer1=[asdict(o) for o in layer1_outputs],
                layer2=[
                    [asdict(o) for o in lo] for lo in all_layer2_outputs
                ],
                synthesis=asdict(synthesis_output),
                models_used=(
                    len(self.proposers) + len(self.aggregators) * len(all_layer2_outputs) + 1
                ),
                total_duration_ms=int(
                    (time.monotonic() - overall_start) * 1000
                ),
                error=f'Arbiter failed: {synthesis_output.error}. Using aggregator fallback.',
            )

        total_models = (
            len(self.proposers)
            + len(self.aggregators) * len(all_layer2_outputs)
            + 1  # arbiter
        )
        total_ms = int((time.monotonic() - overall_start) * 1000)

        logger.info(
            'MoA complete: %d models, %dms total.', total_models, total_ms,
        )

        return MoAResult(
            answer=synthesis_output.content,
            layer1=[asdict(o) for o in layer1_outputs],
            layer2=[
                [asdict(o) for o in lo] for lo in all_layer2_outputs
            ],
            synthesis=asdict(synthesis_output),
            models_used=total_models,
            total_duration_ms=total_ms,
        )


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def list_available_free_models() -> List[Dict[str, str]]:
    """Return the curated list of free OpenRouter models suitable for MoA.

    Each entry includes the model identifier and a short description of its
    strength, making it easier to select proposer/aggregator sets.
    """
    return [
        {'model': 'nvidia/nemotron-3-ultra-550b-a55b:free',
         'params': '550B', 'strength': 'Largest free model, strong reasoning'},
        {'model': 'nousresearch/hermes-3-llama-3.1-405b:free',
         'params': '405B', 'strength': 'Strong instruction following'},
        {'model': 'qwen/qwen3-235b-a22b:free',
         'params': '235B', 'strength': 'Strong multilingual and coding'},
        {'model': 'nvidia/nemotron-3-super-120b-a12b:free',
         'params': '120B', 'strength': 'Good balance of speed and quality'},
        {'model': 'openai/gpt-oss-120b:free',
         'params': '120B', 'strength': 'OpenAI open-source, general purpose'},
        {'model': 'qwen/qwen3-next-80b-a3b-instruct:free',
         'params': '80B', 'strength': 'Fast, efficient MoE'},
        {'model': 'meta-llama/llama-3.3-70b-instruct:free',
         'params': '70B', 'strength': 'Reliable general purpose'},
        {'model': 'google/gemma-4-31b-it:free',
         'params': '31B', 'strength': 'Google, compact and fast'},
        {'model': 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free',
         'params': '30B', 'strength': 'Reasoning specialist'},
        {'model': 'nvidia/nemotron-3-nano-30b-a3b:free',
         'params': '30B', 'strength': 'General purpose, fast'},
        {'model': 'google/gemma-4-26b-a4b-it:free',
         'params': '26B', 'strength': 'Efficient MoE from Google'},
        {'model': 'cognitivecomputations/dolphin-mistral-24b-venice-edition:free',
         'params': '24B', 'strength': 'Uncensored, creative'},
        {'model': 'openai/gpt-oss-20b:free',
         'params': '20B', 'strength': 'Small OpenAI open-source'},
        {'model': 'qwen/qwen3-coder:free',
         'params': 'varies', 'strength': 'Code specialist'},
        {'model': 'deepseek/deepseek-chat',
         'params': 'varies', 'strength': 'Strong reasoning and code'},
        {'model': 'google/gemini-2.0-flash-exp:free',
         'params': 'varies', 'strength': 'Fast, multimodal'},
        {'model': 'qwen/qwen3-30b-a3b:free',
         'params': '30B', 'strength': 'Efficient MoE'},
        {'model': 'poolside/laguna-m.1:free',
         'params': 'varies', 'strength': 'Code-oriented'},
        {'model': 'meta-llama/llama-3.2-3b-instruct:free',
         'params': '3B', 'strength': 'Ultra-fast, simple tasks only'},
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Mixture of Agents - Multi-layer LLM aggregation',
    )
    parser.add_argument(
        'prompt', nargs='?',
        help='The question or task to process',
    )
    parser.add_argument(
        '--layers', type=int, default=2,
        help='Number of aggregation layers (2-4, default: 2)',
    )
    parser.add_argument(
        '--proposers', nargs='+',
        help='Override default proposer models',
    )
    parser.add_argument(
        '--aggregators', nargs='+',
        help='Override default aggregator models',
    )
    parser.add_argument(
        '--arbiter', type=str,
        help='Override default arbiter model',
    )
    parser.add_argument(
        '--system', type=str,
        help='System prompt for all models',
    )
    parser.add_argument(
        '--max-tokens', type=int, default=4096,
        help='Max tokens per model response (default: 4096)',
    )
    parser.add_argument(
        '--temperature', type=float, default=0.7,
        help='Sampling temperature (default: 0.7)',
    )
    parser.add_argument(
        '--json', action='store_true',
        help='Output full result as JSON (includes per-layer details)',
    )
    parser.add_argument(
        '--list-models', action='store_true',
        help='List available free models for MoA and exit',
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Enable verbose/debug logging',
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if args.list_models:
        models = list_available_free_models()
        print(f'{"Model":<58} {"Params":<8} Strength')
        print('-' * 100)
        for m in models:
            print(f'{m["model"]:<58} {m["params"]:<8} {m["strength"]}')
        sys.exit(0)

    if not args.prompt:
        # Try reading from stdin if no prompt argument
        if not sys.stdin.isatty():
            args.prompt = sys.stdin.read().strip()
        if not args.prompt:
            parser.error('A prompt is required (positional arg or via stdin)')

    moa = MixtureOfAgents(
        proposers=args.proposers,
        aggregators=args.aggregators,
        arbiter=args.arbiter,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        system=args.system,
        num_layers=args.layers,
    )

    result = moa.query(args.prompt)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        if result.error:
            print(f'[Warning: {result.error}]\n', file=sys.stderr)
        print(result.answer)
        print(
            f'\n--- MoA stats: {result.models_used} models, '
            f'{result.total_duration_ms}ms ---',
            file=sys.stderr,
        )


if __name__ == '__main__':
    main()
