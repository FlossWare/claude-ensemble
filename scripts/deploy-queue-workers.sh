#!/bin/bash
#
# Deploy Queue Workers to Fleet
#
# Deploys store/chunk/embed/graph workers across fleet nodes
# with proper idempotency checking
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
API_DIR="$PROJECT_ROOT/api"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================================="
echo "DEPLOYING QUEUE WORKERS TO FLEET"
echo "=============================================================="
echo

# Worker configuration
# Format: hostname:worker_type:count
WORKERS=(
    "server-01:store:2"
    "server-02:store:2"
    "server-03:chunk:2"
    "laptop-01:embed:1"
    "aio-01:graph:1"
)

echo "Workers to deploy:"
for worker in "${WORKERS[@]}"; do
    echo "  - $worker"
done
echo

# Copy worker files to aio-01 (NFS mount point)
echo "[1] Copying worker files to aio-01..."
rsync -avz --progress \
    "$API_DIR/queue_worker_base.py" \
    "$API_DIR/store_worker.py" \
    aio-01:/exports/claude-orchestrator/api/

echo -e "${GREEN}✓${NC} Worker files copied"
echo

# Deploy workers to each node
deploy_worker() {
    local host=$1
    local worker_type=$2
    local count=$3

    echo "[2] Deploying ${worker_type} workers to ${host} (${count} instances)..."

    for i in $(seq 1 $count); do
        local worker_id="${worker_type}-worker-${host}-${i}"
        local log_file="/var/log/claude/${worker_type}-worker-${i}.log"

        echo "  Starting: $worker_id"

        # SSH to host and start worker
        ssh "$host" bash <<EOF
set -e

# Create log directory
mkdir -p /var/log/claude

# Kill existing worker with same ID (if any)
pkill -f "$worker_id" || true

# Start worker in background
cd /mnt/aio-01/claude-orchestrator/api || exit 1

nohup python3 ${worker_type}_worker.py > "$log_file" 2>&1 &
worker_pid=\$!

echo "Started $worker_id (PID: \$worker_pid)"
echo \$worker_pid > /var/run/${worker_type}-worker-${i}.pid

# Wait briefly and check if still running
sleep 2
if kill -0 \$worker_pid 2>/dev/null; then
    echo "✓ Worker is running"
else
    echo "✗ Worker failed to start"
    tail -20 "$log_file"
    exit 1
fi
EOF

        if [ $? -eq 0 ]; then
            echo -e "  ${GREEN}✓${NC} $worker_id started on $host"
        else
            echo -e "  ${RED}✗${NC} Failed to start $worker_id on $host"
        fi

        sleep 1
    done

    echo
}

# Deploy each worker configuration
for worker in "${WORKERS[@]}"; do
    IFS=':' read -r host type count <<< "$worker"
    deploy_worker "$host" "$type" "$count"
done

# Verify workers are registered
echo "[3] Verifying worker registration..."
echo

sleep 5

# Query worker heartbeat table
psql -h aio-01 -p 5433 -U sfloess -d learning <<SQL
SELECT
    worker_id,
    queue_name,
    last_seen,
    EXTRACT(EPOCH FROM (NOW() - last_seen)) as seconds_ago
FROM queue.worker_heartbeat
ORDER BY last_seen DESC;
SQL

echo
echo "=============================================================="
echo -e "${GREEN}QUEUE WORKERS DEPLOYED${NC}"
echo "=============================================================="
echo
echo "Next steps:"
echo "  1. Check worker logs: ssh <host> tail -f /var/log/claude/<type>-worker-1.log"
echo "  2. Monitor queue stats: curl http://aio-01:5000/queue/stats"
echo "  3. Run idempotency test: python3 $API_DIR/test_idempotency.py"
echo
