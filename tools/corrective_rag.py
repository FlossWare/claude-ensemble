#!/usr/bin/env python3
"""
Corrective RAG (CRAG) - LLM-graded retrieval with fallback strategies.

After retrieving documents from the knowledge base, an LLM judge grades each
result as CORRECT, AMBIGUOUS, or INCORRECT.  Based on the distribution of
grades, the system either:

  - Uses results directly     (all CORRECT)
  - Refines ambiguous results (mix of CORRECT + AMBIGUOUS)
  - Falls back to alternative strategies (all INCORRECT/AMBIGUOUS):
      1. Reformulate the query (LLM rephrase)
      2. Try a different search mode (fulltext, vector, hybrid)
      3. Expand to web search as last resort

All knowledge-base access goes through the REST API at aio-01:5000.
LLM calls go through OpenRouter (free models).

Usage:
    # Basic query
    python3 corrective_rag.py "What is Thompson Sampling?"

    # Verbose output (shows grading details)
    python3 corrective_rag.py "What is Thompson Sampling?" --verbose

    # Limit retrieval results
    python3 corrective_rag.py "RoPE position encoding" --limit 10

    # Force a specific search mode for the initial retrieval
    python3 corrective_rag.py "flash attention" --mode vector

    # Show statistics only
    python3 corrective_rag.py --stats
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = os.environ.get('API_BASE', 'http://aio-01:5000')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Free models for grading (fast, cheap - grading is a simple classification task)
GRADING_MODELS = [
    'qwen/qwen3-4b:free',
    'meta-llama/llama-3.2-3b-instruct:free',
    'google/gemma-3-4b-it:free',
    'nvidia/nemotron-3-nano-30b-a3b:free',
]

# Stronger models for refinement and query reformulation
REFINEMENT_MODELS = [
    'qwen/qwen3-30b-a3b:free',
    'google/gemma-4-26b-a4b-it:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'deepseek/deepseek-chat-v3-0324:free',
]

# Rate limiting
REQUESTS_PER_MINUTE = 20
REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0

# Retrieval defaults
DEFAULT_LIMIT = 5
DEFAULT_MODE = 'hybrid'
MAX_CONTENT_LENGTH = 800       # Max chars of document content sent to grader
MAX_REFINEMENT_LENGTH = 1500   # Max chars for refinement extraction
PIPELINE_TIMEOUT_S = 120       # Max total seconds for the full CRAG pipeline

# Search modes to try during fallback
SEARCH_MODES = ['hybrid', 'fulltext', 'vector']

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('corrective-rag')


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

GRADING_PROMPT = """You are a relevance judge for a technical knowledge base.

Grade the document's relevance to the query using these definitions:
- CORRECT: Directly answers the query or provides the exact information sought.
- AMBIGUOUS: Partially relevant, tangentially related, or requires inference to connect to the query.
- INCORRECT: Irrelevant, wrong topic, or does not help answer the query at all.

Query: {query}
Document: {doc_content}

Respond with exactly one word: CORRECT, AMBIGUOUS, or INCORRECT
Grade:"""

REFINEMENT_PROMPT = """Given the query "{query}", extract ONLY the sentences from this document that are relevant:
{document}
Relevant excerpt:"""

REFORMULATION_PROMPT = """The following search query returned no relevant results from a knowledge base.
Rewrite it as a better search query that might find relevant documents.
Return ONLY the rewritten query, nothing else.

Original query: {query}
Rewritten query:"""


# ---------------------------------------------------------------------------
# HTTP session and API key management
# ---------------------------------------------------------------------------

_session: Optional[requests.Session] = None
_cached_api_key: Optional[str] = None


def _get_session() -> requests.Session:
    """Return a reusable requests session with connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=0,
        )
        _session.mount('http://', adapter)
        _session.mount('https://', adapter)
    return _session


def _get_openrouter_key() -> str:
    """Fetch the OpenRouter API key (env -> orchestrator secrets endpoint)."""
    global _cached_api_key
    if _cached_api_key:
        return _cached_api_key

    key = os.environ.get('PERSONAL_OPENROUTER_API_KEY', '').strip()
    if key:
        _cached_api_key = key
        return key

    try:
        resp = _get_session().get(
            f'{API_BASE}/secrets/PERSONAL_OPENROUTER_API_KEY',
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
        'No OpenRouter API key found.  Set PERSONAL_OPENROUTER_API_KEY or ensure '
        f'{API_BASE}/secrets/PERSONAL_OPENROUTER_API_KEY is reachable.'
    )


# ---------------------------------------------------------------------------
# LLM call helper
# ---------------------------------------------------------------------------

def _call_llm(
    prompt: str,
    models: List[str],
    max_tokens: int = 128,
    temperature: float = 0.1,
) -> Tuple[str, str]:
    """Call an LLM via OpenRouter with cascading model fallback.

    Tries each model in order; returns (response_text, model_used).
    Raises RuntimeError if all models fail.
    """
    api_key = _get_openrouter_key()
    session = _get_session()

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com/sfloess/claude-global-skills',
        'X-Title': 'Corrective RAG',
    }

    last_error = None
    for model in models:
        for attempt in range(MAX_RETRIES):
            payload = {
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': max_tokens,
                'temperature': temperature,
            }

            try:
                time.sleep(REQUEST_INTERVAL)
                resp = session.post(
                    OPENROUTER_URL,
                    headers=headers,
                    json=payload,
                    timeout=30,
                )

                if resp.status_code == 429:
                    # Respect Retry-After header if present
                    retry_after = resp.headers.get('Retry-After')
                    if retry_after:
                        try:
                            wait = float(retry_after)
                        except (ValueError, TypeError):
                            wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                    else:
                        wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        'Rate limited on %s (attempt %d), waiting %.1fs',
                        model, attempt + 1, wait,
                    )
                    time.sleep(wait)
                    continue

                if resp.status_code != 200:
                    logger.warning(
                        'Model %s returned HTTP %d: %s',
                        model, resp.status_code, resp.text[:200],
                    )
                    last_error = f'HTTP {resp.status_code} from {model}'
                    break  # Try next model

                data = resp.json()
                choices = data.get('choices', [])
                if choices:
                    text = choices[0].get('message', {}).get('content', '')
                    if text.strip():
                        return text.strip(), model

                last_error = f'Empty response from {model}'
                break  # Try next model

            except requests.exceptions.Timeout:
                logger.warning('Timeout calling %s (attempt %d)', model, attempt + 1)
                last_error = f'Timeout from {model}'
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_BASE ** (attempt + 1))
                continue

            except requests.RequestException as exc:
                logger.warning('Request error calling %s: %s', model, exc)
                last_error = str(exc)
                break  # Try next model

    raise RuntimeError(f'All LLM models failed.  Last error: {last_error}')


# ---------------------------------------------------------------------------
# Knowledge base search
# ---------------------------------------------------------------------------

def search_knowledge_base(
    query: str,
    limit: int = DEFAULT_LIMIT,
    mode: str = DEFAULT_MODE,
) -> List[Dict[str, Any]]:
    """Search the knowledge base via the REST API.

    Returns a list of result dicts with keys: title, url, content, category,
    similarity, chunk_id, document_id.
    """
    session = _get_session()

    try:
        resp = session.post(
            f'{API_BASE}/knowledge/search',
            json={'query': query, 'limit': limit, 'mode': mode},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get('results', [])
    except requests.RequestException as exc:
        logger.error('Knowledge base search failed: %s', exc)
        return []


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

VALID_GRADES = {'CORRECT', 'AMBIGUOUS', 'INCORRECT'}


def _parse_grade(raw: str) -> str:
    """Extract a valid grade from the LLM response text."""
    upper = raw.upper().strip()
    # Direct match
    for grade in VALID_GRADES:
        if grade in upper:
            return grade
    # Fuzzy fallback: check first non-empty line
    first_line = upper.split('\n')[0].strip().rstrip('.').strip()
    for grade in VALID_GRADES:
        if grade in first_line:
            return grade
    # Default to AMBIGUOUS if we cannot parse (tracked as grading failure)
    logger.warning('Could not parse grade from: %s — defaulting to AMBIGUOUS', raw[:80])
    return 'AMBIGUOUS'




def grade_result(query: str, result: Dict[str, Any]) -> str:
    """Grade a single search result's relevance to the query.

    Returns one of: CORRECT, AMBIGUOUS, INCORRECT.
    """
    content = result.get('content', '')[:MAX_CONTENT_LENGTH]
    title = result.get('title', '')
    if title:
        content = f"Title: {title}\n{content}"

    prompt = GRADING_PROMPT.format(query=query, doc_content=content)

    try:
        response, model = _call_llm(prompt, GRADING_MODELS, max_tokens=16)
        grade = _parse_grade(response)
        logger.debug('Graded result "%s" as %s (model: %s)', title[:40], grade, model)
        return grade
    except RuntimeError as exc:
        logger.warning('Grading failed for "%s": %s — defaulting to AMBIGUOUS', title[:40], exc)
        return 'AMBIGUOUS'


def grade_results(
    query: str,
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Grade all results and attach grade metadata.

    Returns the same list with a 'grade' key added to each result dict.
    """
    graded = []
    for r in results:
        grade = grade_result(query, r)
        r_copy = dict(r)
        r_copy['grade'] = grade
        graded.append(r_copy)
    return graded


# ---------------------------------------------------------------------------
# Knowledge refinement (for AMBIGUOUS results)
# ---------------------------------------------------------------------------

def refine_result(query: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only the relevant portions of an AMBIGUOUS result.

    Returns a modified copy of the result with refined content.
    """
    content = result.get('content', '')[:MAX_REFINEMENT_LENGTH]
    prompt = REFINEMENT_PROMPT.format(query=query, document=content)

    try:
        response, model = _call_llm(prompt, REFINEMENT_MODELS, max_tokens=256)
        refined = dict(result)
        refined['original_content'] = result.get('content', '')
        refined['content'] = response
        refined['refined'] = True
        refined['refined_by'] = model
        logger.debug('Refined result "%s" (model: %s)', result.get('title', '')[:40], model)
        return refined
    except RuntimeError as exc:
        logger.warning('Refinement failed: %s — using original content', exc)
        return result


# ---------------------------------------------------------------------------
# Query reformulation
# ---------------------------------------------------------------------------

def reformulate_query(query: str) -> str:
    """Ask an LLM to rephrase the query for better retrieval."""
    prompt = REFORMULATION_PROMPT.format(query=query)

    try:
        response, model = _call_llm(prompt, REFINEMENT_MODELS, max_tokens=128)
        # Clean up: remove quotes, leading/trailing whitespace
        reformulated = response.strip().strip('"').strip("'").strip()
        if not reformulated or len(reformulated) < 5:
            logger.warning('Reformulation produced empty/too-short result, keeping original')
            return query
        logger.info('Query reformulated: "%s" -> "%s" (model: %s)', query, reformulated, model)
        return reformulated
    except RuntimeError as exc:
        logger.warning('Query reformulation failed: %s — keeping original', exc)
        return query


# ---------------------------------------------------------------------------
# Fallback strategies
# ---------------------------------------------------------------------------

def _try_alternative_modes(
    query: str,
    original_mode: str,
    limit: int,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Try searching with different modes than the original.

    Returns (results, mode_used) or ([], None) if all fail.
    """
    for mode in SEARCH_MODES:
        if mode == original_mode:
            continue
        results = search_knowledge_base(query, limit=limit, mode=mode)
        if results:
            logger.info('Alternative search mode "%s" returned %d results', mode, len(results))
            return results, mode
    return [], None


def _try_web_search(query: str) -> List[Dict[str, Any]]:
    """Attempt web search as a last-resort fallback.

    Uses the orchestrator's web search endpoint if available.
    Returns a list of result-like dicts.
    """
    session = _get_session()

    # Try the orchestrator's web search endpoint
    for endpoint in [
        f'{API_BASE}/web/search',
        f'{API_BASE}/search/web',
    ]:
        try:
            resp = session.post(
                endpoint,
                json={'query': query, 'limit': 5},
                timeout=15,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            web_results = data.get('results', [])
            if web_results:
                # Normalize to knowledge-base-like format
                normalized = []
                for wr in web_results:
                    normalized.append({
                        'title': wr.get('title', 'Web Result'),
                        'url': wr.get('url', wr.get('link', '')),
                        'content': wr.get('snippet', wr.get('content', wr.get('description', ''))),
                        'category': 'web_search',
                        'similarity': 0.0,
                        'source': 'web_search',
                    })
                logger.info('Web search returned %d results', len(normalized))
                return normalized
        except requests.RequestException:
            continue

    logger.info('Web search not available or returned no results')
    return []


# ---------------------------------------------------------------------------
# Main CRAG pipeline
# ---------------------------------------------------------------------------

class CorrectiveRAG:
    """Corrective RAG pipeline: retrieve -> grade -> refine/fallback -> respond.

    Parameters
    ----------
    limit : int
        Number of results to retrieve per search.
    mode : str
        Initial search mode ('hybrid', 'fulltext', 'vector').
    max_fallback_rounds : int
        Maximum number of fallback attempts before giving up.
    """

    def __init__(
        self,
        limit: int = DEFAULT_LIMIT,
        mode: str = DEFAULT_MODE,
        max_fallback_rounds: int = 2,
    ):
        self.limit = limit
        self.mode = mode
        self.max_fallback_rounds = max_fallback_rounds
        self.grading_failures = 0

        # Runtime statistics
        self._stats: Dict[str, Any] = {
            'total_queries': 0,
            'grading_distribution': {'CORRECT': 0, 'AMBIGUOUS': 0, 'INCORRECT': 0},
            'actions_taken': {'direct_use': 0, 'refined': 0, 'fallback': 0},
            'fallback_triggers': {
                'reformulate': 0, 'alt_mode': 0,
                'web_search': 0, 'refined_ambiguous': 0,
            },
            'total_results_graded': 0,
            'refinements_performed': 0,
            'avg_correct_ratio': 0.0,
            'started_at': datetime.now(timezone.utc).isoformat(),
        }

    def _update_stats(
        self,
        grades: List[str],
        action: str,
        fallback_type: Optional[str] = None,
    ) -> None:
        """Update runtime statistics."""
        self._stats['total_queries'] += 1
        self._stats['total_results_graded'] += len(grades)

        for g in grades:
            self._stats['grading_distribution'][g] = (
                self._stats['grading_distribution'].get(g, 0) + 1
            )

        self._stats['actions_taken'][action] = (
            self._stats['actions_taken'].get(action, 0) + 1
        )

        if fallback_type:
            self._stats['fallback_triggers'][fallback_type] = (
                self._stats['fallback_triggers'].get(fallback_type, 0) + 1
            )

        # Update rolling average of correct ratio
        total_graded = self._stats['total_results_graded']
        total_correct = self._stats['grading_distribution']['CORRECT']
        if total_graded > 0:
            self._stats['avg_correct_ratio'] = round(total_correct / total_graded, 4)

    def get_stats(self) -> Dict[str, Any]:
        """Return current runtime statistics."""
        stats = dict(self._stats)
        stats['grading_failures'] = self.grading_failures
        return stats

    def _check_timeout(self, start_time: float) -> bool:
        """Return True if the pipeline has exceeded its time budget."""
        return (time.monotonic() - start_time) > PIPELINE_TIMEOUT_S

    def _grade_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Grade results and track grading failures on this instance."""
        graded = []
        for r in results:
            content = r.get('content', '')[:MAX_CONTENT_LENGTH]
            title = r.get('title', '')
            if title:
                content = f"Title: {title}\n{content}"

            prompt = GRADING_PROMPT.format(query=query, doc_content=content)

            try:
                response, model = _call_llm(prompt, GRADING_MODELS, max_tokens=16)
                grade = _parse_grade(response)
                logger.debug(
                    'Graded result "%s" as %s (model: %s)',
                    title[:40], grade, model,
                )
            except RuntimeError as exc:
                self.grading_failures += 1
                logger.warning(
                    'Grading failed for "%s": %s - defaulting to AMBIGUOUS',
                    title[:40], exc,
                )
                grade = 'AMBIGUOUS'

            r_copy = dict(r)
            r_copy['grade'] = grade
            graded.append(r_copy)
        return graded

    def query(
        self,
        query: str,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Run the full CRAG pipeline.

        Parameters
        ----------
        query : str
            The user's search query.
        verbose : bool
            If True, include grading details in the response.

        Returns
        -------
        dict with keys:
            query          str   - original query
            results        list  - final results (graded, possibly refined)
            action         str   - 'direct_use', 'refined', or 'fallback'
            fallback_type  str   - None, 'reformulate', 'alt_mode', or 'web_search'
            grading        dict  - grade distribution {CORRECT: n, AMBIGUOUS: n, INCORRECT: n}
            metadata       dict  - timing, models used, etc.
        """
        start_time = time.monotonic()
        metadata: Dict[str, Any] = {
            'initial_mode': self.mode,
            'limit': self.limit,
        }

        # --- Step 1: Initial retrieval ---
        logger.info('Searching knowledge base: "%s" (mode=%s, limit=%d)',
                     query, self.mode, self.limit)
        results = search_knowledge_base(query, limit=self.limit, mode=self.mode)

        if not results:
            logger.info('No results from initial search, attempting fallback')
            return self._handle_no_results(query, verbose, start_time, metadata)

        metadata['initial_result_count'] = len(results)

        # --- Step 2: Grade each result ---
        logger.info('Grading %d results...', len(results))
        graded = self._grade_results(query, results)

        grades = [r['grade'] for r in graded]
        grade_dist = {
            'CORRECT': grades.count('CORRECT'),
            'AMBIGUOUS': grades.count('AMBIGUOUS'),
            'INCORRECT': grades.count('INCORRECT'),
        }
        metadata['grade_distribution'] = grade_dist

        if verbose:
            for r in graded:
                logger.info(
                    '  [%s] %s (sim=%.3f)',
                    r['grade'],
                    r.get('title', 'Untitled')[:60],
                    r.get('similarity', 0),
                )

        # --- Step 3: Decide action based on grades ---
        correct_results = [r for r in graded if r['grade'] == 'CORRECT']
        ambiguous_results = [r for r in graded if r['grade'] == 'AMBIGUOUS']
        incorrect_results = [r for r in graded if r['grade'] == 'INCORRECT']

        # Case 1: All or mostly CORRECT -> use directly
        if correct_results and not ambiguous_results and not incorrect_results:
            action = 'direct_use'
            final_results = correct_results
            fallback_type = None
            logger.info('All %d results graded CORRECT, using directly', len(correct_results))

        # Case 2: Mix of CORRECT + AMBIGUOUS -> use CORRECT, refine AMBIGUOUS
        elif correct_results:
            action = 'refined'
            fallback_type = None
            refined = []
            for r in ambiguous_results:
                refined_r = refine_result(query, r)
                refined.append(refined_r)
                self._stats['refinements_performed'] += 1
            final_results = correct_results + refined
            logger.info(
                'Using %d CORRECT + refining %d AMBIGUOUS results',
                len(correct_results), len(ambiguous_results),
            )

        # Case 3: All INCORRECT/AMBIGUOUS -> fallback
        else:
            logger.info('No CORRECT results, triggering fallback strategies')
            return self._handle_fallback(
                query, graded, ambiguous_results, verbose, start_time, metadata,
            )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        metadata['elapsed_ms'] = elapsed_ms
        metadata['grading_failures'] = self.grading_failures

        self._update_stats(grades, action, fallback_type)

        return {
            'query': query,
            'results': final_results,
            'action': action,
            'fallback_type': fallback_type,
            'grading': grade_dist,
            'result_count': len(final_results),
            'metadata': metadata,
        }

    def _make_empty_response(
        self,
        query: str,
        start_time: float,
        metadata: Dict[str, Any],
        reason: str = 'exhausted',
    ) -> Dict[str, Any]:
        """Build a standard empty-result response."""
        metadata['elapsed_ms'] = int((time.monotonic() - start_time) * 1000)
        self._update_stats([], 'fallback', None)
        return {
            'query': query,
            'results': [],
            'action': 'fallback',
            'fallback_type': reason,
            'grading': {'CORRECT': 0, 'AMBIGUOUS': 0, 'INCORRECT': 0},
            'result_count': 0,
            'metadata': metadata,
        }

    def _handle_no_results(
        self,
        query: str,
        verbose: bool,
        start_time: float,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle the case where initial retrieval returns nothing."""
        metadata['initial_result_count'] = 0

        # Strategy 1: Reformulate and retry
        if self._check_timeout(start_time):
            return self._make_empty_response(query, start_time, metadata, 'timeout')
        reformulated = reformulate_query(query)
        if reformulated != query:
            self._stats['fallback_triggers']['reformulate'] += 1
            results = search_knowledge_base(reformulated, limit=self.limit, mode=self.mode)
            if results:
                graded = self._grade_results(reformulated, results)
                correct = [r for r in graded if r['grade'] == 'CORRECT']
                if correct:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    metadata['elapsed_ms'] = elapsed_ms
                    metadata['reformulated_query'] = reformulated
                    grades = [r['grade'] for r in graded]
                    self._update_stats(grades, 'fallback', 'reformulate')
                    return {
                        'query': query,
                        'reformulated_query': reformulated,
                        'results': correct,
                        'action': 'fallback',
                        'fallback_type': 'reformulate',
                        'grading': {
                            'CORRECT': len(correct),
                            'AMBIGUOUS': grades.count('AMBIGUOUS'),
                            'INCORRECT': grades.count('INCORRECT'),
                        },
                        'result_count': len(correct),
                        'metadata': metadata,
                    }

        # Strategy 2: Try alternative search modes
        if self._check_timeout(start_time):
            return self._make_empty_response(query, start_time, metadata, 'timeout')
        alt_results, alt_mode = _try_alternative_modes(query, self.mode, self.limit)
        if alt_results:
            self._stats['fallback_triggers']['alt_mode'] += 1
            graded = self._grade_results(query, alt_results)
            usable = [r for r in graded if r['grade'] in ('CORRECT', 'AMBIGUOUS')]
            if usable:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                metadata['elapsed_ms'] = elapsed_ms
                metadata['alt_search_mode'] = alt_mode
                grades = [r['grade'] for r in graded]
                self._update_stats(grades, 'fallback', 'alt_mode')
                return {
                    'query': query,
                    'results': usable,
                    'action': 'fallback',
                    'fallback_type': 'alt_mode',
                    'grading': {
                        'CORRECT': grades.count('CORRECT'),
                        'AMBIGUOUS': grades.count('AMBIGUOUS'),
                        'INCORRECT': grades.count('INCORRECT'),
                    },
                    'result_count': len(usable),
                    'metadata': metadata,
                }

        # Strategy 3: Web search
        if self._check_timeout(start_time):
            return self._make_empty_response(query, start_time, metadata, 'timeout')
        web_results = _try_web_search(query)
        if web_results:
            self._stats['fallback_triggers']['web_search'] += 1
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            metadata['elapsed_ms'] = elapsed_ms
            self._update_stats([], 'fallback', 'web_search')
            return {
                'query': query,
                'results': web_results,
                'action': 'fallback',
                'fallback_type': 'web_search',
                'grading': {'CORRECT': 0, 'AMBIGUOUS': 0, 'INCORRECT': 0},
                'result_count': len(web_results),
                'metadata': metadata,
            }

        # Nothing worked
        return self._make_empty_response(query, start_time, metadata, 'exhausted')

    def _handle_fallback(
        self,
        query: str,
        graded: List[Dict[str, Any]],
        ambiguous_results: List[Dict[str, Any]],
        verbose: bool,
        start_time: float,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle the case where no results are graded CORRECT.

        Attempts fallback strategies in order:
          1. Reformulate query and re-search
          2. Try alternative search modes
          3. Refine ambiguous results as a last resort
          4. Web search
        """
        original_grades = [r['grade'] for r in graded]

        # Strategy 1: Reformulate query
        if self._check_timeout(start_time):
            return self._make_empty_response(query, start_time, metadata, 'timeout')
        reformulated = reformulate_query(query)
        if reformulated != query:
            results = search_knowledge_base(reformulated, limit=self.limit, mode=self.mode)
            if results:
                re_graded = self._grade_results(reformulated, results)
                correct = [r for r in re_graded if r['grade'] == 'CORRECT']
                if correct:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    metadata['elapsed_ms'] = elapsed_ms
                    metadata['reformulated_query'] = reformulated
                    new_grades = [r['grade'] for r in re_graded]
                    self._update_stats(
                        original_grades + new_grades, 'fallback', 'reformulate',
                    )
                    return {
                        'query': query,
                        'reformulated_query': reformulated,
                        'results': correct,
                        'action': 'fallback',
                        'fallback_type': 'reformulate',
                        'grading': {
                            'CORRECT': new_grades.count('CORRECT'),
                            'AMBIGUOUS': new_grades.count('AMBIGUOUS'),
                            'INCORRECT': new_grades.count('INCORRECT'),
                        },
                        'result_count': len(correct),
                        'metadata': metadata,
                    }

        # Strategy 2: Try different search modes
        if self._check_timeout(start_time):
            return self._make_empty_response(query, start_time, metadata, 'timeout')
        alt_results, alt_mode = _try_alternative_modes(query, self.mode, self.limit)
        if alt_results:
            alt_graded = self._grade_results(query, alt_results)
            correct = [r for r in alt_graded if r['grade'] == 'CORRECT']
            if correct:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                metadata['elapsed_ms'] = elapsed_ms
                metadata['alt_search_mode'] = alt_mode
                new_grades = [r['grade'] for r in alt_graded]
                self._update_stats(
                    original_grades + new_grades, 'fallback', 'alt_mode',
                )
                return {
                    'query': query,
                    'results': correct,
                    'action': 'fallback',
                    'fallback_type': 'alt_mode',
                    'grading': {
                        'CORRECT': new_grades.count('CORRECT'),
                        'AMBIGUOUS': new_grades.count('AMBIGUOUS'),
                        'INCORRECT': new_grades.count('INCORRECT'),
                    },
                    'result_count': len(correct),
                    'metadata': metadata,
                }

        # Strategy 3: If we have ambiguous results, refine them as best-effort
        if self._check_timeout(start_time):
            return self._make_empty_response(query, start_time, metadata, 'timeout')
        if ambiguous_results:
            refined = []
            for r in ambiguous_results:
                refined_r = refine_result(query, r)
                refined.append(refined_r)
                self._stats['refinements_performed'] += 1

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            metadata['elapsed_ms'] = elapsed_ms
            self._update_stats(original_grades, 'fallback', 'refined_ambiguous')
            return {
                'query': query,
                'results': refined,
                'action': 'fallback',
                'fallback_type': 'refined_ambiguous',
                'grading': {
                    'CORRECT': 0,
                    'AMBIGUOUS': len(ambiguous_results),
                    'INCORRECT': original_grades.count('INCORRECT'),
                },
                'result_count': len(refined),
                'metadata': metadata,
            }

        # Strategy 4: Web search
        if self._check_timeout(start_time):
            return self._make_empty_response(query, start_time, metadata, 'timeout')
        web_results = _try_web_search(query)
        if web_results:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            metadata['elapsed_ms'] = elapsed_ms
            self._update_stats(original_grades, 'fallback', 'web_search')
            return {
                'query': query,
                'results': web_results,
                'action': 'fallback',
                'fallback_type': 'web_search',
                'grading': {
                    'CORRECT': 0,
                    'AMBIGUOUS': original_grades.count('AMBIGUOUS'),
                    'INCORRECT': original_grades.count('INCORRECT'),
                },
                'result_count': len(web_results),
                'metadata': metadata,
            }

        # Nothing worked
        return self._make_empty_response(query, start_time, metadata, 'exhausted')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _format_result(r: Dict[str, Any], index: int) -> str:
    """Format a single result for CLI display."""
    lines = []
    grade = r.get('grade', 'N/A')
    title = r.get('title', 'Untitled')[:80]
    url = r.get('url', '')
    sim = r.get('similarity', 0)
    refined = r.get('refined', False)
    content = r.get('content', '')[:300]

    grade_marker = {'CORRECT': '+', 'AMBIGUOUS': '~', 'INCORRECT': '-'}.get(grade, '?')
    lines.append(f'  [{grade_marker}] {index}. [{grade}] {title}')
    if url:
        lines.append(f'       URL: {url}')
    if sim:
        lines.append(f'       Similarity: {sim:.4f}')
    if refined:
        lines.append(f'       (Refined by {r.get("refined_by", "unknown")})')
    lines.append(f'       {content}')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Corrective RAG - LLM-graded retrieval with fallback strategies',
    )
    parser.add_argument(
        'query',
        nargs='?',
        help='Search query',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed grading information',
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=DEFAULT_LIMIT,
        help=f'Number of results to retrieve (default: {DEFAULT_LIMIT})',
    )
    parser.add_argument(
        '--mode', '-m',
        choices=SEARCH_MODES,
        default=DEFAULT_MODE,
        help=f'Initial search mode (default: {DEFAULT_MODE})',
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics from the orchestrator (requires API)',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        dest='json_output',
        help='Output raw JSON instead of formatted text',
    )

    args = parser.parse_args()

    if args.stats:
        try:
            resp = _get_session().get(f'{API_BASE}/rag/corrective/stats', timeout=10)
            resp.raise_for_status()
            print(json.dumps(resp.json(), indent=2))
        except requests.RequestException as exc:
            print(f'Error fetching stats: {exc}', file=sys.stderr)
            sys.exit(1)
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    if args.verbose:
        logging.getLogger('corrective-rag').setLevel(logging.DEBUG)

    crag = CorrectiveRAG(limit=args.limit, mode=args.mode)
    result = crag.query(args.query, verbose=args.verbose)

    if args.json_output:
        print(json.dumps(result, indent=2, default=str))
        return

    # Formatted output
    print(f'\nQuery: {result["query"]}')
    if result.get('reformulated_query'):
        print(f'Reformulated: {result["reformulated_query"]}')
    print(f'Action: {result["action"]}')
    if result.get('fallback_type'):
        print(f'Fallback: {result["fallback_type"]}')

    grading = result.get('grading', {})
    print(
        f'Grading: {grading.get("CORRECT", 0)} correct, '
        f'{grading.get("AMBIGUOUS", 0)} ambiguous, '
        f'{grading.get("INCORRECT", 0)} incorrect'
    )
    print(f'Results: {result["result_count"]}')

    elapsed = result.get('metadata', {}).get('elapsed_ms', 0)
    if elapsed:
        print(f'Time: {elapsed}ms')

    print()
    for i, r in enumerate(result.get('results', []), 1):
        print(_format_result(r, i))
        print()

    # Print local stats
    if args.verbose:
        print('\n--- Session Statistics ---')
        print(json.dumps(crag.get_stats(), indent=2))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrupted.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
