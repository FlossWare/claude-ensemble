#!/usr/bin/env python3
"""
Path Validation Library - Prevents path traversal vulnerabilities

Usage:
    from path_validator import validate_path, validate_read_path, validate_write_path

    # Throws exception if path is unsafe
    validate_path('/tmp/../etc/passwd')  # ValueError: Path traversal attempt

    # Validate against specific allowed directories
    validate_read_path('/home/user/.claude/learning/data.json')  # OK
    validate_write_path('/tmp/output.json')  # OK
"""

import os
import re
from pathlib import Path
from typing import List, Optional

# ============================================================================
# ALLOWED DIRECTORIES
# ============================================================================

HOME = os.path.expanduser('~')

# Directories where we can READ files (most permissive)
ALLOWED_READ_DIRS = [
    os.path.join(HOME, '.claude'),
    os.path.join(HOME, 'Development'),
    '/tmp',
    '/var/tmp',
]

# Directories where we can WRITE files (more restrictive)
ALLOWED_WRITE_DIRS = [
    os.path.join(HOME, '.claude', 'learning'),
    os.path.join(HOME, '.claude', 'reports'),
    os.path.join(HOME, '.claude', 'logs'),
    os.path.join(HOME, 'Development', 'redhat', 'scm', 'gitlab', 'cee', 'sfloess', 'claude-global-skills'),
    '/tmp',
]

# Forbidden patterns (even within allowed dirs)
FORBIDDEN_PATTERNS = [
    re.compile(r'/etc/passwd$'),
    re.compile(r'/etc/shadow$'),
    re.compile(r'\.ssh/id_rsa$'),
    re.compile(r'\.ssh/id_ed25519$'),
    re.compile(r'\.env$'),
    re.compile(r'secrets\.json$'),
    re.compile(r'credentials\.json$'),
    re.compile(r'\.aws/credentials$'),
]

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_path(file_path: str, allowed_dirs: Optional[List[str]] = None) -> str:
    """
    Validate a file path to prevent traversal attacks

    Args:
        file_path: Path to validate
        allowed_dirs: Array of allowed base directories (default: ALLOWED_READ_DIRS)

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path is unsafe or outside allowed directories
    """
    if allowed_dirs is None:
        allowed_dirs = ALLOWED_READ_DIRS

    if not file_path or not isinstance(file_path, str):
        raise ValueError('Invalid file path: must be non-empty string')

    # Resolve to absolute path (prevents ../ tricks)
    resolved = os.path.abspath(os.path.expanduser(file_path))

    # Check for null bytes (common injection technique)
    if '\0' in resolved:
        raise ValueError('Path traversal attempt: null byte detected')

    # Check if path is within allowed directories
    is_allowed = False
    for dir_path in allowed_dirs:
        normalized_dir = os.path.abspath(os.path.expanduser(dir_path))
        if resolved.startswith(normalized_dir + os.sep) or resolved == normalized_dir:
            is_allowed = True
            break

    if not is_allowed:
        raise ValueError(f'Access denied: {resolved} is outside allowed directories')

    # Check for forbidden patterns
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(resolved):
            raise ValueError(f'Access denied: {resolved} matches forbidden pattern')

    return resolved


def validate_read_path(file_path: str) -> str:
    """
    Validate path for READ operations (most permissive)

    Args:
        file_path: Path to validate

    Returns:
        Resolved absolute path
    """
    return validate_path(file_path, ALLOWED_READ_DIRS)


def validate_write_path(file_path: str) -> str:
    """
    Validate path for WRITE operations (more restrictive)

    Args:
        file_path: Path to validate

    Returns:
        Resolved absolute path
    """
    return validate_path(file_path, ALLOWED_WRITE_DIRS)


def is_path_safe(file_path: str, allowed_dirs: Optional[List[str]] = None) -> bool:
    """
    Check if a path is safe without throwing

    Args:
        file_path: Path to check
        allowed_dirs: Allowed directories

    Returns:
        True if path is safe
    """
    try:
        validate_path(file_path, allowed_dirs)
        return True
    except ValueError:
        return False


def validate_paths(paths: List[str], allowed_dirs: Optional[List[str]] = None) -> List[str]:
    """
    Validate multiple paths at once

    Args:
        paths: Array of paths to validate
        allowed_dirs: Allowed directories

    Returns:
        Array of resolved paths
    """
    return [validate_path(p, allowed_dirs) for p in paths]


# ============================================================================
# SAFE FILE OPERATIONS (convenience wrappers)
# ============================================================================

def safe_open(file_path: str, mode: str = 'r', **kwargs):
    """
    Safe open() with path validation

    Args:
        file_path: Path to file
        mode: File mode ('r', 'w', 'a', etc.)
        **kwargs: Additional arguments to open()

    Returns:
        File object
    """
    if 'r' in mode and 'w' not in mode and 'a' not in mode:
        # Read mode
        valid_path = validate_read_path(file_path)
    else:
        # Write/append mode
        valid_path = validate_write_path(file_path)

    return open(valid_path, mode, **kwargs)


def safe_read_file(file_path: str, encoding: str = 'utf-8') -> str:
    """
    Safe file read with path validation

    Args:
        file_path: Path to file
        encoding: Text encoding

    Returns:
        File contents as string
    """
    valid_path = validate_read_path(file_path)
    with open(valid_path, 'r', encoding=encoding) as f:
        return f.read()


def safe_write_file(file_path: str, content: str, encoding: str = 'utf-8') -> None:
    """
    Safe file write with path validation

    Args:
        file_path: Path to file
        content: Content to write
        encoding: Text encoding
    """
    valid_path = validate_write_path(file_path)
    with open(valid_path, 'w', encoding=encoding) as f:
        f.write(content)


def safe_exists(file_path: str) -> bool:
    """
    Safe os.path.exists() with path validation

    Args:
        file_path: Path to check

    Returns:
        True if file exists and path is safe
    """
    try:
        valid_path = validate_read_path(file_path)
        return os.path.exists(valid_path)
    except ValueError:
        return False


# ============================================================================
# TESTING
# ============================================================================

if __name__ == '__main__':
    print("Path Validator Tests")
    print("=" * 60)

    # Test 1: Normal path (should pass)
    try:
        result = validate_read_path('/tmp/test.txt')
        print(f"✓ Normal path: {result}")
    except ValueError as e:
        print(f"✗ Normal path failed: {e}")

    # Test 2: Path traversal (should fail)
    try:
        result = validate_read_path('/tmp/../etc/passwd')
        print(f"✗ Path traversal ALLOWED (BUG): {result}")
    except ValueError as e:
        print(f"✓ Path traversal blocked: {e}")

    # Test 3: Forbidden file (should fail)
    try:
        result = validate_read_path(os.path.expanduser('~/.ssh/id_rsa'))
        print(f"✗ Forbidden file ALLOWED (BUG): {result}")
    except ValueError as e:
        print(f"✓ Forbidden file blocked: {e}")

    # Test 4: Null byte injection (should fail)
    try:
        result = validate_read_path('/tmp/test.txt\0/etc/passwd')
        print(f"✗ Null byte injection ALLOWED (BUG): {result}")
    except ValueError as e:
        print(f"✓ Null byte injection blocked: {e}")

    # Test 5: Valid .claude path (should pass)
    try:
        result = validate_read_path(os.path.expanduser('~/.claude/learning/data.json'))
        print(f"✓ Valid .claude path: {result}")
    except ValueError as e:
        print(f"✗ Valid .claude path failed: {e}")

    print("=" * 60)
