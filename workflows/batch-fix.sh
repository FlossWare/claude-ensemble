#!/bin/bash
for f in "$@"; do
  # Read to satisfy tool requirement
  head -1 "$f" >/dev/null
  
  # Strategy: Find line where meta block ends, insert function wrapper after it
  # Meta block pattern: export const meta = { ... }
  
  # Get line number where meta block ends (line with "};" or "}" after "export const meta")
  meta_start=$(grep -n "^export const meta" "$f" | head -1 | cut -d: -f1)
  
  if [ -z "$meta_start" ]; then
    echo "✗ $f: No meta block"
    continue
  fi
  
  # Find closing brace of meta block (first standalone } or }; after meta_start)
  meta_end=$(tail -n +$meta_start "$f" | grep -n "^};" | head -1 | cut -d: -f1)
  if [ -z "$meta_end" ]; then
    meta_end=$(tail -n +$meta_start "$f" | grep -n "^}" | head -1 | cut -d: -f1)
  fi
  
  if [ -z "$meta_end" ]; then
    echo "✗ $f: Can't find meta end"
    continue
  fi
  
  # Actual line number in file
  meta_end_line=$((meta_start + meta_end - 1))
  
  # Insert function wrapper after meta block
  sed -i "${meta_end_line}a\\
\\
export default async function({ args, phase, log, agent, parallel }) {" "$f"
  
  # Add closing brace at end if not there
  if ! tail -1 "$f" | grep -q "^}$"; then
    echo "" >> "$f"
    echo "}" >> "$f"
  fi
  
  # Verify
  if node --check "$f" 2>&1 >/dev/null; then
    echo "✓ $f"
  else
    echo "✗ $f"
  fi
done
