#!/usr/bin/env bash
# arbiter skill - Multi-model arbiter system with learning

set -euo pipefail

# Show help
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]] || [[ $# -eq 0 ]]; then
    cat << 'EOF'
/arbiter - Multi-Model Decision Making with Learning

USAGE:
  /arbiter review <issue-id>
  /arbiter review-all
  /arbiter stats
  /arbiter learn <issue-id> <outcome>
  /arbiter models
  /arbiter --help

DESCRIPTION:
  Invoke multiple AI models as arbiters to review work, make decisions,
  and learn from accuracy over time.

COMMANDS:
  review <issue-id>          Review specific issue with multiple arbiters
  review-all                 Review all pending issues
  stats                      Show arbiter accuracy statistics
  learn <issue-id> <outcome> Record actual outcome for learning
  models                     List configured arbiter models

EXAMPLES:
  /arbiter review 011
  /arbiter review-all
  /arbiter stats
  /arbiter learn 011 correct

FEATURES:
  - Multi-model decision making
  - Consensus tracking
  - Learning from outcomes
  - Accuracy statistics per model
  - Issue attribution

DOCUMENTATION:
  See: arbiter.md
EOF
    exit 0
fi

echo "This skill requires implementation in arbiter workflow"
echo "Command: $*"
echo ""
echo "Note: This skill should be invoked through Claude Code's skill system."
