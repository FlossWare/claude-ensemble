---
name: multiformat-serialization
description: "Multi-format serialization implementation (JSON, XML, YAML, MessagePack) with format auto-detection"
metadata: 
  node_type: memory
  type: project
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

# Multi-Format Serialization Implementation

jremote now supports 4 serialization formats: JSON (default), XML, YAML, and MessagePack.

**Architecture:**
- Strategy pattern with `SerializationStrategy` interface
- Client-side format selection via constructor: `new JRemoteClient(host, port, SerializationFormat.YAML)`
- Server-side auto-detection from single-byte format marker prefix (J/X/Y/M)
- Format marker added to every message: `[MARKER][PAYLOAD]\n`

**Key implementation details:**
- YAML strategy uses JSON mapper for serialization (JSON is valid YAML and single-line compatible with line-based protocol), YAML mapper for deserialization
- MessagePack uses Base64 encoding for text-based wire protocol compatibility
- XML, YAML, and MessagePack strategies require `activateDefaultTyping()` to handle `@JsonTypeInfo` annotations on polymorphic fields (`RemoteInvocation.args`, `RemoteResponse.result`)
- Server error responses must use same format as request (not hardcoded JSON fallback)
- **Type coercion**: Automatic conversion handles format differences (JRemoteServer: arguments, JRemoteClient: return values)
  - String→primitive/wrapper (XML deserializes numbers as strings)
  - Number→primitive (YAML/MessagePack may use wrapper types)
  - Supports all primitives: int, long, double, float, boolean, byte, short, char

**Status (2026-05-18):**
- Implementation complete with 181 tests (97 integration + 84 unit tests)
- **All 181 tests passing** ✅
- Type coercion implemented to handle format-specific serialization differences
- Automatic conversion: String→primitive (XML), Number→primitive (YAML/MessagePack)
- Coercion applied to both method arguments (server-side) and return values (client-side)
- Commits: 60ad289 (strategy config), c99999f (Windows scripts), 36c6117 (unit tests), 1375abd (type coercion), d88d00f (docs)

**Why:** Enables performance optimization (MessagePack), debugging (YAML), enterprise integration (XML), while maintaining JSON as default for backward compatibility.

**How to apply:** When debugging serialization issues, check that all strategies have proper Jackson configuration including default typing for polymorphic fields.
