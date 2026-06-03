#!/usr/bin/env bash
# PR Review Skill - Multi-AI Pull Request / Merge Request Review
# Uses arbiter/worker pattern for consensus-based review

set -euo pipefail

# Show help if requested
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    cat << 'EOF'
/pr-review - Multi-AI Pull Request / Merge Request Review

USAGE:
  /pr-review <pr_number> [ARBITER_MODE] [OPTIONS]
  /pr-review --all [ARBITER_MODE] [OPTIONS]
  /pr-review loop [ARBITER_MODE] [OPTIONS]
  /pr-review --help

DESCRIPTION:
  Multi-AI code review of PRs/MRs with arbiter/worker consensus pattern.
  Fetches PR/MR from GitHub/GitLab/Bitbucket, reviews changes, posts comments.

EXAMPLES:
  /pr-review 123                Review PR/MR #123 (rotating consensus, parallel execution)
  /pr-review 123 --consensus=single --execution=parallel   Fast single arbiter
  /pr-review 123 --consensus=weighted --execution=cascade  Adaptive smart review
  /pr-review 123 --post         Review and post comments to PR
  /pr-review 123 --approve      Review and auto-approve if clean
  /pr-review --all --post       Review all open PRs
  /pr-review loop --auto-approve   Continuous monitoring with auto-approve

CONSENSUS STRATEGIES:
  rotating    Democratic - each AI judges others (most thorough, default)
  single      One arbiter judges all (fast)
  majority    Simple majority vote (no arbiter overhead)
  pairwise    Workers review in pairs (balanced)
  weighted    Confidence-based voting (quality-aware)

EXECUTION STRATEGIES:
  parallel    All workers simultaneously (fastest, default)
  sequential  One worker at a time (resource-friendly)
  batched     Process in batches (balanced)
  cascade     Fast workers first, escalate if needed (adaptive)
  weighted-parallel  Priority-based parallel (smart)

OPTIONS:
  --post              Post review comments to PR/MR
  --approve           Approve if quality score >= threshold
  --request-changes   Request changes if issues found
  --comment-only      Only comment, don't change status
  --threshold=N       Quality score threshold for approval (default: 90)

  --all               Review all open PRs/MRs
  --author=user       Filter by author
  --label=tag         Filter by label
  --target=branch     Filter by target branch

  --workers=N         Number of AI reviewers (default: 6)
  --consensus=MODE    Consensus strategy (default: rotating)
  --execution=MODE    Worker execution strategy (default: parallel)
  --depth=full        Full codebase context (default: diff only)
  --verbose           Detailed output
  --json              JSON output for CI/CD

LOOP MODE:
  Continuously monitors for new/updated PRs/MRs:
  - Checks every 5 minutes
  - Reviews new/updated PRs
  - Posts comments automatically
  - Can auto-approve clean PRs
  - Press Ctrl+C to stop

MULTI-AI REVIEW PROCESS:
  1. Fetch PR/MR details from GitHub/GitLab/Bitbucket (via MCP)
  2. Checkout PR branch locally
  3. 6 AI workers independently review changes
  4. Arbiter(s) vote on findings (democratic consensus)
  5. Post review comments to PR/MR
  6. Approve/request changes based on quality score
  7. Cleanup temporary branch

PLATFORMS:
  - GitHub (via github MCP server)
  - GitLab (via gitlab MCP server)
  - Bitbucket (via bitbucket MCP server)

REQUIREMENTS:
  - GITHUB_TOKEN or GITLAB_TOKEN or BITBUCKET credentials
  - MCP proxy running (./start-mcp-servers.sh)
  - Ollama with models (codellama:13b, mistral:7b)
  - Optional: GEMINI_API_KEY, ANTHROPIC_API_KEY for cloud workers

QUALITY SCORE:
  Score = 100 - (critical×10 + major×5 + minor×1)

  Default threshold: 90
  - Score >= 90: Approve
  - Score < 90: Request changes

DOCUMENTATION:
  See: pr-review.md
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

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
PR_NUMBER=""
ARBITER_MODE="rotating"
POST_COMMENTS=false
AUTO_APPROVE=false
REQUEST_CHANGES=false
COMMENT_ONLY=false
THRESHOLD=90
REVIEW_ALL=false
LOOP_MODE=false
AUTHOR_FILTER=""
LABEL_FILTER=""
TARGET_FILTER=""
WORKERS=6
DEPTH="diff"
VERBOSE=false
JSON_OUTPUT=false

# First arg: PR number, --all, or loop
if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
    PR_NUMBER="$1"
    shift
elif [[ "${1:-}" == "--all" ]]; then
    REVIEW_ALL=true
    shift
elif [[ "${1:-}" == "loop" ]]; then
    LOOP_MODE=true
    shift
fi

# Second arg: arbiter mode (if not a flag)
if [[ "${1:-}" == "rotating" ]] || [[ "${1:-}" == "single" ]]; then
    ARBITER_MODE="$1"
    shift
fi

# Parse remaining options
while [[ $# -gt 0 ]]; do
    case $1 in
        --post)
            POST_COMMENTS=true
            shift
            ;;
        --approve)
            AUTO_APPROVE=true
            POST_COMMENTS=true
            shift
            ;;
        --request-changes)
            REQUEST_CHANGES=true
            POST_COMMENTS=true
            shift
            ;;
        --comment-only)
            COMMENT_ONLY=true
            POST_COMMENTS=true
            shift
            ;;
        --threshold=*)
            THRESHOLD="${1#*=}"
            shift
            ;;
        --all)
            REVIEW_ALL=true
            shift
            ;;
        --author=*)
            AUTHOR_FILTER="${1#*=}"
            shift
            ;;
        --label=*)
            LABEL_FILTER="${1#*=}"
            shift
            ;;
        --target=*)
            TARGET_FILTER="${1#*=}"
            shift
            ;;
        --workers=*)
            WORKERS="${1#*=}"
            shift
            ;;
        --depth=*)
            DEPTH="${1#*=}"
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        loop)
            LOOP_MODE=true
            shift
            ;;
        --auto-approve)
            AUTO_APPROVE=true
            POST_COMMENTS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate
if [ -z "$PR_NUMBER" ] && [ "$REVIEW_ALL" = false ] && [ "$LOOP_MODE" = false ]; then
    echo -e "${RED}Error: PR number required${RESET}"
    echo ""
    echo "Usage: /pr-review <pr_number> [options]"
    echo "   or: /pr-review --all [options]"
    echo "   or: /pr-review loop [options]"
    echo ""
    exit 1
fi

# Check for platform token
if [ -z "${GITHUB_TOKEN:-}" ] && [ -z "${GITLAB_TOKEN:-}" ] && [ -z "${BITBUCKET_USER:-}" ]; then
    echo -e "${RED}Error: Platform token required${RESET}"
    echo ""
    echo "Set one of:"
    echo "  export GITHUB_TOKEN='ghp_...'"
    echo "  export GITLAB_TOKEN='glpat_...'"
    echo "  export BITBUCKET_USER='user'"
    echo "  export BITBUCKET_APP_PASSWORD='...'"
    echo ""
    exit 1
fi

# Print header
if [ "$JSON_OUTPUT" != true ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}📋 PR Review - Multi-AI Pull Request Review${RESET}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""

    if [ -n "$PR_NUMBER" ]; then
        echo -e "PR/MR: ${CYAN}#$PR_NUMBER${RESET}"
    elif [ "$REVIEW_ALL" = true ]; then
        echo -e "Mode: ${CYAN}Review all open PRs/MRs${RESET}"
    elif [ "$LOOP_MODE" = true ]; then
        echo -e "Mode: ${CYAN}Continuous monitoring${RESET}"
    fi

    echo -e "Arbiter: ${CYAN}$ARBITER_MODE${RESET}"
    echo -e "Workers: ${CYAN}$WORKERS${RESET}"
    echo -e "Threshold: ${CYAN}$THRESHOLD${RESET}"

    if [ "$AUTO_APPROVE" = true ]; then
        echo -e "Auto-approve: ${GREEN}Enabled${RESET}"
    fi

    echo ""
fi

# Build Python command args
PYTHON_ARGS=(
    "--arbiter" "$ARBITER_MODE"
    "--workers" "$WORKERS"
    "--threshold" "$THRESHOLD"
    "--depth" "$DEPTH"
)

[ "$POST_COMMENTS" = true ] && PYTHON_ARGS+=("--post")
[ "$AUTO_APPROVE" = true ] && PYTHON_ARGS+=("--auto-approve")
[ "$REQUEST_CHANGES" = true ] && PYTHON_ARGS+=("--request-changes")
[ "$COMMENT_ONLY" = true ] && PYTHON_ARGS+=("--comment-only")
[ "$VERBOSE" = true ] && PYTHON_ARGS+=("--verbose")
[ "$JSON_OUTPUT" = true ] && PYTHON_ARGS+=("--json")

if [ -n "$PR_NUMBER" ]; then
    PYTHON_ARGS+=("--pr" "$PR_NUMBER")
fi

if [ "$REVIEW_ALL" = true ]; then
    PYTHON_ARGS+=("--all")
fi

if [ "$LOOP_MODE" = true ]; then
    PYTHON_ARGS+=("--loop")
fi

[ -n "$AUTHOR_FILTER" ] && PYTHON_ARGS+=("--author" "$AUTHOR_FILTER")
[ -n "$LABEL_FILTER" ] && PYTHON_ARGS+=("--label" "$LABEL_FILTER")
[ -n "$TARGET_FILTER" ] && PYTHON_ARGS+=("--target" "$TARGET_FILTER")

# Run PR review
python3 "$SCRIPT_DIR/cli/pr_review.py" "${PYTHON_ARGS[@]}"

# Print footer
if [ "$JSON_OUTPUT" != true ] && [ "$LOOP_MODE" != true ]; then
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${GREEN}✓${RESET} Review complete"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
fi
