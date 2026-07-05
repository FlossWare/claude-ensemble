#!/usr/bin/env python3
"""
Bulk fix path validation vulnerabilities in Python files

Applies path validation to all file operations automatically
"""

import os
import re
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Files to process
TOOLS_DIR = PROJECT_ROOT / 'tools'

# Track fixes
fixes_applied = 0
files_modified = 0
errors = []

def fix_python_file(filepath):
    """Add path validation to a Python file"""
    global fixes_applied, files_modified

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        local_fixes = 0

        # Skip if already imports path_validator
        if 'from path_validator import' in content or 'import path_validator' in content:
            print(f"  ⏭️  Already has path_validator: {filepath.name}")
            return

        # Skip test files and the validator itself
        if 'test_' in filepath.name or filepath.name == 'path_validator.py':
            return

        # Find imports section
        import_match = re.search(r'^(import\s+.*?$|from\s+.*?import\s+.*?$)', content, re.MULTILINE)
        if not import_match:
            print(f"  ⚠️  No imports found: {filepath.name}")
            return

        # Check if file has file operations
        has_file_ops = bool(
            re.search(r'\bopen\s*\(', content) or
            re.search(r'\bwith\s+open\s*\(', content)
        )

        if not has_file_ops:
            return

        # Add import after existing imports
        import_line = import_match.end()
        lines = content.split('\n')

        # Find last import line
        last_import_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                last_import_idx = i

        # Insert path_validator import
        lines.insert(last_import_idx + 1, 'from path_validator import validate_read_path, validate_write_path, safe_open')
        content = '\n'.join(lines)
        local_fixes += 1

        # Fix open() calls for reading
        # Pattern: open(filepath, 'r') or open(filepath) or open(filepath, 'rb')
        def fix_read_open(match):
            nonlocal local_fixes
            filepath_arg = match.group(1)
            mode = match.group(2) if match.group(2) else "'r'"

            # Skip if already validated
            if 'validate_' in filepath_arg or 'safe_' in filepath_arg:
                return match.group(0)

            local_fixes += 1
            # Replace with safe_open
            return f"safe_open({filepath_arg}, {mode}"

        # Pattern: with open(..., 'r') or open(..., 'r', ...)
        content = re.sub(
            r'\bopen\s*\(\s*([^,\)]+)\s*(?:,\s*([\'\"]r[b]?[\'\"]))?',
            fix_read_open,
            content
        )

        # Only write if changes were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            files_modified += 1
            fixes_applied += local_fixes
            print(f"  ✓ Fixed {local_fixes} issues in {filepath.name}")

    except Exception as e:
        errors.append(f"{filepath.name}: {e}")
        print(f"  ✗ Error fixing {filepath.name}: {e}")


def main():
    print("=" * 60)
    print("BULK PATH VALIDATION FIXER")
    print("=" * 60)

    # Process all Python files in tools/
    python_files = list(TOOLS_DIR.glob('*.py'))

    print(f"\nFound {len(python_files)} Python files in tools/")
    print("Processing...\n")

    for filepath in python_files:
        fix_python_file(filepath)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Files modified: {files_modified}")
    print(f"Fixes applied: {fixes_applied}")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  - {error}")

    print("=" * 60)

if __name__ == '__main__':
    main()
