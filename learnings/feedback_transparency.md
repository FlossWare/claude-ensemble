---
name: feedback_transparency
description: User requires complete transparency - create GitHub issues for all findings before fixing
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f3324023-02df-438a-bb60-0174b5bcd186
---

Always create GitHub issues for bugs/findings before fixing them. User wants full visibility and tracking.

**Why:** User explicitly requested "complete transparency" when asked whether to create issues or fix directly. When given option "1. create issues, 2. fix directly, 3. both", user chose option 3.

**How to apply:** 
- After code-review: create issues for all findings, then run code-solve
- After app-test: create issues for failures, then fix
- Never silently fix bugs without documenting them in the issue tracker
- Default to "both" when offering fix options
