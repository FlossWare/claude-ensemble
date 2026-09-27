#!/bin/bash
# Install RH Thompson Router Service as systemd user service

set -e

REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
SERVICE_FILE="$REPO_ROOT/thompson-service/rh-thompson.service"
SERVICE_NAME="rh-thompson.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file not found at $SERVICE_FILE"
    exit 1
fi

echo "Installing RH Thompson Router Service..."
echo "  Service file: $SERVICE_FILE"
echo "  Repo root: $REPO_ROOT"

# Create systemd user directory
mkdir -p "$HOME/.config/systemd/user"

# Symlink service file
SYMLINK_TARGET="$HOME/.config/systemd/user/$SERVICE_NAME"
if [ -L "$SYMLINK_TARGET" ]; then
    rm "$SYMLINK_TARGET"
fi
ln -sf "$SERVICE_FILE" "$SYMLINK_TARGET"
echo "✓ Symlinked service file to $SYMLINK_TARGET"

# Create socket directory with proper permissions
mkdir -p /tmp
echo "✓ Socket directory ready"

# Reload systemd
systemctl --user daemon-reload
echo "✓ Reloaded systemd"

# Enable service
systemctl --user enable "$SERVICE_NAME"
echo "✓ Enabled service (auto-start on login)"

# Start service
systemctl --user start "$SERVICE_NAME"
echo "✓ Started service"

# Check status
sleep 1
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo "✓ Thompson Router service running successfully"
    echo ""
    echo "Service status:"
    systemctl --user status "$SERVICE_NAME" --no-pager || true
else
    echo ""
    echo "✗ Service failed to start. Check logs:"
    journalctl --user -n 20 -u "$SERVICE_NAME"
    exit 1
fi
