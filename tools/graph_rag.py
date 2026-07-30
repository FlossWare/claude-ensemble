#!/usr/bin/env python3
"""
Graph RAG - Entity extraction, triple storage, and graph-enhanced retrieval.

Extracts (subject, predicate, object) triples from document chunks using free
LLMs via OpenRouter, stores them as vertices and edges in OrientDB, and provides
graph-enhanced RAG queries that combine vector similarity with multi-hop graph
traversal.

Architecture:
  - All database access via REST API at aio-01:5000 (NEVER direct connections)
  - OrientDB: aio-01:5000/graph/query (OrientDB SQL through unified API)
  - Knowledge base: aio-01:5000/knowledge/* (PostgreSQL + pgvector)
  - LLMs: OpenRouter free-tier models for entity extraction

Usage:
    # Extract triples from 100 chunks
    python3 graph_rag.py extract --batch-size 100 --limit 1000

    # Query with graph-enhanced retrieval
    python3 graph_rag.py query "What algorithms does Thompson Sampling relate to?"

    # Check extraction stats
    python3 graph_rag.py stats

    # Dry run (no LLM calls, no writes)
    python3 graph_rag.py extract --dry-run --limit 10

Author: Distributed LLM Orchestration Framework
"""

import argparse
import json
import logging
import os
import re
import socket
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

# Free models for entity extraction (ordered by preference)
DEFAULT_MODELS = [
    'google/gemma-4-26b-a4b-it:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'qwen/qwen3-coder:free',
    'nvidia/nemotron-3-nano-30b-a3b:free',
]

# Rate limiting
REQUESTS_PER_MINUTE = 20
REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0

# Batch processing
DEFAULT_BATCH_SIZE = 50
DEFAULT_LIMIT = 500
CHUNK_EXCERPT_LEN = 1500  # Max chars of chunk content sent to LLM

# OrientDB classes for Graph RAG
ENTITY_CLASS = 'Entity'
RELATION_CLASS = 'RELATED_TO'

# Allowed predicates for normalization (reviewers flagged predicate drift)
ALLOWED_PREDICATES = {
    'is_a', 'uses', 'extends', 'part_of', 'related_to', 'implements',
    'depends_on', 'created_by', 'alternative_to', 'configured_by',
    'contains', 'enables', 'requires', 'produces', 'inherits_from',
    'instance_of', 'composed_of', 'interacts_with', 'based_on',
}
PREDICATE_ALIASES = {
    'is a': 'is_a', 'is_a_type': 'is_a', 'type_of': 'is_a',
    'used_by': 'uses', 'using': 'uses', 'utilized_by': 'uses',
    'part of': 'part_of', 'component_of': 'part_of',
    'depends on': 'depends_on', 'dependency_of': 'depends_on',
    'created by': 'created_by', 'authored_by': 'created_by',
    'alternative to': 'alternative_to', 'similar_to': 'alternative_to',
    'configured by': 'configured_by', 'configures': 'configured_by',
    'based on': 'based_on', 'derived_from': 'based_on',
    'extends': 'extends', 'inherits': 'inherits_from',
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('graph-rag')

# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5, pool_maxsize=10, max_retries=0
        )
        _session.mount('http://', adapter)
        _session.mount('https://', adapter)
    return _session


# ---------------------------------------------------------------------------
# API key retrieval
# ---------------------------------------------------------------------------

def get_openrouter_api_key() -> str:
    env_key = os.environ.get('OPENROUTER_API_KEY', '')
    if env_key:
        return env_key
    try:
        resp = _get_session().get(f'{API_BASE}/secrets/OPENROUTER_API_KEY', timeout=10)
        resp.raise_for_status()
        key = resp.json().get('value', '')
        if not key:
            raise ValueError('Empty API key from secrets endpoint')
        return key
    except requests.RequestException as e:
        logger.error('Failed to fetch OpenRouter API key: %s', e)
        raise


# ---------------------------------------------------------------------------
# OrientDB helpers (all via REST API at :5000/graph/query)
# ---------------------------------------------------------------------------

# Strict allowlist for OrientDB identifiers (class names, property names)
_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')


def _validate_identifier(name: str) -> str:
    """Validate that a string is a safe OrientDB identifier.

    Raises ValueError if the name contains characters that could enable
    injection.  Only letters, digits, and underscores are permitted.
    """
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe OrientDB identifier: {name!r}")
    return name


def _escape_orient_string(value: str) -> str:
    """Escape a string value for safe embedding in OrientDB SQL.

    OrientDB uses single-quoted strings.  We escape single quotes by
    doubling them and strip any characters that could break out of the
    string context (backslashes are literal in OrientDB SQL, but we
    replace them to be safe).
    """
    if not isinstance(value, str):
        value = str(value)
    # Remove null bytes
    value = value.replace('\0', '')
    # Escape single quotes (OrientDB convention)
    value = value.replace("'", "''")
    # Remove backslashes (prevent escape-sequence tricks)
    value = value.replace('\\', '')
    # Truncate excessively long values
    return value[:2000]


def _escape_orient_like(value: str) -> str:
    """Escape a string for use inside a LIKE pattern in OrientDB SQL.

    In addition to standard string escaping, also escapes the LIKE
    wildcards ``%`` and ``_`` so they are matched literally.
    """
    escaped = _escape_orient_string(value)
    # Escape LIKE wildcards so they are treated as literal characters
    escaped = escaped.replace('%', '\\%')
    escaped = escaped.replace('_', '\\_')
    return escaped


def graph_query(sql: str) -> List[Dict]:
    """Execute an OrientDB SQL query via the REST API."""
    try:
        resp = _get_session().post(
            f'{API_BASE}/graph/query',
            json={'query': sql},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get('success', False):
            raise RuntimeError(data.get('error', 'Unknown graph query error'))
        return data.get('results', [])
    except requests.RequestException as e:
        logger.error('Graph query failed: %s (SQL: %s)', e, sql[:200])
        raise


def ensure_schema() -> None:
    """Create Entity vertex class and RELATED_TO edge class if not present."""
    for stmt in [
        f"CREATE CLASS {ENTITY_CLASS} EXTENDS V IF NOT EXISTS",
        f"CREATE CLASS {RELATION_CLASS} EXTENDS E IF NOT EXISTS",
    ]:
        try:
            graph_query(stmt)
        except Exception as e:
            # Class may already exist
            if 'already exists' not in str(e).lower():
                logger.warning('Schema creation warning: %s', e)

    # Create indexes for faster lookups
    for stmt in [
        f"CREATE INDEX Entity.name ON {ENTITY_CLASS} (name) NOTUNIQUE IF NOT EXISTS",
        f"CREATE INDEX Entity.entity_type ON {ENTITY_CLASS} (entity_type) NOTUNIQUE IF NOT EXISTS",
    ]:
        try:
            graph_query(stmt)
        except Exception as e:
            if 'already exists' not in str(e).lower():
                logger.debug('Index creation note: %s', e)


def find_or_create_entity(
    name: str,
    entity_type: str = 'concept',
    source_doc_id: Optional[int] = None,
) -> Optional[str]:
    """Find an existing entity vertex or create a new one.

    Returns the @rid of the entity, or None on failure.
    """
    safe_name = _escape_orient_string(name.lower().strip())
    safe_type = _escape_orient_string(entity_type.lower().strip())

    if not safe_name:
        return None

    # Try to find existing
    try:
        results = graph_query(
            f"SELECT @rid FROM {ENTITY_CLASS} "
            f"WHERE name = '{safe_name}'"
        )
        if results:
            rid = results[0].get('@rid')
            if rid:
                return rid
    except Exception as e:
        logger.debug('Entity lookup failed for %s: %s', safe_name, e)

    # Create new
    try:
        doc_clause = ''
        if source_doc_id is not None:
            doc_clause = f", source_doc_id = {int(source_doc_id)}"

        now_iso = datetime.now(timezone.utc).isoformat()
        results = graph_query(
            f"CREATE VERTEX {ENTITY_CLASS} SET "
            f"name = '{safe_name}', "
            f"entity_type = '{safe_type}', "
            f"created_at = '{now_iso}'"
            f"{doc_clause} "
            f"RETURN @rid"
        )
        if results:
            return results[0].get('@rid') or results[0].get('result')
        # Fallback: look it up
        results = graph_query(
            f"SELECT @rid FROM {ENTITY_CLASS} WHERE name = '{safe_name}'"
        )
        if results:
            return results[0].get('@rid')
    except Exception as e:
        logger.warning('Entity creation failed for %s: %s', safe_name, e)

    return None


def create_relation(
    from_rid: str,
    to_rid: str,
    predicate: str,
    confidence: float = 0.8,
    source_chunk_id: Optional[int] = None,
) -> bool:
    """Create an edge between two entity vertices.

    Returns True on success.
    """
    safe_pred = _escape_orient_string(predicate.lower().strip())
    if not safe_pred:
        return False

    # Validate RIDs look like OrientDB record IDs
    rid_re = re.compile(r'^#\d+:\d+$')
    if not rid_re.match(from_rid) or not rid_re.match(to_rid):
        logger.warning('Invalid RIDs: %s -> %s', from_rid, to_rid)
        return False

    try:
        # Check for duplicate edge (same subject, object, predicate)
        # to prevent redundant triples from concurrent workers
        existing = graph_query(
            f"SELECT count(*) as cnt FROM {RELATION_CLASS} "
            f"WHERE out = {from_rid} AND in = {to_rid} "
            f"AND predicate = '{safe_pred}'"
        )
        if existing and existing[0].get('cnt', 0) > 0:
            logger.debug(
                'Edge already exists: %s -[%s]-> %s',
                from_rid, safe_pred, to_rid,
            )
            return True  # Already exists, not an error

        chunk_clause = ''
        if source_chunk_id is not None:
            chunk_clause = f", source_chunk_id = {int(source_chunk_id)}"

        now_iso = datetime.now(timezone.utc).isoformat()
        graph_query(
            f"CREATE EDGE {RELATION_CLASS} FROM {from_rid} TO {to_rid} SET "
            f"predicate = '{safe_pred}', "
            f"confidence = {float(confidence)}, "
            f"created_at = '{now_iso}'"
            f"{chunk_clause}"
        )
        return True
    except Exception as e:
        logger.warning(
            'Edge creation failed %s -[%s]-> %s: %s',
            from_rid, safe_pred, to_rid, e,
        )
        return False


# ---------------------------------------------------------------------------
# Entity extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """Extract entity relationships (triples) from the following text chunk.

Return ONLY a valid JSON array of objects, each with exactly these keys:
- "subject": the source entity (a noun phrase, technology name, concept, etc.)
- "predicate": the relationship type -- MUST be one of: "is_a", "uses", "extends", "part_of", "related_to", "implements", "depends_on", "created_by", "alternative_to", "configured_by", "contains", "enables", "requires", "produces", "inherits_from", "instance_of", "composed_of", "interacts_with", "based_on"
- "object": the target entity
- "confidence": your confidence as a number between 0.0 and 1.0

Example output:
[{"subject": "thompson sampling", "predicate": "is_a", "object": "bandit algorithm", "confidence": 0.95}, {"subject": "flask", "predicate": "uses", "object": "wsgi", "confidence": 0.9}]

Rules:
1. Extract 3-10 triples per chunk (focus on the most important relationships)
2. Use concise entity names (1-4 words, lowercase, canonical form)
3. You MUST use a predicate from the list above -- do NOT invent new predicates
4. Skip trivial relationships (articles, pronouns, filler)
5. Subject and object must be different
6. If you cannot extract any triples, return an empty array: []
7. Return ONLY the JSON array, no explanation or markdown

Text chunk:
{chunk_text}

JSON array of triples:"""


# ---------------------------------------------------------------------------
# LLM-based entity extraction
# ---------------------------------------------------------------------------

def extract_triples_from_chunk(
    api_key: str,
    chunk_text: str,
    model: str,
    model_fallbacks: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Use an LLM to extract entity triples from a text chunk.

    Returns a list of dicts with keys: subject, predicate, object, confidence.
    Returns empty list on failure.
    """
    models_to_try = [model] + (model_fallbacks or [])

    prompt = EXTRACTION_PROMPT.format(
        chunk_text=chunk_text[:CHUNK_EXCERPT_LEN],
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
                        'X-Title': 'Graph RAG Entity Extraction',
                    },
                    json={
                        'model': attempt_model,
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': 1024,
                        'temperature': 0.2,
                    },
                    timeout=45,
                )

                if resp.status_code == 429:
                    retry_after = float(
                        resp.headers.get('Retry-After', RETRY_BACKOFF_BASE ** (retry + 1))
                    )
                    logger.warning(
                        'Rate limited on %s, waiting %.1fs', attempt_model, retry_after
                    )
                    time.sleep(retry_after)
                    continue

                if resp.status_code in (502, 503):
                    logger.warning('Model %s returned %d, trying next', attempt_model, resp.status_code)
                    break

                resp.raise_for_status()
                data = resp.json()
                choices = data.get('choices', [])
                if not choices:
                    break

                content = choices[0].get('message', {}).get('content', '').strip()
                if not content:
                    break

                return _parse_triples_json(content)

            except requests.Timeout:
                logger.warning('Timeout on %s (retry %d/%d)', attempt_model, retry + 1, MAX_RETRIES)
                time.sleep(RETRY_BACKOFF_BASE ** (retry + 1))
            except requests.RequestException as e:
                logger.warning('Request error on %s: %s', attempt_model, e)
                time.sleep(RETRY_BACKOFF_BASE ** (retry + 1))

    logger.error('All models failed to extract triples')
    return []


def _parse_triples_json(content: str) -> List[Dict[str, Any]]:
    """Parse the LLM response into a list of triple dicts.

    Handles markdown code fences, leading text, etc.
    """
    # Strip markdown code fences
    content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
    content = re.sub(r'```\s*$', '', content, flags=re.MULTILINE)
    content = content.strip()

    # Try to find a JSON array in the response
    # First try the whole string
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return _validate_triples(parsed)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON array from surrounding text
    match = re.search(r'\[.*\]', content, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return _validate_triples(parsed)
        except json.JSONDecodeError:
            pass

    logger.warning('Failed to parse triples JSON from LLM response')
    return []


def _normalize_predicate(pred: str) -> str:
    """Normalize a predicate to one of the allowed values.

    Checks aliases first, then checks if the predicate (with spaces
    replaced by underscores) matches an allowed predicate.  Falls back
    to 'related_to' if no match is found.
    """
    pred = pred.strip().lower()
    # Check aliases
    if pred in PREDICATE_ALIASES:
        return PREDICATE_ALIASES[pred]
    # Normalize spaces to underscores
    normalized = pred.replace(' ', '_').replace('-', '_')
    if normalized in ALLOWED_PREDICATES:
        return normalized
    # Fallback
    return 'related_to'


def _validate_triples(raw: List) -> List[Dict[str, Any]]:
    """Validate and normalize extracted triples."""
    valid = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        subj = str(item.get('subject', '')).strip().lower()
        pred = str(item.get('predicate', '')).strip().lower()
        obj = str(item.get('object', '')).strip().lower()
        try:
            conf = float(item.get('confidence', 0.8))
        except (ValueError, TypeError):
            conf = 0.8

        # Validation
        if not subj or not pred or not obj:
            continue
        if subj == obj:
            continue
        if len(subj) > 100 or len(pred) > 50 or len(obj) > 100:
            continue
        # Filter out likely noise
        noise_words = {'it', 'this', 'that', 'the', 'a', 'an', 'they', 'we', 'i',
                       'he', 'she', 'them', 'their', 'its', 'my', 'our', 'your'}
        if subj in noise_words or obj in noise_words:
            continue

        # Normalize predicate to allowed set
        pred = _normalize_predicate(pred)
        conf = max(0.0, min(1.0, conf))

        valid.append({
            'subject': subj,
            'predicate': pred,
            'object': obj,
            'confidence': round(conf, 2),
        })

    return valid


# ---------------------------------------------------------------------------
# Knowledge base helpers (via REST API)
# ---------------------------------------------------------------------------

def get_chunks_for_extraction(
    limit: int = DEFAULT_BATCH_SIZE,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Fetch chunks that have not yet been processed for triple extraction.

    Uses a tracking mechanism: chunks whose IDs appear in OrientDB Entity
    vertices (source_chunk_id) are considered processed.  We fetch chunks
    from the knowledge API and filter.
    """
    try:
        resp = _get_session().get(
            f'{API_BASE}/knowledge/embeddings/pending',
            params={'limit': 1},
            timeout=10,
        )
        # We actually want embedded chunks (those are complete), not pending ones
    except Exception:
        pass

    # Fetch chunks with content via the knowledge search endpoint
    # Use a direct query approach through the knowledge stats to find chunk range
    try:
        # Get a batch of chunks ordered by ID
        resp = _get_session().post(
            f'{API_BASE}/knowledge/search',
            json={
                'query': '*',
                'limit': limit,
                'mode': 'text',
                'min_score': 0.0,
            },
            timeout=30,
        )
        if resp.ok:
            data = resp.json()
            results = data.get('results', [])
            if results:
                return results
    except Exception as e:
        logger.debug('Search-based chunk fetch failed: %s', e)

    # Fallback: use the chunks/without-context endpoint
    try:
        resp = _get_session().get(
            f'{API_BASE}/pipeline/contextual-retrieval/chunks/without-context',
            params={'limit': limit, 'offset': offset},
            timeout=30,
        )
        if resp.ok:
            return resp.json().get('items', [])
    except Exception:
        pass

    return []


def get_processed_chunk_ids() -> set:
    """Get set of chunk IDs already processed for triples."""
    try:
        results = graph_query(
            f"SELECT source_chunk_id FROM {RELATION_CLASS} "
            f"WHERE source_chunk_id IS NOT NULL"
        )
        return {r.get('source_chunk_id') for r in results if r.get('source_chunk_id')}
    except Exception:
        return set()


def get_chunks_batch(
    limit: int = DEFAULT_BATCH_SIZE,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Fetch a batch of chunks for processing.

    Queries the pipeline endpoint for chunks with content.
    """
    try:
        resp = _get_session().get(
            f'{API_BASE}/pipeline/contextual-retrieval/chunks/without-context',
            params={'limit': limit * 2, 'offset': offset},
            timeout=30,
        )
        if resp.ok:
            items = resp.json().get('items', [])
            return items[:limit]
    except Exception:
        pass

    # Fallback to embeddings/pending
    try:
        resp = _get_session().get(
            f'{API_BASE}/knowledge/embeddings/pending',
            params={'limit': limit},
            timeout=30,
        )
        if resp.ok:
            return resp.json().get('items', [])
    except Exception:
        pass

    return []


# ---------------------------------------------------------------------------
# Graph-enhanced retrieval
# ---------------------------------------------------------------------------

def extract_query_entities(query: str) -> List[str]:
    """Extract likely entity names from a search query using simple heuristics.

    For production, this could use an LLM, but heuristics are faster and
    avoid LLM round-trips on the query path.
    """
    # Remove common stop words
    stop_words = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'can', 'shall',
        'of', 'in', 'to', 'for', 'with', 'on', 'at', 'by', 'from',
        'as', 'into', 'about', 'between', 'through', 'during', 'before',
        'after', 'and', 'but', 'or', 'not', 'no', 'nor', 'so', 'yet',
        'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
        'that', 'this', 'these', 'those', 'it', 'its', 'they', 'them',
        'does', 'relate', 'related', 'use', 'used', 'using',
    }

    # Tokenize
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9_.-]*[a-zA-Z0-9]|[a-zA-Z]', query)
    entities = []

    # Extract multi-word phrases (capitalized sequences, hyphenated, etc.)
    # Also extract individual meaningful words
    for word in words:
        lower = word.lower()
        if lower not in stop_words and len(lower) > 1:
            entities.append(lower)

    # Also try to detect compound terms
    query_lower = query.lower()
    # Common technical compound patterns
    compound_patterns = [
        r'[a-z]+[-_][a-z]+',  # hyphenated/underscored terms
        r'[A-Z][a-z]+(?:[A-Z][a-z]+)+',  # CamelCase
    ]
    for pattern in compound_patterns:
        for match in re.finditer(pattern, query):
            term = match.group().lower()
            if term not in stop_words:
                entities.append(term)

    return list(dict.fromkeys(entities))  # Deduplicate preserving order


def find_graph_entities(entity_names: List[str]) -> List[Dict[str, Any]]:
    """Find matching entity vertices in OrientDB."""
    if not entity_names:
        return []

    found = []
    for name in entity_names[:10]:  # Limit to avoid huge queries
        safe_name = _escape_orient_string(name)
        try:
            results = graph_query(
                f"SELECT @rid, name, entity_type FROM {ENTITY_CLASS} "
                f"WHERE name = '{safe_name}'"
            )
            found.extend(results)
        except Exception:
            pass

        # Also try partial matches (use LIKE-safe escaping for wildcards)
        if not results:
            safe_like = _escape_orient_like(name)
            try:
                results = graph_query(
                    f"SELECT @rid, name, entity_type FROM {ENTITY_CLASS} "
                    f"WHERE name LIKE '%{safe_like}%' LIMIT 5"
                )
                found.extend(results)
            except Exception:
                pass

    return found


def traverse_graph(
    entity_rids: List[str],
    max_depth: int = 2,
    max_results: int = 20,
) -> List[Dict[str, Any]]:
    """Traverse the graph from given entity vertices to find related entities.

    Uses OrientDB's TRAVERSE to walk edges up to max_depth hops.
    Returns related entities with their relationship paths.
    """
    if not entity_rids:
        return []

    all_related = []
    seen_rids = set()

    for rid in entity_rids[:5]:  # Limit starting points
        # Validate RID format
        if not re.match(r'^#\d+:\d+$', rid):
            continue

        try:
            # Use both() for bidirectional traversal.
            # OrientDB TRAVERSE with both() follows edges in both
            # directions, returning all connected vertices within
            # max_depth hops.  We filter to Entity class afterwards.
            results = graph_query(
                f"SELECT @rid, @class, name, entity_type "
                f"FROM (TRAVERSE both('{RELATION_CLASS}') "
                f"FROM {rid} MAXDEPTH {int(max_depth)}) "
                f"WHERE @class = '{ENTITY_CLASS}' AND @rid <> {rid} "
                f"LIMIT {int(max_results)}"
            )
            for r in results:
                r_rid = r.get('@rid')
                if r_rid and r_rid not in seen_rids:
                    seen_rids.add(r_rid)
                    all_related.append(r)
        except Exception as e:
            logger.debug('Traversal from %s failed: %s', rid, e)

    return all_related[:max_results]


def graph_enhanced_search(
    query: str,
    limit: int = 10,
    graph_expansion: bool = True,
    max_hops: int = 2,
) -> Dict[str, Any]:
    """Perform a graph-enhanced RAG query.

    1. Extract entities from the query
    2. Find matching vertices in OrientDB
    3. Traverse 1-2 hops for related entities
    4. Use related entity names to expand the vector search
    5. Return combined results

    Args:
        query: The search query
        limit: Max results to return
        graph_expansion: Whether to use graph traversal
        max_hops: Max traversal depth (1 or 2)

    Returns:
        Dict with keys: query, entities, graph_entities, related_entities,
        expanded_query, vector_results, combined_results
    """
    result = {
        'query': query,
        'entities': [],
        'graph_entities': [],
        'related_entities': [],
        'expanded_query': query,
        'vector_results': [],
        'graph_context': [],
        'combined_results': [],
        'search_time_ms': 0,
    }

    t0 = time.time()

    # Step 1: Extract entities from query
    entities = extract_query_entities(query)
    result['entities'] = entities
    logger.info('Extracted %d entities from query: %s', len(entities), entities)

    graph_entity_names = []

    if graph_expansion and entities:
        # Step 2: Find matching vertices
        graph_entities = find_graph_entities(entities)
        result['graph_entities'] = [
            {'name': e.get('name'), 'type': e.get('entity_type'), 'rid': e.get('@rid')}
            for e in graph_entities
        ]
        logger.info('Found %d matching graph entities', len(graph_entities))

        # Step 3: Traverse graph
        entity_rids = [e.get('@rid') for e in graph_entities if e.get('@rid')]
        if entity_rids:
            related = traverse_graph(entity_rids, max_depth=max_hops)
            result['related_entities'] = [
                {'name': r.get('name'), 'type': r.get('entity_type'), 'rid': r.get('@rid')}
                for r in related
            ]
            graph_entity_names = [
                r.get('name') for r in related if r.get('name')
            ]
            logger.info('Found %d related entities via traversal', len(related))

    # Step 4: Expand query with graph entity names
    if graph_entity_names:
        # Add unique related entity names to query for expanded search
        expansion_terms = list(dict.fromkeys(graph_entity_names))[:5]
        expanded = query + ' ' + ' '.join(expansion_terms)
        result['expanded_query'] = expanded
        logger.info('Expanded query: %s', expanded[:200])
    else:
        expanded = query

    # Step 5: Vector search with expanded query
    try:
        resp = _get_session().post(
            f'{API_BASE}/knowledge/search',
            json={
                'query': expanded,
                'limit': limit,
                'mode': 'hybrid',
                'rerank': False,
            },
            timeout=60,
        )
        if resp.ok:
            search_data = resp.json()
            result['vector_results'] = search_data.get('results', [])
    except Exception as e:
        logger.warning('Vector search failed: %s', e)

    # Also do original query if expanded is different
    if expanded != query:
        try:
            resp = _get_session().post(
                f'{API_BASE}/knowledge/search',
                json={'query': query, 'limit': limit, 'mode': 'hybrid'},
                timeout=60,
            )
            if resp.ok:
                original_results = resp.json().get('results', [])
                # Merge (deduplicate by chunk_id)
                seen_ids = {r.get('chunk_id') for r in result['vector_results']}
                for r in original_results:
                    if r.get('chunk_id') not in seen_ids:
                        result['vector_results'].append(r)
                        seen_ids.add(r.get('chunk_id'))
        except Exception:
            pass

    # Build graph context from entity relationships
    if result['graph_entities']:
        for ge in result['graph_entities'][:5]:
            rid = ge.get('rid')
            if rid and re.match(r'^#\d+:\d+$', rid):
                try:
                    edges = graph_query(
                        f"SELECT expand(outE('{RELATION_CLASS}')) FROM {rid} LIMIT 10"
                    )
                    for edge in edges:
                        result['graph_context'].append({
                            'from': ge.get('name'),
                            'predicate': edge.get('predicate'),
                            'to_rid': edge.get('in'),
                        })
                except Exception:
                    pass

    # Combine: vector results first, enriched with graph context
    result['combined_results'] = result['vector_results'][:limit]
    result['search_time_ms'] = round((time.time() - t0) * 1000, 1)

    return result


# ---------------------------------------------------------------------------
# Batch extraction processor
# ---------------------------------------------------------------------------

class GraphRAGExtractor:
    """Extract entity triples from document chunks and store in OrientDB."""

    def __init__(
        self,
        model: str = DEFAULT_MODELS[0],
        batch_size: int = DEFAULT_BATCH_SIZE,
        limit: int = DEFAULT_LIMIT,
        dry_run: bool = False,
    ):
        self.model = model
        self.model_fallbacks = [m for m in DEFAULT_MODELS if m != model]
        self.batch_size = batch_size
        self.limit = limit
        self.dry_run = dry_run
        self.worker_id = f'graph-rag-{socket.gethostname()}-{os.getpid()}'

        # Stats
        self.chunks_processed = 0
        self.triples_extracted = 0
        self.triples_stored = 0
        self.errors = 0
        self.skipped = 0
        self.start_time: Optional[float] = None

        self._api_key: Optional[str] = None

    @property
    def api_key(self) -> str:
        if self._api_key is None:
            self._api_key = get_openrouter_api_key()
        return self._api_key

    def run(self, offset: int = 0) -> Dict[str, Any]:
        """Run batch triple extraction.

        Returns summary statistics.
        """
        self.start_time = time.time()

        logger.info(
            'Starting Graph RAG extraction (worker=%s, model=%s, batch=%d, limit=%d, dry_run=%s)',
            self.worker_id, self.model, self.batch_size, self.limit, self.dry_run,
        )

        if not self.dry_run:
            ensure_schema()

        # Get already-processed chunk IDs
        processed_ids = get_processed_chunk_ids() if not self.dry_run else set()
        logger.info('Already processed %d chunks', len(processed_ids))

        # Fetch chunks
        total_processed = 0
        current_offset = offset

        while total_processed < self.limit:
            remaining = self.limit - total_processed
            fetch_size = min(self.batch_size, remaining)

            chunks = get_chunks_batch(
                limit=fetch_size,
                offset=current_offset,
            )

            if not chunks:
                logger.info('No more chunks to process')
                break

            for chunk in chunks:
                if total_processed >= self.limit:
                    break

                chunk_id = chunk.get('chunk_id') or chunk.get('id')
                content = chunk.get('content', '')

                if not chunk_id or not content:
                    self.skipped += 1
                    continue

                if chunk_id in processed_ids:
                    self.skipped += 1
                    continue

                if len(content.strip()) < 50:
                    self.skipped += 1
                    continue

                self._process_chunk(chunk_id, content, chunk.get('document_id'))
                total_processed += 1

                # Rate limiting
                time.sleep(REQUEST_INTERVAL)

            current_offset += len(chunks)

        return self._summary()

    def _process_chunk(
        self,
        chunk_id: int,
        content: str,
        doc_id: Optional[int] = None,
    ) -> None:
        """Extract triples from a single chunk and store them."""
        self.chunks_processed += 1

        if self.dry_run:
            logger.info(
                '[DRY RUN] Would extract triples from chunk %s (%d chars)',
                chunk_id, len(content),
            )
            self.triples_extracted += 3  # Estimate
            return

        triples = extract_triples_from_chunk(
            api_key=self.api_key,
            chunk_text=content,
            model=self.model,
            model_fallbacks=self.model_fallbacks,
        )

        if not triples:
            self.errors += 1
            logger.warning('No triples extracted from chunk %s', chunk_id)
            return

        self.triples_extracted += len(triples)
        logger.info(
            'Extracted %d triples from chunk %s', len(triples), chunk_id
        )

        # Store each triple
        for triple in triples:
            subj_rid = find_or_create_entity(
                triple['subject'],
                entity_type='concept',
                source_doc_id=doc_id,
            )
            obj_rid = find_or_create_entity(
                triple['object'],
                entity_type='concept',
                source_doc_id=doc_id,
            )

            if subj_rid and obj_rid:
                success = create_relation(
                    from_rid=subj_rid,
                    to_rid=obj_rid,
                    predicate=triple['predicate'],
                    confidence=triple['confidence'],
                    source_chunk_id=chunk_id,
                )
                if success:
                    self.triples_stored += 1

    def _summary(self) -> Dict[str, Any]:
        elapsed = time.time() - (self.start_time or time.time())
        rate = self.chunks_processed / max(elapsed, 0.001)

        summary = {
            'worker_id': self.worker_id,
            'model': self.model,
            'dry_run': self.dry_run,
            'chunks_processed': self.chunks_processed,
            'triples_extracted': self.triples_extracted,
            'triples_stored': self.triples_stored,
            'errors': self.errors,
            'skipped': self.skipped,
            'elapsed_seconds': round(elapsed, 1),
            'rate_chunks_per_second': round(rate, 3),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            'Graph RAG extraction complete: %d chunks, %d triples extracted, '
            '%d stored, %d errors, %d skipped (%.1fs)',
            self.chunks_processed, self.triples_extracted,
            self.triples_stored, self.errors, self.skipped, elapsed,
        )

        return summary


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_graph_rag_stats() -> Dict[str, Any]:
    """Get Graph RAG statistics from OrientDB."""
    stats = {
        'entity_count': 0,
        'relation_count': 0,
        'entity_types': [],
        'predicate_types': [],
        'top_entities': [],
    }

    try:
        # Entity count
        results = graph_query(f"SELECT count(*) as cnt FROM {ENTITY_CLASS}")
        if results:
            stats['entity_count'] = results[0].get('cnt', 0)

        # Relation count
        results = graph_query(f"SELECT count(*) as cnt FROM {RELATION_CLASS}")
        if results:
            stats['relation_count'] = results[0].get('cnt', 0)

        # Entity types distribution
        results = graph_query(
            f"SELECT entity_type, count(*) as cnt FROM {ENTITY_CLASS} "
            f"GROUP BY entity_type ORDER BY cnt DESC LIMIT 20"
        )
        stats['entity_types'] = [
            {'type': r.get('entity_type'), 'count': r.get('cnt')}
            for r in results
        ]

        # Predicate types distribution
        results = graph_query(
            f"SELECT predicate, count(*) as cnt FROM {RELATION_CLASS} "
            f"GROUP BY predicate ORDER BY cnt DESC LIMIT 20"
        )
        stats['predicate_types'] = [
            {'predicate': r.get('predicate'), 'count': r.get('cnt')}
            for r in results
        ]

        # Top entities by connection count
        results = graph_query(
            f"SELECT name, entity_type, both('{RELATION_CLASS}').size() as connections "
            f"FROM {ENTITY_CLASS} ORDER BY connections DESC LIMIT 20"
        )
        stats['top_entities'] = [
            {'name': r.get('name'), 'type': r.get('entity_type'),
             'connections': r.get('connections')}
            for r in results
        ]

    except Exception as e:
        stats['error'] = str(e)
        logger.error('Failed to get graph RAG stats: %s', e)

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Graph RAG: Entity extraction, triple storage, and graph-enhanced retrieval'
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # extract command
    extract_parser = subparsers.add_parser('extract', help='Extract triples from chunks')
    extract_parser.add_argument(
        '--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
        help=f'Chunks per batch (default: {DEFAULT_BATCH_SIZE})'
    )
    extract_parser.add_argument(
        '--limit', type=int, default=DEFAULT_LIMIT,
        help=f'Total chunks to process (default: {DEFAULT_LIMIT})'
    )
    extract_parser.add_argument(
        '--model', type=str, default=DEFAULT_MODELS[0],
        help=f'OpenRouter model (default: {DEFAULT_MODELS[0]})'
    )
    extract_parser.add_argument(
        '--offset', type=int, default=0,
        help='Chunk offset for resuming (default: 0)'
    )
    extract_parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be processed without LLM/DB calls'
    )
    extract_parser.add_argument(
        '--rpm', type=int, default=REQUESTS_PER_MINUTE,
        help=f'Rate limit: requests per minute (default: {REQUESTS_PER_MINUTE})'
    )

    # query command
    query_parser = subparsers.add_parser('query', help='Graph-enhanced RAG query')
    query_parser.add_argument('query_text', help='Search query')
    query_parser.add_argument(
        '--limit', type=int, default=10,
        help='Max results (default: 10)'
    )
    query_parser.add_argument(
        '--max-hops', type=int, default=2, choices=[1, 2, 3],
        help='Max graph traversal hops (default: 2)'
    )
    query_parser.add_argument(
        '--no-graph', action='store_true',
        help='Disable graph expansion (vector-only)'
    )

    # stats command
    subparsers.add_parser('stats', help='Show Graph RAG statistics')

    # Common args
    parser.add_argument(
        '--api-base', type=str, default=API_BASE,
        help=f'REST API base URL (default: {API_BASE})'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    global API_BASE, REQUEST_INTERVAL
    API_BASE = args.api_base

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == 'extract':
        REQUEST_INTERVAL = 60.0 / args.rpm
        extractor = GraphRAGExtractor(
            model=args.model,
            batch_size=args.batch_size,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        summary = extractor.run(offset=args.offset)
        print(json.dumps(summary, indent=2))
        sys.exit(0 if summary['errors'] == 0 else 1)

    elif args.command == 'query':
        result = graph_enhanced_search(
            query=args.query_text,
            limit=args.limit,
            graph_expansion=not args.no_graph,
            max_hops=args.max_hops,
        )
        print(json.dumps(result, indent=2, default=str))

    elif args.command == 'stats':
        stats = get_graph_rag_stats()
        print(json.dumps(stats, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
