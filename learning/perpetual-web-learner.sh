#!/bin/bash
#
# Perpetual Web Learner - Systemd Timer Wrapper
#
# Called by systemd timer every 6 hours. Handles environment setup,
# crash recovery, and exit code reporting.
#
# Usage:
#   ./perpetual-web-learner.sh          # Normal run (timer invocation)
#   ./perpetual-web-learner.sh --status # Show state
#   ./perpetual-web-learner.sh --dry-run # Preview
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_BIN="${NODE_BIN:-/usr/bin/node}"
LEARNER="$SCRIPT_DIR/perpetual-web-learner.js"
LOG_DIR="$HOME/.claude/learning/logs"
LOCK_FILE="$HOME/.claude/learning/perpetual-web-learner.lock"

mkdir -p "$LOG_DIR"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    lock_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
        echo "[perpetual-web-learner] Another instance running (PID $lock_pid). Skipping."
        exit 0
    fi
    # Stale lock file, remove it
    rm -f "$LOCK_FILE"
fi

# Write lock
echo $$ > "$LOCK_FILE"

cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

# Verify node
if ! command -v "$NODE_BIN" &>/dev/null; then
    echo "[perpetual-web-learner] ERROR: Node.js not found at $NODE_BIN" >&2
    exit 1
fi

# Verify learner script
if [ ! -f "$LEARNER" ]; then
    echo "[perpetual-web-learner] ERROR: Learner script not found at $LEARNER" >&2
    exit 1
fi

# Export tokens if available from user environment
# (systemd services may not inherit login shell exports)
if [ -f "$HOME/.config/environment.d/tokens.conf" ]; then
    set -a
    source "$HOME/.config/environment.d/tokens.conf" 2>/dev/null || true
    set +a
fi

# Also try .env file in learning directory
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env" 2>/dev/null || true
    set +a
fi

# Run the learner
exec "$NODE_BIN" "$LEARNER" "$@"
