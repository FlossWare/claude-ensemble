---
name: reference_cicd_troubleshooting
description: Common CI/CD issues and solutions for FlossWare GitHub Actions workflows
metadata: 
  node_type: memory
  type: reference
  originSessionId: 991c96d3-12be-4e89-a221-88c867f72eb4
---

Common issues encountered and resolved in FlossWare CI/CD pipelines:

## Missing build-helper-maven-plugin

**Problem:** GitHub Actions workflow uses `mvn build-helper:parse-version` but build-helper-maven-plugin not declared in pom.xml.

**Solution:** Add to pom.xml:
```xml
<plugin>
    <groupId>org.codehaus.mojo</groupId>
    <artifactId>build-helper-maven-plugin</artifactId>
    <version>3.5.0</version>
</plugin>
```

**Why:** The workflow step `mvn -U build-helper:parse-version versions:set -DnewVersion=\${parsedVersion.majorVersion}.\${parsedVersion.nextMinorVersion}` requires this plugin to parse the current version and increment it.

## Packagecloud.io HTTP 422 Error

**Problem:** `status code: 422, reason phrase: Unprocessable Entity` when deploying to packagecloud.io.

**Cause:** Attempting to deploy a version that already exists in the packagecloud.io repository.

**Solution:** Each deployment must use a unique version number. The CI/CD pipeline handles this by auto-incrementing the version on each main branch push.

**Prevention:** Don't manually deploy the same version twice. Let the CI/CD pipeline manage versions.

## Node.js Action Deprecation Warnings

**Problem:** Warnings about Node.js 20 being deprecated in GitHub Actions, even after updating to compatible action versions.

**Root cause:** Actions are Node.js 24-compatible but still running on Node.js 20 by default until the June 2nd deadline.

**Complete solution (both steps required):**

1. Update actions to Node.js 24-compatible versions:
   - `actions/checkout@v2` → `actions/checkout@v4`
   - `s4u/maven-settings-action@v3.0.0` → `s4u/maven-settings-action@v3.1.0`
   - `actions/setup-java@v4` already compatible

2. **Force Node.js 24 execution** by adding environment variable to workflow:
   ```yaml
   jobs:
     build:
       runs-on: ubuntu-latest
       env:
         FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
   ```

**Important:** Simply updating action versions is not enough - you must also add the environment variable to actually run on Node.js 24 and eliminate warnings.

**Deadline:** Node.js 24 becomes default June 2, 2026; Node.js 20 removed September 16, 2026.

**How to apply:** When encountering build failures in FlossWare projects, check these common issues first. All FlossWare projects (jcollections, jremote, commons) use similar CI/CD patterns, so fixes often apply across projects.
