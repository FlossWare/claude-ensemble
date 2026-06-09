---
name: serialization-debugging
description: Server error responses must match request format; debug argument type mismatches
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

When implementing multi-format serialization with auto-detection, server error responses must use the same format as the incoming request, not a hardcoded fallback format.

**Why:** During MultiFormatIntegrationTest debugging, XML clients were receiving JSON error responses from the server's catch block. This caused "Unexpected character '{' in prolog; expected '<'" errors because XmlSerializationStrategy tried to parse JSON as XML.

**How to apply:** 
- Capture the detected `SerializationStrategy` before the try block
- In the catch block, use the same strategy for error responses (or JSON as fallback only if strategy is null)
- For debugging "argument type mismatch" errors during reflection-based method invocation, add debug logging to show actual argument types vs expected parameter types

Code pattern:
```java
SerializationStrategy strategy = null;
try {
    strategy = detectAndGetStrategy(request);
    processRequest(request, strategy);
} catch (Exception e) {
    SerializationStrategy errorStrategy = strategy != null ? strategy : jsonFallback;
    sendErrorResponse(e, errorStrategy);
}
```
