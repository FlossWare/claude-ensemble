#!/bin/bash
# Workflow Output Verification Script
# Usage: verify_workflow_output.sh <workflow_id>

set -euo pipefail

WORKFLOW_ID="${1:-}"

if [[ -z "$WORKFLOW_ID" ]]; then
    echo "ERROR: workflow_id required"
    echo "Usage: $0 <workflow_id>"
    exit 1
fi

# Find workflow directory (support CLAUDE_HOME override for testing)
SEARCH_ROOT="${CLAUDE_HOME:-$HOME/.claude}"
WORKFLOW_DIR=$(find "$SEARCH_ROOT" -type d -path "*/tasks/$WORKFLOW_ID" 2>/dev/null | head -1 || true)

if [[ -z "$WORKFLOW_DIR" ]]; then
    echo "ERROR: Workflow $WORKFLOW_ID not found"
    exit 1
fi

echo "Verifying workflow: $WORKFLOW_ID"
echo "Location: $WORKFLOW_DIR"
echo ""

# Check .output file
OUTPUT_FILE="$WORKFLOW_DIR/.output"
if [[ ! -f "$OUTPUT_FILE" ]]; then
    echo "❌ FAILED: .output file missing"
    exit 1
fi

OUTPUT_SIZE=$(stat -c%s "$OUTPUT_FILE" 2>/dev/null || stat -f%z "$OUTPUT_FILE" 2>/dev/null)
if [[ "$OUTPUT_SIZE" -eq 0 ]]; then
    echo "❌ FAILED: .output file is empty"
    exit 1
fi

echo "✅ .output file exists (${OUTPUT_SIZE} bytes)"

# Check agent JSONL files
AGENT_FILES=$(find "$WORKFLOW_DIR" -maxdepth 1 -name "agent-*.jsonl" 2>/dev/null | wc -l)
if [[ "$AGENT_FILES" -eq 0 ]]; then
    echo "⚠️  WARNING: No agent JSONL files found"
else
    echo "✅ Found $AGENT_FILES agent JSONL file(s)"
fi

# Validate JSON if applicable
if head -1 "$OUTPUT_FILE" | grep -q '^{'; then
    if jq empty "$OUTPUT_FILE" 2>/dev/null; then
        echo "✅ .output is valid JSON"
    else
        echo "⚠️  WARNING: .output appears to be JSON but is malformed"
    fi
fi

# Validate agent JSONL files
if [[ "$AGENT_FILES" -gt 0 ]]; then
    for jsonl in "$WORKFLOW_DIR"/agent-*.jsonl; do
        if [ -f "$jsonl" ]; then
            if ! jq -e . "$jsonl" >/dev/null 2>&1; then
                echo "⚠️  WARNING: $(basename "$jsonl") is malformed"
            fi
        fi
    done
fi

# Display output preview
echo ""
echo "Output preview:"
echo "First line: $(head -1 "$OUTPUT_FILE")"
echo "Last line: $(tail -1 "$OUTPUT_FILE")"

# Summary
echo ""
echo "✅ VERIFICATION PASSED"
echo "Output file: $OUTPUT_FILE"
echo "Size: $OUTPUT_SIZE bytes"
echo "Agent files: $AGENT_FILES"

exit 0
