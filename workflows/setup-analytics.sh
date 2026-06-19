#!/bin/bash
# Setup Deep Research Analytics
# Initializes PostgreSQL views, materialized views, and Grafana dashboard

set -e

DB_HOST="laptop-01"
DB_USER="sfloess"
DB_NAME="learning"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "Deep Research Analytics Setup"
echo "=========================================="
echo ""
echo "Database: $DB_HOST:5432/$DB_NAME"
echo "User: $DB_USER"
echo ""

# Check PostgreSQL connectivity
echo "Step 1: Testing database connection..."
if ! psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo "ERROR: Cannot connect to PostgreSQL"
    echo "Check that PostgreSQL is running and credentials are correct"
    exit 1
fi
echo "  ✓ Database connection successful"
echo ""

# Initialize analytics views
echo "Step 2: Creating analytics views and materialized views..."
if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$SCRIPT_DIR/analytics.sql" > /dev/null 2>&1; then
    echo "  ✓ Analytics views created successfully"
else
    echo "  ✗ Failed to create analytics views"
    echo "  Check $SCRIPT_DIR/analytics.sql for errors"
    exit 1
fi
echo ""

# Refresh materialized views
echo "Step 3: Refreshing materialized views..."
refresh_output=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT * FROM monitoring.refresh_all_views();" 2>&1)
if [ $? -eq 0 ]; then
    echo "$refresh_output" | while read -r line; do
        if [[ "$line" =~ OK ]]; then
            echo "  ✓ $line"
        elif [[ "$line" =~ FAILED ]]; then
            echo "  ✗ $line"
        fi
    done
else
    echo "  ⚠ Warning: Could not refresh materialized views (may be empty)"
    echo "  This is normal if no workflow data exists yet"
fi
echo ""

# Count existing data
echo "Step 4: Checking existing data..."
exec_count=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM monitoring.execution_summary" 2>/dev/null || echo "0")
exec_count=$(echo "$exec_count" | tr -d ' ')

if [ "$exec_count" -gt 0 ]; then
    echo "  ✓ Found $exec_count execution records"

    workflow_count=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(DISTINCT workflow) FROM monitoring.execution_summary" 2>/dev/null || echo "0")
    workflow_count=$(echo "$workflow_count" | tr -d ' ')
    echo "  ✓ Found $workflow_count distinct workflows"

    model_count=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(DISTINCT model) FROM monitoring.execution_summary" 2>/dev/null || echo "0")
    model_count=$(echo "$model_count" | tr -d ' ')
    echo "  ✓ Found $model_count distinct models"
else
    echo "  ⚠ No execution data found yet"
    echo "  Run a workflow (e.g., deep-research.mjs) to populate analytics"
fi
echo ""

# Verify views are accessible
echo "Step 5: Verifying views..."
view_count=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT COUNT(*)
    FROM pg_views
    WHERE schemaname IN ('monitoring', 'learning')
    AND viewname LIKE '%_performance%'
       OR viewname LIKE '%_quality%'
       OR viewname LIKE '%_cost%'
       OR viewname LIKE 'grafana_%'
" 2>/dev/null || echo "0")
view_count=$(echo "$view_count" | tr -d ' ')

matview_count=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT COUNT(*)
    FROM pg_matviews
    WHERE schemaname IN ('monitoring', 'learning')
" 2>/dev/null || echo "0")
matview_count=$(echo "$matview_count" | tr -d ' ')

echo "  ✓ Created $view_count regular views"
echo "  ✓ Created $matview_count materialized views"
echo ""

# Test sample queries
echo "Step 6: Testing sample queries..."

test_query() {
    local query_name="$1"
    local query="$2"

    if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "$query" > /dev/null 2>&1; then
        echo "  ✓ $query_name"
        return 0
    else
        echo "  ✗ $query_name"
        return 1
    fi
}

test_query "Top model combinations" "SELECT * FROM monitoring.top_model_combinations LIMIT 1"
test_query "Model champions" "SELECT * FROM monitoring.model_champions LIMIT 1"
test_query "Cost-quality frontier" "SELECT * FROM monitoring.cost_quality_frontier LIMIT 1"
test_query "Workflow cost-quality" "SELECT * FROM monitoring.workflow_cost_quality LIMIT 1"
test_query "Recent executions" "SELECT * FROM monitoring.recent_executions LIMIT 1"
test_query "Grafana timeseries" "SELECT * FROM monitoring.grafana_model_timeseries LIMIT 1"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Analytics infrastructure is ready to use."
echo ""
echo "Next steps:"
echo ""
echo "1. Run validation tests:"
echo "   bash $SCRIPT_DIR/test-analytics.sh"
echo ""
echo "2. Query analytics from command line:"
echo "   psql -h $DB_HOST -U $DB_USER -d $DB_NAME"
echo "   > SELECT * FROM monitoring.top_model_combinations;"
echo ""
echo "3. Import Grafana dashboard:"
echo "   - Navigate to http://pi-02:3000"
echo "   - Dashboards → Import"
echo "   - Upload: $SCRIPT_DIR/grafana-dashboard.json"
echo "   - Select datasource: laptop-01-learning"
echo ""
echo "4. Generate sample data (if needed):"
echo "   node workflows/deep-research.mjs \"test query\""
echo ""
echo "5. Read documentation:"
echo "   cat $SCRIPT_DIR/ANALYTICS.md"
echo ""
echo "Analytics views will auto-refresh after each workflow execution."
echo "For manual refresh: psql -c 'SELECT * FROM monitoring.refresh_all_views()'"
echo ""
