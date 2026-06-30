#!/usr/bin/env python3
"""
Automatic Storage System - Stores conversations, memory, workflows, issues, sessions
Runs continuously, monitors for new data, and auto-stores to PostgreSQL + Neo4j
"""

import os
import json
import time
import psycopg2
import hashlib
import fcntl
from datetime import datetime
from pathlib import Path

# Paths to monitor
PROJECTS_ROOT = Path.home() / ".claude" / "projects"
CURRENT_PROJECT_DIR = Path.home() / ".claude" / "projects" / "-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills"
MEMORY_DIR = CURRENT_PROJECT_DIR / "memory"
WORKFLOWS_DIR = Path("/tmp/claude-1000/-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills")

# Database connection - aio-01 is main instance, laptop-01 is backup only
conn = psycopg2.connect(host="aio-01", port=5433, database="learning", user="claude")

# Track processed files
PROCESSED_FILE = Path.home() / ".claude" / "learning" / "auto_storage_processed.json"
processed = {}

if PROCESSED_FILE.exists():
    with open(PROCESSED_FILE, 'r') as f:
        try:
            # Acquire shared lock for reading
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            processed = json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def save_processed():
    """Save processed file hashes with exclusive file locking"""
    # Ensure parent directory exists
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Use exclusive lock to prevent concurrent writes
    with open(PROCESSED_FILE, 'w') as f:
        try:
            # Acquire exclusive lock (blocks if another process has it)
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(processed, f, indent=2)
        finally:
            # Release lock (happens automatically on close, but explicit is better)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def file_hash(filepath):
    """Calculate file hash to detect changes"""
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def store_session(session_file):
    """Store session JSONL to PostgreSQL + Neo4j"""
    try:
        session_id = session_file.stem
        file_size = session_file.stat().st_size

        print(f"\n[AUTO-STORAGE] Processing session: {session_id}")
        print(f"  File: {session_file.name} ({file_size / 1024 / 1024:.1f} MB)")

        # Check if already processed
        current_hash = file_hash(session_file)
        if processed.get(str(session_file)) == current_hash:
            print(f"  ✓ Already processed (hash match)")
            return

        # Parse JSONL
        messages = []
        with open(session_file, 'r') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if record.get('type') in ['human', 'assistant']:
                        messages.append({
                            'type': record['type'],
                            'content': str(record.get('content', ''))[:5000],
                            'timestamp': record.get('timestamp', '')
                        })
                except:
                    pass

        if not messages:
            print(f"  ⚠️  No messages found, skipping")
            return

        # Chunk messages
        chunks = []
        chunk_size = 800
        current_chunk = ""
        chunk_index = 0

        for msg in messages:
            content = f"[{msg['type']}] {msg['content']}\n\n"

            if len(current_chunk) + len(content) > chunk_size:
                if current_chunk:
                    chunks.append({
                        'text': current_chunk.strip(),
                        'index': chunk_index,
                        'char_count': len(current_chunk)
                    })
                    chunk_index += 1
                current_chunk = content
            else:
                current_chunk += content

        if current_chunk:
            chunks.append({
                'text': current_chunk.strip(),
                'index': chunk_index,
                'char_count': len(current_chunk)
            })

        # Insert into PostgreSQL
        cursor = conn.cursor()
        inserted = 0

        for chunk in chunks:
            try:
                cursor.execute("""
                    INSERT INTO learning.session_chunks
                    (session_id, chunk_index, chunk_text, char_count, has_code, quality_score, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    session_id,
                    chunk['index'],
                    chunk['text'],
                    chunk['char_count'],
                    'import' in chunk['text'].lower() or 'def ' in chunk['text'],
                    0.75,
                    datetime.now()
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                print(f"  ⚠️  Error inserting chunk: {e}")
                conn.rollback()
                continue

        conn.commit()
        cursor.close()

        print(f"  ✓ Stored {inserted} chunks ({len(messages)} messages → {len(chunks)} chunks)")

        # Mark as processed
        processed[str(session_file)] = current_hash
        save_processed()

    except Exception as e:
        print(f"  ✗ Error storing session: {e}")
        conn.rollback()

def store_memory_file(memory_file):
    """Store memory markdown to PostgreSQL"""
    try:
        print(f"\n[AUTO-STORAGE] Processing memory: {memory_file.name}")

        # Check if already processed
        current_hash = file_hash(memory_file)
        if processed.get(str(memory_file)) == current_hash:
            print(f"  ✓ Already processed (hash match)")
            return

        # Read memory content
        with open(memory_file, 'r') as f:
            content = f.read()

        if not content.strip():
            return

        # Parse frontmatter
        frontmatter = {}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                fm_text = parts[1]
                for line in fm_text.strip().split('\n'):
                    if ':' in line:
                        key, val = line.split(':', 1)
                        frontmatter[key.strip()] = val.strip()
                content = parts[2].strip()

        memory_type = frontmatter.get('type', 'unknown')

        # Store as single chunk
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO learning.session_chunks
            (session_id, chunk_index, chunk_text, char_count, has_code, quality_score, created_at, keywords)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            f"memory-{memory_file.stem}",
            0,
            content[:5000],
            len(content),
            False,
            0.9,  # High quality for memory
            datetime.now(),
            '{memory,' + memory_type + '}'
        ))

        inserted = cursor.rowcount > 0
        conn.commit()
        cursor.close()

        if inserted:
            print(f"  ✓ Stored memory file (type: {memory_type})")
            processed[str(memory_file)] = current_hash
            save_processed()

    except Exception as e:
        print(f"  ✗ Error storing memory: {e}")
        conn.rollback()

def store_workflow_result(workflow_file):
    """Store workflow output to PostgreSQL"""
    try:
        print(f"\n[AUTO-STORAGE] Processing workflow: {workflow_file.name}")

        # Check if already processed
        current_hash = file_hash(workflow_file)
        if processed.get(str(workflow_file)) == current_hash:
            print(f"  ✓ Already processed (hash match)")
            return

        # Read workflow output
        with open(workflow_file, 'r') as f:
            content = f.read()

        if not content.strip():
            return

        # Store as single chunk
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO learning.session_chunks
            (session_id, chunk_index, chunk_text, char_count, has_code, quality_score, created_at, keywords)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            f"workflow-{workflow_file.stem}",
            0,
            content[:5000],
            len(content),
            True,  # Workflows often contain code
            0.8,
            datetime.now(),
            '{workflow,automation}'
        ))

        inserted = cursor.rowcount > 0
        conn.commit()
        cursor.close()

        if inserted:
            print(f"  ✓ Stored workflow result")
            processed[str(workflow_file)] = current_hash
            save_processed()

    except Exception as e:
        print(f"  ✗ Error storing workflow: {e}")
        conn.rollback()

def scan_existing_files(worker_id=0, total_workers=1):
    """Scan and process all existing files (with optional fleet distribution)"""
    print("\n" + "="*60)
    if total_workers > 1:
        print(f"SCANNING FILES (WORKER {worker_id}/{total_workers})")
    else:
        print("SCANNING EXISTING FILES (ALL PROJECTS)")
    print("="*60)

    # Sessions - scan ALL project directories
    if PROJECTS_ROOT.exists():
        session_files = list(PROJECTS_ROOT.rglob("*.jsonl"))

        # Filter by modulo for fleet distribution
        if total_workers > 1:
            my_files = [f for i, f in enumerate(session_files) if i % total_workers == worker_id]
            print(f"\nWorker {worker_id}: Processing {len(my_files)} of {len(session_files)} total files")
        else:
            my_files = session_files
            print(f"\nFound {len(session_files)} session files across all projects")

        print("Processing in batches...")
        for i, f in enumerate(my_files):
            store_session(f)
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i+1}/{len(my_files)} files processed")

    # Memory files
    if MEMORY_DIR.exists():
        memory_files = list(MEMORY_DIR.glob("*.md"))

        # Filter by modulo for fleet distribution
        if total_workers > 1:
            my_memory_files = [f for i, f in enumerate(memory_files) if i % total_workers == worker_id]
            print(f"\nWorker {worker_id}: Processing {len(my_memory_files)} of {len(memory_files)} memory files")
        else:
            my_memory_files = memory_files
            print(f"\nFound {len(memory_files)} memory files")

        for f in my_memory_files:
            store_memory_file(f)

    # Workflow outputs
    if WORKFLOWS_DIR.exists():
        workflow_files = []
        for session_dir in WORKFLOWS_DIR.iterdir():
            if session_dir.is_dir():
                task_dir = session_dir / "tasks"
                if task_dir.exists():
                    workflow_files.extend(task_dir.glob("*.output"))

        # Filter by modulo for fleet distribution
        if total_workers > 1:
            my_workflow_files = [f for i, f in enumerate(workflow_files) if i % total_workers == worker_id]
            print(f"\nWorker {worker_id}: Processing {len(my_workflow_files)} of {len(workflow_files)} workflow files")
        else:
            my_workflow_files = workflow_files
            print(f"\nFound {len(workflow_files)} workflow output files")

        for f in my_workflow_files:
            store_workflow_result(f)

def main():
    import sys

    # Parse arguments: --worker-id N --total-workers M
    worker_id = 0
    total_workers = 1

    for i, arg in enumerate(sys.argv):
        if arg == '--worker-id' and i + 1 < len(sys.argv):
            worker_id = int(sys.argv[i + 1])
        elif arg == '--total-workers' and i + 1 < len(sys.argv):
            total_workers = int(sys.argv[i + 1])

    # Validate worker_id
    if not (0 <= worker_id < total_workers):
        print(f"ERROR: Invalid worker_id={worker_id}. Must be in range [0, {total_workers-1}]", file=sys.stderr)
        sys.exit(1)

    print("="*60)
    if total_workers > 1:
        print(f"AUTO-STORAGE WORKER {worker_id}/{total_workers} STARTED")
    else:
        print("AUTO-STORAGE SYSTEM STARTED")
    print("="*60)

    # Initial scan
    scan_existing_files(worker_id, total_workers)

    # Status report
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM learning.session_chunks")
    total = cursor.fetchone()[0]
    cursor.close()

    print("\n" + "="*60)
    print(f"AUTO-STORAGE COMPLETE - {total} chunks stored")
    if total_workers > 1:
        print(f"Worker {worker_id} finished")
    else:
        print("Monitoring for new files...")
    print("="*60)

    # Only keep running if single worker (original behavior)
    if total_workers == 1:
        try:
            while True:
                time.sleep(300)  # Check every 5 minutes
                scan_existing_files(worker_id, total_workers)
        except KeyboardInterrupt:
            print("\nShutting down auto-storage...")
            conn.close()
    else:
        conn.close()

if __name__ == "__main__":
    main()
