#!/bin/bash
#
# Setup automated model regression monitoring
#
# This script:
# 1. Adds a weekly cron job to run consensus replay analysis
# 2. Creates report directory
# 3. Tests the monitor script
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_SCRIPT="$SCRIPT_DIR/tools/model_regression_monitor.cjs"
REPORT_DIR="/tmp/consensus-replay-reports"
CRON_SCHEDULE="0 2 * * 0"  # Sundays at 2am

echo "Setting up Model Regression Monitor..."

# 1. Create report directory
echo "Creating report directory: $REPORT_DIR"
mkdir -p "$REPORT_DIR"

# 2. Test the monitor script
echo "Testing monitor script..."
if ! node "$MONITOR_SCRIPT" --weeks 1; then
    echo "⚠ Monitor script test failed (this may be expected if no workflows exist)"
    echo "  Continuing with setup..."
fi

# 3. Add cron job
echo "Setting up cron job..."
CRON_CMD="cd $SCRIPT_DIR && node $MONITOR_SCRIPT --weeks 4 --html $REPORT_DIR >> /var/log/model-regression-monitor.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "model_regression_monitor"; then
    echo "✓ Cron job already exists"
else
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_CMD") | crontab -
    echo "✓ Cron job added: $CRON_SCHEDULE"
fi

# 4. Create log file
sudo touch /var/log/model-regression-monitor.log
sudo chown "$USER:$USER" /var/log/model-regression-monitor.log

echo ""
echo "=== Setup Complete ==="
echo "Monitor script: $MONITOR_SCRIPT"
echo "Reports directory: $REPORT_DIR"
echo "Cron schedule: $CRON_SCHEDULE (Sundays at 2am)"
echo "Log file: /var/log/model-regression-monitor.log"
echo ""
echo "To run manually:"
echo "  node $MONITOR_SCRIPT --weeks 4"
echo ""
echo "To view cron jobs:"
echo "  crontab -l"
echo ""
echo "To check logs:"
echo "  tail -f /var/log/model-regression-monitor.log"
