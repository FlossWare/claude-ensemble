#!/usr/bin/env python3
"""
Automate wrapping workflow files with export default async function.

Handles files with code before meta block by:
1. Keeping imports at top
2. Moving other pre-meta code inside function
3. Adding function wrapper after meta
4. Adding closing brace
"""

import re
import sys
from pathlib import Path

def fix_workflow_file(filepath):
    """Fix a single workflow file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if already has wrapper
    if 'export default async function' in content:
        return False, "Already has wrapper"

    # Find meta block
    meta_match = re.search(r'(export const meta = \{[^}]*\})', content, re.DOTALL)
    if not meta_match:
        return False, "No meta block found"

    meta_block = meta_match.group(1)
    meta_start = meta_match.start()
    meta_end = meta_match.end()

    # Split content into sections
    before_meta = content[:meta_start]
    after_meta = content[meta_end:]

    # Extract imports from before_meta
    import_lines = []
    other_before_meta = []

    for line in before_meta.split('\n'):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('//') or stripped == '':
            import_lines.append(line)
        else:
            # This is code that needs to move inside function
            other_before_meta.append(line)

    # Remove trailing empty lines from imports
    while import_lines and import_lines[-1].strip() == '':
        import_lines.pop()

    # Remove leading empty lines from other_before_meta
    while other_before_meta and other_before_meta[0].strip() == '':
        other_before_meta.pop(0)

    # Build new content
    new_content_parts = []

    # 1. Imports
    if import_lines:
        new_content_parts.append('\n'.join(import_lines))
        new_content_parts.append('\n\n')

    # 2. Meta block
    new_content_parts.append(meta_block)
    new_content_parts.append('\n\n')

    # 3. Function wrapper
    new_content_parts.append('export default async function({ args, phase, log, agent, parallel }) {\n')

    # 4. Code that was before meta (if any)
    if other_before_meta:
        new_content_parts.append('\n'.join(other_before_meta))
        new_content_parts.append('\n')

    # 5. Code after meta
    # Remove leading newline from after_meta
    after_meta_clean = after_meta.lstrip('\n')
    new_content_parts.append(after_meta_clean)

    # 6. Ensure ends with newline and closing brace
    if not after_meta_clean.endswith('\n'):
        new_content_parts.append('\n')

    # Check if already has closing brace at end
    if not after_meta_clean.rstrip().endswith('}'):
        new_content_parts.append('\n}\n')
    else:
        # Has closing brace but might need wrapper's closing brace
        new_content_parts.append('\n}\n')

    new_content = ''.join(new_content_parts)

    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True, "Fixed"

def main():
    workflows_dir = Path(__file__).parent

    fixed_count = 0
    failed_count = 0
    skipped_count = 0

    for js_file in sorted(workflows_dir.glob('*.js')):
        success, message = fix_workflow_file(js_file)

        if success:
            fixed_count += 1
            print(f"✓ {js_file.name}: {message}")
        elif "Already has wrapper" in message:
            skipped_count += 1
        else:
            failed_count += 1
            print(f"✗ {js_file.name}: {message}")

    print(f"\n{'='*60}")
    print(f"Fixed: {fixed_count}")
    print(f"Skipped (already fixed): {skipped_count}")
    print(f"Failed: {failed_count}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
