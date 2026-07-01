#!/bin/bash

# Find Confidence Calibration Integration Points
#
# Scans codebase to identify files that:
# 1. Make arbiter decisions (need recordArbiterOutcome)
# 2. Calculate quality scores (need recordQualityOutcome)
# 3. Run weighted voting (need recordVotingOutcome)
#
# Usage: ./scripts/find-calibration-integration-points.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=================================================="
echo "Confidence Calibration Integration Point Scanner"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Find arbiter decision points
echo -e "${BLUE}[1] Files with arbiter decisions (need recordArbiterOutcome):${NC}"
echo ""

grep -r "arbiter.*decision\|selected.*answer\|storeArbiterDecision" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/ 2>/dev/null | \
  grep -v "confidence-calibration" | \
  cut -d: -f1 | \
  sort -u | \
  while read -r file; do
    # Check if already integrated
    if grep -q "recordArbiterOutcome" "$file" 2>/dev/null; then
      echo -e "  ${GREEN}✓${NC} $file (already integrated)"
    else
      echo -e "  ${YELLOW}○${NC} $file (needs integration)"
    fi
  done

echo ""

# 2. Find quality scoring points
echo -e "${BLUE}[2] Files with quality scoring (need recordQualityOutcome):${NC}"
echo ""

grep -r "calculateQualityScore\|quality.*score\|meetsQualityThreshold" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/ 2>/dev/null | \
  grep -v "confidence-calibration\|quality-scorer.js\|quality-scorer.test.js" | \
  cut -d: -f1 | \
  sort -u | \
  while read -r file; do
    if grep -q "recordQualityOutcome" "$file" 2>/dev/null; then
      echo -e "  ${GREEN}✓${NC} $file (already integrated)"
    else
      echo -e "  ${YELLOW}○${NC} $file (needs integration)"
    fi
  done

echo ""

# 3. Find weighted voting points
echo -e "${BLUE}[3] Files using weighted voting (need recordVotingOutcome):${NC}"
echo ""

grep -r "runWeightedVoting\|weightedVoting" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/ 2>/dev/null | \
  grep -v "confidence-calibration\|weighted-voting.cjs\|weighted-voting.test.cjs" | \
  cut -d: -f1 | \
  sort -u | \
  while read -r file; do
    if grep -q "recordVotingOutcome" "$file" 2>/dev/null; then
      echo -e "  ${GREEN}✓${NC} $file (already integrated)"
    else
      echo -e "  ${YELLOW}○${NC} $file (needs integration)"
    fi
  done

echo ""

# 4. Summary
echo -e "${BLUE}[4] Integration Summary:${NC}"
echo ""

TOTAL_ARBITER=$(grep -r "arbiter.*decision\|selected.*answer\|storeArbiterDecision" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/ 2>/dev/null | \
  grep -v "confidence-calibration" | \
  cut -d: -f1 | sort -u | wc -l)

INTEGRATED_ARBITER=$(grep -r "recordArbiterOutcome" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/ 2>/dev/null | \
  cut -d: -f1 | sort -u | wc -l || echo "0")

TOTAL_QUALITY=$(grep -r "calculateQualityScore\|quality.*score\|meetsQualityThreshold" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/ 2>/dev/null | \
  grep -v "confidence-calibration\|quality-scorer.js\|quality-scorer.test.js" | \
  cut -d: -f1 | sort -u | wc -l)

INTEGRATED_QUALITY=$(grep -r "recordQualityOutcome" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/ 2>/dev/null | \
  cut -d: -f1 | sort -u | wc -l || echo "0")

TOTAL_VOTING=$(grep -r "runWeightedVoting\|weightedVoting" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/ 2>/dev/null | \
  grep -v "confidence-calibration\|weighted-voting.cjs\|weighted-voting.test.cjs" | \
  cut -d: -f1 | sort -u | wc -l)

INTEGRATED_VOTING=$(grep -r "recordVotingOutcome" \
  --include="*.cjs" --include="*.js" --include="*.mjs" \
  workflows/ shared/ skills/ 2>/dev/null | \
  cut -d: -f1 | sort -u | wc -l || echo "0")

echo "  Arbiter Decisions:   $INTEGRATED_ARBITER/$TOTAL_ARBITER integrated"
echo "  Quality Scoring:     $INTEGRATED_QUALITY/$TOTAL_QUALITY integrated"
echo "  Weighted Voting:     $INTEGRATED_VOTING/$TOTAL_VOTING integrated"
echo ""

TOTAL=$((TOTAL_ARBITER + TOTAL_QUALITY + TOTAL_VOTING))
INTEGRATED=$((INTEGRATED_ARBITER + INTEGRATED_QUALITY + INTEGRATED_VOTING))

if [ "$TOTAL" -eq 0 ]; then
  echo -e "${YELLOW}No integration points found${NC}"
elif [ "$INTEGRATED" -eq "$TOTAL" ]; then
  echo -e "${GREEN}✓ All integration points covered!${NC}"
else
  REMAINING=$((TOTAL - INTEGRATED))
  echo -e "${YELLOW}○ $REMAINING integration points remaining${NC}"
fi

echo ""
echo "Next steps:"
echo "  1. Review files marked with ${YELLOW}○${NC} (needs integration)"
echo "  2. Add integration using helper functions from:"
echo "     shared/confidence-calibration-integration.cjs"
echo "  3. See docs/CONFIDENCE_CALIBRATION_INTEGRATION.md for examples"
echo ""
