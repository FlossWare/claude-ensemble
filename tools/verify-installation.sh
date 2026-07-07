#!/bin/bash
###############################################################################
# Fleet Health Predictor - Installation Verification Script
#
# Verifies all components are correctly installed and configured.
###############################################################################

set -euo pipefail

echo "============================================================"
echo "Fleet Health Predictor - Installation Verification"
echo "============================================================"
echo ""

ERRORS=0
WARNINGS=0

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
  echo -e "${GREEN}✅ PASS${NC}: $1"
}

check_fail() {
  echo -e "${RED}❌ FAIL${NC}: $1"
  ((ERRORS++))
}

check_warn() {
  echo -e "${YELLOW}⚠️  WARN${NC}: $1"
  ((WARNINGS++))
}

echo "1. Checking file permissions..."
if [ -x tools/fleet-health-predictor.js ]; then
  check_pass "fleet-health-predictor.js is executable"
else
  check_fail "fleet-health-predictor.js is not executable"
fi

if [ -x bin/fleet-health-predictor-cron.sh ]; then
  check_pass "fleet-health-predictor-cron.sh is executable"
else
  check_fail "fleet-health-predictor-cron.sh is not executable"
fi

if [ -x tools/test-fleet-health-predictor.js ]; then
  check_pass "test-fleet-health-predictor.js is executable"
else
  check_warn "test-fleet-health-predictor.js is not executable"
fi

if [ -x examples/fleet-health-integration.js ]; then
  check_pass "fleet-health-integration.js is executable"
else
  check_warn "fleet-health-integration.js is not executable"
fi

echo ""
echo "2. Checking PostgreSQL connection..."
if psql -h aio-01 -p 5433 -U claude -d learning -c "SELECT 1" &>/dev/null; then
  check_pass "PostgreSQL connection successful"
else
  check_fail "PostgreSQL connection failed"
fi

echo ""
echo "3. Checking database table..."
if psql -h aio-01 -p 5433 -U claude -d learning -c "SELECT COUNT(*) FROM monitoring.health_predictions" &>/dev/null; then
  check_pass "Table monitoring.health_predictions exists"
  COUNT=$(psql -h aio-01 -p 5433 -U claude -d learning -t -c "SELECT COUNT(*) FROM monitoring.health_predictions" | tr -d ' ')
  echo "   Rows: $COUNT"
else
  check_fail "Table monitoring.health_predictions does not exist"
fi

echo ""
echo "4. Checking database views..."
if psql -h aio-01 -p 5433 -U claude -d learning -c "SELECT COUNT(*) FROM monitoring.latest_health_predictions" &>/dev/null; then
  check_pass "View monitoring.latest_health_predictions exists"
else
  check_fail "View monitoring.latest_health_predictions does not exist"
fi

if psql -h aio-01 -p 5433 -U claude -d learning -c "SELECT COUNT(*) FROM monitoring.degraded_servers" &>/dev/null; then
  check_pass "View monitoring.degraded_servers exists"
else
  check_fail "View monitoring.degraded_servers does not exist"
fi

echo ""
echo "5. Checking Prometheus connection..."
if curl -s http://pi-02:9090/api/v1/query?query=up &>/dev/null; then
  check_pass "Prometheus connection successful"
else
  check_warn "Prometheus connection failed (may need to start node_exporter)"
fi

echo ""
echo "6. Checking API keys..."
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  check_pass "ANTHROPIC_API_KEY environment variable set"
else
  if [ -f ~/.claude/credentials.json ]; then
    if grep -q "anthropic" ~/.claude/credentials.json; then
      check_pass "Anthropic API key found in credentials.json"
    else
      check_fail "Anthropic API key not found in credentials.json"
    fi
  else
    check_fail "ANTHROPIC_API_KEY not set and credentials.json not found"
  fi
fi

echo ""
echo "7. Checking Node.js version..."
NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -ge 18 ]; then
  check_pass "Node.js version $(node --version) >= 18"
else
  check_fail "Node.js version $(node --version) < 18 (required: >=18)"
fi

echo ""
echo "8. Checking fleet configuration..."
if [ -f ~/.claude/fleet.json ]; then
  check_pass "Fleet configuration exists (~/.claude/fleet.json)"
  WORKER_COUNT=$(jq '.machines | map(select(.role == "worker")) | length' ~/.claude/fleet.json)
  echo "   Workers configured: $WORKER_COUNT"
else
  check_warn "Fleet configuration not found (~/.claude/fleet.json)"
fi

echo ""
echo "9. Checking documentation..."
if [ -f docs/FLEET_HEALTH_PREDICTOR.md ]; then
  check_pass "Documentation exists (docs/FLEET_HEALTH_PREDICTOR.md)"
else
  check_warn "Documentation not found"
fi

echo ""
echo "10. Testing import statements..."
if node -e "import('./tools/fleet-health-predictor.js').then(() => console.log('OK'))" 2>&1 | grep -q "OK"; then
  check_pass "fleet-health-predictor.js can be imported"
else
  check_fail "fleet-health-predictor.js import failed"
fi

if node -e "import('./shared/fleet-utils.js').then(m => { if (m.getServerHealth && m.getPredictiveHealth) console.log('OK'); })" 2>&1 | grep -q "OK"; then
  check_pass "fleet-utils.js exports new functions"
else
  check_fail "fleet-utils.js new functions not found"
fi

echo ""
echo "============================================================"
echo "Verification Summary"
echo "============================================================"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
  echo -e "${GREEN}✅ All checks passed!${NC}"
  echo ""
  echo "Next steps:"
  echo "  1. Deploy cron to pi-02: ssh pi-02 'crontab -l; echo \"*/5 * * * * /home/claude/bin/fleet-health-predictor-cron.sh\"' | ssh pi-02 crontab -"
  echo "  2. Run initial prediction: node tools/fleet-health-predictor.js --all"
  echo "  3. Monitor logs: ssh pi-02 tail -f /var/log/fleet-health-predictor.log"
  exit 0
elif [ $ERRORS -eq 0 ]; then
  echo -e "${YELLOW}⚠️  Installation complete with $WARNINGS warning(s)${NC}"
  echo ""
  echo "Review warnings above. Installation is functional but may have optional issues."
  exit 0
else
  echo -e "${RED}❌ Installation incomplete: $ERRORS error(s), $WARNINGS warning(s)${NC}"
  echo ""
  echo "Fix errors above before proceeding."
  exit 1
fi
