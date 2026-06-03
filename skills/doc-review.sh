#!/usr/bin/env bash
# Doc-Review skill - Multi-AI documentation review
# READ-ONLY - Never modifies files

set -euo pipefail

# Show help if requested
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    cat << 'EOF'
/doc-review - Multi-AI Documentation Review (READ-ONLY)

USAGE:
  /doc-review [PATH] [OPTIONS]
  /doc-review --help

DESCRIPTION:
  Multi-AI documentation review with consensus voting.

  IMPORTANT: This skill is READ-ONLY - it never modifies files!
  Safe to run multiple instances simultaneously.

EXAMPLES:
  /doc-review                    Review all documentation
  /doc-review docs/              Review specific directory
  /doc-review README.md          Review single file
  /doc-review --check-all        Enable all checks
  /doc-review --stats            Show statistics

OPTIONS:
  --check-links           Check for broken links
  --check-examples        Validate code examples
  --check-grammar         Check grammar and spelling
  --check-format          Check formatting consistency
  --check-completeness    Check for missing sections
  --check-all             Enable all checks

  --arbiter MODE          Arbiter mode: rotating|single (default: rotating)
  --workers N             Number of worker AIs (default: 6)

  --verbose               Detailed output
  --summary               Summary only
  --json                  JSON output for CI/CD
  --stats                 Show learning statistics

  --continuous            Keep running continuously
  --loop, loop            Continuous review mode

REVIEW DIMENSIONS:
  - Content Quality (completeness, accuracy, clarity)
  - Technical Quality (links, examples, commands)
  - Writing Quality (grammar, style, formatting)
  - Accessibility (readability, navigation)

OUTPUT:
  - Issues found (critical, major, minor)
  - Consensus votes
  - Confidence scores
  - Suggested fixes

QUALITY SCORE:
  Score = 100 - (critical×10 + major×5 + minor×1)

DOCUMENTATION:
  See: doc-review.md
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

# Defaults
PATH_FILTER="${1:-.}"
ARBITER_MODE="rotating"
WORKERS=6
CHECK_LINKS=false
CHECK_EXAMPLES=false
CHECK_GRAMMAR=false
CHECK_FORMAT=false
CHECK_COMPLETENESS=false
VERBOSE=false
SUMMARY_ONLY=false
JSON_OUTPUT=false
CONTINUOUS=false

# Parse arguments
shift 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --check-links)
            CHECK_LINKS=true
            shift
            ;;
        --check-examples)
            CHECK_EXAMPLES=true
            shift
            ;;
        --check-grammar)
            CHECK_GRAMMAR=true
            shift
            ;;
        --check-format)
            CHECK_FORMAT=true
            shift
            ;;
        --check-completeness)
            CHECK_COMPLETENESS=true
            shift
            ;;
        --check-all)
            CHECK_LINKS=true
            CHECK_EXAMPLES=true
            CHECK_GRAMMAR=true
            CHECK_FORMAT=true
            CHECK_COMPLETENESS=true
            shift
            ;;
        --arbiter)
            ARBITER_MODE="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --summary)
            SUMMARY_ONLY=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --continuous|--loop|loop)
            CONTINUOUS=true
            shift
            ;;
        --stats)
            python3 cli/doc_review.py --stats
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Print header
if [ "$JSON_OUTPUT" != true ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}📚 Doc Review - Multi-AI Documentation Review${RESET}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""
    echo -e "Path: ${CYAN}$PATH_FILTER${RESET}"
    echo -e "Arbiter: ${CYAN}$ARBITER_MODE${RESET}"
    echo -e "Workers: ${CYAN}$WORKERS${RESET}"
    echo ""

    # Show enabled checks
    CHECKS=""
    [ "$CHECK_LINKS" = true ] && CHECKS="$CHECKS links"
    [ "$CHECK_EXAMPLES" = true ] && CHECKS="$CHECKS examples"
    [ "$CHECK_GRAMMAR" = true ] && CHECKS="$CHECKS grammar"
    [ "$CHECK_FORMAT" = true ] && CHECKS="$CHECKS format"
    [ "$CHECK_COMPLETENESS" = true ] && CHECKS="$CHECKS completeness"

    if [ -n "$CHECKS" ]; then
        echo -e "Checks: ${CYAN}$CHECKS${RESET}"
        echo ""
    fi
fi

# Build Python command
PYTHON_ARGS=("--path" "$PATH_FILTER" "--arbiter" "$ARBITER_MODE" "--workers" "$WORKERS")

[ "$CHECK_LINKS" = true ] && PYTHON_ARGS+=("--check-links")
[ "$CHECK_EXAMPLES" = true ] && PYTHON_ARGS+=("--check-examples")
[ "$CHECK_GRAMMAR" = true ] && PYTHON_ARGS+=("--check-grammar")
[ "$CHECK_FORMAT" = true ] && PYTHON_ARGS+=("--check-format")
[ "$CHECK_COMPLETENESS" = true ] && PYTHON_ARGS+=("--check-completeness")
[ "$VERBOSE" = true ] && PYTHON_ARGS+=("--verbose")
[ "$SUMMARY_ONLY" = true ] && PYTHON_ARGS+=("--summary")
[ "$JSON_OUTPUT" = true ] && PYTHON_ARGS+=("--json")

# Run review
if [ "$CONTINUOUS" = true ]; then
    if [ "$JSON_OUTPUT" != true ]; then
        echo -e "${YELLOW}⟳${RESET} Continuous review mode (Ctrl+C to stop)"
        echo ""
    fi

    while true; do
        python3 cli/doc_review.py "${PYTHON_ARGS[@]}" || true

        if [ "$JSON_OUTPUT" != true ]; then
            echo ""
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
            echo -e "Waiting 60 seconds before next review..."
            sleep 60
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
            echo ""
        else
            sleep 60
        fi
    done
else
    python3 cli/doc_review.py "${PYTHON_ARGS[@]}"
fi

# Print footer
if [ "$JSON_OUTPUT" != true ] && [ "$CONTINUOUS" != true ]; then
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${GREEN}✓${RESET} Review complete"
    echo ""
    echo -e "To fix issues automatically: ${CYAN}/doc-solve${RESET}"
    echo -e "To improve iteratively: ${CYAN}/doc-improve --target-score 95${RESET}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
fi
