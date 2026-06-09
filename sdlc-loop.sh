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

MAX_ITERATIONS=${1:-5}
BUDGET=${2:-200k}
ITERATION=0

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

  echo ""
  echo "────────────────────────────────────────────────────────────"
  echo "🔁 ITERATION $ITERATION/$MAX_ITERATIONS"
  echo "────────────────────────────────────────────────────────────"
  echo ""

  # Phase 1: Development (code-review + code-solve)
  echo "═══ PHASE 1: DEVELOPMENT ═══"
  echo ""

  echo "🔍 Running code-review-auto..."
  claude run code-review-auto +$BUDGET || {
    echo "⚠️  code-review-auto failed, continuing..."
  }

  # Check if there are issues to fix
  ISSUES_COUNT=$(gh issue list --json number --label "ai-review" 2>/dev/null | jq 'length' || echo "0")
  echo "📊 Found $ISSUES_COUNT issues"

  if [ "$ISSUES_COUNT" -gt 0 ]; then
    echo ""
    echo "🔧 Running code-solve-auto..."
    claude run code-solve-auto +$BUDGET || {
      echo "⚠️  code-solve-auto failed, continuing..."
    }
  else
    echo "ℹ️  No issues found, skipping code-solve-auto"
  fi

  # Phase 2: Testing
  echo ""
  echo "═══ PHASE 2: TESTING ═══"
  echo ""
  echo "🧪 Running code-test-auto..."
  claude run code-test-auto +$BUDGET || {
    echo "⚠️  code-test-auto failed, continuing..."
  }

  # Phase 3: PR Review
  echo ""
  echo "═══ PHASE 3: PR REVIEW ═══"
  echo ""

  # Check if there are open PRs
  PR_COUNT=$(gh pr list --json number 2>/dev/null | jq 'length' || glab mr list 2>/dev/null | wc -l || echo "0")
  echo "📊 Found $PR_COUNT open PRs"

  if [ "$PR_COUNT" -gt 0 ]; then
    echo "🔀 Running code-pr-review-auto..."
    claude run code-pr-review-auto +$BUDGET || {
      echo "⚠️  code-pr-review-auto failed, continuing..."
    }
  else
    echo "ℹ️  No open PRs, skipping code-pr-review-auto"
  fi

  # Phase 4: Security
  echo ""
  echo "═══ PHASE 4: SECURITY ═══"
  echo ""
  echo "🔒 Running code-security-auto..."
  claude run code-security-auto +$BUDGET || {
    echo "⚠️  code-security-auto failed, continuing..."
  }

  # Phase 5: Documentation
  echo ""
  echo "═══ PHASE 5: DOCUMENTATION ═══"
  echo ""
  echo "📚 Running code-doc-auto..."
  claude run code-doc-auto +$BUDGET || {
    echo "⚠️  code-doc-auto failed, continuing..."
  }

  # Phase 6: Release
  echo ""
  echo "═══ PHASE 6: RELEASE ═══"
  echo ""

  # Check if there are commits since last release
  COMMITS_SINCE_LAST=$(git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~10")..HEAD 2>/dev/null | wc -l || echo "0")
  echo "📊 Found $COMMITS_SINCE_LAST commits since last release"

  if [ "$COMMITS_SINCE_LAST" -gt 0 ]; then
    echo "📦 Running code-release-notes-auto..."
    claude run code-release-notes-auto +$BUDGET || {
      echo "⚠️  code-release-notes-auto failed, continuing..."
    }
  else
    echo "ℹ️  No new commits, skipping code-release-notes-auto"
  fi

  # Phase 7: Check if clean
  echo ""
  echo "═══ PHASE 7: SUMMARY ═══"
  echo ""

  FINAL_ISSUES=$(gh issue list --json number 2>/dev/null | jq 'length' || echo "0")
  FINAL_PRS=$(gh pr list --json number 2>/dev/null | jq 'length' || echo "0")

  echo "📊 Iteration $ITERATION Summary:"
  echo "   Open issues: $FINAL_ISSUES"
  echo "   Open PRs: $FINAL_PRS"
  echo ""

  # Check if codebase is clean
  if [ "$FINAL_ISSUES" -eq 0 ] && [ "$FINAL_PRS" -eq 0 ]; then
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
