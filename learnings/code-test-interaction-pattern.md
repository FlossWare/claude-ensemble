---
name: code-test-interaction-pattern
description: "code-test prompts user before creating issues, code-test-auto auto-creates"
metadata:
  type: feedback
  priority: critical
  originSessionId: cd831c80-3852-47b6-8899-f8cba2b22342
---

# Code Test Interaction Pattern

**Rule**: code-test should PROMPT user before creating issues, code-test-auto auto-creates

**Why**: User correction: "code-test should prompt the user to create issues where as code-test-auto should automatically create issus"

**How to apply**:

## Correct Pattern

### code-test (base workflow)
- Runs comprehensive tests (UI, integration, issue validation)
- Finds bugs/failures
- Shows test results to user
- **Prompts**: "Create issues for these X test failures?"
- User decides: YES/NO/SELECT
- Only creates issues if user approves

### code-test-auto (autonomous variant)
- Runs comprehensive tests
- Finds bugs/failures
- Verifies with multi-AI consensus
- **Auto-creates** issues for verified failures
- NO user interaction
- 100% autonomous

## Current State

**code-test.js**:
- ✅ FIXED: Changed to `autonomous: false` (interactive by default)
- ✅ FIXED: Added Impact Analysis phase
- ✅ FIXED: Added User Confirmation phase (prompts before creating)
- ✅ User options: ALL / HIGH_ONLY / CRITICAL_ONLY / REPRODUCED_ONLY / NONE

**code-test-auto.js**:
- ✅ COMPLETE: Fully autonomous testing bot
- ✅ Auto-creates issues for verified failures
- ✅ Enhanced impact analysis with boosted scores
- ✅ NO user interaction

## Implementation ✅ COMPLETE

### 1. code-test.js ✅
- ✅ Set `autonomous: false` (interactive by default)
- ✅ Added Impact Analysis phase (scores by severity + type)
- ✅ Shows detailed test failures summary
- ✅ **Prompts user**: "Create issues for these failures?"
- ✅ User options: ALL / HIGH_ONLY / CRITICAL_ONLY / REPRODUCED_ONLY / NONE
- ✅ Only creates issues user approves

### 2. code-test-auto.js ✅
- ✅ Full autonomous testing bot
- ✅ Runs all tests automatically
- ✅ Multi-AI verification of failures
- ✅ Enhanced impact analysis (UI, security, reproducibility boosts)
- ✅ Auto-creates issues for verified failures
- ✅ NO user interaction

## Pattern Consistency

| Workflow | Base (Interactive) | Auto (Autonomous) |
|----------|-------------------|-------------------|
| **pr-review** | User approves/rejects | Auto approve/reject |
| **code-solve** | User decides push | Auto push |
| **code-review** | User decides create issues | Auto create issues |
| **code-test** | User decides create issues | Auto create issues |

## code-test-auto Features

Should include:
- UI testing (if applicable)
- Integration testing
- Open issue verification
- Test result verification (multi-AI)
- Impact analysis of failures
- Auto-create issues for real failures
- Filter false positives
- Categorize by severity

## Next Steps

1. Create code-test-auto.js
2. Update code-test.js to prompt before creating issues
3. Add multi-AI verification to code-test-auto
4. Test both workflows
5. Update documentation

## Related

- [[code-review-interaction-pattern]] - Same pattern for code review
- [[code-solve-interaction-pattern]] - Same pattern for code solve
- [[autonomous-workflow-suite]] - Full suite (need to add code-test-auto)
