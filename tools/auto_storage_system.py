#!/usr/bin/env python3
"""
Automatic Storage System - Stores conversations, memory, workflows, issues, sessions
Runs continuously, monitors for new data, and auto-stores to PostgreSQL + Neo4j
IMPROVED: Uses semantic chunker for intelligent text segmentation
"""

import os
import json
import time
import psycopg2
import hashlib
import fcntl
import sys
from datetime import datetime
from pathlib import Path

# Import semantic chunker and path validator
sys.path.insert(0, str(Path(__file__).parent))
from semantic_chunker import SemanticChunker
from path_validator import validate_read_path, validate_write_path

# Paths to monitor
PROJECTS_ROOT = Path.home() / ".claude" / "projects"
CURRENT_PROJECT_DIR = Path.home() / ".claude" / "projects" / "-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills"
MEMORY_DIR = CURRENT_PROJECT_DIR / "memory"
WORKFLOWS_DIR = Path("/tmp/claude-1000/-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills")

# Database connection - aio-01 is main instance, laptop-01 is backup only
conn = psycopg2.connect(host="aio-01", port=5433, database="learning", user="claude")

# Initialize semantic chunker
chunker = SemanticChunker(min_chunk_size=500, max_chunk_size=1500, overlap_size=100)

# Track processed files
PROCESSED_FILE = Path.home() / ".claude" / "learning" / "auto_storage_processed.json"
processed = {}

if PROCESSED_FILE.exists():
    # Validate path before reading
    valid_processed_file = validate_read_path(str(PROCESSED_FILE))
    with open(valid_processed_file, 'r') as f:
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

    # Validate path before writing
    valid_processed_file = validate_write_path(str(PROCESSED_FILE))

    # Use exclusive lock to prevent concurrent writes
    with open(valid_processed_file, 'w') as f:
        try:
            # Acquire exclusive lock (blocks if another process has it)
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(processed, f, indent=2)
        finally:
            # Release lock (happens automatically on close, but explicit is better)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def file_hash(filepath):
    """Calculate file hash to detect changes"""
    # Validate path before reading
    valid_filepath = validate_read_path(str(filepath))
    with open(valid_filepath, 'rb') as f:
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

        # Validate session file path
        valid_session_file = validate_read_path(str(session_file))

        # Parse JSONL
        messages = []
        with open(valid_session_file, 'r') as f:
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

        # Chunk messages using semantic chunker (IMPROVED)
        # Combine messages into single text for semantic analysis
        full_text = "\n\n".join([f"[{msg['type']}] {msg['content']}" for msg in messages])

        # Use semantic chunker for intelligent segmentation
        semantic_chunks = chunker.chunk_text(full_text)

        # Convert to format expected by storage code
        chunks = []
        for chunk in semantic_chunks:
            chunks.append({
                'text': chunk['content'],
                'index': chunk['index'],
                'char_count': chunk['char_count'],
                'has_code': chunk['has_code'],
                'chunk_type': chunk['chunk_type'],
                'language': chunk.get('language', 'unknown')
            })

        print(f"  ✓ Semantic chunking: {len(messages)} messages → {len(chunks)} chunks ({chunks[0]['chunk_type'] if chunks else 'N/A'})")

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
                    chunk.get('has_code', False),  # Use semantic chunker's detection
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

        print(f"  ✓ Stored {inserted} semantic chunks")

        # Extract and store model tuning data
        extract_and_store_model_tuning(session_file)

        # Extract and store procedural rules
        extract_and_store_procedural_rules(session_file)

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

        # Validate memory file path
        valid_memory_file = validate_read_path(str(memory_file))

        # Read memory content
        with open(valid_memory_file, 'r') as f:
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

        # Validate workflow file path
        valid_workflow_file = validate_read_path(str(workflow_file))

        # Read workflow output
        with open(valid_workflow_file, 'r') as f:
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

def extract_and_store_model_tuning(session_file):
    """Extract model performance data and update monitoring.model_tuning"""
    try:
        # Validate session file path
        valid_session_file = validate_read_path(str(session_file))

        # Parse JSONL for model usage patterns
        model_tasks = {}  # model -> {task_type -> [quality, cost, duration]}

        with open(valid_session_file, 'r') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    # Look for tool_use records with model/quality metadata
                    if record.get('type') == 'tool_use' and 'model' in record:
                        model = record.get('model', 'unknown')
                        task_type = record.get('task_type', 'general')
                        quality = record.get('quality_score', 0.0)
                        cost = record.get('cost_usd', 0.0)
                        duration = record.get('duration_ms', 0)

                        if model not in model_tasks:
                            model_tasks[model] = {}
                        if task_type not in model_tasks[model]:
                            model_tasks[model][task_type] = []

                        model_tasks[model][task_type].append({
                            'quality': quality,
                            'cost': cost,
                            'duration': duration
                        })
                except:
                    pass

        # Update model_tuning table
        cursor = conn.cursor()
        for model, tasks in model_tasks.items():
            for task_type, metrics in tasks.items():
                if not metrics:
                    continue

                avg_quality = sum(m['quality'] for m in metrics) / len(metrics)
                avg_cost = sum(m['cost'] for m in metrics) / len(metrics)
                avg_duration = sum(m['duration'] for m in metrics) / len(metrics)

                cursor.execute("""
                    INSERT INTO monitoring.model_tuning
                    (model, task_type, avg_quality, avg_cost_usd, avg_duration_ms, sample_count)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (model, task_type) DO UPDATE SET
                        avg_quality = (monitoring.model_tuning.avg_quality * monitoring.model_tuning.sample_count + EXCLUDED.avg_quality * EXCLUDED.sample_count) / (monitoring.model_tuning.sample_count + EXCLUDED.sample_count),
                        avg_cost_usd = (monitoring.model_tuning.avg_cost_usd * monitoring.model_tuning.sample_count + EXCLUDED.avg_cost_usd * EXCLUDED.sample_count) / (monitoring.model_tuning.sample_count + EXCLUDED.sample_count),
                        avg_duration_ms = (monitoring.model_tuning.avg_duration_ms * monitoring.model_tuning.sample_count + EXCLUDED.avg_duration_ms * EXCLUDED.sample_count) / (monitoring.model_tuning.sample_count + EXCLUDED.sample_count),
                        sample_count = monitoring.model_tuning.sample_count + EXCLUDED.sample_count,
                        updated_at = NOW()
                """, (model, task_type, avg_quality, avg_cost, avg_duration, len(metrics)))

        conn.commit()
        cursor.close()
        print(f"  ✓ Updated model_tuning for {len(model_tasks)} models")

    except Exception as e:
        print(f"  ⚠️  Error extracting model tuning: {e}")
        conn.rollback()

def extract_and_store_procedural_rules(session_file):
    """Extract procedural patterns and store to learning.procedural_rules"""
    try:
        # Validate session file path
        valid_session_file = validate_read_path(str(session_file))

        # Look for if-then patterns in assistant messages
        rules_found = []

        with open(valid_session_file, 'r') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if record.get('type') == 'assistant':
                        content = str(record.get('content', ''))

                        # Simple pattern matching for rules
                        # "if X then Y", "when X, do Y", etc.
                        import re
                        patterns = [
                            r'(?:if|when)\s+(.+?)\s+(?:then|do)\s+(.+?)[\.\n]',
                            r'always\s+(.+?)\s+(?:when|if)\s+(.+?)[\.\n]'
                        ]

                        for pattern in patterns:
                            matches = re.findall(pattern, content.lower(), re.MULTILINE)
                            for match in matches:
                                condition = match[0].strip()[:200]
                                action = match[1].strip()[:200]

                                # Hash the condition for deduplication
                                condition_hash = hashlib.sha256(condition.encode()).hexdigest()[:16]

                                rules_found.append({
                                    'condition_hash': condition_hash,
                                    'condition': {'text': condition},
                                    'action': action,
                                    'confidence': 0.7  # Default confidence
                                })
                except:
                    pass

        # Store unique rules
        cursor = conn.cursor()
        for rule in rules_found:
            cursor.execute("""
                INSERT INTO learning.procedural_rules
                (condition_hash, condition, action, confidence, evidence_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (condition_hash, action) DO UPDATE SET
                    confidence = LEAST(1.0, learning.procedural_rules.confidence + 0.05),
                    evidence_count = learning.procedural_rules.evidence_count + 1,
                    last_updated = NOW()
            """, (
                rule['condition_hash'],
                json.dumps(rule['condition']),
                rule['action'],
                rule['confidence'],
                1
            ))

        conn.commit()
        cursor.close()

        if rules_found:
            print(f"  ✓ Stored {len(rules_found)} procedural rules")

    except Exception as e:
        print(f"  ⚠️  Error extracting procedural rules: {e}")
        conn.rollback()

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

def store_api_call(api_data):
    """Store API call with full metrics to PostgreSQL

    Args:
        api_data: dict with keys:
            - messages: list of message dicts
            - response: response message dict
            - model: str
            - provider: str
            - worker_id: str
            - prompt_tokens: int
            - completion_tokens: int
            - cost_usd: float
            - latency_ms: int
            - timestamp: str (ISO format)
            - request_method: str (optional)
            - error_message: str (optional)
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv('PGHOST', 'aio-01'),
            port=int(os.getenv('PGPORT', '5433')),
            database=os.getenv('PGDATABASE', 'learning'),
            user=os.getenv('PGUSER', os.getenv('USER', 'claude'))
        )
        if not conn:
            print("[auto_storage] No database connection available")
            return False

        cur = conn.cursor()

        # Store full conversation context as JSON
        conversation_json = json.dumps({
            'messages': api_data.get('messages', []),
            'response': api_data.get('response', {}),
            'metadata': {
                'model': api_data.get('model'),
                'provider': api_data.get('provider'),
                'worker_id': api_data.get('worker_id'),
                'prompt_tokens': api_data.get('prompt_tokens'),
                'completion_tokens': api_data.get('completion_tokens'),
                'cost_usd': api_data.get('cost_usd'),
                'latency_ms': api_data.get('latency_ms'),
                'timestamp': api_data.get('timestamp'),
                'request_method': api_data.get('request_method', 'POST')
            }
        })

        # Chunk if large
        max_chunk_size = 10000
        if len(conversation_json) > max_chunk_size:
            chunks = [conversation_json[i:i+max_chunk_size]
                     for i in range(0, len(conversation_json), max_chunk_size)]
        else:
            chunks = [conversation_json]

        # Store each chunk with parameterized query (SQL injection safe)
        for idx, chunk in enumerate(chunks):
            cur.execute("""
                INSERT INTO auto_storage.api_calls
                (worker_id, model, provider, conversation_chunk, chunk_index,
                 prompt_tokens, completion_tokens, cost_usd, latency_ms,
                 request_method, error_message, request_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                api_data.get('worker_id', 'unknown'),
                api_data.get('model', 'unknown'),
                api_data.get('provider', 'unknown'),
                chunk,
                idx,
                api_data.get('prompt_tokens', 0),
                api_data.get('completion_tokens', 0),
                api_data.get('cost_usd', 0.0),
                api_data.get('latency_ms', 0),
                api_data.get('request_method', 'POST'),
                api_data.get('error_message'),
                api_data.get('timestamp')
            ))

        conn.commit()
        return True
    except psycopg2.Error as e:
        print(f"[auto_storage] PostgreSQL error storing API call: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        print(f"[auto_storage] Failed to store API call: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()
