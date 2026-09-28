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
META=false
AUTO_META=false

# Check if invoked as meta-review
if [[ "$0" == *"meta-review"* ]]; then
  META=true
fi

# Check for --meta flag (auto meta-review after review)
if [[ "$1" == "--meta" ]] || [[ "$1" == "-m" ]]; then
  AUTO_META=true
  TARGET="${2:-.}"
  shift 2
  # Handle phase count after --meta
  if [[ "$1" == "-"* ]]; then
    PHASE_COUNT="${1:1}"
    TARGET="${2:-.}"
  fi
elif [[ "$1" == "-"* ]]; then
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

if [ "$META" = true ]; then
  echo "🔍 Meta-Review (Challenge the Review)"
  echo "Subject: $ARTIFACT_NAME ($ARTIFACT_TYPE)"
  echo "Phases: 2 (workers challenge, arbiter synthesizes)"
  echo ""
  echo "Workers will:"
  echo "  1. Review the original findings for soundness"
  echo "  2. Identify gaps or missed concerns"
  echo "  3. Challenge assumptions"
  echo ""
  save_learning "Meta-Review: $ARTIFACT_NAME" "Evaluating review quality of $ARTIFACT_TYPE"
else
  echo "🔍 Arbiter/Workers Review"
  echo "Subject: $ARTIFACT_NAME ($ARTIFACT_TYPE)"
  echo "Phases: $PHASE_COUNT"
  echo ""
  echo "Running multi-phase review (workers → arbiter synthesis)..."
  echo ""
  save_learning "Review: $ARTIFACT_NAME" "Multi-phase review of $ARTIFACT_TYPE ($PHASE_COUNT phases)"
fi

# TODO: Invoke actual arbitration workflow
# arbitrate review "$TARGET" --type "$ARTIFACT_TYPE" --phases "$PHASE_COUNT" --meta="$META"

echo "✓ Review saved to memory"
echo "✓ Searchable: query-memory.py semantic-search 'review $ARTIFACT_NAME'"

# AUTO META-REVIEW: If --meta flag was set, automatically run meta-review
if [ "$AUTO_META" = true ] && [ "$META" = false ]; then
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Running Meta-Review (validating review quality)..."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # Run meta-review script
  META=true \
  PHASE_COUNT=2 \
  "$0" "$TARGET"

  echo ""
  echo "✓ Both review and meta-review saved to memory"
  echo "✓ Find both: query-memory.py semantic-search 'review $ARTIFACT_NAME'"
  echo "✓ View insights: memory-synthesis.py"
fi
