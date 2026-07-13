#!/usr/bin/env python3
"""Debug Lua function extraction"""

from pathlib import Path

lua_path = Path('shared/redis-atomic-operations.lua')
lua_content = lua_path.read_text()

def extract_function(content: str, function_name: str) -> str:
    start_pattern = f"local function {function_name}("
    start = content.find(start_pattern)

    if start == -1:
        raise ValueError(f"Function {function_name} not found")

    # Find matching 'end' by counting nested function/end pairs
    depth = 0
    in_function = False
    end = start

    i = start
    while i < len(content):
        if content[i:i+8] == 'function':
            depth += 1
            in_function = True
            i += 8
        elif content[i:i+3] == 'end':
            if in_function:
                depth -= 1
                if depth == 0:
                    end = i + 3
                    break
            i += 3
        else:
            i += 1

    return content[start:end]

# Test extraction
print("Extracting atomic_dequeue...")
try:
    func = extract_function(lua_content, 'atomic_dequeue')
    print(f"Extracted {len(func)} characters")
    print("\n--- First 500 chars ---")
    print(func[:500])
    print("\n--- Last 200 chars ---")
    print(func[-200:])
except Exception as e:
    print(f"ERROR: {e}")
