#!/usr/bin/env python3
"""
Test path validation in auto_storage_system.py
"""

import sys
import os
from pathlib import Path

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

from path_validator import validate_read_path, validate_write_path

print("Testing path validation integration")
print("=" * 60)

# Test 1: Valid paths should work
print("\nTest 1: Valid paths")
try:
    valid = validate_read_path(os.path.expanduser('~/.claude/learning/test.json'))
    print(f"✓ Valid read path accepted: {valid}")
except ValueError as e:
    print(f"✗ Valid path rejected: {e}")

try:
    valid = validate_write_path('/tmp/test.json')
    print(f"✓ Valid write path accepted: {valid}")
except ValueError as e:
    print(f"✗ Valid path rejected: {e}")

# Test 2: Path traversal should be blocked
print("\nTest 2: Path traversal attacks")
try:
    bad = validate_read_path('/tmp/../etc/passwd')
    print(f"✗ Path traversal ALLOWED (VULNERABILITY): {bad}")
except ValueError as e:
    print(f"✓ Path traversal blocked: {e}")

try:
    bad = validate_read_path('/home/user/.claude/../../../etc/passwd')
    print(f"✗ Path traversal ALLOWED (VULNERABILITY): {bad}")
except ValueError as e:
    print(f"✓ Path traversal blocked: {e}")

# Test 3: Forbidden files should be blocked
print("\nTest 3: Forbidden files")
try:
    bad = validate_read_path(os.path.expanduser('~/.ssh/id_rsa'))
    print(f"✗ SSH key ALLOWED (VULNERABILITY): {bad}")
except ValueError as e:
    print(f"✓ SSH key blocked: {e}")

try:
    bad = validate_read_path('/tmp/.env')
    print(f"✗ .env file ALLOWED (VULNERABILITY): {bad}")
except ValueError as e:
    print(f"✓ .env file blocked: {e}")

# Test 4: Null byte injection should be blocked
print("\nTest 4: Null byte injection")
try:
    bad = validate_read_path('/tmp/test.txt\0/etc/passwd')
    print(f"✗ Null byte ALLOWED (VULNERABILITY): {bad}")
except ValueError as e:
    print(f"✓ Null byte blocked: {e}")

# Test 5: Absolute path resolution
print("\nTest 5: Absolute path resolution")
try:
    # This should resolve to /etc/passwd (outside allowed dirs)
    bad = validate_read_path(os.path.expanduser('~/.claude/../../../../../../etc/passwd'))
    print(f"✗ Traversal to /etc/passwd ALLOWED (VULNERABILITY): {bad}")
except ValueError as e:
    print(f"✓ Traversal to /etc/passwd blocked: {e}")

print("\n" + "=" * 60)
print("Path validation tests complete")
print("=" * 60)
