#!/usr/bin/env python3
"""
Document Ingestion API - Production FastAPI Service (SECURITY HARDENED)
Complete implementation with security, rate limiting, and async processing
"""

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import secrets
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import asyncpg
import bcrypt
import magic
import numpy as np
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from PIL import Image
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from PyPDF2 import PdfReader
from redis.sentinel import Sentinel
from sentence_transformers import SentenceTransformer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://sfloess@aio-01:5433/learning"
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    db_command_timeout: int = 30

    # Redis Sentinel
    redis_sentinel_hosts: str = "aio-01:26379,server-01:26379,server-02:26379"
    redis_sentinel_master: str = "mymaster"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    # Security
    https_required: bool = False  # Changed to False - HTTPS not yet configured
    allowed_origins: List[str] = ["http://localhost:8000", "http://aio-01:8000", "http://127.0.0.1:8000"]

    # File Upload Limits
    max_pdf_size_mb: int = 50
    max_image_size_mb: int = 20
    max_text_size_mb: int = 10

    # Embeddings
    embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    embedding_batch_size: int = 32

    class Config:
        env_file = ".env"


settings = Settings()

# ============================================================================
# SECURITY: Constant-time API key validation
# ============================================================================


async def validate_api_key_constant_time(api_key: str, pool: asyncpg.Pool) -> dict:
    """
    Validates API key using constant-time comparison to prevent timing attacks.
    Checks expiration and returns key metadata if valid.
    Raises HTTPException if invalid or expired.
    """
    if not api_key or len(api_key) < 8:
        # Fake work to prevent timing leak
        bcrypt.checkpw(b"fake", bcrypt.hashpw(b"fake", bcrypt.gensalt()))
        raise HTTPException(status_code=401, detail="Invalid API key")

    key_prefix = api_key[:8]

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, key_hash, scopes, rate_limit_per_minute, is_active, expires_at "
            "FROM auth.api_keys WHERE key_prefix = $1 AND is_active = true",
            key_prefix,
        )

    if not row:
        # Fake work to prevent timing leak
        bcrypt.checkpw(b"fake", bcrypt.hashpw(b"fake", bcrypt.gensalt()))
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check expiration BEFORE constant-time check to prevent timing leak on expired keys
    now = datetime.now(timezone.utc)
    if row["expires_at"] and row["expires_at"] < now:
        # Fake work to prevent timing leak
        bcrypt.checkpw(b"fake", bcrypt.hashpw(b"fake", bcrypt.gensalt()))
        raise HTTPException(status_code=401, detail="API key expired")

    # Constant-time password check
    key_hash = row["key_hash"]
    if isinstance(key_hash, str):
        key_hash = key_hash.encode('utf-8')

    # Ensure API key is properly encoded
    api_key_bytes = api_key.encode('utf-8')

    try:
        is_valid = bcrypt.checkpw(api_key_bytes, key_hash)
    except ValueError as e:
        # Log the error for debugging but maintain constant-time
        logger.error(f"bcrypt checkpw error: {e}, key_hash type: {type(key_hash)}, key_hash length: {len(key_hash)}")
        # Fake work to maintain constant-time
        bcrypt.checkpw(b"fake", bcrypt.hashpw(b"fake", bcrypt.gensalt()))
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return dict(row)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


async def chunk_text_semantic(text: str, max_size: int = 1500) -> List[str]:
    """
    Semantic chunking that respects sentence boundaries.
    Improved implementation that doesn't break mid-sentence.
    """
    # Split on sentence boundaries (period, exclamation, question mark)
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = []
    current_size = 0

    for sentence in sentences:
        sentence_size = len(sentence)

        # If adding this sentence exceeds max_size, start new chunk
        if current_size + sentence_size > max_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_size = 0

        # If single sentence exceeds max_size, split it at word boundaries
        if sentence_size > max_size:
            words = sentence.split()
            for word in words:
                if current_size + len(word) > max_size and current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                current_chunk.append(word)
                current_size += len(word) + 1
        else:
            current_chunk.append(sentence)
            current_size += sentence_size + 1

    # Add final chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate normalized embeddings using the global embedding model.
    Validates dimension to prevent schema mismatches.
    """
    if not embedding_model:
        raise RuntimeError("Embedding model not loaded")

    embeddings = embedding_model.encode(texts, convert_to_numpy=True)

    # Validate dimension matches schema expectation
    if embeddings.shape[1] != 768:
        raise ValueError(
            f"Embedding dimension mismatch: expected 768, got {embeddings.shape[1]}"
        )

    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-9)  # Prevent division by zero
    embeddings = embeddings / norms

    return embeddings.tolist()


async def validate_file_magic_bytes(file_path: str, expected_type: str) -> dict:
    """
    Validates file type using magic bytes and computes SHA-256 hash.
    Uses streaming hash to prevent memory exhaustion on large files.
    """
    mime = magic.from_file(file_path, mime=True)
    allowed = {
        "pdf": ["application/pdf"],
        "image": ["image/png", "image/jpeg", "image/tiff"],
        "text": ["text/plain"],
    }
    if mime not in allowed.get(expected_type, []):
        raise ValueError(f"File type mismatch: expected {expected_type}, got {mime}")

    # Streaming hash to prevent memory exhaustion on large files
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):  # Read 8KB chunks
            sha256.update(chunk)
    file_hash = sha256.hexdigest()

    return {"mime_type": mime, "file_hash": file_hash}


# ============================================================================
# BACKGROUND PROCESSING
# ============================================================================


async def process_pdf_document(document_id: UUID, file_path: str):
    """
    Background task to extract text, chunk, and generate embeddings.
    Wrapped in transaction for atomicity.
    """
    try:
        active_processing.inc()
        start_time = datetime.now(timezone.utc)

        async with db_pool.acquire() as conn:
            # Update status to processing
            await conn.execute(
                """
                UPDATE documents.documents
                SET status = 'processing', processing_started_at = $2
                WHERE id = $1
                """,
                document_id,
                start_time,
            )

        # Extract text from PDF
        reader = PdfReader(file_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n\n"

        # Chunk text semantically
        chunks = await chunk_text_semantic(full_text)

        # Generate embeddings in batches
        all_embeddings = []
        for i in range(0, len(chunks), settings.embedding_batch_size):
            batch = chunks[i:i + settings.embedding_batch_size]
            batch_embeddings = await generate_embeddings(batch)
            all_embeddings.extend(batch_embeddings)

        # Insert chunks with embeddings in transaction
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                for idx, (chunk_text, embedding) in enumerate(zip(chunks, all_embeddings)):
                    content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()

                    await conn.execute(
                        """
                        INSERT INTO documents.chunks
                        (document_id, chunk_index, content, content_hash, embedding)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        document_id,
                        idx,
                        chunk_text,
                        content_hash,
                        embedding,
                    )

                # Update document status to completed
                end_time = datetime.now(timezone.utc)
                await conn.execute(
                    """
                    UPDATE documents.documents
                    SET status = 'completed', processing_completed_at = $2
                    WHERE id = $1
                    """,
                    document_id,
                    end_time,
                )

                # Log processing
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                await conn.execute(
                    """
                    INSERT INTO documents.processing_log
                    (document_id, stage, status, duration_ms, chunks_created, embeddings_generated)
                    VALUES ($1, 'complete', 'success', $2, $3, $4)
                    """,
                    document_id,
                    duration_ms,
                    len(chunks),
                    len(all_embeddings),
                )

        embeddings_generated.inc(len(all_embeddings))
        logger.info(
            f"Processed document {document_id}: {len(chunks)} chunks, {duration_ms}ms"
        )

    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {e}")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE documents.documents
                SET status = 'failed', error_message = $2
                WHERE id = $1
                """,
                document_id,
                str(e),
            )

            await conn.execute(
                """
                INSERT INTO documents.processing_log
                (document_id, stage, status, error_message)
                VALUES ($1, 'complete', 'error', $2)
                """,
                document_id,
                str(e),
            )

    finally:
        active_processing.dec()
        # Clean up temp file
        Path(file_path).unlink(missing_ok=True)


# ============================================================================
# GLOBAL STATE (initialized in lifespan)
# ============================================================================

db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[Any] = None
embedding_model: Optional[SentenceTransformer] = None


# ============================================================================
# LIFESPAN CONTEXT MANAGER (startup/shutdown)
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database pool, Redis, and embedding model on startup."""
    global db_pool, redis_client, embedding_model

    # Parse database URL
    db_url = settings.database_url.replace("postgresql://", "")
    user_host, db_name = db_url.split("/")
    user, host_port = user_host.split("@")
    host, port = host_port.split(":")

    # Initialize asyncpg connection pool
    logger.info(f"Connecting to PostgreSQL at {host}:{port}/{db_name}")
    db_pool = await asyncpg.create_pool(
        host=host,
        port=int(port),
        user=user,
        database=db_name,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        command_timeout=settings.db_command_timeout,
    )

    # Initialize Redis Sentinel
    sentinel_hosts = [
        tuple(h.split(":")) for h in settings.redis_sentinel_hosts.split(",")
    ]
    sentinel_hosts = [(h, int(p)) for h, p in sentinel_hosts]
    logger.info(f"Connecting to Redis Sentinel: {sentinel_hosts}")
    sentinel = Sentinel(sentinel_hosts, socket_timeout=1.0)
    redis_client = sentinel.master_for(
        settings.redis_sentinel_master, socket_timeout=1.0
    )

    # Load embedding model
    logger.info(f"Loading embedding model: {settings.embedding_model}")
    embedding_model = SentenceTransformer(settings.embedding_model)

    logger.info("Application startup complete")
    yield

    # Cleanup
    logger.info("Shutting down application")
    if db_pool:
        await db_pool.close()
    if redis_client:
        redis_client.close()


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Document Ingestion API", version="1.0.0", lifespan=lifespan
)

# HTTPS enforcement middleware (if enabled)
if settings.https_required:
    @app.middleware("http")
    async def enforce_https(request: Request, call_next):
        """Enforce HTTPS for all requests except health checks."""
        if request.url.path not in ["/health", "/metrics"]:
            if request.url.scheme != "https":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "HTTPS required"}
                )
        return await call_next(request)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Prometheus metrics
http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
http_request_duration = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "endpoint"]
)
documents_uploaded = Counter("documents_uploaded_total", "Total documents uploaded")
embeddings_generated = Counter("embeddings_generated_total", "Total embeddings generated")
active_processing = Gauge("documents_processing_active", "Documents currently processing")


# ============================================================================
# API KEY DEPENDENCY
# ============================================================================

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: str = Depends(api_key_header)) -> dict:
    """FastAPI dependency to validate API key and return metadata."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not initialized")

    return await validate_api_key_constant_time(api_key, db_pool)


# ============================================================================
# RATE LIMITING
# ============================================================================


async def check_rate_limit(request: Request, api_key_data: dict = Depends(get_api_key)):
    """
    Rate limiting with atomic updates to prevent race conditions.
    Uses INSERT...ON CONFLICT for atomic read-modify-write.
    Skips rate limiting for /health and /metrics endpoints.
    """
    # Skip rate limiting for monitoring endpoints
    if request.url.path in ["/health", "/metrics"]:
        return True

    api_key_id = api_key_data["id"]
    rate_limit = api_key_data["rate_limit_per_minute"]

    now = datetime.now(timezone.utc)
    minute_window = now.replace(second=0, microsecond=0)

    async with db_pool.acquire() as conn:
        # Atomic read-modify-write with INSERT...ON CONFLICT
        row = await conn.fetchrow(
            """
            INSERT INTO monitoring.rate_limit_state (api_key_id, minute_window, request_count, updated_at)
            VALUES ($1, $2, 1, $3)
            ON CONFLICT (api_key_id) DO UPDATE
            SET
                request_count = CASE
                    WHEN monitoring.rate_limit_state.minute_window = $2
                    THEN monitoring.rate_limit_state.request_count + 1
                    ELSE 1
                END,
                minute_window = $2,
                updated_at = $3
            RETURNING request_count
            """,
            api_key_id,
            minute_window,
            now,
        )

    request_count = row["request_count"]

    if request_count > rate_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {rate_limit} requests per minute",
        )

    return True


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_results: int = Field(default=10, ge=1, le=100)


class ChunkResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    similarity: float
    metadata: dict


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint (no auth required)."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint (no auth required)."""
    return Response(content=generate_latest(), media_type="text/plain")


@app.post("/api/v1/ingest/pdf")
async def ingest_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source: str = Form("user_upload"),
    tags: Optional[str] = Form(None),
    api_key_data: dict = Depends(get_api_key),
    rate_limit_ok: bool = Depends(check_rate_limit),
):
    """
    Ingest PDF document with deduplication, chunking, and embedding.
    Processing happens asynchronously in background.
    """
    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset

    max_size = settings.max_pdf_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {file_size} bytes (max {max_size})"
        )

    # Check for empty file
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Sanitize string inputs (source, tags come from Form fields)
    source = re.sub(r'<[^>]*>', '', source).strip()[:200]
    if tags:
        tags = re.sub(r'<[^>]*>', '', tags).strip()[:1000]
    if file.filename and '..' in file.filename:
        raise HTTPException(status_code=400, detail="Path traversal detected in filename")
    safe_filename = re.sub(r'[<>:"/\\|?*]', '_', file.filename or 'unnamed.pdf')[:255]

    # Save to temp file for validation
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        # Validate magic bytes and compute hash
        validation = await validate_file_magic_bytes(tmp_path, "pdf")
        file_hash = validation["file_hash"]
        mime_type = validation["mime_type"]

        # Check for duplicate
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id, status FROM documents.documents WHERE file_hash = $1",
                file_hash,
            )

            if existing:
                # Clean up temp file immediately for duplicates
                Path(tmp_path).unlink(missing_ok=True)
                return {
                    "status": "duplicate",
                    "document_id": str(existing["id"]),
                    "message": "Document already exists",
                }

            # Insert document
            document_id = await conn.fetchval(
                """
                INSERT INTO documents.documents
                (file_hash, file_name, file_type, file_size_bytes, mime_type, source, tags, status)
                VALUES ($1, $2, 'pdf', $3, $4, $5, $6, 'pending')
                RETURNING id
                """,
                file_hash,
                safe_filename,
                file_size,
                mime_type,
                source,
                tags.split(",") if tags else [],
            )

        documents_uploaded.inc()

        # Schedule background processing
        background_tasks.add_task(process_pdf_document, document_id, tmp_path)

        return {
            "status": "accepted",
            "document_id": str(document_id),
            "file_hash": file_hash,
            "file_size_bytes": file_size,
            "message": "Processing started in background",
        }

    except Exception as e:
        # Clean up temp file on error
        Path(tmp_path).unlink(missing_ok=True)
        raise


@app.post("/api/v1/query", response_model=List[ChunkResult])
async def query_documents(
    request: QueryRequest,
    api_key_data: dict = Depends(get_api_key),
    rate_limit_ok: bool = Depends(check_rate_limit),
):
    """
    Query documents by semantic similarity.
    Returns most similar chunks with metadata.
    """
    # Generate embedding for query
    query_embeddings = await generate_embeddings([request.query])
    query_embedding = query_embeddings[0]

    # Query database using similarity function
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM documents.find_similar_chunks($1::vector, $2, $3)
            """,
            query_embedding,
            request.similarity_threshold,
            request.max_results,
        )

    results = [
        ChunkResult(
            chunk_id=str(row["chunk_id"]),
            document_id=str(row["document_id"]),
            content=row["content"],
            similarity=float(row["similarity"]),
            metadata=row["metadata"],
        )
        for row in rows
    ]

    return results


@app.get("/api/v1/documents/{document_id}/status")
async def get_document_status(
    document_id: UUID,
    api_key_data: dict = Depends(get_api_key),
):
    """Get processing status of a document."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, file_name, status, processing_started_at,
                   processing_completed_at, error_message
            FROM documents.documents
            WHERE id = $1
            """,
            document_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "document_id": str(row["id"]),
        "file_name": row["file_name"],
        "status": row["status"],
        "processing_started_at": row["processing_started_at"].isoformat() if row["processing_started_at"] else None,
        "processing_completed_at": row["processing_completed_at"].isoformat() if row["processing_completed_at"] else None,
        "error_message": row["error_message"],
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
    )
