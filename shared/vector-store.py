#!/usr/bin/env python3
"""
Vector Storage Prototype - Test ChromaDB for .claude global memory

Borrows concepts from vectordb-ai for testing:
- Local ChromaDB storage
- Semantic embeddings (all-mpnet-base-v2)
- Similarity search
- Metadata filtering

Usage:
    from vector_store import VectorStore

    store = VectorStore(collection='claude-memory')
    store.add(text='...', metadata={'type': 'feedback', 'name': 'multi-model'})
    results = store.query('multi-model consensus', top_k=5)
"""

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib


class VectorStore:
    """
    Prototype vector storage using ChromaDB

    Tests concepts from FlossWare vectordb-ai
    """

    def __init__(
        self,
        collection: str = 'claude-memory',
        persist_directory: str = '~/.claude/vector_db',
        embedding_model: str = 'all-mpnet-base-v2',
        verbose: bool = False
    ):
        """
        Initialize vector store

        Args:
            collection: Collection name for this knowledge base
            persist_directory: Where to store ChromaDB data
            embedding_model: Sentence transformer model
            verbose: Enable logging
        """
        self.collection_name = collection
        self.verbose = verbose

        # Expand path
        persist_path = Path(persist_directory).expanduser()
        persist_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Create embedding function
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection,
            embedding_function=self.embedding_fn,
            metadata={"description": "Claude Code global memory vector storage"}
        )

        if verbose:
            print(f"✓ Initialized vector store: {collection}")
            print(f"  Path: {persist_path}")
            print(f"  Model: {embedding_model}")
            print(f"  Count: {self.collection.count()}")

    def add(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """
        Add document to vector store

        Args:
            text: Document text to embed and store
            metadata: Optional metadata (type, name, domain, etc.)
            doc_id: Optional document ID (auto-generated if not provided)

        Returns:
            Document ID
        """
        # Generate ID if not provided (hash of text)
        if doc_id is None:
            doc_id = hashlib.sha256(text.encode()).hexdigest()[:16]

        # Add to collection
        self.collection.add(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[doc_id]
        )

        if self.verbose:
            print(f"✓ Added document: {doc_id} ({len(text)} chars)")

        return doc_id

    def add_batch(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        doc_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add multiple documents in batch

        Args:
            texts: List of document texts
            metadatas: Optional list of metadata dicts
            doc_ids: Optional list of document IDs

        Returns:
            List of document IDs
        """
        # Generate IDs if not provided
        if doc_ids is None:
            doc_ids = [
                hashlib.sha256(text.encode()).hexdigest()[:16]
                for text in texts
            ]

        # Add to collection
        self.collection.add(
            documents=texts,
            metadatas=metadatas or [{} for _ in texts],
            ids=doc_ids
        )

        if self.verbose:
            print(f"✓ Added {len(texts)} documents")

        return doc_ids

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search query

        Args:
            query_text: Query text
            top_k: Number of results to return
            where: Optional metadata filter (e.g., {"type": "feedback"})

        Returns:
            List of results with document, metadata, distance
        """
        results = self.collection.query(
            query_texts=[query_text],
            n_results=top_k,
            where=where
        )

        # Format results
        formatted = []
        for i in range(len(results['ids'][0])):
            formatted.append({
                'id': results['ids'][0][i],
                'document': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i],
                'similarity': 1 - results['distances'][0][i]  # Convert distance to similarity
            })

        if self.verbose:
            print(f"✓ Query: '{query_text}' → {len(formatted)} results")

        return formatted

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get document by ID

        Args:
            doc_id: Document ID

        Returns:
            Document dict or None if not found
        """
        results = self.collection.get(ids=[doc_id])

        if not results['ids']:
            return None

        return {
            'id': results['ids'][0],
            'document': results['documents'][0],
            'metadata': results['metadatas'][0]
        }

    def delete(self, doc_id: str):
        """Delete document by ID"""
        self.collection.delete(ids=[doc_id])

        if self.verbose:
            print(f"✓ Deleted document: {doc_id}")

    def count(self) -> int:
        """Get total document count"""
        return self.collection.count()

    def reset(self):
        """Delete all documents in collection"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn
        )

        if self.verbose:
            print(f"✓ Reset collection: {self.collection_name}")


if __name__ == '__main__':
    # Test the vector store
    print("Testing ChromaDB Vector Store\n")

    store = VectorStore(verbose=True)

    # Add some test documents
    print("\n1. Adding test documents...")
    store.add(
        "Multi-model consensus uses arbiter/worker pattern for validation",
        metadata={'type': 'feedback', 'topic': 'multi-model'}
    )
    store.add(
        "Claude Code workflows use pipeline() by default, parallel() only for barriers",
        metadata={'type': 'feedback', 'topic': 'workflows'}
    )
    store.add(
        "Never create git tags - user handles all versioning",
        metadata={'type': 'feedback', 'topic': 'version-control'}
    )

    # Query
    print("\n2. Semantic search...")
    results = store.query("how does multi-model work", top_k=2)
    for r in results:
        print(f"  Similarity: {r['similarity']:.3f}")
        print(f"  Text: {r['document'][:80]}...")
        print(f"  Metadata: {r['metadata']}")
        print()

    # Filtered query
    print("3. Filtered search (type=feedback)...")
    results = store.query(
        "versioning",
        top_k=5,
        where={"type": "feedback"}
    )
    for r in results:
        print(f"  Similarity: {r['similarity']:.3f}")
        print(f"  Text: {r['document'][:80]}...")
        print()

    print(f"✓ Total documents: {store.count()}")
