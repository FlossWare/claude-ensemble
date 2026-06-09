---
name: feedback-git-workflow
description: User prefers squash merge workflow with branch cleanup for feature branches
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 94f4d6f1-3bcc-4b78-a0b9-7eca2b004c75
---

Use squash merge for feature branches, then delete both local and remote feature branches after merging to main.

**Why:** User explicitly requested "squash merge into main and push that out" followed by "remove both local and remote sfloess_initial branches." This keeps main branch history clean with meaningful commits instead of many small incremental commits.

**How to apply:**
1. When completing work on a feature branch, switch to main and use `git merge --squash feature-branch`
2. Create a comprehensive commit message summarizing all changes
3. Push to GitHub
4. Delete local branch: `git branch -D feature-branch`
5. Delete remote branch: `git push origin --delete feature-branch`

This workflow condenses many commits (in this case 22 commits) into one meaningful commit on main, while preserving all code changes. The detailed commit history is lost, but the final state is identical.
