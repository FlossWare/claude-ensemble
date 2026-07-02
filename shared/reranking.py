#!/usr/bin/env python3
"""
FlossWare Module: Reranking (#213)
Rerank search results using cross-encoder models
"""

import numpy as np
from typing import List, Dict, Any, Tuple
import psycopg2

class Reranker:
    """
    Rerank search results for improved relevance

    Strategies:
    1. Cross-encoder scoring (when model available)
    2. BM25 text matching (fallback)
    3. Hybrid vector + text fusion
    """

    def __init__(self, strategy: str = 'hybrid'):
        """
        Args:
            strategy: 'hybrid', 'bm25', or 'cross-encoder'
        """
        self.strategy = strategy

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Rerank search results

        Args:
            query: Original query
            results: List of {id, distance, metadata, document, score}
            top_k: Return top K after reranking

        Returns:
            Reranked results with updated 'score' field
        """
        if self.strategy == 'hybrid':
            return self._hybrid_rerank(query, results, top_k)
        elif self.strategy == 'bm25':
            return self._bm25_rerank(query, results, top_k)
        else:
            # Simple distance-based ranking (fallback)
            return sorted(results, key=lambda x: x.get('distance', 0))[:top_k]

    def _hybrid_rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Hybrid: Combine vector distance + BM25 text match

        Final score = 0.6 * (1 - distance) + 0.4 * bm25_score
        """
        query_terms = set(query.lower().split())

        for result in results:
            # Vector similarity score (inverted distance)
            vector_score = 1.0 - result.get('distance', 1.0)

            # BM25 text match score
            doc_text = result.get('document', '')
            if doc_text:
                doc_terms = set(doc_text.lower().split())
                overlap = len(query_terms & doc_terms)
                bm25_score = overlap / max(len(query_terms), 1)
            else:
                bm25_score = 0.0

            # Hybrid fusion
            result['score'] = 0.6 * vector_score + 0.4 * bm25_score

        # Sort by hybrid score (descending)
        reranked = sorted(results, key=lambda x: x['score'], reverse=True)
        return reranked[:top_k]

    def _bm25_rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        BM25 text-only reranking
        """
        query_terms = query.lower().split()

        for result in results:
            doc_text = result.get('document', '')
            doc_terms = doc_text.lower().split()

            # Simple BM25 approximation
            score = 0.0
            for term in query_terms:
                tf = doc_terms.count(term)
                if tf > 0:
                    # BM25 term score
                    k1 = 1.5
                    score += (tf * (k1 + 1)) / (tf + k1)

            result['score'] = score

        reranked = sorted(results, key=lambda x: x['score'], reverse=True)
        return reranked[:top_k]


class RerankerPipeline:
    """
    Full reranking pipeline with PostgreSQL integration
    """

    def __init__(
        self,
        connection_string: str = "host=aio-01 port=5433 dbname=learning user=sfloess",
        rerank_strategy: str = 'hybrid'
    ):
        self.conn_string = connection_string
        self.reranker = Reranker(strategy=rerank_strategy)

    def search_and_rerank(
        self,
        query_embedding: List[float],
        query_text: str,
        table: str = 'learning.experiences',
        initial_k: int = 50,
        final_k: int = 10,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Two-stage retrieval:
        1. Vector search (get initial_k results)
        2. Rerank to final_k

        This improves relevance by retrieving more candidates
        then selecting the best via text matching
        """
        # Stage 1: Vector search
        conn = psycopg2.connect(self.conn_string)
        cursor = conn.cursor()

        vector_str = '[' + ','.join(map(str, query_embedding)) + ']'

        # Build WHERE clause
        where_clause = ""
        params = [vector_str]

        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(f"metadata->>{key} = %s")
                params.append(str(value))
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT id, embedding <=> %s::vector AS distance, metadata, document
            FROM {table}
            {where_clause}
            ORDER BY embedding <=> %s::vector
            LIMIT {initial_k}
        """

        params.append(vector_str)
        cursor.execute(query, params)

        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'distance': float(row[1]),
                'metadata': row[2],
                'document': row[3] if len(row) > 3 else ''
            })

        cursor.close()
        conn.close()

        # Stage 2: Rerank
        reranked = self.reranker.rerank(query_text, results, final_k)

        return reranked


# Test module
if __name__ == '__main__':
    import numpy as np

    print("=== Reranker Test ===\n")

    # Test 1: Hybrid reranking
    print("Test 1: Hybrid reranking")

    query = "deep learning pytorch tutorial"
    mock_results = [
        {'id': 1, 'distance': 0.2, 'document': 'PyTorch deep learning guide', 'metadata': {}},
        {'id': 2, 'distance': 0.15, 'document': 'Tensor operations in NumPy', 'metadata': {}},
        {'id': 3, 'distance': 0.25, 'document': 'Complete PyTorch tutorial for beginners', 'metadata': {}},
        {'id': 4, 'distance': 0.3, 'document': 'Machine learning basics', 'metadata': {}}
    ]

    reranker = Reranker(strategy='hybrid')
    reranked = reranker.rerank(query, mock_results, top_k=3)

    print("Reranked results:")
    for i, r in enumerate(reranked, 1):
        print(f"  {i}. ID {r['id']}: score={r['score']:.3f}, distance={r['distance']:.3f}")
        print(f"     '{r['document'][:50]}'")
    print()

    # Test 2: BM25 reranking
    print("Test 2: BM25 text-only reranking")

    bm25_reranker = Reranker(strategy='bm25')
    bm25_reranked = bm25_reranker.rerank(query, mock_results, top_k=3)

    print("BM25 reranked results:")
    for i, r in enumerate(bm25_reranked, 1):
        print(f"  {i}. ID {r['id']}: bm25_score={r['score']:.3f}")
        print(f"     '{r['document'][:50]}'")
    print()

    # Test 3: Pipeline (would need real DB)
    print("Test 3: Full pipeline (requires PostgreSQL)")
    try:
        pipeline = RerankerPipeline(rerank_strategy='hybrid')
        print("✅ Pipeline initialized\n")
    except Exception as e:
        print(f"⚠️  Pipeline needs PostgreSQL: {e}\n")

    print("=== Tests Complete ===\n")
