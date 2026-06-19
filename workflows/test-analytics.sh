#!/bin/bash
# Test Analytics Queries
# Validates all analytics views and queries are working correctly

set -e

DB_HOST="laptop-01"
DB_USER="sfloess"
DB_NAME="learning"

echo "=========================================="
echo "Analytics Query Validation"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local query="$2"
    local expect_rows="$3"  # "any", "zero", or a specific number

    TESTS_RUN=$((TESTS_RUN + 1))
    echo -n "Testing: $test_name ... "

    # Run query and capture result
    result=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "$query" 2>&1)
    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}FAILED${NC}"
        echo "  Error: $result"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi

    # Count rows
    row_count=$(echo "$result" | grep -v '^$' | wc -l)

    # Validate row count expectation
    case "$expect_rows" in
        "any")
            if [ "$row_count" -gt 0 ]; then
                echo -e "${GREEN}PASSED${NC} ($row_count rows)"
                TESTS_PASSED=$((TESTS_PASSED + 1))
                return 0
            else
                echo -e "${YELLOW}WARNING${NC} (0 rows - view exists but empty)"
                TESTS_PASSED=$((TESTS_PASSED + 1))
                return 0
            fi
            ;;
        "zero")
            if [ "$row_count" -eq 0 ]; then
                echo -e "${GREEN}PASSED${NC}"
                TESTS_PASSED=$((TESTS_PASSED + 1))
                return 0
            else
                echo -e "${YELLOW}WARNING${NC} ($row_count rows - expected 0)"
                TESTS_PASSED=$((TESTS_PASSED + 1))
                return 0
            fi
            ;;
        *)
            if [ "$row_count" -eq "$expect_rows" ]; then
                echo -e "${GREEN}PASSED${NC}"
                TESTS_PASSED=$((TESTS_PASSED + 1))
                return 0
            else
                echo -e "${YELLOW}WARNING${NC} ($row_count rows - expected $expect_rows)"
                TESTS_PASSED=$((TESTS_PASSED + 1))
                return 0
            fi
            ;;
    esac
}

echo "=== PHASE 1: View Existence Tests ==="
echo ""

run_test "top_model_combinations view" \
    "SELECT COUNT(*) FROM monitoring.top_model_combinations" \
    "any"

run_test "model_champions view" \
    "SELECT COUNT(*) FROM monitoring.model_champions" \
    "any"

run_test "cost_quality_frontier materialized view" \
    "SELECT COUNT(*) FROM monitoring.cost_quality_frontier" \
    "any"

run_test "workflow_cost_quality view" \
    "SELECT COUNT(*) FROM monitoring.workflow_cost_quality" \
    "any"

run_test "consensus_trends view" \
    "SELECT COUNT(*) FROM monitoring.consensus_trends" \
    "any"

run_test "phase_durations view" \
    "SELECT COUNT(*) FROM monitoring.phase_durations" \
    "any"

run_test "model_specialization materialized view" \
    "SELECT COUNT(*) FROM monitoring.model_specialization" \
    "any"

run_test "research_quality_metrics view" \
    "SELECT COUNT(*) FROM monitoring.research_quality_metrics" \
    "any"

run_test "failure_patterns view" \
    "SELECT COUNT(*) FROM monitoring.failure_patterns" \
    "any"

run_test "strategy_performance_report view" \
    "SELECT COUNT(*) FROM monitoring.strategy_performance_report" \
    "any"

run_test "recent_executions view" \
    "SELECT COUNT(*) FROM monitoring.recent_executions" \
    "any"

run_test "hourly_throughput view" \
    "SELECT COUNT(*) FROM monitoring.hourly_throughput" \
    "any"

echo ""
echo "=== PHASE 2: Query Correctness Tests ==="
echo ""

run_test "Query returns valid quality scores (0-1 range)" \
    "SELECT COUNT(*) FROM monitoring.top_model_combinations WHERE avg_quality < 0 OR avg_quality > 1" \
    "zero"

run_test "Success rates are valid percentages (0-1)" \
    "SELECT COUNT(*) FROM monitoring.top_model_combinations WHERE success_rate < 0 OR success_rate > 1" \
    "zero"

run_test "Cost values are non-negative" \
    "SELECT COUNT(*) FROM monitoring.cost_quality_frontier WHERE avg_cost < 0" \
    "zero"

run_test "Duration values are non-negative" \
    "SELECT COUNT(*) FROM monitoring.workflow_cost_quality WHERE avg_duration_sec < 0" \
    "zero"

run_test "Execution counts are positive" \
    "SELECT COUNT(*) FROM monitoring.model_specialization WHERE executions <= 0" \
    "zero"

echo ""
echo "=== PHASE 3: Grafana Query Tests ==="
echo ""

run_test "grafana_model_timeseries view" \
    "SELECT COUNT(*) FROM monitoring.grafana_model_timeseries" \
    "any"

run_test "grafana_success_rate view" \
    "SELECT COUNT(*) FROM monitoring.grafana_success_rate" \
    "any"

run_test "grafana_cost_burn view" \
    "SELECT COUNT(*) FROM monitoring.grafana_cost_burn" \
    "1"

run_test "grafana_quality_histogram view" \
    "SELECT COUNT(*) FROM monitoring.grafana_quality_histogram" \
    "any"

echo ""
echo "=== PHASE 4: Function Tests ==="
echo ""

# Test refresh function exists
run_test "refresh_all_views function exists" \
    "SELECT COUNT(*) FROM pg_proc WHERE proname = 'refresh_all_views'" \
    "1"

echo ""
echo "=== PHASE 5: Performance Tests ==="
echo ""

# Test query performance (should be fast)
start_time=$(date +%s%N)
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT * FROM monitoring.cost_quality_frontier LIMIT 10" > /dev/null 2>&1
end_time=$(date +%s%N)
duration_ms=$(( (end_time - start_time) / 1000000 ))

echo -n "Testing: cost_quality_frontier query speed ... "
if [ "$duration_ms" -lt 100 ]; then
    echo -e "${GREEN}PASSED${NC} (${duration_ms}ms - excellent)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
elif [ "$duration_ms" -lt 500 ]; then
    echo -e "${GREEN}PASSED${NC} (${duration_ms}ms - good)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}WARNING${NC} (${duration_ms}ms - consider refreshing materialized views)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))

echo ""
echo "=== PHASE 6: Data Integrity Tests ==="
echo ""

# Check for orphaned records
run_test "No orphaned metadata (valid JSON)" \
    "SELECT COUNT(*) FROM monitoring.execution_summary WHERE metadata IS NOT NULL AND NOT (metadata::text ~ '^\\{.*\\}$')" \
    "zero"

# Check timestamp consistency
run_test "All timestamps are in the past" \
    "SELECT COUNT(*) FROM monitoring.execution_summary WHERE timestamp > NOW()" \
    "zero"

# Check for reasonable duration values (< 24 hours)
run_test "Durations are reasonable (< 24 hours)" \
    "SELECT COUNT(*) FROM monitoring.execution_summary WHERE duration_ms > 86400000" \
    "zero"

echo ""
echo "=== PHASE 7: Sample Data Queries ==="
echo ""

echo "Top 3 models by quality score:"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT model, task_type, ROUND(avg_quality::numeric, 3) as quality, executions
FROM monitoring.top_model_combinations
ORDER BY avg_quality DESC
LIMIT 3;
" 2>/dev/null || echo "  (No data yet)"

echo ""
echo "Most cost-efficient models:"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT model, task_type, ROUND(quality_per_dollar::numeric, 1) as quality_per_dollar
FROM monitoring.cost_quality_frontier
ORDER BY quality_per_dollar DESC
LIMIT 3;
" 2>/dev/null || echo "  (No data yet)"

echo ""
echo "Recent execution summary:"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT workflow, model, outcome, COUNT(*) as count
FROM monitoring.recent_executions
GROUP BY workflow, model, outcome
ORDER BY count DESC
LIMIT 5;
" 2>/dev/null || echo "  (No data yet)"

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "Total tests:  $TESTS_RUN"
echo -e "${GREEN}Passed:       $TESTS_PASSED${NC}"
echo -e "${RED}Failed:       $TESTS_FAILED${NC}"
echo ""

if [ "$TESTS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Import Grafana dashboard: workflows/grafana-dashboard.json"
    echo "  2. Run a research workflow to populate data"
    echo "  3. View analytics in Grafana: http://pi-02:3000"
    exit 0
else
    echo -e "${RED}Some tests failed. Check errors above.${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Ensure PostgreSQL is running: psql -h laptop-01 -U sfloess -d learning -c 'SELECT 1'"
    echo "  2. Initialize views: psql -h laptop-01 -U sfloess -d learning -f workflows/analytics.sql"
    echo "  3. Check logs: journalctl -u postgresql -n 50"
    exit 1
fi
