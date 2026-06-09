---
name: phase-2a-progress
description: Phase 2A (ai/core module creation) in progress - core module complete, Claude integration nearly done with test files needing cleanup
metadata:
  type: project
---

Phase 2A of code duplication elimination is 90% complete. Created ai/core module with shared infrastructure, migrated Claude to use it, but test files need cleanup after aggressive sed command.

**Why:** Eliminating 13,838 LOC of duplication across 9 AI plugins. Phase 2A establishes foundation (exceptions, RetryPolicy, PreferencesUtil) that all plugins will use.

**Current Status (as of 2026-05-27):**

✅ **Completed:**
- Created ai/core module with Maven configuration and 80% JaCoCo threshold
- Created shared exception hierarchy in `ai/core/src/main/java/org/flossware/netbeans/ai/core/exceptions/`:
  - AIException (base)
  - AuthException, ConfigException, NetworkException, ParseException
  - RateLimitException (with retryAfterSeconds field)
- Moved RetryPolicy from Claude to `ai/core/src/main/java/org/flossware/netbeans/ai/core/retry/RetryPolicy.java`
- Created PreferencesUtil in `ai/core/src/main/java/org/flossware/netbeans/ai/core/util/PreferencesUtil.java`
- All 16 RetryPolicy tests passing in ai/core
- Updated ClaudeException to extend core AIException
- Updated ClaudeClient to import core RetryPolicy
- Updated all ClaudeClient public methods to throw `org.flossware.netbeans.ai.core.exceptions.AIException`:
  - sendMessage() line 120
  - sendMessageStreaming() line 235
  - sendMessageWithContext() line 192
  - sendMessageWithContextStreaming() line 321
- Updated sendMessageInternal() and sendMessageStreamingInternal() to throw AIException
- Removed Throwable-only constructors from Claude exception classes (ClaudeAuthException, ClaudeConfigException, ClaudeNetworkException, ClaudeParseException)

🚧 **In Progress - Needs Immediate Fix:**
- Claude test files broken by sed command that removed Throwable-only constructor tests
- File: `ai/claude/src/test/java/org/flossware/netbeans/claude/exceptions/ClaudeExceptionTest.java` line 30 has orphaned assertion
- Likely same issue in ClaudeAuthExceptionTest, ClaudeConfigExceptionTest, ClaudeNetworkExceptionTest, ClaudeParseExceptionTest
- Main compilation successful, test compilation failing

**How to apply:** 

**Next Immediate Steps:**
1. Fix broken test files - manually clean up orphaned lines from sed command:
   - ClaudeExceptionTest.java (line 30 orphaned assertion)
   - Check other 4 exception test files for similar issues
2. Run `mvn test -pl ai/claude` to verify all 573 tests pass
3. Run `mvn verify -pl ai/core` to verify 80%+ coverage
4. Commit Phase 2A: "Create ai/core module with shared exceptions, RetryPolicy, and PreferencesUtil"

**Files Modified:**
- pom.xml (parent) - added ai/core module
- ai/core/pom.xml - created
- ai/core/src/main/java/org/flossware/netbeans/ai/core/exceptions/* - 6 files created
- ai/core/src/main/java/org/flossware/netbeans/ai/core/retry/RetryPolicy.java - moved from Claude
- ai/core/src/main/java/org/flossware/netbeans/ai/core/util/PreferencesUtil.java - created
- ai/claude/pom.xml - added ai/core dependency
- ai/claude/src/main/java/org/flossware/netbeans/claude/api/ClaudeClient.java - uses core exceptions
- ai/claude/src/main/java/org/flossware/netbeans/claude/exceptions/* - extend core exceptions

**After Phase 2A Completion:**
Proceed to Phase 2B (Week 4): Create AbstractAIService and migrate all 9 services (eliminate 882 LOC).
