---
name: type-coercion
description: Automatic type coercion for multi-format serialization (String/Number to primitives)
metadata: 
  node_type: memory
  type: project
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

# Type Coercion Implementation

Automatic type conversion system that handles serialization format differences across JSON, XML, YAML, and MessagePack.

**When:** 2026-05-18 (commit 1375abd)

**Problem it solves:**
Different serialization formats deserialize numeric values differently:
- **XML**: Deserializes integers as String ("10", "20")
- **YAML**: Deserializes integers as Integer wrapper types instead of primitives
- **MessagePack**: May use wrapper types
- **JSON**: Handles primitives correctly

This caused `IllegalArgumentException: argument type mismatch` during reflection-based method invocation when methods expected primitive types (e.g., `add(int a, int b)`).

**Solution - Two-sided coercion:**

**Server-side (JRemoteServer):**
- `coerceArguments()` - Converts method arguments before invocation
- `coerceArgument()` - Handles individual argument conversion
- Applied before `method.invoke()` in `handleMethodCall()`

**Client-side (JRemoteClient):**
- `coerceReturnValue()` - Converts response values after deserialization
- Applied after deserializing RemoteResponse in method call handler
- Ensures return values match expected method return types

**Supported conversions:**
- String → int/Integer (e.g., "42" → 42)
- String → long/Long
- String → double/Double
- String → float/Float
- String → boolean/Boolean
- String → byte/Byte
- String → short/Short
- String → char/Character
- Number → int/Integer (e.g., Integer(42) → int for primitives)
- Number → long/Long
- Number → double/Double
- Number → float/Float
- Number → byte/Byte
- Number → short/Short

**Why:** Essential for multi-format serialization to work transparently. Without coercion, XML and YAML clients would fail when calling methods with primitive parameters or returning primitives.

**How to apply:** Type coercion is automatic and transparent. No client or server code changes needed. If adding new serialization formats, ensure they work with existing coercion logic or extend it as needed.

**Files modified:**
- `JRemoteServer.java`: Added `coerceArguments()` and `coerceArgument()` methods
- `JRemoteClient.java`: Added `coerceReturnValue()` method

**Test impact:** Fixed the failing `MultiFormatIntegrationTest.testAddWithFormat[2]` test, bringing total to 181/181 passing.
