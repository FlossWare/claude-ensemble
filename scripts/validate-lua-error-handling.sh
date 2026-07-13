#!/bin/bash
# Validate Lua Error Handling Implementation
# Checks that all required error handling patterns are present

set -e

LUA_FILE="scripts/redis-lua-scripts.lua"

echo "======================================================================"
echo "Validating Lua Error Handling in $LUA_FILE"
echo "======================================================================"

# Check file exists
if [ ! -f "$LUA_FILE" ]; then
    echo "✗ ERROR: $LUA_FILE not found"
    exit 1
fi

echo "✓ File exists: $LUA_FILE"

# Check helper functions exist
echo ""
echo "Checking helper functions..."

if grep -q "local function safe_decode" "$LUA_FILE"; then
    echo "  ✓ safe_decode() defined"
else
    echo "  ✗ safe_decode() NOT found"
    exit 1
fi

if grep -q "local function safe_encode" "$LUA_FILE"; then
    echo "  ✓ safe_encode() defined"
else
    echo "  ✗ safe_encode() NOT found"
    exit 1
fi

if grep -q "local function validate_args" "$LUA_FILE"; then
    echo "  ✓ validate_args() defined"
else
    echo "  ✗ validate_args() NOT found"
    exit 1
fi

if grep -q "local function safe_redis_call" "$LUA_FILE"; then
    echo "  ✓ safe_redis_call() defined"
else
    echo "  ✗ safe_redis_call() NOT found"
    exit 1
fi

# Check all 6 main functions exist
echo ""
echo "Checking main functions..."

functions=("claim_task" "complete_task" "fail_task" "batch_claim_tasks" "update_heartbeat" "recover_stuck_tasks")

for func in "${functions[@]}"; do
    if grep -q "local function $func" "$LUA_FILE"; then
        echo "  ✓ $func() defined"
    else
        echo "  ✗ $func() NOT found"
        exit 1
    fi
done

# Check validation patterns are used
echo ""
echo "Checking validation patterns..."

validate_count=$(grep -c "validate_args" "$LUA_FILE" || true)
if [ "$validate_count" -ge 6 ]; then
    echo "  ✓ validate_args() used $validate_count times (expected ≥6)"
else
    echo "  ✗ validate_args() used only $validate_count times (expected ≥6)"
    exit 1
fi

safe_decode_count=$(grep -c "safe_decode" "$LUA_FILE" || true)
if [ "$safe_decode_count" -ge 5 ]; then
    echo "  ✓ safe_decode() used $safe_decode_count times (expected ≥5)"
else
    echo "  ✗ safe_decode() used only $safe_decode_count times (expected ≥5)"
    exit 1
fi

safe_encode_count=$(grep -c "safe_encode" "$LUA_FILE" || true)
if [ "$safe_encode_count" -ge 5 ]; then
    echo "  ✓ safe_encode() used $safe_encode_count times (expected ≥5)"
else
    echo "  ✗ safe_encode() used only $safe_encode_count times (expected ≥5)"
    exit 1
fi

safe_redis_count=$(grep -c "safe_redis_call" "$LUA_FILE" || true)
if [ "$safe_redis_count" -ge 20 ]; then
    echo "  ✓ safe_redis_call() used $safe_redis_count times (expected ≥20)"
else
    echo "  ✗ safe_redis_call() used only $safe_redis_count times (expected ≥20)"
    exit 1
fi

# Check error messages are present
echo ""
echo "Checking error messages..."

error_count=$(grep -c "ERROR:" "$LUA_FILE" || true)
if [ "$error_count" -ge 30 ]; then
    echo "  ✓ $error_count error messages defined (expected ≥30)"
else
    echo "  ✗ Only $error_count error messages found (expected ≥30)"
    exit 1
fi

# Check pcall usage
echo ""
echo "Checking pcall usage (error trapping)..."

pcall_count=$(grep -c "pcall" "$LUA_FILE" || true)
if [ "$pcall_count" -ge 3 ]; then
    echo "  ✓ pcall used $pcall_count times (in helper functions)"
else
    echo "  ✗ pcall used only $pcall_count times (expected ≥3)"
    exit 1
fi

# Check specific validation patterns
echo ""
echo "Checking specific validations..."

if grep -q "if not.*or.*== ''" "$LUA_FILE"; then
    echo "  ✓ Empty string checks present"
else
    echo "  ✗ Empty string checks NOT found"
    exit 1
fi

if grep -q "<= 0\|< 0" "$LUA_FILE"; then
    echo "  ✓ Numeric range validations present"
else
    echo "  ✗ Numeric range validations NOT found"
    exit 1
fi

if grep -q "Task.*not found" "$LUA_FILE"; then
    echo "  ✓ Task existence checks present"
else
    echo "  ✗ Task existence checks NOT found"
    exit 1
fi

if grep -q "owned by different worker" "$LUA_FILE"; then
    echo "  ✓ Worker ownership checks present"
else
    echo "  ✗ Worker ownership checks NOT found"
    exit 1
fi

# Summary
echo ""
echo "======================================================================"
echo "✓ ALL VALIDATION CHECKS PASSED"
echo "======================================================================"
echo ""
echo "Summary:"
echo "  - 4 helper functions defined"
echo "  - 6 main functions defined"
echo "  - $validate_count validation calls"
echo "  - $safe_decode_count safe_decode calls"
echo "  - $safe_encode_count safe_encode calls"
echo "  - $safe_redis_count safe_redis_call calls"
echo "  - $error_count error messages"
echo "  - $pcall_count pcall usages"
echo ""
echo "File: $LUA_FILE ($(wc -l < "$LUA_FILE") lines)"
echo ""
echo "✓ Comprehensive error handling successfully implemented"
