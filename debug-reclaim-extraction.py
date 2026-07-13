#!/usr/bin/env python3
"""Debug atomic_reclaim_stale extraction"""

import sys
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).parent / 'shared'))

lua_path = Path('shared/redis-atomic-operations.lua')
lua_content = lua_path.read_text()

def extract_function(content: str, function_name: str) -> str:
    start_pattern = f"local function {function_name}("
    start = content.find(start_pattern)

    if start == -1:
        raise ValueError(f"Function {function_name} not found")

    lines = content[start:].split('\n')
    depth = 0
    end_line = 0

    for i, line in enumerate(lines):
        # Remove comments and strings
        stripped = re.sub(r'--.*$', '', line)
        stripped = re.sub(r'"[^"]*"', '', stripped)
        stripped = re.sub(r"'[^']*'", '', stripped)

        # Count block starters
        depth += len(re.findall(r'\b(function|if|for|while|repeat|do)\b', stripped))

        # Count block enders
        end_count = len(re.findall(r'\bend\b', stripped))
        until_count = len(re.findall(r'\buntil\b', stripped))
        depth -= (end_count + until_count)

        print(f"Line {i}: depth={depth:2d} | {line[:60]}")

        if depth == 0 and i > 0:
            end_line = i
            break

    function_text = '\n'.join(lines[:end_line+1])
    return function_text

# Test
print("Extracting atomic_reclaim_stale...\n")
try:
    func = extract_function(lua_content, 'atomic_reclaim_stale')
    print(f"\n\nExtracted {len(func)} characters")
    print("\n--- Extracted Function ---")
    print(func)
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
