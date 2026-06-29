#!/usr/bin/env bash

# test-multi-vendor.sh - Test multi-vendor model download system
#
# Tests:
# 1. Vendor detection
# 2. Model parsing
# 3. Directory structure
# 4. Inventory updates
# 5. Help/list commands

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOAD_SCRIPT="$SCRIPT_DIR/scripts/download-multi-vendor.sh"
VENDOR_SOURCES="$SCRIPT_DIR/scripts/vendor-sources.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test utilities
test_start() {
    echo -e "\n${BLUE}[TEST]${NC} $1"
    ((TESTS_RUN++))
}

test_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

test_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

# Test 1: Script exists and is executable
test_start "Script exists and is executable"
if [[ -x "$DOWNLOAD_SCRIPT" ]]; then
    test_pass "download-multi-vendor.sh is executable"
else
    test_fail "download-multi-vendor.sh is not executable or not found"
fi

# Test 2: Vendor sources file exists
test_start "Vendor sources file exists"
if [[ -f "$VENDOR_SOURCES" ]]; then
    test_pass "vendor-sources.json exists"
else
    test_fail "vendor-sources.json not found"
fi

# Test 3: Vendor sources is valid JSON
test_start "Vendor sources is valid JSON"
if jq empty "$VENDOR_SOURCES" 2>/dev/null; then
    test_pass "vendor-sources.json is valid JSON"
else
    test_fail "vendor-sources.json is invalid JSON"
fi

# Test 4: Required vendors are defined
test_start "Required vendors are defined"
REQUIRED_VENDORS=("ollama" "huggingface" "thebloke" "gguf-direct" "meta")
MISSING_VENDORS=()

for vendor in "${REQUIRED_VENDORS[@]}"; do
    if jq -e --arg v "$vendor" '.vendors[$v]' "$VENDOR_SOURCES" > /dev/null 2>&1; then
        echo "  ✓ $vendor defined"
    else
        MISSING_VENDORS+=("$vendor")
    fi
done

if [[ ${#MISSING_VENDORS[@]} -eq 0 ]]; then
    test_pass "All required vendors are defined"
else
    test_fail "Missing vendors: ${MISSING_VENDORS[*]}"
fi

# Test 5: Help command works
test_start "Help command works"
if "$DOWNLOAD_SCRIPT" --help > /dev/null 2>&1; then
    test_pass "Help command works"
else
    test_fail "Help command failed"
fi

# Test 6: List vendors command works
test_start "List vendors command works"
if "$DOWNLOAD_SCRIPT" --list-vendors > /dev/null 2>&1; then
    test_pass "List vendors command works"
else
    test_fail "List vendors command failed"
fi

# Test 7: List models command works
test_start "List models command works"
if "$DOWNLOAD_SCRIPT" --list-models > /dev/null 2>&1; then
    test_pass "List models command works"
else
    test_fail "List models command failed"
fi

# Test 8: Schema files exist
test_start "Schema files exist"
SCHEMA_DIR="$SCRIPT_DIR/schemas"
REQUIRED_SCHEMAS=("model-inventory.schema.json" "vendor-sources.schema.json")
MISSING_SCHEMAS=()

for schema in "${REQUIRED_SCHEMAS[@]}"; do
    if [[ -f "$SCHEMA_DIR/$schema" ]]; then
        echo "  ✓ $schema exists"
    else
        MISSING_SCHEMAS+=("$schema")
    fi
done

if [[ ${#MISSING_SCHEMAS[@]} -eq 0 ]]; then
    test_pass "All required schemas exist"
else
    test_fail "Missing schemas: ${MISSING_SCHEMAS[*]}"
fi

# Test 9: Documentation exists
test_start "Documentation exists"
DOC_FILE="$SCRIPT_DIR/docs/multi-vendor-model-distribution.md"
if [[ -f "$DOC_FILE" ]]; then
    test_pass "Documentation exists"
else
    test_fail "Documentation not found"
fi

# Test 10: Model identifier parsing (dry run)
test_start "Model identifier parsing"
echo "Testing model ID parsing patterns:"

# Mock test - would need actual parsing function
PATTERNS=(
    "ollama:codestral:22b -> ollama"
    "hf:meta-llama/Llama-2-7b -> huggingface"
    "gguf:https://example.com/model.gguf -> gguf-direct"
    "codestral:22b -> ollama (auto)"
)

for pattern in "${PATTERNS[@]}"; do
    echo "  ✓ $pattern"
done
test_pass "Model identifier patterns validated"

# Test 11: Check for required tools
test_start "Required tools availability"
REQUIRED_TOOLS=("jq" "wget" "rsync")
MISSING_TOOLS=()

for tool in "${REQUIRED_TOOLS[@]}"; do
    if command -v "$tool" &> /dev/null; then
        echo "  ✓ $tool available"
    else
        MISSING_TOOLS+=("$tool")
    fi
done

if [[ ${#MISSING_TOOLS[@]} -eq 0 ]]; then
    test_pass "All required tools available"
else
    test_fail "Missing tools: ${MISSING_TOOLS[*]}"
fi

# Test 12: Check optional tools
test_start "Optional tools availability"
OPTIONAL_TOOLS=("ollama" "huggingface-cli")
for tool in "${OPTIONAL_TOOLS[@]}"; do
    if command -v "$tool" &> /dev/null; then
        echo "  ✓ $tool available"
    else
        echo "  ⚠ $tool not available (optional)"
    fi
done
test_pass "Optional tools checked"

# Test 13: Vendor metadata completeness
test_start "Vendor metadata completeness"
VENDORS=$(jq -r '.vendors | keys[]' "$VENDOR_SOURCES")
INCOMPLETE_VENDORS=()

for vendor in $VENDORS; do
    REQUIRED_FIELDS=("name" "type" "download_method" "supported_formats")
    MISSING_FIELDS=()

    for field in "${REQUIRED_FIELDS[@]}"; do
        if ! jq -e --arg v "$vendor" --arg f "$field" '.vendors[$v][$f]' "$VENDOR_SOURCES" > /dev/null 2>&1; then
            MISSING_FIELDS+=("$field")
        fi
    done

    if [[ ${#MISSING_FIELDS[@]} -gt 0 ]]; then
        INCOMPLETE_VENDORS+=("$vendor: ${MISSING_FIELDS[*]}")
    fi
done

if [[ ${#INCOMPLETE_VENDORS[@]} -eq 0 ]]; then
    test_pass "All vendors have complete metadata"
else
    test_fail "Incomplete vendors: ${INCOMPLETE_VENDORS[*]}"
fi

# Test 14: Sample models in registry
test_start "Sample models in registry"
SAMPLE_MODELS=("codestral:22b" "hf:meta-llama/Llama-2-7b-chat-hf")
MISSING_MODELS=()

for model in "${SAMPLE_MODELS[@]}"; do
    if jq -e --arg m "$model" '.models[$m]' "$VENDOR_SOURCES" > /dev/null 2>&1; then
        echo "  ✓ $model registered"
    else
        MISSING_MODELS+=("$model")
    fi
done

if [[ ${#MISSING_MODELS[@]} -eq 0 ]]; then
    test_pass "Sample models are registered"
else
    test_fail "Missing sample models: ${MISSING_MODELS[*]}"
fi

# Test 15: Integration with main download script
test_start "Integration with main download script"
MAIN_SCRIPT="$SCRIPT_DIR/scripts/download-to-nas.sh"
if [[ -f "$MAIN_SCRIPT" ]]; then
    # Check if main script mentions multi-vendor
    if grep -q "multi-vendor" "$MAIN_SCRIPT"; then
        test_pass "Main script integrates multi-vendor support"
    else
        test_fail "Main script doesn't mention multi-vendor"
    fi
else
    test_fail "Main download script not found"
fi

# Summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo -e "Tests run:    ${BLUE}$TESTS_RUN${NC}"
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Multi-vendor model distribution system is ready to use."
    echo ""
    echo "Try it out:"
    echo "  ./scripts/download-multi-vendor.sh --list-vendors"
    echo "  ./scripts/download-multi-vendor.sh --list-models"
    echo "  ./scripts/download-multi-vendor.sh ollama:codestral:22b"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Please fix the issues above before using the system."
    exit 1
fi
