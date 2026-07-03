#!/bin/bash
# Run all integration tests for the orchestrator

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=========================================="
echo "RUNNING ALL INTEGRATION TESTS"
echo "=========================================="
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

cd "$PROJECT_ROOT"

# Test 1: Smart Orchestrator
echo "=========================================="
echo "TEST 1: Smart Orchestrator"
echo "=========================================="
python3 tests/integration/test_smart_orchestrator.py
TEST1_RESULT=$?
echo ""

# Test 2: ML Systems
echo "=========================================="
echo "TEST 2: ML Training Systems"
echo "=========================================="
python3 tests/integration/test_ml_systems.py
TEST2_RESULT=$?
echo ""

# Test 3: Document API (if running)
echo "=========================================="
echo "TEST 3: Document Ingestion API"
echo "=========================================="

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q "200"; then
    echo "✓ API is running, testing endpoints..."
    bash tests/api_test_script.sh
    TEST3_RESULT=$?
else
    echo "⚠ API not running (expected - it's optional)"
    echo "  To test: cd api && ./start.sh"
    TEST3_RESULT=0  # Don't fail if API isn't running
fi
echo ""

# Summary
echo "=========================================="
echo "INTEGRATION TEST SUMMARY"
echo "=========================================="
echo ""

if [ $TEST1_RESULT -eq 0 ]; then
    echo "✓ Smart Orchestrator: PASS"
else
    echo "✗ Smart Orchestrator: FAIL"
fi

if [ $TEST2_RESULT -eq 0 ]; then
    echo "✓ ML Systems: PASS"
else
    echo "✗ ML Systems: FAIL"
fi

if [ $TEST3_RESULT -eq 0 ]; then
    echo "✓ Document API: PASS (or skipped)"
else
    echo "✗ Document API: FAIL"
fi

echo ""

# Overall result
TOTAL_FAILED=$((TEST1_RESULT + TEST2_RESULT + TEST3_RESULT))

if [ $TOTAL_FAILED -eq 0 ]; then
    echo "✅ ALL INTEGRATION TESTS PASSED"
    exit 0
else
    echo "❌ $TOTAL_FAILED TEST SUITE(S) FAILED"
    exit 1
fi
