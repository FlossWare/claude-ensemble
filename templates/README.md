# Claude Code Permission Templates

## auto-accept-all-operations.json
**Auto-accepts:** Bash, Write, Edit, Read

This template allows Claude Code to work autonomously without permission prompts for:
- ✅ All bash commands (git, tests, scripts, etc.)
- ✅ Creating new files (Write)
- ✅ Modifying existing files (Edit)
- ✅ Reading files (Read)

### Usage
```bash
# Copy to any project
cp ~/.claude/templates/auto-accept-all-operations.json /path/to/project/.claude/settings.json

# Or use the shortcut:
mkdir -p /path/to/project/.claude
cp ~/.claude/templates/auto-accept-all-operations.json /path/to/project/.claude/settings.json
```

### Quick Setup Script
```bash
# Add to ~/.bashrc or ~/.zshrc
claude-auto-accept() {
  mkdir -p "${1:-.}/.claude"
  cp ~/.claude/templates/auto-accept-all-operations.json "${1:-.}/.claude/settings.json"
  echo "✅ Claude auto-accept enabled for: ${1:-.}"
}
```

Then just run: `claude-auto-accept /path/to/project`
