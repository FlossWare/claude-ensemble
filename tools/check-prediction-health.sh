#!/bin/bash
# Prediction System Health Check
# Monitors all ML predictors and reports status
# Usage: ./check-prediction-health.sh [--json]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LEARNING_DIR="$HOME/.claude/learning/predictors"

# Check if --json flag is passed
JSON_OUTPUT=false
if [[ "${1:-}" == "--json" ]]; then
    JSON_OUTPUT=true
fi

# Check predictor files exist
check_predictors() {
    local count=0
    local missing=0
    local total=0

    if [[ -d "$LEARNING_DIR" ]]; then
        total=$(find "$LEARNING_DIR" -name "*.pkl" -type f 2>/dev/null | wc -l)

        # Test if predictors are loadable
        for pkl in "$LEARNING_DIR"/*.pkl; do
            if [[ -f "$pkl" ]]; then
                ((count++))
                # Quick size check (corrupt files are usually 0 bytes)
                if [[ ! -s "$pkl" ]]; then
                    ((missing++))
                fi
            fi
        done
    fi

    echo "$count $missing $total"
}

# Check PostgreSQL connection
check_database() {
    if command -v psql &>/dev/null; then
        if psql -h aio-01 -p 5433 -U claude -d learning -c "SELECT 1" &>/dev/null; then
            echo "connected"
        else
            echo "disconnected"
        fi
    else
        echo "no_client"
    fi
}

# Check if fleet-health-predictor exists
check_fleet_predictor() {
    if [[ -f "$PROJECT_DIR/tools/fleet-health-predictor.js" ]]; then
        # Try to run it in test mode
        if node "$PROJECT_DIR/tools/test-fleet-health-predictor.js" &>/dev/null; then
            echo "ok"
        else
            echo "error"
        fi
    else
        echo "missing"
    fi
}

# Main health check
main() {
    read -r pred_count pred_missing pred_total <<< "$(check_predictors)"
    db_status=$(check_database)
    fleet_status=$(check_fleet_predictor)

    if $JSON_OUTPUT; then
        # JSON output
        cat <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "predictors": {
    "total": $pred_total,
    "loaded": $pred_count,
    "corrupt": $pred_missing,
    "status": "$([ $pred_missing -eq 0 ] && echo "healthy" || echo "degraded")"
  },
  "database": {
    "status": "$db_status"
  },
  "fleet_predictor": {
    "status": "$fleet_status"
  },
  "overall_health": "$([ $pred_missing -eq 0 ] && [ "$db_status" == "connected" ] && echo "healthy" || echo "degraded")"
}
EOF
    else
        # Human-readable output
        echo "=== Prediction System Health Check ==="
        echo "Timestamp: $(date)"
        echo ""
        echo "Predictors:"
        echo "  Total: $pred_total"
        echo "  Loaded: $pred_count"
        echo "  Corrupt: $pred_missing"
        echo "  Status: $([ $pred_missing -eq 0 ] && echo "✓ healthy" || echo "✗ degraded")"
        echo ""
        echo "Database:"
        echo "  Status: $db_status"
        echo ""
        echo "Fleet Predictor:"
        echo "  Status: $fleet_status"
        echo ""
        echo "Overall: $([ $pred_missing -eq 0 ] && [ "$db_status" == "connected" ] && echo "✓ HEALTHY" || echo "✗ DEGRADED")"
    fi
}

main
