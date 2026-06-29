#!/bin/bash
#
# SDLC Continuous Loop - Keeps running SDLC phases until codebase is clean
#
# Usage:
#   ./sdlc-loop.sh [max_iterations] [budget_per_iteration]
#
# Examples:
#   ./sdlc-loop.sh              # Run until clean (default 5 iterations, 200k budget each)
#   ./sdlc-loop.sh 10           # Max 10 iterations
#   ./sdlc-loop.sh 10 500k      # Max 10 iterations, 500k tokens each

set -e

# Concurrency control - prevent multiple instances
LOCKFILE="/tmp/sdlc-loop.lock"
exec 200>"$LOCKFILE"
if ! flock -n 200; then
  echo "❌ Another instance of sdlc-loop.sh is already running"
  echo "   Lock file: $LOCKFILE"
  echo "   If this is incorrect, remove the lock file and try again"
  exit 1
fi
trap 'rm -f "$LOCKFILE"' EXIT

MAX_ITERATIONS=${1:-5}
BUDGET=${2:-200k}
ITERATION=0
FAILED_PHASES=""

echo "════════════════════════════════════════════════════════════"
echo "🔄 CONTINUOUS SDLC LOOP"
echo "════════════════════════════════════════════════════════════"
echo "Max iterations: $MAX_ITERATIONS"
echo "Budget per iteration: $BUDGET"
echo ""
echo "Will run these workflows in sequence:"
echo "  1. code-review-auto  - Find bugs"
echo "  2. code-solve-auto   - Fix issues"
echo "  3. code-test-auto    - Run tests"
echo "  4. code-pr-review-auto - Review PRs"
echo "  5. code-security-auto - Security audit"
echo "  6. code-doc-auto     - Generate docs"
echo "  7. code-release-notes-auto - Publish release"
echo ""
echo "Loop continues until codebase is clean or max iterations reached"
echo "════════════════════════════════════════════════════════════"
echo ""

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
  ITERATION=$((ITERATION + 1))
  FAILED_PHASES=""  # Reset for each iteration

  echo ""
  echo "────────────────────────────────────────────────────────────"
  echo "🔁 ITERATION $ITERATION/$MAX_ITERATIONS"
  echo "────────────────────────────────────────────────────────────"
  echo ""

  # Phase 1: Development (code-review + code-solve)
  echo "═══ PHASE 1: DEVELOPMENT ═══"
  echo ""

  echo "🔍 Running code-review-auto..."
  if ! claude run code-review-auto +$BUDGET; then
    echo "⚠️  code-review-auto failed"
    FAILED_PHASES="$FAILED_PHASES code-review-auto"
  fi

  # Check if there are issues to fix (detect GitHub vs GitLab)
  if git remote -v | grep -q "github.com"; then
    ISSUES_COUNT=$(gh issue list --json number --label "ai-review" 2>/dev/null | jq 'length' 2>/dev/null || echo "0")
  elif git remote -v | grep -q "gitlab"; then
    ISSUES_COUNT=$(glab issue list --all 2>/dev/null | grep -c "^" || echo "0")
  else
    ISSUES_COUNT=0
  fi
  ISSUES_COUNT=${ISSUES_COUNT:-0}  # Default to 0 if empty
  echo "📊 Found $ISSUES_COUNT issues"

  if [ "$ISSUES_COUNT" -gt 0 ] 2>/dev/null; then
    echo ""
    echo "🔧 Running code-solve-auto..."
    if ! claude run code-solve-auto +$BUDGET; then
      echo "⚠️  code-solve-auto failed"
    FAILED_PHASES="$FAILED_PHASES code-solve-auto"
    fi
  else
    echo "ℹ️  No issues found, skipping code-solve-auto"
  fi

  # Phase 2: Testing
  echo ""
  echo "═══ PHASE 2: TESTING ═══"
  echo ""
  echo "🧪 Running code-test-auto..."
  if ! claude run code-test-auto +$BUDGET; then
    echo "⚠️  code-test-auto failed"
    FAILED_PHASES="$FAILED_PHASES code-test-auto"
  fi

  # Phase 3: PR Review
  echo ""
  echo "═══ PHASE 3: PR REVIEW ═══"
  echo ""

  # Check if there are open PRs (detect GitHub vs GitLab)
  if git remote -v | grep -q "github.com"; then
    PR_COUNT=$(gh pr list --json number 2>/dev/null | jq 'length' 2>/dev/null || echo "0")
  elif git remote -v | grep -q "gitlab"; then
    PR_COUNT=$(glab mr list 2>/dev/null | grep -c "^!" || echo "0")
  else
    PR_COUNT=0
  fi
  PR_COUNT=${PR_COUNT:-0}  # Default to 0 if empty
  echo "📊 Found $PR_COUNT open PRs"

  if [ "$PR_COUNT" -gt 0 ] 2>/dev/null; then
    echo "🔀 Running code-pr-review-auto..."
    if ! claude run code-pr-review-auto +$BUDGET; then
      echo "⚠️  code-pr-review-auto failed"
    FAILED_PHASES="$FAILED_PHASES code-pr-review-auto"
    fi
  else
    echo "ℹ️  No open PRs, skipping code-pr-review-auto"
  fi

  # Phase 4: Security
  echo ""
  echo "═══ PHASE 4: SECURITY ═══"
  echo ""
  echo "🔒 Running code-security-auto..."
  if ! claude run code-security-auto +$BUDGET; then
    echo "⚠️  code-security-auto failed"
    FAILED_PHASES="$FAILED_PHASES code-security-auto"
  fi

  # Phase 5: Documentation
  echo ""
  echo "═══ PHASE 5: DOCUMENTATION ═══"
  echo ""
  echo "📚 Running code-doc-auto..."
  if ! claude run code-doc-auto +$BUDGET; then
    echo "⚠️  code-doc-auto failed"
    FAILED_PHASES="$FAILED_PHASES code-doc-auto"
  fi

  # Phase 6: Release
  echo ""
  echo "═══ PHASE 6: RELEASE ═══"
  echo ""

  # Check if there are commits since last release
  COMMITS_SINCE_LAST=$(git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~10")..HEAD 2>/dev/null | wc -l || echo "0")
  echo "📊 Found $COMMITS_SINCE_LAST commits since last release"

  if [ "$COMMITS_SINCE_LAST" -gt 0 ]; then
    echo "📦 Running code-release-notes-auto..."
    if ! claude run code-release-notes-auto +$BUDGET; then
      echo "⚠️  code-release-notes-auto failed"
    FAILED_PHASES="$FAILED_PHASES code-release-notes-auto"
    fi
  else
    echo "ℹ️  No new commits, skipping code-release-notes-auto"
  fi

  # Phase 7: Check if clean
  echo ""
  echo "═══ PHASE 7: SUMMARY ═══"
  echo ""

  # Check final status (detect GitHub vs GitLab)
  if git remote -v | grep -q "github.com"; then
    FINAL_ISSUES=$(gh issue list --json number 2>/dev/null | jq 'length' 2>/dev/null || echo "0")
    FINAL_PRS=$(gh pr list --json number 2>/dev/null | jq 'length' 2>/dev/null || echo "0")
  elif git remote -v | grep -q "gitlab"; then
    FINAL_ISSUES=$(glab issue list --all 2>/dev/null | grep -c "^" || echo "0")
    FINAL_PRS=$(glab mr list 2>/dev/null | grep -c "^!" || echo "0")
  else
    FINAL_ISSUES=0
    FINAL_PRS=0
  fi
  FINAL_ISSUES=${FINAL_ISSUES:-0}  # Default to 0 if empty
  FINAL_PRS=${FINAL_PRS:-0}  # Default to 0 if empty

  echo "📊 Iteration $ITERATION Summary:"
  echo "   Open issues: $FINAL_ISSUES"
  echo "   Open PRs: $FINAL_PRS"
  if [ -n "$FAILED_PHASES" ]; then
    echo "   ⚠️  Failed phases:$FAILED_PHASES"
  fi
  echo ""

  # Check if codebase is clean
  if [ "$FINAL_ISSUES" -eq 0 ] 2>/dev/null && [ "$FINAL_PRS" -eq 0 ] 2>/dev/null; then
    echo "════════════════════════════════════════════════════════════"
    echo "🎉 CODEBASE IS CLEAN!"
    echo "════════════════════════════════════════════════════════════"
    echo "Completed in $ITERATION iterations"
    echo ""
    exit 0
  fi

  echo "🔄 More work remains, continuing to next iteration..."
done

echo ""
echo "════════════════════════════════════════════════════════════"
echo "⚠️  MAX ITERATIONS REACHED"
echo "════════════════════════════════════════════════════════════"
echo "Stopped after $MAX_ITERATIONS iterations"
echo "Codebase may still have issues - check manually"
echo ""
exit 1
