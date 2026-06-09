---
name: workflow-nesting-workaround
description: Shell script workaround for Claude Code's workflow nesting limitation
metadata:
  type: feedback
  date: 2026-06-09
  severity: critical
---

# Workflow Nesting Limitation & Shell Script Workaround

**Problem**: Claude Code workflows can only nest **1 level deep**. Attempting to call `workflow()` from within a child workflow fails with:

```
Error: workflow() cannot be called from within a child workflow — nesting is limited to one level
```

## Why This Matters

**BREAKING**: The `code-sdlc-auto-continuous` workflow was designed to call `workflow('code-sdlc-auto')` in a loop, which calls other workflows (`code-review-auto`, `code-solve-auto`, etc.). This creates **2 levels of nesting**, which is not allowed.

## The Wrong Solution: Inlining

**DON'T** inline all workflow code into one massive file:
- ❌ Creates code duplication
- ❌ Breaks reusability
- ❌ Maintenance nightmare (fix bugs in multiple places)
- ❌ Defeats the purpose of having separate workflows

## The Right Solution: Shell Script Orchestration

**DO** use a shell script to orchestrate workflows from outside:

```bash
#!/bin/bash
# Each `claude run` starts a FRESH Claude session (no nesting)
while [ $ITERATION -lt $MAX_ITERATIONS ]; do
  claude run code-review-auto +$BUDGET
  claude run code-solve-auto +$BUDGET
  claude run code-test-auto +$BUDGET
  claude run code-pr-review-auto +$BUDGET
  claude run code-security-auto +$BUDGET
  claude run code-doc-auto +$BUDGET
  claude run code-release-notes-auto +$BUDGET
  
  # Check if clean, break if done
  [ $ISSUES -eq 0 ] && break
done
```

## Benefits

✅ **No nesting** - Each workflow runs in a separate Claude session
✅ **Reusable** - Workflows stay independent and maintainable
✅ **No duplication** - Fix a bug once, it's fixed everywhere
✅ **Fresh permissions** - Each session loads current settings from disk
✅ **PATH integration** - Add to `~/.bashrc` for global access

## Implementation

Created: `~/.claude/workflows/sdlc-loop.sh`

**Setup:**
```bash
# Add to ~/.bashrc:
export PATH="$HOME/.claude/workflows:$PATH"

# Reload:
source ~/.bashrc

# Use from any project:
cd ~/any/project
sdlc-loop.sh 5 500k
```

## Lesson Learned

**When Claude Code has a limitation (like nesting), work WITH the platform, not against it:**
- Use shell scripts for orchestration
- Keep workflows modular and reusable
- Don't sacrifice maintainability for convenience

## Related Issues

- Workflow nesting depth: 1 level only
- Permission caching: Sessions cache permissions at startup (can't reload mid-session)
- Solution applies to any multi-workflow orchestration need

**Why:** This approach maintains the Unix philosophy - small, composable tools orchestrated by scripts.
