#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
export FLOSSWARE_MEMORY_URL="http://127.0.0.1:9"
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

# Foreign hook conflict must refuse without --force.
rm -f "$HOME/.claude/hooks/memory-search-on-prompt.js"
printf '%s\n' '#!/bin/sh' 'echo foreign' > "$HOME/.claude/hooks/memory-search-on-prompt.js"
if bash "$ROOT/install.sh" --non-interactive; then
  echo "expected foreign hook conflict" >&2
  exit 1
fi

# --force replaces the foreign hook, with a backup created.
bash "$ROOT/install.sh" --non-interactive --force
grep -q "FlossWare Claude Ensemble Memory Hook" "$HOME/.claude/hooks/memory-search-on-prompt.js"
backup="$(find "$HOME/.claude/.flossware-claude-config/backups" -name 'memory-search-on-prompt.js' -print -quit)"
test -n "$backup"

# Lock must prevent concurrent mutation.
mkdir "$HOME/.claude/.flossware-claude-config/install.lock"
if bash "$ROOT/install.sh" --non-interactive; then
  echo "expected lock failure" >&2
  exit 1
fi
rmdir "$HOME/.claude/.flossware-claude-config/install.lock"

# Uninstall must refuse a modified managed hook.
printf '%s\n' '// modified' >> "$HOME/.claude/hooks/memory-search-on-prompt.js"
if bash "$ROOT/uninstall.sh"; then
  echo "expected modified-hook uninstall refusal" >&2
  exit 1
fi

# A clean uninstall succeeds.
cp "$ROOT/hooks/memory-search-on-prompt.js" "$HOME/.claude/hooks/memory-search-on-prompt.js"
bash "$ROOT/install.sh" --non-interactive
bash "$ROOT/uninstall.sh"
test ! -e "$HOME/.claude/hooks/memory-search-on-prompt.js"
test ! -e "$HOME/.claude/.flossware-claude-config/manifest.json"

# Rollback must restore an existing manifest instead of deleting it.
bash "$ROOT/install.sh" --non-interactive
manifest_before="$(cat "$HOME/.claude/.flossware-claude-config/manifest.json")"
mkdir -p "$TMP/fakebin"
cat > "$TMP/fakebin/node" <<'SH'
#!/bin/sh
exit 1
SH
chmod +x "$TMP/fakebin/node"
if PATH="$TMP/fakebin:/usr/bin:/bin" bash "$ROOT/install.sh" --non-interactive; then
  echo "expected verification failure" >&2
  exit 1
fi
test -f "$HOME/.claude/.flossware-claude-config/manifest.json"
test "$(cat "$HOME/.claude/.flossware-claude-config/manifest.json")" = "$manifest_before"

echo "claude-config tests passed"
