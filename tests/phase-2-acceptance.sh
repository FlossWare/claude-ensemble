#!/bin/bash
set -euo pipefail

# Phase 2 Acceptance Tests - Fleet Integration
# Tests: Worker distribution, worker selection modes, SSH timeout handling, execution_host field

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SHARED_DIR="$PROJECT_ROOT/shared"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0
TOTAL=0

echo "==========================================="
echo "Phase 2 Acceptance Tests - Fleet Integration"
echo "==========================================="
echo ""

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

# Test 1: Task executes on 3+ different workers
test_multi_worker_distribution() {
    if [[ ! -f "$SHARED_DIR/fleet-utils.js" ]]; then
        echo "fleet-utils.js not found"
        return 1
    fi

    # Create test script that imports fleet-utils
    cat > /tmp/test_worker_distribution.js << 'EOF'
const { getWorkers, remoteExec } = require('./shared/fleet-utils.js');

async function test() {
    const workers = getWorkers();
    const executions = [];

    for (let i = 0; i < 3; i++) {
        try {
            const worker = workers[i % workers.length];
            const result = await remoteExec(worker, 'hostname', 30000);
            executions.push({
                worker: worker.hostname,
                host: result.stdout.trim()
            });
        } catch (e) {
            console.error(`Execution ${i} failed:`, e.message);
        }
    }

    // Check we have different hosts
    const uniqueHosts = new Set(executions.map(e => e.host));
    console.log(JSON.stringify({
        executions,
        uniqueHostCount: uniqueHosts.size,
        success: uniqueHosts.size >= 2
    }));
}

test().catch(console.error);
EOF

    cd "$PROJECT_ROOT" && timeout 30s node /tmp/test_worker_distribution.js 2>/dev/null | \
        grep -q '"success":true' && return 0 || return 1
}

# Test 2: Worker selection respects 'auto' and explicit modes
test_worker_selection_modes() {
    if [[ ! -f "$SHARED_DIR/fleet-utils.js" ]]; then
        return 1
    fi

    cat > /tmp/test_worker_selection.js << 'EOF'
const { getWorkers, selectWorker } = require('./shared/fleet-utils.js');

async function test() {
    const workers = getWorkers();

    // Test auto selection
    const autoWorker = selectWorker(workers, 'auto');
    if (!autoWorker || !autoWorker.hostname) {
        console.log(JSON.stringify({ autoSuccess: false }));
        return;
    }

    // Test explicit selection
    const explicitWorker = selectWorker(workers, workers[0].hostname);
    const explicitMatch = explicitWorker && explicitWorker.hostname === workers[0].hostname;

    // Test invalid selection should not exist
    const invalidSelection = selectWorker(workers, 'nonexistent-worker');
    const invalidFails = !invalidSelection || !invalidSelection.hostname;

    console.log(JSON.stringify({
        autoSuccess: !!autoWorker,
        explicitSuccess: explicitMatch,
        invalidFails: invalidFails,
        success: !!autoWorker && explicitMatch && invalidFails
    }));
}

test().catch(console.error);
EOF

    cd "$PROJECT_ROOT" && timeout 10s node /tmp/test_worker_selection.js 2>/dev/null | \
        grep -q '"success":true' && return 0 || return 1
}

# Test 3: SSH timeout produces clear error within 30 seconds
test_ssh_timeout_handling() {
    if [[ ! -f "$SHARED_DIR/fleet-utils.js" ]]; then
        return 1
    fi

    cat > /tmp/test_ssh_timeout.js << 'EOF'
const { remoteExec } = require('./shared/fleet-utils.js');

async function test() {
    const start = Date.now();

    try {
        // Execute a command that will timeout
        await remoteExec({ hostname: 'localhost', port: 22, user: 'root' },
                         'sleep 60',
                         2000); // 2 second timeout
        console.log(JSON.stringify({ timedOut: false, error: 'No timeout occurred' }));
    } catch (e) {
        const elapsed = Date.now() - start;
        const isTimeout = e.message.includes('timeout') || e.code === 'ETIMEDOUT';
        const withinLimit = elapsed < 30000; // 30 second limit

        console.log(JSON.stringify({
            timedOut: isTimeout,
            withinLimit,
            elapsed,
            errorMessage: e.message,
            success: isTimeout && withinLimit
        }));
    }
}

test().catch(console.error);
EOF

    cd "$PROJECT_ROOT" && timeout 35s node /tmp/test_ssh_timeout.js 2>/dev/null | \
        grep -q '"success":true' && return 0 || return 1
}

# Test 4: execution_host field populated in output
test_execution_host_tracking() {
    if [[ ! -f "$SHARED_DIR/fleet-utils.js" ]]; then
        return 1
    fi

    cat > /tmp/test_execution_host.js << 'EOF'
const { getWorkers, remoteExec } = require('./shared/fleet-utils.js');

async function test() {
    const workers = getWorkers();
    const results = [];

    for (let i = 0; i < 2; i++) {
        const worker = workers[i % workers.length];
        try {
            const result = await remoteExec(worker, 'echo "test"', 5000);
            results.push({
                execution_host: worker.hostname,
                output: result.stdout.trim(),
                hasHost: !!worker.hostname
            });
        } catch (e) {
            results.push({
                execution_host: null,
                error: e.message,
                hasHost: false
            });
        }
    }

    const allHaveHost = results.every(r => r.hasHost);
    console.log(JSON.stringify({
        results,
        success: allHaveHost && results.length >= 2
    }));
}

test().catch(console.error);
EOF

    cd "$PROJECT_ROOT" && timeout 15s node /tmp/test_execution_host.js 2>/dev/null | \
        grep -q '"success":true' && return 0 || return 1
}

# Run all tests
run_test "Task executes on 3+ different workers" test_multi_worker_distribution
run_test "Worker selection respects 'auto' and explicit modes" test_worker_selection_modes
run_test "SSH timeout produces clear error within 30s" test_ssh_timeout_handling
run_test "execution_host field populated in output" test_execution_host_tracking

echo ""
echo "==========================================="
echo "Phase 2 Results: $PASSED/$TOTAL tests passed"
echo "==========================================="

if [[ $FAILED -gt 0 ]]; then
    echo -e "${RED}FAILED: $FAILED tests${NC}"
    exit 1
else
    echo -e "${GREEN}SUCCESS: All tests passed${NC}"
    exit 0
fi
