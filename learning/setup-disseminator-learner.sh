#!/bin/bash
#
# Setup script for Disseminator Autonomous Learning System
#
# This script sets up the systemd service for continuous learning
# or creates a cron job for periodic execution.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="disseminator-learner.service"
SERVICE_DEST="/etc/systemd/system/$SERVICE_FILE"

echo "═══════════════════════════════════════════════════════════════════════"
echo "  Disseminator Autonomous Learning System - Setup"
echo "═══════════════════════════════════════════════════════════════════════"
echo

# Check if running as root for systemd service
if [ "$1" == "systemd" ]; then
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  Systemd service installation requires root privileges."
        echo "   Please run: sudo $0 systemd"
        exit 1
    fi

    echo "📦 Installing systemd service..."
    cp "$SCRIPT_DIR/$SERVICE_FILE" "$SERVICE_DEST"

    echo "🔄 Reloading systemd daemon..."
    systemctl daemon-reload

    echo "✅ Enabling service to start on boot..."
    systemctl enable disseminator-learner

    echo "🚀 Starting service..."
    systemctl start disseminator-learner

    echo
    echo "✅ Systemd service installed successfully!"
    echo
    echo "Useful commands:"
    echo "  sudo systemctl status disseminator-learner    # Check status"
    echo "  sudo systemctl stop disseminator-learner      # Stop service"
    echo "  sudo systemctl restart disseminator-learner   # Restart service"
    echo "  sudo journalctl -u disseminator-learner -f    # Follow logs"
    echo "  tail -f ~/.claude/learning/logs/disseminator-learner.log"
    echo

elif [ "$1" == "cron" ]; then
    echo "⏰ Setting up cron job..."
    echo

    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "disseminator-learner.js --incremental"; then
        echo "ℹ️  Cron job already exists. Skipping..."
    else
        # Add cron job to run every hour
        (crontab -l 2>/dev/null; echo "# Disseminator Autonomous Learning System - Run every hour") | crontab -
        (crontab -l 2>/dev/null; echo "7 * * * * cd $SCRIPT_DIR && node disseminator-learner.js --incremental >> logs/disseminator-learner.log 2>&1") | crontab -

        echo "✅ Cron job added successfully!"
        echo
        echo "The learner will run every hour at :07 past the hour."
        echo "Logs: $SCRIPT_DIR/logs/disseminator-learner.log"
    fi
    echo
    echo "View cron jobs: crontab -l"
    echo "Remove cron job: crontab -e (then delete the disseminator line)"
    echo

elif [ "$1" == "manual" ]; then
    echo "📖 Manual setup instructions:"
    echo
    echo "1. Initial extraction (one-time):"
    echo "   cd $SCRIPT_DIR"
    echo "   node disseminator-learner.js --initial-run"
    echo
    echo "2. Incremental processing (run periodically):"
    echo "   cd $SCRIPT_DIR"
    echo "   node disseminator-learner.js --incremental"
    echo
    echo "3. View status:"
    echo "   node disseminator-status.js"
    echo
    echo "4. Search knowledge:"
    echo "   node disseminator-search.js \"your query\""
    echo

elif [ "$1" == "uninstall" ]; then
    echo "🗑️  Uninstalling..."
    echo

    # Remove systemd service
    if [ -f "$SERVICE_DEST" ]; then
        if [ "$EUID" -ne 0 ]; then
            echo "⚠️  Root privileges required to remove systemd service."
            echo "   Run: sudo $0 uninstall"
        else
            systemctl stop disseminator-learner 2>/dev/null || true
            systemctl disable disseminator-learner 2>/dev/null || true
            rm -f "$SERVICE_DEST"
            systemctl daemon-reload
            echo "✅ Systemd service removed"
        fi
    fi

    # Remove cron job
    if crontab -l 2>/dev/null | grep -q "disseminator-learner.js"; then
        crontab -l 2>/dev/null | grep -v "disseminator-learner" | crontab -
        echo "✅ Cron job removed"
    fi

    echo
    echo "⚠️  Note: Data files are preserved in:"
    echo "   $SCRIPT_DIR/disseminator-knowledge.jsonl"
    echo "   $SCRIPT_DIR/disseminator-vectors.jsonl"
    echo "   $SCRIPT_DIR/disseminator-learner-state.json"
    echo
    echo "To remove all data: rm -f $SCRIPT_DIR/disseminator-*"
    echo

else
    echo "Usage: $0 {systemd|cron|manual|uninstall}"
    echo
    echo "Options:"
    echo "  systemd    Install as systemd service (requires sudo)"
    echo "  cron       Install as hourly cron job"
    echo "  manual     Show manual setup instructions"
    echo "  uninstall  Remove service/cron job (requires sudo for systemd)"
    echo
    echo "Examples:"
    echo "  sudo $0 systemd      # Install as systemd service"
    echo "  $0 cron              # Install as cron job"
    echo "  $0 manual            # Show manual instructions"
    echo
    exit 1
fi

echo "═══════════════════════════════════════════════════════════════════════"
echo "  Setup complete!"
echo "═══════════════════════════════════════════════════════════════════════"
