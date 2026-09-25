#!/usr/bin/env python3
"""
Vector Storage - PostgreSQL + pgvector implementation

Migrated from ChromaDB to PostgreSQL + pgvector.
Drop-in replacement with same API.
"""

import psycopg2
import psycopg2.extras
from psycopg2 import sql
from typing import List, Dict, Any, Optional
import hashlib
import json
import re


class VectorStore:
    """PostgreSQL + pgvector vector storage (replaces ChromaDB)"""

    @staticmethod
    def _validate_identifier(name: str) -> str:
        """Validate an identifier to prevent SQL injection. Only letters, digits, and underscores allowed."""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            raise ValueError(f"Invalid identifier: {name}. Only letters, digits, and underscores are allowed.")
        return name

    def __init__(
        self,
        collection: str = 'claude-memory',
        host: str = 'aio-01',
        port: int = 5433,
        database: str = 'learning',
        user: str = 'sfloess',
        embedding_model: str = 'all-mpnet-base-v2',
        verbose: bool = False
    ):
        """Initialize vector store"""
        self.collection_name = self._validate_identifier(collection.replace('-', '_'))
        self.verbose = verbose
        self.embedding_dim = 1024  # nomic-embed-text-v1.5

        # Connect to PostgreSQL
        self.conn = psycopg2.connect(host=host, port=port, database=database, user=user)
        self.conn.autocommit = True

        # Build safe table/index identifiers
        table_ident = sql.Identifier('learning', f'vec_{self.collection_name}')
        index_ident = sql.Identifier(f'idx_vec_{self.collection_name}_emb')

        # Create table in learning schema
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {} (
                    id TEXT PRIMARY KEY,
                    document TEXT NOT NULL,
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    embedding vector({}),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """).format(table_ident, sql.Literal(self.embedding_dim)))

            # Create index
            cur.execute(sql.SQL("""
                CREATE INDEX IF NOT EXISTS {}
                ON {}
                USING hnsw (embedding vector_cosine_ops)
            """).format(index_ident, table_ident))

        if verbose:
            print(f"✓ Initialized: {collection} ({self._count()} docs)")

    def _generate_embedding(self, text: str) -> List[float]:
        """Use existing embedding generation from shared/generate-embeddings.py"""
        return self._generate_embeddings_batch([text])[0]

    def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding generation - much faster than individual calls"""
        import subprocess
        try:
            # generate-embeddings.py expects JSON array input, returns {"embeddings": [[...]], "dimension": 384}
            result = subprocess.run(
                ['python3', '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/generate-embeddings.py'],
                input=json.dumps(texts),
                capture_output=True,
                text=True,
                timeout=30
            )
            response = json.loads(result.stdout.strip())
            return response.get('embeddings', [[0.0] * self.embedding_dim for _ in texts])
        except Exception as e:
            if self.verbose:
                print(f"Warning: Embedding generation failed: {e}")
            return [[0.0] * self.embedding_dim for _ in texts]

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None, doc_id: Optional[str] = None) -> str:
        """Add document"""
        if doc_id is None:
            doc_id = hashlib.sha256(text.encode()).hexdigest()[:16]

        embedding = self._generate_embedding(text)

        table_ident = sql.Identifier('learning', f'vec_{self.collection_name}')
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("""
                INSERT INTO {} (id, document, metadata, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET document = EXCLUDED.document
            """).format(table_ident), (doc_id, text, json.dumps(metadata or {}), embedding))

        if self.verbose:
            print(f"✓ Added: {doc_id}")
        return doc_id

    def add_batch(self, texts: List[str], metadatas: Optional[List[Dict]] = None, doc_ids: Optional[List[str]] = None) -> List[str]:
        """Add multiple documents"""
        if doc_ids is None:
            doc_ids = [hashlib.sha256(t.encode()).hexdigest()[:16] for t in texts]

        # Use batch embedding generation for performance
        embeddings = self._generate_embeddings_batch(texts)

        table_ident = sql.Identifier('learning', f'vec_{self.collection_name}')
        query = sql.SQL("""
                INSERT INTO {} (id, document, metadata, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET document = EXCLUDED.document
            """).format(table_ident)
        with self.conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, query.as_string(self.conn),
                [(doc_id, text, json.dumps(meta or {}), emb)
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
                safe_key = self._validate_identifier(key)
                conditions.append(f"metadata->>'{safe_key}' = %s")
                where_params.append(str(value))
            where_sql = "WHERE " + " AND ".join(conditions)

        # params order: query_emb (3x), where_params..., top_k
        params = [query_emb, query_emb] + where_params + [query_emb, top_k]

        table_ident = sql.Identifier('learning', f'vec_{self.collection_name}')
        query_sql = sql.SQL("""
                SELECT id, document, metadata,
                       1 - (embedding <=> %s::vector) AS similarity,
                       embedding <=> %s::vector AS distance
                FROM {}
                {where_clause}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """).format(table_ident, where_clause=sql.SQL(where_sql))

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query_sql, params)
            results = [dict(row) for row in cur.fetchall()]

        if self.verbose:
            print(f"✓ Query: {len(results)} results")
        return results

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        table_ident = sql.Identifier('learning', f'vec_{self.collection_name}')
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql.SQL("SELECT id, document, metadata FROM {} WHERE id = %s").format(table_ident), (doc_id,))
            result = cur.fetchone()
        return dict(result) if result else None

    def delete(self, doc_id: str):
        """Delete document"""
        table_ident = sql.Identifier('learning', f'vec_{self.collection_name}')
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("DELETE FROM {} WHERE id = %s").format(table_ident), (doc_id,))
        if self.verbose:
            print(f"Deleted: {doc_id}")

    def count(self) -> int:
        """Get document count"""
        return self._count()

    def _count(self) -> int:
        table_ident = sql.Identifier('learning', f'vec_{self.collection_name}')
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(table_ident))
            return cur.fetchone()[0]

    def reset(self):
        """Delete all documents"""
        table_ident = sql.Identifier('learning', f'vec_{self.collection_name}')
        with self.conn.cursor() as cur:
            cur.execute(sql.SQL("TRUNCATE TABLE {}").format(table_ident))
        if self.verbose:
            print(f"Reset: {self.collection_name}")

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
