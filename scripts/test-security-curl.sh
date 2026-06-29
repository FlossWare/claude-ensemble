#!/bin/bash

# TEST: Security - curl without auth
# Purpose: Test API endpoints to verify authentication requirements
# This script tests that APIs properly reject unauthenticated requests

set -e

TEST_DIR="/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
RESULTS_FILE="$TEST_DIR/security-curl-results.json"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Initialize results
declare -A RESULTS
PASSED=0
FAILED=0

echo "========================================"
echo "Security Test: curl without auth"
echo "========================================"
echo ""

# Helper function to test endpoint
test_endpoint() {
  local name="$1"
  local method="$2"
  local endpoint="$3"
  local expected_auth_failure="$4"

  echo -n "Testing: $name ... "

  # Build curl command
  local cmd="curl -s -X $method -w '\n%{http_code}' '$endpoint' 2>&1"

  # Execute and capture response + status code
  local output=$(eval "$cmd")
  local http_code=$(echo "$output" | tail -n1)
  local body=$(echo "$output" | sed '$d')

  # Check if status code indicates auth failure (401, 403)
  if [[ "$expected_auth_failure" == "true" ]]; then
    if [[ "$http_code" == "401" ]] || [[ "$http_code" == "403" ]]; then
      echo -e "${GREEN}PASS${NC} (HTTP $http_code)"
      RESULTS["$name"]="PASS: HTTP $http_code (Auth required)"
      ((PASSED++))
    elif [[ "$http_code" == "404" ]]; then
      echo -e "${YELLOW}SKIP${NC} (HTTP $http_code - Endpoint not found)"
      RESULTS["$name"]="SKIP: HTTP $http_code (Endpoint unavailable)"
    else
      echo -e "${RED}FAIL${NC} (HTTP $http_code - Expected 401/403)"
      RESULTS["$name"]="FAIL: HTTP $http_code (No auth required!)"
      ((FAILED++))
    fi
  else
    if [[ "$http_code" == "200" ]] || [[ "$http_code" == "201" ]]; then
      echo -e "${GREEN}PASS${NC} (HTTP $http_code)"
      RESULTS["$name"]="PASS: HTTP $http_code"
      ((PASSED++))
    else
      echo -e "${YELLOW}INFO${NC} (HTTP $http_code)"
      RESULTS["$name"]="INFO: HTTP $http_code"
    fi
  fi
}

# Test 1: Agent Execute Endpoint (should require auth)
echo "=== Agent Execute Endpoints ==="
test_endpoint "GET /agent/execute" "GET" "http://localhost:3000/agent/execute" "true"
test_endpoint "POST /agent/execute" "POST" "http://localhost:3000/agent/execute" "true"

# Test 2: Learning API (should require auth)
echo ""
echo "=== Learning API Endpoints ==="
test_endpoint "GET /api/learning" "GET" "http://localhost:8000/api/learning" "true"
test_endpoint "POST /api/learning/record-feedback" "POST" "http://localhost:8000/api/learning/record-feedback" "true"

# Test 3: Fleet Dispatcher Endpoints
echo ""
echo "=== Fleet Dispatcher Endpoints ==="
test_endpoint "GET /fleet/status" "GET" "http://localhost:3001/fleet/status" "true"
test_endpoint "POST /fleet/dispatch" "POST" "http://localhost:3001/fleet/dispatch" "true"

# Test 4: SSH Command Generation (should require auth)
echo ""
echo "=== SSH Command Generation ==="
test_endpoint "GET /agent/execute-command" "GET" "http://localhost:3000/agent/execute-command" "true"

# Summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo -e "Passed:  ${GREEN}$PASSED${NC}"
echo -e "Failed:  ${RED}$FAILED${NC}"
echo -e "Total:   $((PASSED + FAILED))"
echo ""

# Save results to JSON
{
  echo "{"
  echo '  "test_name": "Security - curl without auth",'
  echo '  "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'", '
  echo '  "summary": {'
  echo "    \"passed\": $PASSED,"
  echo "    \"failed\": $FAILED,"
  echo "    \"total\": $((PASSED + FAILED))"
  echo "  },"
  echo '  "results": {'
  first=true
  for test_name in "${!RESULTS[@]}"; do
    if [[ "$first" == "false" ]]; then
      echo ","
    fi
    echo -n "    \"$test_name\": \"${RESULTS[$test_name]}\""
    first=false
  done
  echo ""
  echo "  }"
  echo "}"
} > "$RESULTS_FILE"

echo "Results saved to: $RESULTS_FILE"

# Exit with error if any tests failed
if [[ $FAILED -gt 0 ]]; then
  exit 1
fi

exit 0
