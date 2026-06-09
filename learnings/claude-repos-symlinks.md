---
name: claude-repos-symlinks
description: "Repos in ~/.claude/repos/ should be symlinks to actual git repos, not real directories"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 43c0d101-3691-456c-9ddf-7e0b1fd97c77
---

# Claude Repos Should Be Symlinks

**Rule**: Repositories in `~/.claude/repos/` should ALWAYS be symlinks to actual git repos, not the repos themselves.

**Why**: User explicitly stated: "yeah but shouldnt all be symlinks out to my local git repo"

**Reason**: 
- `~/.claude/` is for Claude Code configuration and cache
- Actual git repos should live in proper development directories
- Symlinks allow Claude Code to access repos while keeping them in their proper locations

**How to apply**:

### Correct Structure
```bash
# Real repo location
~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/
  ├── .git/
  ├── workflows/
  └── ...

# Symlink in Claude directory
~/.claude/repos/claude-global-skills → ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/
```

### How to Fix If Wrong

If a repo exists directly in `~/.claude/repos/` instead of as a symlink:

```bash
# 1. Move repo to proper location
mv ~/.claude/repos/repo-name ~/Development/path/to/repos/

# 2. Create symlink
ln -s ~/Development/path/to/repos/repo-name ~/.claude/repos/repo-name

# 3. Verify
ls -la ~/.claude/repos/  # Should show symlink with ->
```

### Detection

Check if it's a symlink:
```bash
ls -la ~/.claude/repos/
# Should show: lrwxrwxrwx ... repo-name -> /actual/path/to/repo
# NOT: drwxr-xr-x ... repo-name
```

## User's Repo Locations

**GitLab (Red Hat CEE)**: `~/Development/redhat/scm/gitlab/cee/sfloess/`
- Remote: `git@gitlab.cee.redhat.com:sfloess/<repo>.git`

**GitHub**: `~/Development/github/sfloess/`

**FlossWare**: `~/Development/FlossWare/sfloess/`

---

**Date**: 2026-06-05  
**Issue Found**: claude-global-skills was a real directory in ~/.claude/repos/ instead of symlink  
**Fixed**: Moved to proper GitLab location, created symlink  
**Status**: Always check this for new repos in ~/.claude/repos/
