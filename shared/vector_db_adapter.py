#!/usr/bin/env python3
"""
FlossWare Module: Vector DB Adapter (#210)
Unified interface for PostgreSQL pgvector
"""

import psycopg2
import json
from typing import List, Dict, Any, Optional

class VectorDBAdapter:
    """
    Unified interface for vector database operations
    Currently supports: PostgreSQL with pgvector extension
    """

    def __init__(self, connection_string: str = "host=aio-01 port=5433 dbname=learning user=sfloess"):
        self.conn_string = connection_string
        self.conn = None

    def connect(self):
        """Establish database connection"""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(self.conn_string)
        return self.conn

    def disconnect(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def insert_embedding(
        self,
        table: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        text: Optional[str] = None
    ) -> int:
        """
        Insert embedding with metadata

        Args:
            table: Table name (e.g., 'learning.experiences')
            embedding: Vector embedding
            metadata: JSONB metadata
            text: Optional text document

        Returns:
            Inserted row ID
        """
        import re
        from psycopg2 import sql

        conn = self.connect()
        cursor = conn.cursor()

        # Validate table name (alphanumeric, underscore, dot only)
        if not re.match(r'^[a-zA-Z0-9_.]+$', table):
            raise ValueError(f"Invalid table name: {table}")

        # Convert embedding to pgvector format
        vector_str = '[' + ','.join(map(str, embedding)) + ']'

        # Use sql.Identifier for safe table name
        table_id = sql.Identifier(*table.split('.'))

        if text:
            query = sql.SQL("""
                INSERT INTO {table} (embedding, metadata, document)
                VALUES (%s::vector, %s::jsonb, %s)
                RETURNING id
            """).format(table=table_id)
            cursor.execute(query, (vector_str, json.dumps(metadata), text))
        else:
            query = sql.SQL("""
                INSERT INTO {table} (embedding, metadata)
                VALUES (%s::vector, %s::jsonb)
                RETURNING id
            """).format(table=table_id)
            cursor.execute(query, (vector_str, json.dumps(metadata)))

        row_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()

        return row_id

    def similarity_search(
        self,
        table: str,
        query_embedding: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        distance_metric: str = 'cosine'
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search

        Args:
            table: Table name
            query_embedding: Query vector
            limit: Max results
            filters: JSONB filters (e.g., {'success': True})
            distance_metric: 'cosine' (<=>) or 'l2' (<->)

        Returns:
            List of {id, distance, metadata, document}
        """
        conn = self.connect()
        cursor = conn.cursor()

        vector_str = '[' + ','.join(map(str, query_embedding)) + ']'
        operator = '<=>' if distance_metric == 'cosine' else '<->'

        # Build WHERE clause for filters
        where_clause = ""
        params = [vector_str]

        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(f"metadata->>{key} = %s")
                params.append(str(value))
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT id, embedding {operator} %s::vector AS distance, metadata, document
            FROM {table}
            {where_clause}
            ORDER BY embedding {operator} %s::vector
            LIMIT {limit}
        """

        # Add query_embedding twice (for distance calc and ORDER BY)
        params.append(vector_str)

        cursor.execute(query, params)
        results = []

        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'distance': float(row[1]),
                'metadata': row[2],
                'document': row[3] if len(row) > 3 else None
            })

        cursor.close()
        return results

    def bulk_insert(
        self,
        table: str,
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        texts: Optional[List[str]] = None
    ) -> List[int]:
        """
        Bulk insert embeddings

        Returns:
            List of inserted IDs
        """
        conn = self.connect()
        cursor = conn.cursor()
        ids = []

        for i, (emb, meta) in enumerate(zip(embeddings, metadatas)):
            text = texts[i] if texts else None
            row_id = self.insert_embedding(table, emb, meta, text)
            ids.append(row_id)

        conn.commit()
        cursor.close()
        return ids

    def delete_by_filter(
        self,
        table: str,
        filters: Dict[str, Any]
    ) -> int:
        """
        Delete rows matching metadata filters

        Returns:
            Number of deleted rows
        """
        import re
        from psycopg2 import sql

        conn = self.connect()
        cursor = conn.cursor()

        # Validate table name (alphanumeric, underscore, dot only)
        if not re.match(r'^[a-zA-Z0-9_.]+$', table):
            raise ValueError(f"Invalid table name: {table}")

        conditions = []
        params = []
        for key, value in filters.items():
            # Validate metadata key (alphanumeric, underscore, hyphen only)
            if not re.match(r'^[a-zA-Z0-9_-]+$', key):
                raise ValueError(f"Invalid metadata key: {key}")

            # Use sql.Identifier for safe key interpolation
            conditions.append(sql.SQL("metadata->>%s = %s"))
            params.append(key)
            params.append(str(value))

        if not conditions:
            raise ValueError("No valid filter conditions provided")

        # Build query with safe table identifier
        query = sql.SQL("DELETE FROM {table} WHERE {conditions} RETURNING id").format(
            table=sql.Identifier(*table.split('.')),
            conditions=sql.SQL(" AND ").join(conditions)
        )

        cursor.execute(query, params)

        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()

        return deleted_count


# Test module
if __name__ == '__main__':
    import numpy as np

    print("=== Vector DB Adapter Test ===\n")

    adapter = VectorDBAdapter()

    # Test 1: Insert embedding
    print("Test 1: Insert embedding")
    test_emb = np.random.rand(128).tolist()
    test_meta = {'test': 'vector-db-adapter', 'version': '1.0'}

    try:
        row_id = adapter.insert_embedding(
            'learning.experiences',
            test_emb,
            test_meta,
            'Test document for vector-db-adapter'
        )
        print(f"✅ Inserted with ID: {row_id}\n")
    except Exception as e:
        print(f"❌ Insert failed: {e}\n")

    # Test 2: Similarity search
    print("Test 2: Similarity search")
    try:
        results = adapter.similarity_search(
            'learning.experiences',
            test_emb,
            limit=3
        )
        print(f"✅ Found {len(results)} similar vectors")
        for r in results[:2]:
            print(f"   ID {r['id']}: distance={r['distance']:.4f}")
        print()
    except Exception as e:
        print(f"❌ Search failed: {e}\n")

    # Test 3: Filtered search
    print("Test 3: Filtered similarity search")
    try:
        results = adapter.similarity_search(
            'learning.experiences',
            test_emb,
            limit=5,
            filters={'test': 'vector-db-adapter'}
        )
        print(f"✅ Found {len(results)} filtered results\n")
    except Exception as e:
        print(f"❌ Filtered search failed: {e}\n")

    # Cleanup
    print("Cleanup: Delete test records")
    try:
        deleted = adapter.delete_by_filter(
            'learning.experiences',
            {'test': 'vector-db-adapter'}
        )
        print(f"✅ Deleted {deleted} test records\n")
    except Exception as e:
        print(f"❌ Cleanup failed: {e}\n")

    adapter.disconnect()
    print("=== Tests Complete ===\n")
