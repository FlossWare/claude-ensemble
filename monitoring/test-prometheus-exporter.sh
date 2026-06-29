#!/bin/bash
# Test script for Prometheus exporter

echo "=== Testing Prometheus Exporter ==="
echo

# Check if exporter is running
echo "1. Checking if exporter is running on port 9101..."
if curl -s http://localhost:9101/health >/dev/null 2>&1; then
  echo "   ✓ Exporter is running"
else
  echo "   ✗ Exporter is NOT running"
  echo "   Start with: node prometheus-exporter.cjs &"
  exit 1
fi
echo

# Test health endpoint
echo "2. Testing /health endpoint..."
HEALTH=$(curl -s http://localhost:9101/health)
if [ "$HEALTH" = "OK" ]; then
  echo "   ✓ Health check passed: $HEALTH"
else
  echo "   ✗ Health check failed: $HEALTH"
fi
echo

# Test metrics endpoint
echo "3. Testing /metrics endpoint..."
METRICS=$(curl -s http://localhost:9101/metrics)
if [ -n "$METRICS" ]; then
  echo "   ✓ Metrics endpoint returned data"
  echo
  echo "   Sample metrics:"
  echo "$METRICS" | head -20
  echo "   ..."
else
  echo "   ✗ Metrics endpoint returned no data"
fi
echo

# Count metrics
echo "4. Counting exposed metrics..."
TOTAL_METRICS=$(echo "$METRICS" | grep -c "^consensus_")
echo "   Found $TOTAL_METRICS consensus metrics"
echo

# Verify required metrics
echo "5. Verifying required metrics exist..."
REQUIRED_METRICS=(
  "consensus_decisions_total"
  "consensus_cost_usd"
  "consensus_disagreement_score_bucket"
  "consensus_quality_score"
  "consensus_drift_alerts_total"
)

for metric in "${REQUIRED_METRICS[@]}"; do
  if echo "$METRICS" | grep -q "^$metric"; then
    echo "   ✓ $metric"
  else
    echo "   ✗ $metric (MISSING)"
  fi
done
echo

# Test PostgreSQL connectivity
echo "6. Testing PostgreSQL connectivity..."
if command -v psql >/dev/null 2>&1; then
  if psql -h laptop-01 -U sfloess -d learning -c "SELECT 1" >/dev/null 2>&1; then
    echo "   ✓ PostgreSQL connection successful"
  else
    echo "   ✗ PostgreSQL connection failed"
    echo "   Check: psql -h laptop-01 -U sfloess -d learning"
  fi
else
  echo "   ⚠ psql not installed, skipping test"
fi
echo

# Summary
echo "=== Test Summary ==="
echo "Exporter: http://localhost:9101/metrics"
echo "Health: http://localhost:9101/health"
echo "Total metrics: $TOTAL_METRICS"
echo
echo "Next steps:"
echo "1. Configure Prometheus to scrape http://localhost:9101/metrics"
echo "2. Import grafana-dashboard-consensus.json to Grafana"
echo "3. Verify dashboard panels show data"
