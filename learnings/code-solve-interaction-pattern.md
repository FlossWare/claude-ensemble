---
name: code-solve-interaction-pattern
description: "code-solve prompts user before pushing fixes, code-solve-auto auto-pushes"
metadata:
  type: feedback
  priority: critical
  originSessionId: cd831c80-3852-47b6-8899-f8cba2b22342
---

# Code Solve Interaction Pattern

**Rule**: code-solve should PROMPT user before pushing fixes, code-solve-auto auto-pushes

**Why**: User correction: "code-solve should prompt the user to push out fixes, where as code-solve-auto should just push them out automatically"

**How to apply**:

## Correct Pattern

### code-solve (base workflow)
- Finds issue
- Generates fix with multi-AI
- Applies fix locally
- Commits fix locally
- **Prompts**: "Push this fix to remote?"
- User decides: YES/NO
- Only pushes if user approves

### code-solve-auto (autonomous variant)
- Finds issue
- Generates fix with multi-AI
- Applies + verifies fix
- Commits automatically (if safe)
- **Auto-pushes** to remote
- NO user interaction
- 100% autonomous

## Current State

**code-solve.js**:
- Has `autonomous: true` in meta
- Auto-commits fixes
- **NEEDS FIX**: Should prompt before pushing
- May already be committing without pushing (need to verify)

**code-solve-auto.js**:
- ✅ Should auto-commit AND auto-push
- Currently only commits, doesn't push
- **NEEDS ENHANCEMENT**: Add auto-push step

## Required Fixes

### code-solve.js
1. Set `autonomous: false` (or remove)
2. After commit, show fix summary
3. **Ask user**: "Push fix for issue #X to remote? (YES/NO)"
4. Only push if user approves
5. Allow skipping push (keep local only)

### code-solve-auto.js
1. After successful commit, add auto-push step
2. Push to remote automatically
3. Update issue comment with "Fix pushed to remote"
4. Handle push failures gracefully

## Pattern Consistency

| Workflow | Base (Interactive) | Auto (Autonomous) |
|----------|-------------------|-------------------|
| **pr-review** | User approves/rejects | Auto approve/reject |
| **code-solve** | User decides to push | Auto push |
| **code-review** | User decides create issues | Auto create issues |

## Push vs Commit

**Important Distinction**:
- **Commit**: Local only (safe, reversible)
- **Push**: Remote (public, affects team)

Both workflows should:
- Always commit locally (needed for worktree cleanup)
- **code-solve**: Ask before pushing
- **code-solve-auto**: Auto-push if fix is safe

## Next Steps

1. Update code-solve.js to prompt before pushing
2. Update code-solve-auto.js to add auto-push
3. Add push failure handling
4. Test both workflows
5. Update documentation

## Related

- [[code-review-interaction-pattern]] - Same pattern for issues
- [[pr-review-auto-autonomous]] - PR review pattern
- [[autonomous-workflow-suite]] - Full suite overview
