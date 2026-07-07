#!/usr/bin/env python3
"""
Learning Ingestion API - Complete data ingestion endpoints
Extends document-ingestion-api.py with conversation, memory, git, issues, tests, errors
"""

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

import asyncpg
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sentence_transformers import SentenceTransformer


# ============================================================================
# INPUT VALIDATION HELPERS
# ============================================================================

def sanitize_html(text: str, max_length: int = 50000) -> str:
    """Strip HTML tags and script content to prevent XSS."""
    if not isinstance(text, str):
        raise ValueError("Input must be a string")
    if len(text) > max_length:
        raise ValueError(f"Input too long: {len(text)} > {max_length}")
    result = re.sub(r'<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>', '', text, flags=re.IGNORECASE)
    result = re.sub(r'<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>', '', result, flags=re.IGNORECASE)
    result = re.sub(r'<[^>]*>', '', result)
    result = result.replace('\0', '')
    return result.strip()

def validate_file_path(path: str) -> str:
    """Block path traversal attempts."""
    if not isinstance(path, str):
        raise ValueError("Path must be a string")
    if '..' in path:
        raise ValueError("Path traversal detected: '..' not allowed")
    if '\0' in path:
        raise ValueError("Null byte detected in path")
    return path

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
    allow_origins=["http://localhost:8001", "http://aio-01:8001", "http://127.0.0.1:8001"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# ============================================================================
# MODELS
# ============================================================================

class ConversationRequest(BaseModel):
    session_id: str = Field(..., max_length=200)
    user_requests: List[str] = []
    tool_uses: List[str] = []
    patterns: List[str] = []
    timestamp: Optional[str] = None

    @field_validator('session_id')
    @classmethod
    def sanitize_session_id(cls, v):
        return sanitize_html(v, max_length=200)

    @field_validator('user_requests', 'tool_uses', 'patterns')
    @classmethod
    def sanitize_string_lists(cls, v):
        return [sanitize_html(item, max_length=10000) for item in v]

class MemoryRequest(BaseModel):
    name: str = Field(..., max_length=500)
    description: str = Field(..., max_length=5000)
    memory_type: str = Field(..., max_length=50)
    content: str = Field(..., max_length=50000)
    tags: List[str] = []

    @field_validator('name', 'description', 'memory_type', 'content')
    @classmethod
    def sanitize_strings(cls, v):
        return sanitize_html(v, max_length=50000)

    @field_validator('tags')
    @classmethod
    def sanitize_tags(cls, v):
        return [sanitize_html(t, max_length=100) for t in v]

class GitCommitRequest(BaseModel):
    commit_hash: str = Field(..., max_length=64)
    author: str = Field(..., max_length=200)
    message: str = Field(..., max_length=5000)
    files_changed: List[str]
    additions: int = Field(..., ge=0)
    deletions: int = Field(..., ge=0)
    timestamp: str
    branch: str = Field(default="main", max_length=200)

    @field_validator('commit_hash')
    @classmethod
    def validate_commit_hash(cls, v):
        if not re.match(r'^[a-fA-F0-9]+$', v):
            raise ValueError('Commit hash must be hexadecimal')
        return v

    @field_validator('author', 'message', 'branch')
    @classmethod
    def sanitize_commit_strings(cls, v):
        return sanitize_html(v, max_length=5000)

    @field_validator('files_changed')
    @classmethod
    def validate_file_paths(cls, v):
        for p in v:
            validate_file_path(p)
        return v

class GitLabIssueRequest(BaseModel):
    issue_id: int = Field(..., ge=1)
    title: str = Field(..., max_length=1000)
    description: str = Field(..., max_length=50000)
    labels: List[str]
    state: str  # open, closed
    created_at: str
    closed_at: Optional[str] = None
    solution: Optional[str] = None

    @field_validator('title', 'description')
    @classmethod
    def sanitize_issue_strings(cls, v):
        return sanitize_html(v, max_length=50000)

    @field_validator('state')
    @classmethod
    def validate_state(cls, v):
        if v not in ('open', 'closed'):
            raise ValueError('State must be "open" or "closed"')
        return v

    @field_validator('labels')
    @classmethod
    def sanitize_labels(cls, v):
        return [sanitize_html(label, max_length=100) for label in v]

class TestResultsRequest(BaseModel):
    test_suite: str = Field(..., max_length=500)
    total_tests: int = Field(..., ge=0)
    passed: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    skipped: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0, le=86400000)
    failures: List[dict] = []  # [{test_name, error, stack_trace}]
    timestamp: str

    @field_validator('test_suite')
    @classmethod
    def sanitize_test_suite(cls, v):
        return sanitize_html(v, max_length=500)

class ErrorLogRequest(BaseModel):
    error_type: str = Field(..., max_length=200)
    message: str = Field(..., max_length=10000)
    stack_trace: str = Field(..., max_length=50000)
    context: dict = {}
    solution: Optional[str] = None
    timestamp: str

    @field_validator('error_type', 'message')
    @classmethod
    def sanitize_error_strings(cls, v):
        return sanitize_html(v, max_length=10000)

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
