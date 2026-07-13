#!/usr/bin/env python3
"""
Full Pipeline Integration Test
Tests: store → chunk → embed → graph

Pipeline Components:
1. Memory file detection and parsing
2. Semantic chunking for large content
3. REST API storage with 5-provider embedding cascade
4. OrientDB graph relationship creation
5. Deduplication and retry logic
"""

import os
import sys
import json
import time
import shutil
import tempfile
import requests
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

try:
    from semantic_chunker import SemanticChunker
    from path_validator import validate_read_path, validate_write_path
    DEPS_AVAILABLE = True
except ImportError as e:
    print(f"ERROR: Missing dependencies: {e}")
    DEPS_AVAILABLE = False

# Test configuration
API_BASE_URL = "http://aio-01:5000"
TEST_DIR = None
PASSED = 0
FAILED = 0

def log_test(name: str):
    print(f"\n\033[1;33m[TEST]\033[0m {name}")

def log_pass(message: str):
    global PASSED
    print(f"\033[0;32m✓ PASS\033[0m {message}")
    PASSED += 1

def log_fail(message: str):
    global FAILED
    print(f"\033[0;31m✗ FAIL\033[0m {message}")
    FAILED += 1

def log_info(message: str):
    print(f"\033[0;36mℹ INFO\033[0m {message}")

# ============================================================================
# TEST UTILITIES
# ============================================================================

def create_test_memory(filename: str, content: str, frontmatter: dict = None) -> Path:
    """Create a test memory file with optional frontmatter"""
    filepath = TEST_DIR / filename

    with open(filepath, 'w') as f:
        if frontmatter:
            f.write("---\n")
            for key, value in frontmatter.items():
                f.write(f"{key}: {value}\n")
            f.write("---\n\n")
        f.write(content)

    return filepath

def check_api_health() -> bool:
    """Check if REST API is available"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.ok
    except:
        return False

def wait_for_processing(delay: int = 2):
    """Wait for async processing"""
    time.sleep(delay)

# ============================================================================
# UNIT TESTS - Chunking
# ============================================================================

def test_semantic_chunker_initialization():
    """Test chunker initialization with valid parameters"""
    log_test("Chunker Initialization - Valid Parameters")

    try:
        chunker = SemanticChunker(
            min_chunk_size=500,
            max_chunk_size=1500,
            overlap_size=100
        )
        log_pass("Chunker initialized successfully")
        return chunker
    except Exception as e:
        log_fail(f"Chunker initialization failed: {e}")
        return None

def test_small_content_no_chunking(chunker: SemanticChunker):
    """Test that small content is NOT chunked"""
    log_test("Chunking - Small Content (No Split)")

    small_content = "This is a small memory file. " * 10  # ~300 chars

    try:
        chunks = chunker.chunk_text(small_content)

        if len(chunks) == 1:
            log_pass(f"Small content not chunked: {len(small_content)} chars → 1 chunk")
        else:
            log_fail(f"Small content incorrectly chunked into {len(chunks)} chunks")
    except Exception as e:
        log_fail(f"Small content chunking failed: {e}")

def test_large_content_chunking(chunker: SemanticChunker):
    """Test that large content IS chunked semantically"""
    log_test("Chunking - Large Content (Semantic Split)")

    # Create large content with clear paragraphs
    paragraphs = []
    for i in range(10):
        paragraphs.append(f"Paragraph {i+1}. " + ("This is test content. " * 50))

    large_content = "\n\n".join(paragraphs)  # ~10,000 chars

    try:
        chunks = chunker.chunk_text(large_content)

        if len(chunks) > 1:
            log_pass(f"Large content chunked: {len(large_content)} chars → {len(chunks)} chunks")

            # Verify overlap
            if chunks[0].get('content', '')[-50:] in chunks[1].get('content', ''):
                log_pass("Chunks have overlap for context preservation")
            else:
                log_fail("Chunks missing overlap")
        else:
            log_fail(f"Large content not chunked (expected multiple chunks)")
    except Exception as e:
        log_fail(f"Large content chunking failed: {e}")

def test_code_block_detection(chunker: SemanticChunker):
    """Test code block detection and preservation"""
    log_test("Chunking - Code Block Detection")

    content_with_code = """
# Python Code Example

Here's a function:

```python
def hello_world():
    print("Hello, World!")
    return True
```

And some more text after the code block.
""" * 5  # Make it long enough to potentially chunk

    try:
        chunks = chunker.chunk_text(content_with_code)

        # Check if any chunk is marked as containing code
        has_code = any(chunk.get('has_code', False) for chunk in chunks)

        if has_code:
            log_pass("Code blocks detected in chunks")
        else:
            log_fail("Code blocks not detected")
    except Exception as e:
        log_fail(f"Code block detection failed: {e}")

# ============================================================================
# INTEGRATION TESTS - API Storage
# ============================================================================

def test_api_health_check():
    """Test REST API availability"""
    log_test("API Health - Endpoint Available")

    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)

        if response.ok:
            log_pass(f"API healthy: {response.json()}")
        else:
            log_fail(f"API unhealthy: {response.status_code}")
    except Exception as e:
        log_fail(f"API connection failed: {e}")

def test_store_single_chunk():
    """Test storing a single-chunk memory via API"""
    log_test("API Storage - Single Chunk Memory")

    payload = {
        'memory_type': 'test',
        'content': 'This is a test memory for integration testing.',
        'metadata': {
            'source': 'test_pipeline',
            'source_file': 'test_single.md',
            'memory_name': 'Test Single Chunk',
            'is_chunk': False,
            'chunk_index': 0,
            'total_chunks': 1,
            'tags': ['test', 'integration']
        },
        'source_file': 'test_single.md'
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/learning/memory",
            json=payload,
            timeout=30
        )

        if response.ok:
            result = response.json()
            memory_id = result.get('id')
            has_embedding = result.get('has_embedding', False)

            log_pass(f"Single chunk stored: id={memory_id}")

            if has_embedding:
                log_pass(f"Embedding generated successfully")
            else:
                log_fail(f"Embedding generation failed (all providers failed)")

            return memory_id
        else:
            log_fail(f"API request failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        log_fail(f"Single chunk storage failed: {e}")
        return None

def test_store_multi_chunk():
    """Test storing multi-chunk memory via API"""
    log_test("API Storage - Multi-Chunk Memory")

    chunk_ids = []

    for i in range(3):
        payload = {
            'memory_type': 'test',
            'content': f'Chunk {i+1} of multi-chunk test. ' + ('Test content. ' * 100),
            'metadata': {
                'source': 'test_pipeline',
                'source_file': 'test_multi.md',
                'memory_name': 'Test Multi Chunk',
                'is_chunk': True,
                'chunk_index': i,
                'total_chunks': 3,
                'tags': ['test', 'multi-chunk']
            },
            'source_file': 'test_multi.md'
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
                log_info(f"Chunk {i+1}/3 stored: id={result['id']}")
            else:
                log_fail(f"Chunk {i+1} failed: {response.status_code}")
        except Exception as e:
            log_fail(f"Chunk {i+1} storage failed: {e}")

    if len(chunk_ids) == 3:
        log_pass(f"Multi-chunk storage complete: {len(chunk_ids)} chunks stored")
        return chunk_ids
    else:
        log_fail(f"Multi-chunk incomplete: {len(chunk_ids)}/3 chunks stored")
        return chunk_ids

def test_deduplication():
    """Test that duplicate content is not re-stored"""
    log_test("API Storage - Deduplication")

    content = "Duplicate test content for deduplication testing."

    payload = {
        'memory_type': 'test',
        'content': content,
        'metadata': {
            'source': 'test_pipeline',
            'source_file': 'test_duplicate.md',
            'memory_name': 'Test Duplicate',
            'is_chunk': False,
            'chunk_index': 0,
            'total_chunks': 1
        },
        'source_file': 'test_duplicate.md'
    }

    try:
        # Store first time
        response1 = requests.post(f"{API_BASE_URL}/learning/memory", json=payload, timeout=30)
        first_id = response1.json().get('id') if response1.ok else None

        # Store second time (should be deduplicated)
        response2 = requests.post(f"{API_BASE_URL}/learning/memory", json=payload, timeout=30)
        second_id = response2.json().get('id') if response2.ok else None

        if first_id and second_id:
            if first_id == second_id:
                log_pass(f"Deduplication working: same ID returned ({first_id})")
            else:
                log_fail(f"Deduplication failed: different IDs ({first_id} vs {second_id})")
        else:
            log_fail("Deduplication test incomplete: storage failed")
    except Exception as e:
        log_fail(f"Deduplication test failed: {e}")

# ============================================================================
# INTEGRATION TESTS - Graph Relationships
# ============================================================================

def test_graph_vertex_creation(memory_ids: list):
    """Test OrientDB vertex creation for memories"""
    log_test("Graph - Vertex Creation")

    if not memory_ids:
        log_fail("No memory IDs to create vertices for")
        return

    try:
        # Query for vertices
        query = f"SELECT FROM Memory WHERE memory_id IN [{','.join(map(str, memory_ids))}]"

        response = requests.post(
            f"{API_BASE_URL}/graph/query",
            json={'query': query},
            timeout=10
        )

        if response.ok:
            result = response.json()
            vertices = result.get('result', [])

            if len(vertices) > 0:
                log_pass(f"Graph vertices created: {len(vertices)}/{len(memory_ids)}")
            else:
                log_fail("No graph vertices found")
        else:
            log_fail(f"Graph query failed: {response.status_code}")
    except Exception as e:
        # Graph relationships are best-effort, so just log warning
        log_info(f"Graph vertex check failed (non-fatal): {e}")

def test_graph_edge_creation(memory_ids: list):
    """Test OrientDB edge creation (NextChunk) for multi-chunk memories"""
    log_test("Graph - Edge Creation (NextChunk)")

    if len(memory_ids) < 2:
        log_info("Skipping edge test (need at least 2 chunks)")
        return

    try:
        # Query for NextChunk edges
        query = f"""
            SELECT FROM NextChunk WHERE
            out.memory_id = {memory_ids[0]} AND
            in.memory_id = {memory_ids[1]}
        """

        response = requests.post(
            f"{API_BASE_URL}/graph/query",
            json={'query': query},
            timeout=10
        )

        if response.ok:
            result = response.json()
            edges = result.get('result', [])

            if len(edges) > 0:
                log_pass(f"NextChunk edges created: {len(edges)}")
            else:
                log_fail("No NextChunk edges found")
        else:
            log_fail(f"Edge query failed: {response.status_code}")
    except Exception as e:
        log_info(f"Graph edge check failed (non-fatal): {e}")

# ============================================================================
# E2E PIPELINE TEST
# ============================================================================

def test_complete_pipeline():
    """
    Test the complete pipeline end-to-end:
    1. Create memory file with frontmatter
    2. Parse and chunk content
    3. Store via API with embeddings
    4. Create graph relationships
    5. Verify all components
    """
    log_test("E2E Pipeline - Complete Workflow")

    # Step 1: Create test memory file
    log_info("Step 1: Creating test memory file...")

    frontmatter = {
        'type': 'reference',
        'name': 'E2E Pipeline Test',
        'tags': 'test,e2e,pipeline'
    }

    # Create large content that will be chunked
    content_parts = []
    for i in range(5):
        content_parts.append(f"""
## Section {i+1}

This is section {i+1} of the end-to-end pipeline test. This content is designed
to test the complete flow from file creation through chunking, embedding, and
graph relationship creation.

{'Test content. ' * 100}
""")

    large_content = "\n\n".join(content_parts)

    filepath = create_test_memory('test_e2e_pipeline.md', large_content, frontmatter)
    log_pass(f"Memory file created: {filepath.name} ({len(large_content)} chars)")

    # Step 2: Chunk content
    log_info("Step 2: Chunking content...")

    chunker = SemanticChunker(min_chunk_size=500, max_chunk_size=1500, overlap_size=100)
    chunks = chunker.chunk_text(large_content)

    log_pass(f"Content chunked: {len(chunks)} chunks")

    # Step 3: Store each chunk via API
    log_info("Step 3: Storing chunks via API...")

    chunk_ids = []
    for chunk in chunks:
        payload = {
            'memory_type': frontmatter['type'],
            'content': chunk['content'],
            'metadata': {
                'source': 'test_pipeline',
                'source_file': filepath.name,
                'memory_name': frontmatter['name'],
                'is_chunk': len(chunks) > 1,
                'chunk_index': chunk['index'],
                'total_chunks': len(chunks),
                'char_count': chunk['char_count'],
                'has_code': chunk.get('has_code', False),
                'chunk_type': chunk['chunk_type'],
                'tags': frontmatter['tags'].split(',')
            },
            'source_file': filepath.name
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

                has_embedding = result.get('has_embedding', False)
                if has_embedding:
                    log_info(f"  Chunk {chunk['index']}: stored with embedding (id={result['id']})")
                else:
                    log_info(f"  Chunk {chunk['index']}: stored without embedding (id={result['id']})")
            else:
                log_fail(f"  Chunk {chunk['index']}: storage failed ({response.status_code})")
        except Exception as e:
            log_fail(f"  Chunk {chunk['index']}: error - {e}")

    if len(chunk_ids) == len(chunks):
        log_pass(f"All chunks stored: {len(chunk_ids)}/{len(chunks)}")
    else:
        log_fail(f"Incomplete storage: {len(chunk_ids)}/{len(chunks)} chunks")

    # Step 4: Verify graph relationships
    log_info("Step 4: Verifying graph relationships...")
    wait_for_processing(2)

    test_graph_vertex_creation(chunk_ids)
    test_graph_edge_creation(chunk_ids)

    # Step 5: Query and verify
    log_info("Step 5: Querying stored memories...")

    try:
        # Query PostgreSQL for stored memories
        response = requests.get(
            f"{API_BASE_URL}/learning/memories",
            params={'source_file': filepath.name},
            timeout=10
        )

        if response.ok:
            memories = response.json()
            if len(memories) > 0:
                log_pass(f"Memories retrievable: {len(memories)} found")
            else:
                log_fail("No memories found in query")
        else:
            log_fail(f"Memory query failed: {response.status_code}")
    except Exception as e:
        log_fail(f"Memory query error: {e}")

    log_pass("E2E pipeline test complete")

# ============================================================================
# MAIN
# ============================================================================

def main():
    global TEST_DIR

    print("=" * 70)
    print("AUTOSTORAGE FULL PIPELINE INTEGRATION TEST")
    print("=" * 70)
    print(f"API: {API_BASE_URL}")
    print(f"Components: chunk → embed → vector → graph")
    print("=" * 70)

    if not DEPS_AVAILABLE:
        print("\n\033[0;31mERROR:\033[0m Missing dependencies (semantic_chunker, path_validator)")
        sys.exit(1)

    # Check API availability
    if not check_api_health():
        print(f"\n\033[0;31mWARNING:\033[0m API at {API_BASE_URL} not responding")
        print("Some tests may fail. Continue anyway? (y/n): ", end='')
        if input().lower() != 'y':
            sys.exit(1)

    # Create temporary test directory
    TEST_DIR = Path(tempfile.mkdtemp(prefix='autostorage_test_'))
    log_info(f"Test directory: {TEST_DIR}")

    try:
        # Unit tests - Chunking
        chunker = test_semantic_chunker_initialization()
        if chunker:
            test_small_content_no_chunking(chunker)
            test_large_content_chunking(chunker)
            test_code_block_detection(chunker)

        # Integration tests - API
        test_api_health_check()
        single_id = test_store_single_chunk()
        multi_ids = test_store_multi_chunk()
        test_deduplication()

        # Integration tests - Graph
        if multi_ids:
            wait_for_processing(2)
            test_graph_vertex_creation(multi_ids)
            test_graph_edge_creation(multi_ids)

        # E2E Pipeline
        test_complete_pipeline()

    finally:
        # Cleanup
        if TEST_DIR and TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
            log_info(f"Test directory cleaned up: {TEST_DIR}")

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUITE COMPLETE")
    print("=" * 70)
    print(f"\033[0;32mPassed: {PASSED}\033[0m")
    print(f"\033[0;31mFailed: {FAILED}\033[0m")
    print("=" * 70)

    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
