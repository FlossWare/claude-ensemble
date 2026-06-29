#!/bin/bash

# Test host display in workflows
# Tests:
# 1. Run test workflow with 4 parallel agents
# 2. Verify meta files contain host field
# 3. Show workflow-status display

set -e

echo "=== Test 1: Run parallel workflow ==="
echo "Creating 4 parallel agents that should land on different hosts..."

# Find the current project/session directory
PROJECT_DIR=$(find ~/.claude/projects -name "subagents" -type d -path "*claude-global-skills*" | head -1 | xargs dirname)
SESSION_ID=$(basename "$PROJECT_DIR")
SUBAGENTS_DIR="$PROJECT_DIR/subagents"
WORKFLOW_RUN_DIR="$SUBAGENTS_DIR/workflows"

echo "Project directory: $PROJECT_DIR"
echo "Session ID: $SESSION_ID"

# Run the test workflow (note: this is simulated since we can't actually invoke the harness)
echo ""
echo "To run the actual test workflow, execute:"
echo "  /workflows run test-host-display"
echo ""
echo "For now, checking existing meta files for host field..."

echo ""
echo "=== Test 2: Check meta files for host field ==="

# Find recent meta files
META_FILES=$(find "$SUBAGENTS_DIR" -name "*.meta.json" -type f -mmin -60 2>/dev/null | head -10)

if [ -z "$META_FILES" ]; then
  echo "⚠️  No recent meta files found (last 60 minutes)"
  echo "   Looking for any meta files..."
  META_FILES=$(find "$SUBAGENTS_DIR" -name "*.meta.json" -type f 2>/dev/null | head -10)
fi

if [ -z "$META_FILES" ]; then
  echo "❌ No meta files found in $SUBAGENTS_DIR"
  echo ""
  echo "You need to run a workflow first to generate meta files."
  exit 1
fi

echo "Found $(echo "$META_FILES" | wc -l) meta files"
echo ""

HAS_HOST=0
NO_HOST=0

for meta in $META_FILES; do
  if grep -q '"host"' "$meta"; then
    HOST=$(jq -r '.host // "unknown"' "$meta" 2>/dev/null)
    AGENT_ID=$(basename "$meta" .meta.json)
    LABEL=$(jq -r '.description // .label // "unknown"' "$meta" 2>/dev/null)
    echo "✓ $(basename $meta): host=$HOST, label=$LABEL"
    ((HAS_HOST++))
  else
    echo "✗ $(basename $meta): NO HOST FIELD"
    ((NO_HOST++))
  fi
done

echo ""
echo "Summary:"
echo "  Meta files with host: $HAS_HOST"
echo "  Meta files without host: $NO_HOST"

if [ $HAS_HOST -eq 0 ]; then
  echo ""
  echo "❌ FAIL: No meta files contain host field"
  echo ""
  echo "This indicates the workflow harness is not writing host information to meta files."
  echo "The harness needs to be updated to include 'host' in agent metadata."
  exit 1
fi

echo ""
echo "=== Test 3: Workflow status display ==="
echo ""

# Try to run the enhanced workflow status
if [ -f "/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/workflow-status-enhanced.js" ]; then
  echo "Running enhanced workflow status..."
  node /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/workflow-status-enhanced.js
else
  echo "⚠️  Enhanced workflow status not found, showing manual analysis..."

  # Manual analysis
  echo ""
  echo "Recent workflows:"
  if [ -d "$WORKFLOW_RUN_DIR" ]; then
    ls -lt "$WORKFLOW_RUN_DIR" | head -6
  else
    echo "No workflow run directory found"
  fi
fi

echo ""
echo "=== Test Complete ==="
echo ""
echo "Next steps:"
echo "1. If host field is missing, the harness needs to write it to meta files"
echo "2. The /workflows command needs to read and display the host field"
echo "3. Format should be: ✓ label (hostname) [agent-id]"
