#!/bin/bash
# Automatically fix path traversal vulnerabilities in all JavaScript files

set -e

PROJECT_ROOT="/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
cd "$PROJECT_ROOT"

echo "========================================"
echo "AUTO-FIXING PATH TRAVERSAL"
echo "========================================"

fixed_count=0
error_count=0

# Function to fix a JavaScript file
fix_js_file() {
  local file="$1"

  # Skip if already fixed
  if grep -q "validateReadPath\|validateWritePath" "$file" 2>/dev/null; then
    return
  fi

  # Skip path-validator.js itself
  if [[ "$file" == *"path-validator"* ]]; then
    return
  fi

  # Create backup
  cp "$file" "$file.bak"

  # Add import after existing imports
  if grep -q "^import.*from" "$file"; then
    # Find last import line and add our import after it
    awk '
      /^import.*from/ { last_import = NR }
      NR == last_import + 1 && !imported {
        print "import { validateReadPath, validateWritePath } from '\''./path-validator.js'\'';"
        imported = 1
      }
      { print }
    ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"

    echo "  ✓ Fixed: $file"
    ((fixed_count++))
    rm "$file.bak"
  else
    # Restore backup if no imports found
    mv "$file.bak" "$file"
  fi
}

# Fix all JavaScript files in shared/
echo ""
echo "Fixing shared/ directory..."
find shared/ -type f \( -name "*.js" -o -name "*.mjs" -o -name "*.cjs" \) -exec grep -l "readFileSync\|writeFileSync" {} \; 2>/dev/null | while read file; do
  fix_js_file "$file" || ((error_count++))
done

# Fix all JavaScript files in tools/
echo "Fixing tools/ directory..."
find tools/ -type f \( -name "*.js" -o -name "*.mjs" -o -name "*.cjs" \) -exec grep -l "readFileSync\|writeFileSync" {} \; 2>/dev/null | while read file; do
  fix_js_file "$file" || ((error_count++))
done

echo ""
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo "Files fixed: $fixed_count"
echo "Errors: $error_count"
echo "========================================"

echo ""
echo "NOTE: Imports added. You must manually wrap file operations"
echo "with validateReadPath() or validateWritePath()."
echo ""
echo "Example:"
echo "  Before: readFileSync(userInput)"
echo "  After:  readFileSync(validateReadPath(userInput))"
