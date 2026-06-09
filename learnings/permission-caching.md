---
name: permission-caching
description: Claude Code sessions cache permissions at startup and never reload
metadata:
  type: feedback
  date: 2026-06-09
  severity: high
---

# Permission Caching in Claude Code Sessions

**Critical behavior**: Claude Code loads permissions **once at session startup** and caches them in memory for the entire session lifetime.

## The Problem

Even if you fix permissions in `~/.claude/settings.json` or delete restrictive project settings:
- ❌ Running Claude sessions **won't see the changes**
- ❌ No hot-reload mechanism exists
- ❌ No way to force a reload mid-session

## Why This Happens

**Security and performance design:**
1. **Security** - Prevents permission escalation (process can't modify its own permissions)
2. **Performance** - Permission checks happen constantly; caching is much faster
3. **Consistency** - Prevents unpredictable behavior from mid-flight permission changes

## What Gets Cached

```
Session Start → Load settings.json → Load settings.local.json → Cache in memory → Never reload
```

**Cached for entire session:**
- Global `~/.claude/settings.json`
- Global `~/.claude/settings.local.json`
- Project `.claude/settings.json`
- Project `.claude/settings.local.json`

## Settings Precedence Order

Claude loads settings in this order (later overrides earlier):
1. `~/.claude/settings.json` (global)
2. `~/.claude/settings.local.json` (user overrides) ← **Often the problem**
3. Project `.claude/settings.json`
4. Project `.claude/settings.local.json` ← **Also often the problem**

## Common Issue: settings.local.json Auto-Creation

When you click **"Yes, and don't ask again"** on a permission prompt:
- Claude creates/modifies `settings.local.json`
- Adds only THAT specific permission
- Uses wrong field `"allow"` instead of `"allowed"` (bug)
- Creates restrictive allowlist that blocks everything else

**Result**: Even with global `"allowed": ["*"]`, the local file overrides it with a restrictive list.

## The Solution

**For running sessions:**
- ✅ **Restart the session** (only way to reload permissions)
- ❌ No workaround exists

**For future sessions:**
1. Delete all project `.claude/settings*.json` files
2. Keep only global settings with wildcard:
   ```json
   {
     "permissions": {
       "mode": "allow",
       "allowed": [
         {
           "tool": "*",
           "match": ".*"
         }
       ]
     }
   }
   ```

3. **Never click "don't ask again"** - it creates restrictive local settings

## Shell Script Workaround

When using `sdlc-loop.sh`:
- ✅ Each `claude run` starts a **fresh session**
- ✅ Fresh sessions load current permissions from disk
- ✅ No restart needed between workflow runs

## How to Fix Stuck Sessions

**Check what's overriding:**
```bash
# Global
cat ~/.claude/settings.json
cat ~/.claude/settings.local.json

# Project (from project directory)
cat .claude/settings.json
cat .claude/settings.local.json
```

**Fix:**
```bash
# Remove restrictive overrides
rm ~/.claude/settings.local.json  # If it has restrictive rules
rm .claude/settings.local.json    # If it exists

# Restart Claude session
```

## Lesson Learned

1. **Permissions are sticky** - Session restart is the ONLY way to reload
2. **settings.local.json is dangerous** - Auto-created with restrictive rules
3. **Use global wildcard** - `"tool": "*", "match": ".*"` in `~/.claude/settings.json`
4. **Shell scripts bypass the issue** - Fresh session per workflow

## Related

- Workflow nesting limitation also benefits from shell scripts (fresh sessions)
- `.gitignore` should include `.claude` to prevent committing session data
