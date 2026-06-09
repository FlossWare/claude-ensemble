---
name: feedback-gitlab-issues
description: User expects test failures to be diagnosed and fixed completely
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0cfee593-446f-468f-9568-41f1f8d2a5ad
---

When user reports "the gitlab page states tests are failing," they expect a complete fix, not just diagnosis. User asked "are the tests passing now" and "continue" showing they wanted issues fully resolved.

**Why:** After initial push, user reported pipeline test failures. User then asked multiple times for updates ("are the tests passing now", "push out to gitlab") showing they were tracking the fix progression and wanted complete resolution. When issues were found, user said "continue" - indicating they wanted me to keep fixing until all tests pass.

**How to apply:** 
- When pipeline failures are reported, diagnose the root cause AND implement fixes
- Run tests locally to verify fixes work before pushing
- Push fixes immediately once verified
- Provide clear summary of what was broken and how it was fixed
- Don't stop at just identifying issues - fix them completely
- User appreciates detailed diagnosis (3 separate issues identified and fixed in this case)
