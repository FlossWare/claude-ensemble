---
name: code-solve-squash-merge
description: "code-solve uses squash merges to keep main branch history clean"
metadata:
  type: project
  priority: high
  originSessionId: cd831c80-3852-47b6-8899-f8cba2b22342
---

# Code Solve Squash Merge Workflow

**Rule**: code-solve ALWAYS uses squash merges to main for clean history

**Why**: User requested "for code-solve always do squash merges to main when you commit" - keeps git history clean with one commit per issue fix

**How to apply**: Both code-solve and code-solve-auto automatically use squash merge workflow

## Workflow

**Steps**:
1. Detect current branch
2. If on main/master → create feature branch `fix/issue-N`
3. Commit fix to feature branch
4. Push feature branch to remote
5. **Squash merge** to main (creates single clean commit)
6. Delete feature branch (local + remote)
7. Close issue with commit reference

## Clean History Result

**Main branch shows**:
```
commit abc123
  fix: resolve issue #42 - authentication timeout
  
  Increase timeout from 10s to 30s in auth middleware
  
  Auto-fixed by code-solve-auto
  Confidence: 92%
  Risk: low
  
  Fixes #42

commit def456
  fix: resolve issue #43 - UI rendering bug
  
  Fixed race condition in component lifecycle
  
  Fixes #43
```

**NOT polluted with**:
- "WIP: trying fix for #42"
- "fix typo"
- "actually fix #42"
- "merge branch fix/issue-42"

## Feature Branch Pattern

**Format**: `fix/issue-N`

**Examples**:
- `fix/issue-42` → Fix for issue #42
- `fix/issue-127` → Fix for issue #127

**Lifecycle**:
1. Created automatically if on main
2. Pushed to remote (for backup/review)
3. Squash merged to main
4. Deleted after merge (local + remote)

## Benefits

**Clean History**:
- One commit per issue
- Easy to read git log
- Easy to revert if needed
- Clear what each commit does

**Better Collaboration**:
- Main branch is production-ready
- No intermediate/WIP commits
- Easy code review (one commit = one issue)
- Clean release notes

**Easier Operations**:
- Git bisect works better
- Cherry-picking is cleaner
- Rollbacks are simpler
- Release management easier

## Applies To

- ✅ **code-solve**: Squash merges when user approves push
- ✅ **code-solve-auto**: Squash merges automatically

## Related

- [[code-solve-interaction-pattern]] - Push prompts and automation
- [[autonomous-workflow-suite]] - All code-solve workflows
