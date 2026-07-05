#!/usr/bin/env python3
"""
Autostorage Integration Test Suite
Tests document detection, API integration, and error handling
"""

import asyncio
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

try:
    from auto_storage_system import (
        DocumentIngestionClient,
        detect_file_type_magic,
        validate_content_size,
        extract_document_from_tool_result,
        canonicalize_path,
        track_ingested_document_atomic,
        parse_tool_results_streaming,
        FIRMWARE_MAGIC_BYTES,
        MAX_CONTENT_SIZE,
    )
    AUTOSTORAGE_AVAILABLE = True
except ImportError as e:
    print(f"ERROR: Cannot import auto_storage_system: {e}")
    AUTOSTORAGE_AVAILABLE = False

# Test counters
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

# ============================================================================
# UNIT TESTS
# ============================================================================

def test_path_canonicalization():
    """Test path traversal protection"""
    log_test("Path Canonicalization - Traversal Protection")

    # Valid path within home directory
    valid_path = str(Path.home() / "test.txt")
    try:
        canonical = canonicalize_path(valid_path)
        if canonical.startswith(str(Path.home())):
            log_pass("Valid path accepted")
        else:
            log_fail(f"Valid path rejected: {canonical}")
    except ValueError:
        log_fail("Valid path raised ValueError")

    # Path traversal attempt
    try:
        canonicalize_path("/etc/passwd")
        log_fail("Path traversal attack accepted (should reject)")
    except ValueError:
        log_pass("Path traversal attack blocked")

def test_file_type_detection():
    """Test magic byte detection for various file types"""
    log_test("File Type Detection - Magic Bytes")

    test_cases = [
        (b'%PDF-1.4', 'test.pdf', 'pdf'),
        (b'\x89PNG\r\n\x1a\n', 'test.png', 'image'),
        (b'def hello():', 'test.py', 'code'),
        (b'hsqs', 'firmware.bin', 'firmware'),
        (b'\x27\x05\x19\x56', 'uboot.bin', 'firmware'),
    ]

    for magic_bytes, filename, expected_type in test_cases:
        detected = detect_file_type_magic(filename, magic_bytes + b'\x00' * 2048)
        if detected == expected_type:
            log_pass(f"Detected {filename} as {expected_type}")
        else:
            log_fail(f"Detected {filename} as {detected} (expected {expected_type})")

def test_content_size_validation():
    """Test content size limits for different file types"""
    log_test("Content Size Validation - Limits Enforcement")

    # Valid sizes
    valid_text = "x" * (5 * 1024 * 1024)  # 5MB text
    valid, error = validate_content_size(valid_text, 'text')
    if valid:
        log_pass("5MB text accepted (under 10MB limit)")
    else:
        log_fail(f"5MB text rejected: {error}")

    # Oversized content
    oversized_text = "x" * (15 * 1024 * 1024)  # 15MB text
    valid, error = validate_content_size(oversized_text, 'text')
    if not valid:
        log_pass(f"15MB text rejected: {error}")
    else:
        log_fail("15MB text accepted (should reject)")

def test_firmware_detection():
    """Test firmware magic byte detection"""
    log_test("Firmware Detection - Magic Byte Database")

    detected_count = 0
    for magic_bytes, fw_type in FIRMWARE_MAGIC_BYTES.items():
        content = magic_bytes + b'\x00' * 2048
        file_type = detect_file_type_magic(f"test_{fw_type}.bin", content)
        if file_type == 'firmware':
            detected_count += 1

    if detected_count == len(FIRMWARE_MAGIC_BYTES):
        log_pass(f"All {detected_count} firmware types detected")
    else:
        log_fail(f"Only {detected_count}/{len(FIRMWARE_MAGIC_BYTES)} firmware types detected")

def test_tool_result_extraction():
    """Test extraction of documents from Read tool results"""
    log_test("Tool Result Extraction - Read Tool Format")

    # Format 1: Direct output
    tool_result_1 = {
        'file_path': '/home/user/test.txt',
        'content': 'Test content',
        'timestamp': datetime.now().isoformat()
    }

    doc = extract_document_from_tool_result(tool_result_1)
    if doc and doc['file_path'] == '/home/user/test.txt':
        log_pass("Format 1 (direct output) extracted correctly")
    else:
        log_fail("Format 1 extraction failed")

    # Format 2: Nested input/output
    tool_result_2 = {
        'input': {'file_path': '/home/user/test2.txt'},
        'output': 'Test content 2'
    }

    doc = extract_document_from_tool_result(tool_result_2)
    if doc and doc['file_path'] == '/home/user/test2.txt':
        log_pass("Format 2 (nested input/output) extracted correctly")
    else:
        log_fail("Format 2 extraction failed")

async def test_streaming_parser():
    """Test ijson streaming parser with size limits"""
    log_test("Streaming Parser - JSONL Processing")

    # Create test JSONL file
    test_file = Path("/tmp/test_session.jsonl")
    with open(test_file, 'w') as f:
        # Small valid record
        f.write(json.dumps({
            'type': 'tool_use',
            'tool': 'Read',
            'file_path': '/home/user/small.txt',
            'content': 'x' * 1000
        }) + '\n')

        # Large record exceeding MAX_CONTENT_SIZE
        f.write(json.dumps({
            'type': 'tool_use',
            'tool': 'Read',
            'file_path': '/home/user/large.txt',
            'content': 'x' * (MAX_CONTENT_SIZE + 1000)
        }) + '\n')

    parsed_count = 0
    async for record in parse_tool_results_streaming(test_file):
        parsed_count += 1

    # Should only parse the small record
    if parsed_count == 1:
        log_pass("Streaming parser filtered oversized content")
    else:
        log_fail(f"Streaming parser returned {parsed_count} records (expected 1)")

    test_file.unlink()

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

async def test_api_client_connection():
    """Test API client connection pooling"""
    log_test("API Client - Connection Pool")

    try:
        client = DocumentIngestionClient(
            base_url='http://aio-01:8000',
            max_retries=3,
            timeout=10
        )
        log_pass("API client initialized successfully")
        await client.close()
        log_pass("Connection pool closed cleanly")
    except Exception as e:
        log_fail(f"API client initialization failed: {e}")

async def test_api_duplicate_check():
    """Test deduplication via API"""
    log_test("API Integration - Duplicate Check")

    try:
        client = DocumentIngestionClient(base_url='http://aio-01:8000')

        # Create unique hash
        test_hash = hashlib.sha256(b"unique_test_content_12345").hexdigest()

        # First check should return False
        exists = await client.check_duplicate(test_hash)
        if not exists:
            log_pass("New content hash not found (expected)")
        else:
            log_fail("New content hash found in database (unexpected)")

        await client.close()
    except Exception as e:
        log_fail(f"Duplicate check failed: {e}")

async def test_api_text_ingestion():
    """Test text ingestion via API"""
    log_test("API Integration - Text Ingestion")

    try:
        client = DocumentIngestionClient(base_url='http://aio-01:8000')

        test_content = f"Autostorage test document {datetime.now().isoformat()}"
        content_hash = hashlib.sha256(test_content.encode()).hexdigest()

        result = await client.ingest_text(
            text=test_content,
            source='/tmp/autostorage_test.txt',
            metadata={'title': 'Autostorage Test', 'tags': ['test', 'autostorage']},
            content_hash=content_hash
        )

        if result.get('success'):
            log_pass(f"Text ingestion successful (doc_id: {result.get('document_id', 'N/A')})")
        else:
            log_fail(f"Text ingestion failed: {result.get('error', 'unknown error')}")

        await client.close()
    except Exception as e:
        log_fail(f"Text ingestion test failed: {e}")

async def test_api_error_handling():
    """Test API error handling and retries"""
    log_test("API Integration - Error Handling")

    try:
        # Test with invalid base URL
        client = DocumentIngestionClient(base_url='https://invalid-host:9999', timeout=2)

        result = await client.ingest_text(
            text="test",
            source="/tmp/test.txt",
            metadata={},
            content_hash="test_hash"
        )

        if not result.get('success'):
            log_pass(f"Connection error handled gracefully: {result.get('error', 'N/A')}")
        else:
            log_fail("Invalid host connection succeeded (unexpected)")

        await client.close()
    except Exception as e:
        log_pass(f"Exception handled correctly: {type(e).__name__}")

async def test_atomic_tracking():
    """Test atomic file tracking with locks"""
    log_test("Atomic Tracking - File Lock")

    test_path = "/tmp/autostorage_test_atomic.txt"
    test_hash = hashlib.sha256(b"atomic_test").hexdigest()

    # Track successful ingestion
    try:
        track_ingested_document_atomic(test_path, test_hash, True)
        log_pass("Successful ingestion tracked atomically")
    except Exception as e:
        log_fail(f"Atomic tracking failed: {e}")

    # Track failed ingestion
    try:
        track_ingested_document_atomic(
            "/tmp/failed_test.txt",
            "failed_hash",
            False,
            error="test error",
            retry_count=2
        )
        log_pass("Failed ingestion tracked with error details")
    except Exception as e:
        log_fail(f"Failed tracking failed: {e}")

# ============================================================================
# E2E WORKFLOW TESTS
# ============================================================================

async def test_pdf_detection_and_ingestion():
    """Test full workflow: PDF detection → API → database"""
    log_test("E2E Workflow - PDF Detection and Ingestion")

    try:
        # Create test PDF
        from reportlab.pdfgen import canvas
        test_pdf = Path("/tmp/autostorage_e2e_test.pdf")
        c = canvas.Canvas(str(test_pdf))
        c.drawString(100, 750, "Autostorage E2E Test Document")
        c.drawString(100, 720, "This document tests the complete ingestion pipeline.")
        c.save()

        # Simulate Read tool result
        with open(test_pdf, 'rb') as f:
            pdf_content = f.read()

        file_type = detect_file_type_magic(str(test_pdf), pdf_content[:2048])

        if file_type == 'pdf':
            log_pass("PDF detected correctly via magic bytes")
        else:
            log_fail(f"PDF detected as {file_type} (expected pdf)")

        # Validate size
        valid, error = validate_content_size(pdf_content, 'pdf')
        if valid:
            log_pass("PDF size validation passed")
        else:
            log_fail(f"PDF size validation failed: {error}")

        # Ingest via API
        client = DocumentIngestionClient(base_url='http://aio-01:8000')
        content_hash = hashlib.sha256(pdf_content).hexdigest()

        result = await client.ingest_pdf(
            pdf_path=str(test_pdf),
            metadata={'title': 'E2E Test PDF', 'tags': ['e2e', 'test']},
            content_hash=content_hash
        )

        if result.get('success'):
            log_pass(f"PDF ingestion successful (doc_id: {result.get('document_id', 'N/A')})")
        else:
            log_fail(f"PDF ingestion failed: {result.get('error', 'unknown')}")

        await client.close()
        test_pdf.unlink()

    except Exception as e:
        log_fail(f"E2E PDF workflow failed: {e}")

async def test_session_processing():
    """Test session JSONL processing with document extraction"""
    log_test("E2E Workflow - Session Processing")

    try:
        # Create test session file
        test_session = Path("/tmp/test_session_e2e.jsonl")
        with open(test_session, 'w') as f:
            # Human message
            f.write(json.dumps({
                'type': 'human',
                'content': 'Please read the DFS documentation',
                'timestamp': datetime.now().isoformat()
            }) + '\n')

            # Assistant message
            f.write(json.dumps({
                'type': 'assistant',
                'content': 'I will read the file now',
                'timestamp': datetime.now().isoformat()
            }) + '\n')

            # Read tool result
            f.write(json.dumps({
                'type': 'tool_use',
                'tool': 'Read',
                'file_path': '/tmp/dfs_doc.txt',
                'content': 'DFS (Dynamic Frequency Selection) is required for 5GHz WiFi to avoid radar interference.'
            }) + '\n')

        # Parse session
        doc_count = 0
        async for record in parse_tool_results_streaming(test_session):
            doc = extract_document_from_tool_result(record)
            if doc:
                doc_count += 1

        if doc_count > 0:
            log_pass(f"Extracted {doc_count} document(s) from session")
        else:
            log_fail("No documents extracted from session")

        test_session.unlink()

    except Exception as e:
        log_fail(f"Session processing failed: {e}")

# ============================================================================
# MAIN
# ============================================================================

async def main():
    print("=" * 60)
    print("AUTOSTORAGE INTEGRATION TEST SUITE")
    print("=" * 60)

    if not AUTOSTORAGE_AVAILABLE:
        print("\n\033[0;31mERROR:\033[0m auto_storage_system.py not available")
        sys.exit(1)

    # Unit tests
    test_path_canonicalization()
    test_file_type_detection()
    test_content_size_validation()
    test_firmware_detection()
    test_tool_result_extraction()
    await test_streaming_parser()

    # Integration tests
    await test_api_client_connection()
    await test_api_duplicate_check()
    await test_api_text_ingestion()
    await test_api_error_handling()
    await test_atomic_tracking()

    # E2E workflow tests
    await test_pdf_detection_and_ingestion()
    await test_session_processing()

    # Summary
    print("\n" + "=" * 60)
    print("AUTOSTORAGE TEST SUITE COMPLETE")
    print("=" * 60)
    print(f"\033[0;32mPassed: {PASSED}\033[0m")
    print(f"\033[0;31mFailed: {FAILED}\033[0m")
    print("=" * 60)

    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
