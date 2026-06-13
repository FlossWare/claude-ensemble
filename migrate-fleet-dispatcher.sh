#!/usr/bin/env bash
# migrate-fleet-dispatcher.sh
# Adds fleet dispatcher integration (import + feature flag) to 14 workflow files.
# Safe: creates backup first, validates syntax after each edit, rolls back on failure.

set -euo pipefail

WORKFLOW_DIR="$HOME/.claude/workflows"
BACKUP_DIR="$HOME/.claude/workflow-backups/pre-migration-$(date +%Y%m%d-%H%M%S)"
IMPORT_LINE="import fleetUtils from './fleet-utils.js';"
FLAG_LINE="const USE_FLEET_DISPATCHER = process.env.FLEET_DISPATCHER !== 'false';"

# The 14 target workflows
WORKFLOWS=(
  code-review-auto
  code-test-auto
  code-solve-auto
  code-test
  code-solve
  code-review
  ai-web-learn-production
  code-pr-review-auto
  code-pr-review
  code-security
  ai-web-code-learn-production
  ai-web-code-learn
  ai-web-learn
  doc-review
)

# Use $((x + 1)) instead of ((x++)) to avoid exit-code-1 with set -e when x=0
SUCCESS=0
FAIL=0
SKIP=0

echo "================================================================="
echo "Fleet Dispatcher Migration"
echo "================================================================="
echo "Workflow dir : $WORKFLOW_DIR"
echo "Backup dir   : $BACKUP_DIR"
echo "Targets      : ${#WORKFLOWS[@]} workflows"
echo ""

# ---- Step 1: Create backup ----
echo "--- Step 1: Creating backup ---"
mkdir -p "$BACKUP_DIR"
for name in "${WORKFLOWS[@]}"; do
  src="$WORKFLOW_DIR/${name}.js"
  if [[ -f "$src" ]]; then
    cp "$src" "$BACKUP_DIR/"
  else
    echo "  WARNING: $src does not exist, skipping backup"
  fi
done
echo "  Backup saved to: $BACKUP_DIR"
echo "  Files backed up: $(ls "$BACKUP_DIR" | wc -l)"
echo ""

# ---- Step 2: Migrate each workflow ----
echo "--- Step 2: Migrating workflows ---"
echo ""

for name in "${WORKFLOWS[@]}"; do
  FILE="$WORKFLOW_DIR/${name}.js"
  echo "  Processing: ${name}.js"

  # Check file exists
  if [[ ! -f "$FILE" ]]; then
    echo "    SKIP: file not found"
    SKIP=$((SKIP + 1))
    continue
  fi

  # Check if already migrated
  if grep -q "import fleetUtils from" "$FILE" 2>/dev/null; then
    echo "    SKIP: already has fleetUtils import"
    SKIP=$((SKIP + 1))
    continue
  fi

  # Find the line number where the meta block's closing } lives.
  # The meta block starts with: export const meta = {
  # We track brace depth to find the matching close.
  META_END=$(awk '
    /^export const meta = \{/ { depth = 1; next }
    depth > 0 {
      n = split($0, chars, "")
      for (i = 1; i <= n; i++) {
        if (chars[i] == "{") depth++
        if (chars[i] == "}") depth--
        if (depth == 0) { print NR; exit }
      }
    }
  ' "$FILE")

  if [[ -z "$META_END" ]]; then
    echo "    FAIL: could not find meta block closing brace"
    FAIL=$((FAIL + 1))
    continue
  fi

  # Verify the line is actually a closing brace
  META_LINE_CONTENT=$(sed -n "${META_END}p" "$FILE")
  if [[ "$META_LINE_CONTENT" != "}" ]]; then
    echo "    FAIL: expected '}' at line $META_END but found: [$META_LINE_CONTENT]"
    FAIL=$((FAIL + 1))
    continue
  fi

  # Check what follows the meta block closing brace.
  # All files have a blank line after }. We insert AFTER that blank line.
  NEXT_LINE=$((META_END + 1))
  NEXT_LINE_CONTENT=$(sed -n "${NEXT_LINE}p" "$FILE")

  if [[ -z "$NEXT_LINE_CONTENT" ]]; then
    # There is a blank line after }. Insert after it.
    INSERT_AFTER=$((META_END + 1))
  else
    # No blank line; insert right after }.
    INSERT_AFTER=$META_END
  fi

  # Use sed to insert the two lines + a trailing blank line after INSERT_AFTER.
  # The 'a' command appends text after the addressed line.
  sed -i "${INSERT_AFTER}a\\
${IMPORT_LINE}\\
${FLAG_LINE}\\
" "$FILE"

  # Validate: check that both lines are now present
  if grep -q "import fleetUtils from './fleet-utils.js';" "$FILE" && \
     grep -q "const USE_FLEET_DISPATCHER = process.env.FLEET_DISPATCHER !== 'false';" "$FILE"; then

    # Validate: check no nimport/nconst corruption
    if grep -q 'nimport\|nconst' "$FILE"; then
      echo "    FAIL: detected nimport/nconst corruption, restoring from backup"
      cp "$BACKUP_DIR/${name}.js" "$FILE"
      FAIL=$((FAIL + 1))
      continue
    fi

    # Validate: check import is not inside the meta block
    IMPORT_LINE_NUM=$(grep -n "import fleetUtils" "$FILE" | head -1 | cut -d: -f1)
    if [[ "$IMPORT_LINE_NUM" -le "$META_END" ]]; then
      echo "    FAIL: import landed inside meta block (line $IMPORT_LINE_NUM <= $META_END), restoring"
      cp "$BACKUP_DIR/${name}.js" "$FILE"
      FAIL=$((FAIL + 1))
      continue
    fi

    AGENT_COUNT=$(grep -c 'agent(' "$FILE" 2>/dev/null || echo 0)
    echo "    OK: import at line $IMPORT_LINE_NUM (meta ended at $META_END) | agent() calls: $AGENT_COUNT"
    SUCCESS=$((SUCCESS + 1))
  else
    echo "    FAIL: lines not found after insertion, restoring from backup"
    cp "$BACKUP_DIR/${name}.js" "$FILE"
    FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "================================================================="
echo "Migration Summary"
echo "================================================================="
echo "  Success : $SUCCESS"
echo "  Failed  : $FAIL"
echo "  Skipped : $SKIP"
echo "  Total   : ${#WORKFLOWS[@]}"
echo ""

# ---- Step 3: Verification report ----
echo "--- Verification: agent() call counts ---"
for name in "${WORKFLOWS[@]}"; do
  FILE="$WORKFLOW_DIR/${name}.js"
  if [[ -f "$FILE" ]]; then
    AGENT_COUNT=$(grep -c 'agent(' "$FILE" 2>/dev/null || echo 0)
    HAS_IMPORT=$(grep -c "import fleetUtils" "$FILE" 2>/dev/null || echo 0)
    HAS_FLAG=$(grep -c "USE_FLEET_DISPATCHER" "$FILE" 2>/dev/null || echo 0)
    printf "  %-35s agents: %2d  import: %s  flag: %s\n" "${name}.js" "$AGENT_COUNT" \
      "$([ "$HAS_IMPORT" -gt 0 ] && echo 'YES' || echo 'NO ')" \
      "$([ "$HAS_FLAG" -gt 0 ] && echo 'YES' || echo 'NO ')"
  fi
done
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo "WARNING: $FAIL file(s) failed migration. Check output above."
  echo "Backups are in: $BACKUP_DIR"
  exit 1
fi

echo "Migration complete. Backups in: $BACKUP_DIR"
echo "To revert all changes: cp $BACKUP_DIR/*.js $WORKFLOW_DIR/"
