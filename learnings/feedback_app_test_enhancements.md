---
name: feedback_app_test_enhancements
description: app-test should generate integration tests and create GitHub issues for failures
metadata:
  type: feedback
---

When app-test finds bugs, it should automatically generate integration tests and create GitHub issues.

**Why:** User requested "for app-test, it should generate an integration test and open issues" after seeing app-test find bugs that unit tests missed. This ensures bugs never come back and maintains transparency.

**How to apply:**
- app-test workflow phases: Detect → Build → Test → **Generate Tests** → **Create Issues** → Verify
- Generate integration tests (*IT.java) that reproduce each failure
- Create GitHub issues with full bug details (file, line, error, root cause, fix suggestions)
- Tests should FAIL until bugs are fixed, then PASS (regression prevention)
- Return both generated tests and issue URLs in workflow result
- Tests use existing test utilities (IntegrationTestBase, MockNcursesBridge, etc.)
