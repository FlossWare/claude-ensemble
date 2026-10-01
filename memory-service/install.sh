#!/usr/bin/env bash
# Install Claude Ensemble Memory Service as a systemd user service.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="claude-memory.service"
SERVICE_TEMPLATE="$REPO_ROOT/memory-service/claude-memory.service.template"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_DIR/$SERVICE_NAME"
if [[ ! -f "$SERVICE_TEMPLATE" ]]; then echo "Error: service template not found: $SERVICE_TEMPLATE" >&2; exit 1; fi
mkdir -p "$SYSTEMD_DIR"
sed "s|%REPO_PATH%|$REPO_ROOT|g" "$SERVICE_TEMPLATE" > "$SERVICE_FILE"
chmod 0644 "$SERVICE_FILE"
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user start "$SERVICE_NAME"
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
  echo "Memory service installed and running: $SERVICE_NAME"
else
  echo "Memory service failed to start. Check: journalctl --user -u $SERVICE_NAME" >&2
  exit 1
fi
