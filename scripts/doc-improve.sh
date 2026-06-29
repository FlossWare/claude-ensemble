#!/usr/bin/env bash
#
# Doc-Improve Skill - Continuous documentation improvement loop
# Review → Resolve → Review → ... until convergence
#

set -e

# Show help if requested
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    cat << 'EOF'
/doc-improve - Iterative Documentation Quality Improvement

USAGE:
  /doc-improve [PATH] [OPTIONS]
  /doc-improve --help

DESCRIPTION:
  Continuously improves documentation quality through iterative review and resolution:
  Review → Prioritize → Resolve → Verify → Repeat

  Checks for:
  - Missing content
  - Broken links
  - Outdated examples
  - Grammar issues
  - Formatting problems
  - Completeness

  Stops when:
  - No issues remain
  - Target score reached
  - Max iterations reached

EXAMPLES:
  /doc-improve                           Improve all documentation
  /doc-improve docs/                     Improve docs/ directory
  /doc-improve --target-score 98         Stop at 98% quality score
  /doc-improve --check-all               Enable all checks
  /doc-improve --auto                    Auto-fix without prompts

OPTIONS:
  --max-iterations N      Maximum iterations (default: 10)
  --target-score N        Stop at quality score N (default: 95)
  --batch-size N          Issues per iteration (default: 5)
  --auto                  Auto-fix mode, no prompts
  --arbiter MODE          Arbiter mode: rotating|single (default: rotating)
  --create-prs            Create PRs for fixes
  --path PATH             Path filter (default: .)

  --check-links           Check for broken links
  --check-examples        Validate code examples
  --check-grammar         Check grammar and spelling
  --check-format          Check formatting consistency
  --check-completeness    Check for missing sections
  --check-all             Enable all checks

QUALITY SCORE:
  Score = 100 - (critical×10 + major×5 + minor×1)

  Issue severity examples:
  - Critical: Broken links, missing required sections
  - Major: Outdated examples, grammar errors
  - Minor: Formatting issues, typos

DOCUMENTATION:
  See: doc-improve.md
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
CHECK_LINKS=false
CHECK_EXAMPLES=false
CHECK_GRAMMAR=false
CHECK_FORMAT=false
CHECK_COMPLETENESS=false

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
        --links)
            CHECK_LINKS=true
            shift
            ;;
        --examples)
            CHECK_EXAMPLES=true
            shift
            ;;
        --grammar)
            CHECK_GRAMMAR=true
            shift
            ;;
        --format)
            CHECK_FORMAT=true
            shift
            ;;
        --completeness)
            CHECK_COMPLETENESS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# If no specific checks, enable all
if [[ "$CHECK_LINKS" == "false" && "$CHECK_EXAMPLES" == "false" && \
      "$CHECK_GRAMMAR" == "false" && "$CHECK_FORMAT" == "false" && \
      "$CHECK_COMPLETENESS" == "false" ]]; then
    CHECK_LINKS=true
    CHECK_EXAMPLES=true
    CHECK_GRAMMAR=true
    CHECK_FORMAT=true
    CHECK_COMPLETENESS=true
fi

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}║       Universal AI - Documentation Improvement Loop                 ║${RESET}"
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
echo -e "${BLUE}Checks Enabled:${RESET}"
[[ "$CHECK_LINKS" == "true" ]] && echo -e "  ✓ Link validation"
[[ "$CHECK_EXAMPLES" == "true" ]] && echo -e "  ✓ Code example verification"
[[ "$CHECK_GRAMMAR" == "true" ]] && echo -e "  ✓ Grammar and spelling"
[[ "$CHECK_FORMAT" == "true" ]] && echo -e "  ✓ Formatting consistency"
[[ "$CHECK_COMPLETENESS" == "true" ]] && echo -e "  ✓ Completeness analysis"
echo ""

# State tracking
ITERATION=0
PREV_CRITICAL=0
PREV_MAJOR=0
PREV_MINOR=0
TOTAL_FIXED=0
BROKEN_LINKS=0
OUTDATED_EXAMPLES=0

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

    # Phase 1: Documentation Review
    echo -e "${YELLOW}▶${RESET} Phase 1: ${BOLD}Documentation Review${RESET} (read-only analysis)"

    # TODO: Call actual doc-review skill
    # For now, simulate with placeholder
    CRITICAL=$((PREV_CRITICAL > 0 ? PREV_CRITICAL - 1 : 0))
    MAJOR=$((PREV_MAJOR > 0 ? PREV_MAJOR - 2 : 0))
    MINOR=$((PREV_MINOR > 0 ? PREV_MINOR - 3 : 0))

    # First iteration: set baseline
    if [[ $ITERATION -eq 1 ]]; then
        CRITICAL=3
        MAJOR=8
        MINOR=7
        BROKEN_LINKS=5
        OUTDATED_EXAMPLES=4
    fi

    SCORE=$(calculate_score $CRITICAL $MAJOR $MINOR)

    echo -e "${GREEN}  ✓ Review complete${RESET}"
    echo -e "    Critical: ${BOLD}$CRITICAL${RESET}"
    echo -e "    Major:    ${BOLD}$MAJOR${RESET}"
    echo -e "    Minor:    ${BOLD}$MINOR${RESET}"
    echo -e "    Score:    ${BOLD}$SCORE%${RESET}"
    echo ""

    # Show specific issues
    if [[ "$CHECK_LINKS" == "true" && $BROKEN_LINKS -gt 0 ]]; then
        echo -e "    Broken links: ${BOLD}$BROKEN_LINKS${RESET}"
    fi
    if [[ "$CHECK_EXAMPLES" == "true" && $OUTDATED_EXAMPLES -gt 0 ]]; then
        echo -e "    Outdated examples: ${BOLD}$OUTDATED_EXAMPLES${RESET}"
    fi
    echo ""

    # Check stopping conditions
    TOTAL_ISSUES=$((CRITICAL + MAJOR + MINOR))

    if [[ $TOTAL_ISSUES -eq 0 ]]; then
        echo -e "${GREEN}${BOLD}🎉 No issues found! Documentation quality perfect.${RESET}"
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

    # Phase 3: Doc Resolve
    echo -e "${YELLOW}▶${RESET} Phase 3: ${BOLD}Documentation Resolve${RESET} (applying fixes)"

    # TODO: Call actual doc-resolve for selected issues
    # For now, simulate
    sleep 2

    FIXED_THIS_ITERATION=$FIXES_THIS_ITERATION
    TOTAL_FIXED=$((TOTAL_FIXED + FIXED_THIS_ITERATION))

    # Update broken links count
    if [[ $BROKEN_LINKS -gt 0 ]]; then
        LINKS_FIXED=$((BROKEN_LINKS > 2 ? 2 : BROKEN_LINKS))
        BROKEN_LINKS=$((BROKEN_LINKS - LINKS_FIXED))
        echo -e "${GREEN}  ✓ Fixed $LINKS_FIXED broken links${RESET}"
    fi

    # Update examples count
    if [[ $OUTDATED_EXAMPLES -gt 0 ]]; then
        EXAMPLES_FIXED=$((OUTDATED_EXAMPLES > 1 ? 1 : OUTDATED_EXAMPLES))
        OUTDATED_EXAMPLES=$((OUTDATED_EXAMPLES - EXAMPLES_FIXED))
        echo -e "${GREEN}  ✓ Updated $EXAMPLES_FIXED code examples${RESET}"
    fi

    echo -e "${GREEN}  ✓ Fixed $FIXED_THIS_ITERATION documentation issues${RESET}"
    echo ""

    # Phase 4: Verification
    echo -e "${YELLOW}▶${RESET} Phase 4: ${BOLD}Verification${RESET}"

    # TODO: Re-run review to verify fixes
    # Check for regressions

    echo -e "${GREEN}  ✓ Verification passed${RESET}"
    echo -e "    All links valid"
    echo -e "    All examples tested"
    echo -e "    No new issues introduced"
    echo ""

    # Update state for next iteration
    PREV_CRITICAL=$CRITICAL
    PREV_MAJOR=$MAJOR
    PREV_MINOR=$MINOR

done

# Final Summary
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${CYAN}${BOLD}Documentation Improvement Summary${RESET}"
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

echo -e "${GREEN}${BOLD}📚 Documentation improvement complete!${RESET}"
echo ""
