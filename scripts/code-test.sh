#!/bin/bash
# code-test skill wrapper

set -e

SKILL_NAME="code-test"
WORKFLOW_PATH="$HOME/.claude/workflows/code-test.js"

# Check if workflow exists
if [ ! -f "$WORKFLOW_PATH" ]; then
  echo "Error: Workflow not found at $WORKFLOW_PATH"
  exit 1
fi

# Parse arguments
MAX_ISSUES=10
AUTONOMOUS=true
CREATE_ISSUES=true

for arg in "$@"; do
  case "$arg" in
    maxIssues=*)
      MAX_ISSUES="${arg#*=}"
      ;;
    autonomous=*)
      AUTONOMOUS="${arg#*=}"
      ;;
    create-issues=*)
      CREATE_ISSUES="${arg#*=}"
      ;;
  esac
done

echo "🧪 Starting code-test workflow..."
echo "Configuration:"
echo "  Max Issues: $MAX_ISSUES"
echo "  Autonomous: $AUTONOMOUS"
echo "  Create Issues: $CREATE_ISSUES"

# Note: The actual workflow execution is handled by Claude Code's Workflow tool
# This script is just for documentation and validation

exit 0
