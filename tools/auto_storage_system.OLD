#!/usr/bin/env python3
"""
Automatic Storage System - COMPLETE PIPELINE VERSION
Stores memory files using full pipeline: chunk → embed → vector → graph

CHANGES FROM ORIGINAL:
1. Uses REST API (POST /learning/memory) instead of direct PostgreSQL
2. Semantic chunking for large memories (>1500 chars)
3. Embeddings auto-generated via 5-provider cascade
4. Graph relationships created in OrientDB
5. Proper error handling with retry logic
"""

import os
import json
import time
import hashlib
import fcntl
import sys
import requests
from datetime import datetime
from pathlib import Path

# Import semantic chunker and path validator
sys.path.insert(0, str(Path(__file__).parent))
from semantic_chunker import SemanticChunker
from path_validator import validate_read_path, validate_write_path

# Paths to monitor
CURRENT_PROJECT_DIR = Path.home() / ".claude" / "projects" / "-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills"
MEMORY_DIR = CURRENT_PROJECT_DIR / "memory"

# Resolve to canonical absolute paths to prevent symlink traversal
CURRENT_PROJECT_DIR = CURRENT_PROJECT_DIR.resolve()
MEMORY_DIR = MEMORY_DIR.resolve()

# REST API endpoint (source of truth)
API_BASE_URL = "http://aio-01:5000"

# Initialize semantic chunker
chunker = SemanticChunker(min_chunk_size=500, max_chunk_size=1500, overlap_size=100)

# Track processed files
PROCESSED_FILE = Path.home() / ".claude" / "learning" / "auto_storage_processed.json"
processed = {}

if PROCESSED_FILE.exists():
    valid_processed_file = validate_read_path(str(PROCESSED_FILE))
    try:
        with open(valid_processed_file, 'r') as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                processed = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: Corrupted processed file ({e}), starting fresh")
                processed = {}
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except FileNotFoundError:
        # File was deleted between exists() check and open()
        print("Warning: Processed file disappeared during read, starting fresh")
        processed = {}

def save_processed():
    """Save processed file hashes with exclusive file locking"""
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    valid_processed_file = validate_write_path(str(PROCESSED_FILE))

    with open(valid_processed_file, 'w') as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(processed, f, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def file_hash(filepath):
    """Calculate file hash to detect changes"""
    valid_filepath = validate_read_path(str(filepath))
    with open(valid_filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def store_chunk_with_retry(payload, chunk_index, max_retries=3):
    """Store chunk via REST API with retry logic"""
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{API_BASE_URL}/learning/memory",
                json=payload,
                timeout=30
            )

            if response.ok:
                return response.json()

            if response.status_code == 400:
                # Bad request - don't retry
                print(f"    ✗ Chunk {chunk_index}: Invalid request - {response.text[:100]}")
                return None

            # Server error - retry
            if attempt < max_retries - 1:
                print(f"    ⚠️  Chunk {chunk_index}: Attempt {attempt+1} failed, retrying in {retry_delay}s...")
                time.sleep(retry_delay)

        except requests.Timeout:
            if attempt < max_retries - 1:
                print(f"    ⚠️  Chunk {chunk_index}: Timeout, retrying ({attempt+1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                print(f"    ✗ Chunk {chunk_index}: Max retries exceeded")
                return None

        except requests.RequestException as e:
            print(f"    ✗ Chunk {chunk_index}: Error - {e}")
            return None

    return None

def sanitize_sql_value(value):
    """Sanitize value for SQL - escape quotes and convert to string"""
    if value is None:
        return 'NULL'
    # Convert to string and escape single quotes
    return str(value).replace("'", "''")

def validate_memory_id(memory_id):
    """Validate memory_id is a positive integer"""
    try:
        mid = int(memory_id)
        if mid <= 0:
            raise ValueError(f"Invalid memory_id: {memory_id} (must be positive)")
        return mid
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid memory_id: {memory_id} (must be an integer)") from e

def create_graph_relationships(memory_ids, memory_type, memory_name, source_file, frontmatter):
    """Create OrientDB vertices and edges (best-effort, non-fatal)"""
    try:
        # Validate and sanitize all inputs
        validated_ids = []
        for mid in memory_ids:
            try:
                validated_ids.append(validate_memory_id(mid))
            except ValueError as e:
                print(f"    ⚠️  Skipping invalid memory_id: {e}")
                continue

        if not validated_ids:
            print(f"  ⚠️  Graph relationships skipped: No valid memory IDs")
            return

        # Sanitize string inputs to prevent injection
        safe_memory_type = sanitize_sql_value(memory_type)
        safe_memory_name = sanitize_sql_value(memory_name)
        safe_source_file = sanitize_sql_value(source_file)
        safe_project_name = sanitize_sql_value(frontmatter.get('project', 'claude-global-skills'))

        # Create Memory vertices
        for memory_id in validated_ids:
            query = f"""
                CREATE VERTEX Memory SET
                    memory_id = {memory_id},
                    memory_type = '{safe_memory_type}',
                    memory_name = '{safe_memory_name}',
                    source_file = '{safe_source_file}',
                    created_at = datetime()
            """

            try:
                response = requests.post(
                    f"{API_BASE_URL}/graph/query",
                    json={'query': query},
                    timeout=10
                )

                if response.ok:
                    print(f"    ✓ Graph vertex: memory_id={memory_id}")
            except:
                pass  # Non-fatal

        # Create BelongsTo edges
        for memory_id in validated_ids:
            query = f"""
                CREATE EDGE BelongsTo FROM
                    (SELECT FROM Memory WHERE memory_id = {memory_id})
                TO
                    (SELECT FROM Project WHERE name = '{safe_project_name}')
            """

            try:
                requests.post(
                    f"{API_BASE_URL}/graph/query",
                    json={'query': query},
                    timeout=10
                )
            except:
                pass  # Non-fatal

        # Create NextChunk edges for multi-chunk memories
        if len(validated_ids) > 1:
            for i in range(len(validated_ids) - 1):
                query = f"""
                    CREATE EDGE NextChunk FROM
                        (SELECT FROM Memory WHERE memory_id = {validated_ids[i]})
                    TO
                        (SELECT FROM Memory WHERE memory_id = {validated_ids[i+1]})
                """

                try:
                    requests.post(
                        f"{API_BASE_URL}/graph/query",
                        json={'query': query},
                        timeout=10
                    )
                except:
                    pass  # Non-fatal

        print(f"  ✓ Graph: {len(validated_ids)} vertices, {len(validated_ids)} edges")

    except Exception as e:
        print(f"  ⚠️  Graph relationships skipped: {e}")
        # Non-fatal - memory still stored in PostgreSQL

def store_memory_via_api(memory_file):
    """
    Store memory using complete pipeline:
    - Parse frontmatter
    - Semantic chunking (if >1500 chars)
    - REST API storage (embeddings auto-generated)
    - Graph relationships
    """
    try:
        print(f"\n[AUTO-STORAGE] Processing: {memory_file.name}")

        # Check if already processed
        current_hash = file_hash(memory_file)
        if processed.get(str(memory_file)) == current_hash:
            print(f"  ✓ Already processed (hash match)")
            return

        # Read memory file
        valid_memory_file = validate_read_path(str(memory_file))
        with open(valid_memory_file, 'r') as f:
            content = f.read()

        if not content.strip():
            return

        # Parse frontmatter
        frontmatter = {}
        actual_content = content
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                fm_text = parts[1]
                for line in fm_text.strip().split('\n'):
                    if ':' in line:
                        key, val = line.split(':', 1)
                        frontmatter[key.strip()] = val.strip()
                actual_content = parts[2].strip()

        memory_type = frontmatter.get('type', 'unknown')
        memory_name = frontmatter.get('name', memory_file.stem)
        tags = frontmatter.get('tags', '').split(',') if frontmatter.get('tags') else []

        # Decide if chunking needed
        content_length = len(actual_content)
        needs_chunking = content_length > 1500

        if needs_chunking:
            # Use semantic chunker
            chunks = chunker.chunk_text(actual_content)
            print(f"  → Chunking: {content_length} chars → {len(chunks)} chunks")
        else:
            # Single chunk
            chunks = [{
                'index': 0,
                'content': actual_content,
                'char_count': content_length,
                'has_code': False,
                'chunk_type': 'text'
            }]

        # Store each chunk via REST API
        chunk_ids = []
        for chunk in chunks:
            payload = {
                'memory_type': memory_type,
                'content': chunk['content'],
                'metadata': {
                    'source': 'auto-storage',
                    'source_file': memory_file.name,
                    'memory_name': memory_name,
                    'is_chunk': needs_chunking,
                    'chunk_index': chunk['index'],
                    'total_chunks': len(chunks),
                    'char_count': chunk['char_count'],
                    'has_code': chunk.get('has_code', False),
                    'language': chunk.get('language'),
                    'chunk_type': chunk['chunk_type'],
                    'tags': tags,
                    'frontmatter': frontmatter
                },
                'source_file': memory_file.name
            }

            result = store_chunk_with_retry(payload, chunk['index'])

            if result:
                chunk_ids.append(result['id'])
                # Proper embedding status check
                has_embedding = False
                if 'has_embedding' in result:
                    has_embedding = bool(result['has_embedding'])
                elif result.get('embedding') is not None:
                    has_embedding = True

                if has_embedding:
                    print(f"    ✓ Chunk {chunk['index']}: id={result['id']}, embedding=YES")
                else:
                    print(f"    ⚠️  Chunk {chunk['index']}: id={result['id']}, embedding=NO (all providers failed)")

        if chunk_ids:
            # Create graph relationships (best-effort)
            create_graph_relationships(chunk_ids, memory_type, memory_name, memory_file.name, frontmatter)

            # Mark as processed
            processed[str(memory_file)] = current_hash
            save_processed()

            print(f"  ✓ Complete: {len(chunk_ids)} chunks stored")
        else:
            print(f"  ✗ Failed: No chunks stored")

    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()

def monitor_loop():
    """Main monitoring loop"""
    print("="*60)
    print("AUTO-STORAGE SYSTEM v2 (COMPLETE PIPELINE)")
    print("="*60)
    print(f"API: {API_BASE_URL}")
    print(f"Memory directory: {MEMORY_DIR}")
    print("Pipeline: chunk → embed → vector → graph")
    print("="*60)

    while True:
        try:
            # Monitor memory directory
            if MEMORY_DIR.exists():
                for memory_file in MEMORY_DIR.glob("*.md"):
                    # Skip index files
                    if memory_file.name in ['MEMORY.md', 'README.md']:
                        continue

                    # Validate path to prevent symlink traversal
                    resolved_path = memory_file.resolve()
                    # Ensure resolved path is still within MEMORY_DIR
                    try:
                        resolved_path.relative_to(MEMORY_DIR)
                    except ValueError:
                        print(f"  ✗ Security: Skipping {memory_file.name} (symlink escape detected)")
                        continue

                    store_memory_via_api(memory_file)

            time.sleep(10)  # Check every 10 seconds

        except KeyboardInterrupt:
            print("\n\n[AUTO-STORAGE] Shutting down...")
            break
        except Exception as e:
            print(f"\n[AUTO-STORAGE] Loop error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(30)

if __name__ == "__main__":
    monitor_loop()
