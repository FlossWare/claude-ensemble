#!/usr/bin/env python3
"""
Vector Storage - PostgreSQL + pgvector implementation

Migrated from ChromaDB to PostgreSQL + pgvector.
Drop-in replacement with same API.
"""

import psycopg2
import psycopg2.extras
from typing import List, Dict, Any, Optional
import hashlib
import json


class VectorStore:
    """PostgreSQL + pgvector vector storage (replaces ChromaDB)"""

    def __init__(
        self,
        collection: str = 'claude-memory',
        host: str = 'aio-01',
        port: int = 5433,
        database: str = 'learning',
        user: str = 'sfloess',
        embedding_model: str = 'all-MiniLM-L6-v2',
        verbose: bool = False
    ):
        """Initialize vector store"""
        self.collection_name = collection.replace('-', '_')
        self.verbose = verbose
        self.embedding_dim = 384  # all-MiniLM-L6-v2

        # Connect to PostgreSQL
        self.conn = psycopg2.connect(host=host, port=port, database=database, user=user)
        self.conn.autocommit = True

        # Create table in learning schema
        with self.conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS learning.vec_{self.collection_name} (
                    id TEXT PRIMARY KEY,
                    document TEXT NOT NULL,
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    embedding vector({self.embedding_dim}),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Create index
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_vec_{self.collection_name}_emb
                ON learning.vec_{self.collection_name}
                USING hnsw (embedding vector_cosine_ops)
            """)

        if verbose:
            print(f"✓ Initialized: {collection} ({self._count()} docs)")

    def _generate_embedding(self, text: str) -> List[float]:
        """Use existing embedding generation from shared/generate-embeddings.py"""
        import subprocess
        try:
            # generate-embeddings.py expects JSON array input, returns {"embeddings": [[...]], "dimension": 384}
            result = subprocess.run(
                ['python3', '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/generate-embeddings.py'],
                input=json.dumps([text]),
                capture_output=True,
                text=True,
                timeout=10
            )
            response = json.loads(result.stdout.strip())
            return response['embeddings'][0] if response.get('embeddings') else [0.0] * self.embedding_dim
        except:
            return [0.0] * self.embedding_dim

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None, doc_id: Optional[str] = None) -> str:
        """Add document"""
        if doc_id is None:
            doc_id = hashlib.sha256(text.encode()).hexdigest()[:16]

        embedding = self._generate_embedding(text)

        with self.conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO learning.vec_{self.collection_name} (id, document, metadata, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET document = EXCLUDED.document
            """, (doc_id, text, json.dumps(metadata or {}), embedding))

        if self.verbose:
            print(f"✓ Added: {doc_id}")
        return doc_id

    def add_batch(self, texts: List[str], metadatas: Optional[List[Dict]] = None, doc_ids: Optional[List[str]] = None) -> List[str]:
        """Add multiple documents"""
        if doc_ids is None:
            doc_ids = [hashlib.sha256(t.encode()).hexdigest()[:16] for t in texts]

        embeddings = [self._generate_embedding(t) for t in texts]

        with self.conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, f"""
                INSERT INTO learning.vec_{self.collection_name} (id, document, metadata, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET document = EXCLUDED.document
            """, [(doc_id, text, json.dumps(meta or {}), emb)
                  for doc_id, text, meta, emb in zip(doc_ids, texts, metadatas or [{} for _ in texts], embeddings)])

        if self.verbose:
            print(f"✓ Added {len(texts)} docs")
        return doc_ids

    def query(self, query_text: str, top_k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Semantic search"""
        query_emb = self._generate_embedding(query_text)

        # Build WHERE clause and params
        where_sql = ""
        where_params = []

        if where:
            conditions = []
            for key, value in where.items():
                conditions.append(f"metadata->>'{key}' = %s")
                where_params.append(str(value))
            where_sql = "WHERE " + " AND ".join(conditions)

        # params order: query_emb (3x), where_params..., top_k
        params = [query_emb, query_emb] + where_params + [query_emb, top_k]

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT id, document, metadata,
                       1 - (embedding <=> %s::vector) AS similarity,
                       embedding <=> %s::vector AS distance
                FROM learning.vec_{self.collection_name}
                {where_sql}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, params)
            results = [dict(row) for row in cur.fetchall()]

        if self.verbose:
            print(f"✓ Query: {len(results)} results")
        return results

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT id, document, metadata FROM learning.vec_{self.collection_name} WHERE id = %s", (doc_id,))
            result = cur.fetchone()
        return dict(result) if result else None

    def delete(self, doc_id: str):
        """Delete document"""
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM learning.vec_{self.collection_name} WHERE id = %s", (doc_id,))
        if self.verbose:
            print(f"✓ Deleted: {doc_id}")

    def count(self) -> int:
        """Get document count"""
        return self._count()

    def _count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM learning.vec_{self.collection_name}")
            return cur.fetchone()[0]

    def reset(self):
        """Delete all documents"""
        with self.conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE learning.vec_{self.collection_name}")
        if self.verbose:
            print(f"✓ Reset: {self.collection_name}")

    def close(self):
        """Close connection"""
        self.conn.close()


if __name__ == '__main__':
    print("Testing PostgreSQL Vector Store\n")

    store = VectorStore(verbose=True)

    print("\n1. Adding test documents...")
    store.add(
        "Multi-model consensus uses arbiter/worker pattern",
        metadata={'type': 'feedback', 'topic': 'multi-model'}
    )
    store.add(
        "Claude Code workflows use pipeline() by default",
        metadata={'type': 'feedback', 'topic': 'workflows'}
    )
    store.add(
        "Never create git tags - user handles versioning",
        metadata={'type': 'feedback', 'topic': 'version-control'}
    )

    print("\n2. Semantic search...")
    results = store.query("how does multi-model work", top_k=2)
    for r in results:
        print(f"  Similarity: {r['similarity']:.3f}")
        print(f"  Text: {r['document'][:60]}...")
        print()

    print("3. Filtered search...")
    results = store.query("versioning", top_k=5, where={"type": "feedback"})
    for r in results:
        print(f"  Similarity: {r['similarity']:.3f}")
        print(f"  Text: {r['document'][:60]}...")
        print()

    print(f"✓ Total: {store.count()}")
    store.close()
