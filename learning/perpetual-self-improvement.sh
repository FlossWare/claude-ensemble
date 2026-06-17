#!/bin/bash
#
# Perpetual Self-Improvement - Systemd Timer Wrapper
#
# Called by systemd timer daily. Handles environment setup,
# crash recovery, and exit code reporting.
#
# NO STOPPING CONDITION. Runs indefinitely via timer.
#
# Usage:
#   ./perpetual-self-improvement.sh              # Normal run (timer invocation)
#   ./perpetual-self-improvement.sh --status     # Show state
#   ./perpetual-self-improvement.sh --research   # Research phase only
#   ./perpetual-self-improvement.sh --measure    # Measure phase only
#   ./perpetual-self-improvement.sh --experiment # Experiment phase only
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_BIN="${NODE_BIN:-/usr/bin/node}"
IMPROVER="$SCRIPT_DIR/perpetual-self-improvement.js"
LOG_DIR="$HOME/.claude/learning/logs"
LOCK_FILE="$HOME/.claude/learning/self-improvement.lock"

mkdir -p "$LOG_DIR"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    lock_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
        echo "[self-improvement] Another instance running (PID $lock_pid). Skipping."
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
    echo "[self-improvement] ERROR: Node.js not found at $NODE_BIN" >&2
    exit 1
fi

# Verify script
if [ ! -f "$IMPROVER" ]; then
    echo "[self-improvement] ERROR: Improver script not found at $IMPROVER" >&2
    exit 1
fi

# Export tokens if available from user environment
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

# Run the self-improvement cycle
exec "$NODE_BIN" "$IMPROVER" "$@"
