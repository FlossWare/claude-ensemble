---
name: project-ci-setup
description: GitHub Actions CD-CI workflow configuration for jsecurity
metadata: 
  node_type: memory
  type: project
  originSessionId: b8036c51-08a6-48f2-aa1c-41877b100b83
---

GitHub Actions workflow successfully configured at `.github/workflows/main.yml`

**Workflow behavior:**
- Triggers: Push to `main` branch (migrated from `master` on 2026-05-16)
- Prevents loops: Skips when pusher email is `version-bump@flossware.org`
- Auto-versioning: Increments minor version (1.0 → 1.6, fully verified)
- Build: Compiles and packages JAR (skips tests - see [[feedback-ci-testing]])
- Commit & Tag: Pushes version bump back to repo with git tag
- Deployment: Pushes to packagecloud.io/flossware/java/maven2

**Key steps:**
1. Setup JDK 11 (Temurin distribution)
2. Setup git credentials for version bump commits
3. Increment version: `mvn build-helper:parse-version versions:set -DnewVersion=\${parsedVersion.majorVersion}.\${parsedVersion.nextMinorVersion}`
4. Build: `mvn -U clean package -DskipTests`
5. Commit and tag: `mvn scm:checkin scm:tag`

**Configuration details:**
- Branch: `main` (migrated from `master` on 2026-05-16, `master` deleted)
- Build time: ~43 seconds (consistent across multiple runs)
- Version format: X.Y (enforced by maven-enforcer-plugin)
- Remote URL: `git@github.com:FlossWare/jsecurity.git` (SSH, not HTTPS)
- Current version: 1.6 (as of 2026-05-16)
- Pipeline fully verified through multiple build cycles

**Manual version bump:**
Use `./ci/rev-version.sh` for local manual version increments.

**Verification status (2026-05-16):**
- Multiple successful builds confirmed
- Auto-versioning working correctly (1.0 → 1.6)
- Deployment to packagecloud.io confirmed
- Git tagging operational (tags 1.1 through 1.6 created)
- All documentation updated to reference `main` branch

**Related:** Setup mirrors [[project-jcollections]] CI/CD approach
