#!/bin/bash
set -e

# Deploy auto-storage workers to fleet nodes as systemd services
# Usage: ./deploy_workers.sh

SCRIPT="/tmp/auto_storage_system.py"
SERVICE_TEMPLATE="/tmp/auto-storage-worker@.service"

# Node configurations: "hostname:user:worker_id"
NODES=(
  "server-01:claude:0"
  "server-02:claude:1"
  "server-03:claude:2"
  "aio-01:sfloess:3"
  "laptop-01:sfloess:4"
)

echo "=== Auto-Storage Worker Deployment ==="
echo "Script: $SCRIPT"
echo "Nodes: ${#NODES[@]}"
echo ""

# Check if script exists
if [[ ! -f "$SCRIPT" ]]; then
  echo "ERROR: $SCRIPT not found"
  exit 1
fi

# Check if service template exists
if [[ ! -f "$SERVICE_TEMPLATE" ]]; then
  echo "ERROR: $SERVICE_TEMPLATE not found"
  exit 1
fi

# Deploy to each node
for node_config in "${NODES[@]}"; do
  IFS=':' read -r hostname user worker_id <<< "$node_config"

  echo "--- Deploying to $hostname (user=$user, worker_id=$worker_id) ---"

  # Copy script
  echo "Copying script..."
  scp -o LogLevel=ERROR -q "$SCRIPT" "${hostname}:/tmp/" 2>&1 || echo "  Warning: scp to $hostname may have failed"

  # Make executable
  ssh -o LogLevel=ERROR "$hostname" "chmod +x /tmp/auto_storage_system.py" 2>&1 || true

  # Copy service file
  echo "Copying service template..."
  scp -o LogLevel=ERROR -q "$SERVICE_TEMPLATE" "${hostname}:/tmp/" 2>&1 || echo "  Warning: scp to $hostname may have failed"

  # Install service
  echo "Installing systemd service..."
  ssh -o LogLevel=ERROR "$hostname" "sudo cp /tmp/auto-storage-worker@.service /etc/systemd/system/" 2>&1 || true

  # Reload systemd
  ssh -o LogLevel=ERROR "$hostname" "sudo systemctl daemon-reload" 2>&1 || true

  # Enable and start service
  echo "Starting auto-storage-worker@${user}.service..."
  ssh -o LogLevel=ERROR "$hostname" "sudo systemctl enable auto-storage-worker@${user}.service" 2>&1 || true
  ssh -o LogLevel=ERROR "$hostname" "sudo systemctl restart auto-storage-worker@${user}.service" 2>&1 || true

  # Check status
  echo "Status:"
  ssh -o LogLevel=ERROR "$hostname" "sudo systemctl status auto-storage-worker@${user}.service --no-pager -l" 2>&1 || true

  echo ""
done

echo "=== Deployment Complete ==="
echo ""
echo "Check logs with:"
echo "  ssh <hostname> journalctl -u auto-storage-worker@<user>.service -f"
echo ""
echo "Check status with:"
echo "  ssh <hostname> systemctl status auto-storage-worker@<user>.service"
