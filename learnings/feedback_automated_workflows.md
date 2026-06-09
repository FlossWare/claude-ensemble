---
name: feedback_automated_workflows
description: User prefers automated multi-agent workflows over manual step-by-step work
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f3324023-02df-438a-bb60-0174b5bcd186
---

Use automated workflows (code-solve, code-review, app-test) instead of manual intervention. User values autonomous multi-agent approaches.

**Why:** User enthusiastically adopted code-solve and app-test workflows. When code-review found 8 bugs, user immediately ran code-solve rather than fixing manually. User requested app-test be created as a global workflow for reuse across projects.

**How to apply:**
- Suggest workflows proactively for repetitive tasks
- Use code-solve for bug fixes rather than manual edits
- Use code-review for quality checks rather than manual review
- Use app-test to verify changes work in practice
- Run workflows in parallel when tasks are independent (e.g., fixing multiple issues)
- Create new global workflows when patterns emerge
