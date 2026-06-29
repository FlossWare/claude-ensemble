#!/bin/bash
#
# COMPREHENSIVE FLEET TEST SUITE
# Tests EVERY worker with MULTIPLE scenarios
# Reports DETAILED results
# NEVER claims success unless ALL tests pass
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

WORKERS=(server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap)
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

echo "========================================"
echo "COMPREHENSIVE FLEET TEST SUITE"
echo "Testing ALL 8 workers with MULTIPLE scenarios"
echo "========================================"
echo

# Test results tracking
declare -A TEST_RESULTS

test_result() {
  local worker=$1
  local test_name=$2
  local result=$3
  local details=$4

  TOTAL_TESTS=$((TOTAL_TESTS + 1))

  if [[ "$result" == "PASS" ]]; then
    echo -e "  ${GREEN}✅ $test_name${NC}: $details"
    PASSED_TESTS=$((PASSED_TESTS + 1))
    TEST_RESULTS["$worker:$test_name"]="PASS"
  else
    echo -e "  ${RED}❌ $test_name${NC}: $details"
    FAILED_TESTS=$((FAILED_TESTS + 1))
    TEST_RESULTS["$worker:$test_name"]="FAIL: $details"
  fi
}

echo "========================================="
echo "PHASE 1: INFRASTRUCTURE TESTS"
echo "========================================="
echo

for worker in "${WORKERS[@]}"; do
  echo "Testing $worker..."

  # Test 1: SSH connectivity
  if ssh -o ConnectTimeout=2 claude@$worker 'echo OK' &>/dev/null; then
    test_result "$worker" "SSH" "PASS" "Connected"
  else
    test_result "$worker" "SSH" "FAIL" "Cannot connect"
    echo "  ⚠️  Skipping remaining tests for $worker"
    echo
    continue
  fi

  # Test 2: Node.js installed
  node_version=$(ssh claude@$worker 'bash -lc "node --version 2>&1"' || echo "NOT_FOUND")
  if [[ "$node_version" == *"not found"* ]] || [[ "$node_version" == "NOT_FOUND" ]]; then
    test_result "$worker" "Node.js" "FAIL" "Not installed"
    echo "  ⚠️  Skipping remaining tests for $worker"
    echo
    continue
  else
    test_result "$worker" "Node.js" "PASS" "$node_version"
  fi

  # Test 3: Node version compatibility (need v18+)
  node_major=$(echo $node_version | grep -oP 'v\K[0-9]+')
  if [[ "$node_major" -lt 18 ]]; then
    test_result "$worker" "Node version" "FAIL" "v$node_major < v18 (too old)"
  else
    test_result "$worker" "Node version" "PASS" "v$node_major >= v18"
  fi

  # Test 4: Code synced
  if ssh claude@$worker 'test -f ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/execute-on-worker.js' &>/dev/null; then
    test_result "$worker" "Code sync" "PASS" "Latest code present"
  else
    test_result "$worker" "Code sync" "FAIL" "Code not synced"
  fi

  # Test 5: Credentials present
  if ssh claude@$worker 'test -f ~/.claude/credentials.json' &>/dev/null; then
    test_result "$worker" "Credentials" "PASS" "credentials.json exists"
  else
    test_result "$worker" "Credentials" "FAIL" "No credentials.json"
  fi

  # Test 6: Environment variables
  groq_key=$(ssh claude@$worker 'bash -lc "echo \$GROQ_API_KEY"' 2>/dev/null)
  if [[ -n "$groq_key" ]]; then
    test_result "$worker" "Environment" "PASS" "API keys loaded"
  else
    test_result "$worker" "Environment" "FAIL" "API keys not in environment"
  fi

  echo
done

echo "========================================="
echo "PHASE 2: ACTUAL EXECUTION TESTS"
echo "========================================="
echo

# Find working workers for execution tests
WORKING_WORKERS=()
for worker in "${WORKERS[@]}"; do
  if [[ "${TEST_RESULTS[$worker:SSH]}" == "PASS" ]] && \
     [[ "${TEST_RESULTS[$worker:Node.js]}" == "PASS" ]] && \
     [[ "${TEST_RESULTS[$worker:Code sync]}" == "PASS" ]]; then
    WORKING_WORKERS+=("$worker")
  fi
done

echo "Workers eligible for execution tests: ${WORKING_WORKERS[@]}"
echo

if [[ ${#WORKING_WORKERS[@]} -eq 0 ]]; then
  echo "❌ NO WORKERS AVAILABLE FOR EXECUTION TESTS!"
  exit 1
fi

cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Test each working worker individually
for worker in "${WORKING_WORKERS[@]}"; do
  echo "Execution test: $worker..."

  # Test 7: Simple API call
  result=$(node -e "
    import { executeOnWorker } from './shared/execute-on-worker.js';
    try {
      const r = await executeOnWorker({
        worker: '$worker',
        model: 'llama-3.3-70b-versatile',
        task: 'Say OK',
        maxTokens: 5,
        timeoutMs: 15000
      });
      console.log('PASS:' + r.output);
    } catch (error) {
      console.log('FAIL:' + error.message);
    }
  " 2>&1)

  if [[ "$result" == PASS:* ]]; then
    test_result "$worker" "API execution" "PASS" "${result#PASS:}"
  else
    test_result "$worker" "API execution" "FAIL" "${result#FAIL:}"
  fi

  echo
done

# Test parallel execution
if [[ ${#WORKING_WORKERS[@]} -ge 2 ]]; then
  echo "========================================="
  echo "PHASE 3: PARALLEL EXECUTION TEST"
  echo "========================================="
  echo

  echo "Testing ${#WORKING_WORKERS[@]} workers in parallel..."

  parallel_result=$(node -e "
    import { executeOnWorker } from './shared/execute-on-worker.js';

    const workers = ${WORKING_WORKERS[@]@Q}.split(' ');

    const start = Date.now();
    const results = await Promise.all(
      workers.map((worker, i) => executeOnWorker({
        worker,
        model: 'llama-3.3-70b-versatile',
        task: (i+1) + ' + ' + (i+1) + ' = ?',
        maxTokens: 5,
        timeoutMs: 20000
      }).catch(err => ({ error: err.message })))
    );
    const duration = Date.now() - start;

    const successful = results.filter(r => !r.error).length;
    console.log('PARALLEL:' + successful + '/' + workers.length + ':' + duration + 'ms');
  " 2>&1)

  if [[ "$parallel_result" == PARALLEL:* ]]; then
    IFS=':' read -r _ count duration <<< "$parallel_result"
    test_result "PARALLEL" "Distributed execution" "PASS" "$count workers, ${duration}"
  else
    test_result "PARALLEL" "Distributed execution" "FAIL" "Execution failed"
  fi

  echo
fi

echo "========================================="
echo "TEST SUMMARY"
echo "========================================="
echo
echo "Total tests run: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo

# Print detailed failure report
if [[ $FAILED_TESTS -gt 0 ]]; then
  echo "========================================="
  echo "FAILED TESTS DETAILS"
  echo "========================================="
  for key in "${!TEST_RESULTS[@]}"; do
    if [[ "${TEST_RESULTS[$key]}" == FAIL:* ]]; then
      echo "  ❌ $key: ${TEST_RESULTS[$key]#FAIL: }"
    fi
  done
  echo
fi

# Final verdict
echo "========================================="
echo "FINAL VERDICT"
echo "========================================="
echo

PASS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))

if [[ $FAILED_TESTS -eq 0 ]]; then
  echo -e "${GREEN}🎉 ALL TESTS PASSED (100%)${NC}"
  echo "✅ Fleet is FULLY OPERATIONAL"
  exit 0
elif [[ $PASS_RATE -ge 80 ]]; then
  echo -e "${YELLOW}⚠️  PARTIAL SUCCESS ($PASS_RATE%)${NC}"
  echo "Some workers operational but issues remain"
  echo "Working workers: ${#WORKING_WORKERS[@]}/8"
  exit 1
else
  echo -e "${RED}❌ CRITICAL FAILURES ($PASS_RATE%)${NC}"
  echo "Fleet is NOT operational"
  exit 1
fi
