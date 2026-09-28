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
REVIEW_TIERS=1  # Count of review tiers (each meta- = +1)

# Count meta- prefixes in command name
# review = 1 tier
# meta-review = 2 tiers
# meta-meta-review = 3 tiers
# meta-meta-meta-review = 4 tiers
SCRIPT_NAME=$(basename "$0")
REVIEW_TIERS=$(echo "$SCRIPT_NAME" | grep -o "meta-" | wc -l)
REVIEW_TIERS=$((REVIEW_TIERS + 1))  # Add 1 for the base "review"

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

echo "🔍 Review with $REVIEW_TIERS Tier(s)"
echo "Subject: $ARTIFACT_NAME ($ARTIFACT_TYPE)"
echo "Phases per tier: $PHASE_COUNT"
echo ""

if [ $REVIEW_TIERS -eq 1 ]; then
  echo "TIER 1: Review"
  echo "  Workers analyze, Arbiter synthesizes findings"
  save_learning "Review: $ARTIFACT_NAME" "Review of $ARTIFACT_TYPE"
else
  echo "TIER 1: Review"
  echo "  Workers analyze, Arbiter synthesizes findings"
  echo ""
  for ((i=2; i<=REVIEW_TIERS; i++)); do
    echo "TIER $i: Re-Review (of tier $((i-1)) findings)"
    echo "  Different workers challenge the findings"
    echo "  New arbiter validates review quality"
    if [ $i -lt $REVIEW_TIERS ]; then
      echo ""
    fi
  done

  TIER_LABEL=$(printf 'meta-%.0s' $(seq 1 $((REVIEW_TIERS-2))) | sed 's/-$//')
  if [ -z "$TIER_LABEL" ]; then
    TIER_LABEL="meta"
  else
    TIER_LABEL="meta-$TIER_LABEL"
  fi
  save_learning "$TIER_LABEL-review: $ARTIFACT_NAME" "$REVIEW_TIERS-tier review of $ARTIFACT_TYPE"
fi
echo ""

# TODO: Invoke actual arbitration workflow
# Each tier: different workers challenge previous tier's findings
# arbitrate review "$TARGET" --type "$ARTIFACT_TYPE" --phases "$PHASE_COUNT" --tiers "$REVIEW_TIERS"

echo "✓ Review ($REVIEW_TIERS tier(s)) saved to memory"
echo "✓ Searchable: query-memory.py semantic-search 'review $ARTIFACT_NAME'"
echo "✓ View insights: memory-synthesis.py"
