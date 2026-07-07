#!/bin/bash
###############################################################################
# Fleet Health Predictor - Cron Script
#
# GitLab Issue: #108
# Purpose: Run predictive health analysis every 5 minutes
# Deploy: Copy to pi-02:/home/claude/bin/fleet-health-predictor-cron.sh
#
# Cron entry (pi-02):
#   */5 * * * * /home/claude/bin/fleet-health-predictor-cron.sh
#
# Logs: /var/log/fleet-health-predictor.log (rotated daily)
###############################################################################

set -euo pipefail

# Configuration
REPO_DIR="/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
LOG_FILE="/var/log/fleet-health-predictor.log"
MAX_LOG_SIZE_MB=100

# Rotate log if too large
if [ -f "$LOG_FILE" ]; then
  LOG_SIZE_MB=$(du -m "$LOG_FILE" | cut -f1)
  if [ "$LOG_SIZE_MB" -gt "$MAX_LOG_SIZE_MB" ]; then
    mv "$LOG_FILE" "$LOG_FILE.$(date +%Y%m%d-%H%M%S)"
    gzip "$LOG_FILE".* 2>/dev/null || true
  fi
fi

# Log header
echo "========================================" | tee -a "$LOG_FILE"
echo "Fleet Health Predictor - $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Change to repo directory
cd "$REPO_DIR" || {
  echo "ERROR: Failed to cd to $REPO_DIR" | tee -a "$LOG_FILE"
  exit 1
}

# Run predictor for all workers
node tools/fleet-health-predictor.js --all 2>&1 | tee -a "$LOG_FILE"

# Exit code preservation
EXIT_CODE=${PIPESTATUS[0]}

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "✅ Prediction completed successfully" | tee -a "$LOG_FILE"
else
  echo "❌ Prediction failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"

exit "$EXIT_CODE"
