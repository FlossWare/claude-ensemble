---
name: project-cicd-pipeline
description: jcurses GitHub Actions CI/CD pipeline configuration and troubleshooting history
metadata: 
  node_type: memory
  type: project
  originSessionId: 94f4d6f1-3bcc-4b78-a0b9-7eca2b004c75
---

jcurses uses GitHub Actions for automated CI/CD with packagecloud.io deployment.

**Pipeline workflow (.github/workflows/main.yml):**
1. Increments version using build-helper:parse-version (X.Y format)
2. Updates dependencies (JUnit, Mockito, AssertJ)
3. Builds and tests with Maven
4. Deploys to packagecloud.io/flossware/java/maven2/
5. Creates automated version bump commit with maven-scm-plugin
6. Tags the release

**Key configuration requirements:**
- build-helper-maven-plugin v3.5.0 - Required for version parsing
- message property in pom.xml - Required for scm:checkin commit messages
- Node.js 24 compatible actions - Required before June 2, 2026 deadline

**Troubleshooting history (May 2026):**

1. **Missing build-helper-maven-plugin** - Pipeline failed at version increment step. Fixed by adding plugin to pom.xml.

2. **Missing message property** - scm:checkin failed. Fixed by adding `<message>Automated Version Bump ${project.version} [ci skip]</message>` to properties.

3. **Version 1.1 duplicate on packagecloud** - Deploy failed with 422 error. CI/CD had incremented to 1.1 and deployed, but scm:checkin failed so version wasn't committed back to git. Fixed by manually bumping to 1.2 in pom.xml to skip the duplicate.

4. **Node.js 20 deprecation warnings** - Fixed in three steps:
   - Step 1: Added FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true (temporary)
   - Step 2: Upgraded actions/checkout@v4→v6, actions/setup-java@v4→v5 (native Node 24)
   - Step 3: Upgraded s4u/maven-settings-action@v3.1.0→v4.0.0, replaced oleksiyrudenko/gha-git-credentials with native git commands

**Final working versions:**
- actions/checkout@v6
- actions/setup-java@v5
- s4u/maven-settings-action@v4.0.0
- Native git config for credentials (no third-party action)

**How to apply:** When troubleshooting CI/CD pipeline failures, check build-helper-maven-plugin presence, message property, and action versions. Common pattern: CI/CD increments version and deploys, but if a later step fails, version isn't committed back causing duplicates on next run.
