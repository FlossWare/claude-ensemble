---
name: scm-plugin-message
description: Maven SCM plugin checkin command requires explicit commit message parameter
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

The maven-scm-plugin:checkin command requires an explicit `-Dmessage` parameter.

**Why:** Without the message parameter, the plugin fails with "Missing parameter: 'message'" error during CI/CD execution.

**How to apply:** Always use `mvn scm:checkin -Dmessage='commit message here'` format. In CI/CD workflows, use a dynamic message like `-Dmessage='chore: bump version to ${project.version}'`.
