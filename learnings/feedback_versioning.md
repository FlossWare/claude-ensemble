---
name: feedback-versioning
description: "User requires strict X.Y versioning format, not X.Y.Z or build numbers"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0cfee593-446f-468f-9568-41f1f8d2a5ad
---

User explicitly requires X.Y versioning format (e.g., 1.22, 1.23) with NO additional components.

**Why:** When I initially implemented X.Y.Z versioning with build numbers, user immediately corrected with "oh no I want the versioning to be X.Y" - indicating a strong organizational or team standard for two-component semantic versioning.

**How to apply:** For any versioning suggestions in Maven, GitLab CI/CD, or release management:
- Use major.minor format only (X.Y)
- Auto-increment minor version on main branch releases
- Use -SNAPSHOT suffix for feature branches, but keep base version as X.Y
- Never add build numbers, patch versions, or timestamps to release versions
