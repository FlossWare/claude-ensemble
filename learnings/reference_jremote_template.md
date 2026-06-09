---
name: reference_jremote_template
description: jremote project at ../jremote serves as reference for project structure and tooling patterns
metadata: 
  node_type: memory
  type: reference
  originSessionId: 43468100-682a-41f1-8f56-f5c078edba57
---

The jremote project located at `/home/sfloess/Development/github/FlossWare/jremote` serves as a reference template for how user prefers FlossWare projects to be structured.

**Key patterns from jremote:**
- Version management using ci/rev-version.sh script
- Maven enforcer plugin with strict version rules (X.Y format, no snapshots)
- versions-maven-plugin for programmatic version updates
- Git workflow: commit with [ci skip], tag as vX.Y, push both

**Why:** User explicitly asked to "review the project at ../jremote and see how it handles reving versions" and wanted the same approach in jcollections.

**How to apply:** When user asks about project structure, tooling, or versioning conventions for FlossWare projects, check jremote for established patterns. If adding new infrastructure (CI scripts, Maven plugins, etc.), follow jremote's approach for consistency across the FlossWare ecosystem.
