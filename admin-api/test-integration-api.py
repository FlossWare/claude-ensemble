#!/usr/bin/env python3
"""
Integration Test API Server

Provides endpoints for full-pipeline integration testing:
- /test/bulk-insert-urls - Generate test tasks in PostgreSQL
- /redis-queue/migrate-from-postgres - Migrate tasks to Redis
- /redis-queue/stats - Get queue statistics
- /storage/recent - Get recently stored documents
- /storage/document/{id} - Get document by ID
- /chunks/recent - Get recent chunks
- /embeddings/stats - Get embedding statistics
- /graph/stats - Get graph statistics
- /test/cleanup - Cleanup test data

Port: 5000 (default orchestrator API port)
Usage: python3 admin-api/test-integration-api.py
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import psycopg2
import redis
import json
import hashlib
from datetime import datetime
import os

app = FastAPI(title="Integration Test API", version="1.0")

# Database connections
PG_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'aio-01'),
    'port': int(os.getenv('POSTGRES_PORT', 5433)),
    'database': os.getenv('POSTGRES_DB', 'learning'),
    'user': os.getenv('POSTGRES_USER', 'sfloess'),
}

REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'aio-01'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'decode_responses': True,
}

# Models
class TestURL(BaseModel):
    url: str
    category: str
    priority: int
    title: str
    content: str

class BulkInsertRequest(BaseModel):
    urls: List[TestURL]

class MigrationRequest(BaseModel):
    limit: int = 100
    batch_size: int = 50

# Utilities
def get_pg_conn():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**PG_CONFIG)

def get_redis_client():
    """Get Redis client."""
    return redis.Redis(**REDIS_CONFIG)

# Endpoints
@app.post("/test/bulk-insert-urls")
async def bulk_insert_urls(req: BulkInsertRequest):
    """
    Insert test URLs into PostgreSQL scraping queue.

    Returns task IDs for tracking.
    """
    conn = get_pg_conn()
    cur = conn.cursor()

    task_ids = []

    try:
        for url_data in req.urls:
            # Insert into scraping.tasks table
            cur.execute("""
                INSERT INTO scraping.tasks (url, category, priority, status, created_at)
                VALUES (%s, %s, %s, 'pending', NOW())
                RETURNING id
            """, (url_data.url, url_data.category, url_data.priority))

            task_id = cur.fetchone()[0]
            task_ids.append(task_id)

            # Pre-store content for testing (simulates scraping)
            content_hash = hashlib.sha256(url_data.url.encode()).hexdigest()[:16]
            cur.execute("""
                INSERT INTO knowledge.documents (url, title, content, category, fetched_at, content_hash)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                ON CONFLICT (content_hash) DO NOTHING
            """, (url_data.url, url_data.title, url_data.content, url_data.category, content_hash))

        conn.commit()

        return {
            'status': 'success',
            'inserted': len(task_ids),
            'task_ids': task_ids,
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk insert failed: {e}")
    finally:
        cur.close()
        conn.close()

@app.post("/redis-queue/migrate-from-postgres")
async def migrate_from_postgres(req: MigrationRequest):
    """
    Migrate pending tasks from PostgreSQL to Redis queues.

    Returns count of migrated and failed tasks.
    """
    conn = get_pg_conn()
    cur = conn.cursor()
    redis_client = get_redis_client()

    migrated = 0
    failed = 0

    try:
        # Get pending tasks
        cur.execute("""
            SELECT id, url, category, priority
            FROM scraping.tasks
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT %s
        """, (req.limit,))

        tasks = cur.fetchall()

        # Migrate to Redis
        for task_id, url, category, priority in tasks:
            try:
                # Determine queue based on category
                queue_map = {
                    'performance': 'queue:performance:high',
                    'ai': 'queue:ai:medium',
                    'ml': 'queue:ml:medium',
                    'ga': 'queue:ga:low',
                }
                queue = queue_map.get(category, 'queue:ga:low')

                # Push to Redis queue
                item = json.dumps({
                    'url': url,
                    'category': category,
                    'priority': priority,
                    'task_id': task_id,
                })
                redis_client.lpush(queue, item)

                # Update PostgreSQL status
                cur.execute("""
                    UPDATE scraping.tasks
                    SET status = 'queued', updated_at = NOW()
                    WHERE id = %s
                """, (task_id,))

                migrated += 1

            except Exception as e:
                print(f"Failed to migrate task {task_id}: {e}")
                failed += 1

        conn.commit()

        return {
            'status': 'success',
            'migrated': migrated,
            'failed': failed,
            'total': len(tasks),
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

@app.get("/redis-queue/stats")
async def redis_queue_stats():
    """Get Redis queue statistics."""
    redis_client = get_redis_client()

    queues = {
        'performance:high': 'queue:performance:high',
        'ai:medium': 'queue:ai:medium',
        'ml:medium': 'queue:ml:medium',
        'ga:low': 'queue:ga:low',
    }

    stats = {}
    total = 0

    for name, key in queues.items():
        count = redis_client.llen(key)
        stats[name] = count
        total += count

    return {
        'queues': stats,
        'total': total,
    }

@app.get("/storage/recent")
async def get_recent_documents(limit: int = 100):
    """Get recently stored documents."""
    conn = get_pg_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, url, title, content, category, fetched_at
            FROM knowledge.documents
            ORDER BY fetched_at DESC
            LIMIT %s
        """, (limit,))

        rows = cur.fetchall()
        documents = []

        for row in rows:
            documents.append({
                'id': row[0],
                'url': row[1],
                'title': row[2],
                'content': row[3][:500],  # Truncate for API response
                'category': row[4],
                'fetched_at': row[5].isoformat() if row[5] else None,
            })

        return {'documents': documents, 'count': len(documents)}

    finally:
        cur.close()
        conn.close()

@app.get("/storage/document/{doc_id}")
async def get_document_by_id(doc_id: int):
    """Get document by ID."""
    conn = get_pg_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, url, title, content, category, fetched_at
            FROM knowledge.documents
            WHERE id = %s
        """, (doc_id,))

        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            'id': row[0],
            'url': row[1],
            'title': row[2],
            'content': row[3],
            'category': row[4],
            'fetched_at': row[5].isoformat() if row[5] else None,
        }

    finally:
        cur.close()
        conn.close()

@app.get("/chunks/recent")
async def get_recent_chunks(limit: int = 500):
    """Get recent chunks."""
    conn = get_pg_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, document_id, chunk_index, content, created_at
            FROM knowledge.chunks
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))

        rows = cur.fetchall()
        chunks = []

        for row in rows:
            chunks.append({
                'id': row[0],
                'document_id': row[1],
                'chunk_index': row[2],
                'content': row[3][:200],  # Truncate
                'created_at': row[4].isoformat() if row[4] else None,
            })

        return {'chunks': chunks, 'count': len(chunks)}

    finally:
        cur.close()
        conn.close()

@app.get("/embeddings/stats")
async def get_embedding_stats():
    """Get embedding statistics."""
    conn = get_pg_conn()
    cur = conn.cursor()

    try:
        # Total embeddings
        cur.execute("SELECT COUNT(*) FROM knowledge.embeddings")
        total_chunks = cur.fetchone()[0]

        # Provider breakdown
        cur.execute("""
            SELECT provider, COUNT(*)
            FROM knowledge.embeddings
            GROUP BY provider
        """)

        providers = {}
        for provider, count in cur.fetchall():
            providers[provider] = count

        return {
            'total_chunks': total_chunks,
            'providers': providers,
        }

    finally:
        cur.close()
        conn.close()

@app.get("/graph/stats")
async def get_graph_stats():
    """Get OrientDB graph statistics."""
    conn = get_pg_conn()
    cur = conn.cursor()

    try:
        # Document nodes (approximation from knowledge.documents)
        cur.execute("SELECT COUNT(*) FROM knowledge.documents")
        document_nodes = cur.fetchone()[0]

        # Chunk nodes
        cur.execute("SELECT COUNT(*) FROM knowledge.chunks")
        chunk_nodes = cur.fetchone()[0]

        # Edges (chunk→document relationships)
        edges = chunk_nodes  # Each chunk has 1 edge to its document

        return {
            'document_nodes': document_nodes,
            'chunk_nodes': chunk_nodes,
            'edges': edges,
            'total_nodes': document_nodes + chunk_nodes,
        }

    finally:
        cur.close()
        conn.close()

@app.post("/test/cleanup")
async def cleanup_test_data(prefix: str = "test-doc-"):
    """Cleanup test data."""
    conn = get_pg_conn()
    cur = conn.cursor()
    redis_client = get_redis_client()

    try:
        # Delete from PostgreSQL
        cur.execute("""
            DELETE FROM knowledge.embeddings
            WHERE chunk_id IN (
                SELECT c.id FROM knowledge.chunks c
                JOIN knowledge.documents d ON c.document_id = d.id
                WHERE d.url LIKE %s
            )
        """, (f'%{prefix}%',))

        cur.execute("""
            DELETE FROM knowledge.chunks
            WHERE document_id IN (
                SELECT id FROM knowledge.documents WHERE url LIKE %s
            )
        """, (f'%{prefix}%',))

        cur.execute("""
            DELETE FROM knowledge.documents WHERE url LIKE %s
        """, (f'%{prefix}%',))

        cur.execute("""
            DELETE FROM scraping.tasks WHERE url LIKE %s
        """, (f'%{prefix}%',))

        conn.commit()

        # Clear Redis queues
        queues = [
            'queue:performance:high',
            'queue:ai:medium',
            'queue:ml:medium',
            'queue:ga:low',
        ]

        for queue in queues:
            redis_client.delete(queue)

        return {'status': 'success', 'message': 'Test data cleaned up'}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {e}")
    finally:
        cur.close()
        conn.close()

@app.get("/health")
async def health():
    """Health check."""
    return {'status': 'ok', 'service': 'integration-test-api'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
