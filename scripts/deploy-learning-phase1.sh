#!/bin/bash
#
# Deploy Learning System - Phase 1
#
# Deploys the learning infrastructure across the fleet:
#   1. Initialize databases on pi-02 (central coordinator)
#   2. Deploy shared/ code to all servers (via NFS verification)
#   3. Deploy learning/ code to server-01 (designated learner)
#   4. Create ~/.claude/learning/ directories on all nodes
#   5. Set permissions
#   6. Test database connectivity from every node
#
# Architecture:
#   pi-02 (arm64, sentinel)  - Central DB host, always-on coordinator
#   server-01                - Designated learner (daemon runs here)
#   server-02, server-03     - Workers (read-only DB access via NFS)
#   aio-01                   - NFS server, metrics (read-only DB access)
#
# Prerequisites:
#   - SSH key access to all fleet nodes (BatchMode)
#   - NFS mounted on all nodes (~/Development shared)
#   - Node.js installed on server-01, server-02, server-03
#   - better-sqlite3 npm package installed
#
# Usage:
#   ./scripts/deploy-learning-phase1.sh              # Full deployment
#   ./scripts/deploy-learning-phase1.sh --check      # Verify existing deployment
#   ./scripts/deploy-learning-phase1.sh --dry-run    # Show what would be done
#

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Fleet topology
CENTRAL_HOST="pi-02"                                    # Central DB + coordinator
LEARNER_HOST="server-01"                                 # Designated learner (daemon)
WORKER_HOSTS="server-01 server-02 server-03"             # All compute workers
ALL_HOSTS="server-01 server-02 server-03 aio-01 pi-02"  # Every fleet node

# Paths
DB_DIR="\$HOME/.claude/learning/db"
DB_PATH="\$HOME/.claude/learning/db/learning.db"
LEARNING_DIR="\$HOME/.claude/learning"
SHARED_DIR="$PROJECT_ROOT/shared"
LEARNING_SRC="$PROJECT_ROOT/learning"
INIT_SQL="$PROJECT_ROOT/learning/init-db.sql"

# SSH options: fast timeout, non-interactive, accept new host keys
SSH_OPTS="-o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

# Flags
DRY_RUN=false
CHECK_ONLY=false

# ============================================================================
# OUTPUT HELPERS
# ============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

pass()    { echo -e "  ${GREEN}[PASS]${NC} $1"; }
fail()    { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn()    { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
info()    { echo -e "  ${BLUE}[INFO]${NC} $1"; }
step()    { echo -e "\n${BOLD}Step $1: $2${NC}"; }
divider() { echo "=========================================="; }

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

for arg in "$@"; do
    case "$arg" in
        --check)   CHECK_ONLY=true ;;
        --dry-run) DRY_RUN=true ;;
        --help|-h)
            echo "Usage: $0 [--check | --dry-run | --help]"
            echo ""
            echo "  --check    Verify existing deployment status"
            echo "  --dry-run  Show what would be done without executing"
            echo "  --help     Show this help"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Use --help for usage"
            exit 1
            ;;
    esac
done

# ============================================================================
# HELPER: SSH wrapper (respects --dry-run)
# ============================================================================

remote_exec() {
    local host="$1"
    shift
    local cmd="$*"

    if $DRY_RUN; then
        info "[DRY-RUN] ssh $host: $cmd"
        return 0
    fi

    ssh $SSH_OPTS "$host" "$cmd" 2>/dev/null
}

remote_exec_stderr() {
    local host="$1"
    shift
    local cmd="$*"

    if $DRY_RUN; then
        info "[DRY-RUN] ssh $host: $cmd"
        return 0
    fi

    ssh $SSH_OPTS "$host" "$cmd"
}

# ============================================================================
# HELPER: Check SSH reachability
# ============================================================================

check_ssh() {
    local host="$1"
    ssh $SSH_OPTS "$host" "echo ok" &>/dev/null
}

# ============================================================================
# CHECK MODE
# ============================================================================

if $CHECK_ONLY; then
    divider
    echo "  Learning System Phase 1 - Deployment Status"
    divider
    echo ""

    # --- Central DB on pi-02 ---
    echo "Central Database (${CENTRAL_HOST}):"
    if check_ssh "$CENTRAL_HOST"; then
        pass "$CENTRAL_HOST reachable"

        if remote_exec "$CENTRAL_HOST" "test -f $DB_PATH"; then
            size=$(remote_exec "$CENTRAL_HOST" "du -h $DB_PATH | cut -f1")
            pass "Database exists ($size)"
        else
            fail "Database not found at $DB_PATH"
        fi

        if remote_exec "$CENTRAL_HOST" "test -d $DB_DIR"; then
            pass "DB directory exists"
        else
            fail "DB directory missing"
        fi
    else
        fail "$CENTRAL_HOST unreachable via SSH"
    fi
    echo ""

    # --- Learning directories on all nodes ---
    echo "Learning Directories:"
    for host in $ALL_HOSTS; do
        if check_ssh "$host"; then
            if remote_exec "$host" "test -d $LEARNING_DIR"; then
                pass "$host: $LEARNING_DIR exists"
            else
                fail "$host: $LEARNING_DIR missing"
            fi
        else
            fail "$host: unreachable"
        fi
    done
    echo ""

    # --- NFS / shared code access ---
    echo "Shared Code Access (NFS):"
    for host in $WORKER_HOSTS; do
        if check_ssh "$host"; then
            if remote_exec "$host" "test -f $SHARED_DIR/learning.js"; then
                pass "$host: shared/ accessible via NFS"
            else
                fail "$host: shared/ not accessible"
            fi
        else
            fail "$host: unreachable"
        fi
    done
    echo ""

    # --- Learning code on designated learner ---
    echo "Learning Code ($LEARNER_HOST):"
    if check_ssh "$LEARNER_HOST"; then
        if remote_exec "$LEARNER_HOST" "test -f $LEARNING_SRC/db.js"; then
            pass "learning/db.js accessible"
        else
            fail "learning/db.js not found"
        fi

        if remote_exec "$LEARNER_HOST" "test -f $LEARNING_SRC/calculate-lis.js"; then
            pass "learning/calculate-lis.js accessible"
        else
            fail "learning/calculate-lis.js not found"
        fi
    else
        fail "$LEARNER_HOST: unreachable"
    fi
    echo ""

    # --- DB connectivity from workers ---
    echo "Database Connectivity:"
    for host in $WORKER_HOSTS; do
        if check_ssh "$host"; then
            result=$(remote_exec "$host" "node -e \"
                const { createRequire } = require('module');
                try {
                    const Database = require('better-sqlite3');
                    const db = new Database('$DB_PATH', { readonly: true });
                    const r = db.prepare('SELECT COUNT(*) as c FROM execution_log').get();
                    console.log('OK:' + r.c);
                    db.close();
                } catch(e) { console.log('FAIL:' + e.message); }
            \"" 2>/dev/null || echo "FAIL:SSH error")

            if [[ "$result" == OK:* ]]; then
                count="${result#OK:}"
                pass "$host: DB readable ($count executions)"
            else
                reason="${result#FAIL:}"
                fail "$host: $reason"
            fi
        else
            fail "$host: unreachable"
        fi
    done
    echo ""

    # --- Permissions ---
    echo "Permissions:"
    if check_ssh "$CENTRAL_HOST"; then
        perms=$(remote_exec "$CENTRAL_HOST" "stat -c '%a' $DB_PATH 2>/dev/null || echo 'MISSING'")
        if [ "$perms" != "MISSING" ]; then
            if [ "$perms" = "664" ] || [ "$perms" = "644" ] || [ "$perms" = "660" ]; then
                pass "$CENTRAL_HOST: DB permissions $perms"
            else
                warn "$CENTRAL_HOST: DB permissions $perms (expected 664)"
            fi
        else
            fail "$CENTRAL_HOST: Cannot read DB permissions"
        fi
    fi
    echo ""

    divider
    echo "  Check complete"
    divider
    exit 0
fi

# ============================================================================
# DEPLOY MODE
# ============================================================================

divider
echo "  Learning System Phase 1 - Deployment"
divider
echo ""

if $DRY_RUN; then
    warn "DRY-RUN mode: no changes will be made"
    echo ""
fi

errors=0

# --------------------------------------------------------------------------
# Step 1: Verify prerequisites
# --------------------------------------------------------------------------

step 1 "Verify prerequisites"

# Check project structure
if [ ! -d "$SHARED_DIR" ]; then
    fail "shared/ directory not found at $SHARED_DIR"
    exit 1
fi
pass "shared/ directory exists ($(ls "$SHARED_DIR"/*.js 2>/dev/null | wc -l) JS files)"

if [ ! -d "$LEARNING_SRC" ]; then
    fail "learning/ directory not found at $LEARNING_SRC"
    exit 1
fi
pass "learning/ directory exists ($(ls "$LEARNING_SRC"/*.js 2>/dev/null | wc -l) JS files)"

if [ ! -f "$INIT_SQL" ]; then
    warn "init-db.sql not found at $INIT_SQL; inline schema in db.js will be used"
else
    pass "init-db.sql schema found"
fi

# Check SSH to all hosts
reachable=0
unreachable=0
for host in $ALL_HOSTS; do
    if check_ssh "$host"; then
        pass "$host: SSH reachable"
        reachable=$((reachable + 1))
    else
        fail "$host: SSH unreachable"
        unreachable=$((unreachable + 1))
        errors=$((errors + 1))
    fi
done

if [ $unreachable -gt 0 ]; then
    warn "$unreachable host(s) unreachable; deployment will skip those"
fi

# Verify Node.js on worker hosts
for host in $WORKER_HOSTS; do
    if check_ssh "$host"; then
        node_ver=$(remote_exec "$host" "node --version 2>/dev/null" || echo "MISSING")
        if [ "$node_ver" != "MISSING" ]; then
            pass "$host: Node.js $node_ver"
        else
            fail "$host: Node.js not installed"
            errors=$((errors + 1))
        fi
    fi
done

# --------------------------------------------------------------------------
# Step 2: Create ~/.claude/learning/ directories on all nodes
# --------------------------------------------------------------------------

step 2 "Create ~/.claude/learning/ directories"

for host in $ALL_HOSTS; do
    if check_ssh "$host"; then
        if $DRY_RUN; then
            info "[DRY-RUN] Would create $LEARNING_DIR and $DB_DIR on $host"
        else
            remote_exec_stderr "$host" "mkdir -p $LEARNING_DIR $DB_DIR 2>/dev/null" && \
                pass "$host: directories created" || \
                { fail "$host: failed to create directories"; errors=$((errors + 1)); }
        fi
    else
        warn "$host: skipped (unreachable)"
    fi
done

# --------------------------------------------------------------------------
# Step 3: Initialize database on pi-02 (central)
# --------------------------------------------------------------------------

step 3 "Initialize database on $CENTRAL_HOST (central)"

if check_ssh "$CENTRAL_HOST"; then
    # Check if DB already exists
    db_exists=$(remote_exec "$CENTRAL_HOST" "test -f $DB_PATH && echo yes || echo no")

    if [ "$db_exists" = "yes" ]; then
        info "Database already exists on $CENTRAL_HOST"
        size=$(remote_exec "$CENTRAL_HOST" "du -h $DB_PATH | cut -f1")
        info "Current size: $size"

        # Back it up before any changes
        if ! $DRY_RUN; then
            backup_name="learning.db.bak-$(date -u +%Y-%m-%dT%H-%M-%S)"
            remote_exec "$CENTRAL_HOST" "cp $DB_PATH ${DB_DIR}/${backup_name}" && \
                pass "Backup created: $backup_name" || \
                warn "Backup failed (continuing anyway)"
        fi
    else
        info "No existing database; will create fresh"
    fi

    # Deploy init-db.sql to pi-02 and initialize
    if [ -f "$INIT_SQL" ]; then
        if $DRY_RUN; then
            info "[DRY-RUN] Would copy init-db.sql to $CENTRAL_HOST:$LEARNING_DIR/"
            info "[DRY-RUN] Would initialize SQLite database"
        else
            scp $SSH_OPTS "$INIT_SQL" "$CENTRAL_HOST:$LEARNING_DIR/init-db.sql" && \
                pass "init-db.sql deployed to $CENTRAL_HOST" || \
                { fail "Failed to copy init-db.sql"; errors=$((errors + 1)); }

            # Initialize DB using sqlite3 (available on pi-02 as lightweight tool)
            # Try sqlite3 first, fall back to node if needed
            init_result=$(remote_exec_stderr "$CENTRAL_HOST" "
                if command -v sqlite3 &>/dev/null; then
                    sqlite3 $DB_PATH < $LEARNING_DIR/init-db.sql 2>&1 && echo 'OK:sqlite3'
                elif command -v node &>/dev/null; then
                    node -e \"
                        const Database = require('better-sqlite3');
                        const fs = require('fs');
                        const db = new Database('$DB_PATH');
                        const sql = fs.readFileSync('$LEARNING_DIR/init-db.sql', 'utf-8');
                        db.exec(sql);
                        db.close();
                        console.log('OK:node');
                    \" 2>&1
                else
                    echo 'FAIL:no sqlite3 or node available'
                fi
            " 2>/dev/null || echo "FAIL:ssh error")

            if [[ "$init_result" == OK:* ]]; then
                tool="${init_result#OK:}"
                pass "Database initialized via $tool on $CENTRAL_HOST"
            else
                reason="${init_result#FAIL:}"
                fail "Database initialization failed: $reason"
                errors=$((errors + 1))
            fi
        fi
    else
        # No init-db.sql; the db.js inline schema will handle it on first connect
        warn "No init-db.sql found; DB will self-initialize on first use via db.js inline schema"
    fi
else
    fail "$CENTRAL_HOST unreachable; cannot initialize central DB"
    errors=$((errors + 1))
fi

# --------------------------------------------------------------------------
# Step 4: Deploy shared/ code to all servers
# --------------------------------------------------------------------------

step 4 "Deploy shared/ code to all servers"

# NFS check: since ~/Development is shared via NFS from aio-01,
# the code is already available. Verify each node can see it.

nfs_ok=0
nfs_fail=0

for host in $WORKER_HOSTS; do
    if check_ssh "$host"; then
        if remote_exec "$host" "test -d $SHARED_DIR && test -f $SHARED_DIR/learning.js"; then
            pass "$host: shared/ accessible via NFS ($(remote_exec "$host" "ls $SHARED_DIR/*.js 2>/dev/null | wc -l") JS files)"
            nfs_ok=$((nfs_ok + 1))
        else
            fail "$host: shared/ NOT accessible via NFS"
            nfs_fail=$((nfs_fail + 1))
            errors=$((errors + 1))

            # Attempt rsync fallback for non-NFS nodes
            if ! $DRY_RUN; then
                info "Attempting rsync fallback to $host..."
                rsync -az --delete \
                    -e "ssh $SSH_OPTS" \
                    "$SHARED_DIR/" "$host:$SHARED_DIR/" 2>/dev/null && \
                    pass "$host: shared/ deployed via rsync" || \
                    fail "$host: rsync fallback also failed"
            fi
        fi
    else
        warn "$host: skipped (unreachable)"
    fi
done

# Also verify shared/ is readable from pi-02 and aio-01
for host in "pi-02" "aio-01"; do
    if check_ssh "$host"; then
        if remote_exec "$host" "test -d $SHARED_DIR"; then
            pass "$host: shared/ accessible"
        else
            warn "$host: shared/ not accessible (may not need it for this role)"
        fi
    fi
done

info "NFS verification: $nfs_ok OK, $nfs_fail failed"

# --------------------------------------------------------------------------
# Step 5: Deploy learning/ code to server-01 (designated learner)
# --------------------------------------------------------------------------

step 5 "Deploy learning/ code to $LEARNER_HOST (designated learner)"

if check_ssh "$LEARNER_HOST"; then
    # Verify NFS access to learning/ directory
    if remote_exec "$LEARNER_HOST" "test -d $LEARNING_SRC && test -f $LEARNING_SRC/db.js"; then
        pass "$LEARNER_HOST: learning/ accessible via NFS"
        file_count=$(remote_exec "$LEARNER_HOST" "ls $LEARNING_SRC/*.js 2>/dev/null | wc -l")
        pass "$LEARNER_HOST: $file_count JS files in learning/"
    else
        fail "$LEARNER_HOST: learning/ NOT accessible via NFS"
        errors=$((errors + 1))

        if ! $DRY_RUN; then
            info "Attempting rsync fallback..."
            rsync -az --delete \
                -e "ssh $SSH_OPTS" \
                "$LEARNING_SRC/" "$LEARNER_HOST:$LEARNING_SRC/" 2>/dev/null && \
                pass "$LEARNER_HOST: learning/ deployed via rsync" || \
                { fail "$LEARNER_HOST: rsync fallback failed"; errors=$((errors + 1)); }
        fi
    fi

    # Verify key files
    for f in db.js calculate-lis.js; do
        if remote_exec "$LEARNER_HOST" "test -f $LEARNING_SRC/$f"; then
            pass "$LEARNER_HOST: $f present"
        else
            fail "$LEARNER_HOST: $f missing"
            errors=$((errors + 1))
        fi
    done

    # Verify npm dependencies (better-sqlite3 needed)
    npm_check=$(remote_exec "$LEARNER_HOST" "
        node -e \"try { require('better-sqlite3'); console.log('OK'); } catch(e) { console.log('MISSING'); }\"
    " 2>/dev/null || echo "ERROR")

    if [ "$npm_check" = "OK" ]; then
        pass "$LEARNER_HOST: better-sqlite3 available"
    elif [ "$npm_check" = "MISSING" ]; then
        warn "$LEARNER_HOST: better-sqlite3 not installed"
        if ! $DRY_RUN; then
            info "Installing dependencies on $LEARNER_HOST..."
            remote_exec_stderr "$LEARNER_HOST" "cd $PROJECT_ROOT && npm install better-sqlite3 2>&1 | tail -3" && \
                pass "Dependencies installed on $LEARNER_HOST" || \
                { fail "npm install failed on $LEARNER_HOST"; errors=$((errors + 1)); }
        fi
    else
        warn "$LEARNER_HOST: Could not verify npm dependencies"
    fi

    # Copy init-db.sql to the learner's local learning directory
    if [ -f "$INIT_SQL" ] && ! $DRY_RUN; then
        remote_exec "$LEARNER_HOST" "
            if [ ! -f $LEARNING_DIR/init-db.sql ] || ! cmp -s $INIT_SQL $LEARNING_DIR/init-db.sql 2>/dev/null; then
                cp $INIT_SQL $LEARNING_DIR/init-db.sql 2>/dev/null
            fi
        " && pass "$LEARNER_HOST: init-db.sql synced to $LEARNING_DIR" || true
    fi
else
    fail "$LEARNER_HOST unreachable; cannot deploy learning code"
    errors=$((errors + 1))
fi

# --------------------------------------------------------------------------
# Step 6: Set permissions
# --------------------------------------------------------------------------

step 6 "Set permissions"

# Database file: rw for owner and group (NFS access)
if check_ssh "$CENTRAL_HOST"; then
    if $DRY_RUN; then
        info "[DRY-RUN] Would set DB permissions on $CENTRAL_HOST"
    else
        remote_exec "$CENTRAL_HOST" "
            if [ -f $DB_PATH ]; then
                chmod 664 $DB_PATH
                chmod 775 $DB_DIR
                chmod 775 $LEARNING_DIR
            fi
        " && pass "$CENTRAL_HOST: DB permissions set (664/775)" || \
            { warn "$CENTRAL_HOST: Failed to set DB permissions"; }
    fi
fi

# Learning directories: rwx for owner and group
for host in $ALL_HOSTS; do
    if check_ssh "$host"; then
        if $DRY_RUN; then
            info "[DRY-RUN] Would set directory permissions on $host"
        else
            remote_exec "$host" "
                chmod -R 775 $LEARNING_DIR 2>/dev/null
                chmod 775 $DB_DIR 2>/dev/null
            " && pass "$host: directory permissions set (775)" || \
                warn "$host: permission setting failed (may be NFS-restricted)"
        fi
    fi
done

# Shared code: read+execute for all (NFS-shared, read-only access fine)
if ! $DRY_RUN; then
    chmod -R 755 "$SHARED_DIR" 2>/dev/null && \
        pass "local: shared/ permissions set (755)" || \
        warn "local: shared/ permission update skipped"
fi

# --------------------------------------------------------------------------
# Step 7: Test database connectivity from all nodes
# --------------------------------------------------------------------------

step 7 "Test database connectivity"

db_ok=0
db_fail=0

for host in $WORKER_HOSTS; do
    if check_ssh "$host"; then
        if $DRY_RUN; then
            info "[DRY-RUN] Would test DB connectivity from $host"
            db_ok=$((db_ok + 1))
            continue
        fi

        result=$(remote_exec "$host" "node -e \"
            try {
                const Database = require('better-sqlite3');
                const db = new Database('$DB_PATH', { readonly: true });

                // Test 1: Can open
                const tables = db.prepare(\\\"SELECT count(*) as cnt FROM sqlite_master WHERE type='table'\\\").get();

                // Test 2: Can read schema version
                let version = 'unknown';
                try {
                    version = db.prepare(\\\"SELECT value FROM learning_metadata WHERE key='schema_version'\\\").get().value;
                } catch(e) { version = 'no metadata'; }

                // Test 3: Can read execution_log
                let execCount = 0;
                try {
                    execCount = db.prepare('SELECT COUNT(*) as c FROM execution_log').get().c;
                } catch(e) { execCount = -1; }

                db.close();
                console.log('OK:tables=' + tables.cnt + ',version=' + version + ',executions=' + execCount);
            } catch(e) {
                console.log('FAIL:' + e.message);
            }
        \"" 2>/dev/null || echo "FAIL:SSH/node error")

        if [[ "$result" == OK:* ]]; then
            details="${result#OK:}"
            pass "$host: DB connected ($details)"
            db_ok=$((db_ok + 1))
        else
            reason="${result#FAIL:}"
            fail "$host: DB connection failed ($reason)"
            db_fail=$((db_fail + 1))
            errors=$((errors + 1))
        fi
    else
        warn "$host: skipped (unreachable)"
    fi
done

# Also test from the central host if it has node
if check_ssh "$CENTRAL_HOST" && ! $DRY_RUN; then
    central_result=$(remote_exec "$CENTRAL_HOST" "
        if command -v node &>/dev/null; then
            node -e \"
                try {
                    const Database = require('better-sqlite3');
                    const db = new Database('$DB_PATH');
                    const r = db.prepare('SELECT COUNT(*) as c FROM execution_log').get();
                    console.log('OK:' + r.c);
                    db.close();
                } catch(e) { console.log('FAIL:' + e.message); }
            \"
        elif command -v sqlite3 &>/dev/null; then
            count=\$(sqlite3 $DB_PATH 'SELECT COUNT(*) FROM execution_log;' 2>/dev/null)
            if [ \$? -eq 0 ]; then
                echo \"OK:\$count\"
            else
                echo 'FAIL:sqlite3 query error'
            fi
        else
            echo 'SKIP:no node or sqlite3'
        fi
    " 2>/dev/null || echo "FAIL:SSH error")

    if [[ "$central_result" == OK:* ]]; then
        count="${central_result#OK:}"
        pass "$CENTRAL_HOST: central DB verified ($count executions)"
    elif [[ "$central_result" == SKIP:* ]]; then
        warn "$CENTRAL_HOST: cannot verify (no node or sqlite3 installed)"
    else
        reason="${central_result#FAIL:}"
        fail "$CENTRAL_HOST: central DB check failed ($reason)"
        errors=$((errors + 1))
    fi
fi

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
divider
echo "  Phase 1 Deployment Summary"
divider
echo ""
echo "  Central DB host:      $CENTRAL_HOST"
echo "  Designated learner:   $LEARNER_HOST"
echo "  Worker hosts:         $WORKER_HOSTS"
echo "  DB connectivity:      $db_ok OK, $db_fail failed"
echo ""

if [ $errors -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}Deployment successful - 0 errors${NC}"
else
    echo -e "  ${RED}${BOLD}Deployment completed with $errors error(s)${NC}"
fi

echo ""
echo "  Next steps:"
echo "    1. Verify: $0 --check"
echo "    2. Start learner daemon on $LEARNER_HOST:"
echo "       ssh $LEARNER_HOST"
echo "       cd $PROJECT_ROOT && ./deploy-learning-system.sh --start"
echo "    3. Monitor: ssh $CENTRAL_HOST sqlite3 $DB_PATH '.tables'"
echo "    4. Run a test workflow to generate first execution_log entries"
echo ""
divider

exit $errors
