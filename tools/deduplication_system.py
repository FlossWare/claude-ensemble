#!/usr/bin/env python3
"""
Deduplication System - Content deduplication using SHA256 + fuzzy matching
Prevents duplicate storage and identifies similar content
"""

import hashlib
import psycopg2
from typing import Optional, List, Dict, Any, Tuple

class Deduplicator:
    def __init__(self, host="aio-01", port=5433, database="learning", user="claude"):
        """Initialize connection to PostgreSQL"""
        self.conn = psycopg2.connect(host=host, port=port, database=database, user=user)
        self._ensure_schema()

    def _ensure_schema(self):
        """Create deduplication tables"""
        cursor = self.conn.cursor()

        # Create dedup schema
        cursor.execute("CREATE SCHEMA IF NOT EXISTS dedup")

        # Content hashes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dedup.content_hashes (
                hash VARCHAR(64) PRIMARY KEY,
                first_seen_id VARCHAR(255) NOT NULL,
                content_preview TEXT,
                content_length INT,
                seen_count INT DEFAULT 1,
                first_seen_at TIMESTAMP DEFAULT NOW(),
                last_seen_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Similar pairs table (fuzzy matches)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dedup.similar_pairs (
                id SERIAL PRIMARY KEY,
                hash1 VARCHAR(64) NOT NULL,
                hash2 VARCHAR(64) NOT NULL,
                similarity_score FLOAT NOT NULL,
                detected_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(hash1, hash2)
            )
        """)

        # Index for similarity lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_similar_hash1
            ON dedup.similar_pairs (hash1, similarity_score DESC)
        """)

        self.conn.commit()
        cursor.close()

    def hash_content(self, text: str) -> str:
        """
        Generate SHA256 hash of content

        Args:
            text: Content to hash

        Returns:
            Hex digest of SHA256 hash
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _simple_hash(self, text: str, ngram_size: int = 3) -> int:
        """
        Generate simple hash for fuzzy matching (simhash-like)

        Args:
            text: Text to hash
            ngram_size: Size of n-grams for hashing

        Returns:
            Integer hash value
        """
        # Normalize text
        normalized = text.lower().strip()

        # Generate n-grams
        tokens = normalized.split()
        hash_value = 0

        for i in range(len(tokens) - ngram_size + 1):
            ngram = ' '.join(tokens[i:i+ngram_size])
            ngram_hash = hash(ngram)
            hash_value ^= ngram_hash  # XOR to combine

        return hash_value

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score 0.0-1.0
        """
        # Simple Jaccard similarity on words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def check_duplicate(self, text: str, content_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if content is an exact duplicate

        Args:
            text: Content to check
            content_id: Identifier for this content

        Returns:
            (is_duplicate, original_id)
        """
        content_hash = self.hash_content(text)
        cursor = self.conn.cursor()

        # Check if hash exists
        cursor.execute(
            "SELECT first_seen_id FROM dedup.content_hashes WHERE hash = %s",
            (content_hash,)
        )
        row = cursor.fetchone()

        if row:
            # Exact duplicate found
            original_id = row[0]

            # Update seen count
            cursor.execute("""
                UPDATE dedup.content_hashes
                SET seen_count = seen_count + 1,
                    last_seen_at = NOW()
                WHERE hash = %s
            """, (content_hash,))
            self.conn.commit()
            cursor.close()

            return True, original_id
        else:
            # Not a duplicate, store hash
            preview = text[:200] if len(text) > 200 else text
            cursor.execute("""
                INSERT INTO dedup.content_hashes
                (hash, first_seen_id, content_preview, content_length)
                VALUES (%s, %s, %s, %s)
            """, (content_hash, content_id, preview, len(text)))
            self.conn.commit()
            cursor.close()

            return False, None

    def find_similar(
        self,
        text: str,
        threshold: float = 0.8,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find similar content using fuzzy matching

        Args:
            text: Content to compare
            threshold: Minimum similarity score (0.0-1.0)
            limit: Maximum number of results

        Returns:
            List of similar content with similarity scores
        """
        cursor = self.conn.cursor()

        # Get all stored content hashes
        cursor.execute("""
            SELECT hash, first_seen_id, content_preview
            FROM dedup.content_hashes
            ORDER BY last_seen_at DESC
            LIMIT 100
        """)

        similar_items = []
        current_hash = self.hash_content(text)

        for row in cursor.fetchall():
            stored_hash, stored_id, preview = row

            # Skip self
            if stored_hash == current_hash:
                continue

            # Calculate similarity
            similarity = self._calculate_similarity(text, preview)

            if similarity >= threshold:
                similar_items.append({
                    'id': stored_id,
                    'hash': stored_hash,
                    'similarity': similarity,
                    'preview': preview[:100]
                })

                # Store similar pair
                try:
                    cursor.execute("""
                        INSERT INTO dedup.similar_pairs (hash1, hash2, similarity_score)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (hash1, hash2) DO UPDATE
                        SET similarity_score = EXCLUDED.similarity_score,
                            detected_at = NOW()
                    """, (current_hash, stored_hash, similarity))
                except:
                    pass  # Ignore duplicates

        self.conn.commit()
        cursor.close()

        # Sort by similarity and limit
        similar_items.sort(key=lambda x: x['similarity'], reverse=True)
        return similar_items[:limit]

    def mark_duplicate(self, original_id: str, duplicate_id: str):
        """
        Mark content as duplicate of another

        Args:
            original_id: ID of the original content
            duplicate_id: ID of the duplicate content
        """
        cursor = self.conn.cursor()

        # Get both hashes
        cursor.execute(
            "SELECT hash FROM dedup.content_hashes WHERE first_seen_id IN (%s, %s)",
            (original_id, duplicate_id)
        )
        hashes = [row[0] for row in cursor.fetchall()]

        if len(hashes) == 2:
            cursor.execute("""
                INSERT INTO dedup.similar_pairs (hash1, hash2, similarity_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (hash1, hash2) DO NOTHING
            """, (hashes[0], hashes[1], 1.0))
            self.conn.commit()

        cursor.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_unique,
                SUM(seen_count) as total_checked,
                SUM(seen_count - 1) as duplicates_avoided,
                COUNT(*) FILTER (WHERE seen_count > 1) as items_with_duplicates
            FROM dedup.content_hashes
        """)
        row = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) FROM dedup.similar_pairs")
        similar_pairs = cursor.fetchone()[0]

        cursor.close()

        return {
            'unique_items': row[0] or 0,
            'total_checked': row[1] or 0,
            'duplicates_avoided': row[2] or 0,
            'items_with_duplicates': row[3] or 0,
            'similar_pairs': similar_pairs
        }

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Test the deduplication system"""
    print("="*60)
    print("DEDUPLICATION SYSTEM TEST")
    print("="*60)

    dedup = Deduplicator()

    # Test exact duplicates
    print("\n1. Testing exact duplicates...")
    text1 = "This is a test document for deduplication testing."
    is_dup, original = dedup.check_duplicate(text1, "doc-001")
    print(f"  First check: is_dup={is_dup}, original={original}")

    is_dup, original = dedup.check_duplicate(text1, "doc-002")
    print(f"  Second check (same text): is_dup={is_dup}, original={original}")

    # Test similar content
    print("\n2. Testing similar content...")
    text2 = "This is a test document for deduplication and similarity testing."
    is_dup, _ = dedup.check_duplicate(text2, "doc-003")
    similar = dedup.find_similar(text2, threshold=0.7)
    print(f"  Found {len(similar)} similar items:")
    for item in similar:
        print(f"    - {item['id']} (similarity: {item['similarity']:.2f})")

    # Get stats
    print("\n3. Deduplication statistics...")
    stats = dedup.get_stats()
    print(f"  Unique items: {stats['unique_items']}")
    print(f"  Total checked: {stats['total_checked']}")
    print(f"  Duplicates avoided: {stats['duplicates_avoided']}")
    print(f"  Similar pairs: {stats['similar_pairs']}")

    dedup.close()
    print("\n✅ Deduplication system test complete!")


if __name__ == "__main__":
    main()
