#!/bin/bash
#
# Grafana Dashboard Import Script
# Imports the Fleet Node Activity Dashboard and configures Prometheus datasource
#

set -e

# Configuration
GRAFANA_URL="${GRAFANA_URL:-http://aio-01:3000}"
GRAFANA_ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://aio-01:9091}"
DASHBOARD_UID="fleet-node-activity"
DASHBOARD_JSON_FILE="${1:-.}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Grafana Dashboard Import Tool ===${NC}"
echo "Grafana URL: $GRAFANA_URL"
echo "Prometheus URL: $PROMETHEUS_URL"
echo "Dashboard UID: $DASHBOARD_UID"
echo ""

# Function to print status
status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

# Function to print error
error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Function to print warning
warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if curl is available
if ! command -v curl &> /dev/null; then
    error "curl is required but not installed. Please install curl."
fi

# Test Grafana connectivity
status "Testing Grafana connectivity..."
if ! curl -s -f -o /dev/null -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" "$GRAFANA_URL/api/health"; then
    error "Cannot connect to Grafana at $GRAFANA_URL. Please verify the URL and credentials."
fi
status "Grafana is reachable"

# Test Prometheus connectivity
status "Testing Prometheus connectivity..."
if ! curl -s -f -o /dev/null "$PROMETHEUS_URL/-/healthy"; then
    warning "Cannot reach Prometheus at $PROMETHEUS_URL. Continuing with datasource creation anyway."
fi

# Step 1: Check if Prometheus datasource exists
status "Checking for existing Prometheus datasource..."
DS_RESPONSE=$(curl -s -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" \
    "$GRAFANA_URL/api/datasources/name/Prometheus")

if echo "$DS_RESPONSE" | grep -q '"id"'; then
    DS_ID=$(echo "$DS_RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
    status "Found existing Prometheus datasource with ID: $DS_ID"
else
    status "Creating new Prometheus datasource..."
    DS_RESPONSE=$(curl -s -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" \
        -X POST "$GRAFANA_URL/api/datasources" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"Prometheus\",
            \"type\": \"prometheus\",
            \"url\": \"$PROMETHEUS_URL\",
            \"access\": \"proxy\",
            \"isDefault\": true,
            \"jsonData\": {
                \"httpMethod\": \"GET\",
                \"customQueryParameters\": \"\"
            }
        }")

    if echo "$DS_RESPONSE" | grep -q '"id"'; then
        DS_ID=$(echo "$DS_RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
        status "Created Prometheus datasource with ID: $DS_ID"
    else
        error "Failed to create Prometheus datasource: $DS_RESPONSE"
    fi
fi

# Step 2: Set as default datasource
status "Setting Prometheus as default datasource..."
curl -s -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" \
    -X PUT "$GRAFANA_URL/api/datasources/$DS_ID" \
    -H "Content-Type: application/json" \
    -d "{
        \"id\": $DS_ID,
        \"orgId\": 1,
        \"name\": \"Prometheus\",
        \"type\": \"prometheus\",
        \"typeLogoUrl\": \"\",
        \"access\": \"proxy\",
        \"url\": \"$PROMETHEUS_URL\",
        \"password\": \"\",
        \"user\": \"\",
        \"database\": \"\",
        \"basicAuth\": false,
        \"isDefault\": true,
        \"jsonData\": {
            \"httpMethod\": \"GET\",
            \"customQueryParameters\": \"\"
        },
        \"readOnly\": false
    }" > /dev/null
status "Prometheus datasource set as default"

# Step 3: Read and prepare dashboard JSON
if [ -f "$DASHBOARD_JSON_FILE" ]; then
    status "Reading dashboard from file: $DASHBOARD_JSON_FILE"
    DASHBOARD_CONTENT=$(cat "$DASHBOARD_JSON_FILE")
else
    status "Expecting dashboard JSON to be piped or provided as argument"
    error "No dashboard JSON file found at: $DASHBOARD_JSON_FILE"
fi

# Step 4: Import dashboard
status "Importing Fleet Node Activity Dashboard..."
IMPORT_RESPONSE=$(curl -s -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" \
    -X POST "$GRAFANA_URL/api/dashboards/db" \
    -H "Content-Type: application/json" \
    -d "{
        \"dashboard\": $DASHBOARD_CONTENT,
        \"overwrite\": true
    }")

if echo "$IMPORT_RESPONSE" | grep -q '"id"'; then
    DASHBOARD_ID=$(echo "$IMPORT_RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
    DASHBOARD_UID=$(echo "$IMPORT_RESPONSE" | grep -o '"uid":"[^"]*"' | head -1 | cut -d'"' -f4)
    status "Dashboard imported successfully!"
    status "Dashboard ID: $DASHBOARD_ID"
    status "Dashboard UID: $DASHBOARD_UID"
else
    error "Failed to import dashboard: $IMPORT_RESPONSE"
fi

# Step 5: Create organization preference for default home dashboard
status "Setting Fleet Node Activity as home dashboard..."
curl -s -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" \
    -X PATCH "$GRAFANA_URL/api/org/preferences" \
    -H "Content-Type: application/json" \
    -d "{
        \"theme\": \"dark\",
        \"homeDashboardId\": $DASHBOARD_ID,
        \"homeDashboardUID\": \"$DASHBOARD_UID\",
        \"timezone\": \"browser\"
    }" > /dev/null
status "Home dashboard updated"

# Step 6: Output summary
echo ""
echo -e "${GREEN}=== Import Complete ===${NC}"
echo ""
echo "Dashboard Access URL:"
echo "  http://aio-01:3000/d/$DASHBOARD_UID/fleet-node-activity-dashboard"
echo ""
echo "Prometheus Datasource:"
echo "  Name: Prometheus"
echo "  URL: $PROMETHEUS_URL"
echo "  ID: $DS_ID"
echo "  Status: Default"
echo ""
echo "Next steps:"
echo "  1. Open Grafana: $GRAFANA_URL"
echo "  2. Navigate to Dashboards > General > Fleet Node Activity"
echo "  3. Verify all panels are loading data from Prometheus"
echo "  4. Adjust time ranges and variables as needed"
echo ""
echo "Troubleshooting:"
echo "  - If panels show 'No data': Check Prometheus is running at $PROMETHEUS_URL"
echo "  - Verify metrics are being exported: curl $PROMETHEUS_URL/api/v1/query?query=up"
echo "  - Check dashboard variables: Click gear icon, then 'Variables'"
echo ""
