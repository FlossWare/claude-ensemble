#!/usr/bin/env python3
"""Debug improved Lua function extraction"""

from pathlib import Path

lua_path = Path('shared/redis-atomic-operations.lua')
lua_content = lua_path.read_text()

def extract_function(content: str, function_name: str) -> str:
    start_pattern = f"local function {function_name}("
    start = content.find(start_pattern)

    if start == -1:
        raise ValueError(f"Function {function_name} not found")

    # Count all control structures that need 'end': function, if, for, while, repeat
    depth = 0
    end_pos = start

    i = start
    while i < len(content):
        # Check for keywords that increase depth
        if content[i:i+8] == 'function' and (i == 0 or not content[i-1:i].isalnum()):
            depth += 1
            i += 8
        elif content[i:i+2] == 'if' and (i+2 >= len(content) or not content[i+2:i+3].isalnum()):
            depth += 1
            i += 2
        elif content[i:i+3] == 'for' and (i+3 >= len(content) or not content[i+3:i+4].isalnum()):
            depth += 1
            i += 3
        elif content[i:i+5] == 'while' and (i+5 >= len(content) or not content[i+5:i+6].isalnum()):
            depth += 1
            i += 5
        elif content[i:i+6] == 'repeat' and (i+6 >= len(content) or not content[i+6:i+7].isalnum()):
            depth += 1
            i += 6
        # Check for 'end' or 'until' that decrease depth
        elif content[i:i+3] == 'end' and (i+3 >= len(content) or not content[i+3:i+4].isalnum()):
            depth -= 1
            if depth == 0:
                end_pos = i + 3
                break
            i += 3
        elif content[i:i+5] == 'until' and (i+5 >= len(content) or not content[i+5:i+6].isalnum()):
            depth -= 1
            i += 5
        else:
            i += 1

    return content[start:end_pos]

# Test extraction
print("Extracting atomic_dequeue...")
try:
    func = extract_function(lua_content, 'atomic_dequeue')
    print(f"Extracted {len(func)} characters")
    print("\n--- Function ---")
    print(func)
    print("\n--- Checking structure ---")
    print(f"Starts with 'local function': {func.startswith('local function')}")
    print(f"Ends with 'end': {func.strip().endswith('end')}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
