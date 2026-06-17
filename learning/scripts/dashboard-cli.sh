#!/bin/bash
################################################################################
# Autonomous AI Learning System - CLI Dashboard
#
# Provides terminal-based dashboard for users without Grafana access.
# Queries learning.db and displays key metrics in formatted tables.
#
# Usage:
#   ./dashboard-cli.sh                    # Show all metrics
#   ./dashboard-cli.sh --lis              # Show LIS score only
#   ./dashboard-cli.sh --models           # Show model performance
#   ./dashboard-cli.sh --combos           # Show model combinations
#   ./dashboard-cli.sh --tuning           # Show parameter tuning
#   ./dashboard-cli.sh --cost             # Show cost analysis
#   ./dashboard-cli.sh --watch            # Refresh every 5 seconds
################################################################################

set -euo pipefail

DB_PATH="${DB_PATH:-$HOME/.claude/learning/db/learning.db}"
WATCH_INTERVAL=5

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Check if database exists
if [[ ! -f "$DB_PATH" ]]; then
    echo -e "${RED}Error: Database not found at $DB_PATH${NC}"
    exit 1
fi

# Check if sqlite3 is available
if ! command -v sqlite3 &> /dev/null; then
    echo -e "${RED}Error: sqlite3 command not found. Please install sqlite3.${NC}"
    exit 1
fi

# Helper: Print section header
print_header() {
    echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════${NC}\n"
}

# Helper: Color code quality scores
color_quality() {
    local score=$1
    if (( $(echo "$score >= 0.8" | bc -l) )); then
        echo -e "${GREEN}${score}${NC}"
    elif (( $(echo "$score >= 0.6" | bc -l) )); then
        echo -e "${YELLOW}${score}${NC}"
    else
        echo -e "${RED}${score}${NC}"
    fi
}

# 1. LIS Score (Learning Intelligence Score)
show_lis() {
    print_header "Learning Intelligence Score (LIS)"

    local lis_data=$(sqlite3 "$DB_PATH" <<EOF
SELECT
  ROUND(AVG(quality_score), 3) as avg_quality,
  ROUND(COUNT(CASE WHEN outcome = 'success' THEN 1 END) * 1.0 / COUNT(*), 3) as success_rate,
  ROUND(AVG(cost_usd), 4) as avg_cost,
  ROUND(AVG(duration_ms) / 1000.0, 2) as avg_duration_sec,
  COUNT(*) as total_executions
FROM execution_log
WHERE quality_score IS NOT NULL;
EOF
)

    IFS='|' read -r avg_quality success_rate avg_cost avg_duration total_executions <<< "$lis_data"

    # Calculate LIS components
    local quality_component=$(echo "$avg_quality * 40" | bc -l)
    local success_component=$(echo "$success_rate * 20" | bc -l)
    local cost_efficiency=$(echo "scale=2; if ($avg_cost > 0) 20 - ($avg_cost * 100) else 20" | bc -l)
    local speed_efficiency=$(echo "scale=2; if ($avg_duration > 0) 20 - $avg_duration else 20" | bc -l)

    # Clamp cost and speed efficiency to 0-20 range
    cost_efficiency=$(echo "if ($cost_efficiency < 0) 0 else if ($cost_efficiency > 20) 20 else $cost_efficiency" | bc -l)
    speed_efficiency=$(echo "if ($speed_efficiency < 0) 0 else if ($speed_efficiency > 20) 20 else $speed_efficiency" | bc -l)

    local lis_score=$(echo "$quality_component + $success_component + $cost_efficiency + $speed_efficiency" | bc -l)
    lis_score=$(printf "%.2f" "$lis_score")

    echo -e "  ${BOLD}Overall LIS Score:${NC}   $(color_quality $(echo "scale=3; $lis_score / 100" | bc -l)) / 100  (${lis_score}%)"
    echo ""
    echo -e "  ${BOLD}Components:${NC}"
    echo -e "    Quality (40%):       ${quality_component}  (avg quality: ${avg_quality})"
    echo -e "    Success (20%):       ${success_component}  (success rate: ${success_rate})"
    echo -e "    Cost Efficiency:     ${cost_efficiency}  (avg cost: \$${avg_cost})"
    echo -e "    Speed Efficiency:    ${speed_efficiency}  (avg duration: ${avg_duration}s)"
    echo ""
    echo -e "  ${BOLD}Total Executions:${NC}  ${total_executions}"
}

# 2. Model Performance
show_models() {
    print_header "Model Performance"

    echo -e "${BOLD}Model          Quality  Success%  Avg Cost   Avg Duration  Executions  Win Rate${NC}"
    echo "─────────────────────────────────────────────────────────────────────────────────"

    sqlite3 "$DB_PATH" <<EOF | while IFS='|' read -r model quality success_rate avg_cost avg_duration count win_rate; do
        printf "%-14s %7s  %7s%%  \$%-8s  %-12s  %-11s  %s%%\n" \
            "$model" \
            "$(color_quality $quality)" \
            "$success_rate" \
            "$avg_cost" \
            "${avg_duration}s" \
            "$count" \
            "$win_rate"
    done
SELECT
  model,
  ROUND(AVG(quality_score), 3) as quality,
  ROUND(COUNT(CASE WHEN outcome = 'success' THEN 1 END) * 100.0 / COUNT(*), 1) as success_rate,
  ROUND(AVG(cost_usd), 4) as avg_cost,
  ROUND(AVG(duration_ms) / 1000.0, 2) as avg_duration,
  COUNT(*) as count,
  ROUND(SUM(was_selected) * 100.0 / NULLIF(COUNT(CASE WHEN model_role = 'worker' THEN 1 END), 0), 1) as win_rate
FROM execution_log
GROUP BY model
ORDER BY quality DESC;
EOF
}

# 3. Model Combinations
show_combos() {
    print_header "Model Combinations (Top 10 by Quality)"

    echo -e "${BOLD}Task Type       Workers                    Arbiter   Quality  Synergy  Consensus  Usage${NC}"
    echo "───────────────────────────────────────────────────────────────────────────────────────"

    sqlite3 "$DB_PATH" <<EOF | while IFS='|' read -r task workers arbiter quality synergy consensus usage; do
        printf "%-15s %-25s  %-8s  %7s  %7s   %9s  %s\n" \
            "$task" \
            "$workers" \
            "$arbiter" \
            "$(color_quality $quality)" \
            "$synergy" \
            "$consensus" \
            "$usage"
    done
SELECT
  task_type,
  SUBSTR(worker_models, 1, 25) as workers,
  arbiter_model,
  ROUND(avg_quality, 3) as quality,
  ROUND(synergy_score, 3) as synergy,
  ROUND(avg_consensus, 3) as consensus,
  usage_count
FROM model_combinations
ORDER BY avg_quality DESC
LIMIT 10;
EOF
}

# 4. Parameter Tuning
show_tuning() {
    print_header "Optimal Parameter Tuning (Top 10)"

    echo -e "${BOLD}Model          Task Type        Temp   Top-P  Quality  Success%  Samples${NC}"
    echo "────────────────────────────────────────────────────────────────────────────"

    sqlite3 "$DB_PATH" <<EOF | while IFS='|' read -r model task temp top_p quality success_rate samples; do
        printf "%-14s %-15s  %5s  %5s  %7s  %7s%%  %s\n" \
            "$model" \
            "$task" \
            "$temp" \
            "$top_p" \
            "$(color_quality $quality)" \
            "$success_rate" \
            "$samples"
    done
SELECT
  model,
  task_type,
  COALESCE(json_extract(optimal_params, '$.temperature'), 'N/A') as temp,
  COALESCE(json_extract(optimal_params, '$.top_p'), 'N/A') as top_p,
  ROUND(avg_quality, 3) as quality,
  ROUND(success_rate * 100, 1) as success_rate,
  sample_count
FROM model_tuning
ORDER BY avg_quality DESC
LIMIT 10;
EOF
}

# 5. Cost Analysis
show_cost() {
    print_header "Cost Analysis"

    # Total cost by model
    echo -e "${BOLD}Total Cost by Model:${NC}"
    echo "─────────────────────────────────"
    sqlite3 "$DB_PATH" <<EOF | while IFS='|' read -r model total_cost avg_cost executions; do
        printf "%-14s  Total: \$%-8s  Avg: \$%-8s  (%s execs)\n" \
            "$model" "$total_cost" "$avg_cost" "$executions"
    done
SELECT
  model,
  ROUND(SUM(cost_usd), 4) as total_cost,
  ROUND(AVG(cost_usd), 6) as avg_cost,
  COUNT(*) as executions
FROM execution_log
GROUP BY model
ORDER BY total_cost DESC;
EOF

    echo ""

    # Cost by workflow
    echo -e "${BOLD}Cost by Workflow (Top 10):${NC}"
    echo "───────────────────────────────────────"
    sqlite3 "$DB_PATH" <<EOF | while IFS='|' read -r workflow total_cost avg_cost executions; do
        printf "%-25s  Total: \$%-8s  Avg: \$%-8s  (%s execs)\n" \
            "$workflow" "$total_cost" "$avg_cost" "$executions"
    done
SELECT
  COALESCE(workflow, 'unknown') as workflow,
  ROUND(SUM(cost_usd), 4) as total_cost,
  ROUND(AVG(cost_usd), 6) as avg_cost,
  COUNT(*) as executions
FROM execution_log
GROUP BY workflow
ORDER BY total_cost DESC
LIMIT 10;
EOF

    echo ""

    # Overall stats
    local overall=$(sqlite3 "$DB_PATH" "SELECT ROUND(SUM(cost_usd), 4), COUNT(*) FROM execution_log;")
    IFS='|' read -r total_cost total_execs <<< "$overall"
    echo -e "${BOLD}Overall:${NC}  Total Cost: \$${total_cost}  |  Total Executions: ${total_execs}"
}

# 6. Quick Summary
show_summary() {
    print_header "Quick Summary"

    local summary=$(sqlite3 "$DB_PATH" <<EOF
SELECT
  COUNT(DISTINCT model) as models,
  COUNT(DISTINCT workflow) as workflows,
  COUNT(DISTINCT task_type) as task_types,
  COUNT(*) as total_execs,
  ROUND(AVG(quality_score), 3) as avg_quality,
  ROUND(SUM(cost_usd), 4) as total_cost
FROM execution_log;
EOF
)

    IFS='|' read -r models workflows task_types total_execs avg_quality total_cost <<< "$summary"

    echo -e "  ${BOLD}Active Models:${NC}       $models"
    echo -e "  ${BOLD}Workflows:${NC}           $workflows"
    echo -e "  ${BOLD}Task Types:${NC}          $task_types"
    echo -e "  ${BOLD}Total Executions:${NC}    $total_execs"
    echo -e "  ${BOLD}Avg Quality:${NC}         $(color_quality $avg_quality)"
    echo -e "  ${BOLD}Total Cost:${NC}          \$${total_cost}"
}

# Main display function
display_dashboard() {
    clear
    echo -e "${BOLD}${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║        Autonomous AI Learning System - CLI Dashboard                     ║"
    echo "║        Database: ${DB_PATH##*/}                                          ║"
    echo "║        $(date '+%Y-%m-%d %H:%M:%S')                                                    ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    case "${1:-all}" in
        --lis)
            show_lis
            ;;
        --models)
            show_models
            ;;
        --combos)
            show_combos
            ;;
        --tuning)
            show_tuning
            ;;
        --cost)
            show_cost
            ;;
        --summary)
            show_summary
            ;;
        all|--all)
            show_summary
            show_lis
            show_models
            show_combos
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac

    echo ""
}

# Watch mode
if [[ "${1:-}" == "--watch" ]]; then
    shift
    while true; do
        display_dashboard "$@"
        echo -e "${CYAN}Refreshing in ${WATCH_INTERVAL}s... (Ctrl+C to exit)${NC}"
        sleep "$WATCH_INTERVAL"
    done
else
    display_dashboard "$@"
fi
