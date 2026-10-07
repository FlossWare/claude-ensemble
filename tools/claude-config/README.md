# Claude Config

Safe, idempotent Claude Code configuration for the FlossWare Claude Ensemble integration.

CLI and TUI share the same installation engine. The TUI uses FlossWare curses-tui for terminal rendering and delegates mutations to the CLI/core.

CLI:
  tools/claude-config/install.sh
  tools/claude-config/bin/claude-config detect
  tools/claude-config/bin/claude-config plan
  tools/claude-config/bin/claude-config verify
  tools/claude-config/bin/claude-config doctor

TUI:
  tools/claude-config/tui.sh

Safety:
- preserve existing Claude configuration
- merge UserPromptSubmit hooks
- track managed files in ~/.claude/.flossware-claude-config/manifest.json
- back up before mutation
- refuse unknown hook conflicts unless --force is supplied
- fail open when Memory REST is unavailable
- support dry-run and non-interactive operation
- serialize mutations with a lock

Memory defaults to http://127.0.0.1:8767 and POST /memory/search. Override with FLOSSWARE_MEMORY_URL.

Integration version: 0.2.
