---
name: code-review-interaction-pattern
description: "code-review prompts user before creating issues, code-review-auto auto-creates"
metadata:
  type: feedback
  priority: critical
  originSessionId: cd831c80-3852-47b6-8899-f8cba2b22342
---

# Code Review Interaction Pattern

**Rule**: code-review should PROMPT user before creating issues, code-review-auto auto-creates

**Why**: User correction: "code-review should prompt the user to create issues wheres code-review-auto should automatically create issues"

**How to apply**: 

## Correct Pattern

### code-review (base workflow)
- Finds bugs/issues
- Shows findings to user
- **Prompts**: "Create issues for these X findings?"
- User decides: YES/NO/SELECT
- Only creates issues if user approves

### code-review-auto (autonomous variant)
- Finds bugs/issues
- Verifies with multi-AI consensus
- **Auto-creates** issues for verified findings
- NO user interaction
- 100% autonomous

## Current State

**code-review.js**:
- Currently has `autonomous: true` in meta
- Auto-creates issues without prompting
- **NEEDS FIX**: Should prompt user before creating

**code-review-auto.js**:
- ✅ Correct: Auto-creates issues
- ✅ Correct: No user prompts
- ✅ Correct: 100% autonomous

## Required Fix

Update `code-review.js` to:
1. Set `autonomous: false` (or remove - default is false)
2. After finding bugs, show summary
3. **Ask user**: "Create issues for these findings? (YES/NO/SELECT)"
4. Only create issues if user approves
5. Allow user to select which findings to create issues for

## Pattern Consistency

This matches the pattern across the suite:

| Workflow | Base (Interactive) | Auto (Autonomous) |
|----------|-------------------|-------------------|
| **pr-review** | User decides approve/reject | Auto approve/reject |
| **code-solve** | User decides commit/discard | Auto commit/discard |
| **code-review** | User decides create issues | Auto create issues |

## Next Steps

1. Update code-review.js to prompt before creating issues
2. Add user interaction for issue creation decision
3. Test both workflows to ensure correct behavior
4. Update documentation to clarify difference

## Related

- [[pr-review-auto-autonomous]] - PR review pattern (same concept)
- [[autonomous-workflow-suite]] - Full suite overview
- [[automation-preferences]] - User prefers automation when explicit
