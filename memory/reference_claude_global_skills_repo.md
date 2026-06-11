---
name: claude-global-skills-repo
description: User has symlinked ~/.claude to a git repo for syncing skills, workflows, and memory across machines
metadata:
  type: reference
---

**Reference**: User's `~/.claude` directory is partially backed by a git repository

**Location**: `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills`

**Symlinks**:
- `~/.claude/docs` → `claude-global-skills/docs`
- `~/.claude/skills` → `claude-global-skills/skills`
- `~/.claude/workflows` → `repos/claude-global-skills`

**Git repository**: `gitlab.cee.redhat.com:sfloess/claude-global-skills.git`

**How to apply**:

When user says "push out everything from global" or "save that globally and push", they mean:

1. Save the memory/setting to `~/.claude/memory/` (global across all sessions)
2. ALSO copy it to `claude-global-skills/memory/`
3. Commit and push to the git repo

**Workflow**:
```bash
# Save memory to both locations
cp ~/.claude/memory/new-memory.md /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/memory/

# Commit and push
git -C /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills add memory/new-memory.md
git -C /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills commit -m "memory: description"
git -C /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills pull --rebase
git -C /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills push
```

**Why**: User syncs Claude Code configuration (skills, workflows, memory) across multiple machines via git. This is a backup AND sync strategy.

**Related**: [[feedback_minimal_docs_global]] - example of memory saved globally and pushed to repo
