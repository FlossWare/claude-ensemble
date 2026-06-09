---
name: feedback_parallel_execution
description: "User wants parallel execution of independent work - don't serialize unnecessarily"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f3324023-02df-438a-bb60-0174b5bcd186
---

Run independent tasks in parallel. User values speed and efficiency.

**Why:** When presented with issues #60 and #61, user chose "both" (create issues AND fix), and I launched both code-solve workflows in parallel. User didn't object or ask to serialize them.

**How to apply:**
- Launch multiple code-solve workflows in parallel for independent bugs
- Use parallel tool calls in single message when operations are independent
- Don't wait for one fix to complete before starting another unless there's a dependency
- Use workflow parallel() for independent verification/testing tasks
