---
name: claude-code-permissions
description: "Claude Code permission system behavior - only first tool call succeeds in \"dontAsk\" mode, then everything blocks"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 182b6e77-c86f-414b-bd2a-462aaf609ee7
---

Claude Code permission system blocks all tool calls except the first one in "dontAsk" mode, even when settings say "allow all".

**Why:** User spent significant time trying to enable autonomous permissions but Claude Code kept blocking after the first tool call succeeded. Settings changes don't take effect until Claude Code restart.

**How to apply:** 
- Settings files: `~/.claude/settings.json` (global) and `.claude/settings.json` (project-level, overrides global)
- Project-level settings take precedence over global
- Settings only reload on Claude Code restart (not live)
- "dontAsk" mode means: prompt user for each permission
- "allow" mode means: auto-allow without prompting
- Symptom: First tool call works, all subsequent calls blocked → restart needed

**Correct global settings for autonomous mode:**
```json
{
  "permissions": {
    "mode": "allow",
    "allowed": ["*"]
  }
}
```

**Delete project-level settings** if they exist (they override global):
```bash
rm /path/to/project/.claude/settings.json
```

**Always restart Claude Code** after changing settings files.

Related: [[user_memorable_interactions]]
