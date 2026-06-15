---
name: feedback_no_auto_issues
description: Never automatically create GitHub/GitLab issues after code reviews. User handles issue creation.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eef2a5e9-6453-4f04-a320-06ec8386a952
---

# Never Auto-Create Issues After Code Reviews

**Rule:** Do NOT automatically open GitHub/GitLab issues after completing code reviews.

**Why:** User explicitly instructed "do not open issues" after harness_cli review (2026-06-15). User prefers to review findings first and manually decide which issues to create.

**How to apply:**

After code reviews:
- ✅ Present findings in conversation
- ✅ Provide detailed bug reports with fixes
- ✅ Ask if user wants issues created (don't assume)
- ❌ Never auto-create issues without explicit request
- ❌ Never use `gh issue create` or GitLab API automatically

**When user DOES want issues:**
They will explicitly say:
- "Create issues for these findings"
- "Open a ticket for each bug"
- "File this in GitLab"

**Default behavior:**
Review findings → present to user → wait for instructions
