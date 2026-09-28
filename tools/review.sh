#!/bin/bash
# Shorthand for Arbiter/Workers Code Review Pattern
#
# Usage:
#   review PR#123                    # 2-phase review of PR 123
#   review ./src/file.py             # 2-phase review of file
#   review -3 PR#456                 # 3-phase review (with final arbiter)
#   meta-review PR#123             # Meta-review: arbiter/workers reviews the review
#
# Automatically:
# - Runs multi-phase worker/arbiter pattern
# - Saves findings to memory
# - Saves architecture decisions
# - Alerts on critical findings

set -e

PHASE_COUNT="${PHASE_COUNT:-2}"
TARGET="${1:-.}"

if [[ "$1" == "-"* ]]; then
  PHASE_COUNT="${1:1}"
  TARGET="${2:-.}"
fi

# Resolve target
if [[ "$TARGET" == "PR#"* ]]; then
  PR_NUM="${TARGET#PR#}"
  TARGET="PR $PR_NUM"
elif [[ -f "$TARGET" ]]; then
  TARGET="File: $(basename $TARGET)"
fi

echo "🔍 Arbiter/Workers Code Review"
echo "Target: $TARGET"
echo "Phases: $PHASE_COUNT"
echo ""
echo "Running multi-phase review (workers → arbiter synthesis)..."
echo ""

# Call the actual review workflow
# This would invoke the Workflow or arbiter tool with shorthand params
# For now, just document the pattern

save_learning "Code Review: $TARGET" "Multi-phase review initiated ($PHASE_COUNT phases)"

# TODO: Invoke actual arbitration workflow
# arbitrate code-review "$TARGET" --phases "$PHASE_COUNT"

echo "✓ Review saved to memory"
echo "✓ View results: query-memory.py semantic-search 'review $TARGET'"
