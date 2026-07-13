#!/bin/bash
#
# Deploy Redis Stuck Task Recovery Daemon
#
# This script:
# 1. Copies systemd service file to /etc/systemd/system/
# 2. Reloads systemd daemon
# 3. Enables service for auto-start
# 4. Starts the service
# 5. Shows status
#
# Usage:
#   sudo ./scripts/deploy-recovery-daemon.sh

set -e

PROJECT_DIR="/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
SERVICE_FILE="redis-stuck-recovery.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_FILE}"

echo "=== Redis Stuck Task Recovery Daemon Deployment ==="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: This script must be run as root (use sudo)"
    exit 1
fi

# Check if service file exists
if [ ! -f "${PROJECT_DIR}/systemd/${SERVICE_FILE}" ]; then
    echo "❌ Error: Service file not found: ${PROJECT_DIR}/systemd/${SERVICE_FILE}"
    exit 1
fi

# Stop existing service if running
if systemctl is-active --quiet "${SERVICE_FILE}"; then
    echo "⏸  Stopping existing service..."
    systemctl stop "${SERVICE_FILE}"
fi

# Copy service file
echo "📋 Copying service file to ${SERVICE_PATH}..."
cp "${PROJECT_DIR}/systemd/${SERVICE_FILE}" "${SERVICE_PATH}"
chmod 644 "${SERVICE_PATH}"

# Reload systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable service
echo "✅ Enabling service for auto-start..."
systemctl enable "${SERVICE_FILE}"

# Start service
echo "▶️  Starting service..."
systemctl start "${SERVICE_FILE}"

# Wait a moment for startup
sleep 2

# Show status
echo
echo "=== Service Status ==="
systemctl status "${SERVICE_FILE}" --no-pager

echo
echo "=== Recent Logs ==="
journalctl -u "${SERVICE_FILE}" -n 20 --no-pager

echo
echo "✅ Deployment complete!"
echo
echo "Useful commands:"
echo "  sudo systemctl status ${SERVICE_FILE}    # Check status"
echo "  sudo systemctl stop ${SERVICE_FILE}      # Stop service"
echo "  sudo systemctl restart ${SERVICE_FILE}   # Restart service"
echo "  sudo journalctl -u ${SERVICE_FILE} -f    # Follow logs"
echo "  sudo systemctl disable ${SERVICE_FILE}   # Disable auto-start"
echo
