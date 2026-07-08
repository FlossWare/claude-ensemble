#!/bin/bash
#
# Red Hat Compliance Alert Script
#
# Runs compliance check and sends email alert if violations found.
# Intended for cron: 0 */6 * * * (every 6 hours)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Email configuration
ALERT_EMAIL="${REDHAT_COMPLIANCE_ALERT_EMAIL:-sfloess@redhat.com}"
FROM_EMAIL="claude-orchestrator@$(hostname)"
SUBJECT="🚨 Red Hat Compliance Violation Detected"

# Temp file for report
REPORT_FILE="/tmp/redhat-compliance-$(date +%Y%m%d-%H%M%S).txt"

# Run compliance check
echo "Running Red Hat compliance check..."
if node "$PROJECT_DIR/tools/check-redhat-compliance.cjs" 6 > "$REPORT_FILE" 2>&1; then
  # No violations (exit code 0)
  echo "✓ No violations detected"
  rm -f "$REPORT_FILE"
  exit 0
else
  # Violations found (exit code 1)
  echo "✗ Violations detected! Sending alert email..."

  # Send email alert
  if command -v mail &>/dev/null; then
    cat "$REPORT_FILE" | mail -s "$SUBJECT" -r "$FROM_EMAIL" "$ALERT_EMAIL"
    echo "✓ Alert email sent to: $ALERT_EMAIL"
  else
    echo "⚠️  'mail' command not found - cannot send email"
    echo "Install with: sudo dnf install mailx"
    echo ""
    echo "Violations report:"
    cat "$REPORT_FILE"
  fi

  # Log to syslog
  logger -t redhat-compliance "VIOLATION: Red Hat tasks used non-Anthropic models"

  # Keep report file for investigation
  echo "Report saved to: $REPORT_FILE"

  exit 1
fi
