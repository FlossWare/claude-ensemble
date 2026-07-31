#!/usr/bin/env python3
"""
Contextual Retrieval - Prepend LLM-generated context to RAG chunks.

Implements Anthropic's Contextual Retrieval technique: for each chunk, uses a
fast/cheap LLM to generate a 1-2 sentence context prefix that explains what
the chunk is about relative to its parent document.  This reduces retrieval
failures by ~67% because chunks no longer lose the context of their origin
after splitting.

Designed to run on fleet workers (NOT aio-01, which is controller only).
All database access goes through the REST API at aio-01:5000.

Usage:
    # Process 100 chunks (default)
    python3 tools/contextual_retrieval.py

    # Process 500 chunks with a specific model
    python3 tools/contextual_retrieval.py --batch-size 500 --model google/gemma-4-26b-a4b-it:free

    # Dry run (show what would be processed, no LLM calls)
    python3 tools/contextual_retrieval.py --dry-run

    # Resume from a specific chunk ID
    python3 tools/contextual_retrieval.py --offset 50000

    # Check progress
    python3 tools/contextual_retrieval.py --status
"""

import argparse
import json
import logging
import os
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_API_BASE = os.environ.get('API_BASE', 'http://aio-01:5000')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Free models suitable for context generation (fast, cheap, good at summarization).
# Ordered by preference: larger models first for better quality, with fallbacks.
DEFAULT_MODELS = [
    'google/gemma-4-26b-a4b-it:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'qwen/qwen3-coder:free',
    'nvidia/nemotron-3-nano-30b-a3b:free',
    'meta-llama/llama-3.2-3b-instruct:free',
]

# Rate limiting
REQUESTS_PER_MINUTE = 20       # Conservative default for free-tier models
REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0       # Exponential backoff base in seconds

# Chunk processing
DEFAULT_BATCH_SIZE = 100
DOC_EXCERPT_LENGTH = 500       # First N chars of parent doc
CONTEXT_MAX_TOKENS = 128       # Max tokens for context generation
CONTEXT_PREFIX_MARKER = '[CTX]'  # Marker to identify already-contextualized chunks

# Bug fix #3: Use a mutable config object instead of mutating module-level
# globals via the 'global' keyword.  main() updates config attributes;
# all functions read from config instead of bare globals.
class _Config:
    """Runtime configuration updated by main() from CLI arguments."""
    api_base: str = _DEFAULT_API_BASE
    request_interval: float = 60.0 / REQUESTS_PER_MINUTE

config = _Config()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('contextual-retrieval')

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

CONTEXT_PROMPT = """Given this document title and excerpt, write a 1-2 sentence context that explains what the following chunk is about. Be specific and concise. Do NOT repeat the chunk content. Only output the context sentences, nothing else.

Document title: {title}
Document excerpt: {doc_excerpt}

Chunk to contextualize:
{chunk_content}

Context (1-2 sentences):"""


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Return a reusable requests session with connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=0,  # We handle retries ourselves
        )
        _session.mount('http://', adapter)
        _session.mount('https://', adapter)
    return _session


def get_openrouter_api_key() -> str:
    """Fetch the OpenRouter API key from the secrets endpoint."""
    # Check environment first (for workers that have it pre-loaded)
    env_key = os.environ.get('PERSONAL_OPENROUTER_API_KEY', '')
    if env_key:
        return env_key

    try:
        resp = _get_session().get(
            f'{config.api_base}/secrets/PERSONAL_OPENROUTER_API_KEY',
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        key = data.get('value', '')
        if not key:
            raise ValueError('Empty API key returned from secrets endpoint')
        return key
    except requests.RequestException as e:
        logger.error('Failed to fetch OpenRouter API key: %s', e)
        raise


def get_knowledge_stats() -> Dict[str, Any]:
    """Fetch knowledge base statistics."""
    resp = _get_session().get(f'{config.api_base}/knowledge/stats', timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_chunks_without_context(
    limit: int = DEFAULT_BATCH_SIZE,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Fetch chunks that do not yet have a contextual prefix.

    Queries the knowledge API for chunks whose content does not start with
    the context prefix marker.

    Returns a list of dicts with keys: chunk_id, content, document_id,
    chunk_index, doc_title, doc_excerpt.
    """
    # Try the blueprint endpoint first, then the knowledge endpoint, then fallback
    for path in [
        '/pipeline/contextual-retrieval/chunks/without-context',
        '/knowledge/chunks/without-context',
    ]:
        try:
            resp = _get_session().get(
                f'{config.api_base}{path}',
                params={'limit': limit, 'offset': offset},
                timeout=30,
            )
            if resp.status_code == 404:
                continue  # Try next path
            resp.raise_for_status()
            data = resp.json()
            return data.get('items', [])
        except requests.RequestException:
            continue

    logger.info(
        'chunks/without-context endpoints not available, '
        'falling back to embeddings/pending'
    )
    return _fallback_get_chunks(limit, offset)


def _fallback_get_chunks(
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    """Fallback: fetch chunks via the pending-embeddings or generic chunks
    endpoint and filter for those without context markers."""
    # Try fetching unembedded chunks (they need processing anyway)
    try:
        resp = _get_session().get(
            f'{config.api_base}/knowledge/embeddings/pending',
            params={'limit': limit * 2},  # Over-fetch to compensate for filtering
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get('items', [])

        # Filter out already-contextualized chunks
        filtered = []
        for item in items:
            content = item.get('content', '')
            if not content.startswith(CONTEXT_PREFIX_MARKER):
                filtered.append(item)
            if len(filtered) >= limit:
                break
        return filtered
    except requests.RequestException as e:
        logger.error('Fallback chunk fetch failed: %s', e)
        return []


def get_document_info(document_id: int) -> Optional[Dict[str, Any]]:
    """Fetch parent document title and excerpt for a given document ID."""
    for path in [
        f'/pipeline/contextual-retrieval/document/{document_id}',
        f'/knowledge/document/{document_id}',
    ]:
        try:
            resp = _get_session().get(
                f'{config.api_base}{path}',
                timeout=10,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            continue
    return None


def get_document_info_batch(document_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Fetch document info for multiple document IDs in one request.

    Falls back to individual lookups if the batch endpoint is unavailable.
    """
    if not document_ids:
        return {}

    unique_ids = list(set(document_ids))

    # Try batch endpoint (blueprint path first, then knowledge path)
    for path in [
        '/pipeline/contextual-retrieval/documents/batch',
        '/knowledge/documents/batch',
    ]:
        try:
            resp = _get_session().post(
                f'{config.api_base}{path}',
                json={'document_ids': unique_ids},
                timeout=30,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            result = {}
            for doc in data.get('documents', []):
                doc_id = doc.get('id')
                if doc_id is not None:
                    result[doc_id] = doc
            return result
        except requests.RequestException:
            continue

    # Fallback: individual lookups
    result = {}
    for doc_id in unique_ids:
        info = get_document_info(doc_id)
        if info:
            result[doc_id] = info
    return result


def update_chunk_content(chunk_id: int, new_content: str) -> bool:
    """Update a chunk's content with the contextual prefix via REST API.

    Also invalidates the existing embedding so the chunk gets re-embedded.
    """
    for path in [
        '/pipeline/contextual-retrieval/chunks/update-content',
        '/knowledge/chunks/update-content',
    ]:
        try:
            resp = _get_session().post(
                f'{config.api_base}{path}',
                json={
                    'chunk_id': chunk_id,
                    'content': new_content,
                    'invalidate_embedding': True,
                },
                timeout=15,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error('Failed to update chunk %s via %s: %s', chunk_id, path, e)
            continue

    # All paths failed, try legacy fallback
    return _fallback_update_chunk(chunk_id, new_content)


def _fallback_update_chunk(chunk_id: int, new_content: str) -> bool:
    """Fallback: update chunk content via a generic update mechanism."""
    try:
        # Try the pipeline chunk store with update semantics
        resp = _get_session().post(
            f'{config.api_base}/knowledge/chunks/update',
            json={'chunk_id': chunk_id, 'content': new_content},
            timeout=15,
        )
        if resp.status_code == 404:
            logger.error(
                'No chunk update endpoint available. '
                'Deploy contextual_retrieval_blueprint.py on aio-01 first.'
            )
            return False
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error('Fallback chunk update failed for %s: %s', chunk_id, e)
        return False


def queue_chunk_for_reembedding(chunk_id: int) -> bool:
    """Queue a chunk for re-embedding after its content changed."""
    for path in [
        '/pipeline/contextual-retrieval/embeddings/invalidate',
        '/knowledge/embeddings/invalidate',
    ]:
        try:
            resp = _get_session().post(
                f'{config.api_base}{path}',
                json={'chunk_ids': [chunk_id]},
                timeout=10,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            return True
        except requests.RequestException:
            continue

    # If no endpoint available, the update_chunk_content call
    # with invalidate_embedding=True should have handled it
    logger.debug(
        'embeddings/invalidate not available; '
        'relying on invalidate_embedding flag'
    )
    return True


# ---------------------------------------------------------------------------
# LLM context generation
# ---------------------------------------------------------------------------

def generate_context(
    api_key: str,
    title: str,
    doc_excerpt: str,
    chunk_content: str,
    model: str,
    model_fallbacks: Optional[List[str]] = None,
) -> Optional[str]:
    """Call OpenRouter to generate a contextual prefix for a chunk.

    Tries the primary model first, then falls back through alternatives
    on failure.  Returns None if all models fail.
    """
    models_to_try = [model] + (model_fallbacks or [])

    prompt = CONTEXT_PROMPT.format(
        title=title or 'Untitled',
        doc_excerpt=doc_excerpt[:DOC_EXCERPT_LENGTH] if doc_excerpt else '(no excerpt available)',
        chunk_content=chunk_content[:1500],  # Limit chunk to avoid huge prompts
    )

    for attempt_model in models_to_try:
        for retry in range(MAX_RETRIES):
            try:
                resp = _get_session().post(
                    OPENROUTER_URL,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {api_key}',
                        'HTTP-Referer': 'https://claude-global-skills.local',
                        'X-Title': 'Contextual Retrieval Pipeline',
                    },
                    json={
                        'model': attempt_model,
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': CONTEXT_MAX_TOKENS,
                        'temperature': 0.3,  # Low temp for consistent output
                    },
                    timeout=30,
                )

                if resp.status_code == 429:
                    # Rate limited -- back off and retry
                    # Bug fix #5: Retry-After can be an HTTP-date string,
                    # not just seconds.  Guard against ValueError.
                    raw_retry = resp.headers.get('Retry-After')
                    try:
                        retry_after = float(raw_retry) if raw_retry else (
                            RETRY_BACKOFF_BASE ** (retry + 1)
                        )
                    except (ValueError, TypeError):
                        retry_after = RETRY_BACKOFF_BASE ** (retry + 1)
                    logger.warning(
                        'Rate limited on %s, waiting %.1fs (retry %d/%d)',
                        attempt_model, retry_after, retry + 1, MAX_RETRIES,
                    )
                    time.sleep(retry_after)
                    continue

                if resp.status_code == 503 or resp.status_code == 502:
                    # Model temporarily unavailable
                    logger.warning(
                        'Model %s returned %d, trying next model',
                        attempt_model, resp.status_code,
                    )
                    break  # Skip to next model

                resp.raise_for_status()
                data = resp.json()

                # Parse OpenRouter response (OpenAI-compatible format)
                choices = data.get('choices', [])
                if not choices:
                    logger.warning('Empty choices from %s', attempt_model)
                    break

                content = choices[0].get('message', {}).get('content', '').strip()
                if not content:
                    logger.warning('Empty content from %s', attempt_model)
                    break

                # Sanitize: strip marker if model echoed it back
                if content.startswith(CONTEXT_PREFIX_MARKER):
                    content = content[len(CONTEXT_PREFIX_MARKER):].strip()

                # Strip surrounding quotes if model wrapped its output
                if (content.startswith('"') and content.endswith('"')) or \
                   (content.startswith("'") and content.endswith("'")):
                    content = content[1:-1].strip()

                # Validate: context should be 1-2 sentences, not too long
                if len(content) > 500:
                    content = content[:500].rsplit('.', 1)[0] + '.'

                if not content:
                    logger.warning('Context was empty after sanitization from %s', attempt_model)
                    break

                return content

            except requests.Timeout:
                logger.warning(
                    'Timeout on %s (retry %d/%d)',
                    attempt_model, retry + 1, MAX_RETRIES,
                )
                time.sleep(RETRY_BACKOFF_BASE ** (retry + 1))
                continue

            except requests.RequestException as e:
                logger.warning(
                    'Request error on %s: %s (retry %d/%d)',
                    attempt_model, e, retry + 1, MAX_RETRIES,
                )
                time.sleep(RETRY_BACKOFF_BASE ** (retry + 1))
                continue

    logger.error('All models failed to generate context')
    return None


# ---------------------------------------------------------------------------
# Batch processor
# ---------------------------------------------------------------------------

class ContextualRetrievalProcessor:
    """Processes chunks in batches, adding contextual prefixes."""

    def __init__(
        self,
        model: str = DEFAULT_MODELS[0],
        batch_size: int = DEFAULT_BATCH_SIZE,
        dry_run: bool = False,
    ):
        self.model = model
        self.model_fallbacks = [m for m in DEFAULT_MODELS if m != model]
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.worker_id = f'ctx-{socket.gethostname()}-{os.getpid()}'

        # Stats
        self.processed = 0
        self.succeeded = 0
        self.failed = 0
        self.skipped = 0
        self.start_time: Optional[float] = None

        # API key (fetched lazily)
        self._api_key: Optional[str] = None

    @property
    def api_key(self) -> str:
        if self._api_key is None:
            self._api_key = get_openrouter_api_key()
        return self._api_key

    def process_batch(self, offset: int = 0) -> Dict[str, Any]:
        """Process a batch of chunks.

        Returns a summary dict with processing statistics.
        """
        self.start_time = time.time()

        logger.info(
            'Starting contextual retrieval (worker=%s, model=%s, batch=%d, dry_run=%s)',
            self.worker_id, self.model, self.batch_size, self.dry_run,
        )

        # 1. Fetch chunks without context
        logger.info('Fetching chunks without contextual prefix...')
        chunks = get_chunks_without_context(
            limit=self.batch_size,
            offset=offset,
        )

        if not chunks:
            logger.info('No chunks need contextual retrieval')
            return self._summary()

        logger.info('Found %d chunks to process', len(chunks))

        # 2. Fetch parent document info in batch
        doc_ids = list(set(
            c.get('document_id') or c.get('doc_id')
            for c in chunks
            if c.get('document_id') or c.get('doc_id')
        ))
        logger.info('Fetching info for %d parent documents...', len(doc_ids))
        doc_info_map = get_document_info_batch(doc_ids)
        logger.info('Retrieved info for %d documents', len(doc_info_map))

        # 3. Process each chunk
        for i, chunk in enumerate(chunks):
            chunk_id = chunk.get('chunk_id') or chunk.get('id')
            content = chunk.get('content', '')
            doc_id = chunk.get('document_id') or chunk.get('doc_id')

            if not chunk_id or not content:
                self.skipped += 1
                continue

            # Skip if already has context prefix
            if content.startswith(CONTEXT_PREFIX_MARKER):
                self.skipped += 1
                continue

            # Skip empty or very short chunks
            if len(content.strip()) < 20:
                self.skipped += 1
                continue

            # Get parent document info
            doc = doc_info_map.get(doc_id, {})
            title = doc.get('title', '')
            doc_content = doc.get('content', '')
            doc_excerpt = doc_content[:DOC_EXCERPT_LENGTH] if doc_content else ''

            # If no title or excerpt, use the chunk's own metadata
            if not title:
                title = chunk.get('title', 'Untitled')
            if not doc_excerpt:
                # Bug fix #6: A URL is not a document excerpt.  Use a
                # semantically correct fallback instead.
                doc_excerpt = 'No excerpt available'

            self.processed += 1

            if self.dry_run:
                logger.info(
                    '[DRY RUN] Would contextualize chunk %s '
                    '(doc=%s, title="%s", %d chars)',
                    chunk_id, doc_id, title[:50], len(content),
                )
                self.succeeded += 1
                continue

            # Generate context via LLM
            context = generate_context(
                api_key=self.api_key,
                title=title,
                doc_excerpt=doc_excerpt,
                chunk_content=content,
                model=self.model,
                model_fallbacks=self.model_fallbacks,
            )

            if context is None:
                logger.warning(
                    'Failed to generate context for chunk %s', chunk_id
                )
                self.failed += 1
                # Rate limit: still wait to avoid hammering
                time.sleep(config.request_interval)
                continue

            # Prepend context to chunk content with marker
            new_content = f'{CONTEXT_PREFIX_MARKER} {context}\n\n{content}'

            # Update chunk content (also invalidates embedding)
            if update_chunk_content(chunk_id, new_content):
                # Additionally queue for re-embedding if needed
                queue_chunk_for_reembedding(chunk_id)
                self.succeeded += 1
                logger.info(
                    'Contextualized chunk %s (%d/%d): "%s"',
                    chunk_id, i + 1, len(chunks), context[:80],
                )
            else:
                self.failed += 1
                logger.warning(
                    'Failed to update chunk %s after context generation',
                    chunk_id,
                )

            # Rate limiting between LLM calls
            time.sleep(config.request_interval)

        return self._summary()

    def _summary(self) -> Dict[str, Any]:
        """Build a summary of the processing run."""
        elapsed = time.time() - (self.start_time or time.time())
        rate = self.processed / max(elapsed, 0.001)

        summary = {
            'worker_id': self.worker_id,
            'model': self.model,
            'batch_size': self.batch_size,
            'dry_run': self.dry_run,
            'processed': self.processed,
            'succeeded': self.succeeded,
            'failed': self.failed,
            'skipped': self.skipped,
            'elapsed_seconds': round(elapsed, 1),
            'rate_per_second': round(rate, 2),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            'Contextual retrieval complete: '
            '%d processed, %d succeeded, %d failed, %d skipped '
            '(%.1fs, %.2f/s)',
            self.processed, self.succeeded, self.failed, self.skipped,
            elapsed, rate,
        )

        return summary


# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------

def check_status() -> Dict[str, Any]:
    """Check contextual retrieval progress from the API."""
    try:
        # Get overall knowledge stats
        stats = get_knowledge_stats()

        # Try the dedicated status endpoint
        try:
            resp = _get_session().get(
                f'{config.api_base}/pipeline/contextual-retrieval/status',
                timeout=10,
            )
            if resp.ok:
                cr_status = resp.json()
                stats['contextual_retrieval'] = cr_status
        except requests.RequestException:
            stats['contextual_retrieval'] = {
                'note': 'Status endpoint not deployed yet'
            }

        return stats
    except requests.RequestException as e:
        return {'error': str(e)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Contextual Retrieval: Add LLM-generated context prefixes to RAG chunks'
    )
    parser.add_argument(
        '--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
        help=f'Number of chunks to process (default: {DEFAULT_BATCH_SIZE})'
    )
    parser.add_argument(
        '--model', type=str, default=DEFAULT_MODELS[0],
        help=f'OpenRouter model to use (default: {DEFAULT_MODELS[0]})'
    )
    parser.add_argument(
        '--offset', type=int, default=0,
        help='Chunk ID offset to resume from (default: 0)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be processed without making LLM calls'
    )
    parser.add_argument(
        '--status', action='store_true',
        help='Check contextual retrieval progress and exit'
    )
    parser.add_argument(
        '--rpm', type=int, default=REQUESTS_PER_MINUTE,
        help=f'Rate limit: requests per minute (default: {REQUESTS_PER_MINUTE})'
    )
    parser.add_argument(
        '--api-base', type=str, default=_DEFAULT_API_BASE,
        help=f'REST API base URL (default: {_DEFAULT_API_BASE})'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Update runtime config from CLI args (no global mutation)
    config.api_base = args.api_base
    config.request_interval = 60.0 / args.rpm

    if args.status:
        status = check_status()
        print(json.dumps(status, indent=2))
        return

    processor = ContextualRetrievalProcessor(
        model=args.model,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    summary = processor.process_batch(offset=args.offset)
    print(json.dumps(summary, indent=2))

    # Exit code: 0 if all succeeded, 1 if any failures
    sys.exit(0 if summary['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
