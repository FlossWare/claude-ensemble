#!/bin/bash
#
# Test script for Grafana JSON Datasource API
# Tests all endpoints with pretty-printed JSON output
#

set -e

API_URL="${1:-http://localhost:3000}"
DELAY=0.5

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

function print_header() {
  echo -e "\n${BLUE}>>> $1${NC}"
}

function print_success() {
  echo -e "${GREEN}✓${NC}"
}

function print_error() {
  echo -e "${RED}✗ $1${NC}"
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
  echo "Warning: jq not found. Installing pretty-print will use 'cat'"
  JQ="cat"
else
  JQ="jq ."
fi

# Test health endpoint
print_header "GET /health"
response=$(curl -s -w "\n%{http_code}" "$API_URL/health")
status=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -1)

if [ "$status" = "200" ]; then
  print_success
  echo "$body" | eval $JQ
else
  print_error "HTTP $status"
  exit 1
fi
sleep $DELAY

# Test /metrics/lis
print_header "GET /metrics/lis"
response=$(curl -s -w "\n%{http_code}" "$API_URL/metrics/lis")
status=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -1)

if [ "$status" = "200" ]; then
  print_success
  echo "$body" | eval $JQ
else
  print_error "HTTP $status"
fi
sleep $DELAY

# Test /metrics/quality
print_header "GET /metrics/quality"
response=$(curl -s -w "\n%{http_code}" "$API_URL/metrics/quality")
status=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -1)

if [ "$status" = "200" ]; then
  print_success
  echo "$body" | eval $JQ
else
  print_error "HTTP $status"
fi
sleep $DELAY

# Test /metrics/cost
print_header "GET /metrics/cost"
response=$(curl -s -w "\n%{http_code}" "$API_URL/metrics/cost")
status=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -1)

if [ "$status" = "200" ]; then
  print_success
  echo "$body" | eval $JQ
else
  print_error "HTTP $status"
fi
sleep $DELAY

# Test /metrics/discoveries
print_header "GET /metrics/discoveries"
response=$(curl -s -w "\n%{http_code}" "$API_URL/metrics/discoveries")
status=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -1)

if [ "$status" = "200" ]; then
  print_success
  echo "$body" | eval $JQ
else
  print_error "HTTP $status"
fi
sleep $DELAY

# Test Grafana /search endpoint
print_header "POST /search"
response=$(curl -s -w "\n%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  "$API_URL/search")
status=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -1)

if [ "$status" = "200" ]; then
  print_success
  echo "$body" | eval $JQ
else
  print_error "HTTP $status"
fi
sleep $DELAY

# Test Grafana /query endpoint
print_header "POST /query with lis_score target"
response=$(curl -s -w "\n%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "targets": [
      {"target": "lis_score"},
      {"target": "quality_score"},
      {"target": "cost_daily"}
    ]
  }' \
  "$API_URL/query")
status=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -1)

if [ "$status" = "200" ]; then
  print_success
  echo "$body" | eval $JQ
else
  print_error "HTTP $status"
fi

print_header "All tests completed!"
