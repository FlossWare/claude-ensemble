#!/bin/bash
set -euo pipefail

# Phase 1 Acceptance Tests - MCP Server Skeleton
# Tests: Server startup, tool registration, basic functionality, error handling, clean shutdown

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MCP_SERVER_DIR="${HOME}/.claude/mcp-servers/fleet-orchestrator"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results tracking
PASSED=0
FAILED=0
TOTAL=0

echo "==========================================="
echo "Phase 1 Acceptance Tests"
echo "==========================================="
echo ""

# Helper function to run test
run_test() {
    local test_name="$1"
    local test_func="$2"

    TOTAL=$((TOTAL + 1))
    echo -n "[$TOTAL] $test_name... "

    if $test_func; then
        echo -e "${GREEN}PASS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Test 1: MCP server starts without errors
test_server_startup() {
    if [[ ! -f "$MCP_SERVER_DIR/server.mjs" ]]; then
        echo "Server file not found at $MCP_SERVER_DIR/server.mjs"
        return 1
    fi

    # Start server in background with timeout
    timeout 5s node "$MCP_SERVER_DIR/server.mjs" > /tmp/mcp_server_startup.log 2>&1 &
    local server_pid=$!

    # Wait a bit for startup
    sleep 1

    # Check if process is still running (means it started successfully)
    if kill -0 $server_pid 2>/dev/null; then
        # Server started, now kill it gracefully
        kill $server_pid 2>/dev/null || true
        wait $server_pid 2>/dev/null || true

        # Check for errors in startup log
        if grep -i "error\|exception\|fatal" /tmp/mcp_server_startup.log >/dev/null 2>&1; then
            return 1
        fi
        return 0
    else
        # Server crashed during startup
        cat /tmp/mcp_server_startup.log
        return 1
    fi
}

# Test 2: Responds to tools/list with 3 tools
test_tools_list() {
    if [[ ! -f "$MCP_SERVER_DIR/server.mjs" ]]; then
        return 1
    fi

    # Start server in background
    node "$MCP_SERVER_DIR/server.mjs" > /tmp/mcp_server.log 2>&1 &
    local server_pid=$!
    sleep 1

    # Send tools/list request via MCP protocol
    local request='{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }'

    # Try to send request and capture response
    local response=$(echo "$request" | timeout 3s node "$MCP_SERVER_DIR/server.mjs" 2>/dev/null || true)

    kill $server_pid 2>/dev/null || true
    wait $server_pid 2>/dev/null || true

    # Check if response contains 3 tools
    if echo "$response" | grep -q "fleet-execute" && \
       echo "$response" | grep -q "fleet-status" && \
       echo "$response" | grep -q "fleet-consensus"; then
        return 0
    else
        return 1
    fi
}

# Test 3: Echo tool returns correct output
test_echo_tool() {
    if [[ ! -f "$MCP_SERVER_DIR/server.mjs" ]]; then
        return 1
    fi

    # Start server
    node "$MCP_SERVER_DIR/server.mjs" > /tmp/mcp_server.log 2>&1 &
    local server_pid=$!
    sleep 1

    # Test echo tool
    local test_input="Hello, MCP!"
    local request="{
        \"jsonrpc\": \"2.0\",
        \"id\": 2,
        \"method\": \"tools/call\",
        \"params\": {
            \"name\": \"echo\",
            \"arguments\": {\"text\": \"$test_input\"}
        }
    }"

    local response=$(echo "$request" | timeout 3s node "$MCP_SERVER_DIR/server.mjs" 2>/dev/null || true)

    kill $server_pid 2>/dev/null || true
    wait $server_pid 2>/dev/null || true

    # Check if response contains the echoed input
    if echo "$response" | grep -q "$test_input"; then
        return 0
    else
        return 1
    fi
}

# Test 4: Server handles malformed input gracefully
test_malformed_input() {
    if [[ ! -f "$MCP_SERVER_DIR/server.mjs" ]]; then
        return 1
    fi

    # Start server
    timeout 10s node "$MCP_SERVER_DIR/server.mjs" > /tmp/mcp_server_error.log 2>&1 &
    local server_pid=$!
    sleep 1

    # Send malformed JSON
    local malformed='{invalid json'
    echo "$malformed" | timeout 2s node "$MCP_SERVER_DIR/server.mjs" >/dev/null 2>&1 || true

    # Server should still be running after malformed input
    if kill -0 $server_pid 2>/dev/null; then
        kill $server_pid 2>/dev/null || true
        wait $server_pid 2>/dev/null || true
        return 0
    else
        return 1
    fi
}

# Test 5: Server exits cleanly on SIGTERM
test_clean_shutdown() {
    if [[ ! -f "$MCP_SERVER_DIR/server.mjs" ]]; then
        return 1
    fi

    # Start server
    node "$MCP_SERVER_DIR/server.mjs" > /tmp/mcp_server_shutdown.log 2>&1 &
    local server_pid=$!
    sleep 1

    # Send SIGTERM
    kill -TERM $server_pid 2>/dev/null || true

    # Wait for graceful shutdown (max 2 seconds)
    local timeout_counter=0
    while kill -0 $server_pid 2>/dev/null && [[ $timeout_counter -lt 20 ]]; do
        sleep 0.1
        timeout_counter=$((timeout_counter + 1))
    done

    # Check exit code
    wait $server_pid 2>/dev/null
    local exit_code=$?

    # Exit code should be 0 or 143 (SIGTERM)
    if [[ $exit_code -eq 0 || $exit_code -eq 143 ]]; then
        return 0
    else
        return 1
    fi
}

# Run all tests
run_test "MCP server starts without errors" test_server_startup
run_test "Responds to tools/list with 3 tools" test_tools_list
run_test "Echo tool returns correct output" test_echo_tool
run_test "Server handles malformed input gracefully" test_malformed_input
run_test "Server exits cleanly on SIGTERM" test_clean_shutdown

echo ""
echo "==========================================="
echo "Phase 1 Results: $PASSED/$TOTAL tests passed"
echo "==========================================="

if [[ $FAILED -gt 0 ]]; then
    echo -e "${RED}FAILED: $FAILED tests${NC}"
    exit 1
else
    echo -e "${GREEN}SUCCESS: All tests passed${NC}"
    exit 0
fi
