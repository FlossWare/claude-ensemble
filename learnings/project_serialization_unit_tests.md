---
name: serialization-unit-tests
description: Comprehensive unit tests for all serialization strategies (84 tests added 2026-05-18)
metadata: 
  node_type: memory
  type: project
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

# Serialization Strategy Unit Tests

Added comprehensive unit test coverage for all serialization strategies and related components.

**When:** 2026-05-18 (commit 36c6117)

**What was added:**
- 84 new unit tests across 6 test classes
- Increased total test count from 97 to 181
- All new tests pass ✅

**Test files created:**

1. **JsonSerializationStrategyTest** (14 tests)
   - Round-trip serialization for all request types (CREATE_INSTANCE, METHOD_CALL, DESTROY_INSTANCE)
   - Success/error responses with various types (String, Integer, null)
   - Null handling, primitive arguments
   - UnsupportedOperationException for binary operations

2. **XmlSerializationStrategyTest** (15 tests)
   - XML-specific format validation (starts with `<`, contains XML tags)
   - Type coercion handling (Integer may serialize as String in XML)
   - All request/response round-trips
   - Error response with RemoteException

3. **YamlSerializationStrategyTest** (17 tests)
   - Validates output is JSON format (single-line, valid YAML)
   - Tests can deserialize both pure YAML and JSON input
   - All request/response types
   - Format compatibility verification

4. **MessagePackSerializationStrategyTest** (16 tests)
   - Base64 encoding validation for string serialization
   - Binary format tests (serializeToBytes/deserializeFromBytes)
   - Round-trip comparison: binary vs Base64 string
   - MessagePack binary marker verification (not JSON `{`, not XML `<`)

5. **SerializationStrategyFactoryTest** (7 tests)
   - Singleton pattern verification (same instance returned)
   - All 4 formats have strategies
   - Null parameter throws IllegalArgumentException
   - Every enum value has a strategy

6. **SerializationFormatTest** (15 tests)
   - Format marker uniqueness (J/X/Y/M)
   - Round-trip: marker → format → marker
   - fromMarker() validation and error handling
   - Enum ordinals, values, valueOf()

**Coverage includes:**
- Edge cases (null values, empty arrays, null fields in RemoteException)
- Type safety (primitive vs wrapper types)
- Format-specific behavior (XML type coercion, YAML can read both formats, MessagePack binary)
- Factory singleton pattern
- Marker-based format detection

**Why:** Provides confidence in serialization layer correctness, catches regressions, validates format-specific behavior, and documents expected behavior through executable tests.

**How to apply:** When modifying serialization strategies, run unit tests first (`mvn test -Dtest="*SerializationStrategyTest"`), then integration tests. Unit tests are faster and isolate issues to specific strategy implementations.
