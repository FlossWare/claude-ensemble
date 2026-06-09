---
name: feedback-naming-versioning
description: User preferences for jsecurity project naming and version format
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b8036c51-08a6-48f2-aa1c-41877b100b83
---

Use "jsecurity" (lowercase) consistently for project name references. Never use "FlossWare jSecurity" or "jSecurity" in documentation.

**Why:** User explicitly requested this change across all documentation. The project is simply "jsecurity" - the FlossWare organization context is understood from the GitHub URL.

**How to apply:**
- Documentation: "jsecurity" not "jSecurity" or "FlossWare jSecurity"
- JAR naming: `jsecurity-1.0.jar` not `jSecurity-1.0.0.jar`
- Code/config artifact IDs: `jsecurity` not `jSecurity`

---

Use X.Y versioning format (e.g., 1.0, 1.1) not X.Y.Z format (e.g., 1.0.0).

**Why:** User wants versioning to match the jcollections project approach. Maven enforcer plugin configured to validate X.Y format.

**How to apply:**
- pom.xml version: `<version>1.0</version>`
- Documentation examples: reference 1.0, 1.1, etc., never 1.0.0
- Git tags: `v1.0`, `v1.1`, not `v1.0.0`
- Auto-increment minor version only: 1.0 → 1.1 → 1.2
