#!/bin/bash
#
# Deploy Redis Queue Workers Across Fleet
#
# Deploys full-content scraping workers to all available fleet nodes.
# Workers pull URLs from Redis queues and fetch complete page content.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WORKER_SCRIPT="$SCRIPT_DIR/redis-queue-worker.py"

# Fleet configuration (6 workers — pi-02 excluded, runs Jellyfin)
WORKERS=(
    "server-01"
    "server-02"
    "server-03"
    "pi-01"
    "server-ap"
    "desktop-ap"
)

SSH_USER="claude"
REMOTE_DIR="/home/claude/workers"
LOG_DIR="/home/claude/workers/logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check worker script exists
    if [[ ! -f "$WORKER_SCRIPT" ]]; then
        log_error "Worker script not found: $WORKER_SCRIPT"
        exit 1
    fi

    # Check API is accessible (workers only talk to REST API, not Redis directly)
    if ! curl -sf http://aio-01:5000/health &>/dev/null; then
        log_error "API on aio-01:5000 is not accessible"
        exit 1
    fi

    log_info "Prerequisites OK"
}

install_dependencies() {
    local host=$1

    log_info "Installing dependencies on $host..."

    ssh ${SSH_USER}@${host} 'bash -s' <<'EOF'
        # Only dependency is requests (no redis, no bs4 needed)
        if ! python3 -c "import requests" 2>/dev/null; then
            echo "Installing requests..."
            if python3 -m pip install --user "requests" 2>&1 | grep -q "Successfully installed\|already satisfied"; then
                echo "  ✓ Installed requests with --user"
            elif python3 -m pip install --user --break-system-packages "requests" 2>&1 | grep -q "Successfully installed\|already satisfied"; then
                echo "  ✓ Installed requests with --break-system-packages"
            else
                echo "  ✗ Failed to install requests"
                exit 1
            fi
        else
            echo "  ✓ requests already installed"
        fi
        echo "Dependencies check complete"
EOF
}

deploy_worker() {
    local host=$1

    log_info "Deploying worker to $host..."

    ssh ${SSH_USER}@${host} "mkdir -p $REMOTE_DIR $LOG_DIR"

    # Copy worker script
    scp -q "$WORKER_SCRIPT" ${SSH_USER}@${host}:${REMOTE_DIR}/

    # Make executable
    ssh ${SSH_USER}@${host} "chmod +x ${REMOTE_DIR}/redis-queue-worker.py"

    log_info "Deployed to $host"
}

start_worker() {
    local host=$1

    log_info "Starting worker on $host..."

    # Check if worker already running
    if ssh ${SSH_USER}@${host} "pgrep -f redis-queue-worker.py" &>/dev/null; then
        log_warn "Worker already running on $host, stopping first..."
        stop_worker "$host"
    fi

    # Start worker in background (nohup); worker handles its own log file via FileHandler
    ssh ${SSH_USER}@${host} "nohup python3 ${REMOTE_DIR}/redis-queue-worker.py --hostname $host > /dev/null 2>&1 &"

    # Wait a moment and check if started
    sleep 2
    local pid
    pid=$(ssh ${SSH_USER}@${host} "pgrep -f redis-queue-worker.py" 2>/dev/null) || true
    if [[ -n "$pid" ]]; then
        log_info "Worker started on $host (PID: $pid)"
        return 0
    else
        log_error "Worker failed to start on $host"
        return 1
    fi
}

stop_worker() {
    local host=$1

    log_info "Stopping worker on $host..."

    ssh ${SSH_USER}@${host} "pkill -f redis-queue-worker.py || true"
    sleep 1

    if ssh ${SSH_USER}@${host} "pgrep -f redis-queue-worker.py" &>/dev/null; then
        log_warn "Worker still running on $host, force killing..."
        ssh ${SSH_USER}@${host} "pkill -9 -f redis-queue-worker.py || true"
    fi

    log_info "Worker stopped on $host"
}

check_worker_status() {
    local host=$1

    if ssh ${SSH_USER}@${host} "pgrep -f redis-queue-worker.py" &>/dev/null; then
        local pid=$(ssh ${SSH_USER}@${host} "pgrep -f redis-queue-worker.py")
        echo -e "${GREEN}✓${NC} $host: Running (PID: $pid)"

        # Show last 3 log lines
        ssh ${SSH_USER}@${host} "tail -3 ${LOG_DIR}/scraper-worker-${host}.log 2>/dev/null || echo '  (no logs yet)'"
    else
        echo -e "${RED}✗${NC} $host: Not running"
    fi
}

get_queue_status() {
    log_info "Queue status (via REST API):"
    curl -sf http://aio-01:5000/redis-queue/stats 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for q, n in sorted(d.get('queues', {}).items()):
        if n > 0:
            print(f'  {q}: {n} URLs')
    t = d.get('totals', {})
    print(f'  Total queued: {t.get(\"queued\", 0)}, completed: {t.get(\"completed\", 0)}, failed: {t.get(\"failed_count\", 0)}')
except:
    print('  (could not fetch queue stats)')
" 2>/dev/null || echo "  (API unreachable)"
}

deploy_all() {
    log_info "Deploying workers to ${#WORKERS[@]} fleet nodes..."

    local success=0
    local failed=0

    for worker in "${WORKERS[@]}"; do
        echo ""
        if install_dependencies "$worker" && deploy_worker "$worker" && start_worker "$worker"; then
            success=$((success + 1))
        else
            failed=$((failed + 1))
            log_error "Failed to deploy to $worker"
        fi
    done

    echo ""
    log_info "Deployment complete: $success succeeded, $failed failed"
}

status_all() {
    log_info "Worker status:"
    echo ""

    for worker in "${WORKERS[@]}"; do
        check_worker_status "$worker"
        echo ""
    done

    echo ""
    get_queue_status
}

stop_all() {
    log_info "Stopping all workers..."

    for worker in "${WORKERS[@]}"; do
        stop_worker "$worker"
    done

    log_info "All workers stopped"
}

show_logs() {
    local host=${1:-}

    if [[ -z "$host" ]]; then
        log_info "Available logs:"
        for worker in "${WORKERS[@]}"; do
            echo "  $worker: ssh ${SSH_USER}@${worker} tail -f ${LOG_DIR}/scraper-worker-${worker}.log"
        done
    else
        log_info "Showing logs for $host (Ctrl+C to exit)..."
        ssh ${SSH_USER}@${host} "tail -f ${LOG_DIR}/scraper-worker-${host}.log"
    fi
}

usage() {
    cat <<EOF
Usage: $0 [COMMAND]

Commands:
  deploy    Deploy and start workers on all fleet nodes (default)
  status    Check worker status on all nodes
  stop      Stop all workers
  logs      Show available log locations
  logs HOST Show logs for specific host

Examples:
  $0                  # Deploy to all workers
  $0 status           # Check status
  $0 logs server-01   # Tail logs from server-01
EOF
}

main() {
    local cmd=${1:-deploy}

    case "$cmd" in
        deploy)
            check_prerequisites
            deploy_all
            echo ""
            status_all
            ;;
        status)
            status_all
            ;;
        stop)
            stop_all
            ;;
        logs)
            show_logs "${2:-}"
            ;;
        -h|--help|help)
            usage
            ;;
        *)
            log_error "Unknown command: $cmd"
            usage
            exit 1
            ;;
    esac
}

main "$@"
