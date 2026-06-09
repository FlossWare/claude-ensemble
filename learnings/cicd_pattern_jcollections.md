---
name: cicd_pattern_jcollections
description: Standard CI/CD pattern for FlossWare Java projects based on jcollections
metadata: 
  node_type: memory
  type: reference
  originSessionId: f26c00bc-2e0f-4df4-8b1f-d7888af7de1f
---

FlossWare Java projects follow the CI/CD pattern established in jcollections project.

**Reference implementation:** `../jcollections/.github/workflows/main.yml`

**Pattern details:**
- Workflow name: "CD-CI"
- Trigger: Push to main branch
- Skip condition: `github.event.pusher.email != 'version-bump@flossware.org'`
- Runner: ubuntu-latest with JDK 21
- Steps:
  1. Update runner (`sudo apt-get update`)
  2. Setup JDK 21 (Temurin distribution)
  3. Checkout code
  4. Prepare Maven settings.xml with packagecloud credentials
  5. Setup git credentials for version bumps (version-bump@flossware.org)
  6. Auto-increment version (X.Y format using build-helper and versions-maven-plugin)
  7. Update JUnit dependencies (`org.junit.jupiter:*`)
  8. Build and test (`mvn -U clean install`)
  9. Deploy to packagecloud.io (`mvn -DskipTests deploy`)
  10. Commit version bump and tag (`mvn scm:checkin scm:tag`)

**Why:** Ensures consistency across all FlossWare projects and automates versioning/deployment.

**How to apply:** When creating CI/CD for new FlossWare projects, copy the workflow from jcollections exactly, only changing repository-specific details in pom.xml.
