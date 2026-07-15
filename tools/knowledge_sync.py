#!/usr/bin/env python3
"""
Multi-Agent Knowledge Sync - Fleet-wide knowledge sharing and verification
Workers share discoveries, vote on verification, and build collective knowledge
IMPROVED: Uses semantic chunker for large discoveries
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

class KnowledgeSync:
    def __init__(self, host="aio-01", port=5433, database="learning", user="claude"):
        """Initialize connection to PostgreSQL"""
        self.conn = psycopg2.connect(host=host, port=port, database=database, user=user)
        self.chunker = SemanticChunker(min_chunk_size=500, max_chunk_size=1500, overlap_size=100)
        self._ensure_schema()

    def _ensure_schema(self):
        """Create knowledge sync tables"""
        cursor = self.conn.cursor()

        # Discoveries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge.discoveries (
                id SERIAL PRIMARY KEY,
                worker_id VARCHAR(255) NOT NULL,
                discovery_type VARCHAR(100) NOT NULL,
                content TEXT NOT NULL,
                confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
                embedding vector(768),
                verified_by TEXT[] DEFAULT ARRAY[]::TEXT[],
                verification_count INT DEFAULT 0,
                rejection_count INT DEFAULT 0,
                status VARCHAR(50) DEFAULT 'pending',
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT NOW(),
                verified_at TIMESTAMP
            )
        """)

        # Verification votes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge.verification_votes (
                id SERIAL PRIMARY KEY,
                discovery_id INT REFERENCES knowledge.discoveries(id) ON DELETE CASCADE,
                worker_id VARCHAR(255) NOT NULL,
                vote BOOLEAN NOT NULL,
                reasoning TEXT,
                voted_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(discovery_id, worker_id)
            )
        """)

        # Index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_discoveries_status
            ON knowledge.discoveries (status, confidence DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_discoveries_worker
            ON knowledge.discoveries (worker_id, created_at DESC)
        """)

        self.conn.commit()
        cursor.close()

    def generate_embedding(self, text: str) -> List[float]:
        """Generate 384-dim embedding (placeholder - uses knowledge_system.py if available)"""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent))
            from knowledge_system import KnowledgeSystem

            ks = KnowledgeSystem()
            embedding = ks.generate_embedding(text)
            ks.close()
            return embedding
        except Exception as e:
            # Fallback: zero vector
            # Send warning to stderr, not stdout (to avoid breaking JSON parsing)
            import sys
            print(f"⚠️  Embedding generation failed: {str(e)}, using zero vector", file=sys.stderr)
            return [0.0] * 384

    def share_discovery(
        self,
        worker_id: str,
        discovery_type: str,
        content: str,
        confidence: float = 0.8
    ) -> int:
        """
        Share a new discovery with the fleet
        IMPROVED: Uses semantic chunking for large discoveries (>1500 chars)

        Args:
            worker_id: ID of the worker making the discovery
            discovery_type: Type of discovery (e.g., 'pattern', 'optimization', 'bug')
            content: Description of the discovery
            confidence: Confidence score 0.0-1.0

        Returns:
            Discovery ID (first chunk if content is chunked)
        """
        cursor = self.conn.cursor()

        # Check if content needs chunking
        if len(content) > 1500:
            # Use semantic chunker
            chunks = self.chunker.chunk_text(content)
            discovery_ids = []

            for chunk in chunks:
                # Generate embedding for chunk
                embedding = self.generate_embedding(chunk['content'])

                cursor.execute("""
                    INSERT INTO knowledge.discoveries
                    (worker_id, discovery_type, content, confidence, embedding)
                    VALUES (%s, %s, %s, %s, %s::vector)
                    RETURNING id
                """, (worker_id, f"{discovery_type}_chunk_{chunk['index']}", chunk['content'], confidence, embedding))

                discovery_ids.append(cursor.fetchone()[0])

            self.conn.commit()
            cursor.close()

            print(f"  ✓ Shared discovery as {len(chunks)} semantic chunks")
            return discovery_ids[0]  # Return first chunk ID
        else:
            # Small content - store as single discovery
            embedding = self.generate_embedding(content)

            cursor.execute("""
                INSERT INTO knowledge.discoveries
                (worker_id, discovery_type, content, confidence, embedding)
                VALUES (%s, %s, %s, %s, %s::vector)
                RETURNING id
            """, (worker_id, discovery_type, content, confidence, embedding))

            discovery_id = cursor.fetchone()[0]
            self.conn.commit()
            cursor.close()

            return discovery_id

    def verify_discovery(
        self,
        discovery_id: int,
        worker_id: str,
        approve: bool,
        reasoning: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Vote on a discovery's validity with IMPROVED concurrency handling

        Args:
            discovery_id: ID of the discovery to verify
            worker_id: ID of the worker voting
            approve: True to approve, False to reject
            reasoning: Optional explanation for the vote

        Returns:
            Dict with verification status
        """
        # Use SERIALIZABLE isolation for concurrent safety
        cursor = self.conn.cursor()

        try:
            # Set transaction isolation level
            cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")

            # Lock the discovery row for update
            cursor.execute("""
                SELECT id, verification_count, rejection_count, status
                FROM knowledge.discoveries
                WHERE id = %s
                FOR UPDATE
            """, (discovery_id,))

            discovery = cursor.fetchone()
            if not discovery:
                self.conn.rollback()
                cursor.close()
                return {'error': 'Discovery not found'}

            # Record the vote (atomic upsert)
            cursor.execute("""
                INSERT INTO knowledge.verification_votes
                (discovery_id, worker_id, vote, reasoning)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (discovery_id, worker_id) DO UPDATE
                SET vote = EXCLUDED.vote,
                    reasoning = EXCLUDED.reasoning,
                    voted_at = NOW()
            """, (discovery_id, worker_id, approve, reasoning))

            # Atomically update counts
            cursor.execute("""
                UPDATE knowledge.discoveries
                SET verified_by = CASE
                        WHEN %s = ANY(verified_by) THEN verified_by
                        ELSE ARRAY_APPEND(verified_by, %s)
                    END,
                    verification_count = (
                        SELECT COUNT(*) FROM knowledge.verification_votes
                        WHERE discovery_id = %s AND vote = TRUE
                    ),
                    rejection_count = (
                        SELECT COUNT(*) FROM knowledge.verification_votes
                        WHERE discovery_id = %s AND vote = FALSE
                    )
                WHERE id = %s
                RETURNING verification_count, rejection_count, status
            """, (worker_id, worker_id, discovery_id, discovery_id, discovery_id))

            row = cursor.fetchone()
            verifications, rejections, current_status = row

            # Check threshold and update status (atomic)
            new_status = current_status
            if verifications >= 3 and current_status == 'pending':
                cursor.execute("""
                    UPDATE knowledge.discoveries
                    SET status = 'verified', verified_at = NOW()
                    WHERE id = %s AND status = 'pending'
                    RETURNING status
                """, (discovery_id,))
                result = cursor.fetchone()
                if result:
                    new_status = result[0]

            elif rejections >= 3 and current_status == 'pending':
                cursor.execute("""
                    UPDATE knowledge.discoveries
                    SET status = 'rejected'
                    WHERE id = %s AND status = 'pending'
                    RETURNING status
                """, (discovery_id,))
                result = cursor.fetchone()
                if result:
                    new_status = result[0]

            self.conn.commit()
            cursor.close()

            return {
                'discovery_id': discovery_id,
                'verifications': verifications,
                'rejections': rejections,
                'status': new_status
            }

        except Exception as e:
            self.conn.rollback()
            cursor.close()
            return {'error': f'Verification failed: {str(e)}'}

    def get_fleet_knowledge(
        self,
        min_confidence: float = 0.7,
        discovery_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get verified knowledge from the fleet

        Args:
            min_confidence: Minimum confidence score
            discovery_type: Optional filter by type
            limit: Maximum results

        Returns:
            List of verified discoveries
        """
        cursor = self.conn.cursor()

        sql = """
            SELECT
                id,
                worker_id,
                discovery_type,
                content,
                confidence,
                verification_count,
                verified_by,
                created_at,
                verified_at
            FROM knowledge.discoveries
            WHERE status = 'verified'
              AND confidence >= %s
        """
        params = [min_confidence]

        if discovery_type:
            sql += " AND discovery_type = %s"
            params.append(discovery_type)

        sql += " ORDER BY confidence DESC, verification_count DESC LIMIT %s"
        params.append(limit)

        cursor.execute(sql, params)

        discoveries = []
        for row in cursor.fetchall():
            discoveries.append({
                'id': row[0],
                'worker_id': row[1],
                'type': row[2],
                'content': row[3],
                'confidence': row[4],
                'verifications': row[5],
                'verified_by': row[6],
                'created_at': row[7],
                'verified_at': row[8]
            })

        cursor.close()
        return discoveries

    def get_pending_discoveries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get discoveries pending verification"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                id,
                worker_id,
                discovery_type,
                content,
                confidence,
                verification_count,
                rejection_count,
                created_at
            FROM knowledge.discoveries
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))

        pending = []
        for row in cursor.fetchall():
            pending.append({
                'id': row[0],
                'worker_id': row[1],
                'type': row[2],
                'content': row[3][:100] + '...' if len(row[3]) > 100 else row[3],
                'confidence': row[4],
                'verifications': row[5],
                'rejections': row[6],
                'created_at': row[7]
            })

        cursor.close()
        return pending

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge sync statistics"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'verified') as verified,
                COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
                COUNT(*) as total,
                COUNT(DISTINCT worker_id) as active_workers
            FROM knowledge.discoveries
        """)
        row = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) FROM knowledge.verification_votes")
        total_votes = cursor.fetchone()[0]

        cursor.close()

        return {
            'pending': row[0],
            'verified': row[1],
            'rejected': row[2],
            'total': row[3],
            'active_workers': row[4],
            'total_votes': total_votes
        }

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Test the knowledge sync system"""
    print("="*60)
    print("MULTI-AGENT KNOWLEDGE SYNC TEST")
    print("="*60)

    ks = KnowledgeSync()

    # Worker 1 shares discoveries
    print("\n1. Worker-01 sharing discoveries...")
    disc1 = ks.share_discovery(
        'worker-01',
        'optimization',
        'Using batch processing for embeddings reduces API calls by 80%',
        confidence=0.9
    )
    disc2 = ks.share_discovery(
        'worker-01',
        'pattern',
        'PostgreSQL HNSW index provides 2x faster similarity search than sequential scan',
        confidence=0.85
    )
    print(f"  ✓ Shared discoveries: {disc1}, {disc2}")

    # Other workers verify
    print("\n2. Fleet verification...")
    result = ks.verify_discovery(disc1, 'worker-02', approve=True, reasoning="Confirmed in testing")
    print(f"  Worker-02 verified: {result}")

    result = ks.verify_discovery(disc1, 'worker-03', approve=True, reasoning="Observed same pattern")
    print(f"  Worker-03 verified: {result}")

    result = ks.verify_discovery(disc1, 'worker-04', approve=True, reasoning="Reproduced results")
    print(f"  Worker-04 verified: {result}")

    # Get fleet knowledge
    print("\n3. Fleet knowledge (verified)...")
    knowledge = ks.get_fleet_knowledge(min_confidence=0.7)
    for k in knowledge:
        print(f"  - [{k['type']}] {k['content'][:60]}... (confidence: {k['confidence']:.2f}, verified by {k['verifications']} workers)")

    # Get pending
    print("\n4. Pending verification...")
    pending = ks.get_pending_discoveries()
    for p in pending:
        print(f"  - {p['content']} (votes: {p['verifications']}/{p['rejections']})")

    # Get stats
    print("\n5. Knowledge sync statistics...")
    stats = ks.get_stats()
    print(f"  Total discoveries: {stats['total']}")
    print(f"  Verified: {stats['verified']}, Pending: {stats['pending']}, Rejected: {stats['rejected']}")
    print(f"  Active workers: {stats['active_workers']}")
    print(f"  Total votes cast: {stats['total_votes']}")

    ks.close()
    print("\n✅ Knowledge sync test complete!")


if __name__ == "__main__":
    main()
