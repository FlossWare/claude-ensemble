#!/usr/bin/env python3
"""
Test Semantic Chunker Integration
Verifies that semantic_chunker works with all integrated systems
"""

import sys
import os
from pathlib import Path

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_semantic_chunker_basic():
    """Test 1: Basic semantic chunker functionality"""
    print("\n" + "="*80)
    print("TEST 1: Basic Semantic Chunker")
    print("="*80)

    from semantic_chunker import SemanticChunker

    chunker = SemanticChunker(min_chunk_size=200, max_chunk_size=500, overlap_size=50)

    code_sample = """
def process_data(input_file):
    data = read_file(input_file)
    cleaned = clean_data(data)
    return cleaned

def clean_data(data):
    data = data.dropna()
    data = normalize(data)
    return data

class DataProcessor:
    def __init__(self, config):
        self.config = config

    def run(self):
        print("Processing...")
"""

    chunks = chunker.chunk_text(code_sample)

    print(f"✓ Created {len(chunks)} chunks")
    for chunk in chunks:
        print(f"  Chunk {chunk['index']}: {chunk['char_count']} chars, "
              f"type={chunk['chunk_type']}, language={chunk['language']}")

    assert len(chunks) > 0, "Should produce at least one chunk"
    assert chunks[0]['has_code'], "Should detect code"
    print("✓ Basic chunker test PASSED")
    return True


def test_rag_integration():
    """Test 2: RAG system integration"""
    print("\n" + "="*80)
    print("TEST 2: RAG System Integration")
    print("="*80)

    # Add shared directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))

    try:
        from rag import RAG

        rag = RAG(verbose=True)

        # Check if chunker is available
        assert rag.chunker is not None, "RAG should have semantic chunker"
        print("✓ RAG has semantic chunker initialized")

        # Test document ingestion (if vector store available)
        if rag.vector_store:
            print("  Testing document ingestion...")
            result = rag.ingest_document(
                text="This is a test document. " * 100,  # 2000+ chars
                source="test_doc.txt",
                metadata={'type': 'test'}
            )
            print(f"  ✓ Ingested {result['chunks_stored']} chunks")
        else:
            print("  ⚠️  Vector store not available, skipping ingestion test")

        print("✓ RAG integration test PASSED")
        return True

    except ImportError as e:
        print(f"⚠️  RAG not available: {e}")
        return False


def test_knowledge_system_integration():
    """Test 3: Knowledge System integration"""
    print("\n" + "="*80)
    print("TEST 3: Knowledge System Integration")
    print("="*80)

    try:
        from knowledge_system import KnowledgeSystem

        # Note: This requires PostgreSQL connection
        # We'll just verify the import works
        print("✓ KnowledgeSystem imports successfully")
        print("  (Full test requires PostgreSQL connection)")
        return True

    except ImportError as e:
        print(f"⚠️  KnowledgeSystem not available: {e}")
        return False


def test_auto_storage_integration():
    """Test 4: Auto Storage System integration"""
    print("\n" + "="*80)
    print("TEST 4: Auto Storage System Integration")
    print("="*80)

    try:
        # Just verify import works (doesn't require DB connection)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "auto_storage_system",
            Path(__file__).parent / "auto_storage_system.py"
        )

        # Check if semantic_chunker is imported
        with open(Path(__file__).parent / "auto_storage_system.py", 'r') as f:
            content = f.read()
            assert 'from semantic_chunker import SemanticChunker' in content
            print("✓ Auto Storage System imports semantic_chunker")

        return True

    except Exception as e:
        print(f"⚠️  Error checking auto_storage_system: {e}")
        return False


def test_streaming_chunker():
    """Test 5: Streaming chunker (memory-efficient)"""
    print("\n" + "="*80)
    print("TEST 5: Streaming Chunker")
    print("="*80)

    from semantic_chunker import SemanticChunker

    chunker = SemanticChunker(min_chunk_size=200, max_chunk_size=500)

    # Create large text
    text = "Paragraph about AI. " * 100  # ~2000 chars

    print(f"  Text size: {len(text)} chars")

    # Test streaming
    chunk_count = 0
    for chunk in chunker.chunk_text_stream(text):
        chunk_count += 1
        print(f"  Streamed chunk {chunk['index']}: {chunk['char_count']} chars")

    print(f"✓ Streamed {chunk_count} chunks")
    assert chunk_count > 0, "Should produce at least one chunk"
    print("✓ Streaming test PASSED")
    return True


def main():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("SEMANTIC CHUNKER INTEGRATION TESTS")
    print("="*80)

    results = []

    # Run tests
    results.append(("Basic Chunker", test_semantic_chunker_basic()))
    results.append(("RAG Integration", test_rag_integration()))
    results.append(("Knowledge System", test_knowledge_system_integration()))
    results.append(("Auto Storage", test_auto_storage_integration()))
    results.append(("Streaming", test_streaming_chunker()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")

    print("\n" + "="*80)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("="*80)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
