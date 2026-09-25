"""
Intelligent Unified Search
==========================

Hybrid search over knowledge base (705K+ chunks):
  1. Semantic search via pgvector cosine similarity
  2. Keyword search via PostgreSQL tsvector/tsquery
  3. Reciprocal Rank Fusion (RRF) to merge result sets
  4. Optional cross-encoder re-ranking via external service

Also searches learning experiences, memories, and graph for comprehensive results.

Endpoints:
  GET/POST /search/intelligent - Hybrid search with optional re-ranking

Author: Distributed LLM Orchestration Framework
Last Updated: 2026-07-18
"""

import logging
import time

from flask import Blueprint, request, jsonify
import requests

logger = logging.getLogger(__name__)
intelligent_search_bp = Blueprint('intelligent_search', __name__)

BASE_URL = 'http://localhost:5000'

# Reciprocal Rank Fusion constant (higher = less weight to rank position)
RRF_K = 60


def classify_query(query: str) -> str:
    """
    Classify query type to determine optimal search strategy.

    Returns: 'factual' | 'semantic' | 'relationship' | 'mixed'
    """
    query_lower = query.lower()

    relationship_keywords = [
        'related to', 'connected to', 'depends on', 'relationship',
        'how does', 'what affects', 'impact of', 'influenced by',
    ]
    if any(kw in query_lower for kw in relationship_keywords):
        return 'relationship'

    factual_keywords = [
        'what is', 'where is', 'who is', 'when did', 'how many',
        'list', 'show me', 'find', 'configuration', 'setting',
    ]
    if any(kw in query_lower for kw in factual_keywords):
        return 'factual'

    semantic_keywords = [
        'similar to', 'like', 'reminds me of', 'comparable to',
        'explain', 'understand', 'concept', 'idea',
    ]
    if any(kw in query_lower for kw in semantic_keywords):
        return 'semantic'

    return 'mixed'


def _search_knowledge_hybrid(query, limit, rerank=False, category=None):
    """
    Hybrid search over knowledge.chunks using the /knowledge/search endpoint.

    This combines:
      - pgvector semantic similarity (1024-dim embeddings)
      - PostgreSQL full-text search (tsvector/tsquery)
      - RRF score fusion
      - Optional cross-encoder re-ranking
    """
    try:
        params = {
            'query': query,
            'limit': limit,
            'mode': 'hybrid',
            'rerank': rerank,
            'min_score': 0.0,  # Let the caller filter
        }
        if category:
            params['category'] = category

        resp = requests.post(
            f'{BASE_URL}/knowledge/search',
            json=params,
            timeout=120 if rerank else 60,
        )
        if resp.ok:
            data = resp.json()
            return {
                'status': 'success',
                'count': data.get('count', 0),
                'mode': data.get('mode', 'hybrid'),
                'results': data.get('results', []),
            }
        else:
            return {'status': f'error: HTTP {resp.status_code}', 'results': []}
    except Exception as e:
        logger.warning("Knowledge hybrid search failed: %s", e)
        return {'status': f'error: {e}', 'results': []}


def _search_memories(query, limit):
    """Search learning memories (PostgreSQL structured data)."""
    try:
        resp = requests.get(
            f'{BASE_URL}/learning/memory/search',
            params={'query': query, 'limit': limit},
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            return {
                'status': 'success',
                'results': data.get('results', data.get('memories', [])),
            }
    except Exception as e:
        logger.debug("Memory search failed: %s", e)
    return {'status': 'error', 'results': []}


def _search_experiences(query, limit):
    """Search learning experiences (vector similarity)."""
    try:
        resp = requests.get(
            f'{BASE_URL}/learning/experiences/similar',
            params={'text': query, 'limit': limit},
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            return {
                'status': 'success',
                'results': data.get('results', data.get('experiences', [])),
            }
    except Exception as e:
        logger.debug("Experience search failed: %s", e)
    return {'status': 'error', 'results': []}


def _search_graph(query, limit):
    """Search knowledge graph (OrientDB relationships)."""
    try:
        import re
        safe_query = re.sub(r'[^a-zA-Z0-9 _-]', '', query)
        resp = requests.post(
            f'{BASE_URL}/graph/query',
            json={
                'query': (
                    f"SELECT FROM V WHERE name LIKE '%{safe_query}%' "
                    f"OR description LIKE '%{safe_query}%' LIMIT {limit}"
                )
            },
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            return {
                'status': 'success',
                'results': data.get('results', []),
            }
    except Exception as e:
        logger.debug("Graph search failed: %s", e)
    return {'status': 'error', 'results': []}


def _rrf_combine(source_results, limit):
    """
    Combine results from multiple sources using Reciprocal Rank Fusion.

    Each source contributes: score = 1 / (RRF_K + rank)
    Results that appear in multiple sources get boosted.
    """
    scores = {}
    items = {}

    for source_name, source_data in source_results.items():
        results = source_data.get('results', [])
        for rank, item in enumerate(results):
            # Create a unique key per item
            if isinstance(item, dict):
                key = item.get('chunk_id') or item.get('id') or f'{source_name}_{rank}'
            else:
                key = f'{source_name}_{rank}'

            rrf_score = 1.0 / (RRF_K + rank + 1)
            scores[key] = scores.get(key, 0.0) + rrf_score

            if key not in items:
                entry = dict(item) if isinstance(item, dict) else {'data': item}
                entry['source'] = source_name
                items[key] = entry

    # Sort by combined RRF score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    combined = []
    for key, rrf_score in ranked[:limit]:
        entry = items[key]
        entry['rrf_combined_score'] = round(rrf_score, 6)
        combined.append(entry)

    return combined


@intelligent_search_bp.route('/intelligent', methods=['GET', 'POST'])
def intelligent_search():
    """
    Intelligent hybrid search across all knowledge sources.

    Combines:
      1. Knowledge base hybrid search (semantic + keyword + RRF fusion)
      2. Learning memories (structured data)
      3. Learning experiences (vector similarity)
      4. Knowledge graph (relationships)

    Optional cross-encoder re-ranking on knowledge base results.

    GET /search/intelligent?q=kubernetes+deployment&limit=10&rerank=true
    POST /search/intelligent {"query": "...", "limit": 10, "rerank": true}

    Parameters:
      q/query    - Search query (required)
      limit      - Max results per source (default: 10)
      rerank     - Enable cross-encoder re-ranking (default: false)
      category   - Filter knowledge base by category (optional)
      sources    - Comma-separated list of sources to search
                   (default: knowledge,memories,experiences,graph)

    Returns combined results ranked by relevance with source attribution.
    """
    t0 = time.time()

    # Parse parameters
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        query = data.get('query', data.get('q', ''))
        limit = int(data.get('limit', 10))
        rerank = data.get('rerank', False)
        category = data.get('category')
        sources_str = data.get('sources', 'knowledge,memories,experiences,graph')
    else:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 10))
        rerank = request.args.get('rerank', 'false').lower() == 'true'
        category = request.args.get('category')
        sources_str = request.args.get('sources', 'knowledge,memories,experiences,graph')

    if not query:
        return jsonify({'error': 'Missing query parameter (q= or query field)'}), 400

    requested_sources = [s.strip() for s in sources_str.split(',')]
    query_type = classify_query(query)

    # Determine fetch limit (over-fetch for RRF combination)
    fetch_limit = limit * 3

    # Execute searches
    source_results = {}

    if 'knowledge' in requested_sources:
        source_results['knowledge'] = _search_knowledge_hybrid(
            query, fetch_limit, rerank=rerank, category=category,
        )

    if 'memories' in requested_sources:
        source_results['memories'] = _search_memories(query, fetch_limit)

    if 'experiences' in requested_sources:
        source_results['experiences'] = _search_experiences(query, fetch_limit)

    if 'graph' in requested_sources:
        source_results['graph'] = _search_graph(query, fetch_limit)

    # Combine results using RRF
    combined = _rrf_combine(source_results, limit)

    elapsed_ms = (time.time() - t0) * 1000

    # Build response
    response = {
        'query': query,
        'query_type': query_type,
        'total_results': len(combined),
        'search_time_ms': round(elapsed_ms, 1),
        'reranked': rerank and 'knowledge' in requested_sources,
        'sources': {},
        'combined': combined,
    }

    # Include per-source summaries
    for name, data in source_results.items():
        response['sources'][name] = {
            'status': data.get('status', 'unknown'),
            'count': len(data.get('results', [])),
            'mode': data.get('mode'),
        }

    return jsonify(response)
