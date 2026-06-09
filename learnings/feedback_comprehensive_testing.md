---
name: feedback_comprehensive_testing
description: "User values comprehensive testing at multiple levels - unit, integration, and smoke tests"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f3324023-02df-438a-bb60-0174b5bcd186
---

Test thoroughly at multiple levels. User built comprehensive test suite (799 tests) and wants smoke tests in addition to unit/integration tests.

**Why:** User requested integration tests be created, then requested app-test workflow for smoke testing actual app launches. User achieved 99% code coverage and wanted to push for 100%. User values testing that catches real bugs, not just coverage numbers.

**How to apply:**
- Run all test levels after changes: unit tests, integration tests, smoke tests
- Use app-test workflow after significant changes to verify app actually works
- Don't assume unit tests passing means the app works - verify with real execution
- Suggest adding tests when gaps are found (e.g., app-test found bugs unit tests missed)
