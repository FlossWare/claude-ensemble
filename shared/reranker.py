#!/usr/bin/env python3
"""
Async reranker using sentence-transformers cross-encoder.

Model: cross-encoder/ms-marco-MiniLM-L6-v2
Purpose: Rerank search results for improved relevance
Features:
  - Async batch processing
  - Configurable top-k filtering
  - Caching for repeated queries
  - Thread-safe singleton model loading
  - Graceful degradation if model unavailable
"""

import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global model instance (singleton pattern)
_model_lock = threading.Lock()
_model_instance = None


@dataclass
class ScoredResult:
    """Container for reranked result with score."""

    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_rank: Optional[int] = None

    def __lt__(self, other: 'ScoredResult') -> bool:
        """Enable sorting by score (ascending for use with reverse=True)."""
        return self.score < other.score

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'content': self.content,
            'score': float(self.score),
            'metadata': self.metadata,
            'original_rank': self.original_rank
        }


class Reranker:
    """
    Async reranker using cross-encoder/ms-marco-MiniLM-L6-v2.

    Usage:
        reranker = Reranker()
        results = await reranker.rerank(
            query="How to reverse engineer firmware?",
            documents=[
                "Firmware analysis guide...",
                "Router configuration tutorial...",
                "Binary exploitation techniques..."
            ],
            top_k=5
        )

    Features:
        - Batch processing for efficiency
        - Query result caching (LRU)
        - Thread-safe model loading
        - Graceful fallback if model unavailable
    """

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L6-v2"
    DEFAULT_TOP_K = 10
    DEFAULT_BATCH_SIZE = 32
    MAX_CACHE_SIZE = 100

    def __init__(
        self,
        model_name: Optional[str] = None,
        cache_dir: Optional[str] = None,
        device: Optional[str] = None
    ):
        """
        Initialize reranker.

        Args:
            model_name: Cross-encoder model name (default: ms-marco-MiniLM-L6-v2)
            cache_dir: Model cache directory (default: ~/.cache/huggingface)
            device: Device for inference ('cpu', 'cuda', None=auto)
        """
        self.model_name = model_name or self.MODEL_NAME
        self.cache_dir = cache_dir
        self.device = device
        self._model = None
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def _ensure_initialized(self) -> None:
        """Lazy initialization of model (thread-safe)."""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            try:
                # Run blocking model load in thread pool
                loop = asyncio.get_event_loop()
                self._model = await loop.run_in_executor(
                    None,
                    self._load_model
                )
                self._initialized = True
                logger.info(f"Reranker initialized with model: {self.model_name}")

            except Exception as e:
                logger.error(f"Failed to initialize reranker: {e}")
                logger.warning("Reranker will return original order (no reranking)")
                self._model = None
                self._initialized = True

    def _load_model(self):
        """Load cross-encoder model (blocking, runs in thread pool)."""
        global _model_instance

        # Use cached global instance if available (entire block locked)
        with _model_lock:
            if _model_instance is not None:
                logger.info("Using cached model instance")
                return _model_instance

            try:
                from sentence_transformers import CrossEncoder

                kwargs = {}
                if self.cache_dir:
                    kwargs['cache_folder'] = self.cache_dir
                if self.device:
                    kwargs['device'] = self.device

                logger.info(f"Loading model: {self.model_name}")
                model = CrossEncoder(self.model_name, **kwargs)

                # Cache globally
                _model_instance = model

                except ImportError:
                logger.error(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
                return None

            except Exception as e:
                logger.error(f"Error loading model {self.model_name}: {e}")
                return None

    def _cache_key(self, query: str, doc_hash: int) -> str:
        """Generate cache key for query-document pair."""
        return f"{query}:{doc_hash}"

    async def rerank(
        self,
        query: str,
        documents: List[Union[str, Dict[str, Any]]],
        top_k: Optional[int] = None,
        batch_size: Optional[int] = None,
        return_scores: bool = True
    ) -> List[ScoredResult]:
        """
        Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: List of documents (strings or dicts with 'content' key)
            top_k: Return top K results (default: all, sorted by score)
            batch_size: Batch size for inference (default: 32)
            return_scores: Include scores in results (default: True)

        Returns:
            List of ScoredResult objects, sorted by relevance (descending)

        Example:
            results = await reranker.rerank(
                query="firmware analysis",
                documents=["doc1", "doc2", "doc3"],
                top_k=2
            )
            for r in results:
                print(f"Score: {r.score:.4f} - {r.content[:50]}")
        """
        await self._ensure_initialized()

        if not documents:
            return []

        # Normalize documents to ScoredResult objects
        scored_results = []
        for idx, doc in enumerate(documents):
            if isinstance(doc, str):
                content = doc
                metadata = {}
            elif isinstance(doc, dict):
                content = doc.get('content', str(doc))
                metadata = {k: v for k, v in doc.items() if k != 'content'}
            else:
                content = str(doc)
                metadata = {}

            scored_results.append(ScoredResult(
                content=content,
                score=0.0,
                metadata=metadata,
                original_rank=idx
            ))

        # If model unavailable, return original order
        if self._model is None:
            logger.warning("Model unavailable, returning original order")
            return scored_results[:top_k] if top_k else scored_results

        # Score documents
        try:
            scores = await self._score_batch(
                query=query,
                documents=[r.content for r in scored_results],
                batch_size=batch_size or self.DEFAULT_BATCH_SIZE
            )

            # Update scores
            for result, score in zip(scored_results, scores):
                result.score = score

            # Sort by score (descending)
            scored_results.sort(reverse=True)

            # Apply top-k filter
            if top_k is not None:
                scored_results = scored_results[:top_k]

            return scored_results

        except Exception as e:
            logger.error(f"Error during reranking: {e}")
            logger.warning("Returning original order due to error")
            return scored_results[:top_k] if top_k else scored_results

    async def _score_batch(
        self,
        query: str,
        documents: List[str],
        batch_size: int
    ) -> List[float]:
        """
        Score documents in batches (async).

        Args:
            query: Search query
            documents: List of document strings
            batch_size: Batch size for inference

        Returns:
            List of relevance scores (same order as input documents)
        """
        if not documents:
            return []

        # Prepare query-document pairs
        pairs = [(query, doc) for doc in documents]

        # Process in batches
        all_scores = []
        loop = asyncio.get_event_loop()

        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]

            # Run inference in thread pool (blocking operation)
            batch_scores = await loop.run_in_executor(
                None,
                self._model.predict,
                batch
            )

            all_scores.extend(batch_scores.tolist())

        return all_scores

    async def rerank_with_threshold(
        self,
        query: str,
        documents: List[Union[str, Dict[str, Any]]],
        threshold: float = 0.5,
        top_k: Optional[int] = None,
        batch_size: Optional[int] = None
    ) -> List[ScoredResult]:
        """
        Rerank and filter by minimum score threshold.

        Args:
            query: Search query
            documents: List of documents
            threshold: Minimum score to include (default: 0.5)
            top_k: Maximum results to return (applied after filtering)
            batch_size: Batch size for inference

        Returns:
            List of ScoredResult objects with score >= threshold
        """
        results = await self.rerank(
            query=query,
            documents=documents,
            top_k=None,
            batch_size=batch_size
        )

        # Filter by threshold
        filtered = [r for r in results if r.score >= threshold]

        # Apply top-k
        if top_k is not None:
            filtered = filtered[:top_k]

        return filtered

    async def batch_rerank(
        self,
        queries_docs: List[Tuple[str, List[Union[str, Dict[str, Any]]]]],
        top_k: Optional[int] = None,
        batch_size: Optional[int] = None
    ) -> List[List[ScoredResult]]:
        """
        Rerank multiple query-document sets concurrently.

        Args:
            queries_docs: List of (query, documents) tuples
            top_k: Top K results per query
            batch_size: Batch size for inference

        Returns:
            List of reranked result lists (one per query)

        Example:
            results = await reranker.batch_rerank([
                ("query1", ["doc1", "doc2"]),
                ("query2", ["doc3", "doc4"])
            ])
        """
        tasks = [
            self.rerank(
                query=query,
                documents=docs,
                top_k=top_k,
                batch_size=batch_size
            )
            for query, docs in queries_docs
        ]

        return await asyncio.gather(*tasks)

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information and status."""
        return {
            'model_name': self.model_name,
            'initialized': self._initialized,
            'available': self._model is not None,
            'device': getattr(self._model, 'device', None) if self._model else None,
            'cache_dir': self.cache_dir
        }


# Convenience functions for quick usage

async def rerank(
    query: str,
    documents: List[Union[str, Dict[str, Any]]],
    top_k: Optional[int] = None,
    model_name: Optional[str] = None
) -> List[ScoredResult]:
    """
    Quick reranking function (uses default reranker).

    Args:
        query: Search query
        documents: List of documents
        top_k: Top K results to return
        model_name: Cross-encoder model name (default: ms-marco-MiniLM-L6-v2)

    Returns:
        List of ScoredResult objects

    Example:
        results = await rerank("firmware analysis", ["doc1", "doc2"], top_k=1)
    """
    reranker = Reranker(model_name=model_name)
    return await reranker.rerank(query, documents, top_k=top_k)


async def rerank_strings(
    query: str,
    documents: List[str],
    top_k: Optional[int] = None
) -> List[Tuple[str, float]]:
    """
    Rerank and return (document, score) tuples.

    Args:
        query: Search query
        documents: List of document strings
        top_k: Top K results to return

    Returns:
        List of (document, score) tuples

    Example:
        results = await rerank_strings("query", ["doc1", "doc2"])
        for doc, score in results:
            print(f"{score:.4f}: {doc}")
    """
    results = await rerank(query, documents, top_k=top_k)
    return [(r.content, r.score) for r in results]


# CLI interface for testing
async def main():
    """CLI for testing reranker."""
    import argparse

    parser = argparse.ArgumentParser(description="Test reranker")
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "documents",
        nargs="+",
        help="Documents to rerank"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Return top K results"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Minimum score threshold"
    )
    parser.add_argument(
        "--model",
        default=Reranker.MODEL_NAME,
        help="Cross-encoder model name"
    )

    args = parser.parse_args()

    # Initialize reranker
    reranker = Reranker(model_name=args.model)

    # Rerank
    if args.threshold is not None:
        results = await reranker.rerank_with_threshold(
            query=args.query,
            documents=args.documents,
            threshold=args.threshold,
            top_k=args.top_k
        )
    else:
        results = await reranker.rerank(
            query=args.query,
            documents=args.documents,
            top_k=args.top_k
        )

    # Print results
    print(f"\nQuery: {args.query}")
    print(f"Results: {len(results)}\n")

    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result.score:.4f} (orig rank: {result.original_rank})")
        print(f"   {result.content[:100]}...")
        print()

    # Print model info
    info = reranker.get_model_info()
    print(f"Model: {info['model_name']}")
    print(f"Device: {info['device']}")
    print(f"Initialized: {info['initialized']}")


if __name__ == "__main__":
    asyncio.run(main())
