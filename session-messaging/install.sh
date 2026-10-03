#!/bin/bash
# Install Claude Ensemble Session Messaging Service
# Sets up systemd user service for inter-session pub/sub messaging

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="claude-messenger"
SERVICE_TEMPLATE="$REPO_ROOT/session-messaging/${SERVICE_NAME}.service.template"
SERVICE_DIR="$HOME/.config/systemd/user"

if [ ! -f "$SERVICE_TEMPLATE" ]; then
    echo "Error: Service template not found at $SERVICE_TEMPLATE"
    exit 1
fi

# Create systemd user directory if it doesn't exist
mkdir -p "$SERVICE_DIR"

# Install service file with repo path substitution
echo "Installing $SERVICE_NAME systemd user service..."
sed "s|%REPO_PATH%|$REPO_ROOT|g" "$SERVICE_TEMPLATE" > "$SERVICE_DIR/${SERVICE_NAME}.service"
chmod 644 "$SERVICE_DIR/${SERVICE_NAME}.service"

# Reload systemd configuration
echo "Reloading systemd configuration..."
"$SYSTEMCTL_BIN" --user daemon-reload

# Enable service (auto-start on login)
echo "Enabling $SERVICE_NAME service (auto-start)..."
"$SYSTEMCTL_BIN" --user enable "${SERVICE_NAME}.service"

# Start service immediately
echo "Starting $SERVICE_NAME service..."
"$SYSTEMCTL_BIN" --user start "${SERVICE_NAME}.service"

# Verify
echo ""
echo "Installation complete!"
echo ""
echo "Service status:"
"$SYSTEMCTL_BIN" --user status "${SERVICE_NAME}.service" --no-pager || true

echo ""
echo "To check the service:"
echo "  "$SYSTEMCTL_BIN" --user status $SERVICE_NAME"
echo ""
echo "To view logs:"
echo "  journalctl --user-unit ${SERVICE_NAME}.service -f"
echo ""
echo "To stop the service:"
echo "  "$SYSTEMCTL_BIN" --user stop $SERVICE_NAME"
echo ""
echo "To disable auto-start:"
echo "  "$SYSTEMCTL_BIN" --user disable $SERVICE_NAME"
