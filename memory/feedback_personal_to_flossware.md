---
name: personal-to-flossware
description: Any personal content found in RH repos must be moved to ~/.FlossWare/claude with correct subdirectory structure
metadata:
  type: feedback
  priority: HIGH
---

# Personal Content Goes to FlossWare

## The Rule

When reviewing RH memory, repos, or files:

**IF you find personal/non-RH content:**
1. Move it to `~/.FlossWare/claude/{subdirectory}/` with the correct subdirectory
2. Remove it from the RH repo
3. Commit removal from RH repo with explanation

**Subdirectory structure:**
- `~/.FlossWare/claude/memory/` — personal memories
- `~/.FlossWare/claude/learning/` — learning artifacts, experiments
- `~/.FlossWare/claude/skills/` — personal skills
- `~/.FlossWare/claude/workflows/` — personal workflows
- `~/.FlossWare/claude/hooks/` — personal hooks
- etc. (mirror the structure from RH repo, but rooted in FlossWare)

## Why

- **Clean separation:** RH repos are strictly Red Hat work only
- **No leakage:** Personal infrastructure/learning doesn't appear in work repos
- **Shareable:** RH repos can be safely shared with team without exposing personal stuff

## How to Apply

Check whenever you:
- Review memory files
- Scan repo contents
- Find references to personal projects (orchestrator, cabin, personal learning, etc.)

If it's not strictly RH Disseminator work → move it.

## What This Fixes

Prevents personal/infrastructure details from bleeding into shared RH repositories.
