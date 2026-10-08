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

# Legacy repository hook symlink must be replaced without modifying its target.
rm -f "$HOME/.claude/hooks/memory-search-on-prompt.js"
legacy_target="$TMP/legacy-claude-ensemble/hooks"
mkdir -p "$legacy_target" "$HOME/.claude/hooks" "$HOME/.claude/.flossware-claude-config"
cp "$ROOT/../../hooks/memory-search-on-prompt.js" "$legacy_target/memory-search-on-prompt.js"
ln -s "$legacy_target/memory-search-on-prompt.js" "$HOME/.claude/hooks/memory-search-on-prompt.js"
legacy_before="$(sha256sum "$legacy_target/memory-search-on-prompt.js" | awk '{print $1}')"
python3 "$ROOT/lib/json_tool.py" manifest   "$HOME/.claude/.flossware-claude-config/manifest.json"   "legacy"   "$HOME/.claude/hooks/memory-search-on-prompt.js"   "$legacy_before"
bash "$ROOT/install.sh" --non-interactive
test ! -L "$HOME/.claude/hooks/memory-search-on-prompt.js"
test -f "$HOME/.claude/hooks/memory-search-on-prompt.js"
test "$(sha256sum "$legacy_target/memory-search-on-prompt.js" | awk '{print $1}')" = "$legacy_before"

# Existing managed hook spellings must collapse to exactly one UserPromptSubmit entry.
python3 - "$HOME/.claude/settings.json" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p,encoding="utf-8"))
d["hooks"]["UserPromptSubmit"] = [
  {"hooks": [
    {"type":"command","command":"~/.claude/hooks/memory-search-on-prompt.js","timeout":3},
    {"type":"command","command":"/home/example/Development/FlossWare/claude-ensemble/hooks/memory-search-on-prompt.js","timeout":3}
  ]},
  {"hooks": [
    {"type":"command","command":"/home/example/.claude/hooks/memory-search-on-prompt.js","timeout":3},
    {"type":"command","command":"/custom/existing-hook"}
  ]}
]
json.dump(d,open(p,"w",encoding="utf-8"),indent=2)
PY
bash "$ROOT/install.sh" --non-interactive
python3 - "$HOME/.claude/settings.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
matches=[h for g in d["hooks"]["UserPromptSubmit"] for h in g["hooks"] if "memory-search-on-prompt.js" in h.get("command","")]
assert len(matches)==1, matches
PY

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
cp "$HOME/.claude/settings.json" "$TMP/install-settings.before"
cp "$HOME/.claude/hooks/memory-search-on-prompt.js" "$TMP/install-hook.before"
mkdir -p "$TMP/fakebin"
cat > "$TMP/fakebin/node" <<'SH'
#!/bin/sh
case "$2" in
  */tools/claude-config/hooks/memory-search-on-prompt.js) exit 0 ;;
  *) exit 1 ;;
esac
SH
chmod +x "$TMP/fakebin/node"
if PATH="$TMP/fakebin:/usr/bin:/bin" bash "$ROOT/install.sh" --non-interactive; then
  echo "expected verification failure" >&2
  exit 1
fi
test -f "$HOME/.claude/.flossware-claude-config/manifest.json"
test "$(cat "$HOME/.claude/.flossware-claude-config/manifest.json")" = "$manifest_before"
cmp "$HOME/.claude/settings.json" "$TMP/install-settings.before"
cmp "$HOME/.claude/hooks/memory-search-on-prompt.js" "$TMP/install-hook.before"

# Uninstall must roll back hook, settings, and manifest if settings removal fails.
bash "$ROOT/install.sh" --non-interactive
cp "$HOME/.claude/settings.json" "$TMP/uninstall-settings.before"
cp "$HOME/.claude/hooks/memory-search-on-prompt.js" "$TMP/uninstall-hook.before"
cp "$HOME/.claude/.flossware-claude-config/manifest.json" "$TMP/uninstall-manifest.before"
cat > "$TMP/fakebin/python3" <<'SH'
#!/bin/sh
if [ "$2" = "remove-hook" ]; then
  echo "injected remove-hook failure" >&2
  exit 1
fi
exec /usr/bin/python3 "$@"
SH
chmod +x "$TMP/fakebin/python3"
if PATH="$TMP/fakebin:$PATH" bash "$ROOT/uninstall.sh"; then
  echo "expected uninstall failure" >&2
  exit 1
fi
cmp "$HOME/.claude/settings.json" "$TMP/uninstall-settings.before"
cmp "$HOME/.claude/hooks/memory-search-on-prompt.js" "$TMP/uninstall-hook.before"
cmp "$HOME/.claude/.flossware-claude-config/manifest.json" "$TMP/uninstall-manifest.before"
rm -f "$TMP/fakebin/python3"
# A modified managed hook must not be overwritten without --force.
bash "$ROOT/install.sh" --non-interactive
printf '%s\n' '// user modification' >> "$HOME/.claude/hooks/memory-search-on-prompt.js"
if bash "$ROOT/install.sh" --non-interactive; then
  echo "expected modified managed hook conflict" >&2
  exit 1
fi
bash "$ROOT/install.sh" --non-interactive --force

# Uninstall must fail closed on malformed or incomplete ownership manifests.
manifest="$HOME/.claude/.flossware-claude-config/manifest.json"
cp "$manifest" "$TMP/valid-manifest.json"
printf '%s\n' '{"product":"flossware-claude-config"}' > "$manifest"
if bash "$ROOT/uninstall.sh"; then
  echo "expected malformed manifest refusal" >&2
  exit 1
fi
cp "$TMP/valid-manifest.json" "$manifest"
python3 - "$manifest" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p,encoding="utf-8"))
d["files"].pop(next(iter(d["files"])))
json.dump(d,open(p,"w",encoding="utf-8"))
PY
if bash "$ROOT/uninstall.sh"; then
  echo "expected missing manifest entry refusal" >&2
  exit 1
fi
cp "$TMP/valid-manifest.json" "$manifest"

# Hook commands must remain valid when HOME contains spaces.
rm -rf "$HOME/.claude"
export HOME="$TMP/home with spaces"
mkdir -p "$HOME/.claude"
bash "$ROOT/install.sh" --non-interactive
python3 - "$HOME/.claude/settings.json" "$HOME/.claude/hooks/memory-search-on-prompt.js" <<'PY'
import json,sys,shlex
settings=json.load(open(sys.argv[1],encoding="utf-8"))
command=next(h["command"] for g in settings["hooks"]["UserPromptSubmit"] for h in g["hooks"])
assert command == shlex.quote(sys.argv[2]), (command,sys.argv[2])
PY

# Standalone root hook must search local memory without a package.json.
mkdir -p "$HOME/.claude/memory"
cat > "$HOME/.claude/memory/multi-ai-rules.md" <<'MD'
---
name: multi-AI rules
description: Rules for multi-AI collaboration
type: reference
---
Use the multi-AI rules when coordinating reviewers and solvers.
MD
hook_output="$TMP/hook-output"
CLAUDE_PROMPT='Remember the multi-AI rules' \
  CLAUDE_MEMORY="$HOME/.claude/memory" \
  node "$ROOT/../../hooks/memory-search-on-prompt.js" 2>"$hook_output"
grep -q 'Memory Search: "the multi-AI rules"' "$hook_output"
grep -q 'multi-AI rules' "$hook_output"

python3 "$ROOT/tests/test-memory-sync.py"

echo "claude-config tests passed"
