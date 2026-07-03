#!/usr/bin/env python3
"""
Train embeddings for code and documentation files

Scans the codebase, generates 384-dim embeddings for:
- Python files (.py)
- JavaScript/Node files (.js, .mjs)
- Documentation files (.md)

Stores in PostgreSQL knowledge.code_embeddings table for semantic search.

Usage:
    python3 tools/train_embeddings.py [--batch-size 32] [--force]

Options:
    --batch-size N    Process N files at once (default: 32)
    --force          Regenerate embeddings even if they exist
    --dry-run        Show what would be processed without storing
"""

import sys
import os
import json
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import psycopg2
from psycopg2.extras import execute_batch

# Add parent directory to path for imports
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("ERROR: sentence-transformers not installed", file=sys.stderr)
    print("Install: pip3 install sentence-transformers", file=sys.stderr)
    sys.exit(1)

# Database connection
DB_CONFIG = {
    'dbname': 'learning',
    'user': 'claude',
    'host': 'aio-01',
    'port': 5433
}

# File patterns to process
CODE_EXTENSIONS = {'.py', '.js', '.mjs'}
DOC_EXTENSIONS = {'.md'}
ALL_EXTENSIONS = CODE_EXTENSIONS | DOC_EXTENSIONS

# Directories to exclude
EXCLUDE_DIRS = {'node_modules', '.git', 'learning', '__pycache__', '.pytest_cache', 'checkpoints'}

# Maximum file size to process (bytes)
MAX_FILE_SIZE = 1024 * 1024  # 1MB


def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(**DB_CONFIG)


def init_schema(conn):
    """Create knowledge.code_embeddings table if it doesn't exist"""
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE SCHEMA IF NOT EXISTS knowledge
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge.code_embeddings (
                id SERIAL PRIMARY KEY,
                file_path TEXT NOT NULL UNIQUE,
                file_type TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                content_preview TEXT,
                embedding vector(384),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create HNSW index for fast similarity search
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS code_embeddings_embedding_idx
            ON knowledge.code_embeddings
            USING hnsw (embedding vector_cosine_ops)
        """)

        # Create index on file_type for filtered searches
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS code_embeddings_type_idx
            ON knowledge.code_embeddings (file_type)
        """)

        conn.commit()


def find_files(root_dir: Path) -> List[Tuple[Path, str]]:
    """
    Find all code and documentation files
    Returns list of (path, file_type) tuples
    """
    files = []

    for path in root_dir.rglob('*'):
        # Skip excluded directories
        if any(excl in path.parts for excl in EXCLUDE_DIRS):
            continue

        # Check extension
        if path.suffix not in ALL_EXTENSIONS:
            continue

        # Skip if too large
        if not path.is_file() or path.stat().st_size > MAX_FILE_SIZE:
            continue

        # Determine file type
        if path.suffix in CODE_EXTENSIONS:
            file_type = 'code'
        elif path.suffix in DOC_EXTENSIONS:
            file_type = 'documentation'
        else:
            continue

        files.append((path, file_type))

    return files


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of file contents"""
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def read_file_content(path: Path) -> Tuple[str, str]:
    """
    Read file content and generate preview
    Returns (full_content, preview)
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Generate preview (first 500 chars)
        preview = content[:500]
        if len(content) > 500:
            preview += "..."

        return content, preview
    except Exception as e:
        print(f"WARNING: Could not read {path}: {e}", file=sys.stderr)
        return "", ""


def check_existing_embeddings(conn, paths: List[Path]) -> Dict[str, str]:
    """
    Check which files already have embeddings
    Returns dict of {path: file_hash} for existing embeddings
    """
    if not paths:
        return {}

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT file_path, file_hash
            FROM knowledge.code_embeddings
            WHERE file_path = ANY(%s)
        """, ([str(p) for p in paths],))

        return {row[0]: row[1] for row in cursor.fetchall()}


def generate_embeddings(model: SentenceTransformer, texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Generate embeddings for a batch of texts"""
    embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_embeddings = model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
        embeddings.extend([emb.tolist() for emb in batch_embeddings])

    return embeddings


def store_embeddings(conn, data: List[Dict]):
    """Store embeddings in database"""
    if not data:
        return

    with conn.cursor() as cursor:
        execute_batch(cursor, """
            INSERT INTO knowledge.code_embeddings
            (file_path, file_type, file_hash, content_preview, embedding, metadata, updated_at)
            VALUES (%(file_path)s, %(file_type)s, %(file_hash)s, %(content_preview)s,
                    %(embedding)s::vector, %(metadata)s, NOW())
            ON CONFLICT (file_path) DO UPDATE SET
                file_type = EXCLUDED.file_type,
                file_hash = EXCLUDED.file_hash,
                content_preview = EXCLUDED.content_preview,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """, data)

        conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Train code and documentation embeddings')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size for embedding generation')
    parser.add_argument('--force', action='store_true', help='Regenerate all embeddings')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    args = parser.parse_args()

    # Setup
    root_dir = Path('/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills')
    print(f"Scanning {root_dir}...")

    # Find files
    files = find_files(root_dir)
    print(f"Found {len(files)} files to process")

    if args.dry_run:
        for path, file_type in files[:10]:
            rel_path = path.relative_to(root_dir)
            print(f"  {file_type:15} {rel_path}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more")
        return

    # Connect to database
    conn = get_db_connection()
    init_schema(conn)

    # Check existing embeddings
    if not args.force:
        existing = check_existing_embeddings(conn, [p for p, _ in files])
        print(f"Found {len(existing)} existing embeddings")
    else:
        existing = {}

    # Load model
    print("Loading embedding model (sentence-transformers/all-MiniLM-L6-v2)...")
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    # Process files in batches
    to_process = []
    skipped = 0

    for path, file_type in files:
        file_hash = compute_file_hash(path)

        # Skip if unchanged
        if not args.force and str(path) in existing and existing[str(path)] == file_hash:
            skipped += 1
            continue

        content, preview = read_file_content(path)
        if not content:
            continue

        to_process.append({
            'path': path,
            'file_type': file_type,
            'file_hash': file_hash,
            'content': content,
            'preview': preview,
            'metadata': {
                'size': len(content),
                'extension': path.suffix,
                'name': path.name
            }
        })

    if skipped > 0:
        print(f"Skipped {skipped} unchanged files")

    if not to_process:
        print("No files to process")
        conn.close()
        return

    print(f"Processing {len(to_process)} files...")

    # Generate embeddings in batches
    for i in range(0, len(to_process), args.batch_size):
        batch = to_process[i:i+args.batch_size]
        texts = [item['content'] for item in batch]

        print(f"Generating embeddings for batch {i//args.batch_size + 1}/{(len(to_process)-1)//args.batch_size + 1}...", end=' ')
        embeddings = generate_embeddings(model, texts, batch_size=args.batch_size)

        # Prepare data for storage
        data = []
        for item, embedding in zip(batch, embeddings):
            data.append({
                'file_path': str(item['path']),
                'file_type': item['file_type'],
                'file_hash': item['file_hash'],
                'content_preview': item['preview'],
                'embedding': embedding,
                'metadata': json.dumps(item['metadata'])
            })

        # Store in database
        store_embeddings(conn, data)
        print(f"stored {len(data)} embeddings")

    conn.close()
    print(f"\nComplete! Processed {len(to_process)} files")
    print(f"Total embeddings in database: {len(files)}")


if __name__ == '__main__':
    main()
