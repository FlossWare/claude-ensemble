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
LAST_BACKUP=""
CC_TXN_ACTIVE="false"
CC_SETTINGS_EXISTED="false"
CC_HOOK_EXISTED="false"
CC_MANIFEST_EXISTED="false"
CC_SETTINGS_BACKUP=""
CC_HOOK_BACKUP=""
CC_MANIFEST_BACKUP=""
rollback_install(){
  local status="${1:-1}"
  [ "$CC_TXN_ACTIVE" = true ] || return "$status"
  warn "installation failed; rolling back all mutations"
  if [ "$CC_SETTINGS_EXISTED" = true ]; then cp -a "$CC_SETTINGS_BACKUP/settings.json" "$CC_SETTINGS_PATH"; else rm -f "$CC_SETTINGS_PATH"; fi
  if [ "$CC_HOOK_EXISTED" = true ]; then cp -a "$CC_HOOK_BACKUP/memory-search-on-prompt.js" "$CC_HOOK_PATH"; else rm -f "$CC_HOOK_PATH"; fi
  if [ "$CC_MANIFEST_EXISTED" = true ]; then cp -a "$CC_MANIFEST_BACKUP/manifest.json" "$CC_MANIFEST"; else rm -f "$CC_MANIFEST"; fi
  CC_TXN_ACTIVE="false"
  return "$status"
}
cleanup(){
  local status="$?"
  if [ "$CC_TXN_ACTIVE" = true ] && [ "$status" -ne 0 ]; then rollback_install "$status" || status=$?; fi
  rmdir "$CC_LOCK_DIR" 2>/dev/null || true
  exit "$status"
}
ok(){ printf '✓ %s\n' "$*"; }; warn(){ printf '⚠ %s\n' "$*" >&2; }; err(){ printf '✗ %s\n' "$*" >&2; }; die(){ err "$*"; exit 1; }
ensure_state(){ mkdir -p "$CC_STATE_DIR" "$CC_BACKUP_DIR"; }
acquire_lock(){ ensure_state; mkdir "$CC_LOCK_DIR" 2>/dev/null || die "another claude-config operation is already running"; trap cleanup EXIT; }
backup_file(){ local src="$1"; [ -e "$src" ] || { LAST_BACKUP=""; return 0; }; ensure_state; local dest="$CC_BACKUP_DIR/$(date +%Y%m%d-%H%M%S)-$$"; mkdir -p "$dest"; cp -a "$src" "$dest/"; LAST_BACKUP="$dest"; }
sha256_file(){
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    die "no SHA-256 utility found (need sha256sum or shasum)"
  fi
}
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
  if [ -f "$CC_SETTINGS_PATH" ]; then python3 "$CC_ROOT/lib/json_tool.py" validate-settings "$CC_SETTINGS_PATH" "$CC_HOOK_PATH" || failed=1; fi
  if [ -f "$CC_HOOK_PATH" ]; then
    if command -v node >/dev/null 2>&1; then
      node --check "$CC_HOOK_PATH" >/dev/null 2>&1 || { err "memory hook JavaScript syntax invalid"; failed=1; }
      [ "$failed" -eq 0 ] && ok "memory hook JavaScript is valid"
    else err "node executable not found; memory hook cannot be executed"; failed=1; fi
  fi
  if [ -f "$CC_MANIFEST" ]; then
    python3 "$CC_ROOT/lib/json_tool.py" validate-manifest "$CC_MANIFEST" "$CC_HOOK_PATH" || { err "FlossWare manifest is invalid"; failed=1; }
    if [ -f "$CC_HOOK_PATH" ] && [ "$failed" -eq 0 ]; then
      local expected actual
      expected="$(python3 "$CC_ROOT/lib/json_tool.py" manifest-sha "$CC_MANIFEST" "$CC_HOOK_PATH")"
      actual="$(sha256_file "$CC_HOOK_PATH")"
      [ "$expected" = "$actual" ] || { err "memory hook checksum does not match the FlossWare manifest"; failed=1; }
    fi
  else err "FlossWare manifest missing"; failed=1; fi
  local memory_url="${FLOSSWARE_MEMORY_URL:-http://127.0.0.1:8767}"
  if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 1 "$memory_url/health" >/dev/null 2>&1; then ok "Memory REST is reachable"; else warn "Memory REST is unavailable (hook will fail open)"; fi
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
  acquire_lock
  mkdir -p "$HOME/.claude/hooks"
  CC_SETTINGS_EXISTED="false"; CC_HOOK_EXISTED="false"; CC_MANIFEST_EXISTED="false"
  CC_SETTINGS_BACKUP=""; CC_HOOK_BACKUP=""; CC_MANIFEST_BACKUP=""
  [ -f "$CC_ROOT/hooks/memory-search-on-prompt.js" ] || die "source memory hook is missing"
  command -v node >/dev/null 2>&1 || die "node executable not found; cannot install the memory hook"
  node --check "$CC_ROOT/hooks/memory-search-on-prompt.js" >/dev/null 2>&1 || die "source memory hook JavaScript is invalid"
  if [ -f "$CC_SETTINGS_PATH" ]; then python3 "$CC_ROOT/lib/json_tool.py" validate-input "$CC_SETTINGS_PATH"; fi
  if [ -f "$CC_HOOK_PATH" ] && [ "$force" != true ]; then
    [ -f "$CC_MANIFEST" ] || die "conflict: existing memory hook has no FlossWare ownership manifest; use --force after review"
    python3 "$CC_ROOT/lib/json_tool.py" validate-manifest "$CC_MANIFEST" "$CC_HOOK_PATH" >/dev/null || die "conflict: existing managed hook cannot be verified against the FlossWare manifest; use --force after review"
    local expected actual
    expected="$(python3 "$CC_ROOT/lib/json_tool.py" manifest-sha "$CC_MANIFEST" "$CC_HOOK_PATH")"
    actual="$(sha256_file "$CC_HOOK_PATH")"
    [ "$expected" = "$actual" ] || die "conflict: managed memory hook was modified after installation; use --force after review"
  fi
  if [ -f "$CC_SETTINGS_PATH" ]; then CC_SETTINGS_EXISTED="true"; backup_file "$CC_SETTINGS_PATH"; CC_SETTINGS_BACKUP="$LAST_BACKUP"; fi
  if [ -f "$CC_HOOK_PATH" ]; then CC_HOOK_EXISTED="true"; backup_file "$CC_HOOK_PATH"; CC_HOOK_BACKUP="$LAST_BACKUP"; fi
  if [ -f "$CC_MANIFEST" ]; then CC_MANIFEST_EXISTED="true"; backup_file "$CC_MANIFEST"; CC_MANIFEST_BACKUP="$LAST_BACKUP"; fi
  CC_TXN_ACTIVE="true"
  cp "$CC_ROOT/hooks/memory-search-on-prompt.js" "$CC_HOOK_PATH"
  chmod 700 "$CC_HOOK_PATH"
  if [ -f "$CC_SETTINGS_PATH" ]; then python3 "$CC_ROOT/lib/json_tool.py" install-hook "$CC_SETTINGS_PATH" "$CC_HOOK_PATH"; else python3 "$CC_ROOT/lib/json_tool.py" create-settings "$CC_SETTINGS_PATH" "$CC_HOOK_PATH"; fi
  local sha; sha="$(sha256_file "$CC_HOOK_PATH")"
  python3 "$CC_ROOT/lib/json_tool.py" manifest "$CC_MANIFEST" "$CC_VERSION" "$CC_HOOK_PATH" "$sha"
  if ! verify; then return 1; fi
  CC_TXN_ACTIVE="false"
  ok "Claude configuration installed/updated"
}
uninstall(){
  acquire_lock
  [ -f "$CC_MANIFEST" ] || die "no FlossWare manifest found; refusing unmanaged uninstall"
  python3 "$CC_ROOT/lib/json_tool.py" validate-manifest "$CC_MANIFEST" "$CC_HOOK_PATH" >/dev/null || die "invalid FlossWare manifest; refusing uninstall"
  [ -f "$CC_SETTINGS_PATH" ] || die "settings.json missing; refusing uninstall"
  python3 "$CC_ROOT/lib/json_tool.py" validate-input "$CC_SETTINGS_PATH" >/dev/null || die "settings.json is invalid; refusing uninstall"
  if [ -f "$CC_HOOK_PATH" ]; then
    local expected actual
    expected="$(python3 "$CC_ROOT/lib/json_tool.py" manifest-sha "$CC_MANIFEST" "$CC_HOOK_PATH")"
    actual="$(sha256_file "$CC_HOOK_PATH")"
    [ "$expected" = "$actual" ] || die "managed hook was modified after installation; refusing to delete it"
  fi
  CC_SETTINGS_EXISTED="true"
  CC_HOOK_EXISTED="false"
  CC_MANIFEST_EXISTED="true"
  backup_file "$CC_SETTINGS_PATH"; CC_SETTINGS_BACKUP="$LAST_BACKUP"
  if [ -f "$CC_HOOK_PATH" ]; then CC_HOOK_EXISTED="true"; backup_file "$CC_HOOK_PATH"; CC_HOOK_BACKUP="$LAST_BACKUP"; fi
  backup_file "$CC_MANIFEST"; CC_MANIFEST_BACKUP="$LAST_BACKUP"
  CC_TXN_ACTIVE="true"
  if [ -f "$CC_HOOK_PATH" ]; then rm -f "$CC_HOOK_PATH"; fi
  python3 "$CC_ROOT/lib/json_tool.py" remove-hook "$CC_SETTINGS_PATH" "$CC_HOOK_PATH"
  rm -f "$CC_MANIFEST"
  CC_TXN_ACTIVE="false"
  ok "FlossWare Claude configuration removed"
}
