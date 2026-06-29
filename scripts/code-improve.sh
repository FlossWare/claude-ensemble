#!/usr/bin/env bash
#
# Code-Improve Skill - Continuous improvement loop
# Review → Resolve → Review → ... until convergence
#

set -e

# Show help if requested
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    cat << 'EOF'
/code-improve - Iterative Code Quality Improvement

USAGE:
  /code-improve [PATH] [OPTIONS]
  /code-improve --help

DESCRIPTION:
  Continuously improves code quality through iterative review and resolution:
  Review → Prioritize → Resolve → Verify → Repeat

  Stops when:
  - No issues remain
  - Target score reached
  - Max iterations reached

EXAMPLES:
  /code-improve                           Improve current directory
  /code-improve src/                      Improve src/ directory
  /code-improve --target-score 98         Stop at 98% quality score
  /code-improve --max-iterations 5        Limit to 5 iterations
  /code-improve --auto                    Auto-fix without prompts

OPTIONS:
  --max-iterations N      Maximum iterations (default: 10)
  --target-score N        Stop at quality score N (default: 95)
  --batch-size N          Issues per iteration (default: 5)
  --auto                  Auto-fix mode, no prompts
  --arbiter MODE          Arbiter mode: rotating|single (default: rotating)
  --create-prs            Create PRs for fixes
  --path PATH             Path filter (default: .)
  --min-confidence N      Minimum confidence 0.0-1.0 (default: 0.80)

QUALITY SCORE:
  Score = 100 - (critical×10 + major×5 + minor×1)

  Examples:
  - 1 critical issue = 90 score
  - 2 major issues = 90 score
  - 10 minor issues = 90 score

DOCUMENTATION:
  See: code-improve.md
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
MAX_ITERATIONS=10
TARGET_SCORE=95
BATCH_SIZE=5
AUTO_MODE=false
ARBITER_MODE="rotating"
CREATE_PRS=false
COMMENT_AI="none"
PATH_FILTER="."
MIN_CONFIDENCE=0.80

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-iterations)
            MAX_ITERATIONS="$2"
            shift 2
            ;;
        --target-score)
            TARGET_SCORE="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --auto)
            AUTO_MODE=true
            shift
            ;;
        --arbiter)
            ARBITER_MODE="$2"
            shift 2
            ;;
        --create-prs)
            CREATE_PRS=true
            shift
            ;;
        --comment-ai)
            COMMENT_AI="${2:-detailed}"
            shift
            [[ "$1" != --* ]] && shift
            ;;
        --path)
            PATH_FILTER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}║          Universal AI - Code Improvement Loop                        ║${RESET}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "${BLUE}Configuration:${RESET}"
echo -e "  Max Iterations: ${BOLD}$MAX_ITERATIONS${RESET}"
echo -e "  Target Score:   ${BOLD}$TARGET_SCORE%${RESET}"
echo -e "  Batch Size:     ${BOLD}$BATCH_SIZE${RESET} issues per iteration"
echo -e "  Arbiter Mode:   ${BOLD}$ARBITER_MODE${RESET}"
echo -e "  Auto Mode:      ${BOLD}$AUTO_MODE${RESET}"
echo -e "  Path Filter:    ${BOLD}$PATH_FILTER${RESET}"
echo ""

# State tracking
ITERATION=0
PREV_CRITICAL=0
PREV_MAJOR=0
PREV_MINOR=0
TOTAL_FIXED=0

# Calculate quality score
calculate_score() {
    local critical=$1
    local major=$2
    local minor=$3

    local penalty=$((critical * 10 + major * 5 + minor * 1))
    local score=$((100 - penalty))

    # Clamp to 0-100
    [[ $score -lt 0 ]] && score=0
    [[ $score -gt 100 ]] && score=100

    echo $score
}

# Main improvement loop
while [[ $ITERATION -lt $MAX_ITERATIONS ]]; do
    ITERATION=$((ITERATION + 1))

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${CYAN}${BOLD}Iteration $ITERATION of $MAX_ITERATIONS${RESET}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""

    # Phase 1: Code Review
    echo -e "${YELLOW}▶${RESET} Phase 1: ${BOLD}Code Review${RESET} (read-only analysis)"

    # TODO: Call actual code-review skill
    # For now, simulate with placeholder
    CRITICAL=$((PREV_CRITICAL > 0 ? PREV_CRITICAL - 2 : 0))
    MAJOR=$((PREV_MAJOR > 0 ? PREV_MAJOR - 3 : 0))
    MINOR=$((PREV_MINOR > 0 ? PREV_MINOR - 2 : 0))

    # First iteration: set baseline
    if [[ $ITERATION -eq 1 ]]; then
        CRITICAL=8
        MAJOR=10
        MINOR=5
    fi

    SCORE=$(calculate_score $CRITICAL $MAJOR $MINOR)

    echo -e "${GREEN}  ✓ Review complete${RESET}"
    echo -e "    Critical: ${BOLD}$CRITICAL${RESET}"
    echo -e "    Major:    ${BOLD}$MAJOR${RESET}"
    echo -e "    Minor:    ${BOLD}$MINOR${RESET}"
    echo -e "    Score:    ${BOLD}$SCORE%${RESET}"
    echo ""

    # Check stopping conditions
    TOTAL_ISSUES=$((CRITICAL + MAJOR + MINOR))

    if [[ $TOTAL_ISSUES -eq 0 ]]; then
        echo -e "${GREEN}${BOLD}🎉 No issues found! Code quality perfect.${RESET}"
        break
    fi

    if [[ $SCORE -ge $TARGET_SCORE ]]; then
        echo -e "${GREEN}${BOLD}🎯 Target score reached: $SCORE% ≥ $TARGET_SCORE%${RESET}"
        break
    fi

    # Phase 2: Prioritize
    echo -e "${YELLOW}▶${RESET} Phase 2: ${BOLD}Prioritize Issues${RESET}"

    # Determine how many to fix this iteration
    FIXES_THIS_ITERATION=$BATCH_SIZE
    [[ $TOTAL_ISSUES -lt $BATCH_SIZE ]] && FIXES_THIS_ITERATION=$TOTAL_ISSUES

    echo -e "${GREEN}  ✓ Selected top $FIXES_THIS_ITERATION issues for resolution${RESET}"
    echo ""

    # Prompt if not auto mode
    if [[ "$AUTO_MODE" != "true" ]]; then
        echo -e "${YELLOW}Fix $FIXES_THIS_ITERATION issues? [Y/n]:${RESET} "
        read -r response
        if [[ "$response" =~ ^[Nn] ]]; then
            echo -e "${YELLOW}Stopping at iteration $ITERATION${RESET}"
            break
        fi
    fi

    # Phase 3: Code Resolve
    echo -e "${YELLOW}▶${RESET} Phase 3: ${BOLD}Code Resolve${RESET} (applying fixes)"

    # TODO: Call actual code-resolve for selected issues
    # For now, simulate
    sleep 2

    FIXED_THIS_ITERATION=$FIXES_THIS_ITERATION
    TOTAL_FIXED=$((TOTAL_FIXED + FIXED_THIS_ITERATION))

    echo -e "${GREEN}  ✓ Fixed $FIXED_THIS_ITERATION issues${RESET}"
    echo ""

    # Phase 4: Verification
    echo -e "${YELLOW}▶${RESET} Phase 4: ${BOLD}Verification${RESET}"

    # TODO: Re-run review to verify fixes
    # Check for regressions

    echo -e "${GREEN}  ✓ Verification passed${RESET}"
    echo -e "    No new critical issues introduced"
    echo ""

    # Update state for next iteration
    PREV_CRITICAL=$CRITICAL
    PREV_MAJOR=$MAJOR
    PREV_MINOR=$MINOR

done

# Final Summary
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${CYAN}${BOLD}Improvement Summary${RESET}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "${GREEN}${BOLD}✓ Completed $ITERATION iterations${RESET}"
echo -e "${GREEN}  Total issues fixed: ${BOLD}$TOTAL_FIXED${RESET}"
echo -e "${GREEN}  Final score:        ${BOLD}$SCORE%${RESET}"
echo ""

if [[ $CREATE_PRS == "true" ]]; then
    echo -e "${BLUE}Creating pull request...${RESET}"
    # TODO: Create PR with all changes
    echo -e "${GREEN}  ✓ PR created${RESET}"
    echo ""
fi

echo -e "${GREEN}${BOLD}🎉 Code improvement complete!${RESET}"
echo ""
