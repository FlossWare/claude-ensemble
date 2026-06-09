---
name: current-version
description: "jremote version 1.13 (as of 2026-05-18)"
metadata: 
  node_type: memory
  type: project
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

Current committed version: 1.13 (as of May 18, 2026). CI/CD workflow auto-increments minor version and deploys next version (1.14) to packagecloud.io on next push to main.

**Why:** Versioning follows X.Y format enforced by maven-enforcer-plugin. Each push to main triggers auto-increment, build, test, and deploy.

**How to apply:** When checking version, remember committed version may differ from deployed version by 1 (deployed = committed + 1). To skip packagecloud conflicts, manually bump committed version and push.
