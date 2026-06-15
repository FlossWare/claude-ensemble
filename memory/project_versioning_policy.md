---
name: versioning-policy
description: "Project uses X.Y version format, every main commit is a release candidate"
metadata: 
  node_type: memory
  type: project
  originSessionId: 47d07339-1426-4013-ba1a-65875db76a2c
---

Project versioning policy:
- Versions use **X format** (single number only)
- Examples: 1, 2, 3, 4 (not 1.0, 1.1, or 1.0.0)
- Every commit to main is considered a **release candidate**

**Why:** Simplest versioning scheme. Just increment the number. Main branch is always releasable.

**How to apply:**
- When referencing versions in documentation, use X format (3 not 3.0 or v3)
- Don't create git tags - user manages those
- Every commit to main should be production-ready quality
- Release notes should use X naming convention (1, 2, 3...)

Related: [[no-version-management]] - User manages git tags
