#!/usr/bin/env python3
"""
RAG (Retrieval Augmented Generation) Prototype

Borrows concepts from knowledge-ai for testing:
- Query memory with hybrid search
- Retrieve relevant chunks from vector DB
- Generate answer with citations
- Cross-session learning!

Usage:
    from rag import RAG

    rag = RAG(collection='claude-memory')
    result = rag.query('How does multi-model consensus work?')
    print(result.answer)
    print(result.citations)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import sys
import os

# Import our prototypes
try:
    from vector_store import VectorStore
except ImportError:
    print("Warning: vector_store not available, using mock mode")
    VectorStore = None

try:
    from semantic_search import HybridSearch, Reranker
except ImportError:
    print("Warning: semantic_search not available, using basic search")
    HybridSearch = None
    Reranker = None


@dataclass
class RAGResult:
    """Result from RAG query"""
    query: str
    answer: str
    citations: List[Dict[str, Any]]
    context_used: List[str]
    retrieval_score: float  # How relevant were retrieved chunks


class RAG:
    """
    Retrieval Augmented Generation

    Combines:
    - Vector search (semantic)
    - Keyword search (exact matches)
    - Hybrid search (RRF)
    - Reranking (precision)
    - LLM generation (with context)
    """

    def __init__(
        self,
        collection: str = 'claude-memory',
        persist_directory: str = '~/.claude/vector_db',
        top_k: int = 5,
        verbose: bool = False
    ):
        """
        Initialize RAG

        Args:
            collection: Vector DB collection name
            persist_directory: Where vector DB is stored
            top_k: Number of chunks to retrieve
            verbose: Enable logging
        """
        self.collection = collection
        self.top_k = top_k
        self.verbose = verbose

        # Initialize vector store
        if VectorStore:
            self.vector_store = VectorStore(
                collection=collection,
                persist_directory=persist_directory,
                verbose=verbose
            )
        else:
            self.vector_store = None
            if verbose:
                print("⚠️  Vector store not available - using fallback mode")

        # Initialize search components
        if HybridSearch:
            self.hybrid_search = HybridSearch(semantic_weight=0.7, keyword_weight=0.3)
        else:
            self.hybrid_search = None

        if Reranker:
            self.reranker = Reranker()
        else:
            self.reranker = None

    def query(
        self,
        query: str,
        use_hybrid: bool = True,
        use_rerank: bool = True,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> RAGResult:
        """
        Query memory and generate answer with citations

        Args:
            query: User query
            use_hybrid: Use hybrid search (semantic + keyword)
            use_rerank: Use reranking for precision
            metadata_filter: Optional filter (e.g., {"type": "feedback"})

        Returns:
            RAGResult with answer and citations
        """
        if self.verbose:
            print(f"\n🔍 RAG Query: {query}")
            print("=" * 80)

        # Step 1: Retrieve relevant chunks
        chunks = self._retrieve_chunks(query, use_hybrid, use_rerank, metadata_filter)

        if not chunks:
            return RAGResult(
                query=query,
                answer="No relevant information found in memory.",
                citations=[],
                context_used=[],
                retrieval_score=0.0
            )

        # Step 2: Build context from chunks
        context = self._build_context(chunks)

        # Step 3: Generate answer with citations
        answer, citations = self._generate_answer(query, chunks, context)

        # Step 4: Calculate retrieval quality
        retrieval_score = self._calculate_retrieval_score(chunks)

        if self.verbose:
            print(f"\n✓ Retrieved {len(chunks)} chunks")
            print(f"✓ Retrieval score: {retrieval_score:.2f}")
            print(f"✓ Citations: {len(citations)}")

        return RAGResult(
            query=query,
            answer=answer,
            citations=citations,
            context_used=context,
            retrieval_score=retrieval_score
        )

    def _retrieve_chunks(
        self,
        query: str,
        use_hybrid: bool,
        use_rerank: bool,
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks from vector DB"""

        if not self.vector_store:
            # Fallback mode - search markdown files
            return self._fallback_search(query)

        # Vector search
        vector_results = self.vector_store.query(
            query_text=query,
            top_k=self.top_k * 2 if use_hybrid else self.top_k,  # Get more for hybrid
            where=metadata_filter
        )

        if self.verbose:
            print(f"  Vector search: {len(vector_results)} results")

        # Hybrid search (if enabled)
        if use_hybrid and self.hybrid_search:
            # TODO: Add keyword search when available
            # For now, just use vector results
            results = vector_results
        else:
            results = vector_results

        # Reranking (if enabled)
        if use_rerank and self.reranker and len(results) > self.top_k:
            if self.verbose:
                print(f"  Reranking {len(results)} → {self.top_k} results")
            results = self.reranker.rerank(query, results, top_k=self.top_k)

        return results[:self.top_k]

    def _fallback_search(self, query: str) -> List[Dict[str, Any]]:
        """Fallback: grep memory files (when vector DB unavailable)"""
        import glob
        import re

        memory_dir = os.path.expanduser('~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/memory')
        if not os.path.exists(memory_dir):
            return []

        results = []
        query_terms = query.lower().split()

        for filepath in glob.glob(f"{memory_dir}/*.md"):
            try:
                with open(filepath, 'r') as f:
                    content = f.read()

                # Simple relevance: count query term matches
                matches = sum(1 for term in query_terms if term in content.lower())
                if matches > 0:
                    results.append({
                        'id': os.path.basename(filepath),
                        'document': content[:500],  # First 500 chars
                        'metadata': {'source': filepath},
                        'similarity': matches / len(query_terms)
                    })
            except Exception as e:
                if self.verbose:
                    print(f"  Warning: Could not read {filepath}: {e}")

        # Sort by relevance
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:self.top_k]

    def _build_context(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Build context strings from chunks"""
        context = []
        for i, chunk in enumerate(chunks, 1):
            doc = chunk.get('document', '')
            metadata = chunk.get('metadata', {})
            source = metadata.get('source', metadata.get('name', f'chunk-{i}'))

            context.append(f"[{i}] {source}:\n{doc}")

        return context

    def _generate_answer(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        context: List[str]
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Generate answer from context

        NOTE: This is a MOCK - in real implementation, call LLM API
        For now, just format the retrieved chunks
        """

        # Mock answer (real implementation would call LLM)
        answer_parts = [f"Based on {len(chunks)} relevant memories:\n"]

        for i, chunk in enumerate(chunks, 1):
            doc = chunk.get('document', '')
            snippet = doc[:200] + ('...' if len(doc) > 200 else '')
            answer_parts.append(f"\n{i}. {snippet}")

        answer = '\n'.join(answer_parts)

        # Build citations
        citations = []
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get('metadata', {})
            citations.append({
                'index': i,
                'source': metadata.get('source', metadata.get('name', f'chunk-{i}')),
                'similarity': chunk.get('similarity', chunk.get('distance', 0)),
                'type': metadata.get('type', 'unknown')
            })

        return answer, citations

    def _calculate_retrieval_score(self, chunks: List[Dict[str, Any]]) -> float:
        """Calculate quality of retrieval (0-1)"""
        if not chunks:
            return 0.0

        # Average similarity/relevance
        scores = [
            chunk.get('similarity', 1 - chunk.get('distance', 0))
            for chunk in chunks
        ]

        return sum(scores) / len(scores) if scores else 0.0


if __name__ == '__main__':
    # Test RAG
    print("Testing RAG (Retrieval Augmented Generation)\n")

    rag = RAG(verbose=True)

    # Test query
    result = rag.query("How does multi-model consensus work?")

    print("\n" + "=" * 80)
    print("ANSWER:")
    print("=" * 80)
    print(result.answer)

    print("\n" + "=" * 80)
    print("CITATIONS:")
    print("=" * 80)
    for citation in result.citations:
        print(f"  [{citation['index']}] {citation['source']}")
        print(f"      Similarity: {citation['similarity']:.3f}")
        print(f"      Type: {citation['type']}")

    print(f"\nRetrieval Score: {result.retrieval_score:.3f}")
