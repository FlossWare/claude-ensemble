#!/bin/bash
# Count path validation coverage

echo "========================================"
echo "PATH VALIDATION STATUS"
echo "========================================"

# Count JavaScript files with file operations
total_js=$(find shared/ tools/ workflows/ -type f \( -name "*.js" -o -name "*.mjs" -o -name "*.cjs" \) -exec grep -l "readFileSync\|writeFileSync\|existsSync" {} \; 2>/dev/null | wc -l)

# Count JavaScript files with path validation
fixed_js=$(find shared/ tools/ workflows/ -type f \( -name "*.js" -o -name "*.mjs" -o -name "*.cjs" \) -exec grep -l "validateReadPath\|validateWritePath\|safeReadFile\|safeWriteFile" {} \; 2>/dev/null | wc -l)

# Count Python files with file operations
total_py=$(find tools/ -type f -name "*.py" -exec grep -l "open(" {} \; 2>/dev/null | wc -l)

# Count Python files with path validation
fixed_py=$(find tools/ -type f -name "*.py" -exec grep -l "validate_read_path\|validate_write_path\|safe_open" {} \; 2>/dev/null | wc -l)

echo ""
echo "JavaScript Files:"
echo "  Total with file operations: $total_js"
echo "  Fixed with validation: $fixed_js"
echo "  Remaining: $((total_js - fixed_js))"
echo "  Coverage: $(( fixed_js * 100 / total_js ))%"

echo ""
echo "Python Files:"
echo "  Total with file operations: $total_py"
echo "  Fixed with validation: $fixed_py"
echo "  Remaining: $((total_py - fixed_py))"
echo "  Coverage: $(( fixed_py * 100 / total_py ))%"

echo ""
echo "Overall:"
total=$((total_js + total_py))
fixed=$((fixed_js + fixed_py))
remaining=$((total - fixed))
coverage=$(( fixed * 100 / total ))
echo "  Total files: $total"
echo "  Fixed: $fixed"
echo "  Remaining: $remaining"
echo "  Coverage: ${coverage}%"

echo ""
echo "========================================"
echo "CRITICAL FILES STATUS"
echo "========================================"

# Check critical files individually
critical_files=(
  "shared/semantic-knowledge-search.js"
  "shared/knowledge-system-adapter.js"
  "tools/auto_storage_system.py"
  "shared/learning-vectordb.js"
  "shared/query-optimizer-adapter.cjs"
  "tools/non_blocking_workflow_pattern.js"
)

for file in "${critical_files[@]}"; do
  if [ -f "$file" ]; then
    if grep -q "validateReadPath\|validateWritePath\|validate_read_path\|validate_write_path" "$file" 2>/dev/null; then
      echo "  ✓ $file"
    else
      echo "  ✗ $file (NOT FIXED)"
    fi
  fi
done

echo "========================================"
