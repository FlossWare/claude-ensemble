#!/bin/bash
# Start OrientDB Auto-Sync Daemon

cd /home/sfloess/.claude/learning

# Check if OrientDB REST API is available
if ! curl -sf -o /dev/null --connect-timeout 5 http://aio-01:5000/graph/query -X POST -H 'Content-Type: application/json' -d '{"query": "SELECT 1"}' 2>/dev/null; then
  echo "OrientDB REST API is not available at http://aio-01:5000/graph/query"
  echo "Check that the orchestrator API is running on aio-01"
  exit 1
fi

# Check if daemon is already running
if pgrep -f "auto-sync-daemon.js" > /dev/null; then
  echo "Auto-Sync Daemon already running"
  echo "PID: $(pgrep -f auto-sync-daemon.js)"
  exit 0
fi

# Start daemon in background
echo "Starting Auto-Sync Daemon..."
nohup node auto-sync-daemon.js > auto-sync.log 2>&1 &
PID=$!

sleep 2

if ps -p $PID > /dev/null; then
  echo "Auto-Sync Daemon started (PID: $PID)"
  echo "   Logs: tail -f /home/sfloess/.claude/learning/auto-sync.log"
  echo "   Stop: kill $PID"
else
  echo "Failed to start daemon"
  tail -20 auto-sync.log
  exit 1
fi
