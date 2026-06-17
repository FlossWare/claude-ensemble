#!/bin/bash
#
# Quick Start Script for Grafana JSON Datasource API
# Usage: ./quickstart.sh [option]
#

set -e

API_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=3000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function print_header() {
  echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

function print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

function print_error() {
  echo -e "${RED}✗ $1${NC}"
  exit 1
}

function print_info() {
  echo -e "${YELLOW}• $1${NC}"
}

function check_node() {
  print_header "Checking Node.js"

  if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js 14+ from https://nodejs.org/"
  fi

  local node_version=$(node --version)
  print_success "Node.js $node_version found"
}

function check_db() {
  print_header "Checking Database"

  if [ ! -f "$API_DIR/db/learning.db" ]; then
    print_error "Database not found at $API_DIR/db/learning.db"
  fi

  local db_size=$(du -h "$API_DIR/db/learning.db" | cut -f1)
  print_success "Database found ($db_size)"
}

function install_deps() {
  print_header "Installing Dependencies"

  if [ ! -d "$API_DIR/node_modules" ]; then
    if [ -f "$API_DIR/package.json" ]; then
      cd "$API_DIR"
      npm install
      print_success "Dependencies installed"
    else
      print_error "package.json not found"
    fi
  else
    print_success "Dependencies already installed"
  fi
}

function start_server() {
  print_header "Starting Grafana API Server"

  print_info "Starting on http://localhost:$PORT"
  cd "$API_DIR"
  node grafana-api.js
}

function test_api() {
  print_header "Testing API Endpoints"

  # Give server time to start
  sleep 2

  print_info "Testing /health endpoint..."
  if curl -s http://localhost:$PORT/health | grep -q '"status"'; then
    print_success "Health check passed"
  else
    print_error "Health check failed"
  fi

  print_info "Testing /metrics/lis endpoint..."
  if curl -s http://localhost:$PORT/metrics/lis | grep -q '"current"'; then
    print_success "LIS metrics endpoint working"
  else
    print_error "LIS metrics endpoint failed"
  fi

  print_info "Testing /metrics/cost endpoint..."
  if curl -s http://localhost:$PORT/metrics/cost | grep -q '"daily"'; then
    print_success "Cost metrics endpoint working"
  else
    print_error "Cost metrics endpoint failed"
  fi

  print_success "All endpoints responding"
}

function show_grafana_setup() {
  print_header "Grafana Configuration"

  echo "1. Open Grafana: http://localhost:3000 (or your Grafana URL)"
  echo ""
  echo "2. Go to Configuration > Data Sources"
  echo ""
  echo "3. Click 'Add data source' and select 'JSON API'"
  echo ""
  echo "4. Set the following:"
  echo "   - Name: AI Learning Metrics"
  echo "   - URL: http://localhost:$PORT"
  echo ""
  echo "5. Click 'Save & Test'"
  echo ""
  echo "6. You should see: 'HTTP 200 response from http://localhost:$PORT/health'"
  echo ""
  echo "7. Create panels using these targets:"
  echo "   - lis_score"
  echo "   - lis_trend"
  echo "   - quality_score"
  echo "   - quality_by_model"
  echo "   - cost_daily"
  echo "   - cost_savings"
  echo "   - discoveries"
  echo "   - model_tuning"
  echo "   - model_combinations"
}

function show_docker_setup() {
  print_header "Docker Setup"

  echo "To run with Docker:"
  echo ""
  echo "  docker-compose up -d"
  echo ""
  echo "Services:"
  echo "  - grafana-learning-api: http://localhost:3000"
  echo "  - grafana: http://localhost:3001"
  echo ""
}

function show_help() {
  echo "Grafana AI Learning System API - Quick Start"
  echo ""
  echo "Usage: $0 [option]"
  echo ""
  echo "Options:"
  echo "  start         Start the API server"
  echo "  test          Run API endpoint tests"
  echo "  install       Install dependencies only"
  echo "  docker        Show Docker setup instructions"
  echo "  grafana       Show Grafana configuration instructions"
  echo "  full          Run all checks and start server"
  echo "  help          Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0 start              # Start the server"
  echo "  $0 full               # Check everything and start"
  echo "  $0 test               # Test all endpoints (requires running server)"
}

# Main logic
case "${1:-help}" in
  start)
    check_node
    check_db
    install_deps
    start_server
    ;;
  test)
    print_header "Running API Tests"
    test_api
    print_success "All tests passed!"
    ;;
  install)
    check_node
    install_deps
    ;;
  docker)
    show_docker_setup
    ;;
  grafana)
    show_grafana_setup
    ;;
  full)
    check_node
    check_db
    install_deps
    print_header "Ready to Start"
    print_success "All checks passed!"
    echo ""
    echo "To start the server, run:"
    echo "  npm start"
    echo ""
    echo "Or to start in background:"
    echo "  nohup npm start > grafana-api.log 2>&1 &"
    echo ""
    show_grafana_setup
    ;;
  help)
    show_help
    ;;
  *)
    print_error "Unknown option: $1"
    show_help
    ;;
esac
