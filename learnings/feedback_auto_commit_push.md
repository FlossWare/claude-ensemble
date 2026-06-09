---
name: feedback_auto_commit_push
description: Always commit and push changes after fixes are applied
metadata:
  type: feedback
---

After code-solve fixes bugs or any changes are made, automatically commit and push to remote.

**Why:** User requested "we want to always commit and push out" - wants changes immediately visible on GitHub without manual intervention.

**How to apply:**
- After code-solve completes: commit the fix + push to remote
- After merging worktree fixes: commit + push immediately
- Don't ask permission to push - just do it
- Use descriptive commit messages with "Fixes #N"
- Include Co-Authored-By: Claude Code in commits
- Push to origin/main (or current branch)
- Verify push succeeded, retry once if it fails
- After push, confirm commit is visible on GitHub
