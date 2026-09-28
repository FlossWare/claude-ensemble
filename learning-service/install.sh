#!/bin/bash
# Install RH Learning Service as systemd user service
# Usage: ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="claude-learning"
SERVICE_FILE="$SCRIPT_DIR/claude-learning.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "Installing RH Learning Service..."

# Ensure the service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "✗ Service file not found: $SERVICE_FILE"
    exit 1
fi

# Create systemd user directory
mkdir -p "$SYSTEMD_DIR"

# Copy service file
echo "Installing service file to $SYSTEMD_DIR/$SERVICE_NAME.service"
cp "$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_NAME.service"

# Make the service executable
chmod +x "$SCRIPT_DIR/learning_service.py"

# Reload systemd
echo "Reloading systemd user daemon..."
systemctl --user daemon-reload

# Enable the service
echo "Enabling $SERVICE_NAME service..."
systemctl --user enable "$SERVICE_NAME.service"

# Start the service
echo "Starting $SERVICE_NAME service..."
systemctl --user start "$SERVICE_NAME.service"

# Check status
echo ""
echo "Checking service status..."
systemctl --user status "$SERVICE_NAME.service" || true

echo ""
echo "✓ RH Learning Service installed and started"
echo ""
echo "Commands:"
echo "  systemctl --user status claude-learning.service     # Check status"
echo "  systemctl --user restart claude-learning.service    # Restart service"
echo "  journalctl --user -u claude-learning.service -f     # Follow logs"
echo ""
