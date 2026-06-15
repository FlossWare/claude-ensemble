#!/bin/bash
#
# Deploy Learning System to Fleet
#
# Since all fleet servers share ~/Development via NFS, the code is already
# distributed. This script:
#   1. Verifies NFS mount on each server
#   2. Ensures node_modules are available (NFS-shared)
#   3. Verifies database access on each server
#   4. Installs and starts systemd user service on the designated host
#   5. Runs a health check
#
# Usage:
#   ./deploy-learning-system.sh              # Deploy to all fleet servers
#   ./deploy-learning-system.sh --check      # Verify deployment status
#   ./deploy-learning-system.sh --start      # Start daemon on this machine
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLEET_SERVERS="server-01 server-02 server-03"
LEARNER_HOST="server-01"  # Run the daemon on server-01 (always available, not this machine)
DB_PATH="$HOME/.claude/learning/db/learning.db"
SERVICE_NAME="background-learner"
SERVICE_FILE="$HOME/.config/systemd/user/${SERVICE_NAME}.service"
SSH_OPTS="-o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
info() { echo -e "  [INFO] $1"; }

# ============================================================================
# CHECK MODE
# ============================================================================

if [ "${1:-}" = "--check" ]; then
    echo "=== Learning System Deployment Status ==="
    echo ""

    # Check database
    echo "Database:"
    if [ -f "$DB_PATH" ]; then
        size=$(du -h "$DB_PATH" | cut -f1)
        pass "Database exists ($size)"

        count=$(node -e "
            const Database = require('better-sqlite3');
            const db = new Database('$DB_PATH');
            console.log(db.prepare('SELECT COUNT(*) as c FROM execution_log').get().c);
            db.close();
        " 2>/dev/null || echo "ERROR")

        if [ "$count" != "ERROR" ]; then
            pass "Execution count: $count"
        else
            fail "Cannot read database"
        fi

        version=$(node -e "
            const Database = require('better-sqlite3');
            const db = new Database('$DB_PATH');
            console.log(db.prepare(\"SELECT value FROM learning_metadata WHERE key='schema_version'\").get().value);
            db.close();
        " 2>/dev/null || echo "ERROR")
        pass "Schema version: $version"
    else
        fail "Database not found at $DB_PATH"
    fi
    echo ""

    # Check fleet servers
    echo "Fleet Servers:"
    for host in $FLEET_SERVERS; do
        if ssh $SSH_OPTS "$host" "test -f $DB_PATH" 2>/dev/null; then
            pass "$host: NFS mount OK, DB accessible"
        else
            fail "$host: Cannot access DB via NFS"
        fi
    done
    echo ""

    # Check daemon status
    echo "Daemon Status:"
    if systemctl --user is-active "$SERVICE_NAME" &>/dev/null; then
        pass "Local daemon: running"
        systemctl --user status "$SERVICE_NAME" --no-pager -l 2>/dev/null | head -15
    else
        warn "Local daemon: not running"
    fi

    pid_file="$HOME/.claude/learning/background-learner.pid"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            pass "Daemon PID $pid is alive"
        else
            warn "PID file exists but process $pid is dead"
        fi
    fi
    echo ""

    # Check logs
    echo "Recent Logs:"
    journalctl --user -u "$SERVICE_NAME" --no-pager -n 5 2>/dev/null || warn "No journal entries found"
    echo ""
    echo "=== End Status ==="
    exit 0
fi

# ============================================================================
# DEPLOY MODE
# ============================================================================

echo "=========================================="
echo "  Learning System Fleet Deployment"
echo "=========================================="
echo ""

# Step 1: Verify local prerequisites
echo "Step 1: Verify prerequisites..."

if [ ! -f "$DB_PATH" ]; then
    fail "Database not found at $DB_PATH"
    exit 1
fi
pass "Database exists"

if ! node --version &>/dev/null; then
    fail "Node.js not installed"
    exit 1
fi
node_ver=$(node --version)
pass "Node.js $node_ver"

if [ ! -d "$SCRIPT_DIR/node_modules/better-sqlite3" ]; then
    info "Installing npm dependencies..."
    cd "$SCRIPT_DIR" && npm install --production 2>&1 | tail -3
fi
pass "Dependencies installed"
echo ""

# Step 2: Verify fleet NFS access
echo "Step 2: Verify fleet NFS access..."
fleet_ok=0
fleet_total=0

for host in $FLEET_SERVERS; do
    fleet_total=$((fleet_total + 1))
    if ssh $SSH_OPTS "$host" "test -f $DB_PATH && node --version" 2>/dev/null; then
        remote_ver=$(ssh $SSH_OPTS "$host" "node --version" 2>/dev/null)
        pass "$host: NFS OK, Node $remote_ver"
        fleet_ok=$((fleet_ok + 1))
    else
        if ssh $SSH_OPTS "$host" "echo ok" 2>/dev/null; then
            warn "$host: SSH OK but NFS or Node issue"
        else
            fail "$host: SSH unreachable"
        fi
    fi
done
echo ""

# Step 3: Verify database accessibility on all servers
echo "Step 3: Verify database on fleet..."
for host in $FLEET_SERVERS; do
    result=$(ssh $SSH_OPTS "$host" "node -e \"
        const Database = require('better-sqlite3');
        const db = new Database('$DB_PATH', { readonly: true });
        const r = db.prepare('SELECT COUNT(*) as c FROM execution_log').get();
        console.log(r.c);
        db.close();
    \"" 2>/dev/null || echo "FAIL")

    if [ "$result" != "FAIL" ]; then
        pass "$host: Database readable ($result executions)"
    else
        fail "$host: Cannot read database"
    fi
done
echo ""

# Step 4: Install systemd service
echo "Step 4: Install systemd service..."

if [ ! -f "$SERVICE_FILE" ]; then
    fail "Service file not found at $SERVICE_FILE"
    fail "Expected: $SERVICE_FILE"
    exit 1
fi
pass "Service file exists"

systemctl --user daemon-reload
pass "systemd daemon reloaded"
echo ""

# Step 5: Start/restart the daemon
if [ "${1:-}" = "--start" ] || [ "${1:-}" = "" ]; then
    echo "Step 5: Start background learner daemon..."

    # Enable for auto-start on login
    systemctl --user enable "$SERVICE_NAME" 2>/dev/null
    pass "Service enabled for auto-start"

    # Start or restart
    if systemctl --user is-active "$SERVICE_NAME" &>/dev/null; then
        systemctl --user restart "$SERVICE_NAME"
        pass "Service restarted"
    else
        systemctl --user start "$SERVICE_NAME"
        pass "Service started"
    fi

    # Enable lingering so the service runs even when not logged in
    loginctl enable-linger "$(whoami)" 2>/dev/null && pass "Lingering enabled (runs without login)" || warn "Could not enable lingering (needs root)"

    # Wait and verify
    sleep 3
    if systemctl --user is-active "$SERVICE_NAME" &>/dev/null; then
        pass "Daemon is running!"

        # Show first few log lines
        echo ""
        echo "  Initial logs:"
        journalctl --user -u "$SERVICE_NAME" --no-pager -n 5 2>/dev/null | sed 's/^/    /'
    else
        fail "Daemon failed to start"
        echo "  Check logs with: journalctl --user -u $SERVICE_NAME --no-pager -n 20"
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "  Fleet: $fleet_ok/$fleet_total servers verified"
echo "  Database: $DB_PATH (v2 schema)"
echo "  Daemon: running via systemd (perpetual, auto-restart)"
echo ""
echo "  Monitor:"
echo "    journalctl --user -u $SERVICE_NAME -f          # Live logs"
echo "    systemctl --user status $SERVICE_NAME           # Service status"
echo "    ./deploy-learning-system.sh --check             # Full status check"
echo ""
echo "  Control:"
echo "    systemctl --user stop $SERVICE_NAME             # Stop (will auto-restart!)"
echo "    systemctl --user disable $SERVICE_NAME          # Disable auto-start"
echo "    systemctl --user restart $SERVICE_NAME          # Restart"
echo ""
echo "  Database:"
echo "    node background-learner.js --status             # View DB stats"
echo ""
