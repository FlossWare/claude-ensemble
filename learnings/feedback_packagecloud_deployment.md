---
name: packagecloud-deployment
description: Handle packagecloud.io 422 conflicts by manually bumping version in pom.xml
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

When packagecloud.io deployment fails with 422 Unprocessable Entity, manually bump the version in pom.xml to skip the conflicting version.

**Why:** Packagecloud.io returns 422 when trying to upload a version that already exists (even from failed deployments). The CI/CD auto-increment will deploy the next version, but we need to commit a base version that skips past all conflicts.

**How to apply:** If deployment fails with 422 for version X.Y, edit pom.xml to set version to X.(Y+1), commit, and push. The CI/CD will then auto-increment to X.(Y+2) and deploy successfully.
