#!/usr/bin/env bash
# Doc-Solve skill - Autonomous documentation issue resolution
# Similar to code-solve but for documentation

set -euo pipefail

# Show help if requested
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    cat << 'EOF'
/doc-solve - Autonomous Documentation Issue Resolution

USAGE:
  /doc-solve [ISSUE_NUMBER] [OPTIONS]
  /doc-solve loop [OPTIONS]
  /doc-solve --help

EXAMPLES:
  /doc-solve 123                                           # Default: rotating + parallel
  /doc-solve 123 --consensus=weighted --execution=cascade  # Adaptive smart
  /doc-solve 123 --consensus=single --execution=parallel   # Fast single arbiter
  /doc-solve 123 --comment-ai                              # Show AI attribution
  /doc-solve loop                                          # Resolve ALL doc issues
  /doc-solve loop --consensus=weighted --execution=cascade # Continuous adaptive

CONSENSUS STRATEGIES:
  rotating    Democratic - each AI judges others (most thorough, default)
  single      One arbiter judges all (fast)
  majority    Simple majority vote (no arbiter overhead)
  pairwise    Workers in pairs (balanced)
  weighted    Confidence-based voting (quality-aware)

EXECUTION STRATEGIES:
  parallel    All workers simultaneously (fastest, default)
  sequential  One at a time (resource-friendly)
  batched     Process in batches (balanced)
  cascade     Fast workers first, escalate if needed (adaptive, recommended)
  weighted-parallel  Priority-based parallel (smart)

OPTIONS:
  --consensus=MODE     Consensus strategy (default: rotating)
  --execution=MODE     Worker execution strategy (default: parallel)
  --comment-ai         Add comments showing which AI models found/verified issues
                       (Default: OFF - no AI attribution comments added)

LOOP MODE:
  Continuously resolves all open documentation issues until:
  - No issues remain
  - You press Ctrl+C
  - Error occurs

REQUIREMENTS:
  - GITLAB_TOKEN or GITHUB_TOKEN environment variable
  - Ollama running with models (codellama:13b, mistral:7b)
  - Optional: GEMINI_API_KEY for cloud arbiter

DOCUMENTATION:
  See: doc-solve.md
  Or:  https://gitlab.cee.redhat.com/sfloess/universal-ai
EOF
    exit 0
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# Get arguments
ISSUE_NUMBER="${1:-}"
ARBITER_MODE="${2:-rotating}"
COMMENT_AI="none"

# Check for loop mode
if [[ "$ISSUE_NUMBER" == "loop" ]]; then
    LOOP_MODE=true
    ARBITER_MODE="${2:-rotating}"
else
    LOOP_MODE=false
fi

# Parse options
shift 2 2>/dev/null || shift 1 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --comment-ai)
            COMMENT_AI="all"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate inputs
if [ "$LOOP_MODE" = false ] && [ -z "$ISSUE_NUMBER" ]; then
    echo -e "${RED}Error: Issue number required${RESET}"
    echo ""
    echo "Usage: /doc-solve <issue_number> [arbiter_mode]"
    echo "   or: /doc-solve loop [arbiter_mode]"
    echo ""
    exit 1
fi

if [[ "$ARBITER_MODE" != "rotating" ]] && [[ "$ARBITER_MODE" != "single" ]]; then
    echo -e "${RED}Error: Invalid arbiter mode: $ARBITER_MODE${RESET}"
    echo "Valid modes: rotating, single"
    exit 1
fi

# Check for required environment variables
if [ -z "${GITHUB_TOKEN:-}" ] && [ -z "${GITLAB_TOKEN:-}" ]; then
    echo -e "${RED}Error: GITHUB_TOKEN or GITLAB_TOKEN required${RESET}"
    echo ""
    echo "Set one of:"
    echo "  export GITHUB_TOKEN='ghp_...'"
    echo "  export GITLAB_TOKEN='glpat_...'"
    echo ""
    exit 1
fi

# Print header
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}📚 Doc Solve - Autonomous Documentation Issue Resolution${RESET}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

if [ "$LOOP_MODE" = true ]; then
    echo -e "Mode: ${CYAN}Continuous Loop${RESET}"
else
    echo -e "Issue: ${CYAN}#$ISSUE_NUMBER${RESET}"
fi

echo -e "Arbiter: ${CYAN}$ARBITER_MODE${RESET}"

if [ "$COMMENT_AI" != "none" ]; then
    echo -e "AI Comments: ${CYAN}Enabled${RESET}"
fi

echo ""

# Build Python command args
PYTHON_ARGS=("--arbiter" "$ARBITER_MODE")

[ "$COMMENT_AI" != "none" ] && PYTHON_ARGS+=("--comment-ai")

if [ "$LOOP_MODE" = true ]; then
    PYTHON_ARGS+=("--loop")

    echo -e "${YELLOW}⟳${RESET} Starting continuous issue resolution..."
    echo -e "${YELLOW}⟳${RESET} Press Ctrl+C to stop"
    echo ""

    python3 cli/doc_solve.py "${PYTHON_ARGS[@]}"
else
    PYTHON_ARGS+=("--issue" "$ISSUE_NUMBER")

    echo -e "${YELLOW}⚙${RESET}  Fetching issue #$ISSUE_NUMBER..."
    echo ""

    python3 cli/doc_solve.py "${PYTHON_ARGS[@]}"

    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${GREEN}✓${RESET} Issue resolution complete"
    echo ""
    echo -e "Check the pull request for details"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
fi
