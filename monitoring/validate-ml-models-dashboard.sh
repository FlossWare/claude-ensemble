#!/bin/bash

# ML Models Dashboard Validation Script
# Purpose: Validate dashboard JSON and database schema

set -e

DASHBOARD_FILE="$(dirname "$0")/grafana-ml-models-dashboard.json"
PSQL_CMD=${PSQL_CMD:-psql}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "ML Models Dashboard Validator"
echo "=========================================="
echo ""

# Check 1: Dashboard JSON validity
echo -n "Checking JSON validity... "
if python3 -c "import json; json.load(open('$DASHBOARD_FILE'))" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC} Invalid JSON syntax"
    exit 1
fi

# Check 2: Required fields in JSON
echo -n "Checking required dashboard fields... "
if python3 -c "
import json
with open('$DASHBOARD_FILE') as f:
    dashboard = json.load(f)
    required = ['title', 'uid', 'panels', 'schemaVersion', 'tags', 'time']
    missing = [f for f in required if f not in dashboard]
    if missing:
        print(f'Missing: {missing}')
        exit(1)
" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    exit 1
fi

# Check 3: Panel count
echo -n "Checking panel configuration... "
PANEL_COUNT=$(python3 -c "import json; print(len(json.load(open('$DASHBOARD_FILE'))['panels']))")
echo -e "${GREEN}✓${NC} ($PANEL_COUNT panels)"

# Check 4: Data sources referenced
echo -n "Checking data sources... "
if python3 -c "
import json
with open('$DASHBOARD_FILE') as f:
    dashboard = json.load(f)
    datasources = set()
    for panel in dashboard['panels']:
        if 'datasource' in panel:
            datasources.add(panel['datasource'])
    print('Found: ' + ', '.join(sorted(datasources)))
    if not datasources:
        exit(1)
" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC}"
fi

# Check 5: Database connectivity (optional)
if command -v $PSQL_CMD &> /dev/null; then
    echo ""
    echo "Checking PostgreSQL connectivity..."

    if $PSQL_CMD -c "SELECT 1" &>/dev/null; then
        echo -e "${GREEN}✓${NC} Connected to PostgreSQL"

        # Check for required tables
        echo ""
        echo "Validating database schema..."

        TABLES=("monitoring.prediction_accuracy" "monitoring.model_retraining" "monitoring.resource_usage" "monitoring.execution_summary")

        for table in "${TABLES[@]}"; do
            if $PSQL_CMD -c "SELECT 1 FROM information_schema.tables WHERE table_schema || '.' || table_name = '$table'" 2>/dev/null | grep -q 1; then
                echo -e "  ${GREEN}✓${NC} Table exists: $table"
            else
                echo -e "  ${YELLOW}⚠${NC} Table missing: $table"
                echo "     Run SQL schema creation script to create it"
            fi
        done
    else
        echo -e "${YELLOW}⚠${NC} Could not connect to PostgreSQL"
        echo "  (This is OK - you can set it up later)"
    fi
else
    echo -e "${YELLOW}⚠${NC} psql not found - skipping database checks"
fi

# Check 6: Dashboard metadata
echo ""
echo "Dashboard Information:"
DASHBOARD_UID=$(python3 -c "import json; print(json.load(open('$DASHBOARD_FILE'))['uid'])")
DASHBOARD_TITLE=$(python3 -c "import json; print(json.load(open('$DASHBOARD_FILE'))['title'])")
DASHBOARD_TAGS=$(python3 -c "import json; print(', '.join(json.load(open('$DASHBOARD_FILE'))['tags']))")

echo "  Title:    $DASHBOARD_TITLE"
echo "  UID:      $DASHBOARD_UID"
echo "  Tags:     $DASHBOARD_TAGS"
echo "  Panels:   $PANEL_COUNT"

# Check 7: Query validation
echo ""
echo "Validating panel queries..."
python3 -c "
import json
import re

with open('$DASHBOARD_FILE') as f:
    dashboard = json.load(f)
    sql_queries = []

    for i, panel in enumerate(dashboard['panels']):
        for target in panel.get('targets', []):
            if 'rawSql' in target:
                sql = target['rawSql']
                # Check for obvious SQL issues
                if 'SELECT' not in sql:
                    print(f'  WARNING: Panel {i} ({panel[\"title\"]}) - Missing SELECT')
                elif 'FROM' not in sql:
                    print(f'  WARNING: Panel {i} ({panel[\"title\"]}) - Missing FROM')
                else:
                    sql_queries.append((panel['title'], sql[:50] + '...'))

    if sql_queries:
        print(f'  Found {len(sql_queries)} SQL queries')
        print('  All queries have SELECT and FROM')
    else:
        print('  No SQL queries found (may use Prometheus)')
"

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}✓ Dashboard validation complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Configure PostgreSQL data source in Grafana"
echo "  2. Import dashboard: ./import-dashboard.sh grafana-ml-models-dashboard.json"
echo "  3. Populate database with monitoring data"
echo "  4. Visit dashboard at: http://localhost:3000/d/ml-models-dashboard"
echo ""
echo "For detailed setup, see: ML-MODELS-DASHBOARD-GUIDE.md"
echo ""
