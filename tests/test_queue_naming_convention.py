#!/usr/bin/env python3
"""
Test Queue Naming Convention Compliance

Verifies that ALL queue names follow the standard redis:queue: convention.

Run: python3 tests/test_queue_naming_convention.py
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Standard queue naming pattern
QUEUE_PATTERN = re.compile(r'"(redis:queue:[^"]+)"')  # Double quotes
QUEUE_PATTERN_SINGLE = re.compile(r"'(redis:queue:[^']+)'")  # Single quotes

# Old pattern (should NOT exist)
OLD_QUEUE_PATTERN = re.compile(r'"(queue:[^"]+)"')
OLD_QUEUE_PATTERN_SINGLE = re.compile(r"'(queue:[^']+)'")

# Exceptions (strings that look like queues but aren't)
EXCEPTIONS = {
    "queue: ",  # Log message
    "queue: {",  # Template
    "queue:",  # Incomplete
    "queue: Optional",  # Type annotation
    "queue: str",  # Type annotation
    "queue: dequeueTest",  # Function name
    "queue: enqueueTest",  # Function name
    "queue: status",  # Different context
}


def find_queue_references(file_path: Path) -> Tuple[List[str], List[str]]:
    """
    Find all queue references in a file.

    Returns:
        (standard_queues, old_queues) - Lists of queue names found
    """
    standard_queues = []
    old_queues = []

    try:
        content = file_path.read_text()

        # Find standard pattern (redis:queue:*)
        standard_queues.extend(QUEUE_PATTERN.findall(content))
        standard_queues.extend(QUEUE_PATTERN_SINGLE.findall(content))

        # Find old pattern (queue:* without redis: prefix)
        candidates = OLD_QUEUE_PATTERN.findall(content)
        candidates.extend(OLD_QUEUE_PATTERN_SINGLE.findall(content))

        # Filter out exceptions
        for candidate in candidates:
            if candidate not in EXCEPTIONS and not any(exc in candidate for exc in EXCEPTIONS):
                old_queues.append(candidate)

    except Exception as e:
        print(f"  Warning: Could not read {file_path}: {e}")

    return standard_queues, old_queues


def test_queue_naming_convention():
    """Test that all queue names follow the standard convention."""

    print("=" * 70)
    print("QUEUE NAMING CONVENTION TEST")
    print("=" * 70)
    print()
    print("Scanning for queue references...")
    print()

    # Files to check
    patterns = [
        "scripts/*.py",
        "scripts/*.sh",
        "workflows/*.mjs",
        "shared/*.js",
        "shared/*.mjs",
        "tests/*.py",
        "tests/*.mjs",
        "docs/*.md",
        "memory/*.md",
    ]

    all_standard = []
    all_old = {}  # file -> [old_queues]

    for pattern in patterns:
        for file_path in PROJECT_ROOT.glob(pattern):
            standard, old = find_queue_references(file_path)

            if standard:
                all_standard.extend(standard)

            if old:
                all_old[file_path] = old

    # Report results
    print(f"✓ Found {len(set(all_standard))} unique standard queue names:")
    for queue in sorted(set(all_standard)):
        print(f"  - {queue}")

    print()

    if all_old:
        print(f"✗ Found {sum(len(v) for v in all_old.values())} OLD queue names (missing redis: prefix):")
        print()
        for file_path, old_queues in sorted(all_old.items()):
            rel_path = file_path.relative_to(PROJECT_ROOT)
            print(f"  {rel_path}:")
            for queue in sorted(set(old_queues)):
                print(f"    - {queue}")
        print()
        print("=" * 70)
        print("TEST FAILED: Queue naming convention violations found!")
        print("=" * 70)
        print()
        print("Fix by replacing:")
        for old_queue in sorted(set(q for queues in all_old.values() for q in queues)):
            new_queue = "redis:" + old_queue
            print(f'  "{old_queue}" → "{new_queue}"')
        print()
        return False
    else:
        print("✓ No old queue names found")
        print()
        print("=" * 70)
        print("TEST PASSED: All queues follow redis:queue: convention!")
        print("=" * 70)
        return True


def main():
    """Run the test."""
    success = test_queue_naming_convention()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
