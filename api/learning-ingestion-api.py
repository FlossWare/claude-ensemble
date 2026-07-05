#!/usr/bin/env python3
"""
Learning Ingestion API - Complete data ingestion endpoints
Extends document-ingestion-api.py with conversation, memory, git, issues, tests, errors
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

import asyncpg
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
DB_URL = "postgresql://sfloess@aio-01:5433/learning"
db_pool = None

# Embedding model
embedding_model = None

app = FastAPI(title="Learning Ingestion API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# MODELS
# ============================================================================

class ConversationRequest(BaseModel):
    session_id: str
    user_requests: List[str] = []
    tool_uses: List[str] = []
    patterns: List[str] = []
    timestamp: Optional[str] = None

class MemoryRequest(BaseModel):
    name: str
    description: str
    memory_type: str  # user, feedback, project, reference
    content: str
    tags: List[str] = []

class GitCommitRequest(BaseModel):
    commit_hash: str
    author: str
    message: str
    files_changed: List[str]
    additions: int
    deletions: int
    timestamp: str
    branch: str = "main"

class GitLabIssueRequest(BaseModel):
    issue_id: int
    title: str
    description: str
    labels: List[str]
    state: str  # open, closed
    created_at: str
    closed_at: Optional[str] = None
    solution: Optional[str] = None

class TestResultsRequest(BaseModel):
    test_suite: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    duration_ms: int
    failures: List[dict] = []  # [{test_name, error, stack_trace}]
    timestamp: str

class ErrorLogRequest(BaseModel):
    error_type: str
    message: str
    stack_trace: str
    context: dict = {}
    solution: Optional[str] = None
    timestamp: str

# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup():
    global db_pool, embedding_model

    # Database pool
    db_pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=20)
    logger.info("Database pool created")

    # Embedding model - LAZY LOAD (aio-01 is orchestrator, not worker)
    # Workers will generate embeddings via workflows
    # embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    # logger.info("Embedding model loaded")
    embedding_model = None
    logger.info("Embedding model deferred to workers (orchestrator mode)")

    # Create tables
    async with db_pool.acquire() as conn:
        # Conversations
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS learning.conversation_learnings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id TEXT,
                learning_type TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding VECTOR(384),
                timestamp TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Memories
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS learning.memories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding VECTOR(384),
                tags TEXT[],
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Git commits
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS learning.git_commits (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                commit_hash TEXT UNIQUE NOT NULL,
                author TEXT,
                message TEXT,
                embedding VECTOR(384),
                files_changed TEXT[],
                additions INT,
                deletions INT,
                branch TEXT,
                timestamp TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # GitLab issues
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS learning.gitlab_issues (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                issue_id INT UNIQUE NOT NULL,
                title TEXT,
                description TEXT,
                embedding VECTOR(384),
                labels TEXT[],
                state TEXT,
                solution TEXT,
                created_at_issue TIMESTAMPTZ,
                closed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Test results
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS learning.test_results (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                test_suite TEXT NOT NULL,
                total_tests INT,
                passed INT,
                failed INT,
                skipped INT,
                duration_ms INT,
                failures JSONB,
                timestamp TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Error logs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS learning.error_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                error_type TEXT,
                message TEXT,
                embedding VECTOR(384),
                stack_trace TEXT,
                context JSONB,
                solution TEXT,
                timestamp TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        logger.info("All tables created/verified")

@app.on_event("shutdown")
async def shutdown():
    await db_pool.close()

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "learning-ingestion-api"}

@app.post("/api/v1/ingest/conversation")
async def ingest_conversation(req: ConversationRequest, background_tasks: BackgroundTasks):
    """Ingest conversation learnings"""

    inserted = 0

    async with db_pool.acquire() as conn:
        # Insert user requests
        for content in req.user_requests:
            # Embedding generation deferred to workers (aio-01 is orchestrator)
            embedding = embedding_model.encode(content).tolist() if embedding_model else None
            await conn.execute("""
                INSERT INTO learning.conversation_learnings
                (session_id, learning_type, content, embedding, timestamp)
                VALUES ($1, $2, $3, $4, $5)
            """, req.session_id, 'user_request', content, embedding, req.timestamp)
            inserted += 1

        # Insert tool uses
        for tool in req.tool_uses:
            embedding = embedding_model.encode(tool).tolist() if embedding_model else None
            await conn.execute("""
                INSERT INTO learning.conversation_learnings
                (session_id, learning_type, content, embedding, timestamp)
                VALUES ($1, $2, $3, $4, $5)
            """, req.session_id, 'tool_use', tool, embedding, req.timestamp)
            inserted += 1

        # Insert patterns
        for pattern in req.patterns:
            embedding = embedding_model.encode(pattern).tolist() if embedding_model else None
            await conn.execute("""
                INSERT INTO learning.conversation_learnings
                (session_id, learning_type, content, embedding, timestamp)
                VALUES ($1, $2, $3, $4, $5)
            """, req.session_id, 'pattern', pattern, embedding, req.timestamp)
            inserted += 1

    return {"status": "success", "rows_inserted": inserted}

@app.post("/api/v1/ingest/memory")
async def ingest_memory(req: MemoryRequest):
    """Ingest memory file"""

    embedding = embedding_model.encode(req.content).tolist()

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO learning.memories
            (name, description, memory_type, content, embedding, tags)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                tags = EXCLUDED.tags,
                updated_at = NOW()
        """, req.name, req.description, req.memory_type, req.content, embedding, req.tags)

    return {"status": "success", "name": req.name}

@app.post("/api/v1/ingest/commit")
async def ingest_commit(req: GitCommitRequest):
    """Ingest git commit"""

    embedding = embedding_model.encode(req.message).tolist()

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO learning.git_commits
            (commit_hash, author, message, embedding, files_changed, additions, deletions, branch, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (commit_hash) DO NOTHING
        """, req.commit_hash, req.author, req.message, embedding, req.files_changed,
            req.additions, req.deletions, req.branch, req.timestamp)

    return {"status": "success", "commit_hash": req.commit_hash}

@app.post("/api/v1/ingest/issue")
async def ingest_issue(req: GitLabIssueRequest):
    """Ingest GitLab issue"""

    # Embed title + description
    text = f"{req.title}\n{req.description}"
    if req.solution:
        text += f"\nSolution: {req.solution}"

    embedding = embedding_model.encode(text).tolist()

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO learning.gitlab_issues
            (issue_id, title, description, embedding, labels, state, solution, created_at_issue, closed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (issue_id) DO UPDATE SET
                state = EXCLUDED.state,
                solution = EXCLUDED.solution,
                closed_at = EXCLUDED.closed_at
        """, req.issue_id, req.title, req.description, embedding, req.labels,
            req.state, req.solution, req.created_at, req.closed_at)

    return {"status": "success", "issue_id": req.issue_id}

@app.post("/api/v1/ingest/test-results")
async def ingest_test_results(req: TestResultsRequest):
    """Ingest test results"""

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO learning.test_results
            (test_suite, total_tests, passed, failed, skipped, duration_ms, failures, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, req.test_suite, req.total_tests, req.passed, req.failed, req.skipped,
            req.duration_ms, json.dumps(req.failures), req.timestamp)

    return {"status": "success", "test_suite": req.test_suite}

@app.post("/api/v1/ingest/error")
async def ingest_error(req: ErrorLogRequest):
    """Ingest error log"""

    # Embed error message + solution if available
    text = f"{req.error_type}: {req.message}"
    if req.solution:
        text += f"\nSolution: {req.solution}"

    embedding = embedding_model.encode(text).tolist()

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO learning.error_logs
            (error_type, message, embedding, stack_trace, context, solution, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, req.error_type, req.message, embedding, req.stack_trace,
            json.dumps(req.context), req.solution, req.timestamp)

    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=4)
