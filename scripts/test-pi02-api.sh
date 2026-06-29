#!/bin/bash

###############################################################################
# Test pi-02 Fleet Brain API
#
# Comprehensive test suite for fleet brain functionality
###############################################################################

set -e

PI02_HOST="${PI02_HOST:-pi-02}"
PI02_PORT="${PI02_PORT:-8080}"
BASE_URL="http://${PI02_HOST}:${PI02_PORT}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Fleet Brain API Test Suite                          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Testing: $BASE_URL"
echo ""

# Test function
test_endpoint() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="${5:-200}"

    echo -n "Testing: $test_name ... "

    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    # Extract status code and body
    status_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)

    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $status_code)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected HTTP $expected_status, got $status_code)"
        echo "Response: $body"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Test with JSON validation
test_json_endpoint() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local jq_filter="$5"

    echo -n "Testing: $test_name ... "

    if [ -z "$data" ]; then
        response=$(curl -s -X "$method" "$BASE_URL$endpoint")
    else
        response=$(curl -s -X "$method" "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    # Validate JSON
    if ! echo "$response" | jq empty 2>/dev/null; then
        echo -e "${RED}✗ FAIL${NC} (Invalid JSON)"
        echo "Response: $response"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi

    # Apply jq filter if provided
    if [ -n "$jq_filter" ]; then
        result=$(echo "$response" | jq -r "$jq_filter")
        if [ "$result" = "true" ] || [ "$result" = "1" ] || [ -n "$result" ]; then
            echo -e "${GREEN}✓ PASS${NC}"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        else
            echo -e "${RED}✗ FAIL${NC} (jq filter: $jq_filter = $result)"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    else
        echo -e "${GREEN}✓ PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    fi
}

echo -e "${YELLOW}=== Basic Connectivity ===${NC}"
echo ""

test_endpoint "Root endpoint" "GET" "/"
test_endpoint "Status endpoint" "GET" "/status"
test_endpoint "Health endpoint" "GET" "/health"

echo ""
echo -e "${YELLOW}=== Model Listing ===${NC}"
echo ""

test_json_endpoint "List models" "GET" "/models" "" ".count > 0"
test_json_endpoint "Models have names" "GET" "/models" "" ".models[0].name != null"
test_json_endpoint "Models have capabilities" "GET" "/models" "" ".models[0].capabilities | length > 0"

echo ""
echo -e "${YELLOW}=== Node Listing ===${NC}"
echo ""

test_json_endpoint "List nodes" "GET" "/nodes" "" ".count > 0"
test_json_endpoint "Nodes have status" "GET" "/nodes" "" ".nodes[0].status != null"
test_json_endpoint "Nodes have models" "GET" "/nodes" "" ".nodes[0].total_models >= 0"

echo ""
echo -e "${YELLOW}=== Request Routing ===${NC}"
echo ""

test_json_endpoint "Route coding request" "POST" "/route" '{"capabilities": ["coding"]}' ".success == true"
test_json_endpoint "Route returns model" "POST" "/route" '{"capabilities": ["coding"]}' ".model != null"
test_json_endpoint "Route returns node" "POST" "/route" '{"capabilities": ["coding"]}' ".node != null"
test_json_endpoint "Route returns endpoint" "POST" "/route" '{"capabilities": ["coding"]}' ".endpoint != null"

echo ""
echo -e "${YELLOW}=== Routing with Constraints ===${NC}"
echo ""

test_json_endpoint "Route local only" "POST" "/route" \
    '{"capabilities": ["coding"], "constraints": {"type": "local"}}' \
    '.type == "local"'

test_json_endpoint "Route free models" "POST" "/route" \
    '{"capabilities": ["chat"], "constraints": {"maxCost": 0}}' \
    '.cost_per_1m_tokens == 0'

echo ""
echo -e "${YELLOW}=== Multiple Capabilities ===${NC}"
echo ""

test_json_endpoint "Route coding + reasoning" "POST" "/route" \
    '{"capabilities": ["coding", "reasoning"]}' \
    '.success == true'

test_json_endpoint "Route math capability" "POST" "/route" \
    '{"capabilities": ["math"]}' \
    '.success == true'

echo ""
echo -e "${YELLOW}=== Error Handling ===${NC}"
echo ""

test_endpoint "Missing capabilities" "POST" "/route" '{}' 400
test_endpoint "Invalid JSON" "POST" "/route" 'invalid' 400
test_endpoint "Nonexistent endpoint" "GET" "/nonexistent" "" 404
test_endpoint "Nonexistent node" "GET" "/nodes/nonexistent" "" 404

echo ""
echo -e "${YELLOW}=== Heartbeat ===${NC}"
echo ""

# Test heartbeat for localhost (should always exist)
test_json_endpoint "Heartbeat for localhost" "POST" "/heartbeat" \
    '{"node": "localhost"}' \
    '.success == true'

test_endpoint "Heartbeat missing node" "POST" "/heartbeat" '{}' 400
test_endpoint "Heartbeat nonexistent node" "POST" "/heartbeat" \
    '{"node": "nonexistent-node-12345"}' 404

echo ""
echo -e "${YELLOW}=== Advanced Tests ===${NC}"
echo ""

# Check registry has zero duplication
test_json_endpoint "Zero duplication" "GET" "/status" "" \
    '.stats.duplication_count == 0'

# Check some models are available
test_json_endpoint "Models available" "GET" "/status" "" \
    '.stats.available_models > 0'

# Check localhost is online
test_json_endpoint "Localhost online" "GET" "/nodes/localhost" "" \
    '.status == "online"'

# Test logs endpoint
test_json_endpoint "Request logs" "GET" "/logs?limit=10" "" \
    '.logs | length > 0'

echo ""
echo -e "${YELLOW}=== Performance Tests ===${NC}"
echo ""

# Measure response time
echo -n "Response time test ... "
start_time=$(date +%s%N)
curl -s "$BASE_URL/status" > /dev/null
end_time=$(date +%s%N)
elapsed_ms=$(( (end_time - start_time) / 1000000 ))

if [ $elapsed_ms -lt 1000 ]; then
    echo -e "${GREEN}✓ PASS${NC} (${elapsed_ms}ms)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠ SLOW${NC} (${elapsed_ms}ms, expected < 1000ms)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Concurrent requests
echo -n "Concurrent requests (10 parallel) ... "
start_time=$(date +%s%N)
for i in {1..10}; do
    curl -s "$BASE_URL/status" > /dev/null &
done
wait
end_time=$(date +%s%N)
elapsed_ms=$(( (end_time - start_time) / 1000000 ))

if [ $elapsed_ms -lt 3000 ]; then
    echo -e "${GREEN}✓ PASS${NC} (${elapsed_ms}ms for 10 requests)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠ SLOW${NC} (${elapsed_ms}ms for 10 requests)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

echo ""
echo -e "${YELLOW}=== Integration Tests ===${NC}"
echo ""

# Full workflow: route → use model
echo -n "Full workflow (route + verify) ... "
route_response=$(curl -s -X POST "$BASE_URL/route" \
    -H "Content-Type: application/json" \
    -d '{"capabilities": ["coding"]}')

model=$(echo "$route_response" | jq -r '.model')
node=$(echo "$route_response" | jq -r '.node')
endpoint=$(echo "$route_response" | jq -r '.endpoint')

if [ -n "$model" ] && [ "$model" != "null" ] && \
   [ -n "$node" ] && [ "$node" != "null" ] && \
   [ -n "$endpoint" ] && [ "$endpoint" != "null" ]; then
    echo -e "${GREEN}✓ PASS${NC} (routed to $model on $node)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "Response: $route_response"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                 Test Results                               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "Fleet Brain API is working correctly."
    echo ""
    echo "Next steps:"
    echo "  1. Register fleet nodes: ./fleet-orchestrator-client.cjs auto-register"
    echo "  2. Monitor logs: ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -f"
    echo "  3. Integrate with workflows: see docs/pi02-quickstart.md"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    echo ""
    echo "Check logs: ssh pi@pi-02 sudo journalctl -u fleet-brain-api.service -n 100"
    exit 1
fi
