#!/bin/bash
#
# Deploy Task Queue Workers to Fleet
#
# Installs task-worker@.service on all 8 worker nodes and starts daemons.
#
# Usage:
#   ./scripts/deploy-task-workers.sh [--start] [--stop] [--status] [--logs]
#
# Examples:
#   ./scripts/deploy-task-workers.sh --start     # Deploy and start
#   ./scripts/deploy-task-workers.sh --status    # Check status
#   ./scripts/deploy-task-workers.sh --logs      # Tail logs
#   ./scripts/deploy-task-workers.sh --stop      # Stop all workers

set -euo pipefail

# Fleet worker nodes (exclude orchestrator aio-01)
WORKERS=(
  server-01
  server-02
  server-03
  laptop-01
  pi-01
  pi-02
  desktop-ap
  server-ap
)

SSH_USER="claude"
SERVICE_FILE="systemd/task-worker@.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
log() {
  local color=$1
  shift
  echo -e "${color}$*${NC}"
}

# Check if service file exists
if [ ! -f "$PROJECT_ROOT/$SERVICE_FILE" ]; then
  log "$RED" "Error: Service file not found: $SERVICE_FILE"
  exit 1
fi

# Deploy service to a single worker
deploy_to_worker() {
  local host=$1

  log "$BLUE" "Deploying to $host..."

  # Copy service file
  scp -q "$PROJECT_ROOT/$SERVICE_FILE" "$SSH_USER@$host:/tmp/task-worker@.service"

  # Install service
  ssh "$SSH_USER@$host" bash <<'EOF'
    set -e

    # Move service file (requires sudo)
    if [ -f /tmp/task-worker@.service ]; then
      sudo mv /tmp/task-worker@.service /etc/systemd/system/
      sudo chown root:root /etc/systemd/system/task-worker@.service
      sudo chmod 644 /etc/systemd/system/task-worker@.service
    fi

    # Reload systemd
    sudo systemctl daemon-reload

    echo "Service installed successfully"
EOF

  log "$GREEN" "✓ Deployed to $host"
}

# Start worker on a single node
start_worker() {
  local host=$1

  log "$BLUE" "Starting worker on $host..."

  ssh "$SSH_USER@$host" bash <<EOF
    set -e
    sudo systemctl enable task-worker@$host.service
    sudo systemctl start task-worker@$host.service
    echo "Worker started"
EOF

  log "$GREEN" "✓ Started worker on $host"
}

# Stop worker on a single node
stop_worker() {
  local host=$1

  log "$BLUE" "Stopping worker on $host..."

  ssh "$SSH_USER@$host" bash <<EOF
    set -e
    sudo systemctl stop task-worker@$host.service || true
    sudo systemctl disable task-worker@$host.service || true
    echo "Worker stopped"
EOF

  log "$YELLOW" "✓ Stopped worker on $host"
}

# Check status on a single node
check_status() {
  local host=$1

  log "$BLUE" "Status on $host:"

  ssh "$SSH_USER@$host" bash <<EOF
    systemctl status task-worker@$host.service --no-pager --lines=5 || true
EOF

  echo ""
}

# Tail logs on a single node
tail_logs() {
  local host=$1

  log "$BLUE" "Logs from $host:"

  ssh "$SSH_USER@$host" bash <<EOF
    journalctl -u task-worker@$host.service -n 20 --no-pager || true
EOF

  echo ""
}

# Main command dispatcher
main() {
  local command=${1:-"--help"}

  case "$command" in
    --start)
      log "$GREEN" "===== DEPLOYING TASK WORKERS TO FLEET ====="
      for host in "${WORKERS[@]}"; do
        deploy_to_worker "$host"
        start_worker "$host"
      done
      log "$GREEN" "===== DEPLOYMENT COMPLETE ====="
      log "$YELLOW" "Check status: ./scripts/deploy-task-workers.sh --status"
      ;;

    --stop)
      log "$YELLOW" "===== STOPPING TASK WORKERS ====="
      for host in "${WORKERS[@]}"; do
        stop_worker "$host"
      done
      log "$YELLOW" "===== ALL WORKERS STOPPED ====="
      ;;

    --status)
      log "$GREEN" "===== TASK WORKER STATUS ====="
      for host in "${WORKERS[@]}"; do
        check_status "$host"
      done
      ;;

    --logs)
      log "$GREEN" "===== TASK WORKER LOGS ====="
      for host in "${WORKERS[@]}"; do
        tail_logs "$host"
      done
      ;;

    --restart)
      log "$YELLOW" "===== RESTARTING TASK WORKERS ====="
      for host in "${WORKERS[@]}"; do
        stop_worker "$host"
        start_worker "$host"
      done
      log "$GREEN" "===== RESTART COMPLETE ====="
      ;;

    --deploy-only)
      log "$GREEN" "===== DEPLOYING SERVICE FILES (NOT STARTING) ====="
      for host in "${WORKERS[@]}"; do
        deploy_to_worker "$host"
      done
      log "$GREEN" "===== DEPLOYMENT COMPLETE (services not started) ====="
      log "$YELLOW" "Start workers: ./scripts/deploy-task-workers.sh --start"
      ;;

    --help)
      cat <<HELP
Task Queue Worker Deployment Script

Usage:
  ./scripts/deploy-task-workers.sh [COMMAND]

Commands:
  --start         Deploy and start workers on all 8 nodes
  --stop          Stop all workers
  --restart       Restart all workers
  --status        Check status of all workers
  --logs          Tail logs from all workers
  --deploy-only   Deploy service files without starting
  --help          Show this help

Fleet Workers:
$(printf "  - %s\n" "${WORKERS[@]}")

Service File: $SERVICE_FILE

Examples:
  # Initial deployment
  ./scripts/deploy-task-workers.sh --start

  # Check status
  ./scripts/deploy-task-workers.sh --status

  # View logs
  ./scripts/deploy-task-workers.sh --logs

  # Restart after config change
  ./scripts/deploy-task-workers.sh --restart

HELP
      ;;

    *)
      log "$RED" "Unknown command: $command"
      log "$YELLOW" "Run --help for usage"
      exit 1
      ;;
  esac
}

main "$@"
