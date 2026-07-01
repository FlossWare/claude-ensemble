#!/bin/bash

# Verify Experiment Integration (Issue #267)
# Created: 2026-07-01

set -e

echo "🔍 Verifying experiment manager integration"
echo ""

# Check files exist
echo "1. Checking files exist..."
FILES=(
  "shared/experiment-manager.cjs"
  "shared/experiment-integration.cjs"
  "shared/example-experiment-integration.cjs"
  "shared/test-experiment-integration.cjs"
  "docs/experiment-integration-guide.md"
)

for file in "${FILES[@]}"; do
  if [ -f "$file" ]; then
    echo "  ✓ $file"
  else
    echo "  ✗ $file (missing)"
    exit 1
  fi
done

echo ""
echo "2. Checking PostgreSQL connection..."
if psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT 1" > /dev/null 2>&1; then
  echo "  ✓ PostgreSQL connection OK"
else
  echo "  ⚠ PostgreSQL connection failed (experiments will not persist)"
fi

echo ""
echo "3. Running integration tests..."
node shared/test-experiment-integration.cjs

echo ""
echo "4. Running example (rollout experiment)..."
node shared/example-experiment-integration.cjs --type rollout

echo ""
echo "5. Checking experiment history..."
EXPERIMENT_COUNT=$(psql -h aio-01 -p 5433 -U sfloess -d learning -t -c "SELECT COUNT(*) FROM workflow.experiments" 2>/dev/null || echo "0")
echo "  Total experiments recorded: $EXPERIMENT_COUNT"

echo ""
echo "✅ Verification complete!"
echo ""
echo "Integration points:"
echo "  - Model rotation: shared/model-rotation.cjs (promoteModel function)"
echo "  - Weighted voting: shared/weighted-voting-with-explain.cjs"
echo "  - Custom experiments: Use shared/experiment-integration.cjs"
echo ""
echo "Next steps:"
echo "  1. Add runRolloutExperiment() to model-rotation.cjs"
echo "  2. Add runVotingExperiment() to periodic voting tests"
echo "  3. Create custom experiments for routing strategies"
echo ""
