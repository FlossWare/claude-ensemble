#!/usr/bin/env python3
"""
Automatic Storage System - FIXED VERSION with DLQ
Stores conversations, memory, workflows, issues, sessions
Uses REST API for full pipeline: chunk → embed → vector → graph

CHANGES FROM ORIGINAL:
1. Uses POST http://aio-01:5000/learning/memory instead of direct PostgreSQL
2. Integrates semantic chunking for large memories
3. Generates embeddings via 5-provider cascade
4. Creates graph relationships (via REST API)
5. Dead-Letter Queue (DLQ) for failed items after 3 retries
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
PROJECTS_ROOT = Path.home() / ".claude" / "projects"
CURRENT_PROJECT_DIR = Path.home() / ".claude" / "projects" / "-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills"
MEMORY_DIR = CURRENT_PROJECT_DIR / "memory"
WORKFLOWS_DIR = Path("/tmp/claude-1000/-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills")

# Dead-Letter Queue directory
DLQ_DIR = Path.home() / ".claude" / "learning" / "dlq"
DLQ_DIR.mkdir(parents=True, exist_ok=True)

# REST API endpoint
API_BASE_URL = "http://aio-01:5000"

# Initialize semantic chunker
chunker = SemanticChunker(min_chunk_size=500, max_chunk_size=1500, overlap_size=100)

# Track processed files
PROCESSED_FILE = Path.home() / ".claude" / "learning" / "auto_storage_processed.json"
processed = {}

# Track retry counts
RETRY_TRACKER_FILE = Path.home() / ".claude" / "learning" / "auto_storage_retries.json"
retry_tracker = {}

# Max retries before DLQ
MAX_RETRIES = 3

if PROCESSED_FILE.exists():
    valid_processed_file = validate_read_path(str(PROCESSED_FILE))
    with open(valid_processed_file, 'r') as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            processed = json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

if RETRY_TRACKER_FILE.exists():
    valid_retry_file = validate_read_path(str(RETRY_TRACKER_FILE))
    with open(valid_retry_file, 'r') as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            retry_tracker = json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

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

def save_retry_tracker():
    """Save retry tracker with exclusive file locking"""
    RETRY_TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    valid_retry_file = validate_write_path(str(RETRY_TRACKER_FILE))

    with open(valid_retry_file, 'w') as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(retry_tracker, f, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def send_to_dlq(item_path, item_type, error_info):
    """
    Send failed item to Dead-Letter Queue after MAX_RETRIES

    Args:
        item_path: Path to the failed item
        item_type: Type of item ('memory', 'session', 'workflow', 'chunk')
        error_info: Dict containing error details
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dlq_filename = f"{item_type}_{Path(item_path).stem}_{timestamp}.json"
        dlq_path = DLQ_DIR / dlq_filename

        dlq_entry = {
            'original_path': str(item_path),
            'item_type': item_type,
            'failed_at': datetime.now().isoformat(),
            'retry_count': retry_tracker.get(str(item_path), {}).get('count', 0),
            'error_info': error_info,
            'last_hash': retry_tracker.get(str(item_path), {}).get('hash', None)
        }

        valid_dlq_path = validate_write_path(str(dlq_path))
        with open(valid_dlq_path, 'w') as f:
            json.dump(dlq_entry, f, indent=2)

        print(f"  ⚠️  Sent to DLQ: {dlq_filename}")

        # Remove from retry tracker (it's in DLQ now)
        if str(item_path) in retry_tracker:
            del retry_tracker[str(item_path)]
            save_retry_tracker()

        return True

    except Exception as e:
        print(f"  ✗ Failed to send to DLQ: {e}")
        return False

def track_retry(item_path, current_hash, error_info):
    """
    Track retry attempts for a failed item

    Returns:
        bool: True if should retry, False if should send to DLQ
    """
    item_key = str(item_path)

    # Initialize or increment retry count
    if item_key not in retry_tracker:
        retry_tracker[item_key] = {
            'count': 1,
            'hash': current_hash,
            'first_failed': datetime.now().isoformat(),
            'last_failed': datetime.now().isoformat(),
            'last_error': error_info
        }
    else:
        retry_tracker[item_key]['count'] += 1
        retry_tracker[item_key]['last_failed'] = datetime.now().isoformat()
        retry_tracker[item_key]['last_error'] = error_info

    save_retry_tracker()

    retry_count = retry_tracker[item_key]['count']

    if retry_count >= MAX_RETRIES:
        print(f"  ⚠️  Max retries ({MAX_RETRIES}) reached")
        return False  # Send to DLQ
    else:
        print(f"  ↻ Retry {retry_count}/{MAX_RETRIES}")
        return True  # Keep retrying

def file_hash(filepath):
    """Calculate file hash to detect changes"""
    valid_filepath = validate_read_path(str(filepath))
    with open(valid_filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def store_memory_via_api(memory_file):
    """
    Store memory file using REST API with full pipeline:
    - Semantic chunking (if >1500 chars)
    - Embedding generation (5-provider cascade)
    - Vector storage (pgvector)
    - Graph relationships (OrientDB via /graph endpoints)
    - DLQ for failed items after MAX_RETRIES
    """
    try:
        print(f"\n[AUTO-STORAGE] Processing memory: {memory_file.name}")

        # Check if already processed
        current_hash = file_hash(memory_file)
        if processed.get(str(memory_file)) == current_hash:
            print(f"  ✓ Already processed (hash match)")
            # Clear from retry tracker if it was there
            if str(memory_file) in retry_tracker:
                del retry_tracker[str(memory_file)]
                save_retry_tracker()
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

        # Decide if chunking is needed
        content_length = len(actual_content)
        needs_chunking = content_length > 1500

        success = False

        if needs_chunking:
            print(f"  → Chunking large memory ({content_length} chars)")
            chunks = chunker.chunk_text(actual_content)
            print(f"  → Generated {len(chunks)} semantic chunks")

            # Store each chunk via REST API
            chunk_ids = []
            failed_chunks = []

            for chunk in chunks:
                payload = {
                    'memory_type': memory_type,
                    'content': chunk['content'],
                    'metadata': {
                        'source': 'auto-storage',
                        'source_file': memory_file.name,
                        'memory_name': memory_name,
                        'is_chunk': True,
                        'chunk_index': chunk['index'],
                        'total_chunks': len(chunks),
                        'char_count': chunk['char_count'],
                        'has_code': chunk['has_code'],
                        'language': chunk.get('language'),
                        'chunk_type': chunk['chunk_type']
                    },
                    'source_file': memory_file.name
                }

                try:
                    response = requests.post(
                        f"{API_BASE_URL}/learning/memory",
                        json=payload,
                        timeout=30
                    )

                    if response.ok:
                        result = response.json()
                        chunk_ids.append(result['id'])
                        print(f"    ✓ Chunk {chunk['index']}: id={result['id']}, embedding={result.get('has_embedding', False)}")
                    else:
                        failed_chunks.append({
                            'chunk_index': chunk['index'],
                            'status_code': response.status_code,
                            'error': response.text[:200]
                        })
                        print(f"    ✗ Chunk {chunk['index']} failed: HTTP {response.status_code}")

                except requests.RequestException as e:
                    failed_chunks.append({
                        'chunk_index': chunk['index'],
                        'error': str(e)
                    })
                    print(f"    ✗ Chunk {chunk['index']} error: {e}")

            if chunk_ids and not failed_chunks:
                print(f"  ✓ Stored {len(chunk_ids)} chunks with embeddings")
                processed[str(memory_file)] = current_hash
                save_processed()
                # Clear from retry tracker
                if str(memory_file) in retry_tracker:
                    del retry_tracker[str(memory_file)]
                    save_retry_tracker()
                success = True
            elif failed_chunks:
                # Some chunks failed - retry or DLQ
                error_info = {
                    'type': 'partial_chunk_failure',
                    'total_chunks': len(chunks),
                    'successful_chunks': len(chunk_ids),
                    'failed_chunks': failed_chunks
                }

                should_retry = track_retry(memory_file, current_hash, error_info)
                if not should_retry:
                    send_to_dlq(memory_file, 'memory_chunked', error_info)

        else:
            # Store as single memory (no chunking needed)
            print(f"  → Storing as single memory ({content_length} chars)")

            payload = {
                'memory_type': memory_type,
                'content': actual_content,
                'metadata': {
                    'source': 'auto-storage',
                    'source_file': memory_file.name,
                    'memory_name': memory_name,
                    'is_chunk': False
                },
                'source_file': memory_file.name
            }

            try:
                response = requests.post(
                    f"{API_BASE_URL}/learning/memory",
                    json=payload,
                    timeout=30
                )

                if response.ok:
                    result = response.json()
                    print(f"  ✓ Stored: id={result['id']}, embedding={result.get('has_embedding', False)}")
                    processed[str(memory_file)] = current_hash
                    save_processed()
                    # Clear from retry tracker
                    if str(memory_file) in retry_tracker:
                        del retry_tracker[str(memory_file)]
                        save_retry_tracker()
                    success = True
                else:
                    error_info = {
                        'type': 'api_error',
                        'status_code': response.status_code,
                        'error': response.text[:200]
                    }
                    print(f"  ✗ Failed: HTTP {response.status_code} - {response.text[:200]}")

                    should_retry = track_retry(memory_file, current_hash, error_info)
                    if not should_retry:
                        send_to_dlq(memory_file, 'memory', error_info)

            except requests.RequestException as e:
                error_info = {
                    'type': 'network_error',
                    'error': str(e)
                }
                print(f"  ✗ Error: {e}")

                should_retry = track_retry(memory_file, current_hash, error_info)
                if not should_retry:
                    send_to_dlq(memory_file, 'memory', error_info)

    except Exception as e:
        print(f"  ✗ Error storing memory: {e}")
        import traceback
        traceback.print_exc()

        error_info = {
            'type': 'exception',
            'error': str(e),
            'traceback': traceback.format_exc()
        }

        should_retry = track_retry(memory_file, file_hash(memory_file), error_info)
        if not should_retry:
            send_to_dlq(memory_file, 'memory', error_info)


def store_session(session_file):
    """
    Store session JSONL via REST API
    Conversations auto-ingested with embeddings for semantic search
    """
    try:
        print(f"\n[AUTO-STORAGE] Processing session: {session_file.name}")

        # Check if already processed
        current_hash = file_hash(session_file)
        if processed.get(str(session_file)) == current_hash:
            print(f"  ✓ Already processed (hash match)")
            # Clear from retry tracker
            if str(session_file) in retry_tracker:
                del retry_tracker[str(session_file)]
                save_retry_tracker()
            return

        # Read session JSONL
        valid_session_file = validate_read_path(str(session_file))
        with open(valid_session_file, 'r') as f:
            lines = f.readlines()

        if not lines:
            return

        # Store via REST API
        payload = {
            'session_file': session_file.name,
            'session_id': session_file.stem,
            'messages': [json.loads(line) for line in lines if line.strip()],
            'metadata': {
                'source': 'auto-storage',
                'total_messages': len(lines)
            }
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/learning/session",
                json=payload,
                timeout=60
            )

            if response.ok:
                result = response.json()
                print(f"  ✓ Stored session: {result.get('messages_stored', 0)} messages")
                processed[str(session_file)] = current_hash
                save_processed()
                # Clear from retry tracker
                if str(session_file) in retry_tracker:
                    del retry_tracker[str(session_file)]
                    save_retry_tracker()
            else:
                error_info = {
                    'type': 'api_error',
                    'status_code': response.status_code,
                    'error': response.text[:200]
                }
                print(f"  ✗ Failed: HTTP {response.status_code}")

                should_retry = track_retry(session_file, current_hash, error_info)
                if not should_retry:
                    send_to_dlq(session_file, 'session', error_info)

        except requests.RequestException as e:
            error_info = {
                'type': 'network_error',
                'error': str(e)
            }
            print(f"  ✗ Error: {e}")

            should_retry = track_retry(session_file, current_hash, error_info)
            if not should_retry:
                send_to_dlq(session_file, 'session', error_info)

    except Exception as e:
        print(f"  ✗ Error storing session: {e}")

        error_info = {
            'type': 'exception',
            'error': str(e),
            'traceback': traceback.format_exc()
        }

        should_retry = track_retry(session_file, file_hash(session_file), error_info)
        if not should_retry:
            send_to_dlq(session_file, 'session', error_info)


def store_workflow_result(workflow_file):
    """Store workflow execution results via REST API"""
    try:
        print(f"\n[AUTO-STORAGE] Processing workflow: {workflow_file.name}")

        # Check if already processed
        current_hash = file_hash(workflow_file)
        if processed.get(str(workflow_file)) == current_hash:
            print(f"  ✓ Already processed (hash match)")
            # Clear from retry tracker
            if str(workflow_file) in retry_tracker:
                del retry_tracker[str(workflow_file)]
                save_retry_tracker()
            return

        # Read workflow result JSON
        valid_workflow_file = validate_read_path(str(workflow_file))
        with open(valid_workflow_file, 'r') as f:
            workflow_data = json.load(f)

        # Store via REST API
        payload = {
            'workflow_file': workflow_file.name,
            'workflow_data': workflow_data,
            'metadata': {
                'source': 'auto-storage'
            }
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/workflows/execution",
                json=payload,
                timeout=60
            )

            if response.ok:
                result = response.json()
                print(f"  ✓ Stored workflow execution: {result.get('id')}")
                processed[str(workflow_file)] = current_hash
                save_processed()
                # Clear from retry tracker
                if str(workflow_file) in retry_tracker:
                    del retry_tracker[str(workflow_file)]
                    save_retry_tracker()
            else:
                error_info = {
                    'type': 'api_error',
                    'status_code': response.status_code,
                    'error': response.text[:200]
                }
                print(f"  ✗ Failed: HTTP {response.status_code}")

                should_retry = track_retry(workflow_file, current_hash, error_info)
                if not should_retry:
                    send_to_dlq(workflow_file, 'workflow', error_info)

        except requests.RequestException as e:
            error_info = {
                'type': 'network_error',
                'error': str(e)
            }
            print(f"  ✗ Error: {e}")

            should_retry = track_retry(workflow_file, current_hash, error_info)
            if not should_retry:
                send_to_dlq(workflow_file, 'workflow', error_info)

    except Exception as e:
        print(f"  ✗ Error storing workflow: {e}")

        error_info = {
            'type': 'exception',
            'error': str(e),
            'traceback': traceback.format_exc()
        }

        should_retry = track_retry(workflow_file, file_hash(workflow_file), error_info)
        if not should_retry:
            send_to_dlq(workflow_file, 'workflow', error_info)


def monitor_loop():
    """Main monitoring loop"""
    print("="*60)
    print("AUTO-STORAGE SYSTEM (FIXED VERSION with DLQ)")
    print("="*60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Memory directory: {MEMORY_DIR}")
    print(f"DLQ directory: {DLQ_DIR}")
    print(f"Max retries before DLQ: {MAX_RETRIES}")
    print(f"Using REST API with full pipeline:")
    print("  ✓ Semantic chunking (>1500 chars)")
    print("  ✓ Embedding generation (5-provider cascade)")
    print("  ✓ Vector storage (pgvector)")
    print("  ✓ Graph relationships (OrientDB)")
    print("  ✓ Dead-Letter Queue (DLQ) for failed items")
    print("="*60)

    while True:
        try:
            # Monitor memory directory
            if MEMORY_DIR.exists():
                for memory_file in MEMORY_DIR.glob("*.md"):
                    if memory_file.name in ['MEMORY.md', 'README.md']:
                        continue

                    store_memory_via_api(memory_file)

            # Monitor session/conversation files
            if CURRENT_PROJECT_DIR.exists():
                for session_file in CURRENT_PROJECT_DIR.glob("*.jsonl"):
                    store_session(session_file)

            # Monitor workflow results
            if WORKFLOWS_DIR.exists():
                # Workflow executions in subdirectories
                for workflow_dir in WORKFLOWS_DIR.glob("tasks/*/"):
                    for workflow_file in workflow_dir.glob("*.json"):
                        if 'workflow' in workflow_file.name.lower():
                            store_workflow_result(workflow_file)

            time.sleep(10)

        except KeyboardInterrupt:
            print("\n\n[AUTO-STORAGE] Shutting down...")
            break
        except Exception as e:
            print(f"\n[AUTO-STORAGE] Error in monitoring loop: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(30)


if __name__ == "__main__":
    monitor_loop()
