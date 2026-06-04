# Lesson: Consolidating Duplicate Git Clones with Symlinks

**Date:** 2026-06-04  
**Issue:** Two separate git clones of the same repo causing sync headaches  
**Solution:** One repo + symlinks = single source of truth

## The Problem

Initial structure had duplicate git repositories:

```
~/.claude/
├── workflows/.git  ← Full git clone
│   └── (files...)
├── skills/.git     ← DUPLICATE git clone of same remote!
│   └── (files...)
└── skills.backup/
```

**Issues:**
- Two separate `.git` directories
- Same remote URL in both
- Changes in one don't sync to the other automatically
- Push from `workflows/` doesn't update `skills/`
- Confusing: which is the "real" repo?
- Wasted disk space (2x all git history)

## The Solution

Consolidate to one repo with symlinks:

```
~/.claude/
├── repos/
│   └── claude-global-skills/  ← THE ONLY GIT REPO
│       ├── .git/
│       ├── code-solve.js
│       └── (all files)
├── workflows → repos/claude-global-skills/  ← SYMLINK
├── skills → repos/claude-global-skills/     ← SYMLINK
└── skills.backup/
```

## Migration Steps

```bash
# 1. Create repos directory
mkdir -p ~/.claude/repos

# 2. Move the repo with latest changes
mv ~/.claude/workflows ~/.claude/repos/claude-global-skills

# 3. Remove duplicate clone
rm -rf ~/.claude/skills

# 4. Create symlinks
ln -s repos/claude-global-skills ~/.claude/workflows
ln -s repos/claude-global-skills ~/.claude/skills

# 5. Verify both paths work
cd ~/.claude/workflows && git status  # Works!
cd ~/.claude/skills && git status     # Same repo!
```

## Benefits

### Single Source of Truth
- Only one `.git` directory
- No sync confusion
- One place to commit
- One place to push

### Easier Workflow
```bash
# Before (need to sync two repos):
cd ~/.claude/workflows
git commit -m "fix"
git push
cd ~/.claude/skills
git pull  # Don't forget!

# After (one repo, many paths):
cd ~/.claude/workflows  # OR ~/.claude/skills - same thing!
git commit -m "fix"
git push
# Done! All paths see the change
```

### Cleaner Organization
- `repos/` - actual git repositories
- `workflows/` - workspace reference (symlink)
- `skills/` - workspace reference (symlink)
- Clear separation between storage and workspace

## Verification

```bash
# All these point to the same repo:
ls -la ~/.claude/ | grep "skills\|workflows"
# lrwxrwxrwx ... skills -> repos/claude-global-skills
# lrwxrwxrwx ... workflows -> repos/claude-global-skills

# Both show same commit:
cd ~/.claude/workflows && git log -1
cd ~/.claude/skills && git log -1
# Identical!

# Changes in one appear in both:
cd ~/.claude/workflows && touch test.txt
cd ~/.claude/skills && ls test.txt
# File exists in both!
```

## When to Use This Pattern

**Use symlinked repos when:**
- Multiple workspace paths need to reference the same git repo
- Claude Code (or other tools) expect files at specific paths
- You want a single source of truth for version control
- Different tools/contexts need different "views" of the same repo

**Don't use when:**
- You actually need separate repos (different remotes, different history)
- You need true isolation between paths
- The tool doesn't support symlinks

## Related Pattern: Worktrees

For temporary isolation (like parallel issue solving), use git worktrees instead:

```bash
git worktree add .claude/worktrees/issue-123 main
# Isolated working copy, shared .git
```

Worktrees are for temporary work; symlinks are for permanent workspace aliases.

## Impact

- ✅ One `git push` instead of coordinating two repos
- ✅ No sync issues
- ✅ Clearer mental model
- ✅ Less disk space (one .git)
- ✅ Both `~/.claude/workflows` and `~/.claude/skills` work identically

## Links

- Original issue: Discovered during git consolidation discussion
- Pattern used: `repos/` + symlinks pattern
- Tools: `ln -s`, `mv`, `rm -rf`
