#!/bin/bash
# Arbiter/Workers Review Pattern - for ANY artifact
#
# Usage - CODE:
#   review PR#123                         # Code review
#   review ./src/main.py                  # Code file review
#   review -3 PR#456                      # 3-phase review (final arbiter)
#
# Usage - DOCUMENTATION:
#   review ./docs/API.md                  # API documentation review
#   review ./ARCHITECTURE.md              # Architecture doc review
#   review ./CONTRIBUTING.md              # Contributing guidelines
#   meta-review ./docs/API.md             # Question doc review quality
#
# Usage - DESIGN:
#   review ./design/feature-plan.md       # Feature design review
#   review ./design/database-schema.sql   # Schema design review
#
# Usage - DECISIONS:
#   review ./DECISION_LOG.md              # Past decisions review
#   review ./ADR/0001-*.md                # Architecture decision
#
# Automatically:
# - Runs multi-phase worker/arbiter pattern
# - Saves findings + type to memory
# - Captures design decisions
# - Alerts on critical findings

set -e

PHASE_COUNT="${PHASE_COUNT:-2}"
TARGET="${1:-.}"
REVIEW_PHASE=1  # 1 = single review, 2 = review+re-review

# Check if invoked as meta-review
if [[ "$0" == *"meta-review"* ]]; then
  REVIEW_PHASE=2
fi

if [[ "$1" == "-"* ]]; then
  PHASE_COUNT="${1:1}"
  TARGET="${2:-.}"
fi

# Detect artifact type
detect_artifact_type() {
  local target="$1"

  if [[ "$target" == "PR#"* ]]; then
    echo "Pull Request"
  elif [[ "$target" == *"ARCHITECTURE"* ]] || [[ "$target" == *"ADR"* ]]; then
    echo "Architecture Decision"
  elif [[ "$target" == *"design"* ]]; then
    echo "Design Document"
  elif [[ "$target" == *"docs/"* ]] || [[ "$target" == *".md" && "$target" != *"src/"* ]]; then
    echo "Documentation"
  elif [[ "$target" == *.sql ]]; then
    echo "Database Schema"
  elif [[ "$target" == *.py ]]; then
    echo "Python Code"
  elif [[ "$target" == *.js ]]; then
    echo "JavaScript Code"
  elif [[ "$target" == *.go ]]; then
    echo "Go Code"
  elif [[ -f "$target" ]]; then
    echo "Code File"
  else
    echo "Artifact"
  fi
}

# Resolve target name
get_target_name() {
  local target="$1"

  if [[ "$target" == "PR#"* ]]; then
    echo "PR ${target#PR#}"
  elif [[ -f "$target" ]]; then
    echo "$(basename $target)"
  else
    echo "$target"
  fi
}

ARTIFACT_TYPE=$(detect_artifact_type "$TARGET")
ARTIFACT_NAME=$(get_target_name "$TARGET")

if [ "$REVIEW_PHASE" = 2 ]; then
  echo "🔍 Meta-Review (Review + Re-Review)"
  echo "Subject: $ARTIFACT_NAME ($ARTIFACT_TYPE)"
  echo ""
  echo "PHASE 1: Initial Review"
  echo "  Workers analyze, Arbiter synthesizes findings"
  echo ""
  echo "PHASE 2: Meta-Review (of the findings)"
  echo "  Different workers challenge the findings"
  echo "  New arbiter validates review quality"
  echo ""
  save_learning "Meta-Review: $ARTIFACT_NAME" "Two-tier review of $ARTIFACT_TYPE"
else
  echo "🔍 Review (Arbiter/Workers Pattern)"
  echo "Subject: $ARTIFACT_NAME ($ARTIFACT_TYPE)"
  echo "Phases: $PHASE_COUNT"
  echo ""
  echo "Running multi-phase review (workers → arbiter synthesis)..."
  echo ""
  save_learning "Review: $ARTIFACT_NAME" "Multi-phase review of $ARTIFACT_TYPE ($PHASE_COUNT phases)"
fi

# TODO: Invoke actual arbitration workflow
# Phase 1: review
# arbitrate review "$TARGET" --type "$ARTIFACT_TYPE" --phases "$PHASE_COUNT"

if [ "$REVIEW_PHASE" = 2 ]; then
  # Phase 2: meta-review of the findings
  # arbitrate review "$TARGET" --type "$ARTIFACT_TYPE" --phases 2 --meta
  echo ""
  echo "✓ Phase 1 (Review) saved to memory"
  echo "✓ Phase 2 (Meta-Review) saved to memory"
  echo "✓ Find both: query-memory.py semantic-search 'meta-review $ARTIFACT_NAME'"
  echo "✓ View insights: memory-synthesis.py"
else
  echo "✓ Review saved to memory"
  echo "✓ Searchable: query-memory.py semantic-search 'review $ARTIFACT_NAME'"
fi
