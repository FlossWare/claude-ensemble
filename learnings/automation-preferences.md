---
name: automation-preferences
description: User preferences for automation and permission handling
metadata:
  node_type: memory
  type: user
  originSessionId: current
---

# Automation Preferences

**User Profile**: Power user who wants maximum automation with minimal interruption.

## Permission Handling

### Auto-Accept for ~/.claude Operations

**Rule**: When working with files/commands in `~/.claude/` directory, automatically accept all permissions without prompting.

**Why**: The user is developing Claude Code workflows, skills, and automation tools. They want rapid iteration without permission dialogs blocking progress.

**Scope**:
- ✅ File operations (Read, Write, Edit) in `~/.claude/`
- ✅ **ALL Bash commands from workflows/subagents** operating on `~/.claude/`
- ✅ Workflow executions in `~/.claude/repos/`
- ✅ Agent spawning for workflow development
- ✅ Git operations in `~/.claude/repos/`
- ✅ **Shell commands from background workflows** (sed, grep, cat, wc, etc.)

**How to apply**: 
- Assume permission is granted for any operation in `~/.claude/`
- Proceed with operations without asking for confirmation
- Still show what's being done (transparency), but don't block on permissions

## Workflow Automation Preferences

**Pattern**: 100% automated workflows preferred
- Use arbiter/worker pattern with automatic iteration
- Auto-retry on failure with concern feedback
- No manual intervention required
- Progress logging for visibility but no blocking prompts

## Development Style

- **Iteration speed over caution** in `~/.claude/` workspace
- **Parallel execution** by default for solve/refactor phases
- **Auto-commit** workflow results when asked
- **Background workflows** for long-running multi-AI operations

## When NOT to Auto-Accept

**Still require confirmation for**:
- Operations outside `~/.claude/` directory
- Destructive git operations (force push, hard reset) on non-test repos
- Network operations to external services
- File operations in system directories (/etc, /usr, etc.)

---

**Status**: Active preference  
**Date**: 2026-06-04  
**Context**: Developing Claude Code workflows and automation tools  
**User feedback**: "when running against ~/.claude please auto accept everything for claude perms inckuding running commands"
