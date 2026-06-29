#!/bin/bash
#
# Background Learner Daemon Wrapper
# Handles crash recovery, log rotation, and perpetual operation.
# Designed to be called by systemd or run standalone.
#
# Usage:
#   ./background-learner-daemon.sh          # Run perpetually
#   ./background-learner-daemon.sh --once   # Single run (for testing)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_BIN="${NODE_BIN:-/usr/bin/node}"
LEARNER="$SCRIPT_DIR/background-learner.js"
DB_PATH="$HOME/.claude/learning/db/learning.db"
LOG_DIR="$HOME/.claude/learning/logs"
PID_FILE="$HOME/.claude/learning/background-learner.pid"
INTERVAL="${INTERVAL:-30}"
MAX_CONSECUTIVE_FAILURES=10

mkdir -p "$LOG_DIR"

# Write PID file for monitoring
echo $$ > "$PID_FILE"

cleanup() {
    rm -f "$PID_FILE"
    echo "[daemon] Shutdown complete at $(date -Iseconds)"
}
trap cleanup EXIT

# Verify database exists
if [ ! -f "$DB_PATH" ]; then
    echo "[daemon] ERROR: Database not found at $DB_PATH" >&2
    exit 1
fi

# Verify node is available
if ! command -v "$NODE_BIN" &>/dev/null; then
    echo "[daemon] ERROR: Node.js not found at $NODE_BIN" >&2
    exit 1
fi

if [ "${1:-}" = "--once" ]; then
    echo "[daemon] Single run mode"
    exec "$NODE_BIN" "$LEARNER"
fi

echo "[daemon] Starting perpetual background learner"
echo "[daemon] Interval: ${INTERVAL}s"
echo "[daemon] Database: $DB_PATH"
echo "[daemon] PID: $$"
echo "[daemon] Started at: $(date -Iseconds)"

consecutive_failures=0

# PERPETUAL LOOP - NO STOPPING CONDITION
while true; do
    if "$NODE_BIN" "$LEARNER" 2>&1; then
        consecutive_failures=0
    else
        exit_code=$?
        consecutive_failures=$((consecutive_failures + 1))
        echo "[daemon] Recompute failed (exit=$exit_code, consecutive=$consecutive_failures)" >&2

        if [ $consecutive_failures -ge $MAX_CONSECUTIVE_FAILURES ]; then
            echo "[daemon] Too many consecutive failures ($consecutive_failures). Pausing 5 minutes." >&2
            sleep 300
            consecutive_failures=0
        fi
    fi

    sleep "$INTERVAL"
done
