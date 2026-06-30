#!/usr/bin/env python3
"""
Knowledge System - Semantic search with PostgreSQL + pgvector
Stores knowledge with embeddings, provenance tracking, and semantic retrieval
"""

import psycopg2
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

class KnowledgeSystem:
    def __init__(self, host="aio-01", port=5433, database="learning", user="claude"):
        """Initialize connection to PostgreSQL"""
        self.conn = psycopg2.connect(host=host, port=port, database=database, user=user)
        self._ensure_schema()

    def _ensure_schema(self):
        """Create knowledge tables if they don't exist"""
        cursor = self.conn.cursor()

        # Knowledge entries table with pgvector
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge.entries (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector(384),
                source TEXT,
                source_type TEXT,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create HNSW index for fast similarity search
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS entries_embedding_idx
            ON knowledge.entries
            USING hnsw (embedding vector_cosine_ops)
        """)

        # Provenance tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge.provenance (
                id SERIAL PRIMARY KEY,
                entry_id INTEGER REFERENCES knowledge.entries(id) ON DELETE CASCADE,
                action TEXT NOT NULL,
                actor TEXT,
                timestamp TIMESTAMP DEFAULT NOW(),
                details JSONB
            )
        """)

        self.conn.commit()
        cursor.close()

    def generate_embedding(self, text: str) -> List[float]:
        """Generate 384-dim embedding using sentence-transformers"""
        try:
            from sentence_transformers import SentenceTransformer

            # Cache model instance
            if not hasattr(self, '_model'):
                self._model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except ImportError:
            # Fallback: zero vector if sentence-transformers not available
            print("⚠️  sentence-transformers not installed, using zero vector")
            return [0.0] * 384

    def store_knowledge(
        self,
        content: str,
        source: str,
        source_type: str = "manual",
        metadata: Optional[Dict] = None,
        actor: str = "system"
    ) -> int:
        """Store knowledge entry with embedding and provenance"""

        # Generate embedding
        embedding = self.generate_embedding(content)

        # Store entry
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO knowledge.entries
            (content, embedding, source, source_type, metadata)
            VALUES (%s, %s::vector, %s, %s, %s)
            RETURNING id
        """, (content, embedding, source, source_type, json.dumps(metadata or {})))

        entry_id = cursor.fetchone()[0]

        # Track provenance
        cursor.execute("""
            INSERT INTO knowledge.provenance
            (entry_id, action, actor, details)
            VALUES (%s, %s, %s, %s)
        """, (entry_id, 'created', actor, json.dumps({
            'source': source,
            'source_type': source_type
        })))

        self.conn.commit()
        cursor.close()

        return entry_id

    def semantic_search(
        self,
        query: str,
        limit: int = 10,
        source_type: Optional[str] = None,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Search knowledge base using semantic similarity"""

        # Generate query embedding
        query_embedding = self.generate_embedding(query)

        cursor = self.conn.cursor()

        # Build query with optional filters
        sql = """
            SELECT
                id,
                content,
                source,
                source_type,
                metadata,
                created_at,
                1 - (embedding <=> %s::vector) as similarity
            FROM knowledge.entries
            WHERE 1=1
        """
        params = [query_embedding]

        if source_type:
            sql += " AND source_type = %s"
            params.append(source_type)

        sql += """
            AND (1 - (embedding <=> %s::vector)) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        params.extend([query_embedding, min_similarity, query_embedding, limit])

        cursor.execute(sql, params)

        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'content': row[1],
                'source': row[2],
                'source_type': row[3],
                'metadata': row[4],
                'created_at': row[5],
                'similarity': float(row[6])
            })

        cursor.close()
        return results

    def get_provenance(self, entry_id: int) -> List[Dict[str, Any]]:
        """Get full provenance history for an entry"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT action, actor, timestamp, details
            FROM knowledge.provenance
            WHERE entry_id = %s
            ORDER BY timestamp DESC
        """, (entry_id,))

        provenance = []
        for row in cursor.fetchall():
            provenance.append({
                'action': row[0],
                'actor': row[1],
                'timestamp': row[2],
                'details': row[3]
            })

        cursor.close()
        return provenance

    def update_knowledge(self, entry_id: int, content: str, actor: str = "system"):
        """Update knowledge entry and track provenance"""

        # Generate new embedding
        embedding = self.generate_embedding(content)

        cursor = self.conn.cursor()

        # Update entry
        cursor.execute("""
            UPDATE knowledge.entries
            SET content = %s, embedding = %s::vector, updated_at = NOW()
            WHERE id = %s
        """, (content, embedding, entry_id))

        # Track provenance
        cursor.execute("""
            INSERT INTO knowledge.provenance
            (entry_id, action, actor, details)
            VALUES (%s, %s, %s, %s)
        """, (entry_id, 'updated', actor, json.dumps({'timestamp': datetime.now().isoformat()})))

        self.conn.commit()
        cursor.close()

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Test the knowledge system"""
    print("="*60)
    print("KNOWLEDGE SYSTEM TEST")
    print("="*60)

    ks = KnowledgeSystem()

    # Test storage
    print("\n1. Storing knowledge...")
    entry_id = ks.store_knowledge(
        content="PostgreSQL with pgvector provides fast semantic search using HNSW index",
        source="system-test",
        source_type="documentation",
        metadata={"topic": "database", "importance": "high"}
    )
    print(f"  ✓ Stored entry {entry_id}")

    # Test semantic search
    print("\n2. Semantic search...")
    results = ks.semantic_search("vector database similarity search", limit=5)
    for r in results:
        print(f"  - {r['content'][:80]}... (similarity: {r['similarity']:.3f})")

    # Test provenance
    print(f"\n3. Provenance for entry {entry_id}...")
    provenance = ks.get_provenance(entry_id)
    for p in provenance:
        print(f"  - {p['action']} by {p['actor']} at {p['timestamp']}")

    ks.close()
    print("\n✅ Knowledge system test complete!")


if __name__ == "__main__":
    main()
