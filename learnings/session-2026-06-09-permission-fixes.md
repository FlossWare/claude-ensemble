---
name: session-2026-06-09-permission-fixes
description: Critical learnings about Claude Code permission system and workflow fixes
metadata:
  type: feedback
  date: 2026-06-09
---

# Session Learnings: Permission System & Workflow Fixes

## Permission System Issues

### Issue: Sessions cache permissions at startup
- **Problem**: Changing settings.json doesn't affect running sessions
- **Why**: Claude Code caches permissions when session starts, never reloads
- **Fix**: Must restart session after changing permission settings
- **Impact**: Users get confused why changes don't take effect immediately

### Issue: "Don't ask again" button corrupts settings
- **Problem**: Clicking "Yes, and don't ask again" creates `"allow"` field instead of `"allowed"`
- **Why**: Bug in Claude Code permission dialog handler
- **Result**: Creates invalid JSON with both fields, permissions get more restrictive
- **Fix**: Never click option 2, always click option 1 ("Yes")
- **Workaround**: Created fix-permissions.sh script to auto-repair

### Issue: Old session directories hold cached state
- **Problem**: Even after restart, permissions still prompt
- **Why**: Named sessions in ~/.claude/projects/ may have cached permission state
- **Fix**: Delete session directories to force fresh sessions
- **Location**: `~/.claude/projects/-<path-with-dashes>/`

### Issue: dontAsk mode doesn't work reliably
- **Problem**: Setting `"mode": "dontAsk"` still prompts for permissions
- **Why**: Possible Claude Code bug, OR old sessions cached before change
- **Fix**: Delete old sessions + restart all Claude windows
- **Alternative**: Use `"mode": "allow"` with `"allowed": ["*", "Bash(*)"]`

## Permission Settings Hierarchy

1. **Project settings** (highest): `.claude/settings.json` in project directory
2. **User settings**: `~/.claude/settings.local.json`
3. **Global settings** (lowest): `~/.claude/settings.json`

**Best practice for autonomous workflows:**
- Set global `~/.claude/settings.json` to `"mode": "dontAsk"`
- Set user `~/.claude/settings.local.json` to `"mode": "dontAsk"`
- Create project `.claude/settings.json` with `"mode": "dontAsk"` for each project
- Run `fix-permissions.sh` to automate this across all projects

## Workflow Nesting Limitation

### Issue: code-sdlc-auto-continuous failed with nesting error
- **Problem**: Workflow tried to nest 3 levels deep (continuous → auto → sdlc → workflows)
- **Limit**: Claude Code workflows can only nest 1 level deep
- **Error**: "workflow() cannot be called from within a child workflow — nesting is limited to one level"

### Solutions Tried
1. ❌ **Inline all workflows** - Would lose reusability, create code duplication
2. ❌ **Call workflows at 2 levels** - Still hits nesting limit eventually
3. ✅ **Shell script workaround** - Each workflow runs in fresh session via `claude run`
4. ✅ **Workflow delegates to script** - workflow calls agent() which runs the shell script

### Final Solution
- Created `sdlc-loop.sh` - runs each workflow via `claude run` in fresh sessions
- Updated `code-sdlc-auto-continuous.js` - delegates to shell script via agent() call
- Each workflow runs in isolated session, no nesting
- Keeps workflows reusable (no duplication)

## Workflow Sandbox Limitations

### Issue: process.env.HOME not available in workflows
- **Problem**: `${process.env.HOME}/.claude/workflows` caused "process is not defined" error
- **Why**: Workflows run in sandboxed environment without Node.js process object
- **Fix**: Use `~/.claude/workflows` instead - Bash expands tilde to home directory
- **Rule**: Never use process, Date.now(), Math.random() in workflows

## Public Repository Creation

### Created clean public version
- **Location**: `/tmp/claude-global-skills-public/`
- **Changes**:
  - Removed all Red Hat references (emails, URLs, paths)
  - Changed `sfloess@redhat.com` → `scot.floess@gmail.com`
  - Changed `gitlab.cee.redhat.com` → `github.com`
  - Changed `~/Development/redhat/...` → `~/Projects/...`
  - Deleted Red Hat-specific memory files
  - Fresh git history (no Red Hat commits)
- **Status**: Ready to push to GitHub when user decides
- **Author**: All commits by Scot Floess <scot.floess@gmail.com>

## Fixes Applied

1. **code-sdlc-auto-continuous.js**
   - Now delegates to `sdlc-loop.sh` via agent()
   - Removed `process.env.HOME` reference
   - No more nesting errors

2. **Permission system**
   - Created `fix-permissions.sh` - sets dontAsk mode globally and per-project
   - Created `watch-settings.sh` - monitors for corruption
   - Updated all docs to recommend dontAsk mode

3. **Documentation**
   - CHANGELOG.md - documented nesting fix
   - PERMISSIONS.md - simplified to dontAsk mode first
   - README.md - added workflow option for continuous loop
   - code-sdlc-auto-continuous.md - complete rewrite

## User Preferences (from this session)

- Wants autonomous execution without permission prompts
- Prefers reusable solutions over code duplication
- Values shell scripts that work from any directory (PATH integration)
- Wants clean public repo separate from internal Red Hat version
- Frustrated by permission system complexity

## Recommendations

1. **For autonomous workflows**: Always use dontAsk mode, document session restart requirement
2. **For workflow nesting**: Use shell scripts, not workflow() calls beyond 1 level
3. **For sandboxed workflows**: Never use process.env, use ~ expansion instead
4. **For public releases**: Create separate git repo, rewrite history with clean author
5. **For session issues**: Delete old session directories when permissions get stuck
