---
name: feedback-regex-webservice-detection
description: Web service detection should use regex with comment/string removal to avoid false positives - proven approach that improved accuracy from 17% to >95%
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5069eeef-3c97-47e3-b069-3f9236a0ac7c
---

When detecting keywords in code (like Apex webservice methods), use regex pattern matching with comment and string literal removal to avoid false positives.

**Why:**
The original naive `str.contains("WebService")` approach had only 17% accuracy due to:
- False positives from comments, string literals, class names
- False negatives from case sensitivity (missing lowercase "webservice")
- No validation that keyword appears in proper context (method signature)

After implementing regex with cleaning, accuracy improved to >95%.

**How to apply:**
For code analysis tasks:
1. **Remove noise first**: Strip out comments and string literals using regex patterns
2. **Use proper patterns**: Match keywords with context (e.g., followed by method signature)
3. **Case-insensitive**: Use `Pattern.CASE_INSENSITIVE` when appropriate
4. **Word boundaries**: Use `\b` to match whole words, not substrings

**Example Implementation (RetrieveWsdls.java):**
```java
// Clean the code
String cleaned = SINGLE_LINE_COMMENT_PATTERN.matcher(content).replaceAll("");
cleaned = MULTI_LINE_COMMENT_PATTERN.matcher(cleaned).replaceAll("");
cleaned = STRING_LITERAL_PATTERN.matcher(cleaned).replaceAll("");

// Then match with context
Pattern pattern = Pattern.compile(
    "\\bwebservice\\s+(?:static\\s+)?\\S+.*?\\w+\\s*\\(",
    Pattern.CASE_INSENSITIVE | Pattern.DOTALL
);
```

**Patterns Used:**
- Single-line comments: `//.*?$` with MULTILINE
- Multi-line comments: `/\*.*?\*/` with DOTALL
- String literals: `'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"` with DOTALL

This approach is validated with 18 comprehensive tests covering all edge cases.
