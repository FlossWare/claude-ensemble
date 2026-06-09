---
name: naming-consistency
description: "Project name must be \"jremote\" - lowercase j, no prefix"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

Always refer to the project as "jremote" (lowercase 'j'), never "jRemote" or "FlossWare jremote".

**Why:** User explicitly corrected this terminology multiple times (2026-05-15). Consistent naming across all documentation and code is important for branding and clarity.

**How to apply:**
- Documentation files (README.md, etc.): Use "# jremote" as title
- pom.xml `<name>` tag: Use "jremote"
- In prose: "the jremote project" not "the FlossWare jremote project"
- Exception: Repository URLs and package names (org.flossware.jremote) remain unchanged for compatibility
