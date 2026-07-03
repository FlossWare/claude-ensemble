#!/bin/bash
# Import Document Ingestion API Dashboard to Grafana

set -e

GRAFANA_URL="${GRAFANA_URL:-http://aio-01:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-admin}"
DASHBOARD_FILE="$(dirname "$0")/document-ingestion-dashboard.json"

echo "=== Importing Document Ingestion API Dashboard to Grafana ==="
echo "Grafana URL: $GRAFANA_URL"
echo ""

# Check if Grafana is reachable
if ! curl -sf "$GRAFANA_URL/api/health" > /dev/null; then
    echo "ERROR: Grafana is not reachable at $GRAFANA_URL"
    echo "Check if Grafana is running: sudo systemctl status grafana-server"
    exit 1
fi

echo "✓ Grafana is reachable"

# Import dashboard
echo "Importing dashboard from $DASHBOARD_FILE..."
RESPONSE=$(curl -sf -X POST \
    -H "Content-Type: application/json" \
    -u "$GRAFANA_USER:$GRAFANA_PASS" \
    -d @"$DASHBOARD_FILE" \
    "$GRAFANA_URL/api/dashboards/db")

if echo "$RESPONSE" | jq -e '.status == "success"' > /dev/null 2>&1; then
    DASHBOARD_UID=$(echo "$RESPONSE" | jq -r '.uid')
    DASHBOARD_URL="$GRAFANA_URL/d/$DASHBOARD_UID/document-ingestion-api-boss-demo"

    echo ""
    echo "✅ Dashboard imported successfully!"
    echo ""
    echo "📊 View dashboard at:"
    echo "   $DASHBOARD_URL"
    echo ""
    echo "🔑 Login credentials:"
    echo "   Username: $GRAFANA_USER"
    echo "   Password: $GRAFANA_PASS"
    echo ""
else
    echo ""
    echo "⚠️  Dashboard import response:"
    echo "$RESPONSE" | jq .
    echo ""
    echo "Note: Dashboard may already exist or credentials may be incorrect"
    echo "Try accessing: $GRAFANA_URL/dashboards"
fi
