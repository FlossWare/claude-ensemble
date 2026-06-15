#!/bin/bash
# Install Message Polling Daemon as systemd service
#
# Usage:
#   ./install-polling-daemon.sh       # Install and start service
#   ./install-polling-daemon.sh stop  # Stop and disable service
#   ./install-polling-daemon.sh logs  # View logs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="${SCRIPT_DIR}/claude-message-polling.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="claude-message-polling.service"
LOG_DIR="$HOME/.claude/learning/logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored message
print_msg() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
}

# Ensure log directory exists
ensure_log_dir() {
    if [[ ! -d "$LOG_DIR" ]]; then
        print_msg "$YELLOW" "Creating log directory: $LOG_DIR"
        mkdir -p "$LOG_DIR"
    fi
}

# Install service
install_service() {
    print_msg "$GREEN" "========================================="
    print_msg "$GREEN" "Installing Message Polling Daemon"
    print_msg "$GREEN" "========================================="

    # Ensure systemd user directory exists
    if [[ ! -d "$SYSTEMD_DIR" ]]; then
        print_msg "$YELLOW" "Creating systemd user directory: $SYSTEMD_DIR"
        mkdir -p "$SYSTEMD_DIR"
    fi

    # Ensure log directory exists
    ensure_log_dir

    # Copy service file
    print_msg "$YELLOW" "Copying service file to $SYSTEMD_DIR"
    cp "$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_NAME"

    # Reload systemd
    print_msg "$YELLOW" "Reloading systemd daemon"
    systemctl --user daemon-reload

    # Enable service
    print_msg "$YELLOW" "Enabling service"
    systemctl --user enable "$SERVICE_NAME"

    # Start service
    print_msg "$YELLOW" "Starting service"
    systemctl --user start "$SERVICE_NAME"

    # Check status
    sleep 2
    if systemctl --user is-active --quiet "$SERVICE_NAME"; then
        print_msg "$GREEN" "✓ Service started successfully"
        print_msg "$GREEN" ""
        print_msg "$GREEN" "Service Status:"
        systemctl --user status "$SERVICE_NAME" --no-pager | head -n 10
        print_msg "$GREEN" ""
        print_msg "$GREEN" "Useful commands:"
        print_msg "$GREEN" "  systemctl --user status $SERVICE_NAME    # Check status"
        print_msg "$GREEN" "  systemctl --user stop $SERVICE_NAME      # Stop service"
        print_msg "$GREEN" "  systemctl --user restart $SERVICE_NAME   # Restart service"
        print_msg "$GREEN" "  journalctl --user -u $SERVICE_NAME -f    # Follow logs"
        print_msg "$GREEN" "  tail -f $LOG_DIR/message-polling.log     # Follow daemon logs"
    else
        print_msg "$RED" "✗ Service failed to start"
        print_msg "$RED" "Check logs with: journalctl --user -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

# Uninstall service
uninstall_service() {
    print_msg "$YELLOW" "========================================="
    print_msg "$YELLOW" "Uninstalling Message Polling Daemon"
    print_msg "$YELLOW" "========================================="

    # Stop service
    if systemctl --user is-active --quiet "$SERVICE_NAME"; then
        print_msg "$YELLOW" "Stopping service"
        systemctl --user stop "$SERVICE_NAME"
    fi

    # Disable service
    if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        print_msg "$YELLOW" "Disabling service"
        systemctl --user disable "$SERVICE_NAME"
    fi

    # Remove service file
    if [[ -f "$SYSTEMD_DIR/$SERVICE_NAME" ]]; then
        print_msg "$YELLOW" "Removing service file"
        rm "$SYSTEMD_DIR/$SERVICE_NAME"
    fi

    # Reload systemd
    print_msg "$YELLOW" "Reloading systemd daemon"
    systemctl --user daemon-reload

    print_msg "$GREEN" "✓ Service uninstalled successfully"
}

# View logs
view_logs() {
    print_msg "$GREEN" "Viewing daemon logs (Ctrl+C to exit)"
    print_msg "$GREEN" "========================================="
    tail -f "$LOG_DIR/message-polling.log"
}

# Main
case "${1:-install}" in
    install)
        install_service
        ;;
    uninstall|remove|stop)
        uninstall_service
        ;;
    logs)
        view_logs
        ;;
    status)
        systemctl --user status "$SERVICE_NAME" --no-pager
        ;;
    restart)
        print_msg "$YELLOW" "Restarting service"
        systemctl --user restart "$SERVICE_NAME"
        sleep 2
        systemctl --user status "$SERVICE_NAME" --no-pager | head -n 10
        ;;
    *)
        print_msg "$RED" "Usage: $0 {install|uninstall|logs|status|restart}"
        exit 1
        ;;
esac
