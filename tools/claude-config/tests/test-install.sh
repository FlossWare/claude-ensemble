#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
mkdir -p "$HOME/.claude"
cat > "$HOME/.claude/settings.json" <<'JSON'
{
  "permissions": {"allow": ["Bash(git status:*)"]},
  "hooks": {
    "UserPromptSubmit": [
      {"hooks": [{"type": "command", "command": "/custom/existing-hook"}]}
    ]
  }
}
JSON
bash "$ROOT/install.sh" --non-interactive
python3 - "$HOME/.claude/settings.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
hooks=d["hooks"]["UserPromptSubmit"]
assert any(h.get("command")=="/custom/existing-hook" for g in hooks for h in g["hooks"])
assert any("memory-search-on-prompt.js" in h.get("command","") for g in hooks for h in g["hooks"])
assert d["permissions"]["allow"]
PY
bash "$ROOT/install.sh" --non-interactive
python3 - "$HOME/.claude/settings.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
hooks=d["hooks"]["UserPromptSubmit"]
matches=[h for g in hooks for h in g["hooks"] if "memory-search-on-prompt.js" in h.get("command","")]
assert len(matches)==1, matches
PY
echo "claude-config tests passed"
