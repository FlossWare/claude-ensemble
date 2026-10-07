#!/usr/bin/env bash
set -euo pipefail
CC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CC_VERSION="0.2"
CC_STATE_DIR="$HOME/.claude/.flossware-claude-config"
if [ -n "${FLOSSWARE_CLAUDE_CONFIG_STATE_DIR:-}" ]; then CC_STATE_DIR="$FLOSSWARE_CLAUDE_CONFIG_STATE_DIR"; fi
CC_MANIFEST="$CC_STATE_DIR/manifest.json"
CC_BACKUP_DIR="$CC_STATE_DIR/backups"
CC_LOCK_DIR="$CC_STATE_DIR/install.lock"
CC_HOOK_PATH="$HOME/.claude/hooks/memory-search-on-prompt.js"
CC_SETTINGS_PATH="$HOME/.claude/settings.json"
ok(){ printf '✓ %s\n' "$*"; }; warn(){ printf '⚠ %s\n' "$*" >&2; }; err(){ printf '✗ %s\n' "$*" >&2; }; die(){ err "$*"; exit 1; }
ensure_state(){ mkdir -p "$CC_STATE_DIR" "$CC_BACKUP_DIR"; }
acquire_lock(){ ensure_state; mkdir "$CC_LOCK_DIR" 2>/dev/null || die "another claude-config operation is already running"; trap 'rmdir "$CC_LOCK_DIR" 2>/dev/null || true' EXIT; }
backup_file(){ local src="$1"; [ -e "$src" ] || return 0; ensure_state; local dest="$CC_BACKUP_DIR/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$dest"; cp -a "$src" "$dest/"; }
detect(){
  local json_mode="false" claude="" memory_url="${FLOSSWARE_MEMORY_URL:-http://127.0.0.1:8767}"
  [ "$#" -gt 0 ] && json_mode="$1"
  command -v claude >/dev/null 2>&1 && claude="$(claude --version 2>/dev/null | head -1 || true)"
  local memory_status="unreachable"
  command -v curl >/dev/null 2>&1 && curl -fsS --max-time 1 "$memory_url/health" >/dev/null 2>&1 && memory_status="reachable" || true
  if [ "$json_mode" = true ]; then
    python3 - "$claude" "$memory_url" "$memory_status" "$CC_SETTINGS_PATH" "$CC_HOOK_PATH" <<'PY'
import json,os,sys
claude,url,status,settings,hook=sys.argv[1:]
print(json.dumps({"claude":{"installed":bool(claude),"version":claude},"memory":{"url":url,"status":status},"settings":{"path":settings,"exists":os.path.exists(settings)},"hook":{"path":hook,"exists":os.path.exists(hook)}},indent=2))
PY
    return
  fi
  [ -n "$claude" ] && ok "Claude Code: $claude" || warn "Claude Code executable not found"
  [ -d "$HOME/.claude" ] && ok "Claude configuration directory exists" || warn "~/.claude does not exist"
  [ -f "$CC_SETTINGS_PATH" ] && ok "User settings exist" || warn "User settings do not exist"
  [ -f "$CC_HOOK_PATH" ] && ok "Memory hook exists" || warn "Memory hook not installed"
  [ "$memory_status" = reachable ] && ok "Memory REST: $memory_url" || warn "Memory REST unavailable: $memory_url"
}
plan(){ python3 "$CC_ROOT/lib/json_tool.py" plan "$CC_SETTINGS_PATH" "$CC_HOOK_PATH"; }
verify(){
  local failed=0
  [ -d "$HOME/.claude" ] || { err "~/.claude missing"; failed=1; }
  [ -f "$CC_HOOK_PATH" ] || { err "memory hook missing"; failed=1; }
  [ -f "$CC_SETTINGS_PATH" ] || { err "settings.json missing"; failed=1; }
  if [ -f "$CC_SETTINGS_PATH" ]; then python3 - "$CC_SETTINGS_PATH" <<'PY' || failed=1
import json,sys
with open(sys.argv[1],encoding="utf-8") as f: json.load(f)
print("✓ settings.json is valid JSON")
PY
  fi
  if [ -f "$CC_HOOK_PATH" ] && command -v node >/dev/null 2>&1; then
    node --check "$CC_HOOK_PATH" >/dev/null 2>&1 || { err "memory hook JavaScript syntax invalid"; failed=1; }
    [ "$failed" -eq 0 ] && ok "memory hook JavaScript is valid"
  fi
  [ -f "$CC_MANIFEST" ] && ok "FlossWare manifest exists" || warn "FlossWare manifest missing"
  return "$failed"
}
doctor(){ detect; printf '\n'; verify || true; }
install(){
  local dry_run="false" force="false"
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --dry-run) dry_run="true";;
      --force) force="true";;
      --non-interactive);;
      *) die "unknown install option: $1";;
    esac
    shift
  done
  [ "$dry_run" = true ] && { plan; return; }
  acquire_lock; mkdir -p "$HOME/.claude/hooks"
  [ -f "$CC_SETTINGS_PATH" ] && backup_file "$CC_SETTINGS_PATH"
  if [ -f "$CC_HOOK_PATH" ]; then
    if ! grep -q "FlossWare Claude Ensemble Memory Hook" "$CC_HOOK_PATH" 2>/dev/null && [ "$force" != true ]; then
      die "conflict: existing hook is not managed by FlossWare; use --force after review"
    fi
    backup_file "$CC_HOOK_PATH"
  fi
  cp "$CC_ROOT/hooks/memory-search-on-prompt.js" "$CC_HOOK_PATH"; chmod 700 "$CC_HOOK_PATH"
  if [ -f "$CC_SETTINGS_PATH" ]; then python3 "$CC_ROOT/lib/json_tool.py" install-hook "$CC_SETTINGS_PATH" "$CC_HOOK_PATH"; else python3 "$CC_ROOT/lib/json_tool.py" create-settings "$CC_SETTINGS_PATH" "$CC_HOOK_PATH"; fi
  local sha; sha="$(sha256sum "$CC_HOOK_PATH" | awk '{print $1}')"
  python3 "$CC_ROOT/lib/json_tool.py" manifest "$CC_MANIFEST" "$CC_VERSION" "$CC_HOOK_PATH" "$sha"
  ok "Claude configuration installed/updated"; verify
}
uninstall(){
  acquire_lock; [ -f "$CC_MANIFEST" ] || die "no FlossWare manifest found; refusing unmanaged uninstall"
  [ -f "$CC_SETTINGS_PATH" ] && backup_file "$CC_SETTINGS_PATH"
  [ -f "$CC_HOOK_PATH" ] && rm -f "$CC_HOOK_PATH"
  python3 "$CC_ROOT/lib/json_tool.py" remove-hook "$CC_SETTINGS_PATH" "$CC_HOOK_PATH"
  rm -f "$CC_MANIFEST"; ok "FlossWare Claude configuration removed"
}
