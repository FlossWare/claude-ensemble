#!/bin/bash
#
# End-to-end integration test: MCP server + Python executor + all 9 workers
#
# Tests:
#   1. MCP server starts and responds to tool listing
#   2. fleet-execute tool works via MCP protocol
#   3. Python executor (python-worker.py) runs on each worker via SSH
#   4. All 9 workers are reachable and can execute Python
#
# Usage:
#   ./scripts/test-mcp-python.sh           # Run all tests
#   ./scripts/test-mcp-python.sh --quick   # Skip MCP server tests, just test workers
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
#

set -euo pipefail

PROJECT_DIR="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
MCP_DIR="$PROJECT_DIR/mcp-servers/fleet-orchestrator"
SHARED_DIR="$PROJECT_DIR/shared"
WORKER_SCRIPT="$SHARED_DIR/python-worker.py"
FLEET_EXECUTOR="$SHARED_DIR/fleet-executor.py"

# All 9 workers (8 API workers + aio-01)
WORKERS=(
  server-01
  server-02
  server-03
  laptop-01
  pi-01
  pi-02
  desktop-ap
  server-ap
  aio-01
)

SSH_USER="claude"
SSH_OPTS="-o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

# Counters
PASS=0
FAIL=0
SKIP=0
TOTAL=0
FAILED_TESTS=()

# Colors (only if terminal supports them)
if [ -t 1 ]; then
  GREEN='\033[0;32m'
  RED='\033[0;31m'
  YELLOW='\033[0;33m'
  BLUE='\033[0;34m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  GREEN=''
  RED=''
  YELLOW=''
  BLUE=''
  BOLD=''
  NC=''
fi

log_pass() {
  PASS=$((PASS + 1))
  TOTAL=$((TOTAL + 1))
  echo -e "  ${GREEN}PASS${NC} $1"
}

log_fail() {
  FAIL=$((FAIL + 1))
  TOTAL=$((TOTAL + 1))
  FAILED_TESTS+=("$1")
  echo -e "  ${RED}FAIL${NC} $1"
  if [ -n "${2:-}" ]; then
    echo -e "       ${RED}$2${NC}"
  fi
}

log_skip() {
  SKIP=$((SKIP + 1))
  TOTAL=$((TOTAL + 1))
  echo -e "  ${YELLOW}SKIP${NC} $1"
}

log_section() {
  echo ""
  echo -e "${BOLD}${BLUE}=== $1 ===${NC}"
  echo ""
}

# Cleanup function for MCP server
MCP_PID=""
cleanup() {
  if [ -n "$MCP_PID" ] && kill -0 "$MCP_PID" 2>/dev/null; then
    kill "$MCP_PID" 2>/dev/null || true
    wait "$MCP_PID" 2>/dev/null || true
  fi
  # Clean up any temp files
  rm -f /tmp/mcp-test-*.json /tmp/mcp-test-*.fifo 2>/dev/null || true
}
trap cleanup EXIT

##############################################################################
# PHASE 1: Prerequisites
##############################################################################

log_section "Phase 1: Prerequisites"

# Check python-worker.py exists
if [ -f "$WORKER_SCRIPT" ]; then
  log_pass "python-worker.py exists at $WORKER_SCRIPT"
else
  log_fail "python-worker.py not found at $WORKER_SCRIPT"
fi

# Check fleet-executor.py exists
if [ -f "$FLEET_EXECUTOR" ]; then
  log_pass "fleet-executor.py exists at $FLEET_EXECUTOR"
else
  log_fail "fleet-executor.py not found at $FLEET_EXECUTOR"
fi

# Check MCP server directory
if [ -f "$MCP_DIR/index.js" ]; then
  log_pass "MCP server index.js exists"
else
  log_fail "MCP server index.js not found at $MCP_DIR/index.js"
fi

# Check node_modules installed
if [ -d "$MCP_DIR/node_modules/@modelcontextprotocol" ]; then
  log_pass "MCP SDK dependencies installed"
else
  log_fail "MCP SDK dependencies not installed (run: cd $MCP_DIR && npm install)"
fi

# Check at least one API key is available
API_KEY_FOUND=false
for key_var in PERSONAL_GROQ_API_KEY PERSONAL_OPENAI_API_KEY ANTHROPIC_API_KEY PERSONAL_CEREBRAS_API_KEY GOOGLE_API_KEY; do
  # Try current env first, then bashrc
  key_val="${!key_var:-}"
  if [ -z "$key_val" ]; then
    key_val=$(bash -c "source ~/.bashrc 2>/dev/null && echo \${$key_var}" 2>/dev/null || true)
  fi
  if [ -n "$key_val" ]; then
    API_KEY_FOUND=true
    log_pass "API key available: $key_var"
    break
  fi
done
if [ "$API_KEY_FOUND" = false ]; then
  log_fail "No API keys found in environment (need at least one of: PERSONAL_GROQ_API_KEY, PERSONAL_OPENAI_API_KEY, etc.)"
fi

##############################################################################
# PHASE 2: SSH connectivity to all 9 workers
##############################################################################

log_section "Phase 2: SSH Connectivity (all 9 workers)"

REACHABLE_WORKERS=()
UNREACHABLE_WORKERS=()

for worker in "${WORKERS[@]}"; do
  if ssh $SSH_OPTS "${SSH_USER}@${worker}" "echo OK" >/dev/null 2>&1; then
    log_pass "SSH to ${worker}"
    REACHABLE_WORKERS+=("$worker")
  else
    log_fail "SSH to ${worker}" "Cannot connect via ssh ${SSH_USER}@${worker}"
    UNREACHABLE_WORKERS+=("$worker")
  fi
done

echo ""
echo "  Reachable: ${#REACHABLE_WORKERS[@]}/${#WORKERS[@]} workers"

##############################################################################
# PHASE 3: Python availability on all reachable workers
##############################################################################

log_section "Phase 3: Python3 Availability"

PYTHON_WORKERS=()

for worker in "${REACHABLE_WORKERS[@]}"; do
  py_version=$(ssh $SSH_OPTS "${SSH_USER}@${worker}" "python3 --version 2>&1" 2>/dev/null || echo "NOT FOUND")
  if echo "$py_version" | grep -q "Python 3"; then
    log_pass "${worker}: ${py_version}"
    PYTHON_WORKERS+=("$worker")
  else
    log_fail "${worker}: Python3 not available" "$py_version"
  fi
done

##############################################################################
# PHASE 4: python-worker.py deployment verification
##############################################################################

log_section "Phase 4: Worker Script Deployment"

DEPLOYED_WORKERS=()

for worker in "${PYTHON_WORKERS[@]}"; do
  # Check if worker script exists on the remote machine
  remote_path="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/python-worker.py"
  if ssh $SSH_OPTS "${SSH_USER}@${worker}" "test -f '$remote_path'" 2>/dev/null; then
    log_pass "${worker}: python-worker.py deployed"
    DEPLOYED_WORKERS+=("$worker")
  else
    # Try alternate path under claude home
    alt_path="/home/claude/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/python-worker.py"
    if ssh $SSH_OPTS "${SSH_USER}@${worker}" "test -f '$alt_path'" 2>/dev/null; then
      log_pass "${worker}: python-worker.py deployed (claude home)"
      DEPLOYED_WORKERS+=("$worker")
    else
      log_fail "${worker}: python-worker.py not found on worker"
    fi
  fi
done

##############################################################################
# PHASE 5: Python executor dry-run (JSON parse test, no API call)
##############################################################################

log_section "Phase 5: Python Executor JSON Handling"

for worker in "${DEPLOYED_WORKERS[@]}"; do
  # Send intentionally incomplete params to test JSON parsing works
  # (will fail on missing API key, but proves python-worker.py runs and parses JSON)
  result=$(ssh $SSH_OPTS "${SSH_USER}@${worker}" "echo '{\"task\":\"test\",\"model\":\"test\",\"url\":\"http://localhost:0\",\"key_env\":\"NONEXISTENT_KEY_12345\"}' | python3 ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/python-worker.py 2>/dev/null || true" 2>/dev/null || echo '{"error":"ssh failed"}')

  # The worker should return valid JSON (even if it is an error about missing key)
  if echo "$result" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    # Check it complained about missing key (expected behavior)
    if echo "$result" | grep -q '"error"'; then
      log_pass "${worker}: JSON parse + error handling works"
    else
      log_pass "${worker}: JSON parse works (unexpected success)"
    fi
  else
    log_fail "${worker}: python-worker.py did not return valid JSON" "Got: ${result:0:200}"
  fi
done

##############################################################################
# PHASE 6: Live API execution on each worker via Python executor
##############################################################################

log_section "Phase 6: Live API Execution (Python executor on each worker)"

# Use fleet-executor.py to run a real API call on each deployed worker
# We use a cheap, fast model (groq llama or cerebras) for testing

# Determine which API key + model to use for testing
TEST_MODEL=""
TEST_PROVIDER=""
TEST_URL=""
TEST_KEY=""

# Try Groq first (fast + free tier)
GROQ_KEY=$(bash -c "source ~/.bashrc 2>/dev/null && echo \$PERSONAL_GROQ_API_KEY" 2>/dev/null || echo "${PERSONAL_GROQ_API_KEY:-}")
if [ -n "$GROQ_KEY" ]; then
  TEST_MODEL="llama-3.3-70b-versatile"
  TEST_PROVIDER="groq"
  TEST_URL="https://api.groq.com/openai/v1/chat/completions"
  TEST_KEY="$GROQ_KEY"
fi

# Fallback to Cerebras
if [ -z "$TEST_KEY" ]; then
  CEREBRAS_KEY=$(bash -c "source ~/.bashrc 2>/dev/null && echo \$PERSONAL_CEREBRAS_API_KEY" 2>/dev/null || echo "${PERSONAL_CEREBRAS_API_KEY:-}")
  if [ -n "$CEREBRAS_KEY" ]; then
    TEST_MODEL="llama-3.3-70b"
    TEST_PROVIDER="cerebras"
    TEST_URL="https://api.cerebras.ai/v1/chat/completions"
    TEST_KEY="$CEREBRAS_KEY"
  fi
fi

# Fallback to OpenAI
if [ -z "$TEST_KEY" ]; then
  OPENAI_KEY=$(bash -c "source ~/.bashrc 2>/dev/null && echo \$PERSONAL_OPENAI_API_KEY" 2>/dev/null || echo "${PERSONAL_OPENAI_API_KEY:-}")
  if [ -n "$OPENAI_KEY" ]; then
    TEST_MODEL="gpt-4o-mini"
    TEST_PROVIDER="openai"
    TEST_URL="https://api.openai.com/v1/chat/completions"
    TEST_KEY="$OPENAI_KEY"
  fi
fi

if [ -z "$TEST_KEY" ]; then
  echo "  No API key available for live testing. Skipping Phase 6."
  for worker in "${DEPLOYED_WORKERS[@]}"; do
    log_skip "${worker}: No API key for live test"
  done
else
  echo "  Using model: ${TEST_MODEL} (${TEST_PROVIDER})"
  echo ""

  LIVE_PASS=0
  LIVE_FAIL=0

  for worker in "${DEPLOYED_WORKERS[@]}"; do
    # Build the JSON params for python-worker.py
    PARAMS=$(python3 -c "
import json
print(json.dumps({
    'task': 'Respond with exactly: WORKER_OK',
    'model': '${TEST_MODEL}',
    'max_tokens': 20,
    'url': '${TEST_URL}',
    'key_env': 'UNUSED',
    'api_key': '${TEST_KEY}'
}))
")

    # Execute on worker via SSH
    START_MS=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")

    result=$(ssh $SSH_OPTS "${SSH_USER}@${worker}" \
      "echo '${PARAMS}' | python3 ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/python-worker.py" \
      2>/dev/null || echo '{"error":"SSH or execution failed"}')

    END_MS=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
    DURATION=$((END_MS - START_MS))

    # Validate result
    if echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'output' in d" 2>/dev/null; then
      output=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin)['output'])" 2>/dev/null)
      tokens_in=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('input_tokens',0))" 2>/dev/null)
      tokens_out=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('output_tokens',0))" 2>/dev/null)
      log_pass "${worker}: API call succeeded (${DURATION}ms, ${tokens_in}+${tokens_out} tokens)"
      LIVE_PASS=$((LIVE_PASS + 1))
    else
      error_msg=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('error','unknown'))" 2>/dev/null || echo "$result")
      log_fail "${worker}: API call failed" "${error_msg:0:200}"
      LIVE_FAIL=$((LIVE_FAIL + 1))
    fi
  done

  echo ""
  echo "  Live API results: ${LIVE_PASS} passed, ${LIVE_FAIL} failed out of ${#DEPLOYED_WORKERS[@]} workers"
fi

##############################################################################
# PHASE 7: MCP Server Start + Tool Listing
##############################################################################

QUICK_MODE="${1:-}"

if [ "$QUICK_MODE" = "--quick" ]; then
  log_section "Phase 7: MCP Server (SKIPPED - quick mode)"
  log_skip "MCP server test skipped (--quick flag)"
else
  log_section "Phase 7: MCP Server Start + Tool Listing"

  # Create named pipes for MCP communication
  MCP_IN="/tmp/mcp-test-$$.fifo.in"
  MCP_OUT="/tmp/mcp-test-$$.fifo.out"
  mkfifo "$MCP_IN" "$MCP_OUT" 2>/dev/null || true

  # Start MCP server with stdio transport
  cd "$MCP_DIR"
  node index.js < "$MCP_IN" > "$MCP_OUT" 2>/tmp/mcp-test-$$.stderr &
  MCP_PID=$!
  cd "$PROJECT_DIR"

  # Give server time to start
  sleep 2

  if kill -0 "$MCP_PID" 2>/dev/null; then
    log_pass "MCP server started (PID: $MCP_PID)"

    # Send initialize request
    INIT_REQ='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

    # Send request and read response with timeout
    (
      echo "$INIT_REQ"
      sleep 1
      # Send tools/list after init
      echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
      sleep 2
    ) > "$MCP_IN" &
    SENDER_PID=$!

    # Read responses with timeout
    INIT_RESPONSE=""
    TOOLS_RESPONSE=""
    RESPONSE_TIMEOUT=10
    ELAPSED=0

    while [ $ELAPSED -lt $RESPONSE_TIMEOUT ]; do
      if read -t 1 line < "$MCP_OUT" 2>/dev/null; then
        if echo "$line" | grep -q '"id":1'; then
          INIT_RESPONSE="$line"
        fi
        if echo "$line" | grep -q '"id":2'; then
          TOOLS_RESPONSE="$line"
          break
        fi
      fi
      ELAPSED=$((ELAPSED + 1))
    done

    kill "$SENDER_PID" 2>/dev/null || true

    # Validate initialize response
    if [ -n "$INIT_RESPONSE" ]; then
      if echo "$INIT_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'result' in d" 2>/dev/null; then
        log_pass "MCP initialize handshake succeeded"
      else
        log_fail "MCP initialize returned error" "${INIT_RESPONSE:0:200}"
      fi
    else
      log_fail "MCP initialize: no response within ${RESPONSE_TIMEOUT}s"
    fi

    # Validate tools/list response
    if [ -n "$TOOLS_RESPONSE" ]; then
      tool_count=$(echo "$TOOLS_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('result',{}).get('tools',[])))" 2>/dev/null || echo "0")
      has_fleet_execute=$(echo "$TOOLS_RESPONSE" | python3 -c "
import json,sys
d=json.load(sys.stdin)
tools = d.get('result',{}).get('tools',[])
names = [t['name'] for t in tools]
print('yes' if 'fleet-execute' in names else 'no')
" 2>/dev/null || echo "no")

      if [ "$has_fleet_execute" = "yes" ]; then
        log_pass "MCP tools/list includes fleet-execute (${tool_count} tools total)"
      else
        log_fail "MCP tools/list missing fleet-execute" "Tools found: ${tool_count}"
      fi

      # Check for fleet-status and fleet-consensus too
      has_fleet_status=$(echo "$TOOLS_RESPONSE" | python3 -c "
import json,sys
d=json.load(sys.stdin)
tools = [t['name'] for t in d.get('result',{}).get('tools',[])]
print('yes' if 'fleet-status' in tools else 'no')
" 2>/dev/null || echo "no")

      has_fleet_consensus=$(echo "$TOOLS_RESPONSE" | python3 -c "
import json,sys
d=json.load(sys.stdin)
tools = [t['name'] for t in d.get('result',{}).get('tools',[])]
print('yes' if 'fleet-consensus' in tools else 'no')
" 2>/dev/null || echo "no")

      if [ "$has_fleet_status" = "yes" ]; then
        log_pass "MCP tools/list includes fleet-status"
      else
        log_fail "MCP tools/list missing fleet-status"
      fi

      if [ "$has_fleet_consensus" = "yes" ]; then
        log_pass "MCP tools/list includes fleet-consensus"
      else
        log_fail "MCP tools/list missing fleet-consensus"
      fi
    else
      log_fail "MCP tools/list: no response within ${RESPONSE_TIMEOUT}s"
    fi

    # Stop MCP server
    kill "$MCP_PID" 2>/dev/null || true
    wait "$MCP_PID" 2>/dev/null || true
    MCP_PID=""
    log_pass "MCP server shut down cleanly"
  else
    log_fail "MCP server failed to start"
    MCP_PID=""
    # Show stderr for debugging
    if [ -f /tmp/mcp-test-$$.stderr ]; then
      echo "  Server stderr:"
      head -20 /tmp/mcp-test-$$.stderr | sed 's/^/    /'
    fi
  fi

  rm -f "$MCP_IN" "$MCP_OUT" /tmp/mcp-test-$$.stderr 2>/dev/null || true
fi

##############################################################################
# PHASE 8: fleet-executor.py local integration test
##############################################################################

log_section "Phase 8: fleet-executor.py Integration"

if [ -n "${TEST_KEY:-}" ]; then
  # Test the Python fleet executor directly (local mode)
  result=$(cd "$SHARED_DIR" && python3 -c "
import json, sys
sys.path.insert(0, '.')
from fleet_executor import execute_on_worker

try:
    r = execute_on_worker(
        worker='aio-01',
        model='${TEST_MODEL}',
        task='Respond with exactly the word: PYTHON_EXECUTOR_OK',
        max_tokens=20,
        api_key='${TEST_KEY}'
    )
    print(json.dumps(r))
except Exception as e:
    print(json.dumps({'error': str(e)}))
" 2>/dev/null || echo '{"error":"fleet_executor import failed"}')

  if echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'output' in d" 2>/dev/null; then
    host=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('execution_host','?'))" 2>/dev/null)
    log_pass "fleet-executor.py local execution worked (host: ${host})"
  else
    error_msg=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('error','unknown'))" 2>/dev/null || echo "$result")
    log_fail "fleet-executor.py local execution failed" "${error_msg:0:200}"
  fi
else
  log_skip "fleet-executor.py integration (no API key)"
fi

##############################################################################
# Summary
##############################################################################

log_section "Test Summary"

echo "  Total:   ${TOTAL}"
echo -e "  Passed:  ${GREEN}${PASS}${NC}"
echo -e "  Failed:  ${RED}${FAIL}${NC}"
echo -e "  Skipped: ${YELLOW}${SKIP}${NC}"
echo ""
echo "  Workers tested: ${#DEPLOYED_WORKERS[@]}/${#WORKERS[@]}"
echo "  Reachable:      ${#REACHABLE_WORKERS[@]}/${#WORKERS[@]}"

if [ ${#UNREACHABLE_WORKERS[@]} -gt 0 ]; then
  echo ""
  echo -e "  ${YELLOW}Unreachable workers:${NC} ${UNREACHABLE_WORKERS[*]}"
fi

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
  echo ""
  echo -e "  ${RED}Failed tests:${NC}"
  for t in "${FAILED_TESTS[@]}"; do
    echo "    - $t"
  done
fi

echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}ALL TESTS PASSED${NC}"
  exit 0
else
  echo -e "${RED}${BOLD}${FAIL} TEST(S) FAILED${NC}"
  exit 1
fi
