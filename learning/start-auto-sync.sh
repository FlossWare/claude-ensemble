#!/bin/bash
# Start Neo4j Auto-Sync Daemon

cd /home/sfloess/.claude/learning

# Check if Neo4j is running
if ! nc -z laptop-01 7687 2>/dev/null; then
  echo "❌ Neo4j is not running on laptop-01:7687"
  echo "Start Neo4j first: sudo systemctl start neo4j"
  exit 1
fi

# Check if daemon is already running
if pgrep -f "auto-sync-daemon.js" > /dev/null; then
  echo "⚠️  Auto-Sync Daemon already running"
  echo "PID: $(pgrep -f auto-sync-daemon.js)"
  exit 0
fi

# Install neo4j-driver if not present
if ! node -e "require('neo4j-driver')" 2>/dev/null; then
  echo "📦 Installing neo4j-driver..."
  npm install neo4j-driver
fi

# Start daemon in background
echo "🚀 Starting Auto-Sync Daemon..."
nohup node auto-sync-daemon.js > auto-sync.log 2>&1 &
PID=$!

sleep 2

if ps -p $PID > /dev/null; then
  echo "✅ Auto-Sync Daemon started (PID: $PID)"
  echo "   Logs: tail -f /home/sfloess/.claude/learning/auto-sync.log"
  echo "   Stop: kill $PID"
else
  echo "❌ Failed to start daemon"
  tail -20 auto-sync.log
  exit 1
fi
