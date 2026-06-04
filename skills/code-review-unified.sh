#!/usr/bin/env bash
# code-review-unified skill - Unified Multi-Model Review with Strategies

set -euo pipefail

# Show help
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]] || [[ $# -eq 0 ]]; then
    cat << 'EOF'
/code-review - Unified Multi-Model Review with Strategies

USAGE:
  /code-review [OPTIONS]
  /code-review --help

DESCRIPTION:
  Unified code review workflow with configurable consensus strategies.
  Replaces auto-review-brutal with better strategy selection.

OPTIONS:
  --strategy=MODE       Consensus strategy (rotating/single/majority/weighted/pairwise)
  --arbiter=MODEL       Override arbiter (opus/sonnet/haiku/gemini)
  --workers=LIST        Comma-separated models (opus,sonnet,haiku)
  --path=DIR            Target directory (default: .)
  --create-issues       Create GitHub issues (default: true)
  --sync                Sync with remote first (default: true)

STRATEGIES:
  rotating    - Different arbiter each time (most democratic) ⭐ RECOMMENDED
  single      - One arbiter judges all (fastest)
  majority    - Simple vote, no arbiter (fast)
  weighted    - Confidence-weighted voting (quality-aware)
  pairwise    - Workers in pairs (balanced)

EXAMPLES:
  /code-review --strategy=rotating
  /code-review --strategy=majority --workers=opus,sonnet
  /code-review --strategy=single --arbiter=opus

FEATURES:
  - 5 Consensus Strategies
  - Configurable Workers
  - Swappable Arbiter
  - Platform Agnostic (GitHub/GitLab/Bitbucket)
  - Review-Only Mode

DOCUMENTATION:
  See: code-review-unified.md
EOF
    exit 0
fi

echo "This skill uses the Workflow tool to run code-review.js"
echo "Arguments: $*"
echo ""
echo "Note: This skill should be invoked through Claude Code's skill system."
