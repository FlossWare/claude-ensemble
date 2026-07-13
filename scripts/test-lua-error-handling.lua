-- Test Lua Error Handling
-- Simple standalone test to verify error handling functions work

-- Mock Redis calls for standalone testing
local redis = {
    call = function(cmd, ...)
        if cmd == 'RPOP' then
            return nil  -- Empty queue test
        end
        return "OK"
    end
}

local cjson = require("cjson")

-- Helper: Safe JSON decode with error handling
local function safe_decode(json_str, context)
    if not json_str or json_str == '' then
        return nil, 'ERROR: Empty JSON string in ' .. context
    end

    local success, result = pcall(cjson.decode, json_str)
    if not success then
        return nil, 'ERROR: Invalid JSON in ' .. context .. ': ' .. tostring(result)
    end

    return result, nil
end

-- Helper: Safe JSON encode with error handling
local function safe_encode(obj, context)
    local success, result = pcall(cjson.encode, obj)
    if not success then
        return nil, 'ERROR: JSON encode failed in ' .. context .. ': ' .. tostring(result)
    end

    return result, nil
end

-- Helper: Validate required arguments
local function validate_args(required_keys, required_argv, context)
    if #KEYS < required_keys then
        return 'ERROR: ' .. context .. ' requires ' .. required_keys .. ' KEYS, got ' .. #KEYS
    end

    if #ARGV < required_argv then
        return 'ERROR: ' .. context .. ' requires ' .. required_argv .. ' ARGV, got ' .. #ARGV
    end

    return nil
end

-- Test cases
print("Testing error handling helpers...")

-- Test 1: safe_decode with empty string
local result, err = safe_decode('', 'test1')
assert(err ~= nil, "Should fail on empty string")
print("✓ Test 1: safe_decode rejects empty string")

-- Test 2: safe_decode with invalid JSON
local result, err = safe_decode('{invalid', 'test2')
assert(err ~= nil, "Should fail on invalid JSON")
print("✓ Test 2: safe_decode rejects invalid JSON")

-- Test 3: safe_decode with valid JSON
local result, err = safe_decode('{"test": "value"}', 'test3')
assert(err == nil, "Should succeed on valid JSON")
assert(result.test == "value", "Should parse correctly")
print("✓ Test 3: safe_decode parses valid JSON")

-- Test 4: safe_encode with valid object
local result, err = safe_encode({test = "value"}, 'test4')
assert(err == nil, "Should succeed on valid object")
print("✓ Test 4: safe_encode encodes valid object")

-- Mock KEYS and ARGV
KEYS = {"key1", "key2"}
ARGV = {"arg1", "arg2", "arg3"}

-- Test 5: validate_args success
local err = validate_args(2, 3, 'test5')
assert(err == nil, "Should succeed with correct args")
print("✓ Test 5: validate_args accepts correct arguments")

-- Test 6: validate_args failure (not enough KEYS)
local err = validate_args(3, 3, 'test6')
assert(err ~= nil, "Should fail with too few KEYS")
print("✓ Test 6: validate_args rejects insufficient KEYS")

-- Test 7: validate_args failure (not enough ARGV)
local err = validate_args(2, 4, 'test7')
assert(err ~= nil, "Should fail with too few ARGV")
print("✓ Test 7: validate_args rejects insufficient ARGV")

print("\n✓ All error handling tests passed!")
