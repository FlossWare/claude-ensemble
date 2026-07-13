#!/bin/bash
# Quick verification script for HYBRID system
# Runs end-to-end tests and displays results

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "================================================================================";
echo "HYBRID System Verification";
echo "================================================================================";
echo "";

# Check dependencies
echo "Checking dependencies...";

if ! command -v node &> /dev/null; then
    echo "✗ Node.js not found (required)";
    exit 1;
fi

if ! command -v python3 &> /dev/null; then
    echo "✗ Python 3 not found (required)";
    exit 1;
fi

if ! python3 -c "import redis" 2>/dev/null; then
    echo "⚠ Python redis library not found (some tests may be skipped)";
fi

echo "✓ Dependencies OK";
echo "";

# Run end-to-end tests
echo "Running end-to-end tests...";
echo "";

cd "$PROJECT_ROOT";
node test-hybrid-e2e.mjs;
EXIT_CODE=$?;

echo "";
echo "================================================================================";

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ HYBRID system verified: All tests passed!";
    echo "================================================================================";
    echo "";
    echo "See docs/HYBRID_SYSTEM_VERIFICATION.md for details.";
    exit 0;
else
    echo "✗ HYBRID system has failing tests!";
    echo "================================================================================";
    echo "";
    echo "Check test output above for details.";
    exit 1;
fi
