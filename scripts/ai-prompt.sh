#!/usr/bin/env bash
# ai-prompt skill - Multi-Model Consensus for Any Question

set -euo pipefail

# Show help
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]] || [[ $# -eq 0 ]]; then
    cat << 'EOF'
/ai-prompt - Multi-Model Consensus for Any Question

USAGE:
  /ai-prompt <question>
  /ai-prompt --help

DESCRIPTION:
  Get multiple AI perspectives on any question using arbiter/worker
  consensus pattern. Uses Opus, Sonnet, and Haiku to provide
  independent responses, then synthesizes the best answer.

EXAMPLES:
  /ai-prompt How should I architect this authentication system?
  /ai-prompt Should I use REST or GraphQL for this API?
  /ai-prompt What's the best way to handle real-time updates?

FEATURES:
  - Multi-Model Responses from 3 AI models
  - Arbiter Synthesis of best answer
  - Consensus Tracking showing agreement levels
  - Attribution of which model contributed what

CONSENSUS LEVELS:
  HIGH   - All 3 models agree (3/3)
  MEDIUM - Majority agree (2/3)
  LOW    - Models disagree (split)

DOCUMENTATION:
  See: ai-prompt.md
EOF
    exit 0
fi

echo "This skill uses the Workflow tool to run ai-prompt.js"
echo "Question: $*"
echo ""
echo "Note: This skill should be invoked through Claude Code's skill system."
