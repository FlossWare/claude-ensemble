#!/usr/bin/env python3
"""
Knowledge System - Semantic search with PostgreSQL + pgvector
Stores knowledge with embeddings, provenance tracking, and semantic retrieval
IMPROVED: Uses semantic chunker for intelligent text segmentation
"""

import psycopg2
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# Import semantic chunker
sys.path.insert(0, str(Path(__file__).parent))
from semantic_chunker import SemanticChunker

class KnowledgeSystem:
    def __init__(self, host="aio-01", port=5433, database="learning", user="claude"):
        """Initialize connection to PostgreSQL"""
        self.conn = psycopg2.connect(host=host, port=port, database=database, user=user)
        self.chunker = SemanticChunker(min_chunk_size=500, max_chunk_size=1500, overlap_size=100)
        self._ensure_schema()

    def _ensure_schema(self):
        """Create knowledge tables if they don't exist"""
        cursor = self.conn.cursor()

        # Knowledge entries table with pgvector
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge.entries (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector(768),
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
                self._model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except ImportError:
            # Fallback: zero vector if sentence-transformers not available
            # Print to stderr to avoid breaking JSON parsing when called from Node.js
            import sys
            print("⚠️  sentence-transformers not installed, using zero vector", file=sys.stderr)
            return [0.0] * 384

    def store_knowledge(
        self,
        content: str,
        source: str,
        source_type: str = "manual",
        metadata: Optional[Dict] = None,
        actor: str = "system"
    ) -> int:
        """
        Store knowledge entry with embedding and provenance
        IMPROVED: Uses semantic chunking for large content (>1500 chars)

        Returns:
            Entry ID of first chunk (or single entry if not chunked)
        """

        # Check if content needs chunking
        if len(content) > 1500:
            # Use semantic chunker
            chunks = self.chunker.chunk_text(content)
            entry_ids = []

            cursor = self.conn.cursor()
            for chunk in chunks:
                # Generate embedding for chunk
                embedding = self.generate_embedding(chunk['content'])

                # Store chunk with metadata indicating it's part of larger content
                chunk_metadata = metadata.copy() if metadata else {}
                chunk_metadata.update({
                    'chunk_index': chunk['index'],
                    'total_chunks': len(chunks),
                    'chunk_type': chunk['chunk_type'],
                    'has_code': chunk['has_code'],
                    'char_count': chunk['char_count']
                })
                if chunk.get('language'):
                    chunk_metadata['language'] = chunk['language']

                cursor.execute("""
                    INSERT INTO knowledge.entries
                    (content, embedding, source, source_type, metadata)
                    VALUES (%s, %s::vector, %s, %s, %s)
                    RETURNING id
                """, (chunk['content'], embedding, source, source_type, json.dumps(chunk_metadata)))

                entry_id = cursor.fetchone()[0]
                entry_ids.append(entry_id)

                # Track provenance
                cursor.execute("""
                    INSERT INTO knowledge.provenance
                    (entry_id, action, actor, details)
                    VALUES (%s, %s, %s, %s)
                """, (entry_id, 'created', actor, json.dumps({
                    'source': source,
                    'source_type': source_type,
                    'chunk_index': chunk['index']
                })))

            self.conn.commit()
            cursor.close()

            print(f"  ✓ Stored {len(chunks)} semantic chunks (char_count: {len(content)})")
            return entry_ids[0]  # Return first chunk ID
        else:
            # Small content - store as single entry
            embedding = self.generate_embedding(content)

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
            # Handle NaN similarity (happens with zero vectors)
            similarity = row[6]
            if similarity is None or (isinstance(similarity, float) and (similarity != similarity)):  # NaN check
                similarity = 0.0
            results.append({
                'id': row[0],
                'content': row[1],
                'source': row[2],
                'source_type': row[3],
                'metadata': row[4],
                'created_at': row[5],
                'similarity': float(similarity)
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

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored knowledge"""
        cursor = self.conn.cursor()

        # Total entries
        cursor.execute("SELECT COUNT(*) FROM knowledge.entries")
        total_entries = cursor.fetchone()[0]

        # By source type
        cursor.execute("""
            SELECT source_type, COUNT(*) as count
            FROM knowledge.entries
            GROUP BY source_type
            ORDER BY count DESC
        """)

        by_source_type = {}
        for row in cursor.fetchall():
            by_source_type[row[0]] = row[1]

        cursor.close()

        return {
            'total_entries': total_entries,
            'by_source_type': by_source_type
        }


def bridge_mode(request_file: str):
    """
    Bridge mode - called from Node.js with JSON request file
    Operations: store, search, provenance, update, stats
    """
    import json

    with open(request_file) as f:
        req = json.load(f)

    operation = req['operation']
    output_file = req.get('output_file')

    ks = KnowledgeSystem()
    result = {'success': True}

    try:
        if operation == 'store':
            entry_id = ks.store_knowledge(
                content=req['content'],
                source=req['source'],
                source_type=req.get('source_type', 'manual'),
                metadata=json.loads(req.get('metadata', '{}')),
                actor=req.get('actor', 'system')
            )
            result['entry_id'] = entry_id

        elif operation == 'search':
            results = ks.semantic_search(
                query=req['query'],
                limit=req.get('limit', 10),
                source_type=req.get('source_type'),
                min_similarity=req.get('min_similarity', 0.0)
            )
            # Convert datetime to ISO string for JSON serialization
            for r in results:
                if r['created_at']:
                    r['created_at'] = r['created_at'].isoformat()
            result['results'] = results

        elif operation == 'provenance':
            provenance = ks.get_provenance(req['entry_id'])
            # Convert datetime to ISO string
            for p in provenance:
                if p['timestamp']:
                    p['timestamp'] = p['timestamp'].isoformat()
            result['provenance'] = provenance

        elif operation == 'update':
            ks.update_knowledge(
                entry_id=req['entry_id'],
                content=req['content'],
                actor=req.get('actor', 'system')
            )

        elif operation == 'stats':
            result['stats'] = ks.get_stats()

        else:
            result = {'success': False, 'error': f'Unknown operation: {operation}'}

    except Exception as e:
        result = {'success': False, 'error': str(e)}
    finally:
        ks.close()

    # Write result to output file
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f)


def main():
    """Test the knowledge system or run in bridge mode"""
    import sys

    # Bridge mode if called with request file argument
    if len(sys.argv) > 1:
        bridge_mode(sys.argv[1])
        return

    # Test mode
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

    # Test stats
    print("\n4. Statistics...")
    stats = ks.get_stats()
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  By source type: {stats['by_source_type']}")

    ks.close()
    print("\n✅ Knowledge system test complete!")


if __name__ == "__main__":
    main()
