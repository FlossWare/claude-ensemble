#!/bin/bash
#
# Sync codebase from aio-01 to all 8 fleet workers
# Usage: ./scripts/sync-fleet.sh [--dry-run]
#

set -e

WORKERS=(server-01 server-02 server-03 laptop-01 pi-01 pi-02 desktop-ap server-ap)
SOURCE_DIR="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
TARGET_DIR="~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"

# Check for dry-run flag
DRY_RUN=""
if [[ "$1" == "--dry-run" ]]; then
  DRY_RUN="--dry-run"
  echo "🔍 DRY RUN MODE - No files will be modified"
  echo
fi

echo "🚀 Syncing fleet workers from aio-01..."
echo "Source: $SOURCE_DIR"
echo "Workers: ${#WORKERS[@]}"
echo

RSYNC_OPTS="-avz --delete $DRY_RUN \
  --exclude=.git \
  --exclude=node_modules \
  --exclude=.claude \
  --exclude=*.log \
  --exclude=*.output \
  --exclude=/tmp/ \
  --exclude=.env \
  --exclude=package-lock.json"

sync_worker() {
  local worker=$1
  echo "📡 Syncing to $worker..."

  if rsync $RSYNC_OPTS \
    "$SOURCE_DIR/" \
    "claude@$worker:$TARGET_DIR/" 2>&1 | grep -v "sending incremental file list" | grep -v "sent.*received.*bytes/sec" || true; then
    echo "   ✅ $worker synced"
  else
    echo "   ❌ $worker failed"
  fi
  echo
}

# Sync all workers in parallel
for worker in "${WORKERS[@]}"; do
  sync_worker "$worker" &
done

# Wait for all background jobs
wait

echo
echo "✅ Fleet sync complete!"
echo
echo "To verify sync:"
echo "  for w in ${WORKERS[@]}; do ssh claude@\$w 'ls -lh $TARGET_DIR/mcp-servers/fleet-orchestrator/index.js'; done"
