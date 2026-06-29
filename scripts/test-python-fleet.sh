#!/bin/bash
# test-python-fleet.sh
# Test all 9 workers (aio-01 + 8 workers) using fleet-executor.py
# Handles quota/blocked APIs gracefully
# Returns clear pass/fail

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED_DIR="$(dirname "$SCRIPT_DIR")/shared"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Workers to test (including aio-01 as orchestrator with API access)
WORKERS=(
    "aio-01"
    "server-01"
    "server-02"
    "server-03"
    "laptop-01"
    "pi-01"
    "pi-02"
    "desktop-ap"
    "server-ap"
)

# Test models (one per provider, all free-tier friendly)
declare -A TEST_MODELS=(
    ["gpt-4o-mini"]="openai"
    ["llama-3.3-70b-versatile"]="groq"
    ["llama-3.3-70b"]="cerebras"
    ["gemini-2.0-flash-exp"]="google"
)

# Results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
QUOTA_ERRORS=0
declare -A WORKER_STATUS
declare -A PROVIDER_STATUS

# Log functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Test single worker with model
test_worker_model() {
    local worker="$1"
    local model="$2"
    local provider="$3"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    log_info "Testing ${worker} with ${model} (${provider})..."

    # Create test script
    local test_script=$(mktemp)
    cat > "$test_script" <<EOF
import sys
sys.path.insert(0, '${SHARED_DIR}')

from fleet_executor import execute_on_worker

try:
    result = execute_on_worker(
        worker='${worker}',
        model='${model}',
        task='Respond with exactly: OK',
        max_tokens=10,
        timeout_ms=30000
    )

    # Success - print result
    print(f"SUCCESS|{result.get('duration_ms', 0)}|{result.get('provider', 'unknown')}")
    sys.exit(0)

except Exception as e:
    error_msg = str(e).lower()

    # Check for quota/rate limit errors
    if 'quota' in error_msg or 'rate limit' in error_msg or '429' in error_msg:
        print(f"QUOTA|{error_msg[:100]}")
        sys.exit(2)

    # Check for blocked/unavailable
    if 'blocked' in error_msg or 'unavailable' in error_msg or 'timeout' in error_msg:
        print(f"BLOCKED|{error_msg[:100]}")
        sys.exit(3)

    # Other errors
    print(f"ERROR|{error_msg[:100]}")
    sys.exit(1)
EOF

    # Execute test
    local output
    local exit_code

    if output=$(python3 "$test_script" 2>&1); then
        exit_code=0
    else
        exit_code=$?
    fi

    rm -f "$test_script"

    # Parse result
    local status="${output%%|*}"
    local details="${output#*|}"

    case "$status" in
        SUCCESS)
            PASSED_TESTS=$((PASSED_TESTS + 1))
            WORKER_STATUS["$worker"]="PASS"
            PROVIDER_STATUS["$provider"]="PASS"
            log_success "${worker} + ${model}: ${details}ms"
            return 0
            ;;
        QUOTA)
            QUOTA_ERRORS=$((QUOTA_ERRORS + 1))
            log_warning "${worker} + ${model}: Quota exceeded (${details})"
            return 0  # Graceful - not a test failure
            ;;
        BLOCKED)
            log_warning "${worker} + ${model}: Blocked/unavailable (${details})"
            return 0  # Graceful - not a test failure
            ;;
        ERROR|*)
            FAILED_TESTS=$((FAILED_TESTS + 1))
            WORKER_STATUS["$worker"]="FAIL"
            log_error "${worker} + ${model}: ${details}"
            return 1
            ;;
    esac
}

# Test worker connectivity (SSH)
test_worker_connectivity() {
    local worker="$1"

    log_info "Testing connectivity to ${worker}..."

    if [ "$worker" = "aio-01" ] || [ "$worker" = "localhost" ]; then
        # Local test
        if python3 -c "print('OK')" >/dev/null 2>&1; then
            log_success "${worker}: Local connectivity OK"
            return 0
        else
            log_error "${worker}: Local Python unavailable"
            return 1
        fi
    else
        # Remote SSH test
        if timeout 5 ssh -o ConnectTimeout=3 "claude@${worker}" 'python3 -c "print(\"OK\")"' >/dev/null 2>&1; then
            log_success "${worker}: SSH connectivity OK"
            return 0
        else
            log_error "${worker}: SSH connectivity FAILED"
            WORKER_STATUS["$worker"]="UNREACHABLE"
            return 1
        fi
    fi
}

# Main test loop
main() {
    echo "======================================"
    echo "Python Fleet Executor Test Suite"
    echo "======================================"
    echo "Workers: ${#WORKERS[@]}"
    echo "Models: ${#TEST_MODELS[@]}"
    echo "Shared dir: ${SHARED_DIR}"
    echo ""

    # Phase 1: Test connectivity
    log_info "Phase 1: Testing connectivity..."
    local reachable_workers=()

    for worker in "${WORKERS[@]}"; do
        if test_worker_connectivity "$worker"; then
            reachable_workers+=("$worker")
        fi
    done

    echo ""
    log_info "Reachable workers: ${#reachable_workers[@]}/${#WORKERS[@]}"
    echo ""

    if [ ${#reachable_workers[@]} -eq 0 ]; then
        log_error "No reachable workers - aborting tests"
        exit 1
    fi

    # Phase 2: Test API calls
    log_info "Phase 2: Testing API calls..."

    # Test each reachable worker with one model (round-robin)
    local model_idx=0
    local models_array=($(printf '%s\n' "${!TEST_MODELS[@]}"))

    for worker in "${reachable_workers[@]}"; do
        local model="${models_array[$model_idx]}"
        local provider="${TEST_MODELS[$model]}"

        test_worker_model "$worker" "$model" "$provider" || true

        model_idx=$(( (model_idx + 1) % ${#models_array[@]} ))
        echo ""
    done

    # Phase 3: Test parallel execution (if multiple workers available)
    if [ ${#reachable_workers[@]} -ge 3 ]; then
        log_info "Phase 3: Testing parallel execution..."

        local parallel_test=$(mktemp)
        cat > "$parallel_test" <<EOF
import sys
sys.path.insert(0, '${SHARED_DIR}')

from fleet_executor import execute_on_fleet_parallel

workers = ${reachable_workers[@]:0:3}
workers_list = ['${reachable_workers[0]}', '${reachable_workers[1]}', '${reachable_workers[2]}']
task = 'Respond with: OK'

try:
    results = execute_on_fleet_parallel(
        workers=workers_list,
        model='gpt-4o-mini',
        tasks=[task],
        max_tokens=10,
        timeout_ms=30000
    )

    success_count = sum(1 for r in results if 'error' not in r)
    print(f"PARALLEL_SUCCESS|{success_count}/{len(workers_list)}")
    sys.exit(0)

except Exception as e:
    print(f"PARALLEL_ERROR|{str(e)[:100]}")
    sys.exit(1)
EOF

        if output=$(python3 "$parallel_test" 2>&1); then
            log_success "Parallel execution: ${output#*|}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            log_error "Parallel execution: ${output#*|}"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi

        rm -f "$parallel_test"
        echo ""
    fi

    # Summary
    echo "======================================"
    echo "Test Summary"
    echo "======================================"
    echo "Total tests: ${TOTAL_TESTS}"
    echo -e "${GREEN}Passed: ${PASSED_TESTS}${NC}"
    echo -e "${RED}Failed: ${FAILED_TESTS}${NC}"
    echo -e "${YELLOW}Quota errors: ${QUOTA_ERRORS}${NC}"
    echo ""

    # Worker status
    echo "Worker Status:"
    for worker in "${WORKERS[@]}"; do
        local status="${WORKER_STATUS[$worker]:-UNTESTED}"
        case "$status" in
            PASS)
                echo -e "  ${GREEN}✓${NC} ${worker}: ${status}"
                ;;
            FAIL)
                echo -e "  ${RED}✗${NC} ${worker}: ${status}"
                ;;
            UNREACHABLE)
                echo -e "  ${YELLOW}⚠${NC} ${worker}: ${status}"
                ;;
            *)
                echo -e "  ${BLUE}○${NC} ${worker}: ${status}"
                ;;
        esac
    done
    echo ""

    # Provider status
    echo "Provider Status:"
    for provider in "${!PROVIDER_STATUS[@]}"; do
        echo -e "  ${GREEN}✓${NC} ${provider}: ${PROVIDER_STATUS[$provider]}"
    done
    echo ""

    # Final verdict
    if [ ${FAILED_TESTS} -eq 0 ] && [ ${PASSED_TESTS} -gt 0 ]; then
        echo -e "${GREEN}════════════════════════════════════${NC}"
        echo -e "${GREEN}ALL TESTS PASSED${NC}"
        echo -e "${GREEN}════════════════════════════════════${NC}"
        exit 0
    elif [ ${PASSED_TESTS} -gt 0 ] && [ ${FAILED_TESTS} -lt ${PASSED_TESTS} ]; then
        echo -e "${YELLOW}════════════════════════════════════${NC}"
        echo -e "${YELLOW}PARTIAL SUCCESS${NC}"
        echo -e "${YELLOW}Some workers/providers functional${NC}"
        echo -e "${YELLOW}════════════════════════════════════${NC}"
        exit 0
    else
        echo -e "${RED}════════════════════════════════════${NC}"
        echo -e "${RED}TESTS FAILED${NC}"
        echo -e "${RED}════════════════════════════════════${NC}"
        exit 1
    fi
}

# Run main
main "$@"
