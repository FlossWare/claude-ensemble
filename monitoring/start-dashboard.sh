#!/usr/bin/env bash

# Quick-start script for Autonomous Learning System Transparency Dashboard
# Usage: ./start-dashboard.sh [cli|grafana|both]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MODE="${1:-cli}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${CYAN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔍 Autonomous Learning System - Transparency Dashboard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${NC}"

# Check dependencies
check_dependencies() {
    echo -e "${BLUE}Checking dependencies...${NC}"

    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js not found. Please install Node.js 18+${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Node.js: $(node --version)${NC}"

    # Check npm packages
    if ! node -e "require('better-sqlite3')" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Installing missing dependencies...${NC}"
        cd "$PROJECT_ROOT"
        npm install better-sqlite3 blessed blessed-contrib
    fi
    echo -e "${GREEN}✅ Dependencies installed${NC}"

    # Check database
    DB_PATH="$HOME/.claude/learning/db/learning.db"
    if [ ! -f "$DB_PATH" ]; then
        echo -e "${YELLOW}⚠️  Learning database not found. Creating...${NC}"
        mkdir -p "$(dirname "$DB_PATH")"

        # Initialize database
        if [ -f "$HOME/.claude/learning/init-learning-db.sql" ]; then
            sqlite3 "$DB_PATH" < "$HOME/.claude/learning/init-learning-db.sql"
            echo -e "${GREEN}✅ Database initialized${NC}"
        else
            echo -e "${YELLOW}⚠️  init-learning-db.sql not found. Database will auto-initialize on first use.${NC}"
        fi
    else
        echo -e "${GREEN}✅ Database found: $DB_PATH${NC}"
    fi
}

start_cli() {
    echo -e "${CYAN}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🖥️  Starting CLI Dashboard"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${NC}"
    echo -e "${BLUE}Keyboard shortcuts:${NC}"
    echo "  ${YELLOW}r${NC}      - Refresh dashboard"
    echo "  ${YELLOW}h / ?${NC}  - Show help"
    echo "  ${YELLOW}q / ESC${NC} - Quit"
    echo ""
    echo -e "${GREEN}Starting in 3 seconds...${NC}"
    sleep 3

    cd "$PROJECT_ROOT"
    node "$SCRIPT_DIR/transparency-dashboard-cli.js"
}

start_grafana() {
    echo -e "${CYAN}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🌐 Starting Grafana Dashboard"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${NC}"

    # Check if Grafana is installed
    if ! command -v grafana-server &> /dev/null; then
        echo -e "${RED}❌ Grafana not found.${NC}"
        echo ""
        echo "Install Grafana:"
        echo "  macOS:  ${CYAN}brew install grafana${NC}"
        echo "  Linux:  ${CYAN}sudo apt install grafana${NC} (or see https://grafana.com/grafana/download)"
        echo ""
        exit 1
    fi

    # Check if Prometheus is installed
    if ! command -v prometheus &> /dev/null; then
        echo -e "${YELLOW}⚠️  Prometheus not found (optional, but recommended)${NC}"
        echo ""
        echo "Install Prometheus:"
        echo "  macOS:  ${CYAN}brew install prometheus${NC}"
        echo "  Linux:  ${CYAN}sudo apt install prometheus${NC}"
        echo ""
    fi

    echo -e "${GREEN}Grafana dashboard configuration:${NC}"
    echo "  Dashboard: $SCRIPT_DIR/autonomous-transparency-dashboard.json"
    echo ""
    echo -e "${BLUE}To import:${NC}"
    echo "  1. Open Grafana: ${CYAN}http://localhost:3000${NC}"
    echo "  2. Go to: Dashboards → Import"
    echo "  3. Upload: $SCRIPT_DIR/autonomous-transparency-dashboard.json"
    echo "  4. Configure data sources:"
    echo "     - ${YELLOW}Prometheus${NC}: http://localhost:9090 (system metrics)"
    echo "     - ${YELLOW}SQLite${NC}: ~/.claude/learning/db/learning.db (learning data)"
    echo ""
    echo -e "${YELLOW}Note: Grafana must be running. Start it with:${NC}"
    echo "  ${CYAN}grafana-server${NC}  (or as a service)"
    echo ""
}

show_status() {
    echo -e "${CYAN}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📊 Dashboard Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${NC}"

    # Check database stats
    DB_PATH="$HOME/.claude/learning/db/learning.db"
    if [ -f "$DB_PATH" ]; then
        EXEC_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM execution_log;" 2>/dev/null || echo "0")
        RECENT_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM execution_log WHERE timestamp > datetime('now', '-1 hour');" 2>/dev/null || echo "0")
        MODEL_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(DISTINCT model) FROM execution_log;" 2>/dev/null || echo "0")

        echo -e "${GREEN}Database Statistics:${NC}"
        echo "  Total executions: $EXEC_COUNT"
        echo "  Last hour: $RECENT_COUNT"
        echo "  Unique models: $MODEL_COUNT"
        echo ""
    else
        echo -e "${YELLOW}⚠️  Database not found. No data yet.${NC}"
        echo ""
    fi

    # Check Grafana
    if command -v grafana-server &> /dev/null; then
        if pgrep -x "grafana-server" > /dev/null; then
            echo -e "${GREEN}✅ Grafana: Running${NC}"
        else
            echo -e "${YELLOW}⚠️  Grafana: Installed but not running${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Grafana: Not installed${NC}"
    fi

    # Check Prometheus
    if command -v prometheus &> /dev/null; then
        if pgrep -x "prometheus" > /dev/null; then
            echo -e "${GREEN}✅ Prometheus: Running${NC}"
        else
            echo -e "${YELLOW}⚠️  Prometheus: Installed but not running${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Prometheus: Not installed${NC}"
    fi

    echo ""
}

show_help() {
    echo -e "${CYAN}Usage:${NC}"
    echo "  $0 [mode]"
    echo ""
    echo -e "${CYAN}Modes:${NC}"
    echo "  ${YELLOW}cli${NC}      - Start CLI dashboard (default)"
    echo "  ${YELLOW}grafana${NC}  - Show Grafana setup instructions"
    echo "  ${YELLOW}status${NC}   - Show dashboard status"
    echo "  ${YELLOW}help${NC}     - Show this help"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo "  $0              # Start CLI dashboard"
    echo "  $0 cli          # Start CLI dashboard"
    echo "  $0 grafana      # Grafana setup"
    echo "  $0 status       # Check status"
    echo ""
}

# Main
case "$MODE" in
    cli)
        check_dependencies
        start_cli
        ;;
    grafana)
        check_dependencies
        start_grafana
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown mode: $MODE${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
