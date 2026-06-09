---
name: feedback-ci-testing
description: CI/CD workflow should skip integration tests that write to disk
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b8036c51-08a6-48f2-aa1c-41877b100b83
---

Skip disk-writing integration tests in GitHub Actions CI. Run them only locally before committing.

**Why:** The jsecurity integration tests actually write data to disk (disk wiping utility tests). On GitHub Actions runners, these tests:
- Timeout after 5+ minutes (vs 29 seconds locally)
- Write excessive amounts of data
- Cause builds to hang indefinitely

Multiple attempts to fix failed:
1. Reduced test sleep times (300ms → 50ms) - still too slow
2. Added 5-minute timeout - tests still timed out
3. Final solution: Skip tests entirely in CI with `-DskipTests`

**How to apply:**
- GitHub Actions workflow uses: `mvn clean package -DskipTests`
- CI verifies: compilation, dependency resolution, JAR packaging, version bumping
- Local testing (before pushing): `mvn test` completes in ~29 seconds, all 76 tests pass
- Developers must run tests locally before committing
- CI workflow completes successfully in ~43 seconds
